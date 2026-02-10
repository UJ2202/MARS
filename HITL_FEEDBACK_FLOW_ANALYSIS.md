# HITL Feedback Flow Analysis

## Executive Summary

**Critical Issues Found:**
1. ❌ **Planning Phase**: Exits after 1 approval, doesn't allow iterative refinement
2. ❌ **Control Phase**: Collects user feedback but NEVER uses it to guide execution
3. ⚠️ **Feedback Transfer**: Planning feedback IS passed to control, but control ignores it

---

## Issue #1: Planning Phase Early Exit

### Location
`cmbagent/phases/hitl_planning.py:229-356`

### Current Behavior
```python
iteration = 0
approved = False

while iteration < self.config.max_human_iterations and not approved:
    iteration += 1

    # Generate plan
    cmbagent.solve(...)

    # Request approval
    resolved = await approval_manager.wait_for_approval_async(...)

    if resolved.resolution in ["approved", "approve"]:
        approved = True  # ❌ Loop exits immediately after first approval!
        final_plan = plan
        break  # Implicit break from approved=True
```

### Problem
- **After iteration 1**: If user approves → exits loop → goes to control phase
- **max_human_iterations=3**: This parameter is meaningless if user approves early
- **No iterative refinement**: User can't see "iteration 1 → revise → iteration 2 → revise → iteration 3 → approve"

### Expected Behavior
The system should:
1. Allow user to request revisions multiple times
2. Show how the plan evolves across iterations
3. Only exit when:
   - User explicitly approves AND satisfied with current iteration
   - OR max_human_iterations reached

### Root Cause
The loop condition `while ... and not approved` makes approval an immediate exit condition.

---

## Issue #2: Control Phase Feedback Black Hole

### Location
`cmbagent/phases/hitl_control.py:264-454`

### Current Behavior

#### Step 1: Feedback Collection (✅ Works)
```python
# Line 264-274: Before-step feedback
if 'feedback' in approval_result:
    feedback = approval_result['feedback']
    self._step_feedback.append({
        'step': step_num,
        'timing': 'before',
        'feedback': feedback,
    })
    # Accumulate
    self._accumulated_feedback += f"\n\n**Step {step_num} guidance:** {feedback}"
```

```python
# Line 442-454: After-step feedback
if 'feedback' in review_result:
    feedback = review_result['feedback']
    self._step_feedback.append({
        'step': step_num,
        'timing': 'after',
        'feedback': feedback,
    })
    # Accumulate
    self._accumulated_feedback += f"\n\n**Step {step_num} notes:** {feedback}"
```

**✅ Feedback is collected and stored in `self._accumulated_feedback`**

#### Step 2: Feedback Usage (❌ MISSING)
```python
# Line 299-356: Step execution
cmbagent = CMBAgent(
    cache_seed=42,
    work_dir=control_dir,
    agent_llm_configs=agent_llm_configs,
    # ...
)

# ❌ NO injection of self._accumulated_feedback here!
# The feedback just sits unused in memory

cmbagent.solve(
    task=context.task,  # ← Original task, no feedback appended
    initial_agent=starter_agent,
    shared_context=step_shared_context,  # ← No feedback in shared_context either
)
```

**❌ The accumulated feedback is NEVER fed back to the agents!**

### Comparison with Planning Phase (Which Does It Right)

```python
# hitl_planning.py:198-213
previous_hitl_feedback = context.shared_state.get('hitl_feedback', '')

base_instructions = ""
if previous_hitl_feedback:
    base_instructions += f"\n\n## Previous Human Feedback\n{previous_hitl_feedback}\n"

# ✅ CORRECTLY injects feedback into agents
cmbagent.inject_to_agents(
    ["planner"],
    base_instructions,
    mode="append"
)
```

### Impact
- Users provide guidance before/after steps
- The guidance is displayed in the UI and stored
- **But the agents executing the steps never see this guidance**
- Feedback is only output at the end for logging purposes (line 539)

---

## Issue #3: Feedback Transfer Between Phases

### Planning → Control Transfer (✅ Works)

```python
# hitl_planning.py:403-427
# Compile feedback from planning iterations
all_feedback = []
for feedback_item in human_feedback_history:
    all_feedback.append(feedback_item.get('feedback', ''))

combined_feedback = "\n\n".join(all_feedback)

# ✅ Pass to control phase via shared state
output_data = {
    'shared': {
        'hitl_feedback': combined_feedback,  # ← Passed forward
        'planning_feedback_history': human_feedback_history,
    }
}
```

### Control Phase Reception (⚠️ Receives but ignores)

```python
# hitl_control.py:192
hitl_feedback = context.shared_state.get('hitl_feedback', '')

# Line 226
self._accumulated_feedback = hitl_feedback  # ← Received from planning

# ... but then never injected into agents (see Issue #2)
```

**Result:**
- Planning feedback IS transferred to control phase
- BUT control phase doesn't use it (same issue as Issue #2)

---

## Detailed Code Flow Trace

### Planning Phase Iteration Loop

```
Iteration 1:
├─ Generate plan with planner agent
├─ Present plan to user
├─ User options:
│  ├─ "approve" → approved=True → EXIT LOOP ❌ (Issue #1)
│  ├─ "reject" → return failure
│  ├─ "revise" → collect feedback → next iteration ✅
│  └─ "modify" → approved=True → EXIT LOOP
└─ If "revise": feedback added to task for iteration 2

Iteration 2 (only if user chose "revise"):
├─ Task includes: original_task + feedback from iteration 1
├─ Generate revised plan
├─ Present to user
├─ User options: (same as above)
└─ Pattern repeats...

Max Iterations: 3 (default)
Exit Conditions:
  - approved=True (happens on first "approve"!) ❌
  - OR iteration >= max_human_iterations
```

### Control Phase Step Execution Loop

```
For each step in plan:
├─ Before-Step Approval (if approval_mode includes "before_step"):
│  ├─ Request approval from user
│  ├─ User can provide feedback
│  └─ Feedback stored in self._accumulated_feedback ✅
│
├─ Execute Step:
│  ├─ Create fresh CMBAgent
│  ├─ ❌ NO injection of self._accumulated_feedback
│  ├─ Execute with cmbagent.solve()
│  └─ Agents don't see any user feedback ❌
│
├─ After-Step Review (if approval_mode includes "after_step"):
│  ├─ Show results to user
│  ├─ User can provide feedback
│  └─ Feedback stored in self._accumulated_feedback ✅
│
└─ Continue to next step
   └─ Previous feedback still not used! ❌
```

---

## How Feedback SHOULD Flow

### Planning Phase (Needs Fix)
```
User provides task
  ↓
Iteration 1: Generate plan
  ↓
Show to user → User: "revise, add more detail"
  ↓
Iteration 2: Generate plan (with feedback)
  ↓
Show to user → User: "revise, change step 3"
  ↓
Iteration 3: Generate plan (with all feedback)
  ↓
Show to user → User: "approve"
  ↓
Go to control phase
```

**Current bug:** Exits after iteration 1 if user approves immediately

### Control Phase (Needs Fix)
```
Step 1 execution preparation
  ↓
User: "Make sure to use Python 3.10" (before-step feedback)
  ↓
Agent should receive:
  - Original task
  - Plan step description
  - ✅ "Make sure to use Python 3.10" ← SHOULD BE INJECTED
  ↓
Execute step with this context
  ↓
Step 1 results
  ↓
User: "The output looks wrong, check the format" (after-step feedback)
  ↓
Step 2 execution preparation
  ↓
Agent should receive:
  - Original task
  - Plan step 2 description
  - ✅ Previous feedback: "use Python 3.10" + "check format" ← SHOULD BE INJECTED
  ↓
Execute step with accumulated context
```

**Current bug:** Feedback is collected but never injected into agents

---

## Recommended Fixes

### Fix #1: Planning Phase Iteration Control

**File:** `cmbagent/phases/hitl_planning.py`

**Option A: Force minimum iterations**
```python
# Add config parameter
min_human_iterations: int = 2  # Must go through at least 2 iterations

# Update loop logic
while iteration < self.config.max_human_iterations and not approved:
    iteration += 1
    # ... generate plan ...

    # Check if approval is allowed
    if resolved.resolution in ["approved", "approve"]:
        if iteration >= self.config.min_human_iterations:
            approved = True  # Can approve now
        else:
            print(f"Minimum {self.config.min_human_iterations} iterations required")
            # Continue to next iteration
```

**Option B: Explicit iteration counter UI**
```python
# Show user current iteration and ask if they want more
message = f"Iteration {iteration}/{self.config.max_human_iterations}\n\n"
message += "Do you want to:\n"
message += "- Approve this plan (will proceed to execution)\n"
message += "- Request another iteration (will generate revised plan)\n"
```

**Option C: Remove early exit logic**
```python
# Always go through all iterations, collect feedback at each step
# Only final iteration has "approve" option
if iteration < self.config.max_human_iterations:
    options = ["revise", "reject"]  # No approve until final iteration
else:
    options = ["approve", "reject", "revise"]
```

### Fix #2: Control Phase Feedback Injection

**File:** `cmbagent/phases/hitl_control.py`

**Add after line 306 (after CMBAgent creation):**
```python
cmbagent = CMBAgent(
    cache_seed=42,
    work_dir=control_dir,
    agent_llm_configs=agent_llm_configs,
    mode="planning_and_control_context_carryover",
    api_keys=api_keys,
)

# ✅ ADD THIS: Inject accumulated feedback into agents
if self._accumulated_feedback:
    feedback_instructions = f"""
## Human Guidance and Feedback

The human has provided the following guidance and feedback that should be
considered during execution:

{self._accumulated_feedback}

Please take this feedback into account when executing the current step.
"""
    cmbagent.inject_to_agents(
        ["engineer", "researcher", "control"],
        feedback_instructions,
        mode="append"
    )
    print(f"→ Injected accumulated feedback into agents for step {step_num}")
```

**Alternative: Inject into task**
```python
# Instead of modifying agent instructions, prepend to task
enhanced_task = context.task
if self._accumulated_feedback:
    enhanced_task = f"""
{context.task}

## Human Guidance:
{self._accumulated_feedback}
"""

cmbagent.solve(
    task=enhanced_task,  # ← Use enhanced task with feedback
    initial_agent=starter_agent,
    max_rounds=self.config.max_rounds,
    shared_context=step_shared_context,
    step=step_num,
)
```

---

## Testing the Fixes

### Test Case 1: Planning Iteration
```python
# Start workflow with max_human_iterations=3
workflow = hitl_interactive_workflow(
    task="Create a web scraper",
    max_human_iterations=3,
)

# Expected behavior:
# Iteration 1: Generate plan → User clicks "approve"
#   → Should NOT exit, should continue to iteration 2
#   → Or show warning: "Continue refining or approve for final?"
```

### Test Case 2: Control Feedback
```python
# Start workflow with approval_mode="both"
workflow = hitl_interactive_workflow(
    task="Create a web scraper",
    approval_mode="both",
)

# Expected behavior:
# Step 1 before: User provides feedback "Use requests library"
#   → Step 1 execution: Agent should see this feedback in context
#   → Check agent's system message includes the feedback
# Step 1 after: User provides feedback "Good, but add error handling"
#   → Step 2 execution: Agent should see BOTH feedbacks
```

---

## Summary Table

| Issue | Location | Current Status | Impact | Fix Complexity |
|-------|----------|----------------|--------|----------------|
| Planning early exit | hitl_planning.py:229-356 | ❌ Broken | High - defeats iterative planning | Medium |
| Control feedback not injected | hitl_control.py:264-356 | ❌ Broken | Critical - feedback ignored | Easy |
| Feedback transfer between phases | Both files | ⚠️ Partial | Medium - planning→control works, but control ignores it | Covered by fix #2 |
| Step-level "redo" broken | hitl_control.py:438-440 | ❌ Broken | High - users expect this to work | Medium |
| Phase-level "redo" missing | composer.py:139-204 | ❌ Doesn't exist | Medium - limits workflow flexibility | High |

**Note:** See `HITL_REDO_FUNCTIONALITY_ANALYSIS.md` for detailed analysis of the "redo" functionality issues.

---

## Additional Observations

### What Works Well ✅
1. Approval manager integration
2. WebSocket event propagation
3. Feedback UI collection
4. Database logging of approvals
5. Planning phase feedback injection (into planning iterations)

### What's Broken ❌
1. Planning exits too early
2. Control phase feedback collection is cosmetic only
3. User guidance has no effect on execution

### Root Cause Analysis
- **Planning issue**: Loop termination logic doesn't align with UX expectations
- **Control issue**: Missing `inject_to_agents()` call after feedback collection
- **Design gap**: No clear specification of "when should feedback affect agents?"
