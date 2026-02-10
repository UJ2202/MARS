"""
Mode-specific handoffs.

Configures handoffs based on operating mode (chat vs standard).
"""

from typing import Dict
from autogen.agentchat.group import AgentTarget, OnCondition, StringLLMCondition
from .debug import debug_print


def register_chat_mode_handoffs(agents: Dict, cmbagent_instance):
    """
    Register handoffs for chat mode (interactive mode with human).

    In chat mode, control hands off to admin (human), who then hands off
    to the selected chat agent for continued interaction.

    Args:
        agents: Dictionary of agent instances
        cmbagent_instance: CMBAgent instance for config access
    """
    debug_print('Registering chat mode handoffs...')

    # Get the chat agent specified in config
    agent_on = cmbagent_instance.get_agent_object_from_name(
        cmbagent_instance.chat_agent
    )

    # Control → Admin → ChatAgent loop
    agents['control'].agent.handoffs.set_after_work(
        AgentTarget(agents['admin'].agent)
    )
    agents['admin'].agent.handoffs.set_after_work(
        AgentTarget(agent_on.agent)
    )

    debug_print(f'Chat mode: control → admin → {cmbagent_instance.chat_agent}\n', indent=2)


def register_standard_mode_handoffs(agents: Dict):
    """
    Register handoffs for standard mode (non-chat).

    Control agent uses LLM to decide which agent to hand off to based on
    the current conversation context.

    Args:
        agents: Dictionary of agent instances
    """
    debug_print('Registering standard mode handoffs...')

    # Default: control → terminator
    agents['control'].agent.handoffs.set_after_work(
        AgentTarget(agents['terminator'].agent)
    )

    # Add conditional handoffs (LLM decides)
    agents['control'].agent.handoffs.add_llm_conditions([
        OnCondition(
            target=AgentTarget(agents['engineer'].agent),
            condition=StringLLMCondition(prompt="Code execution failed."),
        ),
        OnCondition(
            target=AgentTarget(agents['researcher'].agent),
            condition=StringLLMCondition(
                prompt="Researcher needed to generate reasoning, write report, or interpret results"
            ),
        ),
        OnCondition(
            target=AgentTarget(agents['engineer'].agent),
            condition=StringLLMCondition(
                prompt="Engineer needed to write code, make plots, do calculations."
            ),
        ),
        OnCondition(
            target=AgentTarget(agents['idea_maker'].agent),
            condition=StringLLMCondition(prompt="idea_maker needed to make new ideas"),
        ),
        OnCondition(
            target=AgentTarget(agents['idea_hater'].agent),
            condition=StringLLMCondition(prompt="idea_hater needed to critique ideas"),
        ),
        OnCondition(
            target=AgentTarget(agents['terminator'].agent),
            condition=StringLLMCondition(prompt="The task is completed."),
        ),
    ])

    debug_print('Standard mode with conditional handoffs configured\n', indent=2)
