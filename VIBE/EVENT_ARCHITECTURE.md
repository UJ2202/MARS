# CMBAgent Event Architecture - Comprehensive Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Event Flow Architecture](#event-flow-architecture)
3. [Database Schema (RDBMS Tables)](#database-schema)
4. [Event Storage Mechanism](#event-storage-mechanism)
5. [WebSocket Event System](#websocket-event-system)
6. [API Endpoints](#api-endpoints)
7. [Event Queue System](#event-queue-system)
8. [Service Layer Architecture](#service-layer-architecture)
9. [Event Types & Data Models](#event-types--data-models)
10. [Complete Data Flow Diagrams](#complete-data-flow-diagrams)

---

## 1. System Overview

The CMBAgent system uses a multi-layered event tracking and logging architecture that combines:
- **Database persistence** (PostgreSQL/SQLite with SQLAlchemy)
- **Real-time WebSocket streaming** (FastAPI WebSockets)
- **In-memory event queue** (for reconnection support)
- **RESTful APIs** (for historical data access)
- **Run ID Resolution Layer** (task_id ↔ db_run_id normalization)

```
┌─────────────────────────────────────────────────────────────┐
│                     CMBAgent System                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Frontend   │◄──►│   Backend    │◄──►│   Database   │  │
│  │  (Next.js)   │    │  (FastAPI)   │    │ (PostgreSQL) │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                     │         │
│    WebSocket            REST API              SQLAlchemy    │
│    Real-time            Historical            Persistence   │
│     (task_id)        (Resolution Layer)        (UUID)       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### CRITICAL: Run ID Architecture

**Production-Grade Normalization**: The system uses a dual-identity run ID architecture:

```
┌──────────────────────────────────────────────────────────────────┐
│                  RUN ID DUAL IDENTITY SYSTEM                      │
└──────────────────────────────────────────────────────────────────┘

FRONTEND (User-Facing ID)
└─► task_id: "task_1768933508543_odu8enmvf"
    │  Human-readable identifier
    │  Used in UI and API requests
    │  Generated at task submission
    │
    ▼
┌──────────────────────────────────────┐
│  RESOLUTION LAYER (Backend)          │
│  resolve_run_id(task_id) → db_run_id│
│  Single source of truth function     │
└──────────────────────────────────────┘
    │
    ▼
DATABASE (Internal ID)
└─► db_run_id: "550e8400-e29b-41d4-a716-446655440000" (UUID)
    │  Database primary key
    │  Used in all foreign key relationships
    │  Stored in all events, steps, nodes, etc.


WHY TWO IDs?
────────────
✓ task_id: User-friendly, embeds timestamp, easier debugging
✓ db_run_id: UUID ensures uniqueness, database best practice
✓ Separation: Frontend concerns vs database integrity


RESOLUTION MAPPING
──────────────────
WorkflowService maintains active mapping:
  _active_runs: Dict[task_id, RunInfo]
  RunInfo {
    task_id: str,
    run_id: UUID,        # Same as db_run_id
    db_run_id: UUID,     # Database primary key
    session_id: str,
    status: str
  }


API CONTRACT
────────────
1. Frontend sends: task_id
2. Backend resolves: task_id → db_run_id
3. Database queries: WHERE run_id = db_run_id
4. Response uses: task_id (for consistency)


CRITICAL: All APIs MUST call resolve_run_id() before querying!
```

---

## 2. Event Flow Architecture

### High-Level Event Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVENT GENERATION FLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

1. WORKFLOW EXECUTION
   ┌──────────────────┐
   │  CMBAgent Task   │
   │   Execution      │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  AG2IOStream     │  ← Captures stdout/stderr
   │  Capture         │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Event Detection │  ← Parse output for events
   │  & Classification│
   └────────┬─────────┘
            │
            ├─────────────────────────┬─────────────────────────┐
            ▼                         ▼                         ▼
   ┌────────────────┐        ┌────────────────┐      ┌──────────────────┐
   │  ExecutionEvent│        │  WebSocket     │      │   Event Queue    │
   │  (Database)    │        │  Event         │      │  (In-Memory)     │
   └────────────────┘        └────────────────┘      └──────────────────┘
            │                         │                         │
            │                         │                         │
            ▼                         ▼                         ▼
   ┌────────────────┐        ┌────────────────┐      ┌──────────────────┐
   │  Persistent    │        │  Real-time     │      │   Reconnection   │
   │  Storage       │        │  UI Update     │      │   Recovery       │
   └────────────────┘        └────────────────┘      └──────────────────┘

2. EVENT CONSUMPTION FLOW

   Frontend Client
        │
        │ WebSocket Connect
        ▼
   ┌──────────────────┐
   │ WebSocket        │
   │ Manager          │
   └────────┬─────────┘
            │
            │ On Connect
            ▼
   ┌──────────────────┐
   │ Send Current     │  ← Load from database
   │ State            │
   └────────┬─────────┘
            │
            │ During Execution
            ▼
   ┌──────────────────┐
   │ Stream Events    │  ← Real-time events
   │ to Client        │
   └────────┬─────────┘
            │
            │ On Disconnect/Reconnect
            ▼
   ┌──────────────────┐
   │ Send Missed      │  ← From event queue
   │ Events           │
   └──────────────────┘
```

---

## 3. Database Schema (RDBMS Tables)

### 3.1 Core Tables

```sql
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATABASE SCHEMA                                    │
└─────────────────────────────────────────────────────────────────────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TABLE: sessions                                                          ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  id                  VARCHAR(36)  PRIMARY KEY                             ┃
┃  user_id             VARCHAR(36)  INDEX                                   ┃
┃  name                VARCHAR(255) NOT NULL                                ┃
┃  created_at          TIMESTAMP    NOT NULL                                ┃
┃  last_active_at      TIMESTAMP    NOT NULL, INDEX                         ┃
┃  status              VARCHAR(50)  NOT NULL, INDEX  (active/archived)      ┃
┃  meta                JSON                                                  ┃
┃  resource_limits     JSON                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                                    │
                                    │ 1:N
                                    ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TABLE: workflow_runs                                                     ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  id                  VARCHAR(36)  PRIMARY KEY (UUID)                      ┃
┃                      ⚠️ This is db_run_id, NOT task_id!                   ┃
┃                      Used in all foreign key relationships                 ┃
┃  session_id          VARCHAR(36)  FK → sessions.id, INDEX                 ┃
┃  project_id          VARCHAR(36)  FK → projects.id                        ┃
┃  mode                VARCHAR(50)  NOT NULL, INDEX  (one_shot/planning)    ┃
┃  agent               VARCHAR(100) NOT NULL, INDEX                          ┃
┃  model               VARCHAR(100) NOT NULL                                 ┃
┃  status              VARCHAR(50)  NOT NULL, INDEX                          ┃
┃                      (draft/planning/executing/paused/completed/failed)    ┃
┃  started_at          TIMESTAMP                                             ┃
┃  completed_at        TIMESTAMP                                             ┃
┃  last_heartbeat_at   TIMESTAMP                                             ┃
┃  task_description    TEXT                                                  ┃
┃  meta                JSON         (May contain task_id for lookup)         ┃
┃  branch_parent_id    VARCHAR(36)  FK → workflow_runs.id                   ┃
┃  is_branch           BOOLEAN      DEFAULT FALSE                            ┃
┃  branch_depth        INTEGER      DEFAULT 0                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
┃  CRITICAL NOTES:                                                          ┃
┃  • id field is UUID (db_run_id), the database primary key                ┃
┃  • task_id is NOT stored directly - it's managed by WorkflowService      ┃
┃  • All child records (events, steps, nodes) reference this UUID          ┃
┃  • APIs must resolve task_id → db_run_id before querying                 ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                    │
                    │ 1:N
                    ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TABLE: workflow_steps                                                    ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  id                  VARCHAR(36)  PRIMARY KEY                             ┃
┃  run_id              VARCHAR(36)  FK → workflow_runs.id, INDEX            ┃
┃  session_id          VARCHAR(36)  FK → sessions.id, INDEX                 ┃
┃  step_number         INTEGER      NOT NULL                                ┃
┃  agent               VARCHAR(100) NOT NULL                                 ┃
┃  status              VARCHAR(50)  NOT NULL, INDEX                          ┃
┃                      (pending/running/completed/failed/skipped)            ┃
┃  started_at          TIMESTAMP                                             ┃
┃  completed_at        TIMESTAMP                                             ┃
┃  progress_percentage INTEGER      DEFAULT 0  (0-100)                       ┃
┃  inputs              JSON                                                  ┃
┃  outputs             JSON                                                  ┃
┃  error_message       TEXT                                                  ┃
┃  meta                JSON                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TABLE: dag_nodes                                                         ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  id                  VARCHAR(36)  PRIMARY KEY                             ┃
┃  run_id              VARCHAR(36)  FK → workflow_runs.id, INDEX            ┃
┃  session_id          VARCHAR(36)  FK → sessions.id, INDEX                 ┃
┃  node_type           VARCHAR(50)  NOT NULL, INDEX                          ┃
┃                      (planning/control/agent/approval/terminator)          ┃
┃  agent               VARCHAR(100)                                          ┃
┃  status              VARCHAR(50)  NOT NULL, INDEX                          ┃
┃                      (pending/running/completed/failed/skipped)            ┃
┃  order_index         INTEGER      NOT NULL                                 ┃
┃  meta                JSON                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
         │
         │ 1:N (outgoing)
         ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TABLE: dag_edges                                                         ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  id                  INTEGER      PRIMARY KEY AUTOINCREMENT               ┃
┃  from_node_id        VARCHAR(36)  FK → dag_nodes.id, INDEX                ┃
┃  to_node_id          VARCHAR(36)  FK → dag_nodes.id, INDEX                ┃
┃  dependency_type     VARCHAR(50)  NOT NULL                                 ┃
┃                      (sequential/parallel/conditional)                     ┃
┃  condition           TEXT                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### 3.2 Event & Logging Tables

```sql
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TABLE: execution_events (PRIMARY EVENT STORAGE)                         ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  id                  VARCHAR(36)  PRIMARY KEY                             ┃
┃  run_id              VARCHAR(36)  FK → workflow_runs.id, INDEX            ┃
┃                      ⚠️ STORES db_run_id (UUID), NOT task_id!            ┃
┃                      APIs must resolve task_id before querying            ┃
┃  node_id             VARCHAR(36)  FK → dag_nodes.id, INDEX                ┃
┃  step_id             VARCHAR(36)  FK → workflow_steps.id                  ┃
┃  session_id          VARCHAR(36)  FK → sessions.id, INDEX                 ┃
┃  parent_event_id     VARCHAR(36)  FK → execution_events.id (SELF)         ┃
┃                                                                            ┃
┃  -- Event Classification --                                               ┃
┃  event_type          VARCHAR(50)  NOT NULL, INDEX                          ┃
┃                      (agent_call/tool_call/code_exec/file_gen/handoff/    ┃
┃                       approval_requested/state_transition/error/info)      ┃
┃  event_subtype       VARCHAR(50)  (start/complete/error/info)             ┃
┃                                                                            ┃
┃  -- Agent Context --                                                      ┃
┃  agent_name          VARCHAR(100) INDEX                                    ┃
┃  agent_role          VARCHAR(50)  (primary/helper/validator)              ┃
┃                                                                            ┃
┃  -- Timing --                                                             ┃
┃  timestamp           TIMESTAMP    NOT NULL, INDEX                          ┃
┃  started_at          TIMESTAMP                                             ┃
┃  completed_at        TIMESTAMP                                             ┃
┃  duration_ms         INTEGER                                               ┃
┃                                                                            ┃
┃  -- Execution Data --                                                     ┃
┃  inputs              JSON         (input params, context)                  ┃
┃  outputs             JSON         (results, return values)                 ┃
┃  error_message       TEXT                                                  ┃
┃                                                                            ┃
┃  -- Hierarchy & Order --                                                  ┃
┃  execution_order     INTEGER      NOT NULL (sequence within node)          ┃
┃  depth               INTEGER      DEFAULT 0 (nesting level)                ┃
┃                                                                            ┃
┃  -- Status & Metadata --                                                  ┃
┃  status              VARCHAR(50)  DEFAULT 'completed'                      ┃
┃                      (pending/running/completed/failed/skipped)            ┃
┃  meta                JSON         (model, tokens, cost, custom data)       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
┃  INDEXES:                                                                 ┃
┃    - idx_events_run_order (run_id, execution_order)                      ┃
┃    - idx_events_node_order (node_id, execution_order)                    ┃
┃    - idx_events_type_subtype (event_type, event_subtype)                 ┃
┃    - idx_events_session_timestamp (session_id, timestamp)                ┃
┃    - idx_events_parent (parent_event_id)                                 ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TABLE: messages                                                          ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  id                  INTEGER      PRIMARY KEY AUTOINCREMENT               ┃
┃  run_id              VARCHAR(36)  FK → workflow_runs.id, INDEX            ┃
┃  step_id             VARCHAR(36)  FK → workflow_steps.id, INDEX           ┃
┃  event_id            VARCHAR(36)  FK → execution_events.id, INDEX         ┃
┃  node_id             VARCHAR(36)  FK → dag_nodes.id, INDEX                ┃
┃  sender              VARCHAR(100) NOT NULL, INDEX                          ┃
┃  recipient           VARCHAR(100) NOT NULL, INDEX                          ┃
┃  content             TEXT         NOT NULL                                 ┃
┃  timestamp           TIMESTAMP    NOT NULL                                 ┃
┃  tokens              INTEGER                                               ┃
┃  meta                JSON                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TABLE: cost_records                                                      ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  id                  INTEGER      PRIMARY KEY AUTOINCREMENT               ┃
┃  run_id              VARCHAR(36)  FK → workflow_runs.id, INDEX            ┃
┃  step_id             VARCHAR(36)  FK → workflow_steps.id, INDEX           ┃
┃  session_id          VARCHAR(36)  FK → sessions.id, INDEX                 ┃
┃  model               VARCHAR(100) NOT NULL, INDEX                          ┃
┃  prompt_tokens       INTEGER      DEFAULT 0                                ┃
┃  completion_tokens   INTEGER      DEFAULT 0                                ┃
┃  total_tokens        INTEGER      DEFAULT 0                                ┃
┃  cost_usd            NUMERIC(10,6) DEFAULT 0.0                             ┃
┃  timestamp           TIMESTAMP    NOT NULL                                 ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TABLE: files                                                             ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  id                  VARCHAR(36)  PRIMARY KEY                             ┃
┃  run_id              VARCHAR(36)  FK → workflow_runs.id, INDEX            ┃
┃  step_id             VARCHAR(36)  FK → workflow_steps.id, INDEX           ┃
┃  event_id            VARCHAR(36)  FK → execution_events.id, INDEX         ┃
┃  node_id             VARCHAR(36)  FK → dag_nodes.id, INDEX                ┃
┃  file_path           VARCHAR(1000) NOT NULL                                ┃
┃  file_type           VARCHAR(50)  NOT NULL, INDEX                          ┃
┃                      (code/data/plot/log/other)                            ┃
┃  size_bytes          BIGINT                                                ┃
┃  created_at          TIMESTAMP    NOT NULL                                 ┃
┃  meta                JSON                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TABLE: state_history (Audit Trail)                                      ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  id                  INTEGER      PRIMARY KEY AUTOINCREMENT               ┃
┃  entity_type         VARCHAR(50)  NOT NULL, INDEX                          ┃
┃                      (workflow_run/workflow_step)                          ┃
┃  entity_id           VARCHAR(36)  NOT NULL, INDEX                          ┃
┃  session_id          VARCHAR(36)  FK → sessions.id, INDEX                 ┃
┃  from_state          VARCHAR(50)  (NULL for initial)                       ┃
┃  to_state            VARCHAR(50)  NOT NULL, INDEX                          ┃
┃  transition_reason   TEXT                                                  ┃
┃  transitioned_by     VARCHAR(100) (user/system)                            ┃
┃  created_at          TIMESTAMP    NOT NULL                                 ┃
┃  meta                JSON                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TABLE: approval_requests                                                 ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  id                  VARCHAR(36)  PRIMARY KEY                             ┃
┃  run_id              VARCHAR(36)  FK → workflow_runs.id, INDEX            ┃
┃  step_id             VARCHAR(36)  FK → workflow_steps.id, INDEX           ┃
┃  status              VARCHAR(50)  NOT NULL, INDEX                          ┃
┃                      (pending/approved/rejected/modified)                  ┃
┃  requested_at        TIMESTAMP    NOT NULL                                 ┃
┃  resolved_at         TIMESTAMP                                             ┃
┃  context_snapshot    JSON                                                  ┃
┃  user_feedback       TEXT                                                  ┃
┃  resolution          VARCHAR(50)                                           ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### 3.3 Relationships Diagram

```
sessions (1) ─────┬───────► (N) workflow_runs
                  │
                  ├───────► (N) workflow_steps
                  │
                  ├───────► (N) dag_nodes
                  │
                  ├───────► (N) execution_events
                  │
                  ├───────► (N) cost_records
                  │
                  └───────► (N) state_history


workflow_runs (1) ┬───────► (N) workflow_steps
                  │
                  ├───────► (N) dag_nodes
                  │
                  ├───────► (N) messages
                  │
                  ├───────► (N) cost_records
                  │
                  ├───────► (N) execution_events
                  │
                  ├───────► (N) files
                  │
                  ├───────► (N) approval_requests
                  │
                  └───────► (N) checkpoints


dag_nodes (1) ────┬───────► (N) dag_edges (as from_node)
                  │
                  ├───────► (N) dag_edges (as to_node)
                  │
                  ├───────► (N) execution_events
                  │
                  ├───────► (N) messages
                  │
                  └───────► (N) files


execution_events (1) ┬────► (N) execution_events (parent-child)
                     │
                     ├────► (N) messages
                     │
                     └────► (N) files
```

---

## 4. Event Storage Mechanism

### 4.1 Three-Tier Storage Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EVENT STORAGE ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────────┘

TIER 1: IN-MEMORY EVENT QUEUE (Transient, Reconnection Support)
┌─────────────────────────────────────────────────────────────────────┐
│  EventQueue                                                          │
│  ├─ Purpose: Handle WebSocket reconnections                         │
│  ├─ Retention: 5 minutes (configurable)                             │
│  ├─ Max Size: 1000 events per run_id                                │
│  ├─ Structure: deque[QueuedEvent]                                   │
│  │    └─ QueuedEvent { event: WebSocketEvent, queued_at: float }   │
│  └─ Thread-Safe: Yes (threading.Lock)                               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ push(run_id, event)
                              │ get_events_since(run_id, timestamp)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Storage: Dict[str, deque[QueuedEvent]]                             │
│           {run_id: deque([event1, event2, ...])}                    │
│                                                                      │
│  Cleanup: Automatic (on push)                                       │
│           - Remove events older than retention_seconds              │
│           - Remove empty queues                                     │
└─────────────────────────────────────────────────────────────────────┘


TIER 2: WEBSOCKET REAL-TIME STREAMING (Ephemeral)
┌─────────────────────────────────────────────────────────────────────┐
│  WebSocketManager                                                    │
│  ├─ Active Connections: Dict[run_id, WebSocket]                     │
│  ├─ Stateless: All state in database                                │
│  └─ Functions:                                                       │
│      ├─ connect() → Send current state from DB                      │
│      ├─ send_event() → Broadcast to connected client                │
│      └─ disconnect() → Clean up connection                          │
└─────────────────────────────────────────────────────────────────────┘


TIER 3: DATABASE PERSISTENCE (Permanent)
┌─────────────────────────────────────────────────────────────────────┐
│  SQLAlchemy Models → PostgreSQL/SQLite                              │
│  ├─ execution_events: Fine-grained event tracking                   │
│  ├─ messages: Agent-to-agent communication                          │
│  ├─ cost_records: API usage and costs                               │
│  ├─ files: Generated/used files                                     │
│  ├─ state_history: State transition audit trail                     │
│  └─ workflow_steps: Step-level logs and status                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Event Persistence Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                       EVENT PERSISTENCE FLOW                            │
└────────────────────────────────────────────────────────────────────────┘

1. EVENT GENERATION (During Execution)
   ┌──────────────────────┐
   │  AG2 Agent Output    │
   │  ├─ Tool call        │
   │  ├─ Agent message    │
   │  ├─ Code execution   │
   │  └─ File generation  │
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │  AG2IOStreamCapture  │
   │  .print() / .send()  │
   └──────────┬───────────┘
              │
              ├──────────────────────┬──────────────────────────┐
              ▼                      ▼                          ▼
   ┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
   │  WebSocket      │    │  EventQueue      │    │  Database          │
   │  send_event()   │    │  push()          │    │  Repository.create │
   └─────────────────┘    └──────────────────┘    └────────────────────┘


2. DATABASE WRITE PATTERN
   ┌──────────────────────────────────────┐
   │  ExecutionService                    │
   │  (Task execution thread)             │
   └───────────┬──────────────────────────┘
               │
               │ Critical events only
               ▼
   ┌──────────────────────────────────────┐
   │  WorkflowRepository                  │
   │  ├─ create_run()                     │
   │  ├─ update_run_status()              │
   │  ├─ create_step()                    │
   │  └─ complete_step()                  │
   └───────────┬──────────────────────────┘
               │
               ▼
   ┌──────────────────────────────────────┐
   │  SQLAlchemy Session                  │
   │  ├─ db.add(record)                   │
   │  ├─ db.commit()                      │
   │  └─ db.refresh(record)               │
   └───────────┬──────────────────────────┘
               │
               ▼
   ┌──────────────────────────────────────┐
   │  PostgreSQL / SQLite                 │
   │  INSERT INTO execution_events ...    │
   └──────────────────────────────────────┘


3. EXECUTION EVENT CREATION
   ┌─────────────────────────────────────────────────────────────┐
   │  Event Creation Points:                                      │
   │                                                              │
   │  1. Workflow Start                                           │
   │     └─ create_run() → WorkflowRun record                    │
   │                                                              │
   │  2. Step Start                                               │
   │     └─ create_step() → WorkflowStep record                  │
   │                                                              │
   │  3. Agent Action (Captured in AG2IOStream)                  │
   │     ├─ Tool call → execution_event (type=tool_call)         │
   │     ├─ Code exec → execution_event (type=code_exec)         │
   │     ├─ File gen  → execution_event + File record            │
   │     └─ Message   → execution_event + Message record         │
   │                                                              │
   │  4. Cost Update                                              │
   │     └─ CostRecord.create()                                  │
   │                                                              │
   │  5. State Change                                             │
   │     └─ StateHistory.create()                                │
   └─────────────────────────────────────────────────────────────┘
```

---

## 5. WebSocket Event System

### 5.1 WebSocket Event Types

```python
# Complete Event Type Hierarchy
WebSocketEventType (Enum):
├─ Connection Events
│  ├─ CONNECTED
│  ├─ DISCONNECTED
│  └─ RECONNECTED
│
├─ Workflow Lifecycle
│  ├─ WORKFLOW_STARTED
│  ├─ WORKFLOW_STATE_CHANGED
│  ├─ WORKFLOW_PAUSED
│  ├─ WORKFLOW_RESUMED
│  ├─ WORKFLOW_COMPLETED
│  └─ WORKFLOW_FAILED
│
├─ Step Execution
│  ├─ STEP_STARTED
│  ├─ STEP_PROGRESS
│  ├─ STEP_COMPLETED
│  └─ STEP_FAILED
│
├─ Retry Events
│  ├─ STEP_RETRY_STARTED
│  ├─ STEP_RETRY_BACKOFF
│  ├─ STEP_RETRY_SUCCEEDED
│  └─ STEP_RETRY_EXHAUSTED
│
├─ DAG Events
│  ├─ DAG_CREATED
│  ├─ DAG_UPDATED
│  └─ DAG_NODE_STATUS_CHANGED
│
├─ Agent Events
│  ├─ AGENT_MESSAGE
│  ├─ AGENT_THINKING
│  └─ AGENT_TOOL_CALL
│
├─ Approval Events
│  ├─ APPROVAL_REQUESTED
│  └─ APPROVAL_RECEIVED
│
├─ Cost & Metrics
│  ├─ COST_UPDATE
│  └─ METRIC_UPDATE
│
├─ File Events
│  ├─ FILE_CREATED
│  └─ FILE_UPDATED
│
├─ Execution Events
│  └─ EVENT_CAPTURED
│
└─ System Events
   ├─ ERROR_OCCURRED
   ├─ HEARTBEAT
   └─ PONG
```

### 5.2 WebSocket Protocol

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WEBSOCKET PROTOCOL FLOW                           │
└─────────────────────────────────────────────────────────────────────┘

CLIENT CONNECTS
┌─────────────────────────┐
│  ws://host/ws/{task_id} │
│  Connection Request     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  WebSocketManager       │
│  .connect(websocket,    │
│           run_id)       │
└───────────┬─────────────┘
            │
            ├──────────────► 1. Send CONNECTED event
            │
            ├──────────────► 2. Load current state from DB
            │                   ├─ WorkflowRun status
            │                   ├─ WorkflowSteps
            │                   ├─ DAGNodes + Edges
            │                   └─ Recent ExecutionEvents
            │
            └──────────────► 3. Send state snapshot events
                               ├─ WORKFLOW_STATE_CHANGED
                               ├─ DAG_CREATED
                               └─ Recent EVENT_CAPTURED


DURING EXECUTION
┌─────────────────────────┐
│  Execution Thread       │
│  ├─ AG2 agent runs      │
│  ├─ Outputs captured    │
│  └─ Events generated    │
└───────────┬─────────────┘
            │
            ├──────────────────────────┬───────────────────────┐
            ▼                          ▼                       ▼
┌───────────────────┐      ┌──────────────────┐    ┌──────────────────┐
│  WebSocket        │      │  EventQueue      │    │  Database        │
│  broadcast        │      │  push(event)     │    │  persist(event)  │
└───────────────────┘      └──────────────────┘    └──────────────────┘
            │
            ▼
┌─────────────────────────┐
│  Frontend receives      │
│  real-time updates      │
└─────────────────────────┘


CLIENT RECONNECTS (after disconnect)
┌─────────────────────────┐
│  Reconnection attempt   │
│  with last_timestamp    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  EventQueue             │
│  .get_events_since(     │
│    run_id, timestamp)   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Send missed events     │
│  (from in-memory queue) │
└─────────────────────────┘


HEARTBEAT / KEEPALIVE
┌─────────────────────────┐
│  Client sends "ping"    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Server responds "pong" │
│  event_type: PONG       │
└─────────────────────────┘
```

### 5.3 Event Data Structure

```typescript
// Generic WebSocket Event Structure
interface WebSocketEvent {
  event_type: WebSocketEventType;
  timestamp: string;  // ISO 8601
  run_id?: string;
  session_id?: string;
  data: {
    // Event-specific data (see section 9)
    [key: string]: any;
  };
}

// Example: COST_UPDATE event
{
  "event_type": "cost_update",
  "timestamp": "2026-01-20T10:30:45.123Z",
  "run_id": "abc-123-def-456",
  "session_id": "session-xyz",
  "data": {
    "run_id": "abc-123-def-456",
    "step_id": "step-789",
    "model": "gpt-4o",
    "tokens": 1024,
    "cost_usd": 0.0512,
    "total_cost_usd": 0.2048
  }
}

// Example: EVENT_CAPTURED event
{
  "event_type": "event_captured",
  "timestamp": "2026-01-20T10:30:45.456Z",
  "run_id": "abc-123-def-456",
  "data": {
    "event_id": "evt-001",
    "node_id": "node-456",
    "event_type": "agent_call",
    "event_subtype": "start",
    "agent_name": "engineer",
    "timestamp": "2026-01-20T10:30:45.456Z",
    "execution_order": 1,
    "depth": 0
  }
}
```

---

## 6. API Endpoints

### 6.1 Complete API Inventory

```
┌─────────────────────────────────────────────────────────────────────┐
│                        REST API ENDPOINTS                            │
└─────────────────────────────────────────────────────────────────────┘

SYSTEM ENDPOINTS
├─ GET  /                           → API info
└─ GET  /api/health                 → Health check


TASK EXECUTION
└─ POST /api/task/submit            → Submit task for execution
    Body: {
      task: string,
      config: {
        mode: "one-shot" | "planning-control",
        agent: "engineer" | "researcher",
        model: string,
        workDir: string
      }
    }
    Response: {
      task_id: string,
      status: "queued"
    }


FILES & ARTIFACTS
├─ GET    /api/files/list           → List files in work directory
│   Query: ?directory={path}
│
├─ GET    /api/files/content        → Get file contents
│   Query: ?path={filepath}
│
├─ DELETE /api/files/clear-directory → Clear work directory
│   Query: ?directory={path}
│
├─ GET    /api/files/images         → List image files
│   Query: ?directory={path}
│
└─ GET    /api/files/serve-image    → Serve image file
    Query: ?path={filepath}


CREDENTIALS MANAGEMENT
├─ GET  /api/credentials/test-all   → Test all API credentials
├─ POST /api/credentials/test       → Test specific credential
│   Body: { provider: string, api_key: string }
├─ POST /api/credentials/store      → Store credentials
│   Body: { provider: string, api_key: string }
└─ GET  /api/credentials/status     → Get credentials status


ARXIV INTEGRATION
├─ POST /api/arxiv/filter           → Filter ArXiv papers
│   Body: { query: string, filters: object }
└─ POST /api/enhance-input          → Enhance task with context
    Body: { query: string }


WORKFLOW & EXECUTION
├─ POST /api/runs/{run_id}/branch              → Create workflow branch
│   Body: { branch_name: string, hypothesis: string }
│
├─ POST /api/runs/{run_id}/play-from-node      → Resume from node
│   Body: { node_id: string }
│
├─ GET  /api/runs/{run_id}/branch-tree         → Get branch hierarchy
├─ GET  /api/runs/{run_id}/resumable-nodes     → Get resumable nodes
├─ GET  /api/runs/{run_id}/history             → Get execution history
├─ GET  /api/runs/{run_id}/files               → Get run files
│
├─ GET  /api/branches/compare                  → Compare branches
│   Query: ?run_id_1={id}&run_id_2={id}


NODE & EVENT QUERIES (⚠️ All require run_id resolution)
├─ GET  /api/nodes/{node_id}/events            → Get node events
│   Query: ?run_id={task_id}  (will be resolved to db_run_id)
│   ⚠️ CRITICAL: run_id parameter is REQUIRED to avoid cross-run contamination
│   Response: [{
│     event_id: string,
│     event_type: string,
│     agent_name: string,
│     timestamp: string,
│     ...
│   }]
│
├─ GET  /api/nodes/{node_id}/execution-summary → Get execution summary
│   Response: {
│     total_events: number,
│     by_type: { [type]: count },
│     by_agent: { [agent]: count },
│     total_duration_ms: number,
│     ...
│   }
│
├─ GET  /api/nodes/{node_id}/files             → Get node files
│
└─ GET  /api/events/{event_id}/tree            → Get event tree
    Response: {
      event: ExecutionEvent,
      children: [ExecutionEvent],
      total_descendants: number
    }


WEBSOCKET
└─ WS   /ws/{task_id}                          → WebSocket connection
    Protocol:
      ← CONNECTED
      ← WORKFLOW_STATE_CHANGED
      ← DAG_CREATED
      ← EVENT_CAPTURED
      ← COST_UPDATE
      ...
      → {"action": "pause"}
      → {"action": "resume"}
      → {"action": "cancel"}
```

### 6.3 Event Query Patterns

**CRITICAL: All queries must use db_run_id (UUID), not task_id!**

```sql
-- Common queries for events

-- 1. Get all events for a run (chronological)
-- ⚠️ IMPORTANT: 'abc-123' here is db_run_id (UUID), NOT task_id
-- APIs must call resolve_run_id(task_id) first to get this UUID
SELECT * FROM execution_events
WHERE run_id = 'abc-123'  -- This is UUID from workflow_runs.id
ORDER BY execution_order ASC;

-- 2. Get events for a specific node
SELECT * FROM execution_events
WHERE node_id = 'node-456'
ORDER BY execution_order ASC;

-- 3. Get only top-level events (no nested)
SELECT * FROM execution_events
WHERE run_id = 'abc-123' AND depth = 0
ORDER BY execution_order ASC;

-- 4. Get event tree (parent + all children)
WITH RECURSIVE event_tree AS (
  -- Base: parent event
  SELECT * FROM execution_events WHERE id = 'evt-001'
  UNION ALL
  -- Recursive: children
  SELECT e.* FROM execution_events e
  INNER JOIN event_tree t ON e.parent_event_id = t.id
)
SELECT * FROM event_tree ORDER BY depth, execution_order;

-- 5. Get execution summary by type
SELECT 
  event_type,
  COUNT(*) as count,
  SUM(duration_ms) as total_duration_ms
FROM execution_events
WHERE node_id = 'node-456'
GROUP BY event_type;

-- 6. Get agent activity timeline
SELECT 
  agent_name,
  event_type,
  timestamp,
  duration_ms
FROM execution_events
WHERE run_id = 'abc-123'
ORDER BY timestamp ASC;

-- 7. Get cost breakdown by model
SELECT 
  model,
  SUM(prompt_tokens) as total_prompt_tokens,
  SUM(completion_tokens) as total_completion_tokens,
  SUM(cost_usd) as total_cost_usd
FROM cost_records
WHERE run_id = 'abc-123'
GROUP BY model;

-- 8. Get files created during execution
SELECT 
  f.file_path,
  f.file_type,
  e.event_type,
  e.timestamp
FROM files f
LEFT JOIN execution_events e ON f.event_id = e.id
WHERE f.run_id = 'abc-123'
ORDER BY f.created_at ASC;
```

---

## 7. Event Queue System

### 7.1 EventQueue Implementation

```python
# Conceptual structure
class EventQueue:
    """Thread-safe in-memory event queue"""
    
    def __init__(self, max_size=1000, retention_seconds=300):
        self.max_size = max_size
        self.retention_seconds = retention_seconds
        self.queues: Dict[str, deque[QueuedEvent]] = {}
        self.lock = Lock()
    
    def push(self, run_id: str, event: WebSocketEvent):
        """Add event to queue (thread-safe)"""
        with self.lock:
            if run_id not in self.queues:
                self.queues[run_id] = deque(maxlen=self.max_size)
            
            queued_event = QueuedEvent(
                event=event,
                queued_at=time.time()
            )
            self.queues[run_id].append(queued_event)
            self._cleanup_old_events(run_id)
    
    def get_events_since(self, run_id: str, since_timestamp: float):
        """Get events after timestamp (for reconnection)"""
        with self.lock:
            if run_id not in self.queues:
                return []
            
            return [
                qe.event
                for qe in self.queues[run_id]
                if qe.queued_at > since_timestamp
            ]
    
    def _cleanup_old_events(self, run_id: str):
        """Remove events older than retention period"""
        now = time.time()
        cutoff = now - self.retention_seconds
        
        queue = self.queues[run_id]
        while queue and queue[0].queued_at < cutoff:
            queue.popleft()

# Global instance
event_queue = EventQueue()
```

### 7.2 Queue Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                      EVENT QUEUE LIFECYCLE                           │
└─────────────────────────────────────────────────────────────────────┘

EVENT PUSH (during execution)
┌──────────────────────┐
│  WebSocket event     │
│  generated           │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  event_queue.push(   │
│    run_id, event)    │
└──────────┬───────────┘
           │
           ├─► 1. Create QueuedEvent wrapper
           │      (add timestamp)
           │
           ├─► 2. Add to deque for run_id
           │      (creates deque if needed)
           │
           ├─► 3. Enforce max_size limit
           │      (deque automatically drops oldest)
           │
           └─► 4. Cleanup old events
                  (remove events older than retention_seconds)


EVENT RETRIEVAL (on reconnection)
┌──────────────────────┐
│  Client reconnects   │
│  with last_timestamp │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  event_queue.        │
│    get_events_since( │
│      run_id,         │
│      timestamp)      │
└──────────┬───────────┘
           │
           ├─► 1. Lock queue
           │
           ├─► 2. Filter by timestamp
           │
           └─► 3. Return matching events


PERIODIC CLEANUP
┌──────────────────────┐
│  Background task     │
│  (optional)          │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  event_queue.        │
│    cleanup_all_      │
│    old_events()      │
└──────────┬───────────┘
           │
           ├─► For each run_id:
           │   └─► Remove events older than retention
           │
           └─► Remove empty queues


QUEUE MEMORY PROFILE
┌─────────────────────────────────────────────────┐
│  Max Memory Per Run (conservative estimate):   │
│                                                 │
│  1000 events × 2 KB avg = 2 MB per run         │
│                                                 │
│  With 100 concurrent runs = 200 MB total       │
│                                                 │
│  Retention: 5 minutes (configurable)           │
│  Cleanup: Automatic on push + periodic         │
└─────────────────────────────────────────────────┘
```

---

## 8. Service Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER ARCHITECTURE                       │
└─────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                          BACKEND (FastAPI)                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐         ┌──────────────┐         ┌────────────┐ │
│  │  main.py     │────────►│  Services    │────────►│  Database  │ │
│  │  (API Layer) │         │  Layer       │         │  Layer     │ │
│  └──────────────┘         └──────────────┘         └────────────┘ │
│         │                        │                        │         │
│         │                        │                        │         │
│   HTTP/WebSocket        Business Logic            Persistence      │
│   Endpoints             & Orchestration            (SQLAlchemy)    │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘

DETAILED SERVICE COMPONENTS:

1. WorkflowService (workflow_service.py)
   ┌──────────────────────────────────────────────────────┐
   │  Responsibilities:                                    │
   │  ├─ Create workflow runs in DB                       │
   │  ├─ Manage session lifecycle                         │
   │  ├─ State machine transitions (pause/resume/cancel)  │
   │  ├─ Track active runs                                │
   │  └─ Integrate with DAG system                        │
   │                                                       │
   │  Key Methods:                                         │
   │  ├─ create_workflow_run(task_id, description, ...)   │
   │  ├─ complete_workflow(task_id, results)              │
   │  ├─ pause_workflow(task_id)                          │
   │  ├─ resume_workflow(task_id)                         │
   │  └─ cancel_workflow(task_id)                         │
   └──────────────────────────────────────────────────────┘

2. ExecutionService (execution_service.py)
   ┌──────────────────────────────────────────────────────┐
   │  Responsibilities:                                    │
   │  ├─ Execute CMBAgent tasks                           │
   │  ├─ Handle pause/resume/cancel flags                 │
   │  ├─ Capture stdout/stderr output                     │
   │  ├─ Stream events to WebSocket                       │
   │  └─ Track execution state                            │
   │                                                       │
   │  Key Methods:                                         │
   │  ├─ execute_task(task_id, task, config, on_output)   │
   │  ├─ is_paused(task_id) → bool                        │
   │  ├─ set_paused(task_id, paused)                      │
   │  ├─ wait_if_paused(task_id)                          │
   │  └─ _run_cmbagent(task_id, task, config, work_dir)   │
   └──────────────────────────────────────────────────────┘

3. ConnectionManager (connection_manager.py)
   ┌──────────────────────────────────────────────────────┐
   │  Responsibilities:                                    │
   │  ├─ Manage WebSocket connections                     │
   │  ├─ Send events to clients                           │
   │  ├─ Handle connection/disconnection                  │
   │  ├─ Integrate with EventQueue                        │
   │  └─ Send state snapshots on connect                  │
   │                                                       │
   │  Key Methods:                                         │
   │  ├─ connect(websocket, task_id, run_id)              │
   │  ├─ disconnect(task_id)                              │
   │  ├─ send_event(task_id, event)                       │
   │  ├─ send_workflow_started(...)                       │
   │  ├─ send_workflow_completed(...)                     │
   │  └─ broadcast_to_run(run_id, event)                  │
   └──────────────────────────────────────────────────────┘

4. WebSocketManager (websocket_manager.py)
   ┌──────────────────────────────────────────────────────┐
   │  Responsibilities:                                    │
   │  ├─ Low-level WebSocket handling                     │
   │  ├─ Load current state from DB on connect            │
   │  ├─ Send missed events from EventQueue               │
   │  └─ Process client commands (pause/resume)           │
   │                                                       │
   │  Key Methods:                                         │
   │  ├─ connect(websocket, run_id)                       │
   │  ├─ send_current_state(run_id)                       │
   │  ├─ send_event(run_id, event)                        │
   │  ├─ handle_client_message(run_id, message)           │
   │  └─ disconnect(run_id)                               │
   └──────────────────────────────────────────────────────┘

SERVICE INTERACTION FLOW:

┌─────────────┐
│  API Route  │  POST /api/task/submit
└──────┬──────┘
       │
       ▼
┌────────────────────────┐
│  WorkflowService       │
│  .create_workflow_run()│
└──────┬─────────────────┘
       │
       ├──► Create DB record (WorkflowRun)
       │
       ▼
┌────────────────────────┐
│  ExecutionService      │
│  .execute_task()       │
└──────┬─────────────────┘
       │
       ├──► Run CMBAgent in thread
       │
       ├──► Capture output (AG2IOStreamCapture)
       │
       ▼
┌────────────────────────┐
│  ConnectionManager     │
│  .send_event()         │
└──────┬─────────────────┘
       │
       ├──► Push to EventQueue
       │
       ├──► Broadcast to WebSocket
       │
       └──► Persist to Database (if critical event)
```

---

## 9. Event Types & Data Models

### 9.1 Pydantic Models (websocket_events.py)

```python
# Base event model
class WebSocketEvent(BaseModel):
    event_type: WebSocketEventType
    timestamp: datetime
    run_id: Optional[str]
    session_id: Optional[str]
    data: Dict[str, Any]

# Specific data models for each event type

class WorkflowStartedData(BaseModel):
    run_id: str
    task_description: str
    agent: str
    model: str
    work_dir: Optional[str]

class StepStartedData(BaseModel):
    step_id: str
    step_number: int
    step_description: str
    agent: str

class CostUpdateData(BaseModel):
    run_id: str
    step_id: Optional[str]
    model: str
    tokens: int
    cost_usd: float
    total_cost_usd: float

class EventCapturedData(BaseModel):
    event_id: str
    node_id: Optional[str]
    event_type: str          # e.g., "agent_call", "tool_call"
    event_subtype: Optional[str]  # e.g., "start", "complete"
    agent_name: Optional[str]
    timestamp: str
    execution_order: int
    depth: int

class DAGNodeStatusChangedData(BaseModel):
    node_id: str
    old_status: str
    new_status: str
    error: Optional[str]

# ... (20+ more data models)
```

### 9.2 Event Classification

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EXECUTION EVENT CLASSIFICATION                    │
└─────────────────────────────────────────────────────────────────────┘

event_type           event_subtype     Description
─────────────────────────────────────────────────────────────────────
agent_call           start             Agent begins execution
agent_call           complete          Agent completes execution
agent_call           error             Agent encounters error

tool_call            start             Tool invocation begins
tool_call            complete          Tool returns result
tool_call            error             Tool fails

code_exec            start             Code execution begins
code_exec            complete          Code execution successful
code_exec            error             Code execution failed

file_gen             complete          File created/modified
file_gen             error             File operation failed

handoff              complete          Agent handoff occurred
handoff              pending           Handoff requested

approval_requested   pending           Human approval needed
approval_requested   approved          Approval granted
approval_requested   rejected          Approval denied

state_transition     complete          State change occurred
                                       (e.g., running → paused)

error                critical          Critical error
error                warning           Non-fatal warning

info                 debug             Debug information
info                 trace             Detailed trace
```

---

## 10. Complete Data Flow Diagrams

### 10.1 Full System Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     COMPLETE END-TO-END DATA FLOW                            │
└─────────────────────────────────────────────────────────────────────────────┘

PHASE 1: TASK SUBMISSION
┌──────────────┐
│   Frontend   │
│   (Next.js)  │
└──────┬───────┘
       │
       │ POST /api/task/submit
       │ { task, config: { mode, agent, model, workDir } }
       │
       ▼
┌──────────────────────────────┐
│   Backend main.py            │
│   @app.post("/api/task/...")│
└──────┬───────────────────────┘
       │
       │ 1. Generate task_id = f"task_{timestamp}_{random}"
       │ 2. Call workflow_service.create_workflow_run()
       │
       ▼
┌──────────────────────────────┐     ┌─────────────────────────┐
│   WorkflowService            │────►│  Database               │
│   .create_workflow_run()     │     │  INSERT WorkflowRun     │
│                              │     │  (id = UUID)            │
│   Creates:                   │     │                         │
│   • db_run_id: UUID (DB PK)  │     │  Stores mapping:        │
│   • task_id: User-facing ID  │     │  task_id ↔ db_run_id   │
│   • Stores in _active_runs   │     │                         │
└──────┬───────────────────────┘     └─────────────────────────┘
       │
       │ 3. Create asyncio task for execution
       │ 4. Return { task_id, run_id: UUID, db_run_id: UUID }
       │    ⚠️ Frontend receives task_id, uses in all API calls
       │
       ▼
┌──────────────┐
│   Frontend   │  Receives task_id (user-facing)
│              │  Stores for all subsequent API calls
└──────────────┘


PHASE 2: WEBSOCKET CONNECTION
┌──────────────┐
│   Frontend   │  ws://host/ws/{task_id}
└──────┬───────┘
       │
       ▼
┌──────────────────────────────┐
│   WebSocketManager           │
│   .connect(websocket, ...)   │
└──────┬───────────────────────┘
       │
       ├─► 1. Accept connection
       │
       ├─► 2. Send CONNECTED event
       │
       ├─► 3. Load state from database:
       │      ├─ WorkflowRun record
       │      ├─ WorkflowSteps
       │      ├─ DAGNodes + Edges
       │      └─ Recent ExecutionEvents
       │
       └─► 4. Send state snapshot events:
              ├─ WORKFLOW_STATE_CHANGED
              ├─ DAG_CREATED
              └─ EVENT_CAPTURED (recent)


PHASE 3: TASK EXECUTION
┌──────────────────────────────┐
│   ExecutionService           │
│   .execute_task()            │
└──────┬───────────────────────┘
       │
       ├─► 1. Setup work directory
       │
       ├─► 2. Send WORKFLOW_STARTED event
       │
       ├─► 3. Create AG2IOStreamCapture
       │      └─► Intercepts all stdout/stderr
       │
       ├─► 4. Run CMBAgent
       │      │
       │      ├─► Agent generates output
       │      │
       │      ▼
       │   ┌────────────────────────────┐
       │   │  AG2IOStreamCapture        │
       │   │  .print() / .send()        │
       │   └────────┬───────────────────┘
       │            │
       │            ├──► Parse output
       │            │    ├─ Detect agent messages
       │            │    ├─ Detect tool calls
       │            │    ├─ Detect cost updates
       │            │    └─ Detect errors
       │            │
       │            ▼
       │   ┌────────────────────────────┐
       │   │  Generate WebSocket Event  │
       │   └────────┬───────────────────┘
       │            │
       │            ├──────────────────┬──────────────────┬─────────────────┐
       │            ▼                  ▼                  ▼                 ▼
       │   ┌─────────────────┐ ┌─────────────────┐ ┌────────────┐ ┌─────────────┐
       │   │  WebSocket      │ │  EventQueue     │ │  Database  │ │  UI Update  │
       │   │  send_event()   │ │  push()         │ │  persist() │ │  (real-time)│
       │   └─────────────────┘ └─────────────────┘ └────────────┘ └─────────────┘
       │
       └─► 5. On completion:
              ├─ Send WORKFLOW_COMPLETED event
              └─ Update database (status, completed_at)


PHASE 4: EVENT PERSISTENCE (Parallel to Phase 3)
┌──────────────────────────────┐
│  Critical Events Only        │
│  (agent_call, tool_call, etc)│
└──────┬───────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  Database Layer              │
│  (SQLAlchemy)                │
└──────┬───────────────────────┘
       │
       ├─► INSERT INTO execution_events
       │   (event_type, agent_name, inputs, outputs, ...)
       │
       ├─► INSERT INTO messages
       │   (sender, recipient, content, ...)
       │
       ├─► INSERT INTO cost_records
       │   (model, tokens, cost_usd, ...)
       │
       ├─► INSERT INTO files
       │   (file_path, file_type, ...)
       │
       └─► INSERT INTO state_history
           (entity_type, from_state, to_state, ...)


PHASE 5: CLIENT RECONNECTION (if disconnected)
┌──────────────┐
│   Frontend   │  Reconnects with last_timestamp
└──────┬───────┘
       │
       ▼
┌──────────────────────────────┐
│   WebSocketManager           │
│   .connect(websocket, ...)   │
└──────┬───────────────────────┘
       │
       ├─► 1. Send RECONNECTED event
       │
       ├─► 2. Query EventQueue:
       │      event_queue.get_events_since(run_id, timestamp)
       │
       └─► 3. Send all missed events in order


PHASE 6: HISTORICAL QUERIES (after execution)
┌──────────────┐
│   Frontend   │
└──────┬───────┘
       │
       │ GET /api/runs/{run_id}/history
       │ GET /api/nodes/{node_id}/events
       │ GET /api/events/{event_id}/tree
       │
       ▼
┌──────────────────────────────┐
│   Backend API Routes         │
└──────┬───────────────────────┘
       │
       ▼
┌──────────────────────────────┐     ┌─────────────────────────┐
│   Repository Layer           │────►│  Database               │
│   (query methods)            │     │  SELECT ... FROM ...    │
└──────┬───────────────────────┘     └─────────────────────────┘
       │
       │ Return JSON response
       │
       ▼
┌──────────────┐
│   Frontend   │  Display in UI
└──────────────┘
```

### 10.2 Event Hierarchy & Relationships

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EVENT RELATIONSHIP DIAGRAM                            │
└─────────────────────────────────────────────────────────────────────────────┘

Session
  │
  ├─► WorkflowRun #1 (run_id: abc-123)
  │     │
  │     ├─► WorkflowStep #1 (step_id: step-001)
  │     │     └─► Messages, CostRecords, Files
  │     │
  │     ├─► WorkflowStep #2 (step_id: step-002)
  │     │
  │     ├─► DAGNode #1 (node_id: node-001, type: planning)
  │     │     │
  │     │     ├─► ExecutionEvent #1 (evt-001)
  │     │     │     ├─ event_type: agent_call
  │     │     │     ├─ agent_name: planner
  │     │     │     ├─ execution_order: 1
  │     │     │     ├─ depth: 0
  │     │     │     │
  │     │     │     ├─► ExecutionEvent #2 (evt-002, parent: evt-001)
  │     │     │     │     ├─ event_type: tool_call
  │     │     │     │     ├─ depth: 1
  │     │     │     │     └─ execution_order: 2
  │     │     │     │
  │     │     │     └─► ExecutionEvent #3 (evt-003, parent: evt-001)
  │     │     │           ├─ event_type: code_exec
  │     │     │           └─ depth: 1
  │     │     │
  │     │     ├─► ExecutionEvent #4 (evt-004)
  │     │     │     └─ event_type: agent_call (complete)
  │     │     │
  │     │     └─► Messages, Files linked to events
  │     │
  │     ├─► DAGNode #2 (node_id: node-002, type: agent)
  │     │     └─► ExecutionEvents (similar hierarchy)
  │     │
  │     ├─► DAGEdge (from: node-001, to: node-002)
  │     │
  │     ├─► CostRecords (aggregated by run/step)
  │     │
  │     └─► StateHistory (workflow state transitions)
  │
  └─► WorkflowRun #2 (run_id: def-456)
        └─► ... (similar structure)


LINKED ENTITIES:

ExecutionEvent (evt-001)
  ├─► child_events: [evt-002, evt-003]
  ├─► messages: [msg-001, msg-002]
  └─► files: [file-001]

Message (msg-001)
  ├─► run_id: abc-123
  ├─► step_id: step-001
  ├─► event_id: evt-001
  └─► node_id: node-001

File (file-001)
  ├─► run_id: abc-123
  ├─► step_id: step-001
  ├─► event_id: evt-001
  └─► node_id: node-001
```

---

---

## 11. DAG Nodes - Usage & Implementation

### 11.1 Purpose & Role

The `dag_nodes` table is central to CMBAgent's workflow orchestration. It represents the **Directed Acyclic Graph (DAG)** that defines the execution plan for a workflow.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DAG NODES PURPOSE                               │
└─────────────────────────────────────────────────────────────────────┘

PURPOSE:
├─ Represent workflow execution structure as a graph
├─ Define dependencies between tasks
├─ Enable parallel execution of independent tasks
├─ Track execution status at granular level
├─ Support branching and conditional workflows
└─ Provide visual representation in UI

KEY CONCEPTS:
├─ Node = A discrete unit of work (planning, agent task, approval, etc.)
├─ Edge = Dependency relationship between nodes
├─ Order = Topological sort order for execution
└─ Level = Parallel execution groups
```

### 11.2 Node Types

```python
┌─────────────────────────────────────────────────────────────────────┐
│                         DAG NODE TYPES                               │
└─────────────────────────────────────────────────────────────────────┘

PLANNING (Root Node)
├─ Purpose: Represents the planning phase
├─ Agent: planner
├─ Always first node in DAG
└─ Creates the execution plan that generates other nodes

CONTROL (Conditional Logic)
├─ Purpose: Decision points in workflow
├─ Evaluates conditions to determine next steps
├─ Can route to different branches
└─ Example: Success/failure routing

AGENT (Execution Node)
├─ Purpose: Execute specific agent tasks
├─ Agent: engineer, researcher, writer, etc.
├─ Most common node type
├─ Contains task description and inputs
└─ Tracks execution state and outputs

APPROVAL (Human-in-the-Loop)
├─ Purpose: Require human approval before proceeding
├─ Pauses workflow until user responds
├─ Stores approval context and decision
└─ Can be approved/rejected/modified

PARALLEL_GROUP (Concurrent Execution)
├─ Purpose: Group of tasks that can run in parallel
├─ Contains metadata about parallel execution
├─ Resource limits and coordination
└─ Wait for all to complete before continuing

TERMINATOR (End Node)
├─ Purpose: Marks workflow completion
├─ Always last node in DAG
├─ Triggers cleanup and finalization
└─ Records final workflow state
```

### 11.3 DAG Building Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DAG BUILDING WORKFLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

STEP 1: PLANNING AGENT GENERATES PLAN
┌──────────────────────┐
│  Planner Agent       │
│  Input: User task    │
└──────────┬───────────┘
           │
           │ Generates JSON plan
           ▼
┌──────────────────────┐
│  Plan JSON           │
│  {                   │
│    "steps": [        │
│      {               │
│        "task": "...",│
│        "agent": "...",
│        "depends_on": [...]
│      }               │
│    ]                 │
│  }                   │
└──────────┬───────────┘
           │
           ▼

STEP 2: DAG BUILDER CONVERTS PLAN TO NODES
┌──────────────────────────────────────────┐
│  DAGBuilder.build_from_plan()            │
│  ├─ Create PLANNING node (root)         │
│  ├─ Parse each step from plan            │
│  ├─ Create AGENT nodes for each step     │
│  ├─ Create DAGEdges for dependencies     │
│  └─ Create TERMINATOR node (end)         │
└──────────┬───────────────────────────────┘
           │
           │ INSERT INTO dag_nodes
           │ INSERT INTO dag_edges
           ▼
┌──────────────────────────────────────────┐
│  Database (Persisted DAG)                │
│                                          │
│  dag_nodes:                              │
│  ├─ node-001 (PLANNING) order_index=0   │
│  ├─ node-002 (AGENT) order_index=1      │
│  ├─ node-003 (AGENT) order_index=2      │
│  └─ node-004 (TERMINATOR) order_index=3 │
│                                          │
│  dag_edges:                              │
│  ├─ node-001 → node-002                 │
│  ├─ node-002 → node-003                 │
│  └─ node-003 → node-004                 │
└──────────┬───────────────────────────────┘
           │
           ▼

STEP 3: TOPOLOGICAL SORT FOR EXECUTION ORDER
┌──────────────────────────────────────────┐
│  TopologicalSorter                       │
│  .get_execution_order()                  │
│  ├─ Analyze dependencies                 │
│  ├─ Identify parallel opportunities      │
│  └─ Return level-by-level execution plan │
└──────────┬───────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Execution Order (Levels)                │
│  [                                       │
│    {                                     │
│      "level": 0,                         │
│      "nodes": [node-001],                │
│      "parallel": false                   │
│    },                                    │
│    {                                     │
│      "level": 1,                         │
│      "nodes": [node-002, node-003],      │
│      "parallel": true  # No dependencies!│
│    },                                    │
│    {                                     │
│      "level": 2,                         │
│      "nodes": [node-004],                │
│      "parallel": false                   │
│    }                                     │
│  ]                                       │
└──────────────────────────────────────────┘
```

### 11.4 DAG Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DAG EXECUTION PROCESS                                │
└─────────────────────────────────────────────────────────────────────────────┘

DAGExecutor.execute(run_id, agent_executor_func)
│
├─► LEVEL 0: Execute PLANNING node
│   └─ TopologicalSorter.get_execution_order(run_id)
│   └─ Execute node-001 (PLANNING)
│       ├─ Update status: pending → running
│       ├─ Call agent_executor_func(node_id, agent, task)
│       ├─ Create ExecutionEvents for node
│       └─ Update status: running → completed
│
├─► LEVEL 1: Execute AGENT nodes (parallel if possible)
│   ├─ Check parallel flag
│   ├─ If parallel AND nodes ≤ max_parallel:
│   │   └─ ThreadPoolExecutor
│   │       ├─ Execute node-002 in thread 1
│   │       └─ Execute node-003 in thread 2
│   │       └─ Wait for all to complete
│   └─ Else: Sequential execution
│       ├─ Execute node-002
│       └─ Execute node-003
│
├─► LEVEL 2: Execute TERMINATOR node
│   └─ Execute node-004 (TERMINATOR)
│       ├─ Mark workflow as completed
│       └─ Trigger cleanup
│
└─► Return execution results
    {
      "run_id": "...",
      "levels_executed": 3,
      "nodes_executed": 4,
      "nodes_failed": 0,
      "level_results": [...]
    }


NODE EXECUTION DETAIL:
┌──────────────────────────────────────────┐
│  _execute_node(node_id, agent, task)    │
└──────────┬───────────────────────────────┘
           │
           ├─► 1. Load node from database
           │      db.query(DAGNode).filter(id=node_id)
           │
           ├─► 2. Update node status
           │      UPDATE dag_nodes SET status='running'
           │
           ├─► 3. Create WorkflowStep (if needed)
           │      INSERT INTO workflow_steps
           │
           ├─► 4. Execute agent
           │      agent_executor_func(node_id, agent, task)
           │
           ├─► 5. Capture events
           │      INSERT INTO execution_events (node_id=node_id)
           │
           ├─► 6. Store outputs
           │      INSERT INTO files (node_id=node_id)
           │      INSERT INTO messages (node_id=node_id)
           │
           ├─► 7. Send WebSocket events
           │      DAG_NODE_STATUS_CHANGED
           │
           └─► 8. Update node status
                  UPDATE dag_nodes SET status='completed'
```

### 11.5 Real-World Usage Examples

```sql
-- Example 1: Get all nodes for a workflow run (ordered)
SELECT * FROM dag_nodes
WHERE run_id = 'abc-123'
ORDER BY order_index ASC;

-- Example 2: Get execution status of all nodes
SELECT 
    node_type,
    status,
    COUNT(*) as count
FROM dag_nodes
WHERE run_id = 'abc-123'
GROUP BY node_type, status;

-- Example 3: Find nodes ready to execute (dependencies completed)
WITH completed_nodes AS (
    SELECT id FROM dag_nodes
    WHERE run_id = 'abc-123' AND status = 'completed'
)
SELECT dn.* FROM dag_nodes dn
WHERE dn.run_id = 'abc-123'
  AND dn.status = 'pending'
  AND NOT EXISTS (
    SELECT 1 FROM dag_edges de
    WHERE de.to_node_id = dn.id
      AND de.from_node_id NOT IN (SELECT id FROM completed_nodes)
  );

-- Example 4: Get all events for a specific node
SELECT * FROM execution_events
WHERE node_id = 'node-002'
ORDER BY execution_order ASC;

-- Example 5: Get node execution timeline
SELECT 
    dn.node_type,
    dn.agent,
    dn.status,
    dn.order_index,
    COUNT(ee.id) as event_count,
    SUM(ee.duration_ms) as total_duration_ms
FROM dag_nodes dn
LEFT JOIN execution_events ee ON ee.node_id = dn.id
WHERE dn.run_id = 'abc-123'
GROUP BY dn.id, dn.node_type, dn.agent, dn.status, dn.order_index
ORDER BY dn.order_index;

-- Example 6: Get parallel execution groups
SELECT 
    de.from_node_id,
    COUNT(de.to_node_id) as outgoing_edges,
    de.dependency_type
FROM dag_edges de
JOIN dag_nodes dn ON dn.id = de.from_node_id
WHERE dn.run_id = 'abc-123'
GROUP BY de.from_node_id, de.dependency_type
HAVING de.dependency_type = 'parallel';
```

### 11.6 UI Integration

```typescript
// Frontend visualization of DAG
interface DAGNodeUI {
  id: string;
  type: 'planning' | 'agent' | 'control' | 'approval' | 'terminator';
  agent?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  order: number;
  dependencies: string[];  // Node IDs this depends on
  position: { x: number; y: number };  // For rendering
}

// Example: Fetch DAG from API
const response = await fetch(`/api/runs/${runId}/dag`);
const dag = await response.json();

// Render nodes and edges
dag.nodes.forEach(node => {
  renderNode(node);  // Draw node with status color
});

dag.edges.forEach(edge => {
  renderEdge(edge);  // Draw arrow between nodes
});

// Real-time updates via WebSocket
websocket.on('dag_node_status_changed', (event) => {
  const { node_id, new_status } = event.data;
  updateNodeStatus(node_id, new_status);  // Update UI
});
```

### 11.7 Advanced Features

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ADVANCED DAG FEATURES                             │
└─────────────────────────────────────────────────────────────────────┘

1. BRANCHING & PLAY-FROM-NODE
   ├─ Create new workflow run from any node
   ├─ Copy DAG structure from branch point onward
   ├─ Useful for exploring alternative approaches
   └─ Implementation: PlayFromNode service

2. CONDITIONAL EXECUTION
   ├─ CONTROL nodes evaluate conditions
   ├─ Route to different paths based on results
   ├─ Stored in dag_edges.condition field
   └─ Example: "if result.status == 'success'"

3. PARALLEL EXECUTION
   ├─ Automatic detection of independent nodes
   ├─ ThreadPoolExecutor for concurrent execution
   ├─ Resource limits per parallel group
   └─ Configurable max_parallel workers

4. APPROVAL GATES
   ├─ APPROVAL nodes pause workflow
   ├─ Store approval context in node.meta
   ├─ Resume on user decision
   └─ Track in approval_requests table

5. RETRY & ERROR HANDLING
   ├─ Retry configuration in node.meta
   ├─ Exponential backoff
   ├─ Max attempts limit
   └─ Error propagation to dependent nodes

6. RESOURCE MANAGEMENT
   ├─ Work directory isolation per node
   ├─ Memory/CPU limits
   ├─ Cleanup on completion
   └─ Managed by WorkDirectoryManager

7. DEPENDENCY ANALYSIS
   ├─ LLM-based dependency detection
   ├─ Automatic parallelization
   ├─ Conflict resolution
   └─ DependencyAnalyzer service
```

### 11.8 Key Files & Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DAG-RELATED COMPONENTS                            │
└─────────────────────────────────────────────────────────────────────┘

DATABASE MODELS:
└─ cmbagent/database/models.py
   ├─ DAGNode: Node model
   ├─ DAGEdge: Edge model
   └─ Relationships to WorkflowRun, ExecutionEvent, File, Message

DAG BUILDING:
└─ cmbagent/database/dag_builder.py
   ├─ DAGBuilder: Converts plan JSON to DAG
   ├─ build_from_plan(): Main entry point
   ├─ validate_dag(): Check for cycles
   └─ _create_node(), _create_edge(): Helper methods

DAG EXECUTION:
└─ cmbagent/database/dag_executor.py
   ├─ DAGExecutor: Executes DAG nodes
   ├─ execute(): Main execution loop
   ├─ _execute_parallel(): Parallel execution
   └─ _execute_sequential(): Sequential execution

TOPOLOGICAL SORTING:
└─ cmbagent/database/topological_sort.py
   ├─ TopologicalSorter: Compute execution order
   ├─ get_execution_order(): Level-by-level ordering
   └─ detect_parallel(): Find independent nodes

REPOSITORY:
└─ cmbagent/database/repository.py
   ├─ DAGRepository: Database access layer
   ├─ create_node(), get_node(), list_nodes()
   └─ create_edge(), get_node_dependencies()

BRANCHING:
└─ cmbagent/branching/play_from_node.py
   ├─ PlayFromNode: Resume workflow from node
   ├─ branch_from_node(): Create branch
   └─ get_resumable_nodes(): Find resume points

METADATA:
└─ cmbagent/database/dag_metadata.py
   ├─ DAGMetadata: Query node metadata
   ├─ get_node_execution_summary()
   └─ enrich_node_with_events()

BACKEND API:
└─ backend/main.py
   ├─ GET /api/nodes/{node_id}/events
   ├─ GET /api/nodes/{node_id}/execution-summary
   ├─ GET /api/nodes/{node_id}/files
   └─ POST /api/runs/{run_id}/play-from-node
```

---

## Summary

This document provides a complete architecture overview of the CMBAgent event system, including:

✅ **Database Schema**: 15+ tables with full column definitions and relationships  
✅ **Event Storage**: 3-tier strategy (in-memory queue, WebSocket streaming, database)  
✅ **WebSocket Protocol**: 30+ event types with real-time streaming  
✅ **REST APIs**: 25+ endpoints for task management and event queries  
✅ **Service Layer**: 4 core services with clear responsibilities  
✅ **Data Flow**: Complete end-to-end flow diagrams  
✅ **Event Classification**: Hierarchical event types and subtypes  
✅ **Reconnection Support**: Event queue for missed event recovery  
✅ **DAG Nodes**: Complete workflow orchestration system with parallel execution  
✅ **Run ID Resolution**: Production-grade normalization layer (task_id ↔ db_run_id)

### CRITICAL Production Requirements

**Run ID Management** (Must be followed by all developers):

1. **Frontend**: Always use `task_id` in API requests
2. **Backend APIs**: Always call `resolve_run_id(task_id)` before database queries
3. **Database**: All events, steps, nodes store `db_run_id` (UUID)
4. **WorkflowService**: Maintains active mapping between task_id and db_run_id
5. **Never**: Query database directly with task_id (will return 0 results)

```python
# ✅ CORRECT API Implementation
@app.get("/api/runs/{run_id}/events")
async def get_events(run_id: str):
    effective_run_id = resolve_run_id(run_id)  # task_id → UUID
    return db.query(ExecutionEvent).filter(
        ExecutionEvent.run_id == effective_run_id
    ).all()

# ❌ WRONG - Will fail in production
@app.get("/api/runs/{run_id}/events")
async def get_events(run_id: str):
    return db.query(ExecutionEvent).filter(
        ExecutionEvent.run_id == run_id  # Using task_id directly!
    ).all()
```  
✅ **Run ID Resolution**: Production-grade normalization layer (task_id ↔ db_run_id)

### CRITICAL Production Requirements

**Run ID Management** (Must be followed by all developers):

1. **Frontend**: Always use `task_id` in API requests
2. **Backend APIs**: Always call `resolve_run_id(task_id)` before database queries
3. **Database**: All events, steps, nodes store `db_run_id` (UUID)
4. **WorkflowService**: Maintains active mapping between task_id and db_run_id
5. **Never**: Query database directly with task_id (will return 0 results)

```python
# ✅ CORRECT API Implementation
@app.get("/api/runs/{run_id}/events")
async def get_events(run_id: str):
    effective_run_id = resolve_run_id(run_id)  # task_id → UUID
    return db.query(ExecutionEvent).filter(
        ExecutionEvent.run_id == effective_run_id
    ).all()

# ❌ WRONG - Will fail in production
@app.get("/api/runs/{run_id}/events")
async def get_events(run_id: str):
    return db.query(ExecutionEvent).filter(
        ExecutionEvent.run_id == run_id  # Using task_id directly!
    ).all()
```

The system is designed for:
- **Real-time observability**: Live WebSocket streaming to UI
- **Complete auditability**: All events persisted to database
- **Fault tolerance**: Reconnection support via event queue
- **Scalability**: Thread-safe, stateless WebSocket manager
- **Flexibility**: Rich event taxonomy with nested event support
- **Workflow orchestration**: DAG-based execution with parallel support

---

**Generated**: January 20, 2026  
**System**: CMBAgent Multi-Agent Orchestration Platform  
**Database**: PostgreSQL (production) / SQLite (development)  
**Backend**: Python + FastAPI + SQLAlchemy  
**Frontend**: TypeScript + Next.js + React
