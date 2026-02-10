"""
Workflow context module for CMBAgent.

This module provides the WorkflowContext class that manages state
across the entire workflow execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json
import pickle
from pathlib import Path


@dataclass
class WorkflowContext:
    """
    Master context that flows through entire workflow.

    Each phase can read and write to this context, enabling
    state to be carried between phases.

    Attributes:
        workflow_id: Unique identifier for the workflow definition
        run_id: Unique identifier for this workflow run
        task: The task description being executed
        work_dir: Working directory for file outputs
        api_keys: API credentials for external services

        plan: The generated plan (list of steps)
        plan_file_path: Path to saved plan JSON

        current_step: Current step being executed
        total_steps: Total number of steps in plan
        step_results: Results from each completed step
        step_summaries: Text summaries of each step

        approvals: HITL approval records
        user_feedback: Feedback from user interactions

        agent_state: Shared state between agents
        output_files: List of generated file paths
        phase_timings: Timing data for each phase
        metadata: Extensible storage for additional data
    """

    # === Immutable (set at workflow start) ===
    workflow_id: str
    run_id: str
    task: str
    work_dir: str
    api_keys: Dict[str, str]

    # === Planning outputs ===
    plan: Optional[List[Dict]] = None
    plan_file_path: Optional[str] = None

    # === Execution tracking ===
    current_step: int = 0
    total_steps: int = 0
    step_results: List[Dict] = field(default_factory=list)
    step_summaries: List[str] = field(default_factory=list)

    # === HITL state ===
    approvals: List[Dict] = field(default_factory=list)
    user_feedback: List[str] = field(default_factory=list)

    # === Shared state (carried between phases via PhaseContext) ===
    shared_state: Dict[str, Any] = field(default_factory=dict)

    # === Shared agent state ===
    agent_state: Dict[str, Any] = field(default_factory=dict)

    # === Files produced ===
    output_files: List[str] = field(default_factory=list)

    # === Timing ===
    phase_timings: Dict[str, float] = field(default_factory=dict)

    # === Extensible storage ===
    metadata: Dict[str, Any] = field(default_factory=dict)

    def save(self, path: Path) -> None:
        """
        Persist context to disk.

        Args:
            path: File path for saving context
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Filter out non-picklable items from shared_state before saving
        original_shared_state = self.shared_state.copy() if self.shared_state else {}
        filtered_shared_state = {}
        
        for key, value in original_shared_state.items():
            # Skip private keys (often contain closures or non-picklable objects)
            if key.startswith('_'):
                print(f"[Context.save] Skipping non-picklable key: {key}")
                continue
            try:
                # Test if item is picklable
                pickle.dumps(value)
                filtered_shared_state[key] = value
            except (TypeError, pickle.PicklingError) as e:
                print(f"[Context.save] Skipping non-picklable item '{key}': {e}")
        
        # Temporarily replace shared_state with filtered version
        self.shared_state = filtered_shared_state
        
        try:
            with open(path, 'wb') as f:
                pickle.dump(self, f)
        finally:
            # Restore original shared_state (with non-picklable items)
            self.shared_state = original_shared_state

    @classmethod
    def load(cls, path: Path) -> 'WorkflowContext':
        """
        Load context from disk.

        Args:
            path: File path to load from

        Returns:
            Loaded WorkflowContext instance
        """
        with open(path, 'rb') as f:
            return pickle.load(f)

    def to_phase_context(self, phase_id: str) -> 'PhaseContext':
        """
        Convert to PhaseContext for phase execution.

        Args:
            phase_id: Identifier for the phase

        Returns:
            PhaseContext configured with current workflow state
        """
        from cmbagent.phases.base import PhaseContext

        # Build shared state from workflow-level fields + accumulated shared_state
        phase_shared_state = {
            'plan': self.plan,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'step_results': self.step_results,
            'agent_state': self.agent_state,
            # Merge in any accumulated shared state (e.g., HITL feedback)
            **self.shared_state,
        }

        return PhaseContext(
            workflow_id=self.workflow_id,
            run_id=self.run_id,
            phase_id=phase_id,
            task=self.task,
            work_dir=self.work_dir,
            shared_state=phase_shared_state,
            input_data={},
            api_keys=self.api_keys,
        )

    def update_from_phase_result(self, result: 'PhaseResult') -> None:
        """
        Update workflow context from phase result.

        Merges phase output into the workflow context,
        extracting shared state and recording timing.

        Args:
            result: PhaseResult from completed phase
        """
        from cmbagent.phases.base import PhaseResult

        if result.context.output_data:
            # Merge shared state
            shared = result.context.output_data.get('shared', {})

            if 'plan' in shared:
                self.plan = shared['plan']
            if 'plan_steps' in shared:
                self.plan = shared['plan_steps']
                self.total_steps = len(self.plan)
            if 'current_step' in shared:
                self.current_step = shared['current_step']

            # Propagate all shared state items to WorkflowContext.shared_state
            # This ensures HITL feedback, planning history, etc. are accessible
            for key, value in shared.items():
                self.shared_state[key] = value

            # Store phase-specific outputs in metadata
            self.metadata[result.context.phase_id] = result.context.output_data

        # Record timing
        if result.timing:
            self.phase_timings[result.context.phase_id] = result.timing.get('total', 0)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert context to dictionary for serialization.

        Returns:
            Dictionary representation of context
        """
        return {
            'workflow_id': self.workflow_id,
            'run_id': self.run_id,
            'task': self.task,
            'work_dir': self.work_dir,
            'plan': self.plan,
            'plan_file_path': self.plan_file_path,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'step_results': self.step_results,
            'step_summaries': self.step_summaries,
            'shared_state': self.shared_state,
            'approvals': self.approvals,
            'user_feedback': self.user_feedback,
            'output_files': self.output_files,
            'phase_timings': self.phase_timings,
            'metadata': self.metadata,
        }

    def to_json(self) -> str:
        """
        Convert context to JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2, default=str)
