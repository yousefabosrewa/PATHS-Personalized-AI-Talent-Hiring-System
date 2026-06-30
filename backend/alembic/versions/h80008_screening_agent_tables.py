"""
PATHS Backend — Alembic migration: screening agent tables.

Creates ``screening_runs`` and ``screening_results`` for the new
Screening Agent that scores + ranks all candidates for a given job.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision = "h80008screening"
down_revision = "g70007candprof"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── screening_runs ──────────────────────────────────────────────────
    op.create_table(
        "screening_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="database",
        ),
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="10"),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("total_candidates_scanned", sa.Integer(), server_default="0"),
        sa.Column("candidates_passed_filter", sa.Integer(), server_default="0"),
        sa.Column("candidates_scored", sa.Integer(), server_default="0"),
        sa.Column("candidates_failed", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── screening_results ───────────────────────────────────────────────
    op.create_table(
        "screening_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "screening_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("screening_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("blind_label", sa.String(60), nullable=False, server_default="Candidate"),
        sa.Column("rank_position", sa.Integer(), nullable=True),
        sa.Column("agent_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("vector_similarity_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("final_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("recommendation", sa.String(40), nullable=True),
        sa.Column("match_classification", sa.String(40), nullable=True),
        sa.Column("criteria_breakdown", JSON(), nullable=True),
        sa.Column("matched_skills", JSON(), nullable=True),
        sa.Column("missing_required_skills", JSON(), nullable=True),
        sa.Column("missing_preferred_skills", JSON(), nullable=True),
        sa.Column("strengths", JSON(), nullable=True),
        sa.Column("weaknesses", JSON(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(40),
            nullable=False,
            server_default="ranked",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("screening_results")
    op.drop_table("screening_runs")
