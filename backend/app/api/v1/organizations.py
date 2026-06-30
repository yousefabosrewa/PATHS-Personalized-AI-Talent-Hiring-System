"""
PATHS Backend — Organization management endpoints.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from sqlalchemy import desc, select

from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    get_current_active_user,
    get_current_hiring_org_context,
    require_org_role,
    require_organization_member,
)
from app.db.models.application import OrganizationMember
from app.db.models.job import Job
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.organization import (
    CreateMemberRequest,
    CreateMemberResponse,
    JobListItem,
    ResendInviteRequest,
)
from app.services import organization_service

import re

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def _unpack_industry(packed: str | None) -> dict:
    """Split a legacy packed industry snapshot into its parts.

    Older rows stored everything in ``industry`` as e.g.
    ``"Healthcare [type:Startup;size:11-50;url:https://x;phone:..;role:..]"``.
    This pulls out the clean industry plus the bracketed metadata so existing
    orgs display correctly even before the data migration runs.
    """
    out: dict[str, str | None] = {
        "industry": None, "company_type": None, "company_size": None,
        "website": None, "phone": None, "role": None,
    }
    if not packed:
        return out
    s = packed.strip()
    m = re.match(r"^(.*?)\s*\[(.*)\]\s*$", s)
    if not m:
        out["industry"] = s or None
        return out
    out["industry"] = m.group(1).strip() or None
    for bit in m.group(2).split(";"):
        key, sep, val = bit.partition(":")
        if not sep:
            continue
        key, val = key.strip().lower(), val.strip()
        if key in ("type", "size", "url", "phone", "role"):
            mapped = {"type": "company_type", "size": "company_size", "url": "website"}.get(key, key)
            out[mapped] = val or None
    return out


def _org_dict(org: Organization) -> dict:
    # Prefer the real columns; fall back to unpacking the legacy packed
    # ``industry`` string for orgs created before the dedicated columns existed.
    packed = _unpack_industry(org.industry)
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "industry": packed["industry"],
        "companySize": org.company_size or packed["company_size"],
        "companyType": org.company_type or packed["company_type"],
        "contactEmail": org.contact_email,
        "website": org.website or packed["website"],
        "isActive": org.is_active,
    }


@router.get("/me")
def get_my_org(
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Return the current user's organisation profile."""
    org = db.get(Organization, ctx.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _org_dict(org)


class OrganizationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    company_size: str | None = Field(default=None, max_length=100)
    company_type: str | None = Field(default=None, max_length=120)
    contact_email: EmailStr | None = None
    website: str | None = Field(default=None, max_length=2048)


@router.patch("/me")
def update_my_org(
    body: OrganizationUpdateRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Update editable fields of the current user's organisation profile.

    ``slug`` and ``status`` are deliberately NOT editable here — those are
    platform-admin lifecycle controls.
    """
    org = db.get(Organization, ctx.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if body.name is not None:
        org.name = body.name.strip()
    if body.industry is not None:
        org.industry = body.industry.strip() or None
    if body.company_size is not None:
        org.company_size = body.company_size.strip() or None
    if body.company_type is not None:
        org.company_type = body.company_type.strip() or None
    if body.contact_email is not None:
        org.contact_email = str(body.contact_email).strip() or None
    if body.website is not None:
        org.website = body.website.strip() or None

    db.commit()
    db.refresh(org)
    return _org_dict(org)


class MemberOut(BaseModel):
    id: UUID
    user_id: UUID
    organization_id: UUID
    role_code: str
    is_active: bool
    status: str = "active"
    joined_at: datetime
    invited_at: datetime | None = None
    activated_at: datetime | None = None
    first_login_at: datetime | None = None
    invited_by_user_id: UUID | None = None
    full_name: str | None = None
    email: str | None = None

    model_config = {"from_attributes": True}


def _member_out(m: OrganizationMember) -> "MemberOut":
    return MemberOut(
        id=m.id,
        user_id=m.user_id,
        organization_id=m.organization_id,
        role_code=m.role_code,
        is_active=m.is_active,
        status=getattr(m, "status", "active") or "active",
        joined_at=m.joined_at,
        invited_at=getattr(m, "invited_at", None),
        activated_at=getattr(m, "activated_at", None),
        first_login_at=getattr(m, "first_login_at", None),
        invited_by_user_id=getattr(m, "invited_by_user_id", None),
        full_name=m.user.full_name if m.user else None,
        email=m.user.email if m.user else None,
    )


# Convenience endpoint — list members for the JWT-scoped org (no path param).
# MUST be declared before the parameterised "/{organization_id}/members" route:
# otherwise FastAPI matches "me" as {organization_id} and 422s on UUID parsing.
@router.get("/me/members", response_model=list[MemberOut])
def list_my_org_members(
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """List members for the current user's organisation (uses JWT org context)."""
    # Lazily enforce the 2-day invite expiry so the Members tab is always
    # correct even when the background scheduler is disabled.
    organization_service.expire_stale_pending_invites(
        db, organization_id=ctx.organization_id,
    )
    rows = db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == ctx.organization_id)
        .order_by(OrganizationMember.joined_at.asc())
    ).scalars().all()
    return [_member_out(m) for m in rows]


class InviteEmailPreviewOut(BaseModel):
    to: str
    subject: str
    body: str


@router.post(
    "/{organization_id}/members/invite-preview",
    response_model=InviteEmailPreviewOut,
    dependencies=[Depends(require_org_role("org_admin"))],
)
def preview_member_invite_email(
    organization_id: UUID,
    data: CreateMemberRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Compose the EXACT invitation email (recipient, subject, body) without
    creating the member or sending anything — the admin reviews and approves
    it first; the approved invite then goes through POST /members."""
    from app.core.config import get_settings
    from app.services.email_service import compose_organization_invite_email

    org = db.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    settings = get_settings()
    return InviteEmailPreviewOut(
        **compose_organization_invite_email(
            to=data.email,
            invited_member_name=data.full_name or data.email,
            inviter_name=(current_user.full_name or current_user.email),
            inviter_email=current_user.email,
            organization_name=org.name,
            temporary_password=data.password,
            login_url=(
                settings.outreach_public_base_url + "/login"
                if settings.outreach_public_base_url
                else None
            ),
        )
    )


@router.post(
    "/{organization_id}/members",
    response_model=CreateMemberResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_org_role("org_admin"))],
)
def create_organization_member(
    organization_id: UUID,
    data: CreateMemberRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Create a new user assigned to the specified organization.
    Only users with 'org_admin' role in this organization can call this endpoint.
    """
    return organization_service.create_member(db, organization_id, data, current_user)


@router.get(
    "/{organization_id}/members",
    response_model=list[MemberOut],
    dependencies=[Depends(require_organization_member)],
)
def list_organization_members(
    organization_id: UUID,
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    """List members of the specified organisation."""
    organization_service.expire_stale_pending_invites(
        db, organization_id=organization_id,
    )
    q = select(OrganizationMember).where(
        OrganizationMember.organization_id == organization_id
    )
    if active_only:
        q = q.where(OrganizationMember.is_active == True)  # noqa: E712
    q = q.order_by(OrganizationMember.joined_at.asc())
    rows = db.execute(q).scalars().all()

    return [_member_out(m) for m in rows]


# fix8&9 — resend invite for a pending member
@router.post(
    "/{organization_id}/members/{membership_id}/resend-invite",
    dependencies=[Depends(require_org_role("org_admin"))],
)
def resend_invite(
    organization_id: UUID,
    membership_id: UUID,
    body: ResendInviteRequest | None = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Resend the invitation email for a still-pending member.

    Optional ``temporary_password`` resets the credential at the same time.
    """
    payload = body or ResendInviteRequest()
    return organization_service.resend_invite_email(
        db, organization_id, membership_id, current_user,
        temporary_password=payload.temporary_password,
    )


# fix8&9 — remove a member from the org (hard-delete the membership row).
# The user account itself stays so they can still log in if they have
# memberships in other organizations.
@router.delete(
    "/{organization_id}/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_org_role("org_admin"))],
)
def delete_organization_member(
    organization_id: UUID,
    membership_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Remove a member from this organisation."""
    membership = db.get(OrganizationMember, membership_id)
    if membership is None or membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if membership.user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot remove yourself from the organisation",
        )
    db.delete(membership)
    db.commit()
    return None


@router.get(
    "/{organization_id}/jobs",
    response_model=list[JobListItem],
    dependencies=[Depends(require_organization_member)],
)
def list_organization_jobs(
    organization_id: UUID,
    db: Session = Depends(get_db),
    limit: int = 200,
    offset: int = 0,
):
    """
    List jobs owned by the organisation (for recruiter dashboards and matching UI).
    """
    if limit < 1 or limit > 500:
        limit = 200
    if offset < 0:
        offset = 0
    rows = (
        db.execute(
            select(Job)
            .where(Job.organization_id == organization_id)
            .order_by(desc(Job.created_at))
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return [JobListItem.model_validate(r) for r in rows]
