"""
PATHS Backend — Open-to-Work Candidate Sourcing schemas.

Used by `app/api/v1/organization_candidate_sourcing.py` and the
candidate sourcing service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CandidateSourcingRunRequest(BaseModel):
    """Body of `POST /admin/candidate-sourcing/run-once`."""

    limit: int | None = None
    provider: str | None = None
    keywords: list[str] | None = None
    location: str | None = None


class CandidateSourcingRunResultSchema(BaseModel):
    source_platform: str
    requested_limit: int
    started_at: datetime
    finished_at: datetime | None = None
    fetched_count: int = 0
    valid_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    graph_synced_count: int = 0
    vector_synced_count: int = 0
    candidate_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    status: str = "success"


class SourcedCandidateSummary(BaseModel):
    candidate_id: UUID
    full_name: str | None = None
    headline: str | None = None
    current_title: str | None = None
    location_text: str | None = None
    years_experience: int | None = None
    skills: list[str] = Field(default_factory=list)
    open_to_job_types: list[str] = Field(default_factory=list)
    open_to_workplace_settings: list[str] = Field(default_factory=list)
    desired_job_titles: list[str] = Field(default_factory=list)
    summary: str | None = None
    status: str | None = None
    source: dict[str, Any] | None = None
    open_to_work: bool = True


class SourcedCandidateMatchSchema(BaseModel):
    candidate_id: UUID
    score: float
    vector_score: float
    skill_overlap_score: float
    matched_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    workplace_match: bool = True
    location_match: bool = True
    candidate: SourcedCandidateSummary
    source: dict[str, Any] | None = None


class CandidateJobReasoningSchema(BaseModel):
    candidate_id: str
    job_id: str
    decision: str
    overall_score: float
    summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    recommended_next_step: str = "review_profile"
    model: str | None = None
    fallback: bool = False


class SourcedCandidateListResponse(BaseModel):
    """Filtered list of sourced candidates available to an organization."""

    organization_id: UUID
    total: int
    items: list[SourcedCandidateSummary]
    job_id: UUID | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class SourcedCandidateMatchListResponse(BaseModel):
    """Job-specific ranked list of sourced candidates with reasoning."""

    organization_id: UUID
    job_id: UUID
    total: int
    top_k: int
    items: list[SourcedCandidateMatchSchema]
    filters: dict[str, Any] = Field(default_factory=dict)


class SourcingFilterParams(BaseModel):
    """Query parameter container shared by listing endpoints."""

    job_id: UUID | None = None
    title: str | None = None
    skills: list[str] | None = None
    location: str | None = None
    workplace_settings: list[str] | None = None
    employment_types: list[str] | None = None
    min_years_experience: int | None = None
    max_years_experience: int | None = None
    min_score: float | None = None
    top_k: int = 20


class ShortlistRequest(BaseModel):
    candidate_id: UUID
    job_id: UUID
    note: str | None = None
    stage_code: str | None = "sourced"


class ShortlistResponse(BaseModel):
    candidate_id: UUID
    job_id: UUID
    application_id: UUID | None = None
    stage_code: str
    overall_status: str
    note: str | None = None
    created: bool = True


class CandidateSourcingStatus(BaseModel):
    enabled: bool
    provider: str
    interval_minutes: int
    max_per_run: int
    reasoning_enabled: bool
    reasoning_model: str
    metadata: dict[str, Any] | None = None
