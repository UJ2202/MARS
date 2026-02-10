# HITL WebSocket Approval - Silent Failure Fix

## Issue

When WebSocket approval events fail to send:
- `ws_send_event("approval_requested", ...)` raises exception
- Exception is caught and only logged as warning
- Workflow continues waiting for approval that UI never received
- **Result:** Workflow hangs indefinitely

## Symptoms

```
============================================================
**Step 1 Review**

**Task:** Generate a list of possible approaches...

**Status:** Completed successfully

**Options:**
- **Continue**: Proceed to next step
- **Redo**: Re-execute this step
- **Abort**: Cancel the workflow
Waiting for review...
============================================================
```

- Message appears in backend logs ✅
- Message DOES NOT appear in UI ❌
- User cannot respond
- Workflow stuck forever

## Root Causes

### 1. WebSocket Connection Lost
- Connection dropped during execution
- `ws_send_event` raises exception
- No reconnection logic

### 2. WebSocket Not Initialized
- Workflow started without WebSocket
- `ws_send_event` is None or broken
- Console fallback not working

### 3. Event Not Reaching Frontend
- WebSocket sends successfully
- Frontend doesn't receive event
- Event name mismatch or filtering issue

## Solutions

### Solution A: Fail Fast (Recommended)

**Don't continue if WebSocket send fails:**

```python
# In websocket_approval_manager.py: create_approval_request()

# Send WebSocket event to UI
try:
    self.ws_send_event("approval_requested", {
        "approval_id": request.id,
        "step_id": step_id,
        "action": checkpoint_type,
        "description": message,
        "message": message,
        "options": request.options,
        "checkpoint_type": checkpoint_type,
        "context": context_snapshot,
    })
    logger.info(f"Approval request {request.id} sent to UI via WebSocket")
except Exception as e:
    logger.error(f"Failed to send approval_requested event: {e}")
    # Clean up
    with self._lock:
        WebSocketApprovalManager._pending.pop(request.id, None)
    # FAIL FAST instead of hanging
    raise RuntimeError(
        f"Cannot send approval request to UI: WebSocket send failed - {e}"
    ) from e

return request
```

**Benefits:**
- ✅ Fails immediately with clear error
- ✅ User knows something is wrong
- ✅ No silent hanging

**Drawbacks:**
- ❌ Workflow stops if WebSocket temporarily down

---

### Solution B: Fallback to Console

**Use console input if WebSocket fails:**

```python
# In websocket_approval_manager.py: create_approval_request()

# Try WebSocket first
websocket_success = False
try:
    self.ws_send_event("approval_requested", {...})
    websocket_success = True
    logger.info(f"Approval request {request.id} sent to UI via WebSocket")
except Exception as e:
    logger.warning(f"WebSocket send failed: {e}. Will use console fallback.")
    request.use_console_fallback = True  # Flag for wait_for_approval_async

return request
```

Then update `wait_for_approval_async`:

```python
async def wait_for_approval_async(
    self,
    approval_id: str,
    timeout_seconds: int = 3600,
) -> SimpleApprovalRequest:
    with self._lock:
        request = WebSocketApprovalManager._pending.get(approval_id)

    if not request:
        raise ValueError(f"Approval {approval_id} not found")

    # If WebSocket failed, use console input
    if getattr(request, 'use_console_fallback', False):
        print("\n" + "="*60)
        print("⚠️ UI NOT AVAILABLE - USING CONSOLE INPUT")
        print("="*60)
        print(request.message)
        print(f"\nOptions: {', '.join(request.options)}")
        print("="*60)

        response = input(f"\nYour choice ({'/'.join(request.options)}): ").strip().lower()

        # Map console input to resolution
        if response in ['approve', 'approved', 'continue', 'y', 'yes']:
            request.resolution = 'approve'
        elif response in ['reject', 'rejected', 'abort', 'n', 'no']:
            request.resolution = 'reject'
        elif response in ['modify', 'modified']:
            request.resolution = 'modify'
        elif response in ['redo', 'retry']:
            request.resolution = 'redo'
        else:
            request.resolution = response  # Use as-is

        request.status = request.resolution
        request._event.set()
        return request

    # Wait for WebSocket response (existing code)
    start_time = time.time()
    poll_interval = 0.5

    while True:
        if request._event.is_set():
            return request

        elapsed = time.time() - start_time
        if elapsed >= timeout_seconds:
            raise TimeoutError(f"Approval timeout for {approval_id}")

        await asyncio.sleep(poll_interval)
```

**Benefits:**
- ✅ Workflow continues even without UI
- ✅ Can still get approvals via console
- ✅ Graceful degradation

**Drawbacks:**
- ❌ More complex
- ❌ Requires console access

---

### Solution C: Heartbeat + Retry

**Detect WebSocket alive before sending:**

```python
class WebSocketApprovalManager:
    def __init__(self, ws_send_event: Callable, run_id: str):
        self.ws_send_event = ws_send_event
        self.run_id = run_id
        self._websocket_alive = True
        self._last_heartbeat = time.time()

    def check_websocket_alive(self) -> bool:
        """Check if WebSocket is responsive."""
        try:
            # Send heartbeat event
            self.ws_send_event("heartbeat", {"timestamp": time.time()})
            self._last_heartbeat = time.time()
            self._websocket_alive = True
            return True
        except Exception as e:
            logger.warning(f"WebSocket heartbeat failed: {e}")
            self._websocket_alive = False
            return False

    def create_approval_request(self, ...):
        """Create approval with retry logic."""
        request = SimpleApprovalRequest(...)

        # Check WebSocket before sending
        if not self.check_websocket_alive():
            raise RuntimeError(
                "WebSocket connection dead - cannot send approval request. "
                "Please ensure UI is connected and WebSocket is healthy."
            )

        # Try sending with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.ws_send_event("approval_requested", {...})
                logger.info(f"Approval request sent (attempt {attempt + 1})")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    # Cleanup and fail
                    with self._lock:
                        WebSocketApprovalManager._pending.pop(request.id, None)
                    raise RuntimeError(
                        f"Failed to send approval after {max_retries} attempts: {e}"
                    )
                logger.warning(f"Send attempt {attempt + 1} failed, retrying...")
                time.sleep(0.5)

        return request
```

**Benefits:**
- ✅ Detects dead WebSocket early
- ✅ Retries temporary failures
- ✅ Clear error message if fails

**Drawbacks:**
- ❌ More overhead (heartbeat checks)
- ❌ Delays if retrying

---

## Recommended Approach

**Use Solution A + B combined:**

1. **Fail Fast by Default** - Don't hang on WebSocket failure
2. **Console Fallback Optional** - Configurable fallback mode
3. **Clear Error Messages** - Tell user what went wrong

```python
class WebSocketApprovalManager:
    def __init__(
        self,
        ws_send_event: Callable,
        run_id: str,
        use_console_fallback: bool = False  # NEW: opt-in fallback
    ):
        self.ws_send_event = ws_send_event
        self.run_id = run_id
        self.use_console_fallback = use_console_fallback

    def create_approval_request(self, ...) -> SimpleApprovalRequest:
        request = SimpleApprovalRequest(...)

        with self._lock:
            WebSocketApprovalManager._pending[request.id] = request

        # Try WebSocket
        websocket_success = False
        try:
            self.ws_send_event("approval_requested", {...})
            websocket_success = True
            logger.info(f"✓ Approval {request.id} sent to UI")
        except Exception as e:
            logger.error(f"✗ WebSocket send failed: {e}")

            if self.use_console_fallback:
                logger.warning("Will use console fallback")
                request.use_console = True  # Flag for later
            else:
                # Cleanup and fail fast
                with self._lock:
                    WebSocketApprovalManager._pending.pop(request.id, None)
                raise RuntimeError(
                    f"Cannot send approval to UI (WebSocket failed). "
                    f"Ensure UI is connected. Error: {e}"
                ) from e

        return request
```

---

## Frontend Check

Also verify the UI is properly handling the event:

### Check event listener exists
```typescript
// In websocket handler
socket.on("approval_requested", (data) => {
    console.log("Received approval request:", data);
    // Show approval UI
    showApprovalPanel(data);
});
```

### Check event name matches
Backend sends: `"approval_requested"`
Frontend listens for: Should be `"approval_requested"` (not "approval_request" or other variant)

---

## Testing

### Test 1: Normal Flow
```bash
# Start workflow with UI connected
# Should see approval in UI
```

### Test 2: WebSocket Down
```bash
# Disconnect UI mid-workflow
# Should get clear error (Solution A)
# OR fallback to console (Solution B)
```

### Test 3: Event Mismatch
```bash
# Check browser console: "Unknown event: approval_requested"
# Fix frontend event name
```

---

## Monitoring

Add logging to see what's happening:

```python
# In websocket_approval_manager.py:

logger.info(f"Creating approval {request.id}")
logger.info(f"WebSocket function: {self.ws_send_event}")
logger.info(f"Sending approval_requested event...")

try:
    self.ws_send_event("approval_requested", {...})
    logger.info(f"✓ Event sent successfully")
except Exception as e:
    logger.error(f"✗ Event send failed: {type(e).__name__}: {e}")
    logger.error(f"WebSocket state: {self.ws_send_event}")
    raise
```

---

## Quick Fix (Immediate)

If you need a quick fix right now:

```bash
# Edit websocket_approval_manager.py line 119-131
# Change from:
try:
    self.ws_send_event(...)
except Exception as e:
    logger.warning(f"Failed: {e}")

# To:
try:
    self.ws_send_event(...)
    logger.info("✓ Approval sent to UI")
except Exception as e:
    logger.error(f"✗ WebSocket send failed: {e}")
    with self._lock:
        WebSocketApprovalManager._pending.pop(request.id, None)
    raise RuntimeError(
        f"Cannot send approval to UI - WebSocket failed: {e}"
    ) from e
```

This will make the workflow **fail fast** instead of hanging.

---

## Status

**Issue:** WebSocket silent failure causing workflow hang
**Severity:** Critical (blocks workflow)
**Recommended Fix:** Solution A (fail fast) + optional console fallback
**Time to Fix:** 15-30 minutes
**Breaking Changes:** None (improves error handling)
