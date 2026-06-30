"""platform admin + organization approval status + access requests.

Phase 1 of the platform-admin / company-approval rollout.

Adds (all additive — no destructive change to existing rows):
  * organizations.status                    (default 'active' for existing orgs
                                             so dashboards keep working)
  * organizations.approved_by_admin_id      (nullable FK -> users.id)
  * organizations.approved_at               (nullable timestamptz)
  * organizations.rejected_by_admin_id      (nullable FK -> users.id)
  * organizations.rejected_at               (nullable timestamptz)
  * organizations.rejection_reason          (nullable text)
  * organizations.suspended_at              (nullable timestamptz)
  * organizations.suspended_reason          (nullable text)
  * organization_access_requests             (new table)
  * users — no schema change (account_type stays String(50); the new value
            'platform_admin' is a runtime string, not a DB enum).

Existing organizations are backfilled with status='active' so currently
working flows keep working. Newly registered organizations will start as
'pending_approval' (set by the auth_service code path).

Revision ID: k110011platformadmin
Revises: j100010outreach
Create Date: 2026-05-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# ── Revision metadata ────────────────────────────────────────────────────────
revision = "k110011platformadmin"
down_revision = "j100010outreach"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── organizations: add status + approval/rejection/suspension fields ───
    op.add_column(
        "organizations",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.create_index(
        "ix_organizations_status",
        "organizations",
        ["status"],
        unique=False,
    )
    op.add_column(
        "organizations",
        sa.Column("approved_by_admin_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("rejected_by_admin_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("suspended_reason", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_organizations_approved_by_admin",
        "organizations",
        "users",
        ["approved_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_organizations_rejected_by_admin",
        "organizations",
        "users",
        ["rejected_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── organization_access_requests: brand new table ──────────────────────
    op.create_table(
        "organization_access_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("requester_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reviewed_by_admin_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("contact_role", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
        sa.Column("additional_info", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requester_user_id"], ["users.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_admin_id"], ["users.id"], ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_organization_access_requests_organization_id",
        "organization_access_requests",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_access_requests_requester_user_id",
        "organization_access_requests",
        ["requester_user_id"],
    )
    op.create_index(
        "ix_organization_access_requests_status",
        "organization_access_requests",
        ["status"],
    )

    # NOTE: We deliberately do NOT modify any existing user or membership
    # rows here. The audit script before this migration confirmed the live
    # data is in a clean state, but mass-changes to existing rows belong in
    # explicit, run-once cleanup scripts (see scripts/disable_demo_data.py),
    # not in a schema migration.


def downgrade() -> None:
    op.drop_index(
        "ix_organization_access_requests_status",
        table_name="organization_access_requests",
    )
    op.drop_index(
        "ix_organization_access_requests_requester_user_id",
        table_name="organization_access_requests",
    )
    op.drop_index(
        "ix_organization_access_requests_organization_id",
        table_name="organization_access_requests",
    )
    op.drop_table("organization_access_requests")

    op.drop_constraint(
        "fk_organizations_rejected_by_admin", "organizations", type_="foreignkey",
    )
    op.drop_constraint(
        "fk_organizations_approved_by_admin", "organizations", type_="foreignkey",
    )
    op.drop_column("organizations", "suspended_reason")
    op.drop_column("organizations", "suspended_at")
    op.drop_column("organizations", "rejection_reason")
    op.drop_column("organizations", "rejected_at")
    op.drop_column("organizations", "rejected_by_admin_id")
    op.drop_column("organizations", "approved_at")
    op.drop_column("organizations", "approved_by_admin_id")
    op.drop_index("ix_organizations_status", table_name="organizations")
    op.drop_column("organizations", "status")
