"""add application_mode, external_apply_url, visibility, created_by_user_id to jobs

Revision ID: 51a8d30455e1
Revises: b66a0ffc95b0
Create Date: 2026-05-10 06:09:16.895356
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "51a8d30455e1"
down_revision: Union[str, None] = "b66a0ffc95b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Add new columns to jobs table ---
    op.add_column(
        "jobs",
        sa.Column(
            "application_mode",
            sa.String(length=20),
            nullable=True,  # temporarily nullable for backfill
            comment="internal_apply | external_redirect",
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("external_apply_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "visibility",
            sa.String(length=20),
            nullable=True,  # temporarily nullable for backfill
            comment="public | private | org_only",
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # --- Backfill existing rows ---
    # Org-owned jobs → internal_apply
    op.execute(
        "UPDATE jobs SET application_mode = 'internal_apply', visibility = 'public' "
        "WHERE organization_id IS NOT NULL"
    )
    # Orphan scraped jobs → external_redirect
    op.execute(
        "UPDATE jobs SET application_mode = 'external_redirect', visibility = 'public', "
        "external_apply_url = source_url "
        "WHERE organization_id IS NULL"
    )

    # Now make application_mode and visibility NOT NULL
    op.alter_column("jobs", "application_mode", nullable=False)
    op.alter_column("jobs", "visibility", nullable=False)

    # --- Add FK constraint for created_by_user_id ---
    op.create_foreign_key(
        "fk_jobs_created_by_user", "jobs", "users",
        ["created_by_user_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_jobs_created_by_user", "jobs", type_="foreignkey",
    )
    op.drop_column("jobs", "created_by_user_id")
    op.drop_column("jobs", "visibility")
    op.drop_column("jobs", "external_apply_url")
    op.drop_column("jobs", "application_mode")
