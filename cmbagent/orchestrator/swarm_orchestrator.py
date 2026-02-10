"""
Swarm Orchestrator - Unified Multi-Agent Orchestration

A single orchestrator that:
- Loads ALL agents into one unified swarm
- Registers ALL tools + phase tools (phases as callable tools)
- Manages conversation rounds with continuation support
- Uses intelligent routing via copilot_control agent
- Supports dynamic phase invocation within the conversation

Architecture:
    User Task
        → SwarmOrchestrator (all agents + all tools)
        → copilot_control routes dynamically
        → Agents execute with access to phase tools
        → Continuation offered at max_rounds

This replaces the rigid "route to separate execution path" pattern
with a truly unified swarm where phases are tools agents can invoke.
"""

import asyncio
import uuid
import time
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Union
from enum import Enum

from cmbagent.phases import (
    Phase,
    PhaseContext,
    PhaseResult,
    PhaseRegistry,
    PhaseStatus,
    WorkflowContext,
)
from cmbagent.orchestrator.config import OrchestratorConfig


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
    shared_context: Dict[str, Any] = field(default_factory=dict)

    # Phase execution tracking
    phases_executed: List[Dict[str, Any]] = field(default_factory=list)
    active_phase: Optional[str] = None

    # Status
    status: SwarmStatus = SwarmStatus.IDLE
    last_agent: Optional[str] = None

    # Timing
    started_at: Optional[float] = None
    last_activity: Optional[float] = None

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

    # HITL configuration
    approval_mode: str = "after_step"  # before_step, after_step, both, none

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

        # Components (initialized later)
        self._cmbagent = None
        self._agents: Dict[str, Any] = {}
        self._tools: Dict[str, Callable] = {}
        self._phase_tools: Dict[str, Callable] = {}

        # Context
        self._api_keys: Dict[str, str] = {}
        self._work_dir: str = ""
        self._approval_manager = None

        # Phase execution context
        self._phase_context: Optional[PhaseContext] = None
        self._workflow_context: Optional[WorkflowContext] = None

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

        # Update config with callbacks
        if callbacks:
            if hasattr(callbacks, 'on_round_start') and callbacks.on_round_start:
                self.config.on_round_start = callbacks.on_round_start
            if hasattr(callbacks, 'on_round_end') and callbacks.on_round_end:
                self.config.on_round_end = callbacks.on_round_end
            if hasattr(callbacks, 'on_agent_message') and callbacks.on_agent_message:
                self.config.on_agent_message = callbacks.on_agent_message

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

        # Copilot control (for routing)
        copilot = ["copilot_control"]

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

            # Create phase context from current state
            phase_context = PhaseContext(
                workflow_id=self._workflow_context.workflow_id,
                run_id=self.state.run_id,
                phase_id=f"{phase_type}_{uuid.uuid4().hex[:6]}",
                task=task or self.state.current_task,
                work_dir=self._work_dir,
                shared_state=self.state.shared_context.copy(),
                api_keys=self._api_keys,
            )

            # Inject approval manager if available
            if self._approval_manager:
                phase_context.shared_state['_approval_manager'] = self._approval_manager

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

            # Update shared context with phase output
            if result.succeeded() and result.context.output_data:
                self.state.shared_context.update({
                    f"phase_{phase_type}_output": result.context.output_data
                })

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
            self.state.shared_context.update(initial_context)

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
        """Execute the main swarm loop with round management."""
        while self.state.status == SwarmStatus.RUNNING:
            # Check for continuation
            if self.state.should_pause_for_continuation():
                return await self._handle_continuation()

            # Execute one round
            round_result = await self._execute_round()

            # Check if task is complete
            if self._is_task_complete(round_result):
                self.state.status = SwarmStatus.COMPLETED
                return self._build_final_result(round_result)

            # Increment round
            self.state.increment_round()

        return self._build_final_result(None)

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
            copilot_control_agent = self._cmbagent.get_agent_from_name("copilot_control")
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

        # Update state
        self.state.last_agent = primary_agent

        if route_type == 'phase':
            # Route to phase tool
            phase_type = routing_result.get('phase_type', 'one_shot')
            return await self._execute_phase_as_tool(
                phase_type=phase_type,
                task=self.state.current_task,
            )
        else:
            # Direct execution with agent
            return await self._execute_with_agent(primary_agent, message)

    async def _get_routing_decision(self, message: str) -> Dict[str, Any]:
        """Get routing decision from copilot_control."""
        try:
            # Call copilot_control for analysis
            result = await asyncio.to_thread(
                self._cmbagent.solve,
                task=f"Analyze and route: {message}",
                agent="copilot_control",
                max_rounds=1,
            )

            # Parse routing decision from result
            # This expects copilot_control to use structured output
            return self._parse_routing_result(result)

        except Exception as e:
            # Fallback to simple heuristics
            return self._heuristic_routing(message)

    def _parse_routing_result(self, result: Any) -> Dict[str, Any]:
        """Parse routing decision from copilot_control."""
        # Default fallback
        default = {
            'route_type': 'direct',
            'primary_agent': 'engineer',
        }

        if not result:
            return default

        # Try to extract structured decision
        if isinstance(result, dict):
            return {
                'route_type': result.get('route_type', 'direct'),
                'primary_agent': result.get('primary_agent', 'engineer'),
                'phase_type': result.get('phase_type'),
            }

        return default

    def _heuristic_routing(self, message: str) -> Dict[str, Any]:
        """Simple heuristic-based routing."""
        message_lower = message.lower()

        # Check for planning keywords
        planning_keywords = ['plan', 'steps', 'breakdown', 'strategy', 'approach']
        if any(kw in message_lower for kw in planning_keywords):
            return {
                'route_type': 'phase',
                'phase_type': 'planning',
                'primary_agent': 'planner',
            }

        # Check for research keywords
        research_keywords = ['research', 'find', 'search', 'learn', 'understand']
        if any(kw in message_lower for kw in research_keywords):
            return {
                'route_type': 'direct',
                'primary_agent': 'researcher',
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
            result = await asyncio.to_thread(
                self._cmbagent.solve,
                task=message,
                agent=agent_name,
                max_rounds=self.config.max_rounds - self.state.current_round,
            )

            return {
                "status": "success",
                "agent": agent_name,
                "result": result,
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
            self.state.shared_context['continuation_context'] = additional_context

        # Resume loop
        return await self._execute_swarm_loop()

    def _build_final_result(self, last_round_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build the final result dictionary."""
        return {
            "status": self.state.status.value,
            "session_id": self.state.session_id,
            "run_id": self.state.run_id,
            "task": self.state.current_task,
            "rounds_executed": self.state.total_rounds_across_continuations,
            "continuations": self.state.continuation_count,
            "phases_executed": self.state.phases_executed,
            "conversation_history": self.state.conversation_history,
            "shared_context": self.state.shared_context,
            "last_result": last_round_result,
            "timing": {
                "started_at": self.state.started_at,
                "completed_at": time.time(),
                "duration": time.time() - self.state.started_at if self.state.started_at else 0,
            },
        }

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
