"""
CMBAgent task execution logic.
"""

import asyncio
import concurrent.futures
import os
import sys
import time
from typing import Any, Dict

from fastapi import WebSocket

from websocket.events import send_ws_event
from execution.stream_capture import StreamCapture, AG2IOStreamCapture
from execution.dag_tracker import DAGTracker

# Services will be loaded at runtime
_services_available = None
_workflow_service = None
_execution_service = None


def _check_services():
    """Check if services are available and load them."""
    global _services_available, _workflow_service, _execution_service
    if _services_available is None:
        try:
            from services import workflow_service, execution_service
            _workflow_service = workflow_service
            _execution_service = execution_service
            _services_available = True
        except ImportError:
            _services_available = False
    return _services_available


async def execute_cmbagent_task(
    websocket: WebSocket,
    task_id: str,
    task: str,
    config: Dict[str, Any]
):
    """Execute CMBAgent task with real-time output streaming.

    Integrates with:
    - Stage 3: State Machine (pause/resume/cancel via workflow_service)
    - Stage 5: WebSocket Protocol (standardized events)
    - Stage 7: Retry Mechanism (via execution_service)
    """
    services_available = _check_services()

    # Get work directory from config or use default
    work_dir = config.get("workDir", "~/Desktop/cmbdir")
    if work_dir.startswith("~"):
        work_dir = os.path.expanduser(work_dir)

    # Create a subdirectory for this specific task
    task_work_dir = os.path.join(work_dir, task_id)
    os.makedirs(task_work_dir, exist_ok=True)

    # Set up environment variables
    os.environ["CMBAGENT_DEBUG"] = "false"
    os.environ["CMBAGENT_DISABLE_DISPLAY"] = "true"

    dag_tracker = None

    try:
        # Debug logging
        print(f"[DEBUG] execute_cmbagent_task called")
        print(f"[DEBUG] Task ID: {task_id}")
        print(f"[DEBUG] Mode: {config.get('mode', 'NOT SET')}")
        print(f"[DEBUG] Config keys: {list(config.keys())}")
        
        await send_ws_event(
            websocket, "status",
            {"message": "Initializing CMBAgent..."},
            run_id=task_id
        )

        # Import cmbagent
        import cmbagent
        from cmbagent.utils import get_api_keys_from_env

        api_keys = get_api_keys_from_env()

        # Map frontend config to CMBAgent parameters
        mode = config.get("mode", "one-shot")
        print(f"[DEBUG] Detected mode: {mode}")
        
        engineer_model = config.get("model", "gpt-4o")
        max_rounds = config.get("maxRounds", 25)
        max_attempts = config.get("maxAttempts", 6)
        agent = config.get("agent", "engineer")
        default_formatter_model = config.get("defaultFormatterModel", "o3-mini-2025-01-31")
        default_llm_model = config.get("defaultModel", "gpt-4.1-2025-04-14")

        # Get run_id from workflow service if available
        db_run_id = None
        if services_available:
            run_info = _workflow_service.get_run_info(task_id)
            if run_info:
                db_run_id = run_info.get("db_run_id")

        # Create DAG tracker for this execution
        dag_tracker = DAGTracker(
            websocket, task_id, mode, send_ws_event, run_id=db_run_id
        )
        dag_data = dag_tracker.create_dag_for_mode(task, config)
        effective_run_id = dag_tracker.run_id or task_id

        # Set initial phase based on mode
        if mode in ["planning-control", "idea-generation", "hitl-interactive", "copilot"]:
            dag_tracker.set_phase("planning", None)
        else:
            dag_tracker.set_phase("execution", None)

        # Emit DAG created event
        await send_ws_event(
            websocket,
            "dag_created",
            {
                "run_id": effective_run_id,
                "nodes": dag_tracker.nodes,
                "edges": dag_tracker.edges,
                "levels": dag_data.get("levels", 1)
            },
            run_id=effective_run_id
        )

        # Planning & Control specific parameters
        planner_model = config.get("plannerModel", "gpt-4.1-2025-04-14")
        plan_reviewer_model = config.get("planReviewerModel", "o3-mini-2025-01-31")
        researcher_model = config.get("researcherModel", "gpt-4.1-2025-04-14")
        max_plan_steps = config.get("maxPlanSteps", 10 if mode == "idea-generation" else 10)  # Dynamic: allow up to 10 steps
        n_plan_reviews = config.get("nPlanReviews", 1)
        plan_instructions = config.get("planInstructions", "")

        # Idea Generation specific parameters
        idea_maker_model = config.get("ideaMakerModel", "gpt-4.1-2025-04-14")
        idea_hater_model = config.get("ideaHaterModel", "o3-mini-2025-01-31")

        # OCR specific parameters
        save_markdown = config.get("saveMarkdown", True)
        save_json = config.get("saveJson", True)
        save_text = config.get("saveText", False)
        max_workers = config.get("maxWorkers", 4)
        ocr_output_dir = config.get("ocrOutputDir", None)

        await send_ws_event(
            websocket, "output",
            {"message": f"🚀 Starting CMBAgent in {mode.replace('-', ' ').title()} mode"},
            run_id=task_id
        )
        await send_ws_event(
            websocket, "output",
            {"message": f"📋 Task: {task}"},
            run_id=task_id
        )

        # Update first node to running
        first_node = dag_tracker.get_first_node()
        if first_node:
            await dag_tracker.update_node_status(first_node, "running")

        # Log mode-specific configuration
        if mode == "planning-control":
            await send_ws_event(
                websocket, "output",
                {"message": f"⚙️ Configuration: Planner={planner_model}, Engineer={engineer_model}"},
                run_id=task_id
            )
        elif mode == "idea-generation":
            await send_ws_event(
                websocket, "output",
                {"message": f"⚙️ Configuration: Idea Maker={idea_maker_model}, Idea Hater={idea_hater_model}"},
                run_id=task_id
            )
        elif mode == "ocr":
            await send_ws_event(
                websocket, "output",
                {"message": f"⚙️ Configuration: Save Markdown={save_markdown}, Max Workers={max_workers}"},
                run_id=task_id
            )
        elif mode == "copilot":
            await send_ws_event(
                websocket, "output",
                {"message": f"⚙️ Configuration: Agents={config.get('availableAgents', ['engineer', 'researcher'])}, Planning={config.get('enablePlanning', True)}"},
                run_id=task_id
            )

        start_time = time.time()
        loop = asyncio.get_event_loop()

        # Create stream capture with DAG tracking
        stream_capture = StreamCapture(
            websocket, task_id, send_ws_event,
            dag_tracker=dag_tracker, loop=loop, work_dir=task_work_dir,
            mode=mode  # Pass mode so StreamCapture knows if it's HITL
        )

        # Create callbacks
        from cmbagent.callbacks import (
            create_websocket_callbacks, merge_callbacks,
            create_print_callbacks, WorkflowCallbacks
        )

        def ws_send_event(event_type: str, data: Dict[str, Any]):
            """Send WebSocket event from sync context"""
            print(f"[ws_send_event] Attempting to send event: {event_type}")
            print(f"[ws_send_event] Event data keys: {list(data.keys())}")
            print(f"[ws_send_event] WebSocket: {websocket}")
            print(f"[ws_send_event] Loop: {loop}")

            try:
                future = asyncio.run_coroutine_threadsafe(
                    send_ws_event(websocket, event_type, data, run_id=task_id),
                    loop
                )
                # Wait for send to complete (increased timeout for stability)
                try:
                    result = future.result(timeout=10.0)
                    if result:
                        print(f"[ws_send_event] ✓ Event {event_type} sent successfully")
                    else:
                        print(f"[ws_send_event] ⚠ Event {event_type} send returned False (connection may be closed)")
                except TimeoutError:
                    print(f"[ws_send_event] ⚠ Event {event_type} queued but not confirmed within 10s")
                except Exception as e:
                    print(f"[ws_send_event] ✗ Event {event_type} failed: {e}")
                    import traceback
                    traceback.print_exc()
            except Exception as e:
                print(f"[ws_send_event] ✗ Failed to queue event {event_type}: {e}")
                import traceback
                traceback.print_exc()

        def sync_pause_check():
            """Synchronous pause check - blocks while paused."""
            if services_available:
                while _execution_service.is_paused(task_id):
                    if _execution_service.is_cancelled(task_id):
                        raise Exception("Workflow cancelled by user")
                    time.sleep(0.5)

        def should_continue():
            """Check if workflow should continue."""
            if services_available:
                if _execution_service.is_cancelled(task_id):
                    return False
            return True

        # Determine HITL mode for proper DAG node handling
        hitl_mode = None
        if mode == "hitl-interactive":
            hitl_mode = config.get("hitlVariant", "full_interactive")

        ws_callbacks = create_websocket_callbacks(ws_send_event, task_id, hitl_mode=hitl_mode)

        # Create execution event tracking callbacks
        def create_execution_event(event_type: str, agent_name: str, **kwargs):
            """Helper to create ExecutionEvent from callbacks"""
            if dag_tracker and dag_tracker.event_repo and dag_tracker.db_session:
                try:
                    from datetime import datetime, timezone as tz
                    dag_tracker.execution_order_counter += 1

                    current_node_id = None
                    for node_id, status in dag_tracker.node_statuses.items():
                        if status == "running":
                            current_node_id = node_id
                            break

                    dag_tracker._persist_dag_nodes_to_db()

                    # Get current phase and step from DAGTracker
                    current_phase = dag_tracker.get_current_phase()
                    current_step = dag_tracker.get_current_step_number()

                    # Add phase info to meta
                    meta = kwargs.pop('meta', {}) or {}
                    meta['workflow_phase'] = current_phase
                    if current_step is not None:
                        meta['step_number'] = current_step

                    dag_tracker.event_repo.create_event(
                        run_id=dag_tracker.run_id,
                        node_id=current_node_id,
                        event_type=event_type,
                        execution_order=dag_tracker.execution_order_counter,
                        agent_name=agent_name,
                        meta=meta,
                        **kwargs
                    )
                except Exception as e:
                    print(f"Error creating {event_type} event: {e}")
                    if dag_tracker.db_session:
                        dag_tracker.db_session.rollback()

        def on_agent_msg(agent, role, content, metadata):
            import re
            try:
                code_blocks = re.findall(r'```(\w*)\n([\s\S]*?)```', content) if content else []
                create_execution_event(
                    event_type="agent_call",
                    agent_name=agent,
                    event_subtype="message",
                    status="completed",
                    inputs={"role": role, "message": content[:500] if content else ""},
                    outputs={"full_content": content[:3000] if content else ""},
                    meta={"has_code": len(code_blocks) > 0, **(metadata or {})}
                )
            except Exception as e:
                print(f"Error in on_agent_msg callback: {e}")

        def on_code_exec(agent, code, language, result):
            try:
                create_execution_event(
                    event_type="code_exec",
                    agent_name=agent,
                    event_subtype="executed",
                    status="completed" if result and "error" not in str(result).lower() else "failed",
                    inputs={"language": language, "code": code[:2000] if code else ""},
                    outputs={"result": result[:2000] if result else None},
                    meta={"language": language}
                )
            except Exception as e:
                print(f"Error in on_code_exec callback: {e}")

        def on_tool(agent, tool_name, arguments, result):
            try:
                import json
                args_str = json.dumps(arguments, default=str)[:500] if isinstance(arguments, dict) else str(arguments)[:500]
                create_execution_event(
                    event_type="tool_call",
                    agent_name=agent,
                    event_subtype="invoked",
                    status="completed" if result else "failed",
                    inputs={"tool": tool_name, "args": args_str},
                    outputs={"result": str(result)[:2000] if result else None},
                    meta={"tool_name": tool_name}
                )
            except Exception as e:
                print(f"Error in on_tool callback: {e}")

        def on_phase_change(phase: str, step_number: int = None):
            """Handle phase change events from the workflow"""
            if dag_tracker:
                dag_tracker.set_phase(phase, step_number)
                print(f"[TaskExecutor] Phase changed to: {phase}, step: {step_number}")

        def on_planning_complete_tracking(plan_info):
            """Track files and sync DAGTracker after planning phase completes"""
            if dag_tracker:
                # Sync DAGTracker internal state with the dynamically added step nodes
                # This ensures DAGTracker.nodes stays consistent for subsequent updates
                if plan_info and plan_info.steps:
                    asyncio.run_coroutine_threadsafe(
                        dag_tracker.add_step_nodes(plan_info.steps), loop
                    ).result(timeout=5.0)
                    # Mark planning as completed in tracker
                    asyncio.run_coroutine_threadsafe(
                        dag_tracker.update_node_status("planning", "completed"), loop
                    ).result(timeout=5.0)
                    # Note: Human review is tracked as events within the planning phase, not a separate node
                # Track files created during planning
                dag_tracker.track_files_in_work_dir(task_work_dir, "planning")
                print(f"[TaskExecutor] Tracked planning files and synced DAG")

        def on_step_start_tracking(step_info):
            """Update DAGTracker when step starts"""
            if dag_tracker:
                step_node_id = f"step_{step_info.step_number}"
                asyncio.run_coroutine_threadsafe(
                    dag_tracker.update_node_status(step_node_id, "running"), loop
                ).result(timeout=5.0)

        def on_step_complete_tracking(step_info):
            """Track files and update DAGTracker after each step completes"""
            if dag_tracker:
                step_node_id = f"step_{step_info.step_number}"
                asyncio.run_coroutine_threadsafe(
                    dag_tracker.update_node_status(step_node_id, "completed", work_dir=task_work_dir), loop
                ).result(timeout=5.0)
                dag_tracker.track_files_in_work_dir(task_work_dir, step_node_id)
                print(f"[TaskExecutor] Tracked files for step {step_info.step_number}")

        def on_step_failed_tracking(step_info):
            """Update DAGTracker when step fails"""
            if dag_tracker:
                step_node_id = f"step_{step_info.step_number}"
                asyncio.run_coroutine_threadsafe(
                    dag_tracker.update_node_status(step_node_id, "failed", error=step_info.error), loop
                ).result(timeout=5.0)

        event_tracking_callbacks = WorkflowCallbacks(
            on_agent_message=on_agent_msg,
            on_code_execution=on_code_exec,
            on_tool_call=on_tool,
            on_phase_change=on_phase_change,
            on_planning_complete=on_planning_complete_tracking,
            on_step_start=on_step_start_tracking,
            on_step_complete=on_step_complete_tracking,
            on_step_failed=on_step_failed_tracking,
        )

        pause_callbacks = WorkflowCallbacks(
            should_continue=should_continue,
            on_pause_check=sync_pause_check
        )

        workflow_callbacks = merge_callbacks(
            ws_callbacks, create_print_callbacks(),
            pause_callbacks, event_tracking_callbacks
        )

        def run_cmbagent():
            """Execute CMBAgent in thread pool"""
            original_stdout = sys.stdout
            original_stderr = sys.stderr

            class StreamWrapper:
                def __init__(self, original, capture, loop):
                    self.original = original
                    self.capture = capture
                    self.loop = loop

                def write(self, text):
                    if self.original:
                        self.original.write(text)
                    if text.strip():
                        asyncio.run_coroutine_threadsafe(
                            self.capture.write(text), self.loop
                        )
                    return len(text)

                def flush(self):
                    if self.original:
                        self.original.flush()

                def fileno(self):
                    """Return file descriptor if available, otherwise raise AttributeError"""
                    if hasattr(self.original, 'fileno'):
                        return self.original.fileno()
                    raise AttributeError("fileno not available")

                def isatty(self):
                    return False

            try:
                sys.stdout = StreamWrapper(original_stdout, stream_capture, loop)
                sys.stderr = StreamWrapper(original_stderr, stream_capture, loop)

                import builtins
                original_print = builtins.print

                def custom_print(*args, **kwargs):
                    output = " ".join(str(arg) for arg in args)
                    asyncio.run_coroutine_threadsafe(
                        stream_capture.write(output + "\n"), loop
                    )
                    if original_stdout:
                        original_stdout.write(output + "\n")
                        original_stdout.flush()

                builtins.print = custom_print

                # Set up AG2 IOStream capture
                try:
                    from autogen.io.base import IOStream
                    ag2_iostream = AG2IOStreamCapture(websocket, task_id, send_ws_event, loop)
                    IOStream.set_global_default(ag2_iostream)
                except Exception as e:
                    print(f"Could not set AG2 IOStream: {e}")

                # Execute based on mode
                if mode == "planning-control":
                    # Set up approval configuration for HITL
                    approval_config = None
                    approval_mode = config.get("approvalMode", "none")
                    
                    if approval_mode != "none":
                        from cmbagent.database.approval_types import ApprovalMode, ApprovalConfig
                        
                        if approval_mode == "after_planning":
                            approval_config = ApprovalConfig(mode=ApprovalMode.AFTER_PLANNING)
                        elif approval_mode == "before_each_step":
                            approval_config = ApprovalConfig(mode=ApprovalMode.BEFORE_EACH_STEP)
                        elif approval_mode == "on_error":
                            approval_config = ApprovalConfig(mode=ApprovalMode.ON_ERROR)
                        elif approval_mode == "manual":
                            approval_config = ApprovalConfig(mode=ApprovalMode.MANUAL)
                        
                        print(f"[TaskExecutor] HITL enabled with mode: {approval_mode}")
                    
                    # Always using phase-based workflow
                    print(f"[TaskExecutor] Using phase-based workflow for planning-control")
                    
                    results = cmbagent.planning_and_control_context_carryover(
                        task=task,
                        max_rounds_control=max_rounds,
                        max_n_attempts=max_attempts,
                        max_plan_steps=max_plan_steps,
                        n_plan_reviews=n_plan_reviews,
                        engineer_model=engineer_model,
                        researcher_model=researcher_model,
                        planner_model=planner_model,
                        plan_reviewer_model=plan_reviewer_model,
                        plan_instructions=plan_instructions if plan_instructions.strip() else None,
                        work_dir=task_work_dir,
                        api_keys=api_keys,
                        clear_work_dir=False,
                        default_formatter_model=default_formatter_model,
                        default_llm_model=default_llm_model,
                        callbacks=workflow_callbacks,
                        approval_config=approval_config
                    )
                elif mode == "hitl-interactive":
                    # HITL Interactive mode - full human-in-the-loop workflow
                    from cmbagent.workflows import hitl_workflow
                    from cmbagent.database.websocket_approval_manager import WebSocketApprovalManager

                    # Get HITL-specific config
                    hitl_variant = config.get("hitlVariant", "full_interactive")
                    max_human_iterations = config.get("maxHumanIterations", 3)
                    approval_mode = config.get("approvalMode", "both")
                    allow_plan_modification = config.get("allowPlanModification", True)
                    allow_step_skip = config.get("allowStepSkip", True)
                    allow_step_retry = config.get("allowStepRetry", True)
                    show_step_context = config.get("showStepContext", True)

                    # Create WebSocket-based approval manager for UI interaction
                    hitl_approval_manager = WebSocketApprovalManager(ws_send_event, task_id)
                    print(f"[TaskExecutor] Created WebSocket approval manager for HITL")

                    print(f"[TaskExecutor] Using HITL workflow variant: {hitl_variant}")

                    # Select workflow based on variant
                    if hitl_variant == "planning_only":
                        results = hitl_workflow.hitl_planning_only_workflow(
                            task=task,
                            max_rounds_planning=50,
                            max_rounds_control=max_rounds,
                            max_plan_steps=max_plan_steps,
                            max_human_iterations=max_human_iterations,
                            n_plan_reviews=n_plan_reviews,
                            allow_plan_modification=allow_plan_modification,
                            planner_model=planner_model,
                            engineer_model=engineer_model,
                            researcher_model=researcher_model,
                            work_dir=task_work_dir,
                            api_keys=api_keys,
                            clear_work_dir=False,
                            default_formatter_model=default_formatter_model,
                            default_llm_model=default_llm_model,
                            callbacks=workflow_callbacks,
                            approval_manager=hitl_approval_manager,
                        )
                    elif hitl_variant == "error_recovery":
                        results = hitl_workflow.hitl_error_recovery_workflow(
                            task=task,
                            max_rounds_planning=50,
                            max_rounds_control=max_rounds,
                            max_plan_steps=max_plan_steps,
                            n_plan_reviews=n_plan_reviews,
                            max_n_attempts=max_attempts,
                            allow_step_retry=allow_step_retry,
                            allow_step_skip=allow_step_skip,
                            planner_model=planner_model,
                            plan_reviewer_model=plan_reviewer_model,
                            engineer_model=engineer_model,
                            researcher_model=researcher_model,
                            work_dir=task_work_dir,
                            api_keys=api_keys,
                            clear_work_dir=False,
                            default_formatter_model=default_formatter_model,
                            default_llm_model=default_llm_model,
                            callbacks=workflow_callbacks,
                            approval_manager=hitl_approval_manager,
                        )
                    else:  # full_interactive (default)
                        results = hitl_workflow.hitl_interactive_workflow(
                            task=task,
                            max_rounds_control=max_rounds,
                            max_n_attempts=max_attempts,
                            max_plan_steps=max_plan_steps,
                            max_human_iterations=max_human_iterations,
                            n_plan_reviews=n_plan_reviews,
                            approval_mode=approval_mode,
                            allow_plan_modification=allow_plan_modification,
                            allow_step_skip=allow_step_skip,
                            allow_step_retry=allow_step_retry,
                            show_step_context=show_step_context,
                            planner_model=planner_model,
                            engineer_model=engineer_model,
                            researcher_model=researcher_model,
                            work_dir=task_work_dir,
                            api_keys=api_keys,
                            clear_work_dir=False,
                            default_formatter_model=default_formatter_model,
                            default_llm_model=default_llm_model,
                            callbacks=workflow_callbacks,
                            approval_manager=hitl_approval_manager,
                        )
                elif mode == "copilot":
                    # Copilot mode - flexible assistant that adapts to task complexity
                    from cmbagent.workflows.copilot import copilot, continue_copilot_sync
                    from cmbagent.database.websocket_approval_manager import WebSocketApprovalManager

                    # Check if this is a continuation of an existing session
                    existing_session_id = config.get("copilotSessionId")
                    
                    if existing_session_id:
                        # Continue existing session
                        print(f"[TaskExecutor] Continuing copilot session: {existing_session_id}")
                        copilot_approval_manager = WebSocketApprovalManager(ws_send_event, task_id)
                        
                        try:
                            results = continue_copilot_sync(
                                session_id=existing_session_id,
                                additional_context=task,
                            )
                        except Exception as e:
                            print(f"[TaskExecutor] Session continuation failed: {e}, starting new session")
                            existing_session_id = None  # Fall through to new session

                    if not existing_session_id:
                        # Get copilot-specific config
                        available_agents = config.get("availableAgents", ["engineer", "researcher"])
                        enable_planning = config.get("enablePlanning", True)
                        use_dynamic_routing = config.get("useDynamicRouting", True)
                        complexity_threshold = config.get("complexityThreshold", 50)
                        continuous_mode = config.get("continuousMode", False)
                        copilot_approval_mode = config.get("approvalMode", "after_step")
                        conversational = config.get("conversational", False) or copilot_approval_mode == "conversational"
                        control_model = config.get("controlModel", planner_model)  # Use planner model as default
                        tool_approval = config.get("toolApproval", "none")  # "prompt" | "auto_allow_all" | "none"
                        intelligent_routing = config.get("intelligentRouting", "balanced")  # "aggressive" | "balanced" | "minimal"

                        # Create WebSocket-based approval manager for HITL interactions
                        copilot_approval_manager = WebSocketApprovalManager(ws_send_event, task_id)
                        print(f"[TaskExecutor] Created WebSocket approval manager for Copilot")
                        print(f"[TaskExecutor] Copilot config: agents={available_agents}, planning={enable_planning}, dynamic_routing={use_dynamic_routing}, continuous={continuous_mode}, tool_approval={tool_approval}")

                        # Run copilot workflow (synchronous - runs in ThreadPoolExecutor)
                        results = copilot(
                            task=task,
                            available_agents=available_agents,
                            engineer_model=engineer_model,
                            researcher_model=researcher_model,
                            planner_model=planner_model,
                            control_model=control_model,
                            enable_planning=enable_planning,
                            use_dynamic_routing=use_dynamic_routing,
                            complexity_threshold=complexity_threshold,
                            continuous_mode=continuous_mode,
                            max_turns=config.get("maxTurns", 20),
                            max_rounds=max_rounds,
                            max_plan_steps=max_plan_steps,
                            max_n_attempts=max_attempts,
                            approval_mode=copilot_approval_mode,
                            conversational=conversational,
                            tool_approval=tool_approval,
                            intelligent_routing=intelligent_routing,
                            auto_approve_simple=config.get("autoApproveSimple", True),
                            engineer_instructions=config.get("engineerInstructions", ""),
                            researcher_instructions=config.get("researcherInstructions", ""),
                            planner_instructions=plan_instructions,
                            work_dir=task_work_dir,
                            api_keys=api_keys,
                            clear_work_dir=False,
                            callbacks=workflow_callbacks,
                            approval_manager=copilot_approval_manager,
                        )
                elif mode == "idea-generation":
                    # Always using phase-based workflow
                    print(f"[TaskExecutor] Using phase-based workflow for idea-generation")
                    
                    results = cmbagent.planning_and_control_context_carryover(
                        task=task,
                        max_rounds_control=max_rounds,
                        max_n_attempts=max_attempts,
                        max_plan_steps=max_plan_steps,
                        n_plan_reviews=n_plan_reviews,
                        idea_maker_model=idea_maker_model,
                        idea_hater_model=idea_hater_model,
                        planner_model=planner_model,
                        plan_reviewer_model=plan_reviewer_model,
                        plan_instructions=plan_instructions if plan_instructions.strip() else None,
                        work_dir=task_work_dir,
                        api_keys=api_keys,
                        clear_work_dir=False,
                        default_formatter_model=default_formatter_model,
                        default_llm_model=default_llm_model,
                        callbacks=workflow_callbacks
                    )
                elif mode == "ocr":
                    pdf_path = task.strip()
                    if pdf_path.startswith("~"):
                        pdf_path = os.path.expanduser(pdf_path)

                    if not os.path.exists(pdf_path):
                        raise ValueError(f"Path does not exist: {pdf_path}")

                    output_dir = ocr_output_dir if ocr_output_dir and ocr_output_dir.strip() else None

                    if os.path.isfile(pdf_path):
                        results = cmbagent.process_single_pdf(
                            pdf_path=pdf_path,
                            save_markdown=save_markdown,
                            save_json=save_json,
                            save_text=save_text,
                            output_dir=output_dir,
                            work_dir=task_work_dir
                        )
                    elif os.path.isdir(pdf_path):
                        results = cmbagent.process_folder(
                            folder_path=pdf_path,
                            save_markdown=save_markdown,
                            save_json=save_json,
                            save_text=save_text,
                            output_dir=output_dir,
                            max_workers=max_workers,
                            work_dir=task_work_dir
                        )
                    else:
                        raise ValueError(f"Path is neither a file nor a directory: {pdf_path}")
                elif mode == "arxiv":
                    results = cmbagent.arxiv_filter(
                        input_text=task,
                        work_dir=task_work_dir
                    )
                elif mode == "enhance-input":
                    max_depth = config.get("maxDepth", 10)
                    results = cmbagent.preprocess_task(
                        text=task,
                        work_dir=task_work_dir,
                        max_workers=max_workers,
                        clear_work_dir=False
                    )
                else:
                    # One Shot mode
                    results = cmbagent.one_shot(
                        task=task,
                        max_rounds=max_rounds,
                        max_n_attempts=max_attempts,
                        engineer_model=engineer_model,
                        agent=agent,
                        work_dir=task_work_dir,
                        api_keys=api_keys,
                        clear_work_dir=False,
                        default_formatter_model=default_formatter_model,
                        default_llm_model=default_llm_model
                    )

                return results

            finally:
                builtins.print = original_print
                sys.stdout = original_stdout
                sys.stderr = original_stderr

        # Run CMBAgent in executor
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_cmbagent)

            while not future.done():
                await asyncio.sleep(1)

                # Check if cancelled
                if services_available and _execution_service.is_cancelled(task_id):
                    print(f"Task {task_id} cancelled")
                    future.cancel()
                    await send_ws_event(
                        websocket, "workflow_cancelled",
                        {"message": "Workflow cancelled by user"},
                        run_id=task_id
                    )
                    return

                # Check if paused
                if services_available:
                    await _execution_service.wait_if_paused(task_id)

                await send_ws_event(
                    websocket, "heartbeat",
                    {"timestamp": time.time()},
                    run_id=task_id
                )

            results = future.result()

        execution_time = time.time() - start_time

        # Update DAG nodes to completed status
        if dag_tracker and dag_tracker.node_statuses:
            for node_id in dag_tracker.node_statuses:
                if node_id != "terminator":
                    await dag_tracker.update_node_status(node_id, "completed")
                    dag_tracker.track_files_in_work_dir(task_work_dir, node_id)
            if "terminator" in dag_tracker.node_statuses:
                await dag_tracker.update_node_status("terminator", "completed")

        # Mark workflow as completed
        if services_available:
            _workflow_service.complete_workflow(task_id)

        await send_ws_event(
            websocket, "output",
            {"message": f"✅ Task completed in {execution_time:.2f} seconds"},
            run_id=task_id
        )

        await send_ws_event(
            websocket, "result",
            {
                "execution_time": execution_time,
                "chat_history": getattr(results, 'chat_history', []) if hasattr(results, 'chat_history') else [],
                "final_context": getattr(results, 'final_context', {}) if hasattr(results, 'final_context') else {},
                "session_id": results.get('session_id') if isinstance(results, dict) else None,
                "work_dir": task_work_dir,
                "base_work_dir": work_dir,
                "mode": mode
            },
            run_id=task_id
        )

        await send_ws_event(
            websocket, "complete",
            {"message": "Task execution completed successfully"},
            run_id=task_id
        )

    except Exception as e:
        error_msg = f"Error executing CMBAgent task: {str(e)}"
        print(error_msg)

        if dag_tracker and dag_tracker.node_statuses:
            for node_id in dag_tracker.node_statuses:
                await dag_tracker.update_node_status(node_id, "failed", error=error_msg)

        if services_available:
            _workflow_service.fail_workflow(task_id, error_msg)

        await send_ws_event(
            websocket, "error",
            {"message": error_msg},
            run_id=task_id
        )
