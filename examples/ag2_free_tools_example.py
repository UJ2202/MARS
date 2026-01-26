"""
Example: Using Free Tools from LangChain and CrewAI with AG2 Agents

This script demonstrates how to integrate all free tools from LangChain
and CrewAI frameworks into AG2 agents using the native Interoperability module.

Based on AG2 documentation:
https://docs.ag2.ai/latest/docs/use-cases/notebooks/notebooks/agentchat_captainagent_crosstool/

Installation:
    pip install -e ".[external-tools]"
    
Or manually:
    pip install ag2[openai,interop-langchain,interop-crewai,duckduckgo]
    pip install langchain-community crewai[tools] duckduckgo-search wikipedia arxiv
"""

import os
from dotenv import load_dotenv
from autogen import UserProxyAgent, ConversableAgent, LLMConfig
from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader, load_all_free_tools

# Load environment variables
load_dotenv()


def example_1_basic_usage():
    """
    Example 1: Basic usage - Load all free tools and use with a single agent.
    """
    print("\n" + "="*70)
    print("Example 1: Basic Usage - Single Agent with All Free Tools")
    print("="*70 + "\n")
    
    # Configure LLM
    llm_config = LLMConfig(
        config_list=[
            {
                "model": "gpt-4o-mini",
                "api_key": os.getenv("OPENAI_API_KEY"),
                "api_type": "openai",
            }
        ]
    )
    
    # Load all free tools
    loader = AG2FreeToolsLoader()
    all_tools = loader.load_all_free_tools()
    
    # Get combined tool list
    combined_tools = loader.get_combined_tool_list()
    
    # Create agent with tools
    assistant = ConversableAgent(
        name="research_assistant",
        system_message="You are a helpful research assistant with access to various tools. "
                      "Use the tools available to answer questions accurately.",
        llm_config=llm_config,
    )
    
    # Register tools with the agent
    for tool in combined_tools:
        assistant.register_for_llm()(tool)
    
    # Create user proxy
    user_proxy = UserProxyAgent(
        name="user",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=5,
        code_execution_config={"use_docker": False, "work_dir": "workspace"},
    )
    
    # Register tools for execution
    for tool in combined_tools:
        user_proxy.register_for_execution()(tool)
    
    # Test the agent
    user_proxy.initiate_chat(
        assistant,
        message="Search Wikipedia for 'Cosmic Microwave Background' and give me a brief summary.",
    )


def example_2_selective_tools():
    """
    Example 2: Load only specific tools for different agents.
    """
    print("\n" + "="*70)
    print("Example 2: Selective Tools - Different Tools for Different Agents")
    print("="*70 + "\n")
    
    # Configure LLM
    llm_config = LLMConfig(
        config_list=[
            {
                "model": "gpt-4o-mini",
                "api_key": os.getenv("OPENAI_API_KEY"),
                "api_type": "openai",
            }
        ]
    )
    
    # Load specific LangChain tools for researcher
    loader = AG2FreeToolsLoader()
    research_tools = loader.load_langchain_tools(
        tool_names=['duckduckgo', 'wikipedia', 'arxiv']
    )
    
    # Load specific CrewAI tools for coder
    code_tools = loader.load_crewai_tools(
        tool_names=['file_read', 'file_write', 'code_interpreter']
    )
    
    # Create researcher agent with search tools
    researcher = ConversableAgent(
        name="researcher",
        system_message="You are a researcher who finds information using search tools.",
        llm_config=llm_config,
    )
    
    for tool in research_tools:
        researcher.register_for_llm()(tool)
    
    # Create coder agent with file/code tools
    coder = ConversableAgent(
        name="coder",
        system_message="You are a coder who works with files and interprets code.",
        llm_config=llm_config,
    )
    
    for tool in code_tools:
        coder.register_for_llm()(tool)
    
    # Create user proxy for both
    user_proxy = UserProxyAgent(
        name="user",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=5,
        code_execution_config={"use_docker": False, "work_dir": "workspace"},
    )
    
    # Register all tools for execution
    for tool in research_tools + code_tools:
        user_proxy.register_for_execution()(tool)
    
    # Test researcher
    print("\n--- Testing Researcher Agent ---")
    user_proxy.initiate_chat(
        researcher,
        message="Search for recent papers on arXiv about 'large language models'.",
    )
    
    # Test coder
    print("\n--- Testing Coder Agent ---")
    user_proxy.initiate_chat(
        coder,
        message="List the files in the current directory.",
    )


def example_3_with_captain_agent():
    """
    Example 3: Use with CaptainAgent (if available in your codebase).
    
    This shows how to pass tools to CaptainAgent following the AG2 documentation.
    """
    print("\n" + "="*70)
    print("Example 3: Using Tools with CaptainAgent (Advanced)")
    print("="*70 + "\n")
    
    try:
        from autogen.agentchat.contrib.captainagent import CaptainAgent
        
        # Configure LLM
        llm_config = LLMConfig(
            config_list=[
                {
                    "model": "gpt-4o-mini",
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "api_type": "openai",
                }
            ]
        )
        
        # Load all free tools
        loader = AG2FreeToolsLoader()
        all_tools = loader.load_all_free_tools()
        combined_tools = loader.get_combined_tool_list()
        
        # Create CaptainAgent with tools
        # The key difference: pass tools to tool_lib argument
        captain_agent = CaptainAgent(
            name="captain_agent",
            code_execution_config={"use_docker": False, "work_dir": "workspace"},
            tool_lib=combined_tools,  # Pass all converted tools here
            llm_config=llm_config,
        )
        
        captain_user_proxy = UserProxyAgent(
            name="captain_user_proxy",
            human_input_mode="NEVER"
        )
        
        # Test with a complex task
        result = captain_user_proxy.initiate_chat(
            captain_agent,
            message="Search Wikipedia for 'Quantum Computing', then use that information "
                   "to write a brief summary to a file called 'quantum_summary.txt'.",
        )
        
        print(f"\n--- Result Summary ---")
        print(result.summary)
        
    except ImportError:
        print("⚠ CaptainAgent not available. Install with: pip install ag2[captainagent]")
        print("  Or use Example 1 or 2 for standard agents.")


def example_4_integration_with_cmbagent():
    """
    Example 4: Integration with your existing CMBAgent system.
    
    This shows how to integrate the tools into your CMBAgent workflow.
    """
    print("\n" + "="*70)
    print("Example 4: Integration with CMBAgent System")
    print("="*70 + "\n")
    
    try:
        # Import your CMBAgent
        from cmbagent import CMBAgent
        from cmbagent.external_tools.integration_helpers import register_external_tools_with_agents
        
        # Initialize CMBAgent (adjust parameters as needed)
        agent = CMBAgent(
            name="research_agent",
            # ... your other parameters
        )
        
        # Register external tools with CMBAgent agents
        registry = register_external_tools_with_agents(
            cmbagent_instance=agent,
            use_crewai_tools=True,
            use_langchain_tools=True,
            agent_names=['engineer', 'researcher', 'planner']  # Your agent names
        )
        
        print("✓ Successfully integrated tools with CMBAgent")
        print(f"  Total tools registered: {len(registry.list_tools())}")
        
    except ImportError as e:
        print(f"⚠ Could not import CMBAgent: {e}")
        print("  This example is for integration with your existing CMBAgent system.")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("AG2 Free Tools Integration Examples")
    print("Based on: https://docs.ag2.ai/latest/docs/use-cases/notebooks/")
    print("          notebooks/agentchat_captainagent_crosstool/")
    print("="*70)
    
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠ WARNING: OPENAI_API_KEY not set in environment!")
        print("  Set it with: export OPENAI_API_KEY='your-key-here'")
        print("  Or add it to .env file")
        return
    
    # Run examples
    try:
        example_1_basic_usage()
    except Exception as e:
        print(f"Example 1 failed: {e}")
    
    try:
        example_2_selective_tools()
    except Exception as e:
        print(f"Example 2 failed: {e}")
    
    try:
        example_3_with_captain_agent()
    except Exception as e:
        print(f"Example 3 failed: {e}")
    
    try:
        example_4_integration_with_cmbagent()
    except Exception as e:
        print(f"Example 4 failed: {e}")


if __name__ == "__main__":
    main()
