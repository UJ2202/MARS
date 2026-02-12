"""
HITL (Human-in-the-Loop) checkpoint phase implementation for CMBAgent.

This module provides the HITLCheckpointPhase class that pauses
workflow execution for human approval.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import time
import asyncio
import logging

logger = logging.getLogger(__name__)

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus


class CheckpointType(Enum):
    """Types of HITL checkpoints."""
    AFTER_PLANNING = "after_planning"
    BEFORE_STEP = "before_step"
    AFTER_STEP = "after_step"
    BEFORE_EXECUTION = "before_execution"
    AFTER_EXECUTION = "after_execution"
    CUSTOM = "custom"


@dataclass
class HITLCheckpointConfig(PhaseConfig):
    """
    Configuration for HITL checkpoint phase.

    Attributes:
        checkpoint_type: Type of checkpoint
        require_approval: Whether approval is required
        timeout_seconds: Maximum wait time for approval
        default_on_timeout: Action on timeout ("approve" or "reject")
        show_plan: Whether to show plan in approval message
        show_context: Whether to show full context
        custom_message: Custom message to show user
        options: Available choices for user
    """
    phase_type: str = "hitl_checkpoint"

    checkpoint_type: str = "after_planning"  # String to allow serialization

    # Approval options
    require_approval: bool = True
    timeout_seconds: int = 3600  # 1 hour
    default_on_timeout: str = "reject"  # "approve" or "reject"

    # What to show user
    show_plan: bool = True
    show_context: bool = False
    custom_message: str = ""

    # Options user can choose
    options: List[str] = field(default_factory=lambda: ["approve", "reject", "modify"])


class HITLCheckpointPhase(Phase):
    """
    Human-in-the-Loop checkpoint phase.

    Pauses workflow execution and waits for human approval.
    Can be placed anywhere in workflow to create approval gates.

    Input Context:
        - Any context from previous phase

    Output Context:
        - approval_status: "approved" | "rejected" | "modified"
        - user_feedback: Optional feedback from user
        - modifications: Any modifications made by user
    """

    config_class = HITLCheckpointConfig

    def __init__(self, config: HITLCheckpointConfig = None):
        if config is None:
            config = HITLCheckpointConfig()
        super().__init__(config)
        self.config: HITLCheckpointConfig = config

    @property
    def phase_type(self) -> str:
        return "hitl_checkpoint"

    @property
    def display_name(self) -> str:
        type_names = {
            "after_planning": "Review Plan",
            "before_step": "Approve Step",
            "after_step": "Review Step Result",
            "after_execution": "Review Results",
            "custom": "Checkpoint",
        }
        return type_names.get(self.config.checkpoint_type, "Checkpoint")

    def get_required_agents(self) -> List[str]:
        return []  # No agents needed - this is human interaction

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute HITL checkpoint.

        Waits for human approval before continuing workflow.

        Args:
            context: Input context

        Returns:
            PhaseResult with approval status
        """
        self._status = PhaseStatus.WAITING_APPROVAL
        context.started_at = time.time()

        if not self.config.require_approval:
            # Skip if approval not required
            context.output_data = {
                'approval_status': 'auto_approved',
                'skipped': True,
            }
            self._status = PhaseStatus.COMPLETED
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
            )

        # Build message for user
        message = self._build_approval_message(context)

        # Get approval manager from context (injected by workflow executor)
        approval_manager = context.shared_state.get('_approval_manager')

        if not approval_manager:
            # No approval manager - auto-approve (for non-HITL runs)
            logger.info("=" * 60)
            logger.info("HITL CHECKPOINT (Auto-approved - no approval manager)")
            logger.info("=" * 60)
            logger.info("%s", message)
            logger.info("=" * 60)

            context.output_data = {
                'approval_status': 'auto_approved',
                'no_hitl_manager': True,
            }
            self._status = PhaseStatus.COMPLETED
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
            )

        try:
            # Create approval request
            approval_request = approval_manager.create_approval_request(
                run_id=context.run_id,
                step_id=context.phase_id,
                checkpoint_type=self.config.checkpoint_type,
                context_snapshot=self._build_context_snapshot(context),
                message=message,
                options=self.config.options,
            )

            logger.info("=" * 60)
            logger.info("HITL CHECKPOINT: %s", self.display_name)
            logger.info("=" * 60)
            logger.info("%s", message)
            logger.info("Waiting for approval...")
            logger.info("=" * 60)

            # Wait for approval
            resolved = await approval_manager.wait_for_approval_async(
                str(approval_request.id),
                timeout_seconds=self.config.timeout_seconds,
            )

            # Handle result (accept both "rejected"/"reject" and "modified"/"modify")
            if resolved.resolution in ["rejected", "reject"]:
                context.output_data = {
                    'approval_status': 'rejected',
                    'user_feedback': resolved.user_feedback,
                    'shared': {
                        'hitl_feedback': resolved.user_feedback,
                        'hitl_rejected': True,
                    }
                }
                self._status = PhaseStatus.FAILED
                return PhaseResult(
                    status=PhaseStatus.FAILED,
                    context=context,
                    error="Rejected by user",
                )

            elif resolved.resolution in ["modified", "modify"]:
                context.output_data = {
                    'approval_status': 'modified',
                    'user_feedback': resolved.user_feedback,
                    'modifications': resolved.modifications,
                    'shared': {
                        'user_modifications': resolved.modifications,
                        'hitl_feedback': resolved.user_feedback,
                        'plan_modified_by_human': True,
                    }
                }

            else:  # approved or approve
                context.output_data = {
                    'approval_status': 'approved',
                    'user_feedback': resolved.user_feedback,
                    'shared': {
                        'hitl_feedback': resolved.user_feedback,
                        'hitl_approved': True,
                    }
                }

            context.completed_at = time.time()
            self._status = PhaseStatus.COMPLETED

            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
            )

        except asyncio.TimeoutError:
            # Handle timeout
            if self.config.default_on_timeout == "approve":
                logger.info("Approval timeout - auto-approving")
                context.output_data = {
                    'approval_status': 'timeout_auto_approved',
                }
                self._status = PhaseStatus.COMPLETED
                return PhaseResult(
                    status=PhaseStatus.COMPLETED,
                    context=context,
                )
            else:
                logger.warning("Approval timeout - rejecting")
                self._status = PhaseStatus.FAILED
                return PhaseResult(
                    status=PhaseStatus.FAILED,
                    context=context,
                    error="Approval timeout - defaulted to reject",
                )

        except Exception as e:
            # Handle other errors
            logger.error("Approval error: %s", e)
            if self.config.default_on_timeout == "approve":
                context.output_data = {
                    'approval_status': 'error_auto_approved',
                    'error': str(e),
                }
                self._status = PhaseStatus.COMPLETED
                return PhaseResult(
                    status=PhaseStatus.COMPLETED,
                    context=context,
                )
            else:
                self._status = PhaseStatus.FAILED
                return PhaseResult(
                    status=PhaseStatus.FAILED,
                    context=context,
                    error=f"Approval error: {e}",
                )

    def _build_approval_message(self, context: PhaseContext) -> str:
        """Build human-readable message for approval UI."""
        parts = []

        if self.config.custom_message:
            parts.append(self.config.custom_message)

        if self.config.checkpoint_type == "after_planning":
            parts.append("Planning phase complete. Please review the plan before execution.")
            if self.config.show_plan:
                plan = context.input_data.get('final_plan', 'Plan not available')
                if isinstance(plan, list):
                    plan_text = "\n".join([
                        f"  Step {i+1}: {step.get('sub_task', 'Unknown')}"
                        for i, step in enumerate(plan)
                    ])
                else:
                    plan_text = str(plan)
                parts.append(f"\n**Plan:**\n{plan_text}")

        elif self.config.checkpoint_type == "after_step":
            step = context.shared_state.get('current_step', '?')
            parts.append(f"Step {step} complete. Review results?")

        elif self.config.checkpoint_type == "before_step":
            step = context.shared_state.get('current_step', '?')
            parts.append(f"About to execute step {step}. Proceed?")

        elif self.config.checkpoint_type == "after_execution":
            parts.append("Execution complete. Review final results?")

        return "\n".join(parts) if parts else "Checkpoint reached. Continue?"

    def _build_context_snapshot(self, context: PhaseContext) -> Dict[str, Any]:
        """Build context snapshot for approval record."""
        snapshot = {
            'task': context.task,
            'phase_id': context.phase_id,
            'checkpoint_type': self.config.checkpoint_type,
        }

        if self.config.show_plan:
            snapshot['plan'] = context.input_data.get('final_plan')

        if self.config.show_context:
            snapshot['context'] = context.input_data

        return snapshot

    def can_skip(self, context: PhaseContext) -> bool:
        """HITL can be skipped if not required."""
        return not self.config.require_approval
