# Copilot Tool-Based Architecture - Fluent Autonomous Operation

## Problem with Current Design

The current copilot has a rigid flow:
```
User Task → Analyze → Route to ONE mode → Execute → Ask "What next?"
```

**Issues:**
1. **Not fluent** - After each operation, copilot asks "what to do next?"
2. **Can't chain operations** - Each operation is isolated
3. **Not autonomous** - Requires user input between steps
4. **Rigid routing** - Must pick ONE mode upfront
5. **Breaks flow** - After planning, asks for next task instead of executing

**Example of bad UX:**
```
User: "Add authentication to the app"
Copilot: [creates plan]
Copilot: "Plan created. What would you like to do next?"  ← BAD!
User: "... execute the plan you just made?"
```

## New Tool-Based Architecture

Instead of modes being hardcoded routes, **modes become tools** that the agent can call:

```
User Task → Agent with tools → Agent chains tools autonomously → Done
```

**Flow:**
1. User gives task
2. One agent has access to "mode tools"
3. Agent decides which tools to use and when
4. Agent chains operations naturally
5. Only asks user when genuinely stuck

**Example of good UX:**
```
User: "Add authentication to the app"
Copilot: [thinks] This needs planning
Copilot: [calls create_and_execute_plan tool]
Copilot: [plan created and approved]
Copilot: [executes step 1] ← NO ASKING!
Copilot: [executes step 2]
Copilot: [executes step 3]
Copilot: "Done! Added authentication with JWT tokens. Files modified: auth.ts, login.tsx"
```

## Available Tools

The copilot agent has these tools:

### 1. `create_and_execute_plan(task, max_steps=5)`
Creates a detailed plan and executes it step by step.

**When to use:**
- Complex multi-step tasks
- Sequential operations
- Mix of different work types (code + research + testing)

**Example:**
```python
# Agent thinks: "This needs multiple steps"
create_and_execute_plan(
    task="Implement user authentication",
    max_steps=5
)
# → Creates plan, gets approval, executes all steps
```

### 2. `execute_task_directly(task, agent_type='engineer')`
Execute immediately without planning.

**When to use:**
- Simple straightforward tasks
- Quick functions or scripts
- Small code changes

**Example:**
```python
# Agent thinks: "This is simple, just do it"
execute_task_directly(
    task="Write a function to validate email addresses",
    agent_type="engineer"
)
# → Writes function immediately
```

### 3. `research_information(query, depth='quick')`
Research or look up information.

**When to use:**
- Need context before coding
- API documentation lookup
- Understanding requirements

**Example:**
```python
# Agent thinks: "I need to understand this first"
research_information(
    query="React hooks best practices for auth",
    depth="quick"
)
# → Gets info, then continues with coding
```

### 4. `ask_user_for_clarification(questions)`
Ask the user for input.

**When to use:**
- Task is vague or ambiguous
- Multiple valid approaches
- Missing critical info
- Needs confirmation for destructive actions

**Example:**
```python
# Agent thinks: "I'm not sure which approach they want"
ask_user_for_clarification(
    questions=[
        "Should we use JWT or session-based auth?",
        "Where should auth tokens be stored?"
    ]
)
# → Waits for user response, then continues
```

### 5. `report_completion(summary, files_modified, next_steps)`
Mark task as complete.

**When to use:**
- Task is fully done
- Ready to return to user

**Example:**
```python
# Agent thinks: "All done!"
report_completion(
    summary="Added email validation with regex pattern",
    files_modified=["utils/validation.ts"],
    next_steps=["Add tests", "Handle international emails"]
)
# → Task complete, user sees summary
```

### 6. `chain_operations(operations)`
Execute multiple operations in sequence.

**When to use:**
- Task naturally has stages
- Each stage depends on previous
- Want to show progress

**Example:**
```python
# Agent thinks: "This has clear stages"
chain_operations([
    {"type": "research", "query": "React hooks patterns"},
    {"type": "execute", "task": "Create useAuth hook"},
    {"type": "execute", "task": "Add tests for hook"}
])
# → Executes each operation in order
```

## Tool Chaining Examples

### Example 1: Research → Code → Complete

```
User: "Implement a caching layer for API calls"

Agent: [analyzes task]
Agent: [calls research_information("API caching patterns", "quick")]
Agent: [gets research results]
Agent: [calls execute_task_directly("Implement LRU cache with TTL")]
Agent: [code executed successfully]
Agent: [calls report_completion(summary="Added caching with LRU + TTL", files=["cache.ts"])]

Done! No interruptions.
```

### Example 2: Clarify → Plan → Execute

```
User: "Add search functionality"

Agent: [analyzes - task is vague]
Agent: [calls ask_user_for_clarification([
    "What should be searchable?",
    "Full-text or exact match?",
    "Should results be paginated?"
])]
User: [provides answers]
Agent: [calls create_and_execute_plan("Add search with pagination")]
Agent: [plan created, approved, all steps executed]
Agent: [calls report_completion(...)]

Done! Only asked when needed clarification.
```

### Example 3: Simple Direct Execution

```
User: "Fix the typo in README.md"

Agent: [analyzes - simple task]
Agent: [calls execute_task_directly("Fix typo in README", "engineer")]
Agent: [fixed]
Agent: [calls report_completion(summary="Fixed typo", files=["README.md"])]

Done! Fast and direct.
```

## Implementation

### Phase 1: Register Tools ✅

**File:** `cmbagent/functions/copilot_tools.py`

Created tool functions with proper annotations and docstrings.

### Phase 2: Setup Function ✅

**File:** `cmbagent/functions/copilot.py`

Added `setup_copilot_tools_mode()` to register tools with the agent.

### Phase 3: Enable in CopilotPhase (TODO)

**File:** `cmbagent/phases/copilot_phase.py`

Need to add a mode flag and handle tool calls:

```python
class CopilotPhaseConfig(PhaseConfig):
    # ... existing config ...

    # New flag
    use_tool_mode: bool = True  # Use autonomous tool-based operation
```

### Phase 4: Tool Call Handler (TODO)

Need to interpret tool calls and execute the corresponding actions:

```python
async def _handle_tool_calls(self, tool_calls, context):
    """Process tool calls from the agent."""
    for tool_call in tool_calls:
        action = json.loads(tool_call.result)

        if action["action"] == "create_and_execute_plan":
            result = await self._execute_with_planning(...)

        elif action["action"] == "execute_directly":
            result = await self._execute_one_shot(...)

        elif action["action"] == "research":
            result = await self._do_research(...)

        elif action["action"] == "ask_clarification":
            result = await self._request_clarification(...)

        elif action["action"] == "complete":
            return action  # Task complete!
```

## How to Enable

### For Users

Add to copilot config:
```python
config = CopilotPhaseConfig(
    use_tool_mode=True,  # ← Enable autonomous tool mode
    available_agents=["engineer", "researcher"],
    # ... other config ...
)

copilot = CopilotPhase(config)
```

### For Developers

The tool mode is registered automatically if `use_tool_mode=True`:

```python
# In _get_or_create_cmbagent_session
if self.config.use_tool_mode:
    from cmbagent.functions.copilot import setup_copilot_tools_mode
    setup_copilot_tools_mode(self._cmbagent_instance, self.config.available_agents)
```

## Benefits

### 1. **Fluent Operation**
- No "what to do next?" after every operation
- Natural chaining of related tasks
- Feels like talking to a smart assistant

### 2. **Truly Autonomous**
- Agent decides what tools to use
- Chains operations without asking
- Only interrupts when genuinely needs input

### 3. **Flexible**
- Not locked into one mode
- Can mix and match (research then code, plan then execute)
- Adapts to task complexity dynamically

### 4. **Better UX**
- Faster (no unnecessary prompts)
- More natural conversation flow
- Matches user expectations (like Claude, GPT)

### 5. **Easier to Extend**
- Add new tools easily
- Tools are composable
- Agent learns to use new tools

## Comparison

### Old Architecture
```
Task → Route Decision (pick ONE) → Execute ONE mode → Stop → Ask user

Pros:
- Simple to understand
- Predictable

Cons:
- Rigid
- Not fluent
- Requires user input between operations
- Can't chain operations
```

### New Tool-Based Architecture
```
Task → Agent with tools → Chain tools autonomously → Complete

Pros:
- Fluent operation
- Can chain multiple operations
- Truly autonomous
- Better UX
- Extensible

Cons:
- More complex internally
- Agent needs good prompting
- Need to handle tool failures gracefully
```

## Migration Path

### Phase 1: Add Tools (✅ Done)
- Created tool functions
- Added setup function

### Phase 2: Enable in Copilot (TODO)
- Add `use_tool_mode` config flag
- Register tools in session setup
- Keep old routing mode as fallback

### Phase 3: Tool Call Handling (TODO)
- Parse tool call results
- Execute corresponding actions
- Chain operations
- Handle completion

### Phase 4: Testing (TODO)
- Test simple direct execution
- Test clarification flow
- Test plan creation and execution
- Test tool chaining
- Test error handling

### Phase 5: Default Enable (TODO)
- Set `use_tool_mode=True` by default
- Deprecate old routing mode
- Update documentation

## Open Questions

### 1. How to handle tool failures?
**Option A:** Agent sees error, can retry with different approach
**Option B:** Escalate to user for guidance
**Decision:** Combination - let agent retry once, then escalate

### 2. Tool execution context?
**Question:** Should tools see full conversation history?
**Answer:** Yes - tools need context to make good decisions

### 3. Maximum tool chain length?
**Question:** How many tools can be chained?
**Answer:** Set limit (e.g., 10) to prevent infinite loops

### 4. Can tools call other tools?
**Question:** Can `execute_task_directly` internally call `research_information`?
**Answer:** No - keep tools simple, let agent orchestrate

### 5. Backward compatibility?
**Question:** Support old routing mode?
**Answer:** Yes - use `use_tool_mode` flag, default to new mode

## Next Steps

1. ✅ Create tool functions
2. ✅ Add setup function
3. ⬜ Add `use_tool_mode` config
4. ⬜ Implement tool call handler
5. ⬜ Test tool chaining
6. ⬜ Update documentation
7. ⬜ Make default mode

## Example Session

```
User: "I need to add authentication to my React app"

Copilot [thinking]: Complex task, needs planning
Copilot [calls]: create_and_execute_plan("Add authentication to React app", 5)
Copilot: "Creating plan..."
Copilot: "Plan ready - 4 steps:
  1. Research best practices
  2. Create auth context and hooks
  3. Add login/logout components
  4. Protect routes with auth check
  Approve?"

User: "Yes"

Copilot [executing step 1]: research_information("React auth patterns")
Copilot: "✓ Step 1: Research complete"

Copilot [executing step 2]: execute_task_directly("Create auth context")
Copilot: "✓ Step 2: Auth context created"

Copilot [executing step 3]: execute_task_directly("Create login form")
Copilot: "✓ Step 3: Login components added"

Copilot [executing step 4]: execute_task_directly("Add route protection")
Copilot: "✓ Step 4: Routes protected"

Copilot [calls]: report_completion(
    summary="Added complete authentication system with JWT",
    files_modified=["contexts/AuthContext.tsx", "components/Login.tsx", "App.tsx"],
    next_steps=["Add password reset", "Add remember me option"]
)

Copilot: "Done! Added authentication. Files modified: AuthContext.tsx, Login.tsx, App.tsx.
          Next you might want to: Add password reset, Add remember me option"

User: "Great! Now add the password reset"

Copilot [calls]: execute_task_directly("Add password reset flow")
Copilot: "✓ Password reset added"
Copilot [calls]: report_completion(...)

User: "Perfect, thanks!"
```

**Notice:** No "what to do next?" interruptions! The agent chains operations fluently.

## Summary

**Old Way:**
- Task → Route → Execute → Ask → ...repeat
- Rigid, not fluent

**New Way:**
- Task → Agent orchestrates tools → Complete
- Autonomous, fluent, natural

**Impact:**
- 🎯 More natural UX
- ⚡ Faster (fewer interruptions)
- 🔗 Can chain operations
- 🤖 Truly autonomous
- 🎨 More flexible

**Status:**
- ✅ Tools created
- ✅ Setup function added
- ⬜ Integration with CopilotPhase needed
- ⬜ Testing needed
