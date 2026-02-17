# Stage 1: DAG Overhaul

## Objectives
1. Make DAGTracker workflow-agnostic (replace 8 hardcoded mode branches with config-driven factory)
2. Remove DAG creation from PhaseExecutionManager (eliminate conflicting nodes)
3. Ensure single DAG ownership through DAGTracker only
4. Support future dynamic DAG shapes (branch points, parallel groups)

## Dependencies
- Stage 0 (callback contract defined)

---

## Current State

### Problem 1: 8 Hardcoded Mode Branches
**File**: `backend/execution/dag_tracker.py:137-321`
```python
def create_dag_for_mode(self, task, config):
    if self.mode == "planning-control":
        return self._create_planning_control_dag(task, config)
    elif self.mode == "idea-generation":
        return self._create_idea_generation_dag(task, config)
    elif self.mode == "hitl-interactive":
        return self._create_hitl_dag(task, config)
    elif self.mode == "one-shot":
        # ... 5 more branches ...
```
Adding a new workflow requires adding a new method + elif branch.

### Problem 2: Conflicting DAG Nodes
**File**: `cmbagent/phases/execution_manager.py:322-337`
PhaseExecutionManager creates UUID-based DAGNode records. DAGTracker uses string IDs ("step_1", "planning"). Both write to the same DB table, creating orphaned records.

### Problem 3: Dual WS Emission
Both `dag_tracker.py:612-638` AND `callbacks.py:527-548` emit `dag_node_status_changed`.

---

## Implementation Tasks

### Task 1.1: Template-Based DAG Factory

**File**: `backend/execution/dag_tracker.py`

Replace 7 `_create_*_dag()` methods with config:

```python
DAG_TEMPLATES = {
    "plan-execute": {
        "initial_nodes": [
            {"id": "planning", "type": "planning", "status": "pending", "step_number": 0}
        ],
        "initial_edges": [],
        "dynamic_steps": True,  # Steps added after planning via add_step_nodes()
    },
    "fixed-pipeline": {
        "initial_nodes": [
            {"id": "init", "type": "planning", "status": "pending", "step_number": 0},
            {"id": "execute", "type": "agent", "status": "pending", "step_number": 1},
            {"id": "terminator", "type": "terminator", "status": "pending", "step_number": 2},
        ],
        "initial_edges": [
            {"source": "init", "target": "execute"},
            {"source": "execute", "target": "terminator"},
        ],
        "dynamic_steps": False,
    },
    "three-stage-pipeline": {
        "initial_nodes": [
            {"id": "init", "type": "planning", "status": "pending", "step_number": 0},
            {"id": "process", "type": "agent", "status": "pending", "step_number": 1},
            {"id": "output", "type": "agent", "status": "pending", "step_number": 2},
            {"id": "terminator", "type": "terminator", "status": "pending", "step_number": 3},
        ],
        "initial_edges": [
            {"source": "init", "target": "process"},
            {"source": "process", "target": "output"},
            {"source": "output", "target": "terminator"},
        ],
        "dynamic_steps": False,
    },
}

MODE_TO_TEMPLATE = {
    "planning-control": ("plan-execute", {"planning": {"label": "Planning Phase"}}),
    "hitl-interactive": ("plan-execute", {"planning": {"label": "HITL Planning"}}),
    "idea-generation": ("plan-execute", {"planning": {"label": "Idea Planning"}}),
    "one-shot": ("fixed-pipeline", {"execute": {"label": "Execute ({agent})"}}),
    "ocr": ("three-stage-pipeline", {"process": {"label": "Process PDFs"}, "output": {"label": "Save Output"}}),
    "arxiv": ("three-stage-pipeline", {"process": {"label": "Filter arXiv"}, "output": {"label": "Download Papers"}}),
    "enhance-input": ("fixed-pipeline", {"execute": {"label": "Enhance Input"}}),
}

def create_dag_for_mode(self, task, config):
    template_key, overrides = MODE_TO_TEMPLATE.get(self.mode, ("fixed-pipeline", {}))
    template = DAG_TEMPLATES[template_key]
    return self._create_from_template(template, task, config, overrides)
```

### Task 1.2: Remove DAG Creation from PhaseExecutionManager

**File**: `cmbagent/phases/execution_manager.py`

Remove ALL DAG-related code:
- Remove `_current_dag_node_id` and `_step_dag_node_ids` (lines 145-146)
- Remove DAG node creation in `start()` (lines 294-339)
- Remove DAG updates in `complete()` (lines 394-401)
- Remove DAG updates in `fail()` (lines 457-464)
- Remove DAG creation in `start_step()` (lines 514-566)
- Remove DAG updates in `complete_step()` (lines 611-629)
- Remove DAG updates in `fail_step()` (lines 667-681)
- Remove `add_plan_step_nodes()` entirely (lines 701-833) - DAGTracker handles this via callbacks
- Remove `create_redo_branch()` (lines 835-874) - branching system handles this

### Task 1.3: Remove Duplicate WS Emission from App Callbacks

**File**: `backend/callbacks/app_callbacks.py` (moved in Stage 0)

Remove DAG-specific WS emissions (they duplicate DAGTracker emissions):
- Remove `on_planning_start` → `dag_node_status_changed`
- Remove `on_planning_complete` → `dag_node_status_changed` AND `dag_updated`
- Remove `on_step_start` → `dag_node_status_changed`
- Remove `on_step_complete` → `dag_node_status_changed`
- Remove `on_step_failed` → `dag_node_status_changed`
- Remove `on_workflow_complete` → `dag_node_status_changed`

Keep NON-DAG events: `agent_message`, `code_execution`, `tool_call`, `phase_change`, `workflow_failed`.

### Task 1.4: Delete Dead DAG Methods

**File**: `backend/execution/dag_tracker.py`

Delete:
- `build_dag_from_plan()` (lines 871-933) - regex text parsing, superseded by `add_step_nodes()`
- `_build_inmemory_dag_from_plan()` (lines 934-964) - same
- 7 individual `_create_*_dag()` methods (lines 159-321) - replaced by templates

### Task 1.5: DAGTracker DB Session Injection

Accept optional DB session from caller instead of always creating own:
```python
def __init__(self, websocket, task_id, mode, send_event_func,
             run_id=None, db_session=None, session_id=None):
    if db_session:
        self.db_session = db_session
        self.session_id = session_id
        self._setup_repos()
    else:
        self._init_database()  # Existing fallback
```

---

## Cleanup Items
| Item | Lines Removed |
|------|--------------|
| 7 `_create_*_dag()` methods | ~160 |
| PhaseExecutionManager DAG code | ~400 |
| Dead `build_dag_from_plan()` methods | ~95 |
| Duplicate WS emissions in callbacks | ~60 |
| **Total** | **~715** |

## Verification
```bash
# Template coverage
python -c "from backend.execution.dag_tracker import MODE_TO_TEMPLATE; assert len(MODE_TO_TEMPLATE) >= 7"
# No DAG in PhaseExecutionManager
grep -c "create_node\|_dag_repo\|_step_dag_node_ids" cmbagent/phases/execution_manager.py  # 0
# HITL still works end-to-end
```

## Files Modified
| File | Action |
|------|--------|
| `backend/execution/dag_tracker.py` | Template factory, delete 7 methods, DB injection |
| `cmbagent/phases/execution_manager.py` | Remove ~400 lines of DAG code |
| `backend/callbacks/app_callbacks.py` | Remove DAG WS emissions |
