"""
HITL Interactive Workflow - Quick Start Example

This example demonstrates the new HITL Interactive workflow mode.

Usage:
    python examples/hitl_quickstart.py

The workflow will:
1. Guide you through interactive planning (3 iterations max)
2. Execute each step with your approval (before & after)
3. Collect and preserve all your feedback
"""

import asyncio
from cmbagent.workflows import hitl_interactive_workflow
from cmbagent.utils import get_api_keys_from_env


async def main():
    print("=" * 70)
    print("HITL Interactive Workflow - Quick Start")
    print("=" * 70)
    
    # Task: Simple data analysis with visualization
    task = "Generate 100 random numbers from a normal distribution and create a histogram plot"
    
    print(f"\n📝 Task: {task}")
    print("\n⚙️ Configuration:")
    print("  - Max Planning Iterations: 3")
    print("  - Approval Mode: both (before & after each step)")
    print("  - Max Plan Steps: 3")
    
    print("\n🚀 Starting HITL Interactive Workflow...")
    print("\nDuring execution you will:")
    print("  1️⃣  Review and approve/revise the plan (up to 3 iterations)")
    print("  2️⃣  Approve each step before execution")
    print("  3️⃣  Review results after each step completes")
    print("\n" + "=" * 70 + "\n")
    
    # Get API keys
    api_keys = get_api_keys_from_env()
    
    # Execute HITL workflow
    results = hitl_interactive_workflow(
        task=task,
        max_plan_steps=3,
        max_human_iterations=3,
        approval_mode="both",  # Approve before AND after each step
        allow_plan_modification=True,
        allow_step_skip=True,
        allow_step_retry=True,
        show_step_context=True,
        work_dir="~/cmbagent_hitl_quickstart",
        api_keys=api_keys,
        clear_work_dir=True,
    )
    
    # Display results
    print("\n" + "=" * 70)
    print("✅ HITL Workflow Complete!")
    print("=" * 70)
    
    # Show timing info
    phase_timings = results.get('phase_timings', {})
    if phase_timings:
        print("\n⏱️  Phase Timings:")
        for phase, duration in phase_timings.items():
            print(f"  - {phase}: {duration:.2f}s")
    
    # Show feedback collected
    hitl_feedback = results.get('hitl_feedback', '')
    if hitl_feedback:
        print("\n💬 Human Feedback Collected:")
        print("-" * 70)
        print(hitl_feedback)
        print("-" * 70)
    
    planning_history = results.get('planning_feedback_history', [])
    if planning_history:
        print(f"\n📋 Planning Iterations: {len(planning_history)}")
        for i, feedback in enumerate(planning_history, 1):
            print(f"  {i}. {feedback[:100]}{'...' if len(feedback) > 100 else ''}")
    
    step_feedback = results.get('step_feedback', [])
    if step_feedback:
        print(f"\n🔧 Step Interventions: {len(step_feedback)}")
        for intervention in step_feedback:
            step = intervention.get('step', '?')
            timing = intervention.get('timing', '?')
            feedback = intervention.get('feedback', '')
            print(f"  - Step {step} ({timing}): {feedback[:80]}{'...' if len(feedback) > 80 else ''}")
    
    work_dir = results.get('work_dir', '')
    if work_dir:
        print(f"\n📁 Output Directory: {work_dir}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
