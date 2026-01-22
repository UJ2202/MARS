"""Add state_history table

Revision ID: fca0d6632d2f
Revises: 92e46cb423de
Create Date: 2026-01-14 17:58:03.949562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fca0d6632d2f'
down_revision: Union[str, Sequence[str], None] = '92e46cb423de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'state_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('from_state', sa.String(length=50), nullable=True),
        sa.Column('to_state', sa.String(length=50), nullable=False),
        sa.Column('transition_reason', sa.Text(), nullable=True),
        sa.Column('transitioned_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_state_history_entity', 'state_history', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_state_history_session', 'state_history', ['session_id'], unique=False)
    op.create_index('idx_state_history_created', 'state_history', ['created_at'], unique=False)
    op.create_index(op.f('ix_state_history_entity_id'), 'state_history', ['entity_id'], unique=False)
    op.create_index(op.f('ix_state_history_entity_type'), 'state_history', ['entity_type'], unique=False)
    op.create_index(op.f('ix_state_history_to_state'), 'state_history', ['to_state'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_state_history_to_state'), table_name='state_history')
    op.drop_index(op.f('ix_state_history_entity_type'), table_name='state_history')
    op.drop_index(op.f('ix_state_history_entity_id'), table_name='state_history')
    op.drop_index('idx_state_history_created', table_name='state_history')
    op.drop_index('idx_state_history_session', table_name='state_history')
    op.drop_index('idx_state_history_entity', table_name='state_history')
    op.drop_table('state_history')
