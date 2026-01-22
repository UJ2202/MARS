"""
Topological Sort - Compute Execution Order for DAG

This module implements topological sorting algorithms to determine the execution
order of DAG nodes, supporting parallel execution levels.
"""

from collections import defaultdict, deque
from typing import List, Set, Dict, Any
from sqlalchemy.orm import Session

from cmbagent.database.models import DAGNode, DAGEdge
from cmbagent.database.dag_types import ExecutionLevel, CycleDetectedError


class TopologicalSorter:
    """Computes execution order for DAG using topological sort"""

    def __init__(self, db_session: Session):
        """
        Initialize topological sorter

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session

    def sort(self, run_id: str) -> List[List[str]]:
        """
        Topological sort returning execution levels

        Uses Kahn's algorithm to compute levels where nodes in the same level
        can be executed in parallel (they have no dependencies on each other).

        Args:
            run_id: Workflow run ID

        Returns:
            List of lists - each inner list is a level that can execute in parallel
            Example: [["planning"], ["step_1", "step_2"], ["step_3"], ["terminator"]]

        Raises:
            CycleDetectedError: If the DAG contains a cycle
        """
        # Load nodes and edges from database
        nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id
        ).all()

        edges = self.db.query(DAGEdge).join(
            DAGNode, DAGEdge.from_node_id == DAGNode.id
        ).filter(
            DAGNode.run_id == run_id
        ).all()

        # Build adjacency list and in-degree map
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        node_map = {node.id: node for node in nodes}

        # Initialize in-degree for all nodes
        for node in nodes:
            in_degree[node.id] = 0

        # Build graph and calculate in-degrees
        for edge in edges:
            graph[edge.from_node_id].append(edge.to_node_id)
            in_degree[edge.to_node_id] += 1

        # Kahn's algorithm for topological sort by levels
        levels = []
        queue = deque([node_id for node_id in in_degree if in_degree[node_id] == 0])

        while queue:
            # All nodes in queue have no dependencies - can execute in parallel
            current_level = []
            level_size = len(queue)

            for _ in range(level_size):
                node_id = queue.popleft()
                current_level.append(node_id)

                # Reduce in-degree for neighbors
                for neighbor_id in graph[node_id]:
                    in_degree[neighbor_id] -= 1
                    if in_degree[neighbor_id] == 0:
                        queue.append(neighbor_id)

            levels.append(current_level)

        # Verify all nodes processed (no cycles)
        total_processed = sum(len(level) for level in levels)
        if total_processed != len(nodes):
            unprocessed = [node.id for node in nodes if node.id not in
                          [n for level in levels for n in level]]
            raise CycleDetectedError(
                f"Cycle detected in DAG - {len(nodes) - total_processed} nodes unprocessed. "
                f"Unprocessed nodes: {unprocessed[:5]}"
            )

        return levels

    def get_execution_order(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get execution order with node details

        Args:
            run_id: Workflow run ID

        Returns:
            List of execution levels with node metadata
            Example:
            [
                {
                    "level": 0,
                    "nodes": [{"id": "...", "type": "planning", ...}],
                    "parallel": False
                },
                {
                    "level": 1,
                    "nodes": [{"id": "...", "type": "agent", ...}, ...],
                    "parallel": True
                }
            ]
        """
        levels = self.sort(run_id)
        node_map = {
            node.id: node for node in self.db.query(DAGNode).filter(
                DAGNode.run_id == run_id
            ).all()
        }

        execution_order = []
        for level_idx, level in enumerate(levels):
            level_info = {
                "level": level_idx,
                "nodes": [
                    {
                        "id": node_id,
                        "type": node_map[node_id].node_type,
                        "agent": node_map[node_id].agent,
                        "status": node_map[node_id].status,
                        "order_index": node_map[node_id].order_index,
                        "metadata": node_map[node_id].meta
                    }
                    for node_id in level
                ],
                "parallel": len(level) > 1,
                "node_count": len(level)
            }
            execution_order.append(level_info)

        return execution_order

    def get_execution_levels(self, run_id: str) -> List[ExecutionLevel]:
        """
        Get execution order as ExecutionLevel objects

        Args:
            run_id: Workflow run ID

        Returns:
            List of ExecutionLevel instances
        """
        levels = self.sort(run_id)

        execution_levels = []
        for level_idx, level_nodes in enumerate(levels):
            exec_level = ExecutionLevel(level=level_idx)
            for node_id in level_nodes:
                exec_level.add_node(node_id)
            execution_levels.append(exec_level)

        return execution_levels

    def get_node_dependencies(self, node_id: str) -> List[str]:
        """
        Get all dependencies for a specific node

        Args:
            node_id: Node ID

        Returns:
            List of node IDs that this node depends on
        """
        edges = self.db.query(DAGEdge).filter(
            DAGEdge.to_node_id == node_id
        ).all()

        return [edge.from_node_id for edge in edges]

    def get_node_dependents(self, node_id: str) -> List[str]:
        """
        Get all nodes that depend on this node

        Args:
            node_id: Node ID

        Returns:
            List of node IDs that depend on this node
        """
        edges = self.db.query(DAGEdge).filter(
            DAGEdge.from_node_id == node_id
        ).all()

        return [edge.to_node_id for edge in edges]

    def can_execute(self, node_id: str) -> bool:
        """
        Check if a node can be executed (all dependencies completed)

        Args:
            node_id: Node ID

        Returns:
            True if all dependencies are completed, False otherwise
        """
        dependencies = self.get_node_dependencies(node_id)

        if not dependencies:
            return True

        # Get dependency nodes
        dep_nodes = self.db.query(DAGNode).filter(
            DAGNode.id.in_(dependencies)
        ).all()

        # All dependencies must be completed
        return all(node.status == "completed" for node in dep_nodes)

    def get_ready_nodes(self, run_id: str) -> List[str]:
        """
        Get all nodes that are ready to execute

        A node is ready if:
        - Its status is "pending"
        - All its dependencies are completed

        Args:
            run_id: Workflow run ID

        Returns:
            List of node IDs ready for execution
        """
        nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id,
            DAGNode.status == "pending"
        ).all()

        ready_nodes = []
        for node in nodes:
            if self.can_execute(node.id):
                ready_nodes.append(node.id)

        return ready_nodes

    def get_parallel_groups(self, run_id: str) -> Dict[str, List[str]]:
        """
        Get parallel execution groups from the DAG

        Args:
            run_id: Workflow run ID

        Returns:
            Dictionary mapping parallel_group -> list of node IDs
        """
        nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id
        ).all()

        groups = defaultdict(list)
        for node in nodes:
            parallel_group = node.meta.get("parallel_group")
            if parallel_group:
                groups[parallel_group].append(node.id)

        return dict(groups)

    def validate_execution_order(self, run_id: str) -> bool:
        """
        Validate that the execution order is valid

        Checks:
        - No cycles exist
        - All nodes are reachable
        - Dependencies are satisfied in order

        Args:
            run_id: Workflow run ID

        Returns:
            True if valid, raises exception otherwise

        Raises:
            CycleDetectedError: If cycle detected
        """
        try:
            levels = self.sort(run_id)

            # Get all nodes
            all_nodes = self.db.query(DAGNode).filter(
                DAGNode.run_id == run_id
            ).all()

            # Check all nodes are in execution order
            nodes_in_levels = set(node_id for level in levels for node_id in level)
            all_node_ids = set(node.id for node in all_nodes)

            if nodes_in_levels != all_node_ids:
                missing = all_node_ids - nodes_in_levels
                raise ValueError(f"Some nodes not in execution order: {missing}")

            return True

        except CycleDetectedError:
            raise
        except Exception as e:
            raise ValueError(f"Execution order validation failed: {str(e)}")
