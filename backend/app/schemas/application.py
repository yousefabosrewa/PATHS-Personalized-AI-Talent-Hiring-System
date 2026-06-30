"""PATHS Backend — Application schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApplicationOut(BaseModel):
    id: UUID
    candidate_id: UUID
    job_id: UUID
    application_type: str
    source_channel: str | None = None
    current_stage_code: str
    overall_status: str
    created_at: datetime
    updated_at: datetime | None = None

    candidate_name: str | None = None
    candidate_email: str | None = None
    candidate_current_title: str | None = None
    candidate_skills: list[str] = Field(default_factory=list)
    job_title: str | None = None
    match_final_score: float | None = None
    match_confidence: float | None = None
    # The candidate's progress against THIS job's configured hiring pipeline
    # (Applied → custom stages → Offer → Hired), identical to what the candidate
    # sees on their side. Lets the recruiter view honour the custom workflow.
    roadmap: dict | None = None

    model_config = {"from_attributes": True}


class StageTransitionRequest(BaseModel):
    stage: str   # applied | screening | assessment | hr_interview | tech_interview | decision | hired | rejected
    reason: str | None = None


class ShortlistItemOut(BaseModel):
    application_id: UUID
    candidate_id: UUID
    candidate_name: str | None = None
    current_stage_code: str
    final_score: float | None = None
    agent_score: float | None = None
    vector_similarity_score: float | None = None
    confidence: float | None = None
    explanation: str | None = None
    strengths: list[str] = []
    weaknesses: list[str] = []
    matched_skills: list[str] = []
    missing_required_skills: list[str] = []
    criteria_breakdown: dict | None = None
    rank: int = 0
