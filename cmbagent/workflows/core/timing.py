"""
Timing management for CMBAgent workflows.

This module provides timing tracking utilities that preserve
the exact same timing information as the original workflow implementations.
"""

import os
import json
import time
import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from contextlib import contextmanager


@dataclass
class TimingPhase:
    """
    Represents a single timing phase in a workflow.

    Attributes:
        name: Name of the phase (e.g., 'initialization', 'execution')
        start_time: Start time in seconds since epoch
        end_time: End time in seconds since epoch (None if not ended)
        duration: Duration in seconds (computed when phase ends)
    """
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None

    def end(self) -> float:
        """End this phase and compute duration."""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        return self.duration


@dataclass
class WorkflowTimer:
    """
    Track timing across workflow phases.

    This class provides timing functionality that matches the exact
    behavior of the original workflow timing code, preserving:
    - initialization_time tracking
    - execution_time tracking
    - total_time computation
    - Timing report format and JSON saving

    Example usage:
        timer = WorkflowTimer()

        with timer.phase("initialization"):
            # initialization code
            pass

        with timer.phase("execution"):
            # execution code
            pass

        # Save timing report
        timer.save_report(work_dir, "timing_report")

        # Or get report dict
        report = timer.to_report()
    """
    phases: Dict[str, TimingPhase] = field(default_factory=dict)
    _current_phase: Optional[str] = None
    _phase_start: Optional[float] = None

    def start_phase(self, phase_name: str) -> None:
        """
        Start timing a phase.

        Args:
            phase_name: Name of the phase to start
        """
        self._current_phase = phase_name
        self._phase_start = time.time()
        self.phases[phase_name] = TimingPhase(name=phase_name, start_time=self._phase_start)

    def end_phase(self) -> float:
        """
        End current phase and return duration.

        Returns:
            Duration of the phase in seconds
        """
        if self._current_phase is None or self._phase_start is None:
            return 0.0

        phase = self.phases.get(self._current_phase)
        if phase:
            duration = phase.end()
        else:
            duration = time.time() - self._phase_start

        self._current_phase = None
        self._phase_start = None
        return duration

    @contextmanager
    def phase(self, phase_name: str):
        """
        Context manager for timing a phase.

        Args:
            phase_name: Name of the phase to time

        Example:
            with timer.phase("execution"):
                cmbagent.solve(...)
        """
        self.start_phase(phase_name)
        try:
            yield
        finally:
            self.end_phase()

    def get_duration(self, phase_name: str) -> float:
        """
        Get duration of a specific phase.

        Args:
            phase_name: Name of the phase

        Returns:
            Duration in seconds, or 0.0 if phase not found
        """
        phase = self.phases.get(phase_name)
        if phase and phase.duration is not None:
            return phase.duration
        return 0.0

    @property
    def initialization_time(self) -> float:
        """Get initialization time (matches original variable name)."""
        return self.get_duration("initialization")

    @property
    def execution_time(self) -> float:
        """Get execution time (matches original variable name)."""
        return self.get_duration("execution")

    @property
    def total_time(self) -> float:
        """Get total time across all phases."""
        return sum(
            phase.duration for phase in self.phases.values()
            if phase.duration is not None
        )

    def to_report(self, prefix: str = "") -> Dict[str, Any]:
        """
        Generate timing report dictionary.

        The format matches the original timing report structure:
        {
            'initialization_time': float,
            'execution_time': float,
            'total_time': float
        }

        For planning/control workflows with prefixes:
        {
            'initialization_time_planning': float,
            'execution_time_planning': float,
            'total_time': float
        }

        Args:
            prefix: Optional prefix for timing keys (e.g., '_planning', '_control')

        Returns:
            Dictionary with timing information
        """
        report = {}

        for phase_name, phase in self.phases.items():
            if phase.duration is not None:
                key = f"{phase_name}_time{prefix}"
                report[key] = phase.duration

        report['total_time'] = self.total_time
        return report

    def to_results_dict(self, prefix: str = "") -> Dict[str, float]:
        """
        Generate dict for adding to results (matches original behavior).

        Args:
            prefix: Optional prefix for timing keys

        Returns:
            Dictionary with initialization_time and execution_time
        """
        result = {}

        init_time = self.get_duration("initialization")
        if init_time > 0:
            key = f"initialization_time{prefix}"
            result[key] = init_time

        exec_time = self.get_duration("execution")
        if exec_time > 0:
            key = f"execution_time{prefix}"
            result[key] = exec_time

        return result

    def save_report(
        self,
        work_dir: str,
        filename_base: str = "timing_report",
        prefix: str = ""
    ) -> str:
        """
        Save timing report as JSON file.

        Matches the original behavior:
        - Creates time/ subdirectory if needed
        - Adds timestamp to filename
        - Uses same JSON format

        Args:
            work_dir: Working directory path
            filename_base: Base name for the file (e.g., 'timing_report', 'timing_report_planning')
            prefix: Optional prefix for timing keys

        Returns:
            Path to the saved timing report file
        """
        report = self.to_report(prefix)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        timing_path = os.path.join(work_dir, f"time/{filename_base}_{timestamp}.json")

        os.makedirs(os.path.dirname(timing_path), exist_ok=True)

        with open(timing_path, 'w') as f:
            json.dump(report, f, indent=2)

        return timing_path


class StepTimer(WorkflowTimer):
    """
    Timer specialized for step-based workflows.

    Tracks timing for individual steps in planning_and_control workflows.
    """

    def __init__(self, step: int):
        """
        Initialize step timer.

        Args:
            step: Step number (1-indexed)
        """
        super().__init__()
        self.step = step

    def to_report(self, prefix: str = "") -> Dict[str, Any]:
        """Generate timing report for a step."""
        report = {}

        for phase_name, phase in self.phases.items():
            if phase.duration is not None:
                # Use _control suffix for step timings (matches original)
                key = f"{phase_name}_time_control"
                report[key] = phase.duration

        report['total_time'] = self.total_time
        return report

    def save_report(
        self,
        work_dir: str,
        filename_base: str = "timing_report",
        prefix: str = ""
    ) -> str:
        """
        Save timing report for this step.

        Args:
            work_dir: Working directory path
            filename_base: Base name (usually 'timing_report')
            prefix: Ignored for step timer

        Returns:
            Path to the saved timing report file
        """
        report = self.to_report()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        timing_path = os.path.join(work_dir, f"time/timing_report_step_{self.step}_{timestamp}.json")

        os.makedirs(os.path.dirname(timing_path), exist_ok=True)

        with open(timing_path, 'w') as f:
            json.dump(report, f, indent=2)

        return timing_path
