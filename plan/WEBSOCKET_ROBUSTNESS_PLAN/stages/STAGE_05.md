# Stage 5: Approval Manager Refactor

**Phase:** 1 - Core Infrastructure
**Dependencies:** Stage 2 (approval_requests table), Stage 4 (ConnectionManager)
**Risk Level:** Medium
**Estimated Time:** 4-5 hours

## Objectives

1. Create `RobustApprovalManager` with database persistence
2. Implement timeout handling for approvals
3. Support both fast path (local event) and slow path (DB polling)
4. Ensure idempotent resolution

## Current State Analysis

### What We Have
- `cmbagent/database/websocket_approval_manager.py` - Class variables, in-memory only
- Approvals lost on server restart
- No timeout handling - can hang forever
- Resolution not idempotent

### What We Need
- Database-backed approvals that survive restarts
- Configurable timeout with automatic expiration
- Local event for fast notification + DB for durability
- Idempotent resolution (clicking approve twice doesn't break things)

## Implementation Tasks

### Task 1: Create RobustApprovalManager

**Objective:** Implement approval manager with persistence and timeout

**File to Create:** `backend/services/approval_manager.py`

```python
"""
Robust Approval Manager for HITL Workflows

Provides database-backed approval handling with:
- Persistence across server restarts
- Configurable timeout and automatic expiration
- Fast path (local event) + slow path (DB polling)
- Idempotent resolution
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ApprovalTimeoutError(Exception):
    """Raised when approval request times out"""
    def __init__(self, approval_id: str, timeout_seconds: int):
        self.approval_id = approval_id
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Approval {approval_id} timed out after {timeout_seconds}s")


class ApprovalExpiredError(Exception):
    """Raised when approval was already expired or cancelled"""
    def __init__(self, approval_id: str):
        self.approval_id = approval_id
        super().__init__(f"Approval {approval_id} is expired or cancelled")


class ApprovalNotFoundError(Exception):
    """Raised when approval request not found"""
    def __init__(self, approval_id: str):
        self.approval_id = approval_id
        super().__init__(f"Approval {approval_id} not found")


class RobustApprovalManager:
    """
    Database-backed approval manager with timeout support.

    Approval flow:
    1. Request approval -> creates DB record + local event
    2. Wait for approval -> waits on local event OR polls DB
    3. Resolve approval -> updates DB + sets local event

    The dual approach ensures:
    - Fast response when running on same instance (local event)
    - Resilience across restarts (DB polling)
    """

    def __init__(
        self,
        db_factory: Callable,
        default_timeout: int = 300,
        poll_interval: float = 2.0
    ):
        """
        Initialize the approval manager.

        Args:
            db_factory: Callable that returns database session
            default_timeout: Default timeout in seconds (5 minutes)
            poll_interval: Interval for DB polling in seconds
        """
        self.db_factory = db_factory
        self.default_timeout = default_timeout
        self.poll_interval = poll_interval

        # Local events for fast notification (same instance)
        self._local_events: Dict[str, asyncio.Event] = {}
        self._local_results: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        logger.info(
            "RobustApprovalManager initialized (timeout=%ds, poll=%.1fs)",
            default_timeout, poll_interval
        )

    async def request_approval(
        self,
        run_id: str,
        approval_type: str,
        context: Dict[str, Any],
        timeout_seconds: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Request an approval from the user.

        Args:
            run_id: Workflow run identifier
            approval_type: Type of approval (plan_approval, step_approval, etc.)
            context: Context data to show user (what they're approving)
            timeout_seconds: Timeout for this approval (uses default if not specified)
            session_id: Optional session identifier

        Returns:
            approval_id (UUID string)
        """
        from cmbagent.database.models import ApprovalRequest

        approval_id = str(uuid4())
        timeout = timeout_seconds or self.default_timeout
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=timeout)

        # Create DB record
        db = self.db_factory()
        try:
            approval = ApprovalRequest(
                id=approval_id,
                run_id=run_id,
                session_id=session_id,
                approval_type=approval_type,
                context=context,
                status="pending",
                expires_at=expires_at
            )
            db.add(approval)
            db.commit()

            logger.info(
                "Created approval request: id=%s, type=%s, run=%s, timeout=%ds",
                approval_id, approval_type, run_id, timeout
            )

        except Exception as e:
            db.rollback()
            logger.error("Failed to create approval request: %s", e)
            raise
        finally:
            db.close()

        # Create local event for fast notification
        async with self._lock:
            self._local_events[approval_id] = asyncio.Event()

        return approval_id

    async def wait_for_approval(
        self,
        approval_id: str,
        timeout_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Wait for approval resolution.

        Uses both local event (fast path) and DB polling (resilient path).

        Args:
            approval_id: Approval request identifier
            timeout_seconds: Override timeout (uses remaining time from DB if not specified)

        Returns:
            Resolution result dict with keys: resolution, feedback, modifications

        Raises:
            ApprovalTimeoutError: If approval times out
            ApprovalExpiredError: If approval was already expired/cancelled
            ApprovalNotFoundError: If approval doesn't exist
        """
        from cmbagent.database.models import ApprovalRequest

        # Get deadline from DB
        db = self.db_factory()
        try:
            approval = db.query(ApprovalRequest).filter(
                ApprovalRequest.id == approval_id
            ).first()

            if not approval:
                raise ApprovalNotFoundError(approval_id)

            if approval.status == "expired":
                raise ApprovalExpiredError(approval_id)

            if approval.status == "resolved":
                # Already resolved (e.g., server restarted and we're checking)
                return approval.result or {}

            deadline = approval.expires_at
            if timeout_seconds:
                deadline = min(
                    deadline,
                    datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
                )

        finally:
            db.close()

        # Get local event
        async with self._lock:
            event = self._local_events.get(approval_id)
            if not event:
                event = asyncio.Event()
                self._local_events[approval_id] = event

        # Wait loop: check event and DB
        while datetime.now(timezone.utc) < deadline:
            # Check if local event set (fast path)
            try:
                await asyncio.wait_for(event.wait(), timeout=self.poll_interval)
                # Event was set - check local result
                async with self._lock:
                    if approval_id in self._local_results:
                        result = self._local_results.pop(approval_id)
                        self._local_events.pop(approval_id, None)
                        logger.info("Approval %s resolved via local event", approval_id)
                        return result
            except asyncio.TimeoutError:
                pass  # Continue to DB check

            # Check DB (slow path - handles server restart case)
            db = self.db_factory()
            try:
                approval = db.query(ApprovalRequest).filter(
                    ApprovalRequest.id == approval_id
                ).first()

                if not approval:
                    raise ApprovalNotFoundError(approval_id)

                if approval.status == "resolved":
                    # Resolved in DB (possibly by another instance)
                    async with self._lock:
                        self._local_events.pop(approval_id, None)
                        self._local_results.pop(approval_id, None)

                    logger.info("Approval %s resolved via DB poll", approval_id)
                    return approval.result or {}

                if approval.status == "expired":
                    raise ApprovalExpiredError(approval_id)

            finally:
                db.close()

        # Timeout reached
        await self._expire_approval(approval_id)
        timeout_used = int((datetime.now(timezone.utc) - deadline).total_seconds()) + self.default_timeout
        raise ApprovalTimeoutError(approval_id, timeout_used)

    async def resolve_approval(
        self,
        approval_id: str,
        resolution: str,
        feedback: str = "",
        modifications: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Resolve an approval request.

        This operation is idempotent - resolving an already-resolved approval
        returns False but doesn't raise an error.

        Args:
            approval_id: Approval request identifier
            resolution: Resolution type (approved, rejected, modified)
            feedback: User feedback text
            modifications: Optional modifications to the approved item

        Returns:
            True if resolved, False if already resolved/expired
        """
        from cmbagent.database.models import ApprovalRequest

        result = {
            "resolution": resolution,
            "feedback": feedback,
            "modifications": modifications or {}
        }

        # Update DB (idempotent - only updates if pending)
        db = self.db_factory()
        try:
            rows_affected = db.query(ApprovalRequest).filter(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.status == "pending"
            ).update({
                "status": "resolved",
                "resolution": resolution,
                "result": result,
                "resolved_at": datetime.now(timezone.utc)
            })

            db.commit()

            if rows_affected == 0:
                # Already resolved or not found
                approval = db.query(ApprovalRequest).filter(
                    ApprovalRequest.id == approval_id
                ).first()

                if not approval:
                    logger.warning("Approval %s not found during resolution", approval_id)
                    return False

                if approval.status == "resolved":
                    logger.info("Approval %s already resolved (idempotent)", approval_id)
                    return False

                logger.warning("Approval %s in unexpected state: %s", approval_id, approval.status)
                return False

            logger.info(
                "Resolved approval %s as %s",
                approval_id, resolution
            )

        except Exception as e:
            db.rollback()
            logger.error("Failed to resolve approval %s: %s", approval_id, e)
            raise
        finally:
            db.close()

        # Set local event for fast notification
        async with self._lock:
            self._local_results[approval_id] = result
            if approval_id in self._local_events:
                self._local_events[approval_id].set()

        return True

    async def cancel_approval(self, approval_id: str) -> bool:
        """
        Cancel a pending approval request.

        Args:
            approval_id: Approval request identifier

        Returns:
            True if cancelled, False if not pending
        """
        from cmbagent.database.models import ApprovalRequest

        db = self.db_factory()
        try:
            rows_affected = db.query(ApprovalRequest).filter(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.status == "pending"
            ).update({
                "status": "cancelled"
            })

            db.commit()

            if rows_affected > 0:
                logger.info("Cancelled approval %s", approval_id)
                return True
            return False

        finally:
            db.close()

    async def _expire_approval(self, approval_id: str):
        """Mark approval as expired"""
        from cmbagent.database.models import ApprovalRequest

        db = self.db_factory()
        try:
            db.query(ApprovalRequest).filter(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.status == "pending"
            ).update({
                "status": "expired"
            })
            db.commit()

            async with self._lock:
                self._local_events.pop(approval_id, None)
                self._local_results.pop(approval_id, None)

            logger.info("Expired approval %s", approval_id)

        finally:
            db.close()

    def has_pending(self, approval_id: str) -> bool:
        """Check if approval is pending (for quick checks)"""
        from cmbagent.database.models import ApprovalRequest

        db = self.db_factory()
        try:
            approval = db.query(ApprovalRequest).filter(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.status == "pending"
            ).first()
            return approval is not None
        finally:
            db.close()

    def get_pending_for_run(self, run_id: str) -> list:
        """Get all pending approvals for a run"""
        from cmbagent.database.models import ApprovalRequest

        db = self.db_factory()
        try:
            approvals = db.query(ApprovalRequest).filter(
                ApprovalRequest.run_id == run_id,
                ApprovalRequest.status == "pending"
            ).all()
            return [a.to_dict() for a in approvals]
        finally:
            db.close()


# Factory function
def create_approval_manager() -> RobustApprovalManager:
    """Create an approval manager with database factory"""
    from cmbagent.database import get_db_session
    return RobustApprovalManager(db_factory=get_db_session)


# Global instance (lazy)
_approval_manager: Optional[RobustApprovalManager] = None


def get_approval_manager() -> RobustApprovalManager:
    """Get global approval manager instance"""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = create_approval_manager()
    return _approval_manager
```

### Task 2: Update WebSocket Handler for Approvals

**Objective:** Use RobustApprovalManager in approval resolution

**File to Modify:** `backend/websocket/handlers.py`

**Update handle_client_message function:**

```python
# Add import
from services.approval_manager import get_approval_manager

# In handle_client_message, update approval handling:
elif msg_type in ["resolve_approval", "approval_response"]:
    approval_id = message.get("approval_id")

    # Support both formats
    if "approved" in message:
        resolution = "approved" if message.get("approved") else "rejected"
    else:
        resolution = message.get("resolution", "rejected")

    feedback = message.get("feedback", "")
    modifications = message.get("modifications")

    # Use RobustApprovalManager
    approval_manager = get_approval_manager()

    try:
        success = await approval_manager.resolve_approval(
            approval_id=approval_id,
            resolution=resolution,
            feedback=feedback,
            modifications=modifications
        )

        if success:
            await send_ws_event(
                websocket, "approval_received",
                {
                    "approval_id": approval_id,
                    "approved": resolution in ("approved", "modified"),
                    "resolution": resolution,
                    "feedback": feedback,
                },
                run_id=task_id,
            )
        else:
            await send_ws_event(
                websocket, "error",
                {"message": f"Approval {approval_id} already resolved or not found"},
                run_id=task_id
            )

    except Exception as e:
        logger.error(f"Error resolving approval: {e}")
        await send_ws_event(
            websocket, "error",
            {"message": f"Failed to resolve approval: {str(e)}"},
            run_id=task_id
        )
```

### Task 3: Export from Services

**File to Modify:** `backend/services/__init__.py`

```python
from services.approval_manager import (
    RobustApprovalManager,
    get_approval_manager,
    ApprovalTimeoutError,
    ApprovalExpiredError,
)
```

## Verification Criteria

### Must Pass
- [ ] Approvals persist to database
- [ ] Timeout works correctly (auto-expires)
- [ ] Resolution is idempotent
- [ ] Fast path (local event) works
- [ ] Slow path (DB polling) works

### Test Script
```python
# test_stage_5.py
import asyncio
from backend.services.approval_manager import (
    create_approval_manager,
    ApprovalTimeoutError
)

async def test_approval_manager():
    am = create_approval_manager()

    # Create a mock run_id
    run_id = "test_run_123"

    # Test request approval
    approval_id = await am.request_approval(
        run_id=run_id,
        approval_type="plan_approval",
        context={"plan": "Test plan", "steps": ["step1", "step2"]},
        timeout_seconds=10
    )
    assert approval_id is not None
    print(f"✅ Created approval: {approval_id}")

    # Test has_pending
    assert am.has_pending(approval_id)
    print("✅ has_pending works")

    # Test resolve (in separate task to simulate user action)
    async def simulate_user_approval():
        await asyncio.sleep(1)  # Simulate user thinking
        result = await am.resolve_approval(
            approval_id=approval_id,
            resolution="approved",
            feedback="Looks good!",
            modifications={"added": "extra"}
        )
        assert result is True
        print("✅ Resolved approval")

    # Start user simulation and wait for approval
    user_task = asyncio.create_task(simulate_user_approval())

    result = await am.wait_for_approval(approval_id)
    assert result["resolution"] == "approved"
    assert result["feedback"] == "Looks good!"
    print("✅ wait_for_approval works")

    await user_task

    # Test idempotent resolution
    result = await am.resolve_approval(approval_id, "rejected", "Too late")
    assert result is False  # Already resolved
    print("✅ Idempotent resolution works")

    # Test timeout
    approval_id_2 = await am.request_approval(
        run_id=run_id,
        approval_type="step_approval",
        context={"step": 1},
        timeout_seconds=2  # Short timeout for testing
    )

    try:
        await am.wait_for_approval(approval_id_2)
        assert False, "Should have timed out"
    except ApprovalTimeoutError as e:
        assert e.approval_id == approval_id_2
        print("✅ Timeout works")

    # Verify expired in DB
    assert not am.has_pending(approval_id_2)
    print("✅ Expiration persisted")

    print("\n✅ All ApprovalManager tests passed!")

if __name__ == "__main__":
    asyncio.run(test_approval_manager())
```

## Common Issues and Solutions

### Issue 1: Event not set across coroutines
**Symptom:** wait_for_approval never returns even after resolve
**Solution:** Ensure same event loop, use asyncio.Lock

### Issue 2: DB deadlock on polling
**Symptom:** Queries hang
**Solution:** Use short-lived DB sessions, always close in finally

## Rollback Procedure

```bash
git checkout backend/websocket/handlers.py
rm backend/services/approval_manager.py
```

## Success Criteria

Stage 5 is complete when:
1. ✅ Approvals persist to database
2. ✅ Timeout works and expires approvals
3. ✅ Resolution is idempotent
4. ✅ Both fast and slow paths work
5. ✅ All tests pass

## Next Stage

Once Stage 5 is verified complete, proceed to:
**Stage 6: Process-Based Isolation**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-11
