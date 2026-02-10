"""
Planning chain handoffs.

Configures the planning workflow: task improvement → planning → review → refinement.
"""

from typing import Dict
from autogen.agentchat.group import AgentTarget
from .debug import debug_print


def register_planning_chain_handoffs(agents: Dict):
    """
    Register planning chain handoffs.

    Flow: task_improver → task_recorder → planner → formatter → recorder →
          reviewer → formatter → recorder → planner (loop for refinement)

    This creates the iterative planning loop where plans are generated,
    formatted, recorded, reviewed, and refined.

    Args:
        agents: Dictionary of agent instances
    """
    debug_print('Registering planning chain handoffs...')

    # Task improvement chain
    agents['task_improver'].agent.handoffs.set_after_work(
        AgentTarget(agents['task_recorder'].agent)
    )
    agents['task_recorder'].agent.handoffs.set_after_work(
        AgentTarget(agents['planner'].agent)
    )

    # Plan generation chain
    agents['plan_setter'].agent.handoffs.set_after_work(
        AgentTarget(agents['planner'].agent)
    )
    agents['planner'].agent.handoffs.set_after_work(
        AgentTarget(agents['planner_response_formatter'].agent)
    )
    agents['planner_response_formatter'].agent.handoffs.set_after_work(
        AgentTarget(agents['plan_recorder'].agent)
    )

    # Plan review chain
    agents['plan_recorder'].agent.handoffs.set_after_work(
        AgentTarget(agents['plan_reviewer'].agent)
    )
    agents['plan_reviewer'].agent.handoffs.set_after_work(
        AgentTarget(agents['reviewer_response_formatter'].agent)
    )
    agents['reviewer_response_formatter'].agent.handoffs.set_after_work(
        AgentTarget(agents['review_recorder'].agent)
    )

    # Review feedback loop (back to planner for refinement)
    agents['review_recorder'].agent.handoffs.set_after_work(
        AgentTarget(agents['planner'].agent)
    )

    debug_print('Planning chain configured\n', indent=2)
