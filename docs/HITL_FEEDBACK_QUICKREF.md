# HITL Feedback Flow - Quick Reference

## TL;DR

Human feedback now flows between HITL phases automatically. Just use `shared_state` - the system handles the rest.

## 3-Step Setup

```python
# 1. Checkpoint captures feedback
checkpoint_result = await checkpoint.execute(context, manager)

# 2. Pass feedback to planning via shared_state
planning_context = PhaseContext(
    ...,
    shared_state={'hitl_feedback': checkpoint_result.output_data['shared']['hitl_feedback']}
)
planning_result = await planning.execute(planning_context, manager)

# 3. Pass to control
control_context = PhaseContext(
    ...,
    shared_state={'hitl_feedback': planning_result.output_data['shared']['hitl_feedback']}
)
control_result = await control.execute(control_context, manager)
```

## What Gets Passed

### From Checkpoint
```python
shared_state = {
    'hitl_feedback': "User's initial feedback/guidance",
    'hitl_approved': True/False,
}
```

### From Planning
```python
shared_state = {
    'hitl_feedback': "Combined feedback from checkpoint + all iterations",
    'planning_feedback_history': ["Iteration 1 feedback", "Iteration 2 feedback", ...],
}
```

### From Control
```python
shared_state = {
    'all_hitl_feedback': "Complete feedback from checkpoint → planning → control",
    'control_feedback': [
        {'step': 1, 'timing': 'before', 'feedback': "..."},
        {'step': 1, 'timing': 'after', 'feedback': "..."},
        ...
    ],
}
```

## How It Works Internally

### Planning Phase
```python
# Reads previous feedback
previous_feedback = context.shared_state.get('hitl_feedback', '')

# Injects into agent
if previous_feedback:
    instructions = f"## Previous Human Feedback\n{previous_feedback}"
    cmbagent.inject_to_agents(['planner'], instructions, mode='append')

# Agent now "sees" feedback in its system message
```

### Control Phase
```python
# Reads planning feedback
hitl_feedback = context.shared_state.get('hitl_feedback', '')

# Injects into agents
if hitl_feedback:
    instructions = f"## Human Feedback from Planning\n{hitl_feedback}"
    cmbagent.inject_to_agents(['engineer'], instructions, mode='append')

# Accumulates step-level feedback
self._accumulated_feedback += new_feedback
```

## Feedback Capture Points

### Checkpoint
- Approval: Provide guidance when approving/rejecting

### Planning
- Each iteration: Provide feedback when requesting revision
- Final approval: Optional notes

### Control
- Before step: Provide guidance before execution
- After step: Provide notes/corrections after completion
- On error: Provide recovery instructions

## Access Feedback

### In Agent Code
Feedback is automatically injected into agent instructions - agents see it as part of their system message.

### In Phase Code
```python
# Read from context
feedback = context.shared_state.get('hitl_feedback', '')
history = context.shared_state.get('planning_feedback_history', [])

# Read from output
step_feedback = result.output_data.get('step_feedback', [])
all_feedback = result.output_data['shared'].get('all_hitl_feedback', '')
```

### In UI/Frontend
Access from phase output:
```python
result = await phase.execute(...)
feedback_data = {
    'combined': result.output_data['shared']['hitl_feedback'],
    'history': result.output_data.get('planning_feedback_history', []),
    'steps': result.output_data.get('step_feedback', []),
}
```

## Common Patterns

### Pattern 1: Checkpoint → Planning → Control
```python
# Full feedback flow through all HITL phases
workflows.FULL_INTERACTIVE_WORKFLOW
```

### Pattern 2: Planning → Checkpoint → Control  
```python
# Autonomous planning, approval gate, then HITL control
workflows.INTERACTIVE_CONTROL_WORKFLOW
```

### Pattern 3: Planning → Control (on_error)
```python
# Autonomous until error, then human intervention
workflows.ERROR_RECOVERY_WORKFLOW
```

## Debugging Feedback

### Check if feedback is captured
```python
result = await phase.execute(...)
print("Feedback:", result.output_data.get('shared', {}).get('hitl_feedback'))
```

### Check if feedback is injected
```python
# Add logging in phase code
print(f"Injecting feedback: {hitl_feedback[:100]}...")
cmbagent.inject_to_agents(['planner'], instructions, mode='append')
```

### Trace complete flow
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check shared_state at each phase
print("Checkpoint output:", checkpoint_result.output_data['shared'])
print("Planning input:", planning_context.shared_state)
print("Planning output:", planning_result.output_data['shared'])
print("Control input:", control_context.shared_state)
print("Control output:", control_result.output_data['shared'])
```

## Key Files

- **Implementation:** `cmbagent/phases/hitl_*.py`
- **Workflows:** `cmbagent/workflows/composer.py`
- **Examples:** `examples/hitl_feedback_flow_example.py`
- **Tests:** `tests/test_hitl_feedback_flow.py`
- **Full Guide:** `docs/HITL_PHASES_GUIDE.md`
- **Implementation Details:** `docs/HITL_FEEDBACK_IMPLEMENTATION.md`

## Common Issues

### Feedback not appearing in next phase
**Problem:** `shared_state` not passed correctly  
**Solution:** 
```python
# Extract from previous result
prev_feedback = prev_result.output_data['shared']['hitl_feedback']

# Pass to next phase
next_context = PhaseContext(
    ...,
    shared_state={'hitl_feedback': prev_feedback}  # ← Don't forget this!
)
```

### Agents not using feedback
**Problem:** Feedback not injected  
**Solution:** Check that feedback exists in shared_state when phase starts. The injection happens automatically in the execute() method.

### Feedback getting lost
**Problem:** Not passing feedback forward in output  
**Solution:** Each HITL phase now automatically includes feedback in `output_data['shared']`. Make sure to use that for the next phase's shared_state.

## Examples

See `examples/hitl_feedback_flow_example.py` for:
- Complete flow demonstration
- Feedback injection mechanism explanation
- Practical research workflow example

Run with:
```bash
python examples/hitl_feedback_flow_example.py
```

## Tests

Run test suite:
```bash
pytest tests/test_hitl_feedback_flow.py -v
```

Covers:
- Checkpoint capture ✓
- Planning reception ✓
- Planning accumulation ✓
- Control reception ✓
- Control accumulation ✓
- Complete chain ✓

---

**Need help?** Check `docs/HITL_PHASES_GUIDE.md` for detailed documentation.
