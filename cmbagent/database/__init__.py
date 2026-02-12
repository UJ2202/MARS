"""
Database module for CMBAgent.

Provides SQLAlchemy models, repository layer, and persistence management
for workflow execution, checkpoints, and history tracking.
"""

from cmbagent.database.base import (
    get_engine,
    get_db_session,
    init_database,
    Base,
)
from cmbagent.database.models import (
    Session,
    Project,
    WorkflowRun,
    WorkflowStep,
    DAGNode,
    DAGEdge,
    Checkpoint,
    Message,
    CostRecord,
    ApprovalRequest,
    Branch,
    WorkflowMetric,
    File,
    StateHistory,
    ExecutionEvent,
)
from cmbagent.database.repository import (
    WorkflowRepository,
    SessionRepository,
    DAGRepository,
    CostRepository,
    CheckpointRepository,
    EventRepository,
)
from cmbagent.database.states import (
    WorkflowState,
    StepState,
)
from cmbagent.database.state_machine import (
    StateMachine,
    StateMachineError,
    EventEmitter,
)
from cmbagent.database.workflow_controller import (
    WorkflowController,
)
from cmbagent.database.dag_builder import (
    DAGBuilder,
)
from cmbagent.database.topological_sort import (
    TopologicalSorter,
)
from cmbagent.database.dag_visualizer import (
    DAGVisualizer,
)
from cmbagent.database.approval_types import (
    ApprovalMode,
    CheckpointType,
    ApprovalResolution,
    ApprovalCheckpoint,
    ApprovalConfig,
    get_approval_config,
)
from cmbagent.database.websocket_approval_manager import (
    WebSocketApprovalManager,
    SimpleApprovalRequest,
)
from cmbagent.database.session_manager import (
    SessionManager,
)

__all__ = [
    # Base
    "get_engine",
    "get_db_session",
    "init_database",
    "Base",
    # Models
    "Session",
    "Project",
    "WorkflowRun",
    "WorkflowStep",
    "DAGNode",
    "DAGEdge",
    "Checkpoint",
    "Message",
    "CostRecord",
    "ApprovalRequest",
    "Branch",
    "WorkflowMetric",
    "File",
    "StateHistory",
    "ExecutionEvent",
    # Repositories
    "WorkflowRepository",
    "SessionRepository",
    "DAGRepository",
    "CostRepository",
    "CheckpointRepository",
    "EventRepository",
    # Session Manager
    "SessionManager",
    # State Machine
    "WorkflowState",
    "StepState",
    "StateMachine",
    "StateMachineError",
    "EventEmitter",
    "WorkflowController",
    # DAG System
    "DAGBuilder",
    "TopologicalSorter",
    "DAGVisualizer",
    # Approval System
    "ApprovalMode",
    "CheckpointType",
    "ApprovalResolution",
    "ApprovalCheckpoint",
    "ApprovalConfig",
    "get_approval_config",
    "WebSocketApprovalManager",
    "SimpleApprovalRequest",
]
