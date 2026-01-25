"""
Workflow initialization utilities for CMBAgent.

This module provides unified initialization logic that preserves the exact same
behavior as the original workflow implementations.
"""

import os
import uuid
from dataclasses import dataclass
from typing import Dict, Any, Optional

from cmbagent.utils import (
    work_dir_default,
    get_api_keys_from_env,
)
from cmbagent.execution.output_collector import WorkflowOutputManager


@dataclass
class WorkflowInitResult:
    """
    Result of workflow initialization.

    Contains all the initialized components needed by workflows:
    - work_dir: Absolute path to working directory
    - run_id: Unique identifier for this run
    - api_keys: Dictionary of API keys
    - output_manager: WorkflowOutputManager instance
    - callbacks: WorkflowCallbacks instance (null callbacks if not provided)
    - context_dir: Path to context directory (for planning_and_control workflows)
    """
    work_dir: str
    run_id: str
    api_keys: Dict[str, str]
    output_manager: WorkflowOutputManager
    callbacks: Any  # WorkflowCallbacks
    context_dir: Optional[str] = None


def initialize_workflow(
    work_dir: str = work_dir_default,
    api_keys: Optional[Dict[str, str]] = None,
    callbacks: Optional[Any] = None,
    clear_work_dir: bool = False,
    create_context_dir: bool = False,
    phase: Optional[str] = None,
    agent: Optional[str] = None,
) -> WorkflowInitResult:
    """
    Initialize a workflow with all common setup tasks.

    This function encapsulates the initialization patterns repeated across:
    - one_shot.py (lines 74-86)
    - planning_control.py (lines 107-136)
    - control.py (lines 78-80, 94-95)

    All original behaviors are preserved:
    - Work directory creation and normalization
    - API key initialization from environment
    - Output manager setup
    - Callbacks initialization (null callbacks if not provided)
    - Context directory creation (for planning_and_control)

    Args:
        work_dir: Working directory path (default: work_dir_default)
        api_keys: Optional API keys dictionary (fetched from env if None)
        callbacks: Optional WorkflowCallbacks instance
        clear_work_dir: Whether to clear the work directory
        create_context_dir: Whether to create context/ subdirectory
        phase: Optional phase name to set on output_manager
        agent: Optional agent name to set on output_manager

    Returns:
        WorkflowInitResult with all initialized components
    """
    from cmbagent.callbacks import create_null_callbacks
    from cmbagent.workflows.utils import clean_work_dir

    # Normalize work directory path (matches original behavior)
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    # Clear work directory if requested
    if clear_work_dir:
        clean_work_dir(work_dir)

    # Initialize context directory for planning_and_control workflows
    context_dir = None
    if create_context_dir:
        context_dir = os.path.join(work_dir, "context")
        os.makedirs(context_dir, exist_ok=True)
        print("Created context directory: ", context_dir)

    # Initialize file tracking system (matches one_shot.py lines 77-83)
    run_id = str(uuid.uuid4())
    output_manager = WorkflowOutputManager(
        work_dir=work_dir,
        run_id=run_id
    )

    # Set phase and agent on output manager if provided
    if phase is not None:
        output_manager.set_phase(phase)
    if agent is not None:
        output_manager.set_agent(agent)

    # Initialize API keys (matches original behavior - lines 85-86 of one_shot.py)
    if api_keys is None:
        api_keys = get_api_keys_from_env()

    # Initialize callbacks (use null callbacks if none provided)
    if callbacks is None:
        callbacks = create_null_callbacks()

    return WorkflowInitResult(
        work_dir=work_dir,
        run_id=run_id,
        api_keys=api_keys,
        output_manager=output_manager,
        callbacks=callbacks,
        context_dir=context_dir,
    )


def initialize_planning_workflow(
    work_dir: str = work_dir_default,
    api_keys: Optional[Dict[str, str]] = None,
    callbacks: Optional[Any] = None,
    clear_work_dir: bool = False,
    task: Optional[str] = None,
    max_plan_steps: int = 3,
    planner_model: str = "",
    engineer_model: str = "",
) -> WorkflowInitResult:
    """
    Initialize a planning_and_control workflow.

    This is a specialized initialization that includes:
    - Context directory creation
    - Workflow start callback invocation
    - Planning phase setup

    Args:
        work_dir: Working directory path
        api_keys: Optional API keys dictionary
        callbacks: Optional WorkflowCallbacks instance
        clear_work_dir: Whether to clear the work directory
        task: Task description (for callback invocation)
        max_plan_steps: Maximum steps in plan
        planner_model: Planner model name
        engineer_model: Engineer model name

    Returns:
        WorkflowInitResult with all initialized components
    """
    # Initialize base workflow
    init = initialize_workflow(
        work_dir=work_dir,
        api_keys=api_keys,
        callbacks=callbacks,
        clear_work_dir=clear_work_dir,
        create_context_dir=True,
    )

    # Invoke workflow start callback (matches planning_control.py lines 141-146)
    if task is not None:
        init.callbacks.invoke_workflow_start(task, {
            'max_plan_steps': max_plan_steps,
            'planner_model': planner_model,
            'engineer_model': engineer_model,
            'work_dir': init.work_dir
        })

    return init


def create_planning_dir(work_dir: str) -> str:
    """
    Create planning subdirectory.

    Args:
        work_dir: Base working directory

    Returns:
        Path to planning directory
    """
    planning_dir = os.path.join(os.path.expanduser(work_dir), "planning")
    os.makedirs(planning_dir, exist_ok=True)
    return planning_dir


def create_control_dir(work_dir: str) -> str:
    """
    Create control subdirectory.

    Args:
        work_dir: Base working directory

    Returns:
        Path to control directory
    """
    control_dir = os.path.join(os.path.expanduser(work_dir), "control")
    os.makedirs(control_dir, exist_ok=True)
    return control_dir
