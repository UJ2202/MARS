# HITL "Redo" Functionality Analysis

## Overview

The HITL workflow has "redo" functionality mentioned in several places, but the implementation is **incomplete and inconsistent** across different levels:

1. **Step-level redo** (control phase) - UI exists, backend broken
2. **Phase-level redo** (planning/control phases) - doesn't exist at all
3. **Iteration-level redo** (planning iterations) - working via "revise"

---

## Current State of "Redo" Implementations

### 1. Planning Phase: No "Redo" (Uses "Revise" Instead)

**Location:** `cmbagent/phases/hitl_planning.py:296`

**Options Available:**
```python
options=["approve", "reject", "revise", "modify"]
```

**Behavior:**
- ✅ **"revise"**: Continues to next iteration with user feedback (works)
- ✅ **"approve"**: Accepts plan and moves to control phase (works, but exits too early - see Issue #1)
- ✅ **"reject"**: Cancels workflow (works)
- ✅ **"modify"**: Direct plan editing (works)
- ❌ **"redo"**: Not available - no way to restart planning from scratch

**Flow:**
```
Planning Iteration 1
  ↓
User clicks "revise" + provides feedback
  ↓
Planning Iteration 2 (incorporates feedback)
  ↓
User clicks "approve"
  ↓
Move to Control Phase
```

**No way to say:** "Start planning over from scratch without going to control"

---

### 2. Control Phase - Step-Level: "Redo" UI Exists but Backend is Broken ❌

**Location:** `cmbagent/phases/hitl_control.py:438-440`

**Options Available (after-step review):**
```python
options=["continue", "abort", "redo"]
```

**Current Implementation:**
```python
# Line 438-440
elif review_result is None:  # Redo
    # Could implement redo logic here
    pass
```

**Status:** ❌❌❌ **COMPLETELY BROKEN** ❌❌❌

**What Happens:**
1. User clicks "Redo" after step completes
2. `_request_step_review()` returns `None`
3. Code hits `pass` statement
4. **Continues to next step anyway!**
5. The redo request is ignored

**What SHOULD Happen:**
```python
elif review_result is None:  # Redo
    # Re-execute this step
    print(f"-> Redoing step {step_num}...")
    continue  # Jump back to start of step loop
```

But there's a problem: the step loop is not designed for redo!

**Step Loop Structure (Problematic for Redo):**
```python
# Line 230
for step_num in steps_to_execute:
    step = plan_steps[step_num - 1]

    # ... execute step ...

    # After-step review
    review_result = await self._request_step_review(...)
    if review_result is None:  # Redo
        pass  # ❌ Can't "continue" here - we're not in a while loop!

    # Next iteration of for loop = next step
```

**To fix this, need to change structure:**
```python
step_index = 0
while step_index < len(steps_to_execute):
    step_num = steps_to_execute[step_index]

    # ... execute step ...

    # After-step review
    review_result = await self._request_step_review(...)
    if review_result is None:  # Redo
        print(f"-> Redoing step {step_num}...")
        continue  # ✅ Jump back to while start, re-execute same step

    step_index += 1  # Only advance if not redoing
```

---

### 3. Phase-Level Redo: Doesn't Exist ❌

**Location:** `cmbagent/workflows/composer.py:139-204`

**Current Workflow Execution:**
```python
# Line 139
for i, phase in enumerate(self.phases):
    # Execute phase
    result = await phase.execute(phase_context)

    # Handle failure
    if not result.succeeded:
        raise RuntimeError(error_msg)  # Stops entire workflow

    # Move to next phase
```

**Problem:**
- Phases run sequentially, no backtracking
- If control phase completes with issues, no way to go back to planning
- No "redo planning" option after control starts

**What Users Might Want:**

**Scenario A: Redo Planning After Seeing Control Results**
```
Planning Phase → Plan approved
  ↓
Control Phase → Step 1 fails badly
  ↓
User: "Wait, the plan is wrong. Let me redo planning."
  ↓
❌ Currently impossible
```

**Scenario B: Redo Entire Control Phase**
```
Planning Phase → Plan approved
  ↓
Control Phase → Complete all steps, but results are not satisfactory
  ↓
User: "Redo the entire control phase with the same plan"
  ↓
❌ Currently impossible
```

**Scenario C: Workflow-Level Checkpoints**
```
Planning Phase [checkpoint A]
  ↓
Control Phase [checkpoint B]
  ↓
Validation Phase [checkpoint C]
  ↓
User at checkpoint C: "Go back to checkpoint A"
  ↓
❌ Currently impossible
```

---

## Detailed Analysis of Each Redo Type

### Step-Level Redo (Most Critical to Fix)

**Purpose:** Re-execute a failed or unsatisfactory step without moving forward

**Use Cases:**
1. Step completed but output is wrong
2. User wants to try with different guidance
3. Transient error occurred (network issue, API timeout)

**Current Status:** UI exists, backend broken

**Required Changes:**

1. **Change loop structure** (hitl_control.py:230):
```python
# OLD:
for step_num in steps_to_execute:
    # ... execute ...

# NEW:
step_index = 0
while step_index < len(steps_to_execute):
    step_num = steps_to_execute[step_index]
    step_redo_requested = False

    # ... execute step ...

    # After-step review
    if self.config.approval_mode in ["after_step", "both"]:
        review_result = await self._request_step_review(...)

        if review_result is None:  # Redo
            step_redo_requested = True
            print(f"→ Redoing step {step_num} as requested by human")

            # Optional: prompt for new guidance
            if hasattr(review_result, 'user_feedback') and review_result.user_feedback:
                # Add feedback for redo attempt
                self._accumulated_feedback += f"\n\n**Step {step_num} redo guidance:** {review_result.user_feedback}"

    # Only advance if not redoing
    if not step_redo_requested:
        step_index += 1
```

2. **Consider redo limits**:
```python
# Prevent infinite redo loops
max_step_redos: int = 3  # Config parameter

step_redo_count = {}  # Track redos per step

if step_redo_requested:
    count = step_redo_count.get(step_num, 0) + 1
    if count > self.config.max_step_redos:
        print(f"⚠ Max redos ({self.config.max_step_redos}) reached for step {step_num}")
        step_index += 1  # Force move to next step
    else:
        step_redo_count[step_num] = count
        print(f"→ Redo attempt {count}/{self.config.max_step_redos}")
        # continue back to while start
```

3. **Preserve feedback across redo attempts**:
```python
# When redoing, keep accumulated feedback for the "redo" attempt
# But also allow user to provide additional guidance
if review_result is None and hasattr(review_result, 'user_feedback'):
    redo_guidance = review_result.user_feedback
    if redo_guidance:
        self._accumulated_feedback += f"\n\n**Redo guidance for step {step_num}:** {redo_guidance}"
```

---

### Phase-Level Redo (Advanced Feature)

**Purpose:** Restart an entire phase (planning or control) from the beginning

**Use Cases:**

**Planning Phase Redo:**
- Control phase reveals the plan was fundamentally flawed
- User wants to replan with new understanding

**Control Phase Redo:**
- All steps completed but overall result unsatisfactory
- User wants to retry execution with same plan but different approach

**Implementation Approach:**

#### Option A: Add Redo to Phase Results
```python
# cmbagent/phases/base.py
@dataclass
class PhaseResult:
    # ... existing fields ...
    redo_requested: bool = False  # NEW field
```

#### Option B: Modify Workflow Executor
```python
# cmbagent/workflows/composer.py
async def run(self) -> WorkflowContext:
    phase_index = 0
    max_phase_redos = 2  # Config: limit redos per phase
    phase_redo_counts = {}

    while phase_index < len(self.phases):
        phase = self.phases[phase_index]

        # Execute phase
        result = await phase.execute(phase_context)

        # Check if redo requested
        if result.redo_requested:
            count = phase_redo_counts.get(phase_index, 0) + 1
            if count > max_phase_redos:
                print(f"⚠ Max phase redos exceeded for {phase.display_name}")
                phase_index += 1  # Move to next phase
            else:
                phase_redo_counts[phase_index] = count
                print(f"→ Redoing phase: {phase.display_name} (attempt {count})")
                # Don't increment phase_index - redo same phase
        else:
            phase_index += 1  # Normal: move to next phase
```

#### Option C: Add Phase Checkpoints
```python
class WorkflowExecutor:
    def __init__(self, ...):
        self.phase_checkpoints = {}  # Save phase contexts

    async def run(self):
        for i, phase in enumerate(self.phases):
            # Save checkpoint before phase
            self.phase_checkpoints[i] = phase_context.to_dict()

            result = await phase.execute(phase_context)

            # Check if user wants to jump back to earlier phase
            if result.jump_to_phase is not None:
                target_phase = result.jump_to_phase
                phase_context = self.restore_checkpoint(target_phase)
                # Jump back to that phase
```

---

### Iteration-Level Redo (Planning) - Already Works via "Revise"

**Current Status:** ✅ Working

**How It Works:**
```python
# Planning phase iteration loop
while iteration < max_human_iterations and not approved:
    iteration += 1

    # Generate plan
    cmbagent.solve(task_with_feedback, ...)

    # Get approval
    resolved = await approval_manager.wait_for_approval_async(...)

    if resolved.resolution == "revise":
        # Collect feedback, continue to next iteration
        feedback_history.append({'iteration': iteration, 'feedback': feedback})
        # Loop continues with feedback
```

**This Works Because:**
- It's a `while` loop (can continue indefinitely until approved or max iterations)
- Feedback is accumulated and passed to next iteration
- Each iteration generates a new plan incorporating previous feedback

---

## Summary of Redo Types and Status

| Redo Type | Location | Status | Priority | Complexity |
|-----------|----------|--------|----------|------------|
| **Step-level** (control) | hitl_control.py:438 | ❌ Broken | **HIGH** | Medium |
| **Iteration-level** (planning) | hitl_planning.py:229 | ✅ Works (via "revise") | N/A | N/A |
| **Phase-level** | composer.py:139 | ❌ Doesn't exist | Medium | High |
| **Workflow-level checkpoints** | composer.py | ❌ Doesn't exist | Low | Very High |

---

## Recommended Implementation Priority

### Priority 1: Fix Step-Level Redo (Critical) 🔥

**Why:**
- UI already exists
- Users expect it to work
- Common use case (redo a failed step)

**Changes Required:**
1. Convert `for step_num in steps_to_execute:` to `while` loop
2. Add `step_redo_requested` flag
3. Implement redo logic with feedback preservation
4. Add redo limit protection

**Estimated Effort:** 2-3 hours

---

### Priority 2: Add Phase-Level Redo (Important)

**Why:**
- Enables more flexible workflows
- Common pattern: "This plan doesn't work, let me replan"

**Changes Required:**
1. Add `redo_requested` field to PhaseResult
2. Modify WorkflowExecutor loop structure
3. Add phase-level approval option
4. Implement context restoration

**Estimated Effort:** 1-2 days

---

### Priority 3: Workflow Checkpoints (Nice to Have)

**Why:**
- Advanced feature for complex workflows
- Enables non-linear workflow navigation

**Changes Required:**
- Complete checkpoint system
- Context serialization/restoration
- UI for checkpoint navigation

**Estimated Effort:** 3-5 days

---

## Proposed API Design

### Step-Level Redo
```python
# In approval UI
options = ["continue", "abort", "redo"]

# User clicks "redo" with optional feedback
{
    "resolution": "redo",
    "user_feedback": "Try using a different approach for parsing"
}

# Backend behavior
# 1. Preserve feedback
# 2. Re-execute same step
# 3. Don't advance step counter
```

### Phase-Level Redo
```python
# At end of control phase, add option
options = ["complete", "redo_control", "redo_planning"]

# User clicks "redo_planning"
{
    "resolution": "redo_planning",
    "reason": "Plan needs fundamental changes"
}

# Backend behavior
# 1. Save control phase insights
# 2. Jump back to planning phase
# 3. Inject insights as context
```

---

## Implementation Challenges

### Challenge 1: Loop Structure Refactoring
**Problem:** Current code uses `for` loops, which don't support redo
**Solution:** Convert to `while` loops with manual index management

### Challenge 2: Context Preservation
**Problem:** When redoing, need to restore previous state
**Solution:** Save checkpoint before each step/phase execution

### Challenge 3: Feedback Accumulation
**Problem:** Redo guidance needs to be remembered but not duplicate old feedback
**Solution:** Tag feedback with attempt number and step/phase identifier

### Challenge 4: Infinite Loop Prevention
**Problem:** User could redo indefinitely
**Solution:** Implement max redo limits with clear error messages

---

## Testing Strategy

### Test Case 1: Step Redo with Feedback
```python
# Scenario: Step 1 produces wrong output
# 1. Execute step 1 → completes
# 2. User reviews → clicks "redo" with feedback "Use JSON format"
# 3. Step 1 re-executes with feedback
# 4. Verify: feedback appears in agent context
# 5. User reviews → clicks "continue"
# 6. Step 2 executes → verify it sees step 1 feedback
```

### Test Case 2: Max Redo Limit
```python
# Scenario: Prevent infinite redo loops
# 1. Execute step 1 → completes
# 2. User clicks "redo" → step 1 re-executes
# 3. User clicks "redo" → step 1 re-executes
# 4. User clicks "redo" → step 1 re-executes
# 5. User clicks "redo" → instead of redoing, show error:
#    "Max redos (3) reached. Moving to next step."
```

### Test Case 3: Phase Redo
```python
# Scenario: Redo planning after control starts
# 1. Complete planning phase → plan approved
# 2. Start control phase → execute step 1
# 3. Step 1 reveals plan is fundamentally wrong
# 4. User clicks "redo planning phase"
# 5. Verify: workflow goes back to planning
# 6. Verify: context from control phase is preserved as feedback
```

---

## Conclusion

**Current State:**
- ❌ Step-level redo is completely broken
- ✅ Iteration-level redo works (via "revise")
- ❌ Phase-level redo doesn't exist

**Recommended Action:**
1. **Immediate:** Fix step-level redo (Priority 1)
2. **Soon:** Add phase-level redo (Priority 2)
3. **Future:** Consider workflow checkpoints (Priority 3)

**User Impact:**
- Without step-level redo fix: Users click "redo" but nothing happens (bad UX)
- Without phase-level redo: Users can't backtrack to planning after starting control
- Fixing these will greatly improve workflow flexibility and user control
