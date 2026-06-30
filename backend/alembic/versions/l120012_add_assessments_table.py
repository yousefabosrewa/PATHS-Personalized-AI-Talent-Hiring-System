"""add assesssments table

Revision ID: l120012addassessments
Revises: 645c2cc8c6ac
Create Date: 2026-05-08 17:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "l120012addassessments"
down_revision = "645c2cc8c6ac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "application_id",
            UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False, server_default=sa.text("'Skills Assessment'")),
        sa.Column(
            "assessment_type",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'coding'"),
        ),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=True),
        sa.Column("score_percent", sa.Float(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("submission_text", sa.Text(), nullable=True),
        sa.Column("submission_uri", sa.String(500), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("criteria_breakdown", sa.JSON(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_assessments_organization_id", "assessments", ["organization_id"])
    op.create_index("ix_assessments_application_id", "assessments", ["application_id"])
    op.create_index("ix_assessments_candidate_id", "assessments", ["candidate_id"])
    op.create_index("ix_assessments_job_id", "assessments", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_assessments_job_id", table_name="assessments")
    op.drop_index("ix_assessments_candidate_id", table_name="assessments")
    op.drop_index("ix_assessments_application_id", table_name="assessments")
    op.drop_index("ix_assessments_organization_id", table_name="assessments")
    op.drop_table("assessments")
