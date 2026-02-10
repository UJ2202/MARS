"""
CMBAgent Workflows Module.

This module provides workflow orchestration functions:
- planning_and_control_context_carryover: Full workflow with context carryover
- planning_and_control: Simpler workflow without context carryover
- one_shot: Single-shot task execution
- human_in_the_loop: Interactive workflow
- control: Control-only workflow from existing plan

Utilities:
- clean_work_dir: Clear working directory
- load_context: Load pickled context
- load_plan: Load plan from JSON
"""

from cmbagent.workflows.utils import (
    clean_work_dir,
    load_context,
    load_plan,
)

from cmbagent.workflows.planning_control import (
    planning_and_control_context_carryover,
    planning_and_control,
    deep_research,  # Alias
)

from cmbagent.workflows.one_shot import (
    one_shot,
    human_in_the_loop,
)

from cmbagent.workflows.control import control

__all__ = [
    # Main workflows
    'planning_and_control_context_carryover',
    'planning_and_control',
    'deep_research',
    'one_shot',
    'human_in_the_loop',
    'control',
    # Utilities
    'clean_work_dir',
    'load_context',
    'load_plan',
]
