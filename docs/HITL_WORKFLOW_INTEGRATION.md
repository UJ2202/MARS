# HITL Workflow Integration Guide

## Overview

The HITL (Human-in-the-Loop) Interactive workflow is now fully integrated into CMBAgent, providing complete end-to-end human control over both planning and execution phases.

## What Was Added

### 1. New HITL Workflow Module (`cmbagent/workflows/hitl_workflow.py`)

Three new workflow functions for different levels of human control:

#### `hitl_interactive_workflow()`
**Full human-in-the-loop control** - Guide planning iteratively and approve/review each execution step.

- **Planning Phase**: HITLPlanningPhase with iterative feedback
- **Control Phase**: HITLControlPhase with step-by-step approval
- **Feedback Flow**: Complete feedback chain from planning through execution

**Configuration Options:**
```python
{
    "max_plan_steps": 5,              # Max steps in the plan
    "max_human_iterations": 3,        # Max planning refinement iterations
    "approval_mode": "both",          # When to request approval:
                                      #   - "both": Before & after each step
                                      #   - "before_step": Before each step
                                      #   - "after_step": After each step
                                      #   - "on_error": Only when errors occur
    "allow_plan_modification": true,  # Allow direct plan editing
    "allow_step_skip": true,          # Allow skipping steps
    "allow_step_retry": true,         # Allow retrying failed steps
    "show_step_context": true,        # Show accumulated context
}
```

#### `hitl_planning_only_workflow()`
**Interactive planning with autonomous execution** - Human guides planning, execution runs autonomously.

- **Planning Phase**: HITLPlanningPhase with iterative feedback
- **Control Phase**: Standard ControlPhase (autonomous)
- **Best for**: When you want control over the plan but trust execution

#### `hitl_error_recovery_workflow()`
**Autonomous with error recovery** - Runs autonomously until errors, then human intervenes.

- **Planning Phase**: Standard PlanningPhase (autonomous)
- **Control Phase**: HITLControlPhase with `approval_mode="on_error"`
- **Best for**: Mostly reliable workflows with occasional issues

### 2. UI Integration (`cmbagent-ui/components/TaskInput.tsx`)

New **🤝 HITL Interactive** mode button added to the UI:

- Located next to "Deep Research", "One Shot", and "Idea Generation"
- Tooltip explains: "Full human-in-the-loop control - guide planning and approve each step during execution"
- Advanced settings include:
  - Max Planning Iterations (1-10)
  - Approval Mode dropdown (both/before_step/after_step/on_error)
  - Agent model selections (Planner, Engineer, Researcher)

### 3. Backend Integration (`backend/execution/task_executor.py`)

New `hitl-interactive` mode handler:

```python
elif mode == "hitl-interactive":
    results = hitl_workflow.hitl_interactive_workflow(
        task=task,
        max_plan_steps=max_plan_steps,
        max_human_iterations=max_human_iterations,
        approval_mode=approval_mode,
        allow_plan_modification=allow_plan_modification,
        allow_step_skip=allow_step_skip,
        allow_step_retry=allow_step_retry,
        show_step_context=show_step_context,
        planner_model=planner_model,
        engineer_model=engineer_model,
        researcher_model=researcher_model,
        work_dir=task_work_dir,
        api_keys=api_keys,
        callbacks=workflow_callbacks,
        approval_manager=approval_mgr
    )
```

### 4. Workflow Module Exports (`cmbagent/workflows/__init__.py`)

Added HITL workflows to public API:

```python
from cmbagent.workflows import (
    hitl_interactive_workflow,
    hitl_planning_only_workflow,
    hitl_error_recovery_workflow,
)
```

## How to Use

### From the UI

1. **Open the CMBAgent UI**
2. **Click the "🤝 HITL Interactive" button** (next to Deep Research)
3. **Enter your task** (e.g., "Analyze CMB power spectrum with custom parameters and plot results")
4. **Optionally configure advanced settings:**
   - Click the ⚙️ Settings icon
   - Adjust Max Planning Iterations
   - Choose Approval Mode
   - Select agent models
5. **Click ▶ Start Task**

### During Execution

#### Planning Phase (Iterative)
1. Agent generates initial plan
2. You review and choose:
   - ✅ **Approve**: Accept plan and proceed to execution
   - ❌ **Reject**: Cancel workflow
   - 🔄 **Revise**: Provide feedback for agent to improve plan
   - ✏️ **Modify**: Directly edit the plan yourself
3. If you provide feedback, agent revises and presents updated plan
4. Process repeats up to `max_human_iterations` times

#### Control Phase (Step-by-Step)

**Approval Mode: "both"** (Before & After)
1. **Before Step**: Review step details, approve/skip/reject
2. **Execution**: Agent executes the step
3. **After Step**: Review results, continue/redo/abort

**Approval Mode: "before_step"**
- Review and approve each step before execution
- Options: Approve, Skip, Reject

**Approval Mode: "after_step"**
- Review results after each step completes
- Options: Continue, Redo, Abort

**Approval Mode: "on_error"**
- Execution runs autonomously
- Only intervene when errors occur
- Options: Retry, Skip, Abort

### From Python Code

```python
from cmbagent.workflows import hitl_interactive_workflow

# Full HITL control
results = hitl_interactive_workflow(
    task="Calculate CMB power spectrum and plot results",
    max_plan_steps=5,
    max_human_iterations=3,
    approval_mode="both",  # Before & after each step
    work_dir="~/cmbagent_output",
)

# Planning only HITL
from cmbagent.workflows import hitl_planning_only_workflow

results = hitl_planning_only_workflow(
    task="Analyze astronomical data",
    max_human_iterations=2,
    work_dir="~/cmbagent_output",
)

# Error recovery HITL
from cmbagent.workflows import hitl_error_recovery_workflow

results = hitl_error_recovery_workflow(
    task="Process complex dataset",
    max_n_attempts=3,
    work_dir="~/cmbagent_output",
)
```

### Using Pre-defined HITL Workflows

The system also provides pre-defined HITL workflows via the composer:

```python
from cmbagent.workflows import (
    FULL_INTERACTIVE_WORKFLOW,      # HITLPlanning → HITLControl (both)
    INTERACTIVE_PLANNING_WORKFLOW,  # HITLPlanning → Control (autonomous)
    INTERACTIVE_CONTROL_WORKFLOW,   # Planning → HITLCheckpoint → HITLControl
    ERROR_RECOVERY_WORKFLOW,        # Planning → HITLControl (on_error)
    PROGRESSIVE_REVIEW_WORKFLOW,    # Planning → HITLControl (after_step)
)

from cmbagent.workflows import WorkflowExecutor

executor = WorkflowExecutor(
    workflow=FULL_INTERACTIVE_WORKFLOW,
    task="Your task here",
    work_dir="~/output",
    api_keys=api_keys,
)

result = executor.run_sync()
```

## Feedback Flow

Human feedback flows seamlessly through the workflow:

```
┌──────────────────┐         ┌──────────────────┐
│ Planning Phase   │────────>│ Control Phase    │
│ (HITL)           │         │ (HITL)           │
└──────────────────┘         └──────────────────┘
         │                            │
         │  feedback:                 │  feedback:
         │  "Use log scale"           │  "Increase resolution"
         │  "Add validation"          │  "Check edge cases"
         v                            v
    shared_state                 shared_state
    hitl_feedback                all_hitl_feedback
```

All feedback is:
1. **Captured** at each human interaction
2. **Injected** into agent instructions
3. **Accumulated** in shared_state
4. **Passed forward** to subsequent phases
5. **Available** in final results

Access feedback in results:
```python
results = hitl_interactive_workflow(...)

# Get accumulated feedback
hitl_feedback = results.get('hitl_feedback', '')
planning_history = results.get('planning_feedback_history', [])
step_feedback = results.get('step_feedback', [])
```

## Example Tasks

Good tasks for HITL Interactive mode:

1. **Complex Analysis with Custom Parameters**
   ```
   Analyze CMB power spectrum with custom parameters and plot results
   ```

2. **Multi-Step Research Workflows**
   ```
   Build a market impact model incorporating order flow and volatility
   ```

3. **Data Processing Pipelines**
   ```
   Process astronomical data from JWST and identify candidate exoplanets
   ```

4. **Iterative Refinement Tasks**
   ```
   Generate and refine a financial risk model with backtesting
   ```

## Comparison with Other Modes

| Mode | Planning | Execution | Best For |
|------|----------|-----------|----------|
| **One Shot** | None | Autonomous | Quick, simple tasks |
| **Deep Research** | Autonomous | Autonomous | Standard multi-step tasks |
| **HITL Interactive** | Interactive | Interactive | Complex tasks needing guidance |
| **Idea Generation** | Autonomous | Idea agents | Brainstorming and ideation |

## Benefits

### For Users
- ✅ **Maximum control** over agent behavior
- ✅ **Guide planning** with domain expertise
- ✅ **Approve/review** each execution step
- ✅ **Continuous feedback** that persists through workflow
- ✅ **Catch and fix errors** before they cascade
- ✅ **Learn from agent** during interactive sessions

### For Complex Tasks
- ✅ **Reduce errors** with human oversight
- ✅ **Incorporate expertise** at every stage
- ✅ **Adjust course** based on intermediate results
- ✅ **Ensure quality** through iterative refinement
- ✅ **Build trust** through transparency

## Technical Details

### Architecture

The HITL workflow uses:
1. **HITLPlanningPhase**: From `cmbagent/phases/hitl_planning.py`
2. **HITLControlPhase**: From `cmbagent/phases/hitl_control.py`
3. **WorkflowExecutor**: From `cmbagent/workflows/composer.py`
4. **Approval Manager**: Database-backed approval system

### Phase Flow

```python
# 1. Create workflow definition
workflow = WorkflowDefinition(
    phases=[
        {"type": "hitl_planning", "config": {...}},
        {"type": "hitl_control", "config": {...}},
    ]
)

# 2. Create executor
executor = WorkflowExecutor(
    workflow=workflow,
    task=task,
    work_dir=work_dir,
    api_keys=api_keys,
    approval_manager=approval_manager,  # Connects to UI
)

# 3. Execute
context = executor.run_sync()
```

### Approval Handling

Approvals are handled by:
- **Backend**: `cmbagent.database.approval_controller.ApprovalController`
- **WebSocket**: Real-time approval requests sent to UI
- **UI**: `ApprovalDialog` component displays approval UI
- **Manager**: `PhaseExecutionManager` integrates approval into phases

## Files Modified/Created

### New Files
- ✨ `cmbagent/workflows/hitl_workflow.py` - HITL workflow implementations

### Modified Files
- 📝 `cmbagent-ui/components/TaskInput.tsx` - Added HITL mode button and config
- 📝 `backend/execution/task_executor.py` - Added HITL mode handler
- 📝 `cmbagent/workflows/__init__.py` - Exported HITL workflows
- 📝 `docs/HITL_WORKFLOW_INTEGRATION.md` - This guide

## Testing

### Manual Testing Steps

1. **Start the backend and UI**
   ```bash
   cd backend && python main.py
   cd cmbagent-ui && npm run dev
   ```

2. **Open the UI** at http://localhost:3000

3. **Click "🤝 HITL Interactive"**

4. **Enter a test task**: "Plot a simple sine wave with custom parameters"

5. **Configure settings** (optional):
   - Max Planning Iterations: 2
   - Approval Mode: "Both"

6. **Start the task**

7. **Verify planning phase**:
   - Approval dialog appears
   - You can review, revise, or approve plan
   - Feedback is captured and shown to agent

8. **Verify control phase**:
   - Before-step approval appears
   - After-step review appears
   - Can skip steps or retry errors

### Automated Testing

See `tests/test_hitl_feedback_flow.py` for comprehensive tests of:
- Feedback capture in planning
- Feedback reception in control
- Complete feedback flow chain

## Troubleshooting

### Issue: Approval dialog not appearing
**Solution**: Check that:
- WebSocket connection is established
- Backend approval system is configured
- Database is initialized with approval tables

### Issue: Feedback not flowing between phases
**Solution**: Check that:
- `shared_state` is being passed correctly
- Feedback is in `shared_state['hitl_feedback']`
- Phase implementations inject feedback into agents

### Issue: UI button not working
**Solution**: Check that:
- Frontend rebuilt: `npm run build` in `cmbagent-ui/`
- Backend restarted to load new workflow module
- No import errors in Python console

## Next Steps

### Potential Enhancements

1. **Feedback Templates**
   - Pre-defined feedback snippets
   - Common guidance patterns
   - Auto-suggest based on history

2. **Approval Presets**
   - Save/load approval configurations
   - Team-specific approval workflows
   - Project-based defaults

3. **Feedback Analytics**
   - Track feedback patterns
   - Identify common corrections
   - Learn from successful interventions

4. **Multi-User HITL**
   - Concurrent approval from team
   - Role-based approval gates
   - Conflict resolution

5. **Smart Approval Suggestions**
   - AI recommends when to intervene
   - Risk-based approval triggers
   - Context-aware suggestions

## Related Documentation

- [HITL_PHASES_GUIDE.md](./HITL_PHASES_GUIDE.md) - Detailed phase documentation
- [HITL_FEEDBACK_IMPLEMENTATION.md](./HITL_FEEDBACK_IMPLEMENTATION.md) - Feedback system details
- [HITL_FEEDBACK_QUICKREF.md](./HITL_FEEDBACK_QUICKREF.md) - Quick reference guide
- [PHASE_DEVELOPMENT_GUIDE.md](./PHASE_DEVELOPMENT_GUIDE.md) - How to create custom phases

---

**Status**: ✅ Complete and tested  
**Version**: 1.0  
**Date**: January 29, 2025
