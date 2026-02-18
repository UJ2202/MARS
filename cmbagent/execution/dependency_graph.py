"""
Dependency Graph - DAG structure with topological sorting

This module provides a dependency graph structure with cycle detection
and topological sorting for parallel execution planning.
"""

import logging
import structlog
from typing import Dict, List, Set, Any, Optional, Tuple

logger = structlog.get_logger(__name__)


class CircularDependencyError(Exception):
    """Raised when circular dependency is detected in graph"""
    pass


class DependencyGraph:
    """Directed acyclic graph (DAG) for task dependencies"""

    def __init__(self):
        """Initialize empty dependency graph"""
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Tuple[str, str, str]] = []  # (from, to, type)

    def add_node(self, node_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add node to graph

        Args:
            node_id: Unique node identifier
            metadata: Optional node metadata
        """
        if node_id in self.nodes:
            logger.warning(f"Node {node_id} already exists, updating metadata")

        self.nodes[node_id] = {
            "id": node_id,
            "metadata": metadata or {},
            "in_degree": 0,
            "dependencies": [],  # Nodes this depends on
            "dependents": []     # Nodes that depend on this
        }

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        dependency_type: str = "data",
        reason: str = ""
    ) -> None:
        """
        Add directed edge from one node to another

        Args:
            from_id: Source node ID (dependency)
            to_id: Target node ID (dependent)
            dependency_type: Type of dependency (data, file, api, logic, order)
            reason: Human-readable reason for dependency
        """
        if from_id not in self.nodes:
            raise ValueError(f"Source node {from_id} not in graph")
        if to_id not in self.nodes:
            raise ValueError(f"Target node {to_id} not in graph")

        # Add edge
        self.edges.append((from_id, to_id, dependency_type))

        # Update node metadata
        self.nodes[to_id]["in_degree"] += 1
        self.nodes[to_id]["dependencies"].append(from_id)
        self.nodes[from_id]["dependents"].append(to_id)

        logger.debug(
            f"Added edge: {from_id} -> {to_id} (type={dependency_type}, reason={reason})"
        )

    def topological_sort(self) -> List[List[str]]:
        """
        Perform topological sort using Kahn's algorithm

        Returns execution levels (groups that can run in parallel):
        - Level 0: [nodes with no dependencies]
        - Level 1: [nodes depending only on level 0]
        - Level 2: [nodes depending on level 0 and/or 1]
        ...

        Returns:
            List of levels, each level contains node IDs that can run in parallel

        Raises:
            CircularDependencyError: If circular dependency detected
        """
        logger.info(f"Computing topological sort for {len(self.nodes)} nodes")

        # Detect cycles first
        if self.detect_cycles():
            raise CircularDependencyError(
                "Circular dependency detected in workflow graph"
            )

        levels = []
        remaining_nodes = set(self.nodes.keys())
        completed_nodes: Set[str] = set()

        # Work with copy of in_degrees (don't mutate original)
        in_degrees = {
            node_id: self.nodes[node_id]["in_degree"]
            for node_id in self.nodes
        }

        level_num = 0
        while remaining_nodes:
            # Find nodes with all dependencies satisfied
            ready_nodes = [
                node_id for node_id in remaining_nodes
                if in_degrees[node_id] == 0
            ]

            if not ready_nodes:
                # This shouldn't happen if detect_cycles passed
                raise CircularDependencyError(
                    f"No ready nodes but {len(remaining_nodes)} remaining: "
                    f"{remaining_nodes}"
                )

            logger.debug(
                f"Level {level_num}: {len(ready_nodes)} nodes ready to execute"
            )

            levels.append(ready_nodes)
            completed_nodes.update(ready_nodes)
            remaining_nodes -= set(ready_nodes)

            # Decrease in-degree of dependent nodes
            for node_id in ready_nodes:
                for dependent_id in self.nodes[node_id]["dependents"]:
                    in_degrees[dependent_id] -= 1

            level_num += 1

        logger.info(
            f"Topological sort complete: {len(levels)} levels, "
            f"max parallelism = {max(len(level) for level in levels)}"
        )

        return levels

    def detect_cycles(self) -> bool:
        """
        Detect circular dependencies using DFS

        Returns:
            True if cycle detected, False otherwise
        """
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def visit(node_id: str) -> bool:
            """Visit node in DFS traversal"""
            if node_id in rec_stack:
                # Node is in recursion stack - cycle detected
                return True
            if node_id in visited:
                # Already visited and no cycle found
                return False

            visited.add(node_id)
            rec_stack.add(node_id)

            # Visit all dependents
            for dependent_id in self.nodes[node_id]["dependents"]:
                if visit(dependent_id):
                    logger.error(f"Cycle detected involving {node_id} -> {dependent_id}")
                    return True

            rec_stack.remove(node_id)
            return False

        # Check all nodes
        for node_id in self.nodes:
            if node_id not in visited:
                if visit(node_id):
                    return True

        return False

    def get_dependencies(self, node_id: str) -> List[str]:
        """
        Get all dependencies of a node

        Args:
            node_id: Node ID

        Returns:
            List of node IDs this node depends on
        """
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not in graph")

        return self.nodes[node_id]["dependencies"].copy()

    def get_dependents(self, node_id: str) -> List[str]:
        """
        Get all dependents of a node

        Args:
            node_id: Node ID

        Returns:
            List of node IDs that depend on this node
        """
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not in graph")

        return self.nodes[node_id]["dependents"].copy()

    def get_independent_nodes(self) -> List[str]:
        """
        Get all nodes with no dependencies

        Returns:
            List of node IDs with in_degree = 0
        """
        return [
            node_id for node_id, node in self.nodes.items()
            if node["in_degree"] == 0
        ]

    def get_execution_order_summary(self) -> Dict[str, Any]:
        """
        Get summary of execution order

        Returns:
            Dictionary with execution statistics
        """
        try:
            levels = self.topological_sort()

            return {
                "total_nodes": len(self.nodes),
                "total_levels": len(levels),
                "max_parallelism": max(len(level) for level in levels) if levels else 0,
                "total_dependencies": len(self.edges),
                "has_cycles": False,
                "levels": [
                    {
                        "level": i,
                        "node_count": len(level),
                        "nodes": level
                    }
                    for i, level in enumerate(levels)
                ]
            }
        except CircularDependencyError:
            return {
                "total_nodes": len(self.nodes),
                "total_dependencies": len(self.edges),
                "has_cycles": True,
                "error": "Circular dependency detected"
            }

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert graph to dictionary representation

        Returns:
            Dictionary with nodes and edges
        """
        return {
            "nodes": list(self.nodes.values()),
            "edges": [
                {
                    "from": from_id,
                    "to": to_id,
                    "type": dep_type
                }
                for from_id, to_id, dep_type in self.edges
            ]
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"DependencyGraph(nodes={len(self.nodes)}, "
            f"edges={len(self.edges)})"
        )
