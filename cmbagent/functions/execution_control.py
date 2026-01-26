"""Execution flow control functionality."""

import os
import json
import base64
from typing import Literal, Optional
from autogen import register_function
from autogen.agentchat.group import ContextVariables, AgentTarget, ReplyResult, TerminateTarget
from ..vlm_utils import account_for_external_api_calls, send_image_to_vlm, create_vlm_prompt, call_external_plot_debugger
from .utils import load_plots


def terminate_session(context_variables: ContextVariables) -> ReplyResult:
    """Terminate the session."""
    return ReplyResult(
        target=TerminateTarget(),  ## terminate
        message="Session terminated.",
        context_variables=context_variables
    )


def post_execution_transfer(next_agent_suggestion: Literal["engineer", "classy_sz_agent", "installer",
                                                           "camb_agent", "cobaya_agent", "camb_context",
                                                           "classy_context", "plot_judge", "control"], 
                            context_variables: ContextVariables,
                            execution_status: Literal["success", "failure"],
                            fix_suggestion: Optional[str] = None,
                            cmbagent_instance=None,
                            plot_judge=None,
                            control=None,
                            terminator=None,
                            engineer=None,
                            installer=None
                            ) -> ReplyResult:
    """Transfer to the next agent based on the execution status."""
    
    # Transfer executed code from global variable to shared context
    try:
        import cmbagent.vlm_utils
        if getattr(cmbagent.vlm_utils, "_last_executed_code", None):
            context_variables["latest_executed_code"] = cmbagent.vlm_utils._last_executed_code
            cmbagent.vlm_utils._last_executed_code = None  # Prevent reuse
        else:
            context_variables["latest_executed_code"] = None
    except Exception:
        context_variables["latest_executed_code"] = None
            
    workflow_status_str = rf"""
xxxxxxxxxxxxxxxxxxxxxxxxxx

Workflow status:

Plan step number: {context_variables["current_plan_step_number"]}

Agent for sub-task (might be different from the next agent suggestion for debugging): {context_variables["agent_for_sub_task"]}

Current status (before execution): {context_variables["current_status"]}

xxxxxxxxxxxxxxxxxxxxxxxxxx
"""
    
    if context_variables["agent_for_sub_task"] in ["engineer", "camb_agent", "camb_context", "classy_context"]:
        
        if context_variables["n_attempts"] >= context_variables["max_n_attempts"]:
            return ReplyResult(
                target=AgentTarget(terminator),
                message=f"Max number of code execution attempts ({context_variables['max_n_attempts']}) reached. Exiting.",
                context_variables=context_variables
            )
        
        if execution_status == "success":
            # Check if plot evaluation is enabled
            evaluate_plots = context_variables.get("evaluate_plots", False)
            
            if evaluate_plots:
                # Check if there are new images that need plot_judge review
                data_directory = os.path.join(cmbagent_instance.work_dir, context_variables['database_path'])
                image_files = load_plots(data_directory)
                displayed_images = context_variables.get("displayed_images", [])
                new_images = [img for img in image_files if img not in displayed_images]
                
                if new_images:
                    # Call VLM to evaluate the latest plot
                    most_recent_image = new_images[-1]
                    context_variables["latest_plot_path"] = most_recent_image
                    if most_recent_image not in context_variables["displayed_images"]:
                        context_variables["displayed_images"].append(most_recent_image)
                    # Handoff to plot_judge
                    return ReplyResult(
                        target=AgentTarget(plot_judge),
                        message=f"Plot created: {most_recent_image}. Please analyze this plot using a VLM.",
                        context_variables=context_variables
                    )
                else:
                    # No new images needing approval, so VLM feedback history is cleared
                    context_variables["vlm_plot_structured_feedback"] = None
                    context_variables["latest_executed_code"] = None
                    
                    # No new plots to evaluate, continue to control
                    return ReplyResult(
                        target=AgentTarget(control),
                        message="Execution status: " + execution_status + ". Transfer to control.\n" + f"{workflow_status_str}\n",
                        context_variables=context_variables
                    )
            else:
                # Plot evaluation disabled, so skip VLM and go straight to control
                context_variables["vlm_plot_structured_feedback"] = None
                context_variables["latest_executed_code"] = None
                
                return ReplyResult(
                    target=AgentTarget(control),
                    message="Execution status: " + execution_status + ". Transfer to control.\n" + f"{workflow_status_str}\n",
                    context_variables=context_variables
                )

        # Get agent references
        classy_sz = cmbagent_instance.get_agent_from_name('classy_sz_agent') if not cmbagent_instance.skip_rag_agents else None
        camb = cmbagent_instance.get_agent_from_name('camb_agent') if not cmbagent_instance.skip_rag_agents else None
        camb_context = cmbagent_instance.get_agent_from_name('camb_context')
        classy_context = cmbagent_instance.get_agent_from_name('classy_context')
        
        if next_agent_suggestion == "engineer":
            context_variables["n_attempts"] += 1
            return ReplyResult(
                target=AgentTarget(engineer),
                message="Execution status: " + execution_status + ". Transfer to engineer.\n" + f"{workflow_status_str}\n" + f"Fix suggestion: {fix_suggestion}\n",
                context_variables=context_variables
            )
        
        elif next_agent_suggestion == "classy_sz_agent" and classy_sz:
            context_variables["n_attempts"] += 1
            return ReplyResult(
                target=AgentTarget(classy_sz),
                message="Execution status: " + execution_status + ". Transfer to classy_sz_agent.\n" + f"{workflow_status_str}\n",
                context_variables=context_variables
            )

        elif next_agent_suggestion == "camb_agent" and camb:
            context_variables["n_attempts"] += 1
            return ReplyResult(
                target=AgentTarget(camb),
                message="Execution status: " + execution_status + ". Transfer to camb_agent.\n" + f"{workflow_status_str}\n",
                context_variables=context_variables
            )
        
        elif next_agent_suggestion == "camb_context":
            context_variables["n_attempts"] += 1
            return ReplyResult(
                target=AgentTarget(camb_context),
                message="Execution status: " + execution_status + ". Transfer to camb_context.\n" + f"{workflow_status_str}\n" + f"Fix suggestion: {fix_suggestion}\n",
                context_variables=context_variables
            )
        
        elif next_agent_suggestion == "classy_context":
            context_variables["n_attempts"] += 1
            return ReplyResult(
                target=AgentTarget(classy_context),
                message="Execution status: " + execution_status + ". Transfer to classy_context.\n" + f"{workflow_status_str}\n" + f"Fix suggestion: {fix_suggestion}\n",
                context_variables=context_variables
            )

        elif next_agent_suggestion == "control":
            context_variables["n_attempts"] += 1
            return ReplyResult(
                target=AgentTarget(control),
                message="Execution status: " + execution_status + ". Transfer to control.\n" + f"{workflow_status_str}\n",
                context_variables=context_variables
            )
        
        elif next_agent_suggestion == "installer":
            context_variables["n_attempts"] += 1
            return ReplyResult(
                target=AgentTarget(installer),
                message="Execution status: " + execution_status + ". Transfer to installer.\n" + f"{workflow_status_str}\n",
                context_variables=context_variables
            )
    else:
        return ReplyResult(
            target=AgentTarget(control),
            message="Transfer to control.\n" + workflow_status_str,
            context_variables=context_variables
        )


def call_vlm_judge(context_variables: ContextVariables, cmbagent_instance, plot_judge, plot_debugger, control) -> ReplyResult:
    """
    Analyze latest_plot_path (set by post_execution_transfer) using VLM and store the analysis in context.
    """
    # Check if we've already reached the maximum number of plot evaluations before calling VLM
    current_evals = context_variables.get("n_plot_evals", 0)
    max_evals = context_variables.get("max_n_plot_evals", 1)
    
    if current_evals >= max_evals:
        # Clear VLM feedback and executed code
        context_variables["vlm_plot_structured_feedback"] = None
        context_variables["latest_executed_code"] = None
        context_variables["n_plot_evals"] = 0
        return ReplyResult(
            target=AgentTarget(control),
            message=f"Plot evaluation retry limit ({max_evals}) reached. Accepting current plot and continuing to control.",
            context_variables=context_variables
        )
    
    print(f"Plot evaluation {current_evals + 1}/{max_evals}")
    
    img_path = context_variables.get("latest_plot_path")
    if not img_path:
        return ReplyResult(
            target=AgentTarget(plot_debugger),
            message="No plot path found in context",
            context_variables=context_variables
        )
    
    # Check if file exists
    if not os.path.exists(img_path):
        return ReplyResult(
            target=AgentTarget(plot_debugger),
            message=f"Plot file not found at {img_path}",
            context_variables=context_variables
        )
    
    try:
        print(f"Reading plot file: {img_path}")
        with open(img_path, 'rb') as img_file:
            base_64_img = base64.b64encode(img_file.read()).decode('utf-8')
            
    except Exception as e:
        return ReplyResult(
            target=AgentTarget(plot_debugger),
            message=f"Error reading image file: {str(e)}",
            context_variables=context_variables
        )
    
    try:
        # Send the image to the VLM model and get the analysis
        executed_code = context_variables.get("latest_executed_code")
        vlm_prompt = create_vlm_prompt(context_variables, executed_code)
        inject_wrong_plot = context_variables.get("inject_wrong_plot", False)
        completion, injected_code = send_image_to_vlm(base_64_img, vlm_prompt, inject_wrong_plot=inject_wrong_plot, context_variables=context_variables)
        
        # Increment plot evaluation counter after VLM call
        context_variables["n_plot_evals"] = current_evals + 1
        vlm_analysis_json = completion.choices[0].message.content
        print(f"\n\nVLM analysis: \n\n{vlm_analysis_json}\n\n")
        
        if injected_code:
            print(f"Injected code:\n{injected_code}\n")
        
        # Parse the structured JSON response
        try:
            vlm_analysis_data = json.loads(vlm_analysis_json)
            vlm_verdict = vlm_analysis_data.get("verdict", "continue")
            vlm_problems = vlm_analysis_data.get("problems", [])
            
            # Store verdict and problems in shared context
            context_variables["vlm_plot_analysis"] = vlm_analysis_json
            context_variables["vlm_verdict"] = vlm_verdict
            context_variables["plot_problems"] = vlm_problems
            
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse VLM JSON response: {e}")
            # Fall back to text parsing for verdict
            vlm_verdict = "continue"
            if "VERDICT: continue" in vlm_analysis_json:
                vlm_verdict = "continue"
            elif "VERDICT: retry" in vlm_analysis_json:
                vlm_verdict = "retry"
            
            context_variables["vlm_plot_analysis"] = vlm_analysis_json
            context_variables["vlm_verdict"] = vlm_verdict
            context_variables["plot_problems"] = ["VLM parsing failed - analysis may be incomplete"]
            print(f"VLM VERDICT (fallback): {vlm_verdict}")
        
        account_for_external_api_calls(plot_judge, completion)
        
        # Track LLM scientific criteria costs if they exist
        llm_completion = context_variables.get("llm_completion")
        if llm_completion:
            account_for_external_api_calls(plot_judge, llm_completion, call_type="LLM")
                    
        return ReplyResult(
            target=AgentTarget(plot_debugger),
            message=f"VLM analysis completed with verdict: {vlm_verdict}.",
            context_variables=context_variables
        )
        
    except Exception as e:
        error_msg = f"Error calling VLM API: {str(e)}"
        context_variables["vlm_plot_analysis"] = f"ERROR: {error_msg}"
        return ReplyResult(
            target=AgentTarget(plot_debugger),
            message=f"VLM analysis failed: {error_msg}. Please handle this error.",
            context_variables=context_variables
        )


def route_plot_judge_verdict(context_variables: ContextVariables, cmbagent_instance, plot_debugger, control, engineer) -> ReplyResult:
    """
    Route based on plot_judge verdict stored in context: continue to control, retry to engineer.
    Handles all debugging logic internally for retry cases.
    """
    # Get verdict and problems from shared context
    verdict = context_variables.get("vlm_verdict", "continue")
    vlm_problems = context_variables.get("plot_problems", [])
    
    # Get current evaluation count (already incremented in call_vlm_judge)
    current_evals = context_variables.get("n_plot_evals", 0)
    max_evals = context_variables.get("max_n_plot_evals", 1)

    # Update displayed_images list
    if "latest_plot_path" in context_variables and "displayed_images" in context_variables:
        if context_variables["latest_plot_path"] not in context_variables["displayed_images"]:
            context_variables["displayed_images"].append(context_variables["latest_plot_path"])

    if verdict == "continue":
        # Clear VLM feedback, problems, and fixes when plot is approved
        context_variables["vlm_plot_structured_feedback"] = None
        context_variables["latest_executed_code"] = None
        context_variables["plot_problems"] = []
        context_variables["plot_fixes"] = []
        return ReplyResult(
            target=AgentTarget(control),
            message="Plot approved. Continuing to control.",
            context_variables=context_variables
        )
    else:  # verdict == "retry"
        # Check if we've reached the maximum number of plot evaluations (retries)
        if current_evals > max_evals:
            print(f"Maximum plot evaluation retries ({max_evals}) reached. Accepting current plot and continuing to control.")
            # Clear VLM feedback and executed code when accepting due to limit
            context_variables["vlm_plot_structured_feedback"] = None
            context_variables["latest_executed_code"] = None
            context_variables["plot_problems"] = []
            context_variables["plot_fixes"] = []
            return ReplyResult(
                target=AgentTarget(control),
                message=f"Plot evaluation retry limit ({max_evals}) reached. Accepting current plot and continuing to control.",
                context_variables=context_variables
            )
        
        # Call external debugger to generate fixes if we have problems
        fixes = []
        if vlm_problems:                
            task_context = context_variables.get("improved_main_task", "No task context")
            vlm_analysis = context_variables.get("vlm_plot_analysis", "No VLM analysis")
            executed_code = context_variables.get("latest_executed_code", "No code available")
            
            fixes = call_external_plot_debugger(
                task_context=task_context,
                vlm_analysis=vlm_analysis, 
                problems=vlm_problems,
                executed_code=executed_code
            )
            
            # Store fixes in shared context
            context_variables["plot_fixes"] = fixes
        
        # Construct comprehensive feedback with problems from VLM and fixes from debugger
        engineer_feedback = ""
        if vlm_problems or fixes:
            engineer_feedback = "The plot has been analyzed and needs improvements:\n\n"
            
            if vlm_problems:
                engineer_feedback += "Problems identified by plot judge:\n" + "\n".join(f"- {p}" for p in vlm_problems) + "\n\n"
            
            if fixes:
                engineer_feedback += "Targeted fixes from code debugger:\n" + "\n".join(f"- {f}" for f in fixes) + "\n\n"
            
            # Include code corresponding to the problematic plot as context
            code_context = context_variables.get("latest_executed_code")
            if code_context and len(code_context.strip()) > 0:
                engineer_feedback += "Code that generated this plot:\n```python\n" + code_context + "\n```\n"
        
        # Store structured feedback in context for engineer prompt injection
        context_variables["vlm_plot_structured_feedback"] = engineer_feedback if engineer_feedback else None
                    
        print(f"\n=== ENGINEER FEEDBACK ===")
        if vlm_problems:
            print("Problems identified by plot judge:")
            for i, problem in enumerate(vlm_problems, 1):
                print(f"  {i}. {problem}")
            print()
        
        if fixes:
            print("Targeted fixes from plot debugger:")
            for i, fix in enumerate(fixes, 1):
                print(f"  {i}. {fix}")
            print()
        
        if context_variables.get("latest_executed_code"):
            print("Code that generated this plot:")
            print("```python")
            print(context_variables.get("latest_executed_code"))
            print("```")
        
        print("=== END ENGINEER FEEDBACK ===\n")
        
        return ReplyResult(
            target=AgentTarget(engineer),
            message="Plot needs fixes. Returning to engineer.",
            context_variables=context_variables
        )


def setup_execution_control_functions(cmbagent_instance):
    """Register execution control functions with the appropriate agents."""
    executor_response_formatter = cmbagent_instance.get_agent_from_name('executor_response_formatter')
    plot_judge = cmbagent_instance.get_agent_from_name('plot_judge')
    plot_debugger = cmbagent_instance.get_agent_from_name('plot_debugger')
    control = cmbagent_instance.get_agent_from_name('control')
    terminator = cmbagent_instance.get_agent_from_name('terminator')
    engineer = cmbagent_instance.get_agent_from_name('engineer')
    installer = cmbagent_instance.get_agent_from_name('installer')
    
    # Create closures to bind cmbagent_instance and agents
    def post_execution_transfer_closure(next_agent_suggestion: Literal["engineer", "classy_sz_agent", "installer",
                                                                       "camb_agent", "cobaya_agent", "camb_context",
                                                                       "classy_context", "plot_judge", "control"], 
                                       context_variables: ContextVariables,
                                       execution_status: Literal["success", "failure"],
                                       fix_suggestion: Optional[str] = None) -> ReplyResult:
        return post_execution_transfer(next_agent_suggestion, context_variables, execution_status, fix_suggestion,
                                       cmbagent_instance, plot_judge, control, terminator, engineer, installer)
    
    def call_vlm_judge_closure(context_variables: ContextVariables) -> ReplyResult:
        return call_vlm_judge(context_variables, cmbagent_instance, plot_judge, plot_debugger, control)
    
    def route_plot_judge_verdict_closure(context_variables: ContextVariables) -> ReplyResult:
        return route_plot_judge_verdict(context_variables, cmbagent_instance, plot_debugger, control, engineer)
    
    # Register functions
    terminator._add_single_function(terminate_session)
    
    register_function(
        post_execution_transfer_closure,
        caller=executor_response_formatter,
        executor=executor_response_formatter,
        description=r"""
Transfer to the next agent based on the execution status.
For the next agent suggestion, follow these rules:

    - Suggest the installer agent if error related to missing Python modules (i.e., ModuleNotFoundError).
    - Suggest the classy_sz_agent if error is an internal classy_sz error.
    - Suggest the camb_context agent if CAMB documentation should be consulted, e.g., if the Python error is related to the camb code.
    - Suggest the classy_context agent if classy documentation should be consulted, e.g., if the Python error is related to the classy code, e.g., classy.CosmoSevereError.
    - Suggest camb_context to fix Python errors related to the camb code.
    - Suggest classy_context to fix Python errors related to the classy code, e.g., classy.CosmoSevereError.
    - Suggest the engineer agent if error related to generic Python code. Don't prioritize the engineer agent if the error is related to the camb or classy code, in this case suggest camb_context or classy_context instead.
    - Suggest the cobaya_agent if error related to internal cobaya code.
    - Suggest the control agent only if execution was successful. 
""",
    )
    
    register_function(
        call_vlm_judge_closure,
        caller=plot_judge,
        executor=plot_judge,
        description=r"""
        Call a VLM to judge the plot.
        """,
    )
    
    register_function(
        route_plot_judge_verdict_closure,
        caller=plot_debugger,
        executor=plot_debugger,
        description=r"""
        Route based on plot_judge verdict stored in context: continue to control, retry to engineer.
        Handles external debugging calls internally for retry cases.
        """,
    )
