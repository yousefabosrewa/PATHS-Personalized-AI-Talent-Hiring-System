"""
PATHS Backend — Screening Agent ORM models.

Tracks screening runs (job → candidates scoring + ranking) and
individual per-candidate results.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.db.models.base import Base


class ScreeningRun(Base):
    """One execution of the Screening Agent for a specific job."""

    __tablename__ = "screening_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source = Column(
        String(50), nullable=False, default="database",
        comment="'database' or 'csv_upload'",
    )
    top_k = Column(Integer, nullable=False, default=10)
    status = Column(
        String(30), nullable=False, default="pending",
        comment="pending | running | completed | failed",
    )

    # Counters
    total_candidates_scanned = Column(Integer, default=0)
    candidates_passed_filter = Column(Integer, default=0)
    candidates_scored = Column(Integer, default=0)
    candidates_failed = Column(Integer, default=0)

    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
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

    # Relationships
    results = relationship(
        "ScreeningResult",
        back_populates="screening_run",
        cascade="all, delete-orphan",
        order_by="ScreeningResult.rank_position",
    )
    bias_reports = relationship(
        "BiasReport",
        back_populates="screening_run",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<ScreeningRun id={self.id} job_id={self.job_id} "
            f"source={self.source} status={self.status}>"
        )


class ScreeningResult(Base):
    """Per-candidate score + rank within a screening run."""

    __tablename__ = "screening_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    screening_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("screening_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Anonymized label shown to the HR user (e.g. "Candidate A")
    blind_label = Column(String(60), nullable=False, default="Candidate")
    rank_position = Column(Integer, nullable=True)

    # Scores
    agent_score = Column(Float, nullable=False, default=0.0)
    vector_similarity_score = Column(Float, nullable=False, default=0.0)
    final_score = Column(Float, nullable=False, default=0.0)
    relevance_score = Column(Float, nullable=True)

    # Classification
    recommendation = Column(String(40), nullable=True)
    match_classification = Column(String(40), nullable=True)

    # Detailed breakdown
    criteria_breakdown = Column(JSON, nullable=True)
    matched_skills = Column(JSON, nullable=True)
    missing_required_skills = Column(JSON, nullable=True)
    missing_preferred_skills = Column(JSON, nullable=True)
    strengths = Column(JSON, nullable=True)
    weaknesses = Column(JSON, nullable=True)
    explanation = Column(Text, nullable=True)

    # Status within the run
    status = Column(
        String(40), nullable=False, default="ranked",
        comment="ranked | shortlisted | approved_for_outreach",
    )

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

    # Relationships
    screening_run = relationship("ScreeningRun", back_populates="results")

    def __repr__(self) -> str:
        return (
            f"<ScreeningResult id={self.id} candidate={self.candidate_id} "
            f"rank={self.rank_position} score={self.final_score}>"
        )
