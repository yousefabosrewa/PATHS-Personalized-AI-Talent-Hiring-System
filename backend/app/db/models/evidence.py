"""
PATHS Backend — Evidence & Source models (Phase 2 completion).

Blueprint Law #1: "Evidence over inference."
Every claim an agent makes must reference a persisted evidence_item.

Tables
------
evidence_items     — one row per extracted entity (skill, experience, etc.)
candidate_sources  — one row per external document/profile fetched for a candidate
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class EvidenceItem(Base):
    """
    One row per extracted/verified fact about a candidate.

    type values (open enum — extend as new pipeline stages are added):
      cv_claim            — extracted from a CV/resume
      github_repo         — scraped from GitHub
      portfolio_artifact  — portfolio or project URL
      assessment          — from a coding test or skills assessment
      interview           — statement from an interview transcript
      manual              — manually entered by a recruiter
    """
    __tablename__ = "evidence_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The ingestion job that produced this item (nullable — manual items have no job)
    ingestion_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # What kind of evidence this is
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Human-readable field name this evidence maps to
    # e.g. "skill:python", "experience:0", "education:0", "certification:AWS"
    field_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Source URI — document path, GitHub URL, etc.
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The actual extracted text that backs this claim
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 0.0 – 1.0 confidence from the extraction model (NULL = no score available)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Extra structured data (e.g. skill category, company name, degree)
    meta_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    candidate = relationship("Candidate", back_populates="evidence_items", lazy="select")

    __table_args__ = (
        Index("ix_evidence_items_candidate_type", "candidate_id", "type"),
        Index("ix_evidence_items_job", "ingestion_job_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EvidenceItem id={self.id!s:.8} type={self.type} candidate={self.candidate_id!s:.8}>"


class CandidateSource(Base):
    """
    One row per external document or profile fetched for a candidate.

    source values:
      cv          — uploaded CV/résumé file
      linkedin    — LinkedIn profile scrape
      github      — GitHub profile
      portfolio   — personal website / portfolio
      manual      — manually added by recruiter
    """
    __tablename__ = "candidate_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Path / URI to the stored raw blob (e.g. S3 key, local path)
    raw_blob_uri: Mapped[str | None] = mapped_column(Text, nullable=True)

    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    candidate = relationship("Candidate", back_populates="candidate_sources", lazy="select")

    __table_args__ = (
        Index("ix_candidate_sources_candidate", "candidate_id"),
        Index("ix_candidate_sources_source", "source"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CandidateSource id={self.id!s:.8} source={self.source} candidate={self.candidate_id!s:.8}>"
