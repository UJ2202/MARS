"""
Retry context data models.

Defines the structure for retry attempts and retry context that gets
passed to agents during retry operations.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class RetryAttempt(BaseModel):
    """Record of a single retry attempt"""

    attempt_number: int = Field(..., description="Attempt number (1-indexed)")
    started_at: datetime = Field(..., description="When attempt started")
    completed_at: Optional[datetime] = Field(None, description="When attempt completed")
    error_type: Optional[str] = Field(None, description="Type of error (e.g., ValueError)")
    error_message: Optional[str] = Field(None, description="Error message")
    traceback: Optional[str] = Field(None, description="Full traceback")
    agent_output: Optional[str] = Field(None, description="Agent output before error")
    modifications_tried: List[str] = Field(
        default_factory=list,
        description="List of modifications attempted"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class RetryContext(BaseModel):
    """Context information for retry attempts"""

    # Attempt tracking
    current_attempt: int = Field(..., description="Current attempt number")
    max_attempts: int = Field(..., description="Maximum retry attempts")

    # Task information
    original_task: str = Field(..., description="Original task description")
    modified_task: Optional[str] = Field(None, description="Modified task (if any)")

    # Previous attempt history
    previous_attempts: List[RetryAttempt] = Field(
        default_factory=list,
        description="History of previous attempts"
    )

    # Error analysis
    error_pattern: Optional[str] = Field(None, description="Matched error pattern name")
    error_category: str = Field(..., description="Error category (file_not_found, api_error, etc.)")
    common_error: bool = Field(..., description="Whether this is a known common error")

    # User guidance
    user_feedback: Optional[str] = Field(None, description="User feedback/guidance")
    user_suggestions: List[str] = Field(
        default_factory=list,
        description="Parsed user suggestions"
    )

    # System suggestions
    suggested_fixes: List[str] = Field(
        default_factory=list,
        description="System-generated fix suggestions"
    )
    similar_errors_resolved: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Similar errors that were successfully resolved"
    )

    # Retry strategy
    strategy: str = Field(..., description="Retry strategy (immediate, exponential_backoff, user_guided)")
    backoff_seconds: Optional[int] = Field(None, description="Backoff delay in seconds")

    # Success indicators
    success_probability: Optional[float] = Field(
        None,
        description="Estimated success probability (0.0 to 1.0)",
        ge=0.0,
        le=1.0
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryContext":
        """Create from dictionary"""
        return cls(**data)
