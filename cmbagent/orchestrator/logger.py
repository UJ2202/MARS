"""
Orchestrator Logger - Logging for phase execution and workflow orchestration.

This logs orchestrator-level events (phase lifecycle, workflow transitions).
CMBAgent has its own logger for agent-level events - these are complementary.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class OrchestratorLogger:
    """
    Logger for orchestrator-level events (phase execution, workflow orchestration).

    This is independent from CMBAgent's agent logging.
    Uses standard Python logging + optional file output.
    """

    def __init__(self, config: Any = None, log_file: Optional[str] = None):
        """
        Initialize the orchestrator logger.

        Args:
            config: Optional configuration object
            log_file: Optional file path for writing logs
        """
        self.config = config
        self.log_file = log_file

        # Use standard Python logging (compatible with CMBAgent)
        self.logger = logging.getLogger("orchestrator")

        # Set level based on config or default to INFO
        if config and hasattr(config, 'log_level'):
            level_name = getattr(config, 'log_level', 'INFO')
            level = getattr(logging, level_name.upper(), logging.INFO)
        else:
            level = logging.INFO

        self.logger.setLevel(level)

        # Add console handler if not already present
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # Add file handler if specified
        if log_file:
            try:
                file_path = Path(log_file)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(level)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception as e:
                self.logger.warning(f"Failed to create file handler: {e}")

    def log_phase_start(self, phase_id: str, phase_type: str, task: str):
        """Log the start of a phase execution."""
        self.logger.info(
            f"Phase started - ID: {phase_id}, Type: {phase_type}, Task: {task[:100]}"
        )

    def log_phase_complete(self, phase_id: str, status: str, duration: float):
        """Log the completion of a phase execution."""
        self.logger.info(
            f"Phase completed - ID: {phase_id}, Status: {status}, Duration: {duration:.2f}s"
        )

    def log_phase_error(self, phase_id: str, error_msg: str, stack_trace: Optional[str] = None):
        """Log a phase execution error."""
        msg = f"Phase error - ID: {phase_id}, Error: {error_msg}"
        if stack_trace:
            msg += f"\nStack trace:\n{stack_trace}"
        self.logger.error(msg)

    def log_event(self, message: str, level: str = "info", **kwargs):
        """
        Log a general orchestration event.

        Args:
            message: Log message
            level: Log level (debug, info, warning, error)
            **kwargs: Additional context to include in log
        """
        log_func = getattr(self.logger, level.lower(), self.logger.info)

        if kwargs:
            context = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
            message = f"{message} ({context})"

        log_func(message)

    def log_chain_start(self, chain_id: str, phases: list):
        """Log the start of a phase chain execution."""
        phase_names = [p['phase_type'] for p in phases]
        self.logger.info(
            f"Chain started - ID: {chain_id}, Phases: {' -> '.join(phase_names)}"
        )

    def log_chain_complete(self, chain_id: str, status: str, duration: float):
        """Log the completion of a phase chain."""
        self.logger.info(
            f"Chain completed - ID: {chain_id}, Status: {status}, Duration: {duration:.2f}s"
        )

    def log_continuation(self, session_id: str, round_count: int, continuation_count: int):
        """Log a workflow continuation event."""
        self.logger.info(
            f"Workflow continuation - Session: {session_id}, "
            f"Round: {round_count}, Continuation: {continuation_count}"
        )

    def log_swarm_start(self, session_id: str, task: str, config: Dict[str, Any]):
        """Log the start of a swarm orchestration."""
        self.logger.info(
            f"Swarm started - Session: {session_id}, Task: {task[:100]}, "
            f"Max rounds: {config.get('max_rounds', 'N/A')}"
        )

    def log_swarm_complete(self, session_id: str, status: str, rounds: int, duration: float):
        """Log the completion of a swarm orchestration."""
        self.logger.info(
            f"Swarm completed - Session: {session_id}, Status: {status}, "
            f"Rounds: {rounds}, Duration: {duration:.2f}s"
        )

    def debug(self, message: str, **kwargs):
        """Log a debug message."""
        self.log_event(message, level="debug", **kwargs)

    def info(self, message: str, **kwargs):
        """Log an info message."""
        self.log_event(message, level="info", **kwargs)

    def warning(self, message: str, **kwargs):
        """Log a warning message."""
        self.log_event(message, level="warning", **kwargs)

    def error(self, message: str, **kwargs):
        """Log an error message."""
        self.log_event(message, level="error", **kwargs)
