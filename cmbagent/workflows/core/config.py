"""
Agent configuration builders for CMBAgent workflows.

This module provides configuration utilities that preserve the exact same
agent configuration behavior as the original workflow implementations.
"""

from typing import Dict, List, Any, Optional

from cmbagent.utils import (
    get_model_config,
    default_agents_llm_model,
)


class AgentConfigBuilder:
    """
    Builder for agent LLM configurations.

    This class provides a fluent interface for building agent configurations
    while preserving compatibility with the original configuration patterns.

    Example usage:
        configs = (
            AgentConfigBuilder(api_keys)
            .add('engineer', 'gpt-4o-2024-11-20')
            .add('researcher', 'gpt-4o-2024-11-20')
            .add_defaults(['plot_judge', 'camb_context'])
            .build()
        )
    """

    def __init__(self, api_keys: Dict[str, str]):
        """
        Initialize the builder with API keys.

        Args:
            api_keys: Dictionary of API keys from get_api_keys_from_env()
        """
        self.api_keys = api_keys
        self.configs: Dict[str, Dict] = {}

    def add(self, agent_name: str, model: str) -> 'AgentConfigBuilder':
        """
        Add configuration for a specific agent.

        Args:
            agent_name: Name of the agent (e.g., 'engineer', 'researcher')
            model: Model to use for this agent

        Returns:
            Self for chaining
        """
        self.configs[agent_name] = get_model_config(model, self.api_keys)
        return self

    def add_defaults(self, agents: List[str]) -> 'AgentConfigBuilder':
        """
        Add default configurations for common agents.

        Uses default_agents_llm_model to determine the model for each agent.

        Args:
            agents: List of agent names to add defaults for

        Returns:
            Self for chaining
        """
        for agent in agents:
            if agent in default_agents_llm_model:
                self.add(agent, default_agents_llm_model[agent])
        return self

    def add_if_not_none(self, agent_name: str, model: Optional[str]) -> 'AgentConfigBuilder':
        """
        Add configuration only if model is not None.

        Args:
            agent_name: Name of the agent
            model: Model to use (skipped if None)

        Returns:
            Self for chaining
        """
        if model is not None:
            self.add(agent_name, model)
        return self

    def build(self) -> Dict[str, Dict]:
        """
        Return the built configuration dictionary.

        Returns:
            Dictionary mapping agent names to their configurations
        """
        return self.configs.copy()


def one_shot_agent_configs(
    api_keys: Dict[str, str],
    engineer_model: str = default_agents_llm_model['engineer'],
    researcher_model: str = default_agents_llm_model['researcher'],
    plot_judge_model: str = default_agents_llm_model['plot_judge'],
    camb_context_model: str = default_agents_llm_model['camb_context'],
) -> Dict[str, Dict]:
    """
    Build agent configurations for one_shot workflow.

    This function preserves the exact same configuration as the original
    one_shot function (lines 88-91 of one_shot.py).

    Args:
        api_keys: Dictionary of API keys
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
        plot_judge_model: Model for plot judge agent
        camb_context_model: Model for CAMB context agent

    Returns:
        Dictionary of agent configurations
    """
    return (
        AgentConfigBuilder(api_keys)
        .add('engineer', engineer_model)
        .add('researcher', researcher_model)
        .add('plot_judge', plot_judge_model)
        .add('camb_context', camb_context_model)
        .build()
    )


def human_in_the_loop_agent_configs(
    api_keys: Dict[str, str],
    engineer_model: str = 'gpt-4o-2024-11-20',
    researcher_model: str = 'gpt-4o-2024-11-20',
) -> Dict[str, Dict]:
    """
    Build agent configurations for human_in_the_loop workflow.

    Preserves the exact same configuration as the original function.

    Args:
        api_keys: Dictionary of API keys
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent

    Returns:
        Dictionary of agent configurations
    """
    return (
        AgentConfigBuilder(api_keys)
        .add('engineer', engineer_model)
        .add('researcher', researcher_model)
        .build()
    )


def control_agent_configs(
    api_keys: Dict[str, str],
    engineer_model: str = default_agents_llm_model['engineer'],
    researcher_model: str = default_agents_llm_model['researcher'],
    idea_maker_model: str = default_agents_llm_model['idea_maker'],
    idea_hater_model: str = default_agents_llm_model['idea_hater'],
    plot_judge_model: str = default_agents_llm_model['plot_judge'],
    camb_context_model: Optional[str] = None,
) -> Dict[str, Dict]:
    """
    Build agent configurations for control workflow.

    Preserves the exact same configuration as the original control function
    (lines 98-102 of control.py) and planning_control.py control phase.

    Args:
        api_keys: Dictionary of API keys
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
        idea_maker_model: Model for idea maker agent
        idea_hater_model: Model for idea hater agent
        plot_judge_model: Model for plot judge agent
        camb_context_model: Model for CAMB context agent (optional, for context carryover)

    Returns:
        Dictionary of agent configurations
    """
    builder = (
        AgentConfigBuilder(api_keys)
        .add('engineer', engineer_model)
        .add('researcher', researcher_model)
        .add('idea_maker', idea_maker_model)
        .add('idea_hater', idea_hater_model)
        .add('plot_judge', plot_judge_model)
    )

    # camb_context is only added in planning_and_control_context_carryover
    if camb_context_model is not None:
        builder.add('camb_context', camb_context_model)

    return builder.build()


def planning_agent_configs(
    api_keys: Dict[str, str],
    planner_model: str = default_agents_llm_model['planner'],
    plan_reviewer_model: str = default_agents_llm_model['plan_reviewer'],
) -> Dict[str, Dict]:
    """
    Build agent configurations for planning phase.

    Preserves the exact same configuration as the original planning_and_control
    function (lines 163-164, 725-726 of planning_control.py).

    Args:
        api_keys: Dictionary of API keys
        planner_model: Model for planner agent
        plan_reviewer_model: Model for plan reviewer agent

    Returns:
        Dictionary of agent configurations
    """
    return (
        AgentConfigBuilder(api_keys)
        .add('planner', planner_model)
        .add('plan_reviewer', plan_reviewer_model)
        .build()
    )


def planning_and_control_control_configs(
    api_keys: Dict[str, str],
    engineer_model: str = default_agents_llm_model['engineer'],
    researcher_model: str = default_agents_llm_model['researcher'],
    idea_maker_model: str = default_agents_llm_model['idea_maker'],
    idea_hater_model: str = default_agents_llm_model['idea_hater'],
) -> Dict[str, Dict]:
    """
    Build agent configurations for planning_and_control control phase.

    Preserves the exact same configuration as the original function
    (lines 802-805 of planning_control.py).

    Args:
        api_keys: Dictionary of API keys
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
        idea_maker_model: Model for idea maker agent
        idea_hater_model: Model for idea hater agent

    Returns:
        Dictionary of agent configurations
    """
    return (
        AgentConfigBuilder(api_keys)
        .add('engineer', engineer_model)
        .add('researcher', researcher_model)
        .add('idea_maker', idea_maker_model)
        .add('idea_hater', idea_hater_model)
        .build()
    )
