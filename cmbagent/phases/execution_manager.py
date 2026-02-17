"""
Phase Execution Manager - Generalized execution infrastructure for phases.

This module provides a unified execution manager that handles all cross-cutting
concerns for phase execution:

1. **Callbacks**: Automatic invocation of workflow callbacks
2. **Database Logging**: WorkflowRun creation, event tracking
3. **Pause/Cancel**: Workflow control checks
4. **Error Handling**: Consistent error handling and recovery
5. **Timing**: Automatic timing of phase execution

File tracking is handled by DAGTracker → FileRepository (Stage 4).
DAG management is handled by DAGTracker in the app layer.
PhaseExecutionManager delegates DAG concerns via callbacks.

Usage:
    class MyPhase(Phase):
        async def execute(self, context: PhaseContext) -> PhaseResult:
            with PhaseExecutionManager(context, self) as manager:
                # Your phase logic here
                manager.log_event("custom_event", {"data": "value"})
                result = do_work()
                return manager.complete(result)

Adding a New Phase:
    1. Create a new phase class extending Phase
    2. Use PhaseExecutionManager in execute() method
    3. The manager automatically handles:
       - Callback invocations (phase_change, step_start, etc.)
       - Database event logging
       - Pause/cancel checks
       - Error handling
"""

from __future__ import annotations

import os
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from enum import Enum
import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from cmbagent.phases.base import Phase, PhaseContext, PhaseResult, PhaseStatus
    from cmbagent.callbacks import WorkflowCallbacks, StepInfo, PlanInfo
    from cmbagent.execution.event_capture import EventCaptureManager


class PhaseEventType(Enum):
    """Types of events that can be logged during phase execution."""
    PHASE_START = "phase_start"
    PHASE_COMPLETE = "phase_complete"
    PHASE_FAILED = "phase_failed"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    STEP_FAILED = "step_failed"
    PLAN_GENERATED = "plan_generated"
    AGENT_MESSAGE = "agent_message"
    CODE_EXECUTION = "code_execution"
    TOOL_CALL = "tool_call"
    CHECKPOINT = "checkpoint"
    CUSTOM = "custom"


@dataclass
class PhaseExecutionConfig:
    """
    Configuration for phase execution behavior.

    Attributes:
        enable_callbacks: Whether to invoke workflow callbacks
        enable_pause_check: Whether to check for pause/cancel
        auto_checkpoint: Whether to auto-save checkpoints
        checkpoint_interval: Seconds between auto-checkpoints
    """
    enable_callbacks: bool = True
    enable_pause_check: bool = True
    auto_checkpoint: bool = False
    checkpoint_interval: int = 300  # 5 minutes


class PhaseExecutionManager:
    """
    Manages the execution lifecycle of a phase.

    Provides a unified interface for:
    - Invoking callbacks at appropriate times
    - Logging events to database
    - Handling pause/cancel requests
    - Managing checkpoints

    File tracking is handled by DAGTracker → FileRepository.
    DAG node management is handled by DAGTracker via callbacks.

    Can be used as a context manager for automatic cleanup.
    """

    def __init__(
        self,
        context: 'PhaseContext',
        phase: 'Phase',
        config: Optional[PhaseExecutionConfig] = None,
    ):
        """
        Initialize the execution manager.

        Args:
            context: The phase context
            phase: The phase being executed
            config: Optional execution configuration
        """
        self.context = context
        self.phase = phase
        self.config = config or PhaseExecutionConfig()

        # Timing
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        # State tracking
        self.current_step: Optional[int] = None
        self.events: List[Dict[str, Any]] = []
        self.is_cancelled = False

        # Database session (if available)
        self._db_session = None
        self._workflow_repo = None
        self._event_repo = None

        # Event capture manager
        self._event_capture: Optional['EventCaptureManager'] = None

        # Extract database objects from context if available
        self._setup_database()
        self._setup_event_capture()

    def _setup_database(self) -> None:
        """Set up database connections from context."""
        shared = self.context.shared_state or {}

        # Check for database session in shared state
        self._db_session = shared.get('_db_session')
        self._workflow_repo = shared.get('_workflow_repo')
        self._event_repo = shared.get('_event_repo')

    def _setup_event_capture(self) -> None:
        """
        Set up AG2 event capture for this phase execution.
        Creates EventCaptureManager and installs AG2 hooks if not already installed.
        """
        shared = self.context.shared_state or {}

        # Check if DB session is available for event capture
        if not self._db_session:
            return

        try:
            from cmbagent.execution.event_capture import EventCaptureManager, set_event_captor
            from cmbagent.execution.ag2_hooks import install_ag2_hooks

            # Create event capture manager
            self._event_capture = EventCaptureManager(
                db_session=self._db_session,
                run_id=self.context.run_id,
                session_id=shared.get('_session_id', 'unknown'),
                enabled=True,
                websocket=None  # TODO: Add websocket if available in context
            )

            # Set context for this phase (node_id managed by DAGTracker)
            self._event_capture.set_context(
                node_id=None,
                step_id=None
            )

            # Set as global event captor
            set_event_captor(self._event_capture)

            # Install AG2 hooks (idempotent - safe to call multiple times)
            install_ag2_hooks()

            logger.info("Event capture initialized for %s", self.phase.phase_type)

        except Exception as e:
            logger.error("Failed to setup event capture: %s", e)
            self._event_capture = None

    def _update_event_capture_context(self, step_id: Optional[str]) -> None:
        """
        Update event capture context for current step.

        Args:
            step_id: Current step ID (None for phase-level events)
        """
        if self._event_capture:
            self._event_capture.set_context(
                node_id=step_id,
                step_id=step_id
            )

    def _flush_event_capture(self) -> None:
        """Flush and clear event capture for this phase."""
        if self._event_capture:
            try:
                self._event_capture.flush()
                self._event_capture.close()

                # Clear global event captor (important: don't leak to next phase)
                from cmbagent.execution.event_capture import set_event_captor
                set_event_captor(None)

                logger.debug("Event capture flushed for %s", self.phase.phase_type)
            except Exception as e:
                logger.error("Error flushing event capture: %s", e)

    def get_managed_cmbagent_kwargs(self) -> Dict[str, Any]:
        """
        Get kwargs for creating a managed CMBAgent instance.

        Returns:
            Dictionary of kwargs to pass to CMBAgent.__init__
        """
        shared = self.context.shared_state or {}

        return {
            'managed_mode': True,
            'parent_session_id': shared.get('_session_id'),
            'parent_db_session': self._db_session,
        }

    # =========================================================================
    # Context Manager Interface
    # =========================================================================

    def __enter__(self) -> 'PhaseExecutionManager':
        """Start phase execution."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        End phase execution.

        If an exception occurred, logs it as a failure.
        Returns False to propagate exceptions.
        """
        if exc_type is not None:
            self.fail(str(exc_val), traceback.format_exc())
        return False  # Don't suppress exceptions

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def start(self) -> None:
        """
        Start phase execution.

        - Records start time
        - Invokes phase_change callback
        - Logs phase_start event
        """
        self.start_time = time.time()
        self.context.started_at = self.start_time

        # Invoke callback
        if self.config.enable_callbacks and self.context.callbacks:
            self.context.callbacks.invoke_phase_change(
                self.phase.phase_type,
                self.current_step
            )

        # Log event
        self._log_event(PhaseEventType.PHASE_START, {
            'phase_type': self.phase.phase_type,
            'phase_id': self.context.phase_id,
        })

        logger.info("=" * 60)
        logger.info("PHASE: %s", self.phase.display_name)
        logger.info("=" * 60)

    def complete(
        self,
        output_data: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict]] = None,
    ) -> 'PhaseResult':
        """
        Complete phase execution successfully.

        Args:
            output_data: Data to pass to next phase
            chat_history: Conversation history from agents

        Returns:
            PhaseResult with success status
        """
        from cmbagent.phases.base import PhaseResult, PhaseStatus

        self.end_time = time.time()
        self.context.completed_at = self.end_time

        if output_data:
            self.context.output_data = output_data

        # Log completion event
        execution_time = self.end_time - (self.start_time or self.end_time)
        self._log_event(PhaseEventType.PHASE_COMPLETE, {
            'phase_type': self.phase.phase_type,
            'execution_time': execution_time,
        })

        logger.info("=" * 60)
        logger.info("PHASE COMPLETE: %s", self.phase.display_name)
        logger.info("Execution time: %.2fs", execution_time)
        logger.info("=" * 60)

        result = PhaseResult(
            status=PhaseStatus.COMPLETED,
            context=self.context,
            chat_history=chat_history or [],
            timing={
                'start': self.start_time,
                'end': self.end_time,
                'total': execution_time,
            }
        )

        # Flush event capture before returning
        self._flush_event_capture()

        return result

    def fail(
        self,
        error: str,
        traceback_str: Optional[str] = None,
    ) -> 'PhaseResult':
        """
        Mark phase execution as failed.

        Args:
            error: Error message
            traceback_str: Optional full traceback

        Returns:
            PhaseResult with failed status
        """
        from cmbagent.phases.base import PhaseResult, PhaseStatus

        self.end_time = time.time()
        self.context.completed_at = self.end_time

        # Log failure event
        self._log_event(PhaseEventType.PHASE_FAILED, {
            'phase_type': self.phase.phase_type,
            'error': error,
            'traceback': traceback_str,
        })

        # Invoke workflow failed callback
        if self.config.enable_callbacks and self.context.callbacks:
            self.context.callbacks.invoke_workflow_failed(error, self.current_step)

        logger.error("=" * 60)
        logger.error("PHASE FAILED: %s", self.phase.display_name)
        logger.error("Error: %s", error)
        logger.error("=" * 60)

        result = PhaseResult(
            status=PhaseStatus.FAILED,
            context=self.context,
            error=error,
            timing={
                'start': self.start_time,
                'end': self.end_time,
                'total': (self.end_time or 0) - (self.start_time or 0),
            }
        )

        # Flush event capture before returning
        self._flush_event_capture()

        return result

    # =========================================================================
    # Step Management (for multi-step phases like Control)
    # =========================================================================

    def start_step(self, step_number: int, description: str = "") -> None:
        """
        Start a new step within the phase.

        Args:
            step_number: Step number (1-indexed)
            description: Human-readable step description
        """
        from cmbagent.callbacks import StepInfo, StepStatus

        self.current_step = step_number

        # Invoke callback (DAGTracker handles node updates via callback chain)
        if self.config.enable_callbacks and self.context.callbacks:
            self.context.callbacks.invoke_phase_change(
                self.phase.phase_type,
                step_number
            )

            step_info = StepInfo(
                step_number=step_number,
                goal=description,
                description=description,
                status=StepStatus.RUNNING,
                started_at=time.time()
            )
            self.context.callbacks.invoke_step_start(step_info)

        # Log event
        self._log_event(PhaseEventType.STEP_START, {
            'step_number': step_number,
            'description': description,
        })

        # Update event capture context for this step
        self._update_event_capture_context(step_id=f"step_{step_number}")

        logger.info("--- Step %d: %s ---", step_number, description)

    def complete_step(
        self,
        step_number: int,
        summary: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Complete a step within the phase.

        Args:
            step_number: Step number that completed
            summary: Human-readable summary of what was done
            result: Optional result data
        """
        from cmbagent.callbacks import StepInfo, StepStatus

        # Invoke callback (DAGTracker handles node updates via callback chain)
        if self.config.enable_callbacks and self.context.callbacks:
            step_info = StepInfo(
                step_number=step_number,
                goal=summary or f"Step {step_number}",
                description=summary or f"Step {step_number}",
                status=StepStatus.COMPLETED,
                completed_at=time.time(),
                summary=summary,
                result=result
            )
            self.context.callbacks.invoke_step_complete(step_info)

        # Log event
        self._log_event(PhaseEventType.STEP_COMPLETE, {
            'step_number': step_number,
            'summary': summary,
        })

        logger.info("--- Step %d Complete ---", step_number)

    def fail_step(
        self,
        step_number: int,
        error: str
    ) -> None:
        """
        Mark a step as failed.

        Args:
            step_number: Step number that failed
            error: Error message
        """
        from cmbagent.callbacks import StepInfo, StepStatus

        # Invoke callback (DAGTracker handles node updates via callback chain)
        if self.config.enable_callbacks and self.context.callbacks:
            step_info = StepInfo(
                step_number=step_number,
                goal=f"Step {step_number}",
                description=f"Step {step_number}",
                status=StepStatus.FAILED,
                completed_at=time.time(),
                error=error
            )
            self.context.callbacks.invoke_step_failed(step_info)

        # Log event
        self._log_event(PhaseEventType.STEP_FAILED, {
            'step_number': step_number,
            'error': error,
        })

    # =========================================================================
    # Event Logging
    # =========================================================================

    def log_agent_message(
        self,
        agent: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an agent message.

        Args:
            agent: Agent name
            role: Message role (user, assistant, etc.)
            content: Message content
            metadata: Optional additional metadata
        """
        if self.config.enable_callbacks and self.context.callbacks:
            self.context.callbacks.invoke_agent_message(
                agent, role, content, metadata or {}
            )

        self._log_event(PhaseEventType.AGENT_MESSAGE, {
            'agent': agent,
            'role': role,
            'content': content[:500] if content else "",
            'metadata': metadata,
        })

    def log_code_execution(
        self,
        agent: str,
        code: str,
        language: str,
        result: Optional[str] = None
    ) -> None:
        """
        Log code execution.

        Args:
            agent: Agent that executed the code
            code: The code that was executed
            language: Programming language
            result: Optional execution result
        """
        if self.config.enable_callbacks and self.context.callbacks:
            self.context.callbacks.invoke_code_execution(
                agent, code, language, result
            )

        self._log_event(PhaseEventType.CODE_EXECUTION, {
            'agent': agent,
            'language': language,
            'code': code[:1000] if code else "",
            'result': result[:500] if result else None,
        })

    def log_tool_call(
        self,
        agent: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Optional[Any] = None
    ) -> None:
        """
        Log a tool/function call.

        Args:
            agent: Agent that called the tool
            tool_name: Name of the tool
            arguments: Tool arguments
            result: Optional tool result
        """
        if self.config.enable_callbacks and self.context.callbacks:
            self.context.callbacks.invoke_tool_call(
                agent, tool_name, arguments, result
            )

        self._log_event(PhaseEventType.TOOL_CALL, {
            'agent': agent,
            'tool_name': tool_name,
            'arguments': str(arguments)[:500],
            'result': str(result)[:500] if result else None,
        })

    def log_event(
        self,
        event_type: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Log a custom event.

        Args:
            event_type: Custom event type name
            data: Event data
        """
        self._log_event(PhaseEventType.CUSTOM, {
            'custom_type': event_type,
            **data
        })

    def _log_event(
        self,
        event_type: PhaseEventType,
        data: Dict[str, Any]
    ) -> None:
        """Internal event logging to database and in-memory list."""
        event = {
            'type': event_type.value,
            'timestamp': time.time(),
            'phase_id': self.context.phase_id,
            'phase_type': self.phase.phase_type,
            'step': self.current_step,
            **data
        }

        self.events.append(event)

        # Persist to database if available
        if self._event_repo:
            try:
                self._event_repo.create_event(
                    run_id=self.context.run_id,
                    node_id=None,
                    event_type=event_type.value,
                    execution_order=len(self.events),
                    agent_name=data.get('agent'),
                    event_subtype=data.get('custom_type'),
                    status=data.get('status', 'info'),
                    meta=data
                )
            except Exception as e:
                logger.error("Event logging failed: %s", e)

    # =========================================================================
    # Pause/Cancel Handling
    # =========================================================================

    def check_should_continue(self) -> bool:
        """
        Check if phase execution should continue.

        Returns:
            True if execution should continue, False if cancelled
        """
        if not self.config.enable_pause_check:
            return True

        if self.context.callbacks:
            # Invoke pause check (may block if paused)
            self.context.callbacks.invoke_pause_check()

            # Check if should continue
            if not self.context.callbacks.check_should_continue():
                self.is_cancelled = True
                return False

        return True

    def raise_if_cancelled(self) -> None:
        """Raise an exception if workflow is cancelled."""
        if self.is_cancelled or not self.check_should_continue():
            raise WorkflowCancelledException("Workflow cancelled by user")

    # =========================================================================
    # Checkpoint Support
    # =========================================================================

    def save_checkpoint(
        self,
        checkpoint_id: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Save a checkpoint for recovery.

        Args:
            checkpoint_id: Unique identifier for this checkpoint
            data: Checkpoint data to save

        Returns:
            Path to saved checkpoint file
        """
        import pickle

        checkpoint_dir = os.path.join(self.context.work_dir, "checkpoints")
        os.makedirs(checkpoint_dir, exist_ok=True)

        checkpoint_path = os.path.join(
            checkpoint_dir,
            f"{self.phase.phase_type}_{checkpoint_id}.pkl"
        )

        checkpoint_data = {
            'phase_type': self.phase.phase_type,
            'phase_id': self.context.phase_id,
            'timestamp': time.time(),
            'step': self.current_step,
            'data': data,
        }

        with open(checkpoint_path, 'wb') as f:
            pickle.dump(checkpoint_data, f)

        self._log_event(PhaseEventType.CHECKPOINT, {
            'checkpoint_id': checkpoint_id,
            'path': checkpoint_path,
        })

        return checkpoint_path

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a checkpoint.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            Checkpoint data if found, None otherwise
        """
        import pickle

        checkpoint_path = os.path.join(
            self.context.work_dir,
            "checkpoints",
            f"{self.phase.phase_type}_{checkpoint_id}.pkl"
        )

        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, 'rb') as f:
                return pickle.load(f)

        return None


class WorkflowCancelledException(Exception):
    """Raised when workflow is cancelled by user."""
    pass


# =============================================================================
# Decorator for Easy Phase Wrapping
# =============================================================================

def managed_phase_execution(func: Callable) -> Callable:
    """
    Decorator that wraps phase execute method with PhaseExecutionManager.

    Usage:
        class MyPhase(Phase):
            @managed_phase_execution
            async def execute(self, context: PhaseContext) -> PhaseResult:
                # Your logic here - manager is available as self._manager
                return self._manager.complete({'output': 'data'})
    """
    import functools
    import asyncio

    @functools.wraps(func)
    async def wrapper(self, context: 'PhaseContext') -> 'PhaseResult':
        manager = PhaseExecutionManager(context, self)
        self._manager = manager

        try:
            manager.start()
            result = await func(self, context)
            return result
        except WorkflowCancelledException:
            return manager.fail("Workflow cancelled by user")
        except Exception as e:
            return manager.fail(str(e), traceback.format_exc())

    return wrapper
