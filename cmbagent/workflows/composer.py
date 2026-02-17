"""
Workflow composer module for CMBAgent.

This module provides the WorkflowDefinition and WorkflowExecutor classes
for defining and executing phase-based workflows.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import uuid
import time
import asyncio
import os
import logging

logger = logging.getLogger(__name__)

from cmbagent.phases.base import Phase, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.context import WorkflowContext
from cmbagent.phases.registry import PhaseRegistry


@dataclass
class WorkflowDefinition:
    """
    Definition of a workflow as a sequence of phases.

    Attributes:
        id: Unique identifier for the workflow
        name: Human-readable name
        description: Description of what the workflow does
        phases: List of phase definitions [{type: "...", config: {...}}, ...]
        version: Version number for the definition
        is_system: Whether this is a system-provided workflow
        created_by: Optional creator identifier
    """
    id: str
    name: str
    description: str
    phases: List[Dict[str, Any]]

    # Metadata
    version: int = 1
    is_system: bool = False
    created_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'phases': self.phases,
            'version': self.version,
            'is_system': self.is_system,
            'created_by': self.created_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowDefinition':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            description=data['description'],
            phases=data['phases'],
            version=data.get('version', 1),
            is_system=data.get('is_system', False),
            created_by=data.get('created_by'),
        )


class WorkflowExecutor:
    """
    Executes a workflow by running phases in sequence.

    Handles context passing, error recovery, and checkpointing.
    """

    def __init__(
        self,
        workflow: WorkflowDefinition,
        task: str,
        work_dir: str,
        api_keys: Dict[str, str],
        callbacks: Any = None,
        approval_manager: Any = None,
        initial_shared_state: Dict[str, Any] = None,
    ):
        """
        Initialize workflow executor.

        Args:
            workflow: The workflow definition to execute
            task: Task description
            work_dir: Working directory for outputs
            api_keys: API credentials
            callbacks: Optional callback handlers
            approval_manager: Optional HITL approval manager
            initial_shared_state: Optional initial shared state for phases
        """
        self.workflow = workflow
        self.task = task
        self.work_dir = os.path.abspath(os.path.expanduser(work_dir))
        self.api_keys = api_keys
        self.callbacks = callbacks
        self.approval_manager = approval_manager
        self.initial_shared_state = initial_shared_state or {}

        # Build phases from definitions
        self.phases: List[Phase] = []
        for phase_def in workflow.phases:
            phase = PhaseRegistry.create_from_dict(phase_def)
            self.phases.append(phase)

        # Initialize workflow context
        self.context = WorkflowContext(
            workflow_id=workflow.id,
            run_id=str(uuid.uuid4()),
            task=task,
            work_dir=self.work_dir,
            api_keys=api_keys,
        )

        # Apply initial shared state
        if self.initial_shared_state:
            self.context.shared_state.update(self.initial_shared_state)

        # Execution state
        self.current_phase_index = 0
        self.results: List[PhaseResult] = []
        self._should_stop = False

    async def run(self) -> WorkflowContext:
        """
        Execute the workflow.

        Runs each phase in sequence, passing context between them.

        Returns:
            Final WorkflowContext after all phases
        """
        # Create work directory
        os.makedirs(self.work_dir, exist_ok=True)

        total_start = time.time()
        previous_result: Optional[PhaseResult] = None

        for i, phase in enumerate(self.phases):
            if self._should_stop:
                break

            self.current_phase_index = i
            phase_id = f"phase_{i}_{phase.phase_type}"

            # Create phase context
            if previous_result and previous_result.succeeded:
                # Use previous phase's output as input
                phase_context = previous_result.context.copy_for_next_phase(phase_id)
            else:
                # First phase or after failure
                phase_context = self.context.to_phase_context(phase_id)

            # Inject callbacks
            phase_context.callbacks = self.callbacks

            # Check if phase should be skipped
            if phase.can_skip(phase_context):
                logger.info("Skipping phase: %s", phase.display_name)
                continue

            # Validate input
            errors = phase.validate_input(phase_context)
            if errors:
                raise ValueError(f"Phase {phase.phase_type} validation failed: {errors}")

            # Inject approval manager for HITL phases
            if self.approval_manager:
                phase_context.shared_state['_approval_manager'] = self.approval_manager

            # Execute phase
            logger.info("PHASE %s/%s: %s", i + 1, len(self.phases), phase.display_name)

            if self.callbacks:
                self.callbacks.invoke_phase_change(phase.phase_type, i)

            result = await phase.execute(phase_context)
            self.results.append(result)
            previous_result = result

            # Handle failure
            if not result.succeeded:
                if result.needs_approval:
                    # HITL waiting - workflow paused
                    logger.info("Phase %s waiting for approval", phase.display_name)
                else:
                    error_msg = f"Phase {phase.phase_type} failed: {result.error}"
                    logger.error("%s", error_msg)
                    raise RuntimeError(error_msg)

            # Update master context
            self.context.update_from_phase_result(result)

        # Record total time
        self.context.phase_timings['total'] = time.time() - total_start

        logger.info(
            "WORKFLOW COMPLETE | Total time: %.2f seconds",
            self.context.phase_timings['total'],
        )

        return self.context

    def run_sync(self) -> WorkflowContext:
        """
        Synchronous wrapper for run().

        Returns:
            Final WorkflowContext after all phases
        """
        return asyncio.run(self.run())

    def stop(self) -> None:
        """Signal workflow to stop after current phase."""
        self._should_stop = True

    def get_status(self) -> Dict[str, Any]:
        """
        Get current execution status.

        Returns:
            Dictionary with status information
        """
        return {
            'workflow_id': self.workflow.id,
            'run_id': self.context.run_id,
            'current_phase': self.current_phase_index,
            'total_phases': len(self.phases),
            'phase_results': [
                {
                    'phase_type': r.context.phase_id,
                    'status': r.status.value,
                    'error': r.error,
                }
                for r in self.results
            ],
        }


# ============================================================================
# PRESET WORKFLOW DEFINITIONS
# ============================================================================

DEEP_RESEARCH_WORKFLOW = WorkflowDefinition(
    id="deep_research",
    name="Deep Research",
    description="Planning followed by multi-step execution with context carryover",
    phases=[
        {"type": "planning", "config": {"max_plan_steps": 3, "n_plan_reviews": 1}},
        {"type": "control", "config": {"execute_all_steps": True}},
    ],
    is_system=True,
)

DEEP_RESEARCH_HITL_WORKFLOW = WorkflowDefinition(
    id="deep_research_hitl",
    name="Deep Research with HITL",
    description="Deep research with human approval after planning",
    phases=[
        {"type": "planning", "config": {"max_plan_steps": 3, "n_plan_reviews": 1}},
        {"type": "hitl_checkpoint", "config": {"checkpoint_type": "after_planning"}},
        {"type": "control", "config": {"execute_all_steps": True}},
    ],
    is_system=True,
)

DEEP_RESEARCH_FULL_HITL_WORKFLOW = WorkflowDefinition(
    id="deep_research_full_hitl",
    name="Deep Research with Full HITL",
    description="Human approval after planning and after each step",
    phases=[
        {"type": "planning", "config": {"max_plan_steps": 3, "n_plan_reviews": 1}},
        {"type": "hitl_checkpoint", "config": {"checkpoint_type": "after_planning"}},
        {"type": "control", "config": {"execute_all_steps": True, "hitl_after_each_step": True}},
    ],
    is_system=True,
)

ONE_SHOT_WORKFLOW = WorkflowDefinition(
    id="one_shot",
    name="Quick Task",
    description="Single-shot execution without planning",
    phases=[
        {"type": "one_shot", "config": {"agent": "engineer"}},
    ],
    is_system=True,
)

ONE_SHOT_RESEARCHER_WORKFLOW = WorkflowDefinition(
    id="one_shot_researcher",
    name="Quick Research",
    description="Single-shot execution with researcher agent",
    phases=[
        {"type": "one_shot", "config": {"agent": "researcher"}},
    ],
    is_system=True,
)

IDEA_GENERATION_WORKFLOW = WorkflowDefinition(
    id="idea_generation",
    name="Idea Generation",
    description="Generate and review research ideas using planning and control workflow with idea agents",
    phases=[
        {"type": "planning", "config": {"max_plan_steps": 6}},
        {"type": "control", "config": {"execute_all_steps": True, "agents": ["idea_maker", "idea_hater"]}},
    ],
    is_system=True,
)

IDEA_TO_EXECUTION_WORKFLOW = WorkflowDefinition(
    id="idea_to_execution",
    name="Idea to Execution",
    description="Generate ideas using planning & control, then plan and execute the selected idea",
    phases=[
        {"type": "planning", "config": {"max_plan_steps": 6}},
        {"type": "control", "config": {"execute_all_steps": True, "agents": ["idea_maker", "idea_hater"]}},
        {"type": "hitl_checkpoint", "config": {"checkpoint_type": "custom", "custom_message": "Select idea to execute"}},
        {"type": "planning", "config": {"max_plan_steps": 5}},
        {"type": "hitl_checkpoint", "config": {"checkpoint_type": "after_planning"}},
        {"type": "control", "config": {"execute_all_steps": True}},
    ],
    is_system=True,
)

# New HITL workflows with feedback support

INTERACTIVE_PLANNING_WORKFLOW = WorkflowDefinition(
    id="interactive_planning",
    name="Interactive Planning with Feedback",
    description="Human-guided iterative planning with feedback incorporated into execution",
    phases=[
        {
            "type": "hitl_planning",
            "config": {
                "max_plan_steps": 5,
                "max_human_iterations": 3,
                "require_explicit_approval": True,
                "allow_plan_modification": True,
                "show_intermediate_plans": True,
            }
        },
        {
            "type": "control",
            "config": {
                "execute_all_steps": True,
                "max_rounds": 150,
            }
        },
    ],
    is_system=True,
)

INTERACTIVE_CONTROL_WORKFLOW = WorkflowDefinition(
    id="interactive_control",
    name="Interactive Execution with Feedback",
    description="Step-by-step execution with human feedback at each step",
    phases=[
        {
            "type": "planning",
            "config": {
                "max_plan_steps": 4,
                "n_plan_reviews": 1,
            }
        },
        {
            "type": "hitl_checkpoint",
            "config": {
                "checkpoint_type": "after_planning",
                "show_plan": True,
            }
        },
        {
            "type": "hitl_control",
            "config": {
                "approval_mode": "before_step",
                "allow_step_skip": True,
                "show_step_context": True,
            }
        },
    ],
    is_system=True,
)

FULL_INTERACTIVE_WORKFLOW = WorkflowDefinition(
    id="full_interactive",
    name="Full Interactive Workflow",
    description="Complete human-in-the-loop workflow with iterative planning and step-by-step control",
    phases=[
        {
            "type": "hitl_planning",
            "config": {
                "max_plan_steps": 5,
                "max_human_iterations": 3,
                "require_explicit_approval": True,
                "allow_plan_modification": True,
            }
        },
        {
            "type": "hitl_control",
            "config": {
                "approval_mode": "both",  # Before and after each step
                "allow_step_skip": True,
                "allow_step_retry": True,
                "show_step_context": True,
            }
        },
    ],
    is_system=True,
)

ERROR_RECOVERY_WORKFLOW = WorkflowDefinition(
    id="error_recovery",
    name="Autonomous with Error Recovery",
    description="Autonomous execution with human intervention only when errors occur",
    phases=[
        {
            "type": "planning",
            "config": {
                "max_plan_steps": 4,
                "n_plan_reviews": 1,
            }
        },
        {
            "type": "hitl_control",
            "config": {
                "approval_mode": "on_error",
                "allow_step_retry": True,
                "allow_step_skip": True,
                "max_n_attempts": 3,
            }
        },
    ],
    is_system=True,
)

PROGRESSIVE_REVIEW_WORKFLOW = WorkflowDefinition(
    id="progressive_review",
    name="Progressive Review Workflow",
    description="Review results after each step completes",
    phases=[
        {
            "type": "planning",
            "config": {
                "max_plan_steps": 4,
            }
        },
        {
            "type": "hitl_control",
            "config": {
                "approval_mode": "after_step",
                "auto_approve_successful_steps": False,
                "show_step_context": True,
            }
        },
    ],
    is_system=True,
)

SMART_APPROVAL_WORKFLOW = WorkflowDefinition(
    id="smart_approval",
    name="Smart Conditional Approval",
    description="AI decides when human approval is needed based on context",
    phases=[
        {
            "type": "planning",
            "config": {
                "max_plan_steps": 5,
            }
        },
        {
            "type": "hitl_checkpoint",
            "config": {
                "checkpoint_type": "after_planning",
                "show_plan": True,
                "options": ["approve", "reject", "modify", "add_feedback"],
            }
        },
        {
            "type": "control",
            "config": {
                "execute_all_steps": True,
                "max_rounds": 150,
            }
        },
    ],
    is_system=True,
)

# Copilot workflow - flexible assistant that adapts to task complexity
COPILOT_WORKFLOW = WorkflowDefinition(
    id="copilot",
    name="Copilot Assistant",
    description="Flexible AI assistant that adapts to task complexity - routes simple tasks to one-shot, complex tasks to planning",
    phases=[
        {
            "type": "copilot",
            "config": {
                "available_agents": ["engineer", "researcher"],
                "enable_planning": True,
                "complexity_threshold": 50,
                "continuous_mode": False,
                "max_turns": 20,
                "max_rounds": 100,
                "max_plan_steps": 5,
                "approval_mode": "after_step",
                "auto_approve_simple": True,
            }
        },
    ],
    is_system=True,
)

COPILOT_CONTINUOUS_WORKFLOW = WorkflowDefinition(
    id="copilot_continuous",
    name="Copilot Interactive Session",
    description="Continuous copilot session - keeps running until user exits",
    phases=[
        {
            "type": "copilot",
            "config": {
                "available_agents": ["engineer", "researcher"],
                "enable_planning": True,
                "continuous_mode": True,
                "max_turns": 50,
                "approval_mode": "after_step",
            }
        },
    ],
    is_system=True,
)

COPILOT_SIMPLE_WORKFLOW = WorkflowDefinition(
    id="copilot_simple",
    name="Simple Copilot (No Planning)",
    description="Direct task execution without planning - for quick simple tasks",
    phases=[
        {
            "type": "copilot",
            "config": {
                "available_agents": ["engineer", "researcher"],
                "enable_planning": False,
                "approval_mode": "none",
            }
        },
    ],
    is_system=True,
)

# Sample extensibility workflow: 4-phase deep research
# Demonstrates that a new workflow requires ZERO tracking code.
DEEP_RESEARCH_EXTENDED_WORKFLOW = WorkflowDefinition(
    id="deep_research_extended",
    name="Extended Deep Research",
    description=(
        "4-phase research workflow: literature review, planning, "
        "multi-step execution, and synthesis. Demonstrates extensibility – "
        "ZERO tracking code needed."
    ),
    phases=[
        {"type": "literature_review", "config": {"max_rounds": 50}},
        {"type": "planning", "config": {"max_plan_steps": 5, "n_plan_reviews": 1}},
        {"type": "control", "config": {"execute_all_steps": True}},
        {"type": "synthesis", "config": {"max_rounds": 50}},
    ],
    is_system=True,
)


# Default workflows available
SYSTEM_WORKFLOWS: Dict[str, WorkflowDefinition] = {
    w.id: w for w in [
        DEEP_RESEARCH_WORKFLOW,
        DEEP_RESEARCH_HITL_WORKFLOW,
        DEEP_RESEARCH_FULL_HITL_WORKFLOW,
        ONE_SHOT_WORKFLOW,
        ONE_SHOT_RESEARCHER_WORKFLOW,
        IDEA_GENERATION_WORKFLOW,
        IDEA_TO_EXECUTION_WORKFLOW,
        # New HITL workflows with feedback
        INTERACTIVE_PLANNING_WORKFLOW,
        INTERACTIVE_CONTROL_WORKFLOW,
        FULL_INTERACTIVE_WORKFLOW,
        ERROR_RECOVERY_WORKFLOW,
        PROGRESSIVE_REVIEW_WORKFLOW,
        SMART_APPROVAL_WORKFLOW,
        # Copilot workflows
        COPILOT_WORKFLOW,
        COPILOT_CONTINUOUS_WORKFLOW,
        COPILOT_SIMPLE_WORKFLOW,
        # Extended research
        DEEP_RESEARCH_EXTENDED_WORKFLOW,
    ]
}


def get_workflow(workflow_id: str) -> WorkflowDefinition:
    """
    Get a workflow definition by ID.

    Args:
        workflow_id: The workflow identifier

    Returns:
        WorkflowDefinition

    Raises:
        ValueError: If workflow not found
    """
    if workflow_id not in SYSTEM_WORKFLOWS:
        raise ValueError(f"Unknown workflow: {workflow_id}. Available: {list(SYSTEM_WORKFLOWS.keys())}")
    return SYSTEM_WORKFLOWS[workflow_id]


def list_workflows() -> List[Dict[str, Any]]:
    """
    List all available workflows.

    Returns:
        List of workflow info dictionaries
    """
    return [
        {
            'id': w.id,
            'name': w.name,
            'description': w.description,
            'num_phases': len(w.phases),
            'is_system': w.is_system,
        }
        for w in SYSTEM_WORKFLOWS.values()
    ]
