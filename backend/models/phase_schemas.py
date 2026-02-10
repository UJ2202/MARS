"""
Pydantic schemas for Phase-based workflow API.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, ConfigDict, Field
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class PhaseStatusEnum(str, Enum):
    """Status of a phase execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"


class CheckpointTypeEnum(str, Enum):
    """Types of HITL checkpoints."""
    AFTER_PLANNING = "after_planning"
    BEFORE_STEP = "before_step"
    AFTER_STEP = "after_step"
    BEFORE_EXECUTION = "before_execution"
    AFTER_EXECUTION = "after_execution"
    CUSTOM = "custom"


# =============================================================================
# Phase Definition Models
# =============================================================================

class PhaseDefinitionResponse(BaseModel):
    """Response model for a phase definition."""
    type: str = Field(..., description="Unique identifier for the phase type")
    display_name: str = Field(..., description="Human-readable name")
    required_agents: List[str] = Field(default_factory=list, description="Agents this phase requires")


class PhaseConfigBase(BaseModel):
    """Base configuration for phases."""
    enabled: bool = True
    timeout_seconds: int = 3600
    max_retries: int = 0
    model_overrides: Dict[str, str] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)


class PlanningPhaseConfigRequest(PhaseConfigBase):
    """Configuration for planning phase."""
    max_rounds: int = 50
    max_plan_steps: int = 3
    n_plan_reviews: int = 1
    planner_model: Optional[str] = None
    plan_reviewer_model: Optional[str] = None
    plan_instructions: str = ""
    hardware_constraints: str = ""
    engineer_instructions: str = ""
    researcher_instructions: str = ""
    max_n_attempts: int = 3


class ControlPhaseConfigRequest(PhaseConfigBase):
    """Configuration for control phase."""
    max_rounds: int = 100
    max_n_attempts: int = 3
    execute_all_steps: bool = True
    step_number: Optional[int] = None
    hitl_enabled: bool = False
    hitl_after_each_step: bool = False
    engineer_model: Optional[str] = None
    researcher_model: Optional[str] = None
    engineer_instructions: str = ""
    researcher_instructions: str = ""


class OneShotPhaseConfigRequest(PhaseConfigBase):
    """Configuration for one-shot phase."""
    max_rounds: int = 50
    max_n_attempts: int = 3
    agent: str = "engineer"
    model: Optional[str] = None
    evaluate_plots: bool = False
    max_n_plot_evals: int = 1
    researcher_filename: str = "researcher_output.md"
    clear_work_dir: bool = False


class HITLCheckpointConfigRequest(PhaseConfigBase):
    """Configuration for HITL checkpoint phase."""
    checkpoint_type: CheckpointTypeEnum = CheckpointTypeEnum.AFTER_PLANNING
    require_approval: bool = True
    timeout_seconds: int = 3600
    default_on_timeout: str = "reject"
    show_plan: bool = True
    show_context: bool = False
    custom_message: str = ""
    options: List[str] = Field(default_factory=lambda: ["approve", "reject", "modify"])


class IdeaGenerationConfigRequest(PhaseConfigBase):
    """Configuration for idea generation phase."""
    max_rounds: int = 50
    n_ideas: int = 3
    n_reviews: int = 1
    idea_maker_model: Optional[str] = None
    idea_hater_model: Optional[str] = None


# =============================================================================
# Workflow Definition Models
# =============================================================================

class PhaseDefinitionRequest(BaseModel):
    """A phase definition within a workflow."""
    type: str = Field(..., description="Phase type (planning, control, one_shot, etc.)")
    config: Dict[str, Any] = Field(default_factory=dict, description="Phase configuration")


class WorkflowDefinitionCreate(BaseModel):
    """Request model for creating a custom workflow."""
    name: str = Field(..., description="Human-readable workflow name")
    description: str = Field(..., description="Description of workflow purpose")
    phases: List[PhaseDefinitionRequest] = Field(..., description="Ordered list of phases")


class WorkflowDefinitionResponse(BaseModel):
    """Response model for a workflow definition."""
    id: str
    name: str
    description: str
    phases: List[Dict[str, Any]]
    version: int = 1
    is_system: bool = False
    created_by: Optional[str] = None


class WorkflowListItemResponse(BaseModel):
    """Summarized workflow info for listings."""
    id: str
    name: str
    description: str
    num_phases: int
    is_system: bool


# =============================================================================
# Workflow Execution Models
# =============================================================================

class WorkflowRunRequest(BaseModel):
    """Request model for starting a workflow run."""
    task: str = Field(..., description="Task description to execute")
    work_dir: Optional[str] = Field(None, description="Working directory (defaults to ~/cmbagent_workdir)")
    config_overrides: Optional[Dict[str, Any]] = Field(None, description="Override phase configurations")
    hitl_enabled: bool = Field(False, description="Enable human-in-the-loop checkpoints")


class WorkflowRunResponse(BaseModel):
    """Response model for workflow run initiation."""
    run_id: str
    workflow_id: str
    workflow_name: str
    status: str
    message: str
    num_phases: int


class PhaseExecutionResponse(BaseModel):
    """Response model for phase execution status."""
    phase_id: str
    phase_type: str
    display_name: str
    status: PhaseStatusEnum
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    timing: Optional[Dict[str, float]] = None


class WorkflowRunStatusResponse(BaseModel):
    """Response model for workflow run status."""
    run_id: str
    workflow_id: str
    status: str
    current_phase: int
    total_phases: int
    phase_results: List[PhaseExecutionResponse]
    total_time: Optional[float] = None


# =============================================================================
# Phase Registry Models
# =============================================================================

class PhaseTypeInfo(BaseModel):
    """Information about a registered phase type."""
    type: str
    display_name: str
    required_agents: List[str]
    description: Optional[str] = None


class PhaseConfigSchemaResponse(BaseModel):
    """JSON schema for phase configuration."""
    model_config = ConfigDict(populate_by_name=True)

    phase_type: str
    config_schema: Dict[str, Any] = Field(..., alias="schema")


# =============================================================================
# Validation Models
# =============================================================================

class WorkflowValidationRequest(BaseModel):
    """Request for validating a workflow definition."""
    phases: List[PhaseDefinitionRequest]


class WorkflowValidationResponse(BaseModel):
    """Response from workflow validation."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
