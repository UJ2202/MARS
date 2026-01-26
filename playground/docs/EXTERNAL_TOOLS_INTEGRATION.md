# External Tools Integration for CMBAgent

This guide explains how to integrate CrewAI and LangChain free tools into your CMBAgent planning and control workflow.

## Overview

CMBAgent uses the AG2 (AutoGen) framework for multi-agent orchestration. This integration allows you to:
- Use CrewAI's free tools (file operations, web scraping, code analysis)
- Use LangChain's free tools (Wikipedia, ArXiv, DuckDuckGo search, etc.)
- Seamlessly pass these tools to your existing agents (engineer, researcher, planner, control)
- Add custom tools alongside external ones

## Installation

1. **Install dependencies:**

```bash
pip install -e .
```

This will install the required packages:
- `crewai>=0.80.0`
- `crewai-tools>=0.13.0`
- `langchain>=0.3.0`
- `langchain-community>=0.3.0`

2. **Verify installation:**

```python
from cmbagent.external_tools import (
    get_crewai_free_tools,
    get_langchain_free_tools
)

print(f"CrewAI tools: {len(get_crewai_free_tools())}")
print(f"LangChain tools: {len(get_langchain_free_tools())}")
```

## Quick Start

### Method 1: Automatic Integration (Recommended)

The simplest way to add external tools to your workflow:

```python
from cmbagent import CMBAgent
from cmbagent.external_tools.integration_helpers import (
    register_external_tools_with_agents
)

# Initialize CMBAgent as usual
cmbagent = CMBAgent(
    work_dir="./my_workflow",
    mode="planning_and_control",
    api_keys=os.environ,
)

# Register all free tools with default agents
registry = register_external_tools_with_agents(
    cmbagent,
    use_crewai_tools=True,
    use_langchain_tools=True,
)

# Run your task - agents now have access to external tools
result = cmbagent.solve(
    "Research CMB on Wikipedia and save a summary to file",
    max_rounds=30
)
```

### Method 2: Selective Integration

Load only specific categories of tools:

```python
from cmbagent.external_tools import get_langchain_search_tools

# Get only search tools
search_tools = get_langchain_search_tools()

# Register with specific agent
registry = get_global_registry()
registry.register_tools(search_tools, category='search')

researcher = cmbagent.get_agent_from_name('researcher')
executor = cmbagent.get_agent_from_name('executor')

registry.register_with_agent(
    agent=researcher,
    category='search',
    executor_agent=executor
)
```

### Method 3: Permanent Integration in functions.py

For permanent integration, add to `cmbagent/functions.py`:

```python
def register_functions_to_agents(cmbagent_instance):
    """Register all functions including external tools"""
    
    # ... existing code ...
    
    # Add external tools integration
    try:
        from cmbagent.external_tools.integration_helpers import (
            register_external_tools_with_agents
        )
        
        registry = register_external_tools_with_agents(
            cmbagent_instance,
            use_crewai_tools=True,
            use_langchain_tools=True,
            agent_names=['engineer', 'researcher', 'planner', 'control'],
            executor_agent_name='executor'
        )
        
        print(f"Registered {len(registry.get_all_tools())} external tools")
        
    except Exception as e:
        print(f"Warning: Could not register external tools: {e}")
```

## Available Tools

### CrewAI Free Tools

**File Operations:**
- `FileReadTool` - Read file contents
- `FileWriteTool` - Write content to files
- `DirectoryReadTool` - List directory contents
- `DirectorySearchTool` - Search directories

**Code Analysis:**
- `CodeDocsSearchTool` - Search code documentation
- `CodeInterpreterTool` - Execute code snippets

**Web Tools:**
- `ScrapeWebsiteTool` - Scrape website content
- `WebsiteSearchTool` - Search within websites

**Document Search:**
- `TXTSearchTool` - Search text files
- `JSONSearchTool` - Search JSON files
- `XMLSearchTool` - Search XML files
- `CSVSearchTool` - Search CSV files
- `MDXSearchTool` - Search MDX files
- `PDFSearchTool` - Search PDF files

### LangChain Free Tools

**Research Tools:**
- `WikipediaQueryRun` - Search Wikipedia
- `ArxivQueryRun` - Search ArXiv papers
- `DuckDuckGoSearchRun` - Web search via DuckDuckGo

**File Operations:**
- `ReadFileTool` - Read files
- `WriteFileTool` - Write files
- `ListDirectoryTool` - List directory contents

**Code Execution:**
- `PythonREPLTool` - Execute Python code
- `ShellTool` - Execute shell commands (use with caution)

**Web/HTTP:**
- `RequestsGetTool` - HTTP GET requests
- `RequestsPostTool` - HTTP POST requests
- `RequestsPatchTool` - HTTP PATCH requests
- `RequestsPutTool` - HTTP PUT requests
- `RequestsDeleteTool` - HTTP DELETE requests

## Usage Examples

### Example 1: Research Task with Wikipedia and ArXiv

```python
task = """
Search Wikipedia for 'cosmic microwave background' and ArXiv for recent CMB papers.
Summarize the findings and save to 'cmb_research.txt'.
"""

result = cmbagent.solve(task, max_rounds=30)
```

The workflow will:
1. Planner creates a plan using available tools
2. Researcher uses `WikipediaQueryRun` and `ArxivQueryRun`
3. Engineer uses `FileWriteTool` to save results

### Example 2: Code Analysis and Execution

```python
task = """
Read the Python file 'analysis.py', check for issues,
and execute it to verify it works correctly.
"""

result = cmbagent.solve(task, max_rounds=30)
```

The workflow will:
1. Engineer uses `FileReadTool` to read the file
2. Engineer uses `CodeInterpreterTool` to analyze
3. Engineer uses `PythonREPLTool` to execute

### Example 3: Web Scraping and Data Processing

```python
task = """
Scrape the CAMB documentation website for installation instructions,
extract key steps, and create a markdown guide.
"""

result = cmbagent.solve(task, max_rounds=30)
```

The workflow will:
1. Researcher uses `ScrapeWebsiteTool`
2. Engineer processes and structures data
3. Engineer uses `FileWriteTool` to save markdown

## Advanced Usage

### Adding Custom Tools

You can add your own tools alongside CrewAI/LangChain tools:

```python
from cmbagent.external_tools.integration_helpers import (
    add_custom_tool_to_registry
)

def my_cosmology_tool(H0: float, omega_m: float) -> dict:
    """Calculate cosmological parameters"""
    return {
        "H0": H0,
        "omega_m": omega_m,
        "omega_lambda": 1.0 - omega_m
    }

add_custom_tool_to_registry(
    tool_name="cosmology_calculator",
    tool_function=my_cosmology_tool,
    tool_description="Calculate basic cosmological parameters",
    category="cosmology"
)
```

### Fine-Grained Control

Register specific tools with specific agents:

```python
from cmbagent.external_tools.integration_helpers import (
    register_specific_external_tools
)

# Researcher gets only search tools
register_specific_external_tools(
    cmbagent,
    tool_names=['WikipediaQueryRun', 'ArxivQueryRun'],
    agent_names=['researcher']
)

# Engineer gets only file tools
register_specific_external_tools(
    cmbagent,
    tool_names=['FileReadTool', 'FileWriteTool'],
    agent_names=['engineer']
)
```

### List Available Tools

```python
from cmbagent.external_tools.integration_helpers import (
    list_available_external_tools
)

# Print all tools with descriptions
print(list_available_external_tools(verbose=True))
```

## Architecture

### How It Works

1. **Tool Adapter** (`tool_adapter.py`):
   - Converts CrewAI/LangChain tools to AG2-compatible format
   - Wraps external tool functions for seamless integration
   - Handles errors and type conversions

2. **Tool Registry** (`tool_registry.py`):
   - Centralized registry for all external tools
   - Manages tool categories and availability
   - Handles bulk registration with agents

3. **Integration Helpers** (`integration_helpers.py`):
   - High-level functions for easy integration
   - Handles tool loading and agent registration
   - Provides utility functions

### Tool Flow

```
External Tool (CrewAI/LangChain)
    ↓
Tool Adapter (converts to AG2 format)
    ↓
Tool Registry (manages tools)
    ↓
AG2 Agent Registration (register_function)
    ↓
Agent uses tool during planning/control
    ↓
Executor executes tool
```

## Best Practices

1. **Start with automatic integration** - Use `register_external_tools_with_agents()` first
2. **Use selective integration** - Once you know which tools you need, load only those
3. **Test with simple tasks** - Verify tools work before complex workflows
4. **Monitor tool usage** - Check which tools agents actually use
5. **Add custom tools** - Extend with domain-specific tools as needed

## Troubleshooting

### Tools not available

If tools aren't working:
1. Check dependencies are installed: `pip install crewai crewai-tools langchain langchain-community`
2. Verify tools are loaded: `print(list_available_external_tools())`
3. Check agent registration: Tools must be registered before `cmbagent.solve()`

### Import errors

Some tools require additional dependencies:
```bash
# For web scraping
pip install beautifulsoup4 lxml

# For document processing
pip install pypdf pdfplumber

# For search tools
pip install wikipedia duckduckgo-search
```

### Tool execution errors

- Ensure executor agent is properly configured
- Check tool permissions (file access, network access)
- Verify tool inputs match expected types

## Examples

See `examples/external_tools_integration.py` for complete working examples:
- Example 1: Automatic integration
- Example 2: Selective integration
- Example 3: Fine-grained control
- Example 4: Custom tools
- Example 5: Integration in functions.py

Run examples:
```bash
cd examples
python external_tools_integration.py
```

## API Reference

### Main Functions

- `register_external_tools_with_agents()` - Register all tools automatically
- `register_specific_external_tools()` - Register specific tools
- `list_available_external_tools()` - List all registered tools
- `add_custom_tool_to_registry()` - Add custom tools

### Tool Loading Functions

- `get_crewai_free_tools()` - Get all CrewAI free tools
- `get_crewai_file_tools()` - Get CrewAI file tools
- `get_crewai_web_tools()` - Get CrewAI web tools
- `get_crewai_code_tools()` - Get CrewAI code tools
- `get_langchain_free_tools()` - Get all LangChain free tools
- `get_langchain_search_tools()` - Get LangChain search tools
- `get_langchain_file_tools()` - Get LangChain file tools

## Contributing

To add support for new external tools:
1. Add tool loading function in `crewai_tools.py` or `langchain_tools.py`
2. Add category support in `tool_registry.py`
3. Update documentation and examples

## License

This integration follows CMBAgent's Apache-2.0 license.
