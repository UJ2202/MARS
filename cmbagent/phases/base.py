"""
Phase base module for CMBAgent.

This module provides the foundational abstractions for the phase-based workflow system:
- PhaseStatus: Enum for phase execution states
- PhaseContext: Context that flows between phases
- PhaseResult: Result of phase execution
- PhaseConfig: Base configuration for phases
- Phase: Abstract base class for all phases
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from enum import Enum


class PhaseStatus(Enum):
    """Status of a phase execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"


@dataclass
class PhaseContext:
    """
    Context that flows between phases.

    Contains both immutable identification data and mutable state that
    gets passed from phase to phase during workflow execution.

    Attributes:
        workflow_id: Unique identifier for the workflow definition
        run_id: Unique identifier for this workflow run
        phase_id: Unique identifier for this phase execution
        task: The task description being executed
        work_dir: Working directory for file outputs
        shared_state: State carried between phases
        input_data: Data received from previous phase
        output_data: Data to pass to next phase
        api_keys: API credentials for external services
        callbacks: Optional callback handlers for events
        started_at: Timestamp when phase started
        completed_at: Timestamp when phase completed
    """
    # Identification
    workflow_id: str
    run_id: str
    phase_id: str

    # Task info
    task: str
    work_dir: str

    # Shared state (carried between phases)
    shared_state: Dict[str, Any] = field(default_factory=dict)

    # Phase-specific input (from previous phase)
    input_data: Dict[str, Any] = field(default_factory=dict)

    # Phase-specific output (for next phase)
    output_data: Dict[str, Any] = field(default_factory=dict)

    # API keys and credentials
    api_keys: Dict[str, str] = field(default_factory=dict)

    # Callbacks
    callbacks: Optional[Any] = None

    # Timing
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            'workflow_id': self.workflow_id,
            'run_id': self.run_id,
            'phase_id': self.phase_id,
            'task': self.task,
            'work_dir': self.work_dir,
            'shared_state': self.shared_state,
            'input_data': self.input_data,
            'output_data': self.output_data,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
        }

    def copy_for_next_phase(self, next_phase_id: str) -> 'PhaseContext':
        """
        Create context for next phase, carrying over shared state.

        The current phase's output becomes the next phase's input,
        and shared state is merged with any new shared data from output.

        Args:
            next_phase_id: Identifier for the next phase

        Returns:
            New PhaseContext configured for the next phase
        """
        return PhaseContext(
            workflow_id=self.workflow_id,
            run_id=self.run_id,
            phase_id=next_phase_id,
            task=self.task,
            work_dir=self.work_dir,
            shared_state={**self.shared_state, **self.output_data.get('shared', {})},
            input_data=self.output_data,  # Previous output becomes next input
            output_data={},
            api_keys=self.api_keys,
            callbacks=self.callbacks,
        )


@dataclass
class PhaseResult:
    """
    Result of phase execution.

    Attributes:
        status: Final status of the phase
        context: Updated context after execution
        error: Error message if phase failed
        chat_history: Conversation history from agents
        timing: Timing breakdown for the phase
    """
    status: PhaseStatus
    context: PhaseContext
    error: Optional[str] = None
    chat_history: List[Dict] = field(default_factory=list)
    timing: Dict[str, float] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        """Check if phase completed successfully."""
        return self.status == PhaseStatus.COMPLETED

    @property
    def needs_approval(self) -> bool:
        """Check if phase is waiting for human approval."""
        return self.status == PhaseStatus.WAITING_APPROVAL


@dataclass
class PhaseConfig:
    """
    Base configuration for all phases.

    Attributes:
        phase_type: Identifier for the phase type
        enabled: Whether the phase should execute
        timeout_seconds: Maximum execution time
        max_retries: Number of retry attempts on failure
        model_overrides: Override models for specific agents
        params: Additional phase-specific parameters
    """
    phase_type: str
    enabled: bool = True
    timeout_seconds: int = 3600  # 1 hour default
    max_retries: int = 0

    # Model overrides (optional)
    model_overrides: Dict[str, str] = field(default_factory=dict)

    # Additional parameters (phase-specific)
    params: Dict[str, Any] = field(default_factory=dict)


class Phase(ABC):
    """
    Abstract base class for all phases.

    A phase is an atomic unit of work within a workflow.
    It receives context, performs work, and returns updated context.

    Subclasses must implement:
    - phase_type: Property returning unique phase identifier
    - display_name: Property returning human-readable name
    - execute: Async method that performs the phase's work
    """

    def __init__(self, config: PhaseConfig = None):
        """
        Initialize phase with configuration.

        Args:
            config: Phase configuration (uses defaults if None)
        """
        if config is None:
            config = PhaseConfig(phase_type=self.phase_type)
        self.config = config
        self._status = PhaseStatus.PENDING

    @property
    @abstractmethod
    def phase_type(self) -> str:
        """Unique identifier for this phase type."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        pass

    @property
    def status(self) -> PhaseStatus:
        """Current status of the phase."""
        return self._status

    @abstractmethod
    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute the phase.

        Args:
            context: Input context from previous phase

        Returns:
            PhaseResult with updated context
        """
        pass

    def validate_input(self, context: PhaseContext) -> List[str]:
        """
        Validate that required input is present.

        Args:
            context: Context to validate

        Returns:
            List of error messages (empty if valid)
        """
        return []

    def get_required_agents(self) -> List[str]:
        """
        Return list of agent names this phase requires.

        Returns:
            List of agent name strings
        """
        return []

    def get_output_schema(self) -> Dict[str, Any]:
        """
        Return JSON schema for this phase's output.

        Returns:
            JSON schema dictionary
        """
        return {}

    def can_skip(self, context: PhaseContext) -> bool:
        """
        Return True if this phase can be skipped given the context.

        Args:
            context: Current phase context

        Returns:
            True if phase should be skipped
        """
        return not self.config.enabled
