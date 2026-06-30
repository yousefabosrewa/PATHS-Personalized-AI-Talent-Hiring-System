"""
PATHS Backend — Candidate sourcing & pool models.

These tables let a company answer "where do my candidates come from?" and
"who is in the pool for this job?" without conflating the two questions:

    organization_candidate_source_settings   org-level default toggles
    job_candidate_pool_config                per-job source toggles + filters
    candidate_pool_runs                      a snapshot of a built pool
    candidate_pool_members                   one row per candidate in a run

The candidate-level provenance fields (source_type / source_platform /
owner_organization_id) live on the `candidates` table itself — see the
m130013 migration. That table conflict is intentional: the existing
`candidate_sources` table already exists in evidence.py for *evidence*
provenance (CV/LinkedIn/GitHub) and we do not want to repurpose it.

Source taxonomy used across the platform:

    PATHS_PROFILE     candidates with PATHS user accounts who opted in
    SOURCED           collected by an outbound sourcing agent
    COMPANY_UPLOADED  uploaded by the company (CV/CSV/Excel/manual)
    JOB_FAIR          imported from a job-fair / university-event roster
    ATS_IMPORT        imported from an external ATS export
    MANUAL_ADD        manually keyed by a recruiter

The string values here MUST match `app.core.candidate_sources.SourceType`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


# ── Org-level default source toggles ─────────────────────────────────────


class OrganizationCandidateSourceSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    One row per organization. Defaults applied to new jobs unless the job
    creator overrides them in JobCandidatePoolConfig.
    """

    __tablename__ = "organization_candidate_source_settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    use_paths_profiles_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_sourced_candidates_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_uploaded_candidates_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_job_fair_candidates_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    use_ats_candidates_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Default minimums applied when a job uses defaults
    default_top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    default_min_profile_completeness: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    default_min_evidence_confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )


# ── Per-job pool config ──────────────────────────────────────────────────


class JobCandidatePoolConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    One row per job. Determines which candidate sources participate in the
    candidate pool for that job and the matching parameters.
    """

    __tablename__ = "job_candidate_pool_configs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    use_paths_profiles: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_sourced_candidates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_uploaded_candidates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_job_fair_candidates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    use_ats_candidates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    min_profile_completeness: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    min_evidence_confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    filters_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )


# ── Candidate pool run ──────────────────────────────────────────────────


class CandidatePoolRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single execution of CandidatePoolBuilderService — a snapshot of which
    candidates were considered eligible for a particular job at a particular
    time. Subsequent matching/screening runs reference a pool_run_id so the
    pool composition is auditable.
    """

    __tablename__ = "candidate_pool_runs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_candidate_pool_configs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Counts (denormalized for fast dashboard reads)
    total_candidates_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eligible_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    excluded_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Per-source counts as a JSON object: {"paths_profile": 14, "sourced": 22, ...}
    source_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # "preview" | "running" | "completed" | "failed"
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="preview")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    members = relationship(
        "CandidatePoolMember",
        back_populates="pool_run",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class CandidatePoolMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One row per candidate considered in a particular pool run."""

    __tablename__ = "candidate_pool_members"
    __table_args__ = (
        UniqueConstraint(
            "pool_run_id", "candidate_id",
            name="uq_pool_run_candidate",
        ),
        Index("ix_pool_member_eligibility", "pool_run_id", "eligibility_status"),
    )

    pool_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_pool_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The candidate's source as it appeared at the moment the pool was built.
    # Captured here rather than re-derived from candidates.source_type so the
    # pool snapshot is internally consistent even if a candidate is later
    # re-classified.
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # "eligible" | "excluded_incomplete_profile" | "excluded_low_evidence"
    # | "excluded_duplicate" | "excluded_source_disabled" | "excluded_consent"
    eligibility_status: Mapped[str] = mapped_column(String(48), nullable=False)
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile_completeness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    pool_run = relationship("CandidatePoolRun", back_populates="members")
