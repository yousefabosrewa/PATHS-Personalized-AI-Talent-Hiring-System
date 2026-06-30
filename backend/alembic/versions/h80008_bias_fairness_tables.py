"""Phase 4 — bias & fairness tables

Revision ID: h80008biasfair
Revises: e50005abcdef
Create Date: 2026-04-27 12:00:00.000000

Adds:
  anonymized_views   — persisted PII-stripped candidate profiles
  bias_flags         — guardrail flags per scope
  de_anon_events     — audit trail for de-anonymization requests
  bias_audit_log     — append-only forensic log
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "h80008biasfair"
down_revision = "e50005abcdef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── anonymized_views ──────────────────────────────────────────────
    op.create_table(
        "anonymized_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("view_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("view_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stripped_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anonymized_views_candidate_id", "anonymized_views", ["candidate_id"])
    op.create_index("ix_anonymized_views_is_current", "anonymized_views", ["is_current"])

    # ── bias_flags ────────────────────────────────────────────────────
    op.create_table(
        "bias_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("scope_id", sa.String(255), nullable=False),
        sa.Column("rule", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bias_flags_org_id", "bias_flags", ["org_id"])
    op.create_index("ix_bias_flags_scope_id", "bias_flags", ["scope_id"])
    op.create_index("ix_bias_flags_status", "bias_flags", ["status"])

    # ── de_anon_events ────────────────────────────────────────────────
    op.create_table(
        "de_anon_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approver_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("purpose", sa.String(255), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("denied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approval_id"], ["hitl_approvals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_de_anon_events_candidate_id", "de_anon_events", ["candidate_id"])
    op.create_index("ix_de_anon_events_approval_id", "de_anon_events", ["approval_id"])
    op.create_index("ix_de_anon_events_org_id", "de_anon_events", ["org_id"])

    # ── bias_audit_log ────────────────────────────────────────────────
    op.create_table(
        "bias_audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(255), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("candidate_id", sa.String(255), nullable=True),
        sa.Column("job_id", sa.String(255), nullable=True),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column("detail_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bias_audit_log_event_type", "bias_audit_log", ["event_type"])
    op.create_index("ix_bias_audit_log_candidate_id", "bias_audit_log", ["candidate_id"])
    op.create_index("ix_bias_audit_log_created_at", "bias_audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("bias_audit_log")
    op.drop_table("de_anon_events")
    op.drop_table("bias_flags")
    op.drop_table("anonymized_views")
