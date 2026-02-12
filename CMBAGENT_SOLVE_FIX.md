# CMBAgent.solve() Return Value Fix

## Problem

Copilot ran 5 rounds but produced **no visible output** to the user. The logs showed:
```
Max rounds (5) reached
Session paused
```

But no agent messages, results, or work products were displayed.

## Root Cause

The `CMBAgent.solve()` method **doesn't return anything**:

```python
def solve(self, task, initial_agent, max_rounds=10):
    # ... lots of work ...
    context_variables = ContextVariables(data=this_shared_context)
    chat_result, context_variables, last_agent = initiate_group_chat(...)
    
    self.final_context = copy.deepcopy(context_variables)
    self.last_agent = last_agent
    self.chat_result = chat_result
    
    # ❌ NO RETURN STATEMENT!
```

But the orchestrator was calling it expecting a return value:

```python
# ❌ This returns None!
result = await asyncio.to_thread(
    self._cmbagent.solve,
    task=task_message,
    agent=agent_name,
    max_rounds=5,
)

# ❌ Empty result
return {
    "status": "success",
    "agent": agent_name,
    "result": result,  # None!
}
```

## The Fix

Updated `_execute_with_agent()` and `_get_routing_decision()` to:
1. Call `solve()` without expecting a return value
2. Access CMBAgent's internal state after execution
3. Extract actual results from `chat_result`, `final_context`, and `last_agent`

### Before (Broken)
```python
result = await asyncio.to_thread(
    self._cmbagent.solve,
    task=task_message,
    agent=agent_name,  # ❌ Wrong parameter name
    max_rounds=5,
)

return {
    "status": "success",
    "agent": agent_name,
    "result": result,  # ❌ None
}
```

### After (Fixed)
```python
# Execute solve - note: solve() doesn't return, it sets internal state
await asyncio.to_thread(
    self._cmbagent.solve,
    task=task_message,
    initial_agent=agent_name,  # ✅ Correct parameter
    shared_context=self.state.context._persistent.copy(),  # ✅ Pass context
    max_rounds=self.config.max_rounds - self.state.current_round,
)

# Get results from CMBAgent's internal state
chat_result = getattr(self._cmbagent, 'chat_result', None)
final_context = getattr(self._cmbagent, 'final_context', None)
last_agent = getattr(self._cmbagent, 'last_agent', agent_name)

# Extract the actual output
result_output = None
if chat_result:
    if hasattr(chat_result, 'summary'):
        result_output = chat_result.summary
    elif hasattr(chat_result, 'chat_history') and chat_result.chat_history:
        last_msg = chat_result.chat_history[-1]
        if isinstance(last_msg, dict):
            result_output = last_msg.get('content', str(last_msg))
        else:
            result_output = str(last_msg)
    else:
        result_output = str(chat_result)

if not result_output and final_context:
    if hasattr(final_context, 'data'):
        result_output = final_context.data
    else:
        result_output = str(final_context)

return {
    "status": "success",
    "agent": last_agent if hasattr(last_agent, 'name') else str(last_agent),
    "result": result_output or "Task completed (no output captured)",
    "final_context": final_context.data if hasattr(final_context, 'data') else None,
}
```

## Additional Fixes

### 1. Correct Parameter Name
The `solve()` method parameter is `initial_agent`, not `agent`:
```python
# ❌ Before
self._cmbagent.solve(task=..., agent=agent_name, max_rounds=5)

# ✅ After  
self._cmbagent.solve(task=..., initial_agent=agent_name, max_rounds=5)
```

### 2. Pass Shared Context
The DurableContext data needs to be passed:
```python
# ✅ Pass orchestrator context to agent
shared_context=self.state.context._persistent.copy()
```

### 3. Fix Routing Decision
The `_get_routing_decision()` had the same issue:
```python
# Execute routing
await asyncio.to_thread(
    self._cmbagent.solve,
    task=task_with_mode,
    initial_agent="copilot_control",
    shared_context=self.state.context._persistent.copy(),
    max_rounds=1,
)

# Get result from internal state
final_context = getattr(self._cmbagent, 'final_context', None)
routing_result = None

if final_context:
    if hasattr(final_context, 'data'):
        routing_result = final_context.data
    elif isinstance(final_context, dict):
        routing_result = final_context
```

## Files Modified

1. **swarm_orchestrator.py::_execute_with_agent()**
   - Removed expectation of return value from `solve()`
   - Access internal CMBAgent state after execution
   - Extract result from `chat_result`, `final_context`, `last_agent`
   - Pass correct parameters: `initial_agent`, `shared_context`

2. **swarm_orchestrator.py::_get_routing_decision()**
   - Same fix for routing decision logic
   - Extract routing result from `final_context`
   - Handle missing data gracefully

## Impact

Now when copilot runs:
- ✅ Agents actually execute and produce output
- ✅ Results are captured from CMBAgent internals
- ✅ User sees agent messages and work products
- ✅ Context flows properly between orchestrator and agents
- ✅ Routing decisions work correctly

## Testing

Run copilot with a simple task:
```
User: "Write a Python script to calculate fibonacci"
```

Expected output:
```
Round 1: Agent analyzes task
Round 2: Engineer writes code
Round 3: Response formatted
...
Result: [actual code output visible]
```

Previously: No output, just "max rounds reached"
Now: Full conversation with visible results
