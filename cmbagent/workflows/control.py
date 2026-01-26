"""
Control workflow function for CMBAgent.
"""

import os
import json
import time
import datetime

from cmbagent.utils import (
    work_dir_default,
    get_api_keys_from_env,
    get_model_config,
    default_agents_llm_model,
)
from cmbagent.workflows.utils import load_plan


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
        task: The task description
        plan: Path to the plan JSON file (defaults to plans/idea_plan.json)
        max_rounds: Maximum conversation rounds
        max_plan_steps: Maximum steps in plan
        n_plan_reviews: Number of plan review iterations
        plan_instructions: Additional planner instructions
        engineer_instructions: Additional engineer instructions
        researcher_instructions: Additional researcher instructions
        hardware_constraints: Hardware constraints to consider
        max_n_attempts: Maximum attempts before failure
        planner_model: Model for planner agent
        plan_reviewer_model: Model for plan reviewer agent
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
        web_surfer_model: Model for web_surfer agent
        retrieve_assistant_model: Model for retrieve_assistant agent
        idea_maker_model: Model for idea maker agent
        idea_hater_model: Model for idea hater agent
        plot_judge_model: Model for plot judge agent
        work_dir: Working directory for outputs
        clear_work_dir: Whether to clear the work directory
        api_keys: API keys dictionary

    Returns:
        Dictionary containing chat history and final context
    """
    from cmbagent.cmbagent import CMBAgent

    # Set default plan path if not provided
    if plan is None:
        plan = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'plans', 'idea_plan.json')

    # check work_dir exists
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    planning_input = load_plan(plan)["sub_tasks"]

    context = {
        'final_plan': planning_input,
        "number_of_steps_in_plan": len(planning_input),
        "agent_for_sub_task": planning_input[0]['sub_task_agent'],
        "current_sub_task": planning_input[0]['sub_task'],
        "current_instructions": ''
    }
    for bullet in planning_input[0]['bullet_points']:
        context["current_instructions"] += f"\t\t- {bullet}\n"

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    # control
    engineer_config = get_model_config(engineer_model, api_keys)
    researcher_config = get_model_config(researcher_model, api_keys)
    web_surfer_config = get_model_config(web_surfer_model, api_keys)
    retrieve_assistant_config = get_model_config(retrieve_assistant_model, api_keys)
    idea_maker_config = get_model_config(idea_maker_model, api_keys)
    idea_hater_config = get_model_config(idea_hater_model, api_keys)
    plot_judge_config = get_model_config(plot_judge_model, api_keys)
    control_dir = os.path.join(os.path.expanduser(work_dir), "control")
    os.makedirs(control_dir, exist_ok=True)

    start_time = time.time()
    cmbagent = CMBAgent(
        cache_seed=42,
        work_dir=control_dir,
        agent_llm_configs={
            'engineer': engineer_config,
            'researcher': researcher_config,
            'web_surfer': web_surfer_config,
            'retrieve_assistant': retrieve_assistant_config,
            'idea_maker': idea_maker_config,
            'idea_hater': idea_hater_config,
            'plot_judge': plot_judge_config,
        },
        clear_work_dir=clear_work_dir,
        api_keys=api_keys
    )

    end_time = time.time()
    initialization_time_control = end_time - start_time

    start_time = time.time()
    cmbagent.solve(
        task,
        max_rounds=max_rounds,
        initial_agent="control",
        shared_context=context
    )
    end_time = time.time()
    execution_time_control = end_time - start_time

    results = {
        'chat_history': cmbagent.chat_result.chat_history,
        'final_context': cmbagent.final_context
    }

    results['initialization_time_control'] = initialization_time_control
    results['execution_time_control'] = execution_time_control

    # Save timing report as JSON
    timing_report = {
        'initialization_time_control': initialization_time_control,
        'execution_time_control': execution_time_control,
        'total_time': initialization_time_control + execution_time_control
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timing_path = os.path.join(results['final_context']['work_dir'], f"time/timing_report_control_{timestamp}.json")
    with open(timing_path, 'w') as f:
        json.dump(timing_report, f, indent=2)

    # Create a dummy groupchat attribute if it doesn't exist
    if not hasattr(cmbagent, 'groupchat'):
        Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
        cmbagent.groupchat = Dummy()

    cmbagent.display_cost()

    # delete empty folders
    database_full_path = os.path.join(results['final_context']['work_dir'], results['final_context']['database_path'])
    codebase_full_path = os.path.join(results['final_context']['work_dir'], results['final_context']['codebase_path'])
    time_full_path = os.path.join(results['final_context']['work_dir'], 'time')
    for folder in [database_full_path, codebase_full_path, time_full_path]:
        if not os.listdir(folder):
            os.rmdir(folder)

    return results
