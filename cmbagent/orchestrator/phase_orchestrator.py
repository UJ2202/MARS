"""
Phase Orchestrator - Execute phases dynamically from tool calls.

This module provides the actual execution logic for phases when they are
invoked as tools by agents. Unlike the stub implementations in phase_tools.py,
this actually executes the phases.
"""

import asyncio
import uuid
import time
import json
import traceback
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

from cmbagent.orchestrator.config import OrchestratorConfig
from cmbagent.orchestrator.dag_tracker import DAGTracker, PhaseNode
from cmbagent.orchestrator.context_pipeline import ContextPipeline
from cmbagent.orchestrator.logger import OrchestratorLogger
from cmbagent.orchestrator.metrics import MetricsCollector


@dataclass
class PhaseExecutionRequest:
    """Request to execute a phase."""
    phase_type: str
    task: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    input_data: Dict[str, Any] = field(default_factory=dict)
    parent_phase_id: Optional[str] = None
    priority: int = 0


@dataclass
class PhaseExecutionResult:
    """Result of phase execution."""
    phase_type: str
    phase_id: str
    status: str  # success, failed, skipped
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration: float = 0.0
    chat_history: List[Dict] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps({
            "phase_type": self.phase_type,
            "phase_id": self.phase_id,
            "status": self.status,
            "output": self.output_data,
            "error": self.error,
            "duration": self.duration,
        })


class PhaseOrchestrator:
    """
    Orchestrator for executing phases dynamically.

    This is the bridge between agent tool calls and actual phase execution.
    When an agent calls invoke_planning_phase(), this orchestrator:
    1. Creates the phase instance
    2. Builds the execution context
    3. Executes the phase
    4. Returns results to the agent

    Features:
    - DAG tracking for phase dependencies
    - Comprehensive logging
    - Metrics collection
    - Context passing between phases
    - Error recovery and retry logic
    """

    def __init__(
        self,
        config: OrchestratorConfig = None,
        api_keys: Dict[str, str] = None,
        work_dir: str = ".",
        approval_manager=None,
    ):
        self.config = config or OrchestratorConfig()
        self._api_keys = api_keys or {}
        self._work_dir = work_dir
        self._approval_manager = approval_manager

        # Resolve orchestrator directories relative to work_dir
        self.config.resolve_dirs(work_dir)

        # Initialize components based on config
        self._dag_tracker = DAGTracker() if self.config.enable_dag_tracking else None
        # Wire log file from config's log_dir
        _log_file = None
        if self.config.enable_logging and self.config.log_dir:
            _log_file = str(self.config.log_dir / f"orchestrator_{uuid.uuid4().hex[:12]}.log")
        self._logger = OrchestratorLogger(self.config, log_file=_log_file) if self.config.enable_logging else None
        self._metrics = MetricsCollector() if self.config.enable_metrics else None
        self._context_pipeline = ContextPipeline()

        # Execution state
        self._execution_id = uuid.uuid4().hex[:12]
        self._phases_executed: List[PhaseExecutionResult] = []
        self._shared_context: Dict[str, Any] = {}
        self._previous_output: Dict[str, Any] = {}

    async def execute_phase(
        self,
        request: PhaseExecutionRequest,
    ) -> PhaseExecutionResult:
        """
        Execute a single phase.

        Args:
            request: Phase execution request

        Returns:
            PhaseExecutionResult with output or error
        """
        from cmbagent.phases import PhaseRegistry, PhaseContext, PhaseStatus

        phase_id = f"{request.phase_type}_{uuid.uuid4().hex[:6]}"
        start_time = time.time()

        # Log start
        if self._logger:
            self._logger.log_phase_start(phase_id, request.phase_type, request.task)

        # Track in DAG
        if self._dag_tracker:
            node = PhaseNode(
                id=phase_id,
                phase_type=request.phase_type,
                status="running",
            )
            if request.parent_phase_id:
                self._dag_tracker.add_dependency(request.parent_phase_id, phase_id)
            self._dag_tracker.add_node(node)

        try:
            # Get phase class
            phase_class = PhaseRegistry.get(request.phase_type)
            if phase_class is None:
                raise ValueError(f"Unknown phase type: {request.phase_type}")

            # Build phase config
            config_class = getattr(phase_class, 'config_class', None)
            if config_class:
                phase_config = config_class(**request.config)
            else:
                phase_config = request.config

            # Create phase instance
            phase = phase_class(phase_config)

            # Build context
            context = PhaseContext(
                workflow_id=f"orchestrator_{self._execution_id}",
                run_id=self._execution_id,
                phase_id=phase_id,
                task=request.task,
                work_dir=self._work_dir,
                shared_state=self._shared_context.copy(),
                input_data=self._merge_input_data(request.input_data),
                api_keys=self._api_keys,
            )

            # Inject approval manager
            if self._approval_manager:
                context.shared_state['_approval_manager'] = self._approval_manager

            # Execute phase
            result = await phase.execute(context)

            # Calculate duration
            duration = time.time() - start_time

            # Update shared context with output
            if result.succeeded() and result.context.output_data:
                self._previous_output = result.context.output_data
                self._shared_context.update({
                    f"{request.phase_type}_output": result.context.output_data
                })

            # Build execution result
            exec_result = PhaseExecutionResult(
                phase_type=request.phase_type,
                phase_id=phase_id,
                status="success" if result.succeeded() else "failed",
                output_data=result.context.output_data if result.succeeded() else {},
                error=result.error if not result.succeeded() else None,
                duration=duration,
                chat_history=result.chat_history,
            )

            # Track metrics
            if self._metrics:
                self._metrics.record_phase_execution(
                    phase_type=request.phase_type,
                    duration=duration,
                    success=result.succeeded(),
                )

            # Update DAG
            if self._dag_tracker:
                self._dag_tracker.update_node_status(
                    phase_id,
                    "completed" if result.succeeded() else "failed"
                )

            # Log completion
            if self._logger:
                self._logger.log_phase_complete(phase_id, exec_result.status, duration)

            # Store result
            self._phases_executed.append(exec_result)

            return exec_result

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            stack_trace = traceback.format_exc()

            # Log error
            if self._logger:
                self._logger.log_phase_error(phase_id, error_msg, stack_trace)

            # Update DAG
            if self._dag_tracker:
                self._dag_tracker.update_node_status(phase_id, "failed")

            # Track metrics
            if self._metrics:
                self._metrics.record_phase_execution(
                    phase_type=request.phase_type,
                    duration=duration,
                    success=False,
                )

            exec_result = PhaseExecutionResult(
                phase_type=request.phase_type,
                phase_id=phase_id,
                status="failed",
                error=error_msg,
                duration=duration,
            )
            self._phases_executed.append(exec_result)

            # Retry if configured
            if self.config.max_retries > 0:
                return await self._retry_phase(request, exec_result)

            return exec_result

    async def _retry_phase(
        self,
        request: PhaseExecutionRequest,
        failed_result: PhaseExecutionResult,
        attempt: int = 1,
    ) -> PhaseExecutionResult:
        """Retry a failed phase execution."""
        if attempt > self.config.max_retries:
            return failed_result

        if self._logger:
            self._logger.log_event(
                f"Retrying phase {request.phase_type}, attempt {attempt}/{self.config.max_retries}"
            )

        # Wait before retry
        await asyncio.sleep(self.config.retry_delay)

        # Create new request with same params
        return await self.execute_phase(request)

    def _merge_input_data(self, request_input: Dict[str, Any]) -> Dict[str, Any]:
        """Merge request input with previous phase output."""
        merged = {}

        # Add previous output if context passing is enabled
        if self.config.pass_context_by_default and self._previous_output:
            merged['$previous'] = self._previous_output

        # Add request-specific input
        merged.update(request_input)

        return merged

    async def execute_chain(
        self,
        phases: List[Dict[str, Any]],
        pass_context: bool = True,
    ) -> List[PhaseExecutionResult]:
        """
        Execute a chain of phases in sequence.

        Args:
            phases: List of phase definitions
            pass_context: Whether to pass output between phases

        Returns:
            List of execution results
        """
        results = []
        previous_result = None

        for phase_def in phases:
            phase_type = phase_def.get('phase', phase_def.get('type'))
            task = phase_def.get('task', phase_def.get('query', ''))
            config = phase_def.get('config', {})

            # Handle $previous placeholder
            if pass_context and previous_result:
                task = self._substitute_previous(task, previous_result.output_data)
                config = self._substitute_previous_in_dict(config, previous_result.output_data)

            request = PhaseExecutionRequest(
                phase_type=phase_type,
                task=task,
                config=config,
                parent_phase_id=previous_result.phase_id if previous_result else None,
            )

            result = await self.execute_phase(request)
            results.append(result)
            previous_result = result

            # Stop chain on failure
            if result.status == "failed":
                if self._logger:
                    self._logger.log_event(f"Chain stopped due to failed phase: {phase_type}")
                break

        return results

    def _substitute_previous(self, value: Any, previous: Dict) -> Any:
        """Substitute $previous placeholder with actual value."""
        if isinstance(value, str):
            if value == "$previous":
                return previous
            elif "$previous" in value:
                return value.replace("$previous", json.dumps(previous))
        return value

    def _substitute_previous_in_dict(self, d: Dict, previous: Dict) -> Dict:
        """Recursively substitute $previous in a dictionary."""
        result = {}
        for k, v in d.items():
            if isinstance(v, dict):
                result[k] = self._substitute_previous_in_dict(v, previous)
            elif isinstance(v, str):
                result[k] = self._substitute_previous(v, previous)
            else:
                result[k] = v
        return result

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of all executions."""
        return {
            "execution_id": self._execution_id,
            "phases_executed": len(self._phases_executed),
            "results": [r.to_json() for r in self._phases_executed],
            "shared_context_keys": list(self._shared_context.keys()),
            "dag": self._dag_tracker.to_dict() if self._dag_tracker else None,
            "metrics": self._metrics.get_summary() if self._metrics else None,
        }


# Tool functions that use PhaseOrchestrator
# These replace the stub implementations in phase_tools.py

_global_orchestrator: Optional[PhaseOrchestrator] = None


def set_global_orchestrator(orchestrator: PhaseOrchestrator) -> None:
    """Set the global phase orchestrator for tool functions."""
    global _global_orchestrator
    _global_orchestrator = orchestrator


def get_global_orchestrator() -> Optional[PhaseOrchestrator]:
    """Get the global phase orchestrator."""
    return _global_orchestrator


async def execute_planning_phase(
    task: str,
    max_steps: int = 5,
    n_reviews: int = 1,
) -> str:
    """
    Execute the planning phase to create a structured plan.

    Args:
        task: Task to create a plan for
        max_steps: Maximum steps in the plan
        n_reviews: Number of plan review iterations

    Returns:
        JSON string with the generated plan
    """
    orchestrator = get_global_orchestrator()
    if not orchestrator:
        return json.dumps({"error": "No orchestrator configured"})

    request = PhaseExecutionRequest(
        phase_type="planning",
        task=task,
        config={
            "max_plan_steps": max_steps,
            "n_plan_reviews": n_reviews,
        }
    )

    result = await orchestrator.execute_phase(request)
    return result.to_json()


async def execute_control_phase(
    plan: Dict[str, Any],
    mode: str = "sequential",
) -> str:
    """
    Execute the control phase to carry out a plan.

    Args:
        plan: The plan to execute
        mode: Execution mode (sequential/parallel)

    Returns:
        JSON string with execution results
    """
    orchestrator = get_global_orchestrator()
    if not orchestrator:
        return json.dumps({"error": "No orchestrator configured"})

    request = PhaseExecutionRequest(
        phase_type="control",
        task=plan.get('goal', ''),
        config={"execution_mode": mode},
        input_data={"plan": plan},
    )

    result = await orchestrator.execute_phase(request)
    return result.to_json()


async def execute_one_shot_phase(
    task: str,
    agent: str = "engineer",
    max_rounds: int = 50,
) -> str:
    """
    Execute a one-shot task without planning.

    Args:
        task: Task to execute
        agent: Agent to use
        max_rounds: Maximum conversation rounds

    Returns:
        JSON string with result
    """
    orchestrator = get_global_orchestrator()
    if not orchestrator:
        return json.dumps({"error": "No orchestrator configured"})

    request = PhaseExecutionRequest(
        phase_type="one_shot",
        task=task,
        config={
            "agent": agent,
            "max_rounds": max_rounds,
        }
    )

    result = await orchestrator.execute_phase(request)
    return result.to_json()


async def execute_hitl_planning_phase(
    task: str,
    max_iterations: int = 3,
    allow_modification: bool = True,
) -> str:
    """
    Execute interactive planning with human feedback.

    Args:
        task: Task to plan
        max_iterations: Maximum human feedback iterations
        allow_modification: Allow human to modify the plan

    Returns:
        JSON string with approved plan
    """
    orchestrator = get_global_orchestrator()
    if not orchestrator:
        return json.dumps({"error": "No orchestrator configured"})

    request = PhaseExecutionRequest(
        phase_type="hitl_planning",
        task=task,
        config={
            "max_human_iterations": max_iterations,
            "allow_plan_modification": allow_modification,
        }
    )

    result = await orchestrator.execute_phase(request)
    return result.to_json()


async def execute_hitl_control_phase(
    plan: Dict[str, Any],
    approval_mode: str = "after_step",
    allow_retry: bool = True,
) -> str:
    """
    Execute plan with human approval at each step.

    Args:
        plan: Plan to execute
        approval_mode: When to request approval (before_step, after_step, both)
        allow_retry: Allow retrying failed steps

    Returns:
        JSON string with execution results
    """
    orchestrator = get_global_orchestrator()
    if not orchestrator:
        return json.dumps({"error": "No orchestrator configured"})

    request = PhaseExecutionRequest(
        phase_type="hitl_control",
        task=plan.get('goal', ''),
        config={
            "approval_mode": approval_mode,
            "allow_step_retry": allow_retry,
        },
        input_data={"plan": plan},
    )

    result = await orchestrator.execute_phase(request)
    return result.to_json()


async def execute_idea_generation_phase(
    topic: str,
    n_ideas: int = 3,
    n_critiques: int = 1,
) -> str:
    """
    Execute idea generation and critique.

    Args:
        topic: Topic to generate ideas for
        n_ideas: Number of ideas to generate
        n_critiques: Number of critique rounds

    Returns:
        JSON string with ideas and critiques
    """
    orchestrator = get_global_orchestrator()
    if not orchestrator:
        return json.dumps({"error": "No orchestrator configured"})

    request = PhaseExecutionRequest(
        phase_type="idea_generation",
        task=topic,
        config={
            "n_ideas": n_ideas,
            "n_critiques": n_critiques,
        }
    )

    result = await orchestrator.execute_phase(request)
    return result.to_json()


async def chain_phases_executable(
    phases: List[Dict[str, Any]],
    pass_context: bool = True,
) -> str:
    """
    Chain multiple phases together.

    Args:
        phases: List of phase definitions
        pass_context: Pass output between phases

    Returns:
        JSON string with all results
    """
    orchestrator = get_global_orchestrator()
    if not orchestrator:
        return json.dumps({"error": "No orchestrator configured"})

    results = await orchestrator.execute_chain(phases, pass_context)

    return json.dumps({
        "status": "completed",
        "phases_executed": len(results),
        "results": [r.to_json() for r in results],
        "final_output": results[-1].output_data if results else None,
    })


# Synchronous wrappers for AG2 tool registration
def execute_planning_phase_sync(task: str, max_steps: int = 5, n_reviews: int = 1) -> str:
    """Sync wrapper for execute_planning_phase."""
    return asyncio.run(execute_planning_phase(task, max_steps, n_reviews))


def execute_control_phase_sync(plan: Dict[str, Any], mode: str = "sequential") -> str:
    """Sync wrapper for execute_control_phase."""
    return asyncio.run(execute_control_phase(plan, mode))


def execute_one_shot_phase_sync(task: str, agent: str = "engineer", max_rounds: int = 50) -> str:
    """Sync wrapper for execute_one_shot_phase."""
    return asyncio.run(execute_one_shot_phase(task, agent, max_rounds))


def execute_hitl_planning_phase_sync(task: str, max_iterations: int = 3, allow_modification: bool = True) -> str:
    """Sync wrapper for execute_hitl_planning_phase."""
    return asyncio.run(execute_hitl_planning_phase(task, max_iterations, allow_modification))


def execute_hitl_control_phase_sync(plan: Dict[str, Any], approval_mode: str = "after_step", allow_retry: bool = True) -> str:
    """Sync wrapper for execute_hitl_control_phase."""
    return asyncio.run(execute_hitl_control_phase(plan, approval_mode, allow_retry))


def execute_idea_generation_phase_sync(topic: str, n_ideas: int = 3, n_critiques: int = 1) -> str:
    """Sync wrapper for execute_idea_generation_phase."""
    return asyncio.run(execute_idea_generation_phase(topic, n_ideas, n_critiques))


def chain_phases_sync(phases: List[Dict[str, Any]], pass_context: bool = True) -> str:
    """Sync wrapper for chain_phases_executable."""
    return asyncio.run(chain_phases_executable(phases, pass_context))


# Export executable phase tools
EXECUTABLE_PHASE_TOOLS = [
    execute_planning_phase_sync,
    execute_control_phase_sync,
    execute_one_shot_phase_sync,
    execute_hitl_planning_phase_sync,
    execute_hitl_control_phase_sync,
    execute_idea_generation_phase_sync,
    chain_phases_sync,
]
