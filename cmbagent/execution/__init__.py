"""
CMBAgent Execution Module

This module contains components for advanced workflow execution including:
- Dependency analysis
- Parallel execution
- Resource management
- Work directory management
- Event capture and AG2 hooks
- File tracking and output collection
"""

from cmbagent.execution.dependency_analyzer import DependencyAnalyzer
from cmbagent.execution.dependency_graph import DependencyGraph, CircularDependencyError
from cmbagent.execution.parallel_executor import ParallelExecutor
from cmbagent.execution.work_directory_manager import WorkDirectoryManager
from cmbagent.execution.resource_manager import ResourceManager
from cmbagent.execution.config import ExecutionConfig
from cmbagent.execution.event_capture import (
    EventCaptureManager,
    get_event_captor,
    set_event_captor
)
from cmbagent.execution.ag2_hooks import (
    install_ag2_hooks,
    uninstall_ag2_hooks
)
from cmbagent.execution.callback_integration import (
    create_callbacks_with_event_capture
)

# File tracking system components
from cmbagent.execution.file_registry import (
    FileRegistry,
    FileCategory,
    OutputPriority,
    TrackedFile,
    get_global_registry,
    set_global_registry
)
from cmbagent.execution.tracked_code_executor import (
    TrackedCodeExecutor,
    TrackedCodeExecutorWrapper,
    create_tracked_executor
)
from cmbagent.execution.output_collector import (
    OutputCollector,
    WorkflowOutputs,
    WorkflowOutputManager,
    create_output_manager
)

__all__ = [
    # Dependency analysis
    "DependencyAnalyzer",
    "DependencyGraph",
    "CircularDependencyError",
    # Execution
    "ParallelExecutor",
    "WorkDirectoryManager",
    "ResourceManager",
    "ExecutionConfig",
    # Event capture
    "EventCaptureManager",
    "get_event_captor",
    "set_event_captor",
    # AG2 hooks
    "install_ag2_hooks",
    "uninstall_ag2_hooks",
    "create_callbacks_with_event_capture",
    # File tracking system
    "FileRegistry",
    "FileCategory",
    "OutputPriority",
    "TrackedFile",
    "get_global_registry",
    "set_global_registry",
    "TrackedCodeExecutor",
    "TrackedCodeExecutorWrapper",
    "create_tracked_executor",
    "OutputCollector",
    "WorkflowOutputs",
    "WorkflowOutputManager",
    "create_output_manager",
]
