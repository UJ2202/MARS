# Phase Development Guide

This guide explains how to create new phases for the CMBAgent workflow system.

## Overview

The phase-based workflow system provides:
1. **Modular execution**: Each phase handles a specific part of the workflow
2. **Automatic infrastructure**: Callbacks, logging, DAG tracking, file tracking
3. **Context passing**: Data flows between phases seamlessly
4. **Pause/cancel support**: Workflows can be paused or cancelled at phase boundaries

## Quick Start: Creating a New Phase

### 1. Create the Phase File

Create a new file `cmbagent/phases/my_phase.py`:

```python
"""
My custom phase implementation.

Uses PhaseExecutionManager for automatic:
- Callback invocation
- Database event logging
- DAG node management
- File tracking
- Pause/cancel handling
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import time

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.execution_manager import PhaseExecutionManager


@dataclass
class MyPhaseConfig(PhaseConfig):
    """Configuration for my phase."""
    phase_type: str = "my_phase"
    
    # Add your phase-specific config options here
    my_option: str = "default_value"
    max_iterations: int = 10


class MyPhase(Phase):
    """
    Description of what this phase does.
    
    Input Context:
        - Describe what data this phase expects from previous phases
        
    Output Context:
        - Describe what data this phase produces for next phases
    """
    
    config_class = MyPhaseConfig
    
    def __init__(self, config: MyPhaseConfig = None):
        if config is None:
            config = MyPhaseConfig()
        super().__init__(config)
        self.config: MyPhaseConfig = config
    
    @property
    def phase_type(self) -> str:
        return "my_phase"
    
    @property
    def display_name(self) -> str:
        return "My Phase"
    
    def get_required_agents(self) -> List[str]:
        """Return list of agents this phase uses."""
        return ["engineer"]  # Adjust based on your phase
    
    async def execute(self, context: PhaseContext) -> PhaseResult:
        """Execute the phase."""
        # Create execution manager for automatic infrastructure
        manager = PhaseExecutionManager(context, self)
        manager.start()
        
        self._status = PhaseStatus.RUNNING
        
        try:
            # Check for pause/cancel before starting
            manager.raise_if_cancelled()
            
            # Your phase logic here
            result_data = self._do_work(context, manager)
            
            # Build output for next phase
            output_data = {
                'my_result': result_data,
                'shared': {
                    # Data to carry to next phases
                    'my_shared_data': result_data,
                }
            }
            
            self._status = PhaseStatus.COMPLETED
            return manager.complete(output_data=output_data)
            
        except Exception as e:
            self._status = PhaseStatus.FAILED
            import traceback
            return manager.fail(str(e), traceback.format_exc())
    
    def _do_work(self, context: PhaseContext, manager: PhaseExecutionManager) -> Dict:
        """Your phase-specific logic."""
        # Example: Process in steps
        for i in range(self.config.max_iterations):
            # Check for cancellation periodically
            manager.raise_if_cancelled()
            
            # Log progress
            manager.log_event("iteration", {"step": i})
            
            # Do work...
            
        return {"status": "done"}
    
    def validate_input(self, context: PhaseContext) -> List[str]:
        """Validate that required input is present."""
        errors = []
        if not context.task:
            errors.append("Task is required")
        return errors
```

### 2. Register the Phase

Add to `cmbagent/phases/__init__.py`:

```python
# Import your phase
from cmbagent.phases.my_phase import MyPhase, MyPhaseConfig

# Register with registry
PhaseRegistry.register_class("my_phase", MyPhase)

# Add to __all__
__all__ = [
    ...
    'MyPhase',
    'MyPhaseConfig',
]
```

### 3. Use in Workflows

Create a workflow that uses your phase:

```python
from cmbagent.workflows.composer import WorkflowDefinition, WorkflowExecutor

workflow = WorkflowDefinition(
    id="my_workflow",
    name="My Custom Workflow",
    description="Uses my custom phase",
    phases=[
        {
            "type": "planning",
            "config": {"max_plan_steps": 3}
        },
        {
            "type": "my_phase",  # Your new phase
            "config": {"my_option": "custom_value"}
        },
        {
            "type": "control",
            "config": {}
        }
    ]
)

executor = WorkflowExecutor(
    workflow=workflow,
    task="Do something",
    work_dir="/path/to/work",
    api_keys=api_keys,
)

result = executor.run_sync()
```

## PhaseExecutionManager Features

The `PhaseExecutionManager` provides these features automatically:

### Callbacks

```python
# Callbacks are invoked automatically by manager.start() and manager.complete()
# For step-based phases:
manager.start_step(1, "First step")  # Invokes step_start callback
manager.complete_step(1, "Step done")  # Invokes step_complete callback
manager.fail_step(1, "Error message")  # Invokes step_failed callback
```

### Event Logging

```python
# Log agent messages (also invokes on_agent_message callback)
manager.log_agent_message("engineer", "assistant", "Hello world", {"step": 1})

# Log code execution (also invokes on_code_execution callback)
manager.log_code_execution("engineer", "print('hello')", "python", "hello")

# Log tool calls (also invokes on_tool_call callback)
manager.log_tool_call("engineer", "search", {"query": "CMB"}, {"results": [...]})

# Log custom events
manager.log_event("my_custom_event", {"data": "value"})
```

### File Tracking

```python
# Track individual files
manager.track_file("/path/to/output.png")

# Files are auto-scanned in work_dir when phase completes
```

### Pause/Cancel Support

```python
# Check if cancelled (non-blocking)
if not manager.check_should_continue():
    return manager.fail("Cancelled by user")

# Raise exception if cancelled (use in loops)
manager.raise_if_cancelled()
```

### Checkpoints

```python
# Save checkpoint for recovery
checkpoint_path = manager.save_checkpoint("step_5", {"state": data})

# Load checkpoint
data = manager.load_checkpoint("step_5")
```

## Phase Lifecycle

1. **Initialization**: Phase config is loaded and validated
2. **Start**: `manager.start()` records start time, creates DAG node, logs phase_start
3. **Execution**: Your phase logic runs
4. **Completion**: `manager.complete()` or `manager.fail()` records end time, updates DAG

## Context Flow

Data flows between phases via `PhaseContext`:

```
Phase A                      Phase B
┌─────────────────────┐     ┌─────────────────────┐
│ context.input_data  │ ──► │ context.input_data  │ (= A's output_data)
│                     │     │                     │
│ context.output_data │ ──► │                     │
│  └─ shared: {...}   │     │ context.shared_state│ (merged shared data)
└─────────────────────┘     └─────────────────────┘
```

### Input Data

Access data from previous phase:
```python
plan = context.input_data.get('final_plan')
prev_result = context.input_data.get('my_result')
```

### Shared State

Access accumulated state from all previous phases:
```python
plan_steps = context.shared_state.get('plan_steps')
```

### Output Data

Set data for next phase:
```python
context.output_data = {
    'my_result': result,
    'shared': {
        'data_for_all_future_phases': value
    }
}
```

## Available Phase Types

| Type | Class | Description |
|------|-------|-------------|
| `planning` | `PlanningPhase` | Generate structured plans |
| `control` | `ControlPhase` | Execute plan steps |
| `one_shot` | `OneShotPhase` | Single-shot execution |
| `hitl_checkpoint` | `HITLCheckpointPhase` | Human approval gates |
| `idea_generation` | `IdeaGenerationPhase` | Generate and review ideas |

## Best Practices

1. **Always use PhaseExecutionManager** for consistent behavior
2. **Check for cancellation** in long loops
3. **Log important events** for debugging and tracking
4. **Validate input** in `validate_input()` method
5. **Use shared state** for data that multiple phases need
6. **Track important files** so they appear in the DAG/UI
7. **Handle exceptions** and return proper `PhaseResult`

## CMBAgent Initialization: Critical Guidelines

When creating phases that use `CMBAgent`, follow these **mandatory patterns** to avoid runtime errors:

### 1. Agent Configuration Pattern

**✅ CORRECT:**
```python
from cmbagent.cmbagent import CMBAgent
from cmbagent.utils import get_model_config

# Get model configs
planner_config = get_model_config(self.config.planner_model, api_keys)
reviewer_config = get_model_config(self.config.plan_reviewer_model, api_keys)

# Initialize with agent_llm_configs
cmbagent = CMBAgent(
    cache_seed=42,
    work_dir=context.work_dir,
    agent_llm_configs={
        'planner': planner_config,
        'plan_reviewer': reviewer_config,
    },
    api_keys=api_keys,
)
```

**❌ WRONG:**
```python
# DON'T: Create empty then assign
cmbagent = CMBAgent()
cmbagent.llm_config = planner_config
cmbagent.set_agents_from_names(['planner'])  # Method doesn't exist!
```

### 2. Required Agents by Phase Type

**Planning Phase:**
- Must include: `planner`, `plan_reviewer`
- Auto-created: `plan_setter`, `planner_response_formatter`, `task_improver`, etc.

**Control Phase:**
- Must include: `engineer`, `researcher`, `web_surfer`, `retrieve_assistant`, `idea_maker`, `idea_hater`, `camb_context`, `plot_judge`
- Auto-created: `control`, `control_starter`, `executor`, etc.
- Must set: `mode="planning_and_control_context_carryover"`

### 3. solve() Method Parameters

**Planning phases:**
```python
cmbagent.solve(
    task=task_with_feedback,
    initial_agent='plan_setter',  # NOT 'planner'!
    max_rounds=self.config.max_rounds,
    shared_context={
        'feedback_left': self.config.n_plan_reviews,
        'max_n_attempts': self.config.max_n_attempts,
        'maximum_number_of_steps_in_plan': self.config.max_plan_steps,
        'planner_append_instructions': self.config.plan_instructions,
        'engineer_append_instructions': self.config.engineer_instructions,
        'researcher_append_instructions': self.config.researcher_instructions,
        'plan_reviewer_append_instructions': self.config.plan_instructions,
        'hardware_constraints': self.config.hardware_constraints,
        **context.shared_state,  # Carry over shared state
    }
)
```

**Control phases:**
```python
cmbagent.solve(
    task=step_task,
    initial_agent='control',
    max_rounds=self.config.max_rounds,
    shared_context={
        'current_plan_step_number': step_num,
        'n_attempts': attempt - 1,
        'agent_for_sub_task': step.get('sub_task_agent'),
        'engineer_append_instructions': self.config.engineer_instructions,
        'researcher_append_instructions': self.config.researcher_instructions,
        **accumulated_context,
    },
    step=step_num,  # CRITICAL: Must pass step number
)
```

### 4. Extracting Results

**After solve() completes:**
```python
# ✅ CORRECT: Access final_context
cmbagent.solve(...)
planning_context = cmbagent.final_context
plan = planning_context.get('final_plan')

# ❌ WRONG: Don't assign return value
planning_context = cmbagent.solve(...)  # Returns None!
```

### 5. Plan Extraction

Plans are stored in Pydantic models with `sub_tasks` field:

```python
def _extract_plan(self, planning_context: Dict) -> List[Dict]:
    """Extract plan from planning context."""
    raw_plan = planning_context.get('final_plan')
    
    # Handle Pydantic models
    if hasattr(raw_plan, 'model_dump'):  # Pydantic v2
        plan_dict = raw_plan.model_dump()
        return plan_dict.get('sub_tasks', [])
    elif hasattr(raw_plan, 'dict'):  # Pydantic v1
        plan_dict = raw_plan.dict()
        return plan_dict.get('sub_tasks', [])
    elif isinstance(raw_plan, dict):
        return raw_plan.get('sub_tasks', [])
    elif isinstance(raw_plan, list):
        return raw_plan
    
    return []
```

### 6. Chat History Collection

Always collect chat history for callbacks and logging:

```python
# At end of phase
chat_history = []
if hasattr(cmbagent, 'chat_result') and cmbagent.chat_result:
    chat_history = cmbagent.chat_result.chat_history or []

return manager.complete(
    output_data=output_data,
    chat_history=chat_history,  # Required!
)
```

### 7. Common Pitfalls to Avoid

| Issue | Symptom | Solution |
|-------|---------|----------|
| Missing agent configs | "Agent X not found" | Add all required agents to `agent_llm_configs` |
| Wrong initial_agent | "Failed to generate plan" | Use `plan_setter` for planning, `control` for execution |
| Missing mode parameter | Context not carried over | Add `mode="planning_and_control_context_carryover"` for control |
| Missing step parameter | Execution fails | Add `step=step_num` to control solve() calls |
| Wrong plan extraction | "Failed to generate plan" | Extract `sub_tasks` from Pydantic model |
| Missing shared_context | Missing instructions/feedback | Always pass `shared_context` dict |
| No chat_history | Callbacks don't work | Collect and pass `chat_result.chat_history` |

### 8. Reference Implementation Checklist

When creating a new phase with CMBAgent, verify:

- [ ] All required agents in `agent_llm_configs`
- [ ] Correct `initial_agent` for phase type
- [ ] `mode` parameter set (if control phase)
- [ ] `shared_context` with all required fields
- [ ] `step` parameter (if control phase)
- [ ] Extract results from `cmbagent.final_context`
- [ ] Handle Pydantic models in plan extraction
- [ ] Collect and pass `chat_history`
- [ ] Config class includes all agent model fields

**Golden Rule:** When in doubt, copy patterns from `planning.py` or `control.py` - they are the reference implementations!

## Testing a Phase

```python
import asyncio
from cmbagent.phases import PhaseContext
from cmbagent.phases.my_phase import MyPhase, MyPhaseConfig

async def test_my_phase():
    config = MyPhaseConfig(my_option="test")
    phase = MyPhase(config)
    
    context = PhaseContext(
        workflow_id="test",
        run_id="test-run",
        phase_id="test-phase",
        task="Test task",
        work_dir="/tmp/test",
        api_keys={},
    )
    
    result = await phase.execute(context)
    
    assert result.succeeded
    print(f"Output: {result.context.output_data}")

asyncio.run(test_my_phase())
```
