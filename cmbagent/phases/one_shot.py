"""
One-shot phase implementation for CMBAgent.

This module provides the OneShotPhase class for single-shot
task execution without planning.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import time
import json
import requests

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.utils import (
    get_model_config,
    default_agents_llm_model,
    camb_context_url,
    classy_context_url,
)
from cmbagent.utils import default_llm_model as default_llm_model_default
from cmbagent.utils import default_formatter_model as default_formatter_model_default


@dataclass
class OneShotPhaseConfig(PhaseConfig):
    """
    Configuration for one-shot execution phase.

    Attributes:
        max_rounds: Maximum conversation rounds
        max_n_attempts: Maximum retry attempts
        agent: Which agent to use for execution
        model: Model for the agent (uses agent default if not set)
        evaluate_plots: Whether to evaluate generated plots
        max_n_plot_evals: Maximum plot evaluation iterations
        researcher_filename: Output filename for researcher
    """
    phase_type: str = "one_shot"

    # Execution parameters
    max_rounds: int = 50
    max_n_attempts: int = 3

    # Which agent to use
    agent: str = "engineer"

    # Model selection (None = use agent default)
    model: Optional[str] = None
    engineer_model: str = field(default_factory=lambda: default_agents_llm_model['engineer'])
    researcher_model: str = field(default_factory=lambda: default_agents_llm_model['researcher'])
    web_surfer_model: str = field(default_factory=lambda: default_agents_llm_model.get('web_surfer', default_agents_llm_model['researcher']))
    plot_judge_model: str = field(default_factory=lambda: default_agents_llm_model['plot_judge'])
    camb_context_model: str = field(default_factory=lambda: default_agents_llm_model['camb_context'])

    # Default models
    default_llm_model: str = field(default_factory=lambda: default_llm_model_default)
    default_formatter_model: str = field(default_factory=lambda: default_formatter_model_default)

    # Plot evaluation
    evaluate_plots: bool = False
    max_n_plot_evals: int = 1

    # Researcher output
    researcher_filename: str = "researcher_output.md"

    # Clear work directory
    clear_work_dir: bool = False


class OneShotPhase(Phase):
    """
    One-shot execution phase - single agent, no planning.

    Input Context:
        - task: The task to execute
        - work_dir: Working directory

    Output Context:
        - result: Execution result
        - chat_history: Conversation history
    """

    config_class = OneShotPhaseConfig

    def __init__(self, config: OneShotPhaseConfig = None):
        if config is None:
            config = OneShotPhaseConfig()
        super().__init__(config)
        self.config: OneShotPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "one_shot"

    @property
    def display_name(self) -> str:
        return f"Execute ({self.config.agent})"

    def get_required_agents(self) -> List[str]:
        return [self.config.agent]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute single-shot task with specified agent.

        Args:
            context: Input context with task

        Returns:
            PhaseResult with execution results
        """
        from cmbagent.cmbagent import CMBAgent

        self._status = PhaseStatus.RUNNING
        context.started_at = time.time()

        # Notify callbacks
        if context.callbacks:
            context.callbacks.invoke_phase_change("one_shot", None)

        # Get model configs
        engineer_config = get_model_config(self.config.engineer_model, context.api_keys)
        researcher_config = get_model_config(self.config.researcher_model, context.api_keys)
        web_surfer_config = get_model_config(self.config.web_surfer_model, context.api_keys)
        plot_judge_config = get_model_config(self.config.plot_judge_model, context.api_keys)
        camb_context_config = get_model_config(self.config.camb_context_model, context.api_keys)

        try:
            # Initialize CMBAgent
            init_start = time.time()
            cmbagent = CMBAgent(
                cache_seed=42,
                mode="one_shot",
                work_dir=context.work_dir,
                agent_llm_configs={
                    'engineer': engineer_config,
                    'researcher': researcher_config,
                    'web_surfer': web_surfer_config,
                    'plot_judge': plot_judge_config,
                    'camb_context': camb_context_config,
                },
                clear_work_dir=self.config.clear_work_dir,
                api_keys=context.api_keys,
                default_llm_model=self.config.default_llm_model,
                default_formatter_model=self.config.default_formatter_model,
            )
            init_time = time.time() - init_start

            # Build shared context
            shared_context = {
                'max_n_attempts': self.config.max_n_attempts,
                'evaluate_plots': self.config.evaluate_plots,
                'max_n_plot_evals': self.config.max_n_plot_evals,
                'researcher_filename': self.config.researcher_filename,
                **context.shared_state,
            }

            # Fetch context for context agents
            if self.config.agent == 'camb_context':
                try:
                    resp = requests.get(camb_context_url, timeout=30)
                    resp.raise_for_status()
                    shared_context["camb_context"] = resp.text
                except Exception as e:
                    print(f"Warning: Could not fetch CAMB context: {e}")

            if self.config.agent == 'classy_context':
                try:
                    resp = requests.get(classy_context_url, timeout=30)
                    resp.raise_for_status()
                    shared_context["classy_context"] = resp.text
                except Exception as e:
                    print(f"Warning: Could not fetch CLASS context: {e}")

            # Execute
            exec_start = time.time()
            cmbagent.solve(
                context.task,
                max_rounds=self.config.max_rounds,
                initial_agent=self.config.agent,
                mode="one_shot",
                shared_context=shared_context,
            )
            exec_time = time.time() - exec_start

            # Create dummy groupchat if needed
            if not hasattr(cmbagent, 'groupchat'):
                Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
                cmbagent.groupchat = Dummy()

            # Display cost
            cmbagent.display_cost()

            print(f"\nTask took {exec_time:.4f} seconds\n")

            # Build output
            context.output_data = {
                'result': cmbagent.final_context,
                'agent_objects': {
                    'engineer': cmbagent.get_agent_object_from_name('engineer'),
                    'researcher': cmbagent.get_agent_object_from_name('researcher'),
                    'plot_judge': cmbagent.get_agent_object_from_name('plot_judge'),
                },
                'shared': {
                    'execution_complete': True,
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
            import traceback
            traceback.print_exc()
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error=str(e),
            )

    def validate_input(self, context: PhaseContext) -> List[str]:
        """Validate that required input is present."""
        errors = []
        if not context.task:
            errors.append("Task is required for one-shot phase")
        if not context.work_dir:
            errors.append("work_dir is required for one-shot phase")
        return errors
