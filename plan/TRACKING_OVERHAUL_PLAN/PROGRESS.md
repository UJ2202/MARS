# Implementation Progress

## Status: ALL STAGES COMPLETE

| Stage | Name | Status | Tasks | Completed | Notes |
|-------|------|--------|-------|-----------|-------|
| 0 | Foundation | **COMPLETE** | 5 | 5/5 | All verified |
| 1 | DAG Overhaul | **COMPLETE** | 5 | 5/5 | All tasks done |
| 2 | Cost Tracking | **COMPLETE** | 6 | 6/6 | All tasks done |
| 3 | Event Tracking | **COMPLETE** | 6 | 6/6 | All tasks done |
| 4 | File Tracking | **COMPLETE** | 6 | 6/6 | All tasks done |
| 5 | Phase Migration | **COMPLETE** | 6 | 6/6 | All tasks done |
| 6 | Workflow Migration | **COMPLETE** | 5 | 5/5 | All tasks done |
| 7 | Robustness | **COMPLETE** | 7 | 7/7 | All tasks done |
| 8 | Branching | **COMPLETE** | 5 | 5/5 | All tasks done |
| 9 | Sample Workflow | **COMPLETE** | 4 | 4/4 | All tasks done |

**Total tasks**: 55
**Total completed**: 55/55

---

## Stage 0: Foundation — COMPLETE
- [x] 0.1: Fix model string concatenation (cmbagent.py:543, cost_manager.py:103)
  - Changed `cost_dict["Model"][i] += model_name` to guarded assignment
  - Prevents "gpt-4ogpt-4o" concatenation bug
- [x] 0.2: Move create_websocket_callbacks & create_database_callbacks to backend/callbacks/
  - Created `backend/callbacks/__init__.py`, `websocket_callbacks.py`, `database_callbacks.py`
  - Removed both factory functions from `cmbagent/callbacks.py`
  - Removed `sqlalchemy.orm.Session` import from library callbacks
  - Updated `cmbagent/__init__.py` exports
  - Updated `backend/execution/task_executor.py` import path
- [x] 0.3: Fix reverse imports (library → backend) in 4 files
  - `cmbagent/execution/event_capture.py` — replaced sys.path hack + backend imports with `emit_event_callback` param
  - `cmbagent/retry/retry_context_manager.py` — replaced backend.websocket_events/event_queue with `emit_event_callback` param
  - `cmbagent/database/dag_executor.py` — replaced backend imports with `emit_event_callback` param
  - `cmbagent/database/state_machine.py` — replaced backend imports with `emit_ws_callback` param; removed dead `_get_workflow_event_type` and `_get_step_event_type` methods
- [x] 0.4: Remove DB writes from library callbacks
  - Resolved by 0.2: `on_cost_update` DB writes now live in `backend/callbacks/websocket_callbacks.py` (app layer)
- [x] 0.5: Define typed ExecutionContext protocol
  - Created `cmbagent/phases/protocols.py` with `ExecutionContext` protocol

### Stage 0 Verification
- `grep -rn "from backend|import backend" cmbagent/ --include="*.py"` → **0 matches**
- `python -c "from cmbagent.callbacks import WorkflowCallbacks, merge_callbacks"` → **passes**
- `python -c "from backend.callbacks import create_websocket_callbacks, create_database_callbacks"` → **passes**
- `python -c "from cmbagent.phases.protocols import ExecutionContext"` → **passes**

### Files Modified (Stage 0)
| File | Action |
|------|--------|
| `cmbagent/cmbagent.py` | Fixed model concat bug (line 543) |
| `cmbagent/managers/cost_manager.py` | Fixed model concat bug (line 103) |
| `cmbagent/callbacks.py` | Removed app callbacks, cleaned imports |
| `cmbagent/__init__.py` | Removed app callback exports |
| `cmbagent/execution/event_capture.py` | Replaced backend imports with callback param |
| `cmbagent/retry/retry_context_manager.py` | Replaced backend imports with callback param |
| `cmbagent/database/dag_executor.py` | Replaced backend imports with callback param |
| `cmbagent/database/state_machine.py` | Replaced backend imports with callback param, removed dead methods |
| `cmbagent/phases/protocols.py` | **NEW** — typed ExecutionContext protocol |
| `backend/callbacks/__init__.py` | **NEW** — app callback exports |
| `backend/callbacks/websocket_callbacks.py` | **NEW** — moved from library |
| `backend/callbacks/database_callbacks.py` | **NEW** — moved from library |
| `backend/execution/task_executor.py` | Updated import path for create_websocket_callbacks |

## Stage 1: DAG Overhaul — COMPLETE
- [x] 1.1: Template-based DAG factory (replace 8 mode branches)
  - Added `DAG_TEMPLATES` dict (plan-execute, fixed-pipeline, three-stage-pipeline)
  - Added `MODE_TO_TEMPLATE` mapping for all 7 modes
  - `create_dag_for_mode()` now does template lookup + dynamic overrides
  - Added `_create_from_template()` method for node/edge construction
  - Deleted 7 individual `_create_*_dag()` methods (~160 lines removed)
- [x] 1.2: Remove DAG creation from PhaseExecutionManager
  - Removed `_dag_repo`, `_current_dag_node_id`, `_step_dag_node_ids` attributes
  - Removed `enable_dag` from `PhaseExecutionConfig`
  - Removed DAG blocks from `start()`, `complete()`, `fail()`
  - Removed DAG blocks from `start_step()`, `complete_step()`, `fail_step()`
  - Removed `update_current_node_metadata()`, `add_plan_step_nodes()`, `create_redo_branch()`, `record_sub_agent_call()` methods
  - Updated `_update_event_capture_context` to use step_id instead of DAG node IDs
  - Updated `_log_event` to pass `node_id=None`
  - Removed callers in `planning.py`, `hitl_planning.py`, `copilot_phase.py`, `hitl_control.py`
- [x] 1.3: Remove duplicate WS emission from app callbacks
  - Made `on_planning_start`, `on_planning_complete`, `on_step_start`, `on_step_complete`, `on_step_failed`, `on_workflow_complete` into no-ops
  - DAGTracker handles all `dag_node_status_changed` and `dag_updated` emissions
  - Kept non-DAG callbacks: `workflow_failed`, `cost_update`, `agent_message`, `code_execution`, `tool_call`, `phase_change`
- [x] 1.4: Delete dead DAG methods
  - Replaced `build_dag_from_plan()` with thin wrapper delegating to `add_step_nodes()` (backwards compat)
  - Deleted `_build_inmemory_dag_from_plan()` (~30 lines)
  - Deleted 7 `_create_*_dag()` methods (replaced by templates in 1.1)
- [x] 1.5: DAGTracker DB session injection
  - Added `db_session` and `session_id` params to `__init__`
  - Extracted `_init_database()` for from-scratch DB setup
  - Extracted `_setup_repos()` for repository initialization (used by both paths)
  - Removed `dag_builder` and `dag_visualizer` attributes (only used by deleted methods)

### Stage 1 Verification
- `grep -rn "_current_dag_node_id\|_step_dag_node_ids\|add_plan_step_nodes\|create_redo_branch\|update_current_node_metadata\|record_sub_agent_call" cmbagent/ --include="*.py"` → **0 matches**
- `grep -rn "_dag_repo" cmbagent/ --include="*.py"` → **0 matches**
- `grep -rn "enable_dag[^_]" cmbagent/ --include="*.py"` → **0 matches**

### Files Modified (Stage 1)
| File | Action |
|------|--------|
| `backend/execution/dag_tracker.py` | Template system, DB injection, dead method removal |
| `cmbagent/phases/execution_manager.py` | Removed all DAG code (~220 lines), simplified config |
| `cmbagent/phases/planning.py` | Removed `add_plan_step_nodes` + `update_current_node_metadata` calls |
| `cmbagent/phases/hitl_planning.py` | Removed `add_plan_step_nodes` + `update_current_node_metadata` calls |
| `cmbagent/phases/copilot_phase.py` | Removed `add_plan_step_nodes` + `update_current_node_metadata` calls |
| `cmbagent/phases/hitl_control.py` | Removed `create_redo_branch` call |
| `backend/callbacks/websocket_callbacks.py` | DAG callbacks made no-ops (~90 lines removed) |

## Stage 2: Cost Tracking — COMPLETE
- [x] 2.1: Create CostCollector (backend/execution/cost_collector.py)
  - JSON-based cost collection reads actual token counts from cost report files
  - `collect_from_callback()` — processes cost data from on_cost_update callback (idempotent via `_processed_files`)
  - `collect_from_work_dir()` — scans work_dir/cost/ for unprocessed JSON files
  - `_persist_records()` — saves to DB via existing `CostRepository.record_cost()`
  - `_emit_ws_events()` — emits `cost_update` WS events with real prompt/completion token counts
- [x] 2.2: Add cost callback invocation in display_cost()
  - After JSON write in `cmbagent.py:display_cost()`, invokes `_callbacks.invoke_cost_update()` with:
    - `cost_json_path`: path to written JSON file
    - `total_cost`, `total_tokens`: aggregated from DataFrame
    - `records`: full cost data array
  - Uses `hasattr(self, '_callbacks')` pattern — backward compatible, no constructor change needed
- [x] 2.3: Wire CostCollector in task_executor + set _callbacks in phases
  - Created `CostCollector` instance in `task_executor.py` after DAGTracker setup (uses `dag_tracker.db_session`)
  - Added `on_cost_update_tracking()` callback that routes to `cost_collector.collect_from_callback()`
  - Included in `event_tracking_callbacks` WorkflowCallbacks
  - Set `cmbagent._callbacks = context.callbacks` in 6 phases after CMBAgent creation:
    - `planning.py`, `control.py`, `hitl_control.py`, `hitl_planning.py`, `idea_generation.py`, `one_shot.py`
- [x] 2.4: Remove cost detection from StreamCapture
  - Deleted `_detect_cost_updates()` method (~8 lines)
  - Deleted `_parse_cost_report()` method (~80 lines) — no more stdout parsing, DB writes, or WS emission from StreamCapture
  - Removed `await self._detect_cost_updates(text)` call from `write()`
  - Removed `self.total_cost` and `self.last_cost_report_time` instance variables
- [x] 2.5: Delete dead CostManager class
  - Deleted `cmbagent/managers/cost_manager.py` (~296 lines)
  - Removed `CostManager` import and export from `cmbagent/managers/__init__.py`
  - Verified no other imports of CostManager exist in codebase
- [x] 2.6: Remove 70/30 token estimation
  - Replaced `on_cost_update()` in `backend/callbacks/websocket_callbacks.py` with no-op
  - Removed ~80 lines of DB writes with `int(total_tokens * 0.7)`/`int(total_tokens * 0.3)` estimation
  - CostCollector now handles all cost DB persistence with actual token counts from JSON

### Stage 2 Verification
- `test ! -f cmbagent/managers/cost_manager.py` → **PASS** (file deleted)
- `grep -c "_detect_cost\|_parse_cost\|total_cost" backend/execution/stream_capture.py` → **0 matches**
- `grep -c "0\.7\|0\.3\|estimated" backend/callbacks/websocket_callbacks.py` → **0 matches**
- `CostCollector` instantiation → **PASS** (all methods present)

### Files Modified (Stage 2)
| File | Action |
|------|--------|
| `backend/execution/cost_collector.py` | **NEW** — JSON-based cost collection (~110 lines) |
| `backend/execution/stream_capture.py` | Removed cost detection (~90 lines deleted) |
| `backend/execution/task_executor.py` | CostCollector creation + cost callback wiring |
| `backend/callbacks/websocket_callbacks.py` | `on_cost_update` made no-op (~80 lines removed) |
| `cmbagent/cmbagent.py` | Added callback invocation in `display_cost()` |
| `cmbagent/managers/cost_manager.py` | **DELETED** (~296 lines) |
| `cmbagent/managers/__init__.py` | Removed CostManager import/export |
| `cmbagent/phases/planning.py` | Set `cmbagent._callbacks = context.callbacks` |
| `cmbagent/phases/control.py` | Set `cmbagent._callbacks = context.callbacks` |
| `cmbagent/phases/hitl_control.py` | Set `cmbagent._callbacks = context.callbacks` |
| `cmbagent/phases/hitl_planning.py` | Set `cmbagent._callbacks = context.callbacks` |
| `cmbagent/phases/idea_generation.py` | Set `cmbagent._callbacks = context.callbacks` |
| `cmbagent/phases/one_shot.py` | Set `cmbagent._callbacks = context.callbacks` |

## Stage 3: Event Tracking — COMPLETE
- [x] 3.1: Replace global singleton with contextvars
  - Already completed in Stage 0: `_event_captor_var` ContextVar with `get_event_captor()`/`set_event_captor()`
  - Lines 619-636 of `event_capture.py` use `contextvars.ContextVar` (not module-level global)
  - Verified: isolation between contexts works correctly
- [x] 3.2: Thread-safe EventCaptureManager (lock, thread-local stacks)
  - Already had `_lock`, `_order_counter`, `_event_stack_local` (threading.local) from Stage 0
  - Fixed bug: `self.buffer_lock` → `self._lock` in `_create_event()` (line 538)
  - Fixed bug: `self.execution_order` → `self._order_counter` in `get_performance_stats()` (line 603)
  - Verified: 10 threads x 100 orders = 1000 unique values (no duplicates)
- [x] 3.3: Remove backend imports from event_capture.py
  - Already completed in Stage 0: `emit_event_callback` param replaced sys.path hacks and backend imports
  - Verified: 0 matches for `from backend` or `from websocket` in event_capture.py
- [x] 3.4: Complete code executor AG2 patch
  - Implemented `patch_code_executor()` in `ag2_hooks.py` (was a stub)
  - Patches `LocalCommandLineCodeExecutor.execute_code_blocks`
  - Captures per-block start events and combined result event with exit_code + duration_ms
  - Uses `capture_code_execution()` from EventCaptureManager
- [x] 3.5: Delete callback_integration.py
  - Deleted `cmbagent/execution/callback_integration.py` (~40 lines)
  - Removed import and `__all__` entry from `cmbagent/execution/__init__.py`
  - Verified: file no longer exists, no remaining imports
- [x] 3.6: Context propagation in ThreadPoolExecutor
  - Added `import contextvars` to `backend/execution/task_executor.py`
  - Changed `executor.submit(run_cmbagent)` → `executor.submit(ctx.run, run_cmbagent)`
  - `ctx = contextvars.copy_context()` copies event captor to worker thread

### Stage 3 Verification
- `python -c "import contextvars; from cmbagent.execution.event_capture import get_event_captor, set_event_captor; set_event_captor('main'); ctx = contextvars.copy_context(); ctx.run(lambda: (set_event_captor('branch'), None)); assert get_event_captor() == 'main'; print('OK')"` → **passes**
- Thread-safety test (10 threads × 100 orders = 1000 unique) → **passes**
- `grep -c "from backend\|from websocket" cmbagent/execution/event_capture.py` → **0 matches**
- `test ! -f cmbagent/execution/callback_integration.py` → **passes**

### Files Modified (Stage 3)
| File | Action |
|------|--------|
| `cmbagent/execution/event_capture.py` | Fixed `buffer_lock` → `_lock`, `execution_order` → `_order_counter` |
| `cmbagent/execution/ag2_hooks.py` | Implemented code executor patch (was stub) |
| `cmbagent/execution/callback_integration.py` | **DELETED** (~40 lines) |
| `cmbagent/execution/__init__.py` | Removed callback_integration import and export |
| `backend/execution/task_executor.py` | Added contextvars propagation to ThreadPoolExecutor |

## Stage 4: File Tracking — COMPLETE
- [x] 4.1: Add session_id to File model + migration
  - Added `session_id` column to `File` model with FK to `sessions.id` (CASCADE delete)
  - Added `session` relationship on File, back-reference `files` on Session
  - Added `idx_files_session` index
  - Created migration `f6a7b8c9d0e1_add_session_id_to_files.py`
- [x] 4.2: Create FileRepository with deduplication
  - Created `cmbagent/database/file_repository.py` (~120 lines)
  - `register_file()` with deduplication by `(run_id, file_path)` — updates metadata on existing records
  - Auto-computes `content_hash` (SHA-256) and `size_bytes` for files < 50 MB
  - `_classify_priority()` for automatic priority assignment
  - `list_files()` with optional `file_type` and `phase` filters
- [x] 4.3: Update DAGTracker to use FileRepository
  - Replaced raw `File()` creation + `db_session.add()` in `track_files_in_work_dir()` with `FileRepository.register_file()`
  - Added `generating_agent` and `workflow_phase` parameters for explicit attribution
  - Extracted `_classify_file_type()` as static method for reuse
  - Deduplication handled automatically by FileRepository
- [x] 4.4: Consolidate FileRegistry into FileRepository
  - Added deprecation notice to `cmbagent/execution/file_registry.py`
  - FileRepository is now the canonical DB-backed file tracking system
  - FileRegistry kept for backward compatibility with `output_collector` and `tracked_code_executor` (to be removed in Stage 6)
- [x] 4.5: Explicit phase attribution in task_executor
  - `on_planning_complete_tracking()` now passes `workflow_phase="planning"` explicitly
  - `on_step_complete_tracking()` now passes `workflow_phase="control"` and `generating_agent` from step_info
  - No more path-based guessing for phase attribution at the callback level
- [x] 4.6: Remove PhaseExecutionManager file tracking
  - Removed `self.files_created` list from `PhaseExecutionManager.__init__()`
  - Removed `_track_output_files()` method (work_dir scan)
  - Removed `track_file()` method
  - Removed file tracking from `complete()` method
  - Removed all `manager.track_file()` calls from phases:
    - `planning.py` (1 call)
    - `control.py` (2 calls)
    - `hitl_control.py` (3 calls)
    - `hitl_planning.py` (2 calls)

### Stage 4 Verification
- `grep -rn "track_file\|files_created\|_track_output" cmbagent/phases/ --include="*.py"` → **0 matches**
- `python -c "from cmbagent.database.file_repository import FileRepository"` → **passes**
- `python -c "from cmbagent.database.models import File; assert hasattr(File, 'session_id')"` → **passes**

### Files Modified (Stage 4)
| File | Action |
|------|--------|
| `cmbagent/database/models.py` | Added `session_id` column + relationship on File and Session |
| `cmbagent/database/file_repository.py` | **NEW** — FileRepository with deduplication (~120 lines) |
| `cmbagent/database/migrations/versions/f6a7b8c9d0e1_add_session_id_to_files.py` | **NEW** — migration |
| `backend/execution/dag_tracker.py` | `track_files_in_work_dir()` uses FileRepository, extracted `_classify_file_type()` |
| `backend/execution/task_executor.py` | Explicit `workflow_phase` and `generating_agent` in callbacks |
| `cmbagent/execution/file_registry.py` | Added deprecation notice |
| `cmbagent/phases/execution_manager.py` | Removed `track_file()`, `_track_output_files()`, `files_created` |
| `cmbagent/phases/planning.py` | Removed `manager.track_file()` call |
| `cmbagent/phases/control.py` | Removed 2 `manager.track_file()` calls |
| `cmbagent/phases/hitl_control.py` | Removed 3 `manager.track_file()` calls |
| `cmbagent/phases/hitl_planning.py` | Removed 2 `manager.track_file()` calls |

## Stage 5: Phase Migration — COMPLETE
- [x] 5.1: Finalize PhaseExecutionManager simplification
  - Updated module docstring to remove file tracking references
  - Removed `FILE_CREATED` from `PhaseEventType` enum
  - Replaced `self.config.enable_database` guards with direct `self._db_session` / `self._event_repo` checks
  - Updated class docstring to reference FileRepository delegation
- [x] 5.2: Fix IdeaGenerationPhase (add PhaseExecutionManager)
  - Added `from cmbagent.phases.execution_manager import PhaseExecutionManager`
  - Replaced manual `context.started_at`, callback invocation, `context.completed_at` with `manager.start()`, `manager.complete()`, `manager.fail()`
  - Added `manager.raise_if_cancelled()` before CMBAgent init
  - Added `**manager.get_managed_cmbagent_kwargs()` to CMBAgent constructor
- [x] 5.3: Fix HITLCheckpointPhase (add PhaseExecutionManager)
  - Added `from cmbagent.phases.execution_manager import PhaseExecutionManager`
  - Replaced manual `context.started_at`/`context.completed_at` with `manager.start()`, `manager.complete()`, `manager.fail()`
  - All early-return paths (auto-approve, no manager, timeout) now call `manager.complete()` or `manager.fail()`
- [x] 5.4: Fix OneShotPhase (add PhaseExecutionManager)
  - Added `from cmbagent.phases.execution_manager import PhaseExecutionManager`
  - Replaced manual `context.started_at`, callback invocation, `context.completed_at` with `manager.start()`, `manager.complete()`, `manager.fail()`
  - Added `manager.raise_if_cancelled()` before CMBAgent init
  - Added `**manager.get_managed_cmbagent_kwargs()` to CMBAgent constructor
- [x] 5.5: Simplify PhaseExecutionConfig (remove stale flags)
  - Removed `enable_database` field (was always True, now checks `_db_session` directly)
  - Removed `enable_file_tracking` field (file tracking moved to FileRepository)
  - Config now has 4 fields: `enable_callbacks`, `enable_pause_check`, `auto_checkpoint`, `checkpoint_interval`
- [x] 5.6: Verify phase registry completeness
  - All 8 phases registered: planning, control, one_shot, hitl_checkpoint, idea_generation, hitl_planning, hitl_control, copilot
  - All 8 phases use PhaseExecutionManager
  - All phase_type properties match registry keys
  - `__init__.py` exports all phases and configs

### Stage 5 Verification
- `grep -rn "PhaseExecutionManager" cmbagent/phases/ --include="*.py" | grep -c "manager = PhaseExecutionManager"` → **8 matches** (one per phase)
- `grep -rn "enable_database\|enable_file_tracking" cmbagent/ --include="*.py"` → **0 matches**
- `grep -rn "FILE_CREATED" cmbagent/ --include="*.py"` → **0 matches**
- `python -c "from cmbagent.phases import PhaseRegistry; assert len(PhaseRegistry.list_all()) == 8"` → **passes**

### Files Modified (Stage 5)
| File | Action |
|------|--------|
| `cmbagent/phases/execution_manager.py` | Removed stale config flags, FILE_CREATED event, enable_database guards |
| `cmbagent/phases/idea_generation.py` | Added PhaseExecutionManager usage |
| `cmbagent/phases/hitl_checkpoint.py` | Added PhaseExecutionManager usage |
| `cmbagent/phases/one_shot.py` | Added PhaseExecutionManager usage |

## Stage 6: Workflow Migration — COMPLETE
- [x] 6.1: Strip StreamCapture to relay only (~400 lines removed)
  - Removed entire `_detect_progress()` method (plan parsing, step transitions, idea generation detection)
  - Removed entire `_detect_agent_activity()` method (agent transitions, code blocks, tool calls, LLM API costs)
  - Removed `dag_tracker`, `mode`, `current_step`, `planning_complete`, `plan_buffer`, `collecting_plan`, `steps_added` instance variables
  - StreamCapture is now purely relay: write to WS + buffer + log file
- [x] 6.2: Add callbacks to one-shot workflow
  - Added `callbacks=None` parameter to `one_shot()` function signature
  - Passes `callbacks` to `WorkflowExecutor(callbacks=callbacks)`
  - Updated docstring
- [x] 6.3: Add callbacks to OCR/arxiv/enhance workflows
  - Added `callbacks=None` parameter to `process_single_pdf()` in `ocr.py`
  - Added `callbacks=None` parameter to `arxiv_filter()` in `arxiv_downloader.py`
  - Added `callbacks=None` parameter to `preprocess_task()` in `processing/task_preprocessor.py`
  - All three invoke `callbacks.invoke_phase_change("execution", 1)` and `callbacks.invoke_step_complete()` around their work
- [x] 6.4: Simplify task_executor callback wiring
  - All modes now pass `callbacks=workflow_callbacks`: one-shot, OCR, arxiv, enhance-input, planning-control, idea-generation, HITL, copilot
  - Single unified callback pipeline: `merge_callbacks(ws_callbacks, print_callbacks, pause_callbacks, event_tracking_callbacks)`
- [x] 6.5: Update StreamCapture construction (remove dag_tracker, mode params)
  - `StreamCapture(websocket, task_id, send_ws_event, loop=loop, work_dir=task_work_dir)` — no more `dag_tracker`, `mode`

### Files Modified (Stage 6)
| File | Action |
|------|--------|
| `backend/execution/stream_capture.py` | Stripped to relay only (~400 lines removed from StreamCapture) |
| `backend/execution/task_executor.py` | Updated StreamCapture construction, added callbacks to all workflow calls |
| `cmbagent/workflows/one_shot.py` | Added `callbacks` parameter |
| `cmbagent/ocr.py` | Added `callbacks` parameter to `process_single_pdf()` |
| `cmbagent/arxiv_downloader.py` | Added `callbacks` parameter to `arxiv_filter()` |
| `cmbagent/processing/task_preprocessor.py` | Added `callbacks` parameter to `preprocess_task()` |

## Stage 7: Robustness & Cleanup — COMPLETE
- [x] 7.1: Circuit breaker for callback invocation
  - Added `_CIRCUIT_BREAKER_THRESHOLD = 5` module constant
  - Added `_failure_counts: Dict[str, int]` field to `WorkflowCallbacks` dataclass
  - Added `_safe_invoke()` method: tracks consecutive failures per callback name, disables after threshold
  - Rewrote all 12 `invoke_*` methods to use `_safe_invoke()` (was inline try/except)
  - `check_should_continue()` also uses circuit breaker (defaults to True when open)
- [x] 7.2: DB transaction safety
  - Added `_safe_commit()` helper in `dag_tracker.py`: catches all exceptions, performs rollback, returns bool
  - Replaced 3 bare `self.db_session.commit()` calls with `_safe_commit(self.db_session, context)`
  - Wrapped all `self.db_session.rollback()` calls in try/except to prevent double-fault crashes
  - CostCollector `_persist_records()` already had safe rollback pattern — verified
- [x] 7.3: WS emission retry
  - Added `_WS_MAX_RETRIES = 2` and `_WS_RETRY_BACKOFF_BASE = 0.1` to `events.py`
  - `send_ws_event()` now retries up to 2 times with exponential backoff (0.1s, 0.2s)
  - Checks `WebSocketState.CONNECTED` between retries — bails immediately on permanent disconnect
  - Added `import asyncio` for `asyncio.sleep()`
- [x] 7.4: Fix session leak in repository defaults
  - Added `_owns_db_session = False` tracking to DAGTracker
  - Mark `_owns_db_session = True` when `_init_database()` creates a session
  - Added `close()` method: closes session only when we own it
  - Called `dag_tracker.close()` in both success and error paths of `task_executor.py`
  - Removed unused `import logging` from `events.py`
- [x] 7.5: Graceful degradation pattern
  - DAGTracker: `_init_database()` already catches all exceptions and logs warning (workflow continues)
  - CostCollector: `collect_from_callback()` now wrapped in top-level try/except (never raises)
  - `create_execution_event()` in task_executor already catches all exceptions
  - All tracking infrastructure failures are logged but never crash the workflow
- [x] 7.6: Structured logging consistency
  - Updated 8 error messages in `event_capture.py` to use `event_capture_failed event_type=<type> error=%s` format
  - All modified files (stream_capture, dag_tracker, cost_collector, events) now use `key=value` structured format
- [x] 7.7: Final dead code sweep
  - Removed unused `import logging` from `backend/websocket/events.py`
  - Verified no leftover references to `stream_capture.dag_tracker`, `stream_capture.mode`, `stream_capture.planning` in task_executor
  - Verified `CostManager`, `callback_integration` not imported anywhere
  - `build_dag_from_plan()` kept as backwards compat wrapper (only defined, not called in production)

### Files Modified (Stage 7)
| File | Action |
|------|--------|
| `cmbagent/callbacks.py` | Circuit breaker: `_failure_counts`, `_safe_invoke()`, rewrote all `invoke_*` methods |
| `backend/execution/dag_tracker.py` | `_safe_commit()` helper, `_owns_db_session` tracking, `close()` method |
| `backend/websocket/events.py` | WS retry with backoff, removed unused `logging` import |
| `backend/execution/task_executor.py` | `dag_tracker.close()` in success/error paths |
| `backend/execution/cost_collector.py` | Top-level try/except in `collect_from_callback()` |
| `cmbagent/execution/event_capture.py` | Structured logging format for 8 error messages |

## Stage 8: Branching — COMPLETE
- [x] 8.1: Verify DAG cloning with template system
  - Fixed `_copy_execution_history()` to preserve node status for nodes at/before branch point
- [x] 8.2: Branch-scoped event capture (contextvars)
  - Added `execute_in_branch_context()` to `BranchExecutor` using `contextvars.copy_context()`
- [x] 8.3: Branch cost tracking and comparison
  - Added `compare_costs()` to `BranchComparator` with per-model breakdown
- [x] 8.4: Racing branch DB model groundwork
  - Created `RacingGroup` table, added racing fields to `Branch`, migration created
- [x] 8.5: Branch point DAG visualization
  - Added `add_branch_point()` to `DAGTracker`

## Stage 9: Sample Workflow — COMPLETE
- [x] 9.1: Create sample phase classes (LiteratureReview, Synthesis) — ZERO tracking code
- [x] 9.2: Create deep-research-extended workflow definition (4 phases)
- [x] 9.3: Add DAG template mapping + mode routing for deep-research-extended
- [x] 9.4: Write extensibility validation tests (23 tests, all passing)

---

## Code Change Summary

| Stage | Lines Removed | Lines Added | Net |
|-------|--------------|------------|-----|
| 0 | ~30 + ~400 moved | ~50 | -380 |
| 1 | ~715 | ~80 | -635 |
| 2 | ~400 | ~120 | -280 |
| 3 | ~82 | ~60 | -22 |
| 4 | ~650 | ~150 | -500 |
| 5 | ~415 | ~80 | -335 |
| 6 | ~585 | ~50 | -535 |
| 7 | ~50 | ~100 | +50 |
| 8 | ~0 | ~80 | +80 |
| 9 | ~0 | ~250 | +250 |
| **Total** | **~3,327** | **~1,020** | **~-2,307** |

---

## Post-Implementation Fixes (Deep Research Tracking)

After implementing all 10 stages, deep research mode had no DAG nodes, no cost tracking,
no timeline history, and no file detection. Root cause: the `USE_ISOLATED_EXECUTION = True`
flag routed `planning-control` mode through an isolated subprocess that has **zero tracking
infrastructure** (no DAGTracker, no CostCollector, no EventRepository, no FileRepository).

### Fixes Applied

| # | Issue | Fix | File |
|---|-------|-----|------|
| 1 | **Isolated execution bypasses all tracking** | Added `planning-control`, `idea-generation`, `deep-research-extended` to `tracked_modes` set that bypasses isolated execution | `backend/execution/task_executor.py` |
| 2 | **Cost directory missing** | Added `os.makedirs(cost_dir, exist_ok=True)` before writing cost JSON | `cmbagent/cmbagent.py` |
| 3 | **CostCollector session_id FK violation** | Changed `session_id or ""` to `session_id or dag_tracker.session_id or ""` to ensure valid FK | `backend/execution/task_executor.py` |
| 4 | **Timeline WS events were no-ops** | Added `planning_start`, `planning_complete`, `step_start`, `step_complete`, `step_failed` WS emissions | `backend/callbacks/websocket_callbacks.py` |
| 5 | **Cost WS callback was no-op** | Added `cost_summary` WS emission with total cost/tokens | `backend/callbacks/websocket_callbacks.py` |
| 6 | **files_updated WS fails from sync thread** | Added `event_loop` param to DAGTracker, uses `asyncio.run_coroutine_threadsafe()` as fallback | `backend/execution/dag_tracker.py` |
| 7 | **Event loop obtained too late** | Moved `loop = asyncio.get_event_loop()` before DAGTracker creation, pass via `event_loop=loop` | `backend/execution/task_executor.py` |
| 8 | **deep-research-extended not in planning phase set** | Added `deep-research-extended` to the modes that start in `"planning"` phase | `backend/execution/task_executor.py` |

### How It Works Now

```
Frontend → WebSocket → task_executor.py
  ↓
  mode in tracked_modes? ─── Yes ──→ In-process execution path
  │                                   ├── DAGTracker (dynamic DAG + DB persistence)
  │                                   ├── CostCollector (JSON → DB + WS)
  │                                   ├── EventRepository (timeline events)
  │                                   ├── FileRepository (file tracking)
  │                                   └── WebSocket callbacks (real-time UI updates)
  │
  └── No ──→ Isolated execution (subprocess, for utility modes like OCR, arxiv)
```

### Dynamic DAG Flow for Deep Research

```
1. DAGTracker.create_dag_for_mode("planning-control")
   → Uses "plan-execute" template
   → Creates: start → planning → end (dynamic_steps=True)

2. PlanningPhase.execute() completes
   → Callback: on_planning_complete(plan_info)
   → DAGTracker.add_step_nodes(plan_info.steps)
   → Dynamically adds: step_1, step_2, ..., step_N between planning and end
   → Emits dag_updated WS event

3. ControlPhase.execute() runs each step
   → Callback: on_step_start(step_info) → DAGTracker updates node to "running"
   → Callback: on_step_complete(step_info) → DAGTracker updates node to "completed"
   → track_files_in_work_dir() → FileRepository registers files + emits files_updated WS event
   → display_cost() → CostCollector persists + emits cost_update WS event
```

---

## Post-Implementation Fixes (One-Shot Tracking)

One-shot mode had the same root cause as deep research: it was NOT in `tracked_modes`
(previously called `legacy_modes`), so it went through isolated subprocess execution
with zero tracking infrastructure.

### Fixes Applied

| # | Issue | Fix | File |
|---|-------|-----|------|
| 1 | **One-shot in isolated execution (no tracking)** | Added `"one-shot"` to `tracked_modes` set | `backend/execution/task_executor.py` |
| 2 | **Renamed `legacy_modes` → `tracked_modes`** | Clearer naming; "tracked" = in-process with full tracking infrastructure | `backend/execution/task_executor.py` |
| 3 | **DAG nodes had no transitions during execution** | Added one-shot handler in `on_phase_change`: when phase="one_shot", marks `init` → completed and `execute` → running | `backend/execution/task_executor.py` |
| 4 | **No one-shot config log** | Added config output message for one-shot mode (agent, model) | `backend/execution/task_executor.py` |

### DAG Flow for One-Shot

```
1. DAGTracker.create_dag_for_mode("one-shot")
   → Uses "fixed-pipeline" template
   → Creates: init → execute → terminator (dynamic_steps=False)

2. Before execution:
   → init node set to "running"

3. OneShotPhase.execute() starts
   → Callback: phase_change("one_shot", None)
   → on_phase_change marks init → completed, execute → running

4. OneShotPhase.execute() completes
   → display_cost() → CostCollector persists + emits cost_update WS
   → Agent messages tracked via on_agent_msg callback

5. Post-completion (after thread pool returns):
   → All nodes marked "completed"
   → track_files_in_work_dir() for each node
   → Terminator marked "completed"
```

### Removal of Human Approval from Planning-Control

Also fixed: deep research (planning-control mode) was showing human approval prompts
even though HITL approval should only exist in `hitl-interactive` mode.

| # | Issue | Fix | File |
|---|-------|-----|------|
| 1 | **Unwanted approval gates in planning-control** | Removed all `WebSocketApprovalManager` creation, `approval_manager` and `hitl_after_planning` params from planning-control code path | `backend/execution/task_executor.py` |

### Auto Schema Migration for `files.session_id`

SQLite error `no such column: files.session_id` was caused by `Base.metadata.create_all()`
not altering existing tables.

| # | Issue | Fix | File |
|---|-------|-----|------|
| 1 | **Missing column in existing DB** | Added `_apply_schema_migrations()` that uses `ALTER TABLE` for missing columns, called from `init_database()` | `cmbagent/database/base.py` |
