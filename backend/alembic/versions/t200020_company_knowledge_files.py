"""company knowledge files (fix2_1.md Feature 1)

Revision ID: t200020companyknowledge
Revises: s190019orglinkedinaccount
Create Date: 2026-05-28 14:00:00.000000

Adds ``company_knowledge_files`` — per-organisation company documents that
agents use as context. Additive only; no existing tables are touched.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "t200020companyknowledge"
down_revision = "s190019orglinkedinaccount"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_knowledge_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "uploaded_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column(
            "category", sa.String(length=64), nullable=False, server_default="other",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="uploaded",
        ),
        sa.Column(
            "is_legal_or_compliance_context",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_company_knowledge_files_org_status",
        "company_knowledge_files",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_company_knowledge_files_org_status",
        table_name="company_knowledge_files",
    )
    op.drop_table("company_knowledge_files")
