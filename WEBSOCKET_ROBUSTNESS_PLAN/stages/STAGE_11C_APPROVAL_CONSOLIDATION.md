# Stage 11C: Approval Manager Consolidation

**Phase:** 4.5 - Bug Fixes & Consolidation
**Dependencies:** Stages 5 (RobustApprovalManager), 11B (Bug Fixes)
**Risk Level:** High (touches all HITL, copilot, and planning-control execution paths)

## Overview

There are currently **three** approval manager systems:

| System | Location | Storage | Thread Model | Used By |
|--------|----------|---------|--------------|---------|
| `WebSocketApprovalManager` | `cmbagent/database/websocket_approval_manager.py` | In-memory dict | `threading.Event` | hitl-interactive, copilot (32 call sites) |
| `RobustApprovalManager` | `backend/services/approval_manager.py` | Database + local cache | `asyncio.Event` | WebSocket handler 2nd fallback (1 call site) |
| `ApprovalManager` | `cmbagent/database/approval_manager.py` | Database + polling | `time.sleep` blocking | planning-control via `approval_config`, CMBAgent CLI, handler 3rd fallback |

### Problems

1. **3-layer resolution guessing game** -- handler tries in-memory, then Robust, then legacy, each with different semantics
2. **No persistence** -- the system all phases use (`WebSocketApprovalManager`) is in-memory only. Approvals lost on disconnect/restart
3. **Different return types** -- `SimpleApprovalRequest` vs `Dict` vs `ApprovalRequest` ORM object
4. **Split injection paths** -- hitl/copilot use `approval_manager=` parameter, planning-control uses `approval_config=` parameter that creates a different manager internally
5. **Copilot continuation gap** -- creates `WebSocketApprovalManager` but never passes it to `continue_copilot_sync()`
6. **Dead code** -- `RobustApprovalManager` has 0 call sites in actual workflow code, only exists as handler fallback
7. **CMBAgent creates but never uses** -- `cmbagent.py:284` creates `ApprovalManager`, never calls a method on it

### Goal

**One approval manager for all WebSocket workflows: `WebSocketApprovalManager` with DB persistence.**

Then **delete** `RobustApprovalManager` entirely, and **delete** `ApprovalManager` entirely (it is unused).

---

## Current Flow Per Workflow Mode

| Mode | Current Approval System | Problem |
|------|------------------------|---------|
| **one-shot** | None | No change needed |
| **planning-control** | `ApprovalManager` via `approval_config=` path | Uses wrong manager; different injection path |
| **hitl-interactive** (3 variants) | `WebSocketApprovalManager` via `approval_manager=` | Needs DB persistence (Task 1) |
| **copilot** (new session) | `WebSocketApprovalManager` via `approval_manager=` | Needs DB persistence (Task 1) |
| **copilot** (continuation) | `WebSocketApprovalManager` created but **not passed** | Bug: approval_manager disconnected (Task 5) |
| **idea-generation** | None | No change needed |
| **ocr** | None | No change needed |
| **arxiv** | None | No change needed |
| **enhance-input** | None | No change needed |

## Target Flow Per Workflow Mode

| Mode | After Stage 11C |
|------|-----------------|
| **planning-control** | `WebSocketApprovalManager` via `approval_manager=` (same as hitl) |
| **hitl-interactive** | `WebSocketApprovalManager` with DB persistence |
| **copilot** (new) | `WebSocketApprovalManager` with DB persistence |
| **copilot** (continuation) | `WebSocketApprovalManager` passed through to `continue_copilot_sync()` |
| **All other modes** | No change (no approvals needed) |

---

## Architecture After Consolidation

```
BEFORE (3 systems, 2 injection paths):

planning-control:
  task_executor → approval_config= → planning_control.py
    → _get_approval_manager(config) → ApprovalManager(db_session, session_id)  ← LEGACY DB
      → injected into shared_state → phases call create/wait

hitl / copilot:
  task_executor → approval_manager= → workflow function
    → WebSocketApprovalManager(ws_send_event, task_id)  ← IN-MEMORY ONLY
      → injected into shared_state → phases call create/wait

handler resolution:
  try WebSocketApprovalManager.has_pending()     ← layer 1
  try RobustApprovalManager.resolve_approval()   ← layer 2
  try ApprovalManager.resolve_approval()         ← layer 3


AFTER (1 system, 1 injection path):

ALL modes with approvals:
  task_executor → approval_manager= → workflow function
    → WebSocketApprovalManager(ws_send_event, task_id, db_factory=...)  ← IN-MEMORY + DB
      → injected into shared_state → phases call create/wait

handler resolution:
  WebSocketApprovalManager.resolve_from_db()     ← single path
```

---

## Implementation Tasks

### Task 1: Add DB Persistence to WebSocketApprovalManager

**File:** `cmbagent/database/websocket_approval_manager.py`

Add optional database persistence. DB writes are best-effort -- if they fail, the in-memory path still works (graceful degradation).

**1a. Add `db_factory` parameter and imports:**

```python
# Add to imports at top of file:
from datetime import datetime, timezone, timedelta

# Update __init__:
def __init__(self, ws_send_event: Callable, run_id: str, db_factory: Callable = None):
    self.ws_send_event = ws_send_event
    self.run_id = run_id
    self._db_factory = db_factory
```

**1b. Persist on `create_approval_request()` -- add after `self._pending[request.id] = request` (line 132):**

```python
# Best-effort DB persist
if self._db_factory:
    try:
        from cmbagent.database.models import ApprovalRequest as ApprovalRequestModel
        db = self._db_factory()
        try:
            db_approval = ApprovalRequestModel(
                id=request.id,
                run_id=request.run_id or self.run_id,
                approval_type=request.checkpoint_type,
                context={
                    "checkpoint_type": request.checkpoint_type,
                    "message": request.message,
                    "options": request.options,
                    "context": request.context_snapshot,
                },
                status="pending",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            db.add(db_approval)
            db.commit()
            logger.debug("Persisted approval %s to database", request.id)
        except Exception as e:
            db.rollback()
            logger.warning("Failed to persist approval to DB (non-fatal): %s", e)
        finally:
            db.close()
    except ImportError:
        pass
```

**1c. Update DB on `resolve()` -- add after `cls._pending.pop(approval_id, None)` (line 371):**

```python
# Best-effort DB update
try:
    from cmbagent.database.base import get_db_session
    from cmbagent.database.models import ApprovalRequest as ApprovalRequestModel
    db = get_db_session()
    try:
        db.query(ApprovalRequestModel).filter(
            ApprovalRequestModel.id == approval_id,
            ApprovalRequestModel.status == "pending"
        ).update({
            "status": "resolved",
            "resolution": resolution,
            "resolved_at": datetime.now(timezone.utc),
            "result": {
                "resolution": resolution,
                "feedback": user_feedback,
                "modifications": modifications or {},
            }
        })
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Failed to update approval in DB (non-fatal): %s", e)
    finally:
        db.close()
except ImportError:
    pass
```

**1d. Add `resolve_from_db()` classmethod (after `get_all_pending`):**

```python
@classmethod
def resolve_from_db(cls, approval_id: str, resolution: str,
                    user_feedback: str = None, modifications: dict = None) -> bool:
    """
    Single entry point for resolution. Tries in-memory first, falls back to DB.
    Used by WebSocket handler -- replaces the 3-layer fallback chain.
    """
    # Fast path: in-memory (normal case, same server instance)
    if cls.has_pending(approval_id):
        return cls.resolve(approval_id, resolution, user_feedback, modifications)

    # Slow path: DB only (server restarted, different instance)
    try:
        from cmbagent.database.base import get_db_session
        from cmbagent.database.models import ApprovalRequest as ApprovalRequestModel
        db = get_db_session()
        try:
            rows = db.query(ApprovalRequestModel).filter(
                ApprovalRequestModel.id == approval_id,
                ApprovalRequestModel.status == "pending"
            ).update({
                "status": "resolved",
                "resolution": resolution,
                "resolved_at": datetime.now(timezone.utc),
                "result": {
                    "resolution": resolution,
                    "feedback": user_feedback,
                    "modifications": modifications or {},
                }
            })
            db.commit()
            if rows > 0:
                logger.info("Resolved approval %s via DB fallback", approval_id)
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error("DB fallback resolution failed for %s: %s", approval_id, e)
            return False
        finally:
            db.close()
    except ImportError:
        return False
```

**1e. Update `__getstate__` to exclude `_db_factory`:**

```python
def __getstate__(self):
    state = self.__dict__.copy()
    state['ws_send_event'] = None
    state['_db_factory'] = None  # Also non-picklable
    return state
```

---

### Task 2: Migrate planning-control to WebSocketApprovalManager

**File:** `backend/execution/task_executor.py` (lines 559-598)

The planning-control block currently creates an `approval_config` object and passes it to the workflow function, which internally creates a legacy `ApprovalManager`. Change it to create a `WebSocketApprovalManager` and pass it as `approval_manager=` instead.

**Before (current):**
```python
elif mode == "planning-control":
    approval_config = None
    approval_mode = config.get("approvalMode", "none")

    if approval_mode != "none":
        from cmbagent.database.approval_types import ApprovalMode, ApprovalConfig
        if approval_mode == "after_planning":
            approval_config = ApprovalConfig(mode=ApprovalMode.AFTER_PLANNING)
        # ... more modes ...

    results = cmbagent.planning_and_control_context_carryover(
        ...,
        approval_config=approval_config  # passes config, not manager
    )
```

**After (migrated):**
```python
elif mode == "planning-control":
    approval_mode = config.get("approvalMode", "none")
    pc_approval_manager = None

    if approval_mode != "none":
        from cmbagent.database.websocket_approval_manager import WebSocketApprovalManager
        pc_approval_manager = WebSocketApprovalManager(
            ws_send_event, task_id, db_factory=_approval_db_factory
        )
        logger.info("Planning-control HITL enabled with mode: %s", approval_mode)

    results = cmbagent.planning_and_control_context_carryover(
        ...,
        approval_manager=pc_approval_manager,  # pass manager directly
        hitl_after_planning=(approval_mode in ("after_planning", "both")),
        # Remove: approval_config=approval_config
    )
```

**File:** `cmbagent/workflows/planning_control.py`

Add `approval_manager=None` parameter to `planning_and_control_context_carryover()`:

```python
def planning_and_control_context_carryover(
    ...,
    approval_config=None,   # DEPRECATED, kept for backwards compat
    approval_manager=None,  # NEW: direct manager injection
    callbacks=None,
    hitl_after_planning=False,
):
```

Update executor creation (line 166-173):

```python
# Determine approval manager: prefer direct injection over config-based
_effective_approval_manager = approval_manager
if not _effective_approval_manager and approval_config:
    _effective_approval_manager = _get_approval_manager(approval_config)

executor = WorkflowExecutor(
    workflow=workflow,
    task=task,
    work_dir=work_dir,
    api_keys=api_keys,
    callbacks=callbacks,
    approval_manager=_effective_approval_manager,
)
```

This is backwards compatible -- if someone passes `approval_config=` (CLI usage via CMBAgent), it still works. If someone passes `approval_manager=` (WebSocket backend), that takes priority.

---

### Task 3: Fix Copilot Continuation Missing approval_manager

**File:** `backend/execution/task_executor.py` (lines 692-704)

The continuation path creates a `WebSocketApprovalManager` but never passes it through.

**Before (current):**
```python
if existing_session_id:
    logger.info("Continuing copilot session: %s", existing_session_id)
    copilot_approval_manager = WebSocketApprovalManager(ws_send_event, task_id, db_factory=_approval_db_factory)

    try:
        results = continue_copilot_sync(
            session_id=existing_session_id,
            additional_context=task,
            # approval_manager NOT passed!
        )
```

**After (fixed):**
```python
if existing_session_id:
    logger.info("Continuing copilot session: %s", existing_session_id)
    copilot_approval_manager = WebSocketApprovalManager(ws_send_event, task_id, db_factory=_approval_db_factory)

    try:
        results = continue_copilot_sync(
            session_id=existing_session_id,
            additional_context=task,
            approval_manager=copilot_approval_manager,
        )
```

**File:** `cmbagent/workflows/copilot.py`

Add `approval_manager` parameter to both continuation functions:

```python
async def continue_copilot(
    session_id: str,
    additional_context: str = None,
    approval_manager=None,  # NEW
) -> Dict[str, Any]:
    ...
    orchestrator = _active_copilot_sessions[session_id]

    # Re-attach approval manager for this continuation
    if approval_manager and hasattr(orchestrator, '_approval_manager'):
        orchestrator._approval_manager = approval_manager

    result = await orchestrator.continue_execution(additional_context)
    ...


def continue_copilot_sync(
    session_id: str,
    additional_context: str = None,
    approval_manager=None,  # NEW
) -> Dict[str, Any]:
    """Synchronous wrapper for continue_copilot."""
    return asyncio.run(continue_copilot(session_id, additional_context, approval_manager))
```

**File:** `cmbagent/workflows/swarm_copilot.py`

Same change for swarm copilot continuation:

```python
async def continue_swarm_copilot(
    session_id: str,
    additional_context: str = None,
    approval_manager=None,  # NEW
) -> Dict[str, Any]:
    ...
    orchestrator = _active_sessions[session_id]

    if approval_manager and hasattr(orchestrator, '_approval_manager'):
        orchestrator._approval_manager = approval_manager

    ...


def continue_swarm_copilot_sync(
    session_id: str,
    additional_context: str = None,
    approval_manager=None,  # NEW
) -> Dict[str, Any]:
    return asyncio.run(continue_swarm_copilot(session_id, additional_context, approval_manager))
```

---

### Task 4: Simplify WebSocket Handler to Single Resolution Path

**File:** `backend/websocket/handlers.py`

Replace the 3-layer fallback chain (lines 268-393, ~120 lines) with one call:

```python
elif msg_type in ["resolve_approval", "approval_response"]:
    approval_id = message.get("approval_id")

    # Support both 'resolution' and 'approved' formats
    if "approved" in message:
        resolution = "approved" if message.get("approved") else "rejected"
    else:
        resolution = message.get("resolution", "rejected")

    feedback = message.get("feedback", "")
    modifications = message.get("modifications", "")

    # Parse modifications into dict
    modifications_dict = {}
    if modifications:
        try:
            import json
            modifications_dict = json.loads(modifications) if isinstance(modifications, str) else modifications
        except (json.JSONDecodeError, TypeError):
            modifications_dict = {"raw": modifications}

    full_feedback = f"{feedback}\n\nModifications: {modifications}" if modifications else feedback

    # Single resolution path (Stage 11C)
    try:
        from cmbagent.database.websocket_approval_manager import WebSocketApprovalManager

        success = WebSocketApprovalManager.resolve_from_db(
            approval_id=approval_id,
            resolution=resolution,
            user_feedback=full_feedback,
            modifications=modifications_dict,
        )

        if success:
            logger.info("Approval %s resolved as %s", approval_id, resolution)
            await send_ws_event(
                websocket, "approval_received",
                {
                    "approval_id": approval_id,
                    "approved": resolution in ("approved", "modified"),
                    "resolution": resolution,
                    "feedback": full_feedback,
                },
                run_id=task_id,
            )
        else:
            logger.warning("Approval %s not found or already resolved", approval_id)
            await send_ws_event(
                websocket, "error",
                {"message": f"Approval {approval_id} not found or already resolved"},
                run_id=task_id,
            )

    except Exception as e:
        logger.error("Error resolving approval: %s", e)
        await send_ws_event(
            websocket, "error",
            {"message": f"Failed to resolve approval: {str(e)}"},
            run_id=task_id,
        )
```

---

### Task 5: Delete RobustApprovalManager

**File to DELETE:** `backend/services/approval_manager.py`

All its responsibilities are absorbed:
- DB persistence -> Task 1 (create + resolve write to DB)
- DB fallback resolution -> Task 1 (`resolve_from_db`)
- Timeout/expiration -> `wait_for_approval_async` timeout + `SessionManager._cleanup_expired()`

**File:** `backend/services/__init__.py`

Remove all approval manager imports and exports:
```python
# DELETE:
from services.approval_manager import (
    RobustApprovalManager,
    get_approval_manager,
    ApprovalTimeoutError,
    ApprovalExpiredError,
    ApprovalNotFoundError,
)

# DELETE from __all__:
"RobustApprovalManager",
"get_approval_manager",
"ApprovalTimeoutError",
"ApprovalExpiredError",
"ApprovalNotFoundError",
```

---

### Task 6: Delete Legacy ApprovalManager

**Key finding:** `CMBAgent` creates `ApprovalManager` at line 284 but **never calls any method on it** (`grep` for `self.approval_manager.` returns zero results). It's dead code.

The only other usage is `_get_approval_manager()` in `planning_control.py`, which is being replaced by Task 2's `approval_manager=` parameter.

**File to DELETE:** `cmbagent/database/approval_manager.py`

**File:** `cmbagent/database/__init__.py` -- remove imports:
```python
# DELETE:
from cmbagent.database.approval_manager import (
    ApprovalManager,
    WorkflowCancelledException,
    ApprovalTimeoutError,
)
```

And remove from `__all__`:
```python
# DELETE from __all__:
"ApprovalManager",
"WorkflowCancelledException",
"ApprovalTimeoutError",
```

**File:** `cmbagent/cmbagent.py` -- remove dead code:
```python
# DELETE line 228:
self.approval_manager: Optional[Any] = None

# DELETE lines 255, 284:
from cmbagent.database.approval_manager import ApprovalManager
self.approval_manager = ApprovalManager(self.db_session, self.session_id)

# DELETE line 305:
self.approval_manager = None
```

**File:** `cmbagent/workflows/planning_control.py` -- remove `_get_approval_manager`:
```python
# DELETE lines 204-210:
def _get_approval_manager(approval_config):
    """Get approval manager from config if available."""
    try:
        from cmbagent.database.approval_manager import ApprovalManager
        return ApprovalManager(approval_config)
    except ImportError:
        return None
```

Update executor creation (done in Task 2) to no longer call this function.

---

### Task 7: Pass db_factory to All WebSocketApprovalManager Instantiations

**File:** `backend/execution/task_executor.py`

The `_approval_db_factory` is already resolved once at lines 551-556. Ensure all instantiation sites use it:

| Line | Mode | Current | After |
|------|------|---------|-------|
| NEW (Task 2) | planning-control | N/A | `WebSocketApprovalManager(ws_send_event, task_id, db_factory=_approval_db_factory)` |
| 614 | hitl-interactive | `WebSocketApprovalManager(ws_send_event, task_id)` | `WebSocketApprovalManager(ws_send_event, task_id, db_factory=_approval_db_factory)` |
| 695 | copilot continuation | `WebSocketApprovalManager(ws_send_event, task_id, db_factory=_approval_db_factory)` | Already correct |
| 720 | copilot new session | `WebSocketApprovalManager(ws_send_event, task_id)` | `WebSocketApprovalManager(ws_send_event, task_id, db_factory=_approval_db_factory)` |

Note: Line 614 and 720 may already have `db_factory=_approval_db_factory` depending on which changes were applied at which point. Verify each site.

---

### Task 8: Update Examples

**File:** `examples/hitl_feedback_flow_example.py`

This file imports `ApprovalManager`. Update to use `WebSocketApprovalManager` or if it demonstrates CLI-only usage without WebSocket, create a mock `ws_send_event`:

```python
# For CLI examples without WebSocket:
def noop_send_event(event_type, data):
    print(f"[APPROVAL] {event_type}: {data.get('message', '')}")

approval_manager = WebSocketApprovalManager(noop_send_event, "example-run")
```

---

## Complete Files Change Summary

### Files to DELETE
| File | Reason |
|------|--------|
| `backend/services/approval_manager.py` | `RobustApprovalManager` -- 0 call sites in workflow code, `asyncio.Event` wrong thread model |
| `cmbagent/database/approval_manager.py` | `ApprovalManager` -- dead code in CMBAgent, replaced by Task 2 in planning-control |

### Files to MODIFY
| File | Change | Task |
|------|--------|------|
| `cmbagent/database/websocket_approval_manager.py` | Add `db_factory`, DB persist on create/resolve, `resolve_from_db()` | 1 |
| `backend/execution/task_executor.py` | Migrate planning-control to `approval_manager=`, fix copilot continuation, `db_factory` on all sites | 2, 3, 7 |
| `cmbagent/workflows/planning_control.py` | Add `approval_manager=` param, remove `_get_approval_manager()` | 2, 6 |
| `cmbagent/workflows/copilot.py` | Add `approval_manager=` to `continue_copilot`/`continue_copilot_sync` | 3 |
| `cmbagent/workflows/swarm_copilot.py` | Add `approval_manager=` to `continue_swarm_copilot`/`continue_swarm_copilot_sync` | 3 |
| `backend/websocket/handlers.py` | Replace 120-line 3-layer fallback with single `resolve_from_db()` | 4 |
| `backend/services/__init__.py` | Remove `RobustApprovalManager` exports | 5 |
| `cmbagent/database/__init__.py` | Remove `ApprovalManager` exports | 6 |
| `cmbagent/cmbagent.py` | Remove dead `self.approval_manager` code | 6 |
| `examples/hitl_feedback_flow_example.py` | Update to use `WebSocketApprovalManager` | 8 |

### Files NOT modified (32 call sites stay the same)
| File | Call Sites |
|------|-----------|
| `cmbagent/phases/copilot_phase.py` | 10 (5 create + 5 wait) |
| `cmbagent/phases/hitl_control.py` | 6 (3 create + 3 wait) |
| `cmbagent/phases/hitl_checkpoint.py` | 2 (1 create + 1 wait) |
| `cmbagent/phases/hitl_planning.py` | 2 (1 create + 1 wait) |
| `cmbagent/orchestrator/swarm_orchestrator.py` | 8 (4 create + 4 wait) |
| `cmbagent/handoffs/hitl.py` | 4 (2 create + 2 wait) |

**Total: 32 call sites -- zero changes needed.**

---

## Execution Order

Tasks must be done in this order due to dependencies:

```
Task 1 (enhance WebSocketApprovalManager)
  │
  ├── Task 7 (db_factory on all instantiation sites)
  │
  ├── Task 2 (migrate planning-control)
  │     └── depends on Task 1 (needs db_factory param)
  │     └── depends on Task 6 (removes _get_approval_manager)
  │
  ├── Task 3 (fix copilot continuation)
  │
  ├── Task 4 (simplify handler)
  │     └── depends on Task 1 (needs resolve_from_db)
  │
  ├── Task 5 (delete RobustApprovalManager)
  │     └── depends on Task 4 (handler no longer imports it)
  │
  ├── Task 6 (delete legacy ApprovalManager)
  │     └── depends on Task 2 (planning-control no longer uses it)
  │
  └── Task 8 (update examples)
        └── depends on Task 6 (examples import deleted class)
```

**Safe implementation sequence:** Task 1 → Task 7 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 8

---

## Rollback Plan

If issues arise:
1. Revert `websocket_approval_manager.py` (DB persistence is additive, removing it restores original behavior)
2. Restore `backend/services/approval_manager.py` from git
3. Restore `cmbagent/database/approval_manager.py` from git
4. Restore the 3-layer fallback in `handlers.py` from git
5. Restore imports in `__init__.py` files

The in-memory fast path works independently of DB persistence, so partial rollback is safe.

---

## Session System Impact

**None.** The session system (Stages 1-3, 10-11) and approval system are independent:

| System | Responsibility | Table |
|--------|---------------|-------|
| `SessionManager` | Workflow state (phase, step, conversation) | `session_states` |
| `WebSocketApprovalManager` | Pause/resume for human input | `approval_requests` |

They share `session_id` as a foreign key but never call each other. `SessionManager._cleanup_expired()` already handles cleaning up expired approval records from the `approval_requests` table.

---

## Verification Criteria

### Must Pass

- [ ] **hitl-interactive**: create approval -> wait -> resolve -> phase resumes
- [ ] **copilot new session**: approval request -> user responds -> workflow continues
- [ ] **copilot continuation**: resumed session can request and receive approvals
- [ ] **planning-control with approvalMode**: approval checkpoint works via `WebSocketApprovalManager`
- [ ] **planning-control without approvalMode**: no approval manager created, workflow runs normally
- [ ] Approval persisted to `approval_requests` table on create
- [ ] Approval updated in `approval_requests` table on resolve
- [ ] Handler uses single `resolve_from_db()` path (no fallback chain)
- [ ] DB persistence failure is non-fatal (in-memory still works)
- [ ] `__init__` without `db_factory` still works (backwards compat)

### Verification Commands

```bash
# Verify both files deleted
test ! -f backend/services/approval_manager.py && echo "PASS: RobustApprovalManager deleted"
test ! -f cmbagent/database/approval_manager.py && echo "PASS: Legacy ApprovalManager deleted"

# Verify no remaining imports of deleted classes
grep -rn "RobustApprovalManager\|from services.approval_manager\|from cmbagent.database.approval_manager" backend/ cmbagent/
# Expected: 0 matches

# Verify handler has no fallback chain
grep -c "legacy_am\|get_approval_manager\|_get_approval_manager" backend/websocket/handlers.py cmbagent/workflows/planning_control.py
# Expected: 0

# Verify resolve_from_db exists
grep -n "def resolve_from_db" cmbagent/database/websocket_approval_manager.py
# Expected: 1 match

# Verify db_factory on all instantiation sites
grep -n "WebSocketApprovalManager(" backend/execution/task_executor.py
# Expected: all lines include db_factory=

# Verify planning-control uses approval_manager= not approval_config=
grep -n "approval_manager=" backend/execution/task_executor.py | grep -i "planning"
# Expected: 1 match

# Verify continue_copilot_sync accepts approval_manager
grep -A2 "def continue_copilot_sync" cmbagent/workflows/copilot.py
# Expected: approval_manager parameter present

# Verify all phase call sites unchanged (regression check)
grep -c "create_approval_request\|wait_for_approval_async" cmbagent/phases/*.py cmbagent/orchestrator/*.py cmbagent/handoffs/hitl.py
# Expected: same counts as before

# Verify CMBAgent no longer creates approval_manager
grep -n "self.approval_manager" cmbagent/cmbagent.py
# Expected: 0 matches

# Verify dead _get_approval_manager removed
grep -n "_get_approval_manager" cmbagent/workflows/planning_control.py
# Expected: 0 matches
```

---

## Success Criteria

Stage 11C is complete when:
1. [ ] `WebSocketApprovalManager` is the **only** approval system for all WebSocket workflows
2. [ ] `backend/services/approval_manager.py` deleted (RobustApprovalManager gone)
3. [ ] `cmbagent/database/approval_manager.py` deleted (legacy ApprovalManager gone)
4. [ ] `planning-control` mode uses `WebSocketApprovalManager` via `approval_manager=` parameter
5. [ ] Copilot continuation passes `approval_manager` through to orchestrator
6. [ ] Handler resolution is a single code path (`resolve_from_db`)
7. [ ] DB persistence works for create and resolve (best-effort)
8. [ ] 32 phase/orchestrator call sites: zero changes
9. [ ] All modes without approvals: zero impact

## Next Stage

**Stage 12: Unit & Integration Tests**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-12
