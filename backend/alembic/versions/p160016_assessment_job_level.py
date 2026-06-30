"""assessment job-level template fields (fix5.md)

Revision ID: p160016assessmentjoblevel
Revises: o150015interviewrecall
Create Date: 2026-05-26 06:00:00.000000

Refactor the ``assessments`` table from "one row per candidate attempt" to
"one job-level template that can be reused for every candidate of that
job". Existing rows are preserved.

Changes:
  * application_id / candidate_id become NULLABLE so we can store
    templates that are not tied to a single candidate. Existing rows
    keep their values.
  * Add description, difficulty, duration_minutes, total_score columns.
  * Add a structured ``questions`` JSON column for generated questions.
  * Add agent_metadata, source_file_id, source_file_name columns.
  * Add created_by, approved_by, approved_at columns for the
    draft → approve workflow.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "p160016assessmentjoblevel"
down_revision = "o150015interviewrecall"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "assessments", "application_id", existing_type=UUID(as_uuid=True), nullable=True,
    )
    op.alter_column(
        "assessments", "candidate_id", existing_type=UUID(as_uuid=True), nullable=True,
    )

    op.add_column(
        "assessments",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("difficulty", sa.String(20), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("total_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("questions", sa.JSON(), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("agent_metadata", sa.JSON(), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("source_file_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("source_file_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assessments", "approved_at")
    op.drop_column("assessments", "approved_by")
    op.drop_column("assessments", "created_by")
    op.drop_column("assessments", "source_file_name")
    op.drop_column("assessments", "source_file_id")
    op.drop_column("assessments", "agent_metadata")
    op.drop_column("assessments", "questions")
    op.drop_column("assessments", "total_score")
    op.drop_column("assessments", "duration_minutes")
    op.drop_column("assessments", "difficulty")
    op.drop_column("assessments", "description")
    op.alter_column(
        "assessments", "candidate_id", existing_type=UUID(as_uuid=True), nullable=False,
    )
    op.alter_column(
        "assessments", "application_id", existing_type=UUID(as_uuid=True), nullable=False,
    )
