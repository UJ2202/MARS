# Quick Reference: WebSurfer & RetrieveAssistant Agents

## Installation
```bash
pip install -e .
# or
pip install markdownify beautifulsoup4 pathvalidate
```

## Usage Examples

### WebSurfer - Browse the Web
```python
from cmbagent import CMBAgent

agent = CMBAgent(
    agent_list=['web_surfer', 'researcher'],
    api_keys={'OPENAI': 'your-key'}
)

result = agent.solve("Browse wikipedia.org and research black holes")
```

### RetrieveAssistant - RAG Search
```python
from cmbagent import CMBAgent

agent = CMBAgent(
    agent_list=['retrieve_assistant', 'researcher'],
    api_keys={'OPENAI': 'your-key'}
)

result = agent.solve("Search our docs for CMB power spectrum info")
```

### Both Together + 22 Tools
```python
from cmbagent import CMBAgent

agent = CMBAgent(
    mode='planning_and_control',
    agent_list=['web_surfer', 'retrieve_assistant', 'researcher', 'engineer'],
    api_keys={'OPENAI': 'your-key'},
    enable_ag2_free_tools=True  # Loads all 22 tools
)

result = agent.solve("""
    Research CMB analysis methods:
    1. Browse arXiv for recent papers
    2. Search local docs for existing methods
    3. Compare and summarize
""")
```

## Available in All Workflows

- `one_shot` - Single-shot tasks
- `chat` - Interactive conversations
- `planning_and_control` - Multi-agent planning
- `planning_and_control_context_carryover` - With context persistence

## Agent Names

Add these to `agent_list`:
- `'web_surfer'` - Web browsing agent
- `'retrieve_assistant'` - RAG agent

## Complete Integration

✓ **47 Agents** (45 existing + 2 new)  
✓ **22 Free Tools** (6 LangChain + 16 CrewAI)  
✓ **All Workflows** (one_shot, chat, planning_and_control)  
✓ **Auto-Discovery** (No manual registration)  

## Test
```bash
python test_new_agents_integration.py
```

## Documentation
- Full guide: `docs/WEBSURFER_AND_RETRIEVE_ASSISTANT.md`
- Summary: `INTEGRATION_SUMMARY.md`

## Support
Both agents have graceful fallback to regular AssistantAgent if dependencies are missing.
