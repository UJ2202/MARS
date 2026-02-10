# HITL Phases Implementation Summary

## What Was Created

### 1. Two New HITL Phases

#### HITLPlanningPhase (`cmbagent/phases/hitl_planning.py`)
- **Purpose**: Interactive planning with iterative human feedback
- **Features**:
  - Review plans at each iteration
  - Provide feedback for plan revision
  - Approve, reject, or directly modify plans
  - Multiple iterations (configurable: default 3)
  - Feedback history accumulated across iterations
  - Auto-approval after N iterations

#### HITLControlPhase (`cmbagent/phases/hitl_control.py`)
- **Purpose**: Step-by-step execution with human approval and error handling
- **Features**:
  - Four approval modes: `before_step`, `after_step`, `both`, `on_error`
  - Error handling with retry/skip/abort options
  - Step skipping capability
  - Context visibility before each step
  - Auto-approve successful steps (optional)

### 2. Documentation Created

#### Main Guide (`docs/HITL_PHASES_GUIDE.md`)
Comprehensive documentation covering:
- Detailed description of both new phases
- Configuration options and examples
- AG2's three human_input_modes (NEVER, TERMINATE, ALWAYS)
- 8 potential future phases based on AG2 patterns
- Usage examples and comparisons
- When to use each phase type

#### Examples (`examples/hitl_phases_examples.py`)
Seven practical examples:
1. Full HITL (planning + control)
2. HITL planning + auto execution
3. Autonomous with error recovery
4. Before-step approval
5. After-step review
6. Teaching/demo mode
7. Progressive automation pattern

### 3. Registration
- Both phases registered in `cmbagent/phases/__init__.py`
- Available for use via `PhaseRegistry`

---

## AG2 Human Input Modes

### Overview

AG2 provides three built-in `human_input_mode` options:

| Mode | Behavior | CMBAgent Usage |
|------|----------|----------------|
| **NEVER** | Fully autonomous, no human input | Default for most agents (executor, engineer, etc.) |
| **TERMINATE** | Ask for input at TERMINATE signals | Review-at-checkpoint mode |
| **ALWAYS** | Ask for input after every message | Admin agent, maximum control |

### Detailed Explanation

#### 1. NEVER (Autonomous)
```yaml
human_input_mode: "NEVER"
```
- Agent runs completely autonomously
- No human intervention during execution
- Used by: executor, executor_bash, researcher_executor
- Best for: Background processing, code execution

#### 2. TERMINATE (Checkpoint)
```yaml
human_input_mode: "TERMINATE"
```
- Agent runs autonomously
- Pauses when TERMINATE message received
- Human can review and provide feedback
- Best for: Final review, checkpoint approval

#### 3. ALWAYS (Full Control)
```yaml
human_input_mode: "ALWAYS"
```
- Agent pauses after EVERY message
- Human reviews and approves each action
- Used by: admin agent
- Best for: Critical operations, teaching, debugging

---

## Other AG2 Modes as Phases

The documentation describes 8 potential future phases based on AG2 capabilities:

### 1. **NestedChatPhase**
- Execute isolated sub-conversations between specific agents
- Based on: `register_nested_chats()`
- Use case: Isolated sub-tasks

### 2. **ReflectionPhase**
- Agent reflects on and improves its own outputs
- Based on: AG2 reflection capabilities
- Use case: Quality improvement, self-correction

### 3. **Multi-Agent Debate Phase**
- Multiple agents debate and reach consensus
- Based on: Group chat with debate patterns
- Use case: Complex decisions, multiple perspectives

### 4. **RAG Phase**
- Query knowledge base and generate informed responses
- Based on: `GPTAssistantAgent` with retrieval
- Use case: Knowledge-intensive tasks, literature review

### 5. **Code Review Phase**
- Automated code review with quality checks
- Based on: Multi-agent collaboration
- Use case: Code quality assurance, security

### 6. **Teaching/Learning Phase**
- One agent teaches another
- Based on: Dynamic system message updates
- Use case: Skill transfer, adaptation

### 7. **Sequential Refinement Phase**
- Iteratively refine output through multiple passes
- Based on: Loop with context accumulation
- Use case: Writing refinement, progressive detail

### 8. **Parallel Exploration Phase**
- Multiple agents explore different approaches in parallel
- Based on: Parallel agent execution
- Use case: Solution space exploration, ensemble methods

---

## Quick Start Examples

### Example 1: Full HITL Workflow
```python
from cmbagent.workflows import WorkflowDefinition, WorkflowExecutor

workflow = WorkflowDefinition(
    id="full_hitl",
    name="Full HITL Research",
    phases=[
        {
            "type": "hitl_planning",
            "config": {
                "max_human_iterations": 3,
                "allow_plan_modification": True,
            }
        },
        {
            "type": "hitl_control",
            "config": {
                "approval_mode": "both",  # Before AND after each step
                "allow_step_skip": True,
            }
        },
    ]
)

executor = WorkflowExecutor(
    workflow=workflow,
    task="Calculate CMB power spectrum",
    work_dir="./output",
    api_keys=api_keys,
)

result = await executor.run()
```

### Example 2: Error-Only HITL
```python
workflow = WorkflowDefinition(
    id="error_hitl",
    name="Autonomous with Error Recovery",
    phases=[
        {"type": "planning", "config": {}},
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

### Example 3: HITL Planning Only
```python
workflow = WorkflowDefinition(
    id="hitl_plan_auto",
    name="HITL Planning + Auto Execute",
    phases=[
        {
            "type": "hitl_planning",
            "config": {"max_human_iterations": 2}
        },
        {
            "type": "control",  # Standard autonomous control
            "config": {"execute_all_steps": True}
        },
    ]
)
```

---

## Approval Modes (HITLControlPhase)

### before_step
```
Step → [HUMAN APPROVAL] → Execute → Step → [APPROVAL] → Execute
```
- Human approves each step **before** execution
- Options: Approve / Skip / Reject

### after_step
```
Step → Execute → [HUMAN REVIEW] → Step → Execute → [REVIEW]
```
- Human reviews results **after** each step
- Options: Continue / Redo / Abort

### both
```
Step → [APPROVAL] → Execute → [REVIEW] → Step → [APPROVAL] → Execute
```
- Maximum control: approval before + review after
- Best for: Critical workflows, teaching

### on_error
```
Step → Execute (success) → Step → Execute (FAILED) → [INTERVENTION]
```
- Autonomous until error occurs
- Human decides: Retry / Skip / Abort
- Best for: Mostly reliable workflows with occasional issues

---

## Comparison: HITL Phases

| Feature | HITLCheckpointPhase | HITLPlanningPhase | HITLControlPhase |
|---------|---------------------|-------------------|------------------|
| **Timing** | Between phases | During planning | During execution |
| **Granularity** | Coarse (phase) | Medium (plan) | Fine (step) |
| **Iterations** | Single | Multiple | Per-step |
| **Feedback** | Approve/reject | Iterative refinement | Step-by-step control |
| **Error Handling** | N/A | Revision | Retry/skip/abort |
| **Best For** | Simple gates | Plan quality | Execution control |

---

## File Structure

```
cmbagent/
├── phases/
│   ├── hitl_planning.py          # NEW: Interactive planning phase
│   ├── hitl_control.py           # NEW: Step-by-step control phase
│   └── __init__.py               # UPDATED: Registration
docs/
└── HITL_PHASES_GUIDE.md          # NEW: Comprehensive guide
examples/
└── hitl_phases_examples.py       # NEW: 7 usage examples
```

---

## Next Steps

### To Use These Phases:

1. **Import the phases:**
   ```python
   from cmbagent.phases import HITLPlanningPhase, HITLControlPhase
   from cmbagent.workflows import WorkflowDefinition, WorkflowExecutor
   ```

2. **Create a workflow:**
   ```python
   workflow = WorkflowDefinition(
       id="my_workflow",
       phases=[
           {"type": "hitl_planning", "config": {...}},
           {"type": "hitl_control", "config": {...}},
       ]
   )
   ```

3. **Execute:**
   ```python
   executor = WorkflowExecutor(workflow=workflow, task="...", ...)
   result = await executor.run()
   ```

### To Implement Future Phases:

1. Review the 8 proposed phases in `HITL_PHASES_GUIDE.md`
2. Follow the pattern in `PHASE_DEVELOPMENT_GUIDE.md`
3. Use `PhaseExecutionManager` for automatic infrastructure
4. Register the phase in `phases/__init__.py`

---

## Key Innovations

1. **Iterative Planning**: Unlike HITLCheckpointPhase (single approval), HITLPlanningPhase supports multiple refinement iterations

2. **Flexible Approval Modes**: Four different approval modes for different use cases

3. **Error Recovery**: Human-in-the-loop error handling with retry/skip/abort

4. **Context Visibility**: Show accumulated context at each step

5. **Progressive Automation**: Support for gradually reducing human intervention

---

## Documentation References

- **HITL_PHASES_GUIDE.md**: Comprehensive guide with all details
- **PHASE_DEVELOPMENT_GUIDE.md**: How to create new phases
- **PHASE_IMPLEMENTATION.md**: Phase architecture overview
- **AG2_INTEGRATION_GUIDE.md**: AG2 framework integration details
- **hitl_phases_examples.py**: 7 practical usage examples

---

*Created: January 2026*
*CMBAgent Phase System v1.0*
