"""candidate duplicate merge fields + audit (fix2_1.md Feature 2)

Revision ID: v210021candidatemerge
Revises: t200020companyknowledge
Create Date: 2026-05-28 14:30:00.000000

Adds soft-merge bookkeeping to ``candidates`` and a ``candidate_merge_audit``
table. Existing rows default to not-merged. Additive and safe.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "v210021candidatemerge"
down_revision = "t200020companyknowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column(
            "merged_into_candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidates.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "candidates",
        sa.Column(
            "is_merged_duplicate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "candidates",
        sa.Column("duplicate_merge_group_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_candidates_merged_into",
        "candidates",
        ["merged_into_candidate_id"],
    )

    op.create_table(
        "candidate_merge_audit",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "canonical_candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("merged_candidate_ids", JSONB, nullable=False),
        sa.Column(
            "merge_reason",
            sa.String(length=64),
            nullable=False,
            server_default="exact_name_email_phone_match",
        ),
        sa.Column(
            "performed_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("details", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("candidate_merge_audit")
    op.drop_index("ix_candidates_merged_into", table_name="candidates")
    op.drop_column("candidates", "duplicate_merge_group_id")
    op.drop_column("candidates", "is_merged_duplicate")
    op.drop_column("candidates", "merged_into_candidate_id")
