"""Denario Experiment Execution Phase.

Source: Denario/denario/experiment.py
Key details:
  - First arg = data_description (the task)
  - 3 prompt injections: planner, engineer, researcher
    (all use {research_idea} + {methodology}; planner also uses {involved_agents_str})
  - Agent: researcher_response_formatter (experiment.py:105)
  - max_rounds_control=500, max_n_attempts=10, max_plan_steps=6 (defaults)
  - n_plan_reviews=1
  - Has restart_at_step and hardware_constraints params
  - Plots from final_context['displayed_images'], NOT glob
  - Plots MOVED to input_files/plots/ for paper stage
"""

import os
import shutil
import traceback
import logging
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.registry import PhaseRegistry
from cmbagent.phases.execution_manager import PhaseExecutionManager
from cmbagent.task_framework.utils import get_task_result, create_work_dir, extract_clean_markdown
from cmbagent.task_framework.config import INPUT_FILES, RESULTS_FILE, PLOTS_FOLDER

logger = logging.getLogger(__name__)


@dataclass
class DenarioExperimentPhaseConfig(PhaseConfig):
    """Configuration for Denario experiment execution phase."""
    phase_type: str = "denario_experiment"

    # Agent involvement
    involved_agents: List[str] = field(default_factory=lambda: ["engineer", "researcher"])

    # Model assignments (from experiment.py:21-30)
    engineer_model: str = "gpt-4.1"
    researcher_model: str = "o3-mini"
    planner_model: str = "gpt-4o"
    plan_reviewer_model: str = "o3-mini"
    orchestration_model: str = "gpt-4.1"
    formatter_model: str = "o3-mini"

    # Execution parameters
    restart_at_step: int = -1
    hardware_constraints: str = ""
    max_n_attempts: int = 10
    max_n_steps: int = 6

    # Parent tracking
    parent_run_id: str = ""
    stage_name: str = "experiment_execution"

    # API keys
    api_keys: Dict[str, Any] = field(default_factory=dict)


@PhaseRegistry.register("denario_experiment")
class DenarioExperimentPhase(Phase):
    """Execute experiments based on idea and methodology.

    Mirrors Denario/denario/experiment.py exactly.
    """

    config_class = DenarioExperimentPhaseConfig

    def __init__(self, config: DenarioExperimentPhaseConfig = None):
        if config is None:
            config = DenarioExperimentPhaseConfig()
        super().__init__(config)
        self.config: DenarioExperimentPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "denario_experiment"

    @property
    def display_name(self) -> str:
        return "Denario Experiment Execution"

    def get_required_agents(self) -> List[str]:
        return ["engineer", "researcher", "planner", "plan_reviewer"]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.workflows.planning_control import planning_and_control_context_carryover
        from cmbagent.task_framework.prompts.denario.experiment import (
            experiment_planner_prompt,
            experiment_engineer_prompt,
            experiment_researcher_prompt,
        )

        manager = PhaseExecutionManager(context, self)
        manager.start()

        try:
            # Read accumulated context
            research_idea = context.shared_state['research_idea']
            methodology = context.shared_state['methodology']
            data_description = context.shared_state.get('data_description', '')

            # Resolve API keys
            api_keys = self.config.api_keys or context.api_keys or None

            # Build involved_agents_str (experiment.py:50)
            involved_agents_str = ', '.join(self.config.involved_agents)

            # Inject context into ALL 3 prompts (experiment.py:53-65)
            planner_instructions = experiment_planner_prompt.format(
                research_idea=research_idea,
                methodology=methodology,
                involved_agents_str=involved_agents_str,
            )
            engineer_instructions = experiment_engineer_prompt.format(
                research_idea=research_idea,
                methodology=methodology,
            )
            researcher_instructions = experiment_researcher_prompt.format(
                research_idea=research_idea,
                methodology=methodology,
            )

            experiment_dir = create_work_dir(context.work_dir, "experiment")

            manager.start_step(1, "Running experiments")

            # CRITICAL: data_description is the FIRST arg (the task)
            # Wrapped in asyncio.to_thread because the function internally
            # uses asyncio.run() which can't be called from a running loop.
            results = await asyncio.to_thread(
                planning_and_control_context_carryover,
                data_description,                                           # task = data_description
                n_plan_reviews=1,                                           # experiment.py:83
                max_n_attempts=self.config.max_n_attempts,                  # experiment.py:84 (default 10)
                max_plan_steps=self.config.max_n_steps,                     # experiment.py:85 (default 6)
                max_rounds_control=500,                                     # experiment.py:86
                engineer_model=self.config.engineer_model,                  # experiment.py:87
                researcher_model=self.config.researcher_model,              # experiment.py:88
                planner_model=self.config.planner_model,                    # experiment.py:89
                plan_reviewer_model=self.config.plan_reviewer_model,        # experiment.py:90
                plan_instructions=planner_instructions,                     # experiment.py:91
                researcher_instructions=researcher_instructions,            # experiment.py:92
                engineer_instructions=engineer_instructions,                # experiment.py:93
                work_dir=str(experiment_dir),                               # experiment.py:94
                api_keys=api_keys,                                          # experiment.py:95
                restart_at_step=self.config.restart_at_step,                # experiment.py:96
                hardware_constraints=self.config.hardware_constraints,      # experiment.py:97
                default_llm_model=self.config.orchestration_model,          # experiment.py:98
                default_formatter_model=self.config.formatter_model,        # experiment.py:99
                parent_run_id=self.config.parent_run_id or None,
                stage_name=self.config.stage_name,
            )

            # Extract results
            chat_history = results['chat_history']
            final_context = results['final_context']
            task_result = get_task_result(chat_history, 'researcher_response_formatter')

            # Post-processing: extract markdown + strip HTML comments (experiment.py:109-111)
            experiment_results = extract_clean_markdown(task_result)

            # Get plot paths from final_context (experiment.py:113)
            # CRITICAL: Use final_context['displayed_images'], NOT glob
            plot_paths = final_context.get('displayed_images', [])

            # Save results to input_files/
            input_files_dir = os.path.join(str(context.work_dir), INPUT_FILES)
            os.makedirs(input_files_dir, exist_ok=True)
            results_path = os.path.join(input_files_dir, RESULTS_FILE)
            with open(results_path, 'w') as f:
                f.write(experiment_results)

            # Move plots to input_files/plots/ (denario.py:758-768)
            # Paper stage expects plots here
            plots_dir = os.path.join(input_files_dir, PLOTS_FOLDER)
            os.makedirs(plots_dir, exist_ok=True)

            # Clear existing plots
            for file in os.listdir(plots_dir):
                file_path = os.path.join(plots_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)

            # Move new plots
            for plot_path in plot_paths:
                if os.path.exists(plot_path):
                    shutil.move(plot_path, plots_dir)

            # Build final plot paths list
            final_plot_paths = []
            if os.path.exists(plots_dir):
                final_plot_paths = [
                    os.path.join(plots_dir, f)
                    for f in os.listdir(plots_dir)
                    if os.path.isfile(os.path.join(plots_dir, f))
                ]

            manager.complete_step(1, "Experiments completed")

            return manager.complete(output_data={
                'shared': {
                    'research_idea': research_idea,
                    'data_description': data_description,
                    'methodology': methodology,
                    'results': experiment_results,
                    'plot_paths': final_plot_paths,
                },
                'artifacts': {
                    'results.md': results_path,
                    'plots/': plots_dir,
                },
                'chat_history': chat_history,
            })

        except Exception as e:
            logger.error("Experiment execution failed: %s", e, exc_info=True)
            return manager.fail(str(e), traceback.format_exc())

    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        if 'research_idea' not in context.shared_state:
            errors.append("research_idea is required (run idea phase first)")
        if 'methodology' not in context.shared_state:
            errors.append("methodology is required (run method phase first)")
        return errors
