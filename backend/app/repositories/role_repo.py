"""
PATHS Backend — Role / membership repository.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import ALLOWED_ORG_ROLES, normalize_role_code
from app.db.models.application import OrganizationMember


# Re-export for any legacy callers that import this name from here.
ALLOWED_ROLES = ALLOWED_ORG_ROLES


class RoleRepository:
    """Data-access layer for the ``organization_members`` table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_membership(
        self,
        *,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        role_code: str,
    ) -> OrganizationMember:
        canonical = normalize_role_code(role_code)
        if canonical not in ALLOWED_ORG_ROLES:
            raise ValueError(
                f"Invalid role_code '{role_code}'. Must be one of {sorted(ALLOWED_ORG_ROLES)}"
            )

        member = OrganizationMember(
            user_id=user_id,
            organization_id=organization_id,
            role_code=canonical,
            is_active=True,
        )
        self.db.add(member)
        self.db.flush()
        return member

    def get_membership(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> OrganizationMember | None:
        stmt = select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_user_memberships(
        self,
        user_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> list[OrganizationMember]:
        """Return memberships for a user.

        By default only active rows are returned. Pass include_inactive=True
        to also surface pending/disabled memberships — used by /auth/me so
        the frontend can route a pending company user to /pending-approval.
        """
        stmt = select(OrganizationMember).where(OrganizationMember.user_id == user_id)
        if not include_inactive:
            stmt = stmt.where(OrganizationMember.is_active == True)  # noqa: E712
        return list(self.db.execute(stmt).scalars().all())
