"""
Nested chat configurations.

Sets up nested conversations for complex agent interactions.
"""

from typing import Dict
from autogen import GroupChatManager, GroupChat
from autogen.agentchat.group import AgentTarget
from .debug import debug_print


def setup_engineer_nested_chat(agents: Dict, cmbagent_instance):
    """
    Setup nested chat for engineer code execution.

    When engineer generates code, it enters a nested conversation with
    executor for code execution and result processing.

    Args:
        agents: Dictionary of agent instances
        cmbagent_instance: CMBAgent instance for config access
    """
    debug_print('Setting up engineer nested chat...')

    # Create nested group chat for code execution
    executor_chat = GroupChat(
        agents=[
            agents['engineer_response_formatter'].agent,
            agents['executor'].agent,
        ],
        messages=[],
        max_round=3,
        speaker_selection_method='round_robin',
    )

    executor_manager = GroupChatManager(
        groupchat=executor_chat,
        llm_config=cmbagent_instance.llm_config,
        name="engineer_nested_chat",
    )

    # Custom summary function that handles empty messages
    def safe_summary(sender, recipient, summary_args):
        """Safely get last message or return empty string."""
        messages = summary_args.get("messages", [])
        if messages and len(messages) > 0:
            return messages[-1].get('content', '')
        return ""

    nested_chats = [{
        "recipient": executor_manager,
        "message": lambda recipient, messages, sender, config: (
            f"{messages[-1]['content']}" if messages and len(messages) > 0 else ""
        ),
        "max_turns": 1,
        "summary_method": safe_summary,  # Use custom safe summary
    }]

    # Register nested chat trigger
    other_agents = [
        agent for agent in cmbagent_instance.agents
        if agent != agents['engineer'].agent
    ]

    agents['engineer_nest'].agent.register_nested_chats(
        trigger=lambda sender: sender not in other_agents,
        chat_queue=nested_chats
    )

    # Setup handoffs
    agents['engineer'].agent.handoffs.set_after_work(
        AgentTarget(agents['engineer_nest'].agent)
    )
    agents['engineer_nest'].agent.handoffs.set_after_work(
        AgentTarget(agents['executor_response_formatter'].agent)
    )

    debug_print('Engineer nested chat configured\n', indent=2)


def setup_idea_maker_nested_chat(agents: Dict, cmbagent_instance):
    """
    Setup nested chat for idea generation.

    When idea_maker generates ideas, it enters a nested conversation with
    idea_saver for processing and storage.

    Args:
        agents: Dictionary of agent instances
        cmbagent_instance: CMBAgent instance for config access
    """
    debug_print('Setting up idea maker nested chat...')

    # Create nested group chat for idea generation
    idea_maker_chat = GroupChat(
        agents=[
            agents['idea_maker_response_formatter'].agent,
            agents['idea_saver'].agent,
        ],
        messages=[],
        max_round=4,
        speaker_selection_method='round_robin',
    )

    idea_maker_manager = GroupChatManager(
        groupchat=idea_maker_chat,
        llm_config=cmbagent_instance.llm_config,
        name="idea_maker_manager",
    )

    # Custom summary function that handles empty messages
    def safe_summary(sender, recipient, summary_args):
        """Safely get last message or return empty string."""
        messages = summary_args.get("messages", [])
        if messages and len(messages) > 0:
            return messages[-1].get('content', '')
        return ""

    nested_chats = [{
        "recipient": idea_maker_manager,
        "message": lambda recipient, messages, sender, config: (
            f"{messages[-1]['content']}" if messages and len(messages) > 0 else ""
        ),
        "max_turns": 1,
        "summary_method": safe_summary,  # Use custom safe summary
    }]

    # Register nested chat trigger
    other_agents = [
        agent for agent in cmbagent_instance.agents
        if agent != agents['idea_maker'].agent
    ]

    agents['idea_maker_nest'].agent.register_nested_chats(
        trigger=lambda sender: sender not in other_agents,
        chat_queue=nested_chats
    )

    # Setup handoffs
    agents['idea_maker'].agent.handoffs.set_after_work(
        AgentTarget(agents['idea_maker_nest'].agent)
    )
    agents['idea_maker_nest'].agent.handoffs.set_after_work(
        AgentTarget(agents['control'].agent)
    )

    debug_print('Idea maker nested chat configured\n', indent=2)
