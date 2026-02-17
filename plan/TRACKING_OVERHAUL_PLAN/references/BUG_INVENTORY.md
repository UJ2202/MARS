# Bug Inventory

## Critical Bugs

### BUG-001: Model String Concatenation
- **Severity**: Critical (corrupts cost data)
- **File**: `cmbagent/cmbagent.py:543`
- **Also in**: `cmbagent/managers/cost_manager.py:103`
- **Symptom**: Cost reports show model names like "gpt-4ogpt-4o" or "gpt-4ogpt-4ogpt-4o"
- **Root cause**: `cost_dict["Model"][i] += model_name` uses Python string concatenation
- **Fix**: Replace with assignment `cost_dict["Model"][i] = model_name` after checking if different
- **Stage**: 0

### BUG-002: Global Event Capture Singleton
- **Severity**: Critical (data corruption with concurrent sessions)
- **File**: `cmbagent/execution/event_capture.py:624-636`
- **Symptom**: Session A's AG2 hooks write events to Session B's EventCaptureManager
- **Root cause**: Module-level `_global_event_captor` variable, not session-scoped
- **Fix**: Replace with `contextvars.ContextVar`
- **Stage**: 0

### BUG-003: Dual WebSocket Emission
- **Severity**: High (phantom UI events, race conditions)
- **Files**: `backend/execution/dag_tracker.py:612-638` AND `cmbagent/callbacks.py:527-548`
- **Symptom**: Frontend receives duplicate `dag_node_status_changed` events
- **Root cause**: Both DAGTracker and callback functions emit the same event
- **Fix**: Only DAGTracker emits DAG events; callbacks emit workflow-level events
- **Stage**: 2

### BUG-004: Conflicting DAG Node IDs
- **Severity**: High (orphaned DB records)
- **Files**: `cmbagent/phases/execution_manager.py:322-337` vs `backend/execution/dag_tracker.py`
- **Symptom**: Database has UUID-based nodes (from PhaseExecutionManager) AND string-based nodes (from DAGTracker) for same run
- **Root cause**: Two independent systems creating DAG nodes
- **Fix**: Remove DAG creation from PhaseExecutionManager
- **Stage**: 1

## Design Issues

### DESIGN-001: Session Leak in Event Queries
- **Severity**: Medium (privacy/data isolation)
- **File**: `cmbagent/database/repository.py:587-600`
- **Issue**: `list_events_for_node(filter_by_session=False)` - defaults to cross-session reads
- **Fix**: Change default to `True`
- **Stage**: 3

### DESIGN-002: 70/30 Token Split Estimation
- **Severity**: Low (inaccurate token counts)
- **File**: `cmbagent/callbacks.py:622-624`
- **Issue**: Estimated prompt/completion token split stored as fact
- **Fix**: Use actual data from cost JSON files (which have real token counts)
- **Stage**: 2

### DESIGN-003: 8 Hardcoded Mode Branches
- **Severity**: Medium (maintenance burden)
- **File**: `backend/execution/dag_tracker.py:137-321`
- **Issue**: Adding a new mode requires adding a new method and elif branch
- **Fix**: Template-based factory pattern
- **Stage**: 2

### DESIGN-004: File Model Missing session_id
- **Severity**: Medium (can't filter files by session)
- **File**: `cmbagent/database/models.py:509-549`
- **Issue**: Every other model has `session_id` except File
- **Fix**: Add column + migration
- **Stage**: 3

## Dead Code

### DEAD-001: CostManager Class
- **Severity**: Low (code clutter)
- **File**: `cmbagent/managers/cost_manager.py`
- **Lines**: ~295
- **Issue**: Never instantiated by any workflow
- **Fix**: Delete file
- **Stage**: 1

### DEAD-002: callback_integration.py
- **Severity**: Low (code clutter)
- **File**: `cmbagent/execution/callback_integration.py`
- **Lines**: ~40
- **Issue**: Explicitly disabled with comment "disabled to avoid duplicate events"
- **Fix**: Delete file
- **Stage**: 1

### DEAD-003: build_dag_from_plan() regex parser
- **Severity**: Low (dead method)
- **File**: `backend/execution/dag_tracker.py:871-964`
- **Lines**: ~95
- **Issue**: Superseded by `add_step_nodes()` which takes structured data
- **Fix**: Delete methods
- **Stage**: 3
