"""organization linkedin account fields

Revision ID: s190019orglinkedinaccount
Revises: r180018externalsourcing
Create Date: 2026-05-28 03:30:00.000000

Adds per-organisation LinkedIn credentials so the recruiter can connect
their LinkedIn account from the Organization settings page. The MCP
LinkedIn sourcing provider uses these credentials to authenticate the
upstream linkedin-mcp-server browser session.

Columns added to ``organizations``:

  * ``linkedin_account_email``         display name / identification
  * ``linkedin_li_at_encrypted``       Fernet-encrypted li_at cookie
  * ``linkedin_jsessionid_encrypted``  optional, improves auth stability
  * ``linkedin_connected_at``          timestamp of last connect
  * ``linkedin_connected_by_user_id``  FK ``users`` (nullable)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "s190019orglinkedinaccount"
down_revision = "r180018externalsourcing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("linkedin_account_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("linkedin_li_at_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("linkedin_jsessionid_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("linkedin_connected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "linkedin_connected_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "linkedin_connected_by_user_id")
    op.drop_column("organizations", "linkedin_connected_at")
    op.drop_column("organizations", "linkedin_jsessionid_encrypted")
    op.drop_column("organizations", "linkedin_li_at_encrypted")
    op.drop_column("organizations", "linkedin_account_email")
