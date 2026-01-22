"""
Tracked Code Executor - AG2 Code Executor with file tracking.

This module wraps AG2's LocalCommandLineCodeExecutor to automatically
track all files generated during code execution.
"""

import os
import time
import logging
from pathlib import Path
from typing import List, Set, Optional, TYPE_CHECKING

try:
    from autogen.coding import LocalCommandLineCodeExecutor
    from autogen.coding.base import CodeBlock, CodeResult
    AG2_AVAILABLE = True
except ImportError:
    AG2_AVAILABLE = False
    # Define stub classes for type checking
    class LocalCommandLineCodeExecutor:
        pass
    class CodeBlock:
        code: str
        language: str
    class CodeResult:
        pass

if TYPE_CHECKING:
    from cmbagent.execution.file_registry import FileRegistry

logger = logging.getLogger(__name__)


class TrackedCodeExecutor:
    """
    Code executor that tracks all files generated during execution.

    Wraps AG2's LocalCommandLineCodeExecutor to:
    1. Snapshot directory before execution
    2. Execute code normally
    3. Detect new files after execution
    4. Register new files with FileRegistry
    """

    def __init__(
        self,
        work_dir: str,
        timeout: int = 120,
        file_registry: Optional['FileRegistry'] = None,
        execution_policies: dict = None,
        **kwargs
    ):
        """
        Initialize the TrackedCodeExecutor.

        Args:
            work_dir: Working directory for code execution
            timeout: Execution timeout in seconds
            file_registry: FileRegistry instance for file tracking
            execution_policies: Execution policy settings
            **kwargs: Additional arguments passed to LocalCommandLineCodeExecutor
        """
        self.work_dir = Path(work_dir)
        self.timeout = timeout
        self.file_registry = file_registry
        self.execution_policies = execution_policies or {}
        self._execution_count = 0
        self._total_files_tracked = 0
        self._kwargs = kwargs

        # Ensure work directory exists
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Initialize the underlying executor if AG2 is available
        self._executor = None
        if AG2_AVAILABLE:
            try:
                self._executor = LocalCommandLineCodeExecutor(
                    work_dir=str(self.work_dir),
                    timeout=timeout,
                    **kwargs
                )
            except Exception as e:
                logger.warning(f"Failed to initialize LocalCommandLineCodeExecutor: {e}")

        logger.info(f"TrackedCodeExecutor initialized for {work_dir}")

    @property
    def executor(self):
        """Get the underlying executor, initializing if needed."""
        if self._executor is None and AG2_AVAILABLE:
            self._executor = LocalCommandLineCodeExecutor(
                work_dir=str(self.work_dir),
                timeout=self.timeout,
                **self._kwargs
            )
        return self._executor

    def execute_code_blocks(
        self,
        code_blocks: List['CodeBlock']
    ) -> 'CodeResult':
        """
        Execute code blocks while tracking generated files.

        Args:
            code_blocks: List of CodeBlock objects to execute

        Returns:
            CodeResult from the execution
        """
        if not AG2_AVAILABLE or self.executor is None:
            raise RuntimeError("AG2 is not available or executor not initialized")

        # Snapshot before
        before_files = self._snapshot_directory()
        code_text = "\n".join(getattr(block, 'code', str(block)) for block in code_blocks)

        # Execute
        start_time = time.time()
        result = self.executor.execute_code_blocks(code_blocks)
        execution_time = time.time() - start_time

        # Snapshot after
        after_files = self._snapshot_directory()

        # Detect new files
        new_files = after_files - before_files

        # Register each new file
        if self.file_registry and new_files:
            for file_path in new_files:
                tracked = self.file_registry.register_file(
                    path=file_path,
                    generating_code=code_text
                )
                if tracked:
                    self._total_files_tracked += 1
                    logger.debug(f"Tracked new file from code execution: {tracked.relative_path}")

        self._execution_count += 1
        logger.info(
            f"Code execution #{self._execution_count}: "
            f"created {len(new_files)} files in {execution_time:.2f}s"
        )

        return result

    def _snapshot_directory(self) -> Set[str]:
        """Get all files in work_dir recursively."""
        files = set()

        if not self.work_dir.exists():
            return files

        for item in self.work_dir.rglob('*'):
            if item.is_file() and not item.name.startswith('.'):
                # Skip common temp/cache files
                if '__pycache__' in str(item):
                    continue
                if item.suffix in {'.pyc', '.pyo'}:
                    continue
                files.add(str(item))

        return files

    def get_statistics(self) -> dict:
        """Get execution statistics."""
        return {
            'execution_count': self._execution_count,
            'total_files_tracked': self._total_files_tracked,
            'work_dir': str(self.work_dir)
        }


class TrackedCodeExecutorWrapper:
    """
    Wrapper that can be used as a drop-in replacement for LocalCommandLineCodeExecutor.

    This class provides the same interface but adds file tracking capabilities.
    """

    def __init__(
        self,
        work_dir: str = None,
        timeout: int = 120,
        file_registry: Optional['FileRegistry'] = None,
        **kwargs
    ):
        """
        Initialize the wrapper.

        Args:
            work_dir: Working directory (defaults to current directory)
            timeout: Execution timeout in seconds
            file_registry: FileRegistry instance for tracking
            **kwargs: Additional arguments for the executor
        """
        self.work_dir = work_dir or os.getcwd()
        self.file_registry = file_registry
        self._tracked_executor = TrackedCodeExecutor(
            work_dir=self.work_dir,
            timeout=timeout,
            file_registry=file_registry,
            **kwargs
        )

    def execute_code_blocks(self, code_blocks) -> 'CodeResult':
        """Execute code blocks with tracking."""
        return self._tracked_executor.execute_code_blocks(code_blocks)

    def __getattr__(self, name):
        """Delegate unknown attributes to the underlying executor."""
        if hasattr(self._tracked_executor, name):
            return getattr(self._tracked_executor, name)
        if self._tracked_executor.executor and hasattr(self._tracked_executor.executor, name):
            return getattr(self._tracked_executor.executor, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


def create_tracked_executor(
    work_dir: str,
    timeout: int = 120,
    file_registry: Optional['FileRegistry'] = None,
    **kwargs
) -> TrackedCodeExecutor:
    """
    Factory function to create a TrackedCodeExecutor.

    Args:
        work_dir: Working directory for execution
        timeout: Execution timeout
        file_registry: Optional FileRegistry instance

    Returns:
        TrackedCodeExecutor instance
    """
    # Try to get global registry if none provided
    if file_registry is None:
        from cmbagent.execution.file_registry import get_global_registry
        file_registry = get_global_registry()

    return TrackedCodeExecutor(
        work_dir=work_dir,
        timeout=timeout,
        file_registry=file_registry,
        **kwargs
    )
