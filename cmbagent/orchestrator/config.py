"""
Orchestrator Configuration

Configuration options for the phase orchestrator system.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path


@dataclass
class OrchestratorConfig:
    """
    Configuration for Phase Orchestrator.

    Attributes:
        enable_dag_tracking: Enable DAG creation and tracking
        enable_logging: Enable comprehensive logging
        enable_metrics: Enable performance metrics collection
        log_dir: Directory for log files
        max_retries: Maximum retries for failed phases
        retry_delay: Delay between retries (seconds)
        pass_context_by_default: Pass phase outputs to next phase automatically
        parallel_execution: Enable parallel execution when possible
        timeout_per_phase: Timeout for each phase (seconds, None = no timeout)
        save_dag_visualization: Save DAG as image files
        dag_output_dir: Directory for DAG visualizations
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        track_resource_usage: Track CPU/memory usage per phase
        checkpoint_interval: Save checkpoints every N phases (0 = disable)
        checkpoint_dir: Directory for checkpoint files
    """

    # Core features
    enable_dag_tracking: bool = True
    enable_logging: bool = True
    enable_metrics: bool = True

    # Directories
    log_dir: Optional[Path] = field(default_factory=lambda: Path("./orchestrator_logs"))
    dag_output_dir: Optional[Path] = field(default_factory=lambda: Path("./orchestrator_dags"))
    checkpoint_dir: Optional[Path] = field(default_factory=lambda: Path("./orchestrator_checkpoints"))

    # Execution behavior
    max_retries: int = 3
    retry_delay: float = 1.0
    pass_context_by_default: bool = True
    parallel_execution: bool = False
    timeout_per_phase: Optional[float] = 600.0  # 10 minutes

    # Visualization
    save_dag_visualization: bool = True

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Monitoring
    track_resource_usage: bool = True

    # Checkpointing
    checkpoint_interval: int = 0  # 0 = disabled
    auto_resume_from_checkpoint: bool = True

    # Advanced
    max_parallel_phases: int = 3
    phase_timeout_multiplier: float = 1.5  # Multiplier for estimated phase times
    enable_cache: bool = True  # Cache phase results
    cache_ttl: int = 3600  # Cache TTL in seconds

    # Database (optional)
    use_database: bool = False
    db_connection_string: Optional[str] = None

    def __post_init__(self):
        """Create directories if they don't exist."""
        if self.enable_logging and self.log_dir:
            self.log_dir = Path(self.log_dir)
            self.log_dir.mkdir(parents=True, exist_ok=True)

        if self.save_dag_visualization and self.dag_output_dir:
            self.dag_output_dir = Path(self.dag_output_dir)
            self.dag_output_dir.mkdir(parents=True, exist_ok=True)

        if self.checkpoint_interval > 0 and self.checkpoint_dir:
            self.checkpoint_dir = Path(self.checkpoint_dir)
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            'enable_dag_tracking': self.enable_dag_tracking,
            'enable_logging': self.enable_logging,
            'enable_metrics': self.enable_metrics,
            'log_dir': str(self.log_dir),
            'dag_output_dir': str(self.dag_output_dir),
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'pass_context_by_default': self.pass_context_by_default,
            'parallel_execution': self.parallel_execution,
            'timeout_per_phase': self.timeout_per_phase,
            'save_dag_visualization': self.save_dag_visualization,
            'log_level': self.log_level,
            'track_resource_usage': self.track_resource_usage,
            'checkpoint_interval': self.checkpoint_interval,
            'max_parallel_phases': self.max_parallel_phases,
            'enable_cache': self.enable_cache,
        }


# Predefined configurations for common use cases
DEFAULT_CONFIG = OrchestratorConfig()

DEVELOPMENT_CONFIG = OrchestratorConfig(
    enable_dag_tracking=True,
    enable_logging=True,
    enable_metrics=True,
    log_level="DEBUG",
    save_dag_visualization=True,
    track_resource_usage=True,
    max_retries=2,
)

PRODUCTION_CONFIG = OrchestratorConfig(
    enable_dag_tracking=True,
    enable_logging=True,
    enable_metrics=True,
    log_level="INFO",
    save_dag_visualization=False,
    track_resource_usage=True,
    max_retries=3,
    checkpoint_interval=5,  # Checkpoint every 5 phases
    use_database=True,  # Log to database in production
)

FAST_CONFIG = OrchestratorConfig(
    enable_dag_tracking=False,
    enable_logging=False,
    enable_metrics=False,
    save_dag_visualization=False,
    track_resource_usage=False,
    max_retries=1,
)

PARALLEL_CONFIG = OrchestratorConfig(
    enable_dag_tracking=True,
    enable_logging=True,
    enable_metrics=True,
    parallel_execution=True,
    max_parallel_phases=5,
    log_level="INFO",
)
