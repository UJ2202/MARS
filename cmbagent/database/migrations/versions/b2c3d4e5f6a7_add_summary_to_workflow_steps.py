"""add_summary_to_workflow_steps

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-20 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add summary column to workflow_steps table.
    
    Summary stores a human-readable description of what was accomplished
    in the step, extracted from the agent's final response.
    """
    with op.batch_alter_table('workflow_steps', schema=None) as batch_op:
        batch_op.add_column(sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove summary column from workflow_steps table."""
    with op.batch_alter_table('workflow_steps', schema=None) as batch_op:
        batch_op.drop_column('summary')
