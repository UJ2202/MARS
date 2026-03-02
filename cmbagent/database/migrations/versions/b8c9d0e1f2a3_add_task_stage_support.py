"""Add task stage support for Denario integration.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add task hierarchy columns to workflow_runs
    op.add_column('workflow_runs', sa.Column('parent_run_id', sa.String(36), sa.ForeignKey('workflow_runs.id', ondelete='SET NULL'), nullable=True))
    op.add_column('workflow_runs', sa.Column('stage_number', sa.Integer(), nullable=True))
    op.add_column('workflow_runs', sa.Column('stage_name', sa.String(100), nullable=True))
    op.create_index('idx_workflow_runs_parent_run', 'workflow_runs', ['parent_run_id'])

    # 2. Create task_stages table
    op.create_table(
        'task_stages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('parent_run_id', sa.String(36), sa.ForeignKey('workflow_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('child_run_id', sa.String(36), sa.ForeignKey('workflow_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('stage_number', sa.Integer(), nullable=False),
        sa.Column('stage_name', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('output_files', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=True),
    )
    op.create_index('idx_task_stages_parent_run', 'task_stages', ['parent_run_id'])
    op.create_index('idx_task_stages_status', 'task_stages', ['status'])
    op.create_index('idx_task_stages_parent_stage', 'task_stages', ['parent_run_id', 'stage_number'])

    # 3. Add parent_run_id to cost_records
    op.add_column('cost_records', sa.Column('parent_run_id', sa.String(36), sa.ForeignKey('workflow_runs.id', ondelete='SET NULL'), nullable=True))
    op.create_index('idx_cost_records_parent_run', 'cost_records', ['parent_run_id'])


def downgrade():
    op.drop_index('idx_cost_records_parent_run', 'cost_records')
    op.drop_column('cost_records', 'parent_run_id')
    op.drop_table('task_stages')
    op.drop_index('idx_workflow_runs_parent_run', 'workflow_runs')
    op.drop_column('workflow_runs', 'stage_name')
    op.drop_column('workflow_runs', 'stage_number')
    op.drop_column('workflow_runs', 'parent_run_id')
