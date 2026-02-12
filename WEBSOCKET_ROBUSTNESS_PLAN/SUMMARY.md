# Implementation Plan Summary

## Overview

Transform CMBAgent's WebSocket and session system from single-connection to robust multi-user with persistent sessions.

**Current State:** Single connection works, multiple fail, sessions lost on restart
**Target State:** 50+ concurrent connections, sessions persist across restarts

## Plan Structure

```
WEBSOCKET_ROBUSTNESS_PLAN/
├── README.md              # Master plan (start here)
├── PROGRESS.md            # Progress tracking
├── ARCHITECTURE.md        # Technical architecture
├── SUMMARY.md             # This file (quick reference)
│
├── stages/
│   ├── STAGE_01.md        # DB Schema - Sessions
│   ├── STAGE_02.md        # DB Schema - Approvals
│   ├── STAGE_03.md        # Session Manager Service
│   ├── STAGE_04.md        # Connection Manager
│   ├── STAGE_05.md        # Approval Manager
│   ├── STAGE_06.md        # Process Isolation
│   ├── STAGE_07.md        # Output Routing
│   ├── STAGE_08.md        # Logging Config
│   ├── STAGE_09.md        # Print Migration
│   ├── STAGE_10.md        # Session API
│   ├── STAGE_11.md        # Frontend Integration
│   ├── STAGE_12.md        # Unit Tests
│   ├── STAGE_13.md        # Load Tests
│   └── STAGE_14.md        # Deployment
│
├── references/
│   ├── data_models.md     # Database schemas
│   ├── api_reference.md   # API endpoints
│   └── event_types.md     # WebSocket events
│
└── tests/
    ├── test_scenarios.md  # Test cases
    └── validation_guide.md
```

## Stage Summary

| Stage | Name | Phase | Risk | Key Deliverable |
|-------|------|-------|------|-----------------|
| 1 | DB Schema - Sessions | 0 | Low | `session_states` table |
| 2 | DB Schema - Approvals | 0 | Low | `approval_requests` table |
| 3 | Session Manager | 1 | Med | `SessionManager` class |
| 4 | Connection Manager | 1 | Med | Consolidated manager |
| 5 | Approval Manager | 1 | Med | `RobustApprovalManager` |
| 6 | Process Isolation | 2 | **High** | `IsolatedTaskExecutor` |
| 7 | Output Routing | 2 | Med | Queue-based output |
| 8 | Logging Config | 3 | Low | structlog setup |
| 9 | Print Migration | 3 | Low | 0 print statements |
| 10 | Session API | 4 | Low | REST endpoints |
| 11 | Frontend Integration | 4 | Med | Session UI |
| 12 | Unit Tests | 5 | Low | Test coverage |
| 13 | Load Tests | 5 | Med | 50+ concurrent |
| 14 | Deployment | 5 | **High** | Production release |

## Files to Create

### Backend (8 files)
```
backend/
├── core/
│   └── logging.py                    # Structured logging
├── execution/
│   └── isolated_executor.py          # Process isolation
├── services/
│   ├── session_manager.py            # Session CRUD
│   └── approval_manager.py           # Approval handling
└── routers/
    └── sessions.py                   # REST API
```

### Database Migrations (2 files)
```
cmbagent/database/migrations/versions/
├── 001_session_states.py
└── 002_approval_requests.py
```

### Frontend (3 files)
```
cmbagent-ui/components/SessionManager/
├── SessionList.tsx
├── SessionResume.tsx
└── index.ts
```

### Tests (4 files)
```
tests/
├── test_session_manager.py
├── test_approval_manager.py
├── test_isolated_executor.py
└── test_concurrent_execution.py
```

## Files to Modify

| File | Stages | Changes |
|------|--------|---------|
| `backend/websocket/handlers.py` | 4,6,7 | Use isolated executor |
| `backend/execution/task_executor.py` | 6,7,9 | Remove global overrides |
| `backend/services/connection_manager.py` | 4 | Add async lock |
| `backend/services/__init__.py` | 4 | Export unified manager |
| `cmbagent/workflows/copilot.py` | 3 | Remove in-memory cache |
| `cmbagent/workflows/swarm_copilot.py` | 3 | Remove in-memory cache |
| `cmbagent/database/models.py` | 1,2 | Add new models |
| `cmbagent-ui/contexts/WebSocketContext.tsx` | 11 | Session support |

## Key Code Patterns

### Process Isolation (Stage 6)
```python
# Instead of modifying globals in main process:
def execute_task(task_id, config):
    process = Process(target=run_in_subprocess, args=(task_id, config, output_queue))
    process.start()
    # Output comes via queue, no global pollution
```

### Session Persistence (Stage 3)
```python
# Instead of in-memory dict:
_active_sessions = {}  # DELETE THIS

# Use database:
session_manager.save_session_state(session_id, conversation, context)
state = session_manager.load_session_state(session_id)
```

### Approval with Timeout (Stage 5)
```python
# Instead of waiting forever:
await event.wait()  # Can hang forever

# Use timeout and DB:
result = await approval_manager.wait_for_approval(approval_id, timeout=300)
```

## Implementation Order

```
Week 1: Foundation + Critical Fix
├── Day 1: Stage 1 (DB Sessions)
├── Day 2: Stage 2 (DB Approvals)
├── Day 3: Stage 6 (Process Isolation) ← Fixes main issue
├── Day 4: Stage 7 (Output Routing)
└── Day 5: Stage 4 (Connection Manager)

Week 2: Services + Logging
├── Day 1-2: Stage 3 (Session Manager)
├── Day 3: Stage 5 (Approval Manager)
├── Day 4: Stage 8 (Logging Config)
└── Day 5: Stage 9 (Print Migration)

Week 3: API + UI
├── Day 1-2: Stage 10 (Session API)
├── Day 3-4: Stage 11 (Frontend)
└── Day 5: Stage 12 (Unit Tests)

Week 4: Testing + Deploy
├── Day 1-2: Stage 13 (Load Tests)
├── Day 3: Stage 14 (Staging)
└── Day 4-5: Production + Monitoring
```

## Quick Commands

```bash
# Navigate to project
cd /srv/projects/mas/mars/denario/cmbagent

# Run backend
cd backend && uvicorn main:app --reload --port 8000

# Run frontend
cd cmbagent-ui && npm run dev

# Run migrations
alembic upgrade head

# Run tests
pytest tests/ -v

# Count print statements (target: 0)
grep -rn "print(" backend/ cmbagent/ --include="*.py" | grep -v test | wc -l

# Check active connections (during testing)
curl http://localhost:8000/api/debug/connections
```

## Success Metrics

| Metric | Current | Target | Test Method |
|--------|---------|--------|-------------|
| Concurrent connections | 1 | 50+ | Load test |
| Session persistence | 0% | 100% | Restart test |
| Approval reliability | ~70% | 99% | E2E test |
| Print statements | 50+ | 0 | grep count |

## Risk Mitigation

| Risk | Stage | Mitigation |
|------|-------|------------|
| Process isolation fails | 6 | Fallback to thread with warnings |
| Migration breaks prod | 14 | Staged rollout, instant rollback |
| Performance regression | 13 | Benchmark before/after |

## Getting Started

1. **Read full plan:** `README.md`
2. **Start Stage 1:** `stages/STAGE_01.md`
3. **Update progress:** `PROGRESS.md` after each stage
4. **Check architecture:** `ARCHITECTURE.md` for design decisions

---

**Created:** 2026-02-11
**Total Stages:** 14
**Status:** Ready for Implementation
