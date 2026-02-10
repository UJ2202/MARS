# HITL Step Review Not Showing - Debug Guide

## Problem

- Plan approval works ✅ (appears in UI)
- Step 1 review doesn't show ❌ (stuck in backend)
- Message appears in backend logs but not UI
- WebSocket connection is working (plan approval proved this)

## What I Fixed

1. **Added missing option configs** to `ApprovalChatPanel.tsx`:
   - `continue` (green, "Continue to next step")
   - `abort` (red, "Stop the workflow")
   - `redo` (yellow, "Repeat this step")
   - `skip` (gray, "Skip this step")

2. **Added "after_step" title** to `ApprovalChatPanel.tsx`:
   - Will now show "✅ Step Review Required"

3. **Fail-fast on WebSocket errors** in `websocket_approval_manager.py`:
   - Will now raise error instead of hanging silently

## Debugging Steps

### Step 1: Check Backend Logs

When step review appears, look for:

```
✓ Approval request <id> sent to UI via WebSocket
```

**If you see this:** WebSocket event sent successfully → Problem is on frontend
**If you see error:** WebSocket send failed → Problem is backend connection
**If you see nothing:** Approval request not being created

### Step 2: Check Browser Console

Open DevTools → Console, and run:

```javascript
// Add temporary logging
const originalSetState = console.log;
window._approvalDebug = true;
```

Then look for:
```
Received approval request: {...}
```

**If you see this:** Event reached frontend → Problem is in approval handling
**If you don't see this:** Event not reaching frontend → WebSocket routing issue

### Step 3: Check WebSocket Events

In browser console:

```javascript
// Log all WebSocket messages
window._originalConsoleLog = console.log;
console.log = function(...args) {
  if (args[0]?.includes('approval') || args[0]?.includes('Approval')) {
    window._originalConsoleLog('[APPROVAL EVENT]', ...args);
  }
  window._originalConsoleLog(...args);
};
```

### Step 4: Check Approval State

In browser console while waiting for approval:

```javascript
// Check if approval is in pending state
// (Replace with actual state inspection method for your app)
// You might need to inspect React DevTools
```

## Possible Causes

### Cause A: WebSocket Event Not Being Sent

**Symptom:** No "✓ Approval request sent" in backend logs

**Check:** Look for exception in backend:
```python
logger.error(f"✗ Failed to send approval_requested event: {e}")
```

**Fix:** Check `ws_send_event` function is properly initialized

---

### Cause B: Event Sent But Not Received

**Symptom:** "✓ Approval request sent" in backend, but nothing in browser console

**Possible Issues:**
1. WebSocket connection dropped between plan approval and step review
2. Event name mismatch (though types look correct)
3. Event being filtered somewhere

**Check:**
```javascript
// In browser console, check WebSocket state
window.WebSocket.prototype.send = function(data) {
  console.log('[WS SEND]', data);
  return originalSend.call(this, data);
};
```

---

### Cause C: Event Received But Not Displaying

**Symptom:** Event log in console, but UI doesn't update

**Check:**
1. Is `pendingApproval` being set?
2. Is `ApprovalChatPanel` component rendering?
3. Is component being hidden by CSS?

**Debug:**
```typescript
// Add to WebSocketContext.tsx line 195:
onApprovalRequested: (data: ApprovalRequestedData) => {
  console.log('[DEBUG] Setting pending approval:', data);
  console.log('[DEBUG] Checkpoint type:', data.checkpoint_type);
  console.log('[DEBUG] Options:', data.options);
  setPendingApproval(data);
  addConsoleOutput(`⏸️ Approval requested: ${data.description}`);
},
```

---

### Cause D: Different Approval Manager Instance

**Symptom:** Backend thinks it sent event, but wrong WebSocket connection

**Check:** Verify same approval_manager instance used:
```python
# In hitl_control.py line 636:
print(f"[DEBUG] Approval manager: {approval_manager}")
print(f"[DEBUG] ws_send_event: {approval_manager.ws_send_event}")
```

---

## Quick Diagnostic Test

Add this to backend `websocket_approval_manager.py` line 117:

```python
# Send WebSocket event to UI
print(f"[DEBUG] About to send approval_requested event")
print(f"[DEBUG] ws_send_event function: {self.ws_send_event}")
print(f"[DEBUG] Event data: approval_id={request.id}, checkpoint_type={checkpoint_type}")

try:
    self.ws_send_event("approval_requested", {
        "approval_id": request.id,
        # ... rest of data
    })
    logger.info(f"✓ Approval request {request.id} sent to UI via WebSocket")
    print(f"[DEBUG] Event sent successfully!")
except Exception as e:
    logger.error(f"✗ Failed to send approval_requested event: {e}")
    print(f"[DEBUG] Event send FAILED: {e}")
    # ... rest of error handling
```

And add to frontend `WebSocketContext.tsx` line 194:

```typescript
onApprovalRequested: (data: ApprovalRequestedData) => {
  console.log('[DEBUG] onApprovalRequested called');
  console.log('[DEBUG] Approval data:', JSON.stringify(data, null, 2));
  console.log('[DEBUG] Current pendingApproval before:', pendingApproval);

  setPendingApproval(data);
  addConsoleOutput(`⏸️ Approval requested: ${data.description}`);

  console.log('[DEBUG] setPendingApproval called');
},
```

## Expected Flow

```
Backend creates approval request
   ↓
Backend calls ws_send_event("approval_requested", {...})
   ↓  [Should see: "✓ Approval request sent" in logs]
   ↓
WebSocket sends message to frontend
   ↓
Frontend WebSocket receives "approval_requested" event
   ↓  [Should see in browser console]
   ↓
useEventHandler routes to onApprovalRequested
   ↓
WebSocketContext.onApprovalRequested calls setPendingApproval(data)
   ↓  [Should see "[DEBUG] onApprovalRequested called"]
   ↓
pendingApproval state updates
   ↓
ApprovalChatPanel component renders (line 372: {pendingApproval && ...})
   ↓  [Should see approval panel at bottom of console]
   ↓
User sees approval UI ✅
```

## Manual Test

In browser console while stuck:

```javascript
// Manually trigger approval UI to test if component works
window.testApproval = {
  approval_id: "test-123",
  step_id: "test_step",
  action: "after_step",
  checkpoint_type: "after_step",
  description: "**Step 1 Review**\n\n**Task:** Test\n\n**Status:** Completed successfully",
  message: "Test step review",
  options: ["continue", "abort", "redo"],
  context: {}
};

// Then in React DevTools or your app's state management:
// Manually set pending approval to window.testApproval
// to see if the UI renders correctly
```

---

## Next Steps

1. **Add debug logging** as shown above
2. **Run workflow** until it sticks on step review
3. **Check each step** in the flow

 above
4. **Report back** which step fails

The specific failure point will tell us exactly what to fix!

---

## Files Modified

- ✅ `cmbagent-ui/components/ApprovalChatPanel.tsx` - Added option configs
- ✅ `cmbagent/database/websocket_approval_manager.py` - Fail-fast on WebSocket error

**Status:** Ready for debugging with enhanced logging
