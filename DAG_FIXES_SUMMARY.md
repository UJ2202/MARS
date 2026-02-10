# DAG Node Display Fixes - Complete Summary

## Issues Fixed

### 1. **Missing WebSocket Event (CRITICAL)**
**Problem:** HITL planning phase wasn't calling `invoke_planning_complete()`, so UI never received DAG structure.

**Fix:** Added callback invocation in `hitl_planning.py` (line 430-439)

### 2. **Wrong Event Ordering (CRITICAL)**
**Problem:** WebSocket events were sent BEFORE database nodes were created.

**Fix:** Reordered operations in both `planning.py` and `hitl_planning.py`:
```python
# CORRECT ORDER:
1. manager.update_current_node_metadata()  # Update planning node
2. manager.add_plan_step_nodes()           # Create DB nodes
3. context.callbacks.invoke_planning_complete()  # Send WebSocket events
4. return manager.complete()               # Mark phase complete
```

### 3. **Approval Node Created**
**Problem:** Callbacks created "human_review_plan" approval node that user didn't want.

**Fix:** Removed approval node creation from `callbacks.py` (lines 470-480, 448-456)

### 4. **Node Connection Bug**
**Problem:** `add_plan_step_nodes()` received string "planning" but tried UUID lookup, causing first step to never connect.

**Fix:** Changed parameter to `Optional[str]` and pass actual `manager._current_dag_node_id`

### 5. **Missing Plan Metadata**
**Problem:** Planning node didn't contain the plan details.

**Fix:** Added `update_current_node_metadata()` method and call it before creating step nodes

## Complete Flow (After Fixes)

```
PLANNING PHASE:
├── manager.start()
│   └── Creates "planning" DAG node (status: running) with UUID
├── ... AI generates plan ...
├── ... Human approves plan (HITL mode) ...
├── manager.update_current_node_metadata()
│   └── Updates planning node with: plan, num_steps, steps_summary
├── manager.add_plan_step_nodes(source_node=manager._current_dag_node_id)
│   ├── Creates step_1 node (UUID-xxx)
│   ├── Creates step_2 node (UUID-yyy)
│   ├── Creates step_N node (UUID-zzz)
│   ├── Creates terminator node (UUID-ttt)
│   ├── Creates edge: planning → step_1
│   ├── Creates edge: step_1 → step_2
│   └── Creates edge: step_N → terminator
├── context.callbacks.invoke_planning_complete()
│   ├── Sends WebSocket "dag_node_status_changed" (planning: running→completed)
│   └── Sends WebSocket "dag_updated" with nodes array + edges array
└── manager.complete()
    └── Updates planning node status=completed in database

CONTROL PHASE:
├── manager.start_step(1, description)
│   ├── Updates step_1 node status=running
│   └── Sends WebSocket "dag_node_status_changed" (step_1: pending→running)
├── ... AI executes step ...
├── manager.complete_step(1, summary)
│   ├── Updates step_1 node status=completed
│   └── Sends WebSocket "dag_node_status_changed" (step_1: running→completed)
└── ... repeat for remaining steps ...
```

## WebSocket Events Format

**Event 1: dag_updated** (sent after planning completes)
```json
{
  "event_type": "dag_updated",
  "run_id": "task-123",
  "data": {
    "nodes": [
      {"id": "planning", "label": "HITL Planning", "type": "planning", "status": "completed"},
      {"id": "step_1", "label": "Step 1: ...", "type": "agent", "agent": "engineer", "description": "..."},
      {"id": "step_2", "label": "Step 2: ...", "type": "agent", "agent": "researcher", "description": "..."},
      {"id": "terminator", "label": "Completion", "type": "terminator", "status": "pending"}
    ],
    "edges": [
      {"source": "planning", "target": "step_1"},
      {"source": "step_1", "target": "step_2"},
      {"source": "step_2", "target": "terminator"}
    ]
  }
}
```

**Event 2: dag_node_status_changed** (sent during execution)
```json
{
  "event_type": "dag_node_status_changed",
  "run_id": "task-123",
  "data": {
    "node_id": "step_1",
    "old_status": "pending",
    "new_status": "running",
    "step_number": 1,
    "goal": "...",
    "timestamp": "2026-02-10T..."
  }
}
```

## Database vs WebSocket IDs

**Important:** There are TWO different ID systems:

1. **Database IDs:** UUIDs like `"550e8400-e29b-41d4-a716-446655440000"`
   - Used in `DAGNode.id`, `DAGEdge.from_node_id`, `DAGEdge.to_node_id`
   - Backend only

2. **WebSocket IDs:** Simple strings like `"planning"`, `"step_1"`, `"step_2"`
   - Used in WebSocket events
   - UI visualization only

The UI receives simple string IDs via WebSocket for display, but the backend tracks everything with UUIDs.

## Files Modified

1. **cmbagent/phases/execution_manager.py**
   - Added `update_current_node_metadata()` method
   - Fixed `add_plan_step_nodes()` parameter and logic

2. **cmbagent/phases/hitl_planning.py**
   - Reordered: metadata update → DB nodes → WebSocket event
   - Added `invoke_planning_complete()` callback

3. **cmbagent/phases/planning.py**
   - Reordered: metadata update → DB nodes → WebSocket event

4. **cmbagent/phases/copilot_phase.py**
   - Same reordering fix

5. **cmbagent/callbacks.py**
   - Removed `human_review_plan` approval node
   - Simplified edge creation

## Testing

Run your HITL workflow and verify:
- ✅ Planning node appears immediately
- ✅ All step nodes appear after plan approval
- ✅ Nodes show descriptions, goals, agents
- ✅ Edges connect planning → step_1 → step_2 → ...
- ✅ No approval node
- ✅ Step status updates as execution progresses

## If Still Not Working

Check these:
1. **Are WebSocket events being received?** (Check browser DevTools → Network → WS)
2. **Is the UI subscribed to the correct run_id?**
3. **Are there any CORS or connection issues?**
4. **Check backend logs for "Created step node" messages**

The database nodes ARE being created now (with the fixes). If they're still not showing, the issue is likely in the UI not receiving or processing the WebSocket events correctly.
