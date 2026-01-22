"""
Workflow Callbacks - Event hooks for workflow execution

This module provides a callback system for tracking workflow execution events.
Designed for long-running deep research workflows that can span days.

Key features:
- Database-backed state persistence
- WebSocket event emission for real-time UI updates
- Recovery/resume support for interrupted workflows
- Autogen-agnostic (no dependency on autogen internals)
"""

from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import time


class WorkflowPhase(Enum):
    """Phases of workflow execution"""
    INITIALIZING = "initializing"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class StepStatus(Enum):
    """Status of a workflow step"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepInfo:
    """Information about a workflow step"""
    step_number: int
    goal: str  # Step goal/description
    description: str  # Deprecated: use goal instead
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    execution_time: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None  # Human-readable summary of what was accomplished


@dataclass
class PlanInfo:
    """Information about the generated plan"""
    task: str
    num_steps: int
    steps: List[Dict[str, Any]]
    plan_text: str
    planning_time: float


@dataclass
class WorkflowCallbacks:
    """
    Callback hooks for workflow execution events.
    
    Usage:
        callbacks = WorkflowCallbacks(
            on_planning_start=lambda task, config: print(f"Planning: {task}"),
            on_step_start=lambda step, agent, desc: print(f"Step {step}: {agent}"),
            on_step_complete=lambda step, result, time: print(f"Step {step} done"),
        )
        
        planning_and_control_context_carryover(
            task="...",
            callbacks=callbacks,
            ...
        )
    """
    
    # Planning phase callbacks
    on_planning_start: Optional[Callable[[str, Dict[str, Any]], None]] = None
    on_planning_complete: Optional[Callable[[PlanInfo], None]] = None
    
    # Step execution callbacks
    on_step_start: Optional[Callable[[StepInfo], None]] = None
    on_step_complete: Optional[Callable[[StepInfo], None]] = None
    on_step_failed: Optional[Callable[[StepInfo], None]] = None
    
    # Workflow lifecycle callbacks
    on_workflow_start: Optional[Callable[[str, Dict[str, Any]], None]] = None
    on_workflow_complete: Optional[Callable[[Dict[str, Any], float], None]] = None
    on_workflow_failed: Optional[Callable[[str, Optional[int]], None]] = None
    
    # Progress updates (for finer granularity within steps)
    on_progress: Optional[Callable[[str, Dict[str, Any]], None]] = None
    
    # Agent transition callbacks (optional, for detailed tracking)
    on_agent_start: Optional[Callable[[str, int], None]] = None  # agent_name, step_number
    on_agent_complete: Optional[Callable[[str, int, Dict[str, Any]], None]] = None
    
    # Pause/Resume support - called before each step to check if should continue
    # Returns True to continue, False to pause/stop
    should_continue: Optional[Callable[[], bool]] = None
    # Called when workflow is paused, with a wait function to block until resumed
    on_pause_check: Optional[Callable[[], None]] = None

    # Cost tracking callback - called when cost data is available
    # Signature: on_cost_update(cost_data: Dict[str, Any]) where cost_data contains:
    #   - total_cost: float
    #   - total_tokens: int
    #   - model_breakdown: List[Dict] with model, cost, tokens
    #   - agent_breakdown: List[Dict] with agent, cost, tokens
    on_cost_update: Optional[Callable[[Dict[str, Any]], None]] = None

    # Agent message callback - called for every agent message during execution
    # Signature: on_agent_message(agent: str, role: str, content: str, metadata: Dict)
    # This captures ALL agent communications for comprehensive logging
    on_agent_message: Optional[Callable[[str, str, str, Dict[str, Any]], None]] = None

    # Code execution callback - called when code is generated or executed
    # Signature: on_code_execution(agent: str, code: str, language: str, result: Optional[str])
    on_code_execution: Optional[Callable[[str, str, str, Optional[str]], None]] = None

    # Tool call callback - called when agents make tool/function calls
    # Signature: on_tool_call(agent: str, tool_name: str, arguments: Dict, result: Optional[Any])
    on_tool_call: Optional[Callable[[str, str, Dict[str, Any], Optional[Any]], None]] = None

    def invoke_planning_start(self, task: str, config: Dict[str, Any]) -> None:
        """Safely invoke on_planning_start callback"""
        if self.on_planning_start:
            try:
                self.on_planning_start(task, config)
            except Exception as e:
                print(f"Error in on_planning_start callback: {e}")
    
    def invoke_planning_complete(self, plan_info: PlanInfo) -> None:
        """Safely invoke on_planning_complete callback"""
        if self.on_planning_complete:
            try:
                self.on_planning_complete(plan_info)
            except Exception as e:
                print(f"Error in on_planning_complete callback: {e}")
    
    def invoke_step_start(self, step_info: StepInfo) -> None:
        """Safely invoke on_step_start callback"""
        if self.on_step_start:
            try:
                self.on_step_start(step_info)
            except Exception as e:
                print(f"Error in on_step_start callback: {e}")
    
    def invoke_step_complete(self, step_info: StepInfo) -> None:
        """Safely invoke on_step_complete callback"""
        if self.on_step_complete:
            try:
                self.on_step_complete(step_info)
            except Exception as e:
                print(f"Error in on_step_complete callback: {e}")
    
    def invoke_step_failed(self, step_info: StepInfo) -> None:
        """Safely invoke on_step_failed callback"""
        if self.on_step_failed:
            try:
                self.on_step_failed(step_info)
            except Exception as e:
                print(f"Error in on_step_failed callback: {e}")
    
    def invoke_workflow_start(self, task: str, config: Dict[str, Any]) -> None:
        """Safely invoke on_workflow_start callback"""
        if self.on_workflow_start:
            try:
                self.on_workflow_start(task, config)
            except Exception as e:
                print(f"Error in on_workflow_start callback: {e}")
    
    def invoke_workflow_complete(self, final_context: Dict[str, Any], total_time: float) -> None:
        """Safely invoke on_workflow_complete callback"""
        if self.on_workflow_complete:
            try:
                self.on_workflow_complete(final_context, total_time)
            except Exception as e:
                print(f"Error in on_workflow_complete callback: {e}")
    
    def invoke_workflow_failed(self, error: str, step_number: Optional[int] = None) -> None:
        """Safely invoke on_workflow_failed callback"""
        if self.on_workflow_failed:
            try:
                self.on_workflow_failed(error, step_number)
            except Exception as e:
                print(f"Error in on_workflow_failed callback: {e}")
    
    def invoke_progress(self, message: str, data: Dict[str, Any]) -> None:
        """Safely invoke on_progress callback"""
        if self.on_progress:
            try:
                self.on_progress(message, data)
            except Exception as e:
                print(f"Error in on_progress callback: {e}")
    
    def check_should_continue(self) -> bool:
        """
        Check if workflow should continue or pause.
        
        Returns:
            True if should continue, False if should pause/stop
        """
        if self.should_continue:
            try:
                return self.should_continue()
            except Exception as e:
                print(f"Error in should_continue callback: {e}")
                return True  # Default to continue on error
        return True  # Default to continue if no callback set
    
    def invoke_pause_check(self) -> None:
        """
        Invoke pause check - blocks if paused until resumed.
        This should be called before each major step.
        """
        if self.on_pause_check:
            try:
                self.on_pause_check()
            except Exception as e:
                print(f"Error in on_pause_check callback: {e}")

    def invoke_cost_update(self, cost_data: Dict[str, Any]) -> None:
        """
        Safely invoke on_cost_update callback with cost information.

        Args:
            cost_data: Dictionary containing:
                - total_cost: float - Total cost in USD
                - total_tokens: int - Total tokens used
                - model_breakdown: List[Dict] - Per-model breakdown
                - agent_breakdown: List[Dict] - Per-agent breakdown
                - step_id: Optional[str] - Current step if applicable
        """
        if self.on_cost_update:
            try:
                self.on_cost_update(cost_data)
            except Exception as e:
                print(f"Error in on_cost_update callback: {e}")

    def invoke_agent_message(self, agent: str, role: str, content: str, metadata: Dict[str, Any] = None) -> None:
        """
        Safely invoke on_agent_message callback for comprehensive agent logging.

        Args:
            agent: Name of the agent sending the message
            role: Role of the message (e.g., 'assistant', 'user', 'system', 'tool')
            content: The message content
            metadata: Optional additional metadata (e.g., model, tokens, tool_calls)
        """
        if self.on_agent_message:
            try:
                self.on_agent_message(agent, role, content, metadata or {})
            except Exception as e:
                print(f"Error in on_agent_message callback: {e}")

    def invoke_code_execution(self, agent: str, code: str, language: str, result: Optional[str] = None) -> None:
        """
        Safely invoke on_code_execution callback when code is generated/executed.

        Args:
            agent: Name of the agent generating/executing the code
            code: The code content
            language: Programming language (e.g., 'python', 'bash')
            result: Optional execution result or output
        """
        if self.on_code_execution:
            try:
                self.on_code_execution(agent, code, language, result)
            except Exception as e:
                print(f"Error in on_code_execution callback: {e}")

    def invoke_tool_call(self, agent: str, tool_name: str, arguments: Dict[str, Any], result: Optional[Any] = None) -> None:
        """
        Safely invoke on_tool_call callback when agents use tools/functions.

        Args:
            agent: Name of the agent making the tool call
            tool_name: Name of the tool/function being called
            arguments: Arguments passed to the tool
            result: Optional result from the tool call
        """
        if self.on_tool_call:
            try:
                self.on_tool_call(agent, tool_name, arguments, result)
            except Exception as e:
                print(f"Error in on_tool_call callback: {e}")


def create_null_callbacks() -> WorkflowCallbacks:
    """Create a callbacks instance with no handlers (for backward compatibility)"""
    return WorkflowCallbacks()


def create_print_callbacks() -> WorkflowCallbacks:
    """Create a callbacks instance that prints all events (for debugging)"""
    return WorkflowCallbacks(
        on_planning_start=lambda task, config: print(f"📋 Planning started: {task[:100]}..."),
        on_planning_complete=lambda plan: print(f"✅ Planning complete: {plan.num_steps} steps"),
        on_step_start=lambda step: print(f"▶️  Step {step.step_number} started: {step.goal}"),
        on_step_complete=lambda step: print(f"✅ Step {step.step_number} completed in {step.execution_time:.2f}s" if step.execution_time else f"✅ Step {step.step_number} completed"),
        on_step_failed=lambda step: print(f"❌ Step {step.step_number} failed: {step.error}"),
        on_workflow_start=lambda task, config: print(f"🚀 Workflow started"),
        on_workflow_complete=lambda ctx, time: print(f"🎉 Workflow complete in {time:.2f}s"),
        on_workflow_failed=lambda err, step: print(f"💥 Workflow failed at step {step}: {err}"),
    )


def merge_callbacks(*callbacks_list: WorkflowCallbacks) -> WorkflowCallbacks:
    """
    Merge multiple WorkflowCallbacks into one that invokes all of them.
    
    Args:
        *callbacks_list: WorkflowCallbacks instances to merge
        
    Returns:
        New WorkflowCallbacks that invokes all provided callbacks
    """
    import logging
    logger = logging.getLogger(__name__)
    
    def make_merged_callback(method_name: str):
        def merged(*args, **kwargs):
            for cb in callbacks_list:
                callback = getattr(cb, method_name, None)
                if callback:
                    try:
                        callback(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"Error in merged callback {method_name}: {e}")
        return merged
    
    def make_merged_should_continue():
        """Special merge for should_continue - returns False if any callback returns False"""
        def merged():
            for cb in callbacks_list:
                if cb.should_continue:
                    try:
                        if not cb.should_continue():
                            return False
                    except Exception as e:
                        logger.error(f"Error in should_continue callback: {e}")
            return True
        return merged
    
    def make_merged_pause_check():
        """Merge pause check callbacks - call all of them"""
        def merged():
            for cb in callbacks_list:
                if cb.on_pause_check:
                    try:
                        cb.on_pause_check()
                    except Exception as e:
                        logger.error(f"Error in on_pause_check callback: {e}")
        return merged
    
    callback_names = [
        "on_planning_start", "on_planning_complete",
        "on_step_start", "on_step_complete", "on_step_failed",
        "on_workflow_start", "on_workflow_complete", "on_workflow_failed",
        "on_progress", "on_agent_start", "on_agent_complete",
        "on_cost_update",  # Include cost callback in merge
        "on_agent_message", "on_code_execution", "on_tool_call"  # Comprehensive logging callbacks
    ]

    merged_dict = {name: make_merged_callback(name) for name in callback_names}

    # Handle special callbacks
    merged_dict["should_continue"] = make_merged_should_continue()
    merged_dict["on_pause_check"] = make_merged_pause_check()

    return WorkflowCallbacks(**merged_dict)


def create_websocket_callbacks(
    send_event_func: Callable[[str, Dict[str, Any]], None],
    run_id: str,
    total_steps: Optional[int] = None
) -> WorkflowCallbacks:
    """
    Create WorkflowCallbacks that emit WebSocket events.
    
    Args:
        send_event_func: Function to send WebSocket events
            Signature: send(event_type: str, data: dict) -> None
        run_id: Workflow run ID for tagging events
        total_steps: Total number of steps (updated after planning)
        
    Returns:
        WorkflowCallbacks configured for WebSocket emission
    """
    from datetime import datetime, timezone
    
    # Mutable container to track state
    state = {"total_steps": total_steps or 0, "steps_info": []}
    
    def on_planning_start(task: str, config: Dict[str, Any]) -> None:
        send_event_func("dag_node_status_changed", {
            "run_id": run_id,
            "node_id": "planning",
            "old_status": "pending",
            "new_status": "running",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def on_planning_complete(plan_info: PlanInfo) -> None:
        state["total_steps"] = plan_info.num_steps
        state["steps_info"] = plan_info.steps
        
        # Mark planning as complete
        send_event_func("dag_node_status_changed", {
            "run_id": run_id,
            "node_id": "planning",
            "old_status": "running",
            "new_status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Send full DAG update with steps
        nodes = [
            {
                "id": "planning",
                "label": "Planning Phase",
                "type": "planning",
                "status": "completed",
                "step_number": 0
            }
        ]
        
        for i, step in enumerate(plan_info.steps, 1):
            agent = step.get('sub_task_agent', 'engineer')
            description = step.get('sub_task_description', '')
            # Create a meaningful label from the description (first 50 chars) or use agent name
            if description:
                # Clean up the description for label
                label_text = description.strip()[:50]
                if len(description) > 50:
                    label_text += "..."
                label = f"Step {i}: {label_text}"
            else:
                label = f"Step {i}: {agent}"
            nodes.append({
                "id": f"step_{i}",
                "label": label,
                "type": "agent",
                "agent": agent,
                "status": "pending",
                "step_number": i,
                "description": description[:200] if description else ""
            })
        
        nodes.append({
            "id": "terminator",
            "label": "Completion",
            "type": "terminator",
            "status": "pending",
            "step_number": plan_info.num_steps + 1
        })
        
        edges = [{"source": "planning", "target": "step_1"}]
        for i in range(1, plan_info.num_steps):
            edges.append({"source": f"step_{i}", "target": f"step_{i+1}"})
        edges.append({"source": f"step_{plan_info.num_steps}", "target": "terminator"})
        
        send_event_func("dag_updated", {
            "run_id": run_id,
            "nodes": nodes,
            "edges": edges,
            "levels": plan_info.num_steps + 2
        })
    
    def on_step_start(step_info: StepInfo) -> None:
        send_event_func("dag_node_status_changed", {
            "run_id": run_id,
            "node_id": f"step_{step_info.step_number}",
            "old_status": "pending",
            "new_status": "running",
            "step_number": step_info.step_number,
            "total_steps": state["total_steps"],
            "goal": step_info.goal,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def on_step_complete(step_info: StepInfo) -> None:
        send_event_func("dag_node_status_changed", {
            "run_id": run_id,
            "node_id": f"step_{step_info.step_number}",
            "old_status": "running",
            "new_status": "completed",
            "step_number": step_info.step_number,
            "execution_time": step_info.execution_time,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def on_step_failed(step_info: StepInfo) -> None:
        send_event_func("dag_node_status_changed", {
            "run_id": run_id,
            "node_id": f"step_{step_info.step_number}",
            "old_status": "running",
            "new_status": "failed",
            "step_number": step_info.step_number,
            "error": step_info.error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def on_workflow_complete(final_context: Dict[str, Any], total_time: float) -> None:
        send_event_func("dag_node_status_changed", {
            "run_id": run_id,
            "node_id": "terminator",
            "old_status": "pending",
            "new_status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def on_workflow_failed(error: str, failed_step: Optional[int]) -> None:
        send_event_func("workflow_failed", {
            "run_id": run_id,
            "error": error,
            "failed_step": failed_step,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def on_cost_update(cost_data: Dict[str, Any]) -> None:
        """Emit cost_update WebSocket event"""
        send_event_func("cost_update", {
            "run_id": run_id,
            "step_id": cost_data.get("step_id"),
            "model": cost_data.get("model", "unknown"),
            "tokens": cost_data.get("total_tokens", 0),
            "cost_usd": cost_data.get("cost_delta", cost_data.get("total_cost", 0)),
            "total_cost_usd": cost_data.get("total_cost", 0),
            "model_breakdown": cost_data.get("model_breakdown", []),
            "agent_breakdown": cost_data.get("agent_breakdown", []),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def on_agent_message(agent: str, role: str, content: str, metadata: Dict[str, Any]) -> None:
        """Emit agent_message WebSocket event for comprehensive logging"""
        send_event_func("agent_message", {
            "run_id": run_id,
            "agent": agent,
            "role": role,
            "message": content,
            "metadata": metadata,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def on_code_execution(agent: str, code: str, language: str, result: Optional[str]) -> None:
        """Emit code_execution WebSocket event"""
        send_event_func("code_execution", {
            "run_id": run_id,
            "agent": agent,
            "code": code,
            "language": language,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def on_tool_call(agent: str, tool_name: str, arguments: Dict[str, Any], result: Optional[Any]) -> None:
        """Emit tool_call WebSocket event"""
        send_event_func("tool_call", {
            "run_id": run_id,
            "agent": agent,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": str(result) if result is not None else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    return WorkflowCallbacks(
        on_planning_start=on_planning_start,
        on_planning_complete=on_planning_complete,
        on_step_start=on_step_start,
        on_step_complete=on_step_complete,
        on_step_failed=on_step_failed,
        on_workflow_complete=on_workflow_complete,
        on_workflow_failed=on_workflow_failed,
        on_cost_update=on_cost_update,
        on_agent_message=on_agent_message,
        on_code_execution=on_code_execution,
        on_tool_call=on_tool_call
    )


def create_database_callbacks(
    db_session,
    session_id: str,
    run_id: str
) -> WorkflowCallbacks:
    """
    Create WorkflowCallbacks that update database state.
    
    Args:
        db_session: SQLAlchemy database session
        session_id: CMBAgent session ID
        run_id: Workflow run ID
        
    Returns:
        WorkflowCallbacks configured for database updates
    """
    import logging
    logger = logging.getLogger(__name__)
    
    def on_planning_start(task: str, config: Dict[str, Any]) -> None:
        try:
            from cmbagent.database.models import DAGNode, WorkflowRun
            from cmbagent.database.states import WorkflowState
            
            # Update workflow status
            run = db_session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if run:
                run.status = WorkflowState.PLANNING.value
                db_session.commit()
            
            # Update planning node
            planning_node = db_session.query(DAGNode).filter(
                DAGNode.run_id == run_id,
                DAGNode.node_type == "planning"
            ).first()
            if planning_node:
                planning_node.status = "running"
                db_session.commit()
        except Exception as e:
            logger.error(f"Error updating database on planning start: {e}")
    
    def on_planning_complete(plan_info: PlanInfo) -> None:
        try:
            from cmbagent.database.models import DAGNode, WorkflowRun
            from cmbagent.database.states import WorkflowState
            from cmbagent.database.dag_builder import DAGBuilder
            
            # Update workflow status
            run = db_session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if run:
                run.status = WorkflowState.EXECUTING.value
                db_session.commit()
            
            # Update planning node
            planning_node = db_session.query(DAGNode).filter(
                DAGNode.run_id == run_id,
                DAGNode.node_type == "planning"
            ).first()
            if planning_node:
                planning_node.status = "completed"
                db_session.commit()
            
            # Build DAG nodes for steps in database
            try:
                dag_builder = DAGBuilder(db_session, session_id)
                steps = [{"task": s.get("sub_task_description", ""), "agent": s.get("sub_task_agent", "engineer")} for s in plan_info.steps]
                dag_builder.build_from_plan(run_id, {"steps": steps})
            except Exception as e:
                logger.warning(f"Could not build DAG in database: {e}")
                
        except Exception as e:
            logger.error(f"Error updating database on planning complete: {e}")
    
    def on_step_start(step_info: StepInfo) -> None:
        try:
            from cmbagent.database.models import DAGNode
            
            step_node = db_session.query(DAGNode).filter(
                DAGNode.run_id == run_id,
                DAGNode.order_index == step_info.step_number
            ).first()
            if step_node:
                step_node.status = "running"
                db_session.commit()
        except Exception as e:
            logger.error(f"Error updating database on step start: {e}")
    
    def on_step_complete(step_info: StepInfo) -> None:
        try:
            from cmbagent.database.models import DAGNode, WorkflowStep
            
            # Update DAGNode status
            step_node = db_session.query(DAGNode).filter(
                DAGNode.run_id == run_id,
                DAGNode.order_index == step_info.step_number
            ).first()
            if step_node:
                step_node.status = "completed"
            
            # Update WorkflowStep with summary
            workflow_step = db_session.query(WorkflowStep).filter(
                WorkflowStep.run_id == run_id,
                WorkflowStep.step_number == step_info.step_number
            ).first()
            if workflow_step and step_info.summary:
                workflow_step.summary = step_info.summary
                workflow_step.status = "completed"
            
            db_session.commit()
        except Exception as e:
            logger.error(f"Error updating database on step complete: {e}")
    
    def on_step_failed(step_info: StepInfo) -> None:
        try:
            from cmbagent.database.models import DAGNode
            
            step_node = db_session.query(DAGNode).filter(
                DAGNode.run_id == run_id,
                DAGNode.order_index == step_info.step_number
            ).first()
            if step_node:
                step_node.status = "failed"
                db_session.commit()
        except Exception as e:
            logger.error(f"Error updating database on step failed: {e}")
    
    def on_workflow_complete(final_context: Dict[str, Any], total_time: float) -> None:
        try:
            from cmbagent.database.models import DAGNode, WorkflowRun
            from cmbagent.database.states import WorkflowState
            
            run = db_session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if run:
                run.status = WorkflowState.COMPLETED.value
                db_session.commit()
            
            # Update terminator node
            terminator = db_session.query(DAGNode).filter(
                DAGNode.run_id == run_id,
                DAGNode.node_type == "terminator"
            ).first()
            if terminator:
                terminator.status = "completed"
                db_session.commit()
        except Exception as e:
            logger.error(f"Error updating database on workflow complete: {e}")
    
    def on_workflow_failed(error: str, failed_step: Optional[int]) -> None:
        try:
            from cmbagent.database.models import WorkflowRun
            from cmbagent.database.states import WorkflowState
            
            run = db_session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if run:
                run.status = WorkflowState.FAILED.value
                db_session.commit()
        except Exception as e:
            logger.error(f"Error updating database on workflow failed: {e}")
    
    return WorkflowCallbacks(
        on_planning_start=on_planning_start,
        on_planning_complete=on_planning_complete,
        on_step_start=on_step_start,
        on_step_complete=on_step_complete,
        on_step_failed=on_step_failed,
        on_workflow_complete=on_workflow_complete,
        on_workflow_failed=on_workflow_failed
    )
