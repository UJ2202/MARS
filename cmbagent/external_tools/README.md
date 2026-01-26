# External Tools Integration Module

This module provides seamless integration of CrewAI and LangChain tools with CMBAgent's AG2-based multi-agent system.

## Quick Start

```python
from cmbagent import CMBAgent
from cmbagent.external_tools.integration_helpers import register_external_tools_with_agents

# Initialize CMBAgent
cmbagent = CMBAgent(
    work_dir="./my_project",
    mode="planning_and_control",
)

# Register all free tools
register_external_tools_with_agents(cmbagent)

# Your agents now have 30+ external tools!
result = cmbagent.solve("Your task here", max_rounds=30)
```

## What This Module Does

1. **Converts** external tools (CrewAI, LangChain) to AG2-compatible format
2. **Manages** tools through a centralized registry
3. **Registers** tools with your CMBAgent agents
4. **Enables** seamless use in planning and control workflows

## Module Structure

```
external_tools/
├── __init__.py                 # Main exports
├── tool_adapter.py             # Tool conversion to AG2 format
├── tool_registry.py            # Central tool management
├── crewai_tools.py             # CrewAI tools loader
├── langchain_tools.py          # LangChain tools loader
└── integration_helpers.py      # High-level helpers
```

## Available Functions

### High-Level Integration

```python
from cmbagent.external_tools.integration_helpers import (
    register_external_tools_with_agents,    # Register all tools automatically
    register_specific_external_tools,       # Fine-grained control
    list_available_external_tools,          # List registered tools
    add_custom_tool_to_registry,           # Add your custom tools
)
```

### Tool Loading

```python
from cmbagent.external_tools import (
    get_crewai_free_tools,                 # All CrewAI free tools
    get_crewai_file_tools,                 # CrewAI file tools only
    get_crewai_web_tools,                  # CrewAI web tools only
    get_crewai_code_tools,                 # CrewAI code tools only
    get_langchain_free_tools,              # All LangChain free tools
    get_langchain_search_tools,            # LangChain search tools
    get_langchain_file_tools,              # LangChain file tools
    get_langchain_web_tools,               # LangChain web tools
)
```

### Core Components

```python
from cmbagent.external_tools import (
    AG2ToolAdapter,                        # Tool adapter class
    ExternalToolRegistry,                  # Registry class
    get_global_registry,                   # Get global registry instance
)
```

## Available Tools (30+)

### CrewAI Tools
- File operations (read, write, directory)
- Code analysis (docs search, interpreter)
- Web scraping (website scrape, search)
- Document search (TXT, JSON, XML, CSV, PDF, MDX)
- GitHub search

### LangChain Tools
- Research (Wikipedia, ArXiv, DuckDuckGo)
- File operations (read, write, list)
- Code execution (Python REPL, Shell)
- Web/HTTP (GET, POST, PATCH, PUT, DELETE)
- Data tools (JSON operations)

## Usage Examples

### Example 1: Automatic Integration

```python
# Load and register all tools
register_external_tools_with_agents(
    cmbagent,
    use_crewai_tools=True,
    use_langchain_tools=True,
)
```

### Example 2: Selective Integration

```python
# Only search tools for researcher
from cmbagent.external_tools import get_langchain_search_tools

tools = get_langchain_search_tools()
registry = get_global_registry()
registry.register_tools(tools, category='search')

researcher = cmbagent.get_agent_from_name('researcher')
executor = cmbagent.get_agent_from_name('executor')

registry.register_with_agent(
    agent=researcher,
    category='search',
    executor_agent=executor
)
```

### Example 3: Specific Tools

```python
# Register specific tools with specific agents
register_specific_external_tools(
    cmbagent,
    tool_names=['WikipediaQueryRun', 'ArxivQueryRun', 'FileWriteTool'],
    agent_names=['researcher', 'engineer']
)
```

### Example 4: Custom Tools

```python
def my_cosmology_tool(H0: float, omega_m: float) -> dict:
    """Calculate cosmological parameters."""
    return {"H0": H0, "omega_m": omega_m, "omega_lambda": 1.0 - omega_m}

add_custom_tool_to_registry(
    tool_name="cosmology_calculator",
    tool_function=my_cosmology_tool,
    tool_description="Calculate cosmological parameters",
    category="cosmology"
)
```

## Documentation

- **Quick Start**: `../docs/EXTERNAL_TOOLS_QUICKSTART.md` (5 min guide)
- **Complete Guide**: `../docs/EXTERNAL_TOOLS_INTEGRATION.md` (full documentation)
- **Implementation**: `../docs/EXTERNAL_TOOLS_SUMMARY.md` (technical details)

## Examples

See `../examples/external_tools_integration.py` for 5 complete examples:
1. Automatic integration
2. Selective integration
3. Fine-grained control
4. Custom tools
5. Integration in functions.py

## Testing

Run tests to verify everything works:

```bash
python ../tests/test_external_tools.py
```

## Architecture

```
External Tool (CrewAI/LangChain)
    ↓
AG2ToolAdapter (converts to AG2 format)
    ↓
ExternalToolRegistry (manages tools)
    ↓
autogen.register_function (registers with agent)
    ↓
Agent uses tool in workflow
    ↓
Executor executes tool
```

## Integration Patterns

### Pattern 1: Script-Level

```python
# In your script
from cmbagent.external_tools.integration_helpers import register_external_tools_with_agents

cmbagent = CMBAgent(...)
register_external_tools_with_agents(cmbagent)
```

### Pattern 2: System-Level (Recommended)

```python
# In cmbagent/functions.py
def register_functions_to_agents(cmbagent_instance):
    # ... existing code ...
    
    from cmbagent.external_tools.integration_helpers import register_external_tools_with_agents
    register_external_tools_with_agents(cmbagent_instance)
```

## Requirements

Install with:
```bash
pip install -e .
```

This installs:
- crewai >= 0.80.0
- crewai-tools >= 0.13.0
- langchain >= 0.3.0
- langchain-community >= 0.3.0
- langchain-core >= 0.3.0

Optional dependencies for specific tools:
```bash
pip install wikipedia arxiv duckduckgo-search beautifulsoup4 pypdf
```

## API Reference

### `register_external_tools_with_agents()`

Register external tools with agents automatically.

**Parameters:**
- `cmbagent_instance`: CMBAgent instance
- `use_crewai_tools`: Load CrewAI tools (default: True)
- `use_langchain_tools`: Load LangChain tools (default: True)
- `tool_categories`: Specific categories to load (default: None = all)
- `agent_names`: Agents to register with (default: ['engineer', 'researcher', 'planner', 'control'])
- `executor_agent_name`: Executor agent name (default: 'executor')

**Returns:** `ExternalToolRegistry` instance

### `ExternalToolRegistry`

Central registry for managing external tools.

**Key Methods:**
- `register_tool(tool, category)`: Register single tool
- `register_tools(tools, category)`: Register multiple tools
- `register_with_agent(agent, tool_names, category, executor)`: Register with agent
- `get_tool(name)`: Get tool by name
- `get_all_tools()`: Get all tools
- `list_tools(verbose)`: Print formatted list

### `AG2ToolAdapter`

Adapter for converting external tools to AG2 format.

**Parameters:**
- `tool_name`: Name of the tool
- `tool_description`: What the tool does
- `tool_function`: The callable to execute

**Methods:**
- `get_ag2_function()`: Get AG2-compatible function

## Contributing

To add support for new external tools:

1. Add loader function in `crewai_tools.py` or `langchain_tools.py`
2. Update category support in `tool_registry.py`
3. Add examples to `../examples/external_tools_integration.py`
4. Update documentation in `../docs/`
5. Add tests in `../tests/test_external_tools.py`

## License

Apache-2.0 (same as CMBAgent)

## Support

- **Issues**: GitHub Issues
- **Docs**: See `../docs/EXTERNAL_TOOLS_*.md`
- **Examples**: See `../examples/external_tools_integration.py`
- **Tests**: Run `python ../tests/test_external_tools.py`
