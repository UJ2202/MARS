# Database and Event Flow Analysis

## Executive Summary

**CRITICAL FINDING**: Events show "✓ Created" in console logs but have 0 database records. The `run_id` being used (`task_1768904279349_a64oayyk2`) does NOT exist in the `workflow_runs` table, causing foreign key constraint violations and silent failures.

## Database Schema (SQLAlchemy Models)

### 1. Core Tables

#### Session
- **Purpose**: User session isolation
- **Primary Key**: `id` (String UUID)
- **Key Fields**: `user_id`, `name`, `status`, `created_at`, `last_active_at`
- **Relationships**: One-to-many with WorkflowRun, DAGNode, ExecutionEvent

#### WorkflowRun  
- **Purpose**: Single workflow execution container
- **Primary Key**: `id` (String UUID)
- **Foreign Keys**: 
  - `session_id` → `sessions.id` (CASCADE DELETE)
  - `project_id` → `projects.id` (SET NULL)
- **Key Fields**:
  - `mode`: one_shot, planning_control, deep_research
  - `agent`: engineer, researcher, etc.
  - `status`: draft, planning, executing, paused, completed, failed
  - `started_at`: **TIMESTAMP** (nullable, used for ordering)
  - `completed_at`: TIMESTAMP (nullable)
  - `task_description`: TEXT
- **Relationships**: 
  - One-to-many: DAGNode, ExecutionEvent, WorkflowStep, File, Message
- **Indexes**: `(session_id, status)`, `(agent, status)`

#### DAGNode
- **Purpose**: Node in directed acyclic graph representing workflow stages
- **Primary Key**: `id` (String UUID OR reusable names like "step_1", "planning")
- **Foreign Keys**:
  - `run_id` → `workflow_runs.id` (CASCADE DELETE) **CRITICAL**
  - `session_id` → `sessions.id` (CASCADE DELETE)
- **Key Fields**:
  - `node_type`: planning, control, agent, approval, parallel_group, terminator
  - `status`: pending, running, completed, failed, skipped
  - `order_index`: Integer for sequencing
  - `meta`: JSON metadata
- **Relationships**:
  - One-to-many: ExecutionEvent, File, Message
  - DAGEdge (incoming/outgoing)
- **Indexes**: `(run_id, order_index)`, `(node_type, status)`
- **❌ NO created_at or started_at field** - auto-detection uses WorkflowRun.started_at via join

#### ExecutionEvent
- **Purpose**: Fine-grained execution tracking (THE PROBLEM AREA)
- **Primary Key**: `id` (String UUID)
- **Foreign Keys** (ALL CRITICAL):
  - `run_id` → `workflow_runs.id` (CASCADE DELETE) **MUST EXIST**
  - `node_id` → `dag_nodes.id` (CASCADE DELETE, nullable)
  - `step_id` → `workflow_steps.id` (SET NULL, nullable)
  - `session_id` → `sessions.id` (CASCADE DELETE) **MUST EXIST**
  - `parent_event_id` → `execution_events.id` (SET NULL, nullable, self-referential)
- **Key Fields**:
  - `event_type`: agent_call, tool_call, code_exec, file_gen, handoff, error
  - `event_subtype`: start, complete, error, info, pending
  - `agent_name`: String (agent identifier)
  - `timestamp`: TIMESTAMP (default: now)
  - `started_at`, `completed_at`: TIMESTAMP (nullable)
  - `duration_ms`: Integer (nullable)
  - `execution_order`: Integer (sequence within node)
  - `depth`: Integer (nesting level, default 0)
  - `status`: pending, running, completed, failed, skipped
  - `inputs`, `outputs`, `meta`: JSON
  - `error_message`: TEXT
- **Relationships**:
  - Many-to-one: WorkflowRun, DAGNode, WorkflowStep, Session
  - One-to-many: File, Message (via event_id)
  - Self-referential: parent_event, child_events
- **Indexes**: 
  - `(run_id, execution_order)`
  - `(node_id, execution_order)`
  - `(event_type, event_subtype)`
  - `(session_id, timestamp)`
  - `(parent_event_id)`

### 2. Supporting Tables

#### WorkflowStep
- **Purpose**: Individual step within workflow run
- **Foreign Keys**: `run_id`, `session_id`
- **Relationships**: One-to-many ExecutionEvent, File, Message

#### File
- **Purpose**: Generated/used files
- **Foreign Keys**: `run_id`, `step_id`, `event_id`, `node_id`
- **Key Fields**: `file_path`, `file_type`, `size_bytes`, `created_at`

#### Message
- **Purpose**: Agent-to-agent communication
- **Foreign Keys**: `run_id`, `step_id`, `event_id`, `node_id`
- **Key Fields**: `sender`, `recipient`, `content`, `timestamp`, `tokens`

## Data Flow: Event Capture to Database

### Step 1: Workflow Initialization
```python
# Location: cmbagent/cmbagent.py line ~1296
# CRITICAL FIX ADDED:
if cmbagent.use_database and cmbagent.workflow_repo:
    run = cmbagent.workflow_repo.create_run(
        mode="planning_control",
        agent="planner",
        model=planner_model,
        status="planning",
        task_description=task,
        meta={...}
    )
    # run.id = generated UUID
    # run.started_at = None (not set yet!)
```

**Problem**: `started_at` is NULLABLE and NOT set during `create_run()`!

### Step 2: DAG Nodes Created
```python
# Location: cmbagent/execution/dag_manager.py
# Creates nodes like:
dag_node = DAGNode(
    id="step_1",  # ← Reusable name OR UUID
    run_id=run_id,  # ← Must match WorkflowRun.id
    session_id=session_id,
    node_type="agent",
    status="pending",
    order_index=1,
    meta={}
)
db.add(dag_node)
db.commit()
```

**Key Point**: `node_id` can be a name ("step_1") used across multiple runs.

### Step 3: Event Capture Initiated
```python
# Location: cmbagent/execution/event_capture.py
class EventCaptureManager:
    def __init__(self, db_session, run_id, session_id, ...):
        self.run_id = run_id  # ← Stores the run_id
        self.current_node_id = None  # ← Set via set_context()
        self.event_repo = EventRepository(db_session, session_id)
```

### Step 4: Events Created
```python
# event_capture.py line ~506
def _create_event(self, event_type, ...):
    with self.buffer_lock:
        event = self.event_repo.create_event(
            run_id=self.run_id,  # ← THE CRITICAL FIELD
            node_id=self.current_node_id,
            step_id=self.current_step_id,
            event_type=event_type,
            ...
        )
        self.db.add(event)
        self.db.commit()  # ← Should persist to DB
        return event
```

### Step 5: EventRepository.create_event()
```python
# Location: cmbagent/database/repository.py line ~408
def create_event(self, run_id, node_id=None, ...):
    event = ExecutionEvent(
        run_id=run_id,  # ← Foreign key to workflow_runs.id
        node_id=node_id,  # ← Foreign key to dag_nodes.id
        session_id=self.session_id,  # ← Foreign key to sessions.id
        ...
    )
    self.db.add(event)
    self.db.commit()  # ← FAILS SILENTLY if run_id doesn't exist!
    self.db.refresh(event)
    return event
```

## THE PROBLEM

### Root Cause Analysis

1. **WorkflowRun Creation**:
   ```python
   run = workflow_repo.create_run(
       mode="planning_control",
       agent="planner",
       model=planner_model,
       status="planning",  # ← Status set
       task_description=task,
       # started_at NOT SET!
   )
   ```
   Result: `run.id` exists BUT `run.started_at` = NULL

2. **Event Capture Uses run_id**:
   ```
   ✓ Created agent_call event for assistant @ node step_1 (order: 3)
   ```
   This prints BEFORE `db.commit()`!

3. **Foreign Key Constraint Check**:
   - SQLite with `PRAGMA foreign_keys = ON`: Would fail immediately
   - SQLite WITHOUT foreign keys enabled: Allows invalid references!
   - PostgreSQL: Would fail immediately with FK violation

4. **API Query Failure**:
   ```python
   # backend/main.py
   query = db.query(ExecutionEvent).filter(
       ExecutionEvent.node_id == node_id,
       ExecutionEvent.run_id == run_id  # ← Filters correctly
   )
   events = query.all()  # ← Returns [] if run_id doesn't exist or events weren't committed
   ```

### Evidence from Logs

```
✓ Created WorkflowRun 1234-uuid-5678 in database  # ← WorkflowRun exists
✓ Created agent_call event for assistant @ node step_1 (order: 3)  # ← Print statement
[API] Raw events for node step_1: 0  # ← But database query finds nothing!
```

**Diagnosis**: Either:
1. `db.commit()` is failing silently (foreign key violation)
2. Events are being created in a DIFFERENT database session
3. Transaction rollback happening somewhere
4. Database isolation issue (events visible in one session, not another)

### Verification Commands

```python
# Check if WorkflowRun exists
run = db.query(WorkflowRun).filter(WorkflowRun.id == "task_1768904279349_a64oayyk2").first()
print(f"Run exists: {run is not None}")  # ← FALSE = ROOT CAUSE

# Check events
events = db.query(ExecutionEvent).filter(ExecutionEvent.run_id == "task_1768904279349_a64oayyk2").all()
print(f"Events: {len(events)}")  # ← 0 because FK constraint violated or never committed
```

## Database Query Patterns

### 1. API Endpoint: Get Node Events
```python
# backend/main.py line ~2318
@app.get("/api/nodes/{node_id}/events")
async def get_node_events(node_id: str, run_id: Optional[str] = None):
    # Auto-detect run_id from most recent node
    if not run_id:
        dag_node = db.query(DAGNode).join(WorkflowRun).filter(
            DAGNode.id == node_id
        ).order_by(WorkflowRun.started_at.desc()).first()  # ← Uses started_at!
        
        if dag_node:
            run_id = dag_node.run_id
    
    # Query events
    query = db.query(ExecutionEvent).filter(
        ExecutionEvent.node_id == node_id
    )
    if run_id:
        query = query.filter(ExecutionEvent.run_id == run_id)
    
    events = query.order_by(ExecutionEvent.execution_order).all()
```

**Problem**: `WorkflowRun.started_at` is NULL, so `.order_by(WorkflowRun.started_at.desc())` may not work correctly!

### 2. API Endpoint: Get Run History
```python
# backend/main.py line ~2103
@app.get("/api/runs/{run_id}/history")
async def get_run_history(run_id: str):
    query = db.query(ExecutionEvent).filter(
        ExecutionEvent.run_id == run_id
    )
    events = query.order_by(ExecutionEvent.execution_order).all()
    # Filter out 'start' subtypes
    filtered_events = [
        e for e in events 
        if e.event_subtype != 'start' and e.event_type not in ['node_started', 'node_completed']
    ]
    return {"events": filtered_events}
```

## Required Fixes

### Fix 1: Set started_at During WorkflowRun Creation
```python
# cmbagent/cmbagent.py line ~1296
from datetime import datetime, timezone

run = cmbagent.workflow_repo.create_run(
    mode="planning_control",
    agent="planner",
    model=planner_model,
    status="planning",
    started_at=datetime.now(timezone.utc),  # ← ADD THIS
    task_description=task,
    meta={...}
)
```

### Fix 2: Verify Foreign Key Constraints
```python
# Check database settings
# SQLite: PRAGMA foreign_keys = ON;
# PostgreSQL: Foreign keys enabled by default
```

### Fix 3: Add Transaction Logging
```python
# event_capture.py
try:
    event = ExecutionEvent(...)
    self.db.add(event)
    self.db.commit()
    print(f"✓ COMMITTED event {event.id} to database")
except Exception as e:
    print(f"✗ FAILED to commit event: {e}")
    self.db.rollback()
    raise
```

### Fix 4: Verify run_id Exists Before Creating Events
```python
# event_capture.py __init__
def __init__(self, db_session, run_id, session_id, ...):
    # Verify run exists
    run = db_session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        raise ValueError(f"WorkflowRun {run_id} does not exist in database!")
    
    self.run_id = run_id
    ...
```

## Summary

| Component | Status | Issue |
|-----------|--------|-------|
| WorkflowRun Creation | ✓ Fixed | Added in cmbagent.py, but `started_at` still NULL |
| DAGNode Creation | ✓ Works | Nodes are persisted correctly |
| Event Capture | ❌ Broken | Events print "Created" but not in database |
| Foreign Keys | ❓ Unknown | May not be enforced (SQLite) |
| API Queries | ✓ Correct | Logic is correct, just no data to return |

**Next Steps**:
1. Add `started_at=datetime.now(timezone.utc)` to `create_run()` call
2. Enable foreign key constraints in SQLite/verify in PostgreSQL
3. Add try/catch around `db.commit()` with logging
4. Verify `run_id` exists before initializing `EventCaptureManager`
