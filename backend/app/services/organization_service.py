"""
PATHS Backend — Organisation service.

Handles member management operations scoped to an organisation.

fix8&9 Update 2 — Invite Flow:
  * New rows always start as ``status='pending'`` and capture
    ``invited_at`` + ``invited_by_user_id``.
  * After insertion we attempt to send the invitation email via the shared
    :pymod:`app.services.email_service` (SMTP, with a no-op dev fallback).
  * Email failure does NOT roll back the invite — the inviter still sees
    the row in the Members tab and can resend later.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.application import OrganizationMember
from app.db.models.user import User
from app.repositories.organization_repo import OrganizationRepository
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.organization import CreateMemberRequest, CreateMemberResponse
from app.services.email_service import send_organization_invite_email

logger = logging.getLogger(__name__)
settings = get_settings()


def invite_is_expired(member: OrganizationMember, *, now: datetime | None = None) -> bool:
    """True when a pending invite was never logged into within the grace window."""
    if member.status != "pending" or getattr(member, "first_login_at", None) is not None:
        return False
    invited_at = getattr(member, "invited_at", None)
    if invited_at is None:
        return False
    if invited_at.tzinfo is None:
        invited_at = invited_at.replace(tzinfo=timezone.utc)
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(
        days=max(0, int(settings.member_invite_grace_days)),
    )
    return invited_at < cutoff


def expire_stale_pending_invites(
    db: Session, *, organization_id: uuid.UUID | None = None,
) -> int:
    """Auto-expire pending invites past the grace window to ``inactive``.

    Idempotent and cheap — call it lazily before listing members so the
    Members tab always reflects the 2-day rule even when the background
    scheduler is disabled. Returns the number of rows expired.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(0, int(settings.member_invite_grace_days)))
    q = select(OrganizationMember).where(
        OrganizationMember.status == "pending",
        OrganizationMember.first_login_at.is_(None),
        OrganizationMember.invited_at.is_not(None),
        OrganizationMember.invited_at < cutoff,
    )
    if organization_id is not None:
        q = q.where(OrganizationMember.organization_id == organization_id)
    rows = db.execute(q).scalars().all()
    if not rows:
        return 0
    for m in rows:
        m.status = "inactive"
        m.is_active = False
    db.commit()
    logger.info(
        "[organization_service] expired %d stale pending invite(s)", len(rows),
    )
    return len(rows)


def create_member(
    db: Session,
    organization_id: uuid.UUID,
    data: CreateMemberRequest,
    current_user: User,
) -> CreateMemberResponse:
    """Create a new organisation member.  Only callable by org_admin.

    The new member starts as ``status='pending'``. The first successful
    login flips them to ``status='active'`` (handled in ``auth_service``).
    """
    user_repo = UserRepository(db)
    org_repo = OrganizationRepository(db)
    role_repo = RoleRepository(db)

    # Ensure org exists
    org = org_repo.get_by_id(organization_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found",
        )

    # ── Resolve the target user ────────────────────────────────────
    # The invite flow has three live cases:
    #   (a) Brand-new email → create a fresh organization_member user.
    #   (b) Email already exists, active in *this* org → reject (409).
    #   (c) Email already exists, pending in *this* org → idempotent
    #       re-invite (reset password, refresh timestamps, resend email).
    #   (d) Email already exists as an organization_member with NO
    #       membership in this org → reuse the user and create a new
    #       pending membership. The temporary password resets so the
    #       email body still contains valid credentials.
    #   (e) Email exists as a different account type (candidate /
    #       platform_admin) → refuse with a clear, actionable error.
    existing_user = user_repo.get_by_email(data.email)
    existing_membership = None
    if existing_user is not None:
        existing_membership = next(
            (
                m
                for m in (existing_user.memberships or [])
                if m.organization_id == organization_id
            ),
            None,
        )
        if existing_membership is not None and existing_membership.status == "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"{data.email} is already an active member of this organisation."
                ),
            )
        # Block cross-account-type collisions with a useful message.
        if (
            existing_membership is None
            and existing_user.account_type
            and existing_user.account_type != "organization_member"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"{data.email} is already registered on PATHS as a "
                    f"'{existing_user.account_type}' account. Use a different "
                    "email, or ask the existing user to sign in directly."
                ),
            )

    if existing_user is None:
        # Case (a): fresh user.
        target_user = user_repo.create_user(
            email=data.email,
            full_name=data.full_name,
            plain_password=data.password,
            account_type="organization_member",
        )
    else:
        # Case (c) and (d): reuse the user record. We always update the
        # temporary password so the email body has working credentials —
        # the user is free to change it on first login.
        target_user = existing_user
        if data.full_name and not (target_user.full_name or "").strip():
            target_user.full_name = data.full_name
        user_repo.update_password(target_user, data.password)

    if existing_membership is None:
        membership = role_repo.create_membership(
            user_id=target_user.id,
            organization_id=organization_id,
            role_code=data.role_code,
        )
    else:
        # Case (c): refresh the existing pending row.
        membership = existing_membership
        membership.role_code = data.role_code

    # Set / reset invite lifecycle fields.
    membership.status = "pending"
    membership.is_active = True  # the user CAN log in (which then activates)
    membership.invited_at = datetime.now(timezone.utc)
    membership.invited_by_user_id = current_user.id
    membership.activated_at = None
    membership.first_login_at = None

    db.commit()
    db.refresh(target_user)
    db.refresh(membership)
    new_user = target_user

    # ── Send invitation email (non-fatal) ──────────────────────────
    try:
        send_result = send_organization_invite_email(
            to=new_user.email,
            invited_member_name=new_user.full_name or new_user.email,
            inviter_name=(current_user.full_name or current_user.email),
            inviter_email=current_user.email,
            organization_name=org.name,
            temporary_password=data.password,
            login_url=settings.outreach_public_base_url
            + "/login" if settings.outreach_public_base_url else None,
        )
        if not send_result.get("ok"):
            logger.warning(
                "[organization_service] invite email failed for %s: %s",
                new_user.email, send_result.get("error", "unknown"),
            )
    except Exception as exc:  # noqa: BLE001
        # Never let an email failure undo a successful invite — the row
        # exists and HR can manually resend later.
        logger.warning(
            "[organization_service] invite email crashed for %s: %s",
            new_user.email, str(exc)[:200],
        )

    return CreateMemberResponse(
        member_id=membership.id,
        user_id=new_user.id,
        organization_id=organization_id,
        role_code=membership.role_code,
        status=membership.status,
        invited_at=membership.invited_at,
    )


# ── Resend invite ───────────────────────────────────────────────────────────


def resend_invite_email(
    db: Session,
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    current_user: User,
    *,
    temporary_password: str | None = None,
) -> dict[str, object]:
    """Resend the invitation email for a pending member.

    If ``temporary_password`` is provided, also reset the user's password to
    match. Otherwise the email is sent without a credential block — useful
    when the inviter just wants to re-prompt the user.
    """
    membership = db.get(OrganizationMember, membership_id)
    if membership is None or membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Member not found")
    # Allow resending for still-pending invites AND for invites that already
    # expired to 'inactive' (re-invite restarts the grace window). An active
    # member doesn't need an invite.
    if membership.status not in ("pending", "inactive"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resend invite — current status: {membership.status}",
        )

    user_repo = UserRepository(db)
    user = db.get(User, membership.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if temporary_password:
        if len(temporary_password) < 8:
            raise HTTPException(status_code=400, detail="Temporary password too short")
        user_repo.update_password(user, temporary_password)

    # Restart the invite lifecycle so the 2-day grace window applies afresh.
    membership.status = "pending"
    membership.is_active = True
    membership.invited_at = datetime.now(timezone.utc)
    membership.invited_by_user_id = current_user.id
    membership.first_login_at = None
    membership.activated_at = None

    org_repo = OrganizationRepository(db)
    org = org_repo.get_by_id(organization_id)
    org_name = org.name if org else "your organisation"

    send_result = send_organization_invite_email(
        to=user.email,
        invited_member_name=user.full_name or user.email,
        inviter_name=(current_user.full_name or current_user.email),
        inviter_email=current_user.email,
        organization_name=org_name,
        temporary_password=temporary_password or "(unchanged)",
        login_url=settings.outreach_public_base_url
        + "/login" if settings.outreach_public_base_url else None,
    )
    db.commit()
    return {"ok": bool(send_result.get("ok")), "provider": send_result.get("provider")}
