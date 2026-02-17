"""
HITL Planning Phase - Interactive planning with human feedback.

This module provides a HITLPlanningPhase that allows humans to:
1. Review and modify plans at each iteration
2. Provide guidance during plan generation
3. Approve, reject, or request revisions
4. Use AG2's human_input_mode for interactive planning

Uses PhaseExecutionManager for automatic:
- Callback invocation
- Database event logging
- DAG node management
- File tracking
- Pause/cancel handling
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import time
import json
import traceback

import logging

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.execution_manager import PhaseExecutionManager
from cmbagent.utils import get_model_config, default_agents_llm_model

logger = logging.getLogger(__name__)


@dataclass
class HITLPlanningPhaseConfig(PhaseConfig):
    """
    Configuration for HITL planning phase.

    Attributes:
        max_rounds: Maximum conversation rounds for planning
        max_plan_steps: Maximum number of steps in generated plan
        n_plan_reviews: Number of plan review iterations
        max_human_iterations: Maximum number of human feedback rounds
        planner_model: Model to use for planner agent
        plan_reviewer_model: Model to use for plan reviewer agent
        plan_instructions: Additional instructions for the planner
        hardware_constraints: Hardware constraints to consider
        auto_approve_after_iterations: Auto-approve after N iterations
        require_explicit_approval: Require explicit human approval
        show_intermediate_plans: Show plans at each review iteration
    """
    phase_type: str = "hitl_planning"

    # Planning parameters
    max_rounds: int = 50
    max_plan_steps: int = 10  # Allow up to 10 steps by default for dynamic plans
    n_plan_reviews: int = 1
    max_human_iterations: int = 3  # Maximum human feedback rounds

    # Model selection
    planner_model: str = field(default_factory=lambda: default_agents_llm_model['planner'])
    plan_reviewer_model: str = field(default_factory=lambda: default_agents_llm_model['plan_reviewer'])

    # Instructions
    plan_instructions: str = ""
    hardware_constraints: str = ""
    engineer_instructions: str = ""
    researcher_instructions: str = ""

    # HITL-specific options
    auto_approve_after_iterations: int = 3  # Auto-approve after N human iterations
    require_explicit_approval: bool = True  # Require explicit approval
    show_intermediate_plans: bool = True  # Show plans during review
    allow_plan_modification: bool = True  # Allow human to modify plans directly

    # Max attempts for step execution (passed to control phase via context)
    max_n_attempts: int = 3

    # AG2 HITL Handoff Configuration (NEW!)
    use_ag2_handoffs: bool = False  # Enable AG2-native HITL handoffs
    ag2_mandatory_checkpoints: List[str] = field(default_factory=lambda: ['after_planning'])  # Default: review plan
    ag2_smart_approval: bool = False  # Enable dynamic escalation
    ag2_smart_criteria: Dict = field(default_factory=dict)  # Criteria for smart escalation


class HITLPlanningPhase(Phase):
    """
    Human-in-the-loop planning phase with interactive feedback.

    This phase combines automated planning with human guidance:
    1. Agent generates initial plan
    2. Human reviews and provides feedback
    3. Agent revises plan based on feedback
    4. Repeat until human approves or max iterations reached

    Uses AG2's human_input_mode capabilities for interactive planning.

    Input Context:
        - task: The task description
        - work_dir: Working directory
        - api_keys: API credentials

    Output Context:
        - final_plan: The approved plan (list of steps)
        - number_of_steps_in_plan: Count of steps
        - plan_file_path: Path to saved plan JSON
        - planning_context: Full context from planning
        - human_feedback: List of human feedback iterations
        - iterations: Number of human feedback rounds
    """

    config_class = HITLPlanningPhaseConfig

    def __init__(self, config: HITLPlanningPhaseConfig = None):
        if config is None:
            config = HITLPlanningPhaseConfig()
        super().__init__(config)
        self.config: HITLPlanningPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "hitl_planning"

    @property
    def display_name(self) -> str:
        return "Interactive Planning (HITL)"

    def get_required_agents(self) -> List[str]:
        return ["planner", "plan_reviewer", "plan_setter", "planner_response_formatter", "admin"]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute HITL planning phase with human feedback loop.

        Args:
            context: Input context with task and configuration

        Returns:
            PhaseResult with approved plan
        """
        # Create execution manager for automatic infrastructure
        manager = PhaseExecutionManager(context, self)
        manager.start()

        self._status = PhaseStatus.RUNNING

        try:
            # Validate input
            validation_errors = self.validate_input(context)
            if validation_errors:
                raise ValueError(f"Input validation failed: {', '.join(validation_errors)}")

            # Setup
            from cmbagent.cmbagent import CMBAgent
            from cmbagent.agents.planner_response_formatter.planner_response_formatter import save_final_plan

            # Get approval manager for HITL
            approval_manager = context.shared_state.get('_approval_manager')
            logger.debug("Retrieved approval_manager: %s", approval_manager)
            logger.debug("shared_state keys: %s", list(context.shared_state.keys()))

            # Initialize agent with proper config
            api_keys = context.api_keys or {}

            # Create planning subdirectory (matches standard PlanningPhase)
            planning_dir = os.path.join(context.work_dir, "planning")
            os.makedirs(planning_dir, exist_ok=True)

            # Get model configs (must include both planner and plan_reviewer)
            planner_config = get_model_config(
                self.config.planner_model,
                api_keys=api_keys
            )
            reviewer_config = get_model_config(
                self.config.plan_reviewer_model,
                api_keys=api_keys
            )

            cmbagent = CMBAgent(
                cache_seed=42,
                work_dir=planning_dir,
                agent_llm_configs={
                    'planner': planner_config,
                    'plan_reviewer': reviewer_config,
                },
                api_keys=api_keys,
                **manager.get_managed_cmbagent_kwargs()
            )
            cmbagent._callbacks = context.callbacks

            # Configure AG2 HITL handoffs (if enabled)
            if self.config.use_ag2_handoffs:
                from cmbagent.handoffs import register_all_hand_offs

                hitl_config = {
                    'mandatory_checkpoints': self.config.ag2_mandatory_checkpoints,
                    'smart_approval': self.config.ag2_smart_approval,
                    'smart_criteria': self.config.ag2_smart_criteria,
                }

                # Register handoffs with HITL config
                register_all_hand_offs(cmbagent, hitl_config=hitl_config)
                logger.info("AG2 HITL handoffs enabled for planning: %s", hitl_config)


            # Check for previous feedback from other phases
            previous_hitl_feedback = context.shared_state.get('hitl_feedback', '')
            
            # Inject additional instructions
            base_instructions = ""
            if previous_hitl_feedback:
                base_instructions += f"\n\n## Previous Human Feedback\n{previous_hitl_feedback}\n\nPlease consider this feedback when creating the plan.\n"
            
            if self.config.plan_instructions:
                base_instructions += f"\n\n{self.config.plan_instructions}"
                
            if base_instructions:
                cmbagent.inject_to_agents(
                    ["planner"],
                    base_instructions,
                    mode="append"
                )

            if self.config.hardware_constraints:
                cmbagent.inject_to_agents(
                    ["planner", "engineer", "researcher"],
                    f"\n\n## Hardware Constraints\n{self.config.hardware_constraints}",
                    mode="append"
                )

            # Human feedback loop
            human_feedback_history = []
            iteration = 0
            approved = False
            final_plan = None
            final_context = None

            while iteration < self.config.max_human_iterations and not approved:
                iteration += 1
                manager.log_event("planning_iteration", {"iteration": iteration})

                # Check for cancellation
                manager.raise_if_cancelled()

                # Build task with feedback if available
                task_with_feedback = self._build_task_with_feedback(
                    context.task,
                    human_feedback_history,
                    iteration
                )

                # Run planning
                logger.info("=" * 60)
                logger.info("HITL PLANNING - Iteration %d/%d", iteration, self.config.max_human_iterations)
                logger.info("=" * 60)

                cmbagent.solve(
                    task=task_with_feedback,
                    initial_agent='plan_setter',  # Must use plan_setter, not planner
                    max_rounds=self.config.max_rounds,
                    shared_context={
                        'feedback_left': self.config.n_plan_reviews,
                        'max_n_attempts': self.config.max_n_attempts,
                        'maximum_number_of_steps_in_plan': self.config.max_plan_steps,
                        'planner_append_instructions': self.config.plan_instructions,
                        'engineer_append_instructions': self.config.engineer_instructions,
                        'researcher_append_instructions': self.config.researcher_instructions,
                        'plan_reviewer_append_instructions': self.config.plan_instructions,
                        'hardware_constraints': self.config.hardware_constraints,
                        'iteration': iteration,
                        **context.shared_state,
                    }
                )

                # Extract planning context from final_context
                planning_context = cmbagent.final_context
                logger.debug("Iteration %d: planning_context keys: %s", iteration, list(planning_context.keys()) if hasattr(planning_context, 'keys') else 'not a dict')

                # Save plan using standard save_final_plan (handles string/Pydantic/dict formats)
                try:
                    plan_file = save_final_plan(planning_context, planning_dir)
                    logger.debug("Iteration %d: plan_file = %s", iteration, plan_file)
                except (KeyError, TypeError) as e:
                    raise RuntimeError(f"Failed to generate plan: {e}")

                # Extract plan steps (matches standard PlanningPhase logic)
                plan = self._extract_plan(planning_context, plan_file)
                logger.debug("Iteration %d: extracted %d steps", iteration, len(plan))
                if plan:
                    logger.debug("Iteration %d: first step = %s", iteration, plan[0].get('sub_task', plan[0])[:100] if isinstance(plan[0], dict) else str(plan[0])[:100])

                if not plan:
                    raise RuntimeError("Failed to generate plan")

                # Present plan to human for approval
                logger.debug("approval_manager=%s, require_explicit_approval=%s", approval_manager, self.config.require_explicit_approval)
                if approval_manager and self.config.require_explicit_approval:
                    logger.debug("Creating approval request for iteration %d...", iteration)
                    approval_message = self._build_approval_message(plan, iteration)

                    approval_request = approval_manager.create_approval_request(
                        run_id=context.run_id,
                        step_id=f"{context.phase_id}_iter_{iteration}",
                        checkpoint_type="during_planning",
                        context_snapshot={
                            'plan': plan,
                            'iteration': iteration,
                            'task': context.task,
                        },
                        message=approval_message,
                        options=["approve", "reject", "revise", "modify"],
                    )

                    logger.info("=" * 60)
                    logger.info("PLAN REVIEW - Iteration %d", iteration)
                    logger.info("=" * 60)
                    logger.info("%s", approval_message)
                    logger.info("Waiting for human review...")
                    logger.info("=" * 60)

                    # Wait for approval
                    logger.debug("Calling wait_for_approval_async for %s...", approval_request.id)
                    resolved = await approval_manager.wait_for_approval_async(
                        str(approval_request.id),
                        timeout_seconds=3600,
                    )
                    logger.debug("wait_for_approval_async returned, resolution=%s", resolved.resolution)

                    # Handle resolution (accept both "approved" and "approve")
                    if resolved.resolution in ["approved", "approve"]:
                        approved = True
                        final_plan = plan
                        final_context = planning_context
                        logger.info("Plan approved by human")

                        # Capture approval-time feedback for the control phase
                        if hasattr(resolved, 'user_feedback') and resolved.user_feedback:
                            human_feedback_history.append({
                                'iteration': iteration,
                                'plan': plan,
                                'feedback': resolved.user_feedback,
                                'type': 'approval_note',
                            })
                            logger.info("Approval note: %s", resolved.user_feedback)
                            manager.log_event("plan_approved_with_feedback", {
                                "iteration": iteration,
                                "feedback": resolved.user_feedback
                            })

                    elif resolved.resolution in ["rejected", "reject"]:
                        error_msg = f"Plan rejected by human: {resolved.user_feedback}"
                        manager.log_event("plan_rejected", {
                            "iteration": iteration,
                            "feedback": resolved.user_feedback
                        })
                        self._status = PhaseStatus.FAILED
                        return manager.fail(error_msg, None)

                    elif resolved.resolution in ["modified", "modify"]:
                        # Human directly modified the plan
                        final_plan = resolved.modifications.get('plan', plan)
                        approved = True
                        final_context = planning_context
                        logger.info("Plan modified and approved by human")
                        manager.log_event("plan_modified", {
                            "iteration": iteration,
                            "modifications": resolved.modifications
                        })

                    else:  # revise or any other value
                        # Collect feedback for next iteration
                        feedback = resolved.user_feedback or "Please revise the plan."
                        human_feedback_history.append({
                            'iteration': iteration,
                            'plan': plan,
                            'feedback': feedback,
                        })
                        logger.info("Human requested revision: %s", feedback)
                        manager.log_event("plan_revision_requested", {
                            "iteration": iteration,
                            "feedback": feedback
                        })

                else:
                    # No approval manager or auto-approve mode
                    logger.debug("ELSE BRANCH: approval_manager=%s, require_explicit_approval=%s", approval_manager, self.config.require_explicit_approval)
                    if iteration >= self.config.auto_approve_after_iterations:
                        approved = True
                        final_plan = plan
                        final_context = planning_context
                        logger.info("Plan auto-approved after %d iterations", iteration)
                    else:
                        # Console-based approval
                        logger.debug("Console-based approval requested (iteration %d)", iteration)
                        logger.info("=" * 60)
                        logger.info("PLAN REVIEW - Iteration %d", iteration)
                        logger.info("=" * 60)
                        logger.info("%s", self._format_plan(plan))
                        logger.info("=" * 60)
                        response = input("\nApprove plan? (y/n/feedback): ").strip().lower()

                        if response == 'y' or response == 'yes':
                            approved = True
                            final_plan = plan
                            final_context = planning_context
                        elif response == 'n' or response == 'no':
                            return manager.fail("Plan rejected by human", None)
                        else:
                            # Treat as feedback
                            human_feedback_history.append({
                                'iteration': iteration,
                                'plan': plan,
                                'feedback': response,
                            })

            # Check if we got approval
            if not approved:
                return manager.fail(
                    f"Max iterations ({self.config.max_human_iterations}) reached without approval",
                    None
                )

            # Save final approved plan
            final_plan_file = os.path.join(planning_dir, 'final_plan_approved.json')
            with open(final_plan_file, 'w') as f:
                json.dump(final_plan, f, indent=2)

            # NOW invoke planning complete callback to send WebSocket events
            if context.callbacks:
                from cmbagent.callbacks import PlanInfo
                plan_info = PlanInfo(
                    task=context.task,
                    num_steps=len(final_plan),
                    steps=final_plan,
                    plan_text=str(final_plan),
                    planning_time=time.time() - manager.start_time if manager.start_time else 0
                )
                context.callbacks.invoke_planning_complete(plan_info)

            # Display cost
            if not hasattr(cmbagent, 'groupchat'):
                Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
                cmbagent.groupchat = Dummy()
            cmbagent.display_cost(name_append="hitl_planning")

            # Compile all feedback for downstream phases
            all_feedback = []
            for feedback_item in human_feedback_history:
                all_feedback.append(feedback_item.get('feedback', ''))
            
            combined_feedback = "\n\n".join(all_feedback) if all_feedback else ""
            
            # Build output for next phase
            output_data = {
                'final_plan': final_plan,
                'number_of_steps_in_plan': len(final_plan),
                'plan_file_path': final_plan_file,
                'planning_context': final_context,
                'human_feedback': human_feedback_history,
                'iterations': iteration,
                'shared': {
                    'plan_steps': final_plan,
                    'max_n_attempts': self.config.max_n_attempts,
                    'planning_context': final_context,
                    # Pass feedback forward to control phase
                    'hitl_feedback': combined_feedback,
                    'planning_feedback_history': human_feedback_history,
                    'human_guided_planning': True,
                }
            }

            self._status = PhaseStatus.COMPLETED
            
            # Collect chat history if available
            chat_history = []
            if hasattr(cmbagent, 'chat_result') and cmbagent.chat_result:
                chat_history = cmbagent.chat_result.chat_history or []
            
            return manager.complete(
                output_data=output_data,
                chat_history=chat_history,
            )

        except Exception as e:
            self._status = PhaseStatus.FAILED
            logger.error("HITL planning phase failed: %s", e, exc_info=True)
            return manager.fail(str(e), traceback.format_exc())

    def validate_input(self, context: PhaseContext) -> List[str]:
        """Validate that required input is present."""
        errors = []
        if not context.task:
            errors.append("Task is required")
        if not context.work_dir:
            errors.append("Work directory is required")
        return errors

    def _build_task_with_feedback(
        self,
        original_task: str,
        feedback_history: List[Dict],
        iteration: int
    ) -> str:
        """Build task string with accumulated human feedback."""
        if not feedback_history:
            return original_task

        task_parts = [
            original_task,
            "",
            "## Human Feedback from Previous Iterations",
            ""
        ]

        for feedback_item in feedback_history:
            task_parts.append(f"### Iteration {feedback_item['iteration']}")
            task_parts.append(f"Feedback: {feedback_item['feedback']}")
            task_parts.append("")

        task_parts.append(f"Please revise the plan based on the feedback above (Current iteration: {iteration}).")

        return "\n".join(task_parts)

    def _extract_plan(self, planning_context, plan_file: str = None) -> List[Dict]:
        """Extract plan from planning context (matches standard planning phase logic)."""
        # Get the raw plan object
        raw_plan = None
        if hasattr(planning_context, 'get'):
            raw_plan = planning_context.get('final_plan', planning_context.get('plan'))

        logger.debug(f"_extract_plan raw_plan type: {type(raw_plan)}")
        logger.debug(f"_extract_plan raw_plan preview: {str(raw_plan)[:500] if raw_plan else 'None'}")

        if not raw_plan:
            # Fallback: try to load from plan_file directly
            if plan_file:
                try:
                    with open(plan_file, 'r') as f:
                        plan_dict = json.load(f)
                    plan_steps_list = plan_dict.get('sub_tasks', [])
                    logger.debug(f"_extract_plan loaded from file: {len(plan_steps_list)} steps")
                    return plan_steps_list
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    logger.debug(f"_extract_plan failed to load from file: {e}")
            return []

        # Handle different plan formats (same as standard planning phase)
        if hasattr(raw_plan, 'model_dump'):  # Pydantic v2
            plan_dict = raw_plan.model_dump()
            plan_steps_list = plan_dict.get('sub_tasks', [])
            logger.debug(f"_extract_plan Pydantic v2: {len(plan_steps_list)} steps")
        elif hasattr(raw_plan, 'dict'):  # Pydantic v1
            plan_dict = raw_plan.dict()
            plan_steps_list = plan_dict.get('sub_tasks', [])
            logger.debug(f"_extract_plan Pydantic v1: {len(plan_steps_list)} steps")
        elif isinstance(raw_plan, dict):
            plan_steps_list = raw_plan.get('sub_tasks', raw_plan.get('steps', []))
            logger.debug(f"_extract_plan Dict: {len(plan_steps_list)} steps")
        elif isinstance(raw_plan, list):
            plan_steps_list = raw_plan
            logger.debug(f"_extract_plan List: {len(plan_steps_list)} steps")
        elif isinstance(raw_plan, str):
            # String plan: first try to load the structured JSON saved by save_final_plan
            if plan_file:
                try:
                    with open(plan_file, 'r') as f:
                        plan_dict = json.load(f)
                    plan_steps_list = plan_dict.get('sub_tasks', [])
                    logger.debug(f"_extract_plan String->File: {len(plan_steps_list)} steps")
                except (json.JSONDecodeError, FileNotFoundError):
                    plan_steps_list = []
            else:
                plan_steps_list = []
            
            # If still empty, the string wasn't parsed by save_final_plan correctly
            if not plan_steps_list:
                logger.debug(f"_extract_plan string plan not parsed, raw: {raw_plan[:300]}...")
        else:
            plan_steps_list = []

        # Validate and normalize steps
        normalized_steps = []
        for step in plan_steps_list:
            if isinstance(step, dict):
                normalized_steps.append(step)
            elif isinstance(step, str):
                normalized_steps.append({'sub_task': step, 'sub_task_agent': 'engineer', 'bullet_points': []})
        
        logger.debug(f"_extract_plan final: {len(normalized_steps)} normalized steps")
        if normalized_steps:
            logger.debug(f"_extract_plan first step: {normalized_steps[0]}")
        
        return normalized_steps

    def _build_approval_message(self, plan: List[Dict], iteration: int) -> str:
        """Build message for human approval."""
        parts = [
            f"Planning iteration {iteration} complete.",
            "",
            "## Generated Plan:",
            "",
            self._format_plan(plan),
            "",
            "**Options:**",
            "- **Approve**: Accept the plan and proceed to execution",
            "- **Reject**: Cancel the workflow",
            "- **Revise**: Provide feedback for plan revision",
            "- **Modify**: Directly edit the plan structure",
        ]
        return "\n".join(parts)

    def _format_plan(self, plan: List[Dict]) -> str:
        """Format plan for display."""
        if not plan:
            return "(No plan steps found)"
        
        lines = []
        for i, step in enumerate(plan, 1):
            # Handle different step formats
            if isinstance(step, dict):
                sub_task = step.get('sub_task', step.get('description', step.get('task', 'Unknown task')))
                agent = step.get('sub_task_agent', step.get('agent', ''))
                bullet_points = step.get('bullet_points', step.get('instructions', []))
                
                # Format step header
                if agent:
                    lines.append(f"**Step {i}** ({agent}): {sub_task}")
                else:
                    lines.append(f"**Step {i}**: {sub_task}")
                
                # Add bullet points if any
                if bullet_points and isinstance(bullet_points, list):
                    for bp in bullet_points[:3]:  # Limit to 3 bullet points
                        lines.append(f"   - {bp}")
            elif isinstance(step, str):
                lines.append(f"**Step {i}**: {step}")
            else:
                lines.append(f"**Step {i}**: {str(step)}")
            
            lines.append("")  # Add spacing between steps
        
        return "\n".join(lines)
