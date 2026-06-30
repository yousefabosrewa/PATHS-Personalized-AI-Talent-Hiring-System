"""external candidate sourcing tables (fix6.md)

Revision ID: r180018externalsourcing
Revises: q170017orgmemberinvite
Create Date: 2026-05-28 03:00:00.000000

Adds the two tables that back the recruiter Source Candidate flow:

  * ``external_candidate_batches`` — one row per Add-to-Process click. Tracks
    provider, requester, requested/fetched counts, and audit metadata.
  * ``external_candidates``        — one row per fetched external profile.
    Holds the raw provider payload until the recruiter clicks Import, at
    which point ``imported_candidate_id`` is populated and ``import_status``
    flips to ``imported`` / ``duplicate``.

The schema is designed to live alongside the existing sourced-candidates
flow (which writes straight into ``candidates`` + ``candidate_sources``).
The new "preview before import" workflow is what the recruiter spec asks
for and what the agent explanation later consumes.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "r180018externalsourcing"
down_revision = "q170017orgmemberinvite"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_candidate_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column(
            "requested_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "role_category",
            sa.String(length=32),
            nullable=False,
            server_default="technical",
        ),
        sa.Column(
            "requested_count",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
        sa.Column(
            "fetched_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="completed",
        ),
        sa.Column("keywords", JSONB, nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_external_candidate_batches_org_created",
        "external_candidate_batches",
        ["organization_id", "created_at"],
    )

    op.create_table(
        "external_candidates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("external_candidate_batches.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("profile_url", sa.Text(), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("current_title", sa.String(length=255), nullable=True),
        sa.Column("current_company", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column(
            "skills",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("open_to_work_signal", sa.Boolean(), nullable=True),
        sa.Column("open_to_work_evidence", sa.Text(), nullable=True),
        sa.Column("technical_role_evidence", sa.Text(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column(
            "import_status",
            sa.String(length=32),
            nullable=False,
            server_default="ready_to_import",
        ),
        sa.Column(
            "imported_candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_external_candidates_org_provider_url",
        "external_candidates",
        ["organization_id", "provider", "profile_url"],
        unique=True,
        postgresql_where=sa.text("profile_url IS NOT NULL"),
    )
    op.create_index(
        "ix_external_candidates_status",
        "external_candidates",
        ["organization_id", "import_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_candidates_status",
        table_name="external_candidates",
    )
    op.drop_index(
        "ix_external_candidates_org_provider_url",
        table_name="external_candidates",
    )
    op.drop_table("external_candidates")
    op.drop_index(
        "ix_external_candidate_batches_org_created",
        table_name="external_candidate_batches",
    )
    op.drop_table("external_candidate_batches")
