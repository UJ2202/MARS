"""
Task submission endpoints.
"""

import uuid
from fastapi import APIRouter

from models.schemas import TaskRequest, TaskResponse

router = APIRouter(prefix="/api/task", tags=["Tasks"])


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
