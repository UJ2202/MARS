"""
HITL Control Phase - Step-by-step execution with human approval.

This module provides a HITLControlPhase that allows humans to:
1. Approve each step before execution
2. Review step results and provide feedback
3. Modify step parameters or skip steps
4. Use AG2's human_input_mode for interactive execution

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
import copy
import json
import pickle
import re

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.execution_manager import PhaseExecutionManager
from cmbagent.utils import get_model_config, default_agents_llm_model


@dataclass
class HITLControlPhaseConfig(PhaseConfig):
    """
    Configuration for HITL control/execution phase.

    Attributes:
        max_rounds: Maximum conversation rounds per step
        max_n_attempts: Maximum attempts per step before failure
        execute_all_steps: Whether to execute all plan steps
        step_number: Specific step to execute (if not all steps)
        approval_mode: When to ask for approval ("before_step", "after_step", "both", "on_error")
        allow_step_skip: Allow human to skip failed steps
        allow_step_retry: Allow human to retry failed steps
        allow_step_modification: Allow human to modify step parameters
        show_step_context: Show accumulated context before each step
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
    """
    phase_type: str = "hitl_control"

    # Execution parameters
    max_rounds: int = 100
    max_n_attempts: int = 3

    # Step handling
    execute_all_steps: bool = True
    step_number: Optional[int] = None

    # HITL options
    approval_mode: str = "before_step"  # "before_step", "after_step", "both", "on_error"
    allow_step_skip: bool = True
    allow_step_retry: bool = True
    allow_step_modification: bool = True
    show_step_context: bool = True
    auto_approve_successful_steps: bool = False  # Auto-approve if step succeeds

    # Model selection
    engineer_model: str = field(default_factory=lambda: default_agents_llm_model['engineer'])
    researcher_model: str = field(default_factory=lambda: default_agents_llm_model['researcher'])
    web_surfer_model: str = field(default_factory=lambda: default_agents_llm_model.get('web_surfer', default_agents_llm_model['researcher']))
    retrieve_assistant_model: str = field(default_factory=lambda: default_agents_llm_model.get('retrieve_assistant', default_agents_llm_model['researcher']))
    idea_maker_model: str = field(default_factory=lambda: default_agents_llm_model['idea_maker'])
    idea_hater_model: str = field(default_factory=lambda: default_agents_llm_model['idea_hater'])
    camb_context_model: str = field(default_factory=lambda: default_agents_llm_model['camb_context'])
    plot_judge_model: str = field(default_factory=lambda: default_agents_llm_model['plot_judge'])

    # Instructions
    engineer_instructions: str = ""
    researcher_instructions: str = ""

    # AG2 HITL Handoff Configuration (NEW!)
    use_ag2_handoffs: bool = False  # Enable AG2-native HITL handoffs
    ag2_mandatory_checkpoints: List[str] = field(default_factory=list)  # e.g., ["before_file_edit", "before_execution"]
    ag2_smart_approval: bool = False  # Enable dynamic escalation
    ag2_smart_criteria: Dict = field(default_factory=dict)  # Criteria for smart escalation


class HITLControlPhase(Phase):
    """
    Human-in-the-loop control phase with step-by-step approval.

    This phase executes plan steps with human oversight:
    1. Present step to human for approval (before_step mode)
    2. Execute step with agents
    3. Present results to human for review (after_step mode)
    4. Handle errors with human feedback (on_error mode)
    5. Continue or abort based on human decisions

    Input Context:
        - final_plan or plan_steps: The plan to execute
        - task: Original task
        - work_dir: Working directory
        - planning_context: Context from planning phase

    Output Context:
        - step_results: Results from each step
        - final_context: Final context after all steps
        - step_summaries: Summary of each step
        - human_interventions: List of human interventions
        - skipped_steps: List of steps skipped by human
    """

    config_class = HITLControlPhaseConfig

    def __init__(self, config: HITLControlPhaseConfig = None):
        if config is None:
            config = HITLControlPhaseConfig()
        super().__init__(config)
        self.config: HITLControlPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "hitl_control"

    @property
    def display_name(self) -> str:
        return "Interactive Execution (HITL)"

    def get_required_agents(self) -> List[str]:
        return ["control", "control_starter", "engineer", "researcher"]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute HITL control phase with human feedback loop.

        Args:
            context: Input context with plan and configuration

        Returns:
            PhaseResult with execution results
        """
        # Create execution manager for automatic infrastructure
        manager = PhaseExecutionManager(context, self)
        manager.start()

        self._status = PhaseStatus.RUNNING

        try:
            # Extract plan (do this before validate_input since we check shared_state too)
            plan_steps = self._extract_plan(context)
            if not plan_steps:
                raise ValueError("No plan steps found in context")

            # Get approval manager
            approval_manager = context.shared_state.get('_approval_manager')
            print(f"[HITLControlPhase] Approval manager type: {type(approval_manager)}")
            print(f"[HITLControlPhase] Approval manager: {approval_manager}")
            if approval_manager:
                print(f"[HITLControlPhase] Approval manager has ws_send_event: {hasattr(approval_manager, 'ws_send_event')}")
            else:
                print(f"[HITLControlPhase] WARNING: No approval manager found in shared_state!")
                print(f"[HITLControlPhase] Shared state keys: {list(context.shared_state.keys())}")

            # Setup
            from cmbagent.cmbagent import CMBAgent

            api_keys = context.api_keys or {}

            # Get model configs (must match standard control phase)
            engineer_config = get_model_config(self.config.engineer_model, api_keys)
            researcher_config = get_model_config(self.config.researcher_model, api_keys)
            web_surfer_config = get_model_config(self.config.web_surfer_model, api_keys)
            retrieve_assistant_config = get_model_config(self.config.retrieve_assistant_model, api_keys)
            idea_maker_config = get_model_config(self.config.idea_maker_model, api_keys)
            idea_hater_config = get_model_config(self.config.idea_hater_model, api_keys)
            camb_context_config = get_model_config(self.config.camb_context_model, api_keys)
            plot_judge_config = get_model_config(self.config.plot_judge_model, api_keys)

            agent_llm_configs = {
                'engineer': engineer_config,
                'researcher': researcher_config,
                'web_surfer': web_surfer_config,
                'retrieve_assistant': retrieve_assistant_config,
                'idea_maker': idea_maker_config,
                'idea_hater': idea_hater_config,
                'camb_context': camb_context_config,
                'plot_judge': plot_judge_config,
            }

            # Include any feedback from previous HITL phases
            hitl_feedback = context.shared_state.get('hitl_feedback', '')

            # Determine which steps to execute
            if self.config.execute_all_steps:
                steps_to_execute = list(range(1, len(plan_steps) + 1))
            elif self.config.step_number is not None:
                steps_to_execute = [self.config.step_number]
            else:
                steps_to_execute = list(range(1, len(plan_steps) + 1))

            # Execution tracking
            step_results = []
            step_summaries = []
            human_interventions = []
            skipped_steps = []
            all_chat_history = []

            # Initialize current context from planning output (matches standard ControlPhase)
            planning_context = (
                context.input_data.get('planning_context') or
                context.shared_state.get('planning_context') or
                {}
            )
            current_context = copy.deepcopy(planning_context)

            # Setup directories (match standard ControlPhase)
            control_dir = os.path.join(context.work_dir, "control")
            os.makedirs(control_dir, exist_ok=True)
            context_dir = os.path.join(context.work_dir, "context")
            os.makedirs(context_dir, exist_ok=True)

            current_context['work_dir'] = control_dir

            # Initialize accumulated feedback from previous phases
            self._accumulated_feedback = hitl_feedback
            self._step_feedback = []  # Feedback collected during control phase

            # Execute steps
            for step_num in steps_to_execute:
                step = plan_steps[step_num - 1]

                # Check for cancellation
                manager.raise_if_cancelled()

                # Update manager's current step
                manager.current_step = step_num

                print(f"\n{'='*60}")
                print(f"STEP {step_num}/{len(plan_steps)}: {step.get('sub_task', 'Unknown')}")
                print(f"{'='*60}\n")

                # Before-step approval
                if self.config.approval_mode in ["before_step", "both"]:
                    approval_result = await self._request_step_approval(
                        approval_manager,
                        context,
                        step,
                        step_num,
                        "before_step",
                        current_context,
                        manager
                    )

                    if approval_result is None:  # Skip
                        skipped_steps.append(step_num)
                        print(f"-> Step {step_num} skipped by human\n")
                        continue
                    elif approval_result is False:  # Rejected
                        return manager.fail(f"Step {step_num} rejected by human", None)
                    elif isinstance(approval_result, dict):  # Approved with feedback
                        if 'feedback' in approval_result:
                            feedback = approval_result['feedback']
                            self._step_feedback.append({
                                'step': step_num,
                                'timing': 'before',
                                'feedback': feedback,
                            })
                            # Add to accumulated feedback
                            if self._accumulated_feedback:
                                self._accumulated_feedback += f"\n\n**Step {step_num} guidance:** {feedback}"
                            else:
                                self._accumulated_feedback = f"**Step {step_num} guidance:** {feedback}"
                            print(f"-> Human feedback for step {step_num}: {feedback}\n")
                    # else: True (approved without feedback)

                # Notify callbacks
                step_desc = step.get('sub_task', f'Step {step_num}')
                manager.start_step(step_num, step_desc)

                # Execute step
                success = False
                attempt = 0
                step_result = None
                step_error = None
                cmbagent = None

                while attempt < self.config.max_n_attempts and not success:
                    attempt += 1

                    try:
                        print(f"Executing step {step_num} (attempt {attempt}/{self.config.max_n_attempts})...")

                        # Determine starter agent (matches standard ControlPhase)
                        clear_work_dir = (step_num == 1)
                        starter_agent = "control" if step_num == 1 else "control_starter"

                        # Initialize fresh CMBAgent for each step (matches standard ControlPhase)
                        cmbagent = CMBAgent(
                            cache_seed=42,
                            work_dir=control_dir,
                            clear_work_dir=clear_work_dir,
                            agent_llm_configs=agent_llm_configs,
                            mode="planning_and_control_context_carryover",
                            api_keys=api_keys,
                        )

                        # Configure AG2 HITL handoffs (if enabled)
                        if self.config.use_ag2_handoffs:
                            from cmbagent.handoffs import register_all_hand_offs, enable_websocket_for_hitl

                            hitl_config = {
                                'mandatory_checkpoints': self.config.ag2_mandatory_checkpoints,
                                'smart_approval': self.config.ag2_smart_approval,
                                'smart_criteria': self.config.ag2_smart_criteria,
                            }

                            # Register handoffs with HITL config
                            register_all_hand_offs(cmbagent, hitl_config=hitl_config)
                            print(f"→ AG2 HITL handoffs enabled: {hitl_config}")

                            # Enable WebSocket for AG2 handoffs so they appear in UI
                            if approval_manager:
                                try:
                                    enable_websocket_for_hitl(cmbagent, approval_manager, context.run_id)
                                    print(f"→ AG2 WebSocket integration enabled ✓")
                                except Exception as e:
                                    print(f"⚠ Warning: Could not enable WebSocket for AG2 handoffs: {e}")
                                    import traceback
                                    traceback.print_exc()
                            else:
                                print(f"⚠ Warning: No approval_manager - AG2 handoffs will use console input")

                        # Get agent for this step
                        if step_num == 1 and plan_steps:
                            agent_for_step = plan_steps[0].get('sub_task_agent')
                        else:
                            agent_for_step = current_context.get('agent_for_sub_task')

                        # Prepare step context (matches standard ControlPhase)
                        step_shared_context = copy.deepcopy(current_context)
                        step_shared_context['current_plan_step_number'] = step_num
                        step_shared_context['n_attempts'] = attempt - 1
                        step_shared_context['agent_for_sub_task'] = agent_for_step
                        step_shared_context['engineer_append_instructions'] = self.config.engineer_instructions
                        step_shared_context['researcher_append_instructions'] = self.config.researcher_instructions

                        # Execute with control agent (use original task, not a custom one)
                        cmbagent.solve(
                            task=context.task,
                            initial_agent=starter_agent,
                            max_rounds=self.config.max_rounds,
                            shared_context=step_shared_context,
                            step=step_num,
                        )

                        # Check for failures (matches standard ControlPhase logic)
                        n_failures = cmbagent.final_context.get('n_attempts', 0)
                        if n_failures >= self.config.max_n_attempts:
                            success = False
                            step_error = f"Max attempts ({n_failures}) exceeded"
                        else:
                            success = True
                            step_result = cmbagent.final_context

                            # Extract step summary (matches standard ControlPhase)
                            this_step_summary = None
                            for msg in cmbagent.chat_result.chat_history[::-1]:
                                if 'name' in msg and agent_for_step:
                                    agent_clean = agent_for_step.removesuffix("_context").removesuffix("_agent")
                                    if msg['name'] in [agent_clean, f"{agent_clean}_nest", f"{agent_clean}_response_formatter"]:
                                        this_step_summary = msg['content']
                                        summary = f"### Step {step_num}\n{this_step_summary.strip()}"
                                        step_summaries.append(summary)
                                        cmbagent.final_context['previous_steps_execution_summary'] = "\n\n".join(
                                            s if isinstance(s, str) else str(s) for s in step_summaries
                                        )
                                        break

                            # Update context for next step
                            current_context = copy.deepcopy(cmbagent.final_context)

                        if success:
                            print(f"Step {step_num} completed successfully")
                        else:
                            print(f"Step {step_num} failed: {step_error}")

                    except Exception as e:
                        success = False
                        step_error = str(e)
                        print(f"Step {step_num} error: {step_error}")

                    # On error, ask for human intervention if configured
                    if not success and self.config.approval_mode in ["on_error", "both"]:
                        action = await self._request_error_handling(
                            approval_manager,
                            context,
                            step,
                            step_num,
                            step_error,
                            attempt,
                            manager
                        )

                        if action == "retry":
                            print(f"-> Retrying step {step_num}...")
                            continue
                        elif action == "skip":
                            print(f"-> Skipping step {step_num}")
                            skipped_steps.append(step_num)
                            success = True  # Treat as success to continue
                            break
                        elif action == "abort":
                            return manager.fail(f"Aborted by human at step {step_num}", None)

                # Check final success
                if not success:
                    manager.fail_step(step_num, step_error or "Max attempts exceeded")
                    return manager.fail(
                        f"Step {step_num} failed after {self.config.max_n_attempts} attempts",
                        step_error
                    )

                # After-step approval/review
                if self.config.approval_mode in ["after_step", "both"]:
                    if not (self.config.auto_approve_successful_steps and success):
                        review_result = await self._request_step_review(
                            approval_manager,
                            context,
                            step,
                            step_num,
                            step_result,
                            manager
                        )

                        if review_result is False:  # Abort
                            return manager.fail(f"Step {step_num} review rejected by human", None)
                        elif review_result is None:  # Redo
                            # Could implement redo logic here
                            pass
                        elif isinstance(review_result, dict):  # Continue with feedback
                            if 'feedback' in review_result:
                                feedback = review_result['feedback']
                                self._step_feedback.append({
                                    'step': step_num,
                                    'timing': 'after',
                                    'feedback': feedback,
                                })
                                # Add to accumulated feedback
                                if self._accumulated_feedback:
                                    self._accumulated_feedback += f"\n\n**Step {step_num} notes:** {feedback}"
                                else:
                                    self._accumulated_feedback = f"**Step {step_num} notes:** {feedback}"
                                print(f"-> Human notes for step {step_num}: {feedback}\n")

                # Record step result with chat history
                step_chat_history = []
                if cmbagent and hasattr(cmbagent, 'chat_result') and cmbagent.chat_result:
                    step_chat_history = cmbagent.chat_result.chat_history or []
                    all_chat_history.extend(step_chat_history)

                step_results.append({
                    'step': step_num,
                    'success': success,
                    'result': step_result,
                    'attempts': attempt,
                    'chat_history': step_chat_history,
                })

                # Save step context (filter non-picklable items)
                context_path = os.path.join(context_dir, f"context_step_{step_num}.pkl")
                
                # Filter out non-picklable items before saving
                filtered_context = {}
                for key, value in current_context.items():
                    if key.startswith('_'):
                        continue  # Skip private keys
                    try:
                        pickle.dumps(value)  # Test if picklable
                        filtered_context[key] = value
                    except (TypeError, pickle.PicklingError, AttributeError):
                        print(f"[HITL] Skipping non-picklable context key: {key}")
                
                with open(context_path, 'wb') as f:
                    pickle.dump(filtered_context, f)
                manager.track_file(context_path)

                # Save chat history
                chat_full_path = os.path.join(control_dir, "chats")
                os.makedirs(chat_full_path, exist_ok=True)
                chat_output_path = os.path.join(chat_full_path, f"chat_history_step_{step_num}.json")
                with open(chat_output_path, 'w') as f:
                    json.dump(step_chat_history, f, indent=2)
                manager.track_file(chat_output_path)

                # Display cost
                if cmbagent:
                    if not hasattr(cmbagent, 'groupchat'):
                        Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
                        cmbagent.groupchat = Dummy()
                    cmbagent.display_cost(name_append=f"step_{step_num}")

                manager.complete_step(step_num, "Step completed")

                print(f"\nStep {step_num} completed in control phase\n")

            # Save final context (filter non-picklable items)
            context_file = os.path.join(context.work_dir, 'final_context.pkl')
            
            # Filter out non-picklable items before saving
            filtered_final_context = {}
            for key, value in current_context.items():
                if key.startswith('_'):
                    continue
                try:
                    pickle.dumps(value)
                    filtered_final_context[key] = value
                except (TypeError, pickle.PicklingError, AttributeError):
                    print(f"[HITL] Skipping non-picklable final context key: {key}")
            
            with open(context_file, 'wb') as f:
                pickle.dump(filtered_final_context, f)

            manager.track_file(context_file)

            # Build output
            output_data = {
                'step_results': step_results,
                'final_context': current_context,
                'step_summaries': step_summaries,
                'human_interventions': human_interventions,
                'skipped_steps': skipped_steps,
                'step_feedback': self._step_feedback,
                'shared': {
                    'final_context': current_context,
                    'executed_steps': len(step_results),
                    'step_feedback': self._step_feedback,
                    'control_feedback': self._step_feedback,
                    'all_hitl_feedback': self._accumulated_feedback,
                    'execution_complete': True,
                }
            }

            self._status = PhaseStatus.COMPLETED

            return manager.complete(
                output_data=output_data,
                chat_history=all_chat_history,
            )

        except Exception as e:
            self._status = PhaseStatus.FAILED
            import traceback
            return manager.fail(str(e), traceback.format_exc())

    def validate_input(self, context: PhaseContext) -> List[str]:
        """Validate that required input is present."""
        errors = []
        if not context.task:
            errors.append("Task is required")
        if not context.work_dir:
            errors.append("Work directory is required")

        # Check for plan in both input_data and shared_state
        plan = (
            context.input_data.get('final_plan') or
            context.input_data.get('plan_steps') or
            context.shared_state.get('final_plan') or
            context.shared_state.get('plan_steps')
        )
        if not plan:
            errors.append("Plan is required (final_plan or plan_steps)")

        return errors

    def _extract_plan(self, context: PhaseContext) -> List[Dict]:
        """Extract plan from context."""
        # Try multiple keys in both input_data and shared_state
        for key in ['final_plan', 'plan_steps', 'plan']:
            plan = context.input_data.get(key) or context.shared_state.get(key)
            if plan and isinstance(plan, list):
                return plan
        return []

    async def _request_step_approval(
        self,
        approval_manager,
        context: PhaseContext,
        step: Dict,
        step_num: int,
        checkpoint_type: str,
        accumulated_context: Dict,
        manager: PhaseExecutionManager
    ) -> Optional[bool]:
        """
        Request human approval before executing a step.

        Returns:
            True: Approved
            False: Rejected
            None: Skipped
            dict: Approved with feedback
        """
        if not approval_manager:
            # Console fallback
            print(f"\n{'='*60}")
            print(f"STEP {step_num} APPROVAL")
            print(f"{'='*60}")
            print(f"Task: {step.get('sub_task')}")
            print(f"{'='*60}")
            response = input("\nApprove step? (y/n/s=skip): ").strip().lower()

            if response == 'y' or response == 'yes':
                return True
            elif response == 's' or response == 'skip':
                return None
            else:
                return False

        # Use approval manager
        message = self._build_step_approval_message(step, step_num, accumulated_context)

        approval_request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"{context.phase_id}_step_{step_num}",
            checkpoint_type=checkpoint_type,
            context_snapshot={
                'step': step,
                'step_num': step_num,
            },
            message=message,
            options=["approve", "reject", "skip"],
        )

        print(f"\n{'='*60}")
        print(f"STEP {step_num} APPROVAL REQUIRED")
        print(f"{'='*60}")
        print(message)
        print("\nWaiting for approval...")
        print(f"{'='*60}\n")

        resolved = await approval_manager.wait_for_approval_async(
            str(approval_request.id),
            timeout_seconds=1800,
        )

        # Accept both "approved" and "approve"
        if resolved.resolution in ["approved", "approve"]:
            # Check for feedback
            if hasattr(resolved, 'user_feedback') and resolved.user_feedback:
                return {'approved': True, 'feedback': resolved.user_feedback}
            return True
        elif resolved.resolution == "skip":
            return None
        else:
            return False

    async def _request_step_review(
        self,
        approval_manager,
        context: PhaseContext,
        step: Dict,
        step_num: int,
        step_result: Dict,
        manager: PhaseExecutionManager
    ) -> Optional[bool]:
        """Request human review after executing a step."""
        print(f"[_request_step_review] Called with approval_manager: {approval_manager}")
        print(f"[_request_step_review] approval_manager type: {type(approval_manager)}")

        if not approval_manager:
            print(f"[_request_step_review] No approval_manager - falling back to console input")
            print(f"\n{'='*60}")
            print(f"STEP {step_num} REVIEW")
            print(f"{'='*60}")
            print("Step completed successfully")
            print(f"{'='*60}")
            response = input("\nContinue? (y/n): ").strip().lower()
            return response == 'y' or response == 'yes'

        print(f"[_request_step_review] Using WebSocket approval manager")
        message = self._build_step_review_message(step, step_num, step_result)

        print(f"[_request_step_review] Creating approval request...")
        approval_request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"{context.phase_id}_step_{step_num}_review",
            checkpoint_type="after_step",
            context_snapshot={
                'step': step,
                'step_num': step_num,
                'result': step_result,
            },
            message=message,
            options=["continue", "abort", "redo"],
        )

        print(f"\n{'='*60}")
        print(f"STEP {step_num} REVIEW")
        print(f"{'='*60}")
        print(message)
        print("\nWaiting for review...")
        print(f"{'='*60}\n")

        resolved = await approval_manager.wait_for_approval_async(
            str(approval_request.id),
            timeout_seconds=1800,
        )

        if resolved.resolution == "continue":
            # Check for feedback
            if hasattr(resolved, 'user_feedback') and resolved.user_feedback:
                return {'continue': True, 'feedback': resolved.user_feedback}
            return True
        elif resolved.resolution == "redo":
            return None
        else:
            return False

    async def _request_error_handling(
        self,
        approval_manager,
        context: PhaseContext,
        step: Dict,
        step_num: int,
        error: str,
        attempt: int,
        manager: PhaseExecutionManager
    ) -> str:
        """
        Request human decision on how to handle an error.

        Returns:
            "retry": Retry the step
            "skip": Skip the step
            "abort": Abort the workflow
        """
        if not approval_manager:
            print(f"\n{'='*60}")
            print(f"STEP {step_num} ERROR (Attempt {attempt})")
            print(f"{'='*60}")
            print(f"Error: {error}")
            print(f"{'='*60}")
            response = input("\nHow to proceed? (r=retry/s=skip/a=abort): ").strip().lower()

            if response == 'r' or response == 'retry':
                return "retry"
            elif response == 's' or response == 'skip':
                return "skip"
            else:
                return "abort"

        message = self._build_error_handling_message(step, step_num, error, attempt)

        approval_request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"{context.phase_id}_step_{step_num}_error",
            checkpoint_type="on_error",
            context_snapshot={
                'step': step,
                'step_num': step_num,
                'error': error,
                'attempt': attempt,
            },
            message=message,
            options=["retry", "skip", "abort"],
        )

        print(f"\n{'='*60}")
        print(f"STEP {step_num} ERROR - HUMAN INTERVENTION REQUIRED")
        print(f"{'='*60}")
        print(message)
        print("\nWaiting for decision...")
        print(f"{'='*60}\n")

        resolved = await approval_manager.wait_for_approval_async(
            str(approval_request.id),
            timeout_seconds=1800,
        )

        return resolved.resolution

    def _build_step_approval_message(self, step: Dict, step_num: int, context: Dict) -> str:
        """Build message for step approval."""
        parts = [
            f"**Step {step_num}**",
            "",
            f"**Task:** {step.get('sub_task', 'Unknown')}",
            "",
        ]

        if self.config.show_step_context:
            parts.extend([
                "**Context:** Previous steps completed successfully",
                "",
            ])

        parts.extend([
            "**Options:**",
            "- **Approve**: Execute this step",
            "- **Skip**: Skip this step and continue",
            "- **Reject**: Cancel the workflow",
        ])

        return "\n".join(parts)

    def _build_step_review_message(self, step: Dict, step_num: int, result: Dict) -> str:
        """Build message for step review."""
        return f"""**Step {step_num} Review**

**Task:** {step.get('sub_task', 'Unknown')}

**Status:** Completed successfully

**Options:**
- **Continue**: Proceed to next step
- **Redo**: Re-execute this step
- **Abort**: Cancel the workflow
"""

    def _build_error_handling_message(self, step: Dict, step_num: int, error: str, attempt: int) -> str:
        """Build message for error handling."""
        return f"""**Step {step_num} Error**

**Task:** {step.get('sub_task', 'Unknown')}

**Attempt:** {attempt}/{self.config.max_n_attempts}

**Error:** {error}

**Options:**
- **Retry**: Attempt to execute the step again
- **Skip**: Skip this step and continue with the workflow
- **Abort**: Cancel the entire workflow
"""
