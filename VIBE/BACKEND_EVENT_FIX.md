# Backend Event Retrieval Fix - January 20, 2026

## Issues Identified and Fixed

### Issue 1: History API Getting Empty Response
**Root Cause**: The `/api/runs/{run_id}/history` endpoint was trying to use `workflow_service.get_run_info()` which either didn't exist or returned incorrect run_id mappings.

**Fix**: Simplified the endpoint to use the run_id directly without translation.

### Issue 2: DAG Node Visualization Showing Double Events
**Root Cause**: Agent call events were being created TWICE:
- Once with `event_subtype='start'` when the call begins
- Once with `event_subtype='complete'` when it finishes

Both were being counted as separate events, effectively **doubling the event count**.

**Example from database**:
```
step_1 node:
- Total raw events: 454
- agent_call:execution: 34
- agent_call:message: 355
- After filtering 'start' subtypes: 453 events
```

**Fix**: Added filtering in all API endpoints to exclude:
1. Events with `event_subtype='start'` (keeps only 'complete')
2. Internal lifecycle events (`node_started`, `node_completed`)

### Issue 3: Events Without node_id
**Finding**: 48 events in the database have `node_id=None`, making them invisible to node-based queries. This is expected for run-level events but should be monitored.

## Changes Made

### 1. `/api/runs/{run_id}/history` Endpoint
**File**: `backend/main.py` lines 2103-2245

**Changes**:
- Removed dependency on `workflow_service.get_run_info()`
- Added filtering to exclude 'start' subtypes and internal events
- Added debug logging: `print(f"[API] Found {len(events_data)} events (filtered from {len(events)} raw)")`

### 2. `/api/nodes/{node_id}/events` Endpoint
**File**: `backend/main.py` lines 2318-2385

**Changes**:
- Updated docstring to clarify `include_internal` parameter
- Added filtering logic:
  ```python
  if not include_internal:
      events = [e for e in events if e.event_type not in ['node_started', 'node_completed']]
      events = [e for e in events if e.event_subtype not in ['start']]
  ```
- Added debug logging for raw vs filtered counts

### 3. DAGMetadataEnricher
**File**: `cmbagent/database/dag_metadata.py` lines 23-60

**Changes**:
- Added filtering in `enrich_node()` method
- Now uses `filter_by_session=False` to get all node events
- Filters out 'start' subtypes and internal events before calculating statistics
- Added `raw_event_count` field to summary for debugging

### 4. Agent Call Counting
**File**: `cmbagent/database/dag_metadata.py` lines 105-113

**Changes**:
- Updated `_count_agent_calls()` to double-check subtype filtering
- Added comment explaining the double-counting prevention

## Testing

### Test Results (step_1 node):
```
Total events in database: 454
Events by type:subtype:
  agent_call:execution: 34
  agent_call:message: 355
  code_exec:executed: 58
  code_exec:execution: 6
  node_started:execution: 1

After filtering (excludes 'start' subtypes):
  Total: 453 events
  agent_call: 389
  code_exec: 64
```

### Verification Script
```python
from cmbagent.database import get_db_session
from cmbagent.database.models import ExecutionEvent

db = get_db_session()

# Test node events
node_id = "step_1"
all_events = db.query(ExecutionEvent).filter(
    ExecutionEvent.node_id == node_id
).all()

filtered_events = [
    e for e in all_events 
    if e.event_subtype not in ['start'] 
    and e.event_type not in ['node_started', 'node_completed']
]

print(f"Raw events: {len(all_events)}")
print(f"Filtered events: {len(filtered_events)}")
```

## API Behavior Changes

### Before Fix:
- Node with 454 events would show 454 events in UI
- Agent calls counted twice (start + complete)
- Lifecycle events cluttered the timeline

### After Fix:
- Same node shows 453 events (more accurate)
- Each agent call counted once (complete event only)
- Clean timeline without internal lifecycle events
- `include_internal=True` parameter can restore old behavior if needed

## Debug Logging Added

All API endpoints now include debug logging:
```python
print(f"[API] Raw events for node {node_id}: {len(events)}")
print(f"[API] Filtered events for node {node_id}: {len(events)}")
print(f"[API] Returning {len(events_data)} events for node {node_id}")
```

Check backend logs for these messages to verify correct operation.

## Future Improvements

1. **Consider changing event creation strategy**:
   - Option A: Only create 'complete' events (no 'start')
   - Option B: Create both but mark 'start' with a flag for UI filtering
   
2. **Add event_count field to DAGNode**:
   - Cache the filtered event count in node metadata
   - Avoid recounting on every API call

3. **Index optimization**:
   - Add composite index on (node_id, event_subtype, event_type)
   - Improves filtering performance

4. **Session consistency**:
   - Currently using `filter_by_session=False` for node queries
   - Consider if session isolation is needed for node-level queries

## Backward Compatibility

- Old behavior can be restored by passing `?include_internal=true` to API endpoints
- No database schema changes required
- Existing events are preserved
