"""
Legacy handoffs module - redirects to new modular structure.

This module maintains backward compatibility with existing code.
All functionality has been moved to cmbagent.handoffs package.

For new code, use:
    from cmbagent.handoffs import register_all_hand_offs

Legacy usage (still works):
    from cmbagent.hand_offs import register_all_hand_offs
"""

# Import everything from new location for backward compatibility
from cmbagent.handoffs import (
    register_all_hand_offs,
    configure_hitl_checkpoints,
    disable_hitl_checkpoints,
    get_all_agents,
)

# Re-export for backward compatibility
__all__ = [
    'register_all_hand_offs',
    'configure_hitl_checkpoints',
    'disable_hitl_checkpoints',
    'get_all_agents',
]

# Note: The old monolithic implementation has been refactored into
# the cmbagent.handoffs package with the following structure:
#
# handoffs/
#   ├── __init__.py              - Main API entry point
#   ├── agent_retrieval.py       - Get all agents
#   ├── planning_chain.py        - Planning workflow handoffs
#   ├── execution_chain.py       - Execution workflow handoffs
#   ├── rag_agents.py            - RAG agent handoffs
#   ├── context_agents.py        - Context agent handoffs
#   ├── utility_agents.py        - Utility agent handoffs
#   ├── nested_chats.py          - Nested chat setup
#   ├── message_limiting.py      - Message history limiting
#   ├── mode_specific.py         - Chat vs standard mode
#   ├── hitl.py                  - HITL handoff configurations
#   └── debug.py                 - Debug utilities
