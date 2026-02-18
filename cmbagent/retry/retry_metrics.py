"""
Retry metrics and reporting.

Tracks retry statistics and generates reports for workflow runs.
"""

import logging
import structlog
from typing import Dict, Any
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)


class RetryMetrics:
    """Track retry statistics"""

    def __init__(self, db_session: Session):
        """
        Initialize retry metrics.

        Args:
            db_session: Database session
        """
        self.db = db_session

    def get_retry_stats(self, run_id: str) -> Dict[str, Any]:
        """
        Get retry statistics for workflow run.

        Args:
            run_id: Workflow run ID

        Returns:
            Dictionary with retry statistics
        """
        from cmbagent.database.models import WorkflowStep

        try:
            steps = self.db.query(WorkflowStep).filter(
                WorkflowStep.run_id == run_id
            ).all()

            total_steps = len(steps)
            steps_with_retries = 0
            total_retries = 0
            retry_success_count = 0
            error_categories = {}

            for step in steps:
                attempts = step.meta.get("retry_attempts", [])
                if len(attempts) > 1:
                    steps_with_retries += 1
                    total_retries += len(attempts) - 1

                    # Track success after retry
                    last_attempt = attempts[-1]
                    if last_attempt.get("error_type") is None:
                        retry_success_count += 1

                    # Count error categories
                    for attempt in attempts:
                        error_type = attempt.get("error_type")
                        if error_type:
                            error_categories[error_type] = error_categories.get(error_type, 0) + 1

            if steps_with_retries > 0:
                retry_success_rate = (retry_success_count / steps_with_retries) * 100
            else:
                retry_success_rate = 0

            return {
                "total_steps": total_steps,
                "steps_with_retries": steps_with_retries,
                "total_retry_attempts": total_retries,
                "retry_success_rate": round(retry_success_rate, 1),
                "avg_retries_per_step": round(total_retries / total_steps, 2) if total_steps > 0 else 0,
                "error_categories": error_categories
            }

        except Exception as e:
            logger.warning("retry_stats_calculation_failed", error=str(e))
            return {
                "total_steps": 0,
                "steps_with_retries": 0,
                "total_retry_attempts": 0,
                "retry_success_rate": 0,
                "avg_retries_per_step": 0,
                "error_categories": {}
            }

    def generate_retry_report(self, run_id: str) -> str:
        """
        Generate human-readable retry report.

        Args:
            run_id: Workflow run ID

        Returns:
            Formatted report string
        """
        stats = self.get_retry_stats(run_id)

        report = []
        report.append("RETRY STATISTICS")
        report.append("=" * 60)
        report.append(f"Total steps: {stats['total_steps']}")
        report.append(f"Steps requiring retry: {stats['steps_with_retries']}")
        report.append(f"Total retry attempts: {stats['total_retry_attempts']}")
        report.append(f"Retry success rate: {stats['retry_success_rate']}%")
        report.append(f"Average retries per step: {stats['avg_retries_per_step']}")
        report.append("")

        if stats['error_categories']:
            report.append("ERROR CATEGORIES:")
            for error_type, count in sorted(
                stats['error_categories'].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                report.append(f"  {error_type}: {count}")

        return "\n".join(report)

    def get_step_retry_history(self, step_id: str) -> Dict[str, Any]:
        """
        Get retry history for a specific step.

        Args:
            step_id: Step ID

        Returns:
            Dictionary with step retry history
        """
        from cmbagent.database.models import WorkflowStep

        try:
            step = self.db.query(WorkflowStep).filter(
                WorkflowStep.id == step_id
            ).first()

            if not step:
                return {"error": "Step not found"}

            attempts = step.meta.get("retry_attempts", [])

            return {
                "step_id": str(step.id),
                "step_number": step.step_number,
                "total_attempts": len(attempts),
                "final_status": step.status,
                "attempts": attempts
            }

        except Exception as e:
            return {"error": str(e)}
