"""
Copilot API endpoints.

This module provides endpoints for the copilot workflow mode:
- Submit copilot tasks
- Get available agents
- Get copilot workflow info
"""

import uuid
from typing import Dict, Any, List
from datetime import datetime
from fastapi import APIRouter, HTTPException

from models.copilot_schemas import (
    CopilotConfig,
    CopilotTaskRequest,
    CopilotTaskResponse,
    CopilotWorkflowInfo,
    CopilotAgentInfo,
    AvailableAgentsResponse,
)

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])


# In-memory storage for copilot sessions
copilot_sessions: Dict[str, Dict[str, Any]] = {}


@router.post("/submit", response_model=CopilotTaskResponse)
async def submit_copilot_task(request: CopilotTaskRequest):
    """Submit a task for copilot execution.

    The copilot automatically analyzes task complexity and routes:
    - Simple tasks → Direct one-shot execution
    - Complex tasks → Planning → HITL approval → Step execution

    Returns a task_id that can be used to connect via WebSocket
    for real-time updates and HITL interactions.
    """
    task_id = f"copilot_{uuid.uuid4()}"

    # Convert config to dict with mode set to copilot
    config_dict = request.config.dict()
    config_dict['mode'] = 'copilot'

    # Store session info
    copilot_sessions[task_id] = {
        'task_id': task_id,
        'task': request.task,
        'status': 'created',
        'created_at': datetime.now().isoformat(),
        'config': config_dict,
    }

    return CopilotTaskResponse(
        task_id=task_id,
        status="submitted",
        message="Copilot task submitted. Connect to WebSocket for real-time updates.",
        mode="copilot"
    )


@router.get("/agents", response_model=AvailableAgentsResponse)
async def get_available_agents():
    """Get list of available agents for copilot mode.

    Returns core agents (always available) and domain-specific agents
    that can be optionally enabled.
    """
    core_agents = [
        CopilotAgentInfo(
            name="engineer",
            description="Writes and executes code, analyzes data, builds solutions",
            default_model="gpt-4.1-2025-04-14",
            capabilities=["code_execution", "file_operations", "data_analysis"]
        ),
        CopilotAgentInfo(
            name="researcher",
            description="Searches for information, analyzes documents, summarizes content",
            default_model="gpt-4.1-2025-04-14",
            capabilities=["web_search", "document_analysis", "summarization"]
        ),
        CopilotAgentInfo(
            name="planner",
            description="Creates structured plans for complex multi-step tasks",
            default_model="gpt-4.1-2025-04-14",
            capabilities=["task_decomposition", "resource_allocation", "scheduling"]
        ),
        CopilotAgentInfo(
            name="web_surfer",
            description="Browses websites and extracts information",
            default_model="gpt-4.1-2025-04-14",
            capabilities=["web_browsing", "content_extraction", "form_filling"]
        ),
    ]

    domain_agents = [
        CopilotAgentInfo(
            name="idea_maker",
            description="Generates creative ideas and solutions",
            default_model="gpt-4.1-2025-04-14",
            capabilities=["brainstorming", "creative_thinking", "solution_generation"]
        ),
        CopilotAgentInfo(
            name="idea_hater",
            description="Critically evaluates ideas and finds weaknesses",
            default_model="o3-mini-2025-01-31",
            capabilities=["critical_analysis", "risk_assessment", "devil_advocate"]
        ),
        CopilotAgentInfo(
            name="camb_context",
            description="Provides context about CAMB cosmology code",
            default_model="gpt-4.1-2025-04-14",
            capabilities=["cosmology", "camb_expertise", "physics"]
        ),
    ]

    return AvailableAgentsResponse(
        core_agents=core_agents,
        domain_agents=domain_agents
    )


@router.get("/workflows", response_model=List[CopilotWorkflowInfo])
async def get_copilot_workflows():
    """Get available copilot workflow presets."""
    return [
        CopilotWorkflowInfo(
            id="copilot",
            name="Copilot Assistant",
            description="Flexible assistant that adapts to task complexity",
            default_config=CopilotConfig(
                enablePlanning=True,
                approvalMode="after_step",
                continuousMode=False,
            )
        ),
        CopilotWorkflowInfo(
            id="copilot_continuous",
            name="Interactive Session",
            description="Continuous copilot session - keeps running until exit",
            default_config=CopilotConfig(
                enablePlanning=True,
                continuousMode=True,
                maxTurns=50,
                approvalMode="after_step",
            )
        ),
        CopilotWorkflowInfo(
            id="copilot_simple",
            name="Quick Task",
            description="Direct execution without planning",
            default_config=CopilotConfig(
                enablePlanning=False,
                approvalMode="none",
                autoApproveSimple=True,
            )
        ),
        CopilotWorkflowInfo(
            id="copilot_interactive",
            name="Interactive Copilot",
            description="True conversational copilot - proposes before acting, reviews after",
            default_config=CopilotConfig(
                enablePlanning=True,
                approvalMode="conversational",
                continuousMode=True,
                maxTurns=50,
            )
        ),
    ]


@router.get("/session/{task_id}")
async def get_copilot_session(task_id: str):
    """Get information about a copilot session."""
    if task_id not in copilot_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return copilot_sessions[task_id]


@router.delete("/session/{task_id}")
async def end_copilot_session(task_id: str):
    """End a copilot session."""
    if task_id not in copilot_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    copilot_sessions[task_id]['status'] = 'ended'
    copilot_sessions[task_id]['ended_at'] = datetime.now().isoformat()

    return {"status": "ended", "task_id": task_id}


@router.get("/config/defaults", response_model=CopilotConfig)
async def get_default_config():
    """Get the default copilot configuration."""
    return CopilotConfig()
