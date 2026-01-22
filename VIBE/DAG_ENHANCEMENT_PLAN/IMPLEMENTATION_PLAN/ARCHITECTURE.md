# CMBAgent Enhancement Architecture

## Executive Summary

This document outlines the architectural decisions and design principles for the CMBAgent enhancement project. The enhancements transform CMBAgent from a file-based sequential execution system into a modern, database-backed, parallel-capable multi-agent orchestration platform.

## Core Architectural Principles

### 1. Backward Compatibility First
- Existing workflows must continue to work without modification
- Gradual migration from pickle files to database
- Feature flags for all new functionality
- Dual-mode operation (legacy and enhanced)

### 2. Dual Persistence Strategy (Database + Pickle Files)
- **Database as Primary:** SQLite for simplicity, PostgreSQL-ready schema
- **Pickle Files as Secondary:** Continue writing pickle files in parallel
- **Rationale:** Pickle files may be useful for:
  - Future analysis and debugging
  - Quick context snapshots
  - Compatibility with external tools
  - Migration safety net
- **Strategy:** Dual-write to both DB and pickle, read from DB primarily
- Queryable execution history in database
- Atomic transactions for state changes in database

### 3. Event-Driven Architecture
- WebSocket events for all state changes
- Real-time UI updates
- Audit trail of all actions
- Event replay capability

### 4. Explicit State Management
- Formal state machine for workflows and steps
- Clear state transitions with guards
- State history tracking
- Resume from any valid state

### 5. Policy as Last Layer (Default: Allow All)
- Features implemented first without policy restrictions
- Policy enforcement added on top as optional layer
- **Default Policy: ALLOW ALL** - No restrictions by default
- Scientific discovery requires flexibility and experimentation
- Users can opt-in to stricter policies when needed
- Policy framework ready but not enforced unless explicitly configured
- Easy override for development and research workflows

### 6. Long-Running Workflow Support (Hours to Days)
- **Design for durability:** Workflows must survive hours/days of execution
- **Checkpoint frequently:** Save state every N minutes and after each step
- **Graceful interruption:** Support pause/resume at any point
- **Connection resilience:** WebSocket reconnection without losing context
- **Resource management:** Memory cleanup, file handle management
- **Progress persistence:** Database stores all progress, not just in-memory
- **Heartbeat monitoring:** Detect stalled workflows and enable recovery
- **Time-series tracking:** Log timestamps for performance analysis
- **Multi-day resume:** Can stop today, resume tomorrow without data loss

### 7. Multi-Session Isolation
- **Strict isolation:** Each session has isolated work directory
- **No cross-contamination:** Sessions cannot interfere with each other
- **Resource boundaries:** Per-session resource limits (disk, memory)
- **Database isolation:** Row-level security, session-scoped queries
- **File system isolation:** Separate directories per session
- **Concurrent execution:** Multiple sessions can run simultaneously
- **Independent lifecycle:** Pause/stop/resume per session independently
- **Session metadata:** Track owner, creation time, status per session

## System Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                             │
│  (Next.js + React + WebSocket Client)                       │
└─────────────────┬───────────────────────────────────────────┘
                  │ WebSocket + REST
┌─────────────────┴───────────────────────────────────────────┐
│                    API Gateway Layer                         │
│  (FastAPI + WebSocket Server + Auth Middleware)             │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────┴───────────────────────────────────────────┐
│                  Orchestration Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ State Machine│  │ DAG Executor │  │Approval Mgr  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────┴───────────────────────────────────────────┐
│                    Agent Layer (AG2)                         │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐            │
│  │Planner│ │Engineer│ │Researcher│ │Control│ │...50+ │     │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘            │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────┴───────────────────────────────────────────┐
│                  Integration Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  MCP Client  │  │  MCP Server  │  │Policy Engine │     │
│  │(External Tools)│ │(Expose CMB)  │  │    (OPA)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────┴───────────────────────────────────────────┐
│                   Persistence Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Database   │  │ File Storage │  │  Vector DB   │     │
│  │  (SQLite)    │  │(work_dir)    │  │   (RAG)      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow Architecture

### Workflow Execution Flow

```
1. User submits task via UI/CLI
   ↓
2. API Gateway creates workflow_run record in DB
   ↓
3. State Machine: DRAFT → PLANNING
   ↓
4. DAG Builder analyzes task → creates execution plan
   ↓
5. State Machine: PLANNING → EXECUTING
   ↓
6. DAG Executor processes nodes (sequential or parallel)
   │
   ├─ For each node:
   │   ├─ Check policy (OPA) - allow/deny
   │   ├─ State Machine: node PENDING → RUNNING
   │   ├─ Execute agent (AG2)
   │   ├─ Capture outputs, cost, logs
   │   ├─ If approval needed → WAITING_APPROVAL
   │   │   ├─ WebSocket event to UI
   │   │   ├─ Wait for human input
   │   │   ├─ Inject feedback into context
   │   │   └─ Resume execution
   │   ├─ If error → retry with context
   │   └─ State Machine: node RUNNING → COMPLETED/FAILED
   │
   └─ All nodes complete
      ↓
7. State Machine: EXECUTING → COMPLETED
   ↓
8. Generate reports, save artifacts
   ↓
9. WebSocket: workflow_complete event
```

### Real-Time Event Flow

```
Backend Event              WebSocket Message           UI Update
─────────────────────     ──────────────────────     ─────────────
workflow_started    →     {type: "workflow_started"} → Show progress
step_started        →     {type: "step_started"}     → Update DAG
agent_message       →     {type: "agent_message"}    → Console output
approval_needed     →     {type: "approval_needed"}  → Show dialog
cost_update         →     {type: "cost_update"}      → Update counter
step_completed      →     {type: "step_completed"}   → Mark node done
dag_updated         →     {type: "dag_updated"}      → Redraw graph
state_changed       →     {type: "state_changed"}    → Update status
error_occurred      →     {type: "error_occurred"}   → Show error
workflow_complete   →     {type: "workflow_complete"}→ Show results
```

## Database Architecture

### Entity Relationship Model

```
projects (1) ─────< (N) sessions (1) ─────< (N) workflow_runs
                                                      │
                                                      │ (1)
                                                      │
                                                      ├─< (N) workflow_steps
                                                      │         │
                                                      │         ├─< (N) messages
                                                      │         ├─< (N) checkpoints
                                                      │         └─< (N) files
                                                      │
                                                      ├─< (N) dag_nodes
                                                      │         │
                                                      │         └─< (N) dag_edges
                                                      │
                                                      ├─< (N) cost_records
                                                      │
                                                      ├─< (N) approval_requests
                                                      │
                                                      └─< (N) branches
```

### Key Tables

**projects:** High-level container for related work
**sessions:** User session within project (multiple runs)
**workflow_runs:** Single execution instance
**workflow_steps:** Individual steps within run
**dag_nodes:** Graph representation of workflow
**dag_edges:** Dependencies between nodes
**checkpoints:** State snapshots for resume
**approval_requests:** HITL approval tracking
**branches:** Alternative execution paths

## State Machine Architecture

### Workflow States

```
DRAFT → PLANNING → EXECUTING ⇄ PAUSED
          ↓           ↓
      CANCELLED  WAITING_APPROVAL
                      ↓
                 EXECUTING
                      ↓
               COMPLETED / FAILED
```

### Step States

```
PENDING → RUNNING ⇄ PAUSED
            ↓
     WAITING_APPROVAL
            ↓
         RUNNING
            ↓
    COMPLETED / FAILED / SKIPPED
```

### State Transition Rules

- DRAFT can only go to PLANNING or CANCELLED
- PLANNING can go to EXECUTING, FAILED, or CANCELLED
- EXECUTING can go to PAUSED, WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED
- PAUSED can only resume to EXECUTING
- WAITING_APPROVAL can only go to EXECUTING or CANCELLED
- COMPLETED and FAILED are terminal states

## DAG Execution Architecture

### Node Types

**PlanningNode:** Creates execution plan
**ControlNode:** Orchestrates steps
**AgentNode:** Executes agent task (engineer, researcher, etc.)
**ApprovalNode:** Human approval gate
**ParallelGroupNode:** Container for parallel tasks
**TerminatorNode:** Workflow end

### Parallel Execution Model

```
Sequential:
Node1 → Node2 → Node3 → Node4

Parallel with dependencies:
Node1 → [Node2, Node3, Node4] → Node5
        (parallel group)

Complex DAG:
         ┌→ Node2 ──┐
Node1 ───┼→ Node3 ──┼→ Node5 → Node6
         └→ Node4 ──┘

Execution groups:
Level 0: [Node1]
Level 1: [Node2, Node3, Node4]  # Execute in parallel
Level 2: [Node5]
Level 3: [Node6]
```

### Dependency Resolution

Uses topological sort to determine execution order:
1. Build directed graph from plan
2. Identify dependency-free nodes (level 0)
3. Execute level 0 (can be parallel if multiple nodes)
4. Remove completed nodes from graph
5. Repeat until all nodes executed

## Human-in-the-Loop Architecture

### Approval Flow

```
1. Agent reaches checkpoint requiring approval
2. Executor pauses and creates approval_request record
3. State changes to WAITING_APPROVAL
4. WebSocket event sent to UI with context
5. UI displays approval dialog with:
   - Current step context
   - Previous outputs
   - Proposed next action
   - Options: Approve / Reject / Modify
6. User provides feedback
7. Feedback injected into agent context
8. State changes back to EXECUTING
9. Execution resumes with enhanced context
```

### Approval Modes

**NONE:** No approvals (current behavior)
**AFTER_PLANNING:** Single approval after plan created
**BEFORE_EACH_STEP:** Approval before each major step
**ON_ERROR:** Approval only when errors occur
**MANUAL:** User can pause anytime and provide feedback

## Retry Architecture

### Context-Aware Retry

Traditional retry:
```
Agent executes → Fails → Retry same task
```

Enhanced retry:
```
Agent executes → Fails → Capture error context → Inject into retry
                                                   - What failed
                                                   - Error message
                                                   - Previous attempt
                                                   - Human feedback
                                                   - Suggestions
```

### Retry Context Structure

```python
{
    "attempt_number": 2,
    "max_attempts": 3,
    "previous_error": "FileNotFoundError: data.csv not found",
    "previous_output": "...",
    "human_feedback": "The file is actually named dataset.csv",
    "suggestions": [
        "Check file exists before loading",
        "Use correct filename"
    ],
    "failed_approach": "pandas.read_csv('data.csv')"
}
```

## MCP Integration Architecture

### MCP Server (Expose CMBAgent)

CMBAgent exposes itself as MCP server so other AI assistants can use CMBAgent agents as tools.

```
Claude Desktop ─(MCP)→ CMBAgent Server ─→ Execute Agent ─→ Return Result
                           ↓
                   50+ tools available:
                   - execute_one_shot()
                   - planning_and_control()
                   - query_camb_docs()
                   - use_engineer()
                   - use_researcher()
                   - etc.
```

### MCP Client (Use External Tools)

CMBAgent agents can call external MCP servers for additional capabilities.

```
CMBAgent Engineer ─→ MCP Client ─→ External MCP Servers:
                                    - Filesystem operations
                                    - GitHub API
                                    - Web search
                                    - Database queries
                                    - 50+ community servers
```

## Policy Enforcement Architecture

### Policy Check Flow

```
Agent requests action
    ↓
Policy Enforcer intercepts
    ↓
Query OPA with context:
  - Agent identity
  - Action type
  - Resource
  - User
  - Cost estimate
    ↓
OPA evaluates policies
    ↓
Returns: ALLOW / DENY + reason
    ↓
If ALLOW: execute action
If DENY: raise PermissionDenied
    ↓
Log policy decision to audit table
```

### Policy Decision Points

- Before file operations (read/write/delete)
- Before external API calls
- Before cost-heavy operations
- Before database modifications
- Before MCP tool invocations

### Policy Types

**Access Control:** Who can do what
**Cost Control:** Budget limits per user/agent/workflow
**Data Privacy:** Sensitive data access rules
**Compliance:** Regulatory requirements
**Rate Limiting:** Request throttling

### Default Policy Configuration

**Stage 15 Implementation:** Default to ALLOW ALL
```rego
# Default policy: Allow everything
package cmbagent.default

default allow = true  # Permissive by default

# Users can override by creating custom policies
# Scientific discovery requires flexibility
```

**Rationale:**
- Scientific workflows need experimentation freedom
- Restrictive policies can block legitimate research
- Users opt-in to stricter policies when needed
- Policy framework ready but not enforced by default

## Cost Tracking Architecture

### Cost Attribution Model

```
Total Cost
├─ By Project
│  └─ By Session
│     └─ By Workflow Run
│        └─ By Step
│           └─ By Agent
│              └─ By Model
```

### Real-Time Cost Tracking

- Intercept all LLM API calls
- Record: tokens, cost, model, timestamp
- Aggregate in real-time
- Stream updates to UI
- Alert on thresholds

### Budget Enforcement

Pre-execution check:
```python
estimated_cost = estimate_workflow_cost(plan)
if current_cost + estimated_cost > budget_limit:
    raise BudgetExceededError()
```

## Observability Architecture

### Three Pillars

**Logs:** Structured logging with correlation IDs
**Metrics:** Performance and usage metrics
**Traces:** Distributed tracing for workflows

### Trace Hierarchy

```
Workflow Span
├─ Planning Span
│  ├─ Planner Agent Span
│  └─ Plan Reviewer Span
├─ Control Span
│  ├─ Step 1 Span
│  │  ├─ Engineer Agent Span
│  │  └─ Executor Span
│  ├─ Step 2 Span
│  └─ Step 3 Span
└─ Finalization Span
```

## Long-Running Workflow Architecture (Hours to Days)

### Design Challenges

Scientific discovery workflows have unique requirements:
- **Duration:** Can run for hours, days, or even weeks
- **Interruption:** System restarts, network issues, power failures
- **Progress:** Must track and visualize progress over long periods
- **Resources:** Memory leaks and resource exhaustion over time
- **Human interaction:** Researchers may leave and return days later

### Durability Strategy

#### 1. Frequent Checkpointing
```
Timeline: ─────────────────────────────────────────>
          │     │     │     │     │     │     │
Checkpoint: t0    t1    t2    t3    t4    t5    t6
          (Plan)(Step1)(Step2)(Step3)(Step4)(Step5)(Done)

Checkpoint triggers:
- After each major step completion
- Every N minutes (configurable, default: 10 minutes)
- Before any risky operation (file deletion, API calls)
- On manual pause request
- On error/exception
```

**Implementation:**
```python
# Dual checkpoint strategy
checkpoint_manager.save({
    "database": True,      # Primary: structured data to DB
    "pickle": True,        # Secondary: full context snapshot
    "timestamp": now,
    "trigger": "step_complete"
})
```

#### 2. Graceful Interruption Handling

**SIGTERM/SIGINT Handler:**
```python
def graceful_shutdown(signum, frame):
    logger.info("Shutdown signal received")
    # 1. Save current state to database
    state_machine.transition_to(WorkflowState.PAUSED, "System shutdown")
    # 2. Write checkpoint (DB + pickle)
    checkpoint_manager.save_emergency_checkpoint()
    # 3. Close WebSocket connections gracefully
    websocket_manager.notify_all_clients("workflow_paused")
    # 4. Flush logs and close database connections
    cleanup_resources()
    sys.exit(0)
```

#### 3. Resume from Any Point

**Resume Flow:**
```
User: cmbagent resume <run_id>
  ↓
Load from database: workflow_runs WHERE id=<run_id>
  ↓
Check state: PAUSED → can resume
  ↓
Load checkpoint: most recent checkpoint for this run
  ↓
Restore context:
  - Shared variables
  - Agent states
  - Previous outputs
  - DAG execution status
  ↓
State transition: PAUSED → EXECUTING
  ↓
Resume from next pending node in DAG
```

#### 4. WebSocket Resilience

**Connection Loss Handling:**
```typescript
// Frontend: Automatic reconnection
const useResilientWebSocket = (runId) => {
  const [connectionStatus, setStatus] = useState('connected');

  useEffect(() => {
    let ws = new WebSocket(`/ws/${runId}`);
    let reconnectAttempts = 0;
    const maxAttempts = 999; // Essentially unlimited

    ws.onclose = () => {
      if (reconnectAttempts < maxAttempts) {
        setTimeout(() => {
          reconnectAttempts++;
          // Reconnect with exponential backoff
          ws = new WebSocket(`/ws/${runId}`);
        }, Math.min(1000 * Math.pow(2, reconnectAttempts), 30000));
      }
    };

    // On reconnect, fetch latest state from API
    ws.onopen = () => {
      fetchLatestWorkflowState(runId);
    };
  }, [runId]);
};
```

**Backend: Stateless WebSocket Handler:**
- No state in WebSocket connection
- All state in database
- Reconnection fetches latest state from DB
- New connection can pick up where old connection left off

#### 5. Progress Persistence

**Database-First Progress Tracking:**
```sql
-- Every action updates database immediately
UPDATE workflow_steps
SET status = 'running',
    started_at = NOW(),
    progress_percentage = 45
WHERE id = <step_id>;

-- Not stored in memory only!
-- UI queries database for latest progress
```

**Progress Broadcasting:**
```python
# After each operation
db.session.commit()  # Persist to database first
websocket.broadcast({
    "type": "progress_update",
    "step_id": step_id,
    "progress": 45,
    "message": "Training model (epoch 45/100)"
})
```

#### 6. Heartbeat Monitoring

**Detect Stalled Workflows:**
```python
# Background monitor daemon
class WorkflowHeartbeatMonitor:
    def run(self):
        while True:
            # Check for workflows in EXECUTING state
            active_runs = db.query(workflow_runs).filter(
                status == 'executing'
            ).all()

            for run in active_runs:
                last_update = run.last_heartbeat_at
                if now() - last_update > STALL_THRESHOLD:
                    # Workflow appears stalled
                    logger.warning(f"Workflow {run.id} stalled")
                    # Transition to PAUSED state
                    # Notify user via email/webhook
                    # Enable manual recovery

# Workflow sends heartbeat every minute
def workflow_heartbeat(run_id):
    db.update(workflow_runs, id=run_id, last_heartbeat_at=now())
```

#### 7. Resource Management

**Memory Cleanup:**
```python
# After each major step
def cleanup_step_resources(step_id):
    # Clear large objects from memory
    clear_agent_caches()
    # Python garbage collection
    import gc
    gc.collect()
    # Log memory usage
    import psutil
    memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
    db.log_metric("memory_usage_mb", memory_mb, step_id)
```

**File Handle Management:**
```python
# Use context managers for all file operations
with open(file_path) as f:
    data = f.read()
# File automatically closed

# Periodic file handle audit
def audit_file_handles():
    import psutil
    open_files = psutil.Process().open_files()
    if len(open_files) > THRESHOLD:
        logger.warning(f"Too many open files: {len(open_files)}")
```

#### 8. Time-Series Tracking

**Database Schema Addition:**
```sql
workflow_metrics (
    id, run_id, step_id, timestamp,
    metric_name, metric_value,
    metadata JSONB
)

-- Examples:
INSERT INTO workflow_metrics VALUES
  (1, 'run_123', 'step_5', '2026-01-14 10:00:00', 'memory_mb', 512, '{}'),
  (2, 'run_123', 'step_5', '2026-01-14 10:05:00', 'memory_mb', 768, '{}'),
  (3, 'run_123', 'step_5', '2026-01-14 10:10:00', 'memory_mb', 1024, '{}');

-- Query for time-series analysis
SELECT timestamp, metric_value
FROM workflow_metrics
WHERE run_id = 'run_123' AND metric_name = 'memory_mb'
ORDER BY timestamp;
```

#### 9. Multi-Day Resume Example

**Day 1:**
```
User starts workflow at 9 AM
  ↓
Planning completes at 9:15 AM
  ↓
Steps 1-5 execute (9:15 AM - 8:00 PM)
  ↓
User manually pauses: "Continue tomorrow"
  ↓
State → PAUSED, checkpoint saved
```

**Day 2:**
```
User runs: cmbagent resume run_abc123
  ↓
System loads checkpoint from database
  ↓
Restores: context, agent states, progress (5/10 steps done)
  ↓
State: PAUSED → EXECUTING
  ↓
Continues from step 6 (10:00 AM)
  ↓
Steps 6-10 execute, workflow completes (2:00 PM)
```

### Implementation Checklist

- [ ] Checkpoint manager with dual-write (DB + pickle)
- [ ] Graceful shutdown handlers (SIGTERM, SIGINT)
- [ ] Resume command: `cmbagent resume <run_id>`
- [ ] WebSocket auto-reconnection in UI
- [ ] Heartbeat monitoring daemon
- [ ] Resource cleanup after each step
- [ ] Time-series metrics table
- [ ] Progress persistence in database
- [ ] Stalled workflow detection
- [ ] Multi-day resume testing

## Multi-Session Isolation Architecture

### Isolation Requirements

CMBAgent must support:
- **Concurrent sessions:** Multiple researchers running workflows simultaneously
- **No interference:** Session A cannot access or modify Session B's data
- **Resource fairness:** Fair allocation of system resources
- **Independent lifecycle:** Each session can pause/resume independently

### Isolation Layers

#### 1. File System Isolation

**Directory Structure:**
```
work_dir/
├── sessions/
│   ├── session_001/
│   │   ├── projects/
│   │   │   └── project_xyz/
│   │   │       ├── runs/
│   │   │       │   ├── run_abc123/
│   │   │       │   │   ├── planning/
│   │   │       │   │   ├── control/
│   │   │       │   │   ├── data/
│   │   │       │   │   ├── codebase/
│   │   │       │   │   └── context/
│   │   │       │   └── run_def456/
│   │   │       └── metadata.json
│   │   └── metadata.json
│   ├── session_002/
│   │   └── ...
│   └── session_003/
│       └── ...
```

**Enforcement:**
```python
class WorkflowExecutor:
    def __init__(self, session_id, project_id, run_id):
        # Construct isolated path
        self.work_dir = (
            f"{BASE_WORK_DIR}/sessions/{session_id}/"
            f"projects/{project_id}/runs/{run_id}"
        )

        # Ensure directory exists
        os.makedirs(self.work_dir, exist_ok=True)

        # Set environment variable for agents
        os.environ['CMBAGENT_WORK_DIR'] = self.work_dir

    def validate_file_access(self, file_path):
        # Prevent directory traversal attacks
        abs_path = os.path.abspath(file_path)
        if not abs_path.startswith(self.work_dir):
            raise SecurityError(
                f"File access outside session dir: {file_path}"
            )
```

#### 2. Database Isolation

**Row-Level Security:**
```sql
-- Every table has session_id column
CREATE TABLE workflow_runs (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    project_id UUID NOT NULL,
    ...
);

-- Application-level query filter
SELECT * FROM workflow_runs
WHERE session_id = :current_session_id;

-- Index for performance
CREATE INDEX idx_runs_session ON workflow_runs(session_id);

-- PostgreSQL Row-Level Security (optional, for production)
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY session_isolation ON workflow_runs
    USING (session_id = current_setting('app.current_session_id')::UUID);
```

**Query Wrapper:**
```python
class SessionScopedQuery:
    def __init__(self, db_session, user_session_id):
        self.db = db_session
        self.session_id = user_session_id

    def query(self, model):
        # Automatically add session filter
        return self.db.query(model).filter(
            model.session_id == self.session_id
        )

    def get_run(self, run_id):
        run = self.query(WorkflowRun).filter(
            WorkflowRun.id == run_id
        ).first()

        if not run:
            raise PermissionDenied(
                "Run not found or not in your session"
            )
        return run
```

#### 3. Resource Boundaries

**Per-Session Quotas:**
```python
class SessionResourceManager:
    def __init__(self, session_id):
        self.session_id = session_id
        self.limits = {
            "max_disk_mb": 10000,      # 10 GB per session
            "max_concurrent_runs": 3,   # 3 workflows at once
            "max_cost_usd": 100.0,      # $100 budget
            "max_memory_mb": 4000       # 4 GB RAM
        }

    def check_disk_quota(self):
        session_dir = f"{BASE_WORK_DIR}/sessions/{self.session_id}"
        usage_mb = get_directory_size_mb(session_dir)

        if usage_mb > self.limits["max_disk_mb"]:
            raise QuotaExceededError(
                f"Disk quota exceeded: {usage_mb} MB / "
                f"{self.limits['max_disk_mb']} MB"
            )

    def check_concurrent_runs(self):
        active_count = db.query(WorkflowRun).filter(
            session_id == self.session_id,
            status.in_(['executing', 'planning'])
        ).count()

        if active_count >= self.limits["max_concurrent_runs"]:
            raise QuotaExceededError(
                f"Max concurrent runs: {active_count} / "
                f"{self.limits['max_concurrent_runs']}"
            )
```

#### 4. Concurrent Execution Isolation

**Thread/Process Safety:**
```python
# Each session runs in isolated worker process
from multiprocessing import Process, Queue

class SessionWorkerPool:
    def __init__(self):
        self.workers = {}  # session_id -> Process

    def start_workflow(self, session_id, run_id, task):
        # Create isolated process for this session
        queue = Queue()
        worker = Process(
            target=run_workflow_isolated,
            args=(session_id, run_id, task, queue)
        )
        worker.start()
        self.workers[session_id] = worker

def run_workflow_isolated(session_id, run_id, task, result_queue):
    # This runs in separate process - full isolation
    try:
        executor = WorkflowExecutor(session_id, run_id)
        result = executor.execute(task)
        result_queue.put({"status": "success", "result": result})
    except Exception as e:
        result_queue.put({"status": "error", "error": str(e)})
```

#### 5. Independent Lifecycle Management

**Per-Session State Machine:**
```python
# Session A: EXECUTING
# Session B: PAUSED
# Session C: COMPLETED
# All independent!

def pause_session(session_id, run_id):
    # Only affects this specific run in this session
    state_machine = StateMachine(run_id)
    state_machine.transition_to(WorkflowState.PAUSED)

    # Other sessions unaffected

def resume_session(session_id, run_id):
    # Verify ownership
    run = db.get_run(run_id)
    if run.session_id != session_id:
        raise PermissionDenied()

    # Resume only this run
    state_machine = StateMachine(run_id)
    state_machine.transition_to(WorkflowState.EXECUTING)
```

#### 6. Session Metadata Tracking

**Database Schema:**
```sql
sessions (
    id UUID PRIMARY KEY,
    user_id UUID,  -- For future multi-user support
    name VARCHAR(255),
    created_at TIMESTAMP,
    last_active_at TIMESTAMP,
    status VARCHAR(50),  -- active, archived, deleted
    metadata JSONB,  -- Custom key-value data
    resource_limits JSONB  -- Per-session quotas
);
```

**Session Management API:**
```python
# Create session
POST /api/sessions
{
    "name": "CMB Power Spectrum Analysis",
    "resource_limits": {
        "max_cost_usd": 50.0,
        "max_disk_mb": 5000
    }
}

# List sessions
GET /api/sessions
→ [{id, name, created_at, active_runs_count, total_cost}, ...]

# Get session details
GET /api/sessions/{session_id}
→ {id, name, runs: [...], total_cost, disk_usage_mb}

# Archive session
POST /api/sessions/{session_id}/archive
→ Moves to archived state, frees resources

# Delete session
DELETE /api/sessions/{session_id}
→ Removes all data (work_dir + database records)
```

### Session Isolation Testing

**Test Scenarios:**
1. **Concurrent Execution:** Start 3 workflows in 3 different sessions simultaneously
2. **File Isolation:** Verify Session A cannot read Session B's files
3. **Database Isolation:** Verify queries only return session-owned data
4. **Resource Limits:** Exceed quota in Session A, verify Session B unaffected
5. **Independent Lifecycle:** Pause Session A, verify Session B continues
6. **Cleanup:** Delete Session A, verify data removed but Session B intact

### Implementation Checklist

- [ ] Session-scoped directory structure
- [ ] File access validation (prevent directory traversal)
- [ ] Database session_id column on all tables
- [ ] Session-scoped query wrapper
- [ ] Resource quota manager
- [ ] Isolated worker processes per session
- [ ] Session management API endpoints
- [ ] Session metadata tracking
- [ ] Concurrent session testing
- [ ] Session cleanup (archive/delete)

## Technology Stack

### Core
- **Python 3.12+** - Application runtime
- **AG2 (latest)** - Multi-agent orchestration
- **SQLAlchemy** - ORM for database
- **Alembic** - Database migrations
- **FastAPI** - API server
- **WebSockets** - Real-time communication

### Database
- **SQLite** - Default (development)
- **PostgreSQL** - Production-ready option

### Frontend
- **Next.js 14+** - UI framework
- **React 18+** - Component library
- **TypeScript** - Type safety
- **WebSocket Client** - Real-time updates

### Integration
- **MCP SDK** - Model Context Protocol
- **OpenTelemetry** - Observability
- **OPA (Open Policy Agent)** - Policy engine

### Optional
- **Redis** - Request queue and caching
- **Jaeger** - Trace visualization
- **Prometheus** - Metrics collection
- **Grafana** - Dashboards

## Security Considerations

### Authentication & Authorization
- User authentication (Stage 15)
- Role-based access control (RBAC)
- API key management for LLM providers

### Data Protection
- Sensitive data encryption at rest
- API keys stored securely (environment variables)
- Audit logging of all actions

### Policy Enforcement
- OPA for fine-grained access control
- Default deny policies
- Regular policy audits

### Network Security
- HTTPS for production
- WebSocket secure (WSS)
- Rate limiting on API endpoints

## Scalability Considerations

### Horizontal Scaling
- Stateless API servers (scale out)
- Database connection pooling
- Message queue for long-running tasks

### Vertical Scaling
- Parallel execution reduces total time
- Database optimization (indexes, query optimization)
- Caching frequently accessed data

### Performance Optimization
- Lazy loading of agents
- Efficient context serialization
- Database query optimization
- WebSocket message batching

## Migration Strategy

### Phase-by-Phase Migration

**Phase 0-1:** Infrastructure (database, state machine, DAG)
- Add new systems alongside old
- Dual-write (pickle + database)
- Verify consistency

**Phase 2-3:** Features (HITL, parallel, MCP)
- Opt-in via feature flags
- Test with new workflows first
- Gradually migrate existing workflows

**Phase 4:** Observability and Policy
- Add as wrapper layers
- No breaking changes to core
- Enable incrementally

### Rollback Plan
- Feature flags allow instant disable
- Database migrations reversible
- Pickle files remain as backup
- Git tags for each stage

## Future Enhancements (Post-Phase 5)

- Multi-cloud deployment (AWS, GCP, Azure)
- Kubernetes orchestration
- Advanced RAG with vector databases
- Agent marketplace and sharing
- Collaborative multi-user workflows
- Advanced visualization (3D DAG, timeline)
- Machine learning for workflow optimization
- Auto-scaling based on load

---

**Version:** 1.0
**Last Updated:** 2026-01-14
**Status:** Design Complete, Ready for Implementation
