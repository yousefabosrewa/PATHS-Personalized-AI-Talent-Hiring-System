"""evidence_items and candidate_sources tables (Phase 2 completion)

Revision ID: i90009evidence
Revises: h80008biasfair
Create Date: 2026-04-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# ── Revision metadata ────────────────────────────────────────────────────────
revision = "i90009evidence"
down_revision = "h80008biasfair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── evidence_items ────────────────────────────────────────────────────────
    op.create_table(
        "evidence_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ingestion_job_id", sa.String(64), nullable=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("field_ref", sa.String(255), nullable=True),
        sa.Column("source_uri", sa.Text, nullable=True),
        sa.Column("extracted_text", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("meta_json", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_evidence_items_candidate_id", "evidence_items", ["candidate_id"])
    op.create_index("ix_evidence_items_type", "evidence_items", ["type"])
    op.create_index(
        "ix_evidence_items_candidate_type", "evidence_items", ["candidate_id", "type"]
    )
    op.create_index(
        "ix_evidence_items_job", "evidence_items", ["ingestion_job_id"]
    )

    # ── candidate_sources ─────────────────────────────────────────────────────
    op.create_table(
        "candidate_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("raw_blob_uri", sa.Text, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_candidate_sources_candidate", "candidate_sources", ["candidate_id"]
    )
    op.create_index(
        "ix_candidate_sources_source", "candidate_sources", ["source"]
    )


def downgrade() -> None:
    op.drop_table("candidate_sources")
    op.drop_table("evidence_items")
