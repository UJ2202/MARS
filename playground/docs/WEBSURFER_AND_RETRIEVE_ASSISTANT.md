# WebSurferAgent and RetrieveAssistantAgent Integration

## Overview

CMBAgent now includes two powerful specialized agents from AG2:

1. **WebSurferAgent** - Browse and extract information from websites
2. **RetrieveAssistantAgent** - Retrieval-Augmented Generation (RAG) capabilities

These agents are automatically discovered and can be used in any workflow alongside your existing agents.

## Installation

The required dependencies are included in the main installation:

```bash
pip install -e .
```

Or install dependencies manually:

```bash
pip install markdownify beautifulsoup4 pathvalidate
```

## Usage

### Using WebSurferAgent

The WebSurferAgent can browse websites and extract information:

```python
from cmbagent import CMBAgent

# Create CMBAgent with WebSurfer
agent = CMBAgent(
    mode='one_shot',
    agent_list=['web_surfer', 'researcher'],
    api_keys=api_keys,
    enable_ag2_free_tools=True
)

# Use in a task
result = agent.solve(
    task="Browse to wikipedia.org and research the Large Hadron Collider",
    max_rounds=20
)
```

### Using RetrieveAssistantAgent

The RetrieveAssistantAgent provides RAG capabilities:

```python
from cmbagent import CMBAgent

# Create CMBAgent with RetrieveAssistant
agent = CMBAgent(
    mode='one_shot',
    agent_list=['retrieve_assistant', 'researcher'],
    api_keys=api_keys,
    enable_ag2_free_tools=True
)

# Use in a task
result = agent.solve(
    task="Search for information about CMB and provide key findings",
    max_rounds=20
)
```

### Using Both Agents Together

You can combine both agents in planning_and_control workflow:

```python
from cmbagent import CMBAgent

# Create CMBAgent with both agents
agent = CMBAgent(
    mode='planning_and_control',
    agent_list=['web_surfer', 'retrieve_assistant', 'researcher', 'engineer'],
    api_keys=api_keys,
    enable_ag2_free_tools=True
)

# Use in a complex task
result = agent.solve(
    task="""
    Research recent CMB findings:
    1. Use web_surfer to browse for recent publications
    2. Use retrieve_assistant to search detailed information
    3. Summarize the findings
    """,
    max_rounds=30
)
```

### Using with Workflow Functions

The agents are also available when using workflow functions:

```python
from cmbagent.workflows import one_shot, planning_and_control_context_carryover

# One-shot with WebSurfer
result = one_shot(
    task="Browse NASA website for Mars mission updates",
    work_dir='./output',
    api_keys=api_keys,
    agent='web_surfer'
)

# Planning & Control with both agents
result = planning_and_control_context_carryover(
    task="Research and compile CMB data analysis methods",
    work_dir='./output',
    api_keys=api_keys
    # Both agents are available to be selected by the planner
)
```

## Agent Capabilities

### WebSurferAgent

**Capabilities:**
- Browse and navigate websites
- Extract text content from web pages
- Follow links and explore related content
- Handle dynamic web content
- Parse HTML and extract structured information

**Best for:**
- Researching online information
- Gathering data from websites
- Monitoring web content
- Accessing public APIs and documentation

**Example tasks:**
- "Browse arXiv.org and find recent papers on transformer models"
- "Go to the official Python documentation and explain list comprehensions"
- "Visit GitHub and check the latest releases of TensorFlow"

### RetrieveAssistantAgent

**Capabilities:**
- Retrieval-Augmented Generation (RAG)
- Search through document collections
- Semantic similarity search
- Context-aware information retrieval
- Citation and source tracking

**Best for:**
- Answering questions from knowledge bases
- Searching through documentation
- Finding relevant information in large corpora
- Providing cited, evidence-based responses

**Example tasks:**
- "Search our CMB documentation and explain the power spectrum calculation"
- "Find all mentions of 'lensing' in the research papers"
- "Retrieve examples of CLASS parameter files from the knowledge base"

## Agent Configuration

### WebSurferAgent Configuration

Located at `cmbagent/agents/web_surfer/web_surfer.yaml`:

```yaml
name: web_surfer
system_message: |
  You are a web browsing specialist. Your role is to:
  - Navigate and browse websites to gather information
  - Extract relevant data from web pages
  - Summarize web content for other agents
  - Search for information online when needed
```

### RetrieveAssistantAgent Configuration

Located at `cmbagent/agents/retrieve_assistant/retrieve_assistant.yaml`:

```yaml
name: retrieve_assistant
system_message: |
  You are a retrieval-augmented generation (RAG) specialist. Your role is to:
  - Retrieve relevant information from document collections
  - Answer questions using retrieved context
  - Search through knowledge bases efficiently
  - Provide citations and sources for your answers
```

## Integration with Existing Workflows

Both agents integrate seamlessly with existing workflows:

### One-Shot Workflow
```python
agent = CMBAgent(mode='one_shot', agent_list=['web_surfer'])
```

### Chat Workflow
```python
agent = CMBAgent(mode='chat', agent_list=['web_surfer', 'retrieve_assistant'])
```

### Planning & Control Workflow
```python
agent = CMBAgent(
    mode='planning_and_control',
    agent_list=['web_surfer', 'retrieve_assistant', 'planner', 'researcher', 'engineer']
)
```

### Planning & Control with Context Carryover
```python
agent = CMBAgent(
    mode='planning_and_control_context_carryover',
    agent_list=['web_surfer', 'retrieve_assistant', 'planner', 'researcher', 'engineer']
)
```

## Combining with Free Tools

Both agents work alongside the 22 free tools from LangChain and CrewAI:

```python
agent = CMBAgent(
    agent_list=['web_surfer', 'retrieve_assistant', 'researcher'],
    enable_ag2_free_tools=True  # Loads all 22 tools
)
```

This gives your agents access to:
- **WebSurferAgent** for web browsing
- **RetrieveAssistantAgent** for RAG
- **22 free tools** including Wikipedia, ArXiv, file operations, web scraping, etc.

## Testing

A comprehensive test suite is available:

```bash
python test_new_agents_integration.py
```

This tests:
1. Agent discovery (both agents are found)
2. WebSurferAgent instantiation
3. RetrieveAssistantAgent instantiation
4. Both agents working together

## Architecture

### File Structure

```
cmbagent/agents/
├── web_surfer/
│   ├── __init__.py
│   ├── web_surfer.py          # WebSurferAgent implementation
│   └── web_surfer.yaml        # Configuration
└── retrieve_assistant/
    ├── __init__.py
    ├── retrieve_assistant.py  # RetrieveAssistantAgent implementation
    └── retrieve_assistant.yaml # Configuration
```

### Automatic Discovery

Both agents are automatically discovered by the `import_non_rag_agents()` function, which:
1. Scans the `cmbagent/agents/` directory
2. Imports all Python files (except `__init__.py`)
3. Registers agent classes following the naming convention
4. Makes them available to all workflows

### Fallback Mechanism

Both agents have built-in fallback to regular `AssistantAgent` if:
- Required dependencies are not installed
- AG2 version doesn't support the feature
- Configuration issues occur

This ensures your workflows continue to work even if specialized features aren't available.

## Examples

### Example 1: Web Research Task

```python
from cmbagent import CMBAgent

agent = CMBAgent(
    mode='one_shot',
    agent_list=['web_surfer', 'researcher'],
    api_keys={'OPENAI': 'your-api-key'}
)

result = agent.solve(
    task="""
    Research the latest CMB observations:
    1. Browse to the Planck mission website
    2. Find recent press releases
    3. Summarize key findings
    """,
    max_rounds=25
)
```

### Example 2: RAG-Enhanced Research

```python
from cmbagent import CMBAgent

agent = CMBAgent(
    mode='one_shot',
    agent_list=['retrieve_assistant', 'researcher'],
    api_keys={'OPENAI': 'your-api-key'}
)

result = agent.solve(
    task="""
    Find all information about CMB lensing in our documentation:
    1. Search for 'lensing' in the knowledge base
    2. Retrieve relevant papers and documentation
    3. Provide a comprehensive summary with citations
    """,
    max_rounds=25
)
```

### Example 3: Combined Web & RAG Research

```python
from cmbagent import CMBAgent

agent = CMBAgent(
    mode='planning_and_control',
    agent_list=['web_surfer', 'retrieve_assistant', 'planner', 'researcher', 'engineer'],
    api_keys={'OPENAI': 'your-api-key'}
)

result = agent.solve(
    task="""
    Comprehensive CMB research task:
    1. Use web_surfer to find recent papers on arXiv
    2. Use retrieve_assistant to search our local documentation
    3. Compare findings from both sources
    4. Generate a summary report
    """,
    max_rounds=40
)
```

## Troubleshooting

### WebSurfer Dependencies Missing

If you see:
```
⚠ Could not create WebSurferAgent, falling back to AssistantAgent
```

Install dependencies:
```bash
pip install markdownify beautifulsoup4 pathvalidate
```

### API Keys Not Found

Ensure your `.env` file contains:
```bash
OPENAI_API_KEY=your-key-here
```

Or pass directly:
```python
agent = CMBAgent(
    api_keys={'OPENAI': 'your-api-key'}
)
```

### Agents Not Available in Workflow

The agents are available in all workflows. If you don't see them:

1. Check they're in agent_list:
   ```python
   agent = CMBAgent(agent_list=['web_surfer', 'retrieve_assistant'])
   ```

2. Verify they're discovered:
   ```python
   from cmbagent.managers.agent_manager import import_non_rag_agents
   agents = import_non_rag_agents()
   print('WebSurferAgent' in agents)  # Should be True
   ```

## Performance Considerations

- **WebSurferAgent**: Web browsing can be slow. Set appropriate timeouts.
- **RetrieveAssistantAgent**: RAG requires indexed documents. Pre-index for best performance.
- **Both**: Use with appropriate max_rounds to allow time for multi-step tasks.

## Future Enhancements

Potential future improvements:
- Custom browser configuration for WebSurfer
- Custom retrieval strategies for RetrieveAssistant
- Integration with vector databases
- Enhanced caching mechanisms
- Advanced web scraping capabilities

## Summary

✅ **WebSurferAgent** - Browse and extract web content  
✅ **RetrieveAssistantAgent** - RAG and semantic search  
✅ **22 Free Tools** - LangChain + CrewAI integration  
✅ **All Workflows** - one_shot, chat, planning_and_control  
✅ **Auto-Discovery** - No manual registration needed  
✅ **Graceful Fallback** - Works even without special dependencies  

Both agents are production-ready and can be used immediately in your CMBAgent workflows!
