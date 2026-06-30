"""
PATHS Backend — Candidate merge audit (fix2_1.md Feature 2).

One row per duplicate-group merge. Records the canonical candidate that was
kept, the duplicate candidate ids that were merged into it, who performed
the merge, and the reason. Append-only.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, UUIDPrimaryKeyMixin


class CandidateMergeAudit(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "candidate_merge_audit"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # JSON array of merged (archived) candidate id strings.
    merged_candidate_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    merge_reason: Mapped[str] = mapped_column(
        String(64), nullable=False, default="exact_name_email_phone_match",
    )
    performed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    # Snapshot of what moved (counts of reassigned rows per table).
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
