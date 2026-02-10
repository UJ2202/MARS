"""
Execution chain handoffs.

Configures the execution workflow: engineer/researcher → execution → results.
"""

from typing import Dict
from autogen.agentchat.group import AgentTarget
from .debug import debug_print


def register_execution_chain_handoffs(agents: Dict):
    """
    Register execution chain handoffs.

    Flow (Engineer): engineer → engineer_nest → executor_response_formatter → control
    Flow (Researcher): researcher → formatter → executor → control
    Flow (Installer): installer → executor_bash → formatter

    Args:
        agents: Dictionary of agent instances
    """
    debug_print('Registering execution chain handoffs...')

    # Engineer chain (configured in nested chat section)
    # engineer → engineer_nest → executor_response_formatter

    # Researcher chain
    agents['researcher'].agent.handoffs.set_after_work(
        AgentTarget(agents['researcher_response_formatter'].agent)
    )
    agents['researcher_response_formatter'].agent.handoffs.set_after_work(
        AgentTarget(agents['researcher_executor'].agent)
    )
    agents['researcher_executor'].agent.handoffs.set_after_work(
        AgentTarget(agents['control'].agent)
    )

    # Installer/bash execution chain
    agents['installer'].agent.handoffs.set_after_work(
        AgentTarget(agents['executor_bash'].agent)
    )
    agents['executor_bash'].agent.handoffs.set_after_work(
        AgentTarget(agents['executor_response_formatter'].agent)
    )

    # Idea chains
    agents['idea_hater'].agent.handoffs.set_after_work(
        AgentTarget(agents['idea_hater_response_formatter'].agent)
    )
    agents['idea_hater_response_formatter'].agent.handoffs.set_after_work(
        AgentTarget(agents['control'].agent)
    )

    debug_print('Execution chain configured\n', indent=2)
