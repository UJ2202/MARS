"""
Message history limiting.

Applies message history limits to prevent context overflow.
"""

from typing import Dict
from autogen.agentchat.contrib.capabilities.transform_messages import TransformMessages
from autogen.agentchat.contrib.capabilities.transforms import MessageHistoryLimiter
from .debug import debug_print


def apply_message_history_limiting(agents: Dict):
    """
    Apply message history limiting to response formatters.

    This prevents context overflow by limiting message history to 1 message
    for agents that only need immediate context.

    Args:
        agents: Dictionary of agent instances
    """
    debug_print('Applying message history limiting...')

    context_handling = TransformMessages(
        transforms=[MessageHistoryLimiter(max_messages=1)]
    )

    # Apply to response formatters (they only need latest message)
    formatter_agents = [
        'executor_response_formatter',
        'planner_response_formatter',
        'plan_recorder',
        'reviewer_response_formatter',
        'review_recorder',
        'researcher_response_formatter',
        'researcher_executor',
        'idea_maker_response_formatter',
        'idea_hater_response_formatter',
        'summarizer_response_formatter',
    ]

    for agent_name in formatter_agents:
        if agent_name in agents:
            context_handling.add_to_agent(agents[agent_name].agent)

    debug_print(f'Applied to {len([a for a in formatter_agents if a in agents])} agents\n', indent=2)
