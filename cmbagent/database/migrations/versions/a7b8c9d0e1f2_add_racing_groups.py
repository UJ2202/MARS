"""Add racing_groups table and racing fields to branches

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-02-12
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    # Create racing_groups table first (branches FK depends on it)
    op.create_table(
        'racing_groups',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('parent_run_id', sa.String(36),
                  sa.ForeignKey('workflow_runs.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('parent_step_id', sa.String(36),
                  sa.ForeignKey('workflow_steps.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('strategy', sa.String(50), nullable=False,
                  server_default='first_complete'),
        sa.Column('status', sa.String(20), nullable=False,
                  server_default='racing'),
        sa.Column('winner_branch_id', sa.String(36),
                  sa.ForeignKey('branches.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False,
                  server_default=sa.func.now()),
        sa.Column('resolved_at', sa.TIMESTAMP, nullable=True),
        sa.Column('meta', sa.JSON, nullable=True),
    )

    # Add racing columns to branches table
    with op.batch_alter_table('branches', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('racing_group_id', sa.String(36), nullable=True))
        batch_op.add_column(
            sa.Column('racing_priority', sa.Integer, nullable=True))
        batch_op.add_column(
            sa.Column('racing_status', sa.String(20), nullable=True))
        batch_op.create_index('idx_branches_racing_group', ['racing_group_id'])
        batch_op.create_foreign_key(
            'fk_branches_racing_group_id', 'racing_groups',
            ['racing_group_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('branches', schema=None) as batch_op:
        batch_op.drop_constraint('fk_branches_racing_group_id',
                                 type_='foreignkey')
        batch_op.drop_index('idx_branches_racing_group')
        batch_op.drop_column('racing_status')
        batch_op.drop_column('racing_priority')
        batch_op.drop_column('racing_group_id')

    op.drop_table('racing_groups')
