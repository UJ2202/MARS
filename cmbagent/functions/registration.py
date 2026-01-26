"""Main coordinator for registering all functions to agents."""

from ..cmbagent_utils import cmbagent_disable_display
from .ideas import setup_idea_functions
from .keywords import setup_keyword_functions
from .planning import setup_planning_functions
from .execution_control import setup_execution_control_functions
from .status import setup_status_functions


def register_functions_to_agents(cmbagent_instance):
    """
    This function registers the functions to the agents.
    """
    task_recorder = cmbagent_instance.get_agent_from_name('task_recorder')
    task_improver = cmbagent_instance.get_agent_from_name('task_improver')
    planner = cmbagent_instance.get_agent_from_name('planner')
    planner_response_formatter = cmbagent_instance.get_agent_from_name('planner_response_formatter')
    plan_recorder = cmbagent_instance.get_agent_from_name('plan_recorder')
    plan_reviewer = cmbagent_instance.get_agent_from_name('plan_reviewer')
    reviewer_response_formatter = cmbagent_instance.get_agent_from_name('reviewer_response_formatter')
    review_recorder = cmbagent_instance.get_agent_from_name('review_recorder')
    researcher = cmbagent_instance.get_agent_from_name('researcher')
    researcher_response_formatter = cmbagent_instance.get_agent_from_name('researcher_response_formatter')
    web_surfer = cmbagent_instance.get_agent_from_name('web_surfer')
    retrieve_assistant = cmbagent_instance.get_agent_from_name('retrieve_assistant')
    engineer = cmbagent_instance.get_agent_from_name('engineer')
    engineer_response_formatter = cmbagent_instance.get_agent_from_name('engineer_response_formatter')

    executor = cmbagent_instance.get_agent_from_name('executor')
    executor_response_formatter = cmbagent_instance.get_agent_from_name('executor_response_formatter')
    terminator = cmbagent_instance.get_agent_from_name('terminator')
    control = cmbagent_instance.get_agent_from_name('control')
    admin = cmbagent_instance.get_agent_from_name('admin')
    perplexity = cmbagent_instance.get_agent_from_name('perplexity')
    aas_keyword_finder = cmbagent_instance.get_agent_from_name('aas_keyword_finder')
    plan_setter = cmbagent_instance.get_agent_from_name('plan_setter')
    idea_maker = cmbagent_instance.get_agent_from_name('idea_maker')
    installer = cmbagent_instance.get_agent_from_name('installer')
    idea_saver = cmbagent_instance.get_agent_from_name('idea_saver')
    control_starter = cmbagent_instance.get_agent_from_name('control_starter')
    camb_context = cmbagent_instance.get_agent_from_name('camb_context')
    classy_context = cmbagent_instance.get_agent_from_name('classy_context')
    plot_judge = cmbagent_instance.get_agent_from_name('plot_judge')
    plot_debugger = cmbagent_instance.get_agent_from_name('plot_debugger')
    
    if not cmbagent_instance.skip_rag_agents:
        classy_sz = cmbagent_instance.get_agent_from_name('classy_sz_agent')
        classy_sz_response_formatter = cmbagent_instance.get_agent_from_name('classy_sz_response_formatter')
        camb = cmbagent_instance.get_agent_from_name('camb_agent')
        camb_response_formatter = cmbagent_instance.get_agent_from_name('camb_response_formatter')
        planck = cmbagent_instance.get_agent_from_name('planck_agent')

    # =============================================================================
    # AG2 FREE TOOLS INTEGRATION - Load all free tools from LangChain and CrewAI
    # =============================================================================
    if getattr(cmbagent_instance, 'enable_ag2_free_tools', True):
        try:
            from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader
            
            print("\n" + "="*70)
            print("Loading AG2 Free Tools for all agents...")
            print("="*70)
            
            # Initialize the loader
            loader = AG2FreeToolsLoader()
            
            # Load all free tools (both LangChain and CrewAI)
            all_tools = loader.load_all_free_tools()
            combined_tools = loader.get_combined_tool_list()
            
            if combined_tools:
                print(f"\n✓ Loaded {len(combined_tools)} free tools total")
                print("  Registering with all agents...")
                
                # List of agents that should have access to external tools
                agents_for_tools = [
                    planner, researcher, web_surfer, retrieve_assistant, engineer, executor, control, admin,
                    task_recorder, task_improver, plan_recorder, plan_reviewer,
                    review_recorder, installer, idea_maker, idea_saver,
                    camb_context, classy_context, plot_judge, plot_debugger,
                ]
                
                # Add RAG agents if available
                if not cmbagent_instance.skip_rag_agents:
                    agents_for_tools.extend([classy_sz, camb, planck])
                
                # Register tools with all agents
                for agent in agents_for_tools:
                    try:
                        for tool in combined_tools:
                            agent.register_for_llm()(tool)
                    except Exception as e:
                        print(f"  ⚠ Could not register tools with {agent.name}: {e}")
                
                # Register tools for execution with executor
                try:
                    for tool in combined_tools:
                        executor.register_for_execution()(tool)
                    print(f"  ✓ Registered {len(combined_tools)} tools for execution with executor")
                except Exception as e:
                    print(f"  ⚠ Could not register tools for execution: {e}")
                
                print("="*70 + "\n")
            else:
                print("  ⚠ No tools loaded. Install dependencies with: pip install -e '.[external-tools]'")
                print("="*70 + "\n")
                
        except ImportError as e:
            print(f"\n⚠ AG2 free tools not available: {e}")
            print("  Install with: pip install -e '.[external-tools]'")
            print("  Or: ./install_ag2_tools.sh\n")
        except Exception as e:
            print(f"\n⚠ Error loading AG2 free tools: {e}")
            print("  Continuing without external tools...\n")
    else:
        print("\n⚠ AG2 free tools disabled (enable_ag2_free_tools=False)\n")
    
    # =============================================================================
    # END AG2 FREE TOOLS INTEGRATION
    # =============================================================================

    # =============================================================================
    # MCP CLIENT INTEGRATION - Connect to external MCP servers
    # =============================================================================
    if getattr(cmbagent_instance, 'enable_mcp_client', False) and cmbagent_instance.mcp_tool_integration:
        try:
            print("\n" + "="*70)
            print("Registering MCP Tools with all agents...")
            print("="*70)
            
            # Get all discovered MCP tools
            mcp_tools = cmbagent_instance.mcp_client_manager.get_all_tools()
            
            if mcp_tools:
                print(f"\n✓ Discovered {len(mcp_tools)} MCP tools")
                
                # Group by server for display
                tools_by_server = {}
                for tool in mcp_tools:
                    server = tool['server_name']
                    if server not in tools_by_server:
                        tools_by_server[server] = []
                    tools_by_server[server].append(tool['name'])
                
                for server_name, tool_names in tools_by_server.items():
                    print(f"  {server_name}: {len(tool_names)} tools")
                
                # List of agents that should have access to MCP tools
                agents_for_mcp = [
                    planner, researcher, web_surfer, retrieve_assistant, engineer, executor, control, admin,
                    task_recorder, task_improver, plan_recorder, plan_reviewer,
                    review_recorder, installer, idea_maker, idea_saver,
                    camb_context, classy_context, plot_judge, plot_debugger,
                ]
                
                # Add RAG agents if available
                if not cmbagent_instance.skip_rag_agents:
                    agents_for_mcp.extend([classy_sz, camb, planck])
                
                # Register MCP tools with all agents
                total_registered = 0
                for agent in agents_for_mcp:
                    try:
                        count = cmbagent_instance.mcp_tool_integration.register_tools_with_agent(agent)
                        total_registered += count
                    except Exception as e:
                        print(f"  ⚠ Could not register MCP tools with {agent.name}: {e}")
                
                print(f"  ✓ Registered MCP tools with {len(agents_for_mcp)} agents")
                print("="*70 + "\n")
            else:
                print("  ⚠ No MCP tools discovered. Check server configuration.")
                print("="*70 + "\n")
                
        except Exception as e:
            print(f"\n⚠ Error registering MCP tools: {e}")
            print("  Continuing without MCP tools...\n")
    elif getattr(cmbagent_instance, 'enable_mcp_client', False):
        print("\n⚠ MCP client enabled but not initialized properly")
        print("  Check MCP configuration and dependencies\n")
    # =============================================================================
    # END MCP CLIENT INTEGRATION
    # =============================================================================

    # Register all modular functions
    setup_idea_functions(cmbagent_instance)
    setup_keyword_functions(cmbagent_instance)
    setup_planning_functions(cmbagent_instance, cmbagent_disable_display)
    setup_execution_control_functions(cmbagent_instance)
    setup_status_functions(cmbagent_instance)
