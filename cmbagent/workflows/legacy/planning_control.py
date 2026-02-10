"""
Planning and control workflow functions for CMBAgent.

This module provides the main planning and control workflow orchestration functions.
"""

import os
import json
import copy
import time
import pickle
import datetime
import re
import uuid
import pandas as pd
from typing import Dict, Any, Optional

from cmbagent.utils import (
    work_dir_default,
    get_api_keys_from_env,
    get_model_config,
    default_agents_llm_model,
)
from cmbagent.utils import default_llm_model as default_llm_model_default
from cmbagent.utils import default_formatter_model as default_formatter_model_default
from cmbagent.context import shared_context as shared_context_default
from cmbagent.agents.planner_response_formatter.planner_response_formatter import save_final_plan
from cmbagent.workflows.utils import clean_work_dir, load_context, load_plan
from cmbagent.execution.output_collector import WorkflowOutputManager


def planning_and_control_context_carryover(
    task,
    max_rounds_planning=50,
    max_rounds_control=100,
    max_plan_steps=3,
    n_plan_reviews=1,
    plan_instructions='',
    engineer_instructions='',  # append to engineer instructions
    researcher_instructions='',  # append to researcher instructions
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
    restart_at_step=-1,  # if -1 or 0, do not restart. if 1, restart from step 1, etc.
    clear_work_dir=False,
    researcher_filename=shared_context_default['researcher_filename'],
    approval_config=None,  # Optional ApprovalConfig for HITL control
    callbacks=None,  # Optional WorkflowCallbacks for event tracking
):
    """
    Execute planning and control workflow with context carryover between steps.

    This is the main deep research workflow that:
    1. Plans the task into sub-steps
    2. Executes each step with context carried over from previous steps
    3. Supports restart from a specific step if needed
    4. Provides callbacks for workflow events

    Args:
        task: The task description to execute
        max_rounds_planning: Maximum rounds for planning phase
        max_rounds_control: Maximum rounds for each control step
        max_plan_steps: Maximum number of steps in the plan
        n_plan_reviews: Number of plan review iterations
        plan_instructions: Additional instructions for the planner
        engineer_instructions: Additional instructions for the engineer
        researcher_instructions: Additional instructions for the researcher
        hardware_constraints: Hardware constraints to consider
        max_n_attempts: Maximum attempts per step before failure
        planner_model: Model to use for planner agent
        plan_reviewer_model: Model to use for plan reviewer agent
        engineer_model: Model to use for engineer agent
        researcher_model: Model to use for researcher agent
        web_surfer_model: Model to use for web_surfer agent
        retrieve_assistant_model: Model to use for retrieve_assistant agent
        idea_maker_model: Model to use for idea maker agent
        idea_hater_model: Model to use for idea hater agent
        camb_context_model: Model to use for CAMB context agent
        plot_judge_model: Model to use for plot judge agent
        default_llm_model: Default LLM model
        default_formatter_model: Default formatter model
        work_dir: Working directory for outputs
        api_keys: API keys dictionary
        restart_at_step: Step to restart from (-1 or 0 for no restart)
        clear_work_dir: Whether to clear the work directory
        researcher_filename: Filename for researcher output
        approval_config: Optional ApprovalConfig for HITL control
        callbacks: Optional WorkflowCallbacks for event tracking

    Returns:
        Dictionary containing chat history and final context
    """
    # Late import to avoid circular dependency
    from cmbagent.cmbagent import CMBAgent
    from cmbagent.callbacks import WorkflowCallbacks, PlanInfo, StepInfo, StepStatus, create_null_callbacks

    # Create work directory if it doesn't exist
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if clear_work_dir:
        clean_work_dir(work_dir)

    context_dir = os.path.join(work_dir, "context")
    os.makedirs(context_dir, exist_ok=True)

    print("Created context directory: ", context_dir)

    # Initialize file tracking system
    run_id = str(uuid.uuid4())
    output_manager = WorkflowOutputManager(
        work_dir=work_dir,
        run_id=run_id
    )

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    # Initialize approval configuration
    if approval_config is None:
        from cmbagent.database.approval_types import ApprovalConfig, ApprovalMode
        approval_config = ApprovalConfig(mode=ApprovalMode.NONE)

    # Initialize callbacks (use null callbacks if none provided)
    if callbacks is None:
        callbacks = create_null_callbacks()

    # Track workflow start time
    workflow_start_time = time.time()

    # Invoke workflow start callback
    callbacks.invoke_workflow_start(task, {
        'max_plan_steps': max_plan_steps,
        'planner_model': planner_model,
        'engineer_model': engineer_model,
        'work_dir': work_dir
    })

    # planning
    if restart_at_step <= 0:
        # planning
        planning_dir_str = os.path.join(os.path.expanduser(work_dir), "planning")
        os.makedirs(planning_dir_str, exist_ok=True)

        # Set file tracking context for planning phase
        output_manager.set_phase("planning")
        output_manager.set_agent("planner")

        # Notify callbacks of phase change
        callbacks.invoke_phase_change("planning", None)

        start_time = time.time()

        planner_config = get_model_config(planner_model, api_keys)
        plan_reviewer_config = get_model_config(plan_reviewer_model, api_keys)

        # Invoke planning start callback
        callbacks.invoke_planning_start(task, {
            'planner_model': planner_model,
            'plan_reviewer_model': plan_reviewer_model,
            'max_plan_steps': max_plan_steps,
            'n_plan_reviews': n_plan_reviews
        })

        cmbagent = CMBAgent(
            cache_seed=42,
            work_dir=planning_dir_str,
            default_llm_model=default_llm_model,
            default_formatter_model=default_formatter_model,
            agent_llm_configs={
                'planner': planner_config,
                'plan_reviewer': plan_reviewer_config,
            },
            api_keys=api_keys,
            approval_config=approval_config
        )

        # CRITICAL FIX: Always create WorkflowRun in database (regardless of approval settings)
        # Events need a valid run_id foreign key to be persisted
        if cmbagent.use_database and cmbagent.workflow_repo:
            try:
                # Create the WorkflowRun for this task execution
                run = cmbagent.workflow_repo.create_run(
                    mode="planning_control",
                    agent="planner",
                    model=planner_model,
                    status="planning",
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    task_description=task,
                    meta={
                        'max_plan_steps': max_plan_steps,
                        'max_rounds_planning': max_rounds_planning,
                        'plan_reviewer_model': plan_reviewer_model
                    }
                )
                print(f"✓ Created WorkflowRun {run.id} in database (started_at={run.started_at})")
            except Exception as e:
                print(f"✗ FAILED to create WorkflowRun in database: {e}")
                import traceback
                traceback.print_exc()
                raise

        end_time = time.time()
        initialization_time_planning = end_time - start_time

        start_time = time.time()

        # Check if workflow should continue or is paused/cancelled before planning
        if callbacks:
            callbacks.invoke_pause_check()
            if not callbacks.check_should_continue():
                print("Workflow stopped before planning phase")
                raise Exception("Workflow cancelled by user")

        cmbagent.solve(
            task,
            max_rounds=max_rounds_planning,
            initial_agent="plan_setter",
            shared_context={
                'feedback_left': n_plan_reviews,
                'max_n_attempts': max_n_attempts,
                'maximum_number_of_steps_in_plan': max_plan_steps,
                'planner_append_instructions': plan_instructions,
                'engineer_append_instructions': engineer_instructions,
                'researcher_append_instructions': researcher_instructions,
                'plan_reviewer_append_instructions': plan_instructions,
                'hardware_constraints': hardware_constraints,
                'researcher_filename': researcher_filename
            }
        )
        end_time = time.time()
        execution_time_planning = end_time - start_time

        # Create a dummy groupchat attribute if it doesn't exist
        if not hasattr(cmbagent, 'groupchat'):
            Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
            cmbagent.groupchat = Dummy()

        # Now call display_cost without triggering the AttributeError
        cmbagent.display_cost()

        planning_output = copy.deepcopy(cmbagent.final_context)

        outfile = save_final_plan(planning_output, planning_dir_str)
        print(f"\nStructured plan written to {outfile}")
        print(f"\nPlanning took {execution_time_planning:.4f} seconds\n")

        # Invoke planning complete callback
        plan_steps = []
        try:
            plan_data = load_plan(outfile)
            plan_steps = plan_data.get('sub_tasks', [])
        except:
            plan_steps = []

        plan_info = PlanInfo(
            task=task,
            num_steps=planning_output.get('number_of_steps_in_plan', len(plan_steps)),
            steps=plan_steps,
            plan_text=planning_output.get('final_plan', ''),
            planning_time=execution_time_planning
        )
        callbacks.invoke_planning_complete(plan_info)

        # CHECKPOINT: After planning (if approval enabled)
        if cmbagent.use_database and cmbagent.approval_manager and cmbagent.approval_config.requires_approval_at_planning():
            # Get plan text for approval
            plan_text = planning_output.get('final_plan', 'Plan not available')

            # Create a workflow run if not already created
            try:
                run = cmbagent.workflow_repo.get_current_run()
                if not run:
                    run = cmbagent.workflow_repo.create_run(
                        task_description=task,
                        config={}
                    )
            except:
                # If workflow repo not available, skip approval
                run = None

            if run:
                print("\n" + "=" * 80)
                print("APPROVAL REQUIRED: Planning Complete")
                print("=" * 80)
                print(f"\nPlan Summary:\n{plan_text}\n")
                print("Waiting for approval to proceed with execution...")
                print("(Approve via the WebSocket UI or API)\n")

                approval = cmbagent.approval_manager.create_approval_request(
                    run_id=str(run.id),
                    step_id=None,
                    checkpoint_type="after_planning",
                    context_snapshot={
                        "plan": plan_text,
                        "task": task,
                        "number_of_steps": planning_output.get('number_of_steps_in_plan', 0)
                    },
                    message=f"Planning complete. Review plan before execution?\n\n{plan_text}",
                    options=["approve", "reject", "modify"]
                )

                # Wait for approval (with timeout if configured)
                try:
                    timeout = cmbagent.approval_config.timeout_seconds
                    resolved_approval = cmbagent.approval_manager.wait_for_approval(
                        str(approval.id),
                        timeout_seconds=timeout
                    )

                    if resolved_approval.resolution == "rejected":
                        print("\n" + "=" * 80)
                        print("PLAN REJECTED BY USER")
                        print("=" * 80)
                        if resolved_approval.user_feedback:
                            print(f"Reason: {resolved_approval.user_feedback}")
                        print("\nExiting workflow.")
                        return

                    # Inject feedback into planning output if provided
                    if resolved_approval.user_feedback:
                        print(f"\nUser feedback: {resolved_approval.user_feedback}")
                        planning_output['user_feedback_planning'] = resolved_approval.user_feedback

                    print("\n" + "=" * 80)
                    print("PLAN APPROVED - Proceeding with execution")
                    print("=" * 80 + "\n")

                except Exception as e:
                    print(f"\nApproval error: {e}")
                    if cmbagent.approval_config.default_on_timeout == "reject":
                        print("Defaulting to rejection due to timeout/error.")
                        return
                    else:
                        print("Defaulting to approval due to timeout/error.")

        context_path = os.path.join(context_dir, "context_step_0.pkl")
        with open(context_path, 'wb') as f:
            pickle.dump(cmbagent.final_context, f)

        # Save timing report as JSON
        timing_report = {
            'initialization_time_planning': initialization_time_planning,
            'execution_time_planning': execution_time_planning,
            'total_time': initialization_time_planning + execution_time_planning
        }

        # Add timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # Save to JSON file in workdir (use main work_dir, not planning subdirectory)
        timing_path = os.path.join(work_dir, f"time/timing_report_planning_{timestamp}.json")
        os.makedirs(os.path.dirname(timing_path), exist_ok=True)
        with open(timing_path, 'w') as f:
            json.dump(timing_report, f, indent=2)

        print(f"\nTiming report data saved to: {timing_path}\n")

        # delete empty folders during planning
        database_full_path = os.path.join(planning_output['work_dir'], planning_output['database_path'])
        codebase_full_path = os.path.join(planning_output['work_dir'], planning_output['codebase_path'])
        for folder in [database_full_path, codebase_full_path]:
            if os.path.exists(folder) and not os.listdir(folder):
                os.rmdir(folder)

    # control
    engineer_config = get_model_config(engineer_model, api_keys)
    researcher_config = get_model_config(researcher_model, api_keys)
    web_surfer_config = get_model_config(web_surfer_model, api_keys)
    retrieve_assistant_config = get_model_config(retrieve_assistant_model, api_keys)
    camb_context_config = get_model_config(camb_context_model, api_keys)
    idea_maker_config = get_model_config(idea_maker_model, api_keys)
    idea_hater_config = get_model_config(idea_hater_model, api_keys)
    plot_judge_config = get_model_config(plot_judge_model, api_keys)

    control_dir_str = os.path.join(os.path.expanduser(work_dir), "control")
    os.makedirs(control_dir_str, exist_ok=True)

    current_context = copy.deepcopy(planning_output) if restart_at_step <= 0 else load_context(
        os.path.join(context_dir, f"context_step_{restart_at_step - 1}.pkl"))

    # Fix work_dir in current_context: planning sets it to planning_dir, but control needs control_dir
    if restart_at_step <= 0:
        current_context['work_dir'] = control_dir_str

    number_of_steps_in_plan = current_context['number_of_steps_in_plan']
    step_summaries = []
    initial_step = 1 if restart_at_step <= 0 else restart_at_step

    for step in range(initial_step, number_of_steps_in_plan + 1):
        clear_work_dir_step = True if step == 1 and restart_at_step <= 0 else False
        starter_agent = "control" if step == 1 else "control_starter"

        # Set file tracking context for control phase
        output_manager.set_phase("control")
        output_manager.set_step(step)

        # Notify callbacks of phase change
        callbacks.invoke_phase_change("control", step)

        start_time = time.time()
        cmbagent = CMBAgent(
            cache_seed=42,
            work_dir=control_dir_str,
            clear_work_dir=clear_work_dir_step,
            default_llm_model=default_llm_model,
            default_formatter_model=default_formatter_model,
            agent_llm_configs={
                'engineer': engineer_config,
                'researcher': researcher_config,
                'web_surfer': web_surfer_config,
                'retrieve_assistant': retrieve_assistant_config,
                'idea_maker': idea_maker_config,
                'idea_hater': idea_hater_config,
                'camb_context': camb_context_config,
                'plot_judge': plot_judge_config,
            },
            mode="planning_and_control_context_carryover",
            api_keys=api_keys,
            approval_config=approval_config
        )

        end_time = time.time()
        initialization_time_control = end_time - start_time

        if step == 1:
            plan_input = load_plan(os.path.join(work_dir, "planning/final_plan.json"))["sub_tasks"]
            agent_for_step = plan_input[0]['sub_task_agent']
        else:
            agent_for_step = current_context.get('agent_for_sub_task')
            if agent_for_step is None:
                # Fallback: try to get from plan if context is stale
                try:
                    plan_input = load_plan(os.path.join(work_dir, "planning/final_plan.json"))["sub_tasks"]
                    if step - 1 < len(plan_input):
                        agent_for_step = plan_input[step - 1].get('sub_task_agent')
                except Exception:
                    pass  # Keep agent_for_step as None, will be handled downstream

        parsed_context = copy.deepcopy(current_context)

        parsed_context["agent_for_sub_task"] = agent_for_step
        parsed_context["current_plan_step_number"] = step
        parsed_context["n_attempts"] = 0  # reset number of failures for each step.

        # Create step info for callbacks
        step_description = parsed_context.get('current_sub_task', f'Step {step}')
        step_info = StepInfo(
            step_number=step,
            goal=step_description,
            description=step_description,
            status=StepStatus.RUNNING
        )
        step_info.started_at = time.time()

        # Check if workflow should continue or is paused/cancelled
        callbacks.invoke_pause_check()
        if not callbacks.check_should_continue():
            print(f"Workflow stopped before step {step}")
            raise Exception("Workflow cancelled by user")

        # Invoke step start callback
        callbacks.invoke_step_start(step_info)

        start_time = time.time()

        cmbagent.solve(
            task,
            max_rounds=max_rounds_control,
            initial_agent=starter_agent,
            shared_context=parsed_context,
            step=step
        )

        end_time = time.time()
        execution_time_control = end_time - start_time

        # Update step info with completion details
        step_info.completed_at = time.time()
        step_info.execution_time = execution_time_control

        # number of failures:
        number_of_failures = cmbagent.final_context['n_attempts']

        results = {
            'chat_history': cmbagent.chat_result.chat_history,
            'final_context': cmbagent.final_context
        }

        # Emit all agent messages from this step's chat history for comprehensive logging
        for msg in results['chat_history']:
            agent_name = msg.get('name', msg.get('role', 'unknown'))
            role = msg.get('role', 'assistant')
            content = msg.get('content', '')
            if content and isinstance(content, str):
                # Detect code blocks in content
                code_blocks = re.findall(r'```(\w*)\n([\s\S]*?)```', content)
                for language, code in code_blocks:
                    if code.strip():
                        callbacks.invoke_code_execution(agent_name, code.strip()[:2000], language or 'python', None)

                # Emit the agent message
                callbacks.invoke_agent_message(
                    agent_name,
                    role,
                    content[:1000] if len(content) > 1000 else content,
                    {"step": step, "has_code": len(code_blocks) > 0}
                )

        if number_of_failures >= cmbagent.final_context['max_n_attempts']:
            print(
                f"in cmbagent.py: number of failures: {number_of_failures} >= max_n_attempts: {cmbagent.final_context['max_n_attempts']}. Exiting.")
            # Invoke step failed callback
            step_info.status = StepStatus.FAILED
            step_info.error = f"Max attempts ({cmbagent.final_context['max_n_attempts']}) exceeded"
            callbacks.invoke_step_failed(step_info)
            # Invoke workflow failed callback
            callbacks.invoke_workflow_failed(step_info.error, step)
            break

        # Extract step summary from agent's final message BEFORE completing
        this_step_execution_summary = None
        for msg in results['chat_history'][::-1]:
            if 'name' in msg:
                if agent_for_step is None:
                    # Skip if agent_for_step wasn't set (can happen in long sessions)
                    break
                agent_for_step_clean = agent_for_step.removesuffix("_context").removesuffix("_agent")
                if msg['name'] == agent_for_step_clean or msg['name'] == f"{agent_for_step_clean}_nest" or msg[
                    'name'] == f"{agent_for_step_clean}_response_formatter":
                    this_step_execution_summary = msg['content']
                    summary = f"### Step {step}\n{this_step_execution_summary.strip()}"
                    step_summaries.append(summary)
                    cmbagent.final_context['previous_steps_execution_summary'] = "\n\n".join(step_summaries)
                    break

        # Invoke step complete callback with summary
        step_info.status = StepStatus.COMPLETED
        step_info.result = {'final_context': cmbagent.final_context}
        step_info.summary = this_step_execution_summary
        callbacks.invoke_step_complete(step_info)

        results['initialization_time_control'] = initialization_time_control
        results['execution_time_control'] = execution_time_control

        # Save timing report as JSON
        timing_report = {
            'initialization_time_control': initialization_time_control,
            'execution_time_control': execution_time_control,
            'total_time': initialization_time_control + execution_time_control
        }

        # Add timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save to JSON file in workdir
        timing_path = os.path.join(current_context['work_dir'], f"time/timing_report_step_{step}_{timestamp}.json")
        os.makedirs(os.path.dirname(timing_path), exist_ok=True)
        with open(timing_path, 'w') as f:
            json.dump(timing_report, f, indent=2)

        print(f"\nTiming report data saved to: {timing_path}\n")

        # Create a dummy groupchat attribute if it doesn't exist
        if not hasattr(cmbagent, 'groupchat'):
            Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
            cmbagent.groupchat = Dummy()

        # Now call display_cost without triggering the AttributeError
        cost_df = cmbagent.display_cost(name_append=f"step_{step}")

        # Emit cost callback with accumulated cost data
        if cost_df is not None and not cost_df.empty:
            try:
                # Get total row if it exists
                total_cost = 0.0
                total_tokens = 0
                if 'Total' in cost_df.index:
                    total_row = cost_df.loc['Total']
                    total_cost = float(total_row.get('Cost ($)', 0)) if pd.notna(total_row.get('Cost ($)')) else 0.0
                    total_tokens = int(total_row.get('Total Tokens', 0)) if pd.notna(
                        total_row.get('Total Tokens')) else 0

                cost_data = {
                    "step_id": f"step_{step}",
                    "total_cost": total_cost,
                    "total_tokens": total_tokens,
                    "model_breakdown": [],
                    "agent_breakdown": []
                }
                # Build agent breakdown from rows (excluding Total)
                for idx, row in cost_df.iterrows():
                    if idx != 'Total':
                        agent_name = row.get('Agent')
                        if agent_name and pd.notna(agent_name):
                            cost_data["agent_breakdown"].append({
                                "agent": str(agent_name),
                                "cost": float(row.get('Cost ($)', 0)) if pd.notna(row.get('Cost ($)')) else 0.0,
                                "tokens": int(row.get('Total Tokens', 0)) if pd.notna(
                                    row.get('Total Tokens')) else 0,
                            })
                callbacks.invoke_cost_update(cost_data)
            except Exception as e:
                print(f"Warning: Failed to emit cost callback: {e}")

        # save the chat history and the final context
        chat_full_path = os.path.join(current_context['work_dir'], "chats")
        os.makedirs(chat_full_path, exist_ok=True)
        chat_output_path = os.path.join(chat_full_path, f"chat_history_step_{step}.json")
        with open(chat_output_path, 'w') as f:
            json.dump(results['chat_history'], f, indent=2)
        context_path = os.path.join(context_dir, f"context_step_{step}.pkl")
        with open(context_path, 'wb') as f:
            pickle.dump(cmbagent.final_context, f)

    # delete empty folders during planning
    database_full_path = os.path.join(current_context['work_dir'], current_context['database_path'])
    codebase_full_path = os.path.join(current_context['work_dir'], current_context['codebase_path'])
    for folder in [database_full_path, codebase_full_path]:
        if not os.listdir(folder):
            os.rmdir(folder)

    # Calculate total workflow time and invoke workflow complete callback
    workflow_total_time = time.time() - workflow_start_time
    callbacks.invoke_workflow_complete(current_context, workflow_total_time)

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

    return results


def planning_and_control(
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
    work_dir=work_dir_default,
    researcher_filename=shared_context_default['researcher_filename'],
    default_llm_model=default_llm_model_default,
    default_formatter_model=default_formatter_model_default,
    api_keys=None,
):
    """
    Execute planning and control workflow without context carryover.

    This is a simpler version of the workflow that executes planning followed
    by a single control phase without step-by-step context carryover.

    Args:
        task: The task description to execute
        max_rounds_planning: Maximum rounds for planning phase
        max_rounds_control: Maximum rounds for control phase
        max_plan_steps: Maximum number of steps in the plan
        n_plan_reviews: Number of plan review iterations
        plan_instructions: Additional instructions for the planner
        engineer_instructions: Additional instructions for the engineer
        researcher_instructions: Additional instructions for the researcher
        hardware_constraints: Hardware constraints to consider
        max_n_attempts: Maximum attempts before failure
        planner_model: Model to use for planner agent
        plan_reviewer_model: Model to use for plan reviewer agent
        engineer_model: Model to use for engineer agent
        researcher_model: Model to use for researcher agent
        idea_maker_model: Model to use for idea maker agent
        idea_hater_model: Model to use for idea hater agent
        work_dir: Working directory for outputs
        researcher_filename: Filename for researcher output
        default_llm_model: Default LLM model
        default_formatter_model: Default formatter model
        api_keys: API keys dictionary

    Returns:
        Dictionary containing chat history and final context
    """
    # Late import to avoid circular dependency
    from cmbagent.cmbagent import CMBAgent
    from cmbagent.agents.planner_response_formatter.planner_response_formatter import save_final_plan

    # Create work directory if it doesn't exist
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    # Initialize file tracking system
    run_id = str(uuid.uuid4())
    output_manager = WorkflowOutputManager(
        work_dir=work_dir,
        run_id=run_id
    )
    output_manager.set_phase("planning")

    # planning
    planning_dir = os.path.join(os.path.expanduser(work_dir), "planning")
    os.makedirs(planning_dir, exist_ok=True)

    start_time = time.time()

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    planner_config = get_model_config(planner_model, api_keys)
    plan_reviewer_config = get_model_config(plan_reviewer_model, api_keys)

    cmbagent = CMBAgent(
        cache_seed=42,
        work_dir=planning_dir,
        default_llm_model=default_llm_model,
        default_formatter_model=default_formatter_model,
        agent_llm_configs={
            'planner': planner_config,
            'plan_reviewer': plan_reviewer_config,
        },
        api_keys=api_keys
    )
    end_time = time.time()
    initialization_time_planning = end_time - start_time

    start_time = time.time()
    cmbagent.solve(
        task,
        max_rounds=max_rounds_planning,
        initial_agent="plan_setter",
        shared_context={
            'feedback_left': n_plan_reviews,
            'max_n_attempts': max_n_attempts,
            'maximum_number_of_steps_in_plan': max_plan_steps,
            'planner_append_instructions': plan_instructions,
            'engineer_append_instructions': engineer_instructions,
            'researcher_append_instructions': researcher_instructions,
            'plan_reviewer_append_instructions': plan_instructions,
            'hardware_constraints': hardware_constraints,
            'researcher_filename': researcher_filename
        }
    )
    end_time = time.time()
    execution_time_planning = end_time - start_time

    # Create a dummy groupchat attribute if it doesn't exist
    if not hasattr(cmbagent, 'groupchat'):
        Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
        cmbagent.groupchat = Dummy()

    # Now call display_cost without triggering the AttributeError
    cmbagent.display_cost()

    planning_output = copy.deepcopy(cmbagent.final_context)
    outfile = save_final_plan(planning_output, planning_dir)
    print(f"Structured plan written to {outfile}")
    print(f"Planning took {execution_time_planning:.4f} seconds")

    # Save timing report as JSON
    timing_report = {
        'initialization_time_planning': initialization_time_planning,
        'execution_time_planning': execution_time_planning,
        'total_time': initialization_time_planning + execution_time_planning
    }

    # Add timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Save to JSON file in workdir
    timing_path = os.path.join(planning_output['work_dir'], f"time/timing_report_planning_{timestamp}.json")
    with open(timing_path, 'w') as f:
        json.dump(timing_report, f, indent=2)

    print(f"\nTiming report data saved to: {timing_path}\n")

    # delete empty folders during control
    database_full_path = os.path.join(planning_output['work_dir'], planning_output['database_path'])
    codebase_full_path = os.path.join(planning_output['work_dir'], planning_output['codebase_path'])
    time_full_path = os.path.join(planning_output['work_dir'], 'time')
    for folder in [database_full_path, codebase_full_path, time_full_path]:
        if not os.listdir(folder):
            os.rmdir(folder)

    # control
    output_manager.set_phase("control")

    engineer_config = get_model_config(engineer_model, api_keys)
    researcher_config = get_model_config(researcher_model, api_keys)
    web_surfer_config = get_model_config(web_surfer_model, api_keys)
    retrieve_assistant_config = get_model_config(retrieve_assistant_model, api_keys)
    idea_maker_config = get_model_config(idea_maker_model, api_keys)
    idea_hater_config = get_model_config(idea_hater_model, api_keys)

    control_dir = os.path.join(os.path.expanduser(work_dir), "control")
    os.makedirs(control_dir, exist_ok=True)

    start_time = time.time()
    cmbagent = CMBAgent(
        cache_seed=42,
        work_dir=control_dir,
        default_llm_model=default_llm_model,
        default_formatter_model=default_formatter_model,
        agent_llm_configs={
            'engineer': engineer_config,
            'researcher': researcher_config,
            'web_surfer': web_surfer_config,
            'retrieve_assistant': retrieve_assistant_config,
            'idea_maker': idea_maker_config,
            'idea_hater': idea_hater_config,
        },
        api_keys=api_keys
    )

    end_time = time.time()
    initialization_time_control = end_time - start_time

    start_time = time.time()
    cmbagent.solve(
        task,
        max_rounds=max_rounds_control,
        initial_agent="control",
        shared_context=planning_output
    )
    end_time = time.time()
    execution_time_control = end_time - start_time

    results = {
        'chat_history': cmbagent.chat_result.chat_history,
        'final_context': cmbagent.final_context
    }

    results['initialization_time_planning'] = initialization_time_planning
    results['execution_time_planning'] = execution_time_planning
    results['initialization_time_control'] = initialization_time_control
    results['execution_time_control'] = execution_time_control

    # Save timing report as JSON
    timing_report = {
        'initialization_time_planning': initialization_time_planning,
        'execution_time_planning': execution_time_planning,
        'initialization_time_control': initialization_time_control,
        'execution_time_control': execution_time_control,
        'total_time': initialization_time_planning + execution_time_planning + initialization_time_control + execution_time_control
    }

    # Add timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save to JSON file in workdir
    timing_path = os.path.join(results['final_context']['work_dir'], f"time/timing_report_control_{timestamp}.json")
    with open(timing_path, 'w') as f:
        json.dump(timing_report, f, indent=2)

    # Create a dummy groupchat attribute if it doesn't exist
    if not hasattr(cmbagent, 'groupchat'):
        Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
        cmbagent.groupchat = Dummy()

    # Now call display_cost without triggering the AttributeError
    cmbagent.display_cost()

    # delete empty folders during control
    database_full_path = os.path.join(results['final_context']['work_dir'], results['final_context']['database_path'])
    codebase_full_path = os.path.join(results['final_context']['work_dir'], results['final_context']['codebase_path'])
    time_full_path = os.path.join(results['final_context']['work_dir'], 'time')
    for folder in [database_full_path, codebase_full_path, time_full_path]:
        try:
            if os.path.exists(folder) and not os.listdir(folder):
                os.rmdir(folder)
        except OSError:
            pass

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

    return results


# Alias for backward compatibility
deep_research = planning_and_control_context_carryover
