"""
MCP Client Manager - Manages connections to external MCP servers.

This module handles connecting to MCP servers, discovering tools,
and executing tool calls.
"""

import asyncio
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPClientManager:
    """
    Manages connections to multiple MCP servers and their tools.
    
    Handles:
    - Connecting to MCP servers via stdio
    - Discovering available tools
    - Executing tool calls
    - Managing sessions and cleanup
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize MCP Client Manager.
        
        Args:
            config_path: Path to client_config.yaml (default: adjacent to this file)
        """
        self.sessions: Dict[str, ClientSession] = {}
        self.server_params: Dict[str, StdioServerParameters] = {}
        self.tools_cache: Dict[str, List[Dict]] = {}
        self.contexts: Dict[str, Any] = {}  # Store context managers for cleanup
        
        # Load configuration
        if config_path is None:
            config_path = Path(__file__).parent / "client_config.yaml"
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.settings = self.config.get('settings', {})
        self.servers_config = self.config.get('mcp_servers', {})
        
        logger.info(f"Initialized MCP Client Manager with {len(self.servers_config)} server configs")
    
    async def connect_to_server(self, server_name: str) -> bool:
        """
        Connect to a single MCP server.
        
        Args:
            server_name: Name of the server from config
            
        Returns:
            True if connection successful, False otherwise
        """
        if server_name not in self.servers_config:
            logger.error(f"Server {server_name} not found in config")
            return False
        
        server_config = self.servers_config[server_name]
        
        if not server_config.get('enabled', False):
            logger.info(f"Server {server_name} is disabled in config")
            return False
        
        try:
            # Substitute environment variables in config
            env = {}
            for key, value in server_config.get('env', {}).items():
                if value.startswith('${') and value.endswith('}'):
                    env_var = value[2:-1]
                    env_value = os.getenv(env_var)
                    if env_value is None:
                        logger.warning(f"Environment variable {env_var} not set for {server_name}")
                        return False
                    env[key] = env_value
                else:
                    env[key] = value
            
            # Create server parameters
            server_params = StdioServerParameters(
                command=server_config['command'],
                args=server_config.get('args', []),
                env=env if env else None
            )
            
            # Connect to server using context manager properly
            logger.info(f"Connecting to MCP server: {server_name}")
            
            # stdio_client returns an async context manager - we need to enter it
            client_context = stdio_client(server_params)
            read_stream, write_stream = await client_context.__aenter__()
            
            # Store the context for proper cleanup later
            self.contexts[server_name] = client_context
            
            # Create and initialize session
            session = ClientSession(read_stream, write_stream)
            await session.initialize()
            
            # Store session and params
            self.sessions[server_name] = session
            self.server_params[server_name] = server_params
            
            # Discover tools if auto-discovery enabled
            if self.settings.get('auto_discover_tools', True):
                await self._discover_tools(server_name)
            
            logger.info(f"Successfully connected to {server_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {server_name}: {e}")
            # Print to console for debugging
            print(f"   ⚠ MCP Connection Error ({server_name}): {e}")
            import traceback
            print(f"   ⚠ Traceback: {traceback.format_exc()}")
            return False
    
    async def connect_all(self) -> Dict[str, bool]:
        """
        Connect to all enabled MCP servers.
        
        Returns:
            Dictionary mapping server names to connection success status
        """
        results = {}
        
        for server_name in self.servers_config:
            if self.servers_config[server_name].get('enabled', False):
                success = await self.connect_to_server(server_name)
                results[server_name] = success
        
        connected_count = sum(1 for v in results.values() if v)
        logger.info(f"Connected to {connected_count}/{len(results)} MCP servers")
        
        return results
    
    async def _discover_tools(self, server_name: str) -> List[Dict]:
        """
        Discover available tools from a server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of tool definitions
        """
        if server_name not in self.sessions:
            logger.error(f"No session found for {server_name}")
            return []
        
        try:
            session = self.sessions[server_name]
            tools_response = await session.list_tools()
            
            tools = []
            for tool in tools_response.tools:
                tool_def = {
                    'server_name': server_name,
                    'name': tool.name,
                    'description': tool.description,
                    'inputSchema': tool.inputSchema
                }
                tools.append(tool_def)
            
            # Cache tools if enabled
            if self.settings.get('cache_tool_schemas', True):
                self.tools_cache[server_name] = tools
            
            logger.info(f"Discovered {len(tools)} tools from {server_name}")
            return tools
            
        except Exception as e:
            logger.error(f"Failed to discover tools from {server_name}: {e}")
            return []
    
    def get_all_tools(self) -> List[Dict]:
        """
        Get all available tools from all connected servers.
        
        Returns:
            List of all tool definitions
        """
        all_tools = []
        for server_name in self.sessions:
            if server_name in self.tools_cache:
                all_tools.extend(self.tools_cache[server_name])
        
        return all_tools
    
    def get_tools_by_server(self, server_name: str) -> List[Dict]:
        """
        Get tools from a specific server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of tool definitions for that server
        """
        return self.tools_cache.get(server_name, [])
    
    def is_server_available(self, server_name: str) -> bool:
        """Check if a server is connected and available."""
        return server_name in self.sessions
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call a tool on a specific server.
        
        Args:
            server_name: Name of the server
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            Dictionary with 'status' and 'result' or 'error'
        """
        if server_name not in self.sessions:
            return {
                'status': 'error',
                'error': f"Server {server_name} not connected"
            }
        
        try:
            session = self.sessions[server_name]
            
            # Call tool with timeout
            timeout = self.settings.get('timeout_seconds', 60)
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments or {}),
                timeout=timeout
            )
            
            return {
                'status': 'success',
                'result': result.content
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Tool call timed out: {server_name}.{tool_name}")
            return {
                'status': 'error',
                'error': 'Tool call timed out'
            }
        except Exception as e:
            logger.error(f"Tool call failed: {server_name}.{tool_name} - {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def disconnect_server(self, server_name: str):
        """Disconnect from a specific server."""
        if server_name in self.sessions:
            try:
                # Exit the context manager if it exists
                if server_name in self.contexts:
                    await self.contexts[server_name].__aexit__(None, None, None)
                    del self.contexts[server_name]
                
                # Clean up session and cache
                del self.sessions[server_name]
                if server_name in self.tools_cache:
                    del self.tools_cache[server_name]
                logger.info(f"Disconnected from {server_name}")
            except Exception as e:
                logger.error(f"Error disconnecting from {server_name}: {e}")
    
    async def disconnect_all(self):
        """Disconnect from all servers."""
        server_names = list(self.sessions.keys())
        for server_name in server_names:
            await self.disconnect_server(server_name)
        
        logger.info("Disconnected from all MCP servers")
    
    def __del__(self):
        """Cleanup on deletion."""
        # Note: In production, you should call disconnect_all() explicitly
        # This is just a safety net
        if self.sessions:
            logger.warning("MCPClientManager deleted with active sessions - cleanup may be incomplete")
