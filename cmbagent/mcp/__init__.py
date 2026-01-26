"""
MCP (Model Context Protocol) Client Integration for CMBAgent.

This module provides MCP client capabilities to connect to external MCP servers
and integrate their tools with AG2 agents.

Example:
    >>> from cmbagent.mcp import MCPClientManager, MCPToolIntegration
    >>> 
    >>> # Create manager and connect to servers
    >>> manager = MCPClientManager()
    >>> await manager.connect_all()
    >>> 
    >>> # Integrate tools with AG2 agents
    >>> integration = MCPToolIntegration(manager)
    >>> integration.register_tools_with_agent(my_agent)
"""

from .client_manager import MCPClientManager
from .tool_integration import MCPToolIntegration

__all__ = [
    'MCPClientManager',
    'MCPToolIntegration',
]
