# Target Architecture

## Library/App Boundary

```
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (App Layer)                         │
│                                                                 │
│  task_executor.py          dag_tracker.py        stream_capture │
│  ┌──────────────┐          ┌──────────────┐      ┌────────────┐│
│  │ Creates       │          │ DAG State    │      │ stdout     ││
│  │ callbacks     │──emit──▶│ Owner        │      │ relay ONLY ││
│  │ wired to      │          │              │      │ (no regex) ││
│  │ DAGTracker    │          │ • nodes      │      └────────────┘│
│  │              │          │ • edges      │                     │
│  │ WS callbacks │          │ • statuses   │      DB Persistence│
│  │ DB callbacks │          │ • file track │      ┌────────────┐│
│  │ Session mgmt │          │ • WS emit    │──────│ SQLAlchemy  ││
│  └──────┬───────┘          └──────────────┘      │ Models     ││
│         │                                         └────────────┘│
│         │  merge_callbacks()                                    │
│         ▼                                                       │
│  ┌──────────────┐                                               │
│  │ Merged       │  WorkflowCallbacks (the boundary contract)    │
│  │ Callbacks    │────────────────────────────────────────────── │
│  └──────┬───────┘                                               │
└─────────┼───────────────────────────────────────────────────────┘
          │ passed as parameter
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CMBAGENT (Library Layer)                    │
│                                                                 │
│  PhaseOrchestrator          Phases                              │
│  ┌──────────────┐          ┌──────────────────┐                │
│  │ Runs phases  │──────────│ Planning         │                │
│  │ in sequence  │          │ Control          │                │
│  │              │          │ HITL Planning    │                │
│  │ Passes       │          │ HITL Control     │                │
│  │ callbacks    │          │ One-Shot         │                │
│  │ to each      │          │ Copilot          │                │
│  │ phase        │          │ Idea Generation  │                │
│  └──────────────┘          └────────┬─────────┘                │
│                                      │                          │
│  PhaseExecutionManager              │ uses                     │
│  ┌──────────────────────┐          ▼                           │
│  │ SIMPLIFIED:          │    CMBAgent.solve()                  │
│  │ • invoke callbacks   │    ┌──────────────────┐              │
│  │ • timing             │    │ AG2 Agents       │              │
│  │ • pause/cancel check │    │ display_cost()   │──▶ cost/*.json│
│  │ • error handling     │    │ work_dir files   │              │
│  │                      │    └──────────────────┘              │
│  │ NO:                  │                                       │
│  │ • DAG creation       │    EventCapture (contextvars)        │
│  │ • DB writes          │    ┌──────────────────┐              │
│  │ • WS emission        │    │ AG2 hooks        │              │
│  └──────────────────────┘    │ Session-scoped   │              │
│                               │ via ContextVar   │              │
│                               └──────────────────┘              │
│                                                                 │
│  WorkflowCallbacks (PURE interface, no app logic)              │
│  ┌─────────────────────────────────────────────┐               │
│  │ on_planning_start/complete                   │               │
│  │ on_step_start/complete/failed               │               │
│  │ on_workflow_start/complete/failed            │               │
│  │ on_cost_update                              │               │
│  │ on_agent_message / on_code_execution        │               │
│  │ on_tool_call / on_phase_change              │               │
│  │ on_file_created (NEW)                       │               │
│  │ should_continue / on_pause_check            │               │
│  │                                              │               │
│  │ merge_callbacks()                            │               │
│  │ create_null_callbacks()                      │               │
│  │ create_print_callbacks()                     │               │
│  │                                              │               │
│  │ NO: create_websocket_callbacks() (REMOVED)   │               │
│  │ NO: create_database_callbacks() (REMOVED)    │               │
│  └─────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow: Callback-Driven (Target State)

Each cross-cutting concern has ONE path. No duplicates, no competing systems.

### DAG Updates (Stage 1)
```
Phase invokes callback.on_step_start(step_info)
  → task_executor bridge callback
    → DAGTracker.update_node_status("step_1", "running")
      → Updates self.nodes, self.node_statuses
      → Persists to DB (DAGNode model)
      → Emits WS event "dag_node_status_changed"
      → Emits WS event "dag_updated"
```

### Cost Tracking (Stage 2)
```
Phase completes → CMBAgent.display_cost() writes cost/*.json
  → Phase invokes callback.on_cost_update(cost_data)
    → task_executor bridge callback
      → CostCollector.collect_from_callback(cost_data)
        → Reads actual JSON file (NOT stdout regex)
        → Persists to DB (CostRecord model) with real token counts
        → Emits WS event "cost_update" with accurate data
        → Idempotent: tracks processed files via _processed_files set
```

### Event Capture (Stage 3)
```
AG2 agent calls LLM → monkey-patched generate_reply()
  → get_event_captor() via contextvars.ContextVar
    → EventCaptureManager for THIS session/branch
      → Thread-safe ordering via _lock + _order_counter
      → Thread-local event stack via threading.local()
      → Buffered DB writes (flush every N events)
      → Optional WS emission via ws_emit_callback (no backend imports)
```

### File Tracking (Stage 4)
```
Phase completes → callback.on_step_complete(step_info)
  → task_executor bridge callback
    → DAGTracker.track_files_in_work_dir(work_dir, node_id, phase, agent)
      → FileRepository.register_file() for each file
        → Deduplication by (run_id, file_path)
        → Content hash (SHA-256) for files < 50MB
        → session_id for multi-tenant isolation
        → Explicit phase attribution (not path guessing)
        → generating_agent tracking
        → Priority classification (primary/secondary/internal)
      → Persists to DB (File model with session_id)
      → Emits WS event "files_updated"
```

### Phase Lifecycle (Stage 5)
```
Orchestrator starts phase
  → PhaseExecutionManager.start()
    → callback.on_phase_change(phase_type, step_number)
      → task_executor bridge → DAGTracker node status update
  → PhaseExecutionManager.start_step(n, description, agent)
    → callback.on_step_start(StepInfo)
  → AG2 agents execute (events captured via contextvars)
  → PhaseExecutionManager.complete_step(n)
    → callback.on_step_complete(StepInfo)
      → task_executor bridge → DAGTracker + FileRepository
  → PhaseExecutionManager.complete()
    → callback.on_phase_change(next_phase, step_number)

PhaseExecutionManager does ONLY:
  - Invoke callbacks
  - Track timing
  - Check pause/cancel via should_continue()
  - Manage event capture context
PhaseExecutionManager does NOT:
  - Create DAG nodes
  - Write to DB
  - Emit WS events
  - Track files
```

### Workflow Orchestration (Stage 6)
```
task_executor receives request
  → Creates DAGTracker with mode
  → DAGTracker.create_dag_for_mode() via template factory
  → Creates merged callbacks (WS + DB + event tracking)
  → Passes callbacks to workflow function
    → Workflow function creates phases, runs in sequence
    → StreamCapture relays stdout ONLY (no regex parsing)
    → All tracking driven by callbacks
```

## DAGTracker Generalization

### Current: 8 hardcoded mode branches
```python
# dag_tracker.py:137-321 - CURRENT (BAD)
def create_dag_for_mode(self, task, config):
    if self.mode == "planning-control":
        return self._create_planning_control_dag(task, config)
    elif self.mode == "idea-generation":
        return self._create_idea_generation_dag(task, config)
    elif self.mode == "hitl-interactive":
        return self._create_hitl_dag(task, config)
    # ... 5 more elif branches
```

### Target: Configuration-driven factory
```python
# dag_tracker.py - TARGET (GOOD)
DAG_TEMPLATES = {
    "plan-execute": {
        "initial_nodes": [
            {"id": "planning", "type": "planning", "label": "{label_prefix} Planning"}
        ],
        "dynamic_steps": True,  # Steps added after planning
    },
    "fixed-pipeline": {
        "initial_nodes": [
            {"id": "init", "type": "planning", "label": "Initialize"},
            {"id": "execute", "type": "agent", "label": "Execute ({agent})"},
            {"id": "terminator", "type": "terminator", "label": "Completion"},
        ],
        "edges": [("init", "execute"), ("execute", "terminator")],
        "dynamic_steps": False,
    },
}

MODE_TO_TEMPLATE = {
    "planning-control": ("plan-execute", {"label_prefix": ""}),
    "hitl-interactive": ("plan-execute", {"label_prefix": "HITL"}),
    "idea-generation": ("plan-execute", {"label_prefix": "Idea"}),
    "one-shot": ("fixed-pipeline", {}),
    "ocr": ("fixed-pipeline", {}),
    "arxiv": ("fixed-pipeline", {}),
    "enhance-input": ("fixed-pipeline", {}),
}

def create_dag_for_mode(self, task, config):
    template_name, params = MODE_TO_TEMPLATE.get(
        self.mode, ("fixed-pipeline", {})
    )
    template = DAG_TEMPLATES[template_name]
    return self._create_from_template(template, task, config, params)
```

## Adding a New Workflow (Target State)

After all stages, adding a new workflow requires ONLY:

| Step | Where | Lines of Code | Example |
|------|-------|--------------|---------|
| 1. Phase class(es) | `cmbagent/phases/` | ~30-50 per phase | Standard pattern with PhaseExecutionManager |
| 2. Workflow function | `cmbagent/workflows/` | ~50 | Wire phases with WorkflowExecutor |
| 3. DAG template | `backend/execution/dag_tracker.py` | 1-3 | `MODE_TO_TEMPLATE["x"] = ("plan-execute", {...})` |
| 4. Mode routing | `backend/execution/task_executor.py` | ~10 | `elif mode == "x": results = ...` |
| **Total** | | **~100-160** | **Zero tracking code** |

ZERO changes needed in:
- StreamCapture (relay only)
- EventCaptureManager (session-scoped via contextvars)
- CostCollector (reads JSON automatically)
- FileRepository (scans work_dir automatically)
- DAG state management (callbacks drive DAGTracker)
- PhaseExecutionManager (just invokes callbacks)

See Stage 9 for a complete "deep-research" sample workflow proving this.

## Cross-Cutting Concerns Matrix

| Concern | Stage | Owner | Library Role | App Role |
|---------|-------|-------|-------------|----------|
| DAG State | 1 | DAGTracker (app) | Invoke callbacks | Template factory, maintain nodes/edges/statuses |
| Cost Tracking | 2 | CostCollector (app) | Write cost/*.json via display_cost() | Read JSON, persist to DB, emit WS |
| Event Capture | 3 | EventCaptureManager (lib) | Capture AG2 events via contextvars hooks | Provide WS emission callback |
| File Tracking | 4 | FileRepository (app) | Create files in work_dir | Dedup, hash, classify, persist to DB |
| Phase Lifecycle | 5 | PhaseExecutionManager (lib) | Invoke callbacks, timing, pause/cancel | Bridge callbacks to DAGTracker |
| Workflow Wiring | 6 | task_executor (app) | Accept callbacks parameter | Create merged callbacks, start workflow |
| Pause/Cancel | 0 | Callbacks (contract) | Check should_continue() | Set pause/cancel state |
| Session Mgmt | - | SessionManager (app) | None (library is session-agnostic) | Create/save/resume sessions |
| Error Handling | 7 | Both | Propagate errors via callbacks | Circuit breaker, retry, log |
| Branching | 8 | BranchManager (lib+app) | contextvars isolation per branch | Clone DAG, compare costs |

## Robustness Patterns (Stage 7)

### Circuit Breaker for Callback Invocation
```python
def safe_invoke(callback, *args, **kwargs):
    try:
        result = callback(*args, **kwargs)
        if asyncio.iscoroutine(result):
            asyncio.get_event_loop().run_until_complete(result)
    except Exception as e:
        logger.error("callback_failed", callback=callback.__name__, error=str(e))
        # Never let callback failure crash the workflow
```

### DB Transaction Safety
```python
def safe_db_operation(db_session, operation, *args):
    savepoint = db_session.begin_nested()
    try:
        result = operation(*args)
        savepoint.commit()
        return result
    except Exception as e:
        savepoint.rollback()
        logger.error("db_operation_failed", error=str(e))
        return None
```

### WS Emission Retry
```python
async def safe_ws_emit(ws, event_type, data, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            await send_event(ws, event_type, data)
            return True
        except Exception as e:
            if attempt == max_retries:
                logger.warning("ws_emit_failed", event=event_type, error=str(e))
                return False
            await asyncio.sleep(0.1 * (attempt + 1))
```

## Session Isolation (contextvars)

```python
# cmbagent/execution/event_capture.py - TARGET
import contextvars

_event_captor_var: contextvars.ContextVar[Optional[EventCaptureManager]] = (
    contextvars.ContextVar('event_captor', default=None)
)

def get_event_captor() -> Optional[EventCaptureManager]:
    return _event_captor_var.get()

def set_event_captor(captor: Optional[EventCaptureManager]):
    _event_captor_var.set(captor)
```

This ensures:
- Concurrent sessions don't overwrite each other's captor
- Branch executions get their own isolated captor
- Thread pool executors inherit context correctly via `contextvars.copy_context()`
