"""add Recall.ai notetaker fields to interviews

Revision ID: o150015interviewrecall
Revises: n140014organizationwebsite, a1b2c3d4e5f6
Create Date: 2026-05-24 11:00:00.000000

Additive — every new column is nullable. Captures Recall.ai bot id,
recording id, transcript id, status, status message, the JSON transcript
blob, the on-disk transcript path, and the HR-chosen recording mode
("post_meeting" | "real_time").

This revision doubles as a merge point: the repo had two divergent heads
(``n140014organizationwebsite`` on the main line and ``a1b2c3d4e5f6`` on
the agent_runs side branch). Declaring both as parents collapses them
into one head again so ``alembic upgrade head`` doesn't error.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "o150015interviewrecall"
down_revision = ("n140014organizationwebsite", "a1b2c3d4e5f6")
branch_labels = None
depends_on = None


_NEW_COLUMNS = (
    sa.Column("recall_recording_mode", sa.String(length=32), nullable=True),
    sa.Column("recall_bot_id", sa.String(length=64), nullable=True),
    sa.Column("recall_recording_id", sa.String(length=64), nullable=True),
    sa.Column("recall_transcript_id", sa.String(length=64), nullable=True),
    sa.Column("recall_status", sa.String(length=32), nullable=True),
    sa.Column("recall_status_message", sa.Text(), nullable=True),
    sa.Column(
        "recall_transcript_json",
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
    ),
    sa.Column("recall_transcript_path", sa.Text(), nullable=True),
)


def upgrade() -> None:
    for col in _NEW_COLUMNS:
        op.add_column("interviews", col)
    # Index on bot_id so the webhook receiver can look the interview up
    # by Recall's bot id in O(log n) instead of scanning the table.
    op.create_index(
        "ix_interviews_recall_bot_id",
        "interviews",
        ["recall_bot_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_interviews_recall_bot_id", table_name="interviews")
    for col in _NEW_COLUMNS:
        op.drop_column("interviews", col.name)
