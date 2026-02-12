"""Add session_states table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    # Create session_states table
    op.create_table(
        'session_states',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mode', sa.String(50), nullable=False),

        # JSON columns for state
        sa.Column('conversation_history', sa.JSON, nullable=True),
        sa.Column('context_variables', sa.JSON, nullable=True),
        sa.Column('plan_data', sa.JSON, nullable=True),

        # Progress
        sa.Column('current_phase', sa.String(50), nullable=True),
        sa.Column('current_step', sa.Integer, nullable=True),

        # Lifecycle
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),

        # Optimistic locking
        sa.Column('version', sa.Integer, server_default='1'),
    )

    # Create indexes
    op.create_index('idx_session_states_session_id', 'session_states', ['session_id'])
    op.create_index('idx_session_states_status', 'session_states', ['status'])
    op.create_index('idx_session_states_session_status', 'session_states', ['session_id', 'status'])
    op.create_index('idx_session_states_mode', 'session_states', ['mode'])
    op.create_index('idx_session_states_updated', 'session_states', ['updated_at'])


def downgrade():
    # Drop indexes first
    op.drop_index('idx_session_states_updated')
    op.drop_index('idx_session_states_mode')
    op.drop_index('idx_session_states_session_status')
    op.drop_index('idx_session_states_status')
    op.drop_index('idx_session_states_session_id')

    # Drop table
    op.drop_table('session_states')
