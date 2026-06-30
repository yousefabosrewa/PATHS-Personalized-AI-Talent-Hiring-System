"""interview HR notes (INST.md §8/§9)

Revision ID: w220022interviewhrnotes
Revises: v210021candidatemerge
Create Date: 2026-05-28 16:00:00.000000

Adds ``hr_notes`` to ``interviews`` so recruiter observations persist with
the interview and feed Run Analysis. Additive and safe.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "w220022interviewhrnotes"
down_revision = "v210021candidatemerge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("hr_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("interviews", "hr_notes")
