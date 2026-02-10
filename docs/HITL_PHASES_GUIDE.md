# HITL Phases and AG2 Integration Guide

## New HITL Phases

This document describes the two new human-in-the-loop (HITL) phases for CMBAgent, their feedback flow capabilities, and explains AG2's HITL features.

---

## Table of Contents

1. [Overview](#overview)
2. [Feedback Flow System](#feedback-flow-system)
3. [HITLPlanningPhase](#hitlplanningphase)
4. [HITLControlPhase](#hitlcontrolphase)
5. [AG2 Human Input Modes](#ag2-human-input-modes)
6. [Other AG2 Modes for Phases](#other-ag2-modes-for-phases)
7. [Usage Examples](#usage-examples)
8. [Comparison with Existing HITL](#comparison-with-existing-hitl)

---

## Overview

CMBAgent now provides two advanced HITL phases that enable deep human involvement during workflow execution:

| Phase | Purpose | When to Use |
|-------|---------|-------------|
| `HITLPlanningPhase` | Interactive plan generation with iterative human feedback | When you want human guidance during plan creation |
| `HITLControlPhase` | Step-by-step execution with human approval and error handling | When you want fine-grained control over execution |

Both phases leverage AG2's `human_input_mode` capabilities and the CMBAgent approval system.

**NEW: Complete Feedback Flow** - Human feedback now flows seamlessly between phases, creating a persistent memory of human guidance throughout the workflow.

---

## Feedback Flow System

### Overview

The HITL system now supports **continuous feedback flow** where human input from one phase influences all subsequent phases.

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  Checkpoint  │────────>│   Planning   │────────>│   Control    │
│    Phase     │         │    Phase     │         │    Phase     │
└──────────────┘         └──────────────┘         └──────────────┘
       │                        │                        │
       │                        │                        │
   feedback ─────────> previous_feedback ────────> all_feedback
       │                        │                        │
       v                        v                        v
  shared_state            shared_state            shared_state
```

### How It Works

1. **Checkpoint Phase**
   - Captures initial human feedback/approval
   - Stores in `shared_state['hitl_feedback']`

2. **Planning Phase**
   - Reads previous feedback from shared_state
   - Injects into planner agent instructions
   - Accumulates feedback from iterations
   - Passes combined feedback forward

3. **Control Phase**
   - Reads combined feedback from planning
   - Injects into engineer/researcher agents
   - Accumulates step-level feedback
   - Passes complete feedback history forward

4. **Subsequent Phases**
   - Can access complete feedback history
   - Can continue accumulating feedback
   - Maintains complete audit trail

### Feedback Storage Structure

```python
# In shared_state after checkpoint
{
    'hitl_feedback': "Initial human guidance...",
    'hitl_approved': True,
}

# In shared_state after planning
{
    'hitl_feedback': "Initial guidance\n\nIteration 1: Add X\nIteration 2: Revise Y",
    'planning_feedback_history': ["Add X", "Revise Y"],
}

# In shared_state after control
{
    'all_hitl_feedback': "Complete feedback from all phases...",
    'control_feedback': [
        {'step': 1, 'timing': 'before', 'feedback': "..."},
        {'step': 1, 'timing': 'after', 'feedback': "..."},
    ],
}
```

### Agent Instruction Injection

Feedback is injected into agent system messages:

```python
# In Planning Phase
previous_feedback = context.shared_state.get('hitl_feedback', '')
if previous_feedback:
    instructions = f"""
## Previous Human Feedback
{previous_feedback}

Please incorporate this feedback into your planning.
"""
    cmbagent.inject_to_agents(['planner'], instructions, mode='append')

# In Control Phase
hitl_feedback = context.shared_state.get('hitl_feedback', '')
if hitl_feedback:
    instructions = f"""
## Human Feedback from Planning Phase
{hitl_feedback}

Please keep this feedback in mind during execution.
"""
    cmbagent.inject_to_agents(['engineer'], instructions, mode='append')
```

This creates **persistent memory** - agents continuously "see" human guidance in their instructions.

---

## HITLPlanningPhase

### Description

The **HITLPlanningPhase** provides an interactive planning experience where humans can:

1. Review plans at each iteration
2. Provide feedback for plan revision
3. Approve, reject, or directly modify plans
4. Guide the planning process with domain expertise

### Configuration

```python
@dataclass
class HITLPlanningPhaseConfig:
    # Planning parameters
    max_rounds: int = 50
    max_plan_steps: int = 3
    n_plan_reviews: int = 1
    max_human_iterations: int = 3  # Maximum human feedback rounds
    
    # Models
    planner_model: str = "gpt-4.1-2025-04-14"
    plan_reviewer_model: str = "o3-mini-2025-01-31"
    
    # Instructions
    plan_instructions: str = ""
    hardware_constraints: str = ""
    
    # HITL-specific options
    auto_approve_after_iterations: int = 3  # Auto-approve after N iterations
    require_explicit_approval: bool = True  # Require explicit approval
    show_intermediate_plans: bool = True  # Show plans during review
    allow_plan_modification: bool = True  # Allow direct plan editing
```

### Features

| Feature | Description |
|---------|-------------|
| **Iterative Refinement** | Agent generates plan → Human reviews → Agent revises based on feedback → Repeat |
| **Multiple Approval Options** | Approve, Reject, Revise (with feedback), Modify (direct editing) |
| **Feedback History** | All human feedback is accumulated and passed to the agent |
| **Intermediate Plans** | Each iteration's plan is saved for reference |
| **Auto-approval** | Automatically approve after N iterations if configured |

### Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    HITL PLANNING PHASE FLOW                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Initial Planning                                            │
│     └── Agent generates initial plan                            │
│                                                                 │
│  2. Human Review (Iteration 1)                                  │
│     ├── Present plan to human                                   │
│     └── Options: Approve / Reject / Revise / Modify             │
│                                                                 │
│  3. If Revise: Collect Feedback                                 │
│     ├── Human provides feedback text                            │
│     └── Add to feedback history                                 │
│                                                                 │
│  4. Plan Revision (Iteration 2)                                 │
│     ├── Agent receives: original task + all feedback            │
│     └── Agent generates revised plan                            │
│                                                                 │
│  5. Human Review (Iteration 2)                                  │
│     └── Repeat until approved or max iterations                 │
│                                                                 │
│  6. Final Plan                                                  │
│     └── Approved plan saved and passed to next phase            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Input/Output

**Input Context:**
- `task`: Task description
- `work_dir`: Working directory
- `api_keys`: API credentials

**Output Context:**
- `final_plan`: The approved plan
- `plan_file_path`: Path to saved plan JSON
- `planning_context`: Full context from planning
- `human_feedback`: List of human feedback iterations
- `iterations`: Number of human feedback rounds

---

## HITLControlPhase

### Description

The **HITLControlPhase** provides step-by-step execution control where humans can:

1. Approve steps before execution
2. Review step results after execution
3. Handle errors with retry/skip/abort options
4. Skip steps or modify execution flow

### Configuration

```python
@dataclass
class HITLControlPhaseConfig:
    # Execution parameters
    max_rounds: int = 100
    max_n_attempts: int = 3
    
    # Step handling
    execute_all_steps: bool = True
    step_number: Optional[int] = None
    
    # HITL options
    approval_mode: str = "before_step"  # "before_step", "after_step", "both", "on_error"
    allow_step_skip: bool = True
    allow_step_retry: bool = True
    allow_step_modification: bool = True
    show_step_context: bool = True
    auto_approve_successful_steps: bool = False
    
    # Models
    engineer_model: str = "gpt-4.1-2025-04-14"
    researcher_model: str = "gpt-4.1-2025-04-14"
```

### Features

| Feature | Description |
|---------|-------------|
| **Approval Modes** | Before step, after step, both, or on error only |
| **Error Handling** | Human decides: retry, skip, or abort |
| **Step Skipping** | Skip steps that are not needed |
| **Context Visibility** | Show accumulated context before each step |
| **Auto-approval** | Auto-approve successful steps if configured |

### Approval Modes

#### 1. Before Step (`approval_mode="before_step"`)

Human approves each step **before** execution:
- Review step task
- Decide: Approve / Skip / Reject

```
Step 1 → [HUMAN APPROVAL] → Execute → Step 2 → [HUMAN APPROVAL] → Execute → ...
```

#### 2. After Step (`approval_mode="after_step"`)

Human reviews results **after** each step:
- Review step outcome
- Decide: Continue / Redo / Abort

```
Step 1 → Execute → [HUMAN REVIEW] → Step 2 → Execute → [HUMAN REVIEW] → ...
```

#### 3. Both (`approval_mode="both"`)

Approval before **and** review after:
- Maximum control
- Approval before execution + Review after completion

```
Step 1 → [APPROVAL] → Execute → [REVIEW] → Step 2 → [APPROVAL] → Execute → [REVIEW] → ...
```

#### 4. On Error (`approval_mode="on_error"`)

Only ask for human input when errors occur:
- Autonomous execution for successful steps
- Human intervention on failures
- Decide: Retry / Skip / Abort

```
Step 1 → Execute (success) → Step 2 → Execute (FAILED) → [HUMAN INTERVENTION] → ...
```

### Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ERROR HANDLING FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Step Execution Fails                                        │
│     └── Error captured with details                             │
│                                                                 │
│  2. Present Error to Human                                      │
│     ├── Step details                                            │
│     ├── Error message                                           │
│     └── Attempt number                                          │
│                                                                 │
│  3. Human Decision                                              │
│     ├── Retry: Try executing the step again                     │
│     ├── Skip: Skip this step and continue                       │
│     └── Abort: Cancel entire workflow                           │
│                                                                 │
│  4. Execute Decision                                            │
│     └── Proceed according to human choice                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Input/Output

**Input Context:**
- `final_plan` or `plan_steps`: Plan to execute
- `task`: Original task
- `work_dir`: Working directory
- `planning_context`: Context from planning

**Output Context:**
- `step_results`: Results from each step
- `final_context`: Final context after all steps
- `step_summaries`: Summary of each step
- `human_interventions`: List of human interventions
- `skipped_steps`: List of steps skipped by human

---

## AG2 Human Input Modes

AG2 (AutoGen) provides three built-in `human_input_mode` options for agent configuration:

### 1. NEVER (Default for Autonomous Agents)

**Description:** Agent runs fully autonomously without human input.

**Use Cases:**
- Code execution agents (`executor`, `executor_bash`)
- Autonomous workflows
- Background processing

**CMBAgent Usage:**
```python
# In agent YAML configuration
human_input_mode: "NEVER"
```

**AG2 Behavior:**
- Agent never pauses for human input
- Executes all actions automatically
- No human intervention possible during execution

**Examples in CMBAgent:**
- `executor` agent
- `executor_bash` agent
- `researcher_executor` agent

---

### 2. TERMINATE (Semi-Autonomous)

**Description:** Agent runs autonomously but asks for human input when it receives a TERMINATE signal.

**Use Cases:**
- Code execution with review
- Workflows that need final approval
- Long-running tasks with checkpoints

**CMBAgent Usage:**
```python
# Agent configuration
human_input_mode: "TERMINATE"
```

**AG2 Behavior:**
- Agent executes autonomously
- When TERMINATE message received, pauses for human input
- Human can provide feedback or continue
- Useful for reviewing final results

**Example Flow:**
```
Agent → Execute → Execute → TERMINATE received → [HUMAN INPUT] → Continue/End
```

---

### 3. ALWAYS (Full Human-in-the-Loop)

**Description:** Agent asks for human input **after every message**.

**Use Cases:**
- Interactive debugging
- Teaching/demonstration mode
- High-risk operations requiring constant oversight
- Admin agents for approval workflows

**CMBAgent Usage:**
```python
# Admin agent uses ALWAYS mode
name: "admin"
human_input_mode: "ALWAYS"
```

**AG2 Behavior:**
- Agent pauses after each message
- Human must review and approve or provide input
- Maximum control but slower execution
- Best for critical decision points

**CMBAgent `admin` Agent:**
```yaml
# cmbagent/agents/admin/admin.yaml
name: "admin"
instructions: |
    A human admin.
code_execution_config: False
# human_input_mode defaults to ALWAYS for UserProxyAgent
```

**Example Flow:**
```
Agent → Message → [HUMAN INPUT] → Agent → Message → [HUMAN INPUT] → ...
```

---

## Other AG2 Modes for Phases

Beyond `human_input_mode`, AG2 provides several other capabilities that can be incorporated as phases:

### 1. Nested Chat Phase

**Description:** Execute sub-conversations between specific agents.

**AG2 Feature:** `register_nested_chats()`

**Use Case:** Isolated sub-tasks that don't need full swarm orchestration.

**Example Phase:**
```python
class NestedChatPhase(Phase):
    """Execute a nested chat between specific agents."""
    
    async def execute(self, context):
        # Create isolated chat between engineer and executor
        nested_chat = GroupChat(
            agents=[engineer, executor],
            messages=[],
            max_round=10,
            speaker_selection_method='round_robin'
        )
        result = await execute_nested_chat(nested_chat, task)
        return result
```

---

### 2. Reflection Phase

**Description:** Agent reflects on its own outputs for self-improvement.

**AG2 Feature:** Built-in reflection capabilities

**Use Case:** Quality improvement, error detection, self-correction.

**Example Phase:**
```python
class ReflectionPhase(Phase):
    """Agent reviews and improves its own work."""
    
    async def execute(self, context):
        original_output = context.input_data['output']
        
        # Critic agent reviews the work
        reflection = critic_agent.reflect(original_output)
        
        # Original agent revises based on reflection
        improved_output = agent.revise(original_output, reflection)
        
        return improved_output
```

---

### 3. Multi-Agent Debate Phase

**Description:** Multiple agents debate and reach consensus.

**AG2 Feature:** Group chat with debate patterns

**Use Case:** Complex decisions, multiple perspectives, consensus building.

**Example Phase:**
```python
class DebatePhase(Phase):
    """Multiple agents debate and reach consensus."""
    
    async def execute(self, context):
        # Agents: proposer, critic, judge
        debate_chat = GroupChat(
            agents=[proposer, critic, judge],
            max_round=20,
            speaker_selection_method='auto'
        )
        
        # Debate until consensus or max rounds
        result = await execute_debate(debate_chat, topic)
        return result
```

---

### 4. RAG (Retrieval-Augmented Generation) Phase

**Description:** Query knowledge base and generate informed responses.

**AG2 Feature:** `GPTAssistantAgent` with retrieval tools

**Use Case:** Knowledge-intensive tasks, literature review, data analysis.

**Example Phase:**
```python
class RAGPhase(Phase):
    """Retrieve relevant information and generate response."""
    
    def get_required_agents(self):
        return ["retrieve_assistant", "camb_agent"]
    
    async def execute(self, context):
        query = context.task
        
        # Retrieve relevant documents
        docs = retrieve_assistant.retrieve(query)
        
        # Generate response using retrieved context
        response = camb_agent.generate(query, context=docs)
        
        return response
```

---

### 5. Code Review Phase

**Description:** Automated code review with quality checks.

**AG2 Feature:** Multi-agent collaboration with code executors

**Use Case:** Code quality assurance, security checks, best practices enforcement.

**Example Phase:**
```python
class CodeReviewPhase(Phase):
    """Review generated code for quality and correctness."""
    
    async def execute(self, context):
        code = context.input_data['generated_code']
        
        # Multiple reviewers: style, security, performance
        style_review = style_checker.review(code)
        security_review = security_checker.review(code)
        performance_review = performance_checker.review(code)
        
        # Aggregate reviews
        reviews = [style_review, security_review, performance_review]
        
        # If issues found, revise code
        if has_issues(reviews):
            revised_code = engineer.revise(code, reviews)
            return revised_code
        
        return code
```

---

### 6. Teaching/Learning Phase

**Description:** One agent teaches another, or agent learns from examples.

**AG2 Feature:** Dynamic system message updates, context learning

**Use Case:** Skill transfer, few-shot learning, adaptation.

**Example Phase:**
```python
class TeachingPhase(Phase):
    """Teacher agent teaches student agent new skills."""
    
    async def execute(self, context):
        examples = context.input_data['examples']
        
        # Teacher demonstrates
        for example in examples:
            demonstration = teacher.demonstrate(example)
            student.observe(demonstration)
        
        # Student attempts task
        result = student.attempt(context.task)
        
        # Teacher provides feedback
        feedback = teacher.evaluate(result)
        
        return {'result': result, 'feedback': feedback}
```

---

### 7. Sequential Refinement Phase

**Description:** Iteratively refine output through multiple passes.

**AG2 Feature:** Loop with context accumulation

**Use Case:** Writing refinement, progressive detail addition.

**Example Phase:**
```python
class RefinementPhase(Phase):
    """Iteratively refine output through multiple passes."""
    
    async def execute(self, context):
        draft = initial_agent.generate_draft(context.task)
        
        for iteration in range(self.config.max_iterations):
            # Critique current draft
            critique = critic.review(draft)
            
            # If good enough, stop
            if critique['quality_score'] > threshold:
                break
            
            # Refine based on critique
            draft = refiner.improve(draft, critique)
        
        return draft
```

---

### 8. Parallel Exploration Phase

**Description:** Multiple agents explore different approaches in parallel.

**AG2 Feature:** Parallel agent execution

**Use Case:** Solution space exploration, ensemble methods.

**Example Phase:**
```python
class ParallelExplorationPhase(Phase):
    """Multiple agents explore different approaches."""
    
    async def execute(self, context):
        task = context.task
        
        # Launch multiple approaches in parallel
        approaches = [
            agent1.solve(task, approach='analytical'),
            agent2.solve(task, approach='numerical'),
            agent3.solve(task, approach='simulation'),
        ]
        
        results = await asyncio.gather(*approaches)
        
        # Synthesizer combines best elements
        final_solution = synthesizer.combine(results)
        
        return final_solution
```

---

## Usage Examples

### Example 1: Full HITL Workflow with Interactive Planning and Control

```python
from cmbagent.workflows import WorkflowDefinition, WorkflowExecutor

# Define workflow with both HITL phases
full_hitl_workflow = WorkflowDefinition(
    id="full_hitl_research",
    name="Full HITL Research Workflow",
    description="Interactive planning and step-by-step execution",
    phases=[
        {
            "type": "hitl_planning",
            "config": {
                "max_plan_steps": 5,
                "max_human_iterations": 3,
                "require_explicit_approval": True,
                "allow_plan_modification": True,
            }
        },
        {
            "type": "hitl_control",
            "config": {
                "approval_mode": "both",  # Before and after each step
                "allow_step_skip": True,
                "show_step_context": True,
            }
        },
    ]
)

# Execute workflow
executor = WorkflowExecutor(
    workflow=full_hitl_workflow,
    task="Analyze CMB power spectrum with CLASS",
    work_dir="./output",
    api_keys=api_keys,
)

result = await executor.run()
```

---

### Example 2: HITL Planning Only

```python
# Workflow with interactive planning, then autonomous execution
hitl_plan_workflow = WorkflowDefinition(
    id="hitl_plan_auto_execute",
    name="Interactive Planning + Auto Execution",
    phases=[
        {
            "type": "hitl_planning",
            "config": {
                "max_human_iterations": 3,
            }
        },
        {
            "type": "control",  # Standard autonomous control
            "config": {
                "execute_all_steps": True,
            }
        },
    ]
)
```

---

### Example 3: Error-Only HITL

```python
# Autonomous execution with human help only on errors
error_hitl_workflow = WorkflowDefinition(
    id="error_hitl",
    name="Autonomous with Error Recovery",
    phases=[
        {
            "type": "planning",  # Autonomous planning
            "config": {}
        },
        {
            "type": "hitl_control",
            "config": {
                "approval_mode": "on_error",  # Only intervene on errors
                "allow_step_retry": True,
                "allow_step_skip": True,
            }
        },
    ]
)
```

---

### Example 4: Teaching Mode with ALWAYS Input

```python
# Use admin agent in ALWAYS mode for teaching
teaching_workflow = WorkflowDefinition(
    id="teaching_mode",
    name="Teaching/Demo Mode",
    phases=[
        {
            "type": "hitl_planning",
            "config": {
                "require_explicit_approval": True,
                "show_intermediate_plans": True,
            }
        },
        {
            "type": "hitl_control",
            "config": {
                "approval_mode": "both",
                "show_step_context": True,
            }
        },
    ]
)
```

---

## Comparison with Existing HITL

| Feature | `HITLCheckpointPhase` | `HITLPlanningPhase` | `HITLControlPhase` |
|---------|----------------------|---------------------|-------------------|
| **Purpose** | Gate between phases | Interactive planning | Interactive execution |
| **Timing** | Between phases | During planning | During control |
| **Iterations** | Single checkpoint | Multiple iterations | Per-step control |
| **Feedback** | Approve/reject/modify | Iterative refinement | Step-by-step approval |
| **Error Handling** | N/A | Revision requests | Retry/skip/abort |
| **Granularity** | Coarse (phase-level) | Medium (plan-level) | Fine (step-level) |

### When to Use Each

**Use `HITLCheckpointPhase` when:**
- You want simple approval gates between phases
- One-time review is sufficient
- No iterative refinement needed

**Use `HITLPlanningPhase` when:**
- Planning requires domain expertise
- Plan quality is critical
- You want to guide the planning process
- Multiple revisions may be needed

**Use `HITLControlPhase` when:**
- Fine-grained execution control is needed
- Steps may fail and need human decisions
- You want to review results progressively
- Dynamic workflow adjustment is required

---

## Summary

### New Phases

1. **HITLPlanningPhase**: Interactive planning with iterative human feedback
2. **HITLControlPhase**: Step-by-step execution with human approval and error handling

### AG2 Human Input Modes

1. **NEVER**: Fully autonomous (default for agents)
2. **TERMINATE**: Review at termination points
3. **ALWAYS**: Review every message (admin agent)

### Potential Future Phases from AG2 Patterns

1. **NestedChatPhase**: Isolated sub-conversations
2. **ReflectionPhase**: Self-improvement and quality checks
3. **DebatePhase**: Multi-agent consensus building
4. **RAGPhase**: Knowledge retrieval and generation
5. **CodeReviewPhase**: Automated code quality assurance
6. **TeachingPhase**: Skill transfer between agents
7. **RefinementPhase**: Iterative output improvement
8. **ParallelExplorationPhase**: Multi-approach exploration

These phases can be combined in workflows to create sophisticated, human-guided AI systems.

---

*HITL Phases Documentation*
*Version 1.0*
*January 2026*
