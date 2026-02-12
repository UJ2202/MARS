"""
Agent handoffs module for CMBAgent.

This module provides modular handoff configuration organized by concern.
Each submodule handles a specific aspect of the agent communication flow.

Main API:
    - register_all_hand_offs(): Register all handoffs for a CMBAgent instance
    - configure_hitl_checkpoints(): Dynamically configure HITL behavior
    - disable_hitl_checkpoints(): Disable HITL and restore standard handoffs

Example:
    from cmbagent.handoffs import register_all_hand_offs

    # Standard handoffs
    register_all_hand_offs(cmbagent_instance)

    # With HITL
    hitl_config = {
        'mandatory_checkpoints': ['after_planning', 'before_file_edit'],
        'smart_approval': True,
        'smart_criteria': {'escalate_keywords': ['delete', 'production']},
    }
    register_all_hand_offs(cmbagent_instance, hitl_config=hitl_config)
"""

from typing import Dict, List, Optional

# Import submodules
from .agent_retrieval import get_all_agents
from .planning_chain import register_planning_chain_handoffs
from .execution_chain import register_execution_chain_handoffs
from .rag_agents import register_rag_handoffs
from .context_agents import register_context_agent_handoffs
from .utility_agents import register_utility_handoffs
from .nested_chats import setup_engineer_nested_chat, setup_idea_maker_nested_chat
from .message_limiting import apply_message_history_limiting
from .mode_specific import register_chat_mode_handoffs, register_standard_mode_handoffs
from .hitl import (
    register_hitl_handoffs,
    configure_hitl_checkpoints,
    disable_hitl_checkpoints,
    configure_admin_for_websocket,
    enable_websocket_for_hitl,
    configure_admin_for_copilot_tool_approval,
)
from .copilot_handoffs import register_copilot_mode_handoffs
from .debug import debug_print, debug_section, is_debug_enabled


# ============================================================================
# MAIN API
# ============================================================================

def register_all_hand_offs(
    cmbagent_instance,
    hitl_config: Optional[Dict] = None,
    copilot_config: Optional[Dict] = None,
):
    """
    Register all agent handoffs for the CMBAgent instance.

    This is the main entry point for configuring agent-to-agent transitions.
    Call this after creating a CMBAgent instance to setup the communication flow.

    Args:
        cmbagent_instance: CMBAgent instance to configure
        hitl_config: Optional HITL configuration dict with keys:
            - mandatory_checkpoints: List[str] - e.g., ["after_planning", "before_file_edit"]
            - smart_approval: bool - Enable dynamic escalation
            - smart_criteria: Dict - Criteria for smart escalation

    Example:
        # Standard mode (no HITL)
        register_all_hand_offs(cmbagent)

        # With mandatory human checkpoints
        hitl_config = {
            'mandatory_checkpoints': ['after_planning', 'before_file_edit'],
        }
        register_all_hand_offs(cmbagent, hitl_config=hitl_config)

        # With smart approval
        hitl_config = {
            'smart_approval': True,
            'smart_criteria': {
                'escalate_keywords': ['delete', 'production', 'deploy'],
            }
        }
        register_all_hand_offs(cmbagent, hitl_config=hitl_config)

        # Hybrid (both mandatory + smart)
        hitl_config = {
            'mandatory_checkpoints': ['after_planning'],
            'smart_approval': True,
            'smart_criteria': {'escalate_keywords': ['delete', 'production']},
        }
        register_all_hand_offs(cmbagent, hitl_config=hitl_config)
    """
    if is_debug_enabled():
        debug_section('REGISTERING AGENT HANDOFFS')

    # Get agent references
    agents = get_all_agents(cmbagent_instance)
    mode = cmbagent_instance.mode

    # Register handoffs by category
    register_planning_chain_handoffs(agents)
    register_execution_chain_handoffs(agents)
    register_rag_handoffs(agents, cmbagent_instance.skip_rag_agents)
    register_context_agent_handoffs(agents, mode)
    register_utility_handoffs(agents)

    # Setup nested chats for complex interactions
    setup_engineer_nested_chat(agents, cmbagent_instance)
    setup_idea_maker_nested_chat(agents, cmbagent_instance)

    # Apply message history limiting
    apply_message_history_limiting(agents)

    # Mode-specific handoffs
    if mode == "chat":
        register_chat_mode_handoffs(agents, cmbagent_instance)
    else:
        register_standard_mode_handoffs(agents)

    # HITL handoffs (if configured)
    if hitl_config:
        register_hitl_handoffs(agents, hitl_config)

    # Copilot-specific handoffs (tool approval with human in exec chain)
    if copilot_config:
        register_copilot_mode_handoffs(agents, copilot_config)

    if is_debug_enabled():
        debug_section('ALL HANDOFFS REGISTERED SUCCESSFULLY')


# Export public API
__all__ = [
    'register_all_hand_offs',
    'configure_hitl_checkpoints',
    'disable_hitl_checkpoints',
    'configure_admin_for_copilot_tool_approval',
    'register_copilot_mode_handoffs',
    'get_all_agents',
]
