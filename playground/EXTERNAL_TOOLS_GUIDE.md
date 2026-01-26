# Complete Guide: Adding CrewAI and LangChain Tools to CMBAgent

## Overview

This guide shows you how to integrate CrewAI and LangChain's free tools into your CMBAgent planning and control workflow. After following this guide, your agents will have access to 30+ external tools for research, file operations, web scraping, code execution, and more.

## What You'll Get

✅ **30+ Free Tools** from CrewAI and LangChain  
✅ **Seamless Integration** with existing agents  
✅ **Zero Code Changes** to your workflow logic  
✅ **Flexible Control** - use all tools or cherry-pick specific ones  
✅ **Custom Tools** - add your own tools easily  

## Installation (2 minutes)

### Step 1: Update Dependencies

The dependencies are already added to `pyproject.toml`. Install them:

```bash
cd /srv/projects/mas/mars/denario/cmbagent
pip install -e .
```

This installs:
- `crewai>=0.80.0`
- `crewai-tools>=0.13.0`
- `langchain>=0.3.0`
- `langchain-community>=0.3.0`
- `langchain-core>=0.3.0`

### Step 2: Install Optional Dependencies (for specific tools)

```bash
# For Wikipedia, ArXiv, web search
pip install wikipedia arxiv duckduckgo-search

# For web scraping
pip install beautifulsoup4 lxml

# For PDF processing
pip install pypdf pdfplumber
```

### Step 3: Verify Installation

```bash
python tests/test_external_tools.py
```

You should see:
```
✓ All tests passed! External tools integration is ready to use.
```

## Quick Start (3 minutes)

### Option A: Temporary Integration (For Testing)

Create a test script:

```python
# test_external_tools_workflow.py
from cmbagent import CMBAgent
from cmbagent.external_tools.integration_helpers import register_external_tools_with_agents
import os

# Initialize CMBAgent
cmbagent = CMBAgent(
    work_dir="./test_external_tools",
    mode="planning_and_control",
    api_keys=os.environ,
)

# Register all external tools
register_external_tools_with_agents(
    cmbagent,
    use_crewai_tools=True,
    use_langchain_tools=True,
)

# Test with a simple task
result = cmbagent.solve(
    """
    Search Wikipedia for 'cosmic microwave background'.
    Summarize the key findings.
    Save the summary to 'cmb_summary.txt'.
    """,
    max_rounds=30
)

print("Result:", result)
```

Run it:
```bash
python test_external_tools_workflow.py
```

### Option B: Permanent Integration (Recommended)

Edit `cmbagent/functions.py` and add this at the end of `register_functions_to_agents()`:

```python
def register_functions_to_agents(cmbagent_instance):
    """
    This function registers the functions to the agents.
    """
    # ... all existing code remains unchanged ...
    
    # ========== ADD THIS BLOCK AT THE END ==========
    
    # Register external tools from CrewAI and LangChain
    try:
        from cmbagent.external_tools.integration_helpers import (
            register_external_tools_with_agents
        )
        
        # Register all free tools with key agents
        registry = register_external_tools_with_agents(
            cmbagent_instance,
            use_crewai_tools=True,
            use_langchain_tools=True,
            agent_names=['engineer', 'researcher', 'planner', 'control'],
            executor_agent_name='executor'
        )
        
        print(f"✓ Registered {len(registry.get_all_tools())} external tools")
        
    except Exception as e:
        print(f"Warning: Could not register external tools: {e}")
    
    # ========== END OF NEW BLOCK ==========
```

Now external tools are available in all your workflows!

## Usage Examples

### Example 1: Research Task

```python
task = """
Research recent papers about CMB lensing on ArXiv.
Find the top 3 most cited papers from the last year.
Create a summary document with titles, authors, and abstracts.
Save it to 'cmb_lensing_papers.txt'.
"""

result = cmbagent.solve(task, max_rounds=40)
```

**What happens:**
1. Planner creates a plan using available tools
2. Researcher uses `ArxivQueryRun` to search ArXiv
3. Researcher analyzes and ranks papers
4. Engineer uses `FileWriteTool` to save results

### Example 2: Code Analysis

```python
task = """
Read the file 'cosmology_analysis.py'.
Check if there are any potential issues.
If found, suggest improvements.
Create a code review document.
"""

result = cmbagent.solve(task, max_rounds=30)
```

**What happens:**
1. Engineer uses `FileReadTool` to read the code
2. Engineer uses `CodeInterpreterTool` to analyze
3. Engineer generates review with suggestions
4. Engineer uses `FileWriteTool` to save review

### Example 3: Web Research + Data Processing

```python
task = """
Search Wikipedia for information about dark energy.
Also search DuckDuckGo for recent news articles.
Compile a comprehensive report combining both sources.
Save as 'dark_energy_report.md'.
"""

result = cmbagent.solve(task, max_rounds=40)
```

**What happens:**
1. Researcher uses `WikipediaQueryRun`
2. Researcher uses `DuckDuckGoSearchRun`
3. Researcher compiles and structures information
4. Engineer uses `FileWriteTool` to save markdown

### Example 4: Multi-Step Data Pipeline

```python
task = """
1. Download the latest CAMB documentation from the web
2. Extract key sections about power spectrum calculation
3. Create a structured JSON file with the information
4. Generate a Python script that demonstrates the key concepts
5. Save both files
"""

result = cmbagent.solve(task, max_rounds=50)
```

**What happens:**
1. Researcher uses `ScrapeWebsiteTool` or `RequestsGetTool`
2. Engineer processes and structures data
3. Engineer uses `JSONSearchTool` and file tools
4. Engineer generates Python code
5. Engineer uses `FileWriteTool` to save both files

## Advanced Usage

### Selective Tool Loading

If you only need specific types of tools:

```python
from cmbagent.external_tools import (
    get_langchain_search_tools,
    get_crewai_file_tools,
)
from cmbagent.external_tools import get_global_registry

# Load only what you need
registry = get_global_registry()

search_tools = get_langchain_search_tools()
registry.register_tools(search_tools, category='search')

file_tools = get_crewai_file_tools()
registry.register_tools(file_tools, category='file')

# Register with specific agents
researcher = cmbagent.get_agent_from_name('researcher')
engineer = cmbagent.get_agent_from_name('engineer')
executor = cmbagent.get_agent_from_name('executor')

registry.register_with_agent(researcher, category='search', executor_agent=executor)
registry.register_with_agent(engineer, category='file', executor_agent=executor)
```

### Fine-Grained Control

Register specific tools with specific agents:

```python
from cmbagent.external_tools.integration_helpers import register_specific_external_tools

# Researcher gets only Wikipedia and ArXiv
register_specific_external_tools(
    cmbagent,
    tool_names=['WikipediaQueryRun', 'ArxivQueryRun'],
    agent_names=['researcher']
)

# Engineer gets file tools and Python REPL
register_specific_external_tools(
    cmbagent,
    tool_names=['FileReadTool', 'FileWriteTool', 'PythonREPLTool'],
    agent_names=['engineer']
)
```

### Adding Custom Tools

You can add your own domain-specific tools:

```python
from cmbagent.external_tools.integration_helpers import add_custom_tool_to_registry

def calculate_hubble_parameter(z: float, H0: float = 70.0, omega_m: float = 0.3) -> dict:
    """
    Calculate Hubble parameter at redshift z.
    
    Args:
        z: Redshift
        H0: Hubble constant at z=0 (km/s/Mpc)
        omega_m: Matter density parameter
        
    Returns:
        Dictionary with H(z) and other parameters
    """
    import math
    omega_lambda = 1.0 - omega_m
    E_z = math.sqrt(omega_m * (1 + z)**3 + omega_lambda)
    H_z = H0 * E_z
    
    return {
        "redshift": z,
        "H_z": H_z,
        "H0": H0,
        "omega_m": omega_m,
        "omega_lambda": omega_lambda
    }

# Add to registry
add_custom_tool_to_registry(
    tool_name="calculate_hubble_parameter",
    tool_function=calculate_hubble_parameter,
    tool_description="Calculate Hubble parameter at given redshift",
    category="cosmology"
)

# Register with agents
from cmbagent.external_tools import get_global_registry

registry = get_global_registry()
researcher = cmbagent.get_agent_from_name('researcher')
engineer = cmbagent.get_agent_from_name('engineer')
executor = cmbagent.get_agent_from_name('executor')

registry.register_with_agent(researcher, category='cosmology', executor_agent=executor)
registry.register_with_agent(engineer, category='cosmology', executor_agent=executor)
```

Now your agents can use this tool in planning and control!

### Listing Available Tools

```python
from cmbagent.external_tools.integration_helpers import list_available_external_tools

# Print all tools with descriptions
print(list_available_external_tools(verbose=True))

# Or just names
print(list_available_external_tools(verbose=False))
```

## Available Tools Reference

### CrewAI Tools (~15 tools)

**File Operations:**
- `FileReadTool` - Read file contents
- `FileWriteTool` - Write content to files
- `DirectoryReadTool` - List directory contents
- `DirectorySearchTool` - Search directories for files

**Code Analysis:**
- `CodeDocsSearchTool` - Search code documentation
- `CodeInterpreterTool` - Execute and analyze code snippets

**Web Scraping:**
- `ScrapeWebsiteTool` - Scrape website content
- `WebsiteSearchTool` - Search within websites

**Document Search:**
- `TXTSearchTool` - Search text files
- `JSONSearchTool` - Search JSON files
- `XMLSearchTool` - Search XML files
- `CSVSearchTool` - Search CSV files
- `MDXSearchTool` - Search MDX files
- `PDFSearchTool` - Search PDF files

**Version Control:**
- `GithubSearchTool` - Search GitHub repositories

### LangChain Tools (~15 tools)

**Research:**
- `WikipediaQueryRun` - Search Wikipedia articles
- `ArxivQueryRun` - Search ArXiv papers
- `DuckDuckGoSearchRun` - Web search via DuckDuckGo

**File Operations:**
- `ReadFileTool` - Read file contents
- `WriteFileTool` - Write content to files
- `ListDirectoryTool` - List directory contents

**Code Execution:**
- `PythonREPLTool` - Execute Python code
- `ShellTool` - Execute shell commands (use carefully!)

**Web/HTTP:**
- `RequestsGetTool` - HTTP GET requests
- `RequestsPostTool` - HTTP POST requests
- `RequestsPatchTool` - HTTP PATCH requests
- `RequestsPutTool` - HTTP PUT requests
- `RequestsDeleteTool` - HTTP DELETE requests

**Data Processing:**
- `JsonListKeysTool` - List keys in JSON
- `JsonGetValueTool` - Get value from JSON

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Your CMBAgent Workflow                    │
│                 (planning_and_control mode)                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────────┐
│                    Planning Phase                            │
│  Planner sees all available tools (internal + external)     │
│  Creates plan using appropriate tools for each step         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────────┐
│                    Control Phase                             │
│  Control assigns tasks to agents                            │
│  Agents use tools based on plan                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────────┐
│                 External Tool Execution                      │
│                                                              │
│  External Tool (CrewAI/LangChain)                           │
│         ↓                                                    │
│  AG2ToolAdapter (converts to AG2 format)                    │
│         ↓                                                    │
│  autogen.register_function (registered with agent)          │
│         ↓                                                    │
│  Executor Agent (executes the tool)                         │
│         ↓                                                    │
│  Result returned to calling agent                           │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

1. **Tool Adapter** (`tool_adapter.py`):
   - Converts external tools to AG2-compatible functions
   - Handles errors and type conversions
   - Wraps tools for seamless execution

2. **Tool Registry** (`tool_registry.py`):
   - Central registry for all external tools
   - Manages tool categories and availability
   - Handles bulk registration with agents

3. **Integration Helpers** (`integration_helpers.py`):
   - High-level functions for easy integration
   - Automatic tool loading and registration
   - Utility functions for tool management

4. **Tool Loaders** (`crewai_tools.py`, `langchain_tools.py`):
   - Load tools from external frameworks
   - Categorize tools by function
   - Handle import errors gracefully

## Best Practices

### 1. Start Simple

Begin with automatic integration:
```python
register_external_tools_with_agents(cmbagent)
```

### 2. Monitor Performance

Check which tools are actually used:
```python
# In your workflow, log tool usage
print(list_available_external_tools(verbose=False))
```

### 3. Optimize Tool Selection

Once you know which tools you need:
```python
# Only load necessary tools
register_specific_external_tools(
    cmbagent,
    tool_names=['WikipediaQueryRun', 'FileWriteTool', 'ArxivQueryRun'],
    agent_names=['researcher', 'engineer']
)
```

### 4. Add Domain-Specific Tools

Extend with your own tools:
```python
# Add cosmology-specific tools
add_custom_tool_to_registry(...)
```

### 5. Test Before Deployment

Always test with simple tasks first:
```bash
python tests/test_external_tools.py
```

## Troubleshooting

### Issue: Tools Not Available

**Symptom:** Agents don't use external tools

**Solution:**
1. Check tools are loaded:
   ```python
   print(list_available_external_tools())
   ```
2. Verify registration happened before `solve()`:
   ```python
   register_external_tools_with_agents(cmbagent)
   result = cmbagent.solve(...)  # Must be after registration
   ```

### Issue: Import Errors

**Symptom:** `ImportError: No module named 'crewai'`

**Solution:**
```bash
pip install -e .
# Or individually
pip install crewai crewai-tools langchain langchain-community
```

### Issue: Tool Execution Fails

**Symptom:** Tool returns error during execution

**Solutions:**
1. Check tool-specific dependencies:
   ```bash
   pip install wikipedia arxiv duckduckgo-search beautifulsoup4
   ```
2. Verify executor agent is configured:
   ```python
   executor = cmbagent.get_agent_from_name('executor')
   # Should not be None
   ```
3. Check tool permissions (file access, network, etc.)

### Issue: Some Tools Missing

**Symptom:** Only some tools available

**Cause:** Import errors for specific tools

**Solution:** Check warnings during loading:
```python
# Will show warnings for missing dependencies
tools = get_crewai_free_tools()
```

## Resources

### Documentation
- **Quick Start**: [`docs/EXTERNAL_TOOLS_QUICKSTART.md`](docs/EXTERNAL_TOOLS_QUICKSTART.md)
- **Full Guide**: [`docs/EXTERNAL_TOOLS_INTEGRATION.md`](docs/EXTERNAL_TOOLS_INTEGRATION.md)
- **Technical Summary**: [`docs/EXTERNAL_TOOLS_SUMMARY.md`](docs/EXTERNAL_TOOLS_SUMMARY.md)
- **Module README**: [`cmbagent/external_tools/README.md`](cmbagent/external_tools/README.md)

### Examples
- **Complete Examples**: [`examples/external_tools_integration.py`](examples/external_tools_integration.py)
  - Run with: `python examples/external_tools_integration.py`

### Testing
- **Test Suite**: [`tests/test_external_tools.py`](tests/test_external_tools.py)
  - Run with: `python tests/test_external_tools.py`

### External Documentation
- **CrewAI**: https://docs.crewai.com/tools
- **LangChain**: https://python.langchain.com/docs/integrations/tools

## FAQ

**Q: Do I need API keys for these tools?**  
A: Most tools are free and don't require API keys. Tools like Wikipedia, ArXiv, DuckDuckGo, file operations are all free.

**Q: Can I use only CrewAI tools or only LangChain tools?**  
A: Yes! Set `use_crewai_tools=False` or `use_langchain_tools=False` as needed.

**Q: How do I know which tools my agents are using?**  
A: Enable verbose logging in your workflow, or check the agent's conversation history.

**Q: Can I add tools from other frameworks?**  
A: Yes! Use the `AG2ToolAdapter` class to wrap any callable as a tool.

**Q: Will this slow down my workflow?**  
A: No. Tools are only executed when called. Loading tools is fast and done once at initialization.

**Q: Can I remove tools after registration?**  
A: Yes! Use `registry.clear()` or create a new registry instance.

## Next Steps

1. **Test the integration:**
   ```bash
   python tests/test_external_tools.py
   ```

2. **Try an example:**
   ```bash
   python examples/external_tools_integration.py
   ```

3. **Integrate into your workflow:**
   - Edit `cmbagent/functions.py` (recommended)
   - Or use script-level integration

4. **Customize:**
   - Add your domain-specific tools
   - Select only the tools you need
   - Configure tool availability per agent

## Summary

You now have:
- ✅ 30+ external tools integrated
- ✅ Seamless AG2 compatibility
- ✅ Flexible integration options
- ✅ Complete documentation
- ✅ Working examples
- ✅ Test suite

Your CMBAgent planning and control workflow is now supercharged with external tools! 🚀

Happy coding! 🎉
