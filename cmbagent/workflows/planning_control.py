"""
Planning and control workflow implementations using phase-based architecture.
"""

import os
import uuid
from typing import Dict, Any, Optional

from cmbagent.utils import (
    work_dir_default,
    get_api_keys_from_env,
    default_agents_llm_model,
)
from cmbagent.utils import default_llm_model as default_llm_model_default
from cmbagent.utils import default_formatter_model as default_formatter_model_default
from cmbagent.context import shared_context as shared_context_default
from cmbagent.workflows.utils import clean_work_dir


def planning_and_control_context_carryover(
    task,
    max_rounds_planning=50,
    max_rounds_control=100,
    max_plan_steps=3,
    n_plan_reviews=1,
    plan_instructions='',
    engineer_instructions='',
    researcher_instructions='',
    hardware_constraints='',
    max_n_attempts=3,
    planner_model=default_agents_llm_model['planner'],
    plan_reviewer_model=default_agents_llm_model['plan_reviewer'],
    engineer_model=default_agents_llm_model['engineer'],
    researcher_model=default_agents_llm_model['researcher'],
    web_surfer_model=default_agents_llm_model.get('web_surfer', default_agents_llm_model['researcher']),
    retrieve_assistant_model=default_agents_llm_model.get('retrieve_assistant', default_agents_llm_model['researcher']),
    idea_maker_model=default_agents_llm_model['idea_maker'],
    idea_hater_model=default_agents_llm_model['idea_hater'],
    camb_context_model=default_agents_llm_model['camb_context'],
    plot_judge_model=default_agents_llm_model['plot_judge'],
    default_llm_model=default_llm_model_default,
    default_formatter_model=default_formatter_model_default,
    work_dir=work_dir_default,
    api_keys=None,
    restart_at_step=-1,
    clear_work_dir=False,
    researcher_filename=shared_context_default['researcher_filename'],
    approval_config=None,
    callbacks=None,
    hitl_after_planning=False,
):
    """
    Execute planning and control workflow with context carryover.

    This workflow:
    1. Planning phase: Creates an execution plan
    2. (Optional) HITL checkpoint: Review and approve the plan
    3. Control phase: Executes the plan step by step

    Args:
        task: Task description
        max_rounds_planning: Max conversation rounds for planning
        max_rounds_control: Max conversation rounds for control
        max_plan_steps: Maximum number of steps in the plan
        n_plan_reviews: Number of plan review iterations
        plan_instructions: Specific instructions for the planner
        engineer_instructions: Instructions for the engineer agent
        researcher_instructions: Instructions for the researcher agent
        hardware_constraints: Hardware constraints description
        max_n_attempts: Maximum retry attempts per step
        *_model: Model configurations for different agents
        work_dir: Working directory for outputs
        api_keys: API keys dictionary
        restart_at_step: Step number to restart from (-1 for fresh start)
        clear_work_dir: Whether to clear work directory before starting
        researcher_filename: Filename for researcher outputs
        approval_config: HITL approval configuration
        callbacks: Workflow callbacks for events
        hitl_after_planning: Add HITL checkpoint after planning

    Returns:
        Dictionary with chat_history, final_context, and timing info
    """
    from cmbagent.workflows.composer import WorkflowDefinition, WorkflowExecutor

    # Setup
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if clear_work_dir:
        clean_work_dir(work_dir)

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    # Determine if HITL is needed
    needs_hitl = hitl_after_planning
    if approval_config is not None:
        from cmbagent.database.approval_types import ApprovalMode
        needs_hitl = approval_config.mode != ApprovalMode.NONE

    # Build workflow definition dynamically
    phases = []

    # Planning phase (skip if restarting)
    if restart_at_step <= 0:
        phases.append({
            "type": "planning",
            "config": {
                "max_rounds": max_rounds_planning,
                "max_plan_steps": max_plan_steps,
                "n_plan_reviews": n_plan_reviews,
                "planner_model": planner_model,
                "plan_reviewer_model": plan_reviewer_model,
                "plan_instructions": plan_instructions,
                "hardware_constraints": hardware_constraints,
                "engineer_instructions": engineer_instructions,
                "researcher_instructions": researcher_instructions,
                "max_n_attempts": max_n_attempts,
            }
        })

        # HITL checkpoint after planning (if enabled)
        if needs_hitl:
            phases.append({
                "type": "hitl_checkpoint",
                "config": {
                    "checkpoint_type": "after_planning",
                    "require_approval": True,
                    "show_plan": True,
                }
            })

    # Control phase
    phases.append({
        "type": "control",
        "config": {
            "max_rounds": max_rounds_control,
            "max_n_attempts": max_n_attempts,
            "execute_all_steps": True,
            "engineer_model": engineer_model,
            "researcher_model": researcher_model,
            "web_surfer_model": web_surfer_model,
            "retrieve_assistant_model": retrieve_assistant_model,
            "idea_maker_model": idea_maker_model,
            "idea_hater_model": idea_hater_model,
            "camb_context_model": camb_context_model,
            "plot_judge_model": plot_judge_model,
            "engineer_instructions": engineer_instructions,
            "researcher_instructions": researcher_instructions,
        }
    })

    # Create workflow definition
    workflow = WorkflowDefinition(
        id=f"planning_control_{uuid.uuid4().hex[:8]}",
        name="Planning and Control",
        description="Planning and control workflow with phase-based architecture",
        phases=phases,
    )

    # Create executor
    executor = WorkflowExecutor(
        workflow=workflow,
        task=task,
        work_dir=work_dir,
        api_keys=api_keys,
        callbacks=callbacks,
        approval_manager=_get_approval_manager(approval_config) if approval_config else None,
    )

    # Handle restart case - load existing context
    if restart_at_step > 0:
        context_path = os.path.join(work_dir, "context", f"context_step_{restart_at_step - 1}.pkl")
        if os.path.exists(context_path):
            from cmbagent.workflows.utils import load_context
            loaded_context = load_context(context_path)
            executor.context.plan = loaded_context.get('final_plan')
            executor.context.current_step = restart_at_step - 1
            executor.context.agent_state = loaded_context

    # Run workflow
    print(f"\n{'=' * 60}")
    print("Planning and Control Workflow")
    print(f"{'=' * 60}")
    print(f"Task: {task[:100]}...")
    print(f"Phases: {[p['type'] for p in phases]}")
    print(f"{'=' * 60}\n")

    try:
        result = executor.run_sync()
        return _convert_workflow_result_to_legacy(result, executor)

    except Exception as e:
        print(f"\nWorkflow failed: {e}")
        import traceback
        traceback.print_exc()
        raise


# Alias
deep_research = planning_and_control_context_carryover


def _get_approval_manager(approval_config):
    """Get approval manager from config if available."""
    try:
        from cmbagent.database.approval_manager import ApprovalManager
        return ApprovalManager(approval_config)
    except ImportError:
        return None


def _convert_workflow_result_to_legacy(workflow_context, executor) -> Dict[str, Any]:
    """
    Convert WorkflowContext result to legacy format.

    The legacy functions return a dictionary with chat_history, final_context,
    and timing information. This function converts the new format to match.
    """
    # Collect all chat history from phases
    all_chat_history = []
    for result in executor.results:
        all_chat_history.extend(result.chat_history)

    # Get final context from last phase
    final_context = {}
    if executor.results:
        last_result = executor.results[-1]
        final_context = last_result.context.output_data.get('final_context', {})
        if not final_context:
            final_context = last_result.context.output_data.get('result', {})
        if not final_context:
            final_context = last_result.context.shared_state.get('final_context', {})

    # Build legacy result format
    result = {
        'chat_history': all_chat_history,
        'final_context': final_context,
        'run_id': workflow_context.run_id,
        'workflow_id': workflow_context.workflow_id,
        'phase_timings': workflow_context.phase_timings,
    }

    # Add individual timing fields for compatibility
    total_time = workflow_context.phase_timings.get('total', 0)
    result['total_time'] = total_time

    # Extract phase-specific timings
    for phase_id, timing in workflow_context.phase_timings.items():
        if 'planning' in phase_id:
            result['execution_time_planning'] = timing
        elif 'control' in phase_id:
            result['execution_time_control'] = timing

    return result
