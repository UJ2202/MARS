"""
Approval request manager for HITL (Human-in-the-Loop) workflow control.

This module manages approval requests, responses, and the workflow state
transitions related to approval gates.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import time
import logging

from sqlalchemy.orm import Session

from cmbagent.database.models import ApprovalRequest, WorkflowRun, WorkflowStep
from cmbagent.database.state_machine import StateMachine
from cmbagent.database.approval_types import ApprovalResolution, CheckpointType

logger = logging.getLogger(__name__)


class WorkflowCancelledException(Exception):
    """Raised when workflow is cancelled by user"""
    pass


class ApprovalTimeoutError(Exception):
    """Raised when approval request times out"""
    pass


class ApprovalManager:
    """
    Manages approval requests and responses for HITL workflow control.

    This manager:
    - Creates approval requests at checkpoints
    - Pauses workflow execution (via state machine)
    - Waits for user responses
    - Resumes workflow after approval
    - Tracks approval history in database
    - Emits WebSocket events for real-time UI updates
    """

    def __init__(self, db_session: Session, session_id: str):
        """
        Initialize approval manager.

        Args:
            db_session: SQLAlchemy database session
            session_id: Current workflow session ID
        """
        self.db = db_session
        self.session_id = session_id
        self.workflow_sm = StateMachine(db_session, "workflow_run")
        self.step_sm = StateMachine(db_session, "workflow_step")

    def create_approval_request(
        self,
        run_id: str,
        step_id: Optional[str],
        checkpoint_type: str,
        context_snapshot: Dict[str, Any],
        message: str,
        options: Optional[List[str]] = None
    ) -> ApprovalRequest:
        """
        Create a new approval request and pause workflow execution.

        This will:
        1. Create approval request in database
        2. Transition workflow to WAITING_APPROVAL state
        3. Optionally transition step to WAITING_APPROVAL state
        4. Emit WebSocket event for UI

        Args:
            run_id: Workflow run ID
            step_id: Current step ID (optional, for step-specific approvals)
            checkpoint_type: Type of checkpoint (planning, step, error, manual)
            context_snapshot: Current workflow context
            message: Message to display to user
            options: Available approval options (default: approve, reject, modify)

        Returns:
            Created ApprovalRequest object

        Raises:
            ValueError: If run_id not found or already has pending approval
        """
        # Validate run exists
        run = self.db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if not run:
            raise ValueError(f"Workflow run {run_id} not found")

        # Check for existing pending approvals
        existing_pending = self.db.query(ApprovalRequest).filter(
            ApprovalRequest.run_id == run_id,
            ApprovalRequest.status == "pending"
        ).count()

        if existing_pending > 0:
            logger.warning(f"Run {run_id} already has {existing_pending} pending approval(s)")

        # Create approval request
        # Store metadata in context_snapshot since there's no meta field
        full_context = {
            "checkpoint_type": checkpoint_type,
            "message": message,
            "options": options or ["approve", "reject", "modify"],
            "context": context_snapshot
        }

        # For approvals without a specific step (e.g., after planning), create a pseudo-step
        effective_step_id = step_id
        if not effective_step_id:
            # Create a workflow step for the approval
            from cmbagent.database.models import WorkflowStep
            pseudo_step = WorkflowStep(
                id=str(uuid.uuid4()),
                run_id=run_id,
                session_id=self.session_id,
                step_number=0,  # 0 indicates planning phase
                agent="planner",
                status="pending"
            )
            self.db.add(pseudo_step)
            self.db.flush()  # Get the ID without committing
            effective_step_id = pseudo_step.id

        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            run_id=run_id,
            step_id=effective_step_id,
            status="pending",
            requested_at=datetime.utcnow(),
            context_snapshot=full_context
        )

        self.db.add(approval)
        self.db.commit()

        logger.info(f"Created approval request {approval.id} for run {run_id} (type: {checkpoint_type})")

        # Transition workflow to WAITING_APPROVAL
        try:
            self.workflow_sm.transition_to(
                run_id,
                "waiting_approval",
                reason=f"Approval requested: {checkpoint_type}",
                transitioned_by="system"
            )
        except Exception as e:
            logger.warning(f"Could not transition workflow to waiting_approval: {e}")

        # If specific step, transition step as well
        if step_id and step_id != effective_step_id:  # Don't transition pseudo-step
            try:
                self.step_sm.transition_to(
                    step_id,
                    "waiting_approval",
                    reason="Awaiting user approval",
                    transitioned_by="system"
                )
            except Exception as e:
                logger.warning(f"Could not transition step to waiting_approval: {e}")

        # Emit WebSocket event
        self._emit_approval_event(approval)

        return approval

    def resolve_approval(
        self,
        approval_id: str,
        resolution: str,
        user_feedback: Optional[str] = None
    ) -> ApprovalRequest:
        """
        Resolve an approval request and resume workflow.

        This will:
        1. Update approval status in database
        2. Transition workflow back to EXECUTING (if approved)
        3. Transition workflow to CANCELLED (if rejected)
        4. Emit WebSocket event

        Args:
            approval_id: Approval request ID
            resolution: Resolution (approved, rejected, modified, retry, skip, abort)
            user_feedback: Optional feedback text from user

        Returns:
            Updated ApprovalRequest object

        Raises:
            ValueError: If approval not found or already resolved
        """
        approval = self.db.query(ApprovalRequest).filter(
            ApprovalRequest.id == approval_id
        ).first()

        if not approval:
            raise ValueError(f"Approval request {approval_id} not found")

        if approval.status != "pending":
            raise ValueError(f"Approval already resolved: {approval.status}")

        # Update approval
        approval.status = resolution
        approval.resolved_at = datetime.utcnow()
        approval.user_feedback = user_feedback
        approval.resolution = resolution

        self.db.commit()

        logger.info(f"Resolved approval {approval_id} as {resolution}")

        # Handle workflow state transitions based on resolution
        if resolution in ["approved", "modified", "retry", "skip"]:
            # Resume execution
            try:
                self.workflow_sm.transition_to(
                    approval.run_id,
                    "executing",
                    reason=f"Approval {resolution}: {user_feedback or 'No feedback'}",
                    transitioned_by="user"
                )
            except Exception as e:
                logger.warning(f"Could not transition workflow to executing: {e}")

            # Resume step if applicable
            if approval.step_id:
                try:
                    if resolution == "skip":
                        self.step_sm.transition_to(
                            approval.step_id,
                            "skipped",
                            reason=f"Skipped by user: {user_feedback or 'No reason'}",
                            transitioned_by="user"
                        )
                    else:
                        self.step_sm.transition_to(
                            approval.step_id,
                            "running",
                            reason="Approved, resuming execution",
                            transitioned_by="user"
                        )
                except Exception as e:
                    logger.warning(f"Could not transition step state: {e}")

        elif resolution in ["rejected", "abort"]:
            # Cancel workflow
            try:
                self.workflow_sm.transition_to(
                    approval.run_id,
                    "cancelled",
                    reason=f"Rejected by user: {user_feedback or 'No reason'}",
                    transitioned_by="user"
                )
            except Exception as e:
                logger.warning(f"Could not transition workflow to cancelled: {e}")

        # Emit WebSocket event
        self._emit_approval_resolved_event(approval)

        return approval

    def get_pending_approvals(self, run_id: str) -> List[ApprovalRequest]:
        """
        Get all pending approval requests for a workflow run.

        Args:
            run_id: Workflow run ID

        Returns:
            List of pending ApprovalRequest objects
        """
        return self.db.query(ApprovalRequest).filter(
            ApprovalRequest.run_id == run_id,
            ApprovalRequest.status == "pending"
        ).all()

    def get_approval_history(self, run_id: str) -> List[ApprovalRequest]:
        """
        Get complete approval history for a workflow run.

        Args:
            run_id: Workflow run ID

        Returns:
            List of all ApprovalRequest objects (pending and resolved)
        """
        return self.db.query(ApprovalRequest).filter(
            ApprovalRequest.run_id == run_id
        ).order_by(ApprovalRequest.requested_at).all()

    def wait_for_approval(
        self,
        approval_id: str,
        timeout_seconds: Optional[int] = None,
        poll_interval: float = 1.0
    ) -> ApprovalRequest:
        """
        Block execution until approval is resolved.

        This is a polling-based wait that checks the database periodically.

        Args:
            approval_id: Approval request ID
            timeout_seconds: Maximum time to wait (None = infinite)
            poll_interval: How often to check database (seconds)

        Returns:
            Resolved ApprovalRequest object

        Raises:
            ApprovalTimeoutError: If timeout exceeded
            ValueError: If approval not found
        """
        start_time = time.time()

        logger.info(f"Waiting for approval {approval_id} (timeout: {timeout_seconds}s)")

        while True:
            # Refresh approval from database
            approval = self.db.query(ApprovalRequest).filter(
                ApprovalRequest.id == approval_id
            ).first()

            if not approval:
                raise ValueError(f"Approval request {approval_id} not found")

            # Check if resolved
            if approval.status != "pending":
                logger.info(f"Approval {approval_id} resolved as {approval.status}")
                return approval

            # Check timeout
            if timeout_seconds and (time.time() - start_time) > timeout_seconds:
                raise ApprovalTimeoutError(
                    f"Approval timeout after {timeout_seconds}s for request {approval_id}"
                )

            # Wait before next poll
            time.sleep(poll_interval)

    def cancel_pending_approvals(self, run_id: str, reason: str = "Workflow cancelled"):
        """
        Cancel all pending approvals for a workflow run.

        Args:
            run_id: Workflow run ID
            reason: Reason for cancellation
        """
        pending = self.get_pending_approvals(run_id)

        for approval in pending:
            approval.status = "cancelled"
            approval.resolved_at = datetime.utcnow()
            approval.resolution = "cancelled"
            approval.user_feedback = reason

        self.db.commit()

        logger.info(f"Cancelled {len(pending)} pending approval(s) for run {run_id}")

    def _emit_approval_event(self, approval: ApprovalRequest):
        """
        Emit approval_requested event via WebSocket.

        Args:
            approval: ApprovalRequest object
        """
        try:
            from backend.websocket_events import WebSocketEvent, WebSocketEventType
            from backend.event_queue import event_queue

            # Extract metadata from context_snapshot
            context = approval.context_snapshot or {}

            event = WebSocketEvent(
                event_type=WebSocketEventType.APPROVAL_REQUESTED,
                timestamp=datetime.utcnow(),
                run_id=str(approval.run_id),
                data={
                    "approval_id": str(approval.id),
                    "step_id": str(approval.step_id) if approval.step_id != approval.run_id else None,
                    "message": context.get("message"),
                    "options": context.get("options"),
                    "checkpoint_type": context.get("checkpoint_type"),
                    "context": context.get("context", {})
                }
            )

            event_queue.push(str(approval.run_id), event)
            logger.debug(f"Emitted approval_requested event for {approval.id}")

        except Exception as e:
            logger.warning(f"Could not emit approval_requested event: {e}")

    def _emit_approval_resolved_event(self, approval: ApprovalRequest):
        """
        Emit approval_received event via WebSocket.

        Args:
            approval: Resolved ApprovalRequest object
        """
        try:
            from backend.websocket_events import WebSocketEvent, WebSocketEventType
            from backend.event_queue import event_queue

            event = WebSocketEvent(
                event_type=WebSocketEventType.APPROVAL_RECEIVED,
                timestamp=datetime.utcnow(),
                run_id=str(approval.run_id),
                data={
                    "approval_id": str(approval.id),
                    "resolution": approval.resolution,
                    "feedback": approval.user_feedback,
                    "resolved_at": approval.resolved_at.isoformat() if approval.resolved_at else None
                }
            )

            event_queue.push(str(approval.run_id), event)
            logger.debug(f"Emitted approval_received event for {approval.id}")

        except Exception as e:
            logger.warning(f"Could not emit approval_received event: {e}")
