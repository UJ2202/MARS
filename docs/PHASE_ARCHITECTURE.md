# Phase-Based Workflow Architecture

> **Design Document: Extracting Phases as First-Class Entities**

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Target Architecture](#target-architecture)
4. [Phase Design](#phase-design)
5. [Context Flow](#context-flow)
6. [Implementation Plan](#implementation-plan)
7. [Database Schema](#database-schema)
8. [API Design](#api-design)
9. [Migration Strategy](#migration-strategy)

---

## Executive Summary

### Goal

Refactor the workflow system to separate **Phases** as independent, reusable components:

1. **Phases** are atomic execution units (planning, control, review, etc.)
2. **Workflows** are compositions of phases with context passing
3. **Context** flows between phases, carrying state
4. **New phases** can be added without modifying existing workflows
5. **UI** can configure phase parameters and workflow composition

### Benefits

- **Reusability**: Same phase can be used in multiple workflows
- **Composability**: Create new workflows by combining phases
- **Testability**: Test phases in isolation
- **Flexibility**: Add new phases (HITL, validation, etc.) without refactoring
- **UI Configuration**: Phases and workflows configurable from UI

---

## Current State Analysis

### Current Workflow Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT: MONOLITHIC WORKFLOWS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  planning_and_control_context_carryover()                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │ EMBEDDED: Planning Phase                                         │  │  │
│  │  │  - Initialize CMBAgent with planner config                      │  │  │
│  │  │  - solve() with plan_setter                                     │  │  │
│  │  │  - Save plan to JSON                                            │  │  │
│  │  │  - Handle HITL approval (if enabled)                            │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                            ↓ planning_output                          │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │ EMBEDDED: Control Phase (loop per step)                         │  │  │
│  │  │  - Initialize CMBAgent with engineer config                     │  │  │
│  │  │  - solve() with control agent                                   │  │  │
│  │  │  - Handle step failures                                         │  │  │
│  │  │  - Context carryover between steps                              │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  one_shot()                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Single execution phase - no planning                                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  control()                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Control only - requires existing plan file                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Problems

| Problem | Impact |
|---------|--------|
| Phases embedded in functions | Can't reuse planning in other workflows |
| Hard to add HITL variants | Need to duplicate entire workflow |
| Context passing is implicit | Hard to understand data flow |
| No phase-level configuration | Must modify code to change behavior |
| Testing requires full workflow | Can't test phases in isolation |

---

## Target Architecture

### Phase-Based Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TARGET: COMPOSABLE PHASES                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE REGISTRY                                                             │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐                   │
│  │ PlanningPhase  │ │ ControlPhase   │ │ ReviewPhase    │                   │
│  └────────────────┘ └────────────────┘ └────────────────┘                   │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐                   │
│  │ OneShotPhase   │ │ HITLCheckpoint │ │ ValidationPhase│                   │
│  └────────────────┘ └────────────────┘ └────────────────┘                   │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐                   │
│  │ IdeaGenPhase   │ │ IdeaReviewPhase│ │ SummaryPhase   │                   │
│  └────────────────┘ └────────────────┘ └────────────────┘                   │
│                                                                              │
│  WORKFLOW COMPOSER                                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  DeepResearchWorkflow = [                                             │  │
│  │      PlanningPhase(max_steps=3, reviews=1),                           │  │
│  │      HITLCheckpoint(type="after_planning"),                           │  │
│  │      ControlPhase(max_rounds=100, hitl=False),                        │  │
│  │      SummaryPhase()                                                   │  │
│  │  ]                                                                    │  │
│  │                                                                        │  │
│  │  DeepResearchWithHITLWorkflow = [                                     │  │
│  │      PlanningPhase(max_steps=3, reviews=1),                           │  │
│  │      HITLCheckpoint(type="after_planning"),                           │  │
│  │      ControlPhase(max_rounds=100, hitl=True, hitl_every_step=True),   │  │
│  │      HITLCheckpoint(type="after_each_step"),                          │  │
│  │      SummaryPhase()                                                   │  │
│  │  ]                                                                    │  │
│  │                                                                        │  │
│  │  QuickTaskWorkflow = [                                                │  │
│  │      OneShotPhase(agent="engineer")                                   │  │
│  │  ]                                                                    │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  WORKFLOW EXECUTOR                                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  executor = WorkflowExecutor(workflow, context)                       │  │
│  │  result = executor.run()                                              │  │
│  │                                                                        │  │
│  │  Phase 1 ──Context──► Phase 2 ──Context──► Phase 3 ──Context──► ...   │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase Design

### Base Phase Interface

```python
# cmbagent/phases/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from enum import Enum

class PhaseStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"          # For HITL
    WAITING_APPROVAL = "waiting_approval"


@dataclass
class PhaseContext:
    """
    Context that flows between phases.
    Immutable input + mutable output.
    """
    # Identification
    workflow_id: str
    run_id: str
    phase_id: str
    
    # Task info
    task: str
    work_dir: str
    
    # Shared state (carried between phases)
    shared_state: Dict[str, Any] = field(default_factory=dict)
    
    # Phase-specific input (from previous phase)
    input_data: Dict[str, Any] = field(default_factory=dict)
    
    # Phase-specific output (for next phase)
    output_data: Dict[str, Any] = field(default_factory=dict)
    
    # API keys and credentials
    api_keys: Dict[str, str] = field(default_factory=dict)
    
    # Callbacks
    callbacks: Optional[Any] = None
    
    # Timing
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'workflow_id': self.workflow_id,
            'run_id': self.run_id,
            'phase_id': self.phase_id,
            'task': self.task,
            'work_dir': self.work_dir,
            'shared_state': self.shared_state,
            'input_data': self.input_data,
            'output_data': self.output_data,
        }
    
    def copy_for_next_phase(self, next_phase_id: str) -> 'PhaseContext':
        """Create context for next phase, carrying over shared state."""
        return PhaseContext(
            workflow_id=self.workflow_id,
            run_id=self.run_id,
            phase_id=next_phase_id,
            task=self.task,
            work_dir=self.work_dir,
            shared_state={**self.shared_state, **self.output_data.get('shared', {})},
            input_data=self.output_data,  # Previous output becomes next input
            output_data={},
            api_keys=self.api_keys,
            callbacks=self.callbacks,
        )


@dataclass
class PhaseResult:
    """Result of phase execution."""
    status: PhaseStatus
    context: PhaseContext
    error: Optional[str] = None
    chat_history: List[Dict] = field(default_factory=list)
    timing: Dict[str, float] = field(default_factory=dict)
    
    @property
    def succeeded(self) -> bool:
        return self.status == PhaseStatus.COMPLETED
    
    @property
    def needs_approval(self) -> bool:
        return self.status == PhaseStatus.WAITING_APPROVAL


@dataclass
class PhaseConfig:
    """Base configuration for all phases."""
    phase_type: str
    enabled: bool = True
    timeout_seconds: int = 3600  # 1 hour default
    max_retries: int = 0
    
    # Model overrides (optional)
    model_overrides: Dict[str, str] = field(default_factory=dict)
    
    # Additional parameters (phase-specific)
    params: Dict[str, Any] = field(default_factory=dict)


class Phase(ABC):
    """
    Abstract base class for all phases.
    
    A phase is an atomic unit of work within a workflow.
    It receives context, performs work, and returns updated context.
    """
    
    def __init__(self, config: PhaseConfig):
        self.config = config
        self._status = PhaseStatus.PENDING
    
    @property
    @abstractmethod
    def phase_type(self) -> str:
        """Unique identifier for this phase type."""
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        pass
    
    @property
    def status(self) -> PhaseStatus:
        return self._status
    
    @abstractmethod
    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute the phase.
        
        Args:
            context: Input context from previous phase
            
        Returns:
            PhaseResult with updated context
        """
        pass
    
    def validate_input(self, context: PhaseContext) -> List[str]:
        """
        Validate that required input is present.
        Returns list of error messages (empty if valid).
        """
        return []
    
    def get_required_agents(self) -> List[str]:
        """Return list of agent names this phase requires."""
        return []
    
    def get_output_schema(self) -> Dict[str, Any]:
        """Return JSON schema for this phase's output."""
        return {}
    
    def can_skip(self, context: PhaseContext) -> bool:
        """Return True if this phase can be skipped given the context."""
        return not self.config.enabled
```

### Concrete Phase Implementations

#### 1. Planning Phase

```python
# cmbagent/phases/planning.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import time

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.utils import get_model_config, default_agents_llm_model


@dataclass
class PlanningPhaseConfig(PhaseConfig):
    """Configuration for planning phase."""
    phase_type: str = "planning"
    
    # Planning parameters
    max_rounds: int = 50
    max_plan_steps: int = 3
    n_plan_reviews: int = 1
    
    # Model selection
    planner_model: str = field(default_factory=lambda: default_agents_llm_model['planner'])
    plan_reviewer_model: str = field(default_factory=lambda: default_agents_llm_model['plan_reviewer'])
    
    # Instructions
    plan_instructions: str = ""
    hardware_constraints: str = ""


class PlanningPhase(Phase):
    """
    Planning phase that generates a structured plan for the task.
    
    Input Context:
        - task: The task description
        - work_dir: Working directory
        - api_keys: API credentials
        
    Output Context:
        - final_plan: The generated plan (list of steps)
        - number_of_steps_in_plan: Count of steps
        - plan_file_path: Path to saved plan JSON
    """
    
    def __init__(self, config: PlanningPhaseConfig = None):
        if config is None:
            config = PlanningPhaseConfig()
        super().__init__(config)
        self.config: PlanningPhaseConfig = config
    
    @property
    def phase_type(self) -> str:
        return "planning"
    
    @property
    def display_name(self) -> str:
        return "Planning"
    
    def get_required_agents(self) -> List[str]:
        return ["planner", "plan_reviewer", "plan_setter", "planner_response_formatter"]
    
    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.cmbagent import CMBAgent
        from cmbagent.agents.planner_response_formatter.planner_response_formatter import save_final_plan
        
        self._status = PhaseStatus.RUNNING
        context.started_at = time.time()
        
        # Notify callbacks
        if context.callbacks:
            context.callbacks.invoke_phase_change("planning", None)
        
        # Setup directory
        planning_dir = os.path.join(context.work_dir, "planning")
        os.makedirs(planning_dir, exist_ok=True)
        
        # Get model configs
        planner_config = get_model_config(self.config.planner_model, context.api_keys)
        reviewer_config = get_model_config(self.config.plan_reviewer_model, context.api_keys)
        
        try:
            # Initialize CMBAgent for planning
            init_start = time.time()
            cmbagent = CMBAgent(
                cache_seed=42,
                work_dir=planning_dir,
                agent_llm_configs={
                    'planner': planner_config,
                    'plan_reviewer': reviewer_config,
                },
                api_keys=context.api_keys,
            )
            init_time = time.time() - init_start
            
            # Execute planning
            exec_start = time.time()
            cmbagent.solve(
                context.task,
                max_rounds=self.config.max_rounds,
                initial_agent="plan_setter",
                shared_context={
                    'feedback_left': self.config.n_plan_reviews,
                    'maximum_number_of_steps_in_plan': self.config.max_plan_steps,
                    'planner_append_instructions': self.config.plan_instructions,
                    'hardware_constraints': self.config.hardware_constraints,
                    # Carry over any shared state
                    **context.shared_state,
                }
            )
            exec_time = time.time() - exec_start
            
            # Save plan
            plan_file = save_final_plan(cmbagent.final_context, planning_dir)
            
            # Build output
            context.output_data = {
                'final_plan': cmbagent.final_context.get('final_plan'),
                'number_of_steps_in_plan': cmbagent.final_context.get('number_of_steps_in_plan'),
                'plan_file_path': plan_file,
                'planning_context': cmbagent.final_context,
                # Shared state to carry forward
                'shared': {
                    'plan_steps': cmbagent.final_context.get('final_plan'),
                    'current_step': 0,
                }
            }
            
            context.completed_at = time.time()
            self._status = PhaseStatus.COMPLETED
            
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
                chat_history=cmbagent.chat_result.chat_history if cmbagent.chat_result else [],
                timing={
                    'initialization': init_time,
                    'execution': exec_time,
                    'total': init_time + exec_time,
                }
            )
            
        except Exception as e:
            self._status = PhaseStatus.FAILED
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error=str(e),
            )
    
    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        if not context.task:
            errors.append("Task is required for planning phase")
        if not context.work_dir:
            errors.append("work_dir is required for planning phase")
        return errors
```

#### 2. Control Phase

```python
# cmbagent/phases/control.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import time
import copy

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.utils import get_model_config, default_agents_llm_model


@dataclass
class ControlPhaseConfig(PhaseConfig):
    """Configuration for control/execution phase."""
    phase_type: str = "control"
    
    # Execution parameters
    max_rounds: int = 100
    max_n_attempts: int = 3
    
    # Step handling
    execute_all_steps: bool = True       # Execute all plan steps
    step_number: Optional[int] = None    # Or execute specific step
    
    # HITL options
    hitl_enabled: bool = False
    hitl_after_each_step: bool = False
    
    # Model selection
    engineer_model: str = field(default_factory=lambda: default_agents_llm_model['engineer'])
    researcher_model: str = field(default_factory=lambda: default_agents_llm_model['researcher'])
    
    # Instructions
    engineer_instructions: str = ""
    researcher_instructions: str = ""


class ControlPhase(Phase):
    """
    Control phase that executes plan steps.
    
    Can execute:
    - All steps in sequence (execute_all_steps=True)
    - A single specific step (step_number=N)
    
    Input Context:
        - final_plan or plan_steps: The plan to execute
        - task: Original task
        - work_dir: Working directory
        
    Output Context:
        - step_results: Results from each step
        - final_context: Final context after all steps
        - step_summaries: Summary of each step
    """
    
    def __init__(self, config: ControlPhaseConfig = None):
        if config is None:
            config = ControlPhaseConfig()
        super().__init__(config)
        self.config: ControlPhaseConfig = config
    
    @property
    def phase_type(self) -> str:
        return "control"
    
    @property
    def display_name(self) -> str:
        return "Execution"
    
    def get_required_agents(self) -> List[str]:
        return ["control", "control_starter", "engineer", "researcher"]
    
    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.cmbagent import CMBAgent
        
        self._status = PhaseStatus.RUNNING
        context.started_at = time.time()
        
        # Setup
        control_dir = os.path.join(context.work_dir, "control")
        os.makedirs(control_dir, exist_ok=True)
        
        # Get plan from input
        plan_steps = (
            context.input_data.get('final_plan') or 
            context.shared_state.get('plan_steps') or
            context.input_data.get('planning_context', {}).get('final_plan')
        )
        
        if not plan_steps:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error="No plan found in context. Run planning phase first.",
            )
        
        # Determine steps to execute
        if self.config.execute_all_steps:
            steps_to_run = range(1, len(plan_steps) + 1)
        else:
            steps_to_run = [self.config.step_number]
        
        # Get model configs
        engineer_config = get_model_config(self.config.engineer_model, context.api_keys)
        researcher_config = get_model_config(self.config.researcher_model, context.api_keys)
        
        step_results = []
        step_summaries = []
        all_chat_history = []
        current_context = context.input_data.get('planning_context', {}).copy()
        
        try:
            for step in steps_to_run:
                if context.callbacks:
                    context.callbacks.invoke_phase_change("control", step)
                
                clear_work_dir = (step == 1)
                starter_agent = "control" if step == 1 else "control_starter"
                
                # Initialize CMBAgent
                cmbagent = CMBAgent(
                    cache_seed=42,
                    work_dir=control_dir,
                    clear_work_dir=clear_work_dir,
                    agent_llm_configs={
                        'engineer': engineer_config,
                        'researcher': researcher_config,
                    },
                    mode="planning_and_control_context_carryover",
                    api_keys=context.api_keys,
                )
                
                # Prepare step context
                step_context = copy.deepcopy(current_context)
                step_context['current_plan_step_number'] = step
                step_context['n_attempts'] = 0
                step_context['engineer_append_instructions'] = self.config.engineer_instructions
                step_context['researcher_append_instructions'] = self.config.researcher_instructions
                
                # Execute step
                exec_start = time.time()
                cmbagent.solve(
                    context.task,
                    max_rounds=self.config.max_rounds,
                    initial_agent=starter_agent,
                    shared_context=step_context,
                    step=step,
                )
                exec_time = time.time() - exec_start
                
                # Check for failures
                n_failures = cmbagent.final_context.get('n_attempts', 0)
                if n_failures >= self.config.max_n_attempts:
                    self._status = PhaseStatus.FAILED
                    return PhaseResult(
                        status=PhaseStatus.FAILED,
                        context=context,
                        error=f"Step {step} failed after {n_failures} attempts",
                        chat_history=all_chat_history,
                    )
                
                # Collect results
                step_results.append({
                    'step': step,
                    'context': cmbagent.final_context,
                    'execution_time': exec_time,
                })
                all_chat_history.extend(cmbagent.chat_result.chat_history)
                
                # Update context for next step
                current_context = cmbagent.final_context
                
                # HITL checkpoint after step (if enabled)
                if self.config.hitl_enabled and self.config.hitl_after_each_step:
                    # This will be handled by HITLCheckpointPhase in the workflow
                    context.output_data['hitl_checkpoint'] = {
                        'step': step,
                        'context': current_context,
                    }
            
            # Build output
            context.output_data = {
                'step_results': step_results,
                'final_context': current_context,
                'step_summaries': step_summaries,
                'shared': {
                    'execution_complete': True,
                    'final_context': current_context,
                }
            }
            
            context.completed_at = time.time()
            self._status = PhaseStatus.COMPLETED
            
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
                chat_history=all_chat_history,
            )
            
        except Exception as e:
            self._status = PhaseStatus.FAILED
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error=str(e),
            )
    
    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        if not context.task:
            errors.append("Task is required for control phase")
        
        # Check for plan
        has_plan = (
            context.input_data.get('final_plan') or
            context.shared_state.get('plan_steps')
        )
        if not has_plan and self.config.execute_all_steps:
            errors.append("Plan is required for control phase (run planning first)")
        
        return errors
```

#### 3. HITL Checkpoint Phase

```python
# cmbagent/phases/hitl_checkpoint.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import time
import asyncio

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus


class CheckpointType(Enum):
    AFTER_PLANNING = "after_planning"
    BEFORE_STEP = "before_step"
    AFTER_STEP = "after_step"
    BEFORE_EXECUTION = "before_execution"
    AFTER_EXECUTION = "after_execution"
    CUSTOM = "custom"


@dataclass
class HITLCheckpointConfig(PhaseConfig):
    """Configuration for HITL checkpoint phase."""
    phase_type: str = "hitl_checkpoint"
    
    checkpoint_type: CheckpointType = CheckpointType.AFTER_PLANNING
    
    # Approval options
    require_approval: bool = True
    timeout_seconds: int = 3600  # 1 hour
    default_on_timeout: str = "reject"  # "approve" or "reject"
    
    # What to show user
    show_plan: bool = True
    show_context: bool = False
    custom_message: str = ""
    
    # Options user can choose
    options: List[str] = field(default_factory=lambda: ["approve", "reject", "modify"])


class HITLCheckpointPhase(Phase):
    """
    Human-in-the-Loop checkpoint phase.
    
    Pauses workflow execution and waits for human approval.
    Can be placed anywhere in workflow to create approval gates.
    
    Input Context:
        - Any context from previous phase
        
    Output Context:
        - approval_status: "approved" | "rejected" | "modified"
        - user_feedback: Optional feedback from user
        - modifications: Any modifications made by user
    """
    
    def __init__(self, config: HITLCheckpointConfig = None):
        if config is None:
            config = HITLCheckpointConfig()
        super().__init__(config)
        self.config: HITLCheckpointConfig = config
    
    @property
    def phase_type(self) -> str:
        return "hitl_checkpoint"
    
    @property
    def display_name(self) -> str:
        type_names = {
            CheckpointType.AFTER_PLANNING: "Review Plan",
            CheckpointType.BEFORE_STEP: "Approve Step",
            CheckpointType.AFTER_STEP: "Review Step Result",
            CheckpointType.AFTER_EXECUTION: "Review Results",
            CheckpointType.CUSTOM: "Checkpoint",
        }
        return type_names.get(self.config.checkpoint_type, "Checkpoint")
    
    def get_required_agents(self) -> List[str]:
        return []  # No agents needed - this is human interaction
    
    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.database.approval_types import ApprovalConfig, ApprovalMode
        from cmbagent.database.approval_manager import ApprovalManager
        
        self._status = PhaseStatus.WAITING_APPROVAL
        context.started_at = time.time()
        
        if not self.config.require_approval:
            # Skip if approval not required
            context.output_data = {
                'approval_status': 'auto_approved',
                'skipped': True,
            }
            self._status = PhaseStatus.COMPLETED
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
            )
        
        # Build message for user
        message = self._build_approval_message(context)
        
        # Get approval manager from context (injected by workflow executor)
        approval_manager = context.shared_state.get('_approval_manager')
        
        if not approval_manager:
            # No approval manager - auto-approve (for non-HITL runs)
            context.output_data = {
                'approval_status': 'auto_approved',
                'no_hitl_manager': True,
            }
            self._status = PhaseStatus.COMPLETED
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
            )
        
        try:
            # Create approval request
            approval_request = approval_manager.create_approval_request(
                run_id=context.run_id,
                step_id=context.phase_id,
                checkpoint_type=self.config.checkpoint_type.value,
                context_snapshot=self._build_context_snapshot(context),
                message=message,
                options=self.config.options,
            )
            
            # Wait for approval
            resolved = await approval_manager.wait_for_approval_async(
                str(approval_request.id),
                timeout_seconds=self.config.timeout_seconds,
            )
            
            # Handle result
            if resolved.resolution == "rejected":
                context.output_data = {
                    'approval_status': 'rejected',
                    'user_feedback': resolved.user_feedback,
                }
                self._status = PhaseStatus.FAILED
                return PhaseResult(
                    status=PhaseStatus.FAILED,
                    context=context,
                    error="Rejected by user",
                )
            
            elif resolved.resolution == "modified":
                context.output_data = {
                    'approval_status': 'modified',
                    'user_feedback': resolved.user_feedback,
                    'modifications': resolved.modifications,
                    'shared': {
                        'user_modifications': resolved.modifications,
                    }
                }
            
            else:  # approved
                context.output_data = {
                    'approval_status': 'approved',
                    'user_feedback': resolved.user_feedback,
                }
            
            context.completed_at = time.time()
            self._status = PhaseStatus.COMPLETED
            
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
            )
            
        except asyncio.TimeoutError:
            # Handle timeout
            if self.config.default_on_timeout == "approve":
                context.output_data = {
                    'approval_status': 'timeout_auto_approved',
                }
                self._status = PhaseStatus.COMPLETED
                return PhaseResult(
                    status=PhaseStatus.COMPLETED,
                    context=context,
                )
            else:
                self._status = PhaseStatus.FAILED
                return PhaseResult(
                    status=PhaseStatus.FAILED,
                    context=context,
                    error="Approval timeout - defaulted to reject",
                )
    
    def _build_approval_message(self, context: PhaseContext) -> str:
        """Build human-readable message for approval UI."""
        parts = []
        
        if self.config.custom_message:
            parts.append(self.config.custom_message)
        
        if self.config.checkpoint_type == CheckpointType.AFTER_PLANNING:
            parts.append("Planning phase complete. Please review the plan before execution.")
            if self.config.show_plan:
                plan = context.input_data.get('final_plan', 'Plan not available')
                parts.append(f"\n**Plan:**\n{plan}")
        
        elif self.config.checkpoint_type == CheckpointType.AFTER_STEP:
            step = context.shared_state.get('current_step', '?')
            parts.append(f"Step {step} complete. Review results?")
        
        return "\n".join(parts)
    
    def _build_context_snapshot(self, context: PhaseContext) -> Dict[str, Any]:
        """Build context snapshot for approval record."""
        snapshot = {
            'task': context.task,
            'phase_id': context.phase_id,
            'checkpoint_type': self.config.checkpoint_type.value,
        }
        
        if self.config.show_plan:
            snapshot['plan'] = context.input_data.get('final_plan')
        
        if self.config.show_context:
            snapshot['context'] = context.input_data
        
        return snapshot
    
    def can_skip(self, context: PhaseContext) -> bool:
        """HITL can be skipped if not required."""
        return not self.config.require_approval
```

#### 4. One-Shot Phase

```python
# cmbagent/phases/one_shot.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import time

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.utils import get_model_config, default_agents_llm_model


@dataclass
class OneShotPhaseConfig(PhaseConfig):
    """Configuration for one-shot execution phase."""
    phase_type: str = "one_shot"
    
    # Execution parameters
    max_rounds: int = 50
    max_n_attempts: int = 3
    
    # Which agent to use
    agent: str = "engineer"
    
    # Model selection
    model: Optional[str] = None  # Uses agent default if not set
    
    # Plot evaluation
    evaluate_plots: bool = False
    max_n_plot_evals: int = 1


class OneShotPhase(Phase):
    """
    One-shot execution phase - single agent, no planning.
    
    Input Context:
        - task: The task to execute
        - work_dir: Working directory
        
    Output Context:
        - result: Execution result
        - chat_history: Conversation history
    """
    
    def __init__(self, config: OneShotPhaseConfig = None):
        if config is None:
            config = OneShotPhaseConfig()
        super().__init__(config)
        self.config: OneShotPhaseConfig = config
    
    @property
    def phase_type(self) -> str:
        return "one_shot"
    
    @property
    def display_name(self) -> str:
        return f"Execute ({self.config.agent})"
    
    def get_required_agents(self) -> List[str]:
        return [self.config.agent]
    
    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.cmbagent import CMBAgent
        
        self._status = PhaseStatus.RUNNING
        context.started_at = time.time()
        
        # Get model config
        model = self.config.model or default_agents_llm_model.get(self.config.agent)
        model_config = get_model_config(model, context.api_keys) if model else {}
        
        try:
            # Initialize CMBAgent
            init_start = time.time()
            cmbagent = CMBAgent(
                cache_seed=42,
                mode="one_shot",
                work_dir=context.work_dir,
                agent_llm_configs={
                    self.config.agent: model_config,
                },
                api_keys=context.api_keys,
            )
            init_time = time.time() - init_start
            
            # Execute
            exec_start = time.time()
            cmbagent.solve(
                context.task,
                max_rounds=self.config.max_rounds,
                initial_agent=self.config.agent,
                shared_context={
                    'max_n_attempts': self.config.max_n_attempts,
                    'evaluate_plots': self.config.evaluate_plots,
                    'max_n_plot_evals': self.config.max_n_plot_evals,
                    **context.shared_state,
                }
            )
            exec_time = time.time() - exec_start
            
            # Build output
            context.output_data = {
                'result': cmbagent.final_context,
                'shared': {
                    'execution_complete': True,
                }
            }
            
            context.completed_at = time.time()
            self._status = PhaseStatus.COMPLETED
            
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
                chat_history=cmbagent.chat_result.chat_history if cmbagent.chat_result else [],
                timing={
                    'initialization': init_time,
                    'execution': exec_time,
                    'total': init_time + exec_time,
                }
            )
            
        except Exception as e:
            self._status = PhaseStatus.FAILED
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error=str(e),
            )
```

#### 5. Idea Generation Phase

```python
# cmbagent/phases/idea_generation.py

from dataclasses import dataclass, field
from typing import List, Dict, Any
import os
import time

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.utils import get_model_config, default_agents_llm_model


@dataclass 
class IdeaGenerationPhaseConfig(PhaseConfig):
    """Configuration for idea generation phase."""
    phase_type: str = "idea_generation"
    
    # Idea parameters
    max_rounds: int = 50
    n_ideas: int = 3
    n_reviews: int = 1
    
    # Model selection
    idea_maker_model: str = field(default_factory=lambda: default_agents_llm_model['idea_maker'])
    idea_hater_model: str = field(default_factory=lambda: default_agents_llm_model['idea_hater'])


class IdeaGenerationPhase(Phase):
    """
    Idea generation phase with maker/hater dynamics.
    
    Input Context:
        - task: Research topic or problem
        
    Output Context:
        - ideas: Generated ideas
        - reviews: Hater reviews
        - selected_idea: Best idea after review
    """
    
    def __init__(self, config: IdeaGenerationPhaseConfig = None):
        if config is None:
            config = IdeaGenerationPhaseConfig()
        super().__init__(config)
        self.config: IdeaGenerationPhaseConfig = config
    
    @property
    def phase_type(self) -> str:
        return "idea_generation"
    
    @property
    def display_name(self) -> str:
        return "Generate Ideas"
    
    def get_required_agents(self) -> List[str]:
        return ["idea_maker", "idea_hater", "idea_setter"]
    
    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.cmbagent import CMBAgent
        
        self._status = PhaseStatus.RUNNING
        context.started_at = time.time()
        
        # Setup
        ideas_dir = os.path.join(context.work_dir, "ideas")
        os.makedirs(ideas_dir, exist_ok=True)
        
        # Get model configs
        maker_config = get_model_config(self.config.idea_maker_model, context.api_keys)
        hater_config = get_model_config(self.config.idea_hater_model, context.api_keys)
        
        try:
            cmbagent = CMBAgent(
                cache_seed=42,
                work_dir=ideas_dir,
                agent_llm_configs={
                    'idea_maker': maker_config,
                    'idea_hater': hater_config,
                },
                api_keys=context.api_keys,
            )
            
            cmbagent.solve(
                context.task,
                max_rounds=self.config.max_rounds,
                initial_agent="idea_setter",
                shared_context={
                    'n_ideas': self.config.n_ideas,
                    'feedback_left': self.config.n_reviews,
                    **context.shared_state,
                }
            )
            
            context.output_data = {
                'ideas': cmbagent.final_context.get('ideas', []),
                'reviews': cmbagent.final_context.get('reviews', []),
                'selected_idea': cmbagent.final_context.get('selected_idea'),
                'shared': {
                    'ideas': cmbagent.final_context.get('ideas', []),
                }
            }
            
            self._status = PhaseStatus.COMPLETED
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
                chat_history=cmbagent.chat_result.chat_history if cmbagent.chat_result else [],
            )
            
        except Exception as e:
            self._status = PhaseStatus.FAILED
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error=str(e),
            )
```

---

## Context Flow

### Context Data Model

```python
# cmbagent/phases/context.py

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json
import pickle
from pathlib import Path


@dataclass
class WorkflowContext:
    """
    Master context that flows through entire workflow.
    Each phase can read and write to this context.
    """
    
    # === Immutable (set at workflow start) ===
    workflow_id: str
    run_id: str
    task: str
    work_dir: str
    api_keys: Dict[str, str]
    
    # === Planning outputs ===
    plan: Optional[List[Dict]] = None
    plan_file_path: Optional[str] = None
    
    # === Execution tracking ===
    current_step: int = 0
    total_steps: int = 0
    step_results: List[Dict] = field(default_factory=list)
    step_summaries: List[str] = field(default_factory=list)
    
    # === HITL state ===
    approvals: List[Dict] = field(default_factory=list)
    user_feedback: List[str] = field(default_factory=list)
    
    # === Shared agent state ===
    agent_state: Dict[str, Any] = field(default_factory=dict)
    
    # === Files produced ===
    output_files: List[str] = field(default_factory=list)
    
    # === Timing ===
    phase_timings: Dict[str, float] = field(default_factory=dict)
    
    # === Extensible storage ===
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def save(self, path: Path):
        """Persist context to disk."""
        with open(path, 'wb') as f:
            pickle.dump(self, f)
    
    @classmethod
    def load(cls, path: Path) -> 'WorkflowContext':
        """Load context from disk."""
        with open(path, 'rb') as f:
            return pickle.load(f)
    
    def to_phase_context(self, phase_id: str) -> 'PhaseContext':
        """Convert to PhaseContext for phase execution."""
        from cmbagent.phases.base import PhaseContext
        
        return PhaseContext(
            workflow_id=self.workflow_id,
            run_id=self.run_id,
            phase_id=phase_id,
            task=self.task,
            work_dir=self.work_dir,
            shared_state={
                'plan': self.plan,
                'current_step': self.current_step,
                'total_steps': self.total_steps,
                'step_results': self.step_results,
                'agent_state': self.agent_state,
            },
            input_data={},
            api_keys=self.api_keys,
        )
    
    def update_from_phase_result(self, result: 'PhaseResult'):
        """Update workflow context from phase result."""
        if result.context.output_data:
            # Merge shared state
            shared = result.context.output_data.get('shared', {})
            
            if 'plan' in shared:
                self.plan = shared['plan']
            if 'plan_steps' in shared:
                self.plan = shared['plan_steps']
                self.total_steps = len(self.plan)
            if 'current_step' in shared:
                self.current_step = shared['current_step']
            
            # Store phase-specific outputs in metadata
            self.metadata[result.context.phase_id] = result.context.output_data
        
        # Record timing
        if result.timing:
            self.phase_timings[result.context.phase_id] = result.timing.get('total', 0)
```

### Context Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CONTEXT FLOW                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  WorkflowContext (Master)                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  task: "Analyze CMB data..."                                          │  │
│  │  work_dir: "/path/to/work"                                            │  │
│  │  api_keys: {openai: "...", anthropic: "..."}                          │  │
│  │                                                                        │  │
│  │  plan: null → [step1, step2, step3]  (after planning)                 │  │
│  │  current_step: 0 → 1 → 2 → 3         (during control)                 │  │
│  │  step_results: [] → [{...}, {...}]   (accumulated)                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐      │
│  │ Planning Phase  │ ───► │ HITL Checkpoint │ ───► │ Control Phase   │      │
│  │                 │      │                 │      │                 │      │
│  │ Input:          │      │ Input:          │      │ Input:          │      │
│  │   - task        │      │   - plan        │      │   - plan        │      │
│  │                 │      │   - task        │      │   - approvals   │      │
│  │ Output:         │      │                 │      │                 │      │
│  │   - plan        │      │ Output:         │      │ Output:         │      │
│  │   - plan_file   │      │   - approved    │      │   - results     │      │
│  │                 │      │   - feedback    │      │   - summaries   │      │
│  └─────────────────┘      └─────────────────┘      └─────────────────┘      │
│         │                        │                        │                  │
│         ▼                        ▼                        ▼                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                       WorkflowContext (Updated)                        │  │
│  │  plan: [step1, step2, step3]                                          │  │
│  │  approvals: [{type: "after_planning", status: "approved"}]            │  │
│  │  step_results: [{step: 1, ...}, {step: 2, ...}]                       │  │
│  │  phase_timings: {planning: 45.2, hitl: 120.0, control: 300.5}        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase Registry

```python
# cmbagent/phases/registry.py

from typing import Dict, Type, List
from cmbagent.phases.base import Phase, PhaseConfig


class PhaseRegistry:
    """Registry of available phases."""
    
    _phases: Dict[str, Type[Phase]] = {}
    
    @classmethod
    def register(cls, phase_type: str):
        """Decorator to register a phase class."""
        def decorator(phase_class: Type[Phase]):
            cls._phases[phase_type] = phase_class
            return phase_class
        return decorator
    
    @classmethod
    def get(cls, phase_type: str) -> Type[Phase]:
        """Get phase class by type."""
        if phase_type not in cls._phases:
            raise ValueError(f"Unknown phase type: {phase_type}")
        return cls._phases[phase_type]
    
    @classmethod
    def create(cls, phase_type: str, config: PhaseConfig = None) -> Phase:
        """Create phase instance."""
        phase_class = cls.get(phase_type)
        return phase_class(config)
    
    @classmethod
    def list_all(cls) -> List[str]:
        """List all registered phase types."""
        return list(cls._phases.keys())
    
    @classmethod
    def get_info(cls, phase_type: str) -> Dict:
        """Get phase metadata."""
        phase_class = cls.get(phase_type)
        instance = phase_class()
        return {
            'type': phase_type,
            'display_name': instance.display_name,
            'required_agents': instance.get_required_agents(),
        }


# Register all phases
from cmbagent.phases.planning import PlanningPhase
from cmbagent.phases.control import ControlPhase
from cmbagent.phases.hitl_checkpoint import HITLCheckpointPhase
from cmbagent.phases.one_shot import OneShotPhase
from cmbagent.phases.idea_generation import IdeaGenerationPhase

PhaseRegistry.register("planning")(PlanningPhase)
PhaseRegistry.register("control")(ControlPhase)
PhaseRegistry.register("hitl_checkpoint")(HITLCheckpointPhase)
PhaseRegistry.register("one_shot")(OneShotPhase)
PhaseRegistry.register("idea_generation")(IdeaGenerationPhase)
```

### Workflow Composer

```python
# cmbagent/workflows/composer.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import uuid
import time
import asyncio

from cmbagent.phases.base import Phase, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.context import WorkflowContext
from cmbagent.phases.registry import PhaseRegistry


@dataclass
class WorkflowDefinition:
    """Definition of a workflow as a sequence of phases."""
    
    id: str
    name: str
    description: str
    phases: List[Dict[str, Any]]  # [{type: "planning", config: {...}}, ...]
    
    # Metadata
    version: int = 1
    is_system: bool = False
    created_by: Optional[str] = None


class WorkflowExecutor:
    """
    Executes a workflow by running phases in sequence.
    Handles context passing, error recovery, and checkpointing.
    """
    
    def __init__(
        self,
        workflow: WorkflowDefinition,
        task: str,
        work_dir: str,
        api_keys: Dict[str, str],
        callbacks: Any = None,
        approval_manager: Any = None,
    ):
        self.workflow = workflow
        self.task = task
        self.work_dir = work_dir
        self.api_keys = api_keys
        self.callbacks = callbacks
        self.approval_manager = approval_manager
        
        # Build phases
        self.phases: List[Phase] = []
        for phase_def in workflow.phases:
            phase = PhaseRegistry.create(
                phase_def['type'],
                phase_def.get('config')
            )
            self.phases.append(phase)
        
        # Initialize context
        self.context = WorkflowContext(
            workflow_id=workflow.id,
            run_id=str(uuid.uuid4()),
            task=task,
            work_dir=work_dir,
            api_keys=api_keys,
        )
        
        # Execution state
        self.current_phase_index = 0
        self.results: List[PhaseResult] = []
        self._should_stop = False
    
    async def run(self) -> WorkflowContext:
        """Execute the workflow."""
        
        total_start = time.time()
        
        for i, phase in enumerate(self.phases):
            if self._should_stop:
                break
            
            self.current_phase_index = i
            
            # Check if phase should be skipped
            phase_context = self.context.to_phase_context(f"phase_{i}_{phase.phase_type}")
            if phase.can_skip(phase_context):
                continue
            
            # Validate input
            errors = phase.validate_input(phase_context)
            if errors:
                raise ValueError(f"Phase {phase.phase_type} validation failed: {errors}")
            
            # Inject approval manager for HITL phases
            if self.approval_manager:
                phase_context.shared_state['_approval_manager'] = self.approval_manager
            
            # Execute phase
            if self.callbacks:
                self.callbacks.invoke_phase_change(phase.phase_type, i)
            
            result = await phase.execute(phase_context)
            self.results.append(result)
            
            # Handle failure
            if not result.succeeded:
                if result.needs_approval:
                    # HITL waiting - workflow paused
                    pass
                else:
                    raise RuntimeError(f"Phase {phase.phase_type} failed: {result.error}")
            
            # Update master context
            self.context.update_from_phase_result(result)
        
        # Record total time
        self.context.phase_timings['total'] = time.time() - total_start
        
        return self.context
    
    def stop(self):
        """Signal workflow to stop after current phase."""
        self._should_stop = True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current execution status."""
        return {
            'workflow_id': self.workflow.id,
            'run_id': self.context.run_id,
            'current_phase': self.current_phase_index,
            'total_phases': len(self.phases),
            'phase_results': [
                {
                    'phase_type': r.context.phase_id,
                    'status': r.status.value,
                    'error': r.error,
                }
                for r in self.results
            ],
        }


# === PRESET WORKFLOW DEFINITIONS ===

DEEP_RESEARCH_WORKFLOW = WorkflowDefinition(
    id="deep_research",
    name="Deep Research",
    description="Planning followed by multi-step execution with context carryover",
    phases=[
        {"type": "planning", "config": {"max_plan_steps": 3, "n_plan_reviews": 1}},
        {"type": "control", "config": {"execute_all_steps": True}},
    ],
    is_system=True,
)

DEEP_RESEARCH_HITL_WORKFLOW = WorkflowDefinition(
    id="deep_research_hitl",
    name="Deep Research with HITL",
    description="Deep research with human approval after planning",
    phases=[
        {"type": "planning", "config": {"max_plan_steps": 3, "n_plan_reviews": 1}},
        {"type": "hitl_checkpoint", "config": {"checkpoint_type": "after_planning"}},
        {"type": "control", "config": {"execute_all_steps": True}},
    ],
    is_system=True,
)

DEEP_RESEARCH_FULL_HITL_WORKFLOW = WorkflowDefinition(
    id="deep_research_full_hitl",
    name="Deep Research with Full HITL",
    description="Human approval after planning and after each step",
    phases=[
        {"type": "planning", "config": {"max_plan_steps": 3, "n_plan_reviews": 1}},
        {"type": "hitl_checkpoint", "config": {"checkpoint_type": "after_planning"}},
        {"type": "control", "config": {"execute_all_steps": True, "hitl_after_each_step": True}},
    ],
    is_system=True,
)

ONE_SHOT_WORKFLOW = WorkflowDefinition(
    id="one_shot",
    name="Quick Task",
    description="Single-shot execution without planning",
    phases=[
        {"type": "one_shot", "config": {"agent": "engineer"}},
    ],
    is_system=True,
)

IDEA_GENERATION_WORKFLOW = WorkflowDefinition(
    id="idea_generation",
    name="Idea Generation",
    description="Generate and review research ideas",
    phases=[
        {"type": "idea_generation", "config": {"n_ideas": 3, "n_reviews": 1}},
        {"type": "hitl_checkpoint", "config": {"checkpoint_type": "custom", "custom_message": "Select idea to pursue"}},
    ],
    is_system=True,
)

IDEA_TO_EXECUTION_WORKFLOW = WorkflowDefinition(
    id="idea_to_execution",
    name="Idea to Execution",
    description="Generate idea, plan it, and execute",
    phases=[
        {"type": "idea_generation", "config": {"n_ideas": 3}},
        {"type": "hitl_checkpoint", "config": {"checkpoint_type": "custom", "custom_message": "Select idea"}},
        {"type": "planning", "config": {"max_plan_steps": 5}},
        {"type": "hitl_checkpoint", "config": {"checkpoint_type": "after_planning"}},
        {"type": "control", "config": {"execute_all_steps": True}},
    ],
    is_system=True,
)


# Default workflows available
SYSTEM_WORKFLOWS = {
    w.id: w for w in [
        DEEP_RESEARCH_WORKFLOW,
        DEEP_RESEARCH_HITL_WORKFLOW,
        DEEP_RESEARCH_FULL_HITL_WORKFLOW,
        ONE_SHOT_WORKFLOW,
        IDEA_GENERATION_WORKFLOW,
        IDEA_TO_EXECUTION_WORKFLOW,
    ]
}
```

---

## Database Schema

```sql
-- =====================================================
-- PHASE AND WORKFLOW TABLES
-- =====================================================

-- Phase definitions (templates)
CREATE TABLE phase_definitions (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    
    phase_type VARCHAR(50) NOT NULL,          -- planning, control, hitl_checkpoint, etc.
    name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Default configuration
    default_config JSONB NOT NULL DEFAULT '{}',
    
    -- Schema for config validation
    config_schema JSONB,
    
    -- What this phase requires/produces
    required_inputs JSONB DEFAULT '[]',       -- ["plan", "task"]
    produced_outputs JSONB DEFAULT '[]',      -- ["plan", "plan_file_path"]
    required_agents JSONB DEFAULT '[]',       -- ["planner", "plan_reviewer"]
    
    -- UI metadata
    icon VARCHAR(50),
    color VARCHAR(20),
    category VARCHAR(50),                     -- planning, execution, review, etc.
    
    is_system BOOLEAN NOT NULL DEFAULT false,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Workflow definitions (templates)
CREATE TABLE workflow_definitions (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) REFERENCES users(id),
    
    name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Ordered list of phases with configs
    phases JSONB NOT NULL,                    -- [{type: "planning", config: {...}}, ...]
    
    -- Metadata
    version INTEGER NOT NULL DEFAULT 1,
    is_system BOOLEAN NOT NULL DEFAULT false,
    is_default BOOLEAN NOT NULL DEFAULT false,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Phase execution records
CREATE TABLE phase_executions (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    
    workflow_run_id VARCHAR(36) NOT NULL REFERENCES workflow_runs(id),
    phase_definition_id VARCHAR(36) REFERENCES phase_definitions(id),
    
    phase_type VARCHAR(50) NOT NULL,
    phase_order INTEGER NOT NULL,             -- Order in workflow
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed, skipped
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Input/Output
    input_context JSONB,
    output_context JSONB,
    
    -- Config used (may differ from default)
    config_used JSONB,
    
    -- Error info
    error_message TEXT,
    error_traceback TEXT,
    
    -- Chat history
    chat_history JSONB,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_phase_exec_run (workflow_run_id),
    INDEX idx_phase_exec_status (status)
);

-- Insert system phases
INSERT INTO phase_definitions (phase_type, name, description, is_system, required_agents, category) VALUES
('planning', 'Planning', 'Generate structured plan for task', true, '["planner", "plan_reviewer", "plan_setter"]', 'planning'),
('control', 'Execution', 'Execute plan steps with context carryover', true, '["control", "engineer", "researcher"]', 'execution'),
('one_shot', 'Quick Execute', 'Single-shot task execution', true, '["engineer"]', 'execution'),
('hitl_checkpoint', 'Human Review', 'Pause for human approval', true, '[]', 'review'),
('idea_generation', 'Idea Generation', 'Generate and review ideas', true, '["idea_maker", "idea_hater"]', 'planning');

-- Insert system workflows
INSERT INTO workflow_definitions (id, name, description, phases, is_system, is_default) VALUES
('deep_research', 'Deep Research', 'Planning + multi-step execution', 
 '[{"type": "planning", "config": {"max_plan_steps": 3}}, {"type": "control", "config": {}}]',
 true, true),
('deep_research_hitl', 'Deep Research (HITL)', 'With human approval after planning',
 '[{"type": "planning"}, {"type": "hitl_checkpoint", "config": {"checkpoint_type": "after_planning"}}, {"type": "control"}]',
 true, false),
('one_shot', 'Quick Task', 'Single execution',
 '[{"type": "one_shot", "config": {"agent": "engineer"}}]',
 true, false);
```

---

## API Design

```python
# backend/routers/phases.py

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/phases", tags=["Phases"])


class PhaseDefinitionResponse(BaseModel):
    id: str
    phase_type: str
    name: str
    description: str
    default_config: dict
    required_agents: List[str]
    category: str


class WorkflowDefinitionCreate(BaseModel):
    name: str
    description: str
    phases: List[dict]  # [{type: "planning", config: {...}}]


class WorkflowDefinitionResponse(BaseModel):
    id: str
    name: str
    description: str
    phases: List[dict]
    is_system: bool
    version: int


# Phase endpoints
@router.get("/types")
async def list_phase_types() -> List[PhaseDefinitionResponse]:
    """List all available phase types."""
    pass


@router.get("/types/{phase_type}")
async def get_phase_type(phase_type: str) -> PhaseDefinitionResponse:
    """Get details of a phase type."""
    pass


@router.get("/types/{phase_type}/config-schema")
async def get_phase_config_schema(phase_type: str) -> dict:
    """Get JSON schema for phase configuration."""
    pass


# Workflow endpoints
@router.get("/workflows")
async def list_workflows(include_system: bool = True) -> List[WorkflowDefinitionResponse]:
    """List all workflow definitions."""
    pass


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str) -> WorkflowDefinitionResponse:
    """Get workflow definition."""
    pass


@router.post("/workflows")
async def create_workflow(workflow: WorkflowDefinitionCreate) -> WorkflowDefinitionResponse:
    """Create a new workflow definition."""
    pass


@router.put("/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, workflow: WorkflowDefinitionCreate) -> WorkflowDefinitionResponse:
    """Update workflow definition."""
    pass


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete workflow (non-system only)."""
    pass


@router.post("/workflows/{workflow_id}/validate")
async def validate_workflow(workflow_id: str) -> dict:
    """Validate workflow definition (check phase compatibility)."""
    pass


# Execution endpoints (using workflow)
@router.post("/workflows/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    task: str,
    config_overrides: Optional[dict] = None,
) -> dict:
    """Start a workflow run."""
    pass


@router.get("/runs/{run_id}/phases")
async def get_run_phases(run_id: str) -> List[dict]:
    """Get phase execution status for a run."""
    pass
```

---

## Migration Strategy

### Phase 1: Create Phase Infrastructure (Week 1)

```
cmbagent/phases/
├── __init__.py
├── base.py              # Phase, PhaseConfig, PhaseContext, PhaseResult
├── context.py           # WorkflowContext
├── registry.py          # PhaseRegistry
├── planning.py          # PlanningPhase
├── control.py           # ControlPhase
├── one_shot.py          # OneShotPhase
├── hitl_checkpoint.py   # HITLCheckpointPhase
└── idea_generation.py   # IdeaGenerationPhase
```

### Phase 2: Create Workflow Composer (Week 1-2)

```
cmbagent/workflows/
├── __init__.py
├── composer.py          # WorkflowDefinition, WorkflowExecutor
├── presets.py           # SYSTEM_WORKFLOWS
└── legacy/              # Keep old functions for compatibility
    ├── planning_control.py
    ├── control.py
    └── one_shot.py
```

### Phase 3: Database & API (Week 2)

- Add database tables
- Create API endpoints
- Add phase execution tracking

### Phase 4: Frontend (Week 3)

- Workflow builder UI
- Phase configuration panels
- Drag-and-drop composer

### Phase 5: Migration (Week 3-4)

- Wrap existing workflows with new executor
- Add deprecation warnings to old functions
- Update documentation

---

## Summary

This architecture enables:

1. **Phases as first-class entities** - Reusable, testable, configurable
2. **Workflow composition** - Create workflows by combining phases
3. **Context flow** - Clear data passing between phases
4. **HITL anywhere** - Add approval checkpoints at any point
5. **UI configuration** - Configure phases and workflows from UI
6. **Future extensibility** - Add new phases without touching existing code

### New Phases Made Easy

```python
# To add a new phase:

@dataclass
class ValidationPhaseConfig(PhaseConfig):
    phase_type: str = "validation"
    validation_rules: List[str] = field(default_factory=list)

@PhaseRegistry.register("validation")
class ValidationPhase(Phase):
    
    @property
    def phase_type(self) -> str:
        return "validation"
    
    async def execute(self, context: PhaseContext) -> PhaseResult:
        # Validation logic here
        pass

# Now usable in any workflow:
WORKFLOW_WITH_VALIDATION = WorkflowDefinition(
    id="validated_research",
    name="Validated Research",
    phases=[
        {"type": "planning"},
        {"type": "hitl_checkpoint"},
        {"type": "control"},
        {"type": "validation"},  # New phase!
    ],
)
```

---

*Phase Architecture Design*  
*Version 1.0*  
*January 2026*
