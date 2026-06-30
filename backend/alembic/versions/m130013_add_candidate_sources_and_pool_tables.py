"""add candidate source provenance + pool tables

Revision ID: m130013candidatesources
Revises: l120012addassessments
Create Date: 2026-05-09 14:00:00.000000

This migration adds the four tables used by the Candidate Sources / Pool
Builder feature plus the three columns on `candidates` that record where
each candidate originally came from. All changes are additive:

  candidates.source_type           string, NOT NULL, default 'paths_profile'
  candidates.source_platform       string, nullable
  candidates.owner_organization_id uuid,   nullable, FK organizations.id

  organization_candidate_source_settings   one row per org
  job_candidate_pool_configs               one row per job
  candidate_pool_runs                      pool snapshots
  candidate_pool_members                   per-candidate per-run

The candidates backfill assumes every existing row was a PATHS profile
(user_id IS NOT NULL was the only path that wrote candidates rows pre-m130).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "m130013candidatesources"
down_revision = "l120012addassessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── candidates: provenance columns ──────────────────────────────────
    op.add_column(
        "candidates",
        sa.Column(
            "source_type",
            sa.String(length=32),
            nullable=False,
            server_default="paths_profile",
        ),
    )
    op.add_column(
        "candidates",
        sa.Column("source_platform", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "candidates",
        sa.Column(
            "owner_organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_candidates_owner_organization_id",
        "candidates",
        ["owner_organization_id"],
    )
    op.create_index(
        "ix_candidates_source_type",
        "candidates",
        ["source_type"],
    )

    # ── org-level default source settings ───────────────────────────────
    op.create_table(
        "organization_candidate_source_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("use_paths_profiles_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_sourced_candidates_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_uploaded_candidates_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_job_fair_candidates_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("use_ats_candidates_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_top_k", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("default_min_profile_completeness", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("default_min_evidence_confidence", sa.Integer(), nullable=False, server_default="20"),
        sa.Column(
            "updated_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_org_source_settings_org_id",
        "organization_candidate_source_settings",
        ["organization_id"],
    )

    # ── per-job pool config ─────────────────────────────────────────────
    op.create_table(
        "job_candidate_pool_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("use_paths_profiles", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_sourced_candidates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_uploaded_candidates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_job_fair_candidates", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("use_ats_candidates", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("min_profile_completeness", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("min_evidence_confidence", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("filters_json", JSONB, nullable=True),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_job_pool_config_job_id",
        "job_candidate_pool_configs",
        ["job_id"],
    )
    op.create_index(
        "ix_job_pool_config_org_id",
        "job_candidate_pool_configs",
        ["organization_id"],
    )

    # ── candidate pool runs ─────────────────────────────────────────────
    op.create_table(
        "candidate_pool_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "config_id",
            UUID(as_uuid=True),
            sa.ForeignKey("job_candidate_pool_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("total_candidates_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_removed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("eligible_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("excluded_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_breakdown", JSONB, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="preview"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pool_run_job_id", "candidate_pool_runs", ["job_id"])
    op.create_index("ix_pool_run_org_id", "candidate_pool_runs", ["organization_id"])

    # ── candidate pool members ──────────────────────────────────────────
    op.create_table(
        "candidate_pool_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pool_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidate_pool_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("eligibility_status", sa.String(length=48), nullable=False),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column("profile_completeness", sa.Integer(), nullable=True),
        sa.Column("evidence_confidence", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pool_run_id", "candidate_id", name="uq_pool_run_candidate"),
    )
    op.create_index("ix_pool_member_run_id", "candidate_pool_members", ["pool_run_id"])
    op.create_index("ix_pool_member_candidate_id", "candidate_pool_members", ["candidate_id"])
    op.create_index(
        "ix_pool_member_eligibility",
        "candidate_pool_members",
        ["pool_run_id", "eligibility_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_pool_member_eligibility", table_name="candidate_pool_members")
    op.drop_index("ix_pool_member_candidate_id", table_name="candidate_pool_members")
    op.drop_index("ix_pool_member_run_id", table_name="candidate_pool_members")
    op.drop_table("candidate_pool_members")

    op.drop_index("ix_pool_run_org_id", table_name="candidate_pool_runs")
    op.drop_index("ix_pool_run_job_id", table_name="candidate_pool_runs")
    op.drop_table("candidate_pool_runs")

    op.drop_index("ix_job_pool_config_org_id", table_name="job_candidate_pool_configs")
    op.drop_index("ix_job_pool_config_job_id", table_name="job_candidate_pool_configs")
    op.drop_table("job_candidate_pool_configs")

    op.drop_index(
        "ix_org_source_settings_org_id",
        table_name="organization_candidate_source_settings",
    )
    op.drop_table("organization_candidate_source_settings")

    op.drop_index("ix_candidates_source_type", table_name="candidates")
    op.drop_index("ix_candidates_owner_organization_id", table_name="candidates")
    op.drop_column("candidates", "owner_organization_id")
    op.drop_column("candidates", "source_platform")
    op.drop_column("candidates", "source_type")
