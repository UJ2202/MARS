"""
Backend services for CMBAgent.

This module provides production-grade service layer that integrates
with the cmbagent database infrastructure (Stages 1-9).

Services:
- WorkflowService: Manages workflow lifecycle with database integration
- ConnectionManager: Manages WebSocket connections with event protocol
- ExecutionService: Handles CMBAgent task execution
"""

from services.workflow_service import WorkflowService, workflow_service
from services.connection_manager import ConnectionManager, connection_manager
from services.execution_service import ExecutionService, execution_service

__all__ = [
    "WorkflowService",
    "workflow_service",
    "ConnectionManager", 
    "connection_manager",
    "ExecutionService",
    "execution_service",
]
