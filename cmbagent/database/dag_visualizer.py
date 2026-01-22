"""
DAG Visualizer - Export DAG Data for UI Visualization

This module exports DAG data in formats suitable for UI visualization,
including JSON for interactive graphs and Mermaid syntax for diagrams.
"""

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from cmbagent.database.models import DAGNode, DAGEdge
from cmbagent.database.topological_sort import TopologicalSorter


class DAGVisualizer:
    """Exports DAG data for visualization"""

    def __init__(self, db_session: Session):
        """
        Initialize DAG visualizer

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session

    def export_for_ui(self, run_id: str) -> Dict[str, Any]:
        """
        Export DAG in format suitable for UI visualization

        Args:
            run_id: Workflow run ID

        Returns:
            Dictionary with nodes and edges for graph rendering
            Format:
            {
                "nodes": [
                    {
                        "id": "node_id",
                        "type": "agent",
                        "agent": "engineer",
                        "status": "pending",
                        "level": 1,
                        "label": "Engineer",
                        "metadata": {...}
                    },
                    ...
                ],
                "edges": [
                    {
                        "id": "edge_id",
                        "from": "node_id_1",
                        "to": "node_id_2",
                        "type": "sequential"
                    },
                    ...
                ],
                "levels": 5,
                "stats": {
                    "total_nodes": 10,
                    "pending": 5,
                    "running": 2,
                    "completed": 2,
                    "failed": 1
                }
            }
        """
        # Load nodes and edges
        nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id
        ).all()

        edges = self.db.query(DAGEdge).join(
            DAGNode, DAGEdge.from_node_id == DAGNode.id
        ).filter(
            DAGNode.run_id == run_id
        ).all()

        # Get execution levels for positioning
        sorter = TopologicalSorter(self.db)
        try:
            levels = sorter.sort(run_id)
        except Exception:
            # If sorting fails, assign all nodes to level 0
            levels = [[node.id for node in nodes]]

        node_levels = {}
        for level_idx, level_nodes in enumerate(levels):
            for node_id in level_nodes:
                node_levels[node_id] = level_idx

        # Format nodes for UI
        ui_nodes = []
        status_counts = {}
        for node in nodes:
            status_counts[node.status] = status_counts.get(node.status, 0) + 1
            
            # Extract metadata
            meta = node.meta or {}
            
            # Build node data with all properties UI needs
            node_data = {
                "id": str(node.id),
                "type": node.node_type,
                "agent": node.agent,
                "status": node.status,
                "level": node_levels.get(node.id, 0),
                "label": meta.get("label") or self._get_node_label(node),
                "step_number": meta.get("step_number") or node.order_index,
                "description": meta.get("description"),
                "started_at": meta.get("started_at"),
                "completed_at": meta.get("completed_at"),
                "error": meta.get("error"),
                "retry_info": meta.get("retry_info"),
                "metadata": meta,
            }
            
            ui_nodes.append(node_data)

        # Format edges for UI
        ui_edges = []
        for edge in edges:
            ui_edges.append({
                "id": str(edge.id),
                "source": str(edge.from_node_id),
                "target": str(edge.to_node_id),
                "type": edge.dependency_type,
                "label": self._get_edge_label(edge.dependency_type)
            })

        return {
            "nodes": ui_nodes,
            "edges": ui_edges,
            "levels": len(levels),
            "stats": {
                "total_nodes": len(nodes),
                **status_counts
            },
            "run_id": run_id
        }

    def _get_node_label(self, node: DAGNode) -> str:
        """
        Generate human-readable label for node

        Args:
            node: DAGNode instance

        Returns:
            Human-readable label string
        """
        if node.node_type == "planning":
            return "Planning"
        elif node.node_type == "terminator":
            return "Complete"
        elif node.node_type == "agent":
            agent_name = node.agent or "Agent"
            # Capitalize first letter of each word
            return agent_name.replace("_", " ").title()
        elif node.node_type == "approval":
            return "Approval Required"
        elif node.node_type == "control":
            return "Control"
        else:
            return node.node_type.replace("_", " ").title()

    def _get_edge_label(self, dependency_type: str) -> str:
        """
        Get human-readable label for edge type

        Args:
            dependency_type: Type of dependency

        Returns:
            Label string
        """
        labels = {
            "sequential": "",
            "parallel": "parallel",
            "conditional": "if",
            "optional": "optional"
        }
        return labels.get(dependency_type, dependency_type)

    def export_mermaid(self, run_id: str) -> str:
        """
        Export DAG as Mermaid diagram syntax

        Args:
            run_id: Workflow run ID

        Returns:
            Mermaid diagram string
        """
        nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id
        ).all()

        edges = self.db.query(DAGEdge).join(
            DAGNode, DAGEdge.from_node_id == DAGNode.id
        ).filter(
            DAGNode.run_id == run_id
        ).all()

        mermaid_lines = ["graph TD"]

        # Add nodes
        for node in nodes:
            label = self._get_node_label(node)
            node_shape = self._get_mermaid_shape(node.node_type)
            node_style = self._get_mermaid_style(node.node_type)

            # Create node definition
            node_def = f"    {self._sanitize_id(node.id)}{node_shape[0]}{label}{node_shape[1]}"
            if node_style:
                node_def += f":::{node_style}"
            mermaid_lines.append(node_def)

        # Add edges
        for edge in edges:
            arrow = self._get_mermaid_arrow(edge.dependency_type)
            from_id = self._sanitize_id(edge.from_node_id)
            to_id = self._sanitize_id(edge.to_node_id)
            label = self._get_edge_label(edge.dependency_type)

            if label:
                edge_def = f"    {from_id} {arrow}|{label}| {to_id}"
            else:
                edge_def = f"    {from_id} {arrow} {to_id}"
            mermaid_lines.append(edge_def)

        # Add styling
        mermaid_lines.extend([
            "",
            "    classDef planning fill:#e1f5ff,stroke:#01579b",
            "    classDef agent fill:#e8f5e9,stroke:#2e7d32",
            "    classDef approval fill:#fff3e0,stroke:#e65100",
            "    classDef terminator fill:#f3e5f5,stroke:#4a148c",
            "    classDef control fill:#fce4ec,stroke:#880e4f"
        ])

        return "\n".join(mermaid_lines)

    def _get_mermaid_shape(self, node_type: str) -> tuple:
        """
        Get Mermaid shape for node type

        Args:
            node_type: Type of node

        Returns:
            Tuple of (opening, closing) shape characters
        """
        shapes = {
            "planning": ("[", "]"),
            "agent": ("(", ")"),
            "approval": ("{", "}"),
            "terminator": ("([", "])"),
            "control": ("[[", "]]")
        }
        return shapes.get(node_type, ("[", "]"))

    def _get_mermaid_arrow(self, dependency_type: str) -> str:
        """
        Get Mermaid arrow for dependency type

        Args:
            dependency_type: Type of dependency

        Returns:
            Arrow string
        """
        arrows = {
            "sequential": "-->",
            "parallel": "-.->",
            "conditional": "-.->",
            "optional": "...->"
        }
        return arrows.get(dependency_type, "-->")

    def _get_mermaid_style(self, node_type: str) -> str:
        """
        Get Mermaid styling class for node type

        Args:
            node_type: Type of node

        Returns:
            Style class name
        """
        styles = {
            "planning": "planning",
            "agent": "agent",
            "approval": "approval",
            "terminator": "terminator",
            "control": "control"
        }
        return styles.get(node_type, "")

    def _sanitize_id(self, node_id: str) -> str:
        """
        Sanitize node ID for Mermaid syntax

        Args:
            node_id: Node ID

        Returns:
            Sanitized ID safe for Mermaid
        """
        # Replace hyphens with underscores (Mermaid doesn't like hyphens in IDs)
        return node_id.replace("-", "_")

    def export_dot(self, run_id: str) -> str:
        """
        Export DAG as Graphviz DOT format

        Args:
            run_id: Workflow run ID

        Returns:
            DOT format string
        """
        nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id
        ).all()

        edges = self.db.query(DAGEdge).join(
            DAGNode, DAGEdge.from_node_id == DAGNode.id
        ).filter(
            DAGNode.run_id == run_id
        ).all()

        dot_lines = [
            "digraph DAG {",
            "    rankdir=TB;",
            "    node [shape=box, style=rounded];",
            ""
        ]

        # Add nodes
        for node in nodes:
            label = self._get_node_label(node)
            color = self._get_dot_color(node.node_type)
            dot_lines.append(
                f'    "{node.id}" [label="{label}", fillcolor="{color}", style="rounded,filled"];'
            )

        dot_lines.append("")

        # Add edges
        for edge in edges:
            style = "solid" if edge.dependency_type == "sequential" else "dashed"
            dot_lines.append(
                f'    "{edge.from_node_id}" -> "{edge.to_node_id}" [style="{style}"];'
            )

        dot_lines.append("}")

        return "\n".join(dot_lines)

    def _get_dot_color(self, node_type: str) -> str:
        """
        Get DOT color for node type

        Args:
            node_type: Type of node

        Returns:
            Color string
        """
        colors = {
            "planning": "#e1f5ff",
            "agent": "#e8f5e9",
            "approval": "#fff3e0",
            "terminator": "#f3e5f5",
            "control": "#fce4ec"
        }
        return colors.get(node_type, "#ffffff")

    def get_node_statistics(self, run_id: str) -> Dict[str, Any]:
        """
        Get statistics about the DAG

        Args:
            run_id: Workflow run ID

        Returns:
            Dictionary with DAG statistics
        """
        nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id
        ).all()

        edges = self.db.query(DAGEdge).join(
            DAGNode, DAGEdge.from_node_id == DAGNode.id
        ).filter(
            DAGNode.run_id == run_id
        ).all()

        # Get execution levels
        sorter = TopologicalSorter(self.db)
        try:
            levels = sorter.sort(run_id)
            max_parallelism = max(len(level) for level in levels) if levels else 0
        except Exception:
            levels = []
            max_parallelism = 0

        # Count by type
        node_type_counts = {}
        status_counts = {}
        for node in nodes:
            node_type_counts[node.node_type] = node_type_counts.get(node.node_type, 0) + 1
            status_counts[node.status] = status_counts.get(node.status, 0) + 1

        # Count edges by type
        edge_type_counts = {}
        for edge in edges:
            edge_type_counts[edge.dependency_type] = edge_type_counts.get(edge.dependency_type, 0) + 1

        return {
            "run_id": run_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "total_levels": len(levels),
            "max_parallelism": max_parallelism,
            "node_types": node_type_counts,
            "node_statuses": status_counts,
            "edge_types": edge_type_counts
        }
