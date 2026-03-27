"""
Pydantic schemas for the RFP (Request for Proposal) Proposal Generator endpoints.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class RfpStageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Requests
# =============================================================================

class RfpCreateRequest(BaseModel):
    """POST /api/rfp/create"""
    task: str = Field("", description="RFP description or pasted RFP text")
    rfp_context: Optional[str] = Field(None, description="Additional context about the RFP or the organization")
    config: Optional[Dict[str, Any]] = Field(None, description="Optional model overrides")
    work_dir: Optional[str] = Field(None, description="Base work directory. Falls back to CMBAGENT_DEFAULT_WORK_DIR")


class RfpExecuteRequest(BaseModel):
    """POST /api/rfp/{task_id}/stages/{num}/execute"""
    config_overrides: Optional[Dict[str, Any]] = Field(None, description="Per-stage model overrides")


class RfpContentUpdateRequest(BaseModel):
    """PUT /api/rfp/{task_id}/stages/{num}/content"""
    content: str = Field(..., description="Updated markdown content")
    field: str = Field("requirements_analysis", description="shared_state key to update")


class RfpRefineRequest(BaseModel):
    """POST /api/rfp/{task_id}/stages/{num}/refine"""
    message: str = Field(..., description="User instruction for the LLM")
    content: str = Field(..., description="Current editor content to refine")


# =============================================================================
# Responses
# =============================================================================

class RfpStageResponse(BaseModel):
    """Single stage info in responses."""
    stage_number: int
    stage_name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class RfpCreateResponse(BaseModel):
    """Response for POST /api/rfp/create"""
    task_id: str
    work_dir: str
    stages: List[RfpStageResponse]


class RfpStageContentResponse(BaseModel):
    """Response for GET /api/rfp/{task_id}/stages/{num}/content"""
    stage_number: int
    stage_name: str
    status: str
    content: Optional[str] = None
    shared_state: Optional[Dict[str, Any]] = None
    output_files: Optional[List[str]] = None


class RfpRefineResponse(BaseModel):
    """Response for POST /api/rfp/{task_id}/stages/{num}/refine"""
    refined_content: str
    message: str = "Content refined successfully"


class RfpTaskStateResponse(BaseModel):
    """Response for GET /api/rfp/{task_id} - full task state for resume."""
    task_id: str
    task: str
    status: str
    work_dir: Optional[str] = None
    created_at: Optional[str] = None
    stages: List[RfpStageResponse]
    current_stage: Optional[int] = None
    progress_percent: float = 0.0
    total_cost_usd: Optional[float] = None


class RfpRecentTaskResponse(BaseModel):
    """Response for GET /api/rfp/recent"""
    task_id: str
    task: str
    status: str
    created_at: Optional[str] = None
    current_stage: Optional[int] = None
    progress_percent: float = 0.0
