# AG2 Free Tools Integration Guide

Complete guide for integrating free tools from LangChain and CrewAI into AG2 agents in your CMBAgent system.

Based on [AG2 Official Documentation](https://docs.ag2.ai/latest/docs/use-cases/notebooks/notebooks/agentchat_captainagent_crosstool/)

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Available Free Tools](#available-free-tools)
4. [Quick Start](#quick-start)
5. [Usage Examples](#usage-examples)
6. [Integration with CMBAgent](#integration-with-cmbagent)
7. [Advanced Usage](#advanced-usage)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This integration allows you to use tools from LangChain and CrewAI frameworks with your AG2 agents using AG2's native `Interoperability` module. All tools are converted to AG2-compatible format automatically.

### Why Use External Tools?

- **Search Capabilities**: DuckDuckGo, Wikipedia, ArXiv searches
- **File Operations**: Read, write, and search files
- **Web Scraping**: Extract information from websites
- **Code Analysis**: Analyze and interpret code
- **Research**: Access scientific papers and documentation

---

## Installation

### Option 1: Install with external-tools extra

```bash
cd /srv/projects/mas/mars/denario/cmbagent
pip install -e ".[external-tools]"
```

### Option 2: Manual installation

```bash
# Install AG2 with interoperability support
pip install -U "ag2[openai,interop-langchain,interop-crewai,duckduckgo]"

# Install tool dependencies
pip install langchain-community crewai[tools]
pip install duckduckgo-search wikipedia arxiv
```

### Verify Installation

```python
from autogen.interop import Interoperability
from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader

loader = AG2FreeToolsLoader()
print("✓ Installation successful!")
```

---

## Available Free Tools

### LangChain Tools (No API Key Required)

| Tool | Description | Import |
|------|-------------|--------|
| **DuckDuckGo Search** | Web search without API key | `duckduckgo` |
| **Wikipedia** | Search Wikipedia articles | `wikipedia` |
| **ArXiv** | Search scientific papers | `arxiv` |
| **Python REPL** | Execute Python code | `python_repl` |
| **File Read** | Read file contents | `file_read` |
| **File Write** | Write to files | `file_write` |
| **List Directory** | List directory contents | `list_directory` |
| **Human Input** | Get input from humans | `human` |

### CrewAI Tools (No API Key Required)

| Tool | Description | Import |
|------|-------------|--------|
| **Scrape Website** | Extract content from websites | `scrape_website` |
| **File Read** | Read files | `file_read` |
| **File Write** | Write files | `file_write` |
| **Directory Read** | Read directory structure | `directory_read` |
| **Code Docs Search** | Search code documentation | `code_docs` |
| **Code Interpreter** | Interpret and run code | `code_interpreter` |
| **Directory Search** | Search in directories | `directory_search` |
| **TXT Search** | Search text files | `txt_search` |
| **JSON Search** | Search JSON files | `json_search` |
| **CSV Search** | Search CSV files | `csv_search` |
| **PDF Search** | Search PDF files | `pdf_search` |
| **Website Search** | Search website content | `website_search` |

---

## Quick Start

### Load All Free Tools

```python
from cmbagent.external_tools.ag2_free_tools import load_all_free_tools

# Load all available free tools
tools = load_all_free_tools()

print(f"Loaded {len(tools['langchain'])} LangChain tools")
print(f"Loaded {len(tools['crewai'])} CrewAI tools")
```

### Load Specific Tools

```python
from cmbagent.external_tools.ag2_free_tools import (
    load_langchain_free_tools,
    load_crewai_free_tools
)

# Load only search tools from LangChain
search_tools = load_langchain_free_tools(['duckduckgo', 'wikipedia', 'arxiv'])

# Load only file tools from CrewAI
file_tools = load_crewai_free_tools(['file_read', 'file_write', 'directory_read'])
```

---

## Usage Examples

### Example 1: Single Agent with Tools

```python
import os
from dotenv import load_dotenv
from autogen import UserProxyAgent, ConversableAgent, LLMConfig
from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader

load_dotenv()

# Configure LLM
llm_config = LLMConfig(
    config_list=[{
        "model": "gpt-4o-mini",
        "api_key": os.getenv("OPENAI_API_KEY"),
        "api_type": "openai",
    }]
)

# Load tools
loader = AG2FreeToolsLoader()
all_tools = loader.load_all_free_tools()
combined_tools = loader.get_combined_tool_list()

# Create agent
assistant = ConversableAgent(
    name="research_assistant",
    system_message="You are a helpful research assistant with access to various tools.",
    llm_config=llm_config,
)

# Register tools
for tool in combined_tools:
    assistant.register_for_llm()(tool)

# Create user proxy
user_proxy = UserProxyAgent(
    name="user",
    human_input_mode="NEVER",
    code_execution_config={"use_docker": False, "work_dir": "workspace"},
)

for tool in combined_tools:
    user_proxy.register_for_execution()(tool)

# Use the agent
user_proxy.initiate_chat(
    assistant,
    message="Search Wikipedia for 'Cosmic Microwave Background' and summarize it.",
)
```

### Example 2: Different Tools for Different Agents

```python
from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader

loader = AG2FreeToolsLoader()

# Researcher gets search tools
research_tools = loader.load_langchain_tools(['duckduckgo', 'wikipedia', 'arxiv'])

# Coder gets file and code tools
code_tools = loader.load_crewai_tools(['file_read', 'file_write', 'code_interpreter'])

# Create and configure agents separately
researcher = ConversableAgent(
    name="researcher",
    system_message="You find information using search tools.",
    llm_config=llm_config,
)

for tool in research_tools:
    researcher.register_for_llm()(tool)

coder = ConversableAgent(
    name="coder",
    system_message="You work with files and code.",
    llm_config=llm_config,
)

for tool in code_tools:
    coder.register_for_llm()(tool)
```

### Example 3: With CaptainAgent

```python
from autogen.agentchat.contrib.captainagent import CaptainAgent
from autogen import UserProxyAgent, LLMConfig
from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader

# Load tools
loader = AG2FreeToolsLoader()
all_tools = loader.load_all_free_tools()
combined_tools = loader.get_combined_tool_list()

# Create CaptainAgent with tools
captain_agent = CaptainAgent(
    name="captain_agent",
    code_execution_config={"use_docker": False, "work_dir": "workspace"},
    tool_lib=combined_tools,  # Pass tools here!
    llm_config=llm_config,
)

captain_user_proxy = UserProxyAgent(
    name="captain_user_proxy",
    human_input_mode="NEVER"
)

# Use CaptainAgent
result = captain_user_proxy.initiate_chat(
    captain_agent,
    message="Research quantum computing on Wikipedia and save a summary to file.",
)
```

---

## Integration with CMBAgent

### Method 1: Using Integration Helpers

```python
from cmbagent import CMBAgent
from cmbagent.external_tools.integration_helpers import register_external_tools_with_agents

# Initialize your CMBAgent
agent = CMBAgent(
    name="research_agent",
    # ... your parameters
)

# Register tools with your agents
registry = register_external_tools_with_agents(
    cmbagent_instance=agent,
    use_crewai_tools=True,
    use_langchain_tools=True,
    agent_names=['engineer', 'researcher', 'planner']
)

print(f"Registered {len(registry.list_tools())} tools")
```

### Method 2: Direct Integration

```python
from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader

# Load tools
loader = AG2FreeToolsLoader()
all_tools = loader.load_all_free_tools()

# Get your CMBAgent agents
engineer = agent.get_agent_from_name('engineer')
researcher = agent.get_agent_from_name('researcher')

# Register tools
combined_tools = loader.get_combined_tool_list()
for tool in combined_tools:
    engineer.register_for_llm()(tool)
    researcher.register_for_llm()(tool)
```

### Method 3: Selective Tool Assignment

```python
from cmbagent.external_tools.integration_helpers import register_specific_external_tools

# Give specific tools to specific agents
register_specific_external_tools(
    cmbagent_instance=agent,
    tool_names=['WikipediaQueryRun', 'ArxivQueryRun', 'DuckDuckGoSearchRun'],
    agent_names=['researcher']
)
```

---

## Advanced Usage

### Custom Tool Loading

```python
from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader

loader = AG2FreeToolsLoader()

# Load only what you need
search_tools = loader.load_langchain_tools(['duckduckgo', 'wikipedia'])
file_tools = loader.load_crewai_tools(['file_read', 'directory_read'])

# Combine as needed
my_tools = search_tools + file_tools
```

### Tool Categories

Organize tools by purpose:

```python
# Research tools
research_tools = loader.load_langchain_tools(['duckduckgo', 'wikipedia', 'arxiv'])

# File management tools
file_tools = loader.load_crewai_tools(['file_read', 'file_write', 'directory_read'])

# Code tools
code_tools = loader.load_crewai_tools(['code_interpreter', 'code_docs'])

# Web tools
web_tools = loader.load_crewai_tools(['scrape_website', 'website_search'])
```

### Error Handling

```python
from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader
import warnings

try:
    loader = AG2FreeToolsLoader()
    tools = loader.load_all_free_tools()
except Exception as e:
    print(f"Error loading tools: {e}")
    # Fallback to specific tools
    tools = loader.load_langchain_tools(['duckduckgo'])
```

---

## Troubleshooting

### Issue: "autogen.interop not available"

**Solution**: Install interoperability support

```bash
pip install -U "ag2[interop-langchain,interop-crewai]"
```

### Issue: "Could not import DuckDuckGo"

**Solution**: Install the duckduckgo-search package

```bash
pip install duckduckgo-search
```

### Issue: "Could not load Wikipedia"

**Solution**: Install the wikipedia package

```bash
pip install wikipedia
```

### Issue: "Could not load CrewAI tools"

**Solution**: Install CrewAI with tools extra

```bash
pip install 'crewai[tools]'
```

### Issue: Tools not working with agents

**Solution**: Make sure to register tools both for LLM and execution:

```python
# Register for LLM (agent decides when to use)
for tool in tools:
    agent.register_for_llm()(tool)

# Register for execution (user_proxy executes)
for tool in tools:
    user_proxy.register_for_execution()(tool)
```

### Issue: "No API key found"

**Solution**: Set your OpenAI API key

```bash
export OPENAI_API_KEY='your-key-here'
```

Or create a `.env` file:

```
OPENAI_API_KEY=your-key-here
```

---

## Testing Your Setup

Run the example script:

```bash
cd /srv/projects/mas/mars/denario/cmbagent
python examples/ag2_free_tools_example.py
```

Or test manually:

```python
from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader

loader = AG2FreeToolsLoader()

print("Testing LangChain tools...")
lc_tools = loader.load_langchain_tools()

print("Testing CrewAI tools...")
ca_tools = loader.load_crewai_tools()

print(f"\n✓ Success! Loaded {len(lc_tools) + len(ca_tools)} tools total")
```

---

## Additional Resources

- [AG2 Documentation](https://docs.ag2.ai/latest/)
- [AG2 CaptainAgent Cross-Tool Tutorial](https://docs.ag2.ai/latest/docs/use-cases/notebooks/notebooks/agentchat_captainagent_crosstool/)
- [LangChain Tools](https://python.langchain.com/docs/modules/tools)
- [CrewAI Tools](https://github.com/crewAIInc/crewAI-tools)

---

## Summary

You now have access to **20+ free tools** from LangChain and CrewAI that can be used with your AG2 agents:

✓ **Search Tools**: DuckDuckGo, Wikipedia, ArXiv  
✓ **File Tools**: Read, write, search files  
✓ **Web Tools**: Scrape websites, search content  
✓ **Code Tools**: Interpret code, search documentation  
✓ **And more!**

All tools are converted automatically using AG2's native `Interoperability` module for seamless integration.

Happy building! 🚀
