"""
PATHS Backend — External candidate sourcing models (fix6.md).

The recruiter "Source Candidate" page fetches small batches (5 at a time)
of technical open-to-work candidates from external providers and shows a
preview list before any candidate account is created. These two tables
hold that intermediate state:

    external_candidate_batches  — one row per Add-to-Process click
    external_candidates         — one row per fetched profile, with
                                  ``import_status`` flipping when the
                                  recruiter clicks Import.

A row in ``external_candidates`` is *not* yet a Candidate. Once imported,
``imported_candidate_id`` points at the row in ``candidates`` and the
candidate behaves like any other (matching, shortlisting, outreach,
agent explanations).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class ExternalCandidateBatch(Base):
    __tablename__ = "external_candidate_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    role_category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="technical",
    )
    requested_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5,
    )
    fetched_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="completed",
    )
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    candidates = relationship(
        "ExternalCandidate",
        back_populates="batch",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class ExternalCandidate(Base):
    __tablename__ = "external_candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_candidate_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    open_to_work_signal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    open_to_work_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    technical_role_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    import_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ready_to_import",
    )
    imported_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    imported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    batch = relationship("ExternalCandidateBatch", back_populates="candidates")
