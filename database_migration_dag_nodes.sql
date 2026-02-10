-- Database Migration: Add parent_node_id and depth to dag_nodes
-- This migration adds support for hierarchical DAG nodes (sub-nodes and branches)
--
-- Usage:
-- PostgreSQL: psql -d your_database -f database_migration_dag_nodes.sql
-- SQLite: sqlite3 your_database.db < database_migration_dag_nodes.sql


-- ============================================================================
-- PostgreSQL Migration
-- ============================================================================

-- Add parent_node_id column
ALTER TABLE dag_nodes ADD COLUMN parent_node_id VARCHAR(36);

-- Add depth column with default value 0
ALTER TABLE dag_nodes ADD COLUMN depth INTEGER NOT NULL DEFAULT 0;

-- Add foreign key constraint for parent_node_id
ALTER TABLE dag_nodes
ADD CONSTRAINT fk_parent_node
FOREIGN KEY (parent_node_id)
REFERENCES dag_nodes(id)
ON DELETE CASCADE;

-- Add index on parent_node_id for faster queries
CREATE INDEX idx_dag_nodes_parent ON dag_nodes(parent_node_id);

-- Verify the migration
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'dag_nodes'
-- AND column_name IN ('parent_node_id', 'depth');


-- ============================================================================
-- SQLite Migration (Alternative approach)
-- ============================================================================
-- Note: SQLite doesn't support ADD FOREIGN KEY via ALTER TABLE
-- Instead, we need to recreate the table

-- UNCOMMENT BELOW FOR SQLITE:

-- -- 1. Create new table with additional columns
-- CREATE TABLE dag_nodes_new (
--     id VARCHAR(36) PRIMARY KEY,
--     run_id VARCHAR(36) NOT NULL,
--     session_id VARCHAR(36) NOT NULL,
--     parent_node_id VARCHAR(36),
--     node_type VARCHAR(50) NOT NULL,
--     agent VARCHAR(100),
--     status VARCHAR(50) NOT NULL DEFAULT 'pending',
--     order_index INTEGER NOT NULL,
--     depth INTEGER NOT NULL DEFAULT 0,
--     meta TEXT,
--     FOREIGN KEY (run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE,
--     FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
--     FOREIGN KEY (parent_node_id) REFERENCES dag_nodes(id) ON DELETE CASCADE
-- );

-- -- 2. Copy existing data (setting depth=0 and parent_node_id=NULL for all existing nodes)
-- INSERT INTO dag_nodes_new (
--     id, run_id, session_id, node_type, agent, status, order_index, depth, meta, parent_node_id
-- )
-- SELECT
--     id, run_id, session_id, node_type, agent, status, order_index, 0, meta, NULL
-- FROM dag_nodes;

-- -- 3. Drop old table
-- DROP TABLE dag_nodes;

-- -- 4. Rename new table
-- ALTER TABLE dag_nodes_new RENAME TO dag_nodes;

-- -- 5. Recreate indexes
-- CREATE INDEX idx_dag_nodes_run_order ON dag_nodes(run_id, order_index);
-- CREATE INDEX idx_dag_nodes_type_status ON dag_nodes(node_type, status);
-- CREATE INDEX idx_dag_nodes_parent ON dag_nodes(parent_node_id);


-- ============================================================================
-- Rollback Script (PostgreSQL)
-- ============================================================================
-- CAUTION: This will delete the columns and all data in them!

-- UNCOMMENT BELOW TO ROLLBACK (PostgreSQL):

-- -- Drop the index
-- DROP INDEX IF EXISTS idx_dag_nodes_parent;

-- -- Drop the foreign key constraint
-- ALTER TABLE dag_nodes DROP CONSTRAINT IF EXISTS fk_parent_node;

-- -- Drop the columns
-- ALTER TABLE dag_nodes DROP COLUMN IF EXISTS parent_node_id;
-- ALTER TABLE dag_nodes DROP COLUMN IF EXISTS depth;


-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Check if columns were added successfully (PostgreSQL)
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'dag_nodes'
-- ORDER BY ordinal_position;

-- Check if indexes were created (PostgreSQL)
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'dag_nodes';

-- Test hierarchical query (get all sub-nodes of a parent)
-- SELECT * FROM dag_nodes WHERE parent_node_id = 'your_parent_node_id';

-- Test recursive query (get full node tree)
-- WITH RECURSIVE node_tree AS (
--     -- Start with top-level nodes (no parent)
--     SELECT id, parent_node_id, node_type, agent, depth, 0 as level
--     FROM dag_nodes
--     WHERE parent_node_id IS NULL
--
--     UNION ALL
--
--     -- Recursively get child nodes
--     SELECT n.id, n.parent_node_id, n.node_type, n.agent, n.depth, nt.level + 1
--     FROM dag_nodes n
--     INNER JOIN node_tree nt ON n.parent_node_id = nt.id
-- )
-- SELECT * FROM node_tree ORDER BY level, id;
