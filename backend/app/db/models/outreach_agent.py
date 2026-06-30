"""
PATHS Backend — Outreach Agent models (Google + outreach + bookings).

Additive — every existing table remains untouched. The five tables
introduced here power the HR Outreach Agent flow (OAuth → email →
booking → Calendar event → Meet link).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GoogleIntegration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-HR-user Google OAuth credentials (encrypted at rest)."""

    __tablename__ = "google_integrations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    google_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="connected",
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutreachSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One outreach attempt: HR drafts, sends, and tracks booking."""

    __tablename__ = "outreach_sessions"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hr_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", index=True,
    )
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    interview_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    interview_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30,
    )
    buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Africa/Cairo",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    booked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class OutreachAvailabilityWindow(Base, UUIDPrimaryKeyMixin):
    """One HR availability window for an outreach session."""

    __tablename__ = "outreach_availability_windows"

    outreach_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outreach_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column(String(8), nullable=False)
    end_time: Mapped[str] = mapped_column(String(8), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Africa/Cairo",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class InterviewBooking(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Confirmed candidate slot with Calendar event and Meet link."""

    __tablename__ = "interview_bookings"
    __table_args__ = (
        UniqueConstraint("outreach_session_id", name="uq_booking_outreach_session"),
    )

    outreach_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outreach_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hr_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    selected_start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    selected_end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Africa/Cairo",
    )
    google_calendar_event_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    google_meet_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="confirmed",
    )
    meta_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
