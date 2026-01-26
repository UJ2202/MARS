"""
AG2 Free Tools - Quick Reference

Import:
    from cmbagent.external_tools.ag2_free_tools import (
        AG2FreeToolsLoader,
        load_all_free_tools,
        load_langchain_free_tools,
        load_crewai_free_tools,
    )

Load All Tools:
    tools = load_all_free_tools()
    # Returns: {'langchain': [...], 'crewai': [...]}

Load Specific LangChain Tools:
    tools = load_langchain_free_tools([
        'duckduckgo',      # Web search
        'wikipedia',       # Wikipedia queries
        'arxiv',          # Scientific papers
        'python_repl',    # Execute Python
        'file_read',      # Read files
        'file_write',     # Write files
        'list_directory', # List files
        'human',          # Human input
    ])

Load Specific CrewAI Tools:
    tools = load_crewai_free_tools([
        'scrape_website',   # Scrape websites
        'file_read',        # Read files
        'file_write',       # Write files
        'directory_read',   # Read directories
        'code_docs',        # Code documentation
        'code_interpreter', # Interpret code
        'directory_search', # Search directories
        'txt_search',       # Search text files
        'json_search',      # Search JSON files
        'csv_search',       # Search CSV files
        'pdf_search',       # Search PDFs
        'website_search',   # Search websites
    ])

Use with AG2 Agents:
    from autogen import ConversableAgent, UserProxyAgent, LLMConfig
    
    # Load tools
    loader = AG2FreeToolsLoader()
    all_tools = loader.load_all_free_tools()
    combined = loader.get_combined_tool_list()
    
    # Create agent
    agent = ConversableAgent(
        name="assistant",
        system_message="You have access to tools.",
        llm_config=llm_config,
    )
    
    # Register tools
    for tool in combined:
        agent.register_for_llm()(tool)
    
    user_proxy = UserProxyAgent(
        name="user",
        human_input_mode="NEVER",
        code_execution_config={"use_docker": False},
    )
    
    for tool in combined:
        user_proxy.register_for_execution()(tool)
    
    # Use
    user_proxy.initiate_chat(agent, message="Your task here")

Use with CaptainAgent:
    from autogen.agentchat.contrib.captainagent import CaptainAgent
    
    loader = AG2FreeToolsLoader()
    tools = loader.get_combined_tool_list()
    
    captain = CaptainAgent(
        name="captain",
        tool_lib=tools,  # Pass tools here!
        llm_config=llm_config,
    )

Integration with CMBAgent:
    from cmbagent.external_tools.integration_helpers import (
        register_external_tools_with_agents
    )
    
    registry = register_external_tools_with_agents(
        cmbagent_instance=agent,
        use_crewai_tools=True,
        use_langchain_tools=True,
        agent_names=['engineer', 'researcher']
    )

Installation:
    # Quick install
    ./install_ag2_tools.sh
    
    # Or manually
    pip install -e ".[external-tools]"
    
    # Or step by step
    pip install -U "ag2[openai,interop-langchain,interop-crewai]"
    pip install langchain-community crewai[tools]
    pip install duckduckgo-search wikipedia arxiv

Test Setup:
    python test_ag2_tools_setup.py

Run Examples:
    python examples/ag2_free_tools_example.py

Documentation:
    - Quick Start: AG2_TOOLS_README.md
    - Full Guide: docs/AG2_FREE_TOOLS_GUIDE.md
    - Summary: AG2_TOOLS_INTEGRATION_SUMMARY.md

Troubleshooting:
    # Missing interop
    pip install -U "ag2[interop-langchain,interop-crewai]"
    
    # Missing LangChain tools
    pip install langchain-community
    
    # Missing CrewAI tools
    pip install 'crewai[tools]'
    
    # Missing search tools
    pip install duckduckgo-search wikipedia arxiv

Tool Categories:
    SEARCH & RESEARCH:
        - DuckDuckGo (LangChain)
        - Wikipedia (LangChain)
        - ArXiv (LangChain)
        - Website Search (CrewAI)
    
    FILE OPERATIONS:
        - File Read/Write (both)
        - List/Search Directories (both)
        - TXT/JSON/CSV/PDF Search (CrewAI)
    
    CODE & DEVELOPMENT:
        - Python REPL (LangChain)
        - Code Interpreter (CrewAI)
        - Code Docs Search (CrewAI)
    
    WEB:
        - Web Scraping (CrewAI)
        - Website Search (CrewAI)
    
    INTERACTIVE:
        - Human Input (LangChain)

Total: 20+ free tools, no API keys required!
"""
