"""Denario Idea Generation Phase.

Source: Denario/denario/idea.py
Key details:
  - First arg to planning_and_control = data_description (NOT a synthetic task string)
  - Agent: idea_maker_nest (idea.py:78)
  - max_plan_steps=6 (NOT 3)
  - n_plan_reviews=1
  - Post-processing: regex replaces "**Ideas** - Idea 1:" with "Project Idea:"
"""

import os
import re
import traceback
import logging
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.registry import PhaseRegistry
from cmbagent.phases.execution_manager import PhaseExecutionManager
from cmbagent.task_framework.utils import get_task_result, create_work_dir
from cmbagent.task_framework.config import INPUT_FILES, IDEA_FILE

logger = logging.getLogger(__name__)


@dataclass
class DenarioIdeaPhaseConfig(PhaseConfig):
    """Configuration for Denario idea generation phase."""
    phase_type: str = "denario_idea"

    # Model assignments (from Denario/denario/idea.py:32-37)
    idea_maker_model: str = "gpt-4o"
    idea_hater_model: str = "o3-mini"
    planner_model: str = "gpt-4o"
    plan_reviewer_model: str = "o3-mini"
    orchestration_model: str = "gpt-4.1"
    formatter_model: str = "o3-mini"

    # Data description (the task)
    data_description: str = ""

    # Parent tracking
    parent_run_id: str = ""
    stage_name: str = "idea_generation"

    # API keys
    api_keys: Dict[str, Any] = field(default_factory=dict)


@PhaseRegistry.register("denario_idea")
class DenarioIdeaPhase(Phase):
    """Generate a research idea using CMBAgent planning & control.

    Mirrors Denario/denario/idea.py exactly.
    """

    config_class = DenarioIdeaPhaseConfig

    def __init__(self, config: DenarioIdeaPhaseConfig = None):
        if config is None:
            config = DenarioIdeaPhaseConfig()
        super().__init__(config)
        self.config: DenarioIdeaPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "denario_idea"

    @property
    def display_name(self) -> str:
        return "Denario Idea Generation"

    def get_required_agents(self) -> List[str]:
        return ["idea_maker", "idea_hater", "planner", "plan_reviewer"]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.workflows.planning_control import planning_and_control_context_carryover
        from cmbagent.task_framework.prompts.denario.idea import idea_planner_prompt

        manager = PhaseExecutionManager(context, self)
        manager.start()

        try:
            # Get data description -- this IS the task (NOT appended to idea text)
            data_description = self.config.data_description
            if not data_description:
                data_description = context.shared_state.get(
                    "data_description", context.task
                )

            # Resolve API keys
            api_keys = self.config.api_keys or context.api_keys or None

            # Create stage-specific work subdirectory (Denario pattern)
            idea_dir = create_work_dir(context.work_dir, "idea")

            manager.start_step(1, "Generating research idea")

            # Call planning_and_control_context_carryover
            # CRITICAL: data_description is the FIRST arg (the task).
            # idea_planner_prompt goes into plan_instructions.
            # idea.py ONLY uses plan_instructions (no researcher_instructions).
            # Wrapped in asyncio.to_thread because the function internally
            # uses asyncio.run() which can't be called from a running loop.
            results = await asyncio.to_thread(
                planning_and_control_context_carryover,
                data_description,                                       # task = data_description
                n_plan_reviews=1,                                       # idea.py:62
                max_plan_steps=6,                                       # idea.py:63 (NOT 3)
                idea_maker_model=self.config.idea_maker_model,          # idea.py:64
                idea_hater_model=self.config.idea_hater_model,          # idea.py:65
                plan_instructions=idea_planner_prompt,                  # idea.py:66
                planner_model=self.config.planner_model,                # idea.py:67
                plan_reviewer_model=self.config.plan_reviewer_model,    # idea.py:68
                work_dir=str(idea_dir),                                 # idea.py:69
                api_keys=api_keys,                                      # idea.py:70
                default_llm_model=self.config.orchestration_model,      # idea.py:71
                default_formatter_model=self.config.formatter_model,    # idea.py:72
                parent_run_id=self.config.parent_run_id or None,
                stage_name=self.config.stage_name,
            )

            # Extract idea from chat history (verified agent: idea_maker_nest)
            chat_history = results['chat_history']
            task_result = get_task_result(chat_history, 'idea_maker_nest')

            # Post-processing: replace "**Ideas** - Idea 1:" with "Project Idea:"
            # Source: idea.py:82-84
            pattern = r'\*\*Ideas\*\*\s*\n- Idea 1:'
            replacement = "Project Idea:"
            research_idea = re.sub(pattern, replacement, task_result)

            # Save idea to input_files/ (Denario pattern)
            input_files_dir = os.path.join(str(context.work_dir), INPUT_FILES)
            os.makedirs(input_files_dir, exist_ok=True)
            idea_path = os.path.join(input_files_dir, IDEA_FILE)
            with open(idea_path, 'w') as f:
                f.write(research_idea)

            manager.complete_step(1, "Research idea generated")

            return manager.complete(output_data={
                'shared': {
                    'research_idea': research_idea,
                    'data_description': data_description,
                },
                'artifacts': {
                    'idea.md': idea_path,
                },
                'chat_history': chat_history,
            })

        except Exception as e:
            logger.error("Idea generation failed: %s", e, exc_info=True)
            return manager.fail(str(e), traceback.format_exc())

    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        data_description = self.config.data_description or context.shared_state.get(
            "data_description", context.task
        )
        if not data_description:
            errors.append("data_description or task is required for idea generation")
        return errors
