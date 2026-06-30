"""outreach agent tables (Google integration + outreach sessions + bookings).

Additive migration. Adds:
  * google_integrations              — per-HR-user Google OAuth tokens
  * outreach_sessions                — one per outreach attempt
  * outreach_availability_windows    — HR availability per session
  * interview_bookings               — confirmed candidate slot + Meet link

Reuses existing ``audit_logs`` for outreach events. Existing tables remain
untouched.

Revision ID: j100010outreach
Revises: i90009evidence
Create Date: 2026-05-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# ── Revision metadata ────────────────────────────────────────────────────────
revision = "j100010outreach"
down_revision = "i90009evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── google_integrations ──────────────────────────────────────────────────
    op.create_table(
        "google_integrations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("google_email", sa.String(320), nullable=True),
        sa.Column("access_token_encrypted", sa.Text, nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=True),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="connected"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index("ix_google_integrations_user_id", "google_integrations", ["user_id"])

    # ── outreach_sessions ────────────────────────────────────────────────────
    op.create_table(
        "outreach_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "hr_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("subject", sa.Text, nullable=True),
        sa.Column("email_body", sa.Text, nullable=True),
        sa.Column("recipient_email", sa.String(320), nullable=True),
        sa.Column("interview_type", sa.String(64), nullable=True),
        sa.Column("interview_duration_minutes", sa.Integer, nullable=False, server_default="30"),
        sa.Column("buffer_minutes", sa.Integer, nullable=False, server_default="10"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Africa/Cairo"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("booked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("meta_json", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index("ix_outreach_sessions_candidate_id", "outreach_sessions", ["candidate_id"])
    op.create_index("ix_outreach_sessions_job_id", "outreach_sessions", ["job_id"])
    op.create_index("ix_outreach_sessions_org_id", "outreach_sessions", ["organization_id"])
    op.create_index("ix_outreach_sessions_token_hash", "outreach_sessions", ["token_hash"])
    op.create_index("ix_outreach_sessions_status", "outreach_sessions", ["status"])

    # ── outreach_availability_windows ────────────────────────────────────────
    op.create_table(
        "outreach_availability_windows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "outreach_session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("outreach_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day_of_week", sa.Integer, nullable=False),  # 0=Mon..6=Sun
        sa.Column("start_time", sa.String(8), nullable=False),  # HH:MM
        sa.Column("end_time", sa.String(8), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Africa/Cairo"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_outreach_availability_session",
        "outreach_availability_windows",
        ["outreach_session_id"],
    )

    # ── interview_bookings ───────────────────────────────────────────────────
    op.create_table(
        "interview_bookings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "outreach_session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("outreach_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "hr_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("selected_start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("selected_end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Africa/Cairo"),
        sa.Column("google_calendar_event_id", sa.String(255), nullable=True),
        sa.Column("google_meet_link", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="confirmed"),
        sa.Column("meta_json", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index("ix_interview_bookings_session", "interview_bookings", ["outreach_session_id"])
    op.create_index("ix_interview_bookings_candidate", "interview_bookings", ["candidate_id"])
    op.create_index("ix_interview_bookings_job", "interview_bookings", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_interview_bookings_job", table_name="interview_bookings")
    op.drop_index("ix_interview_bookings_candidate", table_name="interview_bookings")
    op.drop_index("ix_interview_bookings_session", table_name="interview_bookings")
    op.drop_table("interview_bookings")

    op.drop_index(
        "ix_outreach_availability_session",
        table_name="outreach_availability_windows",
    )
    op.drop_table("outreach_availability_windows")

    op.drop_index("ix_outreach_sessions_status", table_name="outreach_sessions")
    op.drop_index("ix_outreach_sessions_token_hash", table_name="outreach_sessions")
    op.drop_index("ix_outreach_sessions_org_id", table_name="outreach_sessions")
    op.drop_index("ix_outreach_sessions_job_id", table_name="outreach_sessions")
    op.drop_index("ix_outreach_sessions_candidate_id", table_name="outreach_sessions")
    op.drop_table("outreach_sessions")

    op.drop_index("ix_google_integrations_user_id", table_name="google_integrations")
    op.drop_table("google_integrations")
