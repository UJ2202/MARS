# HITL Approval Issues - Complete Analysis

## Issue 1: Step Approval Not Working (Planning Works, Control Doesn't)

### Problem
- **Planning approval works fine** ✅ - User can see and respond to approval requests during planning
- **Step approval doesn't work** ❌ - During control phase, approval requests show in logs but not in UI

### Root Cause
The `approval_manager` is **None** when `_request_step_review()` is called in the HITLControlPhase.

Looking at the code:
```python
# hitl_control.py line 625-632
if not approval_manager:
    # Falls back to console input() - this is what's happening!
    print(f"\n{'='*60}")
    print(f"STEP {step_num} REVIEW")
    print(f"{'='*60}")
    response = input("\nContinue? (y/n): ").strip().lower()
    return response == 'y' or response == 'yes'
```

When `approval_manager` is None, it falls back to `input()` which:
- Prints the approval message to console logs (what you see)
- Waits for stdin input (why it's stuck)
- Has no way to receive UI input

### Why is approval_manager None?

The approval_manager should be:
1. **Passed to WorkflowExecutor** (`hitl_workflow.py` line 142): ✅ This happens correctly
2. **Injected into phase context** (`composer.py` line 169): ✅ This should happen
3. **Retrieved in HITLControlPhase** (`hitl_control.py` line 156): ❓ This is where it's failing

### Debug Changes Made

Added logging to see what's happening:

**In `hitl_control.py` lines 157-163:**
```python
approval_manager = context.shared_state.get('_approval_manager')
print(f"[HITLControlPhase] Approval manager type: {type(approval_manager)}")
print(f"[HITLControlPhase] Approval manager: {approval_manager}")
if approval_manager:
    print(f"[HITLControlPhase] Approval manager has ws_send_event: {hasattr(approval_manager, 'ws_send_event')}")
else:
    print(f"[HITLControlPhase] WARNING: No approval manager found in shared_state!")
    print(f"[HITLControlPhase] Shared state keys: {list(context.shared_state.keys())}")
```

**In `hitl_control.py` lines 632-648:**
```python
print(f"[_request_step_review] Called with approval_manager: {approval_manager}")
print(f"[_request_step_review] approval_manager type: {type(approval_manager)}")

if not approval_manager:
    print(f"[_request_step_review] No approval_manager - falling back to console input")
    # ... console fallback ...

print(f"[_request_step_review] Using WebSocket approval manager")
print(f"[_request_step_review] Creating approval request...")
# ... create approval request ...
```

### Next Steps to Diagnose

Run the HITL workflow again and check logs for:

1. **At HITLControlPhase initialization:**
   ```
   [HITLControlPhase] Approval manager type: <class '...WebSocketApprovalManager'>
   [HITLControlPhase] Approval manager has ws_send_event: True
   ```

   OR

   ```
   [HITLControlPhase] WARNING: No approval manager found in shared_state!
   [HITLControlPhase] Shared state keys: [...]
   ```

2. **At step review call:**
   ```
   [_request_step_review] Called with approval_manager: <WebSocketApprovalManager...>
   [_request_step_review] Using WebSocket approval manager
   [WebSocketApprovalManager] Sending approval_requested event:
   ```

   OR

   ```
   [_request_step_review] No approval_manager - falling back to console input
   ```

This will tell us exactly where the approval_manager is getting lost.

### Possible Causes

1. **Context not passed correctly between phases**
   - Planning phase creates new context
   - Control phase doesn't inherit shared_state

2. **Approval manager cleared after planning**
   - Something is resetting shared_state after planning completes

3. **Different context instances**
   - Planning phase uses one context
   - Control phase creates a new context without copying shared_state

---

## Issue 2: AG2 Handoffs Dynamic Approval Messages

### Question
> "Dynamic approval message will also come from AG2 agents as we added handoffs. How will UI handle that?"

### Current State: NOT SUPPORTED ❌

The AG2 handoffs (configured in `cmbagent/handoffs/`) use AG2's built-in HITL system, which:
- Uses the **"admin" agent** (a UserProxyAgent or ConversableAgent with `human_input_mode`)
- When agents hand off to admin, it calls `input()` to get human feedback
- This blocks on console input - **the UI won't see these requests**

### Example Flow (Current - Broken for UI)

```
Engineer Agent → (handoff decision) → Admin Agent
                                           ↓
                                    input("What should I do?")
                                           ↓
                                    BLOCKS WAITING FOR CONSOLE INPUT
                                           ↓
                                    UI doesn't know anything happened
```

### How AG2 Handoffs Work

From `cmbagent/handoffs/hitl.py`:

```python
# Mandatory checkpoint: after_planning
agents['plan_reviewer'].agent.handoffs.set_after_work(
    AgentTarget(admin.agent)  # Hands off to admin (human)
)

# Smart checkpoint: before_file_edit
agents['engineer'].agent.handoffs.add_llm_conditions([
    OnCondition(
        target=AgentTarget(admin.agent),  # Escalate to human
        condition=StringLLMCondition(
            prompt="About to edit files. MUST get admin approval first."
        )
    )
])
```

When these conditions trigger:
1. Agent hands off to `admin` agent
2. Admin agent uses its `get_human_input()` method
3. Default `get_human_input()` calls `input()` → console only

###  Solution: Configure Admin Agent to Use WebSocket

To make AG2 handoffs work with the UI, we need to:

#### Option 1: Override admin agent's input function

```python
# In cmbagent initialization or phase setup
def websocket_input_func(prompt: str) -> str:
    """
    Custom input function that uses WebSocketApprovalManager
    instead of console input().
    """
    approval_manager = get_approval_manager_from_context()

    approval_request = approval_manager.create_approval_request(
        run_id=current_run_id,
        step_id="ag2_handoff",
        checkpoint_type="ag2_dynamic",
        context_snapshot={"agent_message": prompt},
        message=prompt,
        options=["approve", "reject", "provide_instructions"],
    )

    resolved = await approval_manager.wait_for_approval_async(
        str(approval_request.id),
        timeout_seconds=1800,
    )

    if resolved.resolution == "approved":
        return ""  # Empty response means "continue"
    elif resolved.resolution == "provide_instructions":
        return resolved.user_feedback  # Return user's instructions
    else:
        return "TERMINATE"  # Stop the workflow

# Configure admin agent
admin_agent.register_reply(
    [autogen.Agent, None],
    reply_func=websocket_input_func,
    config={"callback": None}
)
```

#### Option 2: Wrap admin agent with custom reply handler

```python
class WebSocketHumanProxy:
    """Wrapper for admin agent that routes input through WebSocket"""

    def __init__(self, admin_agent, approval_manager):
        self.admin_agent = admin_agent
        self.approval_manager = approval_manager

    async def get_human_input(self, prompt: str) -> str:
        # Similar to Option 1, but encapsulated in a class
        ...
```

#### Option 3: Disable AG2 handoffs in HITL mode

If we can't easily integrate AG2 handoffs with WebSocket, we can:
- Disable AG2 handoffs when using HITL workflows
- Use only the phase-based approval system (HITLPlanningPhase, HITLControlPhase)
- AG2 handoffs would only work in non-HITL modes

### Implementation Required

To properly support AG2 handoffs in the UI, we need to:

1. **Create a WebSocket input adapter** for the admin agent
2. **Inject approval_manager into CMBAgent instance** so it's accessible during agent execution
3. **Register the custom input handler** when AG2 handoffs are enabled
4. **Update UI to handle "ag2_dynamic" checkpoint types**

### Code Changes Needed

#### 1. In `cmbagent/handoffs/hitl.py`:

```python
def configure_admin_for_websocket(admin_agent, approval_manager, run_id):
    """
    Configure admin agent to use WebSocket instead of console input.
    """
    async def websocket_input(prompt: str) -> str:
        approval_request = approval_manager.create_approval_request(
            run_id=run_id,
            step_id="ag2_handoff",
            checkpoint_type="ag2_dynamic",
            context_snapshot={"prompt": prompt},
            message=prompt,
            options=["continue", "provide_instructions", "abort"],
        )

        resolved = await approval_manager.wait_for_approval_async(
            str(approval_request.id),
            timeout_seconds=1800,
        )

        if resolved.resolution == "continue":
            return ""
        elif resolved.resolution == "provide_instructions":
            return resolved.user_feedback
        else:
            return "TERMINATE"

    # Override admin's get_human_input method
    admin_agent.get_human_input = websocket_input
```

#### 2. In `cmbagent/phases/hitl_control.py`:

```python
# After getting approval_manager
if approval_manager and self.config.use_ag2_handoffs:
    # Configure admin agent for WebSocket
    admin_agent = cmbagent.get_agent_object_from_name('admin')
    from cmbagent.handoffs.hitl import configure_admin_for_websocket
    configure_admin_for_websocket(
        admin_agent,
        approval_manager,
        context.run_id
    )
```

#### 3. UI updates (if needed):

The `ApprovalChatPanel` should already handle "ag2_dynamic" checkpoint types, but we can add specific styling:

```typescript
// In ApprovalChatPanel.tsx
const getCheckpointTitle = (type?: string) => {
  switch (type) {
    case 'ag2_dynamic':
      return '🤖 Agent Requires Input';
    case 'after_planning':
      return '📋 Plan Review Required';
    // ... etc
  }
};
```

### Summary

**AG2 Handoffs Currently:**
- ❌ Use console `input()` for human interaction
- ❌ Don't appear in UI
- ❌ Block workflow execution waiting for console input

**To Make Them Work:**
- Need to override admin agent's input function
- Route approval requests through WebSocketApprovalManager
- UI already supports flexible approval types, so minimal frontend changes needed

**Recommendation:**
Start with **Option 3** (disable AG2 handoffs in HITL mode) for now, then implement proper WebSocket integration as a follow-up task once the step approval issue is fixed.

---

## Testing Plan

1. **Fix Step Approval First**
   - Run workflow with new debug logging
   - Identify where approval_manager is lost
   - Fix the context passing issue
   - Verify step approval works

2. **Then Add AG2 Handoffs Support**
   - Implement websocket input adapter
   - Configure admin agent
   - Test with mandatory checkpoints
   - Test with smart approval

3. **Full Integration Test**
   - Run HITL workflow with AG2 handoffs enabled
   - Verify all approval types appear in UI:
     - Planning approval (after_planning)
     - Step approval (before_step, after_step)
     - Error approval (on_error)
     - AG2 dynamic approval (ag2_dynamic)
   - Verify user can respond to all approval types
   - Verify workflow continues correctly after approval
