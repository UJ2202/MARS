"""
Example: Using CMBAgent with MCP Tools

This example shows how to use MCP tools in your CMBAgent workflows.
Once MCP is enabled, agents automatically have access to external tools.
"""

import os
from dotenv import load_dotenv

# Load API keys from .env
load_dotenv()

from cmbagent import CMBAgent

def main():
    print("="*70)
    print("CMBAgent with MCP Tools - Example Workflow")
    print("="*70)
    
    # API keys from environment
    api_keys = {
        "OPENAI": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC": os.getenv("ANTHROPIC_API_KEY"),
    }
    
    # Initialize CMBAgent with MCP enabled
    print("\n1. Initializing CMBAgent with MCP enabled...")
    agent = CMBAgent(
        work_dir="./example_mcp_workflow",
        mode="planning_and_control",
        enable_mcp_client=True,  # ← Enable MCP
        enable_ag2_free_tools=True,  # Also keep free tools
        skip_rag_agents=True,  # For faster demo
        verbose=True,
        api_keys=api_keys,
    )
    
    print("\n2. Checking available tools...")
    if agent.mcp_client_manager:
        mcp_tools = agent.mcp_client_manager.get_all_tools()
        print(f"   MCP tools available: {len(mcp_tools)}")
        
        if mcp_tools:
            print("\n   Available MCP servers and tools:")
            tools_by_server = {}
            for tool in mcp_tools:
                server = tool['server_name']
                if server not in tools_by_server:
                    tools_by_server[server] = []
                tools_by_server[server].append(tool['name'])
            
            for server, tools in tools_by_server.items():
                print(f"\n   {server}:")
                for tool_name in tools:
                    print(f"      - {tool_name}")
    
    # Example tasks that can use MCP tools
    print("\n3. Example tasks you can now run:")
    print("="*70)
    
    examples = [
        {
            "name": "File Operations (MCP Filesystem)",
            "task": """
            Read the contents of /tmp/test.txt and 
            create a summary in /tmp/summary.txt
            """,
            "requires": "filesystem server enabled"
        },
        {
            "name": "GitHub Operations (MCP GitHub)",
            "task": """
            Search GitHub for 'model-context-protocol' repositories,
            clone the top result, and analyze its README
            """,
            "requires": "github server + GITHUB_TOKEN"
        },
        {
            "name": "Web Search (AG2 Free Tools + MCP)",
            "task": """
            Search for latest CMB papers on ArXiv,
            download the top 3, and save summaries to files
            """,
            "requires": "AG2 free tools (already available)"
        },
        {
            "name": "Combined Workflow",
            "task": """
            1. Search DuckDuckGo for "cosmic microwave background"
            2. Save results to /tmp/cmb_search.txt
            3. Read the file and create a summary
            4. Post summary to a report file
            """,
            "requires": "AG2 free tools + filesystem server"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\nExample {i}: {example['name']}")
        print(f"  Requires: {example['requires']}")
        print(f"  Task: {example['task'].strip()}")
    
    print("\n" + "="*70)
    print("To run a task:")
    print("="*70)
    print("""
    result = agent.solve(
        task="Your task here",
        max_rounds=30
    )
    
    # Or use one_shot mode:
    result = agent.one_shot(
        task="Your task here",
        agent="researcher"  # or "engineer", "planner", etc.
    )
    """)
    
    print("\n" + "="*70)
    print("Configuration:")
    print("="*70)
    print(f"  Work directory: {agent.work_dir}")
    print(f"  MCP enabled: {agent.enable_mcp_client}")
    print(f"  AG2 free tools: {agent.enable_ag2_free_tools}")
    print(f"  MCP servers connected: {len(agent.mcp_client_manager.sessions) if agent.mcp_client_manager else 0}")
    
    # Cleanup
    print("\n4. Cleaning up...")
    import shutil
    shutil.rmtree("./example_mcp_workflow", ignore_errors=True)
    
    print("\n" + "="*70)
    print("Setup complete! Your agents now have access to:")
    print("  • 21+ AG2 free tools (DuckDuckGo, Wikipedia, ArXiv, etc.)")
    print("  • MCP tools (filesystem, GitHub, etc.)")
    print("  • All standard CMBAgent capabilities")
    print("="*70)


if __name__ == "__main__":
    main()
