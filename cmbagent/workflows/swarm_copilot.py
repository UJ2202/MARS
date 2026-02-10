"""
Swarm Copilot - Unified Multi-Agent Workflow

This is the unified entry point that brings everything together:
- Single swarm with ALL agents
- ALL tools including phase tools
- Intelligent routing via copilot_control
- Max rounds with continuation support
- Dynamic phase invocation

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                    SwarmOrchestrator                        │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │              All Agents (49)                         │   │
    │  │  engineer, researcher, planner, control, ...        │   │
    │  └─────────────────────────────────────────────────────┘   │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │              All Tools                               │   │
    │  │  + Phase Tools (planning, control, hitl, ...)       │   │
    │  └─────────────────────────────────────────────────────┘   │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │           copilot_control (Router)                   │   │
    │  │  Analyzes task → Routes to agent/phase              │   │
    │  └─────────────────────────────────────────────────────┘   │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │           Round Management                           │   │
    │  │  max_rounds → pause → continue_execution()          │   │
    │  └─────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────┘

Usage:
    # Basic usage
    result = swarm_copilot("Build a REST API")

    # With configuration
    result = swarm_copilot(
        task="Build a REST API with auth",
        max_rounds=50,
        enable_phase_tools=True,
        approval_mode="after_step",
    )

    # Async with continuation
    result = await swarm_copilot_async("Complex task")
    if result['status'] == 'paused':
        result = await continue_swarm_copilot(result['session_id'])
"""

import os
import uuid
import asyncio
from typing import Dict, Any, List, Optional, Callable

from cmbagent.utils import work_dir_default, get_api_keys_from_env, CORE_AGENTS
from cmbagent.workflows.utils import clean_work_dir
from cmbagent.orchestrator import (
    SwarmOrchestrator,
    SwarmConfig,
    SwarmStatus,
    OrchestratorConfig,
)


# Global session storage for continuation support
_active_sessions: Dict[str, SwarmOrchestrator] = {}


def swarm_copilot(
    task: str,
    # Round management
    max_rounds: int = 100,
    auto_continue: bool = False,
    # Agent configuration
    load_all_agents: bool = False,
    lightweight_mode: bool = True,
    available_agents: List[str] = None,
    # Phase tools
    enable_phase_tools: bool = True,
    available_phases: List[str] = None,
    # Routing
    use_copilot_control: bool = True,
    routing_model: str = None,
    # Models
    default_model: str = None,
    agent_models: Dict[str, str] = None,
    # HITL
    approval_mode: str = "after_step",
    # Environment
    work_dir: str = work_dir_default,
    api_keys: Dict[str, str] = None,
    clear_work_dir: bool = False,
    # Callbacks
    callbacks: Dict[str, Callable] = None,
    approval_manager=None,
    # Initial context
    initial_context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Execute a unified swarm copilot workflow.

    This is the single entry point that:
    1. Loads ALL agents into one swarm
    2. Registers ALL tools + phase tools
    3. Uses intelligent routing via copilot_control
    4. Manages rounds with continuation support

    Args:
        task: Task to execute
        max_rounds: Maximum conversation rounds before pause
        auto_continue: Automatically continue when max_rounds reached
        load_all_agents: Load all 49 agents (vs lightweight mode)
        lightweight_mode: Use minimal agent set for speed
        available_agents: Specific agents to load
        enable_phase_tools: Allow phases to be invoked as tools
        available_phases: Which phases to expose as tools
        use_copilot_control: Use LLM-based routing
        routing_model: Model for routing decisions
        default_model: Default model for agents
        agent_models: Per-agent model overrides
        approval_mode: HITL approval timing
        work_dir: Working directory
        api_keys: API keys
        clear_work_dir: Clear work directory before starting
        callbacks: Event callbacks
        approval_manager: HITL approval manager
        initial_context: Initial shared context

    Returns:
        Dictionary with:
        - status: completed/paused/failed
        - session_id: For continuation
        - result: Execution results
        - rounds_executed: Number of rounds
        - phases_executed: List of invoked phases
        - conversation_history: Full history
    """
    return asyncio.run(swarm_copilot_async(
        task=task,
        max_rounds=max_rounds,
        auto_continue=auto_continue,
        load_all_agents=load_all_agents,
        lightweight_mode=lightweight_mode,
        available_agents=available_agents,
        enable_phase_tools=enable_phase_tools,
        available_phases=available_phases,
        use_copilot_control=use_copilot_control,
        routing_model=routing_model,
        default_model=default_model,
        agent_models=agent_models,
        approval_mode=approval_mode,
        work_dir=work_dir,
        api_keys=api_keys,
        clear_work_dir=clear_work_dir,
        callbacks=callbacks,
        approval_manager=approval_manager,
        initial_context=initial_context,
    ))


async def swarm_copilot_async(
    task: str,
    # Round management
    max_rounds: int = 100,
    auto_continue: bool = False,
    # Agent configuration
    load_all_agents: bool = False,
    lightweight_mode: bool = True,
    available_agents: List[str] = None,
    # Phase tools
    enable_phase_tools: bool = True,
    available_phases: List[str] = None,
    # Routing
    use_copilot_control: bool = True,
    routing_model: str = None,
    # Models
    default_model: str = None,
    agent_models: Dict[str, str] = None,
    # HITL
    approval_mode: str = "after_step",
    # Environment
    work_dir: str = work_dir_default,
    api_keys: Dict[str, str] = None,
    clear_work_dir: bool = False,
    # Callbacks
    callbacks: Dict[str, Callable] = None,
    approval_manager=None,
    # Initial context
    initial_context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Async version of swarm_copilot.

    See swarm_copilot() for full documentation.
    """
    global _active_sessions

    # Setup defaults
    if available_agents is None:
        available_agents = [
            "engineer", "researcher", "web_surfer",
            "executor", "executor_bash", "installer",
            "planner", "plan_reviewer", "control",
            "summarizer", "admin", "copilot_control",
        ]

    if available_phases is None:
        available_phases = [
            "planning", "control", "one_shot",
            "hitl_planning", "hitl_control",
            "hitl_checkpoint", "idea_generation",
            "copilot",
        ]

    if default_model is None:
        default_model = CORE_AGENTS.get('engineer', 'gpt-4o')

    if routing_model is None:
        routing_model = CORE_AGENTS.get('planner', 'gpt-4o')

    # Setup work directory
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if clear_work_dir:
        clean_work_dir(work_dir)

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    # Build swarm config
    config = SwarmConfig(
        max_rounds=max_rounds,
        auto_continue=auto_continue,
        load_all_agents=load_all_agents,
        lightweight_mode=lightweight_mode,
        available_agents=available_agents,
        enable_phase_tools=enable_phase_tools,
        available_phases=available_phases,
        use_copilot_control=use_copilot_control,
        routing_model=routing_model,
        default_model=default_model,
        agent_models=agent_models or {},
        approval_mode=approval_mode,
    )

    # Build orchestrator config
    orchestrator_config = OrchestratorConfig(
        enable_dag_tracking=True,
        enable_logging=True,
        enable_metrics=True,
    )

    # Create orchestrator
    orchestrator = SwarmOrchestrator(config, orchestrator_config)

    # Initialize
    await orchestrator.initialize(
        api_keys=api_keys,
        work_dir=work_dir,
        approval_manager=approval_manager,
        callbacks=callbacks,
    )

    # Store for continuation
    session_id = orchestrator.state.session_id
    _active_sessions[session_id] = orchestrator

    # Print banner
    _print_swarm_banner(task, config, session_id)

    try:
        # Run the swarm
        result = await orchestrator.run(task, initial_context)

        # Handle result
        if result.get('status') == 'paused':
            # Keep session alive for continuation
            print(f"\n{'=' * 60}")
            print(f"⏸  SWARM PAUSED - Max rounds ({max_rounds}) reached")
            print(f"   Session ID: {session_id}")
            print(f"   Call continue_swarm_copilot('{session_id}') to continue")
            print(f"{'=' * 60}\n")
        else:
            # Clean up completed session
            await _cleanup_session(session_id)

        return result

    except Exception as e:
        # Clean up on error
        await _cleanup_session(session_id)
        raise


async def continue_swarm_copilot(
    session_id: str,
    additional_context: str = None,
) -> Dict[str, Any]:
    """
    Continue a paused swarm copilot session.

    Args:
        session_id: Session ID from paused result
        additional_context: Optional additional instructions

    Returns:
        Result dictionary (same format as swarm_copilot)
    """
    global _active_sessions

    if session_id not in _active_sessions:
        return {
            "status": "error",
            "error": f"Session {session_id} not found. May have expired or completed.",
        }

    orchestrator = _active_sessions[session_id]

    print(f"\n{'=' * 60}")
    print(f"▶  CONTINUING SWARM SESSION: {session_id}")
    print(f"   Previous rounds: {orchestrator.state.total_rounds_across_continuations}")
    print(f"   Continuation #{orchestrator.state.continuation_count + 1}")
    print(f"{'=' * 60}\n")

    try:
        result = await orchestrator.continue_execution(additional_context)

        # Clean up if completed
        if result.get('status') != 'paused':
            await _cleanup_session(session_id)

        return result

    except Exception as e:
        await _cleanup_session(session_id)
        raise


def continue_swarm_copilot_sync(
    session_id: str,
    additional_context: str = None,
) -> Dict[str, Any]:
    """Synchronous wrapper for continue_swarm_copilot."""
    return asyncio.run(continue_swarm_copilot(session_id, additional_context))


async def _cleanup_session(session_id: str) -> None:
    """Clean up a swarm session."""
    global _active_sessions

    if session_id in _active_sessions:
        orchestrator = _active_sessions[session_id]
        await orchestrator.close()
        del _active_sessions[session_id]


def get_active_sessions() -> Dict[str, Dict[str, Any]]:
    """Get information about active swarm sessions."""
    return {
        session_id: orchestrator.state.to_dict()
        for session_id, orchestrator in _active_sessions.items()
    }


def _print_swarm_banner(
    task: str,
    config: SwarmConfig,
    session_id: str,
) -> None:
    """Print the swarm startup banner."""
    print(f"\n{'=' * 60}")
    print(f"🐝 SWARM COPILOT")
    print(f"{'=' * 60}")
    print(f"Task: {task[:200]}{'...' if len(task) > 200 else ''}")
    print(f"Session: {session_id}")
    print(f"Max rounds: {config.max_rounds}")
    print(f"Agents: {len(config.available_agents)} loaded")
    print(f"Phase tools: {config.enable_phase_tools}")
    print(f"Routing: {'LLM-based' if config.use_copilot_control else 'Heuristic'}")
    print(f"{'=' * 60}\n")


# Convenience functions

def quick_swarm(
    task: str,
    work_dir: str = work_dir_default,
    api_keys: Dict[str, str] = None,
) -> Dict[str, Any]:
    """
    Quick swarm execution with minimal configuration.

    Uses lightweight mode, no phase tools, simple routing.
    Good for quick tasks that don't need full orchestration.
    """
    return swarm_copilot(
        task=task,
        max_rounds=50,
        lightweight_mode=True,
        enable_phase_tools=False,
        use_copilot_control=False,
        work_dir=work_dir,
        api_keys=api_keys,
    )


def full_swarm(
    task: str,
    work_dir: str = work_dir_default,
    api_keys: Dict[str, str] = None,
    approval_manager=None,
) -> Dict[str, Any]:
    """
    Full swarm execution with all features enabled.

    Loads all agents, enables phase tools, uses LLM routing.
    Good for complex tasks requiring orchestration.
    """
    return swarm_copilot(
        task=task,
        max_rounds=100,
        load_all_agents=True,
        lightweight_mode=False,
        enable_phase_tools=True,
        use_copilot_control=True,
        approval_mode="after_step",
        work_dir=work_dir,
        api_keys=api_keys,
        approval_manager=approval_manager,
    )


def interactive_swarm(
    initial_task: str = None,
    work_dir: str = work_dir_default,
    api_keys: Dict[str, str] = None,
) -> Dict[str, Any]:
    """
    Interactive swarm session with continuation support.

    Runs until task complete or user exits.
    Automatically continues on max rounds.
    """
    if initial_task is None:
        initial_task = input("Enter your task: ").strip()

    return swarm_copilot(
        task=initial_task,
        max_rounds=50,
        auto_continue=True,
        enable_phase_tools=True,
        use_copilot_control=True,
        work_dir=work_dir,
        api_keys=api_keys,
    )


# Export for the module
__all__ = [
    'swarm_copilot',
    'swarm_copilot_async',
    'continue_swarm_copilot',
    'continue_swarm_copilot_sync',
    'get_active_sessions',
    'quick_swarm',
    'full_swarm',
    'interactive_swarm',
]
