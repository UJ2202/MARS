"""
Utility agent handoffs.

Configures utility agents like summarizer, terminator, etc.
"""

from typing import Dict
from autogen.agentchat.group import AgentTarget, TerminateTarget
from .debug import debug_print


def register_utility_handoffs(agents: Dict):
    """
    Register utility agent handoffs (summarizer, terminator, etc.).

    Args:
        agents: Dictionary of agent instances
    """
    debug_print('Registering utility handoffs...')

    # Summarizer chain
    agents['summarizer'].agent.handoffs.set_after_work(
        AgentTarget(agents['summarizer_response_formatter'].agent)
    )
    agents['summarizer_response_formatter'].agent.handoffs.set_after_work(
        AgentTarget(agents['terminator'].agent)
    )

    # AAS keyword finder
    agents['aas_keyword_finder'].agent.handoffs.set_after_work(
        AgentTarget(agents['control'].agent)
    )

    # Terminator (ends conversation)
    agents['terminator'].agent.handoffs.set_after_work(TerminateTarget())

    debug_print('Utility agents configured\n', indent=2)
