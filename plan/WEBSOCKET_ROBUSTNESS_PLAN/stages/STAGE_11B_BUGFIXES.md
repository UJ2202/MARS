# Stage 11B: Post-Implementation Bug Fixes & Corrections

**Phase:** 4.5 - Bug Fixes (between Phase 4 and Phase 5)
**Dependencies:** Stages 1-11
**Risk Level:** High (bugs prevent isolated execution from working)

## Overview

This stage documents all bugs and issues discovered during the Stage 1-11 implementation verification audit.
Fixes are organized by severity: **Critical** (runtime errors), **Medium** (functional gaps), **Low** (cleanup).

---

## CRITICAL BUGS

### Bug 1: Wrong Method Name in Isolated Execution Path

**File:** `backend/execution/task_executor.py`
**Lines:** 1000, 1024
**Severity:** CRITICAL - causes `AttributeError` at runtime

**Problem:**
The `_execute_isolated` function calls `session_manager.save_state()`, but this method does not exist on `SessionManager`. The correct method is `save_session_state()`.

Additionally, the parameter format is wrong. The isolated path passes a nested `state={}` dict, but `save_session_state()` expects flat keyword arguments.

**Current (broken):**
```python
# Line 1000 - phase change save
await session_manager.save_state(
    session_id=session_id,
    state={
        "conversation_history": conversation_buffer[-100:],
        "context_variables": data.get("context", {}),
        "current_phase": data.get("phase"),
        "current_step": data.get("step"),
    }
)

# Line 1024 - final save on completion
await session_manager.save_state(
    session_id=session_id,
    state={
        "conversation_history": conversation_buffer,
        "context_variables": result.get("final_context", {}),
        "current_phase": "completed",
    }
)
```

**Fix (correct):**
```python
# Line 1000 - phase change save (matches legacy path at line 415)
session_manager.save_session_state(
    session_id=session_id,
    conversation_history=conversation_buffer[-100:],
    context_variables=data.get("context", {}),
    current_phase=data.get("phase"),
    current_step=data.get("step"),
)

# Line 1024 - final save on completion (matches legacy path at line 879)
session_manager.save_session_state(
    session_id=session_id,
    conversation_history=conversation_buffer,
    context_variables=result.get("final_context", {}),
    current_phase="completed",
)
```

**Reference:** The legacy execution path at lines 415-420 and 879-883 uses the correct pattern.

---

### Bug 2: Awaiting Synchronous Methods in Isolated Path

**File:** `backend/execution/task_executor.py`
**Lines:** 1000, 1024, 1032, 1062
**Severity:** CRITICAL - causes `TypeError: object NoneType can't be used in 'await' expression`

**Problem:**
`SessionManager.save_session_state()`, `.complete_session()`, and `.suspend_session()` are all **synchronous** methods (they use blocking SQLAlchemy calls). The isolated execution path incorrectly uses `await` on all of them.

**Current (broken):**
```python
# Line 1000 & 1024
await session_manager.save_state(...)   # save_session_state is sync

# Line 1032
await session_manager.complete_session(session_id)  # complete_session is sync

# Line 1062
await session_manager.suspend_session(session_id)   # suspend_session is sync
```

**Fix:** Remove `await` from all four calls:
```python
# Line 1000 & 1024
session_manager.save_session_state(...)   # no await

# Line 1032
session_manager.complete_session(session_id)  # no await

# Line 1062
session_manager.suspend_session(session_id)   # no await
```

**Reference:** The legacy path at lines 415, 884, 935 correctly calls these without `await`.

---

## MEDIUM ISSUES

### Issue 3: Three Approval Systems Coexist Without Deprecation Warnings

**File:** `backend/websocket/handlers.py`
**Lines:** 269-385
**Severity:** MEDIUM - maintenance burden, potential inconsistency

**Problem:**
The approval handler has a three-layer fallback chain:
1. `WebSocketApprovalManager` (in-memory, from `cmbagent.database`)
2. `RobustApprovalManager` (database-backed, from `backend.services`)
3. `ApprovalManager` (legacy database-backed, from `cmbagent.database`)

None of the legacy systems emit deprecation warnings. Developers may unknowingly use the wrong one.

**Fix:**
Add deprecation logging to legacy approval managers when they're invoked:

```python
# In the approval handler fallback chain:
# After WebSocketApprovalManager resolves:
logger.info("Approval resolved via legacy WebSocketApprovalManager (deprecated)")

# After cmbagent.database.ApprovalManager resolves:
logger.info("Approval resolved via legacy ApprovalManager (deprecated)")
```

**Long-term:** Migrate all callers to `RobustApprovalManager` and remove legacy systems.

---

### Issue 4: PROGRESS.md Is Stale

**File:** `WEBSOCKET_ROBUSTNESS_PLAN/PROGRESS.md`
**Severity:** MEDIUM - misleading for anyone using the plan

**Problem:**
PROGRESS.md shows Stages 6-9 as "Not Started" when they are actually implemented. This creates confusion for anyone resuming the plan.

**Fix:**
Update PROGRESS.md to reflect the true state:
- Stage 6: Complete (with critical bugs - pending this fix stage)
- Stage 7: Complete (with critical bugs - pending this fix stage)
- Stage 8: Complete
- Stage 9: Complete
- Stage 10: Complete
- Stage 11: Complete
- Current stage: 11B (Bug Fixes)

---

### Issue 5: In-Memory Session Caches Still Active

**File:** `cmbagent/workflows/copilot.py` (line 45), `cmbagent/workflows/swarm_copilot.py` (line 72)
**Severity:** MEDIUM - sessions lost on restart, blocks horizontal scaling

**Problem:**
Module-level dicts `_active_copilot_sessions` and `_active_sessions` hold live `SwarmOrchestrator` instances in memory. Stage 3 required these be removed in favor of `SessionManager`.

**Context:**
These caches serve a dual purpose: they store live orchestrator objects for active conversations (which cannot be serialized to a database). The `SessionManager` handles state *persistence* (conversation history, phase, context), but the live orchestrator reference must exist in-memory during active execution.

**Fix:**
1. Add comments clarifying the distinction between live orchestrator cache vs. persistent state
2. Add cleanup on session completion to prevent memory leaks
3. Ensure orchestrator is re-created from `SessionManager` state on session resume (not from in-memory dict)

---

## LOW ISSUES

### Issue 6: Conversation Buffer Unbounded Growth

**File:** `backend/execution/task_executor.py`
**Lines:** 351-375 (legacy), 990-995 (isolated)
**Severity:** LOW - mitigated by `-100:` slice on save

**Problem:**
The `conversation_buffer` list grows without bound during execution. Only the last 100 entries are saved to DB, but the in-memory list could become very large during long-running workflows.

**Fix (optional):**
Cap the buffer at 200 entries with periodic pruning:
```python
# After appending to conversation_buffer:
if len(conversation_buffer) > 200:
    conversation_buffer = conversation_buffer[-100:]
```

---

### Issue 7: No Optimistic Locking Retry

**File:** `backend/services/session_manager.py`
**Lines:** 122-191
**Severity:** LOW - unlikely in practice since one task = one session

**Problem:**
`save_session_state()` uses optimistic locking (version column increment), but if a version conflict occurs, the save silently fails. There's no retry logic.

**Fix (optional):**
Add a single retry on version mismatch:
```python
def save_session_state(self, ...):
    for attempt in range(2):  # retry once
        db = self.db_factory()
        try:
            state = db.query(SessionState).filter(...).first()
            if not state:
                return False
            state.version += 1
            # ... set fields ...
            db.commit()
            return True
        except StaleDataError:
            db.rollback()
            if attempt == 0:
                logger.warning("Version conflict for session %s, retrying", session_id)
                continue
            return False
        finally:
            db.close()
```

---

### Issue 8: Session ID Key Naming Inconsistency

**Files:** `backend/websocket/handlers.py` (line 87), `cmbagent-ui/contexts/WebSocketContext.tsx`
**Severity:** LOW - functional but confusing

**Problem:**
Two naming conventions are used for session ID:
- `copilotSessionId` (camelCase, frontend/WebSocket)
- `session_id` (snake_case, backend/API)

The handler checks both: `config.get("copilotSessionId") or config.get("session_id")`

**Fix (optional):**
Standardize on `session_id` for all new code. Keep `copilotSessionId` as alias for backwards compatibility but add a comment noting the canonical name.

---

### Issue 9: Missing Error Recovery UI Feedback on Session Resume

**File:** `cmbagent-ui/app/page.tsx`
**Lines:** 342-394
**Severity:** LOW - errors are logged but user sees nothing

**Problem:**
If the session resume API call fails, the error is caught and logged to console but the user isn't notified visually.

**Fix (optional):**
Add toast/notification on resume failure:
```typescript
} catch (error) {
  console.error("Failed to resume session:", error);
  addConsoleOutput(`Failed to resume session: ${error}`);
  // Optionally show a toast notification
}
```

---

## Implementation Checklist

### Must Fix (Before Stage 12)

| # | Bug | File | Lines | Fix |
|---|-----|------|-------|-----|
| 1 | Wrong method name `save_state` | `task_executor.py` | 1000, 1024 | Rename to `save_session_state` with flat args |
| 2 | `await` on sync methods | `task_executor.py` | 1000, 1024, 1032, 1062 | Remove `await` keyword |
| 4 | Stale PROGRESS.md | `PROGRESS.md` | - | Update stage statuses |

### Should Fix (Before Stage 14)

| # | Issue | File | Fix |
|---|-------|------|-----|
| 3 | No deprecation warnings on legacy approval managers | `handlers.py` | Add deprecation log lines |
| 5 | In-memory cache lifecycle | `copilot.py`, `swarm_copilot.py` | Add cleanup + clarifying comments |

### Nice to Have (Before Stage 14)

| # | Issue | File | Fix |
|---|-------|------|-----|
| 6 | Unbounded conversation buffer | `task_executor.py` | Cap at 200 entries |
| 7 | No optimistic locking retry | `session_manager.py` | Add single retry |
| 8 | Session ID naming inconsistency | Multiple | Standardize on `session_id` |
| 9 | Missing resume error UI feedback | `page.tsx` | Add user-visible error notification |

---

## Verification Criteria

### Must Pass
- [ ] `_execute_isolated` calls `session_manager.save_session_state()` (not `save_state`)
- [ ] No `await` before `session_manager.save_session_state()`, `.complete_session()`, `.suspend_session()`
- [ ] Isolated path uses flat keyword args matching the `save_session_state()` signature
- [ ] Legacy execution path (lines 415, 879-884, 930-935) still works correctly (no regression)
- [ ] PROGRESS.md reflects accurate stage completion status

### Verification Commands

```bash
# Verify no more calls to non-existent save_state method
grep -n "session_manager.save_state(" backend/execution/task_executor.py
# Expected: 0 matches

# Verify no await on sync session_manager methods
grep -n "await session_manager\.\(save_session_state\|complete_session\|suspend_session\)" backend/execution/task_executor.py
# Expected: 0 matches

# Verify correct sync calls exist
grep -n "session_manager.save_session_state\|session_manager.complete_session\|session_manager.suspend_session" backend/execution/task_executor.py
# Expected: 6+ matches (3 legacy + 3 isolated, all without await)
```

## Success Criteria

Stage 11B is complete when:
1. [ ] All critical bugs fixed (Bugs 1-2)
2. [ ] PROGRESS.md updated (Issue 4)
3. [ ] Isolated execution path session management works identically to legacy path
4. [ ] No regressions in existing functionality

## Next Stage

**Stage 12: Unit & Integration Tests**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-12
