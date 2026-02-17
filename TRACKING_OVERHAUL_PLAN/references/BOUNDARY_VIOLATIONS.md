# Library/App Boundary Violations

## Complete Inventory

### Category 1: Reverse Imports (Library imports Backend)

| File | Line(s) | Import | Severity |
|------|---------|--------|----------|
| `cmbagent/execution/event_capture.py` | 556-561 | `from websocket_events import create_event_captured_event` | CRITICAL |
| `cmbagent/execution/event_capture.py` | 556-561 | `from websocket.events import send_ws_event` | CRITICAL |
| `cmbagent/retry/retry_context_manager.py` | 124-125 | `from backend...` (backend service import) | HIGH |
| `cmbagent/database/dag_executor.py` | ~185 | `from backend...` (backend execution) | HIGH |
| `cmbagent/database/state_machine.py` | ~215-245 | `from backend...` (backend state) | HIGH |

### Category 2: App Logic in Library Code

| File | Line(s) | Issue | Severity |
|------|---------|-------|----------|
| `cmbagent/callbacks.py` | 413-715 | `create_websocket_callbacks()` - entire function is app logic | CRITICAL |
| `cmbagent/callbacks.py` | 594-658 | `on_cost_update` does DB writes via `CostRepository` | HIGH |
| `cmbagent/callbacks.py` | 718-882 | `create_database_callbacks()` - entire function is app logic | HIGH |
| `cmbagent/callbacks.py` | 19 | Imports `sqlalchemy.orm.Session` | MEDIUM |

### Category 3: Stringly-Typed Shared State

| File | Line(s) | Issue | Severity |
|------|---------|-------|----------|
| `cmbagent/phases/execution_manager.py` | 155-164 | `_setup_database()` extracts `_db_session`, `_workflow_repo`, etc. from `shared_state` dict | HIGH |
| `cmbagent/phases/execution_manager.py` | 165-205 | `_setup_event_capture()` extracts `session_id` from `shared_state` | MEDIUM |

### Category 4: Library Creating App-Specific Artifacts

| File | Line(s) | Issue | Severity |
|------|---------|-------|----------|
| `cmbagent/phases/execution_manager.py` | 294-339 | Creates DAGNode records in database | HIGH |
| `cmbagent/phases/execution_manager.py` | 1073-1088 | Tracks files in work_dir (duplicate of DAGTracker) | MEDIUM |

## Resolution Plan

| Category | Resolution | Stage |
|----------|------------|-------|
| 1. Reverse imports | Remove imports, use callback/protocol pattern | Stage 0 |
| 2. App logic in library | Move to `backend/callbacks/app_callbacks.py` | Stage 0 |
| 3. Stringly-typed state | Replace with typed protocol `ExecutionContext` | Stage 1 |
| 4. Library creating app artifacts | Remove DAG creation from PhaseExecutionManager | Stage 1 |
