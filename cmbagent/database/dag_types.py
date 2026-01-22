"""
DAG (Directed Acyclic Graph) Types and Metadata Definitions

This module defines the types and metadata structures used for workflow DAG representation.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict


class DAGNodeType(str, Enum):
    """Types of nodes in execution DAG"""
    PLANNING = "planning"           # Initial planning step
    CONTROL = "control"             # Orchestration logic
    AGENT = "agent"                 # Agent execution (engineer, researcher, etc.)
    APPROVAL = "approval"           # Human approval gate
    PARALLEL_GROUP = "parallel_group"  # Container for parallel tasks
    TERMINATOR = "terminator"       # End of workflow


@dataclass
class DAGNodeMetadata:
    """Metadata for DAG nodes

    This dataclass contains all the metadata associated with a DAG node,
    including dependencies, task information, and execution configuration.
    """
    agent: Optional[str] = None                    # Agent to execute (for AGENT nodes)
    task_description: Optional[str] = None         # Task for this node
    depends_on: List[str] = field(default_factory=list)  # List of node IDs this depends on
    parallel_group: Optional[str] = None           # Group ID for parallel execution
    approval_required: bool = False                # Whether approval needed
    retry_config: Dict[str, Any] = field(default_factory=dict)  # Retry settings
    estimated_duration: Optional[int] = None       # Estimated time in seconds
    phase: Optional[str] = None                    # Workflow phase (planning, execution, etc.)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary for JSON serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DAGNodeMetadata':
        """Create metadata from dictionary"""
        return cls(**data)


class DependencyType(str, Enum):
    """Types of dependencies between DAG nodes"""
    SEQUENTIAL = "sequential"       # Must execute after predecessor completes
    PARALLEL = "parallel"           # Can execute in parallel with siblings
    CONDITIONAL = "conditional"     # Execute based on condition
    OPTIONAL = "optional"           # Optional dependency


@dataclass
class ExecutionLevel:
    """Represents a level in the execution order

    Each level contains nodes that can be executed in parallel.
    """
    level: int
    node_ids: List[str] = field(default_factory=list)
    parallel: bool = False

    def __len__(self) -> int:
        """Return number of nodes in this level"""
        return len(self.node_ids)

    def add_node(self, node_id: str) -> None:
        """Add a node to this execution level"""
        if node_id not in self.node_ids:
            self.node_ids.append(node_id)
            # Mark as parallel if more than one node
            self.parallel = len(self.node_ids) > 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "level": self.level,
            "node_ids": self.node_ids,
            "parallel": self.parallel,
            "node_count": len(self.node_ids)
        }


class DAGValidationError(Exception):
    """Raised when DAG validation fails"""
    pass


class CycleDetectedError(DAGValidationError):
    """Raised when a cycle is detected in the DAG"""
    pass


class InvalidDependencyError(DAGValidationError):
    """Raised when an invalid dependency is specified"""
    pass
