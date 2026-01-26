"""
Tool registry for managing external tools and registering them with AG2 agents.

This module provides a centralized registry for managing CrewAI and LangChain tools
and making them available to CMBAgent agents.
"""

from typing import Dict, List, Optional, Any
from autogen import register_function
from .tool_adapter import AG2ToolAdapter, convert_multiple_tools


class ExternalToolRegistry:
    """
    Registry for managing external tools and their registration with AG2 agents.
    
    This class provides a centralized way to:
    1. Register external tools from CrewAI and LangChain
    2. Manage tool availability per agent
    3. Bulk register tools with specific agents
    """
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, AG2ToolAdapter] = {}
        self._tool_categories: Dict[str, List[str]] = {}
        
    def register_tool(
        self,
        tool_adapter: AG2ToolAdapter,
        category: Optional[str] = None
    ):
        """
        Register a single tool in the registry.
        
        Args:
            tool_adapter: AG2ToolAdapter instance
            category: Optional category for organizing tools (e.g., 'search', 'file', 'web')
        """
        self._tools[tool_adapter.name] = tool_adapter
        
        if category:
            if category not in self._tool_categories:
                self._tool_categories[category] = []
            self._tool_categories[category].append(tool_adapter.name)
    
    def register_tools(
        self,
        tools: List[AG2ToolAdapter],
        category: Optional[str] = None
    ):
        """
        Register multiple tools in the registry.
        
        Args:
            tools: List of AG2ToolAdapter instances
            category: Optional category for organizing tools
        """
        for tool in tools:
            self.register_tool(tool, category)
    
    def register_external_tools(
        self,
        tools: List[Any],
        source_framework: str = 'auto',
        category: Optional[str] = None
    ):
        """
        Convert and register external tools from CrewAI or LangChain.
        
        Args:
            tools: List of tool instances from external frameworks
            source_framework: 'crewai', 'langchain', or 'auto'
            category: Optional category for organizing tools
        """
        converted_tools = convert_multiple_tools(tools, source_framework)
        self.register_tools(converted_tools, category)
    
    def get_tool(self, tool_name: str) -> Optional[AG2ToolAdapter]:
        """Get a tool by name."""
        return self._tools.get(tool_name)
    
    def get_tools_by_category(self, category: str) -> List[AG2ToolAdapter]:
        """Get all tools in a specific category."""
        tool_names = self._tool_categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]
    
    def get_all_tools(self) -> List[AG2ToolAdapter]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def get_tool_names(self) -> List[str]:
        """Get names of all registered tools."""
        return list(self._tools.keys())
    
    def get_categories(self) -> List[str]:
        """Get all tool categories."""
        return list(self._tool_categories.keys())
    
    def register_with_agent(
        self,
        agent,
        tool_names: Optional[List[str]] = None,
        category: Optional[str] = None,
        executor_agent = None
    ):
        """
        Register tools with an AG2 agent.
        
        Args:
            agent: The AG2 agent to register tools with
            tool_names: Specific tool names to register (if None, registers all)
            category: Register all tools in this category
            executor_agent: Optional executor agent for function execution
        """
        if tool_names is None and category is None:
            # Register all tools
            tools_to_register = self.get_all_tools()
        elif category is not None:
            # Register tools from specific category
            tools_to_register = self.get_tools_by_category(category)
        else:
            # Register specific tools
            tools_to_register = [
                self._tools[name] for name in tool_names 
                if name in self._tools
            ]
        
        # Use executor_agent if provided, otherwise use agent as executor
        exec_agent = executor_agent if executor_agent is not None else agent
        
        for tool_adapter in tools_to_register:
            register_function(
                tool_adapter.get_ag2_function(),
                caller=agent,
                executor=exec_agent,
                name=tool_adapter.name,
                description=tool_adapter.description
            )
    
    def register_with_multiple_agents(
        self,
        agents: List[Any],
        tool_names: Optional[List[str]] = None,
        category: Optional[str] = None,
        executor_agent = None
    ):
        """
        Register tools with multiple AG2 agents.
        
        Args:
            agents: List of AG2 agents
            tool_names: Specific tool names to register
            category: Register all tools in this category
            executor_agent: Optional executor agent for function execution
        """
        for agent in agents:
            self.register_with_agent(
                agent=agent,
                tool_names=tool_names,
                category=category,
                executor_agent=executor_agent
            )
    
    def list_tools(self, verbose: bool = False) -> str:
        """
        Get a formatted list of all tools.
        
        Args:
            verbose: If True, includes descriptions
            
        Returns:
            Formatted string of all tools
        """
        output = "Registered External Tools:\n"
        output += "=" * 50 + "\n\n"
        
        if self._tool_categories:
            for category in sorted(self._tool_categories.keys()):
                output += f"Category: {category}\n"
                output += "-" * 50 + "\n"
                
                for tool_name in self._tool_categories[category]:
                    tool = self._tools.get(tool_name)
                    if tool:
                        output += f"  - {tool.name}"
                        if verbose:
                            output += f"\n    Description: {tool.description}\n"
                        output += "\n"
                output += "\n"
        
        # Tools without category
        uncategorized = [
            name for name in self._tools.keys()
            if not any(name in cat_tools for cat_tools in self._tool_categories.values())
        ]
        
        if uncategorized:
            output += "Category: Uncategorized\n"
            output += "-" * 50 + "\n"
            for tool_name in uncategorized:
                tool = self._tools.get(tool_name)
                if tool:
                    output += f"  - {tool.name}"
                    if verbose:
                        output += f"\n    Description: {tool.description}\n"
                    output += "\n"
        
        return output
    
    def clear(self):
        """Clear all registered tools."""
        self._tools.clear()
        self._tool_categories.clear()


# Global registry instance
_global_registry = ExternalToolRegistry()


def get_global_registry() -> ExternalToolRegistry:
    """Get the global tool registry instance."""
    return _global_registry
