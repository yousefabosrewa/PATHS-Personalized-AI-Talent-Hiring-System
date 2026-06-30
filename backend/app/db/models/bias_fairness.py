"""
PATHS Backend — Bias & Fairness models (Phase 4).

Tables:
  anonymized_views  — persisted PII-stripped candidate profile (per candidate, versioned).
  bias_flags        — flags raised by the guardrail for a job / scoring run / candidate.
  de_anon_events    — audit trail every time a full profile is revealed.
  bias_audit_log    — append-only forensic log for all bias-relevant events.

Blueprint laws enforced here:
  Law #2: "Anonymize before evaluate, de-anonymize only on outreach approval."
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


# ── Anonymized Views ──────────────────────────────────────────────────────────


class AnonymizedView(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Persisted PII-free projection of a candidate profile.

    One row per (candidate_id, view_version). Only the row with
    is_current=True is used by the scoring pipeline.

    ``view_json`` is the canonical anonymized shape consumed by agents.
    It never contains: name, email, phone, photo, age, gender, nationality,
    address, social IDs, religion, race, or ethnicity.
    """

    __tablename__ = "anonymized_views"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    view_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # The stripped profile JSON — what agents actually see.
    view_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Which fields were stripped (for audit replay).
    stripped_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Fingerprint of the source candidate row — if the candidate profile changes,
    # the view is regenerated and version is bumped.
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


# ── Bias Flags ────────────────────────────────────────────────────────────────


class BiasFlag(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A flag raised by the bias guardrail.

    Flags are associated with a scope (job, scoring_run, candidate)
    and a specific rule that triggered the flag.
    """

    __tablename__ = "bias_flags"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope: Mapped[str] = mapped_column(String(50), nullable=False)   # job | scoring_run | candidate | application
    scope_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    rule: Mapped[str] = mapped_column(String(100), nullable=False)    # e.g. "pii_in_scoring_input", "missing_anonymized_view"
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")  # low | medium | high | critical
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")      # open | reviewed | dismissed
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ── De-anonymization Events ───────────────────────────────────────────────────


class DeAnonEvent(Base, UUIDPrimaryKeyMixin):
    """Audit record created whenever a recruiter requests access to a
    candidate's full (non-anonymized) profile.

    The event starts with ``granted_at=None`` (pending HITL approval) and
    is updated once the linked HITLApproval is decided.
    """

    __tablename__ = "de_anon_events"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # FK to hitl_approvals — the approval that gates the reveal.
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hitl_approvals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)   # e.g. "outreach", "final_decision"
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    denied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


# ── Bias Audit Log ────────────────────────────────────────────────────────────


class BiasAuditLog(Base):
    """Append-only forensic log for every bias-relevant event in the pipeline.

    This table is intentionally write-once: rows are never updated or deleted.
    In production it should be backed by an object-lock bucket.

    Event types:
      scoring_started          — a scoring run began for a candidate
      anonymized_view_created  — a new anonymized view was persisted
      anonymized_view_used     — the scoring agent consumed an anonymized view
      pii_access_blocked       — a request to score without an anonymized view was blocked
      deanon_requested         — a user requested de-anonymization
      deanon_granted           — de-anonymization was approved
      deanon_denied            — de-anonymization was rejected
      bias_flag_raised         — guardrail raised a bias flag
    """

    __tablename__ = "bias_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    candidate_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )
