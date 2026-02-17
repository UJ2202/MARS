"""
Synthesis phase for deep-research workflow.

Sample phase that combines outputs from all prior phases into
a final synthesized result.  Uses PhaseExecutionManager for
automatic tracking — ZERO tracking code needed.
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
class SynthesisConfig(PhaseConfig):
    """Configuration for the synthesis phase."""
    phase_type: str = "synthesis"

    max_rounds: int = 50
    researcher_model: str = "gpt-4.1-2025-04-14"


class SynthesisPhase(Phase):
    """Combine outputs from all prior phases into a final result.

    Input Context (from shared_state):
        - literature_findings: Findings from literature review
        - step_outputs: Outputs from control-phase steps

    Output Context:
        - synthesis: Combined research result
    """

    config_class = SynthesisConfig

    def __init__(self, config: SynthesisConfig = None):
        if config is None:
            config = SynthesisConfig()
        super().__init__(config)
        self.config: SynthesisConfig = config

    @property
    def phase_type(self) -> str:
        return "synthesis"

    @property
    def display_name(self) -> str:
        return "Result Synthesis"

    def get_required_agents(self) -> List[str]:
        return ["researcher"]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """Synthesize results from all prior phases.

        Zero tracking code: callbacks drive DAG, cost, events, files.
        """
        from cmbagent.cmbagent import CMBAgent
        from cmbagent.utils import get_model_config

        manager = PhaseExecutionManager(context, self)
        manager.start()

        self._status = PhaseStatus.RUNNING

        synthesis_dir = os.path.join(context.work_dir, "synthesis")
        os.makedirs(synthesis_dir, exist_ok=True)

        researcher_config = get_model_config(
            self.config.researcher_model, context.api_keys
        )

        try:
            manager.raise_if_cancelled()

            # Gather results from shared state
            literature = context.shared_state.get("literature_findings", {})
            step_outputs = context.shared_state.get("step_outputs", [])
            planning_context = context.shared_state.get("planning_context", {})

            # Build synthesis prompt
            synthesis_prompt = self._build_synthesis_prompt(
                context.task, literature, step_outputs, planning_context
            )

            init_start = time.time()
            cmbagent = CMBAgent(
                cache_seed=42,
                mode="one_shot",
                work_dir=synthesis_dir,
                agent_llm_configs={"researcher": researcher_config},
                api_keys=context.api_keys,
                **manager.get_managed_cmbagent_kwargs(),
            )
            cmbagent._callbacks = context.callbacks
            init_time = time.time() - init_start

            exec_start = time.time()
            cmbagent.solve(
                synthesis_prompt,
                max_rounds=self.config.max_rounds,
                initial_agent="researcher",
                mode="one_shot",
                shared_context={
                    "researcher_filename": "synthesis_report.md",
                    **context.shared_state,
                },
            )
            exec_time = time.time() - exec_start

            if not hasattr(cmbagent, "groupchat"):
                Dummy = type("Dummy", (object,), {"new_conversable_agents": []})
                cmbagent.groupchat = Dummy()

            cmbagent.display_cost()

            synthesis_result = cmbagent.final_context or {}

            output_data = {
                "synthesis": synthesis_result,
                "shared": {
                    "synthesis": synthesis_result,
                    "execution_complete": True,
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
            logger.error("Synthesis phase failed: %s", e, exc_info=True)
            return manager.fail(str(e))

    @staticmethod
    def _build_synthesis_prompt(
        task: str,
        literature: Dict[str, Any],
        step_outputs: list,
        planning_context: Dict[str, Any],
    ) -> str:
        """Build a prompt that asks the researcher to synthesize all results."""
        sections = [
            "You are writing the final synthesis for a multi-step research project.",
            f"\n=== ORIGINAL TASK ===\n{task}",
        ]

        if literature:
            lit_summary = literature.get("summary", str(literature))
            sections.append(f"\n=== LITERATURE REVIEW ===\n{lit_summary}")

        if step_outputs:
            sections.append("\n=== STEP OUTPUTS ===")
            for i, out in enumerate(step_outputs, 1):
                sections.append(f"\nStep {i}: {str(out)[:1000]}")

        sections.append(
            "\n=== YOUR TASK ===\n"
            "Combine the above into a coherent final report. "
            "Include conclusions, limitations, and suggestions for future work."
        )

        return "\n".join(sections)

    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        if not context.task:
            errors.append("Task is required for synthesis phase")
        if not context.work_dir:
            errors.append("work_dir is required for synthesis phase")
        return errors
