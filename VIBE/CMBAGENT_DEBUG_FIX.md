# CMBAgent Debug Parameter Fix

## Problem

After upgrading from the custom `cmbagent_autogen` fork to official AG2 (Stage 1), there was a compatibility issue where the `cmbagent_debug` parameter was being passed to AG2's `ConversableAgent` and `GPTAssistantAgent` classes, which don't accept this parameter.

### Error Message
```
ConversableAgent.__init__() got an unexpected keyword argument 'cmbagent_debug'
```

### Why Unit Tests Passed But Python API Failed
- Unit tests mocked/simulated the internals and didn't actually create real agents
- Python API (`one_shot`) creates real agents, which triggered the error
- The `cmbagent_debug` parameter was a custom addition in the old fork that doesn't exist in official AG2

## Solution

Removed the `cmbagent_debug` parameter from all agent instantiations in `cmbagent/base_agent.py`:

### Changes Made

1. **GPTAssistantAgent** (line 144-152)
   - Removed `cmbagent_debug=cmbagent_debug` from initialization
   - The variable is still used for conditional logging via `if cmbagent_debug:` statements

2. **CmbAgentSwarmAgent in set_assistant_agent** (line 209-216)
   - Removed `cmbagent_debug=cmbagent_debug` from initialization
   - The variable is still used for conditional logging

3. **CmbAgentSwarmAgent in set_code_agent** (line 261-276)
   - Removed `cmbagent_debug=cmbagent_debug` from initialization
   - The variable is still used for conditional logging

### What Was Preserved

The `cmbagent_debug` variable is still:
- Imported from `cmbagent.cmbagent_utils`
- Used throughout the codebase for conditional debug printing with `if cmbagent_debug:`
- Properly scoped as a module-level variable

### What Changed

The parameter is no longer:
- Passed to AG2 agent constructors (GPTAssistantAgent, ConversableAgent)
- This prevents the "unexpected keyword argument" error

## Testing

Created test scripts to verify the fix:

1. `test_agent_init.py` - Verifies agents can be initialized without errors
2. `test_cmbagent_debug_fix.py` - Tests the `one_shot` API

Both tests confirm that:
- Agents initialize successfully without the `cmbagent_debug` parameter error
- The API no longer raises TypeError for unexpected keyword argument
- Debug logging still works via the `if cmbagent_debug:` conditional statements

## Files Modified

- `cmbagent/base_agent.py` - Removed 3 instances of `cmbagent_debug` parameter passing

## Verification

Run the test to verify:
```bash
python test_agent_init.py
```

Expected output:
```
✓ Successfully imported agent classes
✓ CmbAgentSwarmAgent initialized successfully without cmbagent_debug
SUCCESS! All tests passed.
```

## Impact on All Modes

This fix ensures compatibility with official AG2 **across all CMBAgent modes**:

### ✓ Planning Mode
- **Planner agent** - Uses `set_assistant_agent()` (fixed)
- **Plan reviewer agent** - Uses `set_assistant_agent()` (fixed)
- **Plan recorder** - Uses `set_assistant_agent()` (fixed)

### ✓ Control Mode
- **Engineer agent** - Uses `set_assistant_agent()` (fixed)
- **Researcher agent** - Uses `set_assistant_agent()` (fixed)
- **Task improver** - Uses `set_assistant_agent()` (fixed)

### ✓ RAG Agents (All Scientific Tools)
- **CAMB, CLASS, Cobaya, Planck, ACT, GetDist, CAMELS, etc.** - All use `set_gpt_assistant_agent()` (fixed)
- These agents use OpenAI's file search with vector stores

### ✓ Code Execution Agents
- **Engineer executor** - Uses `set_code_agent()` (fixed)
- **Researcher executor** - Uses `set_code_agent()` (fixed)
- **Bash executor** - Uses `set_code_agent()` (fixed)

### ✓ Response Formatters
- **All formatter agents** (planner, reviewer, idea_maker, etc.) - Use `set_assistant_agent()` (fixed)

### ✓ All Operational Modes
1. **one_shot mode** - Single task execution
2. **chat mode** - Interactive conversation
3. **planning_and_control mode** - Multi-phase execution
4. **planning_and_control_context_carryover mode** - With context preservation

## Architecture Insight

All agent types in CMBAgent inherit from `BaseAgent` and call one of three methods:
- `set_assistant_agent()` - For regular conversational agents
- `set_gpt_assistant_agent()` - For RAG agents with OpenAI Assistants API
- `set_code_agent()` - For code execution agents

**Our fix in `base_agent.py` covers ALL agents** because every agent in the system inherits from `BaseAgent` and uses one of these three methods. No agent directly instantiates AG2 classes.

## Verification

The fix preserves all debug logging functionality through the existing `if cmbagent_debug:` conditional statements throughout the codebase while ensuring compatibility with official AG2.
