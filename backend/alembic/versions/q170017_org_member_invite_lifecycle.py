"""organization member invite lifecycle (fix8&9 Update 2)

Revision ID: q170017orgmemberinvite
Revises: p160016assessmentjoblevel
Create Date: 2026-05-27 06:00:00.000000

Adds the invite/activation lifecycle fields to ``organization_members``:

  * ``status`` — pending | active | suspended (default "active" so existing
    rows keep working).
  * ``invited_at`` — when the invite was created.
  * ``activated_at`` — when status flipped to active.
  * ``first_login_at`` — when the invited user first signed in.
  * ``invited_by_user_id`` — FK to ``users.id`` (nullable).

Existing rows: ``status`` defaults to ``'active'``, ``activated_at`` is set
to ``joined_at`` so they're consistent.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "q170017orgmemberinvite"
down_revision = "p160016assessmentjoblevel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organization_members",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.add_column(
        "organization_members",
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_members",
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_members",
        sa.Column("first_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_members",
        sa.Column("invited_by_user_id", UUID(as_uuid=True), nullable=True),
    )

    # Backfill: any existing row is treated as an already-active member.
    op.execute(
        """
        UPDATE organization_members
        SET activated_at = joined_at,
            status = 'active'
        WHERE activated_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("organization_members", "invited_by_user_id")
    op.drop_column("organization_members", "first_login_at")
    op.drop_column("organization_members", "activated_at")
    op.drop_column("organization_members", "invited_at")
    op.drop_column("organization_members", "status")
