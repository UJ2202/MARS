# WebSocket Robustness & Session Management Implementation Plan

## Overview

This plan addresses critical issues in the CMBAgent WebSocket and session management system:

1. **Concurrent Execution Failure**: Only one WebSocket connection works at a time due to global state pollution
2. **Session Persistence**: Sessions lost on server restart (in-memory storage)
3. **Logging Chaos**: 50+ print statements output directly to console
4. **Approval Reliability**: HITL approvals lost if user disconnects or server restarts
5. **Connection Management**: Duplicate connection managers causing confusion

**Total Stages:** 16 stages organized into 7 phases (including Stages 11B-11C)
**Current Stage:** 11B (Bug Fixes)
**Stages Complete:** 11 of 16

## How to Use This Plan

### For Each Stage:
1. Read `STAGE_XX.md` in the `stages/` directory
2. Review the stage objectives and verification criteria
3. Implement the stage following the guidelines
4. Run verification tests listed in the stage document
5. Mark stage as complete in `PROGRESS.md`
6. Move to next stage only after all verifications pass

### Resuming Implementation:
When resuming, provide:
- Current stage number (from `PROGRESS.md`)
- This README file location: `/srv/projects/mas/mars/denario/cmbagent/WEBSOCKET_ROBUSTNESS_PLAN/README.md`
- Any blockers encountered

## Stage Overview

### Phase 0: Foundation (Stages 1-2)
**Goal:** Establish database schema for robust session and approval persistence

| Stage | Name | Risk | Description |
|-------|------|------|-------------|
| 1 | Database Schema - Sessions | Low | Create tables for session state persistence |
| 2 | Database Schema - Approvals | Low | Create tables for approval requests and connections |

### Phase 1: Core Infrastructure (Stages 3-5)
**Goal:** Build core services for session and connection management

| Stage | Name | Risk | Description |
|-------|------|------|-------------|
| 3 | Session Manager Service | Medium | Implement database-backed session manager |
| 4 | Connection Manager Consolidation | Medium | Unify duplicate connection managers |
| 5 | Approval Manager Refactor | Medium | Implement persistent approval system |

### Phase 2: Execution Isolation (Stages 6-7)
**Goal:** Fix concurrent execution by isolating task processes

| Stage | Name | Risk | Description |
|-------|------|------|-------------|
| 6 | Process-Based Isolation | High | Execute tasks in isolated subprocesses |
| 7 | Output Channel Routing | Medium | Route output without global pollution |

### Phase 3: Logging System (Stages 8-9)
**Goal:** Replace print statements with structured logging

| Stage | Name | Risk | Description |
|-------|------|------|-------------|
| 8 | Logging Configuration | Low | Set up structlog with context binding |
| 9 | Print Statement Migration | Low | Replace all print() with logger calls |

### Phase 4: API & Frontend (Stages 10-11)
**Goal:** Expose session management to users

| Stage | Name | Risk | Description |
|-------|------|------|-------------|
| 10 | Session Management API | Low | REST endpoints for session CRUD |
| 11 | Frontend Session Integration | Medium | UI for session list, resume, management |

### Phase 4.5: Bug Fixes & Consolidation (Stages 11B-11C)
**Goal:** Fix critical bugs and consolidate approval managers into one system

| Stage | Name | Risk | Description |
|-------|------|------|-------------|
| 11B | Post-Implementation Bug Fixes | High | Fix broken isolated execution path, stale PROGRESS.md |
| 11C | Approval Manager Consolidation | High | Merge 3 approval systems into one, add DB persistence to WebSocketApprovalManager |

### Phase 5: Testing & Deployment (Stages 12-14)
**Goal:** Validate and deploy the changes

| Stage | Name | Risk | Description |
|-------|------|------|-------------|
| 12 | Unit & Integration Tests | Low | Test all new components |
| 13 | Load Testing | Medium | Validate concurrent execution |
| 14 | Migration & Deployment | High | Production deployment |

## Directory Structure

### New Files to Create
```
backend/
├── core/
│   └── logging.py                    # Stage 8
├── execution/
│   └── isolated_executor.py          # Stage 6
├── services/
│   ├── session_manager.py            # Stage 3 (new)
│   ├── approval_manager.py           # Stage 5 (new)
│   └── connection_manager.py         # Stage 4 (modify)
└── routers/
    └── sessions.py                   # Stage 10

cmbagent/
└── database/
    └── migrations/
        ├── xxx_session_states.py     # Stage 1
        └── xxx_approval_requests.py  # Stage 2

cmbagent-ui/
└── components/
    └── SessionManager/               # Stage 11
        ├── SessionList.tsx
        └── SessionResume.tsx

tests/
├── test_session_manager.py           # Stage 12
├── test_isolated_executor.py         # Stage 12
└── test_concurrent_execution.py      # Stage 13
```

### Files to Modify
```
backend/
├── websocket/handlers.py             # Stages 4, 6, 7
├── execution/task_executor.py        # Stages 6, 7, 9
├── services/__init__.py              # Stage 4
└── routers/__init__.py               # Stage 10

cmbagent/
├── workflows/copilot.py              # Stage 3
├── workflows/swarm_copilot.py        # Stage 3
└── database/models.py                # Stages 1, 2

cmbagent-ui/
├── contexts/WebSocketContext.tsx     # Stage 11
└── components/CopilotView.tsx        # Stage 11
```

## Stage Dependencies

```
Phase 0 (Foundation)
┌─────────┐     ┌─────────┐
│ Stage 1 │────►│ Stage 2 │
└────┬────┘     └────┬────┘
     │               │
     └───────┬───────┘
             │
             ▼
Phase 1 (Core Infrastructure)
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Stage 3 │────►│ Stage 4 │────►│ Stage 5 │
└────┬────┘     └────┬────┘     └────┬────┘
     │               │               │
     └───────────────┼───────────────┘
                     │
                     ▼
Phase 2 (Execution Isolation)          Phase 3 (Logging)
┌─────────┐     ┌─────────┐            ┌─────────┐     ┌─────────┐
│ Stage 6 │────►│ Stage 7 │            │ Stage 8 │────►│ Stage 9 │
└────┬────┘     └────┬────┘            └────┬────┘     └────┬────┘
     │               │                      │               │
     └───────┬───────┘                      └───────┬───────┘
             │                                      │
             └──────────────┬───────────────────────┘
                            │
                            ▼
Phase 4 (API & Frontend)
┌──────────┐     ┌──────────┐
│ Stage 10 │────►│ Stage 11 │
└────┬─────┘     └────┬─────┘
     │                │
     └────────┬───────┘
              │
              ▼
Phase 4.5 (Bug Fixes & Consolidation)
┌───────────┐     ┌───────────┐
│ Stage 11B │────►│ Stage 11C │
└────┬──────┘     └────┬──────┘
     │                 │
     └────────┬────────┘
              │
              ▼
Phase 5 (Testing & Deployment)
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Stage 12 │────►│ Stage 13 │────►│ Stage 14 │
└──────────┘     └──────────┘     └──────────┘
```

## Critical Success Factors

1. **Process Isolation Works**: Two concurrent tasks execute without output mixing
2. **Sessions Persist**: Session survives server restart and can be resumed
3. **Approvals Reliable**: HITL approval works across reconnections
4. **No Regressions**: All existing modes continue to work
5. **Performance Acceptable**: <5% latency increase, handles 50+ concurrent users

## Quick Reference Commands

```bash
# Run backend
cd /srv/projects/mas/mars/denario/cmbagent/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run frontend
cd /srv/projects/mas/mars/denario/cmbagent/cmbagent-ui
npm run dev

# Run migrations
cd /srv/projects/mas/mars/denario/cmbagent
alembic upgrade head

# Run tests
pytest tests/ -v

# Check for print statements
grep -rn "print(" backend/ cmbagent/ --include="*.py" | wc -l
```

## Risk Management

### High-Risk Stages

| Stage | Risk | Mitigation |
|-------|------|------------|
| 6 | Process isolation complexity | Start with simple subprocess, benchmark |
| 7 | Output routing breakage | Maintain fallback to current behavior |
| 14 | Production deployment | Staged rollout, immediate rollback ready |

### Rollback Strategy
Each stage includes rollback procedures. For emergency full rollback:
```bash
git checkout HEAD~N  # Revert N commits
alembic downgrade -N  # Revert N migrations
systemctl restart cmbagent-backend
```

## Key Metrics to Track

| Metric | Before | Target | How to Measure |
|--------|--------|--------|----------------|
| Concurrent connections | 1 | 50+ | Load test |
| Session persistence | 0% | 100% | Restart test |
| HITL approval success | ~70% | 99% | E2E test |
| Print statements | 50+ | 0 | grep count |
| Memory per connection | Unknown | <50MB | Profiling |

---

**Last Updated:** 2026-02-11
**Plan Version:** 1.0
**Status:** Ready for implementation
**Author:** Claude Code
