"""phase1_fairness_rubric_and_pipeline_stage

Revision ID: dbb1e9d0785d
Revises: d9bfc9b5ca58
Create Date: 2026-05-12 04:23:13.940377
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'dbb1e9d0785d'
down_revision: Union[str, None] = 'd9bfc9b5ca58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PATHS-010: fairness rubric table (one row per job)
    op.create_table(
        'fairness_rubric',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('protected_attrs', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('disparate_impact_threshold', sa.Float(), nullable=False, server_default='0.8'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id'),
    )

    # PATHS-011: pipeline stage column on applications
    # Uses the existing current_stage_code string column convention;
    # pipeline_stage is a dedicated varchar for the 9-stage kanban board.
    op.add_column(
        'applications',
        sa.Column(
            'pipeline_stage',
            sa.String(50),
            nullable=False,
            server_default='screen',
        ),
    )
    op.create_index('ix_applications_pipeline_stage', 'applications', ['pipeline_stage'])


def downgrade() -> None:
    op.drop_index('ix_applications_pipeline_stage', table_name='applications')
    op.drop_column('applications', 'pipeline_stage')
    op.drop_table('fairness_rubric')
