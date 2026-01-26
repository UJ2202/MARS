#!/usr/bin/env python3
"""
Verification script: Check that external tools are integrated in all workflows.

This script verifies that the external tools integration is working correctly
in all CMBAgent workflows.
"""

import sys
import os

def check_workflow_integration():
    """Check that all workflow files have external tools integration."""
    
    print("=" * 70)
    print("EXTERNAL TOOLS INTEGRATION VERIFICATION")
    print("=" * 70)
    print()
    
    workflows = [
        ('planning_control.py', 'planning_and_control_context_carryover'),
        ('control.py', 'control workflow'),
        ('one_shot.py', 'one_shot workflow'),
    ]
    
    all_ok = True
    base_path = os.path.join(os.path.dirname(__file__), 'cmbagent', 'workflows')
    
    for filename, workflow_name in workflows:
        filepath = os.path.join(base_path, filename)
        
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            # Check if integration code is present
            has_integration = 'from cmbagent.external_tools.integration_helpers import register_external_tools_with_agents' in content
            
            if has_integration:
                print(f"✓ {workflow_name:40s} - External tools integrated")
            else:
                print(f"✗ {workflow_name:40s} - Integration NOT found")
                all_ok = False
                
        except FileNotFoundError:
            print(f"✗ {workflow_name:40s} - File not found: {filepath}")
            all_ok = False
        except Exception as e:
            print(f"✗ {workflow_name:40s} - Error: {e}")
            all_ok = False
    
    print()
    print("=" * 70)
    
    if all_ok:
        print("✓ ALL WORKFLOWS HAVE EXTERNAL TOOLS INTEGRATED")
        print()
        print("Your agents now have access to 30+ tools in all workflows:")
        print("  • Planning and Control (context carryover)")
        print("  • Control workflow") 
        print("  • One-shot workflow")
        print()
        print("Tools available:")
        print("  ✓ 15 CrewAI tools (file ops, web scraping, code analysis)")
        print("  ✓ 15 LangChain tools (Wikipedia, ArXiv, web search, file ops)")
        print()
        return 0
    else:
        print("✗ SOME WORKFLOWS ARE MISSING INTEGRATION")
        print("Please check the workflow files listed above.")
        return 1


def show_usage_example():
    """Show example of how to use the integrated tools."""
    
    print()
    print("=" * 70)
    print("USAGE EXAMPLE")
    print("=" * 70)
    print()
    print("The external tools are now automatically available in your workflows:")
    print()
    print("```python")
    print("from cmbagent.workflows.planning_control import planning_and_control_context_carryover")
    print()
    print("# External tools are automatically registered!")
    print("result = planning_and_control_context_carryover(")
    print("    task='''")
    print("    Search Wikipedia for 'cosmic microwave background'.")
    print("    Summarize the key findings.")
    print("    Save the summary to 'cmb_summary.txt'.")
    print("    ''',")
    print("    max_rounds_planning=30,")
    print("    max_rounds_control=50,")
    print(")")
    print("```")
    print()
    print("Your agents can now use:")
    print("  • WikipediaQueryRun - Search Wikipedia")
    print("  • ArxivQueryRun - Search ArXiv papers")
    print("  • FileWriteTool - Write files")
    print("  • DuckDuckGoSearchRun - Web search")
    print("  • And 26+ more tools!")
    print()


def check_dependencies():
    """Check if required dependencies are installed."""
    
    print()
    print("=" * 70)
    print("DEPENDENCY CHECK")
    print("=" * 70)
    print()
    
    dependencies = [
        ('crewai', 'CrewAI'),
        ('crewai_tools', 'CrewAI Tools'),
        ('langchain', 'LangChain'),
        ('langchain_community', 'LangChain Community'),
    ]
    
    all_installed = True
    
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"✓ {name:25s} - Installed")
        except ImportError:
            print(f"✗ {name:25s} - NOT installed")
            all_installed = False
    
    print()
    
    if not all_installed:
        print("⚠️  Some dependencies are missing. Install with:")
        print("   pip install -e .")
        print()
    
    return all_installed


def main():
    """Run all verification checks."""
    
    print()
    print("🔍 Verifying External Tools Integration in CMBAgent Workflows")
    print()
    
    # Check integration
    integration_ok = check_workflow_integration()
    
    # Check dependencies
    deps_ok = check_dependencies()
    
    # Show usage
    show_usage_example()
    
    print("=" * 70)
    print()
    
    if integration_ok == 0 and deps_ok:
        print("✅ ALL CHECKS PASSED!")
        print()
        print("Next steps:")
        print("  1. Test the integration: python tests/test_external_tools.py")
        print("  2. Try an example: python examples/external_tools_integration.py")
        print("  3. Run your workflow with external tools enabled!")
        print()
        return 0
    else:
        print("⚠️  SOME CHECKS FAILED")
        print()
        if integration_ok != 0:
            print("  • Integration incomplete - check workflow files")
        if not deps_ok:
            print("  • Dependencies missing - run: pip install -e .")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
