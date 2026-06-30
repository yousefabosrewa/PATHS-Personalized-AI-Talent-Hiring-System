"""add agent_runs table

Revision ID: a1b2c3d4e5f6
Revises: dbb1e9d0785d
Create Date: 2026-05-22

The AgentRun model (app/db/models/agent_runs.py) shipped without a matching
migration, so the `agent_runs` table was never created. Every call to
GET /api/v1/agent-runs 500'd with `UndefinedTable: relation "agent_runs"
does not exist`. This additive, backward-compatible migration creates the
table exactly as the model declares it.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "dbb1e9d0785d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard with checkfirst-style logic: if a previous environment created the
    # table out-of-band, skip creation so the migration stays idempotent.
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "agent_runs"):
        return

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("run_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_node", sa.String(length=128), nullable=True),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("input_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_organization_id", "agent_runs", ["organization_id"])
    op.create_index("ix_agent_runs_org_type", "agent_runs", ["organization_id", "run_type"])
    op.create_index("ix_agent_runs_entity", "agent_runs", ["entity_type", "entity_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_entity", table_name="agent_runs")
    op.drop_index("ix_agent_runs_org_type", table_name="agent_runs")
    op.drop_index("ix_agent_runs_organization_id", table_name="agent_runs")
    op.drop_table("agent_runs")
