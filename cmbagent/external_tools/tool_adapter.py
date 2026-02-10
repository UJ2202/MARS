"""
Tool adapter to convert CrewAI and LangChain tools to AG2-compatible format.

This module provides adapters to bridge external tool frameworks with AG2 agents.
Uses AG2's native Interoperability module for robust cross-framework tool conversion.
"""

import inspect
from typing import Any, Callable, Dict, List, Optional, Union
from functools import wraps
import json

try:
    from autogen.interop import Interoperability
    HAS_INTEROP = True
except ImportError:
    HAS_INTEROP = False
    print("Warning: autogen.interop not available. Using fallback adapter.")


class AG2ToolAdapter:
    """
    Adapter class to convert external tools to AG2-compatible functions.
    
    AG2 agents use the autogen.register_function API to register tools.
    This adapter converts CrewAI and LangChain tools to match that format.
    """
    
    def __init__(self, tool_name: str, tool_description: str, tool_function: Callable):
        """
        Initialize the tool adapter.
        
        Args:
            tool_name: Name of the tool
            tool_description: Description of what the tool does
            tool_function: The actual function to execute
        """
        self.name = tool_name
        self.description = tool_description
        self.function = tool_function
        
    def get_ag2_function(self) -> Callable:
        """
        Get the AG2-compatible function.
        
        Returns:
            A callable that can be registered with AG2 agents
        """
        @wraps(self.function)
        def ag2_wrapper(*args, **kwargs):
            """Wrapper function for AG2 compatibility."""
            try:
                result = self.function(*args, **kwargs)
                return result
            except Exception as e:
                return f"Error executing {self.name}: {str(e)}"
        
        # Preserve function name and docstring
        ag2_wrapper.__name__ = self.name
        ag2_wrapper.__doc__ = self.description
        
        return ag2_wrapper


def convert_crewai_tool_to_ag2(crewai_tool) -> Union[Any, AG2ToolAdapter]:
    """
    Convert a CrewAI tool to AG2-compatible format.
    
    Uses AG2's native Interoperability module when available (recommended),
    falls back to custom adapter if not available.
    
    CrewAI tools typically have:
    - name: str
    - description: str
    - func: Callable or _run method
    
    Args:
        crewai_tool: A CrewAI tool instance
        
    Returns:
        AG2-compatible tool (native Interop or AG2ToolAdapter instance)
        
    Example:
        >>> from crewai_tools import SerperDevTool
        >>> crewai_tool = SerperDevTool()
        >>> ag2_tool = convert_crewai_tool_to_ag2(crewai_tool)
    """
    # Use native AG2 Interoperability if available (recommended)
    if HAS_INTEROP:
        try:
            interop = Interoperability()
            return interop.convert_tool(tool=crewai_tool, type="crewai")
        except Exception as e:
            print(f"Warning: AG2 native interop failed for {crewai_tool}, using fallback: {e}")
    
    # Fallback to custom adapter
    # Extract tool properties
    tool_name = getattr(crewai_tool, 'name', crewai_tool.__class__.__name__)
    tool_description = getattr(crewai_tool, 'description', '')
    
    # Get the executable function
    if hasattr(crewai_tool, 'func'):
        tool_function = crewai_tool.func
    elif hasattr(crewai_tool, '_run'):
        tool_function = crewai_tool._run
    elif hasattr(crewai_tool, 'run'):
        tool_function = crewai_tool.run
    elif callable(crewai_tool):
        tool_function = crewai_tool
    else:
        raise ValueError(f"Cannot extract callable from CrewAI tool: {crewai_tool}")
    
    return AG2ToolAdapter(
        tool_name=tool_name,
        tool_description=tool_description,
        tool_function=tool_function
    )


def convert_langchain_tool_to_ag2(langchain_tool) -> Union[Any, AG2ToolAdapter]:
    """
    Convert a LangChain tool to AG2-compatible format.
    
    Uses AG2's native Interoperability module when available (recommended),
    falls back to custom adapter if not available.
    
    LangChain tools typically have:
    - name: str
    - description: str
    - func: Callable or _run/_arun method
    
    Args:
        langchain_tool: A LangChain tool instance
        
    Returns:
        AG2-compatible tool (native Interop or AG2ToolAdapter instance)
        
    Example:
        >>> from langchain_community.tools import WikipediaQueryRun
        >>> from langchain_community.utilities import WikipediaAPIWrapper
        >>> wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
        >>> ag2_tool = convert_langchain_tool_to_ag2(wikipedia)
    """
    # Use native AG2 Interoperability if available (recommended)
    if HAS_INTEROP:
        try:
            interop = Interoperability()
            return interop.convert_tool(tool=langchain_tool, type="langchain")
        except Exception as e:
            print(f"Warning: AG2 native interop failed for {langchain_tool}, using fallback: {e}")
    
    # Fallback to custom adapter
    # Extract tool properties
    tool_name = getattr(langchain_tool, 'name', langchain_tool.__class__.__name__)
    tool_description = getattr(langchain_tool, 'description', '')
    
    # Get the executable function
    if hasattr(langchain_tool, 'func'):
        tool_function = langchain_tool.func
    elif hasattr(langchain_tool, '_run'):
        # LangChain tools use _run for synchronous execution
        tool_function = langchain_tool._run
    elif hasattr(langchain_tool, 'run'):
        tool_function = langchain_tool.run
    elif callable(langchain_tool):
        tool_function = langchain_tool
    else:
        raise ValueError(f"Cannot extract callable from LangChain tool: {langchain_tool}")
    
    return AG2ToolAdapter(
        tool_name=tool_name,
        tool_description=tool_description,
        tool_function=tool_function
    )


def convert_multiple_tools(
    tools: List[Any],
    source_framework: str = 'auto'
) -> List[AG2ToolAdapter]:
    """
    Convert multiple tools from external frameworks to AG2 format.
    
    Args:
        tools: List of tool instances from CrewAI or LangChain
        source_framework: 'crewai', 'langchain', or 'auto' to detect automatically
        
    Returns:
        List of AG2ToolAdapter instances
        
    Example:
        >>> from crewai_tools import SerperDevTool, FileReadTool
        >>> tools = [SerperDevTool(), FileReadTool()]
        >>> ag2_tools = convert_multiple_tools(tools, source_framework='crewai')
    """
    converted_tools = []
    
    for tool in tools:
        if source_framework == 'auto':
            # Try to detect framework from tool type
            tool_class_name = tool.__class__.__module__
            
            if 'crewai' in tool_class_name.lower():
                converter = convert_crewai_tool_to_ag2
            elif 'langchain' in tool_class_name.lower():
                converter = convert_langchain_tool_to_ag2
            else:
                # Default to CrewAI converter
                print(f"Warning: Could not detect framework for {tool}. Trying CrewAI converter...")
                converter = convert_crewai_tool_to_ag2
        elif source_framework == 'crewai':
            converter = convert_crewai_tool_to_ag2
        elif source_framework == 'langchain':
            converter = convert_langchain_tool_to_ag2
        else:
            raise ValueError(f"Unknown framework: {source_framework}")
        
        try:
            converted_tool = converter(tool)
            converted_tools.append(converted_tool)
        except Exception as e:
            print(f"Warning: Failed to convert tool {tool}: {str(e)}")
    
    return converted_tools
