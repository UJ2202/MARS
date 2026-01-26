# Stage 11: MCP Client for External Tools

**Phase:** 3 - Integration
**Estimated Time:** 40-50 minutes
**Dependencies:** Stage 10 (MCP Server) recommended but not required
**Risk Level:** Medium

## Objectives

1. Implement MCP client within CMBAgent to call external MCP servers
2. Integrate external tools into agent workflows
3. Support dynamic tool discovery from MCP servers
4. Enable agents to use filesystem, GitHub, web search, and other MCP tools
5. Implement secure credential management for external services
6. Add tool execution tracking and cost attribution
7. Create fallback mechanisms when external tools unavailable

## Current State Analysis

### What We Have
- 50+ specialized CMBAgent agents
- Agent execution framework with AG2
- Tool/function registration system
- Database tracking of all operations
- MCP server exposing CMBAgent (Stage 10)

### What We Need
- MCP client SDK integration
- Tool discovery from external MCP servers
- Tool execution wrapper for agents
- Credential management for external services
- Dynamic tool registration with AG2 agents
- Error handling for external tool failures
- Cost tracking for external API calls

## Pre-Stage Verification

### Check Prerequisites
1. Stages 1-9 complete (Stage 10 optional)
2. CMBAgent agents execute successfully
3. AG2 function registration working
4. Database operations stable
5. Python MCP SDK installed

### Expected State
- Agents can register and call functions
- Ready to add external tool capabilities
- MCP client SDK available
- Environment supports async operations

## Implementation Tasks

### Task 1: Install MCP Client Dependencies
**Objective:** Add MCP client capabilities to project

**Actions:**
- Update `pyproject.toml` dependencies section
- Add: `mcp>=1.0.0` (if not already added in Stage 10)
- Install dependencies: `pip install -e .`

**Files to Modify:**
- `pyproject.toml` (dependencies section)

**Verification:**
- Dependencies install without conflicts
- Can import MCP client: `from mcp.client import ClientSession, StdioServerParameters`
- MCP version >= 1.0.0

### Task 2: Design MCP Client Configuration
**Objective:** Define which external MCP servers to connect to

**Configuration Schema:**

```yaml
# cmbagent/mcp/client_config.yaml
mcp_servers:
  filesystem:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"]
    env:
      # No special env vars needed for filesystem server
    description: "File system operations (read, write, search)"

  github:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
    description: "GitHub API operations (repos, issues, PRs)"

  brave_search:
    enabled: false  # Requires API key
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-brave-search"]
    env:
      BRAVE_API_KEY: "${BRAVE_API_KEY}"
    description: "Web search using Brave Search API"

  postgres:
    enabled: false
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-postgres", "postgresql://..."]
    env:
      DATABASE_URL: "${POSTGRES_URL}"
    description: "PostgreSQL database operations"

  puppeteer:
    enabled: false
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-puppeteer"]
    env: {}
    description: "Browser automation and web scraping"

  slack:
    enabled: false
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-slack"]
    env:
      SLACK_BOT_TOKEN: "${SLACK_BOT_TOKEN}"
    description: "Slack messaging and workspace operations"

# Global settings
settings:
  auto_discover_tools: true  # Automatically discover tools on connection
  cache_tool_schemas: true   # Cache tool schemas to avoid repeated queries
  timeout_seconds: 60        # Tool execution timeout
  max_retries: 3             # Retry failed tool calls
  fallback_on_error: true    # Continue execution if external tool fails
```

**Files to Create:**
- `cmbagent/mcp/client_config.yaml`

**Verification:**
- Configuration file valid YAML
- Environment variable substitution works
- Can enable/disable servers individually

### Task 3: Implement MCP Client Manager
**Objective:** Manage connections to external MCP servers

**Implementation:**

```python
import asyncio
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from typing import Dict, List, Optional
import yaml
import os
import logging

logger = logging.getLogger(__name__)

class MCPClientManager:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "client_config.yaml"
            )

        self.config = self._load_config(config_path)
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: Dict[str, List[dict]] = {}  # server_name -> tools

    def _load_config(self, config_path: str) -> dict:
        """Load MCP client configuration"""
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Substitute environment variables
        for server_name, server_config in config['mcp_servers'].items():
            if 'env' in server_config:
                for key, value in server_config['env'].items():
                    if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                        env_var = value[2:-1]
                        server_config['env'][key] = os.getenv(env_var, '')

        return config

    async def connect_all(self):
        """Connect to all enabled MCP servers"""
        for server_name, server_config in self.config['mcp_servers'].items():
            if server_config.get('enabled', False):
                await self.connect_server(server_name, server_config)

    async def connect_server(self, server_name: str, server_config: dict):
        """Connect to a specific MCP server"""
        try:
            logger.info(f"Connecting to MCP server: {server_name}")

            # Create server parameters
            server_params = StdioServerParameters(
                command=server_config['command'],
                args=server_config.get('args', []),
                env=server_config.get('env', {})
            )

            # Create stdio client
            stdio = stdio_client(server_params)

            # Create session
            async with stdio as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize session
                    await session.initialize()

                    # Discover tools
                    if self.config['settings']['auto_discover_tools']:
                        tools_result = await session.list_tools()
                        self.tools[server_name] = tools_result.tools

                        logger.info(
                            f"Discovered {len(tools_result.tools)} tools from {server_name}"
                        )

                    # Store session
                    self.sessions[server_name] = session

            logger.info(f"Connected to {server_name}")

        except Exception as e:
            logger.error(f"Failed to connect to {server_name}: {e}")

            if not self.config['settings']['fallback_on_error']:
                raise

    async def disconnect_all(self):
        """Disconnect from all MCP servers"""
        for server_name in list(self.sessions.keys()):
            await self.disconnect_server(server_name)

    async def disconnect_server(self, server_name: str):
        """Disconnect from a specific MCP server"""
        if server_name in self.sessions:
            # Sessions close when context exits
            del self.sessions[server_name]
            logger.info(f"Disconnected from {server_name}")

    def get_all_tools(self) -> List[dict]:
        """Get all tools from all connected servers"""
        all_tools = []

        for server_name, tools in self.tools.items():
            for tool in tools:
                # Add server metadata to tool
                tool_with_metadata = {
                    **tool,
                    "server_name": server_name,
                    "server_description": self.config['mcp_servers'][server_name]['description']
                }
                all_tools.append(tool_with_metadata)

        return all_tools

    def get_tools_by_server(self, server_name: str) -> List[dict]:
        """Get tools from a specific server"""
        return self.tools.get(server_name, [])

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict
    ) -> dict:
        """
        Call a tool on an external MCP server

        Args:
            server_name: Name of MCP server (e.g., "filesystem")
            tool_name: Name of tool to call (e.g., "read_file")
            arguments: Tool arguments as dict

        Returns:
            Tool execution result
        """
        if server_name not in self.sessions:
            raise ValueError(f"Not connected to server: {server_name}")

        session = self.sessions[server_name]

        try:
            logger.info(f"Calling tool {tool_name} on {server_name}")

            result = await session.call_tool(tool_name, arguments)

            return {
                "status": "success",
                "result": result.content,
                "server": server_name,
                "tool": tool_name
            }

        except Exception as e:
            logger.error(f"Tool call failed: {e}")

            if self.config['settings']['fallback_on_error']:
                return {
                    "status": "error",
                    "error": str(e),
                    "server": server_name,
                    "tool": tool_name
                }
            else:
                raise

    def list_available_servers(self) -> List[str]:
        """List all available MCP servers"""
        return list(self.sessions.keys())

    def is_server_available(self, server_name: str) -> bool:
        """Check if server is connected"""
        return server_name in self.sessions
```

**Files to Create:**
- `cmbagent/mcp/client_manager.py`

**Verification:**
- Can connect to MCP servers
- Tools discovered automatically
- Can call tools successfully
- Error handling graceful
- Disconnect cleanup works

### Task 4: Integrate MCP Tools with AG2 Agents
**Objective:** Make external tools available to CMBAgent agents

**Implementation:**

```python
from cmbagent.mcp.client_manager import MCPClientManager
from autogen import ConversableAgent
import asyncio

class MCPToolIntegration:
    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp_manager = mcp_manager

    def register_tools_with_agent(self, agent: ConversableAgent):
        """
        Register all MCP tools with an AG2 agent

        Creates wrapper functions for each external tool
        """
        all_tools = self.mcp_manager.get_all_tools()

        for tool in all_tools:
            # Create wrapper function for this tool
            tool_func = self._create_tool_wrapper(
                tool['server_name'],
                tool['name'],
                tool.get('description', ''),
                tool.get('inputSchema', {})
            )

            # Register with agent
            agent.register_for_llm(
                name=f"{tool['server_name']}_{tool['name']}",
                description=tool.get('description', '')
            )(tool_func)

    def _create_tool_wrapper(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        input_schema: dict
    ):
        """
        Create a wrapper function for an external MCP tool

        This wrapper will be called by the agent and will forward
        the call to the external MCP server
        """
        async def tool_wrapper(**kwargs):
            """
            Wrapper for external MCP tool
            """
            try:
                result = await self.mcp_manager.call_tool(
                    server_name=server_name,
                    tool_name=tool_name,
                    arguments=kwargs
                )

                if result['status'] == 'success':
                    return result['result']
                else:
                    return f"Error: {result['error']}"

            except Exception as e:
                return f"Tool execution failed: {str(e)}"

        # Set function metadata for AG2
        tool_wrapper.__name__ = f"{server_name}_{tool_name}"
        tool_wrapper.__doc__ = description

        return tool_wrapper

    def get_tool_descriptions(self) -> str:
        """Get formatted list of all available external tools"""
        all_tools = self.mcp_manager.get_all_tools()

        descriptions = []
        for tool in all_tools:
            desc = f"- {tool['name']} ({tool['server_name']}): {tool.get('description', 'No description')}"
            descriptions.append(desc)

        return "\n".join(descriptions)
```

**Files to Create:**
- `cmbagent/mcp/tool_integration.py`

**Verification:**
- Tools registered with agents
- Agents can call external tools
- Tool wrappers handle errors gracefully
- Tool descriptions accurate

### Task 5: Update CMBAgent to Use MCP Client
**Objective:** Initialize MCP client when CMBAgent starts

**Files to Modify:**
- `cmbagent/cmbagent.py`

**Changes:**

```python
class CMBAgent:
    def __init__(self, ...):
        # Existing initialization
        ...

        # NEW: Initialize MCP client
        self.mcp_client_manager = None
        self.mcp_enabled = os.getenv("CMBAGENT_ENABLE_MCP_CLIENT", "false").lower() == "true"

        if self.mcp_enabled:
            self._initialize_mcp_client()

    def _initialize_mcp_client(self):
        """Initialize MCP client and connect to external servers"""
        from cmbagent.mcp.client_manager import MCPClientManager
        from cmbagent.mcp.tool_integration import MCPToolIntegration

        try:
            logger.info("Initializing MCP client...")

            # Create MCP client manager
            self.mcp_client_manager = MCPClientManager()

            # Connect to all enabled servers (synchronous wrapper)
            asyncio.run(self.mcp_client_manager.connect_all())

            # Create tool integration helper
            self.mcp_tool_integration = MCPToolIntegration(self.mcp_client_manager)

            logger.info(
                f"MCP client initialized. Connected to {len(self.mcp_client_manager.sessions)} servers."
            )

        except Exception as e:
            logger.warning(f"Failed to initialize MCP client: {e}")
            self.mcp_enabled = False

    def _create_agent_with_mcp_tools(self, agent_name, agent_config):
        """Create agent and register MCP tools"""
        # Create agent normally
        agent = self._create_agent(agent_name, agent_config)

        # Register MCP tools if enabled
        if self.mcp_enabled and self.mcp_tool_integration:
            self.mcp_tool_integration.register_tools_with_agent(agent)

            logger.info(f"Registered MCP tools with agent {agent_name}")

        return agent

    def __del__(self):
        """Cleanup: disconnect from MCP servers"""
        if self.mcp_client_manager:
            asyncio.run(self.mcp_client_manager.disconnect_all())
```

**Verification:**
- MCP client initializes when enabled
- External tools available to agents
- Agents can use external tools in workflows
- Cleanup happens on shutdown

### Task 6: Add MCP Tool Execution Tracking
**Objective:** Track external tool usage in database

**Database Schema Extension:**

```sql
-- Add new table for external tool calls
CREATE TABLE external_tool_calls (
    id SERIAL PRIMARY KEY,
    run_id UUID NOT NULL,
    step_id UUID,
    session_id UUID NOT NULL,
    server_name VARCHAR(100),
    tool_name VARCHAR(200),
    arguments JSONB,
    result JSONB,
    status VARCHAR(50),  -- success, failed, timeout
    cost_usd NUMERIC(10, 6),  -- If tool has API costs
    execution_time_ms INTEGER,
    error_message TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (run_id) REFERENCES workflow_runs(id),
    FOREIGN KEY (step_id) REFERENCES workflow_steps(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX idx_external_tool_calls_run ON external_tool_calls(run_id);
CREATE INDEX idx_external_tool_calls_session ON external_tool_calls(session_id);
```

**Update Models:**

```python
# In cmbagent/database/models.py
class ExternalToolCall(Base):
    __tablename__ = "external_tool_calls"

    id = Column(Integer, primary_key=True)
    run_id = Column(UUID, ForeignKey("workflow_runs.id"))
    step_id = Column(UUID, ForeignKey("workflow_steps.id"), nullable=True)
    session_id = Column(UUID, ForeignKey("sessions.id"))
    server_name = Column(String(100))
    tool_name = Column(String(200))
    arguments = Column(JSONB)
    result = Column(JSONB)
    status = Column(String(50))
    cost_usd = Column(Numeric(10, 6))
    execution_time_ms = Column(Integer)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    run = relationship("WorkflowRun", back_populates="external_tool_calls")
    step = relationship("WorkflowStep", back_populates="external_tool_calls")
```

**Track Tool Calls:**

```python
# In tool_wrapper function
async def tool_wrapper(**kwargs):
    start_time = time.time()

    try:
        result = await self.mcp_manager.call_tool(
            server_name=server_name,
            tool_name=tool_name,
            arguments=kwargs
        )

        execution_time = (time.time() - start_time) * 1000  # ms

        # Record in database
        self._record_tool_call(
            server_name=server_name,
            tool_name=tool_name,
            arguments=kwargs,
            result=result,
            status=result['status'],
            execution_time_ms=execution_time
        )

        return result['result']

    except Exception as e:
        execution_time = (time.time() - start_time) * 1000

        # Record failure
        self._record_tool_call(
            server_name=server_name,
            tool_name=tool_name,
            arguments=kwargs,
            result=None,
            status="failed",
            execution_time_ms=execution_time,
            error_message=str(e)
        )

        raise
```

**Files to Modify:**
- `cmbagent/database/models.py`
- `cmbagent/mcp/tool_integration.py`

**Verification:**
- External tool calls recorded in database
- Can query tool usage statistics
- Execution times tracked
- Errors logged

### Task 7: Add Cost Attribution for External APIs
**Objective:** Track costs for paid external services

**Implementation:**

```python
# In cmbagent/mcp/cost_tracker.py
class ExternalToolCostTracker:
    """Track costs for external tool usage"""

    # Cost per call for various services
    TOOL_COSTS = {
        "brave_search": {
            "search": 0.001,  # $0.001 per search
        },
        "github": {
            # GitHub API is free but has rate limits
            "*": 0.0
        },
        "puppeteer": {
            "*": 0.0  # Self-hosted, no cost
        }
    }

    @staticmethod
    def get_tool_cost(server_name: str, tool_name: str) -> float:
        """Get cost for a tool call"""
        if server_name not in ExternalToolCostTracker.TOOL_COSTS:
            return 0.0

        server_costs = ExternalToolCostTracker.TOOL_COSTS[server_name]

        # Check for specific tool cost
        if tool_name in server_costs:
            return server_costs[tool_name]

        # Check for wildcard cost
        if "*" in server_costs:
            return server_costs["*"]

        return 0.0

    @staticmethod
    def calculate_session_external_costs(session_id: str) -> float:
        """Calculate total external tool costs for a session"""
        from cmbagent.database import get_db_session
        from cmbagent.database.models import ExternalToolCall

        db = get_db_session()

        tool_calls = db.query(ExternalToolCall).filter(
            ExternalToolCall.session_id == session_id
        ).all()

        total_cost = sum(
            call.cost_usd or 0.0
            for call in tool_calls
        )

        return total_cost
```

**Files to Create:**
- `cmbagent/mcp/cost_tracker.py`

**Verification:**
- Tool costs calculated correctly
- Total session cost includes external tools
- Cost tracking integrated with existing cost system

### Task 8: Add CLI Commands for MCP Client
**Objective:** Manage MCP client from command line

**Files to Modify:**
- `cmbagent/cli.py`

**Add Commands:**

```python
@cli.group()
def mcp():
    """MCP client management commands"""
    pass

@mcp.command()
def list_servers():
    """List all configured MCP servers"""
    from cmbagent.mcp.client_manager import MCPClientManager

    manager = MCPClientManager()

    click.echo("Configured MCP Servers:\n")

    for server_name, config in manager.config['mcp_servers'].items():
        enabled = "✓" if config['enabled'] else "✗"
        click.echo(f"{enabled} {server_name}: {config['description']}")

@mcp.command()
@click.argument("server_name")
def test_server(server_name):
    """Test connection to an MCP server"""
    from cmbagent.mcp.client_manager import MCPClientManager

    manager = MCPClientManager()

    async def test():
        server_config = manager.config['mcp_servers'].get(server_name)

        if not server_config:
            click.echo(f"Server {server_name} not found in config")
            return

        await manager.connect_server(server_name, server_config)

        if manager.is_server_available(server_name):
            click.echo(f"✓ Connected to {server_name}")

            tools = manager.get_tools_by_server(server_name)
            click.echo(f"  {len(tools)} tools available")

            await manager.disconnect_server(server_name)
        else:
            click.echo(f"✗ Failed to connect to {server_name}")

    asyncio.run(test())

@mcp.command()
def list_tools():
    """List all available external tools"""
    from cmbagent.mcp.client_manager import MCPClientManager

    manager = MCPClientManager()

    async def list_all():
        await manager.connect_all()

        all_tools = manager.get_all_tools()

        click.echo(f"Available External Tools ({len(all_tools)} total):\n")

        by_server = {}
        for tool in all_tools:
            server = tool['server_name']
            if server not in by_server:
                by_server[server] = []
            by_server[server].append(tool)

        for server_name, tools in by_server.items():
            click.echo(f"{server_name} ({len(tools)} tools):")
            for tool in tools:
                click.echo(f"  - {tool['name']}: {tool.get('description', '')[:60]}")
            click.echo()

        await manager.disconnect_all()

    asyncio.run(list_all())
```

**Verification:**
- `cmbagent mcp list-servers` shows all servers
- `cmbagent mcp test-server <name>` tests connection
- `cmbagent mcp list-tools` shows all available tools

### Task 9: Add Documentation and Examples
**Objective:** Document MCP client usage

**Files to Create:**
- `docs/MCP_CLIENT_GUIDE.md`
- `examples/mcp_client_usage.py`

**Example Usage:**

```python
# examples/mcp_client_usage.py
from cmbagent import CMBAgent
import os

# Enable MCP client
os.environ['CMBAGENT_ENABLE_MCP_CLIENT'] = 'true'

# Create agent with external tools
agent = CMBAgent()

# Use filesystem tool via MCP
result = agent.one_shot(
    task="""
    Use the filesystem tool to:
    1. Read the file /path/to/data.csv
    2. Analyze the data
    3. Write a summary to /path/to/summary.txt
    """,
    agent="engineer",
    model="gpt-4o"
)

# Use GitHub tool via MCP
result = agent.one_shot(
    task="""
    Use the GitHub tool to:
    1. List all issues in repository owner/repo
    2. Filter for issues with label "bug"
    3. Create a summary report
    """,
    agent="engineer",
    model="gpt-4o"
)

# Use web search tool via MCP
result = agent.one_shot(
    task="""
    Use the web search tool to:
    1. Search for "CMB power spectrum analysis methods"
    2. Summarize the top 5 results
    3. Extract key papers and techniques
    """,
    agent="researcher",
    model="gpt-4o"
)
```

**Verification:**
- Documentation complete and clear
- Examples run successfully
- Use cases well explained

## Files to Create (Summary)

### New Files
```
cmbagent/mcp/
├── client_config.yaml
├── client_manager.py
├── tool_integration.py
└── cost_tracker.py

examples/
└── mcp_client_usage.py

docs/
└── MCP_CLIENT_GUIDE.md
```

### Modified Files
- `pyproject.toml` - Add MCP client dependencies
- `cmbagent/cmbagent.py` - Initialize MCP client
- `cmbagent/database/models.py` - Add external_tool_calls table
- `cmbagent/cli.py` - Add MCP client commands

## Verification Criteria

### Must Pass
- [ ] MCP client connects to external servers
- [ ] Tools discovered automatically
- [ ] Agents can call external tools
- [ ] Tool execution tracked in database
- [ ] Errors handled gracefully
- [ ] Configuration via YAML file
- [ ] Environment variables substituted correctly
- [ ] CLI commands functional
- [ ] Cleanup on shutdown

### Should Pass
- [ ] Multiple MCP servers supported simultaneously
- [ ] Cost attribution for paid services
- [ ] Fallback when external tools unavailable
- [ ] Tool descriptions clear and helpful
- [ ] Examples demonstrate common use cases

### Integration Tests
- [ ] Agent uses filesystem tool successfully
- [ ] Agent uses GitHub tool successfully
- [ ] Agent combines external tools with internal capabilities
- [ ] Error in external tool doesn't crash workflow
- [ ] Multiple external tool calls in single workflow

## Testing Checklist

### Unit Tests
```python
# Test MCP client manager
@pytest.mark.asyncio
async def test_mcp_client_manager():
    manager = MCPClientManager()

    # Test connection
    await manager.connect_all()

    assert len(manager.sessions) > 0

    # Test tool discovery
    tools = manager.get_all_tools()

    assert len(tools) > 0

    # Test tool call
    if manager.is_server_available('filesystem'):
        result = await manager.call_tool(
            'filesystem',
            'list_directory',
            {'path': '/tmp'}
        )

        assert result['status'] == 'success'

    # Cleanup
    await manager.disconnect_all()

# Test tool integration
def test_tool_integration():
    from cmbagent.mcp.client_manager import MCPClientManager
    from cmbagent.mcp.tool_integration import MCPToolIntegration
    from autogen import ConversableAgent

    manager = MCPClientManager()
    asyncio.run(manager.connect_all())

    integration = MCPToolIntegration(manager)

    # Create test agent
    agent = ConversableAgent(name="test", llm_config={"model": "gpt-4"})

    # Register tools
    integration.register_tools_with_agent(agent)

    # Verify tools registered
    assert len(agent.function_map) > 0

    asyncio.run(manager.disconnect_all())
```

### Integration Tests
```python
# Test full workflow with external tools
def test_workflow_with_external_tools():
    import os
    os.environ['CMBAGENT_ENABLE_MCP_CLIENT'] = 'true'

    agent = CMBAgent()

    # Task requiring external filesystem access
    result = agent.one_shot(
        task="Read /tmp/test.txt and count words",
        agent="engineer"
    )

    assert result.status == "completed"

    # Verify external tool call recorded
    from cmbagent.database.models import ExternalToolCall

    tool_calls = agent.repo.db.query(ExternalToolCall).filter(
        ExternalToolCall.run_id == result.run_id
    ).all()

    assert len(tool_calls) > 0
```

## Common Issues and Solutions

### Issue 1: MCP Server Connection Fails
**Symptom:** Cannot connect to external MCP server
**Solution:** Check command path, verify npx installed, check environment variables

### Issue 2: Tools Not Registered with Agent
**Symptom:** Agent doesn't see external tools
**Solution:** Verify CMBAGENT_ENABLE_MCP_CLIENT=true, check tool discovery logs

### Issue 3: External Tool Call Timeout
**Symptom:** Tool call hangs indefinitely
**Solution:** Increase timeout in config, check MCP server responsiveness

### Issue 4: Cost Not Tracked
**Symptom:** External tool costs not appearing
**Solution:** Add tool to cost tracker, verify cost_usd field populated

### Issue 5: Environment Variables Not Substituted
**Symptom:** ${VAR} appears literally in config
**Solution:** Set environment variable before starting, check substitution logic

## Rollback Procedure

If MCP client causes issues:

1. **Disable MCP client:**
   ```bash
   export CMBAGENT_ENABLE_MCP_CLIENT=false
   ```

2. **Comment out MCP server configs:**
   ```yaml
   # In client_config.yaml, set all enabled: false
   ```

3. **Keep all other functionality** - MCP client is optional feature

4. **Agents work without external tools** - Graceful degradation

## Post-Stage Actions

### Documentation
- Create comprehensive MCP client guide
- Document each supported MCP server
- Add troubleshooting section
- Create video tutorial

### Update Progress
- Mark Stage 11 complete in `PROGRESS.md`
- Document external tools integrated
- Note any limitations

### Prepare for Next Phase
- MCP integration complete (server + client)
- Core enhancement phases complete
- Ready for observability and policy stages

## Success Criteria

Stage 11 is complete when:
1. MCP client connects to external servers successfully
2. External tools available to CMBAgent agents
3. Agents can call and use external tools in workflows
4. Tool execution tracked in database
5. Configuration flexible and environment-aware
6. CLI commands functional for management
7. Documentation complete and clear
8. Verification checklist 100% complete

## Estimated Time Breakdown

- MCP client dependencies and config: 6 min
- Client manager implementation: 12 min
- Tool integration with AG2: 10 min
- CMBAgent integration: 6 min
- Database tracking: 7 min
- Cost attribution: 5 min
- CLI commands: 5 min
- Testing and verification: 12 min
- Documentation and examples: 7 min

**Total: 40-50 minutes**

## Next Stage

Once Stage 11 is verified complete, proceed to:
**Stage 12: Real-Time WebSocket Events** (if not already implemented in earlier stages)

Or continue with remaining stages in the implementation plan.

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
