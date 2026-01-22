"""
DAG Builder - Builds DAG from Planning Output

This module converts planning output (JSON format) into a directed acyclic graph (DAG)
structure stored in the database.
"""

from typing import List, Dict, Set, Optional, Any
from sqlalchemy.orm import Session
import uuid

from cmbagent.database.models import DAGNode, DAGEdge
from cmbagent.database.dag_types import (
    DAGNodeType,
    DAGNodeMetadata,
    DependencyType,
    CycleDetectedError,
    InvalidDependencyError
)


class DAGBuilder:
    """Builds DAG from planning output and stores in database"""

    def __init__(self, db_session: Session, session_id: str):
        """
        Initialize DAG builder

        Args:
            db_session: SQLAlchemy database session
            session_id: Current session ID
        """
        self.db = db_session
        self.session_id = session_id

    def build_from_plan(self, run_id: str, plan: Dict[str, Any]) -> Dict[str, DAGNode]:
        """
        Build DAG from plan JSON

        Args:
            run_id: Workflow run ID
            plan: Plan dictionary from planner agent
                Expected format:
                {
                    "steps": [
                        {
                            "task": "description",
                            "agent": "engineer",
                            "depends_on": ["planning"],  # Optional
                            "parallel": False,           # Optional
                            "parallel_group": "group1",  # Optional
                            "approval_required": False   # Optional
                        },
                        ...
                    ]
                }

        Returns:
            Dictionary of node_id -> DAGNode
        """
        nodes = {}
        edges = []

        # Create planning node (root of DAG)
        planning_node = self._create_node(
            run_id=run_id,
            node_type=DAGNodeType.PLANNING,
            order_index=0,
            metadata={"phase": "planning"}
        )
        nodes["planning"] = planning_node

        # Parse plan steps
        steps = plan.get("steps", [])
        previous_node_id = "planning"

        for idx, step in enumerate(steps):
            # Determine dependencies
            is_parallel = step.get("parallel", False)
            depends_on = step.get("depends_on", [])

            # If no explicit dependencies, depend on previous node (unless parallel)
            if not depends_on:
                depends_on = [previous_node_id]

            # Create agent node
            node_id = f"step_{idx}"
            agent = step.get("agent", "engineer")
            task = step.get("task", "")

            metadata = DAGNodeMetadata(
                agent=agent,
                task_description=task,
                depends_on=depends_on,
                parallel_group=step.get("parallel_group"),
                approval_required=step.get("approval_required", False),
                retry_config=step.get("retry_config", {})
            )

            agent_node = self._create_node(
                run_id=run_id,
                node_type=DAGNodeType.AGENT,
                agent=agent,
                order_index=idx + 1,
                metadata=metadata.to_dict()
            )
            nodes[node_id] = agent_node

            # Create edges from dependencies
            for dep_id in depends_on:
                if dep_id in nodes:
                    dependency_type = DependencyType.PARALLEL if is_parallel else DependencyType.SEQUENTIAL
                    edge = self._create_edge(
                        from_node_id=nodes[dep_id].id,
                        to_node_id=agent_node.id,
                        dependency_type=dependency_type
                    )
                    edges.append(edge)
                else:
                    raise InvalidDependencyError(
                        f"Node {node_id} depends on non-existent node {dep_id}"
                    )

            # Update previous for sequential steps
            if not is_parallel:
                previous_node_id = node_id

        # Create terminator node (end of DAG)
        terminator = self._create_node(
            run_id=run_id,
            node_type=DAGNodeType.TERMINATOR,
            order_index=len(steps) + 1,
            metadata={"phase": "completion"}
        )
        nodes["terminator"] = terminator

        # Connect last step(s) to terminator
        # Find nodes with no outgoing edges
        node_ids_with_outgoing = set(e.from_node_id for e in edges)
        for node_id, node in nodes.items():
            if node.node_type == DAGNodeType.AGENT and node.id not in node_ids_with_outgoing:
                edge = self._create_edge(
                    from_node_id=node.id,
                    to_node_id=terminator.id,
                    dependency_type=DependencyType.SEQUENTIAL
                )
                edges.append(edge)

        # Commit to database
        self.db.commit()

        return nodes

    def _create_node(
        self,
        run_id: str,
        node_type: DAGNodeType,
        order_index: int,
        agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DAGNode:
        """
        Create and persist DAG node

        Args:
            run_id: Workflow run ID
            node_type: Type of node
            order_index: Order in original plan
            agent: Agent name (for AGENT nodes)
            metadata: Node metadata

        Returns:
            Created DAGNode instance
        """
        node = DAGNode(
            id=str(uuid.uuid4()),
            run_id=run_id,
            session_id=self.session_id,
            node_type=node_type,
            agent=agent,
            status="pending",
            order_index=order_index,
            meta=metadata or {}
        )
        self.db.add(node)
        self.db.flush()  # Get ID without committing
        return node

    def _create_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        dependency_type: DependencyType
    ) -> DAGEdge:
        """
        Create and persist DAG edge

        Args:
            from_node_id: Source node ID
            to_node_id: Target node ID
            dependency_type: Type of dependency

        Returns:
            Created DAGEdge instance
        """
        edge = DAGEdge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            dependency_type=str(dependency_type.value) if isinstance(dependency_type, DependencyType) else dependency_type
        )
        self.db.add(edge)
        self.db.flush()
        return edge

    def validate_dag(self, nodes: Dict[str, DAGNode]) -> bool:
        """
        Validate DAG is acyclic

        Args:
            nodes: Dictionary of node_id -> DAGNode

        Returns:
            True if valid DAG (no cycles), False if cycles detected

        Raises:
            CycleDetectedError: If a cycle is found in the DAG
        """
        # Build adjacency list from database edges
        graph = {}
        for node_id, node in nodes.items():
            graph[node.id] = []

        # Query edges for these nodes
        node_db_ids = [n.id for n in nodes.values()]
        edges = self.db.query(DAGEdge).filter(
            DAGEdge.from_node_id.in_(node_db_ids)
        ).all()

        for edge in edges:
            if edge.from_node_id in graph:
                graph[edge.from_node_id].append(edge.to_node_id)

        # Detect cycles using DFS with recursion stack
        visited = set()
        rec_stack = set()
        cycle_path = []

        def has_cycle(node_id: str, path: List[str]) -> bool:
            """DFS helper to detect cycles"""
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            for neighbor in graph.get(node_id, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    # Cycle detected
                    cycle_path.extend(path)
                    cycle_path.append(neighbor)
                    return True

            rec_stack.remove(node_id)
            path.pop()
            return False

        # Check all nodes for cycles
        for node_id in graph:
            if node_id not in visited:
                path = []
                if has_cycle(node_id, path):
                    raise CycleDetectedError(
                        f"Cycle detected in DAG: {' -> '.join(cycle_path)}"
                    )

        return True

    def get_node_by_id(self, node_id: str) -> Optional[DAGNode]:
        """
        Get DAG node by ID

        Args:
            node_id: Node ID

        Returns:
            DAGNode instance or None if not found
        """
        return self.db.query(DAGNode).filter(DAGNode.id == node_id).first()

    def get_nodes_by_run(self, run_id: str) -> List[DAGNode]:
        """
        Get all DAG nodes for a workflow run

        Args:
            run_id: Workflow run ID

        Returns:
            List of DAGNode instances
        """
        return self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id
        ).order_by(DAGNode.order_index).all()

    def get_edges_by_run(self, run_id: str) -> List[DAGEdge]:
        """
        Get all DAG edges for a workflow run

        Args:
            run_id: Workflow run ID

        Returns:
            List of DAGEdge instances
        """
        return self.db.query(DAGEdge).join(
            DAGNode, DAGEdge.from_node_id == DAGNode.id
        ).filter(
            DAGNode.run_id == run_id
        ).all()

    def rebuild_dag(self, run_id: str) -> Dict[str, DAGNode]:
        """
        Rebuild DAG from database for a given run

        Args:
            run_id: Workflow run ID

        Returns:
            Dictionary of node_id -> DAGNode
        """
        nodes = self.get_nodes_by_run(run_id)

        # Create mapping
        node_map = {}
        for node in nodes:
            # Use order_index to reconstruct original node IDs
            if node.node_type == DAGNodeType.PLANNING:
                node_map["planning"] = node
            elif node.node_type == DAGNodeType.TERMINATOR:
                node_map["terminator"] = node
            elif node.node_type == DAGNodeType.AGENT:
                node_map[f"step_{node.order_index - 1}"] = node

        return node_map
