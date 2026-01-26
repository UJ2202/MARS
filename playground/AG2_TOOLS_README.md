# AG2 Free Tools Integration

🚀 Complete integration of **20+ free tools** from LangChain and CrewAI into your AG2 agents!

## What's Included

### LangChain Tools (8 tools)
- 🔍 **DuckDuckGo Search** - Web search without API keys
- 📚 **Wikipedia** - Access to Wikipedia articles
- 📄 **ArXiv** - Search scientific papers
- 🐍 **Python REPL** - Execute Python code
- 📁 **File Operations** - Read, write, list files
- 👤 **Human Input** - Interactive input

### CrewAI Tools (12+ tools)
- 🌐 **Web Scraping** - Extract website content
- 📂 **File Management** - Advanced file operations
- 💻 **Code Analysis** - Code interpretation and documentation
- 🔎 **Search Tools** - JSON, CSV, PDF, TXT search
- 🌍 **Website Search** - Search within websites

## Quick Installation

```bash
# Option 1: Use the installation script
chmod +x install_ag2_tools.sh
./install_ag2_tools.sh

# Option 2: Install with pip
pip install -e ".[external-tools]"

# Option 3: Manual installation
pip install -U "ag2[openai,interop-langchain,interop-crewai,duckduckgo]"
pip install langchain-community crewai[tools]
pip install duckduckgo-search wikipedia arxiv
```

## Quick Start

### Load All Tools

```python
from cmbagent.external_tools.ag2_free_tools import load_all_free_tools

# Load all available free tools
tools = load_all_free_tools()
# Returns: {'langchain': [...], 'crewai': [...]}
```

### Use with AG2 Agents

```python
from autogen import ConversableAgent, UserProxyAgent, LLMConfig
from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader

# Load tools
loader = AG2FreeToolsLoader()
all_tools = loader.load_all_free_tools()
combined_tools = loader.get_combined_tool_list()

# Create agent with tools
llm_config = LLMConfig(
    config_list=[{
        "model": "gpt-4o-mini",
        "api_key": "your-key-here",
        "api_type": "openai",
    }]
)

assistant = ConversableAgent(
    name="research_assistant",
    system_message="You are a helpful assistant with access to tools.",
    llm_config=llm_config,
)

# Register tools
for tool in combined_tools:
    assistant.register_for_llm()(tool)

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
    message="Search Wikipedia for 'Artificial Intelligence' and summarize.",
)
```

### Use with CaptainAgent

```python
from autogen.agentchat.contrib.captainagent import CaptainAgent
from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader

loader = AG2FreeToolsLoader()
tools = loader.load_all_free_tools()
combined_tools = loader.get_combined_tool_list()

captain = CaptainAgent(
    name="captain",
    code_execution_config={"use_docker": False, "work_dir": "workspace"},
    tool_lib=combined_tools,  # Pass tools here!
    llm_config=llm_config,
)
```

## Examples

Run the comprehensive examples:

```bash
python examples/ag2_free_tools_example.py
```

Examples include:
1. Basic single agent with all tools
2. Different tools for different agents
3. CaptainAgent integration
4. CMBAgent system integration

## Documentation

📖 **Full Guide**: [docs/AG2_FREE_TOOLS_GUIDE.md](docs/AG2_FREE_TOOLS_GUIDE.md)

The guide includes:
- Complete tool list with descriptions
- Installation instructions
- Usage examples
- Integration patterns
- Troubleshooting
- Best practices

## Architecture

This integration uses AG2's native `Interoperability` module as shown in the [official AG2 documentation](https://docs.ag2.ai/latest/docs/use-cases/notebooks/notebooks/agentchat_captainagent_crosstool/).

```
┌─────────────────────────────────────────┐
│         AG2 Agents                      │
│  (Your conversable agents)              │
└────────────────┬────────────────────────┘
                 │
                 │ register_for_llm()
                 │ register_for_execution()
                 │
┌────────────────┴────────────────────────┐
│   AG2 Interoperability Module          │
│   (Native AG2 tool conversion)         │
└────────────────┬────────────────────────┘
                 │
        ┌────────┴──────────┐
        │                   │
┌───────▼────────┐  ┌──────▼────────┐
│ LangChain      │  │  CrewAI       │
│ Free Tools     │  │  Free Tools   │
│ (8 tools)      │  │  (12+ tools)  │
└────────────────┘  └───────────────┘
```

## Benefits

✅ **No API Keys Required** - All tools are completely free  
✅ **Native AG2 Integration** - Uses official Interoperability module  
✅ **Easy to Use** - Simple API, just load and register  
✅ **Extensible** - Easy to add more tools  
✅ **Well Documented** - Comprehensive guides and examples  

## Supported Tools

### Search & Research
- DuckDuckGo Search (LangChain)
- Wikipedia (LangChain)
- ArXiv Papers (LangChain)
- Website Search (CrewAI)

### File Operations
- Read/Write Files (both)
- List Directories (LangChain)
- Directory Search (CrewAI)
- TXT/JSON/CSV/PDF Search (CrewAI)

### Code & Development
- Python REPL (LangChain)
- Code Interpreter (CrewAI)
- Code Documentation Search (CrewAI)

### Web
- Web Scraping (CrewAI)
- Website Content Search (CrewAI)

### Interactive
- Human Input (LangChain)

## Requirements

- Python >= 3.12
- ag2[openai] >= 0.10.3
- ag2[interop-langchain,interop-crewai]
- langchain-community
- crewai[tools]
- duckduckgo-search
- wikipedia
- arxiv

## Contributing

Found a bug or want to add more tools? Contributions are welcome!

## License

Apache-2.0 (same as CMBAgent)

## Support

- 📚 [Full Documentation](docs/AG2_FREE_TOOLS_GUIDE.md)
- 🐛 [Report Issues](https://github.com/CMBAgents/cmbagent/issues)
- 💬 [Discussions](https://github.com/CMBAgents/cmbagent/discussions)

## Acknowledgments

Based on the [AG2 CaptainAgent Cross-Tool Tutorial](https://docs.ag2.ai/latest/docs/use-cases/notebooks/notebooks/agentchat_captainagent_crosstool/)

---

**Ready to supercharge your AG2 agents with 20+ free tools?** 🚀

Start with: `./install_ag2_tools.sh`
