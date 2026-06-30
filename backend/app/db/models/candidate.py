"""
PATHS Backend — Candidate model.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Candidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "candidates"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, unique=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Additional emails the candidate can be reached at, beyond the primary
    # (sign-in) email above. Also used to verify that linked GitHub / LinkedIn
    # profiles belong to them. Captured during onboarding ("Other email addresses").
    other_emails: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    career_level: Mapped[str | None] = mapped_column(String(80), nullable=True)
    skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    open_to_job_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    open_to_workplace_settings: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    desired_job_titles: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    desired_job_categories: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")

    # Source provenance — added in m130013. See app/core/candidate_sources.py
    # for the canonical taxonomy. Defaults to "paths_profile" because every
    # pre-existing candidate row had user_id IS NOT NULL (i.e. came from a
    # PATHS account). The migration backfills accordingly.
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="paths_profile",
    )
    source_platform: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
    )
    # If non-NULL, the candidate is owned by a specific organization
    # (uploaded/sourced/job-fair). If NULL, the candidate is a public PATHS
    # profile visible to any organization that enables PATHS_PROFILE source.
    owner_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True,
    )

    # ── Duplicate merge (fix2_1.md Feature 2) ────────────────────────────────
    # When a candidate is merged into another (canonical) record, the duplicate
    # is soft-archived: is_merged_duplicate=True, merged_into_candidate_id points
    # at the canonical record, and status flips to "merged". Canonical records
    # keep these NULL/False.
    merged_into_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=True, index=True,
    )
    is_merged_duplicate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    duplicate_merge_group_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
    )

    # Relationships
    user = relationship("User", back_populates="candidate_profile", lazy="selectin")
    applications = relationship("Application", back_populates="candidate", lazy="selectin")
    evidence_items = relationship("EvidenceItem", back_populates="candidate", lazy="dynamic",
                                  cascade="all, delete-orphan")
    candidate_sources = relationship("CandidateSource", back_populates="candidate", lazy="dynamic",
                                     cascade="all, delete-orphan")
