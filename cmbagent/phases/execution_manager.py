"""
Phase Execution Manager - Generalized execution infrastructure for phases.

This module provides a unified execution manager that handles all cross-cutting
concerns for phase execution:

1. **Callbacks**: Automatic invocation of workflow callbacks
2. **Database Logging**: WorkflowRun creation, event tracking
3. **DAG Management**: Node creation and status updates
4. **Output Tracking**: File tracking and output collection
5. **Pause/Cancel**: Workflow control checks
6. **Error Handling**: Consistent error handling and recovery
7. **Timing**: Automatic timing of phase execution

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
       - DAG node updates
       - File tracking
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
    FILE_CREATED = "file_created"
    CHECKPOINT = "checkpoint"
    CUSTOM = "custom"


@dataclass
class PhaseExecutionConfig:
    """
    Configuration for phase execution behavior.
    
    Attributes:
        enable_callbacks: Whether to invoke workflow callbacks
        enable_database: Whether to log to database
        enable_dag: Whether to update DAG nodes
        enable_file_tracking: Whether to track output files
        enable_pause_check: Whether to check for pause/cancel
        auto_checkpoint: Whether to auto-save checkpoints
        checkpoint_interval: Seconds between auto-checkpoints
    """
    enable_callbacks: bool = True
    enable_database: bool = True
    enable_dag: bool = True
    enable_file_tracking: bool = True
    enable_pause_check: bool = True
    auto_checkpoint: bool = False
    checkpoint_interval: int = 300  # 5 minutes


class PhaseExecutionManager:
    """
    Manages the execution lifecycle of a phase.
    
    Provides a unified interface for:
    - Invoking callbacks at appropriate times
    - Logging events to database
    - Updating DAG node status
    - Tracking output files
    - Handling pause/cancel requests
    - Managing checkpoints
    
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
        self.files_created: List[str] = []
        self.is_cancelled = False
        
        # Database session (if available)
        self._db_session = None
        self._workflow_repo = None
        self._event_repo = None
        self._dag_repo = None
        
        # DAG node tracking
        self._current_dag_node_id: Optional[str] = None
        self._step_dag_node_ids: Dict[int, str] = {}  # step_number -> node_id

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
        self._dag_repo = shared.get('_dag_repo')

    def _setup_event_capture(self) -> None:
        """
        Set up AG2 event capture for this phase execution.
        Creates EventCaptureManager and installs AG2 hooks if not already installed.
        """
        shared = self.context.shared_state or {}

        # Check if event capture is disabled
        if not self.config.enable_database or not self._db_session:
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

            # Set context for this phase
            self._event_capture.set_context(
                node_id=self._current_dag_node_id,
                step_id=None  # Will be set per-step
            )

            # Set as global event captor
            set_event_captor(self._event_capture)

            # Install AG2 hooks (idempotent - safe to call multiple times)
            install_ag2_hooks()

            print(f"[PhaseExecutionManager] Event capture initialized for {self.phase.phase_type}")

        except Exception as e:
            print(f"[PhaseExecutionManager] Failed to setup event capture: {e}")
            self._event_capture = None

    def _update_event_capture_context(self, step_id: Optional[str]) -> None:
        """
        Update event capture context for current step.

        Args:
            step_id: Current step ID (None for phase-level events)
        """
        if self._event_capture:
            node_id = self._step_dag_node_ids.get(self.current_step) if self.current_step else self._current_dag_node_id
            self._event_capture.set_context(
                node_id=node_id,
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

                print(f"[PhaseExecutionManager] Event capture flushed for {self.phase.phase_type}")
            except Exception as e:
                print(f"[PhaseExecutionManager] Error flushing event capture: {e}")

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
        - Creates DAG node if enabled
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
        
        # Create DAG node with rich metadata for UI display
        if self.config.enable_dag and self._dag_repo:
            try:
                # Build metadata for UI display
                phase_label = f"{self.phase.display_name} Phase"

                # Create phase-specific descriptions
                phase_descriptions = {
                    "planning": "Analyzing task and creating execution plan",
                    "control": "Executing planned steps with agent coordination",
                    "hitl_planning": "Planning with human review and approval",
                    "hitl_control": "Executing steps with human-in-the-loop oversight",
                    "hitl_checkpoint": "Waiting for human approval to proceed",
                    "one_shot": "Single agent execution of task",
                    "idea_generation": "Generating and exploring creative ideas",
                    "copilot": "Interactive copilot session"
                }

                phase_description = phase_descriptions.get(
                    self.phase.phase_type,
                    f"Executing {self.phase.display_name} phase"
                )

                # Truncate task for display
                task_display = self.context.task
                if len(task_display) > 100:
                    task_display = task_display[:100] + "..."

                node = self._dag_repo.create_node(
                    run_id=self.context.run_id,
                    node_type=self.phase.phase_type,
                    agent=self.phase.phase_type,
                    order_index=0,
                    status="running",
                    meta={
                        "label": phase_label,
                        "description": phase_description,
                        "task": task_display,
                        "step_number": 0,
                        "phase_name": self.phase.display_name,
                        "phase_id": self.context.phase_id
                    }
                )
                self._current_dag_node_id = node.id
            except Exception as e:
                print(f"[PhaseExecutionManager] DAG node creation failed: {e}")
        
        # Log event
        self._log_event(PhaseEventType.PHASE_START, {
            'phase_type': self.phase.phase_type,
            'phase_id': self.context.phase_id,
        })
        
        print(f"\n{'=' * 60}")
        print(f"PHASE: {self.phase.display_name}")
        print(f"{'=' * 60}\n")

    def update_current_node_metadata(self, metadata_update: Dict[str, Any]) -> None:
        """
        Update the metadata of the current phase's DAG node.

        Args:
            metadata_update: Dictionary of metadata fields to add/update.
                            Will be merged with existing metadata.
        """
        if self.config.enable_dag and self._dag_repo and self._current_dag_node_id:
            try:
                self._dag_repo.update_node_status(
                    node_id=self._current_dag_node_id,
                    status="running",  # Keep current status
                    meta=metadata_update
                )
                print(f"[PhaseExecutionManager] Updated phase node metadata with: {list(metadata_update.keys())}")
            except Exception as e:
                print(f"[PhaseExecutionManager] Failed to update phase node metadata: {e}")

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
        
        # Update DAG node
        if self.config.enable_dag and self._dag_repo and self._current_dag_node_id:
            try:
                self._dag_repo.update_node_status(
                    self._current_dag_node_id,
                    status="completed"
                )
            except Exception as e:
                print(f"[PhaseExecutionManager] DAG node update failed: {e}")
        
        # Track files
        if self.config.enable_file_tracking:
            self._track_output_files()
        
        # Log completion event
        execution_time = self.end_time - (self.start_time or self.end_time)
        self._log_event(PhaseEventType.PHASE_COMPLETE, {
            'phase_type': self.phase.phase_type,
            'execution_time': execution_time,
            'files_created': self.files_created,
        })
        
        print(f"\n{'=' * 60}")
        print(f"PHASE COMPLETE: {self.phase.display_name}")
        print(f"Execution time: {execution_time:.2f}s")
        print(f"{'=' * 60}\n")

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
        
        # Update DAG node
        if self.config.enable_dag and self._dag_repo and self._current_dag_node_id:
            try:
                self._dag_repo.update_node_status(
                    self._current_dag_node_id,
                    status="failed"
                )
            except Exception as e:
                print(f"[PhaseExecutionManager] DAG node update failed: {e}")
        
        # Log failure event
        self._log_event(PhaseEventType.PHASE_FAILED, {
            'phase_type': self.phase.phase_type,
            'error': error,
            'traceback': traceback_str,
        })
        
        # Invoke workflow failed callback
        if self.config.enable_callbacks and self.context.callbacks:
            self.context.callbacks.invoke_workflow_failed(error, self.current_step)
        
        print(f"\n{'=' * 60}")
        print(f"PHASE FAILED: {self.phase.display_name}")
        print(f"Error: {error}")
        print(f"{'=' * 60}\n")

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

        # Update or create DAG node for this step
        if self.config.enable_dag and self._dag_repo:
            try:
                # Check if node already exists from add_plan_step_nodes()
                existing_node_id = self._step_dag_node_ids.get(step_number)

                if existing_node_id:
                    # Update existing node to running status
                    # Preserve existing metadata (agent, label, description from planning)
                    self._dag_repo.update_node_status(
                        existing_node_id,
                        status="running",
                        meta={
                            "started_at": time.time(),
                            "phase_type": self.phase.phase_type,
                            "phase_name": self.phase.display_name
                        }
                    )
                    print(f"[PhaseExecutionManager] Updated existing DAG node for step {step_number}")
                else:
                    # Create new node if it doesn't exist (fallback for phases without planning)
                    # Build step label
                    step_label = f"Step {step_number}"
                    if description:
                        truncated_desc = description[:50] + "..." if len(description) > 50 else description
                        step_label = f"{step_label}: {truncated_desc}"

                    # Prepare task display (for consistency with phase nodes)
                    task_display = description or self.context.task
                    if len(task_display) > 200:
                        task_display = task_display[:200] + "..."

                    # Use generic step identifier for consistency
                    node = self._dag_repo.create_node(
                        run_id=self.context.run_id,
                        node_type="agent",
                        agent=f"step_{step_number}",  # Generic identifier for step nodes
                        order_index=step_number,
                        status="running",
                        meta={
                            "step_number": step_number,
                            "description": description,
                            "label": step_label,
                            "task": task_display,
                            "phase_type": self.phase.phase_type,
                            "phase_name": self.phase.display_name,
                            "started_at": time.time()
                        }
                    )
                    self._step_dag_node_ids[step_number] = node.id
                    print(f"[PhaseExecutionManager] Created new DAG node for step {step_number}")
            except Exception as e:
                print(f"[PhaseExecutionManager] Step DAG node update/creation failed: {e}")

        # Invoke callback
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

        print(f"\n--- Step {step_number}: {description} ---\n")
    
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

        # Update DAG node status for this step
        if self.config.enable_dag and self._dag_repo:
            step_node_id = self._step_dag_node_ids.get(step_number)
            if step_node_id:
                try:
                    # Merge summary and completion time with existing metadata
                    meta_update = {
                        "completed_at": time.time()
                    }
                    if summary:
                        meta_update["summary"] = summary

                    self._dag_repo.update_node_status(
                        step_node_id,
                        status="completed",
                        meta=meta_update
                    )
                except Exception as e:
                    print(f"[PhaseExecutionManager] Step DAG node update failed: {e}")

        # Invoke callback
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

        print(f"\n--- Step {step_number} Complete ---\n")
    
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

        # Update DAG node status for this step
        if self.config.enable_dag and self._dag_repo:
            step_node_id = self._step_dag_node_ids.get(step_number)
            if step_node_id:
                try:
                    # Merge error and failed time with existing metadata
                    self._dag_repo.update_node_status(
                        step_node_id,
                        status="failed",
                        meta={
                            "error": error,
                            "failed_at": time.time()
                        }
                    )
                except Exception as e:
                    print(f"[PhaseExecutionManager] Step DAG node update failed: {e}")

        # Invoke callback
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

    def add_plan_step_nodes(
        self,
        plan_steps: List[Dict[str, Any]],
        source_node: Optional[str] = None
    ) -> None:
        """
        Add DAG nodes for plan steps after planning completes.

        This method creates DAG nodes for each step in a plan, enabling
        dynamic DAG expansion after planning phase generates the plan.

        Args:
            plan_steps: List of step dictionaries with keys like:
                - sub_task or task: Step description
                - sub_task_agent or agent: Agent to execute
                - goal, summary, bullet_points: Optional metadata
            source_node: The node ID (UUID) that these steps connect from.
                        If None, steps won't be connected to a source node.
                        Pass manager._current_dag_node_id to connect to the planning phase.
        """
        if not plan_steps:
            return

        print(f"[PhaseExecutionManager] Adding {len(plan_steps)} plan step nodes to DAG")

        # Create DAG nodes in database
        if self.config.enable_dag and self._dag_repo:
            try:
                previous_node_id = None

                for i, step in enumerate(plan_steps, 1):
                    # Extract step info from various formats (handles both standard and HITL formats)
                    description = step.get('sub_task') or step.get('task') or step.get('description') or f"Step {i}"
                    step_agent = step.get('sub_task_agent') or step.get('agent') or 'engineer'
                    goal = step.get('goal') or step.get('summary') or description
                    summary = step.get('summary', '')
                    bullet_points = step.get('bullet_points', [])

                    # Create truncated label
                    label = f"Step {i}: {description[:50]}..." if len(description) > 50 else f"Step {i}: {description}"

                    # Create the node with complete metadata
                    node = self._dag_repo.create_node(
                        run_id=self.context.run_id,
                        node_type="agent",
                        agent=step_agent,  # Use actual agent name for better display
                        order_index=i,
                        status="pending",
                        meta={
                            "step_number": i,
                            "description": description,
                            "task": description,  # Duplicate for compatibility
                            "goal": goal,
                            "label": label,
                            "summary": summary,
                            "bullet_points": bullet_points,
                            "executing_agent": step_agent,
                            "agent": step_agent,  # Duplicate for compatibility
                        }
                    )
                    self._step_dag_node_ids[i] = node.id
                    print(f"[PhaseExecutionManager] Created step {i} node: {node.id}, agent: {step_agent}, desc: {description[:50]}...")

                    # Create edge from previous node
                    if previous_node_id:
                        try:
                            self._dag_repo.create_edge(
                                from_node_id=previous_node_id,
                                to_node_id=node.id,
                                dependency_type="sequential"
                            )
                        except Exception as e:
                            print(f"[PhaseExecutionManager] Edge creation failed: {e}")
                    elif i == 1 and source_node:
                        # First step connects from source node (e.g., planning phase)
                        # source_node is already the UUID, use it directly
                        try:
                            self._dag_repo.create_edge(
                                from_node_id=source_node,
                                to_node_id=node.id,
                                dependency_type="sequential"
                            )
                            print(f"[PhaseExecutionManager] Connected first step to source node")
                        except Exception as e:
                            print(f"[PhaseExecutionManager] Source edge creation failed: {e}")
                            import traceback
                            traceback.print_exc()

                    previous_node_id = node.id

                # Create terminator node
                terminator = self._dag_repo.create_node(
                    run_id=self.context.run_id,
                    node_type="terminator",
                    agent="system",
                    order_index=len(plan_steps) + 1,
                    status="pending",
                    meta={
                        "label": "Completion",
                        "description": "Workflow completed"
                    }
                )

                # Connect last step to terminator
                if previous_node_id:
                    try:
                        self._dag_repo.create_edge(
                            from_node_id=previous_node_id,
                            to_node_id=terminator.id,
                            dependency_type="sequential"
                        )
                    except Exception as e:
                        print(f"[PhaseExecutionManager] Terminator edge creation failed: {e}")

                print(f"[PhaseExecutionManager] Created {len(plan_steps)} step nodes + terminator in database")

            except Exception as e:
                print(f"[PhaseExecutionManager] Plan step nodes creation failed: {e}")
                import traceback
                traceback.print_exc()

        # NOTE: Do NOT call invoke_planning_complete here!
        # The phase itself (planning.py or hitl_planning.py) is responsible for
        # calling invoke_planning_complete at the correct time after plan approval.

        # Log event
        self._log_event(PhaseEventType.PLAN_GENERATED, {
            'num_steps': len(plan_steps),
            'steps': [
                {
                    'step_number': i + 1,
                    'agent': s.get('sub_task_agent') or s.get('agent', 'engineer'),
                    'description': (s.get('sub_task') or s.get('task', ''))[:100]
                }
                for i, s in enumerate(plan_steps)
            ]
        })

    def create_redo_branch(
        self,
        step_number: int,
        redo_number: int,
        hypothesis: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a redo branch for a failed step.

        Args:
            step_number: Step being redone
            redo_number: Redo attempt number (1, 2, 3...)
            hypothesis: Hypothesis for why this redo will succeed

        Returns:
            Branch node ID if created, None on error
        """
        if not self.config.enable_dag or not self._dag_repo:
            return None

        try:
            step_node_id = self._step_dag_node_ids.get(step_number)
            if not step_node_id:
                print(f"[PhaseExecutionManager] Cannot create redo branch: step {step_number} node not found")
                return None

            # Create branch node
            branch_name = f"redo_{redo_number}"
            branch_node = self._dag_repo.create_branch_node(
                source_node_id=step_node_id,
                branch_name=branch_name,
                hypothesis=hypothesis or f"Retry attempt {redo_number}"
            )

            print(f"[PhaseExecutionManager] Created redo branch: step {step_number}, redo {redo_number}")
            return branch_node.id

        except Exception as e:
            print(f"[PhaseExecutionManager] Failed to create redo branch: {e}")
            return None

    def record_sub_agent_call(
        self,
        step_number: int,
        agent_name: str,
        action: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Record a sub-agent call within a step.

        Args:
            step_number: Current step number
            agent_name: Name of sub-agent
            action: Action being performed
            metadata: Additional metadata

        Returns:
            Sub-node ID if created, None on error
        """
        if not self.config.enable_dag or not self._dag_repo:
            return None

        try:
            step_node_id = self._step_dag_node_ids.get(step_number)
            if not step_node_id:
                return None

            # Create sub-node
            sub_node = self._dag_repo.create_sub_node(
                parent_node_id=step_node_id,
                node_type="sub_agent",
                agent=agent_name,
                status="running",
                meta={
                    "action": action,
                    **(metadata or {})
                }
            )

            return sub_node.id

        except Exception as e:
            print(f"[PhaseExecutionManager] Failed to record sub-agent call: {e}")
            return None

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
        if self.config.enable_database and self._event_repo:
            try:
                self._event_repo.create_event(
                    run_id=self.context.run_id,
                    node_id=self._current_dag_node_id,
                    event_type=event_type.value,
                    execution_order=len(self.events),
                    agent_name=data.get('agent'),
                    event_subtype=data.get('custom_type'),
                    status=data.get('status', 'info'),
                    meta=data
                )
            except Exception as e:
                print(f"[PhaseExecutionManager] Event logging failed: {e}")
    
    # =========================================================================
    # File Tracking
    # =========================================================================
    
    def track_file(self, file_path: str) -> None:
        """
        Track a file created during phase execution.
        
        Args:
            file_path: Path to the created file
        """
        if os.path.exists(file_path):
            self.files_created.append(file_path)
    
    def _track_output_files(self) -> None:
        """Scan work directory for new files created during phase."""
        if not os.path.exists(self.context.work_dir):
            return
        
        for root, _, files in os.walk(self.context.work_dir):
            for f in files:
                file_path = os.path.join(root, f)
                if file_path not in self.files_created:
                    # Check if file was created after phase started
                    try:
                        mtime = os.path.getmtime(file_path)
                        if self.start_time and mtime >= self.start_time:
                            self.files_created.append(file_path)
                    except OSError:
                        pass
    
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
