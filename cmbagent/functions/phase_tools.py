"""
Phase Tools - Making Phases Callable as Tools

This module exposes phases as tools that agents can call. This enables:
- Agents to orchestrate complex workflows dynamically
- Phases to be composable building blocks
- Flexible workflows instead of hardcoded sequences

Registered phases (from PhaseRegistry):
- planning: PlanningPhase - Generate structured plans
- control: ControlPhase - Execute plan steps with context carryover
- one_shot: OneShotPhase - Single agent, no planning
- hitl_checkpoint: HITLCheckpointPhase - Human approval gates
- idea_generation: IdeaGenerationPhase - Idea creation and review
- hitl_planning: HITLPlanningPhase - Interactive planning with feedback
- hitl_control: HITLControlPhase - Step execution with approval
- copilot: CopilotPhase - Flexible assistant

Instead of:
    Workflow → Research Phase → Planning Phase → Execution Phase (rigid)

We have:
    Agent → Invokes phases as needed → Chains phases dynamically (flexible)
"""

from typing import Annotated, Dict, Any, Optional, List
import json


def invoke_planning_phase(
    task: Annotated[str, "Task to create a plan for"],
    max_steps: Annotated[int, "Maximum steps in plan"] = 5,
    n_reviews: Annotated[int, "Number of plan review iterations"] = 1
) -> str:
    """
    Invoke the planning phase to create a detailed execution plan.

    Use this when:
    - Task is complex and needs breakdown
    - Need step-by-step approach
    - Multiple agents will be involved
    - Want structured approach

    Returns:
        JSON with generated plan
    """
    return json.dumps({
        "phase": "planning",
        "task": task,
        "config": {
            "max_plan_steps": max_steps,
            "n_plan_reviews": n_reviews,
        },
        "status": "phase_invocation_requested"
    })


def invoke_control_phase(
    plan: Annotated[Dict, "Plan to execute (from planning phase)"],
    mode: Annotated[str, "Execution mode: 'sequential', 'parallel'"] = "sequential"
) -> str:
    """
    Invoke the control phase to carry out a plan step by step.

    Use this when:
    - Have a plan ready to execute
    - Need to run multiple steps with context carryover
    - Want progress tracking

    Returns:
        JSON with execution results
    """
    return json.dumps({
        "phase": "control",
        "plan": plan,
        "config": {
            "execution_mode": mode,
        },
        "status": "phase_invocation_requested"
    })


def invoke_one_shot_phase(
    task: Annotated[str, "Task for single agent to execute"],
    agent: Annotated[str, "Agent to use: 'engineer' or 'researcher'"] = "engineer",
    max_rounds: Annotated[int, "Maximum conversation rounds"] = 50
) -> str:
    """
    Invoke one-shot phase for direct task execution without planning.

    Use this when:
    - Task is simple and doesn't need planning
    - Single agent can handle it
    - Want quick execution

    Returns:
        JSON with execution result
    """
    return json.dumps({
        "phase": "one_shot",
        "task": task,
        "config": {
            "agent": agent,
            "max_rounds": max_rounds,
        },
        "status": "phase_invocation_requested"
    })


def invoke_hitl_planning_phase(
    task: Annotated[str, "Task to plan with human feedback"],
    max_iterations: Annotated[int, "Maximum human feedback iterations"] = 3,
    allow_modification: Annotated[bool, "Allow human to modify the plan"] = True
) -> str:
    """
    Invoke HITL planning phase for interactive planning with human feedback.

    Use this when:
    - Plan needs human approval before execution
    - Want human to review and modify steps
    - Iterative planning with user input

    Returns:
        JSON with approved plan
    """
    return json.dumps({
        "phase": "hitl_planning",
        "task": task,
        "config": {
            "max_human_iterations": max_iterations,
            "allow_plan_modification": allow_modification,
        },
        "status": "phase_invocation_requested"
    })


def invoke_hitl_control_phase(
    plan: Annotated[Dict, "Plan to execute with human oversight"],
    approval_mode: Annotated[str, "When to request approval: 'before_step', 'after_step', 'both'"] = "after_step",
    allow_retry: Annotated[bool, "Allow retrying failed steps"] = True
) -> str:
    """
    Invoke HITL control phase for step execution with human approval.

    Use this when:
    - Each step needs human review
    - Want checkpoint approvals
    - User oversight is required

    Returns:
        JSON with execution results
    """
    return json.dumps({
        "phase": "hitl_control",
        "plan": plan,
        "config": {
            "approval_mode": approval_mode,
            "allow_step_retry": allow_retry,
        },
        "status": "phase_invocation_requested"
    })


def invoke_idea_generation_phase(
    topic: Annotated[str, "Topic to generate ideas for"],
    n_ideas: Annotated[int, "Number of ideas to generate"] = 3,
    n_critiques: Annotated[int, "Number of critique rounds"] = 1
) -> str:
    """
    Invoke idea generation phase for brainstorming.

    Use this when:
    - Need creative ideas on a topic
    - Want ideas reviewed critically
    - Exploring multiple approaches

    Returns:
        JSON with generated ideas and critiques
    """
    return json.dumps({
        "phase": "idea_generation",
        "topic": topic,
        "config": {
            "n_ideas": n_ideas,
            "n_critiques": n_critiques,
        },
        "status": "phase_invocation_requested"
    })


def invoke_hitl_checkpoint_phase(
    checkpoint_type: Annotated[str, "Type of checkpoint: 'approval', 'review', 'confirm'"] = "approval",
    message: Annotated[str, "Message to show user"] = "Please approve to continue"
) -> str:
    """
    Invoke HITL checkpoint phase for human approval gate.

    Use this when:
    - Need explicit user confirmation
    - Critical decision point
    - Pausing for human review

    Returns:
        JSON with approval status
    """
    return json.dumps({
        "phase": "hitl_checkpoint",
        "config": {
            "checkpoint_type": checkpoint_type,
            "message": message,
        },
        "status": "phase_invocation_requested"
    })


def invoke_copilot_phase(
    task: Annotated[str, "Task for copilot to handle"],
    mode: Annotated[str, "Copilot mode: 'autonomous', 'guided'"] = "autonomous",
    enable_planning: Annotated[bool, "Auto-plan complex tasks"] = True
) -> str:
    """
    Invoke copilot phase for flexible task handling.

    Use this when:
    - Task needs adaptive execution
    - Want automatic routing based on complexity
    - Interactive assistance

    Returns:
        JSON with copilot execution results
    """
    return json.dumps({
        "phase": "copilot",
        "task": task,
        "config": {
            "mode": mode,
            "enable_planning": enable_planning,
        },
        "status": "phase_invocation_requested"
    })


def chain_phases(
    phases: Annotated[List[Dict[str, Any]], "Sequence of phases to invoke"],
    pass_context: Annotated[bool, "Pass output of each phase to next"] = True
) -> str:
    """
    Chain multiple phases in sequence, optionally passing context.

    Use this when:
    - Workflow has clear stages
    - Each phase builds on previous
    - Want structured process

    Example:
        [
            {"phase": "planning", "task": "Design API"},
            {"phase": "control", "plan": "$previous"},
            {"phase": "hitl_checkpoint", "checkpoint_type": "review"}
        ]

    Returns:
        JSON indicating phase chain started
    """
    return json.dumps({
        "action": "chain_phases",
        "phases": phases,
        "pass_context": pass_context,
        "status": "chaining_requested"
    })


# All phase tools - matches PhaseRegistry
PHASE_TOOLS = [
    invoke_planning_phase,
    invoke_control_phase,
    invoke_one_shot_phase,
    invoke_hitl_planning_phase,
    invoke_hitl_control_phase,
    invoke_idea_generation_phase,
    invoke_hitl_checkpoint_phase,
    invoke_copilot_phase,
    chain_phases,
]


def get_phase_tools_description() -> str:
    """Get description of available phase tools for agent prompt."""
    return """
## Phase Tools (Registered Phases)

You can invoke entire phases as tools to orchestrate complex workflows.
These map directly to phases in the PhaseRegistry:

**1. invoke_planning_phase(task, max_steps=5, n_reviews=1)**
   - Create detailed execution plan
   - Breaks down complex tasks
   - Returns structured plan with steps

**2. invoke_control_phase(plan, mode='sequential')**
   - Execute a plan step-by-step
   - Context carryover between steps
   - Tracks progress and state

**3. invoke_one_shot_phase(task, agent='engineer', max_rounds=50)**
   - Direct single-agent execution
   - No planning overhead
   - Good for simple tasks

**4. invoke_hitl_planning_phase(task, max_iterations=3)**
   - Interactive planning with human feedback
   - User can review and modify plan
   - Iterative until approval

**5. invoke_hitl_control_phase(plan, approval_mode='after_step')**
   - Step execution with human oversight
   - Approval gates at each step
   - Modes: 'before_step', 'after_step', 'both'

**6. invoke_idea_generation_phase(topic, n_ideas=3)**
   - Generate creative ideas
   - Critical review (idea_hater)
   - Good for brainstorming

**7. invoke_hitl_checkpoint_phase(checkpoint_type='approval')**
   - Human approval gate
   - Pause for user confirmation
   - Types: 'approval', 'review', 'confirm'

**8. invoke_copilot_phase(task, mode='autonomous')**
   - Flexible assistant mode
   - Auto-routes based on complexity
   - Can invoke other phases

**9. chain_phases(phases, pass_context=True)**
   - Chain multiple phases together
   - Pass context between phases
   - Structured workflows

## Workflow Examples

**Example 1: Plan → Execute**
```
1. invoke_planning_phase("Build REST API")
2. invoke_control_phase(plan_from_step_1)
```

**Example 2: With Human Oversight**
```
1. invoke_hitl_planning_phase("Add authentication")
2. invoke_hitl_control_phase(approved_plan)
```

**Example 3: Full Chain**
```
chain_phases([
    {"phase": "planning", "task": "Create feature"},
    {"phase": "hitl_checkpoint", "checkpoint_type": "approval"},
    {"phase": "control", "plan": "$previous"}
])
```

## Guidelines

- **Match phase to need** - Use one_shot for simple, planning for complex
- **Use HITL phases** - When human oversight is needed
- **Chain for workflows** - When multiple phases are needed
- **Pass context** - Let phases build on each other
"""


# Mapping of phase names to their actual phase classes (for reference)
PHASE_REGISTRY_MAP = {
    "planning": "PlanningPhase",
    "control": "ControlPhase",
    "one_shot": "OneShotPhase",
    "hitl_checkpoint": "HITLCheckpointPhase",
    "idea_generation": "IdeaGenerationPhase",
    "hitl_planning": "HITLPlanningPhase",
    "hitl_control": "HITLControlPhase",
    "copilot": "CopilotPhase",
}
