# Stage 7: Robustness & Dead Code Cleanup

## Objectives
1. Add error-resilient callback invocation (circuit breaker pattern)
2. Fix DB transaction safety (savepoints, batch commits)
3. Add WS emission retry for transient failures
4. Fix session leak in repository query defaults
5. Add graceful degradation throughout tracking pipeline
6. Remove any remaining dead code and stale patterns

## Dependencies
- Stages 0-6 complete (single path per concern established)

---

## Implementation Tasks

### Task 7.1: Circuit Breaker for Callbacks

**File**: `cmbagent/callbacks.py`

```python
class WorkflowCallbacks:
    _error_count: int = 0
    _max_errors: int = 50

    def _safe_invoke(self, name, callback, *args, **kwargs):
        if self._error_count >= self._max_errors:
            return None  # Circuit breaker open
        if callback is None:
            return None
        try:
            return callback(*args, **kwargs)
        except Exception as e:
            self._error_count += 1
            logger.error("callback_failed name=%s errors=%d/%d",
                         name, self._error_count, self._max_errors, exc_info=True)
            if self._error_count >= self._max_errors:
                logger.critical("callback_circuit_breaker_open")
            return None
```

Update all `invoke_*` methods to use `_safe_invoke()`.

### Task 7.2: DB Transaction Safety

**File**: `backend/execution/dag_tracker.py`

Use savepoints for atomic operations:
```python
def _persist_dag_nodes_to_db(self):
    if not self.db_session:
        return
    try:
        with self.db_session.begin_nested():  # Savepoint
            for node in self.nodes:
                # ... create/update DAGNode ...
        self.db_session.commit()
    except Exception as e:
        logger.error("dag_persist_failed", error=str(e))
        try:
            self.db_session.rollback()
        except Exception:
            pass
```

### Task 7.3: WS Emission Retry

**File**: `backend/websocket/events.py`

```python
async def send_ws_event_with_retry(websocket, event_type, data,
                                     run_id=None, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            return await send_ws_event(websocket, event_type, data, run_id=run_id)
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (attempt + 1))
            else:
                logger.error("ws_event_failed event=%s", event_type)
                return False
```

### Task 7.4: Fix Session Leak in Repository

**File**: `cmbagent/database/repository.py`

```python
# BEFORE:
def list_events_for_node(self, node_id, filter_by_session=False):

# AFTER:
def list_events_for_node(self, node_id, filter_by_session=True):
```

Audit all repository methods for correct session filtering defaults.

### Task 7.5: Graceful Degradation Pattern

All tracking operations must follow this pattern:
```python
def track_something(self, ...):
    try:
        # Tracking logic
    except Exception as e:
        logger.warning("tracking_degraded component=%s", self.__class__.__name__)
        # NEVER propagate - tracking failure must not stop workflow
```

Apply to:
- `DAGTracker.update_node_status()`
- `DAGTracker.track_files_in_work_dir()`
- `EventCaptureManager.capture_*()`
- `CostCollector.collect_from_callback()`
- All callback invocations

### Task 7.6: Structured Logging Consistency

Ensure all tracking components log with consistent fields:
```python
logger.info("event_name", run_id=run_id, session_id=session_id,
            node_id=node_id, phase=phase, duration_ms=duration)
```

### Task 7.7: Remove Remaining Dead Code Sweep

Final audit:
```bash
# Unused imports
grep -rn "^from\|^import" cmbagent/ backend/ --include="*.py" | grep -v __pycache__
# Commented-out code blocks
grep -rn "^# " cmbagent/ backend/ --include="*.py" | grep -v __pycache__ | grep -v "# TODO\|# NOTE"
# Unused functions/classes
# (manual review of each file touched in prior stages)
```

---

## Verification
```bash
# Circuit breaker test
python -c "
from cmbagent.callbacks import WorkflowCallbacks
cb = WorkflowCallbacks(on_step_start=lambda s: 1/0)
cb._max_errors = 3
for _ in range(10): cb._safe_invoke('test', cb.on_step_start, None)
assert cb._error_count == 3
print('OK: circuit breaker works')
"

# Session isolation
grep -n "filter_by_session=False" cmbagent/database/repository.py  # Should be 0
```

## Files Modified
| File | Action |
|------|--------|
| `cmbagent/callbacks.py` | Circuit breaker, safe_invoke |
| `backend/execution/dag_tracker.py` | Savepoints, batch commits |
| `backend/websocket/events.py` | WS retry wrapper |
| `cmbagent/database/repository.py` | Fix session leak defaults |
| Various | Structured logging, graceful degradation |
