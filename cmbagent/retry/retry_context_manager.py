"""
Retry context manager.

Manages creation and updates of retry context, including loading
previous attempts, analyzing errors, and formatting retry prompts.
"""

import logging
import re
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from cmbagent.retry.retry_context import RetryContext, RetryAttempt
from cmbagent.retry.error_analyzer import ErrorAnalyzer
from cmbagent.database.models import WorkflowStep


class RetryContextManager:
    """Manages retry context for workflow steps"""

    def __init__(self, db_session: Session, session_id: str, emit_event_callback=None):
        """
        Initialize retry context manager.

        Args:
            db_session: Database session
            session_id: Current session ID
            emit_event_callback: Optional callback for emitting WebSocket events.
                Signature: (event_type: str, run_id: str, data: dict) -> None
        """
        self.db = db_session
        self.session_id = session_id
        self.error_analyzer = ErrorAnalyzer()
        self._emit_event_callback = emit_event_callback

    def create_retry_context(
        self,
        step: WorkflowStep,
        attempt_number: int,
        max_attempts: int,
        user_feedback: Optional[str] = None
    ) -> RetryContext:
        """
        Create retry context for step.

        Args:
            step: WorkflowStep being retried
            attempt_number: Current attempt number
            max_attempts: Maximum retry attempts
            user_feedback: Optional user guidance

        Returns:
            RetryContext with all retry information
        """
        # Load previous attempts
        previous_attempts = self._load_previous_attempts(step)

        # Analyze latest error
        latest_error = step.error_message or "Unknown error"
        error_analysis = self.error_analyzer.analyze_error(latest_error)

        # Get user suggestions from feedback
        user_suggestions = []
        if user_feedback:
            user_suggestions = self._parse_user_suggestions(user_feedback)

        # Get similar resolved errors
        similar_errors = self.error_analyzer.get_similar_resolved_errors(
            self.db,
            error_analysis["category"]
        )

        # Estimate success probability
        success_prob = self.error_analyzer.estimate_success_probability(
            attempt_number=attempt_number,
            error_category=error_analysis["category"],
            has_user_feedback=bool(user_feedback)
        )

        # Determine retry strategy
        if user_feedback:
            strategy = "user_guided"
            backoff_seconds = 0  # Immediate retry with guidance
        elif attempt_number > 2:
            strategy = "exponential_backoff"
            backoff_seconds = min(2 ** attempt_number, 60)
        else:
            strategy = "immediate"
            backoff_seconds = 0

        # Get task from step inputs
        original_task = step.inputs.get("task", "") if step.inputs else ""

        retry_context = RetryContext(
            current_attempt=attempt_number,
            max_attempts=max_attempts,
            original_task=original_task,
            modified_task=None,
            previous_attempts=previous_attempts,
            error_pattern=error_analysis.get("pattern"),
            error_category=error_analysis["category"],
            common_error=error_analysis["common_error"],
            user_feedback=user_feedback,
            user_suggestions=user_suggestions,
            suggested_fixes=error_analysis["suggestions"],
            similar_errors_resolved=similar_errors,
            strategy=strategy,
            backoff_seconds=backoff_seconds,
            success_probability=success_prob
        )

        # Emit retry started event to WebSocket
        self._emit_retry_started_event(step, retry_context, user_feedback)

        # Emit backoff event if backoff needed
        if backoff_seconds > 0:
            self._emit_retry_backoff_event(step, attempt_number, backoff_seconds, strategy)

        return retry_context

    def _emit_retry_started_event(self, step, retry_context, user_feedback):
        """Emit retry started event via callback"""
        if not self._emit_event_callback:
            return
        try:
            self._emit_event_callback(
                "step_retry_started",
                str(step.run_id) if step.run_id else None,
                {
                    "step_id": str(step.id),
                    "step_number": step.step_number,
                    "attempt_number": retry_context.current_attempt,
                    "max_attempts": retry_context.max_attempts,
                    "error_category": retry_context.error_category,
                    "error_pattern": retry_context.error_pattern,
                    "success_probability": retry_context.success_probability,
                    "strategy": retry_context.strategy,
                    "suggestions": retry_context.suggested_fixes[:5],
                    "has_user_feedback": bool(user_feedback)
                }
            )
        except Exception as e:
            # Don't fail retry if event emission fails
            logger.warning("retry_started_event_emission_failed error=%s", e)

    def _emit_retry_backoff_event(self, step, attempt_number, backoff_seconds, strategy):
        """Emit retry backoff event via callback"""
        if not self._emit_event_callback:
            return
        try:
            self._emit_event_callback(
                "step_retry_backoff",
                str(step.run_id) if step.run_id else None,
                {
                    "step_id": str(step.id),
                    "step_number": step.step_number,
                    "attempt_number": attempt_number,
                    "backoff_seconds": backoff_seconds,
                    "retry_strategy": strategy
                }
            )
        except Exception as e:
            # Don't fail retry if event emission fails
            logger.warning("retry_backoff_event_emission_failed error=%s", e)

    def _load_previous_attempts(self, step: WorkflowStep) -> List[RetryAttempt]:
        """
        Load previous retry attempts from step metadata.

        Args:
            step: WorkflowStep

        Returns:
            List of RetryAttempt objects
        """
        attempts_data = step.meta.get("retry_attempts", [])

        attempts = []
        for attempt_data in attempts_data:
            try:
                # Handle datetime strings
                if "started_at" in attempt_data and isinstance(attempt_data["started_at"], str):
                    attempt_data["started_at"] = datetime.fromisoformat(attempt_data["started_at"])
                if "completed_at" in attempt_data and isinstance(attempt_data["completed_at"], str):
                    attempt_data["completed_at"] = datetime.fromisoformat(attempt_data["completed_at"])

                attempts.append(RetryAttempt(**attempt_data))
            except Exception as e:
                logger.warning("retry_attempt_load_failed", error=str(e))
                continue

        return attempts

    def _parse_user_suggestions(self, feedback: str) -> List[str]:
        """
        Parse user feedback into actionable suggestions.

        Args:
            feedback: User feedback text

        Returns:
            List of parsed suggestions
        """
        suggestions = []

        for line in feedback.split('\n'):
            line = line.strip()
            # Remove bullet points and list markers
            line = re.sub(r'^[-*•\d+.)\]]\s*', '', line)
            if line and len(line) > 5:  # Skip very short lines
                suggestions.append(line)

        return suggestions

    def record_attempt(
        self,
        step: WorkflowStep,
        attempt_number: int,
        error_type: Optional[str],
        error_message: Optional[str],
        traceback: Optional[str],
        agent_output: Optional[str]
    ):
        """
        Record retry attempt in step metadata.

        Args:
            step: WorkflowStep
            attempt_number: Attempt number
            error_type: Type of error (if failed)
            error_message: Error message (if failed)
            traceback: Full traceback (if failed)
            agent_output: Agent output
        """
        attempt = RetryAttempt(
            attempt_number=attempt_number,
            started_at=step.started_at or datetime.utcnow(),
            completed_at=datetime.utcnow(),
            error_type=error_type,
            error_message=error_message,
            traceback=traceback,
            agent_output=agent_output
        )

        # Add to step metadata
        if "retry_attempts" not in step.meta:
            step.meta["retry_attempts"] = []

        # Convert datetime objects to ISO format for JSON serialization
        attempt_dict = attempt.dict()
        if attempt_dict.get("started_at"):
            attempt_dict["started_at"] = attempt_dict["started_at"].isoformat()
        if attempt_dict.get("completed_at"):
            attempt_dict["completed_at"] = attempt_dict["completed_at"].isoformat()

        step.meta["retry_attempts"].append(attempt_dict)

        # Mark as modified to trigger update
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(step, "meta")

        self.db.commit()

    def format_retry_prompt(self, retry_context: RetryContext) -> str:
        """
        Format retry context into agent prompt.

        Args:
            retry_context: Retry context

        Returns:
            Formatted prompt string for agent
        """
        prompt_parts = []

        # Header
        prompt_parts.append(f"\n{'='*70}")
        prompt_parts.append(f"RETRY ATTEMPT {retry_context.current_attempt}/{retry_context.max_attempts}")
        prompt_parts.append('='*70)
        prompt_parts.append("")

        # Original task
        if retry_context.original_task:
            prompt_parts.append("ORIGINAL TASK:")
            prompt_parts.append(retry_context.original_task)
            prompt_parts.append("")

        # Previous attempts summary
        if retry_context.previous_attempts:
            prompt_parts.append("PREVIOUS ATTEMPTS:")
            for attempt in retry_context.previous_attempts[-3:]:  # Show last 3 attempts
                prompt_parts.append(f"\nAttempt {attempt.attempt_number}:")
                if attempt.error_message:
                    # Truncate long error messages
                    error_msg = attempt.error_message[:200]
                    if len(attempt.error_message) > 200:
                        error_msg += "..."
                    prompt_parts.append(f"  Error: {error_msg}")
                if attempt.modifications_tried:
                    prompt_parts.append(f"  Tried: {', '.join(attempt.modifications_tried)}")
            prompt_parts.append("")

        # Error analysis
        prompt_parts.append("ERROR ANALYSIS:")
        prompt_parts.append(f"  Category: {retry_context.error_category}")
        if retry_context.error_pattern:
            prompt_parts.append(f"  Pattern: {retry_context.error_pattern}")
        prompt_parts.append(f"  Known error type: {'Yes' if retry_context.common_error else 'No'}")
        prompt_parts.append("")

        # User feedback
        if retry_context.user_feedback:
            prompt_parts.append("USER GUIDANCE:")
            prompt_parts.append(retry_context.user_feedback)
            prompt_parts.append("")

        # Suggestions
        all_suggestions = retry_context.user_suggestions + retry_context.suggested_fixes
        if all_suggestions:
            prompt_parts.append("SUGGESTIONS TO TRY:")
            for idx, suggestion in enumerate(all_suggestions[:8], 1):  # Limit to 8 suggestions
                prompt_parts.append(f"  {idx}. {suggestion}")
            prompt_parts.append("")

        # Similar resolved errors
        if retry_context.similar_errors_resolved:
            prompt_parts.append("SIMILAR ERRORS SUCCESSFULLY RESOLVED:")
            for example in retry_context.similar_errors_resolved:
                prompt_parts.append(f"  - {example.get('description', 'Unknown')}")
                if 'solution' in example:
                    prompt_parts.append(f"    Solution: {example['solution']}")
            prompt_parts.append("")

        # Success probability
        if retry_context.success_probability is not None:
            prob_pct = retry_context.success_probability * 100
            prompt_parts.append(f"ESTIMATED SUCCESS PROBABILITY: {prob_pct:.0f}%")
            prompt_parts.append("")

        # Instructions
        prompt_parts.append("INSTRUCTIONS FOR RETRY:")
        prompt_parts.append("Please retry the task taking into account:")
        prompt_parts.append("  1. Why previous attempts failed")
        prompt_parts.append("  2. User guidance provided (if any)")
        prompt_parts.append("  3. Suggested fixes above")
        prompt_parts.append("  4. Try different approaches that might work")
        prompt_parts.append("")
        prompt_parts.append("If you determine the task cannot be completed, explain why clearly.")
        prompt_parts.append('='*70)
        prompt_parts.append("")

        return "\n".join(prompt_parts)

    def get_retry_summary(self, step: WorkflowStep) -> str:
        """
        Get human-readable retry summary for step.

        Args:
            step: WorkflowStep

        Returns:
            Formatted summary string
        """
        attempts = self._load_previous_attempts(step)

        if not attempts:
            return "No retry attempts recorded"

        summary_parts = []
        summary_parts.append(f"Retry Summary for Step {step.step_number}:")
        summary_parts.append(f"  Total attempts: {len(attempts)}")

        # Count successes and failures
        failures = sum(1 for a in attempts if a.error_type is not None)
        successes = len(attempts) - failures

        summary_parts.append(f"  Failures: {failures}")
        summary_parts.append(f"  Successes: {successes}")

        # Show error types
        error_types = [a.error_type for a in attempts if a.error_type]
        if error_types:
            unique_errors = list(set(error_types))
            summary_parts.append(f"  Error types: {', '.join(unique_errors)}")

        return "\n".join(summary_parts)
