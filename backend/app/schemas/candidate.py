"""
PATHS Backend — Candidate profile schemas.

The profile is the union of:
  * scalar columns on the ``candidates`` row, and
  * relational sections (``candidate_education``, ``candidate_experiences``,
    ``candidate_links``, ``candidate_documents``).

``CandidateProfileOut`` returns the whole thing so the candidate portal can
display everything they entered during onboarding (and everything the CV
ingestion agent extracted). ``CandidateProfileUpdateRequest`` accepts the same
sections so "Submit Profile" persists the full draft.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Relational section items ──────────────────────────────────────────────

class EducationItem(BaseModel):
    institution: str = Field(..., min_length=1, max_length=255)
    degree: str | None = Field(default=None, max_length=255)
    field_of_study: str | None = Field(default=None, max_length=255)
    start_date: str | None = Field(default=None, max_length=50)
    end_date: str | None = Field(default=None, max_length=50)

    model_config = {"from_attributes": True}


class ExperienceItem(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    start_date: str | None = Field(default=None, max_length=50)
    end_date: str | None = Field(default=None, max_length=50)
    description: str | None = None

    model_config = {"from_attributes": True}


class LinkItem(BaseModel):
    link_type: str = Field(..., min_length=1, max_length=50)
    url: str = Field(..., min_length=1, max_length=1024)
    label: str | None = Field(default=None, max_length=255)

    model_config = {"from_attributes": True}


class DocumentItem(BaseModel):
    id: UUID
    document_type: str
    original_filename: str
    mime_type: str
    # Real upload timestamp — without this the UI fell back to 1970.
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Profile read model ────────────────────────────────────────────────────

class CandidateProfileOut(BaseModel):
    id: UUID
    full_name: str
    email: str | None = None
    other_emails: list[str] = Field(default_factory=list)
    phone: str | None = None
    location: str | None = None
    headline: str | None = None
    current_title: str | None = None
    summary: str | None = None
    years_experience: int | None = None
    career_level: str | None = None
    skills: list[str] = Field(default_factory=list)
    open_to_job_types: list[str] = Field(default_factory=list)
    open_to_workplace_settings: list[str] = Field(default_factory=list)
    desired_job_titles: list[str] = Field(default_factory=list)
    desired_job_categories: list[str] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    experiences: list[ExperienceItem] = Field(default_factory=list)
    links: list[LinkItem] = Field(default_factory=list)
    documents: list[DocumentItem] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ── Profile update model ──────────────────────────────────────────────────

class CandidateProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    # Additional contact emails (the primary sign-in email is never changed here).
    other_emails: list[str] | None = Field(default=None, max_length=10)
    phone: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=255)
    current_title: str | None = Field(default=None, max_length=255)
    summary: str | None = Field(default=None, max_length=5000)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    career_level: str | None = Field(default=None, max_length=80)
    # None = "omit field" so partial PUTs do not clear existing data.
    skills: list[str] | None = Field(default=None, max_length=100)
    open_to_job_types: list[str] | None = Field(default=None, max_length=10)
    open_to_workplace_settings: list[str] | None = Field(default=None, max_length=10)
    desired_job_titles: list[str] | None = Field(default=None, max_length=10)
    desired_job_categories: list[str] | None = Field(default=None, max_length=20)
    # Relational sections — when provided (not None) they REPLACE existing rows.
    # The frontend only sends these when non-empty, so a profile submit never
    # wipes CV-extracted education/experience the candidate did not re-enter.
    education: list[EducationItem] | None = Field(default=None, max_length=50)
    experiences: list[ExperienceItem] | None = Field(default=None, max_length=50)
    links: list[LinkItem] | None = Field(default=None, max_length=30)
