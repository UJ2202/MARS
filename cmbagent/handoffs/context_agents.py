"""
Context agent handoffs.

Configures domain-specific context agents (CAMB, CLASS, etc.).
"""

from typing import Dict
from autogen.agentchat.group import AgentTarget
from .debug import debug_print


def register_context_agent_handoffs(agents: Dict, mode: str):
    """
    Register context-specific agent handoffs (CAMB, CLASS, etc.).

    These agents provide domain-specific context and documentation.
    Handoff destination depends on mode (one_shot vs others).

    Args:
        agents: Dictionary of agent instances
        mode: Operating mode ("one_shot" or other)
    """
    debug_print(f'Registering context agent handoffs (mode: {mode})...')

    # CAMB context chain
    agents['camb_context'].agent.handoffs.set_after_work(
        AgentTarget(agents['camb_response_formatter'].agent)
    )

    if mode == "one_shot":
        agents['camb_response_formatter'].agent.handoffs.set_after_work(
            AgentTarget(agents['engineer'].agent)
        )
    else:
        agents['camb_response_formatter'].agent.handoffs.set_after_work(
            AgentTarget(agents['control'].agent)
        )

    # CLASS context chain
    agents['classy_context'].agent.handoffs.set_after_work(
        AgentTarget(agents['classy_response_formatter'].agent)
    )

    if mode == "one_shot":
        agents['classy_response_formatter'].agent.handoffs.set_after_work(
            AgentTarget(agents['engineer'].agent)
        )
    else:
        agents['classy_response_formatter'].agent.handoffs.set_after_work(
            AgentTarget(agents['control'].agent)
        )

    debug_print('Context agents configured\n', indent=2)
