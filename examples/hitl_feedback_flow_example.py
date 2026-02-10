"""
HITL Feedback Flow Example
===========================

This example demonstrates how human feedback flows between HITL phases:
1. HITLCheckpointPhase captures initial approval/feedback
2. HITLPlanningPhase incorporates that feedback and generates a plan with iterative human input
3. HITLControlPhase uses feedback from planning to guide execution
4. Step-level feedback during control is accumulated and can be used downstream

Complete feedback chain: Checkpoint → Planning → Control → Next Phase
"""

import asyncio
from cmbagent.phases.hitl_checkpoint import HITLCheckpointPhase, HITLCheckpointPhaseConfig
from cmbagent.phases.hitl_planning import HITLPlanningPhase, HITLPlanningPhaseConfig
from cmbagent.phases.hitl_control import HITLControlPhase, HITLControlPhaseConfig
from cmbagent.phases import PhaseContext, PhaseExecutionManager
from cmbagent.database.approval_manager import ApprovalManager


async def example_complete_feedback_flow():
    """
    Complete example showing feedback flowing through all HITL phases.
    
    Workflow:
    1. Checkpoint with user approval/feedback
    2. Planning that incorporates checkpoint feedback
    3. Control that uses planning feedback
    """
    
    # Setup
    approval_manager = ApprovalManager()
    run_id = "hitl_feedback_demo_001"
    
    # === Phase 1: Initial Checkpoint ===
    print("\n" + "="*70)
    print("PHASE 1: HITL CHECKPOINT")
    print("="*70)
    
    checkpoint_phase = HITLCheckpointPhase(
        config=HITLCheckpointPhaseConfig(
            checkpoint_name="Initial Requirements Review",
            message="Review the task requirements and provide guidance",
        )
    )
    
    checkpoint_context = PhaseContext(
        run_id=run_id,
        phase_id="initial_checkpoint",
        input_data={
            "task": "Analyze CMB power spectrum data and create visualization",
            "data_file": "planck_spectra.fits",
        },
        shared_state={},
    )
    
    manager1 = PhaseExecutionManager(
        run_id=run_id,
        phase_id="initial_checkpoint",
        approval_manager=approval_manager,
    )
    
    # Execute checkpoint - human provides initial feedback
    # Example: "Focus on the low-l anomaly, use log scale for y-axis"
    checkpoint_result = await checkpoint_phase.execute(
        context=checkpoint_context,
        manager=manager1
    )
    
    if checkpoint_result.status != "success":
        print(f"Checkpoint failed: {checkpoint_result.error_message}")
        return
    
    # Extract feedback from checkpoint
    hitl_feedback = checkpoint_result.output_data.get('shared', {}).get('hitl_feedback', '')
    print(f"\n✓ Checkpoint completed")
    print(f"✓ Human feedback captured: {hitl_feedback[:100]}...")
    
    
    # === Phase 2: Planning with Feedback ===
    print("\n" + "="*70)
    print("PHASE 2: HITL PLANNING (with checkpoint feedback)")
    print("="*70)
    
    planning_phase = HITLPlanningPhase(
        config=HITLPlanningPhaseConfig(
            max_human_iterations=2,  # Allow up to 2 revision cycles
            auto_approve_after_iterations=False,
        )
    )
    
    # Pass checkpoint feedback via shared_state
    planning_context = PhaseContext(
        run_id=run_id,
        phase_id="planning_with_feedback",
        input_data=checkpoint_result.output_data,
        shared_state={
            'hitl_feedback': hitl_feedback,  # From checkpoint
            'hitl_approved': checkpoint_result.output_data.get('shared', {}).get('hitl_approved', False),
        },
    )
    
    manager2 = PhaseExecutionManager(
        run_id=run_id,
        phase_id="planning_with_feedback",
        approval_manager=approval_manager,
    )
    
    # Execute planning - iterative feedback loop
    # Iteration 1: Human might say "Add step to check data quality first"
    # Iteration 2: Human approves or provides final notes
    planning_result = await planning_phase.execute(
        context=planning_context,
        manager=manager2
    )
    
    if planning_result.status != "success":
        print(f"Planning failed: {planning_result.error_message}")
        return
    
    # Extract combined feedback from planning
    planning_feedback = planning_result.output_data.get('shared', {}).get('hitl_feedback', '')
    planning_feedback_history = planning_result.output_data.get('shared', {}).get('planning_feedback_history', [])
    
    print(f"\n✓ Planning completed with {len(planning_feedback_history)} human iterations")
    print(f"✓ Combined feedback for control phase:")
    print(f"  {planning_feedback[:200]}...")
    
    
    # === Phase 3: Control with Accumulated Feedback ===
    print("\n" + "="*70)
    print("PHASE 3: HITL CONTROL (with planning feedback)")
    print("="*70)
    
    control_phase = HITLControlPhase(
        config=HITLControlPhaseConfig(
            approval_mode="both",  # Approve before and after each step
            auto_approve_successful_steps=False,  # Always review
            enable_error_recovery=True,
        )
    )
    
    # Pass accumulated feedback to control phase
    control_context = PhaseContext(
        run_id=run_id,
        phase_id="control_with_feedback",
        input_data=planning_result.output_data,
        shared_state={
            'hitl_feedback': planning_feedback,  # Combined feedback from checkpoint + planning
            'planning_feedback_history': planning_feedback_history,
        },
    )
    
    manager3 = PhaseExecutionManager(
        run_id=run_id,
        phase_id="control_with_feedback",
        approval_manager=approval_manager,
    )
    
    # Execute control - step-by-step with feedback
    # Before each step: Human can add guidance
    # After each step: Human can provide notes/corrections
    control_result = await control_phase.execute(
        context=control_context,
        manager=manager3
    )
    
    if control_result.status != "success":
        print(f"Control failed: {control_result.error_message}")
        return
    
    # Extract step feedback
    step_feedback = control_result.output_data.get('step_feedback', [])
    all_feedback = control_result.output_data.get('shared', {}).get('all_hitl_feedback', '')
    
    print(f"\n✓ Control completed")
    print(f"✓ Step-level feedback collected: {len(step_feedback)} interventions")
    print(f"✓ Complete feedback chain available for downstream phases")
    
    
    # === Summary ===
    print("\n" + "="*70)
    print("FEEDBACK FLOW SUMMARY")
    print("="*70)
    
    print("\n1. Checkpoint Phase:")
    print(f"   - Initial feedback: {len(hitl_feedback)} chars")
    
    print("\n2. Planning Phase:")
    print(f"   - Received checkpoint feedback: ✓")
    print(f"   - Human iterations: {len(planning_feedback_history)}")
    print(f"   - Combined feedback: {len(planning_feedback)} chars")
    
    print("\n3. Control Phase:")
    print(f"   - Received planning feedback: ✓")
    print(f"   - Step interventions: {len(step_feedback)}")
    print(f"   - Complete feedback history: {len(all_feedback)} chars")
    
    print("\n4. Available for Next Phase:")
    print("   - all_hitl_feedback: Complete history from all phases")
    print("   - control_feedback: Step-specific feedback list")
    print("   - planning_feedback_history: Planning iteration details")
    
    print("\n" + "="*70)
    print("✓ Complete feedback flow demonstrated successfully!")
    print("="*70)
    
    return {
        'checkpoint_feedback': hitl_feedback,
        'planning_feedback': planning_feedback,
        'planning_iterations': planning_feedback_history,
        'control_feedback': step_feedback,
        'complete_feedback': all_feedback,
    }


async def example_feedback_injection_in_agents():
    """
    Demonstrates how feedback is injected into agent instructions.
    
    Shows internal mechanism of how agents "see" the human feedback.
    """
    print("\n" + "="*70)
    print("FEEDBACK INJECTION MECHANISM")
    print("="*70)
    
    print("\n1. Checkpoint Phase:")
    print("   - Captures user_feedback from ApprovalResolution")
    print("   - Stores in shared_state['hitl_feedback']")
    print("   - Example: 'Focus on low-l anomaly, use log scale'")
    
    print("\n2. Planning Phase receives feedback:")
    print("   - Extracts: previous_hitl_feedback = shared_state.get('hitl_feedback')")
    print("   - Builds instruction addition:")
    print("     '''")
    print("     ## Previous Human Feedback")
    print("     Focus on low-l anomaly, use log scale")
    print("     ")
    print("     Please incorporate this feedback into your planning.")
    print("     '''")
    print("   - Injects: cmbagent.inject_to_agents(['planner'], instructions, mode='append')")
    print("   - Planner agent now 'sees' the feedback in its system message")
    
    print("\n3. Planning Phase iteration loop:")
    print("   - After each human review, captures new feedback")
    print("   - Appends to feedback_history list")
    print("   - Reinjects combined feedback for next iteration")
    print("   - Compiles all feedback at end:")
    print("     combined_feedback = '\\n\\n'.join(all_iteration_feedback)")
    
    print("\n4. Control Phase receives combined feedback:")
    print("   - Extracts: hitl_feedback = shared_state.get('hitl_feedback')")
    print("   - Extracts: planning_feedback_history = shared_state.get('planning_feedback_history')")
    print("   - Builds instruction addition:")
    print("     '''")
    print("     ## Human Feedback from Planning Phase")
    print("     [Combined feedback from checkpoint + planning iterations]")
    print("     ")
    print("     Please keep this feedback in mind during execution.")
    print("     '''")
    print("   - Injects: cmbagent.inject_to_agents(['engineer'], instructions, mode='append')")
    
    print("\n5. Control Phase step execution:")
    print("   - Before/after each step, human can provide additional guidance")
    print("   - New feedback accumulated: self._accumulated_feedback += new_feedback")
    print("   - Included in task for next step: _build_step_task() includes guidance")
    print("   - Agents continuously updated with latest human input")
    
    print("\n6. Control Phase output:")
    print("   - Passes all feedback in shared_state:")
    print("     - control_feedback: List of step-level interventions")
    print("     - all_hitl_feedback: Complete accumulated feedback")
    print("   - Downstream phases can access complete history")
    
    print("\n" + "="*70)
    print("KEY INSIGHT: Feedback is continuously injected into agent")
    print("instructions, creating a 'persistent memory' of human guidance")
    print("="*70)


async def example_practical_workflow():
    """
    Practical example: Research paper analysis with HITL feedback.
    """
    print("\n" + "="*70)
    print("PRACTICAL EXAMPLE: Research Paper Analysis")
    print("="*70)
    
    print("\nScenario: Analyzing a cosmology paper and creating summary")
    print("\nHuman provides feedback at each stage:")
    
    print("\n1. Checkpoint Phase:")
    print("   Task: 'Analyze paper on CMB lensing and create technical summary'")
    print("   → Human feedback: 'Pay special attention to systematic errors")
    print("                      and comparison with previous results'")
    
    print("\n2. Planning Phase (Iteration 1):")
    print("   Plan generated with 5 steps:")
    print("   1. Download paper")
    print("   2. Extract key results")
    print("   3. Analyze methodology")
    print("   4. Compare with literature")
    print("   5. Create summary")
    print("   → Human feedback: 'Add step to check for code availability")
    print("                      and reproducibility concerns'")
    
    print("\n3. Planning Phase (Iteration 2):")
    print("   Revised plan with 6 steps (added reproducibility check)")
    print("   → Human approves: 'Looks good, proceed'")
    
    print("\n4. Control Phase - Step 1 (Download):")
    print("   Before execution:")
    print("   → Human guidance: 'Also grab supplementary materials if available'")
    print("   [Step executes with guidance in mind]")
    print("   After execution:")
    print("   → Human notes: 'Good, supplementary has additional data tables'")
    
    print("\n5. Control Phase - Step 2 (Extract results):")
    print("   [Agent now knows about supplementary tables from previous feedback]")
    print("   Before execution:")
    print("   → Human: 'approve' (no additional guidance needed)")
    print("   After execution:")
    print("   → Human: 'Make sure to extract error bars from Table 3'")
    
    print("\n6. Control Phase - Steps 3-6:")
    print("   [Continue with accumulated feedback from all previous interactions]")
    print("   Each step benefits from complete context of human guidance")
    
    print("\n7. Final Output:")
    print("   - Technical summary created")
    print("   - Complete feedback history preserved:")
    print("     * Initial focus on systematic errors")
    print("     * Added reproducibility check")
    print("     * Used supplementary materials")
    print("     * Included error bars from Table 3")
    print("   - Can be reviewed against human requirements")
    
    print("\n" + "="*70)
    print("✓ Human remained in control throughout entire process")
    print("✓ Feedback accumulated and influenced every subsequent step")
    print("✓ Complete audit trail of human guidance preserved")
    print("="*70)


async def main():
    """Run all examples."""
    
    print("\n" + "#"*70)
    print("# HITL FEEDBACK FLOW EXAMPLES")
    print("#"*70)
    
    # Example 1: Complete flow
    print("\n\nEXAMPLE 1: Complete Feedback Flow")
    print("="*70)
    # Note: This would require actual ApprovalManager setup
    # await example_complete_feedback_flow()
    print("(See code for async implementation)")
    
    # Example 2: Mechanism explanation
    print("\n\nEXAMPLE 2: Feedback Injection Mechanism")
    await example_feedback_injection_in_agents()
    
    # Example 3: Practical workflow
    print("\n\nEXAMPLE 3: Practical Workflow")
    await example_practical_workflow()
    
    print("\n\n" + "#"*70)
    print("# SUMMARY")
    print("#"*70)
    
    print("""
Key Features of HITL Feedback System:

1. **Persistent Feedback Chain**
   - Feedback from each phase preserved and passed forward
   - Complete history available to all downstream phases
   - Agents continuously updated with latest guidance

2. **Multi-Level Feedback**
   - Checkpoint: Initial approval/guidance
   - Planning: Iterative plan refinement
   - Control: Step-by-step corrections
   - Each level builds on previous feedback

3. **Agent Instruction Injection**
   - Feedback injected into agent system messages
   - Agents "see" feedback as part of their instructions
   - Creates persistent memory of human guidance

4. **Structured Feedback Storage**
   - hitl_feedback: Combined feedback from all phases
   - planning_feedback_history: List of planning iterations
   - control_feedback: List of step-level interventions
   - all_hitl_feedback: Complete accumulated feedback

5. **Flexible Approval Modes**
   - before_step: Guide execution before it happens
   - after_step: Correct/annotate after completion
   - both: Maximum control at every step
   - on_error: Only intervene when needed

6. **Workflow Integration**
   - Works with WorkflowComposer's HITL workflows
   - Compatible with non-HITL phases (feedback passed through)
   - Can mix HITL and autonomous phases

Usage Pattern:
    checkpoint (initial guidance)
        → planning (iterative refinement with feedback)
            → control (step-by-step with feedback)
                → next phase (receives complete feedback history)

This creates a complete Human-in-the-Loop system where:
- Human maintains oversight and control
- Feedback influences all subsequent steps
- Complete audit trail preserved
- Agents learn from human guidance throughout process
    """)


if __name__ == "__main__":
    asyncio.run(main())
