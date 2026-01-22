"""Workflow controller for pause/resume and execution control."""
from typing import Optional
from sqlalchemy.orm import Session

from cmbagent.database.state_machine import StateMachine, StateMachineError
from cmbagent.database.states import WorkflowState, StepState
from cmbagent.database.models import WorkflowRun, WorkflowStep


class WorkflowController:
    """Controls workflow execution with pause/resume capabilities."""

    def __init__(self, db_session: Session, session_id: str):
        """
        Initialize workflow controller.

        Args:
            db_session: SQLAlchemy session
            session_id: Session ID for isolating operations
        """
        self.db = db_session
        self.session_id = session_id
        self.workflow_sm = StateMachine(db_session, "workflow_run")
        self.step_sm = StateMachine(db_session, "workflow_step")

    def pause_workflow(
        self,
        run_id: str,
        reason: str = "User requested pause",
        transitioned_by: str = "user"
    ) -> None:
        """
        Pause running workflow.

        Args:
            run_id: UUID of workflow run
            reason: Reason for pausing
            transitioned_by: Who triggered the pause

        Raises:
            ValueError: If run not found
            StateMachineError: If workflow cannot be paused
        """
        run = self.db.query(WorkflowRun).filter(
            WorkflowRun.id == run_id,
            WorkflowRun.session_id == self.session_id
        ).first()

        if not run:
            raise ValueError(f"Run {run_id} not found in session {self.session_id}")

        # Can only pause if currently executing
        if run.status != WorkflowState.EXECUTING.value:
            raise StateMachineError(
                f"Cannot pause workflow in state: {run.status}. "
                f"Must be in '{WorkflowState.EXECUTING.value}' state."
            )

        # Transition workflow to PAUSED
        self.workflow_sm.transition_to(
            run_id,
            WorkflowState.PAUSED.value,
            reason=reason,
            transitioned_by=transitioned_by
        )

        # Pause currently running steps
        running_steps = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id,
            WorkflowStep.status == StepState.RUNNING.value
        ).all()

        for step in running_steps:
            self.step_sm.transition_to(
                step.id,
                StepState.PAUSED.value,
                reason="Workflow paused",
                transitioned_by=transitioned_by
            )

    def resume_workflow(
        self,
        run_id: str,
        reason: str = "User requested resume",
        transitioned_by: str = "user"
    ) -> None:
        """
        Resume paused workflow.

        Args:
            run_id: UUID of workflow run
            reason: Reason for resuming
            transitioned_by: Who triggered the resume

        Raises:
            ValueError: If run not found
            StateMachineError: If workflow cannot be resumed
        """
        run = self.db.query(WorkflowRun).filter(
            WorkflowRun.id == run_id,
            WorkflowRun.session_id == self.session_id
        ).first()

        if not run:
            raise ValueError(f"Run {run_id} not found in session {self.session_id}")

        # Can only resume if currently paused
        if run.status != WorkflowState.PAUSED.value:
            raise StateMachineError(
                f"Cannot resume workflow in state: {run.status}. "
                f"Must be in '{WorkflowState.PAUSED.value}' state."
            )

        # Transition workflow back to EXECUTING
        self.workflow_sm.transition_to(
            run_id,
            WorkflowState.EXECUTING.value,
            reason=reason,
            transitioned_by=transitioned_by
        )

        # Resume paused steps
        paused_steps = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id,
            WorkflowStep.status == StepState.PAUSED.value
        ).all()

        for step in paused_steps:
            self.step_sm.transition_to(
                step.id,
                StepState.RUNNING.value,
                reason="Workflow resumed",
                transitioned_by=transitioned_by
            )

    def cancel_workflow(
        self,
        run_id: str,
        reason: str = "User cancelled workflow",
        transitioned_by: str = "user"
    ) -> None:
        """
        Cancel a workflow.

        Args:
            run_id: UUID of workflow run
            reason: Reason for cancellation
            transitioned_by: Who triggered the cancellation

        Raises:
            ValueError: If run not found
            StateMachineError: If workflow cannot be cancelled
        """
        run = self.db.query(WorkflowRun).filter(
            WorkflowRun.id == run_id,
            WorkflowRun.session_id == self.session_id
        ).first()

        if not run:
            raise ValueError(f"Run {run_id} not found in session {self.session_id}")

        # Transition workflow to CANCELLED
        self.workflow_sm.transition_to(
            run_id,
            WorkflowState.CANCELLED.value,
            reason=reason,
            transitioned_by=transitioned_by
        )

        # Cancel all non-terminal steps
        active_steps = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id,
            WorkflowStep.status.in_([
                StepState.PENDING.value,
                StepState.RUNNING.value,
                StepState.PAUSED.value,
                StepState.WAITING_APPROVAL.value
            ])
        ).all()

        for step in active_steps:
            self.step_sm.transition_to(
                step.id,
                StepState.CANCELLED.value,
                reason="Workflow cancelled",
                transitioned_by=transitioned_by
            )

    def get_workflow_status(self, run_id: str) -> Optional[dict]:
        """
        Get current workflow status with step details.

        Args:
            run_id: UUID of workflow run

        Returns:
            Dictionary with workflow status or None if not found
        """
        run = self.db.query(WorkflowRun).filter(
            WorkflowRun.id == run_id,
            WorkflowRun.session_id == self.session_id
        ).first()

        if not run:
            return None

        steps = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id
        ).order_by(WorkflowStep.step_number).all()

        return {
            "run_id": run.id,
            "status": run.status,
            "mode": run.mode,
            "agent": run.agent,
            "model": run.model,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "task_description": run.task_description,
            "steps": [
                {
                    "step_id": step.id,
                    "step_number": step.step_number,
                    "goal": step.goal,
                    "summary": step.summary,
                    "status": step.status,
                    "progress_percentage": step.progress_percentage,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "error_message": step.error_message
                }
                for step in steps
            ],
            "allowed_transitions": self.workflow_sm.get_allowed_transitions(run_id)
        }

    def can_pause(self, run_id: str) -> bool:
        """Check if workflow can be paused."""
        return self.workflow_sm.can_transition_to(run_id, WorkflowState.PAUSED.value)

    def can_resume(self, run_id: str) -> bool:
        """Check if workflow can be resumed."""
        return self.workflow_sm.can_transition_to(run_id, WorkflowState.EXECUTING.value)

    def can_cancel(self, run_id: str) -> bool:
        """Check if workflow can be cancelled."""
        return self.workflow_sm.can_transition_to(run_id, WorkflowState.CANCELLED.value)
