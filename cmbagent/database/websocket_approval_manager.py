"""
Lightweight WebSocket-based approval manager for HITL workflows.

This module provides a simple in-memory approval manager that uses
WebSocket events to communicate with the UI, without requiring
database records for approval requests.

Used when running HITL workflows from the web UI where the full
database-backed ApprovalManager may not be initialized.
"""

import asyncio
import threading
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable

logger = logging.getLogger(__name__)


@dataclass
class SimpleApprovalRequest:
    """In-memory approval request."""
    id: str
    run_id: str
    step_id: str
    checkpoint_type: str
    context_snapshot: Dict[str, Any]
    message: str
    options: List[str]
    status: str = "pending"
    resolution: str = None
    user_feedback: str = None
    modifications: Dict[str, Any] = field(default_factory=dict)
    _event: threading.Event = field(default_factory=threading.Event)


class WebSocketApprovalManager:
    """
    Lightweight approval manager using WebSocket events.

    This manager stores approval requests in memory and uses
    threading.Event for synchronization between the workflow thread
    and the WebSocket handler thread.

    Usage:
        # In task executor (workflow thread):
        manager = WebSocketApprovalManager(ws_send_event, task_id)

        # In HITL phase (called by workflow):
        request = manager.create_approval_request(...)
        resolved = await manager.wait_for_approval_async(request.id)

        # In WebSocket handler (main thread):
        WebSocketApprovalManager.resolve(approval_id, resolution, feedback)
    """

    # Class-level registry of pending approvals (shared across threads)
    _pending: Dict[str, SimpleApprovalRequest] = {}
    _lock = threading.Lock()

    def __init__(self, ws_send_event: Callable, run_id: str, db_factory: Callable = None):
        """
        Initialize the approval manager.

        Args:
            ws_send_event: Function to send WebSocket events.
                           Signature: (event_type: str, data: dict) -> None
            run_id: The workflow run/task ID
            db_factory: Optional callable that returns a SQLAlchemy session.
                        When provided, approvals are persisted to the database
                        for resilience across disconnects/restarts.
        """
        self.ws_send_event = ws_send_event
        self.run_id = run_id
        self._db_factory = db_factory

    def __getstate__(self):
        """
        Custom pickle state - exclude ws_send_event and _db_factory which are closures.

        This allows the approval manager to be pickled as part of context
        without failing on the non-picklable ws_send_event function.
        """
        state = self.__dict__.copy()
        # Remove the non-picklable closures
        state['ws_send_event'] = None
        state['_db_factory'] = None
        return state

    def __setstate__(self, state):
        """
        Restore state from pickle.

        Note: ws_send_event will be None after unpickling.
        It must be re-attached if the manager needs to send events.
        """
        self.__dict__.update(state)
        # ws_send_event is None - must be re-attached if needed

    def create_approval_request(
        self,
        run_id: str,
        step_id: str,
        checkpoint_type: str,
        context_snapshot: Dict[str, Any],
        message: str,
        options: Optional[List[str]] = None,
    ) -> SimpleApprovalRequest:
        """
        Create an approval request and notify the UI via WebSocket.

        Args:
            run_id: Workflow run ID
            step_id: Current step identifier
            checkpoint_type: Type of checkpoint
            context_snapshot: Current context for display
            message: Message to show to the user
            options: Available approval options

        Returns:
            SimpleApprovalRequest object
        """
        request = SimpleApprovalRequest(
            id=str(uuid.uuid4()),
            run_id=run_id or self.run_id,
            step_id=step_id or "",
            checkpoint_type=checkpoint_type,
            context_snapshot=context_snapshot,
            message=message,
            options=options or ["approve", "reject", "modify"],
        )

        with self._lock:
            WebSocketApprovalManager._pending[request.id] = request

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

        logger.info("approval_request_created",
                     approval_id=request.id,
                     checkpoint_type=checkpoint_type,
                     run_id=run_id)

        # Send WebSocket event to UI
        try:
            logger.debug("sending_approval_requested_event",
                         approval_id=request.id,
                         step_id=step_id,
                         checkpoint_type=checkpoint_type,
                         message_preview=message[:200],
                         options=request.options)

            # Debug: Print plan from context_snapshot
            if 'plan' in context_snapshot:
                plan_data = context_snapshot['plan']
                plan_info = len(plan_data) if isinstance(plan_data, list) else 'not a list'
                logger.debug("approval_context_plan",
                             plan_steps=plan_info)
                if isinstance(plan_data, list) and len(plan_data) > 0:
                    first_step = plan_data[0]
                    preview = first_step.get('sub_task', str(first_step))[:150] if isinstance(first_step, dict) else str(first_step)[:150]
                    logger.debug("approval_plan_first_step", preview=preview)

            # Sanitize context to make it JSON serializable
            def make_json_serializable(obj):
                """Convert objects to JSON-serializable format"""
                if obj is None or isinstance(obj, (str, int, float, bool)):
                    return obj
                elif isinstance(obj, dict):
                    return {k: make_json_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [make_json_serializable(item) for item in obj]
                elif hasattr(obj, '__dict__'):
                    # For objects with __dict__, convert to dict
                    return make_json_serializable(obj.__dict__)
                elif hasattr(obj, 'to_dict'):
                    # For objects with to_dict method
                    return make_json_serializable(obj.to_dict())
                else:
                    # For everything else, convert to string
                    return str(obj)

            safe_context = make_json_serializable(context_snapshot)
            logger.debug("approval_context_sanitized")

            self.ws_send_event("approval_requested", {
                "approval_id": request.id,
                "step_id": step_id,
                "action": checkpoint_type,  # For frontend compatibility
                "description": message,     # Frontend expects 'description'
                "message": message,         # Also include 'message' for flexibility
                "options": request.options,
                "checkpoint_type": checkpoint_type,
                "context": safe_context,
            })

            logger.info("approval_request_sent_to_ui",
                         approval_id=request.id)
        except Exception as e:
            logger.error("approval_request_send_failed",
                         approval_id=request.id,
                         error=str(e),
                         ws_function=str(self.ws_send_event),
                         exc_info=True)

            # Clean up the pending request
            with self._lock:
                WebSocketApprovalManager._pending.pop(request.id, None)

            # Fail fast instead of hanging silently
            raise RuntimeError(
                f"Cannot send approval request to UI: WebSocket send failed. "
                f"Ensure the UI is connected and WebSocket is active. "
                f"Original error: {type(e).__name__}: {e}"
            ) from e

        return request

    def wait_for_approval(
        self,
        approval_id: str,
        timeout_seconds: int = 3600,
        poll_interval: float = 1.0,
    ) -> SimpleApprovalRequest:
        """
        Block until approval is resolved (synchronous).

        Args:
            approval_id: Approval request ID
            timeout_seconds: Maximum wait time
            poll_interval: Not used (threading.Event handles timing)

        Returns:
            Resolved SimpleApprovalRequest

        Raises:
            ValueError: If approval not found
            TimeoutError: If timeout exceeded
        """
        with self._lock:
            request = WebSocketApprovalManager._pending.get(approval_id)

        if not request:
            raise ValueError(f"Approval {approval_id} not found")

        if request._event.wait(timeout=timeout_seconds):
            return request
        else:
            raise TimeoutError(
                f"Approval timeout after {timeout_seconds}s for {approval_id}"
            )

    async def wait_for_approval_async(
        self,
        approval_id: str,
        timeout_seconds: int = 3600,
    ) -> SimpleApprovalRequest:
        """
        Wait for approval without blocking the event loop (async).

        Polls the threading.Event periodically using asyncio.sleep
        so the event loop stays responsive.

        Args:
            approval_id: Approval request ID
            timeout_seconds: Maximum wait time

        Returns:
            Resolved SimpleApprovalRequest

        Raises:
            ValueError: If approval not found
            TimeoutError: If timeout exceeded
        """
        logger.debug("wait_for_approval_async_called", approval_id=approval_id)

        with self._lock:
            request = WebSocketApprovalManager._pending.get(approval_id)
            pending_count = len(WebSocketApprovalManager._pending)
            pending_ids = list(WebSocketApprovalManager._pending.keys())

        logger.debug("pending_approvals_state",
                      count=pending_count,
                      ids=pending_ids)

        if not request:
            logger.error("approval_not_found_in_pending", approval_id=approval_id)
            raise ValueError(f"Approval {approval_id} not found")

        logger.debug("approval_wait_loop_starting",
                      approval_id=approval_id,
                      status=request.status,
                      event_is_set=request._event.is_set())

        start = time.time()
        poll_count = 0
        while not request._event.is_set():
            poll_count += 1
            elapsed = time.time() - start
            if poll_count % 10 == 0:  # Log every 10 seconds
                logger.debug("approval_still_waiting",
                              elapsed_seconds=round(elapsed, 1),
                              poll_count=poll_count)
            if elapsed > timeout_seconds:
                logger.warning("approval_wait_timeout",
                                approval_id=approval_id,
                                timeout_seconds=timeout_seconds)
                raise TimeoutError(
                    f"Approval timeout after {timeout_seconds}s for {approval_id}"
                )
            await asyncio.sleep(1.0)

        elapsed = time.time() - start
        logger.info("approval_wait_completed",
                      approval_id=approval_id,
                      elapsed_seconds=round(elapsed, 1),
                      resolution=request.resolution)
        return request

    @classmethod
    def resolve(
        cls,
        approval_id: str,
        resolution: str,
        user_feedback: Optional[str] = None,
        modifications: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Resolve a pending approval request.

        Called from the WebSocket handler when the user submits a response.

        Args:
            approval_id: Approval request ID
            resolution: Resolution string (approved, rejected, modified, etc.)
            user_feedback: Optional user feedback text
            modifications: Optional modifications dict

        Returns:
            True if resolved, False if approval not found
        """
        logger.info("approval_resolve_called",
                      approval_id=approval_id,
                      resolution=resolution)

        with cls._lock:
            request = cls._pending.get(approval_id)
            pending_count = len(cls._pending)

        logger.debug("approval_resolve_pending_count", count=pending_count)

        if not request:
            logger.error("approval_resolve_not_found", approval_id=approval_id)
            return False

        logger.debug("approval_resolve_setting_resolution", approval_id=approval_id)

        request.status = resolution
        request.resolution = resolution
        request.user_feedback = user_feedback
        request.modifications = modifications or {}

        # Signal the waiting thread
        request._event.set()
        logger.debug("approval_resolve_event_set",
                      approval_id=approval_id,
                      event_is_set=request._event.is_set())

        logger.info("approval_resolved",
                      approval_id=approval_id,
                      resolution=resolution)

        # Clean up immediately since the waiter already read the result
        # (the waiter exits the loop once event is set, before we get here)
        with cls._lock:
            cls._pending.pop(approval_id, None)

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

        return True

    @classmethod
    def has_pending(cls, approval_id: str) -> bool:
        """Check if an approval ID is pending in memory."""
        with cls._lock:
            return approval_id in cls._pending

    @classmethod
    def get_all_pending(cls) -> List[SimpleApprovalRequest]:
        """Get all pending approval requests."""
        with cls._lock:
            return [r for r in cls._pending.values() if r.status == "pending"]

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
