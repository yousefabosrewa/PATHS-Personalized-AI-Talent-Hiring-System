"""
PATHS Backend — Authentication schemas (requests & responses).
"""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


# ── Candidate Registration ────────────────────────────────────────────────

class CandidateRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    phone: str | None = Field(None, max_length=50)
    location: str | None = Field(None, max_length=255)
    headline: str | None = Field(None, max_length=500)


class CandidateRegisterResponse(BaseModel):
    user_id: UUID
    candidate_profile_id: UUID
    account_type: str
    message: str


# ── Organisation Registration ─────────────────────────────────────────────

class OrganizationRegisterRequest(BaseModel):
    organization_name: str = Field(..., min_length=1, max_length=255)
    organization_slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    industry: str | None = Field(None, max_length=255)
    organization_email: EmailStr | None = None
    company_website: str | None = Field(None, max_length=512)
    company_size: str | None = Field(None, max_length=100)
    company_type: str | None = Field(None, max_length=120)
    first_admin_full_name: str = Field(..., min_length=1, max_length=255)
    first_admin_email: EmailStr
    first_admin_password: str = Field(..., min_length=8, max_length=128)
    first_admin_job_title: str | None = Field(None, max_length=255)
    first_admin_phone: str | None = Field(None, max_length=50)
    accept_terms: bool = False
    confirm_authorized: bool = False

    @model_validator(mode="after")
    def _require_legal_acknowledgements(self):
        if not self.accept_terms:
            raise ValueError("You must accept the Terms and Conditions")
        if not self.confirm_authorized:
            raise ValueError(
                "You must confirm that you are authorized to register this company on PATHS",
            )
        return self


class OrganizationRegisterResponse(BaseModel):
    organization_id: UUID
    user_id: UUID
    role_code: str
    message: str


# ── Login ─────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OrganizationContext(BaseModel):
    organization_id: UUID
    organization_name: str
    role_code: str
    status: str = "active"  # active | pending_approval | rejected | suspended


class UserSummary(BaseModel):
    id: UUID
    email: str
    full_name: str
    account_type: str
    organization: OrganizationContext | None = None
    is_platform_admin: bool = False

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary


# ── /auth/me ──────────────────────────────────────────────────────────────

class CandidateProfileSummary(BaseModel):
    id: UUID
    phone: str | None = None
    location: str | None = None
    headline: str | None = None
    years_experience: int | None = None
    career_level: str | None = None
    skills: list[str] = Field(default_factory=list)
    open_to_job_types: list[str] = Field(default_factory=list)
    open_to_workplace_settings: list[str] = Field(default_factory=list)
    desired_job_titles: list[str] = Field(default_factory=list)
    desired_job_categories: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    account_type: str
    is_active: bool
    is_platform_admin: bool = False
    candidate_profile: CandidateProfileSummary | None = None
    organization: OrganizationContext | None = None
    permissions: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}
