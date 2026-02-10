"""
One-shot workflow implementation using phase-based architecture.
"""

import os
import uuid
from typing import Dict, Any

from cmbagent.utils import (
    work_dir_default,
    get_api_keys_from_env,
    default_agents_llm_model,
)
from cmbagent.utils import default_llm_model as default_llm_model_default
from cmbagent.utils import default_formatter_model as default_formatter_model_default
from cmbagent.context import shared_context as shared_context_default
from cmbagent.workflows.utils import clean_work_dir


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

    This workflow runs a single agent to complete the task without
    multi-step planning.

    Args:
        task: Task description
        max_rounds: Maximum conversation rounds
        max_n_attempts: Maximum retry attempts
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
        web_surfer_model: Model for web surfer agent
        plot_judge_model: Model for plot judge agent
        camb_context_model: Model for CAMB context agent
        default_llm_model: Default LLM model
        default_formatter_model: Default formatter model
        researcher_filename: Filename for researcher outputs
        agent: Agent to use ('engineer' or 'researcher')
        work_dir: Working directory
        api_keys: API keys dictionary
        clear_work_dir: Whether to clear work directory
        evaluate_plots: Whether to evaluate plots
        max_n_plot_evals: Maximum plot evaluations
        inject_wrong_plot: Whether to inject wrong plots for testing

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
    workflow = WorkflowDefinition(
        id=f"one_shot_{uuid.uuid4().hex[:8]}",
        name=f"One Shot ({agent})",
        description="One-shot workflow with single agent",
        phases=[{
            "type": "one_shot",
            "config": {
                "max_rounds": max_rounds,
                "max_n_attempts": max_n_attempts,
                "agent": agent,
                "engineer_model": engineer_model,
                "researcher_model": researcher_model,
                "web_surfer_model": web_surfer_model,
                "plot_judge_model": plot_judge_model,
                "camb_context_model": camb_context_model,
                "default_llm_model": default_llm_model,
                "default_formatter_model": default_formatter_model,
                "evaluate_plots": evaluate_plots,
                "max_n_plot_evals": max_n_plot_evals,
                "researcher_filename": researcher_filename,
            }
        }],
    )

    # Create executor
    executor = WorkflowExecutor(
        workflow=workflow,
        task=task,
        work_dir=work_dir,
        api_keys=api_keys,
    )

    # Run workflow
    print(f"\n{'=' * 60}")
    print(f"One Shot Workflow ({agent})")
    print(f"{'=' * 60}")
    print(f"Task: {task[:100]}...")
    print(f"{'=' * 60}\n")

    try:
        result = executor.run_sync()
        return _convert_workflow_result_to_legacy(result, executor)

    except Exception as e:
        print(f"\nWorkflow failed: {e}")
        import traceback
        traceback.print_exc()
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

    This workflow provides interactive chat mode with human-in-the-loop control.
    Uses legacy implementation (not yet migrated to phases).

    Args:
        task: The task description
        work_dir: Working directory for outputs
        max_rounds: Maximum conversation rounds
        max_n_attempts: Maximum attempts before failure
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
        web_surfer_model: Model for web_surfer agent
        agent: Which agent to use
        api_keys: API keys dictionary

    Returns:
        Dictionary containing chat history, final context, and agent objects
    """
    import time
    import json
    import datetime
    from cmbagent.cmbagent import CMBAgent
    from cmbagent.utils import get_model_config

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
