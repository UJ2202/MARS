#!/usr/bin/env python3
"""
Swarm Copilot Example - Unified Multi-Agent Orchestration

This example demonstrates the unified swarm orchestrator that:
1. Loads ALL agents into one swarm
2. Registers ALL tools + phase tools (phases as callable tools)
3. Uses intelligent routing via copilot_control
4. Manages rounds with continuation support

Usage:
    python examples/swarm_copilot_example.py
"""

import asyncio
import os
from typing import Dict, Any


def example_basic_usage():
    """Basic usage of swarm_copilot."""
    from cmbagent.workflows import swarm_copilot

    print("\n" + "=" * 60)
    print("EXAMPLE 1: Basic Swarm Copilot")
    print("=" * 60)

    result = swarm_copilot(
        task="Create a Python function that validates email addresses",
        max_rounds=50,
        lightweight_mode=True,
    )

    print(f"\nResult status: {result['status']}")
    print(f"Rounds executed: {result.get('rounds_executed', 0)}")
    print(f"Phases invoked: {len(result.get('phases_executed', []))}")


def example_with_phase_tools():
    """Using phase tools within the swarm."""
    from cmbagent.workflows import swarm_copilot

    print("\n" + "=" * 60)
    print("EXAMPLE 2: With Phase Tools")
    print("=" * 60)

    # Enable phase tools - agents can invoke planning, control, etc.
    result = swarm_copilot(
        task="Build a REST API with authentication. Plan it first, then implement.",
        max_rounds=100,
        enable_phase_tools=True,  # Allow phases as tools
        available_phases=[
            "planning",      # invoke_planning_phase
            "control",       # invoke_control_phase
            "one_shot",      # invoke_one_shot_phase
            "hitl_planning", # invoke_hitl_planning_phase
        ],
        use_copilot_control=True,  # Use LLM-based routing
    )

    print(f"\nResult status: {result['status']}")
    print(f"Phases executed: {result.get('phases_executed', [])}")


async def example_continuation():
    """Continuation when max rounds reached."""
    from cmbagent.workflows import swarm_copilot_async, continue_swarm_copilot

    print("\n" + "=" * 60)
    print("EXAMPLE 3: Continuation Support")
    print("=" * 60)

    # Start with low max_rounds to trigger pause
    result = await swarm_copilot_async(
        task="Research and implement a comprehensive logging system",
        max_rounds=10,  # Low to trigger pause
        auto_continue=False,
    )

    print(f"\nInitial status: {result['status']}")

    if result['status'] == 'paused':
        print(f"Session ID: {result['session_id']}")
        print("Continuing execution...")

        # Continue from where we left off
        result = await continue_swarm_copilot(
            session_id=result['session_id'],
            additional_context="Focus on finishing the implementation",
        )

        print(f"Final status: {result['status']}")
        print(f"Total rounds: {result.get('rounds_executed', 0)}")


def example_full_swarm():
    """Full swarm with all agents loaded."""
    from cmbagent.workflows import full_swarm

    print("\n" + "=" * 60)
    print("EXAMPLE 4: Full Swarm (All Agents)")
    print("=" * 60)

    result = full_swarm(
        task="Create a data analysis pipeline with visualization",
    )

    print(f"\nResult status: {result['status']}")
    print(f"Conversation history length: {len(result.get('conversation_history', []))}")


def example_quick_swarm():
    """Quick swarm for simple tasks."""
    from cmbagent.workflows import quick_swarm

    print("\n" + "=" * 60)
    print("EXAMPLE 5: Quick Swarm (Lightweight)")
    print("=" * 60)

    result = quick_swarm(
        task="Write a Python function to reverse a linked list",
    )

    print(f"\nResult status: {result['status']}")


def example_with_callbacks():
    """Using callbacks to monitor execution."""
    from cmbagent.workflows import swarm_copilot

    print("\n" + "=" * 60)
    print("EXAMPLE 6: With Callbacks")
    print("=" * 60)

    def on_round_start(round_num, state):
        print(f"  → Round {round_num + 1} starting...")

    def on_round_end(round_num, result):
        status = result.get('status', 'unknown')
        print(f"  ← Round {round_num + 1} complete: {status}")

    def on_phase_invoked(phase_type, task, config):
        print(f"  📦 Phase invoked: {phase_type}")

    result = swarm_copilot(
        task="Create a simple web scraper",
        max_rounds=20,
        callbacks={
            'on_round_start': on_round_start,
            'on_round_end': on_round_end,
            'on_phase_invoked': on_phase_invoked,
        },
    )

    print(f"\nFinal status: {result['status']}")


def example_using_orchestrator_directly():
    """Direct usage of SwarmOrchestrator for more control."""
    from cmbagent.orchestrator import SwarmOrchestrator, SwarmConfig
    from cmbagent.utils import get_api_keys_from_env

    print("\n" + "=" * 60)
    print("EXAMPLE 7: Direct Orchestrator Usage")
    print("=" * 60)

    async def run():
        # Create custom config
        config = SwarmConfig(
            max_rounds=50,
            enable_phase_tools=True,
            available_agents=[
                "engineer", "researcher", "planner",
                "copilot_control", "summarizer",
            ],
            available_phases=["planning", "one_shot"],
            use_copilot_control=True,
            default_model="gpt-4o",
        )

        # Create orchestrator
        orchestrator = SwarmOrchestrator(config)

        # Initialize with your settings
        api_keys = get_api_keys_from_env()
        await orchestrator.initialize(
            api_keys=api_keys,
            work_dir="./swarm_output",
        )

        # Run task
        result = await orchestrator.run(
            task="Design a database schema for a blog platform",
            initial_context={"project": "blog_platform"},
        )

        # Access state
        print(f"\nSession: {orchestrator.state.session_id}")
        print(f"Status: {orchestrator.state.status.value}")
        print(f"Rounds: {orchestrator.state.total_rounds_across_continuations}")

        # Cleanup
        await orchestrator.close()

        return result

    result = asyncio.run(run())
    print(f"\nFinal result status: {result['status']}")


def example_interactive_session():
    """Interactive session mode."""
    from cmbagent.workflows import interactive_swarm

    print("\n" + "=" * 60)
    print("EXAMPLE 8: Interactive Session")
    print("=" * 60)
    print("Note: This would normally prompt for input")

    # For demo, we'll use a predefined task
    # In real usage, interactive_swarm() prompts for tasks
    from cmbagent.workflows import swarm_copilot

    result = swarm_copilot(
        task="Help me design a microservices architecture",
        max_rounds=50,
        auto_continue=True,  # Auto-continue on max rounds
    )

    print(f"\nResult status: {result['status']}")


def example_phase_orchestrator():
    """Using PhaseOrchestrator to execute phases as tools."""
    from cmbagent.orchestrator import (
        PhaseOrchestrator,
        PhaseExecutionRequest,
        OrchestratorConfig,
    )
    from cmbagent.utils import get_api_keys_from_env

    print("\n" + "=" * 60)
    print("EXAMPLE 9: Phase Orchestrator")
    print("=" * 60)

    async def run():
        # Create config
        config = OrchestratorConfig(
            enable_dag_tracking=True,
            enable_logging=True,
            max_retries=2,
        )

        # Create orchestrator
        api_keys = get_api_keys_from_env()
        orchestrator = PhaseOrchestrator(
            config=config,
            api_keys=api_keys,
            work_dir="./phase_output",
        )

        # Execute a planning phase
        request = PhaseExecutionRequest(
            phase_type="planning",
            task="Design a CI/CD pipeline",
            config={"max_plan_steps": 5},
        )

        result = await orchestrator.execute_phase(request)

        print(f"\nPhase: {result.phase_type}")
        print(f"Status: {result.status}")
        print(f"Duration: {result.duration:.2f}s")

        # Chain multiple phases
        chain_results = await orchestrator.execute_chain([
            {"phase": "planning", "task": "Design API endpoints"},
            {"phase": "one_shot", "task": "Implement the first endpoint"},
        ])

        print(f"\nChain executed: {len(chain_results)} phases")

        return orchestrator.get_execution_summary()

    result = asyncio.run(run())
    print(f"\nExecution summary: {result}")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("  SWARM COPILOT EXAMPLES")
    print("  Unified Multi-Agent Orchestration with Phase Tools")
    print("=" * 70)

    # Note: In a real scenario, each example would run
    # Here we just show the structure

    examples = [
        ("Basic Usage", example_basic_usage),
        ("With Phase Tools", example_with_phase_tools),
        ("Continuation Support", lambda: asyncio.run(example_continuation())),
        ("Full Swarm", example_full_swarm),
        ("Quick Swarm", example_quick_swarm),
        ("With Callbacks", example_with_callbacks),
        ("Direct Orchestrator", example_using_orchestrator_directly),
        ("Interactive Session", example_interactive_session),
        ("Phase Orchestrator", example_phase_orchestrator),
    ]

    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\nTo run an example, uncomment the relevant function call below.")
    print("Each example requires API keys to be configured.")

    # Uncomment to run specific examples:
    # example_basic_usage()
    # example_with_phase_tools()
    # asyncio.run(example_continuation())
    # example_full_swarm()
    # example_quick_swarm()
    # example_with_callbacks()
    # example_using_orchestrator_directly()
    # example_interactive_session()
    # example_phase_orchestrator()


if __name__ == "__main__":
    main()
