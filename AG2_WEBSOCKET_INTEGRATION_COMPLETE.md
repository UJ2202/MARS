# AG2 Handoffs WebSocket Integration - Complete Implementation

## Overview

This document describes the complete implementation of WebSocket integration for AG2 (AutoGen) handoffs in HITL workflows. This allows dynamic approval requests from AG2 agents (like engineer, control, etc.) to appear in the UI instead of blocking on console `input()`.

## Problem Statement

AG2 handoffs use the "admin" agent (a human proxy) to request human input. By default, the admin agent calls `input()` which:
- Blocks on console stdin
- Has no connection to the WebSocket UI
- Prevents users from responding through the web interface

## Solution Architecture

### 1. WebSocket Input Handler (`cmbagent/handoffs/hitl.py`)

Created two functions to override the admin agent's input method:

#### `configure_admin_for_websocket(admin_agent, approval_manager, run_id)`

Configures a single admin agent to use WebSocket instead of console input.

**How it works:**
1. Overrides `admin_agent.get_human_input()` with a custom function
2. When AG2 agents hand off to admin, the custom function:
   - Creates an approval request via `WebSocketApprovalManager`
   - Sends it to the UI via WebSocket event
   - Waits for user response (blocking but async-compatible)
   - Returns user's response to AG2 agent
3. Handles different user responses:
   - "continue"/"approve" → returns empty string (proceed)
   - "provide_instructions" → returns user's feedback text
   - "abort"/"reject" → returns "TERMINATE" (stop workflow)

**Key implementation details:**
```python
def websocket_human_input_sync(prompt: str) -> str:
    # Create approval request
    approval_request = approval_manager.create_approval_request(
        run_id=run_id,
        step_id=f"ag2_handoff_{agent_name}",
        checkpoint_type="ag2_dynamic",  # Special type for AG2 approvals
        message=f"**Agent Handoff: {agent_name}**\n\n{prompt}",
        options=["continue", "provide_instructions", "abort"],
    )

    # Wait for WebSocket approval (blocks until UI response)
    resolved = loop.run_until_complete(
        approval_manager.wait_for_approval_async(...)
    )

    # Return appropriate response to AG2
    if resolved.resolution == "continue":
        return ""  # Empty = proceed
    elif resolved.resolution == "provide_instructions":
        return resolved.user_feedback  # User's instructions
    else:
        return "TERMINATE"  # Stop workflow
```

#### `enable_websocket_for_hitl(cmbagent_instance, approval_manager, run_id)`

Convenience function that:
1. Gets all agents from the CMBAgent instance
2. Finds the admin agent
3. Calls `configure_admin_for_websocket()` on it

### 2. Integration Point (`cmbagent/phases/hitl_control.py`)

Integrated WebSocket enablement into the HITL control phase execution:

**Location:** Lines 308-332, right after AG2 handoffs are registered

```python
# Configure AG2 HITL handoffs (if enabled)
if self.config.use_ag2_handoffs:
    from cmbagent.handoffs import register_all_hand_offs, enable_websocket_for_hitl

    # Register handoffs (sets up which agents hand off to admin)
    register_all_hand_offs(cmbagent, hitl_config=hitl_config)

    # Enable WebSocket for admin agent (if approval_manager exists)
    if approval_manager:
        enable_websocket_for_hitl(cmbagent, approval_manager, context.run_id)
        print(f"→ AG2 WebSocket integration enabled ✓")
    else:
        print(f"⚠ Warning: No approval_manager - AG2 handoffs will use console input")
```

**Why this location?**
- We just created the CMBAgent instance (line 292)
- We just registered AG2 handoffs (line 319)
- We have both `cmbagent` and `approval_manager` available
- We're about to execute the step, so admin agent needs to be ready

### 3. UI Support (`cmbagent-ui/components/ApprovalChatPanel.tsx`)

Added display support for AG2 dynamic approvals:

```typescript
const getCheckpointTitle = (type?: string) => {
  switch (type) {
    case 'ag2_dynamic':
      return '🤖 Agent Requesting Input'
    // ... other cases
  }
}
```

The ApprovalChatPanel already supports:
- Displaying custom messages ✓
- Showing approval options ✓
- Collecting user feedback ✓
- Sending responses back ✓

So minimal changes needed - just the title customization.

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ HITL Workflow Execution                                         │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ HITLControlPhase.execute()                                      │
│  - Creates CMBAgent instance                                    │
│  - Registers AG2 handoffs                                       │
│  - Enables WebSocket for admin agent  ← NEW                    │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step Execution                                                  │
│  - Engineer agent processes task                                │
│  - Detects risky operation (e.g., "delete file")                │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ AG2 Handoff Triggered                                           │
│  - Handoff condition matches (smart approval)                   │
│  - Engineer hands off to Admin agent                            │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ Admin Agent Called                                              │
│  - AG2 calls: admin.get_human_input(prompt)                     │
│  - Our override intercepts this  ← NEW                          │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ WebSocket Approval Request Created                              │
│  - approval_manager.create_approval_request()                   │
│  - checkpoint_type = "ag2_dynamic"                              │
│  - options = ["continue", "provide_instructions", "abort"]      │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ WebSocket Event Sent to UI                                      │
│  - Event type: "approval_requested"                             │
│  - Data includes agent name, prompt, options                    │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ UI Displays Approval Panel                                      │
│  - ApprovalChatPanel renders                                    │
│  - Shows: "🤖 Agent Requesting Input"                           │
│  - Displays agent's message/prompt                              │
│  - Shows buttons: Continue / Provide Instructions / Abort       │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ User Responds in UI                                             │
│  - Selects option                                               │
│  - Optionally provides feedback text                            │
│  - Clicks Submit                                                │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ WebSocket Response Sent                                         │
│  - Message type: "resolve_approval"                             │
│  - Contains: resolution, feedback                               │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ Backend Receives Response                                       │
│  - approval_manager.resolve(approval_id, resolution, feedback)  │
│  - Unblocks wait_for_approval_async()                           │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ Response Returned to AG2                                        │
│  - admin.get_human_input() returns:                             │
│    - "" if continue                                             │
│    - feedback text if provide_instructions                      │
│    - "TERMINATE" if abort                                       │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ AG2 Workflow Continues                                          │
│  - Admin hands back to Engineer (if approved)                   │
│  - Engineer continues with user's instructions                  │
│  - Or workflow terminates (if aborted)                          │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration

### Enable AG2 Handoffs in HITL Config

```python
config = HITLControlPhaseConfig(
    use_ag2_handoffs=True,  # Enable AG2 handoffs
    ag2_mandatory_checkpoints=['before_file_edit'],  # Always ask before file edits
    ag2_smart_approval=True,  # Let LLM decide when to escalate
    ag2_smart_criteria={
        'escalate_keywords': ['delete', 'production', 'deploy']
    }
)
```

### Workflow Setup

The integration happens automatically when:
1. `use_ag2_handoffs=True` in config
2. `approval_manager` exists (WebSocketApprovalManager instance)
3. HITLControlPhase executes

No additional code needed - it's integrated into the phase execution!

## Types of AG2 Approvals

### 1. Mandatory Checkpoints

Always require approval at specific points:

- **after_planning**: After planner completes, before execution starts
- **before_file_edit**: Before any file modification
- **before_execution**: Before running code
- **before_deploy**: Before deployment operations

### 2. Smart Approval (Dynamic)

LLM decides when to escalate based on:
- **Risk keywords**: delete, production, deploy, critical, irreversible
- **Uncertainty**: Ambiguous requirements, multiple valid solutions
- **Complexity**: Architectural decisions, cost/benefit trade-offs
- **Error recovery**: Repeated failures, unclear how to proceed

## User Experience

### AG2 Dynamic Approval in UI

When an AG2 handoff occurs:

1. **Approval panel appears** at bottom of console tab
2. **Title**: "🤖 Agent Requesting Input"
3. **Message**: Shows the agent's request/context
4. **Options**:
   - **Continue**: Approve and proceed (no instructions)
   - **Provide Instructions**: Give specific guidance to the agent
   - **Abort**: Stop the workflow

5. **Feedback box**: Optional text input for instructions
6. **Context toggle**: View additional details if available

### Example AG2 Approval Message

```
🤖 Agent Requesting Input

Agent Handoff: engineer

From: engineer

I'm about to delete the file "production_config.yaml".
This operation is irreversible. Should I proceed?

[Continue] [Provide Instructions] [Abort]

Optional feedback:
┌────────────────────────────────────┐
│ Actually, just comment it out      │
│ instead of deleting it             │
└────────────────────────────────────┘
```

## Fallback Behavior

If WebSocket integration fails, the system gracefully falls back:

1. **Try WebSocket first** (primary path)
2. **If WebSocket fails**, try original `get_human_input()` if available
3. **If no fallback**, return "TERMINATE" to stop safely

This ensures the workflow never hangs indefinitely.

## Testing

### Test AG2 Handoffs

1. **Enable AG2 handoffs** in HITL config:
```python
use_ag2_handoffs=True
ag2_mandatory_checkpoints=['before_file_edit']
```

2. **Run HITL workflow** with a task that triggers handoffs:
```
"Delete the old database migration files"
```

3. **Verify in UI**:
   - Approval panel appears with "🤖 Agent Requesting Input"
   - Shows agent's message about file deletion
   - User can respond with Continue/Instructions/Abort

4. **Check logs** for:
```
[AG2 Admin] Human input requested via WebSocket
[AG2 Admin] Approval request created: <uuid>
[WebSocketApprovalManager] Sending approval_requested event:
  - checkpoint_type: ag2_dynamic
[AG2 Admin] Approval resolved: continue
```

### Test Scenarios

✅ **Mandatory checkpoint (before_file_edit)**
- Engineer tries to edit a file
- Hands off to admin
- UI shows approval request
- User approves
- Engineer continues

✅ **Smart approval (risky keyword detected)**
- Engineer says "I'll delete the production database"
- LLM detects "delete" + "production"
- Escalates to admin
- UI shows approval request
- User provides safer instructions

✅ **User provides instructions**
- Admin receives prompt
- User selects "Provide Instructions"
- Types feedback: "Use a backup first"
- Engineer receives feedback and adjusts approach

✅ **User aborts**
- Admin receives prompt
- User selects "Abort"
- Workflow terminates gracefully

## Summary of Changes

### Files Modified

1. **`cmbagent/handoffs/hitl.py`**
   - Added `configure_admin_for_websocket()` function
   - Added `enable_websocket_for_hitl()` function
   - ~130 lines of new code

2. **`cmbagent/handoffs/__init__.py`**
   - Exported new functions

3. **`cmbagent/phases/hitl_control.py`**
   - Integrated WebSocket enablement after AG2 handoffs registration
   - ~10 lines of integration code

4. **`cmbagent-ui/components/ApprovalChatPanel.tsx`**
   - Added "ag2_dynamic" case to checkpoint title function
   - 2 lines of UI code

### Total Changes
- **Backend**: ~140 lines
- **Frontend**: ~2 lines
- **Files**: 4

## Future Enhancements

1. **Agent-specific handling**: Different UI for different agent types (engineer vs. planner)
2. **Rich context**: Show agent conversation history in approval panel
3. **Suggested responses**: LLM-generated response suggestions for the user
4. **Approval templates**: Pre-defined responses for common scenarios
5. **Approval history**: Track all AG2 approvals in the session

## Troubleshooting

### AG2 Approvals Not Appearing in UI

**Check:**
1. Is `use_ag2_handoffs=True` in config?
2. Does `approval_manager` exist? (Check logs for "No approval_manager" warning)
3. Is WebSocket connected? (Check browser console)
4. Are handoffs registered? (Check logs for "AG2 HITL handoffs enabled")
5. Is WebSocket enabled? (Check logs for "AG2 WebSocket integration enabled ✓")

### AG2 Approvals Still Using Console Input

**Possible causes:**
1. `approval_manager` is None - check shared_state has `_approval_manager`
2. Admin agent not found - check CMBAgent has admin agent registered
3. WebSocket enablement failed - check exception logs
4. Override didn't apply - check `admin_agent.agent.get_human_input` is our function

### Approval Hangs Forever

**Check:**
1. WebSocket connection active?
2. UI receiving "approval_requested" event? (Browser console)
3. Backend waiting on correct approval_id?
4. Timeout not too short? (Default: 30 minutes)

## Conclusion

This implementation successfully bridges AG2's handoff system with the WebSocket UI, providing:

- ✅ Seamless integration with existing HITL workflow
- ✅ No changes to AG2 handoff configuration
- ✅ Graceful fallback on errors
- ✅ Flexible approval options for users
- ✅ Minimal code changes (~140 lines backend, 2 lines frontend)
- ✅ Comprehensive error handling and logging

Users can now interact with AG2 agents through the web UI instead of being limited to console input!
