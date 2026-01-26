# Stage 6: Human-in-the-Loop Approval System

**Phase:** 2 - Human-in-the-Loop and Parallel Execution
**Estimated Time:** 35-45 minutes
**Dependencies:** Stage 5 (Enhanced WebSocket) must be complete
**Risk Level:** Medium

## Objectives

1. Implement approval gates in workflow execution
2. Support multiple approval modes (after planning, before steps, on error, manual)
3. Create approval request UI component
4. Inject user feedback into agent context for subsequent steps
5. Support workflow pause at approval points
6. Track approval history and decisions in database

## Current State Analysis

### What We Have
- Fully autonomous execution (no human intervention)
- No approval checkpoints
- Cannot inject feedback during execution
- Errors cause immediate failure
- No way to guide agent mid-workflow

### What We Need
- Configurable approval gates
- UI for approval dialogs
- Feedback injection into context
- Pause/resume at approval points
- Approval audit trail
- Multiple approval modes

## Pre-Stage Verification

### Check Prerequisites
1. Stage 5 complete and verified
2. WebSocket event protocol working
3. Real-time updates functioning
4. State machine supports WAITING_APPROVAL state
5. Database has approval_requests table

### Expected State
- Can pause/resume workflows
- WebSocket delivers events reliably
- State transitions tracked
- Ready to add approval gates
- No breaking changes to autonomous execution

## Implementation Tasks

### Task 1: Define Approval Modes
**Objective:** Create configurable approval policies

**Implementation:**

Create approval mode enum:
```python
from enum import Enum

class ApprovalMode(str, Enum):
    """Approval modes for workflow execution"""
    NONE = "none"                          # No approvals (default)
    AFTER_PLANNING = "after_planning"      # Single approval after plan created
    BEFORE_EACH_STEP = "before_each_step"  # Approval before each major step
    ON_ERROR = "on_error"                  # Approval only when errors occur
    MANUAL = "manual"                      # User can pause anytime
    CUSTOM = "custom"                      # Custom approval checkpoints

class ApprovalCheckpoint:
    """Defines when approval is required"""
    step_number: Optional[int]   # Specific step number
    step_type: Optional[str]     # Type of step (planning, agent, etc.)
    condition: Optional[Callable]  # Custom condition function
    message: str                 # Message to show user
    options: List[str]           # Available options (approve, reject, modify)
    allow_feedback: bool         # Whether user can provide text feedback
```

**Files to Create:**
- `cmbagent/database/approval_types.py`

**Verification:**
- Approval modes defined
- Checkpoint configuration flexible
- Can specify custom checkpoints
- Default mode is NONE (backward compatible)

### Task 2: Implement Approval Request Manager
**Objective:** Create and manage approval requests

**Implementation:**

```python
from typing import Optional, Dict, Any
from cmbagent.database.models import ApprovalRequest, WorkflowRun, WorkflowStep
from cmbagent.database.states import WorkflowState, StepState
from cmbagent.database.state_machine import StateMachine
from datetime import datetime
import uuid

class ApprovalManager:
    """Manages approval requests and responses"""

    def __init__(self, db_session, session_id):
        self.db = db_session
        self.session_id = session_id
        self.workflow_sm = StateMachine(db_session, "workflow_run")
        self.step_sm = StateMachine(db_session, "workflow_step")

    def create_approval_request(
        self,
        run_id: str,
        step_id: Optional[str],
        checkpoint_type: str,
        context_snapshot: Dict[str, Any],
        message: str,
        options: List[str] = None
    ) -> ApprovalRequest:
        """
        Create new approval request

        Args:
            run_id: Workflow run ID
            step_id: Current step ID (optional)
            checkpoint_type: Type of checkpoint (planning, step, error)
            context_snapshot: Current workflow context
            message: Message for user
            options: Available approval options

        Returns:
            Created ApprovalRequest
        """
        approval = ApprovalRequest(
            id=uuid.uuid4(),
            run_id=run_id,
            step_id=step_id,
            status="pending",
            requested_at=datetime.utcnow(),
            context_snapshot=context_snapshot,
            metadata={
                "checkpoint_type": checkpoint_type,
                "message": message,
                "options": options or ["approve", "reject", "modify"]
            }
        )

        self.db.add(approval)
        self.db.commit()

        # Transition workflow to WAITING_APPROVAL
        self.workflow_sm.transition_to(
            run_id,
            WorkflowState.WAITING_APPROVAL,
            reason=f"Approval requested: {checkpoint_type}"
        )

        # If specific step, transition step as well
        if step_id:
            self.step_sm.transition_to(
                step_id,
                StepState.WAITING_APPROVAL,
                reason="Awaiting user approval"
            )

        # Emit WebSocket event
        self._emit_approval_event(approval)

        return approval

    def resolve_approval(
        self,
        approval_id: str,
        resolution: str,
        user_feedback: Optional[str] = None
    ) -> ApprovalRequest:
        """
        Resolve approval request

        Args:
            approval_id: Approval request ID
            resolution: "approved", "rejected", or "modified"
            user_feedback: Optional feedback from user

        Returns:
            Updated ApprovalRequest
        """
        approval = self.db.query(ApprovalRequest).filter(
            ApprovalRequest.id == approval_id
        ).first()

        if not approval:
            raise ValueError(f"Approval request {approval_id} not found")

        if approval.status != "pending":
            raise ValueError(f"Approval already resolved: {approval.status}")

        # Update approval
        approval.status = resolution
        approval.resolved_at = datetime.utcnow()
        approval.user_feedback = user_feedback
        approval.resolution = resolution

        self.db.commit()

        # Transition workflow back to EXECUTING (if approved)
        if resolution == "approved" or resolution == "modified":
            self.workflow_sm.transition_to(
                approval.run_id,
                WorkflowState.EXECUTING,
                reason=f"Approval {resolution}: {user_feedback or 'No feedback'}"
            )

            # Resume step if applicable
            if approval.step_id:
                self.step_sm.transition_to(
                    approval.step_id,
                    StepState.RUNNING,
                    reason="Approved, resuming execution"
                )

        elif resolution == "rejected":
            self.workflow_sm.transition_to(
                approval.run_id,
                WorkflowState.CANCELLED,
                reason=f"Rejected by user: {user_feedback or 'No reason'}"
            )

        # Emit WebSocket event
        self._emit_approval_resolved_event(approval)

        return approval

    def get_pending_approvals(self, run_id: str) -> List[ApprovalRequest]:
        """Get all pending approvals for run"""
        return self.db.query(ApprovalRequest).filter(
            ApprovalRequest.run_id == run_id,
            ApprovalRequest.status == "pending"
        ).all()

    def wait_for_approval(self, approval_id: str, timeout_seconds: int = None):
        """
        Block until approval is resolved

        Args:
            approval_id: Approval request ID
            timeout_seconds: Max time to wait (None = infinite)

        Returns:
            Resolved ApprovalRequest

        Raises:
            TimeoutError: If timeout exceeded
        """
        import time
        start_time = time.time()

        while True:
            approval = self.db.query(ApprovalRequest).filter(
                ApprovalRequest.id == approval_id
            ).first()

            if approval.status != "pending":
                return approval

            if timeout_seconds and (time.time() - start_time) > timeout_seconds:
                raise TimeoutError(f"Approval timeout after {timeout_seconds}s")

            time.sleep(1)  # Poll every second
            self.db.refresh(approval)

    def _emit_approval_event(self, approval: ApprovalRequest):
        """Emit approval_requested event via WebSocket"""
        from backend.websocket_events import WebSocketEvent, WebSocketEventType
        from backend.event_queue import event_queue

        event = WebSocketEvent(
            event_type=WebSocketEventType.APPROVAL_REQUESTED,
            timestamp=datetime.utcnow(),
            run_id=str(approval.run_id),
            data={
                "approval_id": str(approval.id),
                "step_id": str(approval.step_id) if approval.step_id else None,
                "message": approval.metadata.get("message"),
                "options": approval.metadata.get("options"),
                "context": approval.context_snapshot
            }
        )

        event_queue.push(str(approval.run_id), event)

    def _emit_approval_resolved_event(self, approval: ApprovalRequest):
        """Emit approval_received event via WebSocket"""
        from backend.websocket_events import WebSocketEvent, WebSocketEventType
        from backend.event_queue import event_queue

        event = WebSocketEvent(
            event_type=WebSocketEventType.APPROVAL_RECEIVED,
            timestamp=datetime.utcnow(),
            run_id=str(approval.run_id),
            data={
                "approval_id": str(approval.id),
                "resolution": approval.resolution,
                "feedback": approval.user_feedback
            }
        )

        event_queue.push(str(approval.run_id), event)
```

**Files to Create:**
- `cmbagent/database/approval_manager.py`

**Verification:**
- Can create approval requests
- Requests pause workflow execution
- Can resolve approvals
- Feedback captured in database
- WebSocket events emitted
- Wait for approval works

### Task 3: Add Approval Checkpoints to Workflow
**Objective:** Integrate approval gates into execution flow

**Implementation:**

Update CMBAgent to support approval mode:
```python
from cmbagent.database.approval_types import ApprovalMode
from cmbagent.database.approval_manager import ApprovalManager

class CMBAgent:
    def __init__(self, approval_mode: ApprovalMode = ApprovalMode.NONE, **kwargs):
        # ... existing init ...
        self.approval_mode = approval_mode
        self.approval_manager = ApprovalManager(self.db_session, self.session_id)

    def planning_and_control_context_carryover(self, task, agent="engineer", model="gpt-4o", ...):
        # ... existing planning execution ...

        # CHECKPOINT: After planning
        if self.approval_mode in [ApprovalMode.AFTER_PLANNING, ApprovalMode.BEFORE_EACH_STEP]:
            approval = self.approval_manager.create_approval_request(
                run_id=run.id,
                step_id=None,
                checkpoint_type="after_planning",
                context_snapshot={
                    "plan": plan,
                    "task": task
                },
                message=f"Planning complete. Review plan before execution?\n\n{plan}"
            )

            # Wait for approval
            approval = self.approval_manager.wait_for_approval(approval.id)

            if approval.resolution == "rejected":
                raise WorkflowCancelledException("User rejected plan")

            # Inject feedback into context
            if approval.user_feedback:
                shared_context["user_feedback_planning"] = approval.user_feedback

        # ... DAG building ...

        # Execute DAG with approval checkpoints
        for level in execution_levels:
            for node in level["nodes"]:
                # CHECKPOINT: Before each step
                if self.approval_mode == ApprovalMode.BEFORE_EACH_STEP:
                    step_approval = self.approval_manager.create_approval_request(
                        run_id=run.id,
                        step_id=node["id"],
                        checkpoint_type="before_step",
                        context_snapshot={
                            "node": node,
                            "previous_outputs": shared_context.get("outputs", [])
                        },
                        message=f"About to execute step {node['step_number']}: {node['task']}\n\nProceed?"
                    )

                    step_approval = self.approval_manager.wait_for_approval(step_approval.id)

                    if step_approval.resolution == "rejected":
                        # Skip this step
                        self.step_sm.transition_to(node["id"], StepState.SKIPPED)
                        continue

                    # Inject feedback
                    if step_approval.user_feedback:
                        shared_context[f"user_feedback_step_{node['step_number']}"] = step_approval.user_feedback

                try:
                    # Execute step
                    result = self._execute_step(node)

                except Exception as e:
                    # CHECKPOINT: On error
                    if self.approval_mode in [ApprovalMode.ON_ERROR, ApprovalMode.BEFORE_EACH_STEP]:
                        error_approval = self.approval_manager.create_approval_request(
                            run_id=run.id,
                            step_id=node["id"],
                            checkpoint_type="on_error",
                            context_snapshot={
                                "error": str(e),
                                "traceback": traceback.format_exc(),
                                "node": node
                            },
                            message=f"Error occurred in step {node['step_number']}:\n\n{str(e)}\n\nHow to proceed?",
                            options=["retry", "skip", "abort", "modify"]
                        )

                        error_approval = self.approval_manager.wait_for_approval(error_approval.id)

                        if error_approval.resolution == "retry":
                            # Inject feedback and retry
                            if error_approval.user_feedback:
                                shared_context[f"retry_guidance_{node['step_number']}"] = error_approval.user_feedback
                            result = self._execute_step(node)  # Retry with guidance

                        elif error_approval.resolution == "skip":
                            self.step_sm.transition_to(node["id"], StepState.SKIPPED)
                            continue

                        elif error_approval.resolution == "abort":
                            raise WorkflowCancelledException("User aborted on error")

                    else:
                        raise  # Re-raise if no approval mode for errors
```

**Files to Modify:**
- `cmbagent/cmbagent.py` (add approval checkpoints)

**Verification:**
- Approval mode configurable
- Checkpoints pause execution
- Feedback injected into context
- Different modes work correctly
- Can retry with guidance
- Can skip failed steps

### Task 4: Create Approval UI Component
**Objective:** Build React component for approval dialogs

**Implementation:**

Create approval dialog component:
```typescript
// cmbagent-ui/components/ApprovalDialog.tsx

import React, { useState } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Radio, RadioGroup, FormControlLabel } from '@mui/material';

interface ApprovalDialogProps {
  open: boolean;
  approval: {
    id: string;
    message: string;
    options: string[];
    context: any;
  };
  onResolve: (resolution: string, feedback?: string) => void;
}

export function ApprovalDialog({ open, approval, onResolve }: ApprovalDialogProps) {
  const [selectedOption, setSelectedOption] = useState(approval.options[0]);
  const [feedback, setFeedback] = useState('');

  const handleSubmit = () => {
    onResolve(selectedOption, feedback || undefined);
    setFeedback('');
  };

  return (
    <Dialog open={open} maxWidth="md" fullWidth>
      <DialogTitle>Approval Required</DialogTitle>

      <DialogContent>
        <div style={{ marginBottom: 16 }}>
          <strong>Message:</strong>
          <pre style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>
            {approval.message}
          </pre>
        </div>

        <RadioGroup
          value={selectedOption}
          onChange={(e) => setSelectedOption(e.target.value)}
        >
          {approval.options.map((option) => (
            <FormControlLabel
              key={option}
              value={option}
              control={<Radio />}
              label={option.charAt(0).toUpperCase() + option.slice(1)}
            />
          ))}
        </RadioGroup>

        <TextField
          label="Feedback / Instructions (optional)"
          multiline
          rows={4}
          fullWidth
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="Provide guidance or modifications to the plan..."
          style={{ marginTop: 16 }}
        />

        {approval.context && (
          <details style={{ marginTop: 16 }}>
            <summary>View Context</summary>
            <pre style={{ fontSize: 12, overflow: 'auto', maxHeight: 200 }}>
              {JSON.stringify(approval.context, null, 2)}
            </pre>
          </details>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={() => onResolve('rejected', 'Cancelled by user')}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} variant="contained" color="primary">
          Submit
        </Button>
      </DialogActions>
    </Dialog>
  );
}
```

Integrate with WebSocket:
```typescript
// cmbagent-ui/pages/workflow.tsx

import { ApprovalDialog } from '@/components/ApprovalDialog';

export default function WorkflowPage() {
  const [approvalRequest, setApprovalRequest] = useState(null);

  const handleMessage = (message) => {
    if (message.event_type === 'approval_requested') {
      setApprovalRequest({
        id: message.data.approval_id,
        message: message.data.message,
        options: message.data.options,
        context: message.data.context
      });
    } else if (message.event_type === 'approval_received') {
      setApprovalRequest(null); // Close dialog
    }
  };

  const { sendMessage } = useResilientWebSocket({
    runId: runId,
    onMessage: handleMessage
  });

  const handleApprovalResolve = (resolution: string, feedback?: string) => {
    sendMessage({
      type: 'resolve_approval',
      approval_id: approvalRequest.id,
      resolution: resolution,
      feedback: feedback
    });
  };

  return (
    <div>
      {/* Workflow UI */}

      <ApprovalDialog
        open={!!approvalRequest}
        approval={approvalRequest}
        onResolve={handleApprovalResolve}
      />
    </div>
  );
}
```

**Files to Create:**
- `cmbagent-ui/components/ApprovalDialog.tsx`

**Files to Modify:**
- `cmbagent-ui/pages/workflow.tsx` (integrate approval dialog)

**Verification:**
- Dialog shows on approval request
- Can select options
- Can provide feedback
- Sends resolution via WebSocket
- Dialog closes on resolution

### Task 5: Handle Approval Responses in Backend
**Objective:** Process approval resolutions from UI

**Implementation:**

Update WebSocket handler:
```python
# In backend/run.py

async def handle_client_message(run_id: str, message: dict):
    msg_type = message.get("type")

    # ... existing handlers ...

    elif msg_type == "resolve_approval":
        # Handle approval resolution
        approval_id = message.get("approval_id")
        resolution = message.get("resolution")
        feedback = message.get("feedback")

        db = get_db_session()
        try:
            # Get session_id from workflow run
            run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()

            approval_manager = ApprovalManager(db, str(run.session_id))
            approval_manager.resolve_approval(
                approval_id=approval_id,
                resolution=resolution,
                user_feedback=feedback
            )

        finally:
            db.close()
```

**Files to Modify:**
- `backend/run.py` (handle approval resolution)

**Verification:**
- Backend receives approval responses
- Approvals resolved in database
- Workflow resumes after approval
- Feedback stored correctly

### Task 6: Inject Feedback into Agent Context
**Objective:** Pass user feedback to agents for informed execution

**Implementation:**

Update agent execution to include feedback:
```python
# In cmbagent.py

def _execute_agent(self, agent_name: str, task: str, run_id: str, step_number: int):
    # Load user feedback from context
    feedback_key = f"user_feedback_step_{step_number}"
    user_feedback = shared_context.get(feedback_key)

    # Augment task with feedback
    if user_feedback:
        augmented_task = f"""
{task}

USER GUIDANCE:
{user_feedback}

Please take the user's guidance into account when executing this task.
"""
    else:
        augmented_task = task

    # Execute agent with augmented task
    result = self.agents[agent_name].execute(augmented_task)

    return result
```

Update retry context to include feedback:
```python
# In retry logic

retry_context = {
    "attempt_number": attempt,
    "previous_error": error_message,
    "user_feedback": shared_context.get(f"retry_guidance_{step_number}"),
    "suggestions": generate_suggestions(error_message)
}

# Inject into agent prompt
agent_prompt = f"""
Previous attempt failed: {error_message}

User guidance: {retry_context['user_feedback']}

Suggestions:
{retry_context['suggestions']}

Please retry with this context in mind.
"""
```

**Files to Modify:**
- `cmbagent/cmbagent.py` (inject feedback into agent execution)

**Verification:**
- Feedback passed to agents
- Agents use feedback in execution
- Retry includes user guidance
- Feedback visible in agent logs

## Files to Create (Summary)

### New Files
```
cmbagent/database/
├── approval_types.py            # Approval modes and checkpoint types
└── approval_manager.py          # Approval request manager

cmbagent-ui/components/
└── ApprovalDialog.tsx           # Approval UI component
```

### Modified Files
- `cmbagent/cmbagent.py` - Add approval checkpoints and feedback injection
- `backend/run.py` - Handle approval resolutions
- `cmbagent-ui/pages/workflow.tsx` - Integrate approval dialog

## Verification Criteria

### Must Pass
- [ ] Approval modes defined and configurable
- [ ] Approval requests created at checkpoints
- [ ] Workflow pauses at approval gates
- [ ] UI dialog shows approval requests
- [ ] User can approve/reject/modify
- [ ] Feedback injected into agent context
- [ ] Workflow resumes after approval
- [ ] Approval history tracked in database
- [ ] WebSocket events for approvals working
- [ ] Can skip failed steps with feedback

### Should Pass
- [ ] Multiple approval modes work correctly
- [ ] Custom approval checkpoints supported
- [ ] Approval timeout handling
- [ ] Can view approval history
- [ ] Approval context visible in UI

### Approval Testing
```python
# Test approval creation
def test_create_approval():
    manager = ApprovalManager(db_session, session_id)
    approval = manager.create_approval_request(
        run_id=run_id,
        step_id=None,
        checkpoint_type="after_planning",
        context_snapshot={"plan": "test"},
        message="Approve plan?"
    )
    assert approval.status == "pending"

# Test approval resolution
def test_resolve_approval():
    approval = manager.resolve_approval(
        approval_id=approval.id,
        resolution="approved",
        user_feedback="Looks good!"
    )
    assert approval.status == "approved"
    assert approval.user_feedback == "Looks good!"

# Test feedback injection
def test_feedback_injection():
    agent = CMBAgent(approval_mode=ApprovalMode.BEFORE_EACH_STEP)
    # Provide feedback at checkpoint
    # Verify feedback in agent context
```

## Testing Checklist

### Unit Tests
```python
# Test approval manager
def test_approval_manager():
    manager = ApprovalManager(db_session, session_id)
    approval = manager.create_approval_request(...)
    assert approval is not None

# Test wait for approval
def test_wait_for_approval():
    # Create approval
    # Resolve in background thread
    # Verify wait_for_approval returns resolved approval
```

### Integration Tests
```typescript
// Test approval dialog
test('shows approval dialog on request', () => {
  render(<WorkflowPage />);
  // Simulate approval_requested event
  // Verify dialog appears
});

test('sends approval resolution', () => {
  // User selects option and submits
  // Verify WebSocket message sent
});
```

## Common Issues and Solutions

### Issue 1: Approval Timeout Not Handled
**Symptom:** Workflow hangs indefinitely waiting for approval
**Solution:** Implement timeout with default action (reject or skip)

### Issue 2: Feedback Not Injected
**Symptom:** Agent ignores user guidance
**Solution:** Verify feedback stored in context and passed to agent prompt

### Issue 3: Multiple Approval Dialogs
**Symptom:** UI shows multiple dialogs simultaneously
**Solution:** Queue approvals, show one at a time

### Issue 4: Approval State Desync
**Symptom:** UI and backend have different approval states
**Solution:** Backend is source of truth, UI requests current state on reconnect

### Issue 5: Cannot Resume After Approval
**Symptom:** Workflow stuck in WAITING_APPROVAL state
**Solution:** Verify state transition logic, ensure EXECUTING state set on approval

## Rollback Procedure

If approval system causes issues:

1. **Disable approval mode:**
   ```python
   approval_mode = ApprovalMode.NONE  # Default
   ```

2. **Remove approval checkpoints:**
   ```python
   # Comment out approval checkpoint code
   # if self.approval_mode == ...:
   #     create_approval_request(...)
   ```

3. **Keep approval tables** - Useful for debugging

4. **Document issues** for future resolution

## Post-Stage Actions

### Documentation
- Document approval modes and usage
- Add approval API reference
- Create approval workflow guide
- Document feedback injection

### Update Progress
- Mark Stage 6 complete in PROGRESS.md
- Note any deviations from plan
- Document time spent
- Update approval lessons learned

### Prepare for Stage 7
- Approval system operational
- Feedback injection working
- Ready to enhance retry mechanism
- Stage 7 can proceed

## Success Criteria

Stage 6 is complete when:
1. Approval modes implemented
2. Approval gates pause execution
3. UI shows approval dialogs
4. User feedback injected into context
5. Workflow resumes after approval
6. Approval history tracked
7. Verification checklist 100% complete

## Estimated Time Breakdown

- Approval types and modes: 5 min
- Approval manager implementation: 10 min
- Checkpoint integration: 8 min
- UI approval dialog: 8 min
- Backend approval handling: 5 min
- Feedback injection: 5 min
- Testing and verification: 9 min
- Documentation: 5 min

**Total: 35-45 minutes**

## Next Stage

Once Stage 6 is verified complete, proceed to:
**Stage 7: Context-Aware Retry Mechanism**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
