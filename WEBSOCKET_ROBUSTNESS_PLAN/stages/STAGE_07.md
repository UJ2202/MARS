# Stage 7: Output Channel Routing

**Phase:** 2 - Execution Isolation
**Dependencies:** Stage 6 (IsolatedTaskExecutor)
**Risk Level:** Medium
**Estimated Time:** 3-4 hours

## Objectives

1. Enhance output routing from subprocess to WebSocket
2. Add DAG tracking support for isolated execution
3. Implement cost tracking via output events
4. Handle session state serialization for each output batch

## Implementation Tasks

### Task 1: Enhance Output Event Types

**File to Modify:** `backend/execution/isolated_executor.py`

Add structured event types for different output categories:

```python
# Add to _run_task_in_subprocess:

def send_dag_event(event_type: str, data: Dict[str, Any]):
    """Send DAG-related events"""
    send_output(f"dag_{event_type}", data)

def send_cost_event(model: str, input_tokens: int, output_tokens: int, cost: float):
    """Send cost tracking event"""
    send_output("cost_update", {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

def send_phase_event(phase: str, step: Optional[int] = None):
    """Send phase change event"""
    send_output("phase_change", {
        "phase": phase,
        "step": step,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
```

### Task 2: DAG Tracking in Subprocess

For DAG visualization, nodes must be created and updated from the subprocess:

```python
# In _execute_cmbagent_task:

def create_dag_for_mode(mode: str, task: str, config: Dict) -> Dict:
    """Create DAG structure for visualization"""
    if mode == "one-shot":
        return {
            "nodes": [
                {"id": "start", "label": "Start", "type": "start", "status": "pending"},
                {"id": "execute", "label": "Execute", "type": "agent", "status": "pending"},
                {"id": "end", "label": "End", "type": "end", "status": "pending"}
            ],
            "edges": [
                {"source": "start", "target": "execute"},
                {"source": "execute", "target": "end"}
            ]
        }
    elif mode == "planning-control":
        return {
            "nodes": [
                {"id": "start", "label": "Start", "type": "start", "status": "pending"},
                {"id": "planning", "label": "Planning", "type": "phase", "status": "pending"},
                {"id": "execution", "label": "Execution", "type": "phase", "status": "pending"},
                {"id": "end", "label": "End", "type": "end", "status": "pending"}
            ],
            "edges": [
                {"source": "start", "target": "planning"},
                {"source": "planning", "target": "execution"},
                {"source": "execution", "target": "end"}
            ]
        }
    # ... add other modes
    return {"nodes": [], "edges": []}

# At start of execution:
dag = create_dag_for_mode(mode, task, config)
send_output("dag_created", dag)

# Update node status during execution:
def update_dag_node(node_id: str, status: str, **kwargs):
    send_output("dag_node_update", {
        "node_id": node_id,
        "status": status,
        **kwargs
    })

update_dag_node("start", "completed")
update_dag_node("execute", "running")
# ... after completion:
update_dag_node("execute", "completed")
update_dag_node("end", "completed")
```

### Task 3: Session State Periodic Save

Add periodic state saving during execution:

```python
# In main process monitor loop:

async def _monitor_subprocess(self, task_id, process, output_queue, result_queue,
                              output_callback, session_id=None):
    last_save_time = time.time()
    SAVE_INTERVAL = 30  # seconds

    while True:
        # ... existing output handling ...

        # Periodic state save
        if session_id and time.time() - last_save_time > SAVE_INTERVAL:
            # Collect state from recent events and save
            # This would require accumulating conversation history
            last_save_time = time.time()
```

### Task 4: Update Main Process Event Handling

**File to Modify:** `backend/execution/task_executor.py`

```python
async def _execute_isolated(websocket, task_id, task, config):
    """Execute with enhanced event handling"""

    executor = get_isolated_executor()
    session_id = config.get("session_id")
    session_manager = get_session_manager() if session_id else None
    conversation_buffer = []

    async def output_callback(event_type: str, data: Dict[str, Any]):
        """Forward and process subprocess output"""

        # Forward to WebSocket
        await send_ws_event(websocket, event_type, data, run_id=task_id)

        # Track conversation for session save
        if event_type == "output" and session_id:
            conversation_buffer.append({
                "role": "system",
                "content": data.get("message", ""),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        # Handle special event types
        if event_type == "phase_change" and session_manager:
            session_manager.save_session_state(
                session_id=session_id,
                conversation_history=conversation_buffer[-100:],  # Keep last 100
                context_variables=data.get("context", {}),
                current_phase=data.get("phase"),
                current_step=data.get("step")
            )

    try:
        result = await executor.execute(
            task_id=task_id,
            task=task,
            config=config,
            output_callback=output_callback
        )

        # Final state save
        if session_manager:
            session_manager.save_session_state(
                session_id=session_id,
                conversation_history=conversation_buffer,
                context_variables=result.get("context", {}),
                current_phase="completed"
            )
            session_manager.complete_session(session_id)

        await send_ws_event(websocket, "result", result, run_id=task_id)
        await send_ws_event(websocket, "complete", {"status": "success"}, run_id=task_id)

    except Exception as e:
        if session_manager:
            session_manager.suspend_session(session_id)

        await send_ws_event(websocket, "error", {
            "message": str(e),
            "error_type": type(e).__name__
        }, run_id=task_id)
```

## Verification Criteria

### Must Pass
- [ ] DAG events route correctly to frontend
- [ ] Cost tracking events received
- [ ] Phase changes trigger state saves
- [ ] Output buffer doesn't grow unbounded

### Test Script
```python
# test_stage_7.py
import asyncio
from backend.execution.isolated_executor import IsolatedTaskExecutor

async def test_output_routing():
    executor = IsolatedTaskExecutor()

    events_by_type = {}

    async def callback(event_type, data):
        if event_type not in events_by_type:
            events_by_type[event_type] = []
        events_by_type[event_type].append(data)

    await executor.execute(
        task_id="routing_test",
        task="Test task",
        config={"mode": "one-shot"},
        output_callback=callback
    )

    # Verify event types received
    assert "output" in events_by_type
    assert "dag_created" in events_by_type or "status" in events_by_type
    print(f"✅ Received event types: {list(events_by_type.keys())}")

if __name__ == "__main__":
    asyncio.run(test_output_routing())
```

## Success Criteria

Stage 7 is complete when:
1. ✅ All output types route correctly
2. ✅ DAG events visualize in frontend
3. ✅ Session state saves on phase changes
4. ✅ No memory leaks from output buffering

## Next Stage

Once Stage 7 is verified complete, proceed to:
**Stage 8: Logging Configuration**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-11
