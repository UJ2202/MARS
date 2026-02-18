"""
Workflow Configuration - Configuration for workflow execution parameters.

This module defines configuration options for controlling workflow execution,
planning, and control phases.
"""

import os
import logging
import structlog
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

logger = structlog.get_logger(__name__)


@dataclass
class WorkflowConfig:
    """Configuration for workflow execution"""

    # Planning settings
    max_rounds_planning: int = 50
    max_rounds_control: int = 100
    max_plan_steps: int = 3
    n_plan_reviews: int = 1
    max_n_attempts: int = 3

    # Instructions (append to agent prompts)
    plan_instructions: str = ""
    engineer_instructions: str = ""
    researcher_instructions: str = ""
    hardware_constraints: str = ""

    # Model configurations
    planner_model: str = "gpt-4o"
    plan_reviewer_model: str = "gpt-4o"
    engineer_model: str = "gpt-4o"
    researcher_model: str = "gpt-4o"
    idea_maker_model: str = "gpt-4o"
    idea_hater_model: str = "gpt-4o"
    camb_context_model: str = "gpt-4o"
    plot_judge_model: str = "gpt-4o"
    default_llm_model: str = "gpt-4o"
    default_formatter_model: str = "gpt-4o-mini"

    # Execution settings
    clear_work_dir: bool = True
    restart_at_step: int = -1  # if -1 or 0, do not restart
    evaluate_plots: bool = False
    max_n_plot_evals: int = 1

    # API keys (if not using environment variables)
    api_keys: Optional[Dict[str, str]] = None

    @classmethod
    def from_env(cls) -> "WorkflowConfig":
        """
        Create configuration from environment variables.

        Environment variables:
        - CMBAGENT_MAX_ROUNDS_PLANNING: Max rounds for planning (default: 50)
        - CMBAGENT_MAX_ROUNDS_CONTROL: Max rounds for control (default: 100)
        - CMBAGENT_MAX_PLAN_STEPS: Max steps in plan (default: 3)
        - CMBAGENT_MAX_N_ATTEMPTS: Max retry attempts (default: 3)
        - CMBAGENT_PLANNER_MODEL: Planner model (default: gpt-4o)
        - CMBAGENT_ENGINEER_MODEL: Engineer model (default: gpt-4o)

        Returns:
            WorkflowConfig instance
        """
        config = cls()

        config.max_rounds_planning = cls._get_int_env(
            "CMBAGENT_MAX_ROUNDS_PLANNING",
            config.max_rounds_planning
        )

        config.max_rounds_control = cls._get_int_env(
            "CMBAGENT_MAX_ROUNDS_CONTROL",
            config.max_rounds_control
        )

        config.max_plan_steps = cls._get_int_env(
            "CMBAGENT_MAX_PLAN_STEPS",
            config.max_plan_steps
        )

        config.max_n_attempts = cls._get_int_env(
            "CMBAGENT_MAX_N_ATTEMPTS",
            config.max_n_attempts
        )

        config.planner_model = os.getenv(
            "CMBAGENT_PLANNER_MODEL",
            config.planner_model
        )

        config.engineer_model = os.getenv(
            "CMBAGENT_ENGINEER_MODEL",
            config.engineer_model
        )

        logger.info(
            f"Workflow config loaded: max_plan_steps={config.max_plan_steps}, "
            f"max_rounds_planning={config.max_rounds_planning}"
        )

        return config

    @classmethod
    def from_kwargs(cls, **kwargs) -> "WorkflowConfig":
        """
        Create configuration from keyword arguments, ignoring unknown keys.

        Args:
            **kwargs: Configuration parameters

        Returns:
            WorkflowConfig instance
        """
        # Get field names from dataclass
        field_names = {f.name for f in cls.__dataclass_fields__.values()}

        # Filter kwargs to only include valid fields
        valid_kwargs = {k: v for k, v in kwargs.items() if k in field_names}

        return cls(**valid_kwargs)

    @staticmethod
    def _get_int_env(key: str, default: int) -> int:
        """Get integer from environment variable"""
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning(f"Invalid integer value for {key}: {value}, using default {default}")
            return default

    def validate(self) -> bool:
        """
        Validate configuration values.

        Returns:
            True if valid, False otherwise
        """
        valid = True

        if self.max_rounds_planning < 1:
            logger.error(f"Invalid max_rounds_planning: {self.max_rounds_planning}, must be >= 1")
            valid = False

        if self.max_rounds_control < 1:
            logger.error(f"Invalid max_rounds_control: {self.max_rounds_control}, must be >= 1")
            valid = False

        if self.max_plan_steps < 1:
            logger.error(f"Invalid max_plan_steps: {self.max_plan_steps}, must be >= 1")
            valid = False

        if self.max_n_attempts < 1:
            logger.error(f"Invalid max_n_attempts: {self.max_n_attempts}, must be >= 1")
            valid = False

        return valid

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "max_rounds_planning": self.max_rounds_planning,
            "max_rounds_control": self.max_rounds_control,
            "max_plan_steps": self.max_plan_steps,
            "n_plan_reviews": self.n_plan_reviews,
            "max_n_attempts": self.max_n_attempts,
            "plan_instructions": self.plan_instructions,
            "engineer_instructions": self.engineer_instructions,
            "researcher_instructions": self.researcher_instructions,
            "hardware_constraints": self.hardware_constraints,
            "planner_model": self.planner_model,
            "plan_reviewer_model": self.plan_reviewer_model,
            "engineer_model": self.engineer_model,
            "researcher_model": self.researcher_model,
            "idea_maker_model": self.idea_maker_model,
            "idea_hater_model": self.idea_hater_model,
            "camb_context_model": self.camb_context_model,
            "plot_judge_model": self.plot_judge_model,
            "default_llm_model": self.default_llm_model,
            "default_formatter_model": self.default_formatter_model,
            "clear_work_dir": self.clear_work_dir,
            "restart_at_step": self.restart_at_step,
            "evaluate_plots": self.evaluate_plots,
            "max_n_plot_evals": self.max_n_plot_evals,
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"WorkflowConfig(max_plan_steps={self.max_plan_steps}, "
            f"max_rounds_planning={self.max_rounds_planning}, "
            f"planner_model={self.planner_model})"
        )


# Default global configuration
_default_config = WorkflowConfig()


def get_workflow_config() -> WorkflowConfig:
    """Get current workflow configuration"""
    return _default_config


def set_workflow_config(config: WorkflowConfig) -> None:
    """Set global workflow configuration"""
    global _default_config
    _default_config = config
    logger.info(f"Workflow configuration updated: {config}")


def reset_workflow_config() -> None:
    """Reset to default configuration"""
    global _default_config
    _default_config = WorkflowConfig()
    logger.info("Workflow configuration reset to defaults")
