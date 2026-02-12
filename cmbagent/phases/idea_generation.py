"""
Idea generation phase implementation for CMBAgent.

This module provides the IdeaGenerationPhase class that generates
and reviews research ideas using maker/hater dynamics.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import os
import time
import logging

logger = logging.getLogger(__name__)

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.utils import get_model_config, default_agents_llm_model


@dataclass
class IdeaGenerationPhaseConfig(PhaseConfig):
    """
    Configuration for idea generation phase.

    Attributes:
        max_rounds: Maximum conversation rounds
        n_ideas: Number of ideas to generate
        n_reviews: Number of review iterations
        idea_maker_model: Model for idea maker agent
        idea_hater_model: Model for idea hater/critic agent
    """
    phase_type: str = "idea_generation"

    # Idea parameters
    max_rounds: int = 50
    n_ideas: int = 3
    n_reviews: int = 1

    # Model selection
    idea_maker_model: str = field(default_factory=lambda: default_agents_llm_model['idea_maker'])
    idea_hater_model: str = field(default_factory=lambda: default_agents_llm_model['idea_hater'])


class IdeaGenerationPhase(Phase):
    """
    Idea generation phase with maker/hater dynamics.

    Uses an "idea maker" to generate ideas and an "idea hater"
    to critically review them, producing refined ideas.

    Input Context:
        - task: Research topic or problem

    Output Context:
        - ideas: Generated ideas
        - reviews: Hater reviews
        - selected_idea: Best idea after review
    """

    config_class = IdeaGenerationPhaseConfig

    def __init__(self, config: IdeaGenerationPhaseConfig = None):
        if config is None:
            config = IdeaGenerationPhaseConfig()
        super().__init__(config)
        self.config: IdeaGenerationPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "idea_generation"

    @property
    def display_name(self) -> str:
        return "Generate Ideas"

    def get_required_agents(self) -> List[str]:
        return ["idea_maker", "idea_hater", "idea_setter"]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute idea generation with maker/hater dynamics.

        Args:
            context: Input context with task

        Returns:
            PhaseResult with generated ideas
        """
        from cmbagent.cmbagent import CMBAgent

        self._status = PhaseStatus.RUNNING
        context.started_at = time.time()

        # Notify callbacks
        if context.callbacks:
            context.callbacks.invoke_phase_change("idea_generation", None)

        # Setup
        ideas_dir = os.path.join(context.work_dir, "ideas")
        os.makedirs(ideas_dir, exist_ok=True)

        # Get model configs
        maker_config = get_model_config(self.config.idea_maker_model, context.api_keys)
        hater_config = get_model_config(self.config.idea_hater_model, context.api_keys)

        try:
            # Initialize CMBAgent
            init_start = time.time()
            cmbagent = CMBAgent(
                cache_seed=42,
                work_dir=ideas_dir,
                agent_llm_configs={
                    'idea_maker': maker_config,
                    'idea_hater': hater_config,
                },
                api_keys=context.api_keys,
            )
            init_time = time.time() - init_start

            # Execute idea generation
            exec_start = time.time()
            cmbagent.solve(
                context.task,
                max_rounds=self.config.max_rounds,
                initial_agent="idea_setter",
                shared_context={
                    'n_ideas': self.config.n_ideas,
                    'feedback_left': self.config.n_reviews,
                    **context.shared_state,
                }
            )
            exec_time = time.time() - exec_start

            # Create dummy groupchat if needed
            if not hasattr(cmbagent, 'groupchat'):
                Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
                cmbagent.groupchat = Dummy()

            # Display cost
            cmbagent.display_cost()

            logger.info("Idea generation took %.4f seconds", exec_time)

            # Build output
            context.output_data = {
                'ideas': cmbagent.final_context.get('ideas', []),
                'reviews': cmbagent.final_context.get('reviews', []),
                'selected_idea': cmbagent.final_context.get('selected_idea'),
                'idea_context': cmbagent.final_context,
                'shared': {
                    'ideas': cmbagent.final_context.get('ideas', []),
                    'selected_idea': cmbagent.final_context.get('selected_idea'),
                }
            }

            context.completed_at = time.time()
            self._status = PhaseStatus.COMPLETED

            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
                chat_history=cmbagent.chat_result.chat_history if cmbagent.chat_result else [],
                timing={
                    'initialization': init_time,
                    'execution': exec_time,
                    'total': init_time + exec_time,
                }
            )

        except Exception as e:
            self._status = PhaseStatus.FAILED
            logger.error("Idea generation phase failed: %s", e, exc_info=True)
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error=str(e),
            )

    def validate_input(self, context: PhaseContext) -> List[str]:
        """Validate that required input is present."""
        errors = []
        if not context.task:
            errors.append("Task is required for idea generation phase")
        if not context.work_dir:
            errors.append("work_dir is required for idea generation phase")
        return errors
