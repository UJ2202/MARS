# Phase-Based Workflow Implementation

> **Implementation Documentation**
> **Date:** January 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Directory Structure](#directory-structure)
4. [Core Components](#core-components)
5. [Phase Types](#phase-types)
6. [Workflow Definitions](#workflow-definitions)
7. [Backend API](#backend-api)
8. [Usage Examples](#usage-examples)
9. [Migration from Legacy](#migration-from-legacy)

---

## Overview

### What Was Implemented

The phase-based workflow system refactors CMBAgent's workflow execution from monolithic functions into composable, reusable phases. This enables:

- **Modularity**: Each phase is an independent unit that can be tested and reused
- **Composability**: Create new workflows by combining existing phases
- **Configurability**: Configure phase parameters via API or code
- **HITL Support**: Add human-in-the-loop checkpoints anywhere in a workflow
- **Extensibility**: Add new phases without modifying existing code

### Key Benefits

| Benefit | Description |
|---------|-------------|
| Reusability | Same phase can be used in multiple workflows |
| Testability | Test phases in isolation |
| Flexibility | Add HITL, validation, or custom phases easily |
| UI Configuration | Phases and workflows configurable from UI |
| Backwards Compatible | Legacy functions still work unchanged |

---

## Architecture

### Before (Monolithic)

```
planning_and_control_context_carryover()
├── [EMBEDDED] Planning Phase
│   ├── Initialize CMBAgent
│   ├── solve() with plan_setter
│   └── Save plan to JSON
├── [EMBEDDED] Control Phase (loop)
│   ├── Initialize CMBAgent
│   ├── solve() with control agent
│   └── Context carryover
```

### After (Phase-Based)

```
WorkflowExecutor
├── PhaseRegistry (registered phases)
│   ├── PlanningPhase
│   ├── ControlPhase
│   ├── OneShotPhase
│   ├── HITLCheckpointPhase
│   └── IdeaGenerationPhase
├── WorkflowDefinition (phase sequence)
│   └── [{type: "planning"}, {type: "control"}, ...]
└── Context Flow
    └── Phase 1 → Context → Phase 2 → Context → Phase 3
```

---

## Directory Structure

```
cmbagent/
├── phases/                          # NEW: Phase system
│   ├── __init__.py                  # Module exports & registration
│   ├── base.py                      # Phase, PhaseContext, PhaseResult, PhaseConfig
│   ├── context.py                   # WorkflowContext
│   ├── registry.py                  # PhaseRegistry
│   ├── planning.py                  # PlanningPhase
│   ├── control.py                   # ControlPhase
│   ├── one_shot.py                  # OneShotPhase
│   ├── hitl_checkpoint.py           # HITLCheckpointPhase
│   └── idea_generation.py           # IdeaGenerationPhase
│
├── workflows/
│   ├── __init__.py                  # UPDATED: Exports new + legacy
│   ├── composer.py                  # NEW: WorkflowDefinition, WorkflowExecutor
│   ├── legacy/                      # NEW: Backup of original files
│   │   ├── planning_control.py
│   │   ├── one_shot.py
│   │   └── control.py
│   ├── planning_control.py          # UNCHANGED: Legacy function
│   ├── one_shot.py                  # UNCHANGED: Legacy function
│   └── control.py                   # UNCHANGED: Legacy function
│
backend/
├── models/
│   └── phase_schemas.py             # NEW: Pydantic schemas
├── routers/
│   ├── __init__.py                  # UPDATED: Register phases router
│   └── phases.py                    # NEW: REST API endpoints
│
tests/
└── test_phases_api.py               # NEW: API tests (18 tests)
```

---

## Core Components

### 1. PhaseStatus (Enum)

```python
class PhaseStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
```

### 2. PhaseContext (Dataclass)

Context that flows between phases:

```python
@dataclass
class PhaseContext:
    # Identification
    workflow_id: str
    run_id: str
    phase_id: str

    # Task info
    task: str
    work_dir: str

    # State management
    shared_state: Dict[str, Any]    # Carried between phases
    input_data: Dict[str, Any]      # From previous phase
    output_data: Dict[str, Any]     # For next phase

    # Credentials & callbacks
    api_keys: Dict[str, str]
    callbacks: Optional[Any]
```

### 3. PhaseResult (Dataclass)

Result of phase execution:

```python
@dataclass
class PhaseResult:
    status: PhaseStatus
    context: PhaseContext
    error: Optional[str]
    chat_history: List[Dict]
    timing: Dict[str, float]

    @property
    def succeeded(self) -> bool

    @property
    def needs_approval(self) -> bool
```

### 4. Phase (Abstract Base Class)

All phases inherit from this:

```python
class Phase(ABC):
    def __init__(self, config: PhaseConfig)

    @property
    @abstractmethod
    def phase_type(self) -> str

    @property
    @abstractmethod
    def display_name(self) -> str

    @abstractmethod
    async def execute(self, context: PhaseContext) -> PhaseResult

    def validate_input(self, context: PhaseContext) -> List[str]
    def get_required_agents(self) -> List[str]
    def can_skip(self, context: PhaseContext) -> bool
```

### 5. PhaseRegistry

Registry for phase types:

```python
class PhaseRegistry:
    @classmethod
    def register(cls, phase_type: str)  # Decorator

    @classmethod
    def create(cls, phase_type: str, config=None) -> Phase

    @classmethod
    def create_from_dict(cls, phase_def: Dict) -> Phase

    @classmethod
    def list_all(cls) -> List[str]

    @classmethod
    def get_info(cls, phase_type: str) -> Dict
```

### 6. WorkflowDefinition

Defines a workflow as a sequence of phases:

```python
@dataclass
class WorkflowDefinition:
    id: str
    name: str
    description: str
    phases: List[Dict[str, Any]]  # [{type: "...", config: {...}}]
    version: int = 1
    is_system: bool = False
```

### 7. WorkflowExecutor

Executes workflows:

```python
class WorkflowExecutor:
    def __init__(
        self,
        workflow: WorkflowDefinition,
        task: str,
        work_dir: str,
        api_keys: Dict[str, str],
        callbacks: Any = None,
        approval_manager: Any = None,
    )

    async def run(self) -> WorkflowContext
    def run_sync(self) -> WorkflowContext
    def stop(self)
    def get_status(self) -> Dict[str, Any]
```

---

## Phase Types

### 1. PlanningPhase

Generates a structured plan for task execution.

**Configuration:**
```python
@dataclass
class PlanningPhaseConfig:
    max_rounds: int = 50
    max_plan_steps: int = 3
    n_plan_reviews: int = 1
    planner_model: str = "gpt-4.1-2025-04-14"
    plan_reviewer_model: str = "o3-mini-2025-01-31"
    plan_instructions: str = ""
    hardware_constraints: str = ""
```

**Input:** task, work_dir, api_keys
**Output:** final_plan, plan_file_path, planning_context

### 2. ControlPhase

Executes plan steps with context carryover.

**Configuration:**
```python
@dataclass
class ControlPhaseConfig:
    max_rounds: int = 100
    max_n_attempts: int = 3
    execute_all_steps: bool = True
    step_number: Optional[int] = None
    hitl_enabled: bool = False
    hitl_after_each_step: bool = False
    engineer_model: str = "gpt-4.1-2025-04-14"
    researcher_model: str = "gpt-4.1-2025-04-14"
```

**Input:** plan_steps, task, planning_context
**Output:** step_results, final_context, step_summaries

### 3. OneShotPhase

Single-shot task execution without planning.

**Configuration:**
```python
@dataclass
class OneShotPhaseConfig:
    max_rounds: int = 50
    max_n_attempts: int = 3
    agent: str = "engineer"
    evaluate_plots: bool = False
```

**Input:** task, work_dir
**Output:** result, chat_history

### 4. HITLCheckpointPhase

Human-in-the-loop approval gate.

**Configuration:**
```python
@dataclass
class HITLCheckpointConfig:
    checkpoint_type: str = "after_planning"
    require_approval: bool = True
    timeout_seconds: int = 3600
    default_on_timeout: str = "reject"
    show_plan: bool = True
    custom_message: str = ""
    options: List[str] = ["approve", "reject", "modify"]
```

**Input:** Any context from previous phase
**Output:** approval_status, user_feedback, modifications

### 5. IdeaGenerationPhase

Generates and reviews research ideas.

**Configuration:**
```python
@dataclass
class IdeaGenerationPhaseConfig:
    max_rounds: int = 50
    n_ideas: int = 3
    n_reviews: int = 1
    idea_maker_model: str = "gpt-4.1-2025-04-14"
    idea_hater_model: str = "o3-mini-2025-01-31"
```

**Input:** task (research topic)
**Output:** ideas, reviews, selected_idea

---

## Workflow Definitions

### Pre-defined System Workflows

| ID | Name | Phases |
|----|------|--------|
| `deep_research` | Deep Research | Planning → Control |
| `deep_research_hitl` | Deep Research with HITL | Planning → HITL → Control |
| `deep_research_full_hitl` | Deep Research with Full HITL | Planning → HITL → Control (HITL per step) |
| `one_shot` | Quick Task | OneShotPhase (engineer) |
| `one_shot_researcher` | Quick Research | OneShotPhase (researcher) |
| `idea_generation` | Idea Generation | IdeaGeneration → HITL |
| `idea_to_execution` | Idea to Execution | IdeaGen → HITL → Planning → HITL → Control |

### Custom Workflow Example

```python
from cmbagent.workflows import WorkflowDefinition, WorkflowExecutor

# Define custom workflow
my_workflow = WorkflowDefinition(
    id="my_custom_workflow",
    name="My Custom Workflow",
    description="Custom workflow with validation",
    phases=[
        {"type": "planning", "config": {"max_plan_steps": 5}},
        {"type": "hitl_checkpoint", "config": {"checkpoint_type": "after_planning"}},
        {"type": "control", "config": {"max_rounds": 150}},
    ]
)

# Execute
executor = WorkflowExecutor(
    workflow=my_workflow,
    task="Analyze CMB data",
    work_dir="./output",
    api_keys=api_keys,
)
result = await executor.run()
```

---

## Backend API

### Phase Type Endpoints

```
GET  /api/phases/types                              # List all phase types
GET  /api/phases/types/{phase_type}                 # Get phase type details
GET  /api/phases/types/{phase_type}/config-schema   # Get config schema
```

### Workflow Definition Endpoints

```
GET    /api/phases/workflows                        # List all workflows
GET    /api/phases/workflows/{workflow_id}          # Get workflow definition
POST   /api/phases/workflows                        # Create custom workflow
PUT    /api/phases/workflows/{workflow_id}          # Update custom workflow
DELETE /api/phases/workflows/{workflow_id}          # Delete custom workflow
POST   /api/phases/workflows/validate               # Validate workflow
```

### Workflow Execution Endpoints

```
POST /api/phases/workflows/{workflow_id}/run        # Start workflow run
GET  /api/phases/runs                               # List all runs
GET  /api/phases/runs/{run_id}                      # Get run status
GET  /api/phases/runs/{run_id}/phases               # Get phase details
POST /api/phases/runs/{run_id}/stop                 # Stop running workflow
```

### API Usage Examples

**List workflows:**
```bash
curl http://localhost:8000/api/phases/workflows
```

**Response:**
```json
[
  {
    "id": "deep_research",
    "name": "Deep Research",
    "description": "Planning followed by multi-step execution",
    "num_phases": 2,
    "is_system": true
  },
  ...
]
```

**Start a workflow run:**
```bash
curl -X POST http://localhost:8000/api/phases/workflows/deep_research/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze CMB temperature fluctuations",
    "work_dir": "~/cmbagent_output"
  }'
```

**Response:**
```json
{
  "run_id": "abc123-...",
  "workflow_id": "deep_research",
  "workflow_name": "Deep Research",
  "status": "pending",
  "message": "Workflow run started",
  "num_phases": 2
}
```

**Check run status:**
```bash
curl http://localhost:8000/api/phases/runs/abc123-...
```

---

## Usage Examples

### Python API Usage

```python
# Option 1: Use pre-defined workflow
from cmbagent.workflows import WorkflowExecutor, get_workflow
from cmbagent.utils import get_api_keys_from_env

workflow = get_workflow('deep_research_hitl')
executor = WorkflowExecutor(
    workflow=workflow,
    task="Compute CMB power spectrum using CAMB",
    work_dir="./output",
    api_keys=get_api_keys_from_env(),
)

# Async execution
result = await executor.run()

# Or sync execution
result = executor.run_sync()
```

```python
# Option 2: Use individual phases
from cmbagent.phases import PlanningPhase, PhaseContext

phase = PlanningPhase(config=PlanningPhaseConfig(
    max_plan_steps=5,
    n_plan_reviews=2,
))

context = PhaseContext(
    workflow_id="manual",
    run_id="test-123",
    phase_id="planning",
    task="My task",
    work_dir="./output",
    api_keys=api_keys,
)

result = await phase.execute(context)
print(f"Plan: {result.context.output_data['final_plan']}")
```

### Adding a New Phase

```python
from dataclasses import dataclass
from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.registry import PhaseRegistry

@dataclass
class ValidationPhaseConfig(PhaseConfig):
    phase_type: str = "validation"
    validation_rules: List[str] = field(default_factory=list)

class ValidationPhase(Phase):
    config_class = ValidationPhaseConfig

    @property
    def phase_type(self) -> str:
        return "validation"

    @property
    def display_name(self) -> str:
        return "Validation"

    async def execute(self, context: PhaseContext) -> PhaseResult:
        # Validation logic here
        context.output_data = {'validated': True}
        return PhaseResult(
            status=PhaseStatus.COMPLETED,
            context=context,
        )

# Register the phase
PhaseRegistry.register_class("validation", ValidationPhase)

# Now usable in workflows
workflow = WorkflowDefinition(
    id="validated_research",
    name="Validated Research",
    phases=[
        {"type": "planning"},
        {"type": "validation"},  # Your new phase!
        {"type": "control"},
    ],
)
```

---

## Migration from Legacy

### Legacy Functions Still Work

All existing code continues to work unchanged:

```python
# These still work exactly as before
from cmbagent.workflows import (
    planning_and_control_context_carryover,
    one_shot,
    control,
)

# Legacy function call
result = planning_and_control_context_carryover(
    task="My task",
    max_plan_steps=3,
    work_dir="./output",
)
```

### Equivalent Phase-Based Code

```python
# New phase-based equivalent
from cmbagent.workflows import WorkflowExecutor, DEEP_RESEARCH_WORKFLOW

executor = WorkflowExecutor(
    workflow=DEEP_RESEARCH_WORKFLOW,
    task="My task",
    work_dir="./output",
    api_keys=get_api_keys_from_env(),
)
result = executor.run_sync()
```

### Backup Location

Original workflow files backed up to:
```
cmbagent/workflows/legacy/
├── planning_control.py
├── one_shot.py
├── control.py
└── __init__.py
```

---

## Testing

Run the test suite:

```bash
# Run all phase API tests
python tests/test_phases_api.py

# Or with pytest directly
pytest tests/test_phases_api.py -v
```

**Test Coverage:**
- Phase type listing and retrieval
- Workflow definition CRUD
- Workflow validation
- Workflow run management
- Phase registry operations
- Workflow executor creation

---

## Summary

The phase-based workflow architecture provides:

1. **Phases as First-Class Entities** - Independent, testable, configurable units
2. **Workflow Composition** - Create workflows by combining phases
3. **Clear Context Flow** - Explicit data passing between phases
4. **HITL Anywhere** - Add approval checkpoints at any point
5. **REST API** - Full API for UI integration
6. **Backwards Compatibility** - Legacy functions unchanged

---

*Phase Architecture Implementation*
*Version 1.0*
*January 2026*
