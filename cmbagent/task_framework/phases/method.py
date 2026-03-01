"""Denario Method Development Phase.

Source: Denario/denario/method.py
Key details:
  - First arg = data_description (the task)
  - Prompts injected: method_planner_prompt.format(research_idea=...),
                      method_researcher_prompt.format(research_idea=...)
  - Agent: researcher_response_formatter (method.py:67)
  - max_plan_steps=4, max_n_attempts=4, n_plan_reviews=1
  - Post-processing: regex markdown extraction + HTML comment stripping
"""

import os
import traceback
import logging
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.registry import PhaseRegistry
from cmbagent.phases.execution_manager import PhaseExecutionManager
from cmbagent.task_framework.utils import get_task_result, create_work_dir, extract_clean_markdown
from cmbagent.task_framework.config import INPUT_FILES, METHOD_FILE

logger = logging.getLogger(__name__)


@dataclass
class DenarioMethodPhaseConfig(PhaseConfig):
    """Configuration for Denario method development phase."""
    phase_type: str = "denario_method"

    # Model assignments (from Denario/denario/method.py:21-25)
    researcher_model: str = "gpt-4.1"
    planner_model: str = "gpt-4.1"
    plan_reviewer_model: str = "o3-mini"
    orchestration_model: str = "gpt-4.1"
    formatter_model: str = "o3-mini"

    # Parent tracking
    parent_run_id: str = ""
    stage_name: str = "method_development"

    # API keys
    api_keys: Dict[str, Any] = field(default_factory=dict)


@PhaseRegistry.register("denario_method")
class DenarioMethodPhase(Phase):
    """Develop research methodology.

    Mirrors Denario/denario/method.py exactly.
    Reads research_idea from context.shared_state (set by DenarioIdeaPhase).
    """

    config_class = DenarioMethodPhaseConfig

    def __init__(self, config: DenarioMethodPhaseConfig = None):
        if config is None:
            config = DenarioMethodPhaseConfig()
        super().__init__(config)
        self.config: DenarioMethodPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "denario_method"

    @property
    def display_name(self) -> str:
        return "Denario Method Development"

    def get_required_agents(self) -> List[str]:
        return ["researcher", "planner", "plan_reviewer"]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.workflows.planning_control import planning_and_control_context_carryover
        from cmbagent.task_framework.prompts.denario.method import (
            method_planner_prompt,
            method_researcher_prompt,
        )

        manager = PhaseExecutionManager(context, self)
        manager.start()

        try:
            # Read accumulated context
            research_idea = context.shared_state['research_idea']
            data_description = context.shared_state.get('data_description', '')

            # Resolve API keys
            api_keys = self.config.api_keys or context.api_keys or None

            # Inject research_idea into prompts (method.py:38-39)
            # Verified placeholder: {research_idea}
            planner_instructions = method_planner_prompt.format(
                research_idea=research_idea
            )
            researcher_instructions = method_researcher_prompt.format(
                research_idea=research_idea
            )

            method_dir = create_work_dir(context.work_dir, "method")

            manager.start_step(1, "Developing methodology")

            # CRITICAL: data_description is the FIRST arg (the task)
            # Wrapped in asyncio.to_thread because the function internally
            # uses asyncio.run() which can't be called from a running loop.
            results = await asyncio.to_thread(
                planning_and_control_context_carryover,
                data_description,                                       # task = data_description
                n_plan_reviews=1,                                       # method.py:50
                max_n_attempts=4,                                       # method.py:51 (NOT default 3)
                max_plan_steps=4,                                       # method.py:52 (NOT 3)
                researcher_model=self.config.researcher_model,          # method.py:53
                planner_model=self.config.planner_model,                # method.py:54
                plan_reviewer_model=self.config.plan_reviewer_model,    # method.py:55
                plan_instructions=planner_instructions,                 # method.py:56
                researcher_instructions=researcher_instructions,        # method.py:57
                work_dir=str(method_dir),                               # method.py:58
                api_keys=api_keys,                                      # method.py:59
                default_llm_model=self.config.orchestration_model,      # method.py:60
                default_formatter_model=self.config.formatter_model,    # method.py:61
                parent_run_id=self.config.parent_run_id or None,
                stage_name=self.config.stage_name,
            )

            # Extract methodology (verified agent: researcher_response_formatter)
            chat_history = results['chat_history']
            task_result = get_task_result(chat_history, 'researcher_response_formatter')

            # Post-processing: extract markdown + strip HTML comments (method.py:71-73)
            methodology = extract_clean_markdown(task_result)

            # Save to input_files/
            input_files_dir = os.path.join(str(context.work_dir), INPUT_FILES)
            os.makedirs(input_files_dir, exist_ok=True)
            methods_path = os.path.join(input_files_dir, METHOD_FILE)
            with open(methods_path, 'w') as f:
                f.write(methodology)

            manager.complete_step(1, "Methodology developed")

            return manager.complete(output_data={
                'shared': {
                    'research_idea': research_idea,
                    'data_description': data_description,
                    'methodology': methodology,
                },
                'artifacts': {
                    'methods.md': methods_path,
                },
                'chat_history': chat_history,
            })

        except Exception as e:
            logger.error("Method development failed: %s", e, exc_info=True)
            return manager.fail(str(e), traceback.format_exc())

    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        if 'research_idea' not in context.shared_state:
            errors.append("research_idea is required (run idea phase first)")
        return errors
