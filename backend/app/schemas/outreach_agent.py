"""
PATHS Backend — Outreach Agent Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Email generation ──────────────────────────────────────────────────────


class GenerateEmailRequest(BaseModel):
    candidate_id: UUID
    job_id: UUID | None = None
    interview_type: str | None = "HR Interview"
    is_final_offer: bool = False
    extra_instructions: str | None = None


class GeneratedEmailSchema(BaseModel):
    subject: str
    body: str
    model: str | None = None
    fallback: bool = False


# ── Sessions ──────────────────────────────────────────────────────────────


class AvailabilityWindowIn(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: str
    end_time: str
    timezone: str | None = None


class CreateSessionRequest(BaseModel):
    candidate_id: UUID
    job_id: UUID | None = None
    subject: str
    email_body: str
    interview_type: str | None = "HR Interview"
    duration_minutes: int = 30
    buffer_minutes: int = 10
    timezone: str = "Africa/Cairo"
    expires_at: datetime | None = None
    availability: list[AvailabilityWindowIn] = Field(default_factory=list)
    recipient_email: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: UUID
    status: str
    booking_link: str
    expires_at: datetime | None = None


class SendSessionResponse(BaseModel):
    ok: bool
    session_id: UUID
    status: str
    error: str | None = None
    gmail_message_id: str | None = None


class OutreachHistoryItem(BaseModel):
    id: UUID
    candidate_id: UUID
    job_id: UUID | None = None
    status: str
    subject: str | None = None
    interview_type: str | None = None
    sent_at: datetime | None = None
    booked_at: datetime | None = None
    expires_at: datetime | None = None
    last_error: str | None = None
    booking: dict[str, Any] | None = None


class OutreachHistoryResponse(BaseModel):
    candidate_id: UUID
    items: list[OutreachHistoryItem]


# ── Public scheduling ─────────────────────────────────────────────────────


class PublicSlot(BaseModel):
    start: str
    end: str
    timezone: str


class PublicScheduleResponse(BaseModel):
    organization_name: str | None = None
    job_title: str | None = None
    candidate_name: str | None = None
    interview_type: str | None = None
    duration_minutes: int = 30
    timezone: str = "UTC"
    expires_at: datetime | None = None
    booked: bool = False
    slots: list[PublicSlot] = Field(default_factory=list)
    booking: dict[str, Any] | None = None


class BookSlotRequest(BaseModel):
    selected_start_time: str
    selected_end_time: str


class BookSlotResponse(BaseModel):
    ok: bool
    error: str | None = None
    booking_id: UUID | None = None
    selected_start_time: str | None = None
    selected_end_time: str | None = None
    google_meet_link: str | None = None
    google_connected: bool = False


# ── Google integration ────────────────────────────────────────────────────


class GoogleStatusResponse(BaseModel):
    connected: bool
    configured: bool
    email: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)
    last_error: str | None = None


class GoogleConnectResponse(BaseModel):
    authorize_url: str
