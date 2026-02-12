"""
Planning phase implementation for CMBAgent.

This module provides the PlanningPhase class that generates
a structured plan for task execution.

Uses PhaseExecutionManager for:
- Automatic callback invocation
- Database event logging
- DAG node management
- File tracking
- Pause/cancel handling
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import time
import traceback
import logging

logger = logging.getLogger(__name__)

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.execution_manager import PhaseExecutionManager
from cmbagent.utils import get_model_config, default_agents_llm_model


@dataclass
class PlanningPhaseConfig(PhaseConfig):
    """
    Configuration for planning phase.

    Attributes:
        max_rounds: Maximum conversation rounds for planning
        max_plan_steps: Maximum number of steps in generated plan
        n_plan_reviews: Number of plan review iterations
        planner_model: Model to use for planner agent
        plan_reviewer_model: Model to use for plan reviewer agent
        plan_instructions: Additional instructions for the planner
        hardware_constraints: Hardware constraints to consider
    """
    phase_type: str = "planning"

    # Planning parameters
    max_rounds: int = 50
    max_plan_steps: int = 3
    n_plan_reviews: int = 1

    # Model selection
    planner_model: str = field(default_factory=lambda: default_agents_llm_model['planner'])
    plan_reviewer_model: str = field(default_factory=lambda: default_agents_llm_model['plan_reviewer'])

    # Instructions
    plan_instructions: str = ""
    hardware_constraints: str = ""

    # Additional append instructions
    engineer_instructions: str = ""
    researcher_instructions: str = ""

    # Max attempts for step execution (passed to control phase via context)
    max_n_attempts: int = 3


class PlanningPhase(Phase):
    """
    Planning phase that generates a structured plan for the task.

    Input Context:
        - task: The task description
        - work_dir: Working directory
        - api_keys: API credentials

    Output Context:
        - final_plan: The generated plan (list of steps)
        - number_of_steps_in_plan: Count of steps
        - plan_file_path: Path to saved plan JSON
        - planning_context: Full context from planning
    """

    config_class = PlanningPhaseConfig

    def __init__(self, config: PlanningPhaseConfig = None):
        if config is None:
            config = PlanningPhaseConfig()
        super().__init__(config)
        self.config: PlanningPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "planning"

    @property
    def display_name(self) -> str:
        return "Planning"

    def get_required_agents(self) -> List[str]:
        return ["planner", "plan_reviewer", "plan_setter", "planner_response_formatter"]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute the planning phase.

        Creates a CMBAgent instance and runs the planning workflow
        to generate a structured plan for the task.

        Args:
            context: Input context with task and configuration

        Returns:
            PhaseResult with generated plan
        """
        from cmbagent.cmbagent import CMBAgent
        from cmbagent.agents.planner_response_formatter.planner_response_formatter import save_final_plan
        from cmbagent.callbacks import PlanInfo

        # Use PhaseExecutionManager for automatic callback/logging handling
        manager = PhaseExecutionManager(context, self)
        manager.start()

        self._status = PhaseStatus.RUNNING

        # Setup directory
        planning_dir = os.path.join(context.work_dir, "planning")
        os.makedirs(planning_dir, exist_ok=True)

        # Get model configs
        planner_config = get_model_config(self.config.planner_model, context.api_keys)
        reviewer_config = get_model_config(self.config.plan_reviewer_model, context.api_keys)

        try:
            # Check for pause/cancel before starting
            manager.raise_if_cancelled()

            # Invoke planning start callback
            if context.callbacks:
                context.callbacks.invoke_planning_start(context.task, {
                    'planner_model': self.config.planner_model,
                    'plan_reviewer_model': self.config.plan_reviewer_model,
                    'max_plan_steps': self.config.max_plan_steps,
                    'n_plan_reviews': self.config.n_plan_reviews,
                })

            # Initialize CMBAgent for planning
            init_start = time.time()
            cmbagent = CMBAgent(
                cache_seed=42,
                work_dir=planning_dir,
                agent_llm_configs={
                    'planner': planner_config,
                    'plan_reviewer': reviewer_config,
                },
                api_keys=context.api_keys,
                **manager.get_managed_cmbagent_kwargs()
            )
            init_time = time.time() - init_start

            # Log initialization
            manager.log_event("agent_initialized", {
                'agent': 'planner',
                'model': self.config.planner_model,
                'init_time': init_time,
            })

            # Execute planning
            exec_start = time.time()
            cmbagent.solve(
                context.task,
                max_rounds=self.config.max_rounds,
                initial_agent="plan_setter",
                shared_context={
                    'feedback_left': self.config.n_plan_reviews,
                    'max_n_attempts': self.config.max_n_attempts,
                    'maximum_number_of_steps_in_plan': self.config.max_plan_steps,
                    'planner_append_instructions': self.config.plan_instructions,
                    'engineer_append_instructions': self.config.engineer_instructions,
                    'researcher_append_instructions': self.config.researcher_instructions,
                    'plan_reviewer_append_instructions': self.config.plan_instructions,
                    'hardware_constraints': self.config.hardware_constraints,
                    # Carry over any shared state
                    **context.shared_state,
                }
            )
            exec_time = time.time() - exec_start

            # Create a dummy groupchat attribute if it doesn't exist
            if not hasattr(cmbagent, 'groupchat'):
                Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
                cmbagent.groupchat = Dummy()

            # Display cost
            cmbagent.display_cost()

            # Save plan
            plan_file = save_final_plan(cmbagent.final_context, planning_dir)
            manager.track_file(plan_file)

            logger.info("Structured plan written to %s", plan_file)
            logger.info("Planning took %.4f seconds", exec_time)

            # Extract plan steps as a list (normalize different formats)
            raw_plan = cmbagent.final_context.get('final_plan')
            if hasattr(raw_plan, 'model_dump'):  # Pydantic v2
                plan_dict = raw_plan.model_dump()
                plan_steps_list = plan_dict.get('sub_tasks', [])
            elif hasattr(raw_plan, 'dict'):  # Pydantic v1
                plan_dict = raw_plan.dict()
                plan_steps_list = plan_dict.get('sub_tasks', [])
            elif isinstance(raw_plan, dict):
                plan_steps_list = raw_plan.get('sub_tasks', [])
            elif isinstance(raw_plan, list):
                plan_steps_list = raw_plan
            elif isinstance(raw_plan, str):
                # Load the saved JSON which has proper structure
                import json
                with open(plan_file, 'r') as f:
                    plan_dict = json.load(f)
                plan_steps_list = plan_dict.get('sub_tasks', [])
            else:
                plan_steps_list = []

            # Update the planning phase node with the plan content BEFORE sending events
            manager.update_current_node_metadata({
                "plan": plan_steps_list,
                "num_steps": len(plan_steps_list),
                "steps_summary": [s.get('sub_task', s.get('task', '')) for s in plan_steps_list]
            })

            # Add plan step nodes to DAG for visualization BEFORE sending WebSocket events
            # Pass the current phase node ID so steps connect to the planning phase
            manager.add_plan_step_nodes(plan_steps_list, source_node=manager._current_dag_node_id)

            # NOW invoke planning complete callback to send WebSocket events (after DB nodes created)
            if context.callbacks:
                plan_info = PlanInfo(
                    task=context.task,
                    num_steps=len(plan_steps_list),
                    steps=plan_steps_list,
                    plan_text=str(plan_steps_list),
                    planning_time=exec_time,
                )
                context.callbacks.invoke_planning_complete(plan_info)

            # Build output
            output_data = {
                'final_plan': plan_steps_list,  # List of step dicts
                'number_of_steps_in_plan': len(plan_steps_list),
                'plan_file_path': plan_file,
                'planning_context': cmbagent.final_context,
                # Shared state to carry forward
                'shared': {
                    'plan_steps': plan_steps_list,
                    'current_step': 0,
                    'number_of_steps_in_plan': len(plan_steps_list),
                    'planning_context': cmbagent.final_context,
                }
            }

            self._status = PhaseStatus.COMPLETED
            return manager.complete(
                output_data=output_data,
                chat_history=cmbagent.chat_result.chat_history if cmbagent.chat_result else [],
            )

        except Exception as e:
            self._status = PhaseStatus.FAILED
            logger.error("Planning phase failed: %s", e, exc_info=True)
            return manager.fail(str(e), traceback.format_exc())

    def validate_input(self, context: PhaseContext) -> List[str]:
        """Validate that required input is present."""
        errors = []
        if not context.task:
            errors.append("Task is required for planning phase")
        if not context.work_dir:
            errors.append("work_dir is required for planning phase")
        return errors
