"""
RAG (Retrieval-Augmented Generation) agent handoffs.

Configures agents that fetch information from documentation and knowledge bases.
"""

from typing import Dict
from autogen.agentchat.group import AgentTarget
from .debug import debug_print


def register_rag_handoffs(agents: Dict, skip_rag: bool):
    """
    Register RAG (Retrieval-Augmented Generation) agent handoffs.

    These agents fetch information from documentation and knowledge bases.
    Flow: rag_agent → response_formatter → control

    Args:
        agents: Dictionary of agent instances
        skip_rag: Whether to skip RAG agent configuration
    """
    if skip_rag:
        debug_print('Skipping RAG agent handoffs (disabled)\n')
        return

    debug_print('Registering RAG agent handoffs...')

    # CAMB RAG agent
    if 'camb_agent' in agents:
        agents['camb_agent'].agent.handoffs.set_after_work(
            AgentTarget(agents['camb_response_formatter'].agent)
        )

    # Classy_SZ RAG agent
    if 'classy_sz_agent' in agents:
        agents['classy_sz_agent'].agent.handoffs.set_after_work(
            AgentTarget(agents['classy_sz_response_formatter'].agent)
        )
        agents['classy_sz_response_formatter'].agent.handoffs.set_after_work(
            AgentTarget(agents['control'].agent)
        )

    # Cobaya RAG agent
    if 'cobaya_agent' in agents:
        agents['cobaya_agent'].agent.handoffs.set_after_work(
            AgentTarget(agents['cobaya_response_formatter'].agent)
        )
        agents['cobaya_response_formatter'].agent.handoffs.set_after_work(
            AgentTarget(agents['control'].agent)
        )

    # Planck RAG agent
    if 'planck_agent' in agents:
        agents['planck_agent'].agent.handoffs.set_after_work(
            AgentTarget(agents['control'].agent)
        )

    debug_print('RAG agents configured\n', indent=2)
