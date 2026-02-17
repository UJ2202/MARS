# WebSocket Robustness Architecture

## Executive Summary

This document describes the architectural redesign of the CMBAgent WebSocket and session management system. The primary goals are:

1. Enable concurrent task execution without output mixing
2. Persist sessions across server restarts
3. Provide reliable HITL (Human-in-the-Loop) approval handling
4. Establish a maintainable logging infrastructure

## Core Architectural Principles

### 1. Process Isolation for Execution

**Problem:** Current implementation modifies Python globals (`builtins.print`, `sys.stdout`, `IOStream.set_global_default`) causing cross-contamination between concurrent tasks.

**Solution:** Execute each task in a separate subprocess.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Main Process (FastAPI)                       │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ WebSocket Handler│  │ WebSocket Handler│                     │
│  │    Task A        │  │    Task B        │                     │
│  └────────┬─────────┘  └────────┬─────────┘                     │
│           │                     │                                │
│           ▼                     ▼                                │
│  ┌──────────────────────────────────────────┐                   │
│  │        IsolatedTaskExecutor              │                   │
│  │  - Manages subprocess lifecycle          │                   │
│  │  - Routes output via queues              │                   │
│  └──────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
           │                     │
           ▼                     ▼
┌──────────────────┐   ┌──────────────────┐
│  Subprocess A    │   │  Subprocess B    │
│  - Own globals   │   │  - Own globals   │
│  - Own stdout    │   │  - Own stdout    │
│  - Isolated      │   │  - Isolated      │
└──────────────────┘   └──────────────────┘
```

**Why Subprocess Over Alternatives:**

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| Subprocess | True isolation, works with any library | Memory overhead, IPC complexity | **Selected** |
| Contextvars | Lightweight, native Python | Won't work with global overrides | Rejected |
| Celery | Battle-tested, scalable | Requires Redis/RabbitMQ | Overkill |
| ThreadLocal | Simple | Same process, globals still shared | Rejected |

### 2. Database-Only Session Persistence

**Problem:** Sessions stored in `_active_copilot_sessions` dict are lost on server restart.

**Solution:** Separate serializable session state from runtime state.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Session State (Database)                      │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  session_states table                                    │   │
│  │  - session_id (UUID)                                     │   │
│  │  - conversation_history (JSONB)  ← Serializable          │   │
│  │  - context_variables (JSONB)     ← Serializable          │   │
│  │  - plan_data (JSONB)             ← Serializable          │   │
│  │  - current_phase (VARCHAR)                               │   │
│  │  - current_step (INTEGER)                                │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Load on resume
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Runtime State (Memory)                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  SwarmOrchestrator (recreated)                           │   │
│  │  - agents: Dict[str, Agent]      ← Recreated from config │   │
│  │  - websocket: WebSocket          ← Current connection    │   │
│  │  - callbacks: WorkflowCallbacks  ← Recreated             │   │
│  │  - approval_events: Dict         ← Fresh events          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**What CAN vs CANNOT Be Serialized:**

| Item | Serializable? | Approach |
|------|---------------|----------|
| Conversation history | Yes | Store as JSON array |
| Context variables | Yes (if JSON-safe) | Store as JSONB |
| Plan structure | Yes | Store as JSONB |
| Agent instances | No | Recreate from config |
| WebSocket connection | No | Use current connection |
| Callbacks/lambdas | No | Recreate on resume |
| asyncio.Event | No | Use database-backed events |

### 3. Single Source of Truth for Connections

**Problem:** Two competing connection managers (`WebSocketManager` and `ConnectionManager`).

**Solution:** Consolidate into single `ConnectionManager` with async locks.

```
Before (Confusing):
┌─────────────────────┐     ┌─────────────────────┐
│ WebSocketManager    │     │ ConnectionManager   │
│ websocket_manager.py│     │ services/conn...py  │
│                     │     │                     │
│ active_connections: │     │ _connections:       │
│   Dict[str, WS]     │     │   Dict[str, WS]     │
└─────────────────────┘     └─────────────────────┘
         ↑                           ↑
         │                           │
    Some code uses             Other code uses

After (Clear):
┌─────────────────────────────────────────────────┐
│              ConnectionManager                   │
│         services/connection_manager.py          │
│                                                 │
│  _connections: Dict[str, WebSocket]             │
│  _metadata: Dict[str, ConnectionMetadata]       │
│  _lock: asyncio.Lock                            │
│                                                 │
│  Methods:                                       │
│  - connect(websocket, task_id, session_id)     │
│  - disconnect(task_id)                         │
│  - send_event(task_id, event)                  │
│  - is_connected(task_id)                       │
└─────────────────────────────────────────────────┘
                     ↑
                     │
            All code uses this
```

### 4. Approval System with Timeout and Persistence

**Problem:** `WebSocketApprovalManager` uses class variables and `asyncio.Event` - lost on restart.

**Solution:** Database-backed approvals with local event notification for fast path.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Approval Flow                                 │
│                                                                  │
│  1. Workflow requests approval                                   │
│     │                                                            │
│     ▼                                                            │
│  ┌──────────────────────────────────────┐                       │
│  │ RobustApprovalManager.request()      │                       │
│  │ - Insert into approval_requests DB   │ ← Survives restart    │
│  │ - Create local asyncio.Event         │ ← Fast notification   │
│  │ - Return approval_id                 │                       │
│  └──────────────────────────────────────┘                       │
│     │                                                            │
│     ▼                                                            │
│  2. WebSocket sends approval_required to UI                      │
│     │                                                            │
│     ▼                                                            │
│  3. Workflow calls wait_for_approval(approval_id)               │
│     │                                                            │
│     ├─────────────────────────────────────┐                     │
│     │                                     │                     │
│     ▼                                     ▼                     │
│  ┌─────────────────┐            ┌─────────────────┐             │
│  │ Fast Path       │            │ Slow Path       │             │
│  │ (Event set)     │            │ (DB polling)    │             │
│  │ ~0ms latency    │            │ ~1-2s latency   │             │
│  └─────────────────┘            └─────────────────┘             │
│     │                                     │                     │
│     └─────────────────┬───────────────────┘                     │
│                       │                                          │
│                       ▼                                          │
│  4. User clicks Approve/Reject in UI                            │
│     │                                                            │
│     ▼                                                            │
│  ┌──────────────────────────────────────┐                       │
│  │ RobustApprovalManager.resolve()      │                       │
│  │ - Update DB (idempotent)             │                       │
│  │ - Set local event (if exists)        │                       │
│  └──────────────────────────────────────┘                       │
│     │                                                            │
│     ▼                                                            │
│  5. Workflow continues with result                               │
└─────────────────────────────────────────────────────────────────┘
```

## High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (Next.js)                              │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  WebSocket       │  │  Session         │  │  Approval        │          │
│  │  Context         │  │  Manager UI      │  │  Dialog          │          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
└───────────┼────────────────────┼────────────────────┼───────────────────────┘
            │                    │                    │
            │ WebSocket          │ REST API           │ WebSocket
            │                    │                    │
┌───────────┼────────────────────┼────────────────────┼───────────────────────┐
│           ▼                    ▼                    ▼                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        FastAPI Backend                               │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ WS Handler   │  │ Sessions     │  │ Other        │               │   │
│  │  │ /ws/{task_id}│  │ Router       │  │ Routers      │               │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────────┘               │   │
│  │         │                 │                                          │   │
│  │         ▼                 ▼                                          │   │
│  │  ┌────────────────────────────────────────────────────────────┐     │   │
│  │  │                    Services Layer                          │     │   │
│  │  │                                                            │     │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │     │   │
│  │  │  │ Connection   │  │ Session      │  │ Approval     │     │     │   │
│  │  │  │ Manager      │  │ Manager      │  │ Manager      │     │     │   │
│  │  │  └──────────────┘  └──────────────┘  └──────────────┘     │     │   │
│  │  │                                                            │     │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │     │   │
│  │  │  │ Workflow     │  │ Execution    │  │ Event        │     │     │   │
│  │  │  │ Service      │  │ Service      │  │ Queue        │     │     │   │
│  │  │  └──────────────┘  └──────────────┘  └──────────────┘     │     │   │
│  │  └────────────────────────────────────────────────────────────┘     │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌────────────────────────────────────────────────────────────┐     │   │
│  │  │              Isolated Task Executor                        │     │   │
│  │  │                                                            │     │   │
│  │  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │     │   │
│  │  │   │ Subprocess  │  │ Subprocess  │  │ Subprocess  │       │     │   │
│  │  │   │   Task 1    │  │   Task 2    │  │   Task N    │       │     │   │
│  │  │   └─────────────┘  └─────────────┘  └─────────────┘       │     │   │
│  │  └────────────────────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                       │
│                                     ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      CMBAgent Core                                   │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ Swarm        │  │ Workflows    │  │ Agents       │               │   │
│  │  │ Orchestrator │  │ (copilot,    │  │ (engineer,   │               │   │
│  │  │              │  │  hitl, etc.) │  │  researcher) │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                       │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Persistence Layer                                  │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ sessions    │  │ session_    │  │ workflow_   │  │ approval_   │        │
│  │             │  │ states      │  │ runs        │  │ requests    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ dag_nodes   │  │ execution_  │  │ cost_       │  │ active_     │        │
│  │             │  │ events      │  │ records     │  │ connections │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Models

### Session State Entity

```python
@dataclass
class SessionState:
    """Persistable session state"""
    id: UUID
    session_id: UUID
    mode: str  # "copilot", "planning-control", "hitl-interactive", etc.

    # Serialized state
    conversation_history: List[Dict[str, Any]]
    context_variables: Dict[str, Any]
    plan_data: Optional[Dict[str, Any]]

    # Progress tracking
    current_phase: str  # "planning", "execution", "review"
    current_step: Optional[int]

    # Lifecycle
    status: str  # "active", "suspended", "completed", "expired"
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]

    # Optimistic locking
    version: int
```

### Approval Request Entity

```python
@dataclass
class ApprovalRequest:
    """Persistent approval request"""
    id: UUID
    run_id: UUID
    session_id: Optional[UUID]

    # Request details
    approval_type: str  # "plan_approval", "step_approval", "error_recovery"
    context: Dict[str, Any]  # What's being approved

    # Resolution
    status: str  # "pending", "resolved", "expired", "cancelled"
    resolution: Optional[str]  # "approved", "rejected", "modified"
    result: Optional[Dict[str, Any]]

    # Timing
    created_at: datetime
    expires_at: datetime
    resolved_at: Optional[datetime]
```

### Connection Entity (for multi-instance)

```python
@dataclass
class ActiveConnection:
    """Track connections for multi-instance deployment"""
    id: UUID
    task_id: str
    session_id: Optional[UUID]
    server_instance: str  # hostname for routing
    connected_at: datetime
    last_heartbeat: datetime
```

## Data Flow Diagrams

### Flow 1: New Task Execution

```
User                    Frontend           Backend              Subprocess           Database
  │                        │                  │                     │                   │
  │ Start Task             │                  │                     │                   │
  ├───────────────────────►│                  │                     │                   │
  │                        │ WS Connect       │                     │                   │
  │                        ├─────────────────►│                     │                   │
  │                        │                  │ Create Session      │                   │
  │                        │                  ├────────────────────────────────────────►│
  │                        │                  │                     │                   │
  │                        │ Send Task        │                     │                   │
  │                        ├─────────────────►│                     │                   │
  │                        │                  │ Spawn Subprocess    │                   │
  │                        │                  ├────────────────────►│                   │
  │                        │                  │                     │                   │
  │                        │                  │◄───Output Queue─────│                   │
  │                        │◄─────WS Event────│                     │                   │
  │◄───────UI Update───────│                  │                     │                   │
  │                        │                  │                     │                   │
  │                        │                  │                     │ Save State        │
  │                        │                  │                     ├──────────────────►│
  │                        │                  │                     │                   │
  │                        │                  │◄────Complete────────│                   │
  │                        │◄─────Complete────│                     │                   │
  │◄───────Complete────────│                  │                     │                   │
```

### Flow 2: Session Resume

```
User                    Frontend           Backend              Database
  │                        │                  │                     │
  │ List Sessions          │                  │                     │
  ├───────────────────────►│                  │                     │
  │                        │ GET /api/sessions│                     │
  │                        ├─────────────────►│                     │
  │                        │                  │ Query sessions      │
  │                        │                  ├────────────────────►│
  │                        │                  │◄───Session list─────│
  │                        │◄───Session list──│                     │
  │◄───Display list────────│                  │                     │
  │                        │                  │                     │
  │ Resume Session X       │                  │                     │
  ├───────────────────────►│                  │                     │
  │                        │ WS Connect       │                     │
  │                        ├─────────────────►│                     │
  │                        │ Task + sessionId │                     │
  │                        ├─────────────────►│                     │
  │                        │                  │ Load session state  │
  │                        │                  ├────────────────────►│
  │                        │                  │◄───State────────────│
  │                        │                  │                     │
  │                        │                  │ Recreate orchestrator│
  │                        │                  │ with loaded state   │
  │                        │                  │                     │
  │                        │◄─────Resume OK───│                     │
  │◄───────Resumed─────────│                  │                     │
```

### Flow 3: HITL Approval

```
Workflow                Backend            Frontend              User            Database
   │                      │                   │                    │                 │
   │ Request Approval     │                   │                    │                 │
   ├─────────────────────►│                   │                    │                 │
   │                      │ Insert pending    │                    │                 │
   │                      ├──────────────────────────────────────────────────────────►│
   │                      │                   │                    │                 │
   │                      │ WS approval_req   │                    │                 │
   │                      ├──────────────────►│                    │                 │
   │                      │                   │ Show dialog        │                 │
   │                      │                   ├───────────────────►│                 │
   │                      │                   │                    │                 │
   │ Wait for approval    │                   │                    │                 │
   │ (polling + event)    │                   │                    │                 │
   ├──────────────────────┤                   │                    │                 │
   │                      │                   │                    │ Click Approve   │
   │                      │                   │◄───────────────────│                 │
   │                      │ WS resolve        │                    │                 │
   │                      │◄──────────────────│                    │                 │
   │                      │                   │                    │                 │
   │                      │ Update DB         │                    │                 │
   │                      ├──────────────────────────────────────────────────────────►│
   │                      │ Set local event   │                    │                 │
   │◄─────Resolution──────│                   │                    │                 │
   │                      │                   │                    │                 │
   │ Continue workflow    │                   │                    │                 │
```

## Technology Stack

### Core
- **FastAPI**: Async web framework with WebSocket support
- **SQLAlchemy**: ORM for database persistence
- **Alembic**: Database migrations
- **Pydantic**: Data validation and settings

### Execution
- **multiprocessing**: Process isolation for concurrent tasks
- **asyncio**: Async I/O for WebSocket handling
- **Queue**: IPC for subprocess output

### Logging
- **structlog**: Structured logging with context binding
- **Python logging**: Standard library integration

### Testing
- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **aiohttp**: Load testing

### Frontend
- **Next.js**: React framework
- **TypeScript**: Type safety
- **WebSocket API**: Real-time communication

## Security Considerations

### Input Validation
- All WebSocket messages validated against schemas
- Task descriptions sanitized before execution
- Config values validated and constrained

### Session Security
- Session IDs are UUIDv4 (unpredictable)
- Sessions isolated by user_id (when implemented)
- Session expiration prevents indefinite resource usage

### Subprocess Security
- Subprocesses run with same permissions as main process
- No arbitrary code execution (task goes to CMBAgent)
- Work directories isolated per task

### Database Security
- Parameterized queries prevent SQL injection
- Connection pooling prevents exhaustion
- Credentials from environment variables

## Performance Considerations

### Subprocess Overhead
- ~50-100ms startup time per subprocess
- ~50MB memory per subprocess
- Acceptable for long-running AI tasks

### Database Connection Pool
- PostgreSQL: pool_size=5, max_overflow=10
- SQLite: WAL mode for concurrent reads
- Connection timeout: 30 seconds

### WebSocket Efficiency
- Event queue limits: 1000 events, 5 min retention
- Heartbeat interval: 30 seconds
- Reconnection backoff: exponential, max 30 seconds

### Session State Size
- Conversation history: ~10KB per turn typical
- Max conversation length: 100 turns recommended
- Context variables: <1MB recommended

## Scalability Path

### Current (Single Instance)
- One backend process
- SQLite or PostgreSQL
- ~50 concurrent users

### Future (Horizontal Scaling)
- Multiple backend instances behind load balancer
- PostgreSQL required (shared state)
- Redis for session caching (optional)
- Sticky sessions OR stateless handlers
- Pub/sub for cross-instance events

---

**Version:** 1.0
**Last Updated:** 2026-02-11
