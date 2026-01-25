"""
CMBAgent factory for standardized agent creation.

This module provides factory utilities that preserve the exact same
CMBAgent instantiation behavior as the original workflow implementations.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple

from cmbagent.utils import (
    default_llm_model as default_llm_model_default,
    default_formatter_model as default_formatter_model_default,
)
from cmbagent.workflows.core.timing import WorkflowTimer


@dataclass
class CMBAgentConfig:
    """
    Configuration for CMBAgent instantiation.

    This dataclass captures all the configuration options used when
    creating CMBAgent instances across different workflows.

    Attributes:
        mode: Workflow mode ('one_shot', 'chat', 'planning_and_control', etc.)
        clear_work_dir: Whether to clear the work directory
        cache_seed: Random seed for caching (default: 42)
        default_llm_model: Default LLM model
        default_formatter_model: Default formatter model
        chat_agent: Agent for chat mode (only for human_in_the_loop)
        approval_config: Optional ApprovalConfig for HITL control
    """
    mode: str = "planning_and_control"
    clear_work_dir: bool = False
    cache_seed: int = 42
    default_llm_model: str = default_llm_model_default
    default_formatter_model: str = default_formatter_model_default
    chat_agent: Optional[str] = None
    approval_config: Optional[Any] = None


class CMBAgentFactory:
    """
    Factory for creating CMBAgent instances with common configurations.

    This factory encapsulates the CMBAgent instantiation patterns from:
    - one_shot.py (lines 93-107)
    - human_in_the_loop (lines 243-253)
    - control.py (lines 107-119)
    - planning_control.py (lines 174-185, 408-425, 728-738, 811-823)

    All original parameters and behaviors are preserved.
    """

    @staticmethod
    def create(
        work_dir: str,
        agent_configs: Dict[str, Dict],
        api_keys: Dict[str, str],
        config: Optional[CMBAgentConfig] = None,
        timer: Optional[WorkflowTimer] = None,
    ) -> Tuple['CMBAgent', float]:
        """
        Create a configured CMBAgent instance.

        Args:
            work_dir: Working directory path
            agent_configs: Dictionary mapping agent names to their LLM configs
            api_keys: Dictionary of API keys
            config: Optional CMBAgentConfig (uses defaults if not provided)
            timer: Optional WorkflowTimer to track initialization time

        Returns:
            Tuple of (CMBAgent instance, initialization_time in seconds)
        """
        from cmbagent.cmbagent import CMBAgent
        import time

        if config is None:
            config = CMBAgentConfig()

        start_time = time.time()

        # Build CMBAgent kwargs matching original instantiation patterns
        kwargs: Dict[str, Any] = {
            'cache_seed': config.cache_seed,
            'work_dir': work_dir,
            'agent_llm_configs': agent_configs,
            'api_keys': api_keys,
            'default_llm_model': config.default_llm_model,
            'default_formatter_model': config.default_formatter_model,
        }

        # Add mode-specific parameters
        if config.mode:
            kwargs['mode'] = config.mode

        if config.clear_work_dir:
            kwargs['clear_work_dir'] = config.clear_work_dir

        if config.chat_agent is not None:
            kwargs['chat_agent'] = config.chat_agent

        if config.approval_config is not None:
            kwargs['approval_config'] = config.approval_config

        cmbagent = CMBAgent(**kwargs)

        end_time = time.time()
        initialization_time = end_time - start_time

        # Track timing if timer provided
        if timer is not None:
            timer.phases['initialization'] = type('TimingPhase', (), {
                'name': 'initialization',
                'start_time': start_time,
                'end_time': end_time,
                'duration': initialization_time
            })()

        return cmbagent, initialization_time

    @staticmethod
    def create_for_one_shot(
        work_dir: str,
        agent_configs: Dict[str, Dict],
        api_keys: Dict[str, str],
        clear_work_dir: bool = False,
        default_llm_model: str = default_llm_model_default,
        default_formatter_model: str = default_formatter_model_default,
    ) -> Tuple['CMBAgent', float]:
        """
        Create CMBAgent for one_shot workflow.

        Preserves exact behavior from one_shot.py lines 93-107.

        Args:
            work_dir: Working directory path
            agent_configs: Dictionary of agent configurations
            api_keys: Dictionary of API keys
            clear_work_dir: Whether to clear work directory
            default_llm_model: Default LLM model
            default_formatter_model: Default formatter model

        Returns:
            Tuple of (CMBAgent instance, initialization_time)
        """
        config = CMBAgentConfig(
            mode="one_shot",
            clear_work_dir=clear_work_dir,
            default_llm_model=default_llm_model,
            default_formatter_model=default_formatter_model,
        )
        return CMBAgentFactory.create(work_dir, agent_configs, api_keys, config)

    @staticmethod
    def create_for_chat(
        work_dir: str,
        agent_configs: Dict[str, Dict],
        api_keys: Dict[str, str],
        chat_agent: str = 'engineer',
    ) -> Tuple['CMBAgent', float]:
        """
        Create CMBAgent for human_in_the_loop workflow.

        Preserves exact behavior from one_shot.py lines 243-253.

        Args:
            work_dir: Working directory path
            agent_configs: Dictionary of agent configurations
            api_keys: Dictionary of API keys
            chat_agent: Agent to use for chat mode

        Returns:
            Tuple of (CMBAgent instance, initialization_time)
        """
        config = CMBAgentConfig(
            mode="chat",
            chat_agent=chat_agent,
        )
        return CMBAgentFactory.create(work_dir, agent_configs, api_keys, config)

    @staticmethod
    def create_for_control(
        work_dir: str,
        agent_configs: Dict[str, Dict],
        api_keys: Dict[str, str],
        clear_work_dir: bool = True,
    ) -> Tuple['CMBAgent', float]:
        """
        Create CMBAgent for control workflow.

        Preserves exact behavior from control.py lines 107-119.

        Args:
            work_dir: Working directory path
            agent_configs: Dictionary of agent configurations
            api_keys: Dictionary of API keys
            clear_work_dir: Whether to clear work directory

        Returns:
            Tuple of (CMBAgent instance, initialization_time)
        """
        config = CMBAgentConfig(
            clear_work_dir=clear_work_dir,
        )
        return CMBAgentFactory.create(work_dir, agent_configs, api_keys, config)

    @staticmethod
    def create_for_planning(
        work_dir: str,
        agent_configs: Dict[str, Dict],
        api_keys: Dict[str, str],
        default_llm_model: str = default_llm_model_default,
        default_formatter_model: str = default_formatter_model_default,
        approval_config: Optional[Any] = None,
    ) -> Tuple['CMBAgent', float]:
        """
        Create CMBAgent for planning phase.

        Preserves exact behavior from planning_control.py lines 174-185, 728-738.

        Args:
            work_dir: Working directory path
            agent_configs: Dictionary of agent configurations
            api_keys: Dictionary of API keys
            default_llm_model: Default LLM model
            default_formatter_model: Default formatter model
            approval_config: Optional ApprovalConfig for HITL

        Returns:
            Tuple of (CMBAgent instance, initialization_time)
        """
        config = CMBAgentConfig(
            default_llm_model=default_llm_model,
            default_formatter_model=default_formatter_model,
            approval_config=approval_config,
        )
        return CMBAgentFactory.create(work_dir, agent_configs, api_keys, config)

    @staticmethod
    def create_for_control_step(
        work_dir: str,
        agent_configs: Dict[str, Dict],
        api_keys: Dict[str, str],
        step: int,
        restart_at_step: int = -1,
        default_llm_model: str = default_llm_model_default,
        default_formatter_model: str = default_formatter_model_default,
        approval_config: Optional[Any] = None,
    ) -> Tuple['CMBAgent', float]:
        """
        Create CMBAgent for a control step in planning_and_control workflow.

        Preserves exact behavior from planning_control.py lines 408-425.

        Args:
            work_dir: Working directory path
            agent_configs: Dictionary of agent configurations
            api_keys: Dictionary of API keys
            step: Current step number (1-indexed)
            restart_at_step: Step to restart from (-1 or 0 for no restart)
            default_llm_model: Default LLM model
            default_formatter_model: Default formatter model
            approval_config: Optional ApprovalConfig for HITL

        Returns:
            Tuple of (CMBAgent instance, initialization_time)
        """
        # Clear work dir only on first step when not restarting (matches original logic)
        clear_work_dir = (step == 1 and restart_at_step <= 0)

        config = CMBAgentConfig(
            mode="planning_and_control_context_carryover",
            clear_work_dir=clear_work_dir,
            default_llm_model=default_llm_model,
            default_formatter_model=default_formatter_model,
            approval_config=approval_config,
        )
        return CMBAgentFactory.create(work_dir, agent_configs, api_keys, config)

    @staticmethod
    def ensure_groupchat(cmbagent: 'CMBAgent') -> None:
        """
        Ensure groupchat attribute exists (fixes display_cost bug).

        This function preserves the exact fix from:
        - one_shot.py lines 147-149
        - planning_control.py lines 244-246, 568-571, 762-765, 866-868
        - control.py lines 154-157

        Args:
            cmbagent: CMBAgent instance to fix
        """
        if not hasattr(cmbagent, 'groupchat'):
            Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
            cmbagent.groupchat = Dummy()
