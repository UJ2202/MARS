"""rename_workflow_step_agent_to_goal

Revision ID: a1b2c3d4e5f6
Revises: f524830711dc
Create Date: 2026-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f524830711dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename agent column to goal in workflow_steps table.
    
    The agent column was incorrectly storing a single agent name, but steps
    are actually executed by multiple agents (tracked in ExecutionEvent).
    The column should store the step's goal/description instead.
    """
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    with op.batch_alter_table('workflow_steps', schema=None) as batch_op:
        batch_op.alter_column('agent',
                              new_column_name='goal',
                              existing_type=sa.String(length=100),
                              type_=sa.Text(),
                              existing_nullable=False)


def downgrade() -> None:
    """Revert goal column back to agent."""
    with op.batch_alter_table('workflow_steps', schema=None) as batch_op:
        batch_op.alter_column('goal',
                              new_column_name='agent',
                              existing_type=sa.Text(),
                              type_=sa.String(length=100),
                              existing_nullable=False)
