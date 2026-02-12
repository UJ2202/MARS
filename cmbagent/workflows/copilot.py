"""
Copilot workflow implementation using unified SwarmOrchestrator.

This module provides a flexible copilot workflow that:
- Uses SwarmOrchestrator for unified multi-agent execution
- Loads ALL agents into one swarm
- Exposes phases as tools (agents can invoke phases dynamically)
- Supports max_rounds with continuation
- Intelligent routing via copilot_control

Architecture:
    copilot() → SwarmOrchestrator
                ├── All Agents (loaded dynamically)
                ├── All Tools + Phase Tools
                ├── copilot_control (routing)
                └── Round Management (pause/continue)
"""

import os
import uuid
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)

from cmbagent.utils import (
    work_dir_default,
    get_api_keys_from_env,
    CORE_AGENTS,
)
from cmbagent.workflows.utils import clean_work_dir
from cmbagent.orchestrator import (
    SwarmOrchestrator,
    SwarmConfig,
    SwarmStatus,
    OrchestratorConfig,
)


# In-memory orchestrator tracking for live session continuation.
# These are volatile references to running SwarmOrchestrator instances.
# Durable session state is managed by SessionManager (Stages 10-11).
# This dict holds live orchestrator references needed by continue_copilot_sync().
_active_copilot_sessions: Dict[str, SwarmOrchestrator] = {}


def copilot(
    task: str,
    # Agent configuration
    available_agents: List[str] = None,
    engineer_model: str = None,
    researcher_model: str = None,
    planner_model: str = None,
    control_model: str = None,  # Model for routing decisions
    # Task routing
    enable_planning: bool = True,
    use_dynamic_routing: bool = True,  # Use LLM-based routing vs heuristics
    complexity_threshold: int = 50,
    # Execution mode
    continuous_mode: bool = False,
    max_turns: int = 20,
    max_rounds: int = 100,
    max_plan_steps: int = 5,
    max_n_attempts: int = 3,
    # HITL settings
    approval_mode: str = "after_step",
    auto_approve_simple: bool = True,
    # Tool approval (like Claude Code's permission system)
    tool_approval: str = "none",  # "prompt" | "auto_allow_all" | "none"
    # Intelligent routing - controls clarification and proposal behavior
    intelligent_routing: str = "balanced",  # "aggressive" | "balanced" | "minimal"
    # Instructions
    engineer_instructions: str = "",
    researcher_instructions: str = "",
    planner_instructions: str = "",
    # Environment
    work_dir: str = work_dir_default,
    api_keys: Dict[str, str] = None,
    clear_work_dir: bool = False,
    # Callbacks and approval
    callbacks: Dict[str, Any] = None,
    approval_manager=None,
    # New: Swarm configuration
    enable_phase_tools: bool = True,
    load_all_agents: bool = False,
    auto_continue: bool = False,
    # Conversational mode (like Claude Code / AG2 human_input_mode="ALWAYS")
    conversational: bool = False,
) -> Dict[str, Any]:
    """
    Execute a unified copilot workflow using SwarmOrchestrator.

    The copilot uses a single swarm with all agents and phase tools:
    - All agents loaded into one orchestrated swarm
    - Phases available as tools (invoke_planning_phase, etc.)
    - Intelligent routing via copilot_control agent
    - Max rounds with continuation support

    Args:
        task: Task description to execute
        available_agents: List of agents to use (default: core agents)
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
        planner_model: Model for planner agent
        control_model: Model for routing decisions
        enable_planning: Whether to auto-plan complex tasks
        use_dynamic_routing: Use LLM-based routing vs heuristics
        complexity_threshold: Word count threshold for complex tasks
        continuous_mode: Keep running until user exits (auto_continue=True)
        max_turns: Maximum interaction turns in continuous mode
        max_rounds: Maximum conversation rounds before pause
        max_plan_steps: Maximum steps in generated plans
        max_n_attempts: Maximum retry attempts per step
        approval_mode: HITL approval mode ("before_step", "after_step", "both", "none")
        auto_approve_simple: Skip approval for simple one-shot tasks
        tool_approval: Tool execution approval mode:
            - "prompt": Ask before dangerous ops with "Allow for Session" option
            - "auto_allow_all": Skip all tool approval prompts
            - "none": No tool-level approval (default)
        engineer_instructions: Additional instructions for engineer
        researcher_instructions: Additional instructions for researcher
        planner_instructions: Additional instructions for planner
        work_dir: Working directory for outputs
        api_keys: API keys dictionary
        clear_work_dir: Whether to clear work directory
        callbacks: Callback functions for events
        approval_manager: HITL approval manager
        enable_phase_tools: Allow phases to be invoked as tools
        load_all_agents: Load all agents (vs lightweight mode)
        auto_continue: Automatically continue when max_rounds reached

    Returns:
        Dictionary with:
        - status: completed/paused/failed
        - session_id: For continuation if paused
        - results: Execution results
        - rounds_executed: Number of rounds
        - phases_executed: List of invoked phases
        - conversation_history: Full history
    """
    return asyncio.run(copilot_async(
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
        max_turns=max_turns,
        max_rounds=max_rounds,
        max_plan_steps=max_plan_steps,
        max_n_attempts=max_n_attempts,
        approval_mode=approval_mode,
        auto_approve_simple=auto_approve_simple,
        tool_approval=tool_approval,
        intelligent_routing=intelligent_routing,
        engineer_instructions=engineer_instructions,
        researcher_instructions=researcher_instructions,
        planner_instructions=planner_instructions,
        work_dir=work_dir,
        api_keys=api_keys,
        clear_work_dir=clear_work_dir,
        callbacks=callbacks,
        approval_manager=approval_manager,
        enable_phase_tools=enable_phase_tools,
        load_all_agents=load_all_agents,
        auto_continue=auto_continue,
        conversational=conversational,
    ))


async def copilot_async(
    task: str,
    available_agents: List[str] = None,
    engineer_model: str = None,
    researcher_model: str = None,
    planner_model: str = None,
    control_model: str = None,
    enable_planning: bool = True,
    use_dynamic_routing: bool = True,
    complexity_threshold: int = 50,
    continuous_mode: bool = False,
    max_turns: int = 20,
    max_rounds: int = 100,
    max_plan_steps: int = 5,
    max_n_attempts: int = 3,
    approval_mode: str = "after_step",
    auto_approve_simple: bool = True,
    tool_approval: str = "none",  # "prompt" | "auto_allow_all" | "none"
    intelligent_routing: str = "balanced",  # "aggressive" | "balanced" | "minimal"
    engineer_instructions: str = "",
    researcher_instructions: str = "",
    planner_instructions: str = "",
    work_dir: str = work_dir_default,
    api_keys: Dict[str, str] = None,
    clear_work_dir: bool = False,
    callbacks: Dict[str, Any] = None,
    approval_manager=None,
    enable_phase_tools: bool = True,
    load_all_agents: bool = False,
    auto_continue: bool = False,
    conversational: bool = False,
) -> Dict[str, Any]:
    """
    Execute copilot workflow asynchronously using SwarmOrchestrator.

    See copilot() for full argument documentation.
    """
    global _active_copilot_sessions

    # Setup defaults
    if available_agents is None:
        available_agents = [
            "engineer", "researcher", "web_surfer",
            "executor", "executor_bash", "installer",
            "planner", "plan_reviewer", "control",
            "summarizer", "admin", "copilot_control",
            "assistant",  # For user interaction/clarification
        ]

    if engineer_model is None:
        engineer_model = CORE_AGENTS.get('engineer', 'gpt-4o')
    if researcher_model is None:
        researcher_model = CORE_AGENTS.get('researcher', 'gpt-4o')
    if planner_model is None:
        planner_model = CORE_AGENTS.get('planner', 'gpt-4o')
    if control_model is None:
        control_model = CORE_AGENTS.get('planner', 'gpt-4o')

    # Setup work directory
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if clear_work_dir:
        clean_work_dir(work_dir)

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    # Define available phases (matches PhaseRegistry)
    available_phases = [
        "planning", "control", "one_shot",
        "hitl_planning", "hitl_control",
        "hitl_checkpoint", "idea_generation",
        "copilot",
    ]

    # Build agent models dict
    agent_models = {
        "engineer": engineer_model,
        "researcher": researcher_model,
        "planner": planner_model,
        "plan_reviewer": planner_model,
        "copilot_control": control_model,
        "control": control_model,
    }

    # Detect conversational mode from either explicit flag or approval_mode
    is_conversational = conversational or approval_mode == "conversational"

    # Build swarm config
    config = SwarmConfig(
        max_rounds=max_rounds,
        auto_continue=auto_continue or continuous_mode,
        load_all_agents=load_all_agents,
        lightweight_mode=not load_all_agents,
        available_agents=available_agents,
        enable_phase_tools=enable_phase_tools,
        available_phases=available_phases,
        use_copilot_control=use_dynamic_routing,
        routing_model=control_model,
        default_model=engineer_model,
        agent_models=agent_models,
        approval_mode=approval_mode,
        conversational=is_conversational,
        tool_approval=tool_approval,
        intelligent_routing=intelligent_routing,
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
    _active_copilot_sessions[session_id] = orchestrator

    # Print banner
    _print_copilot_banner(task, config, session_id)

    try:
        # Build initial context with instructions
        initial_context = {
            'engineer_instructions': engineer_instructions,
            'researcher_instructions': researcher_instructions,
            'planner_instructions': planner_instructions,
            'enable_planning': enable_planning,
            'complexity_threshold': complexity_threshold,
            'max_plan_steps': max_plan_steps,
            'max_n_attempts': max_n_attempts,
            'auto_approve_simple': auto_approve_simple,
        }

        # Run the swarm
        result = await orchestrator.run(task, initial_context)

        # Convert to copilot result format
        copilot_result = _convert_swarm_to_copilot_result(result, orchestrator)

        # Handle paused state
        if result.get('status') == 'paused':
            logger.info(
                "COPILOT PAUSED - Max rounds (%s) reached | Session ID: %s | "
                "Call continue_copilot('%s') to continue",
                max_rounds, session_id, session_id,
            )
        else:
            # Clean up completed session
            await _cleanup_copilot_session(session_id)

        return copilot_result

    except Exception as e:
        await _cleanup_copilot_session(session_id)
        logger.error("Copilot workflow failed: %s", e, exc_info=True)
        raise


async def continue_copilot(
    session_id: str,
    additional_context: str = None,
    approval_manager=None,
) -> Dict[str, Any]:
    """
    Continue a paused copilot session.

    Args:
        session_id: Session ID from paused result
        additional_context: Optional additional instructions
        approval_manager: Optional approval manager to re-attach for this continuation

    Returns:
        Result dictionary (same format as copilot)
    """
    global _active_copilot_sessions

    if session_id not in _active_copilot_sessions:
        return {
            "status": "error",
            "error": f"Session {session_id} not found. May have expired or completed.",
        }

    orchestrator = _active_copilot_sessions[session_id]

    # Re-attach approval manager for this continuation
    if approval_manager and hasattr(orchestrator, '_approval_manager'):
        orchestrator._approval_manager = approval_manager

    logger.info(
        "CONTINUING COPILOT SESSION: %s | Previous rounds: %s | Continuation #%s",
        session_id,
        orchestrator.state.total_rounds_across_continuations,
        orchestrator.state.continuation_count + 1,
    )

    try:
        result = await orchestrator.continue_execution(additional_context)
        copilot_result = _convert_swarm_to_copilot_result(result, orchestrator)

        # Clean up if completed
        if result.get('status') != 'paused':
            await _cleanup_copilot_session(session_id)

        return copilot_result

    except Exception as e:
        await _cleanup_copilot_session(session_id)
        raise


def continue_copilot_sync(
    session_id: str,
    additional_context: str = None,
    approval_manager=None,
) -> Dict[str, Any]:
    """Synchronous wrapper for continue_copilot."""
    return asyncio.run(continue_copilot(session_id, additional_context, approval_manager))


async def _cleanup_copilot_session(session_id: str) -> None:
    """Clean up a copilot session."""
    global _active_copilot_sessions

    if session_id in _active_copilot_sessions:
        orchestrator = _active_copilot_sessions[session_id]
        await orchestrator.close()
        del _active_copilot_sessions[session_id]


def get_active_copilot_sessions() -> Dict[str, Dict[str, Any]]:
    """Get information about active copilot sessions."""
    return {
        session_id: orchestrator.state.to_dict()
        for session_id, orchestrator in _active_copilot_sessions.items()
    }


def _convert_swarm_to_copilot_result(
    swarm_result: Dict[str, Any],
    orchestrator: SwarmOrchestrator,
) -> Dict[str, Any]:
    """Convert SwarmOrchestrator result to copilot format."""
    return {
        # Core result fields
        'status': swarm_result.get('status', 'unknown'),
        'session_id': swarm_result.get('session_id'),
        'run_id': swarm_result.get('run_id'),

        # Results
        'results': swarm_result.get('last_result'),
        'conversation_history': swarm_result.get('conversation_history', []),

        # Execution stats
        'rounds_executed': swarm_result.get('rounds_executed', 0),
        'turns': swarm_result.get('continuations', 0) + 1,
        'phases_executed': swarm_result.get('phases_executed', []),

        # Context
        'shared_context': swarm_result.get('shared_context', {}),
        'final_context': swarm_result.get('shared_context', {}),

        # Timing
        'timing': swarm_result.get('timing', {}),
        'total_time': swarm_result.get('timing', {}).get('duration', 0),

        # Legacy compatibility
        'workflow_id': f"copilot_{swarm_result.get('session_id', '')}",
        'phase_timings': {'total': swarm_result.get('timing', {}).get('duration', 0)},
    }


def _print_copilot_banner(
    task: str,
    config: SwarmConfig,
    session_id: str,
) -> None:
    """Log the copilot startup banner."""
    logger.info(
        "COPILOT (Unified Swarm Mode) | Task: %s | Session: %s | "
        "Max rounds: %s | Agents: %s loaded | Phase tools: %s | Routing: %s",
        task[:200] + ('...' if len(task) > 200 else ''),
        session_id,
        config.max_rounds,
        len(config.available_agents),
        config.enable_phase_tools,
        'LLM-based' if config.use_copilot_control else 'Heuristic',
    )


# Convenience functions for common use cases

def quick_task(
    task: str,
    agent: str = "engineer",
    work_dir: str = work_dir_default,
    api_keys: Dict[str, str] = None,
) -> Dict[str, Any]:
    """
    Execute a quick one-shot task without planning.

    Args:
        task: Task description
        agent: Agent to use ("engineer" or "researcher")
        work_dir: Working directory
        api_keys: API keys

    Returns:
        Result dictionary
    """
    return copilot(
        task=task,
        available_agents=[agent, "copilot_control"],
        enable_planning=False,
        enable_phase_tools=False,
        approval_mode="none",
        max_rounds=50,
        work_dir=work_dir,
        api_keys=api_keys,
    )


def planned_task(
    task: str,
    max_steps: int = 5,
    approval_mode: str = "after_step",
    work_dir: str = work_dir_default,
    api_keys: Dict[str, str] = None,
    approval_manager=None,
) -> Dict[str, Any]:
    """
    Execute a task with planning and HITL approval.

    Args:
        task: Task description
        max_steps: Maximum plan steps
        approval_mode: When to request approval
        work_dir: Working directory
        api_keys: API keys
        approval_manager: HITL manager

    Returns:
        Result dictionary
    """
    return copilot(
        task=task,
        enable_planning=True,
        enable_phase_tools=True,
        max_plan_steps=max_steps,
        approval_mode=approval_mode,
        work_dir=work_dir,
        api_keys=api_keys,
        approval_manager=approval_manager,
    )


def interactive_session(
    initial_task: str = None,
    work_dir: str = work_dir_default,
    api_keys: Dict[str, str] = None,
) -> Dict[str, Any]:
    """
    Start an interactive copilot session.

    Runs with auto_continue enabled, executing until task complete.

    Args:
        initial_task: Optional initial task (will prompt if not provided)
        work_dir: Working directory
        api_keys: API keys

    Returns:
        Result dictionary with all session results
    """
    if initial_task is None:
        initial_task = input("Enter your task: ").strip()

    return copilot(
        task=initial_task,
        continuous_mode=True,
        auto_continue=True,
        enable_planning=True,
        enable_phase_tools=True,
        approval_mode="after_step",
        work_dir=work_dir,
        api_keys=api_keys,
    )


def interactive_copilot(
    task: str,
    work_dir: str = work_dir_default,
    api_keys: Dict[str, str] = None,
    approval_manager=None,
    callbacks: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    True interactive copilot — conversational mode like Claude Code.

    The human is a participant in every round of the conversation.
    After each agent action, the human can provide feedback, redirect,
    or give a completely new task. Uses AG2-style human_input_mode="ALWAYS"
    pattern at the orchestrator level.

    Args:
        task: Initial task description
        work_dir: Working directory
        api_keys: API keys
        approval_manager: WebSocket approval manager (required for web UI)
        callbacks: Optional callbacks

    Returns:
        Result dictionary with full conversation history
    """
    return copilot(
        task=task,
        conversational=True,
        enable_planning=True,
        enable_phase_tools=True,
        work_dir=work_dir,
        api_keys=api_keys,
        approval_manager=approval_manager,
        callbacks=callbacks,
    )


# Export for backwards compatibility
__all__ = [
    'copilot',
    'copilot_async',
    'continue_copilot',
    'continue_copilot_sync',
    'quick_task',
    'planned_task',
    'interactive_session',
    'interactive_copilot',
]
