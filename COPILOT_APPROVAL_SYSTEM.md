# Copilot Approval System - Implementation Guide

This document describes the approval and control system for the Copilot phase, including how to enable permissions for code execution, file operations, and stop/continue controls.

## Overview

The copilot system now supports AG2-style approvals for sensitive operations:
- Code execution
- File edits/deletes
- Command execution
- Task clarification
- Stop/Continue/Cancel controls

## What Was Fixed

### 1. Clarification Request UI Issue ✅
**Problem:** When copilot requested clarification, UI showed "provide_info" button but no text input field.

**Solution:** Added `requires_text_input=True` flag to clarification request context:
```python
# copilot_phase.py:489-500
request = approval_manager.create_approval_request(
    ...
    context_snapshot={
        'questions': questions,
        'requires_text_input': True,  # ← NEW: Tells UI to show text input
        'input_placeholder': 'Enter your clarification...',
    },
    options=["submit", "cancel"],  # Changed from "provide_info"
)
```

### 2. Missing Code Execution Agents ✅
**Problem:** Code execution would hang because required agents were missing.

**Solution:** Added all necessary agents for code execution flow:
```python
# copilot_phase.py:136-154
def get_required_agents(self) -> List[str]:
    base_agents = ["admin", "executor", "executor_response_formatter"]

    if "engineer" in self.config.available_agents:
        base_agents.extend(["engineer_nest", "engineer_response_formatter"])
    if "researcher" in self.config.available_agents:
        base_agents.extend(["researcher_response_formatter", "researcher_executor"])
```

### 3. New Checkpoint Types for Copilot Operations ✅
**Added to `database/approval_types.py`:**
```python
class CheckpointType(str, Enum):
    # ... existing ...
    BEFORE_CODE_EXECUTION = "before_code_execution"
    BEFORE_FILE_EDIT = "before_file_edit"
    BEFORE_FILE_DELETE = "before_file_delete"
    BEFORE_COMMAND_EXECUTION = "before_command_execution"
```

### 4. New COPILOT Approval Mode ✅
**Added to `database/approval_types.py`:**
```python
class ApprovalMode(str, Enum):
    # ... existing ...
    COPILOT = "copilot"  # Approval for code/file/command operations
```

**Default copilot configuration:**
```python
DEFAULT_CONFIGS = {
    ...
    "copilot": ApprovalConfig(
        mode=ApprovalMode.COPILOT,
        auto_approve_patterns=["read_file", "search", "list_files"]
    ),
}
```

### 5. Graceful Agent Missing Handling ✅
**Added to `handoffs/nested_chats.py`:**
- Checks if all required agents exist before setting up nested chats
- Skips setup with debug message if agents are missing
- Try-except wrapper for error handling

## How Stop/Continue/Cancel Works

The copilot system already has built-in cancellation support:

### Current Implementation

1. **Cancellation Check Points:**
   ```python
   # copilot_phase.py - checks happen at multiple points:
   manager.raise_if_cancelled()  # Raises exception if workflow cancelled
   ```

2. **How User Can Cancel:**
   - Any approval request with "reject" or "cancel" option
   - Approval manager transitions workflow to "cancelled" state
   - `raise_if_cancelled()` throws `WorkflowCancelledException`

3. **UI Integration:**
   - UI should provide Cancel/Stop button that calls approval rejection
   - WebSocket events notify UI of cancellation status
   - Approval requests pause execution until resolved

### Example Flow

```
User starts copilot task
  ↓
Copilot requests approval (e.g., "Execute this code?")
  ↓
UI shows approval dialog with options: [Approve, Reject, Cancel]
  ↓
User clicks "Cancel"
  ↓
Approval manager transitions workflow to "cancelled"
  ↓
Next `raise_if_cancelled()` throws exception
  ↓
Execution stops, cleanup happens
```

## How to Use AG2-Style Permissions

### Option 1: Enable Copilot Approval Mode (Recommended)

When creating a copilot workflow via API/UI, pass approval config:

```python
from cmbagent.database.approval_types import get_approval_config

# Use predefined copilot config
approval_config = get_approval_config("copilot")

# Or custom config
from cmbagent.database.approval_types import ApprovalConfig, ApprovalMode

approval_config = ApprovalConfig(
    mode=ApprovalMode.COPILOT,
    auto_approve_patterns=["read_file", "search"],  # Auto-approve safe ops
    timeout_seconds=300,  # 5 min timeout
    default_on_timeout="reject",  # Reject if no response
)
```

### Option 2: Custom Checkpoints

For fine-grained control, add custom checkpoints:

```python
from cmbagent.database.approval_types import (
    ApprovalConfig,
    ApprovalCheckpoint,
    CheckpointType
)

approval_config = ApprovalConfig(
    mode=ApprovalMode.CUSTOM,
    custom_checkpoints=[
        ApprovalCheckpoint(
            checkpoint_type=CheckpointType.BEFORE_CODE_EXECUTION,
            message="About to execute code. Approve?",
            options=["approve", "reject", "modify"],
            allow_feedback=True,
            # Optional: conditional trigger
            condition=lambda ctx: "dangerous_operation" in ctx.get("code", "")
        ),
        ApprovalCheckpoint(
            checkpoint_type=CheckpointType.BEFORE_FILE_EDIT,
            message="About to edit file. Approve?",
            options=["approve", "skip"],
        ),
    ]
)
```

## UI Requirements

To fully support the copilot approval system, the UI needs:

### 1. Text Input for Clarification/Chat
When approval request has `context_snapshot.requires_text_input=True`:
```tsx
// ApprovalChatPanel.tsx
if (approval.context_snapshot?.requires_text_input) {
  return (
    <div>
      <input
        type="text"
        placeholder={approval.context_snapshot.input_placeholder}
        value={userInput}
        onChange={(e) => setUserInput(e.target.value)}
      />
      <button onClick={() => resolveWithText(userInput)}>Submit</button>
      <button onClick={() => resolve("cancel")}>Cancel</button>
    </div>
  );
}
```

### 2. Cancel/Stop Button During Execution
Always show a cancel button when workflow is running:
```tsx
{workflowStatus === "running" && (
  <button onClick={() => cancelWorkflow()}>Stop Execution</button>
)}
```

### 3. Permission Approval Dialogs
For copilot checkpoints, show appropriate UI:
```tsx
switch (approval.checkpoint_type) {
  case "before_code_execution":
    return <CodeExecutionApproval approval={approval} />;
  case "before_file_edit":
    return <FileEditApproval approval={approval} />;
  case "clarification":
    return <ClarificationInput approval={approval} />;
  // ...
}
```

## Backend API Integration

### Creating Copilot Run with Approvals

```python
# backend/routers/copilot.py
from cmbagent.database.approval_types import get_approval_config

@router.post("/copilot/run")
async def create_copilot_run(request: CopilotRequest):
    # Get approval config based on user preference
    approval_mode = request.approval_mode or "copilot"
    approval_config = get_approval_config(approval_mode)

    # Create copilot phase context
    context = PhaseContext(
        task=request.task,
        work_dir=work_dir,
        api_keys=api_keys,
        run_id=run_id,
        shared_state={
            '_approval_manager': approval_manager,
            # ... other state ...
        }
    )

    # Execute with approval config
    result = await copilot_phase.execute(context)
```

### Cancelling Execution

```python
# backend/routers/copilot.py
@router.post("/copilot/cancel/{run_id}")
async def cancel_copilot_run(run_id: str):
    # Cancel all pending approvals
    approval_manager.cancel_pending_approvals(
        run_id,
        reason="User cancelled execution"
    )

    # Transition workflow to cancelled
    workflow_sm.transition_to(
        run_id,
        "cancelled",
        reason="User requested cancellation",
        transitioned_by="user"
    )
```

## Testing the System

### Test Clarification Input
```python
# Should show text input in UI
routing_decision = {'route_type': 'clarify', 'clarifying_questions': ['What do you want?']}
```

### Test Code Execution Approval
```python
# With COPILOT mode, should request approval before executing
approval_config = get_approval_config("copilot")
# ... run copilot with this config ...
# When engineer generates code, approval request should appear
```

### Test Cancellation
```python
# During execution, reject any approval
# Should cancel entire workflow and clean up
```

## Migration Notes

### For Existing Copilot Users

The system is **backward compatible**. Existing code works without changes:
- Default approval_mode is "none" (no approvals)
- Clarification now works properly with text input
- Code execution no longer hangs

To enable new approval features, update your copilot creation:
```python
# Before (still works)
copilot_phase = CopilotPhase()

# After (with approvals)
copilot_phase = CopilotPhase()
# Pass approval_manager in context with copilot config
```

## Troubleshooting

### Clarification doesn't show text input
- Check `context_snapshot.requires_text_input` is True
- Check UI is handling this flag correctly
- Options should be `["submit", "cancel"]` not `["provide_info", "cancel"]`

### Code execution still hangs
- Verify all required agents are loaded
- Check handoffs setup doesn't fail silently
- Enable debug mode to see agent loading messages

### Cancel doesn't work
- Check approval manager is passed in context
- Verify UI is calling reject/cancel on approval
- Check workflow state machine transitions

## Summary

**Fixed Issues:**
1. ✅ Clarification text input works
2. ✅ Code execution no longer hangs
3. ✅ Stop/Continue through approval rejection
4. ✅ AG2-style permission checkpoints added
5. ✅ Graceful error handling for missing agents

**What UI Needs to Do:**
1. Show text input when `requires_text_input=True`
2. Always show Cancel button during execution
3. Handle different checkpoint types appropriately
4. Call approval resolution APIs to stop/continue
