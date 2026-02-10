"""
CMBAgent Workflows Module.

This module provides workflow orchestration using the phase-based architecture.

== Phase-Based Workflows ==
- WorkflowExecutor: Execute phase-based workflows
- WorkflowDefinition: Define workflow as sequence of phases
- SYSTEM_WORKFLOWS: Pre-defined workflow templates
- get_workflow: Get workflow definition by ID
- list_workflows: List all available workflows

== Function API ==
Backwards-compatible function signatures using the phase system:
- planning_and_control_context_carryover: Full workflow with context carryover
- planning_and_control: Simpler workflow without context carryover
- one_shot: Single-shot task execution
- control: Control workflow from existing plan
- human_in_the_loop: Interactive workflow
- idea_generation: Idea generation workflow
- idea_to_execution: Full idea to execution workflow

== Utilities ==
- clean_work_dir: Clear working directory
- load_context: Load pickled context
- load_plan: Load plan from JSON

Note: Phase-based workflows are the default and only implementation.
Legacy implementations are kept as *.legacy backup files for reference.

All workflows now use the phase-based architecture for consistency.
"""

import os

# Utilities
from cmbagent.workflows.utils import (
    clean_work_dir,
    load_context,
    load_plan,
)

# New phase-based workflow system
from cmbagent.workflows.composer import (
    WorkflowExecutor,
    WorkflowDefinition,
    SYSTEM_WORKFLOWS,
    get_workflow,
    list_workflows,
    # Preset workflows
    DEEP_RESEARCH_WORKFLOW,
    DEEP_RESEARCH_HITL_WORKFLOW,
    DEEP_RESEARCH_FULL_HITL_WORKFLOW,
    ONE_SHOT_WORKFLOW,
    ONE_SHOT_RESEARCHER_WORKFLOW,
    IDEA_GENERATION_WORKFLOW,
    IDEA_TO_EXECUTION_WORKFLOW,
    # Copilot workflows
    COPILOT_WORKFLOW,
    COPILOT_CONTINUOUS_WORKFLOW,
    COPILOT_SIMPLE_WORKFLOW,
)

# Phase-based function wrappers
from cmbagent.workflows.planning_control import (
    planning_and_control_context_carryover,
    deep_research,
)
from cmbagent.workflows.one_shot import one_shot, human_in_the_loop
from cmbagent.workflows.control import control
from cmbagent.workflows.idea_workflows import (
    idea_generation,
    idea_to_execution,
)

# HITL workflows
from cmbagent.workflows.hitl_workflow import (
    hitl_interactive_workflow,
    hitl_planning_only_workflow,
    hitl_error_recovery_workflow,
)

# Copilot workflows (now uses SwarmOrchestrator internally)
# Make these imports optional in case orchestrator module is not available
try:
    from cmbagent.workflows.copilot import (
        copilot,
        copilot_async,
        continue_copilot,
        continue_copilot_sync,
        get_active_copilot_sessions,
        quick_task,
        planned_task,
        interactive_session,
    )
except ImportError as e:
    print(f"Warning: Could not import copilot workflows: {e}")
    # Define placeholder functions
    def copilot(*args, **kwargs):
        raise NotImplementedError("Copilot workflows require the orchestrator module")
    copilot_async = copilot
    continue_copilot = copilot
    continue_copilot_sync = copilot
    get_active_copilot_sessions = lambda: {}
    quick_task = copilot
    planned_task = copilot
    interactive_session = copilot

# Swarm Copilot - Unified orchestration
try:
    from cmbagent.workflows.swarm_copilot import (
        swarm_copilot,
        swarm_copilot_async,
        continue_swarm_copilot,
        continue_swarm_copilot_sync,
        get_active_sessions,
        quick_swarm,
        full_swarm,
        interactive_swarm,
    )
except ImportError as e:
    print(f"Warning: Could not import swarm_copilot workflows: {e}")
    # Define placeholder functions
    def swarm_copilot(*args, **kwargs):
        raise NotImplementedError("Swarm Copilot workflows require the orchestrator module")
    swarm_copilot_async = swarm_copilot
    continue_swarm_copilot = swarm_copilot
    continue_swarm_copilot_sync = swarm_copilot
    get_active_sessions = lambda: {}
    quick_swarm = swarm_copilot
    full_swarm = swarm_copilot
    interactive_swarm = swarm_copilot

# Alias for simpler planning_and_control (without context carryover)
# Currently using the same implementation as the full version
planning_and_control = planning_and_control_context_carryover


__all__ = [
    # Phase-based workflow system
    'WorkflowExecutor',
    'WorkflowDefinition',
    'SYSTEM_WORKFLOWS',
    'get_workflow',
    'list_workflows',
    # Preset workflows
    'DEEP_RESEARCH_WORKFLOW',
    'DEEP_RESEARCH_HITL_WORKFLOW',
    'DEEP_RESEARCH_FULL_HITL_WORKFLOW',
    'ONE_SHOT_WORKFLOW',
    'ONE_SHOT_RESEARCHER_WORKFLOW',
    'IDEA_GENERATION_WORKFLOW',
    'IDEA_TO_EXECUTION_WORKFLOW',
    # Copilot preset workflows
    'COPILOT_WORKFLOW',
    'COPILOT_CONTINUOUS_WORKFLOW',
    'COPILOT_SIMPLE_WORKFLOW',
    # Function API (all use phase-based implementation)
    'planning_and_control_context_carryover',
    'planning_and_control',
    'deep_research',
    'one_shot',
    'control',
    'idea_generation',
    'idea_to_execution',
    'human_in_the_loop',
    # HITL workflows
    'hitl_interactive_workflow',
    'hitl_planning_only_workflow',
    'hitl_error_recovery_workflow',
    # Copilot functions (uses SwarmOrchestrator)
    'copilot',
    'copilot_async',
    'continue_copilot',
    'continue_copilot_sync',
    'get_active_copilot_sessions',
    'quick_task',
    'planned_task',
    'interactive_session',
    # Swarm Copilot - Unified orchestration
    'swarm_copilot',
    'swarm_copilot_async',
    'continue_swarm_copilot',
    'continue_swarm_copilot_sync',
    'get_active_sessions',
    'quick_swarm',
    'full_swarm',
    'interactive_swarm',
    # Utilities
    'clean_work_dir',
    'load_context',
    'load_plan',
]
