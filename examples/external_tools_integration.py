"""
Example: Integrating CrewAI and LangChain Tools with CMBAgent

This example demonstrates how to integrate external tools from CrewAI and LangChain
into your CMBAgent planning and control workflow.

There are three main approaches:
1. Automatic integration - Load all available free tools
2. Selective integration - Choose specific tool categories
3. Custom integration - Add your own tools alongside external ones
"""

import os
from cmbagent import CMBAgent
from cmbagent.external_tools import (
    get_global_registry,
    get_crewai_free_tools,
    get_langchain_free_tools,
)
from cmbagent.external_tools.integration_helpers import (
    register_external_tools_with_agents,
    register_specific_external_tools,
    list_available_external_tools,
    add_custom_tool_to_registry,
)


# =============================================================================
# APPROACH 1: Automatic Integration with All Free Tools
# =============================================================================

def example_1_automatic_integration():
    """
    Load all available CrewAI and LangChain free tools automatically.
    
    This is the simplest approach - it loads all available tools and registers
    them with your commonly-used agents.
    """
    print("=" * 70)
    print("EXAMPLE 1: Automatic Integration")
    print("=" * 70)
    
    # Initialize CMBAgent as usual
    cmbagent = CMBAgent(
        work_dir="./cmbagent_with_external_tools",
        mode="planning_and_control",
        api_keys=os.environ,
    )
    
    # Register all external tools with default agents
    # This will register tools with: engineer, researcher, planner, control
    registry = register_external_tools_with_agents(
        cmbagent,
        use_crewai_tools=True,
        use_langchain_tools=True,
    )
    
    # List all available tools
    print("\n" + list_available_external_tools(verbose=True))
    
    # Now your agents can use these tools in planning and control
    task = """
    Search Wikipedia for information about cosmic microwave background,
    then create a summary and save it to a file called 'cmb_summary.txt'.
    """
    
    # The researcher agent can now use WikipediaQueryRun tool
    # The engineer agent can now use FileWriteTool
    result = cmbagent.solve(task, max_rounds=30)
    
    return result


# =============================================================================
# APPROACH 2: Selective Integration by Category
# =============================================================================

def example_2_selective_integration():
    """
    Load only specific categories of tools.
    
    This approach gives you more control - you can choose which types of tools
    to enable for your workflow.
    """
    print("=" * 70)
    print("EXAMPLE 2: Selective Integration by Category")
    print("=" * 70)
    
    # Initialize CMBAgent
    cmbagent = CMBAgent(
        work_dir="./cmbagent_selective_tools",
        mode="planning_and_control",
        api_keys=os.environ,
    )
    
    # Approach 2A: Register only search tools with researcher
    from cmbagent.external_tools import (
        get_crewai_free_tools,
        get_langchain_search_tools,
    )
    
    registry = get_global_registry()
    
    # Get LangChain search tools
    search_tools = get_langchain_search_tools()
    registry.register_tools(search_tools, category='search')
    
    # Register search tools only with researcher agent
    researcher = cmbagent.get_agent_from_name('researcher')
    executor = cmbagent.get_agent_from_name('executor')
    
    registry.register_with_agent(
        agent=researcher,
        category='search',
        executor_agent=executor
    )
    
    print(f"\nRegistered {len(search_tools)} search tools with researcher agent")
    
    # Approach 2B: Register file tools only with engineer
    from cmbagent.external_tools import get_crewai_file_tools
    
    file_tools = get_crewai_file_tools()
    registry.register_tools(file_tools, category='file')
    
    engineer = cmbagent.get_agent_from_name('engineer')
    
    registry.register_with_agent(
        agent=engineer,
        category='file',
        executor_agent=executor
    )
    
    print(f"Registered {len(file_tools)} file tools with engineer agent")
    
    # Now run a task
    task = """
    Research recent developments in cosmological parameter estimation using ArXiv,
    then create a structured summary of the top 3 papers.
    """
    
    result = cmbagent.solve(task, max_rounds=30)
    
    return result


# =============================================================================
# APPROACH 3: Fine-Grained Control - Specific Tools for Specific Agents
# =============================================================================

def example_3_specific_tools():
    """
    Register specific tools with specific agents.
    
    This approach gives you maximum control over which tools are available
    to which agents.
    """
    print("=" * 70)
    print("EXAMPLE 3: Fine-Grained Tool Control")
    print("=" * 70)
    
    # Initialize CMBAgent
    cmbagent = CMBAgent(
        work_dir="./cmbagent_specific_tools",
        mode="planning_and_control",
        api_keys=os.environ,
    )
    
    # First, load all available tools into the registry
    registry = get_global_registry()
    
    crewai_tools = get_crewai_free_tools()
    registry.register_tools(crewai_tools, category='crewai')
    
    langchain_tools = get_langchain_free_tools()
    registry.register_tools(langchain_tools, category='langchain')
    
    # Now register specific tools with specific agents
    # Researcher gets only search tools
    register_specific_external_tools(
        cmbagent,
        tool_names=['WikipediaQueryRun', 'ArxivQueryRun', 'DuckDuckGoSearchRun'],
        agent_names=['researcher']
    )
    
    # Engineer gets file and code tools
    register_specific_external_tools(
        cmbagent,
        tool_names=[
            'FileReadTool', 'FileWriteTool', 'DirectoryReadTool',
            'PythonREPLTool', 'CodeInterpreterTool'
        ],
        agent_names=['engineer']
    )
    
    # Planner gets web scraping tools
    register_specific_external_tools(
        cmbagent,
        tool_names=['ScrapeWebsiteTool', 'WebsiteSearchTool'],
        agent_names=['planner']
    )
    
    print("\nTool registration complete!")
    print(list_available_external_tools(verbose=False))
    
    # Run task
    task = """
    Research the latest CAMB features on GitHub and ArXiv,
    then write a Python script that demonstrates a key feature.
    Save the script to 'camb_demo.py'.
    """
    
    result = cmbagent.solve(task, max_rounds=30)
    
    return result


# =============================================================================
# APPROACH 4: Adding Custom Tools
# =============================================================================

def example_4_custom_tools():
    """
    Add your own custom tools alongside CrewAI and LangChain tools.
    """
    print("=" * 70)
    print("EXAMPLE 4: Adding Custom Tools")
    print("=" * 70)
    
    # Initialize CMBAgent
    cmbagent = CMBAgent(
        work_dir="./cmbagent_custom_tools",
        mode="planning_and_control",
        api_keys=os.environ,
    )
    
    # Load external tools
    registry = register_external_tools_with_agents(
        cmbagent,
        use_crewai_tools=True,
        use_langchain_tools=True,
    )
    
    # Define custom tools
    def cosmology_calculator(H0: float, omega_m: float) -> dict:
        """
        Calculate basic cosmological parameters.
        
        Args:
            H0: Hubble constant in km/s/Mpc
            omega_m: Matter density parameter
            
        Returns:
            Dictionary with calculated parameters
        """
        omega_lambda = 1.0 - omega_m
        age_universe = 13.8  # Simplified calculation
        
        return {
            "H0": H0,
            "omega_m": omega_m,
            "omega_lambda": omega_lambda,
            "age_gyr": age_universe,
            "message": f"Calculated for H0={H0}, Ωm={omega_m}"
        }
    
    def cmb_power_spectrum_analyzer(l_max: int = 2500) -> str:
        """
        Placeholder for CMB power spectrum analysis.
        
        Args:
            l_max: Maximum multipole
            
        Returns:
            Analysis summary
        """
        return f"Would analyze CMB power spectrum up to l={l_max}"
    
    # Add custom tools to registry
    add_custom_tool_to_registry(
        tool_name="cosmology_calculator",
        tool_function=cosmology_calculator,
        tool_description="Calculate basic cosmological parameters from H0 and Omega_m",
        category="cosmology"
    )
    
    add_custom_tool_to_registry(
        tool_name="cmb_power_spectrum_analyzer",
        tool_function=cmb_power_spectrum_analyzer,
        tool_description="Analyze CMB power spectrum data",
        category="cosmology"
    )
    
    # Register custom tools with agents
    engineer = cmbagent.get_agent_from_name('engineer')
    researcher = cmbagent.get_agent_from_name('researcher')
    executor = cmbagent.get_agent_from_name('executor')
    
    registry.register_with_agent(
        agent=engineer,
        category='cosmology',
        executor_agent=executor
    )
    
    registry.register_with_agent(
        agent=researcher,
        category='cosmology',
        executor_agent=executor
    )
    
    print("\nAll available tools:")
    print(list_available_external_tools(verbose=True))
    
    # Run task using custom tools
    task = """
    Calculate cosmological parameters for H0=70 and omega_m=0.3,
    then research the implications using Wikipedia and ArXiv.
    """
    
    result = cmbagent.solve(task, max_rounds=30)
    
    return result


# =============================================================================
# APPROACH 5: Integration in functions.py
# =============================================================================

def example_5_integration_in_functions():
    """
    Show how to integrate tools in the functions.py registration system.
    
    This is the recommended approach for permanent integration.
    Add this code to your cmbagent/functions.py file.
    """
    
    example_code = '''
# Add to cmbagent/functions.py at the end of register_functions_to_agents()

def register_functions_to_agents(cmbagent_instance):
    """
    This function registers the functions to the agents.
    """
    # ... existing code ...
    
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
        
        print(f"Registered {len(registry.get_all_tools())} external tools")
        
    except Exception as e:
        print(f"Warning: Could not register external tools: {e}")
    
    # ... rest of existing code ...
    '''
    
    print("=" * 70)
    print("EXAMPLE 5: Integration in functions.py")
    print("=" * 70)
    print("\nAdd the following code to your cmbagent/functions.py:")
    print(example_code)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("CMBAgent External Tools Integration Examples")
    print("=" * 70)
    
    print("\nThese examples demonstrate different ways to integrate")
    print("CrewAI and LangChain tools with your CMBAgent system.")
    print("\nChoose which example to run:")
    print("  1. Automatic integration (all tools)")
    print("  2. Selective integration (by category)")
    print("  3. Fine-grained control (specific tools)")
    print("  4. Add custom tools")
    print("  5. Show integration code for functions.py")
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    examples = {
        '1': example_1_automatic_integration,
        '2': example_2_selective_integration,
        '3': example_3_specific_tools,
        '4': example_4_custom_tools,
        '5': example_5_integration_in_functions,
    }
    
    if choice in examples:
        examples[choice]()
    else:
        print("Invalid choice. Running example 5 (integration code)...")
        example_5_integration_in_functions()
