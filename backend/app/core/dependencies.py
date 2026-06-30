"""
PATHS Backend — FastAPI authentication and authorization dependencies.

Provides reusable Depends-compatible helpers:
  - get_current_user            — extract + validate JWT
  - get_current_active_user     — ensure is_active flag
  - require_account_type(...)   — gate by account type
  - require_platform_admin      — global platform admin gate
  - require_org_role(...)       — gate by organisation role
  - get_current_org_context     — JWT-derived org scope (no path param)
  - require_active_org_status   — also blocks pending/rejected/suspended orgs

The string constants for account types and roles are re-exported here for
backwards compatibility but the source of truth lives in app.core.rbac.
"""

from dataclasses import dataclass
from typing import Sequence
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.rbac import (
    AccountType,
    HIRING_STAFF_ROLE_CODES as _HIRING_STAFF_ROLE_CODES,
)
from app.db.models.user import User
from app.db.models.application import OrganizationMember
from app.db.models.organization import Organization, OrganizationStatus

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Re-export so existing call sites that import HIRING_STAFF_ROLE_CODES from
# this module keep working.
HIRING_STAFF_ROLE_CODES = _HIRING_STAFF_ROLE_CODES


# ── Core user extraction ──────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode bearer token and return the corresponding User row."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    email: str | None = payload.get("sub")
    if email is None:
        raise credentials_exception

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the authenticated user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


# ── Account-type gate ─────────────────────────────────────────────────────

def require_account_type(*allowed_types: str):
    """Return a dependency that rejects users whose account_type is not in *allowed_types*."""

    def _dependency(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.account_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account type '{current_user.account_type}' is not permitted for this resource",
            )
        return current_user

    return _dependency


# ── Organisation role gate ────────────────────────────────────────────────

def require_org_role(*allowed_roles: str):
    """Return a dependency that rejects users who are not members of the
    target organisation (path param ``organization_id``) with one of the
    *allowed_roles*.

    The path **must** contain ``{organization_id}`` as a UUID path parameter.
    """

    def _dependency(
        organization_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> User:
        if current_user.account_type != "organization_member":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organization members can access this resource",
            )
        membership = db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.is_active == True,  # noqa: E712
            )
        ).scalar_one_or_none()

        if membership is None or membership.role_code not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles {list(allowed_roles)} in this organisation",
            )
        return current_user

    return _dependency


# ── Any organisation member (e.g. list jobs) ───────────────────────────────

@dataclass
class OrgContext:
    """JWT-derived org context — available in any org-member route without a path param."""
    user: User
    organization_id: UUID
    role_code: str


def get_current_org_context(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_active_user),
) -> "OrgContext":
    """Extract org context from the JWT for org-member users (no path param required)."""
    if current_user.account_type != "organization_member":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization member account required",
        )
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    org_id_str = payload.get("organization_id")
    role_code = payload.get("role_code", "member")
    if not org_id_str:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization in token")
    return OrgContext(user=current_user, organization_id=UUID(org_id_str), role_code=role_code)


def get_current_hiring_org_context(
    ctx: OrgContext = Depends(get_current_org_context),
) -> OrgContext:
    """Like ``get_current_org_context`` but restricted to hiring / HR-type roles."""
    if ctx.role_code not in HIRING_STAFF_ROLE_CODES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires a recruiter, HR, or hiring manager role",
        )
    return ctx


def require_organization_member(
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> User:
    """Active membership in ``organization_id`` (any ``role_code``)."""
    if current_user.account_type != "organization_member":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization members can access this resource",
        )
    membership = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.is_active == True,  # noqa: E712
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organisation",
        )
    return current_user


# ── Platform admin gate ───────────────────────────────────────────────────

def require_platform_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Allow only users with account_type='platform_admin'.

    Used on every /api/v1/admin/* route. Platform admins are seeded via
    backend/scripts/seed_platform_admins.py and never via public signup.
    """
    if current_user.account_type != AccountType.PLATFORM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin privileges required",
        )
    return current_user


# ── Approved organisation gate ────────────────────────────────────────────

def require_active_org_status(
    ctx: "OrgContext" = Depends(get_current_org_context),
    db: Session = Depends(get_db),
) -> "OrgContext":
    """Block users whose organisation is not in the ACTIVE state.

    Used on every endpoint that operates on org-scoped data (jobs, applications,
    members, etc.). Users in pending/rejected/suspended orgs may still call
    /auth/me so the frontend can route them to /pending-approval, but every
    other org endpoint refuses them.
    """
    org = db.get(Organization, ctx.organization_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organisation not found",
        )
    if org.status != OrganizationStatus.ACTIVE.value:
        # Use 403 with a structured detail — frontend reads this to drive UX.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "organization_not_active",
                "status": org.status,
                "message": (
                    "Your company account is pending approval"
                    if org.status == OrganizationStatus.PENDING_APPROVAL.value
                    else f"Your company access is currently {org.status}"
                ),
            },
        )
    return ctx
