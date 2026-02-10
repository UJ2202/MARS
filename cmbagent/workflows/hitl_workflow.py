"""
HITL (Human-in-the-Loop) workflow implementation.

This module provides a complete HITL workflow where humans can:
1. Guide planning iteratively with feedback
2. Control execution step-by-step
3. Have feedback flow through all phases

Uses the HITLPlanningPhase and HITLControlPhase for complete interactive control.
"""

import os
from typing import Dict, Any, Optional

from cmbagent.utils import (
    work_dir_default,
    get_api_keys_from_env,
    default_agents_llm_model,
)
from cmbagent.utils import default_llm_model as default_llm_model_default
from cmbagent.utils import default_formatter_model as default_formatter_model_default
from cmbagent.workflows.utils import clean_work_dir


def hitl_interactive_workflow(
    task,
    max_rounds_planning=50,
    max_rounds_control=100,
    max_plan_steps=5,
    max_human_iterations=3,
    max_n_attempts=3,
    approval_mode="both",  # both, before_step, after_step, on_error
    allow_plan_modification=True,
    allow_step_skip=True,
    allow_step_retry=True,
    show_step_context=True,
    planner_model=default_agents_llm_model['planner'],
    engineer_model=default_agents_llm_model['engineer'],
    researcher_model=default_agents_llm_model['researcher'],
    default_llm_model=default_llm_model_default,
    default_formatter_model=default_formatter_model_default,
    work_dir=work_dir_default,
    api_keys=None,
    clear_work_dir=False,
    callbacks=None,
    approval_manager=None,
):
    """
    Execute a complete HITL workflow with interactive planning and control.

    This workflow provides maximum human control:
    1. HITLPlanningPhase: Iterative plan creation with human feedback
    2. HITLControlPhase: Step-by-step execution with approval/review

    Human feedback flows through both phases, creating persistent memory
    of guidance and corrections.

    Args:
        task: Task description
        max_rounds_planning: Max conversation rounds for planning
        max_rounds_control: Max conversation rounds for control
        max_plan_steps: Maximum number of steps in the plan
        max_human_iterations: Max iterations for plan refinement
        approval_mode: When to request approval - "both", "before_step", "after_step", "on_error"
        allow_plan_modification: Allow humans to directly edit plans
        allow_step_skip: Allow humans to skip steps
        allow_step_retry: Allow humans to retry failed steps
        show_step_context: Show accumulated context before each step
        planner_model: Model for planning phase
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
        default_llm_model: Default LLM model
        default_formatter_model: Default formatter model
        work_dir: Working directory for outputs
        api_keys: API keys dictionary
        clear_work_dir: Whether to clear work directory before starting
        callbacks: Workflow callbacks for events
        approval_manager: HITL approval manager instance

    Returns:
        Dictionary with workflow results including:
        - final_context: Complete workflow context
        - phase_timings: Timing for each phase
        - hitl_feedback: All human feedback collected
        - planning_feedback_history: Planning iteration feedback
        - step_feedback: Step-level interventions
    """
    from cmbagent.workflows.composer import WorkflowDefinition, WorkflowExecutor

    # Setup
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if clear_work_dir:
        clean_work_dir(work_dir)

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    # Define the HITL workflow
    workflow = WorkflowDefinition(
        id="hitl_interactive_custom",
        name="HITL Interactive Workflow",
        description="Complete human-in-the-loop workflow with iterative planning and step-by-step control",
        phases=[
            {
                "type": "hitl_planning",
                "config": {
                    "max_plan_steps": max_plan_steps,
                    "max_human_iterations": max_human_iterations,
                    "require_explicit_approval": True,
                    "allow_plan_modification": allow_plan_modification,
                    "show_intermediate_plans": True,
                    "planner_model": planner_model,
                    "max_rounds": max_rounds_planning,
                }
            },
            {
                "type": "hitl_control",
                "config": {
                    "approval_mode": approval_mode,
                    "allow_step_skip": allow_step_skip,
                    "allow_step_retry": allow_step_retry,
                    "show_step_context": show_step_context,
                    "max_n_attempts": max_n_attempts,
                    "engineer_model": engineer_model,
                    "researcher_model": researcher_model,
                    "max_rounds": max_rounds_control,
                }
            },
        ],
        is_system=False,
    )

    # Create executor
    executor = WorkflowExecutor(
        workflow=workflow,
        task=task,
        work_dir=work_dir,
        api_keys=api_keys,
        callbacks=callbacks,
        approval_manager=approval_manager,
    )

    # Execute workflow
    context = executor.run_sync()

    # Compile results
    results = {
        'final_context': context.to_dict(),
        'phase_timings': context.phase_timings,
        'work_dir': work_dir,
    }

    # Extract HITL feedback from context
    if hasattr(context, 'shared_state'):
        results['hitl_feedback'] = context.shared_state.get('all_hitl_feedback', '')
        results['planning_feedback_history'] = context.shared_state.get('planning_feedback_history', [])
        results['step_feedback'] = context.shared_state.get('step_feedback', [])

    return results


def hitl_planning_only_workflow(
    task,
    max_rounds_planning=50,
    max_rounds_control=100,
    max_plan_steps=5,
    max_human_iterations=3,
    allow_plan_modification=True,
    planner_model=default_agents_llm_model['planner'],
    engineer_model=default_agents_llm_model['engineer'],
    researcher_model=default_agents_llm_model['researcher'],
    default_llm_model=default_llm_model_default,
    default_formatter_model=default_formatter_model_default,
    work_dir=work_dir_default,
    api_keys=None,
    clear_work_dir=False,
    callbacks=None,
    approval_manager=None,
):
    """
    Execute workflow with HITL planning but autonomous control.

    Human guides planning iteratively, then execution runs autonomously
    with the human-approved plan.

    Args:
        Similar to hitl_interactive_workflow but execution is autonomous

    Returns:
        Dictionary with workflow results
    """
    from cmbagent.workflows.composer import WorkflowDefinition, WorkflowExecutor

    # Setup
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if clear_work_dir:
        clean_work_dir(work_dir)

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    # Define workflow: HITL planning + autonomous control
    workflow = WorkflowDefinition(
        id="hitl_planning_autonomous_control",
        name="HITL Planning + Autonomous Control",
        description="Interactive planning with human feedback, then autonomous execution",
        phases=[
            {
                "type": "hitl_planning",
                "config": {
                    "max_plan_steps": max_plan_steps,
                    "max_human_iterations": max_human_iterations,
                    "require_explicit_approval": True,
                    "allow_plan_modification": allow_plan_modification,
                    "show_intermediate_plans": True,
                    "planner_model": planner_model,
                    "max_rounds": max_rounds_planning,
                }
            },
            {
                "type": "control",
                "config": {
                    "execute_all_steps": True,
                    "engineer_model": engineer_model,
                    "researcher_model": researcher_model,
                    "max_rounds": max_rounds_control,
                }
            },
        ],
        is_system=False,
    )

    # Create executor
    executor = WorkflowExecutor(
        workflow=workflow,
        task=task,
        work_dir=work_dir,
        api_keys=api_keys,
        callbacks=callbacks,
        approval_manager=approval_manager,
    )

    # Execute workflow
    context = executor.run_sync()

    # Compile results
    results = {
        'final_context': context.to_dict(),
        'phase_timings': context.phase_timings,
        'work_dir': work_dir,
    }

    # Extract HITL feedback from context
    if hasattr(context, 'shared_state'):
        results['hitl_feedback'] = context.shared_state.get('hitl_feedback', '')
        results['planning_feedback_history'] = context.shared_state.get('planning_feedback_history', [])

    return results


def hitl_error_recovery_workflow(
    task,
    max_rounds_planning=50,
    max_rounds_control=100,
    max_plan_steps=4,
    n_plan_reviews=1,
    max_n_attempts=3,
    allow_step_retry=True,
    allow_step_skip=True,
    planner_model=default_agents_llm_model['planner'],
    plan_reviewer_model=default_agents_llm_model['plan_reviewer'],
    engineer_model=default_agents_llm_model['engineer'],
    researcher_model=default_agents_llm_model['researcher'],
    default_llm_model=default_llm_model_default,
    default_formatter_model=default_formatter_model_default,
    work_dir=work_dir_default,
    api_keys=None,
    clear_work_dir=False,
    callbacks=None,
    approval_manager=None,
):
    """
    Execute workflow with autonomous execution but HITL error recovery.

    Execution runs autonomously until an error occurs, then human can
    intervene to retry, skip, or abort.

    Args:
        Similar to hitl_interactive_workflow but only intervenes on errors

    Returns:
        Dictionary with workflow results
    """
    from cmbagent.workflows.composer import WorkflowDefinition, WorkflowExecutor

    # Setup
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if clear_work_dir:
        clean_work_dir(work_dir)

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    # Define workflow: Autonomous planning + HITL error recovery
    workflow = WorkflowDefinition(
        id="hitl_error_recovery",
        name="Autonomous with HITL Error Recovery",
        description="Autonomous execution with human intervention only when errors occur",
        phases=[
            {
                "type": "planning",
                "config": {
                    "max_plan_steps": max_plan_steps,
                    "n_plan_reviews": n_plan_reviews,
                    "planner_model": planner_model,
                    "plan_reviewer_model": plan_reviewer_model,
                    "max_rounds": max_rounds_planning,
                }
            },
            {
                "type": "hitl_control",
                "config": {
                    "approval_mode": "on_error",
                    "allow_step_retry": allow_step_retry,
                    "allow_step_skip": allow_step_skip,
                    "max_n_attempts": max_n_attempts,
                    "engineer_model": engineer_model,
                    "researcher_model": researcher_model,
                    "max_rounds": max_rounds_control,
                }
            },
        ],
        is_system=False,
    )

    # Create executor
    executor = WorkflowExecutor(
        workflow=workflow,
        task=task,
        work_dir=work_dir,
        api_keys=api_keys,
        callbacks=callbacks,
        approval_manager=approval_manager,
    )

    # Execute workflow
    context = executor.run_sync()

    # Compile results
    results = {
        'final_context': context.to_dict(),
        'phase_timings': context.phase_timings,
        'work_dir': work_dir,
    }

    # Extract HITL feedback from context
    if hasattr(context, 'shared_state'):
        results['step_feedback'] = context.shared_state.get('step_feedback', [])

    return results
