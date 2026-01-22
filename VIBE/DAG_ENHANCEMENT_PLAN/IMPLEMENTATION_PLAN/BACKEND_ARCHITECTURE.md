# CMBAgent Backend Architecture

## Overview

This document describes the production-grade backend architecture for CMBAgent, including the services layer, WebSocket communication protocol, database integration, and workflow control mechanisms.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (Next.js)                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Task Input  │  │  Workflow   │  │    DAG      │  │  Workflow Controls  │ │
│  │   Panel     │  │  Dashboard  │  │ Visualizer  │  │  (Pause/Resume)     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ WebSocket (ws://localhost:8000/ws/{task_id})
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Backend (FastAPI + Uvicorn)                        │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         WebSocket Endpoint                              │ │
│  │   - Receives: start, pause, resume, cancel, approval messages          │ │
│  │   - Sends: workflow events, DAG updates, console output                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         Services Layer                                │   │
│  │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐  │   │
│  │  │ WorkflowService  │ │ConnectionManager │ │  ExecutionService    │  │   │
│  │  │                  │ │                  │ │                      │  │   │
│  │  │ - Create runs    │ │ - WebSocket mgmt │ │ - Pause/Cancel flags │  │   │
│  │  │ - Update status  │ │ - Event routing  │ │ - Thread-safe locks  │  │   │
│  │  │ - DB integration │ │ - Broadcast      │ │ - Task tracking      │  │   │
│  │  └──────────────────┘ └──────────────────┘ └──────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    CMBAgent Core (ThreadPoolExecutor)                 │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                    WorkflowCallbacks                             │ │   │
│  │  │  - on_planning_start/complete                                   │ │   │
│  │  │  - on_step_start/complete/failed                                │ │   │
│  │  │  - on_workflow_start/complete/failed                            │ │   │
│  │  │  - on_pause_check (blocks while paused)                         │ │   │
│  │  │  - should_continue (cancel check)                               │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                    AG2/AutoGen Runtime                           │ │   │
│  │  │  - Agent orchestration                                          │ │   │
│  │  │  - LLM API calls                                                │ │   │
│  │  │  - Context management                                           │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         Database Layer (SQLite)                       │   │
│  │  - WorkflowRun records                                                │   │
│  │  - DAG nodes and edges                                                │   │
│  │  - Step execution history                                             │   │
│  │  - Session management                                                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Services Layer

### 1. WorkflowService (`backend/services/workflow_service.py`)

Manages workflow lifecycle with database integration.

```python
class WorkflowService:
    """
    Responsibilities:
    - Create and track workflow runs
    - Manage workflow state transitions
    - Integrate with database layer
    - Handle pause/resume at workflow level
    """
    
    def create_workflow_run(task_id, task_description, mode, agent, model, config) -> Dict
    def update_workflow_status(task_id, status, error_message=None) -> Dict
    def pause_workflow(task_id) -> Dict
    def resume_workflow(task_id) -> Dict
    def cancel_workflow(task_id) -> Dict
    def get_workflow_status(task_id) -> Dict
    def cleanup_run(task_id) -> None
```

### 2. ConnectionManager (`backend/services/connection_manager.py`)

Manages WebSocket connections with event protocol.

```python
class ConnectionManager:
    """
    Responsibilities:
    - Track active WebSocket connections per task
    - Route events to correct clients
    - Send typed workflow events
    - Handle connection lifecycle
    """
    
    async def connect(websocket, task_id) -> None
    async def disconnect(websocket, task_id) -> None
    async def send_event(task_id, event) -> None
    async def send_workflow_started(task_id, message) -> None
    async def send_workflow_paused(task_id, message) -> None
    async def send_workflow_resumed(task_id, message) -> None
    async def send_workflow_cancelled(task_id, message) -> None
    async def broadcast(event) -> None
```

### 3. ExecutionService (`backend/services/execution_service.py`)

Handles task execution with pause/cancel support.

```python
class ExecutionService:
    """
    Responsibilities:
    - Track pause/cancel flags per task
    - Thread-safe flag access with locks
    - Async wait while paused
    - Task execution coordination
    """
    
    def is_paused(task_id) -> bool
    def is_cancelled(task_id) -> bool
    def set_paused(task_id, paused) -> None
    def set_cancelled(task_id, cancelled) -> None
    async def wait_if_paused(task_id) -> bool
```

---

## Pause/Resume Implementation

### The Challenge

AG2/AutoGen does **not** have native pause support. Once `cmbagent.solve()` is called:
- AG2 controls the agent transition loop internally
- LLM API calls are blocking
- We cannot interrupt mid-execution

### The Solution: Step Boundary Pause

We inject pause checks at **step boundaries** - the points between major workflow phases.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Planning      │────▶│  Pause Check    │────▶│     Step 1      │
│   Phase         │     │  (blocks here)  │     │   Execution     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     Step 2      │◀────│  Pause Check    │◀────│   Step 1        │
│   Execution     │     │  (blocks here)  │     │   Complete      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Implementation Details

#### 1. Callback Extension (`cmbagent/callbacks.py`)

Added two new callback types:

```python
@dataclass
class WorkflowCallbacks:
    # ... existing callbacks ...
    
    # Pause support
    should_continue: Optional[Callable[[], bool]] = None  # Returns False to stop
    on_pause_check: Optional[Callable[[], None]] = None   # Blocks while paused
    
    def check_should_continue(self) -> bool:
        """Check if workflow should continue (not cancelled)."""
        if self.should_continue:
            return self.should_continue()
        return True
    
    def invoke_pause_check(self) -> None:
        """Block if paused, until resumed."""
        if self.on_pause_check:
            self.on_pause_check()
```

#### 2. Callback Merging (`cmbagent/callbacks.py`)

Extended `merge_callbacks()` to handle pause callbacks:

```python
def merge_callbacks(*callbacks_list) -> WorkflowCallbacks:
    # ... existing merge logic ...
    
    def make_merged_should_continue():
        """Returns False if ANY callback returns False."""
        def merged():
            for cb in callbacks_list:
                if cb.should_continue and not cb.should_continue():
                    return False
            return True
        return merged
    
    def make_merged_pause_check():
        """Call all pause check callbacks."""
        def merged():
            for cb in callbacks_list:
                if cb.on_pause_check:
                    cb.on_pause_check()
        return merged
    
    merged_dict["should_continue"] = make_merged_should_continue()
    merged_dict["on_pause_check"] = make_merged_pause_check()
```

#### 3. Pause Check Injection (`cmbagent/cmbagent.py`)

Added pause checks before each step:

```python
# In planning_and_control_context_carryover()

# Before planning phase
if callbacks:
    callbacks.invoke_pause_check()
    if not callbacks.check_should_continue():
        raise Exception("Workflow cancelled by user")

# Before each control step
callbacks.invoke_pause_check()
if not callbacks.check_should_continue():
    raise Exception("Workflow cancelled by user")

callbacks.invoke_step_start(step_info)
cmbagent.solve(...)
```

#### 4. Sync Pause Check (`backend/main.py`)

Blocking loop that waits while paused:

```python
def sync_pause_check():
    """Blocks while workflow is paused."""
    if SERVICES_AVAILABLE:
        while execution_service.is_paused(task_id):
            if execution_service.is_cancelled(task_id):
                raise Exception("Workflow cancelled by user")
            time.sleep(0.5)
```

#### 5. Thread-Safe Execution Service

Uses threading locks for cross-thread safety:

```python
class ExecutionService:
    def __init__(self):
        self._pause_flags: Dict[str, bool] = {}
        self._cancel_flags: Dict[str, bool] = {}
        self._lock = threading.Lock()  # Thread-safe access
    
    def is_paused(self, task_id: str) -> bool:
        with self._lock:
            return self._pause_flags.get(task_id, False)
    
    def set_paused(self, task_id: str, paused: bool):
        with self._lock:
            self._pause_flags[task_id] = paused
```

---

## WebSocket Protocol

### Client → Server Messages

| Type | Payload | Description |
|------|---------|-------------|
| `start` | `{task, config}` | Start workflow execution |
| `pause` | `{}` | Request pause at next step boundary |
| `resume` | `{}` | Resume paused workflow |
| `cancel` | `{}` | Cancel workflow execution |
| `approval` | `{approved, feedback?}` | HITL approval response |

### Server → Client Events

| Type | Payload | Description |
|------|---------|-------------|
| `workflow_started` | `{message}` | Workflow execution began |
| `workflow_paused` | `{message}` | Workflow paused |
| `workflow_resumed` | `{message}` | Workflow resumed |
| `workflow_complete` | `{message, duration}` | Workflow finished |
| `workflow_failed` | `{error, traceback?}` | Workflow error |
| `planning_started` | `{task}` | Planning phase began |
| `planning_complete` | `{num_steps}` | Planning finished |
| `step_started` | `{step_number, agent}` | Step execution began |
| `step_completed` | `{step_number, duration}` | Step finished |
| `dag_update` | `{nodes, edges}` | DAG state changed |
| `console_output` | `{text}` | Stdout/stderr capture |
| `approval_required` | `{step, type, context}` | HITL checkpoint |

---

## Workflow Modes

All 6 workflow modes are integrated with the services layer:

| Mode | Function | Description |
|------|----------|-------------|
| `planning-control` | `planning_and_control_context_carryover()` | Multi-step planning with execution |
| `one-shot` | `one_shot()` | Single agent task execution |
| `idea-generation` | Uses planning mode | Idea brainstorming workflow |
| `ocr` | `process_folder()` | PDF document processing |
| `arxiv` | `arxiv_filter()` | arXiv paper filtering |
| `enhance-input` | Uses planning mode | Task enhancement workflow |

---

## Database Integration

### Schema (from Stage 1-9)

```sql
-- Workflow runs table
CREATE TABLE workflow_runs (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    task_description TEXT,
    status TEXT,  -- 'pending', 'executing', 'paused', 'completed', 'failed'
    mode TEXT,
    agent TEXT,
    model TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    error_message TEXT
);

-- DAG nodes table
CREATE TABLE dag_nodes (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES workflow_runs(id),
    node_type TEXT,  -- 'planning', 'step_1', 'step_2', etc.
    status TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

---

## Error Handling

### Graceful Degradation

The backend operates with or without database:

```python
try:
    from services import workflow_service, connection_manager, execution_service
    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False

# In handlers:
if SERVICES_AVAILABLE:
    workflow_service.create_workflow_run(...)
else:
    # Fallback to simple tracking
```

### Error Recovery

```python
try:
    result = await loop.run_in_executor(executor, run_cmbagent)
except Exception as e:
    if SERVICES_AVAILABLE:
        workflow_service.update_workflow_status(task_id, 'failed', str(e))
    await connection_manager.send_event(task_id, WebSocketEvent(
        type=WebSocketEventType.WORKFLOW_FAILED,
        data={"error": str(e), "traceback": traceback.format_exc()}
    ))
```

---

## UI Integration

### Pause Button Tooltip

The pause button includes a tooltip explaining the behavior:

```tsx
<div className="relative group">
  <button onClick={onPause}>
    <Pause /> Pause
  </button>
  <div className="tooltip">
    Pauses at step boundaries (after current LLM call completes)
  </div>
</div>
```

### State Synchronization

Frontend state is synchronized via WebSocket events:

```typescript
// WebSocketContext.tsx
onWorkflowPaused: () => {
  setWorkflowStatus('paused');
  addConsoleOutput('⏸️ Workflow paused');
}

onWorkflowResumed: () => {
  setWorkflowStatus('executing');
  addConsoleOutput('▶️ Workflow resumed');
}
```

---

## File Structure

```
backend/
├── main.py                    # FastAPI app, WebSocket endpoint
├── run.py                     # Development server runner
├── credentials.py             # API key management
├── event_queue.py             # Event queue utilities
├── websocket_events.py        # WebSocket event types
├── websocket_manager.py       # Legacy WebSocket manager
└── services/
    ├── __init__.py            # Service exports
    ├── workflow_service.py    # Workflow lifecycle management
    ├── connection_manager.py  # WebSocket connection management
    └── execution_service.py   # Task execution with pause/cancel

cmbagent/
├── callbacks.py               # WorkflowCallbacks with pause support
├── cmbagent.py                # Core execution with pause checks
└── ...
```

---

## Testing

### Manual Testing Steps

1. **Start Backend**: `uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`
2. **Start Frontend**: `cd cmbagent-ui && npm run dev`
3. **Test Pause/Resume**:
   - Start a planning-control workflow
   - Click Pause during planning phase
   - Observe workflow pauses before Step 1
   - Click Resume
   - Observe workflow continues

### Expected Behavior

- Pause requested during planning → Pauses before Step 1
- Pause requested during Step N → Pauses before Step N+1
- Resume → Continues from pause point
- Cancel → Stops workflow immediately

---

## Future Improvements

1. **Finer-grained pause**: Investigate AG2 hooks for mid-step pause
2. **Checkpoint/restore**: Save workflow state for later resumption
3. **Distributed execution**: Support for multi-worker task execution
4. **Real-time progress**: More granular progress updates during LLM calls
