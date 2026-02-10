"""
Metrics Collector - Performance tracking for phase execution.

This tracks orchestrator-level metrics (phase execution, workflow performance).
CMBAgent has its own agent-level tracking - these are complementary.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class PhaseExecutionMetric:
    """Metrics for a single phase execution."""
    phase_id: str
    phase_type: str
    status: str
    duration: float
    timestamp: datetime
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """
    Collects orchestrator-level metrics (phase execution, workflow performance).

    This is independent from CMBAgent's agent-level tracking.
    """

    def __init__(self):
        self.metrics: List[PhaseExecutionMetric] = []
        self.phase_counts: Dict[str, int] = defaultdict(int)
        self.phase_durations: Dict[str, List[float]] = defaultdict(list)
        self.phase_failures: Dict[str, int] = defaultdict(int)
        self.phase_successes: Dict[str, int] = defaultdict(int)
        self.start_time = datetime.now()
        self.total_duration = 0.0

    def record_phase_execution(
        self,
        phase_type: str,
        duration: float,
        status: str,
        phase_id: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a phase execution."""
        metric = PhaseExecutionMetric(
            phase_id=phase_id or f"{phase_type}_{len(self.metrics)}",
            phase_type=phase_type,
            status=status,
            duration=duration,
            timestamp=datetime.now(),
            error=error,
            metadata=metadata or {}
        )

        self.metrics.append(metric)
        self.phase_counts[phase_type] += 1
        self.phase_durations[phase_type].append(duration)
        self.total_duration += duration

        if status in ["success", "completed"]:
            self.phase_successes[phase_type] += 1
        elif status in ["failed", "error"]:
            self.phase_failures[phase_type] += 1

    def get_phase_stats(self, phase_type: str) -> Dict[str, Any]:
        """Get statistics for a specific phase type."""
        if phase_type not in self.phase_counts:
            return {
                "count": 0,
                "avg_duration": 0.0,
                "min_duration": 0.0,
                "max_duration": 0.0,
                "success_rate": 0.0,
            }

        durations = self.phase_durations[phase_type]
        count = self.phase_counts[phase_type]
        successes = self.phase_successes[phase_type]

        return {
            "count": count,
            "avg_duration": sum(durations) / len(durations) if durations else 0.0,
            "min_duration": min(durations) if durations else 0.0,
            "max_duration": max(durations) if durations else 0.0,
            "total_duration": sum(durations),
            "success_rate": successes / count if count > 0 else 0.0,
            "successes": successes,
            "failures": self.phase_failures[phase_type],
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get overall execution summary."""
        total_phases = len(self.metrics)
        total_successes = sum(self.phase_successes.values())
        total_failures = sum(self.phase_failures.values())

        phase_stats = {}
        for phase_type in self.phase_counts.keys():
            phase_stats[phase_type] = self.get_phase_stats(phase_type)

        all_durations = [m.duration for m in self.metrics]
        elapsed_time = (datetime.now() - self.start_time).total_seconds()

        return {
            "total_phases": total_phases,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "success_rate": total_successes / total_phases if total_phases > 0 else 0.0,
            "total_duration": self.total_duration,
            "elapsed_time": elapsed_time,
            "avg_phase_duration": sum(all_durations) / len(all_durations) if all_durations else 0.0,
            "min_phase_duration": min(all_durations) if all_durations else 0.0,
            "max_phase_duration": max(all_durations) if all_durations else 0.0,
            "phase_stats": phase_stats,
            "unique_phase_types": len(self.phase_counts),
        }

    def get_recent_metrics(self, count: int = 10) -> List[PhaseExecutionMetric]:
        """Get the most recent metrics."""
        return self.metrics[-count:]

    def get_slowest_phases(self, count: int = 5) -> List[PhaseExecutionMetric]:
        """Get the slowest phase executions."""
        sorted_metrics = sorted(self.metrics, key=lambda m: m.duration, reverse=True)
        return sorted_metrics[:count]

    def get_failed_phases(self) -> List[PhaseExecutionMetric]:
        """Get all failed phase executions."""
        return [m for m in self.metrics if m.status in ["failed", "error"]]

    def reset(self):
        """Reset all collected metrics."""
        self.metrics.clear()
        self.phase_counts.clear()
        self.phase_durations.clear()
        self.phase_failures.clear()
        self.phase_successes.clear()
        self.start_time = datetime.now()
        self.total_duration = 0.0
