"""
PATHS Backend — Authentication service.

Orchestrates candidate registration, organisation onboarding, login,
and the /me context builder.

Platform-admin overhaul (changed in this revision):
  - Public registration paths CANNOT create platform_admin accounts. Both
    register_candidate and register_organization hard-code account_type
    server-side and ignore any body fields that try to override it.
  - register_organization now creates the organisation in PENDING_APPROVAL
    state, deactivates the requester's membership, AND opens a row in
    organization_access_requests. Login is permitted but every org-scoped
    endpoint refuses access until a platform admin approves the request.
  - Login and /auth/me return organization.status so the frontend can route
    pending users to /pending-approval and rejected users to /rejected.
  - is_platform_admin flag and a permissions[] list are surfaced for the
    frontend to gate UI without re-deriving role.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import AccountType, OrgRole
from app.core.security import create_access_token, hash_password, needs_rehash, verify_password
from app.db.models.organization import (
    Organization,
    OrganizationAccessRequest,
    OrganizationAccessRequestStatus,
    OrganizationStatus,
)
from app.db.repositories.sync_status import write_audit_log
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.organization_repo import OrganizationRepository
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    CandidateProfileSummary,
    CandidateRegisterRequest,
    CandidateRegisterResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
    OrganizationContext,
    OrganizationRegisterRequest,
    OrganizationRegisterResponse,
    UserSummary,
)


# ── Permissions ──────────────────────────────────────────────────────────

# Permission strings the frontend uses to gate UI. Backend never trusts these
# from the request — endpoints always check role_code/account_type directly.
PERMISSIONS_BY_ROLE: dict[str, list[str]] = {
    OrgRole.ORG_ADMIN.value: [
        "org.manage_members",
        "org.manage_settings",
        "org.create_jobs",
        "org.view_audit",
        "org.view_applications",
        "org.run_screening",
    ],
    OrgRole.HIRING_MANAGER.value: [
        "org.create_jobs",
        "org.view_applications",
        "org.run_screening",
    ],
    OrgRole.RECRUITER.value: [
        "org.create_jobs",
        "org.view_applications",
        "org.run_screening",
    ],
    OrgRole.HR.value: [
        "org.view_applications",
        "org.run_screening",
    ],
    OrgRole.INTERVIEWER.value: [
        "org.view_assigned_interviews",
    ],
    # Legacy values — preserved for users who still hold them.
    "hr_manager": [
        "org.view_applications",
        "org.run_screening",
    ],
    "admin": [
        "org.manage_members",
        "org.manage_settings",
        "org.create_jobs",
        "org.view_audit",
        "org.view_applications",
        "org.run_screening",
    ],
}

PLATFORM_ADMIN_PERMISSIONS = [
    "platform.approve_organizations",
    "platform.suspend_organizations",
    "platform.view_all_organizations",
    "platform.view_all_users",
    "platform.view_audit",
]


def _permissions_for(user, membership_role_code: str | None) -> list[str]:
    if user.account_type == AccountType.PLATFORM_ADMIN.value:
        return list(PLATFORM_ADMIN_PERMISSIONS)
    if user.account_type == AccountType.CANDIDATE.value:
        return ["candidate.view_jobs", "candidate.apply_to_jobs", "candidate.edit_profile"]
    if user.account_type == AccountType.ORGANIZATION_MEMBER.value and membership_role_code:
        return list(PERMISSIONS_BY_ROLE.get(membership_role_code, []))
    return []


# ── Candidate Registration ────────────────────────────────────────────────

def register_candidate(db: Session, data: CandidateRegisterRequest) -> CandidateRegisterResponse:
    user_repo = UserRepository(db)
    cand_repo = CandidateRepository(db)

    if user_repo.get_by_email(data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # account_type is hard-coded — schema does not accept it from the body,
    # but we set it explicitly here as a second layer of defence.
    user = user_repo.create_user(
        email=data.email,
        full_name=data.full_name,
        plain_password=data.password,
        account_type=AccountType.CANDIDATE.value,
    )

    profile = cand_repo.create_profile(
        user_id=user.id,
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        location=data.location,
        headline=data.headline,
    )

    write_audit_log(
        db,
        action="auth.register.candidate",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        new_value={"email": user.email, "account_type": user.account_type},
    )

    db.commit()
    db.refresh(user)
    db.refresh(profile)

    return CandidateRegisterResponse(
        user_id=user.id,
        candidate_profile_id=profile.id,
        account_type=user.account_type,
        message="Candidate registered successfully",
    )


# ── Organisation Registration ─────────────────────────────────────────────

def _organization_industry_snapshot(data: OrganizationRegisterRequest) -> str | None:
    """Pack signup metadata into ``organizations.industry`` (single string, max 255) — no new columns."""
    main = (data.industry or "").strip() or None
    bits: list[str] = []
    if data.company_type and (ct := data.company_type.strip()):
        bits.append(f"type:{ct[:60]}")
    if data.company_size and (s := data.company_size.strip()):
        bits.append(f"size:{s[:40]}")
    if data.company_website and (w := data.company_website.strip()):
        bits.append(f"url:{w[:80]}")
    if data.first_admin_job_title and (t := data.first_admin_job_title.strip()):
        bits.append(f"role:{t[:50]}")
    if data.first_admin_phone and (p := data.first_admin_phone.strip()):
        bits.append(f"phone:{p[:24]}")
    if not main and not bits:
        return None
    if bits:
        tail = "[" + ";".join(bits) + "]"
        if main:
            return f"{main} {tail}"[:255]
        return tail[:255]
    return main[:255] if main else None


def register_organization(
    db: Session, data: OrganizationRegisterRequest
) -> OrganizationRegisterResponse:
    """Create a PENDING_APPROVAL organisation + access request.

    The user account is created (so they can log in to /pending-approval),
    but the org is_active flag is False and status is PENDING_APPROVAL until
    a platform admin approves the access request. The user's membership is
    also created with is_active=False.
    """
    user_repo = UserRepository(db)
    org_repo = OrganizationRepository(db)
    role_repo = RoleRepository(db)

    if org_repo.get_by_slug(data.organization_slug):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organisation with this slug already exists",
        )
    if user_repo.get_by_email(data.first_admin_email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with the admin email already exists",
        )

    # Create the org row. The repo defaults is_active=True, but we override
    # the status flags right after — single transaction, no commit yet.
    org = org_repo.create_organization(
        name=data.organization_name,
        slug=data.organization_slug,
        industry=(data.industry or "").strip() or None,
        contact_email=data.organization_email or str(data.first_admin_email),
    )
    # Store the rest in their own columns (no more cramming into `industry`).
    org.website = (data.company_website or "").strip() or None
    org.company_size = (data.company_size or "").strip() or None
    org.company_type = (data.company_type or "").strip() or None
    org.status = OrganizationStatus.PENDING_APPROVAL.value
    org.is_active = False  # legacy mirror — keeps legacy code paths consistent

    # account_type is hard-coded server-side. The schema does not accept
    # account_type from the body either, so this is a second layer of
    # defence against privilege escalation via signup.
    admin_user = user_repo.create_user(
        email=data.first_admin_email,
        full_name=data.first_admin_full_name,
        plain_password=data.first_admin_password,
        account_type=AccountType.ORGANIZATION_MEMBER.value,
    )

    membership = role_repo.create_membership(
        user_id=admin_user.id,
        organization_id=org.id,
        role_code=OrgRole.ORG_ADMIN.value,
    )
    # The membership stays inactive until approval. The user can still log in
    # because the User row itself is is_active=True; they just can't operate
    # in the org workspace yet.
    membership.is_active = False

    request = OrganizationAccessRequest(
        organization_id=org.id,
        requester_user_id=admin_user.id,
        status=OrganizationAccessRequestStatus.PENDING.value,
        contact_role=data.first_admin_job_title,
        contact_phone=data.first_admin_phone,
    )
    db.add(request)

    write_audit_log(
        db,
        action="auth.register.organization",
        entity_type="organization",
        entity_id=org.id,
        actor_user_id=admin_user.id,
        new_value={
            "name": org.name,
            "slug": org.slug,
            "status": org.status,
            "requester_email": admin_user.email,
        },
    )

    db.commit()
    db.refresh(org)
    db.refresh(admin_user)

    return OrganizationRegisterResponse(
        organization_id=org.id,
        user_id=admin_user.id,
        role_code=OrgRole.ORG_ADMIN.value,
        message=(
            "Your company access request has been submitted. A platform admin "
            "will review it shortly. You can sign in to view the status."
        ),
    )


# ── Helpers ───────────────────────────────────────────────────────────────

def _is_platform_admin(user) -> bool:
    return user.account_type == AccountType.PLATFORM_ADMIN.value


def _build_org_context(db: Session, user) -> OrganizationContext | None:
    """Fetch the user's primary membership AND the parent org status.

    Returns None for non-org-member accounts. Returns a context even for
    pending/rejected/suspended orgs so the frontend can route correctly.
    """
    if user.account_type != AccountType.ORGANIZATION_MEMBER.value:
        return None
    role_repo = RoleRepository(db)
    memberships = role_repo.get_user_memberships(user.id, include_inactive=True)
    if not memberships:
        return None
    m = memberships[0]
    org = m.organization or db.get(Organization, m.organization_id)
    return OrganizationContext(
        organization_id=m.organization_id,
        organization_name=org.name if org else "",
        role_code=m.role_code,
        status=(org.status if org else OrganizationStatus.SUSPENDED.value),
    )


# ── Login ─────────────────────────────────────────────────────────────────

def _activate_pending_memberships_on_first_login(db: Session, user) -> None:
    """Flip pending memberships → active on first successful login.

    Safe to call on every login: it only updates rows whose ``status`` is
    still ``'pending'``. ``first_login_at`` is only set on the very first
    login; ``activated_at`` is set on the same call.
    """
    from datetime import datetime, timezone as _tz  # local to keep top imports clean

    from app.db.models.application import OrganizationMember

    now = datetime.now(_tz.utc)
    rows = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.status == "pending",
        )
    ).scalars().all()
    if not rows:
        # Stamp first_login_at on the user / membership the first time even
        # for non-pending users, but only if previously null. We use the
        # membership row(s) so the field stays scoped to org context.
        for m in (user.memberships or []):
            if getattr(m, "first_login_at", None) is None:
                m.first_login_at = now
                db.add(m)
        return
    from app.services.organization_service import invite_is_expired

    for m in rows:
        if invite_is_expired(m, now=now):
            # The invite's grace window elapsed before this first sign-in —
            # expire the membership instead of activating it.
            m.status = "inactive"
            m.is_active = False
            db.add(m)
            continue
        m.status = "active"
        m.activated_at = now
        if getattr(m, "first_login_at", None) is None:
            m.first_login_at = now
        m.is_active = True
        db.add(m)


def login(db: Session, data: LoginRequest) -> LoginResponse:
    user_repo = UserRepository(db)

    user = user_repo.get_by_email(data.email)

    if user is None or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Progressive rehash: upgrade bcrypt → argon2id on successful login (PATHS-170)
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(data.password)

    # fix8&9 Update 2 — activate any pending org membership on first
    # successful login. Stamps ``first_login_at`` and ``activated_at`` so
    # the Members tab can show the correct lifecycle.
    _activate_pending_memberships_on_first_login(db, user)

    # Build JWT claims
    claims: dict = {
        "sub": user.email,
        "account_type": user.account_type,
        "is_platform_admin": _is_platform_admin(user),
    }
    org_context = _build_org_context(db, user)
    if org_context is not None:
        claims["organization_id"] = str(org_context.organization_id)
        claims["role_code"] = org_context.role_code
        claims["organization_status"] = org_context.status

    token = create_access_token(claims)

    write_audit_log(
        db,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        new_value={"account_type": user.account_type},
    )
    db.commit()

    return LoginResponse(
        access_token=token,
        user=UserSummary(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            account_type=user.account_type,
            organization=org_context,
            is_platform_admin=_is_platform_admin(user),
        ),
    )


# ── /auth/me Context Builder ─────────────────────────────────────────────

def get_me_context(db: Session, user) -> MeResponse:
    """Build the full user context for GET /auth/me."""
    candidate_profile: CandidateProfileSummary | None = None
    org_context: OrganizationContext | None = None

    if user.account_type == AccountType.CANDIDATE.value and user.candidate_profile:
        p = user.candidate_profile
        candidate_profile = CandidateProfileSummary(
            id=p.id,
            phone=p.phone,
            location=p.location_text,
            headline=p.headline,
            years_experience=p.years_experience,
            career_level=p.career_level,
            skills=list(p.skills or []),
            open_to_job_types=list(p.open_to_job_types or []),
            open_to_workplace_settings=list(p.open_to_workplace_settings or []),
            desired_job_titles=list(p.desired_job_titles or []),
            desired_job_categories=list(p.desired_job_categories or []),
        )

    if user.account_type == AccountType.ORGANIZATION_MEMBER.value:
        org_context = _build_org_context(db, user)

    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        account_type=user.account_type,
        is_active=user.is_active,
        is_platform_admin=_is_platform_admin(user),
        candidate_profile=candidate_profile,
        organization=org_context,
        permissions=_permissions_for(user, org_context.role_code if org_context else None),
    )
