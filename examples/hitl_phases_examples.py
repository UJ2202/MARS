"""
Example: Using HITL Planning and Control Phases

This example demonstrates how to use the new HITLPlanningPhase and HITLControlPhase
for interactive, human-guided workflow execution.
"""

import asyncio
from cmbagent.workflows import WorkflowDefinition, WorkflowExecutor
from cmbagent.utils import get_api_keys_from_env


async def example_1_full_hitl():
    """
    Example 1: Full HITL workflow with interactive planning and step-by-step control.
    
    This workflow provides maximum human control:
    - Interactive planning with iterative refinement
    - Step-by-step approval before and after each step
    """
    print("\n" + "="*60)
    print("Example 1: Full HITL Workflow")
    print("="*60 + "\n")
    
    workflow = WorkflowDefinition(
        id="full_hitl_example",
        name="Full HITL Example",
        description="Interactive planning + step-by-step execution",
        phases=[
            {
                "type": "hitl_planning",
                "config": {
                    "max_plan_steps": 3,
                    "max_human_iterations": 3,
                    "require_explicit_approval": True,
                    "allow_plan_modification": True,
                    "show_intermediate_plans": True,
                }
            },
            {
                "type": "hitl_control",
                "config": {
                    "approval_mode": "both",  # Approve before AND review after each step
                    "allow_step_skip": True,
                    "allow_step_retry": True,
                    "show_step_context": True,
                    "max_rounds": 100,
                }
            },
        ]
    )
    
    executor = WorkflowExecutor(
        workflow=workflow,
        task="Calculate CMB power spectrum using CAMB and create a plot",
        work_dir="./output/full_hitl",
        api_keys=get_api_keys_from_env(),
    )
    
    result = await executor.run()
    
    print("\n" + "="*60)
    print("Workflow completed!")
    print(f"Status: {result.status}")
    print(f"Steps executed: {len(result.step_results)}")
    print("="*60 + "\n")
    
    return result


async def example_2_hitl_planning_only():
    """
    Example 2: HITL planning followed by autonomous execution.
    
    This workflow:
    - Uses interactive planning for human-guided plan creation
    - Executes the approved plan autonomously without further human input
    """
    print("\n" + "="*60)
    print("Example 2: HITL Planning + Autonomous Execution")
    print("="*60 + "\n")
    
    workflow = WorkflowDefinition(
        id="hitl_plan_auto_execute",
        name="HITL Planning + Auto Execute",
        description="Human-guided planning, then autonomous execution",
        phases=[
            {
                "type": "hitl_planning",
                "config": {
                    "max_plan_steps": 5,
                    "max_human_iterations": 2,
                    "require_explicit_approval": True,
                }
            },
            {
                "type": "control",  # Standard autonomous control phase
                "config": {
                    "execute_all_steps": True,
                    "max_rounds": 150,
                }
            },
        ]
    )
    
    executor = WorkflowExecutor(
        workflow=workflow,
        task="Analyze Planck data for temperature anisotropies",
        work_dir="./output/hitl_planning",
        api_keys=get_api_keys_from_env(),
    )
    
    result = await executor.run()
    
    print("\n" + "="*60)
    print("Workflow completed!")
    print(f"Human iterations during planning: {result.iterations}")
    print("="*60 + "\n")
    
    return result


async def example_3_error_recovery():
    """
    Example 3: Autonomous execution with human intervention only on errors.
    
    This workflow:
    - Uses standard autonomous planning
    - Executes steps autonomously
    - Only asks for human input when a step fails
    """
    print("\n" + "="*60)
    print("Example 3: Autonomous with Error Recovery")
    print("="*60 + "\n")
    
    workflow = WorkflowDefinition(
        id="error_recovery_hitl",
        name="Error Recovery HITL",
        description="Autonomous execution with human error handling",
        phases=[
            {
                "type": "planning",  # Standard autonomous planning
                "config": {
                    "max_plan_steps": 4,
                    "n_plan_reviews": 1,
                }
            },
            {
                "type": "hitl_control",
                "config": {
                    "approval_mode": "on_error",  # Only intervene on errors
                    "allow_step_retry": True,
                    "allow_step_skip": True,
                    "max_n_attempts": 3,
                }
            },
        ]
    )
    
    executor = WorkflowExecutor(
        workflow=workflow,
        task="Run CLASS to compute matter power spectrum",
        work_dir="./output/error_recovery",
        api_keys=get_api_keys_from_env(),
    )
    
    result = await executor.run()
    
    print("\n" + "="*60)
    print("Workflow completed!")
    print(f"Human interventions: {len(result.human_interventions)}")
    print(f"Skipped steps: {result.skipped_steps}")
    print("="*60 + "\n")
    
    return result


async def example_4_before_step_approval():
    """
    Example 4: Approve each step before execution.
    
    This workflow:
    - Uses standard planning
    - Asks for approval before executing each step
    - Allows skipping steps
    """
    print("\n" + "="*60)
    print("Example 4: Before-Step Approval")
    print("="*60 + "\n")
    
    workflow = WorkflowDefinition(
        id="before_step_approval",
        name="Before-Step Approval",
        description="Approve each step before execution",
        phases=[
            {
                "type": "planning",
                "config": {
                    "max_plan_steps": 3,
                }
            },
            {
                "type": "hitl_control",
                "config": {
                    "approval_mode": "before_step",
                    "allow_step_skip": True,
                    "show_step_context": True,
                }
            },
        ]
    )
    
    executor = WorkflowExecutor(
        workflow=workflow,
        task="Compare CAMB and CLASS power spectrum outputs",
        work_dir="./output/before_step",
        api_keys=get_api_keys_from_env(),
    )
    
    result = await executor.run()
    
    print("\n" + "="*60)
    print("Workflow completed!")
    print("="*60 + "\n")
    
    return result


async def example_5_after_step_review():
    """
    Example 5: Review results after each step.
    
    This workflow:
    - Uses standard planning
    - Executes steps autonomously
    - Asks for review after each step completes
    """
    print("\n" + "="*60)
    print("Example 5: After-Step Review")
    print("="*60 + "\n")
    
    workflow = WorkflowDefinition(
        id="after_step_review",
        name="After-Step Review",
        description="Review results after each step",
        phases=[
            {
                "type": "planning",
                "config": {
                    "max_plan_steps": 3,
                }
            },
            {
                "type": "hitl_control",
                "config": {
                    "approval_mode": "after_step",
                    "auto_approve_successful_steps": False,
                }
            },
        ]
    )
    
    executor = WorkflowExecutor(
        workflow=workflow,
        task="Fit cosmological parameters to mock data",
        work_dir="./output/after_step",
        api_keys=get_api_keys_from_env(),
    )
    
    result = await executor.run()
    
    print("\n" + "="*60)
    print("Workflow completed!")
    print("="*60 + "\n")
    
    return result


async def example_6_teaching_mode():
    """
    Example 6: Teaching/demonstration mode with maximum visibility.
    
    This workflow:
    - Shows intermediate plans during planning
    - Shows context before each step
    - Requires approval before and review after each step
    - Perfect for teaching or demonstrating CMBAgent capabilities
    """
    print("\n" + "="*60)
    print("Example 6: Teaching/Demo Mode")
    print("="*60 + "\n")
    
    workflow = WorkflowDefinition(
        id="teaching_mode",
        name="Teaching Mode",
        description="Maximum visibility for teaching/demos",
        phases=[
            {
                "type": "hitl_planning",
                "config": {
                    "max_plan_steps": 3,
                    "max_human_iterations": 3,
                    "show_intermediate_plans": True,
                    "allow_plan_modification": True,
                    "plan_instructions": "Create a detailed, educational plan with explanations",
                }
            },
            {
                "type": "hitl_control",
                "config": {
                    "approval_mode": "both",
                    "show_step_context": True,
                    "max_rounds": 80,
                }
            },
        ]
    )
    
    executor = WorkflowExecutor(
        workflow=workflow,
        task="Tutorial: Calculate and visualize CMB lensing power spectrum",
        work_dir="./output/teaching",
        api_keys=get_api_keys_from_env(),
    )
    
    result = await executor.run()
    
    print("\n" + "="*60)
    print("Teaching session completed!")
    print("="*60 + "\n")
    
    return result


async def example_7_progressive_automation():
    """
    Example 7: Progressive automation - start with full HITL, reduce over time.
    
    This workflow demonstrates a pattern where:
    - First workflow run: Full HITL (max human control)
    - Later runs: Reduce human intervention as confidence builds
    """
    print("\n" + "="*60)
    print("Example 7: Progressive Automation")
    print("="*60 + "\n")
    
    # First run: Full HITL
    workflow_v1 = WorkflowDefinition(
        id="progressive_v1",
        name="Progressive Automation v1 (Full HITL)",
        phases=[
            {"type": "hitl_planning", "config": {"max_human_iterations": 3}},
            {"type": "hitl_control", "config": {"approval_mode": "both"}},
        ]
    )
    
    # Later run: Error-only HITL
    workflow_v2 = WorkflowDefinition(
        id="progressive_v2",
        name="Progressive Automation v2 (Error-Only)",
        phases=[
            {"type": "planning", "config": {}},
            {"type": "hitl_control", "config": {"approval_mode": "on_error"}},
        ]
    )
    
    # Final run: Fully autonomous with single checkpoint
    workflow_v3 = WorkflowDefinition(
        id="progressive_v3",
        name="Progressive Automation v3 (Mostly Autonomous)",
        phases=[
            {"type": "planning", "config": {}},
            {"type": "hitl_checkpoint", "config": {"checkpoint_type": "after_planning"}},
            {"type": "control", "config": {}},
        ]
    )
    
    print("This example shows three progressive workflow versions:")
    print("  v1: Full HITL (maximum control)")
    print("  v2: Error-only HITL (balanced)")
    print("  v3: Checkpoint-only (mostly autonomous)")
    print("\nUse v1 for initial runs, v2 when comfortable, v3 for production")
    print("="*60 + "\n")


def run_example(example_func):
    """Helper to run async examples."""
    asyncio.run(example_func())


if __name__ == "__main__":
    import sys
    
    examples = {
        "1": example_1_full_hitl,
        "2": example_2_hitl_planning_only,
        "3": example_3_error_recovery,
        "4": example_4_before_step_approval,
        "5": example_5_after_step_review,
        "6": example_6_teaching_mode,
        "7": example_7_progressive_automation,
    }
    
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        if example_num in examples:
            run_example(examples[example_num])
        else:
            print(f"Invalid example number: {example_num}")
            print(f"Available examples: {', '.join(examples.keys())}")
    else:
        print("\nHITL Phases Examples")
        print("="*60)
        print("\nUsage: python hitl_phases_examples.py <example_number>")
        print("\nAvailable examples:")
        print("  1 - Full HITL (planning + control)")
        print("  2 - HITL planning + auto execution")
        print("  3 - Autonomous with error recovery")
        print("  4 - Before-step approval")
        print("  5 - After-step review")
        print("  6 - Teaching/demo mode")
        print("  7 - Progressive automation pattern")
        print("\nExample:")
        print("  python hitl_phases_examples.py 1")
        print("="*60 + "\n")
