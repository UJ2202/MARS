"""Add file tracking columns to files table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new columns for enhanced file tracking."""
    # Add workflow_phase column
    op.add_column('files', sa.Column('workflow_phase', sa.String(50), nullable=True))

    # Add is_final_output column with default False
    op.add_column('files', sa.Column('is_final_output', sa.Boolean(), nullable=False, server_default='0'))

    # Add content_hash column
    op.add_column('files', sa.Column('content_hash', sa.String(64), nullable=True))

    # Add generating_agent column
    op.add_column('files', sa.Column('generating_agent', sa.String(100), nullable=True))

    # Add generating_code_hash column
    op.add_column('files', sa.Column('generating_code_hash', sa.String(64), nullable=True))

    # Add priority column
    op.add_column('files', sa.Column('priority', sa.String(20), nullable=True))

    # Create indexes for new columns
    op.create_index('idx_files_phase', 'files', ['run_id', 'workflow_phase'])
    op.create_index('idx_files_final_output', 'files', ['run_id', 'is_final_output'])


def downgrade() -> None:
    """Remove file tracking columns."""
    # Drop indexes first
    op.drop_index('idx_files_final_output', table_name='files')
    op.drop_index('idx_files_phase', table_name='files')

    # Drop columns
    op.drop_column('files', 'priority')
    op.drop_column('files', 'generating_code_hash')
    op.drop_column('files', 'generating_agent')
    op.drop_column('files', 'content_hash')
    op.drop_column('files', 'is_final_output')
    op.drop_column('files', 'workflow_phase')
