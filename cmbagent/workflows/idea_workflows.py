"""
Idea generation and idea-to-execution workflows using phase-based architecture.
"""

import os
import uuid
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

from cmbagent.utils import (
    work_dir_default,
    get_api_keys_from_env,
    default_agents_llm_model,
)
from cmbagent.workflows.utils import clean_work_dir


def idea_generation(
    task,
    max_rounds=50,
    n_ideas=3,
    n_reviews=1,
    idea_maker_model=default_agents_llm_model['idea_maker'],
    idea_hater_model=default_agents_llm_model['idea_hater'],
    work_dir=work_dir_default,
    api_keys=None,
    clear_work_dir=False,
    hitl_after_ideas=True,
):
    """
    Generate and review research ideas using maker/hater dynamics.

    Args:
        task: Research topic or problem to generate ideas for
        max_rounds: Maximum conversation rounds
        n_ideas: Number of ideas to generate
        n_reviews: Number of review iterations
        idea_maker_model: Model for idea maker agent
        idea_hater_model: Model for idea hater/critic agent
        work_dir: Working directory for outputs
        api_keys: API keys dictionary
        clear_work_dir: Whether to clear the work directory
        hitl_after_ideas: If True, adds HITL checkpoint for idea selection

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

    # Build workflow definition
    phases = [{
        "type": "idea_generation",
        "config": {
            "max_rounds": max_rounds,
            "n_ideas": n_ideas,
            "n_reviews": n_reviews,
            "idea_maker_model": idea_maker_model,
            "idea_hater_model": idea_hater_model,
        }
    }]

    if hitl_after_ideas:
        phases.append({
            "type": "hitl_checkpoint",
            "config": {
                "checkpoint_type": "custom",
                "custom_message": "Ideas generated. Select an idea to pursue.",
                "require_approval": True,
            }
        })

    workflow = WorkflowDefinition(
        id=f"idea_generation_{uuid.uuid4().hex[:8]}",
        name="Idea Generation",
        description="Idea generation workflow",
        phases=phases,
    )

    # Create executor
    executor = WorkflowExecutor(
        workflow=workflow,
        task=task,
        work_dir=work_dir,
        api_keys=api_keys,
    )

    # Run workflow
    logger.info(
        "Idea Generation Workflow | Task: %s | Generating %s ideas with %s review rounds",
        task[:100], n_ideas, n_reviews,
    )

    try:
        result = executor.run_sync()
        return _convert_workflow_result_to_legacy(result, executor)

    except Exception as e:
        logger.error("Workflow failed: %s", e, exc_info=True)
        raise


def idea_to_execution(
    task,
    # Idea generation params
    n_ideas=3,
    n_reviews=1,
    idea_maker_model=default_agents_llm_model['idea_maker'],
    idea_hater_model=default_agents_llm_model['idea_hater'],
    # Planning params
    max_rounds_planning=50,
    max_plan_steps=5,
    n_plan_reviews=1,
    planner_model=default_agents_llm_model['planner'],
    plan_reviewer_model=default_agents_llm_model['plan_reviewer'],
    plan_instructions='',
    # Control params
    max_rounds_control=100,
    max_n_attempts=3,
    engineer_model=default_agents_llm_model['engineer'],
    researcher_model=default_agents_llm_model['researcher'],
    engineer_instructions='',
    researcher_instructions='',
    # General params
    work_dir=work_dir_default,
    api_keys=None,
    clear_work_dir=False,
    hitl_enabled=True,
):
    """
    Full idea-to-execution pipeline: Generate ideas → Select idea → Plan → Execute

    Args:
        task: Research topic or problem
        n_ideas: Number of ideas to generate
        n_reviews: Number of idea review iterations
        idea_maker_model: Model for idea maker
        idea_hater_model: Model for idea critic
        max_rounds_planning: Max rounds for planning
        max_plan_steps: Max steps in plan
        n_plan_reviews: Number of plan reviews
        planner_model: Model for planner
        plan_reviewer_model: Model for plan reviewer
        plan_instructions: Additional planner instructions
        max_rounds_control: Max rounds per control step
        max_n_attempts: Max attempts per step
        engineer_model: Model for engineer
        researcher_model: Model for researcher
        engineer_instructions: Additional engineer instructions
        researcher_instructions: Additional researcher instructions
        work_dir: Working directory
        api_keys: API keys
        clear_work_dir: Clear work directory first
        hitl_enabled: Enable HITL checkpoints

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

    # Build full workflow
    phases = [
        # Phase 1: Idea Generation
        {
            "type": "idea_generation",
            "config": {
                "n_ideas": n_ideas,
                "n_reviews": n_reviews,
                "idea_maker_model": idea_maker_model,
                "idea_hater_model": idea_hater_model,
            }
        },
    ]

    if hitl_enabled:
        # Phase 2: HITL - Select idea
        phases.append({
            "type": "hitl_checkpoint",
            "config": {
                "checkpoint_type": "custom",
                "custom_message": "Select an idea to develop",
                "require_approval": True,
            }
        })

    # Phase 3: Planning
    phases.append({
        "type": "planning",
        "config": {
            "max_rounds": max_rounds_planning,
            "max_plan_steps": max_plan_steps,
            "n_plan_reviews": n_plan_reviews,
            "planner_model": planner_model,
            "plan_reviewer_model": plan_reviewer_model,
            "plan_instructions": plan_instructions,
        }
    })

    if hitl_enabled:
        # Phase 4: HITL - Approve plan
        phases.append({
            "type": "hitl_checkpoint",
            "config": {
                "checkpoint_type": "after_planning",
                "require_approval": True,
            }
        })

    # Phase 5: Control/Execution
    phases.append({
        "type": "control",
        "config": {
            "max_rounds": max_rounds_control,
            "max_n_attempts": max_n_attempts,
            "execute_all_steps": True,
            "engineer_model": engineer_model,
            "researcher_model": researcher_model,
            "engineer_instructions": engineer_instructions,
            "researcher_instructions": researcher_instructions,
        }
    })

    workflow = WorkflowDefinition(
        id=f"idea_to_execution_{uuid.uuid4().hex[:8]}",
        name="Idea to Execution",
        description="Full pipeline: Ideas → Plan → Execute",
        phases=phases,
    )

    # Create executor
    executor = WorkflowExecutor(
        workflow=workflow,
        task=task,
        work_dir=work_dir,
        api_keys=api_keys,
    )

    # Run workflow
    logger.info(
        "Idea to Execution Workflow | Task: %s | Pipeline: %s",
        task[:100], ' -> '.join(p['type'] for p in phases),
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

    return result
