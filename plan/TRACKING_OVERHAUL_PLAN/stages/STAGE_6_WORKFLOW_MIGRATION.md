# Stage 6: Workflow Migration

## Objectives
1. Strip StreamCapture to stdout relay ONLY (remove all regex-based detection)
2. Ensure all workflows pass callbacks correctly through the chain
3. Simplify task_executor callback wiring (3 sets max, no duplicates)
4. Verify all modes work with callback-driven tracking (no StreamCapture fallback)
5. Skip copilot workflow (will be revamped separately)

## Dependencies
- Stage 1 (DAG templates)
- Stage 5 (all phases use PhaseExecutionManager)

---

## Current State

### StreamCapture Does Too Much
**File**: `backend/execution/stream_capture.py`

Currently StreamCapture handles stdout relay AND:
- `_detect_progress()` (lines 451-640) - 190 lines of regex parsing plan files, step transitions, idea phases
- `_detect_cost_updates()` (lines 255-344) - already removed in Stage 2
- `_detect_agent_activity()` (lines 346-449) - regex for handoffs, code blocks, tool calls

The HITL mode already skips auto-detection (lines 490-493), proving callbacks are sufficient.

### Workflow → Callback Wiring Status

| Workflow | Entry Point | Callbacks Passed | Path to DAGTracker |
|----------|------------|-----------------|-------------------|
| planning-control | `cmbagent.py:586` → `planning_and_control_context_carryover()` | YES via `callbacks=` param | callbacks → task_executor bridge → DAGTracker |
| hitl-interactive | `hitl_workflow.py:52` → `hitl_interactive_workflow()` | YES via `callbacks=` param | Same path |
| idea-generation | `cmbagent.py:766` → `planning_and_control_context_carryover()` | YES via `callbacks=` param | Same path |
| one-shot | `cmbagent.py:829` → `one_shot()` | **NO** - `callbacks=` NOT passed | StreamCapture regex only! |
| ocr | `cmbagent.py:795` → `process_single_pdf()` | **NO** callbacks support | No tracking at all |
| arxiv | `cmbagent.py:816` → `arxiv_filter()` | **NO** callbacks support | No tracking at all |
| enhance-input | `cmbagent.py:821` → `preprocess_task()` | **NO** callbacks support | No tracking at all |

### task_executor Callback Wiring (Current)
**File**: `backend/execution/task_executor.py:260-498`

Creates 4 callback sets:
1. `ws_callbacks` - WebSocket events
2. `event_tracking_callbacks` - DB event creation (DUPLICATE of EventCaptureManager)
3. `pause_callbacks` - Pause/cancel control
4. Print callbacks

Merges all 4 → `workflow_callbacks`. The `event_tracking_callbacks` (lines 319-488) duplicates what EventCaptureManager does via AG2 hooks + what PhaseExecutionManager does via callbacks.

---

## Implementation Tasks

### Task 6.1: Strip StreamCapture to Relay Only

**File**: `backend/execution/stream_capture.py`

Delete ALL detection methods and state:

```python
class StreamCapture:
    """Relay stdout to WebSocket and log file. Zero detection logic."""

    def __init__(self, websocket, task_id, send_event_func, loop=None, work_dir=None):
        self.websocket = websocket
        self.task_id = task_id
        self.send_event = send_event_func
        self.buffer = StringIO()
        self.loop = loop
        self._log_file = None

        if work_dir:
            try:
                log_dir = os.path.join(work_dir, "logs")
                os.makedirs(log_dir, exist_ok=True)
                self._log_file = open(os.path.join(log_dir, "console_output.log"), "a")
            except Exception as e:
                logger.warning("console_log_file_open_failed", error=str(e))

    async def write(self, text: str):
        if text.strip():
            try:
                await self.send_event(
                    self.websocket, "output",
                    {"message": text.strip()},
                    run_id=self.task_id
                )
            except Exception as e:
                logger.warning("ws_stream_send_failed", error=str(e))

        self.buffer.write(text)

        if self._log_file:
            try:
                self._log_file.write(text)
                self._log_file.flush()
            except Exception:
                pass

        return len(text)

    def flush(self):
        pass

    def getvalue(self):
        return self.buffer.getvalue()

    def close(self):
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None
```

**Delete**:
- `_detect_progress()` (lines 451-640) - ~190 lines
- `_detect_agent_activity()` (lines 346-449) - ~104 lines
- All state: `self.dag_tracker`, `self.mode`, `self.current_step`, `self.planning_complete`, `self.plan_buffer`, `self.collecting_plan`, `self.steps_added`, `self.total_cost`, `self.last_cost_report_time`

**Remove** `__init__` params: `dag_tracker`, `mode`

### Task 6.2: Add Callbacks to One-Shot Workflow

**File**: `cmbagent/workflows/one_shot.py`

Currently one-shot doesn't accept/pass callbacks:
```python
# ADD callbacks parameter:
def one_shot_workflow(task, ..., callbacks=None):
    context = PhaseContext(
        task=task,
        callbacks=callbacks,  # Pass through
        ...
    )
    # Execute with PhaseExecutionManager (fixed in Stage 5)
```

**File**: `backend/execution/task_executor.py`

Pass callbacks to one-shot:
```python
elif mode == "one-shot":
    results = cmbagent.one_shot(
        task=task,
        ...,
        callbacks=workflow_callbacks,  # ADD THIS
    )
```

### Task 6.3: Add Minimal Callbacks to OCR/Arxiv/Enhance

These are simple fixed-pipeline modes. Add basic callback support:

**File**: `cmbagent/cmbagent.py` (or relevant module)

For OCR:
```python
def process_single_pdf(self, pdf_path, ..., callbacks=None):
    if callbacks:
        callbacks.invoke_phase_change("execution", 1)
    # ... existing OCR logic ...
    if callbacks:
        step_info = StepInfo(step_number=1, status=StepStatus.COMPLETED)
        callbacks.invoke_step_complete(step_info)
```

Similar pattern for `arxiv_filter()` and `preprocess_task()`.

**File**: `backend/execution/task_executor.py`

Pass callbacks:
```python
elif mode == "ocr":
    results = cmbagent.process_single_pdf(
        ...,
        callbacks=workflow_callbacks,  # ADD
    )
elif mode == "arxiv":
    results = cmbagent.arxiv_filter(
        ...,
        callbacks=workflow_callbacks,  # ADD
    )
elif mode == "enhance-input":
    results = cmbagent.preprocess_task(
        ...,
        callbacks=workflow_callbacks,  # ADD
    )
```

### Task 6.4: Simplify task_executor Callback Wiring

**File**: `backend/execution/task_executor.py`

Reduce from 4 callback sets to 3:

```python
# 1. WS callbacks (non-DAG events: agent_message, code_execution, tool_call)
ws_callbacks = create_websocket_callbacks(ws_send_event, task_id)

# 2. DAG + tracking callbacks (bridge to DAGTracker + CostCollector)
tracking_callbacks = WorkflowCallbacks(
    on_planning_complete=lambda pi: _on_planning_complete(dag_tracker, pi, loop, task_work_dir),
    on_step_start=lambda si: _on_step_start(dag_tracker, si, loop),
    on_step_complete=lambda si: _on_step_complete(dag_tracker, si, loop, task_work_dir),
    on_step_failed=lambda si: _on_step_failed(dag_tracker, si, loop),
    on_phase_change=lambda phase, step: dag_tracker.set_phase(phase, step),
    on_cost_update=lambda cd: cost_collector.collect_from_callback(cd, ws_send_event),
)

# 3. Pause/Cancel callbacks
pause_callbacks = WorkflowCallbacks(
    should_continue=should_continue,
    on_pause_check=sync_pause_check,
)

# Merge (no more event_tracking_callbacks - replaced by:
# - EventCaptureManager via AG2 hooks
# - PhaseExecutionManager via callbacks)
workflow_callbacks = merge_callbacks(ws_callbacks, tracking_callbacks, pause_callbacks)
```

**Delete**: `event_tracking_callbacks` (lines 319-488) - ~170 lines:
- `create_execution_event()` (lines 320-358)
- `on_agent_msg()` (lines 359-385)
- `on_code_exec()` (lines 387-399)
- `on_tool()` (lines 401-415)

### Task 6.5: Update StreamCapture Construction

**File**: `backend/execution/task_executor.py`

Remove `dag_tracker` and `mode` params:
```python
# BEFORE:
stream_capture = StreamCapture(
    websocket, task_id, send_ws_event,
    dag_tracker=dag_tracker, loop=loop, work_dir=task_work_dir,
    mode=mode
)

# AFTER:
stream_capture = StreamCapture(
    websocket, task_id, send_ws_event,
    loop=loop, work_dir=task_work_dir
)
```

---

## Cleanup Items
| Item | Lines Removed |
|------|--------------|
| StreamCapture detection methods | ~400 |
| task_executor event_tracking_callbacks | ~170 |
| StreamCapture state variables | ~15 |
| **Total** | **~585** |

## Verification
```bash
# StreamCapture has no detection
grep -c "_detect_\|dag_tracker\|planning_complete\|re\." backend/execution/stream_capture.py  # 0

# All modes pass callbacks
grep -c "callbacks=" backend/execution/task_executor.py  # Should appear for each mode

# No event_tracking_callbacks
grep -c "event_tracking_callbacks\|create_execution_event\|on_agent_msg\|on_code_exec" \
  backend/execution/task_executor.py  # 0

# HITL end-to-end still works
# planning-control still works
# one-shot still works (now with callback-driven tracking!)
# OCR/arxiv/enhance have basic tracking
```

## Files Modified
| File | Action |
|------|--------|
| `backend/execution/stream_capture.py` | Strip to relay only (~400 lines removed) |
| `backend/execution/task_executor.py` | Simplify callbacks, pass to all modes |
| `cmbagent/workflows/one_shot.py` | Accept callbacks parameter |
| `cmbagent/cmbagent.py` | Add callbacks to OCR/arxiv/enhance methods |
