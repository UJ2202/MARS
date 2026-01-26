# Quick Start: Adding External Tools to CMBAgent

This guide gets you started with CrewAI and LangChain tools in under 5 minutes.

## Step 1: Install Dependencies (1 minute)

```bash
cd /srv/projects/mas/mars/denario/cmbagent
pip install -e .
```

This installs:
- crewai & crewai-tools
- langchain & langchain-community
- All necessary dependencies

## Step 2: Choose Your Integration Method (1 minute)

### Option A: Quick Integration (Easiest)

Add to any Python script:

```python
from cmbagent import CMBAgent
from cmbagent.external_tools.integration_helpers import (
    register_external_tools_with_agents
)

# Initialize CMBAgent
cmbagent = CMBAgent(
    work_dir="./my_project",
    mode="planning_and_control",
    api_keys=os.environ,
)

# Register all free tools
register_external_tools_with_agents(
    cmbagent,
    use_crewai_tools=True,
    use_langchain_tools=True,
)

# Use as normal
result = cmbagent.solve("Your task here", max_rounds=30)
```

### Option B: Permanent Integration (Recommended)

Edit `cmbagent/functions.py` and add this at the end of `register_functions_to_agents()`:

```python
def register_functions_to_agents(cmbagent_instance):
    # ... existing code ...
    
    # ADD THIS:
    try:
        from cmbagent.external_tools.integration_helpers import (
            register_external_tools_with_agents
        )
        
        register_external_tools_with_agents(
            cmbagent_instance,
            use_crewai_tools=True,
            use_langchain_tools=True,
            agent_names=['engineer', 'researcher', 'planner', 'control'],
            executor_agent_name='executor'
        )
    except Exception as e:
        print(f"Warning: Could not register external tools: {e}")
```

## Step 3: Test It (3 minutes)

### Test 1: Wikipedia Search

```python
from cmbagent import CMBAgent
from cmbagent.external_tools.integration_helpers import register_external_tools_with_agents
import os

cmbagent = CMBAgent(
    work_dir="./test_wikipedia",
    mode="planning_and_control",
    api_keys=os.environ,
)

register_external_tools_with_agents(cmbagent)

result = cmbagent.solve(
    "Search Wikipedia for 'cosmic microwave background' and summarize the key points",
    max_rounds=20
)

print(result)
```

### Test 2: File Operations

```python
result = cmbagent.solve(
    """
    Create a Python script that prints 'Hello CMB!'
    Save it to 'hello.py'
    Then read it back and verify the content
    """,
    max_rounds=20
)
```

### Test 3: Research + File Writing

```python
result = cmbagent.solve(
    """
    Search ArXiv for recent papers about 'CMB lensing'
    Summarize the top 3 results
    Save the summary to 'cmb_lensing_papers.txt'
    """,
    max_rounds=30
)
```

## What Just Happened?

Your agents now have access to:

**Research Tools:**
- Wikipedia search
- ArXiv paper search  
- DuckDuckGo web search

**File Tools:**
- Read/write files
- List directories
- Search documents (TXT, JSON, CSV, PDF, etc.)

**Code Tools:**
- Python REPL
- Code interpreter
- Shell commands

**Web Tools:**
- Web scraping
- Website search
- HTTP requests

## Next Steps

1. **See all available tools:**
```python
from cmbagent.external_tools.integration_helpers import list_available_external_tools
print(list_available_external_tools(verbose=True))
```

2. **Add custom tools:**
```python
from cmbagent.external_tools.integration_helpers import add_custom_tool_to_registry

def my_tool(input_data: str) -> str:
    return f"Processed: {input_data}"

add_custom_tool_to_registry(
    tool_name="my_tool",
    tool_function=my_tool,
    tool_description="My custom tool",
    category="custom"
)
```

3. **Selective tool loading:**
```python
# Load only search tools
from cmbagent.external_tools import get_langchain_search_tools

tools = get_langchain_search_tools()
# Register with specific agents...
```

## Troubleshooting

**Tools not found?**
```bash
pip install wikipedia arxiv duckduckgo-search beautifulsoup4
```

**Import errors?**
```bash
pip install crewai crewai-tools langchain langchain-community
```

**Need help?**
See full documentation: `docs/EXTERNAL_TOOLS_INTEGRATION.md`
Run examples: `python examples/external_tools_integration.py`

## Summary

You've now integrated 30+ external tools into your CMBAgent workflow!

- ✅ CrewAI tools installed
- ✅ LangChain tools installed
- ✅ Tools registered with agents
- ✅ Ready for planning & control workflows

Your agents can now:
- Search Wikipedia, ArXiv, web
- Read/write files
- Execute code
- Scrape websites
- And much more!

**Total time: ~5 minutes** ⚡
