# Stage 10: MCP Server Interface

**Phase:** 3 - Integration
**Estimated Time:** 45-55 minutes
**Dependencies:** Stages 1-9 (All core functionality) must be complete
**Risk Level:** Medium

## Objectives

1. Implement Model Context Protocol (MCP) server exposing CMBAgent
2. Create MCP tools for all 50+ specialized agents
3. Enable external AI assistants (Claude Desktop, etc.) to use CMBAgent
4. Implement streaming responses for long-running operations
5. Add resource management and rate limiting for MCP access
6. Create comprehensive tool schemas and documentation
7. Support both stdio and SSE transport protocols

## Current State Analysis

### What We Have
- 50+ specialized agents (engineer, planner, researcher, RAG agents, etc.)
- `cmbagent.one_shot()` and `planning_and_control()` APIs
- Database-backed execution with state tracking
- WebSocket-based real-time updates
- Work directory structure with outputs

### What We Need
- MCP server implementation using official MCP SDK
- Tool definitions for each agent/capability
- Schema definitions for inputs/outputs
- Transport layer (stdio for Claude Desktop)
- Authentication and authorization
- Rate limiting and resource quotas
- Streaming support for long-running tasks
- Error handling and validation

## Pre-Stage Verification

### Check Prerequisites
1. Stages 1-9 complete and verified
2. All core CMBAgent functionality working
3. Database operations stable
4. Agent execution reliable
5. Python MCP SDK installed

### Expected State
- CMBAgent agents execute successfully
- Database queries work
- Ready to expose functionality via MCP
- MCP SDK available in environment

## Implementation Tasks

### Task 1: Install MCP SDK and Dependencies
**Objective:** Add MCP server capabilities to project

**Actions:**
- Update `pyproject.toml` dependencies section
- Add: `mcp>=1.0.0`, `pydantic>=2.0` (for schemas)
- Install dependencies: `pip install -e .`

**Files to Modify:**
- `pyproject.toml` (dependencies section)

**Verification:**
- Dependencies install without conflicts
- Can import MCP SDK: `from mcp.server import Server`
- MCP version >= 1.0.0

### Task 2: Design MCP Tool Schema
**Objective:** Define tools exposing CMBAgent capabilities

**Tool Categories:**

**1. Core Execution Tools:**
- `cmbagent_one_shot` - Execute single-shot task with specified agent
- `cmbagent_planning_and_control` - Multi-step planning and execution
- `cmbagent_deep_research` - Deep research workflow

**2. Specialized Agent Tools:**
- `cmbagent_engineer` - Software engineering tasks
- `cmbagent_researcher` - Scientific research tasks
- `cmbagent_planner` - Task planning and decomposition
- `cmbagent_control` - Execution control and orchestration
- `cmbagent_executor` - Direct task execution

**3. RAG Agent Tools:**
- `cmbagent_query_camb_docs` - Query CAMB documentation
- `cmbagent_query_class_docs` - Query CLASS documentation
- `cmbagent_query_cobaya_docs` - Query Cobaya documentation
- `cmbagent_query_healpy_docs` - Query HEALPix documentation
- `cmbagent_query_literature` - Query scientific literature

**4. Utility Tools:**
- `cmbagent_list_agents` - List all available agents
- `cmbagent_get_run_status` - Check workflow run status
- `cmbagent_get_run_outputs` - Retrieve workflow outputs
- `cmbagent_list_runs` - List all workflow runs in session
- `cmbagent_resume_run` - Resume paused workflow

**Tool Schema Example:**

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class OnehotInput(BaseModel):
    """Input schema for one-shot execution"""
    task: str = Field(
        description="The task description to execute"
    )
    agent: str = Field(
        default="engineer",
        description="Agent to use: engineer, researcher, planner, control, executor"
    )
    model: str = Field(
        default="gpt-4o",
        description="LLM model to use"
    )
    work_dir: Optional[str] = Field(
        default=None,
        description="Work directory for outputs (auto-generated if not provided)"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for isolation (auto-generated if not provided)"
    )

class OneshotOutput(BaseModel):
    """Output schema for one-shot execution"""
    run_id: str = Field(description="Unique workflow run ID")
    status: str = Field(description="Execution status: completed, failed, paused")
    outputs: dict = Field(description="Execution outputs and results")
    work_dir: str = Field(description="Path to work directory with artifacts")
    cost_usd: float = Field(description="Total cost in USD")
    execution_time_seconds: float = Field(description="Total execution time")
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if execution failed"
    )
```

**Files to Create:**
- `cmbagent/mcp/schemas.py`

**Verification:**
- All tool schemas defined
- Pydantic validation works
- Schemas include helpful descriptions
- Input/output types correct

### Task 3: Implement MCP Server Core
**Objective:** Create MCP server exposing CMBAgent tools

**Implementation:**

```python
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from cmbagent import CMBAgent
from cmbagent.mcp.schemas import *
import logging

logger = logging.getLogger(__name__)

class CMBAgentMCPServer:
    def __init__(self):
        self.server = Server("cmbagent-server")
        self.agent_instances = {}  # session_id -> CMBAgent

        # Register tools
        self._register_tools()

    def _register_tools(self):
        """Register all CMBAgent tools with MCP server"""

        # Core execution tool
        @self.server.call_tool()
        async def cmbagent_one_shot(
            task: str,
            agent: str = "engineer",
            model: str = "gpt-4o",
            work_dir: str = None,
            session_id: str = None
        ) -> list[TextContent]:
            """
            Execute a single-shot task using CMBAgent

            Args:
                task: Task description to execute
                agent: Agent to use (engineer, researcher, planner, control, executor)
                model: LLM model to use
                work_dir: Work directory path (auto-generated if not provided)
                session_id: Session ID for isolation (auto-generated if not provided)

            Returns:
                Execution results including outputs, status, cost, and artifacts
            """
            try:
                # Get or create CMBAgent instance
                cmbagent = self._get_agent_instance(session_id)

                logger.info(f"Executing one-shot task with agent={agent}, model={model}")

                # Execute task
                result = cmbagent.one_shot(
                    task=task,
                    agent=agent,
                    model=model,
                    work_dir=work_dir
                )

                # Format response
                response = {
                    "run_id": result.run_id,
                    "status": result.status,
                    "outputs": result.outputs,
                    "work_dir": result.work_dir,
                    "cost_usd": result.cost,
                    "execution_time_seconds": result.execution_time,
                    "summary": result.summary
                }

                return [
                    TextContent(
                        type="text",
                        text=f"Task completed successfully!\n\n"
                             f"Run ID: {result.run_id}\n"
                             f"Status: {result.status}\n"
                             f"Cost: ${result.cost:.4f}\n"
                             f"Time: {result.execution_time:.2f}s\n\n"
                             f"Outputs:\n{json.dumps(result.outputs, indent=2)}"
                    )
                ]

            except Exception as e:
                logger.error(f"Error executing one-shot: {e}")
                return [
                    TextContent(
                        type="text",
                        text=f"Error: {str(e)}"
                    )
                ]

        # Planning and control tool
        @self.server.call_tool()
        async def cmbagent_planning_and_control(
            task: str,
            agent: str = "engineer",
            model: str = "gpt-4o",
            work_dir: str = None,
            session_id: str = None,
            approval_mode: str = "none"
        ) -> list[TextContent]:
            """
            Execute multi-step planning and control workflow

            Args:
                task: Task description to execute
                agent: Primary agent for execution
                model: LLM model to use
                work_dir: Work directory path
                session_id: Session ID for isolation
                approval_mode: Approval mode (none, after_planning, before_each_step)

            Returns:
                Execution results with plan, step-by-step outputs, and artifacts
            """
            try:
                cmbagent = self._get_agent_instance(session_id)

                logger.info(f"Executing planning and control workflow")

                # Execute workflow
                result = cmbagent.planning_and_control(
                    task=task,
                    agent=agent,
                    model=model,
                    work_dir=work_dir,
                    approval_mode=approval_mode
                )

                # Format response with plan and steps
                plan_text = json.dumps(result.plan, indent=2)
                steps_text = "\n\n".join([
                    f"Step {i+1}: {step['description']}\n"
                    f"  Status: {step['status']}\n"
                    f"  Output: {step['output'][:200]}..."
                    for i, step in enumerate(result.steps)
                ])

                return [
                    TextContent(
                        type="text",
                        text=f"Workflow completed successfully!\n\n"
                             f"Run ID: {result.run_id}\n"
                             f"Status: {result.status}\n\n"
                             f"Plan:\n{plan_text}\n\n"
                             f"Execution Steps:\n{steps_text}\n\n"
                             f"Total Cost: ${result.cost:.4f}\n"
                             f"Total Time: {result.execution_time:.2f}s"
                    )
                ]

            except Exception as e:
                logger.error(f"Error executing planning and control: {e}")
                return [
                    TextContent(
                        type="text",
                        text=f"Error: {str(e)}"
                    )
                ]

        # RAG query tool example
        @self.server.call_tool()
        async def cmbagent_query_camb_docs(
            query: str,
            model: str = "gpt-4o",
            session_id: str = None
        ) -> list[TextContent]:
            """
            Query CAMB documentation using RAG agent

            Args:
                query: Question or query about CAMB
                model: LLM model to use
                session_id: Session ID for isolation

            Returns:
                Answer with relevant documentation citations
            """
            try:
                cmbagent = self._get_agent_instance(session_id)

                result = cmbagent.query_rag_agent(
                    agent_name="camb_docs",
                    query=query,
                    model=model
                )

                return [
                    TextContent(
                        type="text",
                        text=f"CAMB Documentation Query Result:\n\n"
                             f"Query: {query}\n\n"
                             f"Answer:\n{result.answer}\n\n"
                             f"Sources:\n{json.dumps(result.sources, indent=2)}"
                    )
                ]

            except Exception as e:
                logger.error(f"Error querying CAMB docs: {e}")
                return [
                    TextContent(
                        type="text",
                        text=f"Error: {str(e)}"
                    )
                ]

        # List agents tool
        @self.server.call_tool()
        async def cmbagent_list_agents() -> list[TextContent]:
            """
            List all available CMBAgent agents

            Returns:
                List of agent names with descriptions
            """
            from cmbagent.agents import list_all_agents

            agents = list_all_agents()

            agent_list = "\n".join([
                f"- {agent['name']}: {agent['description']}"
                for agent in agents
            ])

            return [
                TextContent(
                    type="text",
                    text=f"Available CMBAgent Agents ({len(agents)} total):\n\n"
                         f"{agent_list}"
                )
            ]

        # Get run status tool
        @self.server.call_tool()
        async def cmbagent_get_run_status(
            run_id: str,
            session_id: str = None
        ) -> list[TextContent]:
            """
            Get status of a workflow run

            Args:
                run_id: Workflow run ID
                session_id: Session ID for isolation

            Returns:
                Run status, progress, and current step
            """
            try:
                cmbagent = self._get_agent_instance(session_id)

                status = cmbagent.get_run_status(run_id)

                return [
                    TextContent(
                        type="text",
                        text=f"Run Status:\n\n"
                             f"Run ID: {run_id}\n"
                             f"Status: {status['status']}\n"
                             f"Progress: {status['progress_percentage']}%\n"
                             f"Current Step: {status['current_step']}\n"
                             f"Started: {status['started_at']}\n"
                             f"Cost So Far: ${status['cost_usd']:.4f}"
                    )
                ]

            except Exception as e:
                return [
                    TextContent(
                        type="text",
                        text=f"Error: {str(e)}"
                    )
                ]

        logger.info("All MCP tools registered")

    def _get_agent_instance(self, session_id: str = None) -> CMBAgent:
        """Get or create CMBAgent instance for session"""
        if session_id is None:
            session_id = "default"

        if session_id not in self.agent_instances:
            self.agent_instances[session_id] = CMBAgent(session_id=session_id)

        return self.agent_instances[session_id]

    async def run(self):
        """Run MCP server with stdio transport"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )

# Entry point
async def main():
    server = CMBAgentMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
```

**Files to Create:**
- `cmbagent/mcp/server.py`

**Verification:**
- MCP server starts without errors
- Tools registered correctly
- Stdio transport works
- Can receive and process requests

### Task 4: Add Tool Discovery and Listing
**Objective:** Enable MCP clients to discover available tools

**Implementation:**

```python
# Add to CMBAgentMCPServer class

@self.server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools"""
    return [
        Tool(
            name="cmbagent_one_shot",
            description="Execute a single-shot task using CMBAgent with specified agent and model",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task description to execute"
                    },
                    "agent": {
                        "type": "string",
                        "enum": ["engineer", "researcher", "planner", "control", "executor"],
                        "default": "engineer",
                        "description": "Agent to use for execution"
                    },
                    "model": {
                        "type": "string",
                        "default": "gpt-4o",
                        "description": "LLM model to use"
                    },
                    "work_dir": {
                        "type": "string",
                        "description": "Work directory path (optional)"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session ID for isolation (optional)"
                    }
                },
                "required": ["task"]
            }
        ),
        Tool(
            name="cmbagent_planning_and_control",
            description="Execute multi-step planning and control workflow with automatic task decomposition",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Complex task description to plan and execute"
                    },
                    "agent": {
                        "type": "string",
                        "enum": ["engineer", "researcher", "planner", "control", "executor"],
                        "default": "engineer"
                    },
                    "model": {
                        "type": "string",
                        "default": "gpt-4o"
                    },
                    "approval_mode": {
                        "type": "string",
                        "enum": ["none", "after_planning", "before_each_step"],
                        "default": "none",
                        "description": "When to request human approval"
                    }
                },
                "required": ["task"]
            }
        ),
        Tool(
            name="cmbagent_query_camb_docs",
            description="Query CAMB cosmology code documentation using RAG",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Question about CAMB"
                    },
                    "model": {
                        "type": "string",
                        "default": "gpt-4o"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="cmbagent_list_agents",
            description="List all available CMBAgent specialized agents",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="cmbagent_get_run_status",
            description="Get status of a workflow run",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Workflow run ID"
                    }
                },
                "required": ["run_id"]
            }
        ),
        # Add all other tools...
    ]
```

**Verification:**
- Tool listing returns all tools
- Schemas valid JSON Schema
- Descriptions helpful and accurate
- Required fields properly marked

### Task 5: Add Resource Management
**Objective:** Prevent MCP server from resource exhaustion

**Implementation:**

```python
from asyncio import Semaphore
import time

class ResourceManager:
    def __init__(self, max_concurrent_tasks=5, rate_limit_per_minute=30):
        self.max_concurrent = max_concurrent_tasks
        self.semaphore = Semaphore(max_concurrent_tasks)
        self.rate_limit = rate_limit_per_minute
        self.request_timestamps = []

    async def acquire(self):
        """Acquire resource slot with rate limiting"""
        # Check rate limit
        now = time.time()
        minute_ago = now - 60

        # Remove old timestamps
        self.request_timestamps = [
            ts for ts in self.request_timestamps
            if ts > minute_ago
        ]

        # Check if rate limit exceeded
        if len(self.request_timestamps) >= self.rate_limit:
            raise RateLimitExceededError(
                f"Rate limit exceeded: {self.rate_limit} requests per minute"
            )

        # Acquire semaphore
        await self.semaphore.acquire()

        # Record request
        self.request_timestamps.append(now)

    def release(self):
        """Release resource slot"""
        self.semaphore.release()

# Add to CMBAgentMCPServer.__init__
self.resource_manager = ResourceManager()

# Wrap tool calls with resource management
async def _execute_with_resource_management(self, func, *args, **kwargs):
    """Execute function with resource management"""
    await self.resource_manager.acquire()
    try:
        result = await func(*args, **kwargs)
        return result
    finally:
        self.resource_manager.release()
```

**Files to Modify:**
- `cmbagent/mcp/server.py`

**Verification:**
- Rate limiting enforced
- Concurrent execution limited
- Resources released properly
- Error messages helpful

### Task 6: Add Streaming Support for Long Operations
**Objective:** Stream progress updates for long-running workflows

**Implementation:**

```python
@self.server.call_tool()
async def cmbagent_planning_and_control_streaming(
    task: str,
    agent: str = "engineer",
    model: str = "gpt-4o",
    session_id: str = None
) -> list[TextContent]:
    """
    Execute planning and control with streaming updates

    Sends progress updates as execution proceeds
    """
    try:
        cmbagent = self._get_agent_instance(session_id)

        # Create progress callback
        progress_messages = []

        def progress_callback(event):
            # Collect progress events
            progress_messages.append(
                f"[{event['timestamp']}] {event['type']}: {event['message']}"
            )

        # Execute with progress callback
        result = cmbagent.planning_and_control(
            task=task,
            agent=agent,
            model=model,
            progress_callback=progress_callback
        )

        # Return all progress messages plus final result
        progress_text = "\n".join(progress_messages)

        return [
            TextContent(
                type="text",
                text=f"Workflow Progress:\n\n{progress_text}\n\n"
                     f"Final Result:\n"
                     f"Status: {result.status}\n"
                     f"Cost: ${result.cost:.4f}"
            )
        ]

    except Exception as e:
        return [
            TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )
        ]
```

**Verification:**
- Progress updates streamed during execution
- Final result includes complete history
- Long operations don't timeout

### Task 7: Create MCP Server Configuration
**Objective:** Configure server for different environments

**Implementation:**

```python
# cmbagent/mcp/config.py
import os
from pydantic import BaseModel

class MCPServerConfig(BaseModel):
    # Server settings
    server_name: str = "cmbagent-server"
    server_version: str = "1.0.0"

    # Resource limits
    max_concurrent_tasks: int = 5
    rate_limit_per_minute: int = 30
    max_execution_time_seconds: int = 3600  # 1 hour

    # Session settings
    default_model: str = "gpt-4o"
    auto_cleanup_sessions: bool = True
    session_timeout_hours: int = 24

    # Logging
    log_level: str = "INFO"
    log_file: str = "/tmp/cmbagent_mcp.log"

    # Transport
    transport: str = "stdio"  # stdio or sse

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        return cls(
            max_concurrent_tasks=int(os.getenv("MCP_MAX_CONCURRENT", "5")),
            rate_limit_per_minute=int(os.getenv("MCP_RATE_LIMIT", "30")),
            log_level=os.getenv("MCP_LOG_LEVEL", "INFO"),
            transport=os.getenv("MCP_TRANSPORT", "stdio")
        )
```

**Files to Create:**
- `cmbagent/mcp/config.py`

**Verification:**
- Configuration loaded from environment
- Defaults sensible
- Override mechanism works

### Task 8: Add Claude Desktop Configuration
**Objective:** Enable CMBAgent as MCP server in Claude Desktop

**Create Configuration File:**

```json
// claude_desktop_config.json (for user's Claude Desktop)
{
  "mcpServers": {
    "cmbagent": {
      "command": "python",
      "args": ["-m", "cmbagent.mcp.server"],
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "CMBAGENT_WORK_DIR": "/path/to/work/dir",
        "MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Create Installation Script:**

```bash
#!/bin/bash
# install_mcp_server.sh

echo "Installing CMBAgent as MCP Server for Claude Desktop..."

# Get Claude Desktop config directory
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CONFIG_DIR="$HOME/.config/Claude"
else
    echo "Unsupported OS"
    exit 1
fi

# Create config if doesn't exist
mkdir -p "$CONFIG_DIR"

# Add CMBAgent to MCP servers
cat > "$CONFIG_DIR/claude_desktop_config.json" <<EOF
{
  "mcpServers": {
    "cmbagent": {
      "command": "python",
      "args": ["-m", "cmbagent.mcp.server"],
      "env": {
        "OPENAI_API_KEY": "${OPENAI_API_KEY}",
        "CMBAGENT_WORK_DIR": "${HOME}/cmbagent_work"
      }
    }
  }
}
EOF

echo "CMBAgent MCP server installed!"
echo "Restart Claude Desktop to activate."
```

**Files to Create:**
- `scripts/install_mcp_server.sh`
- `docs/MCP_SERVER_SETUP.md`

**Verification:**
- Claude Desktop config valid
- Server starts from Claude Desktop
- Tools appear in Claude Desktop UI
- Can execute tools successfully

### Task 9: Add CLI Command for MCP Server
**Objective:** Easy way to start MCP server from command line

**Files to Modify:**
- `cmbagent/cli.py`

**Add Command:**

```python
@cli.command()
@click.option("--transport", default="stdio", help="Transport protocol: stdio or sse")
@click.option("--port", default=8080, help="Port for SSE transport")
def mcp_server(transport, port):
    """Start CMBAgent as MCP server"""
    from cmbagent.mcp.server import main

    click.echo(f"Starting CMBAgent MCP server (transport: {transport})")

    if transport == "stdio":
        asyncio.run(main())
    elif transport == "sse":
        click.echo(f"Starting SSE server on port {port}")
        # SSE server implementation
        asyncio.run(main_sse(port))
    else:
        click.echo(f"Unknown transport: {transport}")
```

**Verification:**
- `cmbagent mcp-server` starts server
- Can communicate with server via stdio
- Ctrl+C gracefully shuts down

## Files to Create (Summary)

### New Files
```
cmbagent/mcp/
├── __init__.py
├── server.py
├── schemas.py
├── config.py
└── resource_manager.py

scripts/
└── install_mcp_server.sh

docs/
└── MCP_SERVER_SETUP.md
```

### Modified Files
- `pyproject.toml` - Add MCP dependencies
- `cmbagent/cli.py` - Add mcp-server command
- `README.md` - Add MCP server documentation

## Verification Criteria

### Must Pass
- [ ] MCP server starts without errors
- [ ] All tools registered and discoverable
- [ ] Can execute tools via MCP protocol
- [ ] Resource management prevents overload
- [ ] Rate limiting enforced
- [ ] Tool schemas valid JSON Schema
- [ ] Stdio transport works correctly
- [ ] Error handling robust
- [ ] Session isolation maintained
- [ ] Claude Desktop integration works

### Should Pass
- [ ] All 50+ agents exposed as tools
- [ ] RAG agents accessible via MCP
- [ ] Streaming support for long operations
- [ ] Configuration via environment variables
- [ ] Logging comprehensive and useful
- [ ] Installation script works on macOS and Linux

### Integration Tests
- [ ] Can call `cmbagent_one_shot` from Claude Desktop
- [ ] Can call `cmbagent_planning_and_control` from Claude Desktop
- [ ] Can query RAG agents via MCP
- [ ] Multiple concurrent requests handled correctly
- [ ] Rate limit errors returned gracefully

## Testing Checklist

### Unit Tests
```python
# Test tool registration
def test_tool_registration():
    server = CMBAgentMCPServer()

    tools = server.list_tools()

    assert len(tools) > 0
    assert any(t.name == "cmbagent_one_shot" for t in tools)

# Test resource management
@pytest.mark.asyncio
async def test_resource_management():
    manager = ResourceManager(max_concurrent_tasks=2, rate_limit_per_minute=10)

    # Should succeed
    await manager.acquire()
    manager.release()

    # Should rate limit after 10 requests
    for i in range(10):
        await manager.acquire()
        manager.release()

    with pytest.raises(RateLimitExceededError):
        await manager.acquire()
```

### Integration Tests
```python
# Test MCP server with actual client
@pytest.mark.asyncio
async def test_mcp_server_integration():
    # Start server
    server = CMBAgentMCPServer()

    # Mock MCP client
    client = MockMCPClient()

    # Call tool
    result = await client.call_tool(
        "cmbagent_one_shot",
        {
            "task": "Print hello world",
            "agent": "engineer",
            "model": "gpt-4o"
        }
    )

    assert result["status"] == "success"
    assert "run_id" in result
```

### Manual Testing with Claude Desktop
1. Install MCP server: `bash scripts/install_mcp_server.sh`
2. Restart Claude Desktop
3. Open chat and type: "Use CMBAgent to analyze CMB data"
4. Verify Claude can access CMBAgent tools
5. Test various tools and agents

## Common Issues and Solutions

### Issue 1: MCP Server Not Starting in Claude Desktop
**Symptom:** Claude Desktop doesn't show CMBAgent tools
**Solution:** Check config file path, verify Python in PATH, check logs

### Issue 2: Rate Limit Errors
**Symptom:** Requests rejected with rate limit error
**Solution:** Increase rate limit in config, or wait before retrying

### Issue 3: Tool Schema Validation Errors
**Symptom:** MCP client rejects tool calls
**Solution:** Verify JSON Schema valid, check required fields match

### Issue 4: Long Operations Timeout
**Symptom:** Operations abort after some time
**Solution:** Increase timeout, add streaming support, use async execution

### Issue 5: Session Isolation Broken
**Symptom:** Multiple clients see each other's data
**Solution:** Verify session_id passed correctly, check database isolation

## Rollback Procedure

If MCP server causes issues:

1. **Remove from Claude Desktop:**
   - Edit Claude Desktop config
   - Remove "cmbagent" from mcpServers
   - Restart Claude Desktop

2. **Disable MCP server:**
   ```python
   ENABLE_MCP_SERVER = False
   ```

3. **Keep all other functionality** - MCP is isolated feature

## Post-Stage Actions

### Documentation
- Create comprehensive MCP server guide
- Add Claude Desktop integration tutorial
- Document all available tools
- Create video demonstration

### Update Progress
- Mark Stage 10 complete in `PROGRESS.md`
- Document tools exposed
- Note any limitations

### Prepare for Stage 11
- MCP server working and tested
- Ready to add MCP client (external tools)
- Stage 11 can proceed

## Success Criteria

Stage 10 is complete when:
1. MCP server starts and runs stably
2. All core tools exposed and functional
3. Tool schemas valid and well-documented
4. Resource management prevents overload
5. Claude Desktop integration working
6. Can execute workflows via MCP protocol
7. Session isolation maintained
8. Verification checklist 100% complete

## Estimated Time Breakdown

- MCP SDK installation and setup: 5 min
- Tool schema design: 8 min
- MCP server core implementation: 15 min
- Resource management: 7 min
- Streaming support: 6 min
- Configuration and CLI: 5 min
- Claude Desktop integration: 8 min
- Testing and verification: 12 min
- Documentation: 9 min

**Total: 45-55 minutes**

## Next Stage

Once Stage 10 is verified complete, proceed to:
**Stage 11: MCP Client for External Tools**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
