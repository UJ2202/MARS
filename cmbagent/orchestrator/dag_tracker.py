"""
DAG (Directed Acyclic Graph) Tracker

Tracks phase execution as a DAG, showing dependencies and data flow.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
from enum import Enum
import json
from pathlib import Path


class PhaseStatus(str, Enum):
    """Status of a phase in the DAG."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CACHED = "cached"


@dataclass
class PhaseNode:
    """
    Represents a phase in the DAG.

    Attributes:
        id: Unique identifier for this phase execution
        phase_name: Name of the phase (e.g., "research", "planning")
        config: Configuration passed to the phase
        dependencies: IDs of phases this depends on
        dependents: IDs of phases that depend on this
        status: Current status of the phase
        start_time: When phase started
        end_time: When phase completed
        duration: Duration in seconds
        result: Result of phase execution
        error: Error message if failed
        context_input: Context passed to phase
        context_output: Context produced by phase
        metrics: Performance metrics
        retry_count: Number of retries attempted
    """
    id: str
    phase_name: str
    config: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    status: PhaseStatus = PhaseStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    context_input: Optional[Dict[str, Any]] = None
    context_output: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'phase_name': self.phase_name,
            'config': self.config,
            'dependencies': self.dependencies,
            'dependents': self.dependents,
            'status': self.status.value,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'error': self.error,
            'metrics': self.metrics,
            'retry_count': self.retry_count,
        }


class DAGTracker:
    """
    Tracks phase execution as a Directed Acyclic Graph.

    Maintains the execution DAG, detects cycles, identifies ready phases,
    and provides visualization capabilities.
    """

    def __init__(self, run_id: str):
        """
        Initialize DAG tracker.

        Args:
            run_id: Unique identifier for this orchestration run
        """
        self.run_id = run_id
        self.nodes: Dict[str, PhaseNode] = {}
        self.execution_order: List[str] = []
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None

    def add_node(
        self,
        phase_id: str,
        phase_name: str,
        config: Dict[str, Any],
        dependencies: Optional[List[str]] = None
    ) -> PhaseNode:
        """
        Add a phase node to the DAG.

        Args:
            phase_id: Unique ID for this phase execution
            phase_name: Name of the phase
            config: Phase configuration
            dependencies: IDs of phases this depends on

        Returns:
            The created PhaseNode

        Raises:
            ValueError: If adding this node creates a cycle
        """
        deps = dependencies or []

        # Validate dependencies exist
        for dep_id in deps:
            if dep_id not in self.nodes:
                raise ValueError(f"Dependency {dep_id} not found in DAG")

        # Create node
        node = PhaseNode(
            id=phase_id,
            phase_name=phase_name,
            config=config,
            dependencies=deps
        )

        # Add to graph
        self.nodes[phase_id] = node

        # Update dependents for dependencies
        for dep_id in deps:
            self.nodes[dep_id].dependents.append(phase_id)

        # Check for cycles
        if self._has_cycle():
            # Rollback
            del self.nodes[phase_id]
            for dep_id in deps:
                self.nodes[dep_id].dependents.remove(phase_id)
            raise ValueError(f"Adding {phase_id} creates a cycle in the DAG")

        return node

    def mark_running(self, phase_id: str):
        """Mark a phase as running."""
        node = self.nodes[phase_id]
        node.status = PhaseStatus.RUNNING
        node.start_time = datetime.now()

    def mark_completed(
        self,
        phase_id: str,
        result: Any,
        context_output: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None
    ):
        """Mark a phase as completed."""
        node = self.nodes[phase_id]
        node.status = PhaseStatus.COMPLETED
        node.end_time = datetime.now()
        node.duration = (node.end_time - node.start_time).total_seconds() if node.start_time else None
        node.result = result
        node.context_output = context_output
        if metrics:
            node.metrics.update(metrics)
        self.execution_order.append(phase_id)

    def mark_failed(self, phase_id: str, error: str):
        """Mark a phase as failed."""
        node = self.nodes[phase_id]
        node.status = PhaseStatus.FAILED
        node.end_time = datetime.now()
        node.duration = (node.end_time - node.start_time).total_seconds() if node.start_time else None
        node.error = error

    def mark_skipped(self, phase_id: str, reason: str):
        """Mark a phase as skipped."""
        node = self.nodes[phase_id]
        node.status = PhaseStatus.SKIPPED
        node.error = f"Skipped: {reason}"

    def mark_cached(self, phase_id: str, cached_result: Any):
        """Mark a phase as cached (didn't need to run)."""
        node = self.nodes[phase_id]
        node.status = PhaseStatus.CACHED
        node.result = cached_result
        node.duration = 0.0

    def get_ready_phases(self) -> List[str]:
        """
        Get phases that are ready to execute.

        A phase is ready if:
        - Status is PENDING
        - All dependencies are COMPLETED or CACHED

        Returns:
            List of phase IDs ready to execute
        """
        ready = []
        for phase_id, node in self.nodes.items():
            if node.status != PhaseStatus.PENDING:
                continue

            # Check all dependencies are satisfied
            deps_satisfied = all(
                self.nodes[dep_id].status in [PhaseStatus.COMPLETED, PhaseStatus.CACHED]
                for dep_id in node.dependencies
            )

            if deps_satisfied:
                ready.append(phase_id)

        return ready

    def get_critical_path(self) -> List[str]:
        """
        Calculate the critical path (longest path) through the DAG.

        Returns:
            List of phase IDs in the critical path
        """
        if not self.nodes:
            return []

        # Calculate earliest start times
        earliest_start = {}
        for phase_id in self.topological_sort():
            if not self.nodes[phase_id].dependencies:
                earliest_start[phase_id] = 0.0
            else:
                max_dep_time = max(
                    earliest_start[dep_id] + (self.nodes[dep_id].duration or 0.0)
                    for dep_id in self.nodes[phase_id].dependencies
                )
                earliest_start[phase_id] = max_dep_time

        # Find longest path (critical path)
        # Start from nodes with no dependents
        leaf_nodes = [p for p, n in self.nodes.items() if not n.dependents]

        max_path = []
        max_duration = 0.0

        for leaf in leaf_nodes:
            path = self._longest_path_to(leaf, earliest_start)
            path_duration = sum(self.nodes[p].duration or 0.0 for p in path)
            if path_duration > max_duration:
                max_duration = path_duration
                max_path = path

        return max_path

    def _longest_path_to(self, node_id: str, earliest_start: Dict[str, float]) -> List[str]:
        """Find longest path to a node."""
        node = self.nodes[node_id]

        if not node.dependencies:
            return [node_id]

        # Find dependency with latest earliest start
        max_dep = max(node.dependencies, key=lambda d: earliest_start[d])
        return self._longest_path_to(max_dep, earliest_start) + [node_id]

    def topological_sort(self) -> List[str]:
        """
        Perform topological sort of the DAG.

        Returns:
            List of phase IDs in topological order

        Raises:
            ValueError: If DAG has a cycle
        """
        # Kahn's algorithm
        in_degree = {node_id: len(node.dependencies) for node_id, node in self.nodes.items()}
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            for dependent_id in self.nodes[node_id].dependents:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        if len(result) != len(self.nodes):
            raise ValueError("DAG contains a cycle")

        return result

    def _has_cycle(self) -> bool:
        """Check if the DAG has a cycle."""
        try:
            self.topological_sort()
            return False
        except ValueError:
            return True

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get execution statistics for the DAG.

        Returns:
            Dictionary with statistics
        """
        total_phases = len(self.nodes)
        completed = sum(1 for n in self.nodes.values() if n.status == PhaseStatus.COMPLETED)
        failed = sum(1 for n in self.nodes.values() if n.status == PhaseStatus.FAILED)
        cached = sum(1 for n in self.nodes.values() if n.status == PhaseStatus.CACHED)
        total_duration = sum(n.duration or 0.0 for n in self.nodes.values())

        critical_path = self.get_critical_path()
        critical_path_duration = sum(
            self.nodes[p].duration or 0.0 for p in critical_path
        )

        return {
            'run_id': self.run_id,
            'total_phases': total_phases,
            'completed': completed,
            'failed': failed,
            'cached': cached,
            'total_duration': total_duration,
            'critical_path_duration': critical_path_duration,
            'critical_path_length': len(critical_path),
            'average_phase_duration': total_duration / total_phases if total_phases > 0 else 0.0,
            'success_rate': completed / total_phases if total_phases > 0 else 0.0,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert DAG to dictionary for serialization."""
        return {
            'run_id': self.run_id,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'nodes': {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            'execution_order': self.execution_order,
            'statistics': self.get_statistics(),
        }

    def save_to_file(self, filepath: Path):
        """Save DAG to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: Path) -> 'DAGTracker':
        """Load DAG from JSON file."""
        with open(filepath) as f:
            data = json.load(f)

        tracker = cls(data['run_id'])
        tracker.created_at = datetime.fromisoformat(data['created_at'])
        if data['completed_at']:
            tracker.completed_at = datetime.fromisoformat(data['completed_at'])
        tracker.execution_order = data['execution_order']

        # Recreate nodes
        for node_id, node_data in data['nodes'].items():
            node = PhaseNode(
                id=node_data['id'],
                phase_name=node_data['phase_name'],
                config=node_data['config'],
                dependencies=node_data['dependencies'],
                dependents=node_data['dependents'],
                status=PhaseStatus(node_data['status']),
                start_time=datetime.fromisoformat(node_data['start_time']) if node_data['start_time'] else None,
                end_time=datetime.fromisoformat(node_data['end_time']) if node_data['end_time'] else None,
                duration=node_data['duration'],
                error=node_data['error'],
                metrics=node_data['metrics'],
                retry_count=node_data['retry_count'],
            )
            tracker.nodes[node_id] = node

        return tracker

    def visualize(self, output_path: Optional[Path] = None) -> str:
        """
        Generate DOT format visualization of the DAG.

        Args:
            output_path: Optional path to save the DOT file

        Returns:
            DOT format string
        """
        dot_lines = ['digraph PhaseDAG {']
        dot_lines.append('  rankdir=TB;')
        dot_lines.append('  node [shape=box, style=rounded];')
        dot_lines.append('')

        # Color scheme for statuses
        colors = {
            PhaseStatus.PENDING: 'lightgray',
            PhaseStatus.RUNNING: 'lightblue',
            PhaseStatus.COMPLETED: 'lightgreen',
            PhaseStatus.FAILED: 'lightcoral',
            PhaseStatus.SKIPPED: 'lightyellow',
            PhaseStatus.CACHED: 'lavender',
        }

        # Add nodes
        for node_id, node in self.nodes.items():
            color = colors[node.status]
            label = f'{node.phase_name}\\n({node.id})\\n{node.status.value}'
            if node.duration:
                label += f'\\n{node.duration:.2f}s'
            dot_lines.append(f'  "{node_id}" [label="{label}", fillcolor={color}, style="rounded,filled"];')

        dot_lines.append('')

        # Add edges
        for node_id, node in self.nodes.items():
            for dep_id in node.dependencies:
                dot_lines.append(f'  "{dep_id}" -> "{node_id}";')

        dot_lines.append('}')

        dot_content = '\n'.join(dot_lines)

        if output_path:
            with open(output_path, 'w') as f:
                f.write(dot_content)

        return dot_content
