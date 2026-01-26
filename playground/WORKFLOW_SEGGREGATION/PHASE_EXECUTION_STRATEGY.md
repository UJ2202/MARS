# Phase Execution Strategy

## Overview

The long `planning_and_control_context_carryover` function (610 lines) can be decomposed into distinct phases with a common execution pattern. This document defines the abstraction strategy.

---

## 1. Phase Decomposition

### Current Monolithic Structure

```
planning_and_control_context_carryover() [610 lines]
├── Initialization (lines 106-146)           ~40 lines
├── Planning Phase (lines 148-373)          ~225 lines
│   ├── Setup (163-186)
│   ├── Database creation (187-210)
│   ├── Execution (215-242)
│   ├── Callbacks (257-272)
│   ├── Approval handling (274-344)
│   └── Context saving (346-373)
├── Control Loop (lines 375-619)            ~245 lines
│   ├── Config setup (375-380)
│   ├── For each step:
│   │   ├── Agent creation (408-425)
│   │   ├── Context setup (444-457)
│   │   ├── Execution (471-477)
│   │   ├── Result processing (489-545)
│   │   └── Cleanup (550-618)
└── Final cleanup (620-642)                  ~22 lines
```

### Proposed Phase Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    WorkflowOrchestrator                     │
│  Coordinates phases, manages state, handles callbacks       │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  PlanningPhase  │  │  ControlPhase   │  │ FinalizationPh  │
│                 │  │                 │  │                 │
│ - setup()       │  │ - setup()       │  │ - collect()     │
│ - execute()     │  │ - execute()     │  │ - cleanup()     │
│ - save_plan()   │  │ - process_step()│  │ - report()      │
│ - handle_approv │  │ - step_complete │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## 2. Base Phase Class

```python
# workflows/phases/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class PhaseResult:
    """Result of a phase execution."""
    success: bool
    context: Dict[str, Any]
    error: Optional[str] = None
    timing: Optional[Dict[str, float]] = None
    outputs: Optional[Dict[str, Any]] = None


class WorkflowPhase(ABC):
    """
    Base class for workflow phases.

    Each phase has a consistent lifecycle:
    1. setup() - Prepare resources
    2. validate() - Check preconditions
    3. execute() - Main logic
    4. cleanup() - Release resources
    """

    def __init__(
        self,
        work_dir: str,
        api_keys: Dict[str, str],
        callbacks: 'WorkflowCallbacks',
        timer: 'WorkflowTimer',
        **kwargs
    ):
        self.work_dir = work_dir
        self.api_keys = api_keys
        self.callbacks = callbacks
        self.timer = timer
        self.cmbagent: Optional['CMBAgent'] = None
        self._context: Dict[str, Any] = {}
        self._kwargs = kwargs

    @property
    @abstractmethod
    def name(self) -> str:
        """Phase name for logging and timing."""
        pass

    @abstractmethod
    def get_agent_configs(self) -> Dict[str, Dict]:
        """Return agent configurations for this phase."""
        pass

    @abstractmethod
    def build_shared_context(self, task: str, input_context: Dict[str, Any]) -> Dict[str, Any]:
        """Build shared context for execution."""
        pass

    @abstractmethod
    def get_initial_agent(self) -> str:
        """Return the initial agent name."""
        pass

    def setup(self) -> None:
        """
        Prepare resources for this phase.
        Override in subclasses for custom setup.
        """
        os.makedirs(self.phase_dir, exist_ok=True)

    @property
    def phase_dir(self) -> str:
        """Directory for this phase's outputs."""
        return os.path.join(self.work_dir, self.name)

    def validate(self, input_context: Dict[str, Any]) -> bool:
        """
        Validate preconditions for this phase.
        Returns True if valid, raises exception otherwise.
        """
        return True

    def create_agent(self, mode: str = "planning_and_control") -> 'CMBAgent':
        """Create and return CMBAgent for this phase."""
        from cmbagent.cmbagent import CMBAgent

        self.timer.start_phase(f"{self.name}_init")

        self.cmbagent = CMBAgent(
            cache_seed=42,
            work_dir=self.phase_dir,
            agent_llm_configs=self.get_agent_configs(),
            api_keys=self.api_keys,
            mode=mode,
            **self._kwargs
        )

        self.timer.end_phase(f"{self.name}_init")
        return self.cmbagent

    def execute(
        self,
        task: str,
        max_rounds: int,
        input_context: Optional[Dict[str, Any]] = None
    ) -> PhaseResult:
        """
        Execute this phase.

        Args:
            task: The task description
            max_rounds: Maximum conversation rounds
            input_context: Context from previous phase

        Returns:
            PhaseResult with execution results
        """
        try:
            # Setup
            self.setup()

            # Validate
            self.validate(input_context or {})

            # Build context
            shared_context = self.build_shared_context(task, input_context or {})

            # Create agent if not exists
            if self.cmbagent is None:
                self.create_agent()

            # Invoke callbacks
            self.callbacks.invoke_phase_change(self.name, None)

            # Execute
            self.timer.start_phase(f"{self.name}_exec")

            self.cmbagent.solve(
                task,
                max_rounds=max_rounds,
                initial_agent=self.get_initial_agent(),
                shared_context=shared_context
            )

            self.timer.end_phase(f"{self.name}_exec")

            # Cleanup
            self.cleanup()

            return PhaseResult(
                success=True,
                context=self.cmbagent.final_context,
                timing=self.timer.to_dict()
            )

        except Exception as e:
            return PhaseResult(
                success=False,
                context=self._context,
                error=str(e)
            )

    def cleanup(self) -> None:
        """
        Cleanup after phase execution.
        Override in subclasses for custom cleanup.
        """
        # Ensure groupchat exists for cost display
        if self.cmbagent:
            CMBAgentFactory.ensure_groupchat(self.cmbagent)
            self.cmbagent.display_cost(name_append=self.name)
```

---

## 3. Planning Phase Implementation

```python
# workflows/phases/planning.py

from typing import Dict, Any, Optional
import copy

class PlanningPhase(WorkflowPhase):
    """
    Executes the planning phase of a workflow.

    Responsibilities:
    - Configure planner and plan_reviewer agents
    - Execute planning conversation
    - Handle plan approval (if configured)
    - Save plan and context
    """

    def __init__(
        self,
        work_dir: str,
        api_keys: Dict[str, str],
        callbacks: 'WorkflowCallbacks',
        timer: 'WorkflowTimer',
        planner_model: str,
        plan_reviewer_model: str,
        max_plan_steps: int = 3,
        n_plan_reviews: int = 1,
        plan_instructions: str = '',
        approval_config: Optional['ApprovalConfig'] = None,
        **kwargs
    ):
        super().__init__(work_dir, api_keys, callbacks, timer, **kwargs)
        self.planner_model = planner_model
        self.plan_reviewer_model = plan_reviewer_model
        self.max_plan_steps = max_plan_steps
        self.n_plan_reviews = n_plan_reviews
        self.plan_instructions = plan_instructions
        self.approval_config = approval_config

    @property
    def name(self) -> str:
        return "planning"

    def get_agent_configs(self) -> Dict[str, Dict]:
        from cmbagent.utils import get_model_config
        return {
            'planner': get_model_config(self.planner_model, self.api_keys),
            'plan_reviewer': get_model_config(self.plan_reviewer_model, self.api_keys)
        }

    def get_initial_agent(self) -> str:
        return "plan_setter"

    def build_shared_context(self, task: str, input_context: Dict[str, Any]) -> Dict[str, Any]:
        context = {
            'feedback_left': self.n_plan_reviews,
            'max_n_attempts': self._kwargs.get('max_n_attempts', 3),
            'maximum_number_of_steps_in_plan': self.max_plan_steps,
            'planner_append_instructions': self.plan_instructions,
            'engineer_append_instructions': self._kwargs.get('engineer_instructions', ''),
            'researcher_append_instructions': self._kwargs.get('researcher_instructions', ''),
            'plan_reviewer_append_instructions': self.plan_instructions,
            'hardware_constraints': self._kwargs.get('hardware_constraints', ''),
            'researcher_filename': self._kwargs.get('researcher_filename', 'researcher_output.md')
        }
        return context

    def execute(
        self,
        task: str,
        max_rounds: int,
        input_context: Optional[Dict[str, Any]] = None
    ) -> PhaseResult:
        """Execute planning with approval handling."""

        # Invoke planning start callback
        self.callbacks.invoke_planning_start(task, {
            'planner_model': self.planner_model,
            'max_plan_steps': self.max_plan_steps
        })

        # Execute base phase
        result = super().execute(task, max_rounds, input_context)

        if not result.success:
            return result

        # Save plan
        plan_output = self._save_plan(result.context)

        # Handle approval
        if self.approval_config and self.approval_config.requires_approval_at_planning():
            approval_result = self._handle_approval(result.context)
            if not approval_result.approved:
                return PhaseResult(
                    success=False,
                    context=result.context,
                    error="Plan rejected by user"
                )

        # Invoke planning complete callback
        from cmbagent.callbacks import PlanInfo
        plan_info = PlanInfo(
            task=task,
            num_steps=result.context.get('number_of_steps_in_plan', 0),
            steps=plan_output.get('sub_tasks', []),
            plan_text=result.context.get('final_plan', ''),
            planning_time=self.timer.get_duration(f"{self.name}_exec")
        )
        self.callbacks.invoke_planning_complete(plan_info)

        # Save context
        self._save_context(result.context)

        return result

    def _save_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Save the structured plan to JSON."""
        from cmbagent.agents.planner_response_formatter.planner_response_formatter import save_final_plan
        outfile = save_final_plan(context, self.phase_dir)
        print(f"\nStructured plan written to {outfile}")
        return self._load_plan(outfile)

    def _load_plan(self, path: str) -> Dict[str, Any]:
        """Load plan from JSON file."""
        import json
        with open(path) as f:
            return json.load(f)

    def _save_context(self, context: Dict[str, Any]) -> None:
        """Save context to pickle file."""
        import pickle
        context_dir = os.path.join(self.work_dir, "context")
        os.makedirs(context_dir, exist_ok=True)
        context_path = os.path.join(context_dir, "context_step_0.pkl")
        with open(context_path, 'wb') as f:
            pickle.dump(context, f)

    def _handle_approval(self, context: Dict[str, Any]) -> 'ApprovalResult':
        """Handle plan approval workflow."""
        # Implementation for approval handling
        # Returns ApprovalResult(approved=True/False, feedback=...)
        pass
```

---

## 4. Control Phase Implementation

```python
# workflows/phases/control.py

from typing import Dict, Any, Optional, List
import copy

class ControlPhase(WorkflowPhase):
    """
    Executes the control phase with step-by-step processing.

    Responsibilities:
    - Execute each step in the plan
    - Maintain context carryover between steps
    - Handle step failures and retries
    - Collect step summaries
    """

    def __init__(
        self,
        work_dir: str,
        api_keys: Dict[str, str],
        callbacks: 'WorkflowCallbacks',
        timer: 'WorkflowTimer',
        engineer_model: str,
        researcher_model: str,
        plan_context: Dict[str, Any],
        restart_at_step: int = -1,
        **kwargs
    ):
        super().__init__(work_dir, api_keys, callbacks, timer, **kwargs)
        self.engineer_model = engineer_model
        self.researcher_model = researcher_model
        self.plan_context = plan_context
        self.restart_at_step = restart_at_step
        self.step_summaries: List[str] = []
        self._current_step = 0

    @property
    def name(self) -> str:
        return "control"

    def get_agent_configs(self) -> Dict[str, Dict]:
        from cmbagent.utils import get_model_config
        return {
            'engineer': get_model_config(self.engineer_model, self.api_keys),
            'researcher': get_model_config(self.researcher_model, self.api_keys),
            'idea_maker': get_model_config(self._kwargs.get('idea_maker_model', self.engineer_model), self.api_keys),
            'idea_hater': get_model_config(self._kwargs.get('idea_hater_model', self.engineer_model), self.api_keys),
            'camb_context': get_model_config(self._kwargs.get('camb_context_model', self.engineer_model), self.api_keys),
            'plot_judge': get_model_config(self._kwargs.get('plot_judge_model', self.engineer_model), self.api_keys),
        }

    def get_initial_agent(self) -> str:
        return "control" if self._current_step == 1 else "control_starter"

    def build_shared_context(self, task: str, input_context: Dict[str, Any]) -> Dict[str, Any]:
        context = copy.deepcopy(input_context)
        context['current_plan_step_number'] = self._current_step
        context['n_attempts'] = 0
        return context

    def execute_all_steps(
        self,
        task: str,
        max_rounds: int,
    ) -> PhaseResult:
        """
        Execute all steps in the plan.

        Returns:
            PhaseResult with final context
        """
        num_steps = self.plan_context.get('number_of_steps_in_plan', 0)
        initial_step = 1 if self.restart_at_step <= 0 else self.restart_at_step

        current_context = copy.deepcopy(self.plan_context)
        current_context['work_dir'] = self.phase_dir

        for step in range(initial_step, num_steps + 1):
            step_result = self.execute_step(
                task=task,
                step_number=step,
                max_rounds=max_rounds,
                input_context=current_context
            )

            if not step_result.success:
                return step_result

            current_context = step_result.context

        return PhaseResult(
            success=True,
            context=current_context,
            timing=self.timer.to_dict()
        )

    def execute_step(
        self,
        task: str,
        step_number: int,
        max_rounds: int,
        input_context: Dict[str, Any]
    ) -> PhaseResult:
        """Execute a single step."""
        from cmbagent.callbacks import StepInfo, StepStatus

        self._current_step = step_number

        # Create step info
        step_info = StepInfo(
            step_number=step_number,
            goal=input_context.get('current_sub_task', f'Step {step_number}'),
            description=input_context.get('current_sub_task', ''),
            status=StepStatus.RUNNING
        )

        # Check for cancellation
        self.callbacks.invoke_pause_check()
        if not self.callbacks.check_should_continue():
            raise Exception("Workflow cancelled by user")

        # Invoke step start
        self.callbacks.invoke_step_start(step_info)

        # Create new agent for this step
        clear_work_dir = (step_number == 1 and self.restart_at_step <= 0)
        self.cmbagent = None
        self._kwargs['clear_work_dir'] = clear_work_dir

        # Execute step
        result = self.execute(task, max_rounds, input_context)

        if result.success:
            # Extract and save summary
            summary = self._extract_step_summary(result.context)
            self.step_summaries.append(f"### Step {step_number}\n{summary}")
            result.context['previous_steps_execution_summary'] = "\n\n".join(self.step_summaries)

            # Save context
            self._save_step_context(step_number, result.context)

            step_info.status = StepStatus.COMPLETED
            step_info.summary = summary
            self.callbacks.invoke_step_complete(step_info)
        else:
            step_info.status = StepStatus.FAILED
            step_info.error = result.error
            self.callbacks.invoke_step_failed(step_info)

        return result

    def _extract_step_summary(self, context: Dict[str, Any]) -> str:
        """Extract summary from agent messages."""
        # Implementation to extract summary from chat history
        pass

    def _save_step_context(self, step: int, context: Dict[str, Any]) -> None:
        """Save step context to pickle file."""
        import pickle
        context_dir = os.path.join(self.work_dir, "context")
        os.makedirs(context_dir, exist_ok=True)
        context_path = os.path.join(context_dir, f"context_step_{step}.pkl")
        with open(context_path, 'wb') as f:
            pickle.dump(context, f)
```

---

## 5. Workflow Orchestrator

```python
# workflows/orchestrator.py

from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class WorkflowConfig:
    """Configuration for a complete workflow."""
    max_rounds_planning: int = 50
    max_rounds_control: int = 100
    max_plan_steps: int = 3
    n_plan_reviews: int = 1
    restart_at_step: int = -1
    clear_work_dir: bool = False


class WorkflowOrchestrator:
    """
    Coordinates multi-phase workflow execution.

    Usage:
        orchestrator = WorkflowOrchestrator(
            work_dir=work_dir,
            api_keys=api_keys,
            callbacks=callbacks,
            config=WorkflowConfig(max_plan_steps=5)
        )

        result = orchestrator.run(task)
    """

    def __init__(
        self,
        work_dir: str,
        api_keys: Dict[str, str],
        callbacks: 'WorkflowCallbacks',
        config: Optional[WorkflowConfig] = None,
        **kwargs
    ):
        self.work_dir = work_dir
        self.api_keys = api_keys
        self.callbacks = callbacks
        self.config = config or WorkflowConfig()
        self.timer = WorkflowTimer()
        self.kwargs = kwargs

    def run(self, task: str) -> Dict[str, Any]:
        """
        Execute the complete workflow.

        Args:
            task: Task description

        Returns:
            Final results dictionary
        """
        # Invoke workflow start
        self.callbacks.invoke_workflow_start(task, {
            'max_plan_steps': self.config.max_plan_steps,
            'work_dir': self.work_dir
        })

        # Execute planning (if not restarting)
        if self.config.restart_at_step <= 0:
            planning_result = self._run_planning(task)
            if not planning_result.success:
                return self._build_error_result(planning_result)
            plan_context = planning_result.context
        else:
            plan_context = self._load_restart_context()

        # Execute control
        control_result = self._run_control(task, plan_context)

        # Finalize
        return self._finalize(control_result)

    def _run_planning(self, task: str) -> PhaseResult:
        """Run the planning phase."""
        planning = PlanningPhase(
            work_dir=self.work_dir,
            api_keys=self.api_keys,
            callbacks=self.callbacks,
            timer=self.timer,
            planner_model=self.kwargs.get('planner_model'),
            plan_reviewer_model=self.kwargs.get('plan_reviewer_model'),
            max_plan_steps=self.config.max_plan_steps,
            n_plan_reviews=self.config.n_plan_reviews,
            **self.kwargs
        )

        return planning.execute(task, self.config.max_rounds_planning)

    def _run_control(self, task: str, plan_context: Dict[str, Any]) -> PhaseResult:
        """Run the control phase."""
        control = ControlPhase(
            work_dir=self.work_dir,
            api_keys=self.api_keys,
            callbacks=self.callbacks,
            timer=self.timer,
            engineer_model=self.kwargs.get('engineer_model'),
            researcher_model=self.kwargs.get('researcher_model'),
            plan_context=plan_context,
            restart_at_step=self.config.restart_at_step,
            **self.kwargs
        )

        return control.execute_all_steps(task, self.config.max_rounds_control)

    def _finalize(self, result: PhaseResult) -> Dict[str, Any]:
        """Finalize workflow and build results."""
        workflow_time = self.timer.total_time
        self.callbacks.invoke_workflow_complete(result.context, workflow_time)

        return {
            'chat_history': result.context.get('chat_history', []),
            'final_context': result.context,
            **self.timer.to_dict(),
            'success': result.success
        }
```

---

## 6. Summary: Before and After

### Before (planning_and_control_context_carryover)
- 610 lines
- Monolithic function
- Duplicated patterns
- Hard to test
- Hard to extend

### After (Phase-Based Architecture)
- ~150 lines per phase class
- Clear separation of concerns
- Reusable base class
- Easy to unit test
- Easy to add new phases/workflows

| Metric | Before | After |
|--------|--------|-------|
| Main function lines | 610 | ~50 (orchestrator.run) |
| Testable units | 1 | 5+ |
| Code reuse | None | High |
| Adding new workflow | Copy+modify 600 lines | Extend WorkflowPhase |
