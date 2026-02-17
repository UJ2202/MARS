# Stage 0: Foundation - Bug Fixes + Callback Contract

## Objectives
1. Fix bugs that actively corrupt data or break concurrent sessions
2. Define the clean callback contract that all subsequent stages depend on
3. Establish the library/app boundary types
4. Zero behavioral changes to working HITL flow

---

## Implementation Tasks

### Task 0.1: Fix Model String Concatenation
**File**: `cmbagent/cmbagent.py:543`
```python
# BEFORE (BUG):
cost_dict["Model"][i] += model_name  # "gpt-4o" + "gpt-4o" = "gpt-4ogpt-4o"

# AFTER:
if model_name not in cost_dict["Model"][i]:
    cost_dict["Model"][i] = model_name
```
Also fix same bug in `cmbagent/managers/cost_manager.py:103`.

### Task 0.2: Move App Callbacks Out of Library
**File**: `cmbagent/callbacks.py`

Move `create_websocket_callbacks()` (lines 413-715) to new file `backend/callbacks/app_callbacks.py`.
Move `create_database_callbacks()` (lines 718-882) to same new file.

Library `callbacks.py` should ONLY contain:
- `WorkflowCallbacks` dataclass
- `StepInfo`, `PlanInfo`, `StepStatus` data classes
- `merge_callbacks()`, `create_null_callbacks()`, `create_print_callbacks()`

### Task 0.3: Fix Reverse Imports (Library → Backend)
Remove backend imports from:
- `cmbagent/execution/event_capture.py:556-561` - replace with optional callback parameter
- `cmbagent/retry/retry_context_manager.py:124-125`
- `cmbagent/database/dag_executor.py:~185`
- `cmbagent/database/state_machine.py:~215-245`

### Task 0.4: Remove DB Writes from Library Callbacks
**File**: `cmbagent/callbacks.py:594-658`
The `on_cost_update` closure directly imports `CostRepository` and writes to DB. Remove - DB writes belong in app layer only.

### Task 0.5: Define Typed Execution Context
**New file**: `cmbagent/phases/protocols.py`
```python
from typing import Protocol, Optional, Any, runtime_checkable

@runtime_checkable
class ExecutionContext(Protocol):
    """Type-safe execution context provided by the app layer."""
    run_id: str
    session_id: str
    work_dir: str
    callbacks: 'WorkflowCallbacks'
```
Replace stringly-typed `shared_state` dict in `execution_manager.py:155-164`.

---

## Cleanup Items
- Remove `create_websocket_callbacks()` from `cmbagent/callbacks.py` (moved to backend)
- Remove `create_database_callbacks()` from `cmbagent/callbacks.py` (moved to backend)
- Remove backend imports from 4 files in `cmbagent/`
- Remove `sqlalchemy.orm.Session` import from `cmbagent/callbacks.py:19`

## Verification
```bash
# No reverse imports
grep -rn "from backend\|import backend" cmbagent/ --include="*.py" | grep -v __pycache__
# Library imports standalone
python -c "from cmbagent.callbacks import WorkflowCallbacks, merge_callbacks"
```

## Files Modified
| File | Action |
|------|--------|
| `cmbagent/cmbagent.py` | Fix model concat (line 543) |
| `cmbagent/callbacks.py` | Remove app callbacks, clean imports |
| `cmbagent/execution/event_capture.py` | Remove backend imports |
| `cmbagent/retry/retry_context_manager.py` | Remove backend imports |
| `cmbagent/database/dag_executor.py` | Remove backend imports |
| `cmbagent/database/state_machine.py` | Remove backend imports |
| `cmbagent/phases/protocols.py` | NEW - typed protocols |
| `backend/callbacks/__init__.py` | NEW - app callback exports |
| `backend/callbacks/app_callbacks.py` | NEW - moved from library |
