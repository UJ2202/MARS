from pydantic import BaseModel, Field
from typing import List, Optional


class EngineerResponse(BaseModel):
    code_explanation: str = Field(..., description="The code explanation")
    python_code:  str = Field(..., description="The Python code in a form ready to execute")

    def format(self) -> str:
        return f"""
**Code Explanation:**

{self.code_explanation}

**Python Code:**

```python
{self.python_code}
```

        """

# plan_reviewer response
class PlanReviewerResponse(BaseModel):
    recommendations: List[str] = Field(..., description="Each recommendation must amount to a modification of one part of the plan.")
    def format(self) -> str:
        recommendations_output = "\n".join(f"- {recommendation}\n" for i, recommendation in enumerate(self.recommendations))
        return f"""
**Recommendations:**

{recommendations_output}
        """

# planner response
class Subtasks(BaseModel):
    sub_task: str = Field(..., description="The sub-task to be performed")
    sub_task_agent:  str = Field(..., description="The name of the agent in charge of the sub-task")


class PlannerResponse(BaseModel):
    main_task: str
    sub_tasks: list[Subtasks]

    def format(self) -> str:
        plan_output = "\n".join(
            f"\n- Step {i + 1}:\n\t * sub-task: {step.sub_task}\n\t * agent in charge: {step.sub_task_agent}\n\t" for i, step in enumerate(self.sub_tasks)
        )
        message = f"""
**PLAN**

- Main task: {self.main_task}

{plan_output}

        """
        return message


class SubtaskSummary(BaseModel):
    sub_task: str
    result: str
    feedback: str
    agent: str

class SummarizerResponse(BaseModel):
    main_task: str
    results: str
    summary: List[SubtaskSummary]

    def format(self) -> str:
        summary_output = "\n".join(
            f"- {step.sub_task}:\n\t * result: {step.result}\n\t * feedback: {step.feedback}\n\t * agent: {step.agent}\n"
            for step in self.summary
        )
        return f"""
**SUMMARY REPORT:**

- Main task: {self.main_task}

- Overall Results:

{self.results}

**Detailed Summary:**

{summary_output}
        """


class FileResult(BaseModel):
    file_name: str = Field(..., description="The name of the consulted file")

class RetrievalTask(BaseModel):
    description: str = Field(..., description="The retrieval task being performed")

class CodeExplanation(BaseModel):
    explanation: Optional[str] = Field(None, description="Explanation of the Python code")

class PythonCode(BaseModel):
    code: Optional[str] = Field(None, description="The Python code retrieved or generated")

class RagSoftwareFormatterResponse(BaseModel):
    retrieval_task: RetrievalTask = Field(..., description="Details of the retrieval task")
    files_consulted: List[FileResult] = Field(..., description="List of consulted files")
    code_explanation: CodeExplanation = Field(..., description="Explanation of the retrieved or generated code")
    python_code: PythonCode = Field(..., description="The Python code block")


    def format(self) -> str:
        files = "\n".join(f"- {file.file_name}" for file in self.files_consulted)
        code_explanation = self.code_explanation.explanation or "No explanation provided."
        python_code = self.python_code.code or "No code provided."

        return f"""
**File Search Results:**

{self.retrieval_task.description}

**Files Consulted:**

{files}

**Code Explanation:**

{code_explanation}

**Python Code:**

```python
{python_code}
```
\n

        """


# ============ COPILOT ROUTING DECISION ============

class AgentCapability(BaseModel):
    """Describes what an agent can do."""
    agent_name: str = Field(..., description="Name of the agent")
    capability: str = Field(..., description="What this agent is good at")
    relevance_score: float = Field(..., description="How relevant this agent is (0-1)")


class CopilotRoutingDecision(BaseModel):
    """
    Structured output from copilot control agent for intelligent task routing.

    This replaces simple heuristics with LLM-based analysis.
    """
    # Primary routing decision
    route_type: str = Field(
        ...,
        description="How to handle this task: 'one_shot' (direct execution), 'planned' (needs planning), 'clarify' (need more info from user)"
    )

    # Complexity analysis
    complexity_score: int = Field(
        ...,
        description="Task complexity 0-100. <30=simple, 30-60=moderate, >60=complex"
    )
    complexity_reasoning: str = Field(
        ...,
        description="Brief explanation of why this complexity score"
    )

    # Agent selection
    primary_agent: str = Field(
        ...,
        description="Best agent to handle this task (e.g., 'engineer', 'researcher')"
    )
    supporting_agents: List[str] = Field(
        default_factory=list,
        description="Other agents that might be needed"
    )
    agent_reasoning: str = Field(
        ...,
        description="Why these agents were selected"
    )

    # For planned routes
    estimated_steps: int = Field(
        default=1,
        description="Estimated number of steps if planning is needed"
    )

    # For clarify routes
    clarifying_questions: List[str] = Field(
        default_factory=list,
        description="Questions to ask user if route_type is 'clarify'"
    )

    # Task refinement
    refined_task: str = Field(
        ...,
        description="Optionally refined/clarified version of the task"
    )

    # Confidence
    confidence: float = Field(
        ...,
        description="Confidence in this routing decision (0-1)"
    )

    def format(self) -> str:
        agents = f"{self.primary_agent}"
        if self.supporting_agents:
            agents += f" + {', '.join(self.supporting_agents)}"

        questions = ""
        if self.clarifying_questions:
            questions = "\n**Clarifying Questions:**\n" + "\n".join(f"- {q}" for q in self.clarifying_questions)

        return f"""
**Routing Decision:**
- Route: {self.route_type}
- Complexity: {self.complexity_score}/100 ({self.complexity_reasoning})
- Agents: {agents}
- Estimated Steps: {self.estimated_steps}
- Confidence: {self.confidence:.0%}

**Agent Reasoning:** {self.agent_reasoning}

**Refined Task:** {self.refined_task}
{questions}
        """

    def should_use_planning(self) -> bool:
        """Helper to check if planning is recommended."""
        return self.route_type == "planned"

    def needs_clarification(self) -> bool:
        """Helper to check if clarification is needed."""
        return self.route_type == "clarify"


class CopilotHandoffDecision(BaseModel):
    """
    Decision for handing off to another agent mid-execution.

    Used when copilot control determines a different agent should take over.
    """
    should_handoff: bool = Field(
        ...,
        description="Whether to handoff to another agent"
    )
    target_agent: str = Field(
        default="",
        description="Agent to handoff to"
    )
    handoff_reason: str = Field(
        default="",
        description="Why this handoff is needed"
    )
    context_to_pass: List[str] = Field(
        default_factory=list,
        description="Key context items to pass to the next agent"
    )

    def format(self) -> str:
        if not self.should_handoff:
            return "**No handoff needed**"
        return f"""
**Handoff Decision:**
- Target: {self.target_agent}
- Reason: {self.handoff_reason}
- Context: {', '.join(self.context_to_pass) if self.context_to_pass else 'None'}
        """