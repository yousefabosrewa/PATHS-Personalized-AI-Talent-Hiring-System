"""
PATHS Backend — Assessment Agent ORM model.

fix5.md refactor: assessments are now **job-level templates** generated
by the LLM agent, reviewed by HR as drafts, and then approved/published.
One approved assessment can be reused by every candidate applying to
the same job.

Backwards compatibility — ``application_id`` and ``candidate_id`` remain
on the model (nullable) so historic per-candidate attempts keep
rendering. New rows created via ``POST /assessments/generate-draft``
leave both of them ``NULL``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID

from app.db.models.base import Base


class Assessment(Base):
    """One assessment template (job-level) or attempt (legacy rows)."""

    __tablename__ = "assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Legacy per-attempt linkage — kept nullable for backwards compatibility.
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # The job an assessment template belongs to — REQUIRED.
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity / metadata
    title = Column(String(200), nullable=False, default="Skills Assessment")
    description = Column(Text, nullable=True)
    assessment_type = Column(
        String(50), nullable=False, default="technical_assessment",
        comment=(
            "technical_assessment | hr_assessment | iq_test | "
            "problem_solving_coding | problem_solving_thinking | quiz "
            "| (legacy types kept for backwards compatibility)"
        ),
    )
    difficulty = Column(
        String(20), nullable=True,
        comment="junior | intermediate | senior | expert",
    )
    duration_minutes = Column(Integer, nullable=True)
    total_score = Column(Integer, nullable=True)

    # Status — fix5.md adds the draft → approved/published workflow.
    status = Column(
        String(30), nullable=False, default="draft",
        comment=(
            "draft | approved | published | archived "
            "| (legacy: pending | in_progress | submitted | reviewed | expired)"
        ),
    )

    # ── Generated questions + agent metadata ────────────────────────────
    questions = Column(JSON, nullable=True)
    agent_metadata = Column(JSON, nullable=True)
    source_file_id = Column(UUID(as_uuid=True), nullable=True)
    source_file_name = Column(String(255), nullable=True)

    # ── Legacy per-candidate scoring fields (still used by old rows) ────
    score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    score_percent = Column(Float, nullable=True)
    instructions = Column(Text, nullable=True)
    submission_text = Column(Text, nullable=True)
    submission_uri = Column(String(500), nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    criteria_breakdown = Column(JSON, nullable=True)

    # ── Audit / workflow timestamps ─────────────────────────────────────
    created_by = Column(UUID(as_uuid=True), nullable=True)
    approved_by = Column(UUID(as_uuid=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    assigned_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Assessment id={self.id} type={self.assessment_type} "
            f"status={self.status} job_id={self.job_id}>"
        )
