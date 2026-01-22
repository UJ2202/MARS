"""State enumerations for workflows and steps."""
from enum import Enum


class WorkflowState(str, Enum):
    """Valid states for workflow_runs."""

    DRAFT = "draft"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepState(str, Enum):
    """Valid states for workflow_steps."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
