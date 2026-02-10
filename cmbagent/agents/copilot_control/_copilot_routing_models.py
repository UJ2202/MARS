"""
Copilot Routing Decision - Structured output for task analysis.

This module defines the structured output format for the CopilotControlAgent
to make intelligent routing decisions based on task analysis.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class AgentCapability(BaseModel):
    """Description of an agent's capabilities."""
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="What this agent can do")
    best_for: List[str] = Field(
        default_factory=list,
        description="Types of tasks this agent excels at"
    )


class ClarificationQuestion(BaseModel):
    """A question to ask the user for clarification."""
    question: str = Field(..., description="The question to ask")
    reason: str = Field(..., description="Why this clarification is needed")
    options: Optional[List[str]] = Field(
        default=None,
        description="Suggested options if applicable"
    )


class RoutingDecision(BaseModel):
    """
    Structured routing decision from the copilot control agent.

    This captures the agent's analysis of a task and its recommendation
    for how to handle it.
    """

    # Routing type
    route_type: Literal["one_shot", "planned", "clarify", "handoff"] = Field(
        ...,
        description=(
            "How to route this task:\n"
            "- one_shot: Simple task, execute directly with single agent\n"
            "- planned: Complex task, needs planning then step-by-step execution\n"
            "- clarify: Need more information from user before proceeding\n"
            "- handoff: Transfer to specialized workflow/agent"
        )
    )

    # Complexity assessment
    complexity: Literal["trivial", "simple", "moderate", "complex", "very_complex"] = Field(
        ...,
        description="Estimated task complexity level"
    )

    complexity_reasoning: str = Field(
        ...,
        description="Brief explanation of why this complexity was assessed"
    )

    # Agent selection
    primary_agent: str = Field(
        ...,
        description="Main agent to handle the task (e.g., 'engineer', 'researcher')"
    )

    supporting_agents: List[str] = Field(
        default_factory=list,
        description="Additional agents that may be needed for collaboration"
    )

    agent_selection_reasoning: str = Field(
        ...,
        description="Why these agents were selected"
    )

    # Planning hints (if route_type is "planned")
    suggested_steps: Optional[List[str]] = Field(
        default=None,
        description="High-level steps if planning is recommended"
    )

    estimated_steps: Optional[int] = Field(
        default=None,
        description="Estimated number of steps needed"
    )

    # Clarification (if route_type is "clarify")
    clarification_questions: Optional[List[ClarificationQuestion]] = Field(
        default=None,
        description="Questions to ask user before proceeding"
    )

    # Handoff (if route_type is "handoff")
    handoff_target: Optional[str] = Field(
        default=None,
        description="Target workflow or specialized agent for handoff"
    )

    handoff_reason: Optional[str] = Field(
        default=None,
        description="Why handoff is recommended"
    )

    # Confidence
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in this routing decision (0.0 to 1.0)"
    )

    # Additional context
    task_summary: str = Field(
        ...,
        description="Brief summary of what the task is asking for"
    )

    special_requirements: List[str] = Field(
        default_factory=list,
        description="Any special requirements identified (e.g., 'needs file access', 'requires web search')"
    )

    warnings: List[str] = Field(
        default_factory=list,
        description="Any warnings about potential issues or limitations"
    )


# Pre-defined agent capability descriptions for the control agent
AGENT_CAPABILITIES = {
    "engineer": AgentCapability(
        name="engineer",
        description="Writes and executes code, analyzes data, creates files, builds solutions",
        best_for=[
            "coding tasks",
            "data analysis",
            "file operations",
            "script creation",
            "debugging",
            "technical implementation"
        ]
    ),
    "researcher": AgentCapability(
        name="researcher",
        description="Searches for information, analyzes documents, summarizes content, extracts knowledge",
        best_for=[
            "information gathering",
            "document analysis",
            "summarization",
            "fact-finding",
            "literature review",
            "content synthesis"
        ]
    ),
    "planner": AgentCapability(
        name="planner",
        description="Creates structured plans for complex multi-step tasks",
        best_for=[
            "breaking down complex tasks",
            "project planning",
            "workflow design",
            "task decomposition"
        ]
    ),
    "web_surfer": AgentCapability(
        name="web_surfer",
        description="Browses websites and extracts information from web pages",
        best_for=[
            "web browsing",
            "content extraction",
            "form filling",
            "web scraping"
        ]
    ),
    "idea_maker": AgentCapability(
        name="idea_maker",
        description="Generates creative ideas and novel solutions",
        best_for=[
            "brainstorming",
            "creative thinking",
            "innovation",
            "solution generation"
        ]
    ),
    "idea_hater": AgentCapability(
        name="idea_hater",
        description="Critically evaluates ideas, finds weaknesses and potential issues",
        best_for=[
            "critical analysis",
            "risk assessment",
            "devil's advocate",
            "idea validation"
        ]
    ),
}


def get_available_capabilities(available_agents: List[str]) -> List[AgentCapability]:
    """Get capability descriptions for available agents."""
    capabilities = []
    for agent in available_agents:
        if agent in AGENT_CAPABILITIES:
            capabilities.append(AGENT_CAPABILITIES[agent])
        else:
            # Generic capability for unknown agents
            capabilities.append(AgentCapability(
                name=agent,
                description=f"Agent: {agent}",
                best_for=["general tasks"]
            ))
    return capabilities


def format_capabilities_for_prompt(available_agents: List[str]) -> str:
    """Format agent capabilities as a string for the control agent prompt."""
    capabilities = get_available_capabilities(available_agents)

    lines = ["## Available Agents\n"]
    for cap in capabilities:
        lines.append(f"### {cap.name}")
        lines.append(f"**Description:** {cap.description}")
        lines.append(f"**Best for:** {', '.join(cap.best_for)}")
        lines.append("")

    return "\n".join(lines)
