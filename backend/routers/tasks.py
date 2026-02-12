"""
Task submission endpoints.
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.schemas import TaskRequest, TaskResponse

from core.logging import get_logger
logger = get_logger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# In-memory storage for task statuses and results
# In production, this should use a database
task_storage: Dict[str, Dict[str, Any]] = {}


class AIWeeklyRequest(BaseModel):
    """Request model for AI Weekly task."""
    tool: str
    parameters: Dict[str, Any]


class AIWeeklyResponse(BaseModel):
    """Response model for AI Weekly task creation."""
    task_id: str
    status: str
    message: str


class TaskConfig(BaseModel):
    """Task configuration for execution."""
    description: str
    config: Dict[str, Any]


@router.post("/submit", response_model=TaskResponse)
async def submit_task(request: TaskRequest):
    """Submit a task for execution.

    Returns a task_id that can be used to connect via WebSocket
    for real-time updates.
    """
    task_id = str(uuid.uuid4())

    return TaskResponse(
        task_id=task_id,
        status="submitted",
        message="Task submitted successfully. Connect to WebSocket for real-time updates."
    )


@router.post("/ai-weekly/execute", response_model=AIWeeklyResponse)
async def execute_ai_weekly(request: AIWeeklyRequest):
    """Create and prepare an AI Weekly report task.
    
    This endpoint creates a task configuration that can be executed
    via WebSocket connection.
    """
    task_id = f"ai-weekly_{uuid.uuid4()}"
    
    params = request.parameters
    date_from = params.get('dateFrom', '')
    date_to = params.get('dateTo', '')
    topics = params.get('topics', [])
    sources = params.get('sources', [])
    style = params.get('style', 'concise')
    
    # Create task description
    description = (
        f"Generate an AI Weekly report for {date_from} to {date_to}. "
        f"Topics: {', '.join(topics)}. Sources: {', '.join(sources)}. "
        f"Style: {style}."
    )
    
    # Store task information
    task_storage[task_id] = {
        'task_id': task_id,
        'tool': 'ai-weekly',
        'status': 'created',
        'created_at': datetime.now().isoformat(),
        'parameters': params,
        'description': description,
        'config': {
            'mode': 'planning-control',
            'model': params.get('model', 'gpt-4o'),
            'plannerModel': params.get('plannerModel', 'gpt-4o'),
            'researcherModel': params.get('researcherModel', 'gpt-4o'),
            'engineerModel': params.get('engineerModel', 'gpt-4o'),
            'planReviewerModel': params.get('planReviewerModel', 'o3-mini-2025-01-31'),
            'defaultModel': params.get('defaultModel', 'gpt-4.1-2025-04-14'),
            'defaultFormatterModel': params.get('defaultFormatterModel', 'o3-mini-2025-01-31'),
            'maxRounds': 25,
            'maxAttempts': 6,
            'maxPlanSteps': params.get('maxPlanSteps', 3),
            'nPlanReviews': params.get('nPlanReviews', 1),
            'planInstructions': params.get('planInstructions', 'Use researcher to gather information from specified sources, then use engineer to analyze and write the report.'),
            'agent': 'planner',
            'workDir': params.get('workDir') or '~/cmbagent_workdir'
        }
    }
    
    return AIWeeklyResponse(
        task_id=task_id,
        status='created',
        message=f'AI Weekly task created successfully. Use task_id {task_id} to connect via WebSocket.'
    )


@router.get("/tasks/{task_id}/config")
async def get_task_config(task_id: str):
    """Get the configuration for a specific task."""
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = task_storage[task_id]
    config = task['config']
    
    # Debug logging
    logger.debug("task_config_requested", task_id=task_id, mode=config.get('mode'), config_keys=list(config.keys()))

    return {
        'task_id': task_id,
        'description': task['description'],
        'config': config
    }


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """Get the status and results of a task."""
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = task_storage[task_id]
    return {
        'task_id': task_id,
        'status': task.get('status', 'unknown'),
        'result': task.get('result'),
        'error': task.get('error'),
        'updated_at': task.get('updated_at')
    }


@router.post("/tasks/{task_id}/result")
async def update_task_result(task_id: str, result: Dict[str, Any]):
    """Update the result for a completed task."""
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_storage[task_id]['result'] = result
    task_storage[task_id]['status'] = 'completed'
    task_storage[task_id]['updated_at'] = datetime.now().isoformat()
    
    return {'success': True, 'message': 'Task result updated'}
