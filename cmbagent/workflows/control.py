"""
Control workflow implementation using phase-based architecture.
"""

import os
import uuid
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

from cmbagent.utils import (
    work_dir_default,
    get_api_keys_from_env,
    default_agents_llm_model,
)
from cmbagent.workflows.utils import clean_work_dir


def control(
    task,
    plan=None,
    max_rounds=100,
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
    plot_judge_model=default_agents_llm_model['plot_judge'],
    work_dir=work_dir_default,
    clear_work_dir=True,
    api_keys=None,
):
    """
    Execute a control workflow from an existing plan.

    This function executes the control phase using a pre-existing plan file,
    bypassing the planning phase.

    Args:
        task: Task description
        plan: Path to plan file (JSON) or None to use default
        max_rounds: Maximum conversation rounds for control
        max_plan_steps: Maximum steps in plan (not used but kept for compatibility)
        n_plan_reviews: Number of reviews (not used but kept for compatibility)
        plan_instructions: Plan instructions (not used but kept for compatibility)
        engineer_instructions: Instructions for engineer agent
        researcher_instructions: Instructions for researcher agent
        hardware_constraints: Hardware constraints (not used but kept for compatibility)
        max_n_attempts: Maximum retry attempts
        *_model: Model configurations for different agents
        work_dir: Working directory
        clear_work_dir: Whether to clear work directory
        api_keys: API keys dictionary

    Returns:
        Dictionary with chat_history, final_context, and timing info
    """
    from cmbagent.workflows.composer import WorkflowDefinition, WorkflowExecutor
    from cmbagent.workflows.utils import load_plan as load_plan_file

    # Setup
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if clear_work_dir:
        clean_work_dir(work_dir)

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    # Load plan if path provided
    if plan is None:
        plan = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'plans', 'idea_plan.json')

    plan_data = load_plan_file(plan)
    plan_steps = plan_data.get("sub_tasks", [])

    # Build workflow definition
    workflow = WorkflowDefinition(
        id=f"control_{uuid.uuid4().hex[:8]}",
        name="Control Only",
        description="Control-only workflow from existing plan",
        phases=[{
            "type": "control",
            "config": {
                "max_rounds": max_rounds,
                "max_n_attempts": max_n_attempts,
                "execute_all_steps": True,
                "engineer_model": engineer_model,
                "researcher_model": researcher_model,
                "web_surfer_model": web_surfer_model,
                "retrieve_assistant_model": retrieve_assistant_model,
                "idea_maker_model": idea_maker_model,
                "idea_hater_model": idea_hater_model,
                "plot_judge_model": plot_judge_model,
                "engineer_instructions": engineer_instructions,
                "researcher_instructions": researcher_instructions,
            }
        }],
    )

    # Create executor with pre-loaded plan
    executor = WorkflowExecutor(
        workflow=workflow,
        task=task,
        work_dir=work_dir,
        api_keys=api_keys,
    )

    # Inject plan into context
    executor.context.plan = plan_steps
    executor.context.total_steps = len(plan_steps)
    executor.context.agent_state = {
        'final_plan': plan_steps,
        'number_of_steps_in_plan': len(plan_steps),
        'agent_for_sub_task': plan_steps[0].get('sub_task_agent') if plan_steps else None,
        'current_sub_task': plan_steps[0].get('sub_task') if plan_steps else None,
    }

    # Also set in the phase context
    executor.phases[0].config.params['preloaded_plan'] = plan_steps

    # Run workflow
    logger.info(
        "Control Only Workflow | Task: %s | Plan steps: %s",
        task[:100], len(plan_steps),
    )

    try:
        result = executor.run_sync()
        return _convert_workflow_result_to_legacy(result, executor)

    except Exception as e:
        logger.error("Workflow failed: %s", e, exc_info=True)
        raise


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
        if 'control' in phase_id:
            result['execution_time_control'] = timing

    return result
