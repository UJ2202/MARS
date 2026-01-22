"""
Resource Manager - Manage resources for concurrent agent execution

This module prevents resource exhaustion during parallel execution by
monitoring and limiting memory, CPU, and disk usage.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ResourceExhaustedError(Exception):
    """Raised when system resources are exhausted"""
    pass


class ResourceManager:
    """Manages system resources for parallel execution"""

    def __init__(
        self,
        max_concurrent_agents: int = 3,
        max_memory_mb: Optional[int] = None,
        max_disk_mb: Optional[int] = None
    ):
        """
        Initialize resource manager

        Args:
            max_concurrent_agents: Maximum concurrent agent executions
            max_memory_mb: Maximum total memory usage in MB (None = auto)
            max_disk_mb: Maximum disk usage in MB (None = auto)
        """
        self.max_concurrent = max_concurrent_agents
        self.max_memory_mb = max_memory_mb
        self.max_disk_mb = max_disk_mb

        # Semaphore for limiting concurrent tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_agents)

        # Track active tasks
        self.active_tasks: Dict[str, Dict[str, Any]] = {}

        # Get system resource info
        self.resource_stats = self._get_system_resources()

        logger.info(
            f"Resource manager initialized: max_concurrent={max_concurrent_agents}, "
            f"available_memory={self.resource_stats['available_memory_mb']:.0f}MB"
        )

    async def acquire(
        self,
        task_id: str,
        estimated_memory_mb: int = 500
    ) -> None:
        """
        Acquire resources for task execution

        Args:
            task_id: Task identifier
            estimated_memory_mb: Estimated memory usage for task

        Raises:
            ResourceExhaustedError: If insufficient resources available
        """
        # Check if resources available
        if not self._check_resources_available(estimated_memory_mb):
            raise ResourceExhaustedError(
                f"Insufficient resources for task {task_id}: "
                f"estimated {estimated_memory_mb}MB, "
                f"available {self.resource_stats['available_memory_mb']:.0f}MB"
            )

        # Acquire semaphore slot
        await self.semaphore.acquire()

        # Track task
        self.active_tasks[task_id] = {
            "started_at": datetime.utcnow(),
            "estimated_memory_mb": estimated_memory_mb
        }

        logger.debug(
            f"Resources acquired for task {task_id} "
            f"({len(self.active_tasks)}/{self.max_concurrent} slots used)"
        )

    def acquire_sync(
        self,
        task_id: str,
        estimated_memory_mb: int = 500
    ) -> None:
        """
        Synchronous version of acquire (for non-async code)

        Args:
            task_id: Task identifier
            estimated_memory_mb: Estimated memory usage

        Raises:
            ResourceExhaustedError: If insufficient resources available
        """
        # Check resources
        if not self._check_resources_available(estimated_memory_mb):
            raise ResourceExhaustedError(
                f"Insufficient resources for task {task_id}"
            )

        # Track task (no semaphore in sync version)
        self.active_tasks[task_id] = {
            "started_at": datetime.utcnow(),
            "estimated_memory_mb": estimated_memory_mb
        }

        logger.debug(f"Resources acquired for task {task_id} (sync)")

    def release(self, task_id: str) -> None:
        """
        Release resources after task completion

        Args:
            task_id: Task identifier
        """
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]

        # Release semaphore
        try:
            self.semaphore.release()
        except RuntimeError:
            # Semaphore not acquired (sync mode)
            pass

        logger.debug(
            f"Resources released for task {task_id} "
            f"({len(self.active_tasks)}/{self.max_concurrent} slots used)"
        )

    def _check_resources_available(self, estimated_memory_mb: int) -> bool:
        """
        Check if system has enough resources

        Args:
            estimated_memory_mb: Estimated memory requirement

        Returns:
            True if resources available, False otherwise
        """
        # Update resource stats
        self.resource_stats = self._get_system_resources()

        available_memory = self.resource_stats["available_memory_mb"]

        # Reserve 20% for system
        safe_available = available_memory * 0.8

        # Check current usage
        current_usage = sum(
            task["estimated_memory_mb"]
            for task in self.active_tasks.values()
        )

        # Check if we have enough
        total_required = current_usage + estimated_memory_mb

        if total_required > safe_available:
            logger.warning(
                f"Insufficient memory: {total_required}MB required, "
                f"{safe_available:.0f}MB available"
            )
            return False

        # Check max_memory_mb limit if set
        if self.max_memory_mb and total_required > self.max_memory_mb:
            logger.warning(
                f"Memory limit exceeded: {total_required}MB > {self.max_memory_mb}MB"
            )
            return False

        return True

    def get_optimal_worker_count(self) -> int:
        """
        Calculate optimal number of parallel workers based on system resources

        Returns:
            Recommended worker count
        """
        try:
            import psutil

            cpu_count = psutil.cpu_count()
            available_memory_gb = psutil.virtual_memory().available / 1024 / 1024 / 1024

            # Assume each agent needs ~2GB RAM
            memory_based = int(available_memory_gb / 2)

            # Conservative: min of CPU-based and memory-based
            optimal = min(cpu_count - 1, memory_based, self.max_concurrent)

            # At least 1 worker
            return max(1, optimal)

        except ImportError:
            # Default to max_concurrent if psutil not available
            return self.max_concurrent

    def _get_system_resources(self) -> Dict[str, float]:
        """
        Get current system resource statistics

        Returns:
            Dictionary with resource stats
        """
        try:
            import psutil

            # Memory stats
            mem = psutil.virtual_memory()
            total_memory_mb = mem.total / 1024 / 1024
            available_memory_mb = mem.available / 1024 / 1024
            used_memory_mb = mem.used / 1024 / 1024

            # Disk stats
            disk = psutil.disk_usage('/')
            total_disk_mb = disk.total / 1024 / 1024
            available_disk_mb = disk.free / 1024 / 1024

            # CPU stats
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()

            return {
                "total_memory_mb": total_memory_mb,
                "available_memory_mb": available_memory_mb,
                "used_memory_mb": used_memory_mb,
                "memory_percent": mem.percent,
                "total_disk_mb": total_disk_mb,
                "available_disk_mb": available_disk_mb,
                "disk_percent": disk.percent,
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count
            }

        except ImportError:
            # psutil not available - return defaults
            logger.warning("psutil not available, using default resource estimates")
            return {
                "total_memory_mb": 8192,  # Assume 8GB
                "available_memory_mb": 4096,  # Assume 4GB available
                "used_memory_mb": 4096,
                "memory_percent": 50.0,
                "total_disk_mb": 102400,  # Assume 100GB
                "available_disk_mb": 51200,  # Assume 50GB available
                "disk_percent": 50.0,
                "cpu_percent": 50.0,
                "cpu_count": 4
            }

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get current resource usage statistics

        Returns:
            Dictionary with usage stats
        """
        current_usage = sum(
            task["estimated_memory_mb"]
            for task in self.active_tasks.values()
        )

        return {
            "active_tasks": len(self.active_tasks),
            "max_concurrent": self.max_concurrent,
            "slots_available": self.max_concurrent - len(self.active_tasks),
            "estimated_memory_mb": current_usage,
            "system_resources": self.resource_stats,
            "tasks": list(self.active_tasks.keys())
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"ResourceManager(active={len(self.active_tasks)}, "
            f"max={self.max_concurrent})"
        )
