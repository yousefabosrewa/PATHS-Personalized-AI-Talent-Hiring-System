"""add organization website column

Revision ID: n140014organizationwebsite
Revises: m130013candidatesources
Create Date: 2026-05-23 22:00:00.000000

Additive — single nullable VARCHAR(2048) on organizations.website. No backfill.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "n140014organizationwebsite"
down_revision = "m130013candidatesources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("website", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "website")
