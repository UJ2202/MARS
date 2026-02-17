"""
Literature Review phase for deep-research workflow.

Sample phase demonstrating how to create a new phase
with ZERO tracking code. The PhaseExecutionManager and
callbacks handle all cross-cutting tracking concerns.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import time
import logging

logger = logging.getLogger(__name__)

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.execution_manager import PhaseExecutionManager


@dataclass
class LiteratureReviewConfig(PhaseConfig):
    """Configuration for the literature review phase."""
    phase_type: str = "literature_review"

    max_rounds: int = 50
    researcher_model: str = "gpt-4.1-2025-04-14"


class LiteratureReviewPhase(Phase):
    """Research phase that reviews existing literature before planning.

    Input Context:
        - task: The research task
        - work_dir: Working directory

    Output Context:
        - literature_findings: Summary of literature review
    """

    config_class = LiteratureReviewConfig

    def __init__(self, config: LiteratureReviewConfig = None):
        if config is None:
            config = LiteratureReviewConfig()
        super().__init__(config)
        self.config: LiteratureReviewConfig = config

    @property
    def phase_type(self) -> str:
        return "literature_review"

    @property
    def display_name(self) -> str:
        return "Literature Review"

    def get_required_agents(self) -> List[str]:
        return ["researcher"]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """Execute literature review using the researcher agent.

        Zero tracking code: callbacks drive DAG, cost, events, files.
        """
        from cmbagent.cmbagent import CMBAgent
        from cmbagent.utils import get_model_config

        manager = PhaseExecutionManager(context, self)
        manager.start()

        self._status = PhaseStatus.RUNNING

        review_dir = os.path.join(context.work_dir, "literature_review")
        os.makedirs(review_dir, exist_ok=True)

        researcher_config = get_model_config(
            self.config.researcher_model, context.api_keys
        )

        try:
            manager.raise_if_cancelled()

            init_start = time.time()
            cmbagent = CMBAgent(
                cache_seed=42,
                mode="one_shot",
                work_dir=review_dir,
                agent_llm_configs={"researcher": researcher_config},
                api_keys=context.api_keys,
                **manager.get_managed_cmbagent_kwargs(),
            )
            cmbagent._callbacks = context.callbacks
            init_time = time.time() - init_start

            review_task = (
                f"Conduct a thorough literature review for the following research task. "
                f"Summarize key findings, relevant papers, existing methods, and gaps. "
                f"Task: {context.task}"
            )

            exec_start = time.time()
            cmbagent.solve(
                review_task,
                max_rounds=self.config.max_rounds,
                initial_agent="researcher",
                mode="one_shot",
                shared_context={
                    "researcher_filename": "literature_review.md",
                    **context.shared_state,
                },
            )
            exec_time = time.time() - exec_start

            if not hasattr(cmbagent, "groupchat"):
                Dummy = type("Dummy", (object,), {"new_conversable_agents": []})
                cmbagent.groupchat = Dummy()

            cmbagent.display_cost()

            # Extract findings from final context
            findings = cmbagent.final_context or {}
            literature_findings = {
                "summary": findings.get("summary", ""),
                "key_findings": findings.get("key_findings", []),
                "papers": findings.get("papers", []),
            }

            output_data = {
                "literature_findings": literature_findings,
                "shared": {
                    "literature_findings": literature_findings,
                },
            }

            self._status = PhaseStatus.COMPLETED
            return manager.complete(
                output_data=output_data,
                chat_history=(
                    cmbagent.chat_result.chat_history
                    if cmbagent.chat_result
                    else []
                ),
            )

        except Exception as e:
            self._status = PhaseStatus.FAILED
            logger.error("Literature review failed: %s", e, exc_info=True)
            return manager.fail(str(e))

    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        if not context.task:
            errors.append("Task is required for literature review phase")
        if not context.work_dir:
            errors.append("work_dir is required for literature review phase")
        return errors
