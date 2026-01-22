"""State transition rules and guards for workflows and steps."""
from typing import Any, Callable, Dict, List
from cmbagent.database.states import WorkflowState, StepState


# Guard functions for workflow transitions
def has_task_description(run: Any) -> bool:
    """Check if workflow run has a task description."""
    return run.task_description is not None and len(run.task_description.strip()) > 0


def has_valid_plan(run: Any) -> bool:
    """Check if workflow run has a valid execution plan."""
    # For now, just check if we've transitioned through planning
    # In future, could check for plan_data or plan nodes
    return True


def has_approval(run: Any) -> bool:
    """Check if workflow has received approval to continue."""
    # This will be properly implemented in Stage 6 (HITL)
    # For now, always return True
    return True


# Workflow transition rules
WORKFLOW_TRANSITIONS: Dict[WorkflowState, Dict[str, Any]] = {
    WorkflowState.DRAFT: {
        "allowed_next": [WorkflowState.PLANNING, WorkflowState.CANCELLED],
        "guards": {
            WorkflowState.PLANNING: has_task_description,
        }
    },
    WorkflowState.PLANNING: {
        "allowed_next": [WorkflowState.EXECUTING, WorkflowState.FAILED, WorkflowState.CANCELLED],
        "guards": {
            WorkflowState.EXECUTING: has_valid_plan,
        }
    },
    WorkflowState.EXECUTING: {
        "allowed_next": [
            WorkflowState.PAUSED,
            WorkflowState.WAITING_APPROVAL,
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED
        ],
        "guards": {}
    },
    WorkflowState.PAUSED: {
        "allowed_next": [WorkflowState.EXECUTING, WorkflowState.CANCELLED],
        "guards": {}
    },
    WorkflowState.WAITING_APPROVAL: {
        "allowed_next": [WorkflowState.EXECUTING, WorkflowState.CANCELLED],
        "guards": {
            WorkflowState.EXECUTING: has_approval,
        }
    },
    WorkflowState.COMPLETED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    },
    WorkflowState.FAILED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    },
    WorkflowState.CANCELLED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    }
}


# Step transition rules
STEP_TRANSITIONS: Dict[StepState, Dict[str, Any]] = {
    StepState.PENDING: {
        "allowed_next": [StepState.RUNNING, StepState.SKIPPED, StepState.CANCELLED],
        "guards": {}
    },
    StepState.RUNNING: {
        "allowed_next": [
            StepState.PAUSED,
            StepState.WAITING_APPROVAL,
            StepState.COMPLETED,
            StepState.FAILED,
            StepState.CANCELLED
        ],
        "guards": {}
    },
    StepState.PAUSED: {
        "allowed_next": [StepState.RUNNING, StepState.CANCELLED],
        "guards": {}
    },
    StepState.WAITING_APPROVAL: {
        "allowed_next": [StepState.RUNNING, StepState.CANCELLED],
        "guards": {}
    },
    StepState.COMPLETED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    },
    StepState.FAILED: {
        "allowed_next": [StepState.RUNNING],  # Can retry failed steps
        "guards": {}
    },
    StepState.SKIPPED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    },
    StepState.CANCELLED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    }
}
