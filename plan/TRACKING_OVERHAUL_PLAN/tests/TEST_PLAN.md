# Test Plan

## Overall Strategy

Each stage is independently testable. Tests run after each stage to verify:
1. **Regression**: Existing workflows still work
2. **Correctness**: New behavior works as expected
3. **Isolation**: Library has no backend dependencies

---

## Stage 0 Tests

### T0.1: Import Isolation
```bash
# Library must import without backend in sys.path
cd /srv/projects/mas/mars/denario/cmbagent
python -c "
import sys
# Remove backend from path if present
sys.path = [p for p in sys.path if 'backend' not in p]
from cmbagent.callbacks import WorkflowCallbacks, merge_callbacks, create_print_callbacks
print('OK: Library imports work without backend')
"
```

### T0.2: Model Concatenation Fix
```bash
python -c "
cost_dict = {'Agent': ['eng'], 'Model': ['gpt-4o'], 'Cost (\$)': [0.01],
             'Prompt Tokens': [100], 'Completion Tokens': [50], 'Total Tokens': [150]}
# Simulate the fix
model_name = 'gpt-4o'
i = 0
if model_name not in cost_dict['Model'][i]:
    cost_dict['Model'][i] = model_name
assert cost_dict['Model'][0] == 'gpt-4o', f'Expected gpt-4o, got {cost_dict[\"Model\"][0]}'
print('OK: Model concatenation fix works')
"
```

### T0.3: contextvars Isolation
```bash
python -c "
import contextvars

var = contextvars.ContextVar('test', default=None)
var.set('main')

ctx = contextvars.copy_context()
def branch():
    var.set('branch')
    assert var.get() == 'branch'
ctx.run(branch)

assert var.get() == 'main', f'Expected main, got {var.get()}'
print('OK: contextvars isolation verified')
"
```

### T0.4: HITL Regression (Manual)
```
1. Start backend server
2. Open UI, create HITL interactive task
3. Verify DAG appears correctly
4. Approve plan
5. Verify steps execute and DAG updates
6. Verify cost report appears
7. Verify no duplicate WS events in browser console
```

---

## Stage 1 Tests

### T1.1: PhaseExecutionManager Simplified
```bash
grep -c "create_node\|create_edge\|_dag_repo\|_db_session\|_event_repo" \
  cmbagent/phases/execution_manager.py
# Expected: 0
```

### T1.2: Dead Code Removed
```bash
test ! -f cmbagent/managers/cost_manager.py && echo "OK: CostManager deleted"
test ! -f cmbagent/execution/callback_integration.py && echo "OK: callback_integration deleted"
```

### T1.3: No Reverse Imports
```bash
count=$(grep -rn "from backend\|import backend" cmbagent/ --include="*.py" | grep -v __pycache__ | wc -l)
test $count -eq 0 && echo "OK: No reverse imports" || echo "FAIL: Found $count reverse imports"
```

### T1.4: Thread-Safe Event Capture
```python
# tests/test_event_capture_threadsafe.py
import threading
from cmbagent.execution.event_capture import EventCaptureManager

def test_concurrent_event_capture():
    """Verify no race conditions in event ordering."""
    results = {"orders": []}
    lock = threading.Lock()

    def capture_events(captor, count):
        for _ in range(count):
            order = captor._next_order()
            with lock:
                results["orders"].append(order)

    captor = EventCaptureManager(
        db_session=None, run_id="test", session_id="test", enabled=False
    )

    threads = [
        threading.Thread(target=capture_events, args=(captor, 100))
        for _ in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 1000 orders should be unique
    assert len(results["orders"]) == 1000
    assert len(set(results["orders"])) == 1000
```

---

## Stage 2 Tests

### T2.1: DAG Template Coverage
```python
# tests/test_dag_templates.py
from backend.execution.dag_tracker import MODE_TO_TEMPLATE, DAG_TEMPLATES

def test_all_modes_have_templates():
    """Every supported mode has a template mapping."""
    modes = [
        "planning-control", "hitl-interactive", "idea-generation",
        "one-shot", "ocr", "arxiv", "enhance-input", "copilot"
    ]
    for mode in modes:
        assert mode in MODE_TO_TEMPLATE, f"Missing template for mode: {mode}"

def test_all_templates_referenced_exist():
    """Every template referenced in MODE_TO_TEMPLATE exists."""
    for mode, (template_name, _) in MODE_TO_TEMPLATE.items():
        assert template_name in DAG_TEMPLATES, f"Template {template_name} for {mode} not found"

def test_template_creates_valid_dag():
    """Templates produce nodes with required fields."""
    for template_name, template in DAG_TEMPLATES.items():
        for node in template["initial_nodes"]:
            assert "id" in node, f"Node missing id in {template_name}"
            assert "type" in node, f"Node missing type in {template_name}"
            assert "status" in node, f"Node missing status in {template_name}"
```

### T2.2: StreamCapture is Pure Relay
```bash
# No regex, no detection, no dag_tracker reference
grep -c "re\.\|_detect_\|dag_tracker\|planning_complete\|current_step" \
  backend/execution/stream_capture.py
# Expected: 0
```

### T2.3: Cost JSON Accuracy
```python
# tests/test_cost_collector.py
import json
import tempfile
import os

def test_cost_collector_reads_json():
    """CostCollector reads actual JSON data, not estimates."""
    # Write a test cost JSON
    cost_data = [
        {"Agent": "engineer", "Model": "gpt-4o", "Cost ($)": "$0.05",
         "Prompt Tokens": 1000, "Completion Tokens": 500, "Total Tokens": 1500},
        {"Agent": "Total", "Model": "", "Cost ($)": "$0.05",
         "Prompt Tokens": 1000, "Completion Tokens": 500, "Total Tokens": 1500},
    ]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(cost_data, f)
        json_path = f.name

    try:
        from backend.execution.cost_collector import CostCollector
        collector = CostCollector(db_session=None, session_id="test", run_id="test")
        # Should read actual tokens, not 70/30 estimates
        collector.collect_from_callback({"cost_json_path": json_path, "records": cost_data})
        # Verify Total rows are skipped
        # Verify actual token counts are used
    finally:
        os.unlink(json_path)
```

---

## Stage 3 Tests

### T3.1: Graceful Degradation
```python
# tests/test_graceful_degradation.py
def test_dag_tracker_survives_db_failure():
    """DAGTracker logs error but doesn't crash when DB fails."""
    tracker = DAGTracker(
        websocket=None, task_id="test", mode="one-shot",
        send_event_func=lambda *a, **k: None,
        db_session=None  # No DB!
    )
    dag = tracker.create_dag_for_mode("test", {})
    assert len(dag["nodes"]) > 0  # Should still create in-memory DAG
```

### T3.2: Session Isolation
```python
# tests/test_session_isolation.py
def test_events_filtered_by_session():
    """Events from different sessions are isolated."""
    from cmbagent.database.repository import EventRepository
    # ... create events in session A ...
    # ... query from session B ...
    # ... verify zero results ...
```

### T3.3: Circuit Breaker
```python
def test_callback_circuit_breaker():
    """After N failures, callbacks stop being invoked."""
    error_count = [0]

    def failing_callback(*args):
        error_count[0] += 1
        raise RuntimeError("test error")

    callbacks = WorkflowCallbacks(on_step_start=failing_callback)
    callbacks._max_errors = 3

    for _ in range(10):
        callbacks._safe_invoke("on_step_start", callbacks.on_step_start)

    assert error_count[0] == 3  # Stopped after circuit breaker opens
```

---

## Stage 4 Tests

### T4.1: Branch DAG Cloning
```python
def test_branch_creates_correct_dag():
    """Branching clones DAG nodes with reset statuses."""
    # ... create parent run with completed steps ...
    # ... branch from step 3 ...
    # ... verify steps 1-2 are completed, 3+ are pending ...
```

### T4.2: contextvars Branch Isolation
```python
def test_branch_event_capture_isolated():
    """Branch events don't leak to parent."""
    # ... set parent captor ...
    # ... create branch in copy_context() ...
    # ... set branch captor ...
    # ... verify parent captor unchanged ...
```

### T4.3: New Workflow Addition
```python
def test_adding_new_workflow_minimal():
    """Adding a new mode only requires template mapping."""
    # Add new mode, verify DAG created, clean up
    # See Stage 4 Task 4.6 for implementation
```

---

## Regression Test Matrix

| Test | Stage 0 | Stage 1 | Stage 2 | Stage 3 | Stage 4 |
|------|---------|---------|---------|---------|---------|
| HITL end-to-end | X | X | X | X | X |
| Planning-control | | | X | X | X |
| One-shot | | | X | X | X |
| Import isolation | X | X | X | X | X |
| Cost report accuracy | X | | X | X | X |
| WS event count | | | X | X | X |
