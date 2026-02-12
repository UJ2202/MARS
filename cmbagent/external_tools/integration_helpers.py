"""
Helper functions for integrating external tools with CMBAgent.

This module provides utility functions to register external tools
from CrewAI and LangChain with CMBAgent agents during the planning
and control workflow.
"""

import logging
from typing import List, Optional
from autogen import register_function
from cmbagent.external_tools import (
    ExternalToolRegistry,
    get_crewai_free_tools,
    get_langchain_free_tools,
    get_global_registry
)

logger = logging.getLogger(__name__)


def register_external_tools_with_agents(
    cmbagent_instance,
    use_crewai_tools: bool = True,
    use_langchain_tools: bool = True,
    tool_categories: Optional[List[str]] = None,
    agent_names: Optional[List[str]] = None,
    executor_agent_name: str = 'executor'
):
    """
    Register external tools from CrewAI and LangChain with CMBAgent agents.

    This function should be called from register_functions_to_agents() or
    during CMBAgent initialization to make external tools available.

    Args:
        cmbagent_instance: Instance of CMBAgent
        use_crewai_tools: Whether to load CrewAI tools
        use_langchain_tools: Whether to load LangChain tools
        tool_categories: Specific tool categories to load (e.g., ['search', 'file', 'web'])
                        If None, loads all tools
        agent_names: List of agent names to register tools with
                    If None, registers with commonly used agents
        executor_agent_name: Name of the executor agent for tool execution

    Returns:
        ExternalToolRegistry instance with all registered tools

    Example:
        >>> # In cmbagent.py or functions.py
        >>> registry = register_external_tools_with_agents(
        ...     cmbagent_instance,
        ...     use_crewai_tools=True,
        ...     use_langchain_tools=True,
        ...     agent_names=['engineer', 'researcher', 'planner']
        ... )
    """
    # Get or create registry
    registry = get_global_registry()

    # Load CrewAI tools if requested
    if use_crewai_tools:
        try:
            crewai_tools = get_crewai_free_tools()
            registry.register_tools(crewai_tools, category='crewai')
            logger.info("tools_loaded", framework="CrewAI", count=len(crewai_tools))
        except Exception as e:
            logger.warning("tools_load_failed", framework="CrewAI", error=str(e))

    # Load LangChain tools if requested
    if use_langchain_tools:
        try:
            langchain_tools = get_langchain_free_tools()
            registry.register_tools(langchain_tools, category='langchain')
            logger.info("tools_loaded", framework="LangChain", count=len(langchain_tools))
        except Exception as e:
            logger.warning("tools_load_failed", framework="LangChain", error=str(e))

    # Determine which agents to register tools with
    if agent_names is None:
        # Default agents that benefit from external tools
        agent_names = [
            'engineer',
            'researcher',
            'planner',
            'control',
        ]

    # Get executor agent
    try:
        executor = cmbagent_instance.get_agent_from_name(executor_agent_name)
    except:
        executor = None
        logger.warning("executor_agent_not_found", agent=executor_agent_name)

    # Register tools with each agent
    for agent_name in agent_names:
        try:
            agent = cmbagent_instance.get_agent_from_name(agent_name)

            if tool_categories:
                # Register only specific categories
                for category in tool_categories:
                    registry.register_with_agent(
                        agent=agent,
                        category=category,
                        executor_agent=executor
                    )
            else:
                # Register all tools
                registry.register_with_agent(
                    agent=agent,
                    executor_agent=executor
                )

            logger.info("tools_registered_with_agent", agent=agent_name)
        except Exception as e:
            logger.warning("tools_registration_failed", agent=agent_name, error=str(e))

    return registry


def register_specific_external_tools(
    cmbagent_instance,
    tool_names: List[str],
    agent_names: List[str],
    executor_agent_name: str = 'executor'
):
    """
    Register specific external tools with specific agents.

    Use this for fine-grained control over which tools are available to which agents.

    Args:
        cmbagent_instance: Instance of CMBAgent
        tool_names: List of specific tool names to register
        agent_names: List of agent names to register tools with
        executor_agent_name: Name of the executor agent

    Example:
        >>> register_specific_external_tools(
        ...     cmbagent_instance,
        ...     tool_names=['WikipediaQueryRun', 'ArxivQueryRun', 'DuckDuckGoSearchRun'],
        ...     agent_names=['researcher']
        ... )
    """
    registry = get_global_registry()

    # Get executor agent
    try:
        executor = cmbagent_instance.get_agent_from_name(executor_agent_name)
    except:
        executor = None

    # Register tools with each agent
    for agent_name in agent_names:
        try:
            agent = cmbagent_instance.get_agent_from_name(agent_name)
            registry.register_with_agent(
                agent=agent,
                tool_names=tool_names,
                executor_agent=executor
            )
            logger.info("specific_tools_registered", agent=agent_name, tool_count=len(tool_names))
        except Exception as e:
            logger.warning("tools_registration_failed", agent=agent_name, error=str(e))


def add_custom_tool_to_registry(
    tool_name: str,
    tool_function: callable,
    tool_description: str,
    category: Optional[str] = None
):
    """
    Add a custom tool to the registry.

    Use this to add your own custom tools alongside CrewAI and LangChain tools.

    Args:
        tool_name: Name of the tool
        tool_function: The function to execute
        tool_description: Description of what the tool does
        category: Optional category for organization

    Example:
        >>> def my_custom_tool(query: str) -> str:
        ...     '''My custom tool implementation'''
        ...     return f"Processed: {query}"
        >>>
        >>> add_custom_tool_to_registry(
        ...     tool_name="my_custom_tool",
        ...     tool_function=my_custom_tool,
        ...     tool_description="A custom tool for processing queries",
        ...     category="custom"
        ... )
    """
    from cmbagent.external_tools.tool_adapter import AG2ToolAdapter

    registry = get_global_registry()
    tool_adapter = AG2ToolAdapter(
        tool_name=tool_name,
        tool_description=tool_description,
        tool_function=tool_function
    )
    registry.register_tool(tool_adapter, category=category)
    logger.info("custom_tool_added", tool=tool_name)
