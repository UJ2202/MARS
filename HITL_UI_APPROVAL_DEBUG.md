# HITL UI Approval Issue - Debugging Guide

## Problem
The HITL workflow is stuck waiting for approval. The backend logs show the approval message ("STEP 1 REVIEW" with options Continue/Redo/Abort), but the UI is not displaying the approval interface.

## Architecture Overview

### How HITL Approvals Work

1. **Backend** (`hitl_control.py`):
   - HITLControlPhase calls `_request_step_review()`
   - Uses `WebSocketApprovalManager.create_approval_request()`
   - This sends an "approval_requested" WebSocket event

2. **WebSocket Manager** (`websocket_approval_manager.py`):
   - Creates an in-memory approval request
   - Sends event via `ws_send_event("approval_requested", data)`

3. **WebSocket Handler** (`handlers.py`):
   - Receives approval response from UI
   - Resolves approval using `WebSocketApprovalManager.resolve()`

4. **Frontend** (`WebSocketContext.tsx`):
   - Receives "approval_requested" event
   - Calls `setPendingApproval(data)`
   - Sets state that triggers UI render

5. **UI Component** (`ApprovalChatPanel.tsx`):
   - Renders when `pendingApproval` is not null
   - Shows approval options and feedback form
   - Calls `onResolve` when user submits

## Diagnostic Changes Made

### 1. Backend - WebSocket Approval Manager
**File:** `cmbagent/database/websocket_approval_manager.py`
**Lines:** 119-145

Added detailed logging:
```python
print(f"[WebSocketApprovalManager] Sending approval_requested event:")
print(f"  - approval_id: {request.id}")
print(f"  - step_id: {step_id}")
print(f"  - checkpoint_type: {checkpoint_type}")
print(f"  - message: {message[:100]}...")
print(f"  - options: {request.options}")
```

This will show in the backend logs exactly what is being sent.

### 2. Frontend - WebSocket Context
**File:** `cmbagent-ui/contexts/WebSocketContext.tsx`
**Line:** 195

Added console logging:
```typescript
console.log('[WebSocket] Approval requested event received:', data);
```

This will show in the browser console if the event is received.

## How to Debug

### Step 1: Check Backend Logs
Look for these lines in the backend output:
```
[WebSocketApprovalManager] Sending approval_requested event:
  - approval_id: <UUID>
  - step_id: hitl_control_step_1_review
  - checkpoint_type: after_step
  - message: **Step 1 Review**...
  - options: ['continue', 'abort', 'redo']
[WebSocketApprovalManager] ✓ Approval request <UUID> sent to UI via WebSocket
```

If you see this, the backend is sending the event correctly.

If you see an error like:
```
[WebSocketApprovalManager] ✗ Failed to send approval_requested event: ...
```

Then there's an issue with the WebSocket connection or the `ws_send_event` function.

### Step 2: Check Frontend Console (Browser DevTools)
Open the browser console (F12) and look for:
```
[WebSocket] Approval requested event received: {approval_id: '...', description: '...', options: [...]}
```

If you see this, the frontend received the event.

If you DON'T see this:
- The WebSocket event is not being sent properly
- The WebSocket connection is broken
- The event type name doesn't match ("approval_requested" vs something else)

### Step 3: Check React State
If the event is received but UI doesn't show, add this to your browser console:
```javascript
// Check if pendingApproval state exists
// (This depends on how React DevTools shows state)
```

Or check the React Components tab in DevTools:
1. Find "WebSocketContext.Provider"
2. Look at its state
3. Check if `pendingApproval` has a value

### Step 4: Check Component Rendering
If state is set but component doesn't render, check:

1. **Is the Console tab selected?**
   - The ApprovalChatPanel only shows in the Console tab
   - Check line 372 in `app/page.tsx`:
     ```typescript
     {rightPanelTab === 'console' && (
       ...
       {pendingApproval && (
         <ApprovalChatPanel
     ```

2. **Is the component mounted?**
   - Look for the element in browser DevTools > Elements
   - Search for `ApprovalChatPanel` or "Approval" text

## Possible Issues & Solutions

### Issue 1: Event Not Sent from Backend
**Symptoms:** No log in backend about sending event, or error shown

**Causes:**
- `ws_send_event` function not working
- Thread/async issue in `asyncio.run_coroutine_threadsafe`

**Solution:**
- Check that `loop` is the correct event loop
- Ensure WebSocket is still connected

### Issue 2: Event Not Received by Frontend
**Symptoms:** Backend sends event, but frontend console.log doesn't fire

**Causes:**
- WebSocket disconnected
- Event type mismatch
- Event handler not registered

**Solution:**
- Check WebSocket connection status in frontend
- Verify event type is exactly "approval_requested"
- Ensure useEventHandler is set up correctly

### Issue 3: State Not Updating
**Symptoms:** Frontend receives event, but `pendingApproval` stays null

**Causes:**
- React state update issue
- Component not re-rendering

**Solution:**
- Check if `setPendingApproval` is called
- Verify no errors in React console
- Check if data format matches `ApprovalRequestedData` type

### Issue 4: Component Not Rendering
**Symptoms:** State updates, but UI doesn't show

**Causes:**
- Wrong tab selected (not Console tab)
- CSS hiding the component
- Conditional rendering false

**Solution:**
- Click on "Console" tab in right panel
- Check if `{rightPanelTab === 'console'}` is true
- Check if `{pendingApproval}` is truthy
- Look for CSS `display: none` or `visibility: hidden`

## Quick Test
To quickly test if the UI component works, add this to your browser console:

```javascript
// Manually trigger an approval request (when on the page)
// This simulates receiving the WebSocket event
const testApproval = {
  approval_id: 'test-123',
  step_id: 'test-step',
  action: 'after_step',
  description: 'Test approval - does the UI show?',
  message: 'This is a test message',
  options: ['approve', 'reject'],
  checkpoint_type: 'after_step',
  context: {}
};

// You'll need to get the WebSocket context and call setPendingApproval
// This is tricky without React DevTools access
```

## Next Steps

1. Run the workflow again with the new debug logging
2. Check both backend logs and browser console
3. Identify at which point the approval request is lost
4. Report findings:
   - Did backend send the event?
   - Did frontend receive the event?
   - Did state update?
   - Is Console tab active?
5. Based on findings, we'll know which layer needs fixing
