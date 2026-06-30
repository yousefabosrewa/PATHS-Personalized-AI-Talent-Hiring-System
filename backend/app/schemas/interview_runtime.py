"""
PATHS Backend — Interview Intelligence runtime schemas.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Sessions ──────────────────────────────────────────────────────────────


class CreateInterviewSessionIn(BaseModel):
    application_id: UUID | None = None
    candidate_id: UUID | None = None
    job_id: UUID | None = None
    organization_id: UUID | None = None
    interview_type: str = "mixed"   # hr | technical | mixed
    difficulty: str | None = None   # junior | mid | senior
    num_questions: int | None = None
    follow_ups_enabled: bool = True
    interview_mode: str = "text"    # text | voice (placeholder)


class CreateInterviewSessionOut(BaseModel):
    session_id: UUID
    status: str
    candidate_id: UUID
    job_id: UUID
    application_id: UUID


class InterviewSessionDetail(BaseModel):
    session: dict[str, Any]
    candidate: dict[str, Any]
    job: dict[str, Any]
    questions: list[dict[str, Any]] = Field(default_factory=list)
    turns: list[dict[str, Any]] = Field(default_factory=list)
    completed: bool = False


# ── Turns ────────────────────────────────────────────────────────────────


class AnswerTurnIn(BaseModel):
    question: str
    answer: str
    is_followup: bool = False
    parent_index: int | None = None


class AnswerTurnOut(BaseModel):
    index: int
    question: str
    answer: str
    asked_at: str | None = None
    answered_at: str | None = None
    is_followup: bool = False
    parent_index: int | None = None


class SessionTurnsOut(BaseModel):
    session_id: UUID
    completed: bool
    turns: list[dict[str, Any]] = Field(default_factory=list)


class FollowUpRequest(BaseModel):
    parent_index: int


class FollowUpResponse(BaseModel):
    question: str
    parent_index: int


class FinishInterviewResponse(BaseModel):
    ok: bool
    status: str
    turn_count: int
    already_completed: bool = False


# ── Reports ──────────────────────────────────────────────────────────────


class InterviewReportOut(BaseModel):
    session_id: UUID
    completed: bool
    interview_type: str | None = None
    status: str | None = None
    candidate: dict[str, Any]
    job: dict[str, Any]
    summary: dict[str, Any] | None = None
    evaluations: list[dict[str, Any]] = Field(default_factory=list)
    decision_packet: dict[str, Any] | None = None
    turns: list[dict[str, Any]] = Field(default_factory=list)
    # Real-meeting enrichment: recall transcript text, HR notes, the human
    # hiring decision, and recording metadata (video URL is fetched lazily
    # via the /recording sub-route so the report itself stays fast).
    transcript_text: str | None = None
    hr_notes: str | None = None
    human_decision: dict[str, Any] | None = None
    recording: dict[str, Any] | None = None
