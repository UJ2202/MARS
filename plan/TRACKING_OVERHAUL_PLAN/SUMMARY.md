# Analysis Summary

## Current System Architecture

The tracking system has **two parallel infrastructure stacks** doing overlapping work:

### Stack 1: Library-side (cmbagent/)
- `PhaseExecutionManager` (phases/execution_manager.py) - creates DAG nodes, logs events, tracks files
- `EventCaptureManager` (execution/event_capture.py) - captures AG2 events via monkey patches
- `WorkflowCallbacks` (callbacks.py) - callback contract, BUT also contains app logic
- `CostManager` (managers/cost_manager.py) - **DEAD CODE**, never instantiated
- `display_cost()` in cmbagent.py - writes cost JSON files (source of truth)

### Stack 2: App-side (backend/)
- `DAGTracker` (execution/dag_tracker.py) - DAG state owner, WS emission, DB persistence
- `StreamCapture` (execution/stream_capture.py) - stdout regex parsing for progress detection
- `task_executor.py` - bridge that wires callbacks to DAGTracker, creates duplicate event tracking

## Key Finding: The Working Pattern

The **HITL workflow** works flawlessly because it has ONE clean path:

```
Phase (library)
  → invokes callbacks
    → task_executor bridge callbacks
      → DAGTracker methods
        → DB persistence + WS emission
```

StreamCapture intentionally **SKIPS** auto-complete for HITL (stream_capture.py:490-493).
This proves the callback path alone is sufficient.

## Root Cause of Bugs

Non-HITL modes have **THREE competing paths**:
1. Callbacks → task_executor → DAGTracker (correct path)
2. StreamCapture regex → DAGTracker (fragile duplicate)
3. PhaseExecutionManager → direct DB (conflicting UUID-based nodes)

These create:
- Dual WS emission (both callbacks and DAGTracker emit `dag_node_status_changed`)
- Conflicting DAG nodes (UUID from PhaseExecutionManager vs string IDs from DAGTracker)
- Race conditions between stdout detection and callback invocation

## Bug Inventory

### Critical Bugs
1. **Model string concatenation** (cmbagent.py:543): `cost_dict["Model"][i] += model_name` produces "gpt-4ogpt-4o"
2. **Global event capture singleton** (event_capture.py:625-636): Concurrent sessions overwrite each other's captor
3. **Dual WS emission**: DAGTracker (dag_tracker.py:612-638) AND callbacks (callbacks.py:527-548) both emit `dag_node_status_changed`
4. **Conflicting DAG nodes**: PhaseExecutionManager creates UUID nodes (execution_manager.py:322-337), DAGTracker uses string IDs like "step_1"

### Design Issues
5. **Library/app boundary violations**: Library imports from backend in 3 places, library does WebSocket emission and DB writes in callbacks
6. **Stringly-typed dependency injection**: DB session passed via `shared_state` dict (execution_manager.py:155-164)
7. **Session leak in event queries**: `filter_by_session=False` default in repository.py
8. **70/30 token split estimation**: Cost stored with fake prompt/completion split (callbacks.py:622-624)
9. **Dead code**: CostManager class (~200 lines), callback_integration.py (40 lines, disabled)
10. **8 hardcoded mode branches**: DAGTracker.create_dag_for_mode (dag_tracker.py:137-321)

## Library/App Boundary Violations

### Reverse Imports (Library → Backend)
- `cmbagent/execution/event_capture.py:556-561` - imports `websocket_events` and `websocket.events` from backend
- `cmbagent/retry/retry_context_manager.py:124-125` - imports from backend
- `cmbagent/database/dag_executor.py:~185` - imports from backend
- `cmbagent/database/state_machine.py:~215-245` - imports from backend

### App Logic in Library
- `callbacks.py:594-658` - `create_websocket_callbacks.on_cost_update()` does DB writes via `CostRepository`
- `callbacks.py:413-715` - `create_websocket_callbacks()` contains WebSocket-specific logic in library
- `execution_manager.py:155-164` - DB session extracted from implicit dict, no type safety

## What Must Be Preserved

1. **DAGTracker as DAG state owner** - self.nodes, self.edges, self.node_statuses
2. **Callback-driven architecture** - WorkflowCallbacks as the contract
3. **Cost JSON file writing** - display_cost() in cmbagent.py
4. **AG2 monkey patches** - for fine-grained event capture
5. **Branching data model** - Branch, WorkflowRun.branch_parent_id
6. **File tracking in DAGTracker** - track_files_in_work_dir()

## What Must Change

1. **Remove `create_websocket_callbacks()` from library** → move to backend
2. **Remove DAG creation from PhaseExecutionManager** → let callbacks → DAGTracker handle it
3. **Replace global event capture singleton** → use contextvars
4. **Strip StreamCapture to stdout relay only** → remove all regex detection
5. **Make DAGTracker workflow-agnostic** → remove 8 mode branches, use factory pattern
6. **Fix cost tracking** → read JSON files directly, remove stdout parsing
7. **Delete dead code** → CostManager class, callback_integration.py
8. **Type-safe dependency injection** → replace shared_state dict with typed protocol
