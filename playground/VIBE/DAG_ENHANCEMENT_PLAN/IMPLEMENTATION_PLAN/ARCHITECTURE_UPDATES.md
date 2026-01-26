# Architecture Updates Based on Review

**Date:** 2026-01-14
**Updated By:** Architecture Review
**Status:** Approved

## Summary of Changes

The architecture has been updated to incorporate 4 critical requirements for scientific discovery workflows:

### 1. Dual Persistence Strategy (Pickle + Database)

**Decision:** Keep both pickle files AND database in parallel

**Rationale:**
- Pickle files may be useful for future analysis
- Provides backward compatibility and migration safety
- Quick context snapshots for debugging
- Compatibility with external tools

**Implementation:**
- Database is PRIMARY source of truth
- Pickle files written as SECONDARY backup
- Dual-write on all checkpoints
- Read from database first, fall back to pickle if needed

**Impact:** Stages 2, 3, 4, 6, 9

---

### 2. Default Allow-All Policy

**Decision:** Default policy enforcement to ALLOW ALL

**Rationale:**
- Scientific discovery requires flexibility
- Restrictive policies can block legitimate research
- Framework ready but not enforcing by default
- Users opt-in to stricter policies when needed

**Implementation:**
```rego
package cmbagent.default
default allow = true  # Permissive by default
```

**Impact:** Stage 15 (Policy integration)

---

### 3. Long-Running Workflow Support (Hours to Days)

**Challenge:** Scientific workflows can run for hours, days, or weeks

**Solutions Implemented:**

#### Frequent Checkpointing
- After each major step
- Every 10 minutes (configurable)
- Before risky operations
- On manual pause
- On errors

#### Graceful Interruption
- SIGTERM/SIGINT handlers
- Save state before shutdown
- Notify clients via WebSocket
- Clean resource cleanup

#### Resume from Any Point
- `cmbagent resume <run_id>` command
- Load from database checkpoint
- Restore full context
- Continue from next pending node

#### WebSocket Resilience
- Auto-reconnection with exponential backoff
- Stateless backend (all state in DB)
- Fetch latest state on reconnect
- Unlimited reconnection attempts

#### Progress Persistence
- Database-first progress tracking
- Not stored in memory only
- Real-time updates broadcast
- Time-series metrics

#### Heartbeat Monitoring
- Detect stalled workflows
- Background daemon monitoring
- Automatic recovery triggers
- Email/webhook notifications

#### Resource Management
- Memory cleanup after each step
- File handle auditing
- Garbage collection
- Resource usage logging

#### Multi-Day Resume
- Pause today, resume tomorrow
- No data loss
- Full context preservation
- Example: 5-day scientific computation

**Impact:** Stages 2, 3, 4, 5, 6, 13

---

### 4. Multi-Session Isolation

**Challenge:** Multiple researchers running concurrent workflows

**Solutions Implemented:**

#### File System Isolation
```
work_dir/sessions/
├── session_001/projects/project_xyz/runs/run_abc/
├── session_002/projects/project_abc/runs/run_def/
└── session_003/projects/project_123/runs/run_ghi/
```
- Strict directory boundaries
- Prevent directory traversal
- Session-scoped paths

#### Database Isolation
- `session_id` column on all tables
- Row-level security
- Session-scoped queries
- Automatic query filtering

#### Resource Boundaries
- Per-session disk quotas (10 GB default)
- Max concurrent runs (3 default)
- Cost budgets ($100 default)
- Memory limits (4 GB default)

#### Concurrent Execution
- Isolated worker processes per session
- No cross-session interference
- Thread/process safety
- Independent execution

#### Independent Lifecycle
- Session A: EXECUTING
- Session B: PAUSED
- Session C: COMPLETED
- All independent!

#### Session Management API
- Create/list/archive/delete sessions
- Session metadata tracking
- Resource usage reporting
- Session-level analytics

**Impact:** Stages 2, 4, 13

---

## Architectural Diagrams Updated

### Persistence Layer (Updated)
```
┌─────────────────────────────────────────────────┐
│            Persistence Layer                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ Database │  │  Pickle  │  │ Vector DB│     │
│  │(Primary) │  │(Secondary)│  │  (RAG)   │     │
│  └──────────┘  └──────────┘  └──────────┘     │
│  ┌────────────────────────────────────────┐   │
│  │      File Storage (work_dir)            │   │
│  │  - Session-isolated directories         │   │
│  │  - Generated code, data, plots          │   │
│  └────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### Work Directory Structure (Updated)
```
work_dir/
└── sessions/
    ├── session_001/
    │   └── projects/
    │       └── project_xyz/
    │           └── runs/
    │               ├── run_abc123/
    │               │   ├── planning/
    │               │   ├── control/
    │               │   ├── data/
    │               │   ├── codebase/
    │               │   └── context/
    │               │       ├── context_step_0.pkl
    │               │       ├── context_step_1.pkl
    │               │       └── ...
    │               └── run_def456/
    ├── session_002/
    └── session_003/
```

## Database Schema Updates

### New Tables Added
```sql
-- Session management
sessions (
    id UUID PRIMARY KEY,
    user_id UUID,
    name VARCHAR(255),
    created_at TIMESTAMP,
    last_active_at TIMESTAMP,
    status VARCHAR(50),
    metadata JSONB,
    resource_limits JSONB
);

-- Time-series metrics for long-running workflows
workflow_metrics (
    id SERIAL PRIMARY KEY,
    run_id UUID NOT NULL,
    step_id UUID,
    timestamp TIMESTAMP NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    metadata JSONB
);

-- Heartbeat tracking
ALTER TABLE workflow_runs ADD COLUMN last_heartbeat_at TIMESTAMP;
ALTER TABLE workflow_runs ADD COLUMN checkpoint_frequency_minutes INTEGER DEFAULT 10;
```

### Session ID Added to All Tables
```sql
ALTER TABLE workflow_runs ADD COLUMN session_id UUID NOT NULL;
ALTER TABLE workflow_steps ADD COLUMN session_id UUID NOT NULL;
ALTER TABLE dag_nodes ADD COLUMN session_id UUID NOT NULL;
-- ... and all other tables
```

## New CLI Commands

```bash
# Resume paused workflow
cmbagent resume <run_id>

# Create new session
cmbagent session create --name "CMB Analysis"

# List sessions
cmbagent session list

# Archive session
cmbagent session archive <session_id>

# Delete session
cmbagent session delete <session_id>

# Pause running workflow
cmbagent pause <run_id>

# View workflow status
cmbagent status <run_id>
```

## New API Endpoints

```python
# Session management
POST   /api/sessions
GET    /api/sessions
GET    /api/sessions/{session_id}
POST   /api/sessions/{session_id}/archive
DELETE /api/sessions/{session_id}

# Workflow lifecycle
POST   /api/workflows/{run_id}/pause
POST   /api/workflows/{run_id}/resume
GET    /api/workflows/{run_id}/status
GET    /api/workflows/{run_id}/checkpoints

# Metrics
GET    /api/workflows/{run_id}/metrics
GET    /api/sessions/{session_id}/metrics
```

## Testing Requirements Updated

### Long-Running Workflow Tests
- [ ] Multi-day workflow (pause overnight, resume next day)
- [ ] Graceful shutdown during execution
- [ ] WebSocket reconnection after disconnect
- [ ] Heartbeat monitoring and stalled detection
- [ ] Resource cleanup verification
- [ ] Time-series metrics collection

### Session Isolation Tests
- [ ] Concurrent workflows in different sessions
- [ ] File system isolation (no cross-session access)
- [ ] Database isolation (session-scoped queries)
- [ ] Resource quota enforcement
- [ ] Independent lifecycle (pause/resume per session)
- [ ] Session cleanup (archive/delete)

## Implementation Priority

### Immediate (Stages 1-4)
1. AG2 upgrade
2. Database with session_id columns
3. State machine with PAUSED state
4. DAG system with checkpoint support

### High Priority (Stages 5-9)
5. WebSocket with reconnection
6. HITL with pause/resume
7. Dual-checkpoint system (DB + pickle)
8. Parallel execution
9. Branching with session context

### Medium Priority (Stages 10-13)
10. MCP server
11. MCP client
12. Agent registry
13. Cost tracking with session aggregation

### Low Priority (Stage 14-15)
14. Observability (OpenTelemetry)
15. Policy enforcement (default: allow all)

## Backward Compatibility Notes

- Existing work_dir structure supported (legacy mode)
- Can migrate old workflows to new session structure
- Pickle files remain readable
- CLI interface unchanged (new commands added)
- WebSocket protocol backward compatible

## Migration Path

1. Install new version
2. Run database migration (adds session_id columns)
3. Create default session for existing workflows
4. Gradually migrate workflows to session-based structure
5. Both old and new systems work in parallel
6. Eventually deprecate non-session workflows

---

**Approved For Implementation:** 2026-01-14
**Ready for Stage Document Creation:** Yes
