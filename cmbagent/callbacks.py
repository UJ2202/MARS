"""
Workflow Callbacks - Event hooks for workflow execution

This module provides a callback system for tracking workflow execution events.
Designed for long-running deep research workflows that can span days.

Key features:
- Database-backed state persistence
- WebSocket event emission for real-time UI updates
- Recovery/resume support for interrupted workflows
- Autogen-agnostic (no dependency on autogen internals)
- Circuit breaker: after N consecutive failures a callback is disabled for the run
"""

import logging
import structlog
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import time

logger = structlog.get_logger(__name__)

# Circuit breaker threshold: disable a callback after this many consecutive failures
_CIRCUIT_BREAKER_THRESHOLD = 5


class WorkflowPhase(Enum):
    """Phases of workflow execution"""
    INITIALIZING = "initializing"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class StepStatus(Enum):
    """Status of a workflow step"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepInfo:
    """Information about a workflow step"""
    step_number: int
    goal: str  # Step goal/description
    description: str  # Deprecated: use goal instead
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    execution_time: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None  # Human-readable summary of what was accomplished


@dataclass
class PlanInfo:
    """Information about the generated plan"""
    task: str
    num_steps: int
    steps: List[Dict[str, Any]]
    plan_text: str
    planning_time: float


@dataclass
class WorkflowCallbacks:
    """
    Callback hooks for workflow execution events.
    
    Usage:
        callbacks = WorkflowCallbacks(
            on_planning_start=lambda task, config: logger.info("planning_started task=%s", task),
            on_step_start=lambda step: logger.info("step_started step=%s", step.step_number),
            on_step_complete=lambda step: logger.info("step_completed step=%s", step.step_number),
        )
        
        planning_and_control_context_carryover(
            task="...",
            callbacks=callbacks,
            ...
        )
    """
    
    # Planning phase callbacks
    on_planning_start: Optional[Callable[[str, Dict[str, Any]], None]] = None
    on_planning_complete: Optional[Callable[[PlanInfo], None]] = None
    
    # Step execution callbacks
    on_step_start: Optional[Callable[[StepInfo], None]] = None
    on_step_complete: Optional[Callable[[StepInfo], None]] = None
    on_step_failed: Optional[Callable[[StepInfo], None]] = None
    
    # Workflow lifecycle callbacks
    on_workflow_start: Optional[Callable[[str, Dict[str, Any]], None]] = None
    on_workflow_complete: Optional[Callable[[Dict[str, Any], float], None]] = None
    on_workflow_failed: Optional[Callable[[str, Optional[int]], None]] = None
    
    # Progress updates (for finer granularity within steps)
    on_progress: Optional[Callable[[str, Dict[str, Any]], None]] = None
    
    # Agent transition callbacks (optional, for detailed tracking)
    on_agent_start: Optional[Callable[[str, int], None]] = None  # agent_name, step_number
    on_agent_complete: Optional[Callable[[str, int, Dict[str, Any]], None]] = None
    
    # Pause/Resume support - called before each step to check if should continue
    # Returns True to continue, False to pause/stop
    should_continue: Optional[Callable[[], bool]] = None
    # Called when workflow is paused, with a wait function to block until resumed
    on_pause_check: Optional[Callable[[], None]] = None

    # Cost tracking callback - called when cost data is available
    # Signature: on_cost_update(cost_data: Dict[str, Any]) where cost_data contains:
    #   - total_cost: float
    #   - total_tokens: int
    #   - model_breakdown: List[Dict] with model, cost, tokens
    #   - agent_breakdown: List[Dict] with agent, cost, tokens
    on_cost_update: Optional[Callable[[Dict[str, Any]], None]] = None

    # Agent message callback - called for every agent message during execution
    # Signature: on_agent_message(agent: str, role: str, content: str, metadata: Dict)
    # This captures ALL agent communications for comprehensive logging
    on_agent_message: Optional[Callable[[str, str, str, Dict[str, Any]], None]] = None

    # Code execution callback - called when code is generated or executed
    # Signature: on_code_execution(agent: str, code: str, language: str, result: Optional[str])
    on_code_execution: Optional[Callable[[str, str, str, Optional[str]], None]] = None

    # Tool call callback - called when agents make tool/function calls
    # Signature: on_tool_call(agent: str, tool_name: str, arguments: Dict, result: Optional[Any])
    on_tool_call: Optional[Callable[[str, str, Dict[str, Any], Optional[Any]], None]] = None

    # Phase change callback - called when workflow phase changes
    # Signature: on_phase_change(phase: str, step_number: Optional[int])
    # phase is one of: 'planning', 'control', 'execution'
    on_phase_change: Optional[Callable[[str, Optional[int]], None]] = None

    # --- Circuit breaker state (internal) ---
    _failure_counts: Dict[str, int] = field(default_factory=dict, repr=False)

    def _safe_invoke(self, name: str, callback: Optional[Callable], *args, **kwargs) -> None:
        """Invoke a callback with circuit breaker protection.

        After ``_CIRCUIT_BREAKER_THRESHOLD`` consecutive failures the callback
        is disabled for the remainder of the run.
        """
        if callback is None:
            return
        if self._failure_counts.get(name, 0) >= _CIRCUIT_BREAKER_THRESHOLD:
            return  # circuit open – skip
        try:
            callback(*args, **kwargs)
            # success resets counter
            self._failure_counts[name] = 0
        except Exception:
            count = self._failure_counts.get(name, 0) + 1
            self._failure_counts[name] = count
            if count >= _CIRCUIT_BREAKER_THRESHOLD:
                logger.error(
                    "circuit_breaker_open callback=%s failures=%d – disabling",
                    name, count,
                )
            else:
                logger.error("callback_error callback=%s failure=%d/%d",
                             name, count, _CIRCUIT_BREAKER_THRESHOLD,
                             exc_info=True)

    def invoke_phase_change(self, phase: str, step_number: Optional[int] = None) -> None:
        """Safely invoke on_phase_change callback when workflow phase changes."""
        self._safe_invoke("on_phase_change", self.on_phase_change, phase, step_number)

    def invoke_planning_start(self, task: str, config: Dict[str, Any]) -> None:
        """Safely invoke on_planning_start callback."""
        self._safe_invoke("on_planning_start", self.on_planning_start, task, config)

    def invoke_planning_complete(self, plan_info: PlanInfo) -> None:
        """Safely invoke on_planning_complete callback."""
        self._safe_invoke("on_planning_complete", self.on_planning_complete, plan_info)

    def invoke_step_start(self, step_info: StepInfo) -> None:
        """Safely invoke on_step_start callback."""
        self._safe_invoke("on_step_start", self.on_step_start, step_info)

    def invoke_step_complete(self, step_info: StepInfo) -> None:
        """Safely invoke on_step_complete callback."""
        self._safe_invoke("on_step_complete", self.on_step_complete, step_info)

    def invoke_step_failed(self, step_info: StepInfo) -> None:
        """Safely invoke on_step_failed callback."""
        self._safe_invoke("on_step_failed", self.on_step_failed, step_info)

    def invoke_workflow_start(self, task: str, config: Dict[str, Any]) -> None:
        """Safely invoke on_workflow_start callback."""
        self._safe_invoke("on_workflow_start", self.on_workflow_start, task, config)

    def invoke_workflow_complete(self, final_context: Dict[str, Any], total_time: float) -> None:
        """Safely invoke on_workflow_complete callback."""
        self._safe_invoke("on_workflow_complete", self.on_workflow_complete, final_context, total_time)

    def invoke_workflow_failed(self, error: str, step_number: Optional[int] = None) -> None:
        """Safely invoke on_workflow_failed callback."""
        self._safe_invoke("on_workflow_failed", self.on_workflow_failed, error, step_number)

    def invoke_progress(self, message: str, data: Dict[str, Any]) -> None:
        """Safely invoke on_progress callback."""
        self._safe_invoke("on_progress", self.on_progress, message, data)

    def check_should_continue(self) -> bool:
        """Check if workflow should continue or pause.

        Returns:
            True if should continue, False if should pause/stop
        """
        if self.should_continue:
            if not callable(self.should_continue):
                logger.warning("should_continue_not_callable type=%s", type(self.should_continue))
                return bool(self.should_continue)
            if self._failure_counts.get("should_continue", 0) >= _CIRCUIT_BREAKER_THRESHOLD:
                return True  # circuit open – default to continue
            try:
                result = self.should_continue()
                self._failure_counts["should_continue"] = 0
                return result
            except Exception:
                count = self._failure_counts.get("should_continue", 0) + 1
                self._failure_counts["should_continue"] = count
                logger.error("callback_error callback=should_continue failure=%d/%d",
                             count, _CIRCUIT_BREAKER_THRESHOLD, exc_info=True)
                return True
        return True

    def invoke_pause_check(self) -> None:
        """Invoke pause check - blocks if paused until resumed."""
        self._safe_invoke("on_pause_check", self.on_pause_check)

    def invoke_cost_update(self, cost_data: Dict[str, Any]) -> None:
        """Safely invoke on_cost_update callback with cost information."""
        self._safe_invoke("on_cost_update", self.on_cost_update, cost_data)

    def invoke_agent_message(self, agent: str, role: str, content: str, metadata: Dict[str, Any] = None) -> None:
        """Safely invoke on_agent_message callback for comprehensive agent logging."""
        self._safe_invoke("on_agent_message", self.on_agent_message, agent, role, content, metadata or {})

    def invoke_code_execution(self, agent: str, code: str, language: str, result: Optional[str] = None) -> None:
        """Safely invoke on_code_execution callback when code is generated/executed."""
        self._safe_invoke("on_code_execution", self.on_code_execution, agent, code, language, result)

    def invoke_tool_call(self, agent: str, tool_name: str, arguments: Dict[str, Any], result: Optional[Any] = None) -> None:
        """Safely invoke on_tool_call callback when agents use tools/functions."""
        self._safe_invoke("on_tool_call", self.on_tool_call, agent, tool_name, arguments, result)


def create_null_callbacks() -> WorkflowCallbacks:
    """Create a callbacks instance with no handlers (for backward compatibility)"""
    return WorkflowCallbacks()


def create_print_callbacks() -> WorkflowCallbacks:
    """Create a callbacks instance that logs all events (for debugging)"""
    _logger = logging.getLogger(__name__ + ".print_callbacks")
    return WorkflowCallbacks(
        on_planning_start=lambda task, config: _logger.info("planning_started task=%s", task[:100]),
        on_planning_complete=lambda plan: _logger.info("planning_complete num_steps=%s", plan.num_steps),
        on_step_start=lambda step: _logger.info("step_started step_number=%s goal=%s", step.step_number, step.goal),
        on_step_complete=lambda step: _logger.info("step_completed step_number=%s execution_time=%s", step.step_number, step.execution_time),
        on_step_failed=lambda step: _logger.error("step_failed step_number=%s error=%s", step.step_number, step.error),
        on_workflow_start=lambda task, config: _logger.info("workflow_started"),
        on_workflow_complete=lambda ctx, time: _logger.info("workflow_complete total_time=%.2f", time),
        on_workflow_failed=lambda err, step: _logger.error("workflow_failed step=%s error=%s", step, err),
    )


def merge_callbacks(*callbacks_list: WorkflowCallbacks) -> WorkflowCallbacks:
    """
    Merge multiple WorkflowCallbacks into one that invokes all of them.
    
    Args:
        *callbacks_list: WorkflowCallbacks instances to merge
        
    Returns:
        New WorkflowCallbacks that invokes all provided callbacks
    """
    def make_merged_callback(method_name: str):
        def merged(*args, **kwargs):
            for cb in callbacks_list:
                callback = getattr(cb, method_name, None)
                if callback:
                    try:
                        callback(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"Error in merged callback {method_name}: {e}")
        return merged
    
    def make_merged_should_continue():
        """Special merge for should_continue - returns False if any callback returns False"""
        def merged():
            for cb in callbacks_list:
                if cb.should_continue:
                    # Defensive check: ensure should_continue is callable
                    if not callable(cb.should_continue):
                        # Treat non-callable truthy values as True, falsy as False
                        if not cb.should_continue:
                            return False
                        continue
                    try:
                        if not cb.should_continue():
                            return False
                    except Exception as e:
                        logger.error(f"Error in should_continue callback: {e}")
            return True
        return merged
    
    def make_merged_pause_check():
        """Merge pause check callbacks - call all of them"""
        def merged():
            for cb in callbacks_list:
                if cb.on_pause_check:
                    try:
                        cb.on_pause_check()
                    except Exception as e:
                        logger.error(f"Error in on_pause_check callback: {e}")
        return merged
    
    callback_names = [
        "on_planning_start", "on_planning_complete",
        "on_step_start", "on_step_complete", "on_step_failed",
        "on_workflow_start", "on_workflow_complete", "on_workflow_failed",
        "on_progress", "on_agent_start", "on_agent_complete",
        "on_cost_update",  # Include cost callback in merge
        "on_agent_message", "on_code_execution", "on_tool_call",  # Comprehensive logging callbacks
        "on_phase_change"  # Phase tracking callback
    ]

    merged_dict = {name: make_merged_callback(name) for name in callback_names}

    # Handle special callbacks
    merged_dict["should_continue"] = make_merged_should_continue()
    merged_dict["on_pause_check"] = make_merged_pause_check()

    return WorkflowCallbacks(**merged_dict)

