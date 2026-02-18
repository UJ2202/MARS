"""
Execution Configuration - Configuration for parallel execution system

This module defines configuration options for controlling parallel execution,
resource limits, and execution modes.
"""

import os
import logging
import structlog
from typing import Optional
from dataclasses import dataclass

logger = structlog.get_logger(__name__)


@dataclass
class ExecutionConfig:
    """Configuration for parallel execution system"""

    # Parallel execution settings
    enable_parallel_execution: bool = True
    max_parallel_workers: int = 3
    auto_detect_dependencies: bool = True
    use_process_pool: bool = False  # Use ThreadPoolExecutor by default

    # Resource limits
    max_memory_per_worker_mb: int = 2000
    max_disk_per_worker_mb: int = 5000
    task_timeout_seconds: int = 3600  # 1 hour max per task

    # Execution modes
    execution_mode: str = "auto"  # "auto", "sequential", "parallel"

    # Dependency analysis
    use_llm_dependency_analysis: bool = True
    dependency_analysis_model: str = "gpt-4"
    cache_dependency_analysis: bool = True

    # Work directory settings
    create_isolated_directories: bool = True
    merge_parallel_results: bool = True
    preserve_node_structure: bool = True

    # Cleanup settings
    cleanup_temp_files: bool = True
    keep_outputs: bool = True
    keep_logs: bool = True

    @classmethod
    def from_env(cls) -> "ExecutionConfig":
        """
        Create configuration from environment variables

        Environment variables:
        - CMBAGENT_ENABLE_PARALLEL: Enable parallel execution (default: true)
        - CMBAGENT_MAX_WORKERS: Maximum parallel workers (default: 3)
        - CMBAGENT_EXECUTION_MODE: Execution mode (default: auto)
        - CMBAGENT_MAX_MEMORY_MB: Max memory per worker in MB (default: 2000)
        - CMBAGENT_TASK_TIMEOUT: Task timeout in seconds (default: 3600)
        - CMBAGENT_USE_PROCESS_POOL: Use ProcessPoolExecutor (default: false)

        Returns:
            ExecutionConfig instance
        """
        config = cls()

        # Parse environment variables
        config.enable_parallel_execution = cls._get_bool_env(
            "CMBAGENT_ENABLE_PARALLEL",
            config.enable_parallel_execution
        )

        config.max_parallel_workers = cls._get_int_env(
            "CMBAGENT_MAX_WORKERS",
            config.max_parallel_workers
        )

        config.execution_mode = os.getenv(
            "CMBAGENT_EXECUTION_MODE",
            config.execution_mode
        )

        config.max_memory_per_worker_mb = cls._get_int_env(
            "CMBAGENT_MAX_MEMORY_MB",
            config.max_memory_per_worker_mb
        )

        config.task_timeout_seconds = cls._get_int_env(
            "CMBAGENT_TASK_TIMEOUT",
            config.task_timeout_seconds
        )

        config.use_process_pool = cls._get_bool_env(
            "CMBAGENT_USE_PROCESS_POOL",
            config.use_process_pool
        )

        config.auto_detect_dependencies = cls._get_bool_env(
            "CMBAGENT_AUTO_DETECT_DEPS",
            config.auto_detect_dependencies
        )

        config.use_llm_dependency_analysis = cls._get_bool_env(
            "CMBAGENT_USE_LLM_DEPS",
            config.use_llm_dependency_analysis
        )

        logger.info(f"Execution config loaded: mode={config.execution_mode}, "
                   f"max_workers={config.max_parallel_workers}, "
                   f"parallel_enabled={config.enable_parallel_execution}")

        return config

    @staticmethod
    def _get_bool_env(key: str, default: bool) -> bool:
        """Get boolean from environment variable"""
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    @staticmethod
    def _get_int_env(key: str, default: int) -> int:
        """Get integer from environment variable"""
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning(f"Invalid integer value for {key}: {value}, using default {default}")
            return default

    def validate(self) -> bool:
        """
        Validate configuration values

        Returns:
            True if valid, False otherwise
        """
        valid = True

        # Validate execution mode
        if self.execution_mode not in ("auto", "sequential", "parallel"):
            logger.error(
                f"Invalid execution_mode: {self.execution_mode}, "
                f"must be 'auto', 'sequential', or 'parallel'"
            )
            valid = False

        # Validate max_parallel_workers
        if self.max_parallel_workers < 1:
            logger.error(
                f"Invalid max_parallel_workers: {self.max_parallel_workers}, "
                f"must be >= 1"
            )
            valid = False

        if self.max_parallel_workers > 10:
            logger.warning(
                f"max_parallel_workers is high: {self.max_parallel_workers}, "
                f"may cause resource exhaustion"
            )

        # Validate resource limits
        if self.max_memory_per_worker_mb < 100:
            logger.error(
                f"Invalid max_memory_per_worker_mb: {self.max_memory_per_worker_mb}, "
                f"must be >= 100"
            )
            valid = False

        if self.task_timeout_seconds < 60:
            logger.warning(
                f"task_timeout_seconds is low: {self.task_timeout_seconds}s, "
                f"tasks may timeout prematurely"
            )

        return valid

    def to_dict(self) -> dict:
        """Convert configuration to dictionary"""
        return {
            "enable_parallel_execution": self.enable_parallel_execution,
            "max_parallel_workers": self.max_parallel_workers,
            "auto_detect_dependencies": self.auto_detect_dependencies,
            "use_process_pool": self.use_process_pool,
            "max_memory_per_worker_mb": self.max_memory_per_worker_mb,
            "max_disk_per_worker_mb": self.max_disk_per_worker_mb,
            "task_timeout_seconds": self.task_timeout_seconds,
            "execution_mode": self.execution_mode,
            "use_llm_dependency_analysis": self.use_llm_dependency_analysis,
            "dependency_analysis_model": self.dependency_analysis_model,
            "cache_dependency_analysis": self.cache_dependency_analysis,
            "create_isolated_directories": self.create_isolated_directories,
            "merge_parallel_results": self.merge_parallel_results,
            "preserve_node_structure": self.preserve_node_structure,
            "cleanup_temp_files": self.cleanup_temp_files,
            "keep_outputs": self.keep_outputs,
            "keep_logs": self.keep_logs
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"ExecutionConfig(mode={self.execution_mode}, "
            f"max_workers={self.max_parallel_workers}, "
            f"parallel={self.enable_parallel_execution})"
        )


# Default global configuration
default_config = ExecutionConfig()


def get_config() -> ExecutionConfig:
    """Get current execution configuration"""
    return default_config
