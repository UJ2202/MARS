"""
Core workflow abstractions for CMBAgent.

This module provides reusable components for workflow management:
- WorkflowTimer: Timing management across workflow phases
- AgentConfigBuilder: Builder pattern for agent LLM configurations
- WorkflowInitResult: Result of workflow initialization
- initialize_workflow: Unified workflow initialization function
- CMBAgentFactory: Factory for creating CMBAgent instances
- WorkflowFinalizer: Handles workflow finalization tasks
"""

from cmbagent.workflows.core.timing import (
    WorkflowTimer,
    TimingPhase,
)

from cmbagent.workflows.core.config import (
    AgentConfigBuilder,
    one_shot_agent_configs,
    control_agent_configs,
    planning_agent_configs,
)

from cmbagent.workflows.core.initialization import (
    WorkflowInitResult,
    initialize_workflow,
)

from cmbagent.workflows.core.factory import (
    CMBAgentFactory,
    CMBAgentConfig,
)

from cmbagent.workflows.core.finalization import (
    WorkflowFinalizer,
    FinalizationConfig,
)

__all__ = [
    # Timing
    'WorkflowTimer',
    'TimingPhase',
    # Config
    'AgentConfigBuilder',
    'one_shot_agent_configs',
    'control_agent_configs',
    'planning_agent_configs',
    # Initialization
    'WorkflowInitResult',
    'initialize_workflow',
    # Factory
    'CMBAgentFactory',
    'CMBAgentConfig',
    # Finalization
    'WorkflowFinalizer',
    'FinalizationConfig',
]
