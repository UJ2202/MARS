"""Add session_id to files table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-12
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('files', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_id', sa.String(36), nullable=True))
        batch_op.create_index('idx_files_session', ['session_id'])
        batch_op.create_foreign_key(
            'fk_files_session_id', 'sessions', ['session_id'], ['id'],
            ondelete='CASCADE'
        )


def downgrade():
    with op.batch_alter_table('files', schema=None) as batch_op:
        batch_op.drop_constraint('fk_files_session_id', type_='foreignkey')
        batch_op.drop_index('idx_files_session')
        batch_op.drop_column('session_id')
