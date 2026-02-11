"""
Pydantic models for Copilot API request and response validation.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# Copilot Configuration Models
# =============================================================================

class CopilotConfig(BaseModel):
    """Configuration options for copilot mode."""

    # Agent configuration
    availableAgents: List[str] = Field(
        default=["engineer", "researcher"],
        description="List of agents available for copilot to use"
    )

    # Task routing
    enablePlanning: bool = Field(
        default=True,
        description="Whether to automatically plan complex tasks"
    )
    complexityThreshold: int = Field(
        default=50,
        description="Word count threshold for determining task complexity"
    )

    # Execution mode
    continuousMode: bool = Field(
        default=False,
        description="Keep running until user exits"
    )
    maxTurns: int = Field(
        default=20,
        description="Maximum interaction turns in continuous mode"
    )
    maxRounds: int = Field(
        default=100,
        description="Maximum conversation rounds per execution"
    )
    maxPlanSteps: int = Field(
        default=5,
        description="Maximum steps in generated plans"
    )
    maxAttempts: int = Field(
        default=3,
        description="Maximum retry attempts per step"
    )

    # HITL settings
    approvalMode: str = Field(
        default="after_step",
        description="When to request human approval: before_step, after_step, both, none, conversational"
    )
    conversational: bool = Field(
        default=False,
        description="Enable conversational mode - human participates in every turn like Claude Code"
    )
    toolApproval: str = Field(
        default="none",
        description="Tool execution approval mode: prompt (ask before dangerous ops with auto-allow), auto_allow_all (skip all), none (no tool-level approval)"
    )
    intelligentRouting: str = Field(
        default="balanced",
        description="Intelligent routing mode: aggressive (always clarify ambiguous tasks, propose for complex), balanced (clarify when clearly ambiguous), minimal (prefer direct action)"
    )
    autoApproveSimple: bool = Field(
        default=True,
        description="Skip approval for simple one-shot tasks"
    )

    # Model selection
    model: str = Field(
        default="gpt-4o",
        description="Primary model for engineer agent"
    )
    plannerModel: str = Field(
        default="gpt-4.1-2025-04-14",
        description="Model for planner agent"
    )
    researcherModel: str = Field(
        default="gpt-4.1-2025-04-14",
        description="Model for researcher agent"
    )

    # Instructions
    engineerInstructions: str = Field(
        default="",
        description="Additional instructions for engineer agent"
    )
    researcherInstructions: str = Field(
        default="",
        description="Additional instructions for researcher agent"
    )
    planInstructions: str = Field(
        default="",
        description="Additional instructions for planner agent"
    )

    # Work directory
    workDir: str = Field(
        default="~/Desktop/cmbdir",
        description="Working directory for task outputs"
    )


class CopilotTaskRequest(BaseModel):
    """Request model for copilot task submission."""
    task: str = Field(..., description="Task description to execute")
    config: CopilotConfig = Field(default_factory=CopilotConfig)


class CopilotTaskResponse(BaseModel):
    """Response model for copilot task submission."""
    task_id: str
    status: str
    message: str
    mode: str = "copilot"


# =============================================================================
# Copilot Session Models
# =============================================================================

class CopilotSessionInfo(BaseModel):
    """Information about an active copilot session."""
    session_id: str
    task_id: str
    status: str  # active, paused, completed, failed
    current_turn: int
    mode: str  # one_shot, planned, continuous
    available_agents: List[str]
    created_at: str
    last_activity: Optional[str] = None


class CopilotTurnResult(BaseModel):
    """Result of a single copilot turn."""
    turn: int
    task: str
    mode: str  # one_shot or planned
    complexity: str  # simple or complex
    success: bool
    summary: Optional[str] = None
    plan: Optional[List[Dict[str, Any]]] = None
    step_results: Optional[List[Dict[str, Any]]] = None


class CopilotConversationHistory(BaseModel):
    """History entry in copilot conversation."""
    turn: int
    task: str
    result_summary: str


class CopilotResult(BaseModel):
    """Complete result of a copilot workflow execution."""
    results: List[CopilotTurnResult]
    turns: int
    conversation_history: List[CopilotConversationHistory]
    final_context: Dict[str, Any] = Field(default_factory=dict)
    run_id: str
    total_time: float


# =============================================================================
# Copilot Feedback Models
# =============================================================================

class CopilotFeedback(BaseModel):
    """User feedback during copilot execution."""
    task_id: str
    step_number: Optional[int] = None
    feedback_type: str  # approval, rejection, redo, skip, feedback
    message: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None


class CopilotNextTaskRequest(BaseModel):
    """Request for next task in continuous mode."""
    task_id: str
    next_task: Optional[str] = None  # None means exit
    feedback: Optional[str] = None


# =============================================================================
# Copilot Workflow Info Models
# =============================================================================

class CopilotWorkflowInfo(BaseModel):
    """Information about available copilot workflows."""
    id: str
    name: str
    description: str
    default_config: CopilotConfig


class CopilotAgentInfo(BaseModel):
    """Information about an available agent."""
    name: str
    description: str
    default_model: str
    capabilities: List[str] = Field(default_factory=list)


class AvailableAgentsResponse(BaseModel):
    """Response listing available agents for copilot."""
    core_agents: List[CopilotAgentInfo]
    domain_agents: List[CopilotAgentInfo]
