"""add_execution_events_and_enhance_artifacts

Revision ID: f524830711dc
Revises: 490016e6a277
Create Date: 2026-01-19 17:40:53.485039

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON


# revision identifiers, used by Alembic.
revision: str = 'f524830711dc'
down_revision: Union[str, Sequence[str], None] = '490016e6a277'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create execution_events table
    op.create_table('execution_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('node_id', sa.String(length=36), nullable=True),
        sa.Column('step_id', sa.String(length=36), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('parent_event_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_subtype', sa.String(length=50), nullable=True),
        sa.Column('agent_name', sa.String(length=100), nullable=True),
        sa.Column('agent_role', sa.String(length=50), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('inputs', JSON(), nullable=True),
        sa.Column('outputs', JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('meta', JSON(), nullable=True),
        sa.Column('execution_order', sa.Integer(), nullable=False),
        sa.Column('depth', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='completed'),
        sa.ForeignKeyConstraint(['run_id'], ['workflow_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['dag_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['workflow_steps.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_event_id'], ['execution_events.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for execution_events
    op.create_index('idx_events_run_order', 'execution_events', ['run_id', 'execution_order'])
    op.create_index('idx_events_node_order', 'execution_events', ['node_id', 'execution_order'])
    op.create_index('idx_events_type_subtype', 'execution_events', ['event_type', 'event_subtype'])
    op.create_index('idx_events_session_timestamp', 'execution_events', ['session_id', 'timestamp'])
    op.create_index('idx_events_parent', 'execution_events', ['parent_event_id'])
    op.create_index(op.f('ix_execution_events_run_id'), 'execution_events', ['run_id'])
    op.create_index(op.f('ix_execution_events_node_id'), 'execution_events', ['node_id'])
    op.create_index(op.f('ix_execution_events_step_id'), 'execution_events', ['step_id'])
    op.create_index(op.f('ix_execution_events_session_id'), 'execution_events', ['session_id'])
    op.create_index(op.f('ix_execution_events_event_type'), 'execution_events', ['event_type'])
    op.create_index(op.f('ix_execution_events_agent_name'), 'execution_events', ['agent_name'])
    op.create_index(op.f('ix_execution_events_timestamp'), 'execution_events', ['timestamp'])
    
    # Add event_id and node_id to files table
    with op.batch_alter_table('files', schema=None) as batch_op:
        batch_op.add_column(sa.Column('event_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('node_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_files_event_id', 'execution_events', ['event_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_files_node_id', 'dag_nodes', ['node_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index('idx_files_event', ['event_id'])
        batch_op.create_index('idx_files_node', ['node_id'])
    
    # Add event_id and node_id to messages table
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('event_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('node_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_messages_event_id', 'execution_events', ['event_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_messages_node_id', 'dag_nodes', ['node_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index('idx_messages_event', ['event_id'])
        batch_op.create_index('idx_messages_node', ['node_id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove indexes from messages
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_index('idx_messages_node')
        batch_op.drop_index('idx_messages_event')
        batch_op.drop_constraint('fk_messages_node_id', type_='foreignkey')
        batch_op.drop_constraint('fk_messages_event_id', type_='foreignkey')
        batch_op.drop_column('node_id')
        batch_op.drop_column('event_id')
    
    # Remove indexes from files
    with op.batch_alter_table('files', schema=None) as batch_op:
        batch_op.drop_index('idx_files_node')
        batch_op.drop_index('idx_files_event')
        batch_op.drop_constraint('fk_files_node_id', type_='foreignkey')
        batch_op.drop_constraint('fk_files_event_id', type_='foreignkey')
        batch_op.drop_column('node_id')
        batch_op.drop_column('event_id')
    
    # Drop execution_events table and indexes
    op.drop_index('ix_execution_events_timestamp', table_name='execution_events')
    op.drop_index('ix_execution_events_agent_name', table_name='execution_events')
    op.drop_index('ix_execution_events_event_type', table_name='execution_events')
    op.drop_index('ix_execution_events_session_id', table_name='execution_events')
    op.drop_index('ix_execution_events_step_id', table_name='execution_events')
    op.drop_index('ix_execution_events_node_id', table_name='execution_events')
    op.drop_index('ix_execution_events_run_id', table_name='execution_events')
    op.drop_index('idx_events_parent', table_name='execution_events')
    op.drop_index('idx_events_session_timestamp', table_name='execution_events')
    op.drop_index('idx_events_type_subtype', table_name='execution_events')
    op.drop_index('idx_events_node_order', table_name='execution_events')
    op.drop_index('idx_events_run_order', table_name='execution_events')
    op.drop_table('execution_events')
