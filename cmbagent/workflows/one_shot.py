"""
One-shot and human-in-the-loop workflow functions for CMBAgent.
"""

import os
import json
import time
import uuid
import requests
import datetime
from typing import Optional

from cmbagent.utils import (
    work_dir_default,
    get_api_keys_from_env,
    get_model_config,
    default_agents_llm_model,
    camb_context_url,
    classy_context_url,
)
from cmbagent.utils import default_llm_model as default_llm_model_default
from cmbagent.utils import default_formatter_model as default_formatter_model_default
from cmbagent.context import shared_context as shared_context_default
from cmbagent.execution.output_collector import WorkflowOutputManager


def one_shot(
    task,
    max_rounds=50,
    max_n_attempts=3,
    engineer_model=default_agents_llm_model['engineer'],
    researcher_model=default_agents_llm_model['researcher'],
    web_surfer_model=default_agents_llm_model.get('web_surfer', default_agents_llm_model['researcher']),
    plot_judge_model=default_agents_llm_model['plot_judge'],
    camb_context_model=default_agents_llm_model['camb_context'],
    default_llm_model=default_llm_model_default,
    default_formatter_model=default_formatter_model_default,
    researcher_filename=shared_context_default['researcher_filename'],
    agent='engineer',
    work_dir=work_dir_default,
    api_keys=None,
    clear_work_dir=False,
    evaluate_plots=False,
    max_n_plot_evals=1,
    inject_wrong_plot: bool | str = False,
):
    """
    Execute a single-shot task with a specified agent.

    Args:
        task: The task description to execute
        max_rounds: Maximum conversation rounds
        max_n_attempts: Maximum attempts before failure
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
        web_surfer_model: Model for web_surfer agent
        plot_judge_model: Model for plot judge agent
        camb_context_model: Model for CAMB context agent
        default_llm_model: Default LLM model
        default_formatter_model: Default formatter model
        researcher_filename: Output filename for researcher
        agent: Which agent to use ('engineer', 'researcher', 'camb_context', etc.)
        work_dir: Working directory for outputs
        api_keys: API keys dictionary
        clear_work_dir: Whether to clear the work directory
        evaluate_plots: Whether to evaluate generated plots
        max_n_plot_evals: Maximum plot evaluation iterations
        inject_wrong_plot: Whether to inject wrong plot for testing

    Returns:
        Dictionary containing chat history, final context, and agent objects
    """
    from cmbagent.cmbagent import CMBAgent

    start_time = time.time()
    work_dir = os.path.abspath(os.path.expanduser(work_dir))

    # Initialize file tracking system
    run_id = str(uuid.uuid4())
    output_manager = WorkflowOutputManager(
        work_dir=work_dir,
        run_id=run_id
    )
    output_manager.set_phase("execution")
    output_manager.set_agent(agent)

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    engineer_config = get_model_config(engineer_model, api_keys)
    researcher_config = get_model_config(researcher_model, api_keys)
    web_surfer_config = get_model_config(web_surfer_model, api_keys)
    plot_judge_config = get_model_config(plot_judge_model, api_keys)
    camb_context_config = get_model_config(camb_context_model, api_keys)

    cmbagent = CMBAgent(
        cache_seed=42,
        mode="one_shot",
        work_dir=work_dir,
        agent_llm_configs={
            'engineer': engineer_config,
            'researcher': researcher_config,
            'web_surfer': web_surfer_config,
            'plot_judge': plot_judge_config,
            'camb_context': camb_context_config,
        },
        clear_work_dir=clear_work_dir,
        api_keys=api_keys,
        default_llm_model=default_llm_model,
        default_formatter_model=default_formatter_model,
    )

    end_time = time.time()
    initialization_time = end_time - start_time

    start_time = time.time()

    shared_context = {
        'max_n_attempts': max_n_attempts,
        'evaluate_plots': evaluate_plots,
        'max_n_plot_evals': max_n_plot_evals,
        'inject_wrong_plot': inject_wrong_plot
    }

    if agent == 'camb_context':
        resp = requests.get(camb_context_url, timeout=30)
        resp.raise_for_status()
        camb_context = resp.text
        shared_context["camb_context"] = camb_context

    if agent == 'classy_context':
        resp = requests.get(classy_context_url, timeout=30)
        resp.raise_for_status()
        classy_context = resp.text
        shared_context["classy_context"] = classy_context

    if researcher_filename is not None:
        shared_context["researcher_filename"] = researcher_filename

    cmbagent.solve(
        task,
        max_rounds=max_rounds,
        initial_agent=agent,
        mode="one_shot",
        shared_context=shared_context
    )

    end_time = time.time()
    execution_time = end_time - start_time

    if not hasattr(cmbagent, 'groupchat'):
        Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
        cmbagent.groupchat = Dummy()

    cmbagent.display_cost()

    results = {
        'chat_history': cmbagent.chat_result.chat_history,
        'final_context': cmbagent.final_context,
        'engineer': cmbagent.get_agent_object_from_name('engineer'),
        'engineer_response_formatter': cmbagent.get_agent_object_from_name('engineer_response_formatter'),
        'researcher': cmbagent.get_agent_object_from_name('researcher'),
        'researcher_response_formatter': cmbagent.get_agent_object_from_name('researcher_response_formatter'),
        'plot_judge': cmbagent.get_agent_object_from_name('plot_judge'),
        'plot_debugger': cmbagent.get_agent_object_from_name('plot_debugger')
    }

    results['initialization_time'] = initialization_time
    results['execution_time'] = execution_time

    timing_report = {
        'initialization_time': initialization_time,
        'execution_time': execution_time,
        'total_time': initialization_time + execution_time
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timing_path = os.path.join(work_dir, f"time/timing_report_{timestamp}.json")

    with open(timing_path, 'w') as f:
        json.dump(timing_report, f, indent=2)

    print("\nTiming report saved to", timing_path)
    print("\nTask took", f"{execution_time:.4f}", "seconds")

    # Collect and finalize file outputs
    try:
        workflow_outputs = output_manager.finalize(write_manifest=True)
        results['outputs'] = workflow_outputs.to_dict()
        results['run_id'] = run_id
        print(f"\nCollected {workflow_outputs.total_files} output files")
    except Exception as e:
        print(f"\nWarning: Could not collect outputs: {e}")
        results['outputs'] = None
        results['run_id'] = run_id

    # delete empty folders
    database_full_path = os.path.join(results['final_context']['work_dir'], results['final_context']['database_path'])
    codebase_full_path = os.path.join(results['final_context']['work_dir'], results['final_context']['codebase_path'])
    time_full_path = os.path.join(results['final_context']['work_dir'], 'time')
    for folder in [database_full_path, codebase_full_path, time_full_path]:
        try:
            if os.path.exists(folder) and not os.listdir(folder):
                os.rmdir(folder)
        except OSError:
            pass  # Folder not empty or doesn't exist

    return results


def human_in_the_loop(
    task,
    work_dir=work_dir_default,
    max_rounds=50,
    max_n_attempts=3,
    engineer_model='gpt-4o-2024-11-20',
    researcher_model='gpt-4o-2024-11-20',
    web_surfer_model='gpt-4o-2024-11-20',
    agent='engineer',
    api_keys=None,
):
    """
    Execute an interactive human-in-the-loop workflow.

    Args:
        task: The task description
        work_dir: Working directory for outputs
        max_rounds: Maximum conversation rounds
        max_n_attempts: Maximum attempts before failure
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent        web_surfer_model: Model for web_surfer agent        agent: Which agent to use
        api_keys: API keys dictionary

    Returns:
        Dictionary containing chat history, final context, and agent objects
    """
    from cmbagent.cmbagent import CMBAgent

    start_time = time.time()

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    engineer_config = get_model_config(engineer_model, api_keys)
    researcher_config = get_model_config(researcher_model, api_keys)
    web_surfer_config = get_model_config(web_surfer_model, api_keys)

    cmbagent = CMBAgent(
        cache_seed=42,
        work_dir=work_dir,
        agent_llm_configs={
            'engineer': engineer_config,
            'researcher': researcher_config,
            'web_surfer': web_surfer_config,
        },
        mode="chat",
        chat_agent=agent,
        api_keys=api_keys
    )

    end_time = time.time()
    initialization_time = end_time - start_time

    start_time = time.time()

    cmbagent.solve(
        task,
        max_rounds=max_rounds,
        initial_agent=agent,
        shared_context={'max_n_attempts': max_n_attempts},
        mode="chat"
    )

    end_time = time.time()
    execution_time = end_time - start_time

    results = {
        'chat_history': cmbagent.chat_result.chat_history,
        'final_context': cmbagent.final_context,
        'engineer': cmbagent.get_agent_object_from_name('engineer'),
        'engineer_nest': cmbagent.get_agent_object_from_name('engineer_nest'),
        'engineer_response_formatter': cmbagent.get_agent_object_from_name('engineer_response_formatter'),
        'researcher': cmbagent.get_agent_object_from_name('researcher'),
        'researcher_response_formatter': cmbagent.get_agent_object_from_name('researcher_response_formatter')
    }

    results['initialization_time'] = initialization_time
    results['execution_time'] = execution_time

    if not hasattr(cmbagent, 'groupchat'):
        Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
        cmbagent.groupchat = Dummy()

    cmbagent.display_cost()

    timing_report = {
        'initialization_time': initialization_time,
        'execution_time': execution_time,
        'total_time': initialization_time + execution_time
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timing_path = os.path.join(work_dir, f"timing_report_{timestamp}.json")
    with open(timing_path, 'w') as f:
        json.dump(timing_report, f, indent=2)

    return results
