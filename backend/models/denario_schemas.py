"""
Pydantic schemas for the Denario Research Paper wizard endpoints.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class DenarioStageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Requests
# =============================================================================

class DenarioCreateRequest(BaseModel):
    """POST /api/denario/create"""
    task: str = Field(..., description="Research description / pitch")
    data_description: Optional[str] = Field(None, description="Optional description of uploaded data")
    config: Optional[Dict[str, Any]] = Field(None, description="Optional model overrides")


class DenarioExecuteRequest(BaseModel):
    """POST /api/denario/{task_id}/stages/{num}/execute"""
    config_overrides: Optional[Dict[str, Any]] = Field(None, description="Per-stage model overrides")


class DenarioContentUpdateRequest(BaseModel):
    """PUT /api/denario/{task_id}/stages/{num}/content"""
    content: str = Field(..., description="Updated markdown content")
    field: str = Field("research_idea", description="shared_state key to update (research_idea, methodology, results)")


class DenarioRefineRequest(BaseModel):
    """POST /api/denario/{task_id}/stages/{num}/refine"""
    message: str = Field(..., description="User instruction for the LLM")
    content: str = Field(..., description="Current editor content to refine")


# =============================================================================
# Responses
# =============================================================================

class DenarioStageResponse(BaseModel):
    """Single stage info in responses."""
    stage_number: int
    stage_name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class DenarioCreateResponse(BaseModel):
    """Response for POST /api/denario/create"""
    task_id: str
    work_dir: str
    stages: List[DenarioStageResponse]


class DenarioStageContentResponse(BaseModel):
    """Response for GET /api/denario/{task_id}/stages/{num}/content"""
    stage_number: int
    stage_name: str
    status: str
    content: Optional[str] = None
    shared_state: Optional[Dict[str, Any]] = None
    output_files: Optional[List[str]] = None


class DenarioRefineResponse(BaseModel):
    """Response for POST /api/denario/{task_id}/stages/{num}/refine"""
    refined_content: str
    message: str = "Content refined successfully"


class DenarioTaskStateResponse(BaseModel):
    """Response for GET /api/denario/{task_id} - full task state for resume."""
    task_id: str
    task: str
    status: str
    work_dir: Optional[str] = None
    created_at: Optional[str] = None
    stages: List[DenarioStageResponse]
    current_stage: Optional[int] = None
    progress_percent: float = 0.0
    total_cost_usd: Optional[float] = None


class DenarioRecentTaskResponse(BaseModel):
    """Single item in GET /api/denario/recent list."""
    task_id: str
    task: str
    status: str
    created_at: Optional[str] = None
    current_stage: Optional[int] = None
    progress_percent: float = 0.0
