"""
PATHS Backend — Platform admin API surface.

Mounted under /api/v1/admin/* via app.main. Every route requires
account_type='platform_admin' (enforced at the router level).

Endpoints:
  GET  /admin/organization-requests            — list pending/approved/rejected requests
  GET  /admin/organization-requests/{id}       — request detail
  POST /admin/organization-requests/{id}/approve  — approve (status=active)
  POST /admin/organization-requests/{id}/reject   — reject (with reason)
  GET  /admin/organizations                    — list ALL organizations (any status)
  POST /admin/organizations/{id}/suspend       — operator-driven suspension
  POST /admin/organizations/{id}/unsuspend
  GET  /admin/organizations/{id}               — full org dossier
  POST /admin/organizations/{id}/impersonate   — short-lived impersonation JWT
  GET  /admin/users                            — list all users (paged, filtered)
  PUT  /admin/users/{id}/suspend               — suspend / unsuspend user
  POST /admin/users/{id}/impersonate           — impersonate user
  GET  /admin/audit                            — recent audit_logs
  GET  /admin/dashboard-stats                  — counts for the admin home page
  GET  /admin/stats                            — richer platform totals
  GET  /admin/agent-runs                       — cross-org agent runs
  POST /admin/agent-runs/{id}/retry            — requeue failed run
  GET  /admin/system-health                    — Postgres/AGE/Qdrant/Ollama probes
  GET  /admin/feature-flags                    — list all feature flags
  POST /admin/feature-flags                    — create feature flag
  PUT  /admin/feature-flags/{id}               — update flag (toggle enabled)
  POST /admin/feature-flags/{id}/org-override  — upsert per-org override
  GET  /admin/settings                         — platform settings
  PUT  /admin/settings                         — update platform settings

PATHS-142–148 (Phase 7 — Admin & Owner Portals)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_platform_admin
from app.core.rbac import AccountType
from app.core.security import create_access_token
from app.db.models.admin_platform import (
    Announcement,
    FeatureFlag,
    FeatureFlagOverride,
    ImpersonationSession,
    PlatformSettings,
)
from app.db.models.agent_runs import AgentRun
from app.db.models.application import OrganizationMember
from app.db.models.billing import Subscription
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.db.models.organization import (
    Organization,
    OrganizationAccessRequest,
    OrganizationAccessRequestStatus,
    OrganizationStatus,
)
from app.db.models.sync import AuditLog
from app.db.models.user import User
from app.db.repositories.sync_status import write_audit_log
from app.services.org_health import compute_org_health


router = APIRouter(
    prefix="/admin",
    tags=["Platform admin"],
    dependencies=[Depends(require_platform_admin)],
)


# ── Schemas ───────────────────────────────────────────────────────────────


class OrgRequestRow(BaseModel):
    id: UUID
    organization_id: UUID
    organization_name: str
    organization_slug: str
    requester_user_id: UUID
    requester_name: str
    requester_email: str
    contact_role: str | None = None
    contact_phone: str | None = None
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None


class OrgRequestDetail(OrgRequestRow):
    organization_industry: str | None = None
    organization_contact_email: str | None = None
    additional_info: str | None = None


class RejectRequestBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)


class SuspendOrgBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)


class OrgRow(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    is_active: bool
    industry: str | None = None
    contact_email: str | None = None
    member_count: int
    created_at: datetime


class UserRow(BaseModel):
    id: UUID
    email: str
    full_name: str
    account_type: str
    is_active: bool
    created_at: datetime


class AuditRow(BaseModel):
    id: UUID
    action: str
    entity_type: str
    entity_id: UUID | None
    actor_user_id: UUID | None
    created_at: datetime


class DashboardStats(BaseModel):
    pending_requests: int
    approved_requests: int
    rejected_requests: int
    total_organizations: int
    active_organizations: int
    suspended_organizations: int
    total_users: int
    candidates: int
    organization_members: int
    platform_admins: int


# ── Helpers ───────────────────────────────────────────────────────────────


def _row_to_request(req: OrganizationAccessRequest, org: Organization, user: User) -> OrgRequestRow:
    return OrgRequestRow(
        id=req.id,
        organization_id=req.organization_id,
        organization_name=org.name,
        organization_slug=org.slug,
        requester_user_id=req.requester_user_id,
        requester_name=user.full_name,
        requester_email=user.email,
        contact_role=req.contact_role,
        contact_phone=req.contact_phone,
        status=req.status,
        submitted_at=req.submitted_at,
        reviewed_at=req.reviewed_at,
        rejection_reason=req.rejection_reason,
    )


def _load_request(db: Session, request_id: UUID) -> tuple[OrganizationAccessRequest, Organization, User]:
    req = db.get(OrganizationAccessRequest, request_id)
    if req is None:
        raise HTTPException(404, detail="organization_access_request_not_found")
    org = db.get(Organization, req.organization_id)
    user = db.get(User, req.requester_user_id)
    if org is None or user is None:
        raise HTTPException(500, detail="orphaned_access_request")
    return req, org, user


# ── Org request endpoints ─────────────────────────────────────────────────


@router.get("/organization-requests", response_model=list[OrgRequestRow])
def list_organization_requests(
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None, description="Match against org name/slug or requester email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[OrgRequestRow]:
    """List access requests, newest first, optionally filtered by status / search."""
    stmt = select(OrganizationAccessRequest, Organization, User).join(
        Organization, Organization.id == OrganizationAccessRequest.organization_id,
    ).join(
        User, User.id == OrganizationAccessRequest.requester_user_id,
    ).order_by(OrganizationAccessRequest.submitted_at.desc())

    if status_filter:
        stmt = stmt.where(OrganizationAccessRequest.status == status_filter)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Organization.name).like(like),
                func.lower(Organization.slug).like(like),
                func.lower(User.email).like(like),
                func.lower(User.full_name).like(like),
            )
        )

    rows = db.execute(stmt.limit(limit).offset(offset)).all()
    return [_row_to_request(req, org, user) for req, org, user in rows]


@router.get("/organization-requests/{request_id}", response_model=OrgRequestDetail)
def get_organization_request(
    request_id: UUID, db: Session = Depends(get_db),
) -> OrgRequestDetail:
    req, org, user = _load_request(db, request_id)
    base = _row_to_request(req, org, user)
    return OrgRequestDetail(
        **base.model_dump(),
        organization_industry=org.industry,
        organization_contact_email=org.contact_email,
        additional_info=req.additional_info,
    )


@router.post("/organization-requests/{request_id}/approve", response_model=OrgRequestDetail)
def approve_organization_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    """Flip the org to ACTIVE and reactivate the requester's membership."""
    req, org, user = _load_request(db, request_id)

    if req.status != OrganizationAccessRequestStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"request is already {req.status}, cannot approve",
        )

    now = datetime.now(timezone.utc)
    old_org_status = org.status

    org.status = OrganizationStatus.ACTIVE.value
    org.is_active = True
    org.approved_by_admin_id = admin.id
    org.approved_at = now
    # If they were previously rejected/suspended, clear those fields.
    org.rejected_by_admin_id = None
    org.rejected_at = None
    org.rejection_reason = None

    # Reactivate the requester's membership(s) for this org.
    memberships = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == user.id,
        )
    ).scalars().all()
    for m in memberships:
        m.is_active = True

    req.status = OrganizationAccessRequestStatus.APPROVED.value
    req.reviewed_by_admin_id = admin.id
    req.reviewed_at = now

    write_audit_log(
        db,
        action="org.access_request.approve",
        entity_type="organization",
        entity_id=org.id,
        actor_user_id=admin.id,
        old_value={"status": old_org_status},
        new_value={
            "status": org.status,
            "request_id": str(req.id),
            "requester_email": user.email,
        },
    )
    db.commit()

    db.refresh(req)
    db.refresh(org)
    db.refresh(user)
    base = _row_to_request(req, org, user)
    return OrgRequestDetail(
        **base.model_dump(),
        organization_industry=org.industry,
        organization_contact_email=org.contact_email,
        additional_info=req.additional_info,
    )


@router.post("/organization-requests/{request_id}/reject", response_model=OrgRequestDetail)
def reject_organization_request(
    request_id: UUID,
    body: RejectRequestBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    req, org, user = _load_request(db, request_id)

    if req.status != OrganizationAccessRequestStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"request is already {req.status}, cannot reject",
        )

    now = datetime.now(timezone.utc)
    old_org_status = org.status

    org.status = OrganizationStatus.REJECTED.value
    org.is_active = False
    org.rejected_by_admin_id = admin.id
    org.rejected_at = now
    org.rejection_reason = body.reason

    # Keep all memberships disabled — they were already inactive at signup.
    req.status = OrganizationAccessRequestStatus.REJECTED.value
    req.reviewed_by_admin_id = admin.id
    req.reviewed_at = now
    req.rejection_reason = body.reason

    write_audit_log(
        db,
        action="org.access_request.reject",
        entity_type="organization",
        entity_id=org.id,
        actor_user_id=admin.id,
        old_value={"status": old_org_status},
        new_value={
            "status": org.status,
            "reason": body.reason,
            "request_id": str(req.id),
            "requester_email": user.email,
        },
    )
    db.commit()

    db.refresh(req)
    db.refresh(org)
    db.refresh(user)
    base = _row_to_request(req, org, user)
    return OrgRequestDetail(
        **base.model_dump(),
        organization_industry=org.industry,
        organization_contact_email=org.contact_email,
        additional_info=req.additional_info,
    )


# ── Organizations (admin view) ────────────────────────────────────────────


@router.get("/organizations", response_model=list[OrgRow])
def list_all_organizations(
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[OrgRow]:
    stmt = select(
        Organization,
        func.count(OrganizationMember.id).label("member_count"),
    ).outerjoin(
        OrganizationMember, OrganizationMember.organization_id == Organization.id,
    ).group_by(Organization.id).order_by(Organization.created_at.desc())

    if status_filter:
        stmt = stmt.where(Organization.status == status_filter)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Organization.name).like(like),
                func.lower(Organization.slug).like(like),
                func.lower(Organization.contact_email).like(like),
            )
        )

    rows = db.execute(stmt.limit(limit).offset(offset)).all()
    return [
        OrgRow(
            id=org.id,
            name=org.name,
            slug=org.slug,
            status=org.status,
            is_active=org.is_active,
            industry=org.industry,
            contact_email=org.contact_email,
            member_count=int(member_count),
            created_at=org.created_at,
        )
        for org, member_count in rows
    ]


@router.post("/organizations/{org_id}/suspend", response_model=OrgRow)
def suspend_organization(
    org_id: UUID,
    body: SuspendOrgBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(404, detail="organization_not_found")
    if org.status == OrganizationStatus.SUSPENDED.value:
        raise HTTPException(409, detail="organization_already_suspended")

    old_status = org.status
    org.status = OrganizationStatus.SUSPENDED.value
    org.is_active = False
    org.suspended_at = datetime.now(timezone.utc)
    org.suspended_reason = body.reason

    write_audit_log(
        db,
        action="org.suspend",
        entity_type="organization",
        entity_id=org.id,
        actor_user_id=admin.id,
        old_value={"status": old_status},
        new_value={"status": org.status, "reason": body.reason},
    )
    db.commit()
    db.refresh(org)
    return _org_row(db, org)


@router.post("/organizations/{org_id}/unsuspend", response_model=OrgRow)
def unsuspend_organization(
    org_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(404, detail="organization_not_found")
    if org.status != OrganizationStatus.SUSPENDED.value:
        raise HTTPException(409, detail=f"organization is {org.status}, not suspended")

    old_status = org.status
    org.status = OrganizationStatus.ACTIVE.value
    org.is_active = True
    org.suspended_at = None
    org.suspended_reason = None

    write_audit_log(
        db,
        action="org.unsuspend",
        entity_type="organization",
        entity_id=org.id,
        actor_user_id=admin.id,
        old_value={"status": old_status},
        new_value={"status": org.status},
    )
    db.commit()
    db.refresh(org)
    return _org_row(db, org)


def _org_row(db: Session, org: Organization) -> OrgRow:
    member_count = db.execute(
        select(func.count(OrganizationMember.id)).where(
            OrganizationMember.organization_id == org.id,
        )
    ).scalar_one()
    return OrgRow(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status,
        is_active=org.is_active,
        industry=org.industry,
        contact_email=org.contact_email,
        member_count=int(member_count),
        created_at=org.created_at,
    )


# ── Users (admin view) ────────────────────────────────────────────────────


@router.get("/users", response_model=list[UserRow])
def list_users(
    db: Session = Depends(get_db),
    account_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[UserRow]:
    stmt = select(User).order_by(User.created_at.desc())
    if account_type:
        stmt = stmt.where(User.account_type == account_type)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like))
        )
    rows = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return [
        UserRow(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            account_type=u.account_type,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in rows
    ]


# ── Audit feed ────────────────────────────────────────────────────────────


@router.get("/audit", response_model=list[AuditRow])
def list_audit(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action_prefix: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
) -> list[AuditRow]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action_prefix:
        stmt = stmt.where(AuditLog.action.like(f"{action_prefix}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    rows = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return [
        AuditRow(
            id=r.id,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            actor_user_id=r.actor_user_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ── Dashboard stats ───────────────────────────────────────────────────────


@router.get("/dashboard-stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)) -> DashboardStats:
    def _count_req(s: str) -> int:
        return int(db.execute(
            select(func.count(OrganizationAccessRequest.id))
            .where(OrganizationAccessRequest.status == s)
        ).scalar_one())

    def _count_org(s: str) -> int:
        return int(db.execute(
            select(func.count(Organization.id))
            .where(Organization.status == s)
        ).scalar_one())

    def _count_user(t: str) -> int:
        return int(db.execute(
            select(func.count(User.id)).where(User.account_type == t)
        ).scalar_one())

    return DashboardStats(
        pending_requests=_count_req(OrganizationAccessRequestStatus.PENDING.value),
        approved_requests=_count_req(OrganizationAccessRequestStatus.APPROVED.value),
        rejected_requests=_count_req(OrganizationAccessRequestStatus.REJECTED.value),
        total_organizations=int(db.execute(select(func.count(Organization.id))).scalar_one()),
        active_organizations=_count_org(OrganizationStatus.ACTIVE.value),
        suspended_organizations=_count_org(OrganizationStatus.SUSPENDED.value),
        total_users=int(db.execute(select(func.count(User.id))).scalar_one()),
        candidates=_count_user(AccountType.CANDIDATE.value),
        organization_members=_count_user(AccountType.ORGANIZATION_MEMBER.value),
        platform_admins=_count_user(AccountType.PLATFORM_ADMIN.value),
    )


# ── Richer platform stats (PATHS-142) ────────────────────────────────────────


@router.get("/stats")
def platform_stats(db: Session = Depends(get_db)):
    """Totals: orgs, candidates, CVs processed, jobs, agent runs."""
    total_orgs = int(db.execute(select(func.count(Organization.id))).scalar_one())
    active_orgs = int(
        db.execute(
            select(func.count(Organization.id)).where(
                Organization.status == OrganizationStatus.ACTIVE.value
            )
        ).scalar_one()
    )
    total_candidates = int(db.execute(select(func.count(Candidate.id))).scalar_one())
    total_jobs = int(db.execute(select(func.count(Job.id))).scalar_one())
    total_users = int(db.execute(select(func.count(User.id))).scalar_one())
    total_agent_runs = int(db.execute(select(func.count(AgentRun.id))).scalar_one())
    failed_agent_runs = int(
        db.execute(
            select(func.count(AgentRun.id)).where(AgentRun.status == "failed")
        ).scalar_one()
    )
    pending_orgs = int(
        db.execute(
            select(func.count(Organization.id)).where(
                Organization.status == OrganizationStatus.PENDING_APPROVAL.value
            )
        ).scalar_one()
    )
    return {
        "total_orgs": total_orgs,
        "active_orgs": active_orgs,
        "pending_orgs": pending_orgs,
        "total_candidates": total_candidates,
        "total_jobs": total_jobs,
        "total_users": total_users,
        "total_agent_runs": total_agent_runs,
        "failed_agent_runs": failed_agent_runs,
    }


# ── Org dossier + impersonation (PATHS-143) ───────────────────────────────────


@router.get("/organizations/{org_id}")
def get_org_dossier(org_id: UUID, db: Session = Depends(get_db)):
    """Full org dossier: metadata, members, jobs, subscription, health score."""
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, detail="organization_not_found")

    members = (
        db.execute(
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(OrganizationMember.organization_id == org_id)
        )
        .all()
    )
    jobs = db.execute(
        select(Job).where(Job.organization_id == org_id).order_by(Job.created_at.desc()).limit(20)
    ).scalars().all()

    sub = db.execute(
        select(Subscription).where(
            Subscription.org_id == org_id, Subscription.status == "active"
        )
    ).scalar_one_or_none()

    health = compute_org_health(str(org_id), db)

    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "status": org.status.value if hasattr(org.status, "value") else str(org.status),
        "industry": org.industry,
        "contact_email": org.contact_email,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "health_score": health,
        "subscription": {
            "plan": sub.plan.code if sub and sub.plan else None,
            "status": sub.status if sub else None,
            "billing_cycle": sub.billing_cycle if sub else None,
        } if sub else None,
        "members": [
            {
                "user_id": str(m.user_id),
                "email": u.email,
                "full_name": u.full_name,
                "role_code": m.role_code,
                "is_active": m.is_active,
            }
            for m, u in members
        ],
        "recent_jobs": [
            {
                "id": str(j.id),
                "title": j.title,
                "status": j.status,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ],
    }


class ImpersonateBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


@router.post("/organizations/{org_id}/impersonate")
def impersonate_org(
    org_id: UUID,
    body: ImpersonateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    """Return a short-lived (15 min) impersonation JWT scoped to this org's first admin member."""
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, detail="organization_not_found")

    # Find the first active owner/admin member of this org
    target_member = db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.is_active.is_(True),
        )
        .order_by(OrganizationMember.created_at)
        .limit(1)
    ).first()

    if not target_member:
        raise HTTPException(404, detail="no_active_member_in_org")

    _, target_user = target_member

    # Write audit row
    session_row = ImpersonationSession(
        impersonator_account_id=admin.id,
        target_account_id=target_user.id,
        reason=body.reason,
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)

    token = create_access_token(
        data={
            "sub": target_user.email,
            "account_type": target_user.account_type,
            "organization_id": str(org_id),
            "impersonating": True,
            "impersonation_session_id": str(session_row.id),
            "impersonated_by": str(admin.id),
        },
        expires_delta=timedelta(minutes=15),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 900,
        "impersonation_session_id": str(session_row.id),
        "target_user_email": target_user.email,
        "target_org": org.name,
    }


# ── User suspend + impersonate (PATHS-144) ────────────────────────────────────


class SuspendUserBody(BaseModel):
    suspended: bool


@router.put("/users/{user_id}/suspend")
def suspend_user(
    user_id: UUID,
    body: SuspendUserBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="user_not_found")
    if user.id == admin.id:
        raise HTTPException(400, detail="cannot_suspend_yourself")

    old_active = user.is_active
    user.is_active = not body.suspended

    write_audit_log(
        db,
        action="user.suspend" if body.suspended else "user.unsuspend",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=admin.id,
        old_value={"is_active": old_active},
        new_value={"is_active": user.is_active},
    )
    db.commit()
    return {"user_id": str(user.id), "is_active": user.is_active}


@router.post("/users/{user_id}/impersonate")
def impersonate_user(
    user_id: UUID,
    body: ImpersonateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    """Return a short-lived (15 min) impersonation JWT for the target user."""
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(404, detail="user_not_found")
    if not target_user.is_active:
        raise HTTPException(400, detail="user_is_inactive")

    session_row = ImpersonationSession(
        impersonator_account_id=admin.id,
        target_account_id=target_user.id,
        reason=body.reason,
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)

    token_data: dict[str, Any] = {
        "sub": target_user.email,
        "account_type": target_user.account_type,
        "impersonating": True,
        "impersonation_session_id": str(session_row.id),
        "impersonated_by": str(admin.id),
    }
    token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 900,
        "impersonation_session_id": str(session_row.id),
        "target_user_email": target_user.email,
    }


# ── Agent runs — cross-org monitor (PATHS-145) ────────────────────────────────


@router.get("/agent-runs")
def list_agent_runs(
    run_type: str = Query(default=""),
    status_filter: str = Query(default="", alias="status"),
    org_id: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Cross-org agent runs — filterable by type, status, org."""
    q = select(AgentRun).order_by(AgentRun.created_at.desc())
    if run_type:
        q = q.where(AgentRun.run_type == run_type)
    if status_filter:
        q = q.where(AgentRun.status == status_filter)
    if org_id:
        q = q.where(AgentRun.organization_id == org_id)

    runs = db.execute(q.limit(limit).offset(offset)).scalars().all()
    return [
        {
            "id": str(r.id),
            "organization_id": r.organization_id,
            "run_type": r.run_type,
            "status": r.status,
            "current_node": r.current_node,
            "triggered_by": r.triggered_by,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "error": r.error,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


@router.post("/agent-runs/{run_id}/retry")
def retry_agent_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    """Reset a failed agent run back to 'queued' so it will be picked up again."""
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(404, detail="agent_run_not_found")
    if run.status not in ("failed", "cancelled"):
        raise HTTPException(400, detail=f"Cannot retry run with status '{run.status}'")

    run.status = "queued"
    run.error = None
    run.current_node = None
    run.started_at = None
    run.finished_at = None
    db.commit()
    return {"id": str(run.id), "status": run.status}


# ── System health probes (PATHS-146) ─────────────────────────────────────────


@router.get("/system-health")
def system_health(db: Session = Depends(get_db)):
    """Live probes: Postgres, AGE, Qdrant, Ollama."""
    from app.services.postgres_service import PostgresService
    from app.services.age_service import AGEService
    from app.services.qdrant_service import QdrantService
    import httpx
    from app.core.config import get_settings as _gs

    s = _gs()

    pg = PostgresService.test_connection()
    age = AGEService.test_connection()
    qdrant_svc = QdrantService()
    qd = qdrant_svc.test_connection()

    try:
        r = httpx.get(f"{s.ollama_base_url}/api/tags", timeout=3.0)
        ol: dict = {"status": "healthy" if r.status_code == 200 else "unhealthy"}
    except Exception:
        ol = {"status": "unreachable"}

    # Count failed agent runs in last 24h
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    failed_24h = int(
        db.execute(
            select(func.count(AgentRun.id)).where(
                AgentRun.status == "failed",
                AgentRun.created_at >= cutoff,
            )
        ).scalar_one()
    )

    services = {
        "postgres": pg,
        "apache_age": age,
        "qdrant": qd,
        "ollama": ol,
    }
    all_healthy = all(
        v.get("status") == "healthy" for v in services.values() if isinstance(v, dict)
    )
    return {
        "overall": "healthy" if all_healthy else "degraded",
        "services": services,
        "agent_runs_failed_24h": failed_24h,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Feature flags (PATHS-147) ─────────────────────────────────────────────────


class FeatureFlagCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    enabled: bool = True


class FeatureFlagUpdate(BaseModel):
    enabled: bool
    description: str | None = None


class OrgOverrideBody(BaseModel):
    org_id: UUID
    enabled: bool


@router.get("/feature-flags")
def list_feature_flags(db: Session = Depends(get_db)):
    flags = db.execute(select(FeatureFlag).order_by(FeatureFlag.code)).scalars().all()
    return [
        {
            "id": str(f.id),
            "code": f.code,
            "description": f.description,
            "enabled": f.enabled,
            "created_at": f.created_at.isoformat(),
            "overrides": [
                {
                    "org_id": str(o.org_id),
                    "enabled": o.enabled,
                    "set_at": o.set_at.isoformat(),
                }
                for o in f.overrides
            ],
        }
        for f in flags
    ]


@router.post("/feature-flags", status_code=201)
def create_feature_flag(
    body: FeatureFlagCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    existing = db.execute(
        select(FeatureFlag).where(FeatureFlag.code == body.code)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(409, detail="feature_flag_code_exists")

    flag = FeatureFlag(
        code=body.code,
        description=body.description,
        enabled=body.enabled,
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return {"id": str(flag.id), "code": flag.code, "enabled": flag.enabled}


@router.put("/feature-flags/{flag_id}")
def update_feature_flag(
    flag_id: UUID,
    body: FeatureFlagUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    flag = db.get(FeatureFlag, flag_id)
    if not flag:
        raise HTTPException(404, detail="feature_flag_not_found")
    flag.enabled = body.enabled
    if body.description is not None:
        flag.description = body.description
    db.commit()
    return {"id": str(flag.id), "code": flag.code, "enabled": flag.enabled}


@router.post("/feature-flags/{flag_id}/org-override")
def upsert_flag_org_override(
    flag_id: UUID,
    body: OrgOverrideBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    flag = db.get(FeatureFlag, flag_id)
    if not flag:
        raise HTTPException(404, detail="feature_flag_not_found")

    override = db.execute(
        select(FeatureFlagOverride).where(
            FeatureFlagOverride.flag_id == flag_id,
            FeatureFlagOverride.org_id == body.org_id,
        )
    ).scalar_one_or_none()

    if override:
        override.enabled = body.enabled
        override.set_by = admin.id
    else:
        override = FeatureFlagOverride(
            flag_id=flag_id,
            org_id=body.org_id,
            enabled=body.enabled,
            set_by=admin.id,
        )
        db.add(override)

    db.commit()
    return {
        "flag_id": str(flag_id),
        "org_id": str(body.org_id),
        "enabled": override.enabled,
    }


# ── Platform settings (PATHS-148) ─────────────────────────────────────────────


class PlatformSettingsUpdate(BaseModel):
    display_name: str | None = None
    support_email: str | None = None
    legal_company_name: str | None = None
    maintenance_mode: bool | None = None
    email_templates: dict | None = None


@router.get("/settings")
def get_platform_settings(db: Session = Depends(get_db)):
    ps = db.get(PlatformSettings, 1)
    if not ps:
        return {}
    return {
        "display_name": ps.display_name,
        "support_email": ps.support_email,
        "legal_company_name": ps.legal_company_name,
        "maintenance_mode": ps.maintenance_mode,
        "email_templates": ps.email_templates,
        "updated_at": ps.updated_at.isoformat() if ps.updated_at else None,
    }


@router.put("/settings")
def update_platform_settings(
    body: PlatformSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    ps = db.get(PlatformSettings, 1)
    if not ps:
        ps = PlatformSettings(id=1)
        db.add(ps)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ps, k, v)
    db.commit()

    write_audit_log(
        db,
        action="platform.settings.update",
        entity_type="platform_settings",
        entity_id=None,
        actor_user_id=admin.id,
        old_value=None,
        new_value=body.model_dump(exclude_none=True),
    )
    db.commit()
    return {"status": "updated"}
