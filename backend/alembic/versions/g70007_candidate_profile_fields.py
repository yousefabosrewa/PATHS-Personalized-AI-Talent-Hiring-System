"""add candidate preference/profile fields

Revision ID: g70007candprof
Revises: f60006dss
Create Date: 2026-04-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "g70007candprof"
down_revision: Union[str, None] = "f60006dss"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("career_level", sa.String(length=80), nullable=True))
    op.add_column("candidates", sa.Column("skills", postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column("candidates", sa.Column("open_to_job_types", postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column(
        "candidates", sa.Column("open_to_workplace_settings", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column("candidates", sa.Column("desired_job_titles", postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column("candidates", sa.Column("desired_job_categories", postgresql.ARRAY(sa.String()), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "desired_job_categories")
    op.drop_column("candidates", "desired_job_titles")
    op.drop_column("candidates", "open_to_workplace_settings")
    op.drop_column("candidates", "open_to_job_types")
    op.drop_column("candidates", "skills")
    op.drop_column("candidates", "career_level")
