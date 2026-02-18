"""
Swarm Orchestrator - Unified Multi-Agent Orchestration

A single orchestrator that:
- Loads ALL agents into one unified swarm
- Registers ALL tools + phase tools (phases as callable tools)
- Manages conversation rounds with continuation support
- Uses intelligent routing via copilot_control agent
- Supports dynamic phase invocation within the conversation
- Supports CONVERSATIONAL mode (like Claude Code / AG2 human_input_mode="ALWAYS")

Architecture:
    User Task
        → SwarmOrchestrator (all agents + all tools)
        → copilot_control routes dynamically
        → Agents execute with access to phase tools
        → Continuation offered at max_rounds

    Conversational Mode (human_input_mode="ALWAYS"):
        User speaks → Agent analyzes & acts → Results shown → User speaks → ...
        Every round includes a human turn. The human steers the conversation.

This replaces the rigid "route to separate execution path" pattern
with a truly unified swarm where phases are tools agents can invoke.
"""

import asyncio
import logging
import structlog
import uuid
import time
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Union
from enum import Enum

logger = structlog.get_logger(__name__)

from cmbagent.phases import (
    Phase,
    PhaseContext,
    PhaseResult,
    PhaseRegistry,
    PhaseStatus,
    WorkflowContext,
)
from cmbagent.orchestrator.config import OrchestratorConfig
from cmbagent.orchestrator.durable_context import DurableContext, ContextSnapshot


class SwarmStatus(Enum):
    """Status of the swarm orchestrator."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"  # Waiting for continuation
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_INPUT = "waiting_input"


@dataclass
class SwarmState:
    """State tracked by the swarm orchestrator."""
    # Identification
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # Round management
    current_round: int = 0
    max_rounds: int = 100
    total_rounds_across_continuations: int = 0
    continuation_count: int = 0

    # Task tracking
    current_task: str = ""
    tasks_completed: List[Dict[str, Any]] = field(default_factory=list)

    # Conversation state
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Enhanced durable context (replaces shared_context dict)
    context: Optional[DurableContext] = None

    # Phase execution tracking
    phases_executed: List[Dict[str, Any]] = field(default_factory=list)
    active_phase: Optional[str] = None

    # Status
    status: SwarmStatus = SwarmStatus.IDLE
    last_agent: Optional[str] = None

    # Timing
    started_at: Optional[float] = None
    last_activity: Optional[float] = None

    # Conversational mode - human feedback tracking
    accumulated_feedback: str = ""
    turn_feedback: List[Dict[str, Any]] = field(default_factory=list)

    def reset_rounds(self):
        """Reset round counter for continuation."""
        self.current_round = 0
        self.continuation_count += 1

    def increment_round(self):
        """Increment round counters."""
        self.current_round += 1
        self.total_rounds_across_continuations += 1
        self.last_activity = time.time()

    def should_pause_for_continuation(self) -> bool:
        """Check if we should pause and offer continuation."""
        return self.current_round >= self.max_rounds

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            'session_id': self.session_id,
            'run_id': self.run_id,
            'current_round': self.current_round,
            'max_rounds': self.max_rounds,
            'total_rounds': self.total_rounds_across_continuations,
            'continuation_count': self.continuation_count,
            'current_task': self.current_task,
            'tasks_completed': len(self.tasks_completed),
            'phases_executed': len(self.phases_executed),
            'active_phase': self.active_phase,
            'status': self.status.value,
            'last_agent': self.last_agent,
        }


@dataclass
class SwarmConfig:
    """Configuration for the swarm orchestrator."""
    # Round management
    max_rounds: int = 100
    auto_continue: bool = False  # Auto-continue without user prompt
    continuation_prompt: str = "Max rounds reached. Continue? (yes/no): "

    # Agent configuration
    load_all_agents: bool = True  # Load all 49 agents
    available_agents: List[str] = field(default_factory=lambda: [
        "engineer", "researcher", "web_surfer",
        "executor", "executor_bash", "installer",
        "planner", "plan_reviewer", "control",
        "summarizer", "admin",
    ])
    lightweight_mode: bool = False  # True = only load available_agents

    # Phase tools configuration
    enable_phase_tools: bool = True  # Allow phases to be invoked as tools
    available_phases: List[str] = field(default_factory=lambda: [
        "planning", "control", "one_shot",
        "hitl_planning", "hitl_control",
        "hitl_checkpoint", "idea_generation",
        "copilot",
    ])

    # Routing configuration
    use_copilot_control: bool = True  # Use LLM routing vs manual
    routing_model: str = "gpt-4o"

    # Intelligent routing mode - controls clarification and proposal behavior
    # "aggressive" = Always ask for clarification on ambiguous tasks, propose approaches for complex tasks
    # "balanced" = Ask for clarification only when clearly ambiguous, propose for very complex tasks
    # "minimal" = Rarely ask for clarification, prefer direct action
    intelligent_routing: str = "balanced"

    # HITL configuration
    approval_mode: str = "after_step"  # before_step, after_step, both, none, conversational

    # Conversational mode (like Claude Code / AG2 human_input_mode="ALWAYS")
    # When True, the human is a participant in every round of the conversation.
    # After each agent action, the human gets to respond, redirect, or provide feedback.
    conversational: bool = False

    # Tool approval mode (like Claude Code's permission system)
    # "prompt" = ask user before dangerous ops (with auto-allow for session)
    # "auto_allow_all" = auto-allow everything
    # "none" = no tool-level approval
    tool_approval: str = "none"

    # Model configuration
    default_model: str = "gpt-4o"
    agent_models: Dict[str, str] = field(default_factory=dict)

    # Execution
    timeout_per_round: float = 300.0  # 5 minutes per round
    parallel_tool_calls: bool = True

    # Callbacks
    on_round_start: Optional[Callable] = None
    on_round_end: Optional[Callable] = None
    on_agent_message: Optional[Callable] = None
    on_phase_invoked: Optional[Callable] = None
    on_continuation_needed: Optional[Callable] = None


class SwarmOrchestrator:
    """
    Unified swarm orchestrator that manages all agents and tools.

    Key features:
    1. Single swarm with ALL agents loaded
    2. Phases as tools - agents can invoke phases dynamically
    3. Round management with continuation support
    4. Intelligent routing via copilot_control
    5. Shared context across all operations

    Usage:
        orchestrator = SwarmOrchestrator(config)
        await orchestrator.initialize(api_keys, work_dir)

        # Run a task
        result = await orchestrator.run("Build a REST API")

        # Continue if paused
        if result.status == SwarmStatus.PAUSED:
            result = await orchestrator.continue_execution()
    """

    def __init__(
        self,
        config: SwarmConfig = None,
        orchestrator_config: OrchestratorConfig = None,
    ):
        self.config = config or SwarmConfig()
        self.orchestrator_config = orchestrator_config or OrchestratorConfig()

        # State
        self.state = SwarmState(max_rounds=self.config.max_rounds)
        
        # Initialize durable context (don't include protected keys in initial_data)
        self.state.context = DurableContext(
            session_id=self.state.session_id,
            initial_data={}
        )
        # Set and protect critical keys
        self.state.context.set('session_id', self.state.session_id, protected=True)
        self.state.context.set('run_id', self.state.run_id, protected=True)

        # Components (initialized later)
        self._cmbagent = None
        self._agents: Dict[str, Any] = {}
        self._tools: Dict[str, Callable] = {}
        self._phase_tools: Dict[str, Callable] = {}

        # Context
        self._api_keys: Dict[str, str] = {}
        self._work_dir: str = ""
        self._approval_manager = None
        self._callbacks = None  # Stored during initialize()

        # Phase execution context
        self._phase_context: Optional[PhaseContext] = None
        self._workflow_context: Optional[WorkflowContext] = None

    @property
    def _is_conversational(self) -> bool:
        """Check if running in conversational mode."""
        return (
            self.config.conversational
            or self.config.approval_mode == "conversational"
        )

    async def initialize(
        self,
        api_keys: Dict[str, str],
        work_dir: str,
        approval_manager=None,
        callbacks: Dict[str, Any] = None,
    ) -> None:
        """
        Initialize the swarm orchestrator.

        Args:
            api_keys: API keys for LLM providers
            work_dir: Working directory for file operations
            approval_manager: Optional HITL approval manager
            callbacks: Optional callback functions
        """
        from cmbagent import CMBAgent

        self._api_keys = api_keys
        self._work_dir = work_dir
        self._approval_manager = approval_manager
        self._callbacks = callbacks  # Store full callbacks object for phase execution

        # Resolve orchestrator directories relative to work_dir
        if work_dir:
            self.orchestrator_config.resolve_dirs(work_dir)

        # Update config with callbacks
        if callbacks:
            if hasattr(callbacks, 'on_round_start') and callbacks.on_round_start:
                self.config.on_round_start = callbacks.on_round_start
            if hasattr(callbacks, 'on_round_end') and callbacks.on_round_end:
                self.config.on_round_end = callbacks.on_round_end
            if hasattr(callbacks, 'on_agent_message') and callbacks.on_agent_message:
                self.config.on_agent_message = callbacks.on_agent_message

        # Ensure work_dir exists and has proper structure
        import os
        os.makedirs(work_dir, exist_ok=True)
        os.makedirs(os.path.join(work_dir, "codebase"), exist_ok=True)
        os.makedirs(os.path.join(work_dir, "planning"), exist_ok=True)
        os.makedirs(os.path.join(work_dir, "control"), exist_ok=True)
        
        # Initialize workflow context
        self._workflow_context = WorkflowContext(
            workflow_id=f"swarm_{self.state.session_id}",
            run_id=self.state.session_id,  # Use session_id as run_id
            task="",  # Set when run() is called
            work_dir=work_dir,
            api_keys=api_keys,
        )

        # Determine which agents to load
        agents_to_load = self._determine_agents_to_load()

        # Build agent config
        agent_configs = self._build_agent_configs(agents_to_load)

        # Initialize CMBAgent with all agents
        self._cmbagent = CMBAgent(
            agent_configs=agent_configs,
            data_dir=work_dir,
            api_keys=api_keys,
        )

        # Register phase tools if enabled
        if self.config.enable_phase_tools:
            self._register_phase_tools()

        # Register phase tools with agents
        self._attach_phase_tools_to_agents()

        # Setup copilot tool approval handoffs (if enabled)
        if self.config.tool_approval != "none":
            self._setup_tool_approval()

        self.state.status = SwarmStatus.IDLE
        self.state.started_at = time.time()

    def _determine_agents_to_load(self) -> List[str]:
        """Determine which agents to load based on config."""
        if self.config.load_all_agents and not self.config.lightweight_mode:
            # Load all available agent types
            return self._get_all_agent_types()
        else:
            return self.config.available_agents

    def _get_all_agent_types(self) -> List[str]:
        """Get all available agent types."""
        # Core execution agents
        core = [
            "engineer", "researcher", "web_surfer",
            "executor", "executor_bash", "installer",
        ]

        # Planning agents
        planning = [
            "planner", "plan_reviewer", "plan_setter",
            "plan_recorder", "control", "control_starter",
        ]

        # Idea agents
        idea = ["idea_maker", "idea_hater", "idea_saver"]

        # Response formatters
        formatters = [
            "engineer_response_formatter",
            "researcher_response_formatter",
            "planner_response_formatter",
        ]

        # Utility agents
        utility = [
            "admin", "terminator", "summarizer",
            "task_recorder", "task_improver",
        ]

        # Copilot control (for routing) and assistant (for user interaction)
        copilot = ["copilot_control", "assistant"]

        return core + planning + idea + formatters + utility + copilot

    def _build_agent_configs(self, agents: List[str]) -> Dict[str, Dict]:
        """Build agent configurations."""
        configs = {}
        for agent_name in agents:
            model = self.config.agent_models.get(
                agent_name,
                self.config.default_model
            )
            configs[agent_name] = {
                "model": model,
                "api_key": self._api_keys.get("openai", ""),
            }
        return configs

    def _register_phase_tools(self) -> None:
        """Register phases as callable tools."""
        for phase_type in self.config.available_phases:
            tool_func = self._create_phase_tool(phase_type)
            self._phase_tools[f"invoke_{phase_type}_phase"] = tool_func

    def _create_phase_tool(self, phase_type: str) -> Callable:
        """Create a tool function that executes a phase."""
        orchestrator = self  # Capture reference

        async def phase_tool(
            task: str = None,
            config: Dict[str, Any] = None,
            **kwargs
        ) -> str:
            """
            Execute a phase and return results.

            This is a dynamic tool that executes an actual phase
            within the orchestrator context.
            """
            return await orchestrator._execute_phase_as_tool(
                phase_type=phase_type,
                task=task,
                config=config or {},
                **kwargs
            )

        # Set function metadata for AG2
        phase_tool.__name__ = f"invoke_{phase_type}_phase"
        phase_tool.__doc__ = f"""
        Invoke the {phase_type} phase to execute a specialized workflow.

        Args:
            task: Task or input for the phase
            config: Optional phase configuration

        Returns:
            JSON string with phase results
        """

        return phase_tool

    async def _execute_phase_as_tool(
        self,
        phase_type: str,
        task: str = None,
        config: Dict[str, Any] = None,
        **kwargs
    ) -> str:
        """Execute a phase and return results as JSON string."""
        try:
            # Mark phase as active
            self.state.active_phase = phase_type

            # Callback
            if self.config.on_phase_invoked:
                self.config.on_phase_invoked(phase_type, task, config)

            # Create phase instance
            phase_class = PhaseRegistry.get(phase_type)
            if phase_class is None:
                return json.dumps({
                    "status": "error",
                    "error": f"Unknown phase type: {phase_type}"
                })

            # Build phase config
            phase_config = phase_class.config_class(**(config or {}))
            phase = phase_class(phase_config)

            # Create snapshot before phase execution
            snapshot = self.state.context.create_snapshot(
                reason=f"before_{phase_type}_phase",
                metadata={'phase_type': phase_type, 'task': task}
            )
            
            # Get deep copied context for phase
            phase_shared_state = self.state.context.get_phase_context()
            
            # Inject approval manager if available
            if self._approval_manager:
                phase_shared_state['_approval_manager'] = self._approval_manager
            
            # Create phase context from current state
            phase_context = PhaseContext(
                workflow_id=self._workflow_context.workflow_id,
                run_id=self.state.run_id,
                phase_id=f"{phase_type}_{uuid.uuid4().hex[:6]}",
                task=task or self.state.current_task,
                work_dir=self._work_dir,
                shared_state=phase_shared_state,
                api_keys=self._api_keys,
                callbacks=self._callbacks,  # Pass callbacks for HITL and events
            )

            # Execute phase
            result = await phase.execute(phase_context)

            # Track execution
            execution_record = {
                "phase_type": phase_type,
                "task": task,
                "status": result.status.value,
                "timestamp": time.time(),
                "output": result.context.output_data if result.succeeded() else None,
                "error": result.error if not result.succeeded() else None,
            }
            self.state.phases_executed.append(execution_record)

            # Merge phase results back into context using safe strategy
            if result.succeeded() and result.context.output_data:
                # Store phase-specific output with prefix
                self.state.context.set(
                    f"phase_{phase_type}_output",
                    result.context.output_data,
                    deep_copy=True
                )
                
                # Merge shared_state changes from phase (if any)
                if hasattr(result.context, 'shared_state'):
                    self.state.context.merge_phase_results(
                        result.context.shared_state,
                        strategy="safe"  # Only add new keys, don't overwrite
                    )
            
            # Create snapshot after phase execution
            self.state.context.create_snapshot(
                reason=f"after_{phase_type}_phase",
                metadata={'phase_type': phase_type, 'status': result.status.value}
            )

            # Clear active phase
            self.state.active_phase = None

            # Return result as JSON
            return json.dumps({
                "status": "success" if result.succeeded() else "failed",
                "phase": phase_type,
                "output": result.context.output_data,
                "error": result.error,
            })

        except Exception as e:
            self.state.active_phase = None
            return json.dumps({
                "status": "error",
                "phase": phase_type,
                "error": str(e),
            })

    def _attach_phase_tools_to_agents(self) -> None:
        """Attach phase tools to relevant agents using autogen register_function."""
        if not self._cmbagent:
            return

        try:
            from autogen import register_function
        except ImportError:
            # If autogen not available, skip registration
            return

        # Agents that should have access to phase tools
        phase_tool_agents = [
            "copilot_control",
            "engineer",
            "researcher",
            "planner",
            "control",
            "admin",
        ]

        for agent_name in phase_tool_agents:
            # Use proper CMBAgent method to get agent
            agent = self._cmbagent.get_agent_from_name(agent_name)
            if agent is None:
                continue

            for tool_name, tool_func in self._phase_tools.items():
                # Create sync wrapper for the async phase tool
                def make_sync_wrapper(async_func, name):
                    def sync_wrapper(task: str = "", config: dict = None) -> str:
                        """Synchronous wrapper for phase tool."""
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                # If already in async context, create new loop in thread
                                import concurrent.futures
                                with concurrent.futures.ThreadPoolExecutor() as pool:
                                    future = pool.submit(
                                        asyncio.run,
                                        async_func(task=task, config=config)
                                    )
                                    return future.result()
                            else:
                                return loop.run_until_complete(
                                    async_func(task=task, config=config)
                                )
                        except RuntimeError:
                            return asyncio.run(async_func(task=task, config=config))
                    sync_wrapper.__name__ = name
                    sync_wrapper.__doc__ = async_func.__doc__
                    return sync_wrapper

                sync_tool = make_sync_wrapper(tool_func, tool_name)

                # Register using autogen's register_function
                try:
                    register_function(
                        sync_tool,
                        caller=agent,
                        executor=agent,
                        name=tool_name,
                        description=f"Invoke the {tool_name.replace('invoke_', '').replace('_phase', '')} phase",
                    )
                except Exception as e:
                    # Log but don't fail if registration fails
                    pass

    def _setup_tool_approval(self) -> None:
        """
        Setup copilot tool approval handoffs with session-level auto-allow.

        This wires up:
        1. ToolPermissionManager to track session permissions
        2. Copilot handoffs (executor_bash → admin, engineer → admin, etc.)
        3. Admin's get_human_input override for tool-aware approval

        The result is Claude Code-like tool approval:
        - First time bash command: UI shows approval with "Allow for Session"
        - User clicks "Allow for Session": all future bash commands auto-allowed
        - Fine-grained per-category control
        """
        from cmbagent.handoffs.tool_permissions import ToolPermissionManager
        from cmbagent.handoffs.copilot_handoffs import register_copilot_mode_handoffs
        from cmbagent.handoffs import get_all_agents
        from cmbagent.handoffs.hitl import configure_admin_for_copilot_tool_approval

        # 1. Create permission manager
        self._permission_manager = ToolPermissionManager(mode=self.config.tool_approval)
        logger.info("tool_approval_mode_set", mode=self.config.tool_approval)

        # 2. Get all agents and register copilot handoffs
        agents = get_all_agents(self._cmbagent)
        copilot_config = {'tool_approval': self.config.tool_approval}
        register_copilot_mode_handoffs(agents, copilot_config)

        # 3. Configure admin agent for tool-aware approval with WebSocket
        if self._approval_manager and 'admin' in agents:
            configure_admin_for_copilot_tool_approval(
                admin_agent=agents['admin'],
                approval_manager=self._approval_manager,
                run_id=self.state.run_id,
                permission_manager=self._permission_manager,
            )
            logger.info("admin_configured_for_tool_approval", transport="websocket")
        else:
            if 'admin' not in agents:
                logger.warning("admin_agent_not_found", detail="tool approval may not work")
            if not self._approval_manager:
                logger.warning("no_approval_manager", detail="tool approval will use console")

    async def run(
        self,
        task: str,
        initial_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Run the swarm orchestrator on a task.

        Args:
            task: Task description
            initial_context: Optional initial context

        Returns:
            Result dictionary with status, output, and state
        """
        # Initialize state for this run
        self.state.current_task = task
        self.state.status = SwarmStatus.RUNNING
        self.state.started_at = time.time()

        if initial_context:
            self.state.context.update(initial_context, deep_copy=True)
        
        # Store initial task as protected
        self.state.context.set('initial_task', task, protected=True)

        # Update workflow context
        self._workflow_context.task = task

        try:
            # Main execution loop
            result = await self._execute_swarm_loop()
            return result

        except Exception as e:
            self.state.status = SwarmStatus.FAILED
            return {
                "status": "failed",
                "error": str(e),
                "state": self.state.to_dict(),
            }

    async def _execute_swarm_loop(self) -> Dict[str, Any]:
        """Execute the main swarm loop with round management.

        In conversational mode, every round includes a human turn:
            Agent acts → Human responds → Agent acts → Human responds → ...
        This mirrors AG2's human_input_mode="ALWAYS" pattern.
        """
        if self._is_conversational:
            return await self._execute_conversational_loop()

        # Standard autonomous loop
        while self.state.status == SwarmStatus.RUNNING:
            # Check for continuation
            if self.state.should_pause_for_continuation():
                return await self._handle_continuation()

            # Execute one round
            round_result = await self._execute_round()
            
            # Check if clarification was skipped or needed but no response yet
            if round_result.get('status') == 'clarification_needed':
                # Return immediately - user needs to respond (console mode)
                self.state.status = SwarmStatus.WAITING_INPUT
                return self._build_final_result(round_result)
            
            # If clarification was received, continue execution without incrementing round
            if round_result.get('status') == 'clarification_received':
                # Task has been updated with user's clarification
                # Re-execute this round with the clarified task
                continue
            
            # If clarification was skipped, proceed normally
            if round_result.get('status') == 'skipped_clarification':
                # Continue with best interpretation
                pass

            # Check if task is complete
            if self._is_task_complete(round_result):
                self.state.status = SwarmStatus.COMPLETED
                return self._build_final_result(round_result)

            # Increment round
            self.state.increment_round()

        return self._build_final_result(None)

    async def _execute_conversational_loop(self) -> Dict[str, Any]:
        """
        Interactive conversation loop — the human is a participant in every turn.

        Flow:
        1. Agent analyzes & executes on current task/feedback
        2. Results presented to human (via WebSocket approval)
        3. Human responds: feedback, new direction, done, or exit
        4. Agent incorporates response and continues

        This is the copilot equivalent of Claude Code's conversation model.
        """
        last_round_result = None

        while self.state.status == SwarmStatus.RUNNING:
            # Check for continuation
            if self.state.should_pause_for_continuation():
                return await self._handle_continuation()

            logger.info("=" * 60)
            logger.info("COPILOT - Round %d", self.state.current_round + 1)
            logger.info("Task: %s", self.state.current_task[:200])
            logger.info("=" * 60)

            # Callback: round start
            if self.config.on_round_start:
                self.config.on_round_start(self.state.current_round, self.state)

            # === AGENT TURN: Execute the current task ===
            message = self._build_conversational_message()

            try:
                copilot_control_agent = (
                    self._cmbagent.get_agent_from_name("copilot_control")
                    if self._cmbagent else None
                )
                if self.config.use_copilot_control and copilot_control_agent is not None:
                    round_result = await self._execute_with_routing(message)
                else:
                    round_result = await self._execute_direct(message)
            except Exception as e:
                round_result = {"error": str(e), "status": "round_failed"}

            # Store in conversation history
            self.state.conversation_history.append({
                "round": self.state.current_round,
                "role": "agent",
                "message": message,
                "result": round_result,
                "timestamp": time.time(),
            })

            # Callback: round end
            if self.config.on_round_end:
                self.config.on_round_end(self.state.current_round, round_result)

            last_round_result = round_result

            # === HUMAN TURN: Present results and get response ===
            human_response = await self._get_human_turn(round_result)

            if human_response is None:
                # Human exited the session
                logger.info("Copilot session ended by user")
                self.state.status = SwarmStatus.COMPLETED
                break

            # Store human turn in conversation history
            self.state.conversation_history.append({
                "round": self.state.current_round,
                "role": "human",
                "message": human_response.get('message', ''),
                "action": human_response.get('action', 'continue'),
                "timestamp": time.time(),
            })

            # Process the human response
            action = human_response.get('action', 'continue')
            feedback = human_response.get('message', '')

            if action == 'done':
                # Human says task is complete
                logger.info("Task marked complete by user")
                self.state.status = SwarmStatus.COMPLETED
                break

            elif action == 'new_task':
                # Human gives a completely new task
                self.state.current_task = feedback
                self._add_feedback("new_task", f"New task: {feedback}", "redirect")
                logger.info("New task: %s", feedback[:100])

            elif action == 'refine':
                # Human wants to refine the last result
                self._add_feedback("refinement", feedback, "refine")
                # Keep same task but inject feedback
                logger.info("Refining with feedback: %s", feedback[:100])

            else:
                # Default: continue with feedback as guidance for next round
                if feedback:
                    self._add_feedback("guidance", feedback, "continue")
                    # Incorporate feedback into the task for next round
                    self.state.current_task = (
                        f"{self.state.current_task}\n\n"
                        f"## Human Feedback (Round {self.state.current_round + 1})\n"
                        f"{feedback}"
                    )
                    logger.info("Continuing with feedback: %s", feedback[:100])

            self.state.increment_round()

        return self._build_final_result(last_round_result)

    def _build_conversational_message(self) -> str:
        """Build message for conversational mode, incorporating human feedback."""
        # Base message
        if self.state.current_round == 0:
            base = self._build_initial_message()
        else:
            base = self._build_continuation_message()

        # Inject accumulated feedback into the message
        if self.state.accumulated_feedback:
            feedback_section = self._truncate_feedback(self.state.accumulated_feedback)
            base += f"""

## Human Guidance
The user has provided the following feedback. Follow these instructions carefully:

{feedback_section}
"""

        return base

    async def _get_human_turn(self, round_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Present results to the human and get their response.

        This is the core of conversational mode — the human turn in the loop.
        Uses WebSocket approval manager if available, falls back to console.

        Returns:
            Dict with 'action' and 'message' keys, or None if user exits.
            action: 'continue' | 'refine' | 'new_task' | 'done'
        """
        # Build a summary of what happened this round
        summary = self._build_round_summary(round_result)

        if self._approval_manager:
            return await self._get_human_turn_ws(summary, round_result)
        else:
            return self._get_human_turn_console(summary)

    async def _get_human_turn_ws(
        self,
        summary: str,
        round_result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Get human response via WebSocket approval manager."""
        # Build the message for the human
        message = f"""## Round {self.state.current_round + 1} Complete

{summary}

**What would you like to do?**
- Type your feedback or next instruction
- Click **Continue** to let the copilot keep going
- Click **Done** to finish the session
"""

        # Build context snapshot with useful info
        context_snapshot = {
            'round': self.state.current_round + 1,
            'total_rounds': self.state.total_rounds_across_continuations + 1,
            'last_agent': self.state.last_agent,
            'phases_executed': len(self.state.phases_executed),
            'requires_text_input': True,
            'input_placeholder': 'Give feedback, redirect, or type a new task...',
        }

        # Add result summary to context if available
        if round_result and isinstance(round_result, dict):
            result_str = round_result.get('result', '')
            if isinstance(result_str, dict):
                result_str = result_str.get('output', result_str.get('result', ''))
            if isinstance(result_str, str) and len(result_str) > 1000:
                result_str = result_str[:1000] + '...'
            context_snapshot['result_preview'] = str(result_str)[:1000] if result_str else ''

        # Create approval request — this pauses and waits for user
        request = self._approval_manager.create_approval_request(
            run_id=self.state.run_id,
            step_id=f"copilot_round_{self.state.current_round + 1}",
            checkpoint_type="copilot_turn",
            context_snapshot=context_snapshot,
            message=message,
            options=["submit", "continue", "done", "exit"],
        )

        logger.debug("Waiting for human response...")

        try:
            resolved = await self._approval_manager.wait_for_approval_async(
                str(request.id),
                timeout_seconds=3600,
            )

            resolution = resolved.resolution
            user_feedback = getattr(resolved, 'user_feedback', '') or ''

            # Map resolution to action
            if resolution in ("exit", "reject"):
                return None  # Exit session
            elif resolution == "done":
                return {'action': 'done', 'message': user_feedback}
            elif resolution in ("continue", "approve", "approved"):
                if user_feedback.strip():
                    return {'action': 'continue', 'message': user_feedback}
                else:
                    return {'action': 'continue', 'message': ''}
            elif resolution == "submit":
                text = user_feedback.strip()
                if not text:
                    return {'action': 'continue', 'message': ''}
                # Detect if user is giving a completely new task vs feedback
                if text.lower().startswith(('new task:', 'do:', 'now:', 'switch to:', 'instead,')):
                    return {'action': 'new_task', 'message': text}
                else:
                    return {'action': 'continue', 'message': text}
            else:
                # Unknown resolution, treat as continue with feedback
                return {'action': 'continue', 'message': user_feedback or ''}

        except TimeoutError:
            logger.warning("Human response timeout - continuing autonomously")
            return {'action': 'continue', 'message': ''}
        except Exception as e:
            logger.error("Error getting human response: %s", e)
            return {'action': 'continue', 'message': ''}

    def _get_human_turn_console(self, summary: str) -> Optional[Dict[str, Any]]:
        """Get human response via console input (fallback)."""
        logger.info("=" * 60)
        logger.info("ROUND %d COMPLETE", self.state.current_round + 1)
        logger.info("=" * 60)
        logger.info("%s", summary)
        logger.info("=" * 60)

        try:
            response = input("\nYour turn (feedback/new task/done/exit): ").strip()
        except (EOFError, KeyboardInterrupt):
            return None

        if not response or response.lower() in ('exit', 'quit', 'bye'):
            return None
        elif response.lower() in ('done', 'complete', 'finished'):
            return {'action': 'done', 'message': ''}
        else:
            return {'action': 'continue', 'message': response}

    def _build_round_summary(self, round_result: Dict[str, Any]) -> str:
        """Build a human-readable summary of what happened in this round."""
        if not round_result:
            return "No results from this round."

        parts = []

        # Agent info
        agent = round_result.get('agent', self.state.last_agent or 'unknown')
        parts.append(f"**Agent:** {agent}")

        # Status
        status = round_result.get('status', 'unknown')
        parts.append(f"**Status:** {status}")

        # Error info
        error = round_result.get('error')
        if error:
            parts.append(f"**Error:** {error}")

        # Result content
        result = round_result.get('result', '')
        if isinstance(result, dict):
            # Phase result
            phase = result.get('phase', '')
            if phase:
                parts.append(f"**Phase:** {phase}")
            output = result.get('output', '')
            if output:
                output_str = json.dumps(output, indent=2) if isinstance(output, dict) else str(output)
                if len(output_str) > 800:
                    output_str = output_str[:800] + '...'
                parts.append(f"**Output:**\n```\n{output_str}\n```")
        elif isinstance(result, str) and result:
            display = result[:800] + '...' if len(result) > 800 else result
            parts.append(f"**Result:**\n{display}")

        # Phases executed this round
        if self.state.phases_executed:
            last_phase = self.state.phases_executed[-1]
            parts.append(f"**Last Phase:** {last_phase.get('phase_type', 'unknown')} ({last_phase.get('status', '')})")

        return "\n".join(parts) if parts else "Round completed."

    def _add_feedback(self, label: str, feedback: str, timing: str) -> None:
        """Add structured feedback from the human.

        Args:
            label: Category label (guidance, refinement, new_task, etc.)
            feedback: The actual feedback text
            timing: When this was given (continue, refine, redirect, etc.)
        """
        entry = f"**Round {self.state.current_round + 1} ({label}):** {feedback}"
        if self.state.accumulated_feedback:
            self.state.accumulated_feedback += f"\n\n{entry}"
        else:
            self.state.accumulated_feedback = entry

        self.state.turn_feedback.append({
            'round': self.state.current_round + 1,
            'label': label,
            'timing': timing,
            'feedback': feedback,
        })

    def _truncate_feedback(self, feedback: str, max_chars: int = 4000) -> str:
        """Truncate accumulated feedback to prevent context overflow.

        Keeps the most recent feedback since it's most relevant.
        """
        if not feedback or len(feedback) <= max_chars:
            return feedback

        truncated = feedback[-(max_chars):]
        # Find first complete section boundary
        boundary = truncated.find('\n\n**Round')
        if boundary > 0:
            truncated = truncated[boundary:]

        return f"[Earlier feedback truncated]\n{truncated}"

    async def _execute_round(self) -> Dict[str, Any]:
        """Execute a single round of agent conversation."""
        # Callback: round start
        if self.config.on_round_start:
            self.config.on_round_start(self.state.current_round, self.state)

        try:
            # Build the message for this round
            if self.state.current_round == 0:
                # First round - use the task
                message = self._build_initial_message()
            else:
                # Subsequent rounds - continue conversation
                message = self._build_continuation_message()

            # Execute via CMBAgent
            # Use copilot_control for routing if enabled
            copilot_control_agent = (
                self._cmbagent.get_agent_from_name("copilot_control")
                if self._cmbagent else None
            )
            if self.config.use_copilot_control and copilot_control_agent is not None:
                result = await self._execute_with_routing(message)
            else:
                result = await self._execute_direct(message)

            # Store in conversation history
            self.state.conversation_history.append({
                "round": self.state.current_round,
                "message": message,
                "result": result,
                "timestamp": time.time(),
            })

            # Callback: round end
            if self.config.on_round_end:
                self.config.on_round_end(self.state.current_round, result)

            return result

        except Exception as e:
            return {"error": str(e), "status": "round_failed"}

    def _build_initial_message(self) -> str:
        """Build the initial message for the swarm."""
        phase_tools_info = ""
        if self.config.enable_phase_tools:
            phase_tools_info = f"""

You have access to phase tools for complex workflows:
- invoke_planning_phase: Create structured plans
- invoke_control_phase: Execute plans step by step
- invoke_hitl_planning_phase: Interactive planning with user feedback
- invoke_hitl_control_phase: Execution with approval gates

Available phases: {', '.join(self.config.available_phases)}
"""

        return f"""Task: {self.state.current_task}

You are the orchestrator of a unified agent swarm. Analyze this task and decide:
1. Can you handle it directly? → Execute with appropriate agent(s)
2. Is it complex? → Use phase tools to plan and execute systematically

Context:
- Session: {self.state.session_id}
- Round: {self.state.current_round + 1}/{self.state.max_rounds}
{phase_tools_info}

Proceed with the task. Use available tools and agents as needed.
"""

    def _build_continuation_message(self) -> str:
        """Build continuation message based on conversation history."""
        last_result = self.state.conversation_history[-1].get('result', {})

        return f"""Continue with the task.

Previous round result: {json.dumps(last_result, indent=2)[:500]}

Current progress:
- Rounds completed: {self.state.current_round}
- Phases executed: {len(self.state.phases_executed)}
- Last agent: {self.state.last_agent}

Continue execution or indicate completion.
"""

    async def _execute_with_routing(self, message: str) -> Dict[str, Any]:
        """Execute with copilot_control routing."""
        # Use copilot_control to analyze and route
        routing_result = await self._get_routing_decision(message)

        route_type = routing_result.get('route_type', 'direct')
        primary_agent = routing_result.get('primary_agent', 'engineer')

        # Store routing result for agent to reference
        self._last_routing_result = routing_result

        # Update state
        self.state.last_agent = primary_agent

        # Handle clarification requests
        if route_type == 'clarify':
            return await self._handle_clarification_request(routing_result)

        # Handle proposal/ideation mode - present options before proceeding
        if route_type == 'propose':
            return await self._handle_proposal_request(routing_result)

        # For ALL routes (including 'phase'), delegate to agent execution
        # The agent has access to phase tools and can invoke them as needed
        # This makes phases truly tool-like rather than orchestrator-invoked
        return await self._execute_with_agent(primary_agent, message)

    async def _handle_clarification_request(self, routing_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle clarification requests - ask user for more info before proceeding.

        Instead of assuming and proceeding, this pauses to get clarity from the user.
        """
        questions = routing_result.get('clarifying_questions', [])
        reasoning = routing_result.get('complexity_reasoning', 'Task is ambiguous')

        if not questions:
            questions = ["Could you please provide more details about what you'd like to accomplish?"]

        # Build clarification message
        message = f"""## Clarification Needed

I want to make sure I understand your request correctly before proceeding.

**Why I'm asking:** {reasoning}

**Questions:**
"""
        for i, q in enumerate(questions, 1):
            message += f"\n{i}. {q}"

        message += "\n\nPlease provide more details so I can help you effectively."
        
        logger.info("Requesting clarification: %s", reasoning)

        # If we have an approval manager, route through WebSocket for user input
        if self._approval_manager:
            return await self._get_clarification_via_websocket(message, questions)
        else:
            # Console fallback
            logger.info("%s", message)
            return {
                'status': 'clarification_needed',
                'questions': questions,
                'message': message,
            }

    async def _get_clarification_via_websocket(
        self,
        message: str,
        questions: List[str]
    ) -> Dict[str, Any]:
        """Get user clarification via WebSocket approval system."""
        approval_request = self._approval_manager.create_approval_request(
            run_id=self.state.run_id,
            step_id="clarification_request",
            checkpoint_type="clarification",
            context_snapshot={
                "questions": questions,
                "requires_text_input": True,
                "input_placeholder": "Please answer the questions above...",
            },
            message=message,
            options=["submit", "skip"],
        )

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        resolved = await self._approval_manager.wait_for_approval_async(
            str(approval_request.id),
            timeout_seconds=1800,
        )

        if resolved.resolution == "skip":
            # User wants to proceed without clarification
            logger.info("Clarification skipped by user")
            return {
                'status': 'skipped_clarification',
                'message': 'Proceeding with best interpretation',
            }

        # User provided clarification - incorporate into task
        user_response = resolved.user_feedback or ""
        if user_response:
            logger.info("Clarification received: %s...", user_response[:100])
            self.state.current_task = f"{self.state.current_task}\n\n## User Clarification:\n{user_response}"
            self._add_feedback("clarification", user_response, "clarify")
        
        logger.info("Continuing with clarified task")
        return {
            'status': 'clarification_received',
            'clarification': user_response,
        }

    async def _handle_proposal_request(self, routing_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle proposal/ideation mode - present multiple approaches before committing.

        This allows users to choose between different strategies rather than
        the copilot immediately picking one.
        """
        proposals = routing_result.get('proposals', [])
        task_summary = routing_result.get('refined_task', self.state.current_task)

        if not proposals:
            # Generate default proposals based on routing hints
            proposals = self._generate_default_proposals(routing_result)

        # Build proposal message
        message = f"""## How would you like me to approach this?

**Task:** {task_summary}

I've identified a few possible approaches:

"""
        for i, proposal in enumerate(proposals, 1):
            title = proposal.get('title', f'Approach {i}')
            description = proposal.get('description', '')
            pros = proposal.get('pros', [])
            cons = proposal.get('cons', [])

            message += f"### Option {i}: {title}\n{description}\n"
            if pros:
                message += f"✅ Pros: {', '.join(pros)}\n"
            if cons:
                message += f"⚠️ Cons: {', '.join(cons)}\n"
            message += "\n"

        message += "Which approach would you prefer? Or describe your own preference."

        if self._approval_manager:
            return await self._get_proposal_choice_via_websocket(message, proposals)
        else:
            logger.info("%s", message)
            return {
                'status': 'proposals_presented',
                'proposals': proposals,
                'message': message,
            }

    async def _get_proposal_choice_via_websocket(
        self,
        message: str,
        proposals: List[Dict]
    ) -> Dict[str, Any]:
        """Get user's choice among proposals via WebSocket."""
        # Create option labels from proposals
        options = [f"option_{i+1}" for i in range(len(proposals))]
        options.append("custom")  # Allow custom approach

        approval_request = self._approval_manager.create_approval_request(
            run_id=self.state.run_id,
            step_id="proposal_choice",
            checkpoint_type="proposal",
            context_snapshot={
                "proposals": proposals,
                "requires_text_input": True,
                "input_placeholder": "Describe your preferred approach or select an option...",
            },
            message=message,
            options=options,
        )

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        resolved = await self._approval_manager.wait_for_approval_async(
            str(approval_request.id),
            timeout_seconds=1800,
        )

        # Parse user choice
        choice = resolved.resolution
        feedback = resolved.user_feedback or ""

        if choice.startswith("option_"):
            try:
                idx = int(choice.split("_")[1]) - 1
                selected_proposal = proposals[idx]
                approach = selected_proposal.get('description', '')
                self.state.current_task = f"{self.state.current_task}\n\n## Selected Approach:\n{approach}"
            except (IndexError, ValueError):
                pass

        if feedback:
            self.state.current_task = f"{self.state.current_task}\n\n## User Preference:\n{feedback}"

        return {
            'status': 'proposal_selected',
            'choice': choice,
            'feedback': feedback,
        }

    def _generate_default_proposals(self, routing_result: Dict[str, Any]) -> List[Dict]:
        """Generate default approach proposals based on routing analysis."""
        complexity = routing_result.get('complexity_score', 50)
        primary_agent = routing_result.get('primary_agent', 'engineer')

        proposals = []

        # Quick/simple approach
        proposals.append({
            'title': 'Quick & Direct',
            'description': f'Handle immediately with {primary_agent} - get results fast',
            'pros': ['Fast results', 'Simple execution'],
            'cons': ['May miss edge cases', 'Less thorough'],
        })

        # Planned/thorough approach
        if complexity > 30:
            proposals.append({
                'title': 'Planned & Thorough',
                'description': 'Create a step-by-step plan first, then execute methodically',
                'pros': ['More reliable', 'Better coverage', 'Easier to review'],
                'cons': ['Takes longer', 'More steps'],
            })

        # Research-first approach
        proposals.append({
            'title': 'Research First',
            'description': 'Gather information and understand the problem deeply before acting',
            'pros': ['Better informed', 'Avoids wrong assumptions'],
            'cons': ['Slower start', 'May over-research'],
        })

        return proposals

    async def _get_routing_decision(self, message: str) -> Dict[str, Any]:
        """Get routing decision from copilot_control."""
        try:
            # Get routing mode from config
            routing_mode = getattr(self.config, 'intelligent_routing', 'balanced')

            # Extract the actual task from the message for routing decisions
            # The message may include instructions, but we need to route based on the task
            actual_task = self.state.current_task or message
            task_word_count = len(actual_task.split())

            # For very short/vague tasks, route to assistant who will use ask_user
            # This is the agent-driven approach (not heuristic-driven)
            if task_word_count <= 6 and routing_mode != 'minimal':
                logger.info("Short task (%d words: '%s...') - routing to assistant for clarification", task_word_count, actual_task[:50])
                return {
                    'route_type': 'direct',
                    'primary_agent': 'assistant',  # Assistant will use ask_user
                }

            # Build mode description
            mode_guide = {
                'minimal': 'Use DIRECT mode: Prefer immediate action, only clarify if completely unclear.',
                'balanced': 'Use BALANCED mode: Prefer action, clarify only essential gaps.',
                'aggressive': 'Use CAUTIOUS mode: Ask questions for ambiguity, propose multiple approaches.',
            }
            mode_instruction = mode_guide.get(routing_mode, mode_guide['balanced'])
            
            # Call copilot_control for analysis
            task_with_mode = f"{mode_instruction}\n\nAnalyze and route: {message}"
            
            # Execute routing - note: solve() doesn't return, sets internal state
            await asyncio.to_thread(
                self._cmbagent.solve,
                task=task_with_mode,
                initial_agent="copilot_control",
                shared_context=self.state.context._persistent.copy() if self.state.context else {},
                max_rounds=1,
            )
            
            # Get result from CMBAgent's internal state
            final_context = getattr(self._cmbagent, 'final_context', None)
            routing_result = None
            
            if final_context:
                if hasattr(final_context, 'data'):
                    routing_result = final_context.data
                elif isinstance(final_context, dict):
                    routing_result = final_context
            
            # Parse routing decision from result
            return self._parse_routing_result(routing_result)

        except Exception as e:
            logger.error("Routing decision error: %s", e)
            # Fallback to simple heuristics
            return self._heuristic_routing(message)

    def _parse_routing_result(self, result: Any) -> Dict[str, Any]:
        """Parse routing decision from copilot_control."""
        # Default fallback - use assistant for unclear tasks
        default = {
            'route_type': 'direct',
            'primary_agent': 'assistant',  # Assistant will clarify via ask_user
        }

        if not result:
            return default

        # Try to extract structured decision from various result formats
        routing_data = None

        if isinstance(result, dict):
            # Direct dict result
            routing_data = result.get('copilot_routing_decision', result)
        elif hasattr(result, 'context_variables'):
            # AG2 ReplyResult with context
            ctx = result.context_variables or {}
            routing_data = ctx.get('copilot_routing_decision', {})
        elif isinstance(result, str):
            # Try to parse JSON from string
            import json
            try:
                routing_data = json.loads(result)
            except json.JSONDecodeError:
                return default

        if not routing_data or not isinstance(routing_data, dict):
            return default

        # Extract all routing fields
        return {
            'route_type': routing_data.get('route_type', 'direct'),
            'primary_agent': routing_data.get('primary_agent', 'engineer'),
            'supporting_agents': routing_data.get('supporting_agents', []),
            'phase_type': routing_data.get('phase_type'),
            'complexity_score': routing_data.get('complexity_score', 50),
            'complexity_reasoning': routing_data.get('complexity_reasoning', ''),
            'clarifying_questions': routing_data.get('clarifying_questions', []),
            'refined_task': routing_data.get('refined_task', ''),
            'estimated_steps': routing_data.get('estimated_steps', 1),
            'confidence': routing_data.get('confidence', 0.5),
            'proposals': routing_data.get('proposals', []),
        }

    def _heuristic_routing(self, message: str) -> Dict[str, Any]:
        """Simple heuristic-based routing with ambiguity detection."""
        # Use the actual task for routing, not the full message
        actual_task = self.state.current_task if self.state.current_task else message
        message_lower = actual_task.lower()
        word_count = len(actual_task.split())

        # Get intelligent routing mode
        routing_mode = getattr(self.config, 'intelligent_routing', 'balanced')

        # Skip clarification checks in minimal mode
        if routing_mode == 'minimal':
            return self._direct_routing(message_lower, word_count)

        # Detect ambiguous/vague requests that need clarification
        vague_patterns = [
            'fix it', 'make it work', 'improve this', 'help me', 'something wrong',
            'not working', 'broken', 'do something', 'make it better',
        ]
        vague_words = ['it', 'this', 'that', 'something', 'stuff', 'things']
        
        # Detect generic actions without specifics
        generic_actions = [
            ('create', 'script'), ('create', 'file'), ('write', 'script'), ('write', 'code'),
            ('make', 'script'), ('make', 'file'), ('build', 'app'), ('create', 'app'),
            ('write', 'function'), ('create', 'function'), ('make', 'program'),
        ]

        # Aggressive mode: Lower threshold for clarification
        word_threshold = 5 if routing_mode == 'balanced' else 8
        vague_word_threshold = 1 if routing_mode == 'balanced' else 2

        # NEW: Detect meta-requests asking system to clarify/plan without actual requirements
        # Route to assistant who will use ask_user to clarify
        meta_clarification_patterns = [
            'clarify requirements', 'clarify the requirements', 'figure out requirements',
            'determine requirements', 'no further details', 'unspecified', 'no details provided',
            'generate a plan to clarify', 'plan to clarify', 'needs clarification',
        ]
        if any(p in message_lower for p in meta_clarification_patterns):
            return {
                'route_type': 'direct',
                'primary_agent': 'assistant',  # Assistant will use ask_user
            }

        # Check for generic action patterns (e.g., "create python script" without purpose)
        message_words = message_lower.split()

        # Purpose-indicating words that suggest the user has described what they want
        purpose_words = [
            'that', 'which', 'to', 'for', 'parse', 'process', 'calculate', 'convert',
            'generate', 'analyze', 'download', 'upload', 'send', 'read', 'write',
            'filter', 'sort', 'transform', 'validate', 'check', 'test', 'monitor',
            'extract', 'import', 'export', 'display', 'show', 'list', 'count',
        ]
        has_purpose = any(pw in message_words for pw in purpose_words)

        for action, target in generic_actions:
            if action in message_words and target in message_words:
                # If short OR no purpose-indicating words, route to assistant
                if word_count <= 5 or (word_count <= 10 and not has_purpose):
                    # Generic request without details - assistant will clarify
                    return {
                        'route_type': 'direct',
                        'primary_agent': 'assistant',  # Assistant will use ask_user
                    }
        
        # Very short messages are often ambiguous
        if word_count < word_threshold:
            vague_word_count = sum(1 for w in message_lower.split() if w in vague_words)
            if vague_word_count >= vague_word_threshold or any(p in message_lower for p in vague_patterns):
                return {
                    'route_type': 'direct',
                    'primary_agent': 'assistant',  # Assistant will use ask_user
                }

        # Check for explicit vague patterns
        if any(p in message_lower for p in vague_patterns):
            return {
                'route_type': 'direct',
                'primary_agent': 'assistant',  # Assistant will use ask_user
            }

        return self._direct_routing(message_lower, word_count)

    def _direct_routing(self, message_lower: str, word_count: int) -> Dict[str, Any]:
        """Direct routing without clarification checks."""
        routing_mode = getattr(self.config, 'intelligent_routing', 'balanced')

        # DON'T route to 'phase' type - phases should be tools that agents use
        # Just determine which agent is best suited
        
        # Check for research keywords
        research_keywords = ['research', 'find', 'search', 'learn', 'understand', 'explain', 'what is']
        if any(kw in message_lower for kw in research_keywords):
            return {
                'route_type': 'direct',
                'primary_agent': 'researcher',
            }

        # Note: "plan" keyword no longer auto-routes to planner
        # Instead, any agent can invoke invoke_planning_phase() tool when needed
        # This allows clarification to happen first before planning begins

        # Complex tasks (longer descriptions) might benefit from proposals
        # Only in aggressive/balanced mode
        proposal_threshold = 40 if routing_mode == 'aggressive' else 60
        if routing_mode != 'minimal' and word_count > proposal_threshold:
            return {
                'route_type': 'propose',
                'complexity_score': 70,
                'complexity_reasoning': 'Task appears complex, presenting approach options',
                'primary_agent': 'engineer',
            }

        # Default to engineer
        return {
            'route_type': 'direct',
            'primary_agent': 'engineer',
        }

    async def _execute_with_agent(
        self,
        agent_name: str,
        message: str
    ) -> Dict[str, Any]:
        """Execute directly with a specific agent."""
        try:
            # Check if routing suggested planning
            routing_mode = getattr(self.config, 'intelligent_routing', 'balanced')
            routing_result = getattr(self, '_last_routing_result', {})
            complexity = routing_result.get('complexity_score', 0)
            
            # Add planning hint if task is complex (70+)
            task_message = message
            if complexity >= 70:
                task_message = f"""{message}

**Note:** This task has complexity score {complexity}. You have access to `invoke_planning_phase(task, max_steps)` if you want to create a structured plan before proceeding."""
            
            # Execute solve - note: solve() doesn't return, it sets internal state
            await asyncio.to_thread(
                self._cmbagent.solve,
                task=task_message,
                initial_agent=agent_name,
                shared_context=self.state.context._persistent.copy() if self.state.context else {},
                max_rounds=self.config.max_rounds - self.state.current_round,
            )
            
            # Get results from CMBAgent's internal state
            chat_result = getattr(self._cmbagent, 'chat_result', None)
            final_context = getattr(self._cmbagent, 'final_context', None)
            last_agent = getattr(self._cmbagent, 'last_agent', agent_name)
            
            # Extract the actual output
            result_output = None
            if chat_result:
                # chat_result is a ChatResult object from AG2
                if hasattr(chat_result, 'summary'):
                    result_output = chat_result.summary
                elif hasattr(chat_result, 'chat_history') and chat_result.chat_history:
                    # Get last message
                    last_msg = chat_result.chat_history[-1]
                    if isinstance(last_msg, dict):
                        result_output = last_msg.get('content', str(last_msg))
                    else:
                        result_output = str(last_msg)
                else:
                    result_output = str(chat_result)
            
            # If no output yet, check final_context
            if not result_output and final_context:
                if hasattr(final_context, 'data'):
                    result_output = final_context.data
                else:
                    result_output = str(final_context)

            # Check if agent requested user input via ask_user tool
            ask_user_request = self._check_for_ask_user_request(result_output)
            if ask_user_request:
                # Handle the ask_user request - get user response
                user_response = await self._handle_ask_user_request(ask_user_request)

                # Return with user response so agent can continue
                return {
                    "status": "user_input_received",
                    "agent": last_agent if hasattr(last_agent, 'name') else str(last_agent),
                    "question": ask_user_request.get('question'),
                    "user_response": user_response,
                    "original_result": result_output,
                    "continue_with": user_response,  # Pass to next round
                }

            return {
                "status": "success",
                "agent": last_agent if hasattr(last_agent, 'name') else str(last_agent),
                "result": result_output or "Task completed (no output captured)",
                "final_context": final_context.data if hasattr(final_context, 'data') else None,
            }

        except Exception as e:
            return {
                "status": "error",
                "agent": agent_name,
                "error": str(e),
            }

    async def _execute_direct(self, message: str) -> Dict[str, Any]:
        """Execute without routing - use default agent."""
        return await self._execute_with_agent("engineer", message)

    async def _handle_ask_user_request(self, request_data: Dict[str, Any]) -> str:
        """
        Handle ask_user tool invocation - send WebSocket event and wait for response.

        Args:
            request_data: The ask_user request containing question, options, etc.

        Returns:
            User's response as a string
        """
        if not self._approval_manager:
            # No approval manager - return a prompt for manual input
            logger.info("ask_user question: %s", request_data.get('question', 'No question provided'))
            if request_data.get('options'):
                logger.info("Options: %s", request_data.get('options'))
            # In terminal mode, just return a default
            return "Please provide clarification via the terminal or UI."

        try:
            # Create approval request using the WebSocket manager
            approval_request = self._approval_manager.create_approval_request(
                run_id=self.state.run_id,
                step_id=f"ask_user_{self.state.current_round}",
                checkpoint_type=request_data.get('request_type', 'clarification'),
                message=request_data.get('question', ''),
                options=['respond'],  # User will provide free-form response
                context={
                    'predefined_options': request_data.get('options'),
                    'additional_context': request_data.get('context'),
                    'request_type': request_data.get('request_type'),
                },
            )

            # Wait for user response
            resolved = await self._approval_manager.wait_for_approval_async(
                approval_request.id,
                timeout_seconds=1800  # 30 min timeout
            )

            # Return user's response
            if resolved.user_feedback:
                return resolved.user_feedback
            elif resolved.resolution == 'approved':
                return "User approved."
            elif resolved.resolution == 'rejected':
                return "User rejected. Please stop or change approach."
            else:
                return resolved.resolution or "No response provided."

        except Exception as e:
            logger.error("Error waiting for user response: %s", e)
            return f"Error getting user input: {e}"

    def _check_for_ask_user_request(self, result: Any) -> Optional[Dict[str, Any]]:
        """
        Check if agent output contains an ask_user request.

        Args:
            result: Agent execution result

        Returns:
            The ask_user request dict if found, None otherwise
        """
        if not result:
            return None

        # Convert to string if not already
        result_str = str(result)

        # Look for ask_user JSON in output
        import re
        # Find JSON objects that contain user_input_requested
        json_pattern = r'\{[^{}]*"action"\s*:\s*"ask_user"[^{}]*\}'
        matches = re.findall(json_pattern, result_str)

        for match in matches:
            try:
                request = json.loads(match)
                if request.get('status') == 'user_input_requested':
                    return request
            except json.JSONDecodeError:
                continue

        return None

    def _is_task_complete(self, round_result: Dict[str, Any]) -> bool:
        """Check if the task is complete."""
        if not round_result:
            return False

        # Check for explicit completion markers
        result_str = str(round_result).lower()
        completion_markers = ['task complete', 'finished', 'done', 'completed']

        return any(marker in result_str for marker in completion_markers)

    async def _handle_continuation(self) -> Dict[str, Any]:
        """Handle max rounds reached - offer continuation."""
        self.state.status = SwarmStatus.PAUSED

        # Callback
        if self.config.on_continuation_needed:
            self.config.on_continuation_needed(self.state)

        if self.config.auto_continue:
            # Auto-continue
            return await self.continue_execution()

        # Return paused state - user must call continue_execution()
        return {
            "status": "paused",
            "reason": "max_rounds_reached",
            "rounds_completed": self.state.current_round,
            "total_rounds": self.state.total_rounds_across_continuations,
            "message": f"Max rounds ({self.state.max_rounds}) reached. Call continue_execution() to continue.",
            "state": self.state.to_dict(),
        }

    async def continue_execution(
        self,
        additional_context: str = None,
    ) -> Dict[str, Any]:
        """
        Continue execution after max rounds pause.

        Args:
            additional_context: Optional additional instructions

        Returns:
            Result dictionary
        """
        if self.state.status != SwarmStatus.PAUSED:
            return {
                "status": "error",
                "error": f"Cannot continue - status is {self.state.status.value}",
            }

        # Reset rounds
        self.state.reset_rounds()
        self.state.status = SwarmStatus.RUNNING

        # Add continuation context
        if additional_context:
            self.state.context.set('continuation_context', additional_context)

        # Resume loop
        return await self._execute_swarm_loop()

    def _build_final_result(self, last_round_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build the final result dictionary."""
        # Save DAG state to dag_output_dir if configured
        if self.orchestrator_config.dag_output_dir:
            try:
                from pathlib import Path
                dag_path = Path(self.orchestrator_config.dag_output_dir) / f"dag_{self.state.session_id}.json"
                dag_data = {
                    "session_id": self.state.session_id,
                    "run_id": self.state.run_id,
                    "status": self.state.status.value,
                    "phases_executed": self.state.phases_executed,
                    "tasks_completed": self.state.tasks_completed,
                    "rounds": self.state.total_rounds_across_continuations,
                    "continuations": self.state.continuation_count,
                    "task": self.state.current_task,
                }
                with open(dag_path, "w") as f:
                    json.dump(dag_data, f, indent=2, default=str)
            except Exception as e:
                logger.warning("dag_state_save_failed: %s", e)

        result = {
            "status": self.state.status.value,
            "session_id": self.state.session_id,
            "run_id": self.state.run_id,
            "task": self.state.current_task,
            "rounds_executed": self.state.total_rounds_across_continuations,
            "continuations": self.state.continuation_count,
            "phases_executed": self.state.phases_executed,
            "conversation_history": self.state.conversation_history,
            "shared_context": self.state.context.to_dict() if self.state.context else {},
            "context_version": self.state.context.version if self.state.context else 0,
            "context_snapshots_count": len(self.state.context.get_snapshots()) if self.state.context else 0,
            "last_result": last_round_result,
            "timing": {
                "started_at": self.state.started_at,
                "completed_at": time.time(),
                "duration": time.time() - self.state.started_at if self.state.started_at else 0,
            },
        }

        # Include conversation feedback in result (for conversational mode)
        if self._is_conversational and self.state.turn_feedback:
            result["human_feedback"] = self.state.turn_feedback
            result["accumulated_feedback"] = self.state.accumulated_feedback

        return result

    # Context management methods

    def get_context_value(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the durable context.
        
        Args:
            key: Context key
            default: Default value if not found
            
        Returns:
            Context value or default
        """
        return self.state.context.get(key, default)
    
    def set_context_value(
        self,
        key: str,
        value: Any,
        protected: bool = False,
        ephemeral: bool = False,
    ) -> None:
        """
        Set a value in the durable context.
        
        Args:
            key: Context key
            value: Value to store
            protected: If True, key cannot be overwritten
            ephemeral: If True, value is ephemeral (cleared after rounds)
        """
        if ephemeral:
            self.state.context.set_ephemeral(key, value)
        else:
            self.state.context.set(key, value, protected=protected)
    
    def create_context_checkpoint(self, reason: str) -> ContextSnapshot:
        """
        Create a checkpoint of the current context.
        
        Args:
            reason: Why checkpoint is being created
            
        Returns:
            ContextSnapshot object
        """
        return self.state.context.create_snapshot(
            reason=reason,
            metadata={
                'round': self.state.current_round,
                'task': self.state.current_task,
            }
        )
    
    def restore_context_checkpoint(self, version: Optional[int] = None) -> bool:
        """
        Restore context from a checkpoint.
        
        Args:
            version: Checkpoint version (None = latest)
            
        Returns:
            True if restored, False if not found
        """
        return self.state.context.restore_snapshot(version)
    
    def get_context_snapshots(self) -> List[ContextSnapshot]:
        """Get all context snapshots."""
        return self.state.context.get_snapshots()
    
    def get_context_change_log(self) -> List[Dict[str, Any]]:
        """Get context change log."""
        return self.state.context.get_change_log()
    
    def save_context_to_disk(self, filepath: str, use_pickle: bool = False) -> None:
        """
        Save context to disk for persistence.
        
        Args:
            filepath: Path to save file
            use_pickle: If True, use pickle (preserves complex objects)
        """
        if use_pickle:
            self.state.context.save_to_disk_pickle(filepath)
        else:
            self.state.context.save_to_disk(filepath)
    
    def load_context_from_disk(self, filepath: str, use_pickle: bool = False) -> None:
        """
        Load context from disk.
        
        Args:
            filepath: Path to load file
            use_pickle: If True, load from pickle file
        """
        if use_pickle:
            self.state.context = DurableContext.load_from_disk_pickle(filepath)
        else:
            self.state.context = DurableContext.load_from_disk(filepath)

    async def close(self) -> None:
        """Clean up resources."""
        if self._cmbagent:
            try:
                await asyncio.to_thread(self._cmbagent.close)
            except Exception:
                pass

        self.state.status = SwarmStatus.IDLE

    # Synchronous wrappers

    def run_sync(
        self,
        task: str,
        initial_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for run()."""
        return asyncio.run(self.run(task, initial_context))

    def continue_sync(
        self,
        additional_context: str = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for continue_execution()."""
        return asyncio.run(self.continue_execution(additional_context))


# Convenience function
async def run_swarm(
    task: str,
    api_keys: Dict[str, str] = None,
    work_dir: str = ".",
    config: SwarmConfig = None,
    approval_manager=None,
) -> Dict[str, Any]:
    """
    Convenience function to run the swarm orchestrator.

    Args:
        task: Task to execute
        api_keys: API keys
        work_dir: Working directory
        config: Swarm configuration
        approval_manager: Optional HITL manager

    Returns:
        Result dictionary
    """
    from cmbagent.utils import get_api_keys_from_env

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    orchestrator = SwarmOrchestrator(config)
    await orchestrator.initialize(api_keys, work_dir, approval_manager)

    try:
        result = await orchestrator.run(task)
        return result
    finally:
        await orchestrator.close()


def run_swarm_sync(
    task: str,
    api_keys: Dict[str, str] = None,
    work_dir: str = ".",
    config: SwarmConfig = None,
    approval_manager=None,
) -> Dict[str, Any]:
    """Synchronous wrapper for run_swarm()."""
    return asyncio.run(run_swarm(task, api_keys, work_dir, config, approval_manager))
