"""add hitl_approvals table

Revision ID: e50005abcdef
Revises: g70007candprof
Create Date: 2026-04-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e50005abcdef'
down_revision = 'g70007candprof'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'hitl_approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('priority', sa.String(10), nullable=False, server_default='medium'),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(255), nullable=False),
        sa.Column('entity_label', sa.String(255), nullable=False, server_default=''),
        sa.Column('requested_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('requested_by_name', sa.String(255), nullable=False, server_default='System'),
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('reviewed_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_by_name', sa.String(255), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision', sa.String(20), nullable=True),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('meta_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_hitl_approvals_organization_id', 'hitl_approvals', ['organization_id'])
    op.create_index('ix_hitl_approvals_status', 'hitl_approvals', ['status'])


def downgrade() -> None:
    op.drop_index('ix_hitl_approvals_status', table_name='hitl_approvals')
    op.drop_index('ix_hitl_approvals_organization_id', table_name='hitl_approvals')
    op.drop_table('hitl_approvals')
