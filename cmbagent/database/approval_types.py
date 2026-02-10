"""
Approval types and configurations for HITL (Human-in-the-Loop) workflow control.

This module defines the approval modes and checkpoint configurations for
pausing workflow execution and gathering user feedback.
"""

from enum import Enum
from typing import Optional, List, Callable, Any, Dict
from dataclasses import dataclass, field


class ApprovalMode(str, Enum):
    """
    Approval modes for workflow execution.

    Determines when and how often the workflow pauses for human approval.
    """
    NONE = "none"                          # No approvals (default, backward compatible)
    AFTER_PLANNING = "after_planning"      # Single approval after plan created
    BEFORE_EACH_STEP = "before_each_step"  # Approval before each major step
    ON_ERROR = "on_error"                  # Approval only when errors occur
    MANUAL = "manual"                      # User can pause anytime via UI
    COPILOT = "copilot"                    # Approval for code/file/command operations
    CUSTOM = "custom"                      # Custom approval checkpoints


class CheckpointType(str, Enum):
    """Types of approval checkpoints"""
    AFTER_PLANNING = "after_planning"
    BEFORE_STEP = "before_step"
    ON_ERROR = "on_error"
    MANUAL_PAUSE = "manual_pause"
    CUSTOM = "custom"
    # Copilot-specific checkpoints
    BEFORE_CODE_EXECUTION = "before_code_execution"
    BEFORE_FILE_EDIT = "before_file_edit"
    BEFORE_FILE_DELETE = "before_file_delete"
    BEFORE_COMMAND_EXECUTION = "before_command_execution"


class ApprovalResolution(str, Enum):
    """Possible resolutions for approval requests"""
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"


@dataclass
class ApprovalCheckpoint:
    """
    Defines a custom approval checkpoint in the workflow.

    Attributes:
        checkpoint_type: Type of checkpoint
        message: Message to show user
        options: Available approval options (approve, reject, modify, etc.)
        allow_feedback: Whether user can provide text feedback
        step_number: Specific step number (optional)
        step_type: Type of step (optional, e.g., "planning", "agent", "data")
        condition: Custom condition function that returns True if approval needed
        metadata: Additional checkpoint metadata
    """
    checkpoint_type: CheckpointType
    message: str
    options: List[str] = field(default_factory=lambda: ["approve", "reject", "modify"])
    allow_feedback: bool = True
    step_number: Optional[int] = None
    step_type: Optional[str] = None
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def should_trigger(self, context: Dict[str, Any]) -> bool:
        """
        Check if this checkpoint should trigger based on context.

        Args:
            context: Current workflow context

        Returns:
            True if checkpoint should trigger
        """
        if self.condition:
            return self.condition(context)
        return True


@dataclass
class ApprovalConfig:
    """
    Configuration for approval system.

    Attributes:
        mode: Primary approval mode
        custom_checkpoints: List of custom checkpoints
        timeout_seconds: Max time to wait for approval (None = infinite)
        default_on_timeout: Default action if timeout occurs
        require_feedback_on_reject: Require feedback when rejecting
        auto_approve_patterns: Patterns that auto-approve (e.g., read-only operations)
    """
    mode: ApprovalMode = ApprovalMode.NONE
    custom_checkpoints: List[ApprovalCheckpoint] = field(default_factory=list)
    timeout_seconds: Optional[int] = None
    default_on_timeout: str = "reject"
    require_feedback_on_reject: bool = False
    auto_approve_patterns: List[str] = field(default_factory=list)

    def is_enabled(self) -> bool:
        """Check if approval system is enabled"""
        return self.mode != ApprovalMode.NONE

    def requires_approval_at_planning(self) -> bool:
        """Check if approval required after planning"""
        return self.mode in [ApprovalMode.AFTER_PLANNING, ApprovalMode.BEFORE_EACH_STEP]

    def requires_approval_before_steps(self) -> bool:
        """Check if approval required before each step"""
        return self.mode == ApprovalMode.BEFORE_EACH_STEP

    def requires_approval_on_error(self) -> bool:
        """Check if approval required on errors"""
        return self.mode in [ApprovalMode.ON_ERROR, ApprovalMode.BEFORE_EACH_STEP]

    def requires_copilot_approvals(self) -> bool:
        """Check if copilot-style approvals required (code, files, commands)"""
        return self.mode == ApprovalMode.COPILOT


# Default approval configurations for common scenarios
DEFAULT_CONFIGS = {
    "autonomous": ApprovalConfig(
        mode=ApprovalMode.NONE
    ),
    "review_plan": ApprovalConfig(
        mode=ApprovalMode.AFTER_PLANNING
    ),
    "step_by_step": ApprovalConfig(
        mode=ApprovalMode.BEFORE_EACH_STEP
    ),
    "error_recovery": ApprovalConfig(
        mode=ApprovalMode.ON_ERROR
    ),
    "copilot": ApprovalConfig(
        mode=ApprovalMode.COPILOT,
        auto_approve_patterns=["read_file", "search", "list_files"]  # Auto-approve read-only ops
    ),
}


def get_approval_config(name: str = "autonomous") -> ApprovalConfig:
    """
    Get a predefined approval configuration.

    Args:
        name: Name of configuration (autonomous, review_plan, step_by_step, error_recovery)

    Returns:
        ApprovalConfig instance
    """
    return DEFAULT_CONFIGS.get(name, DEFAULT_CONFIGS["autonomous"])
