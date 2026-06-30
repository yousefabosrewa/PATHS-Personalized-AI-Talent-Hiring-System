"""
PATHS Backend — Organisation schemas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    slug: str
    industry: str | None = None
    contact_email: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class CreateMemberRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role_code: str = Field(..., pattern=r"^(recruiter|hr|hr_manager|hiring_manager|org_admin)$")


class CreateMemberResponse(BaseModel):
    member_id: UUID
    user_id: UUID
    organization_id: UUID
    role_code: str
    status: str = "pending"
    invited_at: datetime | None = None


class ResendInviteRequest(BaseModel):
    temporary_password: str | None = Field(
        default=None, min_length=8, max_length=128,
        description=(
            "Optional new temporary password. If omitted, the email is "
            "re-sent without resetting the credential."
        ),
    )


class JobListItem(BaseModel):
    """Lightweight job row for org dashboards (frontend)."""

    id: UUID
    title: str
    company_name: str | None = None
    status: str
    location_mode: str | None = None
    location_text: str | None = None
    role_family: str | None = None
    is_active: bool
    source_platform: str | None = None

    model_config = {"from_attributes": True}
