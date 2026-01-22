"""
Parallel Executor - Execute independent tasks concurrently

This module provides parallel execution of independent workflow tasks
using process isolation for safety.
"""

import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional
from multiprocessing import Queue

logger = logging.getLogger(__name__)


class ParallelExecutor:
    """Execute independent tasks in parallel with resource management"""

    def __init__(
        self,
        max_workers: int = 3,
        resource_limits: Optional[Dict[str, Any]] = None,
        use_processes: bool = False
    ):
        """
        Initialize parallel executor

        Args:
            max_workers: Maximum number of parallel workers (default: 3)
            resource_limits: Resource limits per worker
            use_processes: Use ProcessPoolExecutor instead of ThreadPoolExecutor
        """
        self.max_workers = max_workers
        self.use_processes = use_processes
        self.resource_limits = resource_limits or {
            "max_memory_per_worker_mb": 2000,
            "max_disk_per_worker_mb": 5000,
            "timeout_seconds": 3600  # 1 hour max per task
        }
        self.active_workers: Dict[str, Dict[str, Any]] = {}
        self.result_queue: Optional[Queue] = None

    async def execute_dag_levels(
        self,
        levels: List[List[str]],
        executor_func: Callable[[str], Any],
        skip_single_task_parallelism: bool = True
    ) -> Dict[str, Any]:
        """
        Execute DAG level by level with parallelism within each level

        Args:
            levels: List of levels, each containing node IDs that can run in parallel
                    Example: [["node_1", "node_2"], ["node_3"], ["node_4", "node_5"]]
            executor_func: Function to execute a single task
                          Signature: func(node_id) -> result
            skip_single_task_parallelism: Don't use parallelism for single-task levels

        Returns:
            Dictionary with execution results per node
        """
        results = {}
        total_tasks = sum(len(level) for level in levels)

        logger.info(
            f"Executing DAG: {len(levels)} levels, {total_tasks} total tasks, "
            f"max {self.max_workers} parallel workers"
        )

        for level_index, node_ids in enumerate(levels):
            logger.info(
                f"Executing level {level_index}: {len(node_ids)} tasks "
                f"(parallel={len(node_ids) > 1})"
            )

            start_time = time.time()

            if len(node_ids) == 1 and skip_single_task_parallelism:
                # Single task - execute directly (no parallelism overhead)
                node_id = node_ids[0]
                try:
                    result = executor_func(node_id)
                    results[node_id] = {
                        "status": "success",
                        "result": result
                    }
                except Exception as e:
                    logger.error(f"Task {node_id} failed: {e}")
                    results[node_id] = {
                        "status": "failed",
                        "error": str(e)
                    }
            else:
                # Multiple tasks - execute in parallel
                level_results = self._execute_parallel_tasks(
                    node_ids,
                    executor_func
                )
                results.update(level_results)

            elapsed = time.time() - start_time
            logger.info(
                f"Level {level_index} complete: {len(node_ids)} tasks "
                f"finished in {elapsed:.2f}s"
            )

        return results

    def execute_dag_levels_sync(
        self,
        levels: List[List[str]],
        executor_func: Callable[[str], Any],
        skip_single_task_parallelism: bool = True
    ) -> Dict[str, Any]:
        """
        Synchronous version of execute_dag_levels (no async/await)

        Args:
            levels: List of levels with node IDs
            executor_func: Function to execute a single task
            skip_single_task_parallelism: Skip parallelism for single tasks

        Returns:
            Dictionary with execution results per node
        """
        results = {}
        total_tasks = sum(len(level) for level in levels)

        logger.info(
            f"Executing DAG: {len(levels)} levels, {total_tasks} total tasks, "
            f"max {self.max_workers} parallel workers"
        )

        for level_index, node_ids in enumerate(levels):
            logger.info(
                f"Executing level {level_index}: {len(node_ids)} tasks "
                f"(parallel={len(node_ids) > 1})"
            )

            start_time = time.time()

            if len(node_ids) == 1 and skip_single_task_parallelism:
                # Single task - execute directly
                node_id = node_ids[0]
                try:
                    result = executor_func(node_id)
                    results[node_id] = {
                        "status": "success",
                        "result": result
                    }
                except Exception as e:
                    logger.error(f"Task {node_id} failed: {e}")
                    results[node_id] = {
                        "status": "failed",
                        "error": str(e)
                    }
            else:
                # Multiple tasks - execute in parallel
                level_results = self._execute_parallel_tasks(
                    node_ids,
                    executor_func
                )
                results.update(level_results)

            elapsed = time.time() - start_time
            logger.info(
                f"Level {level_index} complete: {len(node_ids)} tasks "
                f"finished in {elapsed:.2f}s"
            )

        return results

    def _execute_parallel_tasks(
        self,
        node_ids: List[str],
        executor_func: Callable[[str], Any]
    ) -> Dict[str, Any]:
        """
        Execute multiple tasks in parallel

        Args:
            node_ids: List of node IDs to execute
            executor_func: Function to execute each task

        Returns:
            Dictionary mapping node_id to result
        """
        results = {}
        timeout = self.resource_limits.get("timeout_seconds", 3600)

        # Choose executor type
        if self.use_processes:
            executor_class = ProcessPoolExecutor
        else:
            executor_class = ThreadPoolExecutor

        with executor_class(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_node = {
                executor.submit(
                    self._isolated_task_wrapper,
                    node_id,
                    executor_func
                ): node_id
                for node_id in node_ids
            }

            # Collect results as they complete
            for future in as_completed(future_to_node, timeout=timeout):
                node_id = future_to_node[future]
                try:
                    result = future.result(timeout=timeout)
                    results[node_id] = result
                    logger.info(
                        f"Task {node_id} completed with status: {result['status']}"
                    )
                except Exception as e:
                    logger.error(f"Task {node_id} failed with exception: {e}")
                    results[node_id] = {
                        "status": "failed",
                        "error": str(e),
                        "node_id": node_id
                    }

        return results

    def _isolated_task_wrapper(
        self,
        node_id: str,
        executor_func: Callable[[str], Any]
    ) -> Dict[str, Any]:
        """
        Wrapper that provides isolation for task execution

        Args:
            node_id: Node ID
            executor_func: Function to execute

        Returns:
            Result dictionary with status, result, and resource info
        """
        start_time = time.time()
        start_memory = 0
        end_memory = 0

        try:
            # Try to monitor resources (optional dependency)
            try:
                import psutil
                process = psutil.Process()
                start_memory = process.memory_info().rss / 1024 / 1024  # MB
            except ImportError:
                pass

            # Execute task
            result = executor_func(node_id)

            # Check resource usage
            try:
                import psutil
                process = psutil.Process()
                end_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_used = end_memory - start_memory

                max_memory = self.resource_limits["max_memory_per_worker_mb"]
                if memory_used > max_memory:
                    logger.warning(
                        f"Task {node_id} exceeded memory limit: "
                        f"{memory_used:.1f} MB > {max_memory} MB"
                    )
            except ImportError:
                memory_used = 0

            elapsed = time.time() - start_time

            return {
                "status": "success",
                "result": result,
                "node_id": node_id,
                "resources": {
                    "memory_mb": memory_used,
                    "elapsed_seconds": elapsed
                }
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Task {node_id} failed after {elapsed:.2f}s: {e}")

            return {
                "status": "failed",
                "error": str(e),
                "node_id": node_id,
                "resources": {
                    "elapsed_seconds": elapsed
                }
            }

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
            optimal = min(cpu_count - 1, memory_based, self.max_workers)

            # At least 1 worker
            return max(1, optimal)

        except ImportError:
            # Default to max_workers if psutil not available
            return self.max_workers
