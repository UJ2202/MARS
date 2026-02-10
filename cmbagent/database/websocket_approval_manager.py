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

    def __init__(self, ws_send_event: Callable, run_id: str):
        """
        Initialize the approval manager.

        Args:
            ws_send_event: Function to send WebSocket events.
                           Signature: (event_type: str, data: dict) -> None
            run_id: The workflow run/task ID
        """
        self.ws_send_event = ws_send_event
        self.run_id = run_id

    def __getstate__(self):
        """
        Custom pickle state - exclude ws_send_event which is a closure.
        
        This allows the approval manager to be pickled as part of context
        without failing on the non-picklable ws_send_event function.
        """
        state = self.__dict__.copy()
        # Remove the non-picklable closure
        state['ws_send_event'] = None
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

        logger.info(
            f"Created approval request {request.id} "
            f"(type: {checkpoint_type}, run: {run_id})"
        )

        # Send WebSocket event to UI
        try:
            print(f"[WebSocketApprovalManager] Sending approval_requested event:")
            print(f"  - approval_id: {request.id}")
            print(f"  - step_id: {step_id}")
            print(f"  - checkpoint_type: {checkpoint_type}")
            print(f"  - message preview: {message[:200]}...")
            print(f"  - options: {request.options}")

            # Debug: Print plan from context_snapshot
            if 'plan' in context_snapshot:
                plan_data = context_snapshot['plan']
                print(f"  - context_snapshot plan: {len(plan_data) if isinstance(plan_data, list) else 'not a list'} steps")
                if isinstance(plan_data, list) and len(plan_data) > 0:
                    first_step = plan_data[0]
                    print(f"  - first step preview: {first_step.get('sub_task', str(first_step))[:150] if isinstance(first_step, dict) else str(first_step)[:150]}")

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
            print(f"[WebSocketApprovalManager] Context sanitized for JSON")

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

            print(f"[WebSocketApprovalManager] ✓ Approval request {request.id} sent to UI via WebSocket")
            logger.info(f"✓ Approval request {request.id} sent to UI via WebSocket")
        except Exception as e:
            print(f"[WebSocketApprovalManager] ✗ Failed to send approval_requested event: {e}")
            logger.error(f"✗ Failed to send approval_requested event: {e}")
            logger.error(f"   WebSocket function: {self.ws_send_event}")
            logger.error(f"   This will cause workflow to hang!")
            import traceback
            traceback.print_exc()

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
        print(f"[WebSocketApprovalManager] wait_for_approval_async called for {approval_id}")

        with self._lock:
            request = WebSocketApprovalManager._pending.get(approval_id)
            pending_count = len(WebSocketApprovalManager._pending)
            pending_ids = list(WebSocketApprovalManager._pending.keys())

        print(f"[WebSocketApprovalManager] Pending approvals count: {pending_count}")
        print(f"[WebSocketApprovalManager] Pending IDs: {pending_ids}")

        if not request:
            print(f"[WebSocketApprovalManager] ERROR: Approval {approval_id} not found in pending!")
            raise ValueError(f"Approval {approval_id} not found")

        print(f"[WebSocketApprovalManager] Found request, starting wait loop...")
        print(f"[WebSocketApprovalManager] Request status: {request.status}, event.is_set(): {request._event.is_set()}")

        start = time.time()
        poll_count = 0
        while not request._event.is_set():
            poll_count += 1
            elapsed = time.time() - start
            if poll_count % 10 == 0:  # Log every 10 seconds
                print(f"[WebSocketApprovalManager] Still waiting... elapsed={elapsed:.1f}s, polls={poll_count}")
            if elapsed > timeout_seconds:
                print(f"[WebSocketApprovalManager] TIMEOUT after {timeout_seconds}s")
                raise TimeoutError(
                    f"Approval timeout after {timeout_seconds}s for {approval_id}"
                )
            await asyncio.sleep(1.0)

        elapsed = time.time() - start
        print(f"[WebSocketApprovalManager] Wait completed! elapsed={elapsed:.1f}s, resolution={request.resolution}")
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
        print(f"[WebSocketApprovalManager] resolve() called: id={approval_id}, resolution={resolution}")

        with cls._lock:
            request = cls._pending.get(approval_id)
            pending_count = len(cls._pending)

        print(f"[WebSocketApprovalManager] resolve() pending count: {pending_count}")

        if not request:
            print(f"[WebSocketApprovalManager] resolve() ERROR: approval {approval_id} not found!")
            return False

        print(f"[WebSocketApprovalManager] resolve() found request, setting resolution...")

        request.status = resolution
        request.resolution = resolution
        request.user_feedback = user_feedback
        request.modifications = modifications or {}

        # Signal the waiting thread
        request._event.set()
        print(f"[WebSocketApprovalManager] resolve() event.set() called, event.is_set()={request._event.is_set()}")

        logger.info(f"Resolved approval {approval_id} as {resolution}")

        # Clean up immediately since the waiter already read the result
        # (the waiter exits the loop once event is set, before we get here)
        with cls._lock:
            cls._pending.pop(approval_id, None)

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
