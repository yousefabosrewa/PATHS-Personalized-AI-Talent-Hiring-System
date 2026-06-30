"""add identity resolution and contact enrichment tables

Revision ID: b66a0ffc95b0
Revises: l120012addassessments
Create Date: 2026-05-08 19:02:25.098952
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b66a0ffc95b0"
down_revision: Union[str, None] = "l120012addassessments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- candidate_duplicates ---
    op.create_table(
        "candidate_duplicates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id_a", sa.UUID(), nullable=False),
        sa.Column("candidate_id_b", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("match_reason", sa.String(length=100), nullable=False),
        sa.Column("match_value", sa.String(length=500), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("merged_into_candidate_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id_a"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id_b"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["merged_into_candidate_id"], ["candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_candidate_duplicates_organization_id"),
        "candidate_duplicates",
        ["organization_id"],
        unique=False,
    )

    # --- enriched_contacts ---
    op.create_table(
        "enriched_contacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column(
            "contact_type",
            sa.String(length=30),
            nullable=False,
            comment="email | phone | linkedin | github | portfolio",
        ),
        sa.Column("original_value", sa.String(length=500), nullable=False),
        sa.Column("enriched_value", sa.String(length=500), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="pending | approved | rejected",
        ),
        sa.Column(
            "source",
            sa.String(length=30),
            nullable=False,
            comment="manual | parsed_cv | email_validation | external_api",
        ),
        sa.Column("provenance", sa.Text(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_enriched_contacts_candidate_id"),
        "enriched_contacts",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_enriched_contacts_organization_id"),
        "enriched_contacts",
        ["organization_id"],
        unique=False,
    )

    # --- merge_history ---
    op.create_table(
        "merge_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("kept_candidate_id", sa.UUID(), nullable=False),
        sa.Column("removed_candidate_id", sa.UUID(), nullable=False),
        sa.Column("merged_by", sa.UUID(), nullable=False),
        sa.Column("merged_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("merge_reason", sa.Text(), nullable=True),
        sa.Column("audit_log", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["kept_candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["merged_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["removed_candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_merge_history_organization_id"),
        "merge_history",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_merge_history_organization_id"), table_name="merge_history")
    op.drop_table("merge_history")
    op.drop_index(op.f("ix_enriched_contacts_organization_id"), table_name="enriched_contacts")
    op.drop_index(op.f("ix_enriched_contacts_candidate_id"), table_name="enriched_contacts")
    op.drop_table("enriched_contacts")
    op.drop_index(op.f("ix_candidate_duplicates_organization_id"), table_name="candidate_duplicates")
    op.drop_table("candidate_duplicates")
