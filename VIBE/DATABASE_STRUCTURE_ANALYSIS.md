# Database Structure Analysis - January 20, 2026

## Complete Database Schema

### Entity Counts
- **Sessions**: 123
- **WorkflowRuns**: 265
- **DAGNodes**: 153 (142 UUID-based, 11 name-based)
- **ExecutionEvents**: 635 (587 with node_id, 48 without)
- **DAGEdges**: 68
- **Files**: 31
- **Messages**: 3

## Data Hierarchy

```
Session (user isolation)
  └── WorkflowRun (one task execution)
        ├── Attributes:
        │     ├── id (run_id): UUID - UNIQUE per execution
        │     ├── session_id: links to Session
        │     ├── status: draft, planning, executing, completed, failed
        │     ├── mode: one_shot, planning_control, etc.
        │     └── agent: engineer, researcher, etc.
        │
        ├── DAGNode (workflow stages)
        │     ├── id: UUID or NAME ("step_1", "planning", "terminator")
        │     ├── run_id: links to parent WorkflowRun
        │     ├── session_id: same as WorkflowRun
        │     ├── node_type: planning, control, agent, terminator
        │     ├── status: pending, running, completed, failed
        │     └── ⚠️ ISSUE: node_id NOT globally unique!
        │
        ├── ExecutionEvent (fine-grained execution tracking)
        │     ├── id: UUID - always unique
        │     ├── run_id: links to WorkflowRun
        │     ├── node_id: links to DAGNode.id (but NOT unique!)
        │     ├── session_id: links to Session
        │     ├── event_type: agent_call, tool_call, code_exec, file_gen
        │     ├── event_subtype: start, complete, execution, message
        │     ├── parent_event_id: for nested events
        │     └── ⚠️ ISSUE: (node_id alone) doesn't uniquely identify node!
        │
        ├── File (generated artifacts)
        │     ├── run_id: links to WorkflowRun
        │     ├── node_id: links to DAGNode.id
        │     └── event_id: links to ExecutionEvent that created it
        │
        └── Message (agent communications)
              ├── run_id: links to WorkflowRun
              ├── node_id: links to DAGNode.id
              └── event_id: links to ExecutionEvent
```

## Critical Problems Identified

### Problem 1: Non-Unique node_id Across Runs

**Evidence**:
```
Node: "step_1"
- Used in: 35 different WorkflowRuns
- Total events: 454 events
- Distribution: 14-16 events per run

Node: "planning"
- Used in: 35 different WorkflowRuns
- Total events: 35 events (1 per run)

Node: "terminator"
- Used in: 42 different WorkflowRuns
- Total events: 42 events (1 per run)
```

**Root Cause**: DAGNode IDs are generated as:
- **UUID-style**: `05902e3b-e25f-47b3-804c-7ca6405c182c` (unique, good)
- **Name-style**: `"step_1"`, `"planning"`, `"terminator"` (reused, bad)

The system uses **name-based IDs** for standard workflow stages, which get **reused across every workflow execution**.

### Problem 2: API Queries Return Mixed Data

**Current Behavior**:
```http
GET /api/nodes/step_1/events
```

**Returns**: 454 events from 35 DIFFERENT workflow runs
- Events from run A (14 events)
- Events from run B (14 events)
- Events from run C (16 events)
- ... (32 more runs)

**User Experience**:
1. User runs workflow A
2. DAG shows node "step_1"  
3. User clicks on "step_1"
4. UI fetches `/api/nodes/step_1/events`
5. **UI shows events from 35 different runs mixed together!**
6. Timeline displays **wrong data from other people's tasks**

### Problem 3: Foreign Key Without Uniqueness Constraint

**Database Schema**:
```sql
CREATE TABLE execution_events (
    id UUID PRIMARY KEY,
    node_id VARCHAR,  -- ⚠️ Not a proper FK, can be name or UUID
    run_id UUID FOREIGN KEY,
    ...
);

CREATE TABLE dag_nodes (
    id VARCHAR PRIMARY KEY,  -- ⚠️ Can be reused across runs!
    run_id UUID FOREIGN KEY,
    ...
);
```

**Issue**: `ExecutionEvent.node_id` references `DAGNode.id`, but `DAGNode.id` is not globally unique. The **composite key should be (node_id, run_id)**.

## Solution

### Fix 1: Add run_id to API Queries (REQUIRED)

**Change API Endpoints**:

**Before** (WRONG):
```http
GET /api/nodes/{node_id}/events
```

**After** (CORRECT):
```http
GET /api/nodes/{node_id}/events?run_id={run_id}
```

Or restructure as:
```http
GET /api/runs/{run_id}/nodes/{node_id}/events
```

**Backend Changes Required**:
```python
# OLD (returns mixed data)
events = db.query(ExecutionEvent).filter(
    ExecutionEvent.node_id == node_id
).all()

# NEW (returns correct data)
events = db.query(ExecutionEvent).filter(
    ExecutionEvent.node_id == node_id,
    ExecutionEvent.run_id == run_id  # ✓ Filter by run!
).all()
```

### Fix 2: Update UI to Pass run_id

**UI Changes Required**:

The DAG visualization component must track and pass the `run_id`:

```typescript
// When DAG is created, store run_id
const dagData = { 
  run_id: "current-run-uuid",
  nodes: [...],
  edges: [...]
};

// When node is clicked
onNodeClick(node) {
  const api_url = `/api/runs/${dagData.run_id}/nodes/${node.id}/events`;
  fetchEvents(api_url);
}
```

### Fix 3: Filter node_id + run_id Everywhere

**All these need updating**:

1. `GET /api/nodes/{node_id}/events` → Add `?run_id=` parameter
2. `GET /api/nodes/{node_id}/execution-summary` → Add `?run_id=`
3. `GET /api/nodes/{node_id}/files` → Add `?run_id=`
4. `GET /api/events/{event_id}/tree` → Already correct (event_id is unique)
5. `DAGMetadataEnricher.enrich_node()` → Add run_id parameter

### Fix 4: Update EventRepository (OPTIONAL)

Add a method that enforces run_id filtering:

```python
def list_events_for_node_in_run(
    self, 
    node_id: str, 
    run_id: str,
    event_type: Optional[str] = None
) -> List[ExecutionEvent]:
    """
    List events for a specific node in a specific run.
    This is the CORRECT way to query events by node.
    """
    query = self.db.query(ExecutionEvent).filter(
        ExecutionEvent.node_id == node_id,
        ExecutionEvent.run_id == run_id  # ✓ Must have both!
    )
    
    if event_type:
        query = query.filter(ExecutionEvent.event_type == event_type)
    
    return query.order_by(ExecutionEvent.execution_order).all()
```

## Testing the Fix

### Before Fix:
```python
# Query by node_id only
events = db.query(ExecutionEvent).filter(
    ExecutionEvent.node_id == "step_1"
).all()
# Returns: 454 events from 35 runs ❌
```

### After Fix:
```python
# Query by node_id AND run_id
events = db.query(ExecutionEvent).filter(
    ExecutionEvent.node_id == "step_1",
    ExecutionEvent.run_id == "4870fb7a-4d8a-4e1d-8ee8-78091fbacc08"
).all()
# Returns: 1 event from this specific run ✓
```

## Long-Term Solution

### Option 1: Always Use UUID for node_id
Stop using name-based node IDs. Always generate UUIDs for DAGNode.id.

**Pros**: node_id becomes globally unique
**Cons**: Loses human-readable names

### Option 2: Add Composite Primary Key
Change DAGNode schema:
```sql
CREATE TABLE dag_nodes (
    id VARCHAR,
    run_id UUID,
    PRIMARY KEY (id, run_id),  -- Composite key
    ...
);
```

**Pros**: Enforces uniqueness at database level
**Cons**: Requires schema migration, FK changes

### Option 3: Keep Current + Always Filter by run_id (RECOMMENDED)
Keep the current schema but enforce run_id filtering in all queries.

**Pros**: No schema changes, backward compatible
**Cons**: Developers must remember to filter by run_id

## Summary

**Data Structure**:
- 265 WorkflowRuns with unique run_ids
- 153 DAGNodes (some with reused IDs like "step_1")
- 635 ExecutionEvents linked to nodes via non-unique node_id

**The Bug**:
- Querying by `node_id` alone returns events from multiple runs
- UI shows mixed data from unrelated workflows
- User sees events from other people's tasks

**The Fix**:
- Add `run_id` parameter to ALL API endpoints that query by node_id
- Update UI to pass `run_id` when fetching node events
- Filter ExecutionEvents by BOTH `node_id` AND `run_id`

**Impact**:
- Backend: 5 API endpoints + 1 repository method
- UI: 2 components (DAGVisualization, NodeActionDialog)
- Testing: Verify events match expected run only
