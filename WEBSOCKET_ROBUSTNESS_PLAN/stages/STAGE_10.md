# Stage 10: Session Management API (All Modes)

**Phase:** 4 - API & Frontend
**Dependencies:** Stage 3 (SessionManager)
**Risk Level:** Low

## Objectives

1. Create REST API endpoints for session management across ALL workflow modes
2. Auto-create sessions for every task execution (not just copilot)
3. Enable session listing with mode filtering, details, resume, suspend, delete
4. Add workflow modes listing endpoint
5. Integrate session lifecycle with WebSocket handler and task executor

## Supported Modes

All workflow modes now have session management:

| Mode | ID | Resume Support | HITL Support |
|------|----|---------------|--------------|
| Copilot | `copilot` | Yes | Yes |
| Planning & Control | `planning-control` | Yes | Yes |
| One Shot | `one-shot` | No | No |
| HITL Interactive | `hitl-interactive` | Yes | Yes |
| Idea Generation | `idea-generation` | Yes | Yes |
| OCR | `ocr` | No | No |
| arXiv Filter | `arxiv` | No | No |
| Enhance Input | `enhance-input` | No | No |

## Implementation (Completed)

### Task 1: Sessions Router

**File:** `backend/routers/sessions.py`

Endpoints:

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/sessions | Create new session |
| GET | /api/sessions | List sessions (with mode and status filters) |
| GET | /api/sessions/{id} | Get session details |
| GET | /api/sessions/{id}/history | Get conversation history |
| POST | /api/sessions/{id}/suspend | Suspend session |
| POST | /api/sessions/{id}/resume | Resume session |
| DELETE | /api/sessions/{id} | Delete session |
| GET | /api/sessions/modes/list | List all available workflow modes |

### Task 2: Auto-Create Sessions in WebSocket Handler

**File:** `backend/websocket/handlers.py`

- Sessions are auto-created for every task execution via `_session_manager.create_session()`
- `session_id` is injected into config so the task executor can use it
- Initial status event includes `session_id` so frontend can track it
- Existing `copilotSessionId` or `session_id` from config is reused (for continuation)

### Task 3: Session State Tracking in Task Executor

**File:** `backend/execution/task_executor.py`

- `_get_session_manager()` lazy-loads the SessionManager
- `session_id` extracted from config (set by websocket handler)
- `conversation_buffer` tracks agent messages during execution
- Session state saved on phase changes via `session_manager.save_session_state()`
- Session completed on success, suspended on failure
- `session_id` included in result events
- Works for ALL modes: legacy (copilot, hitl-interactive) and isolated execution

### Task 4: Legacy Cleanup

**Files:** `cmbagent/workflows/copilot.py`, `cmbagent/workflows/swarm_copilot.py`, `cmbagent/workflows/__init__.py`

- Updated misleading deprecation comments on `_active_copilot_sessions` and `_active_sessions`
- Clarified that these are volatile in-memory orchestrator references (needed for live continuation)
- Durable session state is now managed by SessionManager
- Removed `get_active_copilot_sessions()` and `get_active_sessions()` from public exports
- External code should use `SessionManager.list_sessions()` instead

## API Reference

### List Sessions with Filters
```bash
# All sessions
curl http://localhost:8000/api/sessions

# Filter by mode
curl http://localhost:8000/api/sessions?mode=planning-control

# Filter by status
curl http://localhost:8000/api/sessions?status=suspended

# Combined filters
curl http://localhost:8000/api/sessions?mode=copilot&status=active&limit=20
```

### List Workflow Modes
```bash
curl http://localhost:8000/api/sessions/modes/list
```

Response:
```json
{
  "modes": [
    {"id": "copilot", "label": "Copilot", "description": "...", "supports_resume": true, "supports_hitl": true},
    {"id": "planning-control", "label": "Planning & Control", ...},
    ...
  ],
  "total": 8
}
```

## Verification Criteria

### Must Pass
- [x] All 8 endpoints working (7 CRUD + 1 modes listing)
- [x] Sessions auto-created for ALL modes via WebSocket handler
- [x] Session state saved on phase changes in task executor
- [x] Sessions completed on success, suspended on failure
- [x] Mode filtering works in list endpoint
- [x] Legacy exports cleaned up

## Success Criteria

Stage 10 is complete when:
1. [x] All endpoints working for all modes
2. [x] Auto session creation in websocket handler
3. [x] Session state tracking in task executor (both legacy and isolated paths)
4. [x] Modes listing endpoint
5. [x] Legacy cleanup done

## Next Stage

**Stage 11: Frontend Session Integration**

---

**Stage Status:** Complete
**Last Updated:** 2026-02-12
