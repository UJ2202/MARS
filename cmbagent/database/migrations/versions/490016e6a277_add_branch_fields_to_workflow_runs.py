"""add_branch_fields_to_workflow_runs

Revision ID: 490016e6a277
Revises: fca0d6632d2f
Create Date: 2026-01-15 04:54:31.394872

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '490016e6a277'
down_revision: Union[str, Sequence[str], None] = 'fca0d6632d2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns to workflow_runs table - simpler approach for SQLite
    op.add_column('workflow_runs', sa.Column('branch_parent_id', sa.String(36), nullable=True))
    op.add_column('workflow_runs', sa.Column('is_branch', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('workflow_runs', sa.Column('branch_depth', sa.Integer(), nullable=False, server_default='0'))

    # Add status column to branches table
    op.add_column('branches', sa.Column('status', sa.String(50), nullable=False, server_default='active'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns from workflow_runs
    op.drop_column('workflow_runs', 'branch_depth')
    op.drop_column('workflow_runs', 'is_branch')
    op.drop_column('workflow_runs', 'branch_parent_id')

    # Remove status from branches
    op.drop_column('branches', 'status')
