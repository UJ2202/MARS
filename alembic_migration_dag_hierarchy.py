"""Add parent_node_id and depth to dag_nodes for hierarchical support

Revision ID: unified_tracking_dag_hierarchy
Revises: <previous_revision_id>
Create Date: 2025-02-10 12:00:00.000000

This migration adds support for hierarchical DAG nodes:
- parent_node_id: Self-referencing foreign key for parent-child relationships
- depth: Integer field to track nesting level (0=top-level, 1=sub-node, etc.)

This enables:
1. Sub-nodes: Track internal agent calls within a step
2. Redo branches: Track alternative execution paths
3. Full execution tree: Query hierarchical relationships
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = 'unified_tracking_dag_hierarchy'
down_revision: Union[str, None] = None  # Replace with actual previous revision ID
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add parent_node_id and depth columns to dag_nodes table."""

    # Add parent_node_id column (nullable, self-referencing FK)
    op.add_column('dag_nodes',
        sa.Column('parent_node_id', sa.String(36), nullable=True)
    )

    # Add depth column (not nullable, default 0)
    op.add_column('dag_nodes',
        sa.Column('depth', sa.Integer(), nullable=False, server_default='0')
    )

    # Create foreign key constraint for parent_node_id
    with op.batch_alter_table('dag_nodes', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_parent_node',
            'dag_nodes',
            ['parent_node_id'],
            ['id'],
            ondelete='CASCADE'
        )

        # Create index on parent_node_id for faster queries
        batch_op.create_index(
            'idx_dag_nodes_parent',
            ['parent_node_id'],
            unique=False
        )


def downgrade() -> None:
    """Remove parent_node_id and depth columns from dag_nodes table."""

    with op.batch_alter_table('dag_nodes', schema=None) as batch_op:
        # Drop index
        batch_op.drop_index('idx_dag_nodes_parent')

        # Drop foreign key constraint
        batch_op.drop_constraint('fk_parent_node', type_='foreignkey')

    # Drop columns
    op.drop_column('dag_nodes', 'depth')
    op.drop_column('dag_nodes', 'parent_node_id')
