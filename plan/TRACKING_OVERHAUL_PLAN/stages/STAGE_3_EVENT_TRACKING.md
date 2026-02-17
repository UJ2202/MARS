# Stage 3: Event Tracking Overhaul

## Objectives
1. Replace global event capture singleton with contextvars for session isolation
2. Fix thread-safety issues in EventCaptureManager
3. Complete AG2 monkey patches (code executor is currently a stub)
4. Remove backend imports from event capture module
5. Clean up disabled callback_integration.py

## Dependencies
- Stage 0 (boundary enforcement, reverse imports removed)

---

## Current State

### Global Singleton Problem
**File**: `cmbagent/execution/event_capture.py:624-636`
```python
_global_event_captor: Optional[EventCaptureManager] = None  # Module-level!

def get_event_captor() -> Optional[EventCaptureManager]:
    return _global_event_captor  # Session A's hooks write to Session B's captor
```

### Thread-Safety Issues
**File**: `cmbagent/execution/event_capture.py`
- `execution_order` counter incremented without lock (line 537)
- `event_stack` is a plain list shared across threads (line 73)
- `buffer_lock` exists but only protects buffer flush, not ordering

### AG2 Hook Gaps
**File**: `cmbagent/execution/ag2_hooks.py:134-149`
```python
# Code executor patch is STUB ONLY:
def patch_code_executor(executor_class):
    """Monitor code execution. Currently placeholder."""
    pass  # Not implemented!
```

### Dead Code
**File**: `cmbagent/execution/callback_integration.py` (~40 lines)
Explicitly disabled with comment "disabled to avoid duplicate events".

### Reverse Backend Imports
**File**: `cmbagent/execution/event_capture.py:556-561`
```python
backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))
from websocket_events import create_event_captured_event
from websocket.events import send_ws_event
```

---

## Implementation Tasks

### Task 3.1: Replace Global Singleton with contextvars

**File**: `cmbagent/execution/event_capture.py`

```python
# REPLACE lines 624-636:
import contextvars

_event_captor_var: contextvars.ContextVar[Optional['EventCaptureManager']] = (
    contextvars.ContextVar('event_captor', default=None)
)

def get_event_captor() -> Optional['EventCaptureManager']:
    """Get the event captor for the current execution context."""
    return _event_captor_var.get()

def set_event_captor(captor: Optional['EventCaptureManager']):
    """Set the event captor for the current execution context.

    Uses contextvars to isolate per-session/per-branch.
    When using ThreadPoolExecutor, use contextvars.copy_context()
    to propagate the captor to worker threads.
    """
    _event_captor_var.set(captor)
```

### Task 3.2: Thread-Safe EventCaptureManager

**File**: `cmbagent/execution/event_capture.py`

Fix three thread-safety issues:

```python
import threading

class EventCaptureManager:
    def __init__(self, db_session, run_id, session_id, enabled=True,
                 buffer_size=50, ws_emit_callback=None):
        self.db_session = db_session
        self.run_id = run_id
        self.session_id = session_id
        self.enabled = enabled
        self.buffer_size = buffer_size
        self.ws_emit_callback = ws_emit_callback  # Optional, replaces backend import

        self._lock = threading.Lock()
        self._order_counter = 0
        self._event_stack_local = threading.local()  # Thread-local stacks
        self._buffer = []

    @property
    def event_stack(self):
        """Thread-local event stack."""
        if not hasattr(self._event_stack_local, 'stack'):
            self._event_stack_local.stack = []
        return self._event_stack_local.stack

    def _next_order(self) -> int:
        """Thread-safe execution order counter."""
        with self._lock:
            self._order_counter += 1
            return self._order_counter

    def _buffer_event(self, event):
        """Thread-safe event buffering."""
        with self._lock:
            self._buffer.append(event)
            if len(self._buffer) >= self.buffer_size:
                self._flush_buffer_locked()

    def _flush_buffer_locked(self):
        """Flush buffer to DB (must hold self._lock)."""
        if not self.db_session or not self._buffer:
            return
        try:
            for event in self._buffer:
                self.db_session.add(event)
            self.db_session.commit()
            self._buffer.clear()
        except Exception as e:
            logger.error("event_buffer_flush_failed", error=str(e))
            self.db_session.rollback()
            self._buffer.clear()
```

### Task 3.3: Remove Backend Imports

**File**: `cmbagent/execution/event_capture.py`

Remove lines 550-583 (the entire backend path manipulation and import block).

Replace WS emission with optional callback:
```python
# In capture methods, replace:
#   send_ws_event(websocket, event_type, event_data)
# With:
if self.ws_emit_callback:
    try:
        self.ws_emit_callback(event_type, event_data)
    except Exception:
        pass  # WS emission should never block event capture
```

### Task 3.4: Complete Code Executor Patch

**File**: `cmbagent/execution/ag2_hooks.py:134-149`

Implement the stub:
```python
def patch_code_executor(executor_class):
    """Monitor code execution via AG2's code executors."""
    original_execute = executor_class.execute_code_blocks

    def patched_execute(self, code_blocks, *args, **kwargs):
        captor = get_event_captor()
        if captor:
            for block in code_blocks:
                captor.capture_code_execution_start(
                    agent_name=getattr(self, '_agent_name', 'executor'),
                    code=block.code if hasattr(block, 'code') else str(block),
                    language=block.language if hasattr(block, 'language') else 'python',
                )

        result = original_execute(self, code_blocks, *args, **kwargs)

        if captor:
            captor.capture_code_execution_end(
                agent_name=getattr(self, '_agent_name', 'executor'),
                result=str(result)[:2000] if result else None,
                success=True,
            )

        return result

    executor_class.execute_code_blocks = patched_execute
```

### Task 3.5: Delete callback_integration.py

**File**: `cmbagent/execution/callback_integration.py` - DELETE entirely (~40 lines)

Verify no imports:
```bash
grep -rn "callback_integration" cmbagent/ --include="*.py" | grep -v __pycache__
```

### Task 3.6: Context Propagation in ThreadPoolExecutor

**File**: `backend/execution/task_executor.py`

When spawning worker threads, propagate contextvars:
```python
import contextvars

# In run_cmbagent():
ctx = contextvars.copy_context()

def run_in_context():
    return ctx.run(run_cmbagent_inner)

with concurrent.futures.ThreadPoolExecutor() as executor:
    future = executor.submit(run_in_context)
```

This ensures the event captor set in the main context is available in the worker thread.

---

## Cleanup Items
| Item | Lines Removed |
|------|--------------|
| `callback_integration.py` | ~40 (DELETE) |
| Backend imports in event_capture | ~30 |
| Global singleton code | ~12 |
| **Total** | **~82** |

## Verification
```bash
# contextvars isolation
python -c "
import contextvars
from cmbagent.execution.event_capture import get_event_captor, set_event_captor
set_event_captor('main')
ctx = contextvars.copy_context()
ctx.run(lambda: (set_event_captor('branch'), None))
assert get_event_captor() == 'main'
print('OK: isolation works')
"

# Thread-safety
python -c "
import threading
from cmbagent.execution.event_capture import EventCaptureManager
m = EventCaptureManager(None, 'r', 's', enabled=False)
orders = []
lock = threading.Lock()
def go():
    for _ in range(100):
        o = m._next_order()
        with lock: orders.append(o)
threads = [threading.Thread(target=go) for _ in range(10)]
[t.start() for t in threads]; [t.join() for t in threads]
assert len(set(orders)) == 1000
print('OK: thread-safe')
"

# No backend imports
grep -c "from backend\|from websocket" cmbagent/execution/event_capture.py  # 0

# callback_integration gone
test ! -f cmbagent/execution/callback_integration.py
```

## Files Modified
| File | Action |
|------|--------|
| `cmbagent/execution/event_capture.py` | contextvars, thread-safety, remove backend imports |
| `cmbagent/execution/ag2_hooks.py` | Implement code executor patch |
| `cmbagent/execution/callback_integration.py` | DELETE |
| `backend/execution/task_executor.py` | Context propagation in ThreadPool |
