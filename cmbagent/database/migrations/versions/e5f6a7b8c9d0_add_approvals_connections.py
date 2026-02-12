"""Add approval_requests and active_connections tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    # Use batch operations for SQLite compatibility
    with op.batch_alter_table('approval_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_id', sa.String(36), nullable=True))
        batch_op.add_column(sa.Column('approval_type', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('context', sa.JSON, nullable=True))
        batch_op.add_column(sa.Column('result', sa.JSON, nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()))
        batch_op.add_column(sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True))

        # Modify existing columns to be nullable for backwards compatibility
        batch_op.alter_column('step_id', nullable=True)
        batch_op.alter_column('requested_at', nullable=True)
        batch_op.alter_column('context_snapshot', nullable=True)
        batch_op.alter_column('user_feedback', nullable=True)

        # Create new indexes for approval_requests
        batch_op.create_index('idx_approval_run_status', ['run_id', 'status'])
        batch_op.create_index('idx_approval_expires', ['expires_at'])
        batch_op.create_index('idx_approval_session', ['session_id'])

        # Create foreign key for session_id
        batch_op.create_foreign_key('fk_approval_session', 'sessions', ['session_id'], ['id'], ondelete='SET NULL')

    # Create active_connections table
    op.create_table(
        'active_connections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(100), nullable=False, unique=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('server_instance', sa.String(100), nullable=True),
        sa.Column('connected_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('last_heartbeat', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes for active_connections
    op.create_index('idx_connection_task_id', 'active_connections', ['task_id'])
    op.create_index('idx_connection_session_id', 'active_connections', ['session_id'])
    op.create_index('idx_connection_heartbeat', 'active_connections', ['last_heartbeat'])


def downgrade():
    # Drop active_connections
    op.drop_index('idx_connection_heartbeat', 'active_connections')
    op.drop_index('idx_connection_session_id', 'active_connections')
    op.drop_index('idx_connection_task_id', 'active_connections')
    op.drop_table('active_connections')

    # Use batch operations for SQLite compatibility
    with op.batch_alter_table('approval_requests', schema=None) as batch_op:
        # Drop new indexes
        batch_op.drop_index('idx_approval_session')
        batch_op.drop_index('idx_approval_expires')
        batch_op.drop_index('idx_approval_run_status')

        # Drop foreign key
        batch_op.drop_constraint('fk_approval_session', type_='foreignkey')

        # Remove new columns
        batch_op.drop_column('expires_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('result')
        batch_op.drop_column('context')
        batch_op.drop_column('approval_type')
        batch_op.drop_column('session_id')

        # Restore step_id to not nullable
        batch_op.alter_column('step_id', nullable=False)
