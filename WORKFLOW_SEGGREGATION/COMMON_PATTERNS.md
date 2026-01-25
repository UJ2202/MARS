# Common Workflow Patterns - Detailed Analysis

## Overview

This document provides a detailed breakdown of the common patterns identified across CMBAgent workflows, with exact code locations and proposed unified implementations.

---

## Pattern 1: Workflow Initialization

### Current Implementations

#### one_shot.py (lines 73-86)
```python
start_time = time.time()
work_dir = os.path.abspath(os.path.expanduser(work_dir))

run_id = str(uuid.uuid4())
output_manager = WorkflowOutputManager(
    work_dir=work_dir,
    run_id=run_id
)
output_manager.set_phase("execution")
output_manager.set_agent(agent)

if api_keys is None:
    api_keys = get_api_keys_from_env()
```

#### planning_control.py (lines 106-146)
```python
work_dir = os.path.abspath(os.path.expanduser(work_dir))
os.makedirs(work_dir, exist_ok=True)

if clear_work_dir:
    clean_work_dir(work_dir)

context_dir = os.path.join(work_dir, "context")
os.makedirs(context_dir, exist_ok=True)

run_id = str(uuid.uuid4())
output_manager = WorkflowOutputManager(
    work_dir=work_dir,
    run_id=run_id
)

if api_keys is None:
    api_keys = get_api_keys_from_env()

if approval_config is None:
    from cmbagent.database.approval_types import ApprovalConfig, ApprovalMode
    approval_config = ApprovalConfig(mode=ApprovalMode.NONE)

if callbacks is None:
    callbacks = create_null_callbacks()

workflow_start_time = time.time()
callbacks.invoke_workflow_start(task, {...})
```

### Proposed Unified Implementation

```python
# workflows/core/initialization.py

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import os
import uuid
import time

@dataclass
class WorkflowInitResult:
    """Result of workflow initialization."""
    work_dir: str
    run_id: str
    output_manager: 'WorkflowOutputManager'
    api_keys: Dict[str, str]
    callbacks: 'WorkflowCallbacks'
    approval_config: Optional['ApprovalConfig']
    context_dir: Optional[str]
    start_time: float

def initialize_workflow(
    work_dir: str,
    api_keys: Optional[Dict[str, str]] = None,
    callbacks: Optional['WorkflowCallbacks'] = None,
    approval_config: Optional['ApprovalConfig'] = None,
    clear_work_dir: bool = False,
    create_context_dir: bool = False,
    phase: str = "execution",
    agent: Optional[str] = None
) -> WorkflowInitResult:
    """
    Initialize a workflow with all required components.

    Args:
        work_dir: Working directory path
        api_keys: Optional API keys (fetched from env if None)
        callbacks: Optional workflow callbacks
        approval_config: Optional HITL approval config
        clear_work_dir: Whether to clear the work directory
        create_context_dir: Whether to create context subdirectory
        phase: Initial phase name for output manager
        agent: Initial agent name for output manager

    Returns:
        WorkflowInitResult with all initialized components
    """
    from cmbagent.workflows.utils import clean_work_dir
    from cmbagent.execution.output_collector import WorkflowOutputManager
    from cmbagent.callbacks import create_null_callbacks
    from cmbagent.utils import get_api_keys_from_env

    # Normalize and create work directory
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if clear_work_dir:
        clean_work_dir(work_dir)

    # Create context directory if needed
    context_dir = None
    if create_context_dir:
        context_dir = os.path.join(work_dir, "context")
        os.makedirs(context_dir, exist_ok=True)

    # Initialize tracking
    run_id = str(uuid.uuid4())
    output_manager = WorkflowOutputManager(work_dir=work_dir, run_id=run_id)
    output_manager.set_phase(phase)
    if agent:
        output_manager.set_agent(agent)

    # Initialize API keys
    if api_keys is None:
        api_keys = get_api_keys_from_env()

    # Initialize callbacks
    if callbacks is None:
        callbacks = create_null_callbacks()

    # Initialize approval config
    if approval_config is None:
        from cmbagent.database.approval_types import ApprovalConfig, ApprovalMode
        approval_config = ApprovalConfig(mode=ApprovalMode.NONE)

    return WorkflowInitResult(
        work_dir=work_dir,
        run_id=run_id,
        output_manager=output_manager,
        api_keys=api_keys,
        callbacks=callbacks,
        approval_config=approval_config,
        context_dir=context_dir,
        start_time=time.time()
    )
```

---

## Pattern 2: Agent Configuration

### Current Implementations

#### one_shot.py (lines 88-91)
```python
engineer_config = get_model_config(engineer_model, api_keys)
researcher_config = get_model_config(researcher_model, api_keys)
plot_judge_config = get_model_config(plot_judge_model, api_keys)
camb_context_config = get_model_config(camb_context_model, api_keys)
```

#### planning_control.py (lines 163-164, 375-380)
```python
# Planning phase
planner_config = get_model_config(planner_model, api_keys)
plan_reviewer_config = get_model_config(plan_reviewer_model, api_keys)

# Control phase
engineer_config = get_model_config(engineer_model, api_keys)
researcher_config = get_model_config(researcher_model, api_keys)
camb_context_config = get_model_config(camb_context_model, api_keys)
idea_maker_config = get_model_config(idea_maker_model, api_keys)
idea_hater_config = get_model_config(idea_hater_model, api_keys)
plot_judge_config = get_model_config(plot_judge_model, api_keys)
```

### Proposed Unified Implementation

```python
# workflows/core/config.py

from typing import Dict, List, Optional, Any
from cmbagent.utils import get_model_config, default_agents_llm_model

class AgentConfigBuilder:
    """
    Builder pattern for creating agent LLM configurations.

    Usage:
        configs = (AgentConfigBuilder(api_keys)
            .add('engineer', engineer_model)
            .add('researcher', researcher_model)
            .add_defaults(['plot_judge', 'camb_context'])
            .build())
    """

    def __init__(self, api_keys: Dict[str, str]):
        self.api_keys = api_keys
        self._configs: Dict[str, Dict] = {}

    def add(self, agent_name: str, model: str) -> 'AgentConfigBuilder':
        """Add a specific agent configuration."""
        self._configs[agent_name] = get_model_config(model, self.api_keys)
        return self

    def add_if(self, condition: bool, agent_name: str, model: str) -> 'AgentConfigBuilder':
        """Conditionally add an agent configuration."""
        if condition:
            self.add(agent_name, model)
        return self

    def add_defaults(self, agent_names: List[str]) -> 'AgentConfigBuilder':
        """Add default configurations for specified agents."""
        for name in agent_names:
            if name in default_agents_llm_model:
                self.add(name, default_agents_llm_model[name])
        return self

    def add_all_defaults(self) -> 'AgentConfigBuilder':
        """Add default configurations for all known agents."""
        return self.add_defaults(list(default_agents_llm_model.keys()))

    def merge(self, other: Dict[str, Dict]) -> 'AgentConfigBuilder':
        """Merge in external configurations."""
        self._configs.update(other)
        return self

    def build(self) -> Dict[str, Dict]:
        """Build and return the configuration dictionary."""
        return self._configs.copy()


# Pre-defined configuration sets
def planning_agent_configs(api_keys: Dict[str, str],
                           planner_model: str,
                           plan_reviewer_model: str) -> Dict[str, Dict]:
    """Standard configuration for planning phase."""
    return (AgentConfigBuilder(api_keys)
            .add('planner', planner_model)
            .add('plan_reviewer', plan_reviewer_model)
            .build())


def control_agent_configs(api_keys: Dict[str, str],
                          engineer_model: str,
                          researcher_model: str,
                          idea_maker_model: Optional[str] = None,
                          idea_hater_model: Optional[str] = None,
                          camb_context_model: Optional[str] = None,
                          plot_judge_model: Optional[str] = None) -> Dict[str, Dict]:
    """Standard configuration for control phase."""
    builder = (AgentConfigBuilder(api_keys)
               .add('engineer', engineer_model)
               .add('researcher', researcher_model))

    if idea_maker_model:
        builder.add('idea_maker', idea_maker_model)
    if idea_hater_model:
        builder.add('idea_hater', idea_hater_model)
    if camb_context_model:
        builder.add('camb_context', camb_context_model)
    if plot_judge_model:
        builder.add('plot_judge', plot_judge_model)

    return builder.build()


def one_shot_agent_configs(api_keys: Dict[str, str],
                           engineer_model: str,
                           researcher_model: str,
                           plot_judge_model: str,
                           camb_context_model: str) -> Dict[str, Dict]:
    """Standard configuration for one-shot execution."""
    return (AgentConfigBuilder(api_keys)
            .add('engineer', engineer_model)
            .add('researcher', researcher_model)
            .add('plot_judge', plot_judge_model)
            .add('camb_context', camb_context_model)
            .build())
```

---

## Pattern 3: CMBAgent Creation

### Current Implementations

#### Common pattern across all workflows
```python
cmbagent = CMBAgent(
    cache_seed=42,
    work_dir=work_dir,
    default_llm_model=default_llm_model,
    default_formatter_model=default_formatter_model,
    agent_llm_configs={...},
    api_keys=api_keys,
    mode=mode,
    clear_work_dir=clear_work_dir,
    approval_config=approval_config,
)
```

### Proposed Unified Implementation

```python
# workflows/core/factory.py

from typing import Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class CMBAgentConfig:
    """Configuration for CMBAgent creation."""
    cache_seed: int = 42
    mode: str = "planning_and_control"
    clear_work_dir: bool = False
    default_llm_model: str = None
    default_formatter_model: str = None

    def __post_init__(self):
        from cmbagent.utils import default_llm_model as default_model
        from cmbagent.utils import default_formatter_model as default_formatter

        if self.default_llm_model is None:
            self.default_llm_model = default_model
        if self.default_formatter_model is None:
            self.default_formatter_model = default_formatter


class CMBAgentFactory:
    """Factory for creating CMBAgent instances with timing tracking."""

    @staticmethod
    def create(
        work_dir: str,
        agent_configs: Dict[str, Dict],
        api_keys: Dict[str, str],
        config: Optional[CMBAgentConfig] = None,
        approval_config: Optional[Any] = None,
        **extra_kwargs
    ) -> tuple['CMBAgent', float]:
        """
        Create a CMBAgent instance.

        Returns:
            Tuple of (cmbagent, initialization_time)
        """
        import time
        from cmbagent.cmbagent import CMBAgent

        if config is None:
            config = CMBAgentConfig()

        start = time.time()

        cmbagent = CMBAgent(
            cache_seed=config.cache_seed,
            work_dir=work_dir,
            default_llm_model=config.default_llm_model,
            default_formatter_model=config.default_formatter_model,
            agent_llm_configs=agent_configs,
            api_keys=api_keys,
            mode=config.mode,
            clear_work_dir=config.clear_work_dir,
            approval_config=approval_config,
            **extra_kwargs
        )

        init_time = time.time() - start
        return cmbagent, init_time

    @staticmethod
    def ensure_groupchat(cmbagent: 'CMBAgent') -> None:
        """
        Ensure groupchat attribute exists.

        This fixes the display_cost bug when groupchat is not initialized.
        """
        if not hasattr(cmbagent, 'groupchat'):
            Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
            cmbagent.groupchat = Dummy()

    @staticmethod
    def execute(
        cmbagent: 'CMBAgent',
        task: str,
        initial_agent: str,
        max_rounds: int,
        shared_context: Dict[str, Any],
        mode: Optional[str] = None,
        step: Optional[int] = None
    ) -> tuple[Dict[str, Any], float]:
        """
        Execute cmbagent.solve() with timing.

        Returns:
            Tuple of (final_context, execution_time)
        """
        import time

        start = time.time()

        solve_kwargs = {
            'max_rounds': max_rounds,
            'initial_agent': initial_agent,
            'shared_context': shared_context,
        }
        if mode:
            solve_kwargs['mode'] = mode
        if step is not None:
            solve_kwargs['step'] = step

        cmbagent.solve(task, **solve_kwargs)

        exec_time = time.time() - start
        return cmbagent.final_context, exec_time
```

---

## Pattern 4: Timing Management

### Current Implementations

Scattered throughout all workflows:
```python
start_time = time.time()
# ... execution ...
end_time = time.time()
execution_time = end_time - start_time
```

### Proposed Unified Implementation

```python
# workflows/core/timing.py

import time
import json
import os
import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional
from contextlib import contextmanager

@dataclass
class TimingPhase:
    """Represents a single timed phase."""
    name: str
    start_time: float
    end_time: Optional[float] = None

    @property
    def duration(self) -> float:
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time


class WorkflowTimer:
    """
    Centralized timing management for workflows.

    Usage:
        timer = WorkflowTimer()

        with timer.phase("initialization"):
            # initialization code

        with timer.phase("execution"):
            # execution code

        timer.save_report(work_dir, "planning")
    """

    def __init__(self):
        self.phases: Dict[str, TimingPhase] = {}
        self.workflow_start = time.time()
        self._current_phase: Optional[str] = None

    @contextmanager
    def phase(self, name: str):
        """Context manager for timing a phase."""
        phase = TimingPhase(name=name, start_time=time.time())
        self.phases[name] = phase
        self._current_phase = name
        try:
            yield phase
        finally:
            phase.end_time = time.time()
            self._current_phase = None

    def start_phase(self, name: str) -> None:
        """Manually start a phase."""
        self.phases[name] = TimingPhase(name=name, start_time=time.time())
        self._current_phase = name

    def end_phase(self, name: Optional[str] = None) -> float:
        """Manually end a phase, returns duration."""
        phase_name = name or self._current_phase
        if phase_name and phase_name in self.phases:
            self.phases[phase_name].end_time = time.time()
            self._current_phase = None
            return self.phases[phase_name].duration
        return 0.0

    def get_duration(self, name: str) -> float:
        """Get duration of a specific phase."""
        if name in self.phases:
            return self.phases[name].duration
        return 0.0

    @property
    def total_time(self) -> float:
        """Total workflow time."""
        return time.time() - self.workflow_start

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization."""
        result = {}
        for name, phase in self.phases.items():
            result[f"{name}_time"] = phase.duration
        result['total_time'] = sum(p.duration for p in self.phases.values())
        return result

    def save_report(
        self,
        work_dir: str,
        phase_suffix: str = "",
        step: Optional[int] = None
    ) -> str:
        """
        Save timing report to JSON file.

        Returns the path to the saved file.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if step is not None:
            filename = f"timing_report_step_{step}_{timestamp}.json"
        elif phase_suffix:
            filename = f"timing_report_{phase_suffix}_{timestamp}.json"
        else:
            filename = f"timing_report_{timestamp}.json"

        timing_dir = os.path.join(work_dir, "time")
        os.makedirs(timing_dir, exist_ok=True)

        timing_path = os.path.join(timing_dir, filename)

        with open(timing_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        print(f"\nTiming report saved to: {timing_path}")
        return timing_path
```

---

## Pattern 5: Results Finalization

### Current Implementations

#### one_shot.py (lines 147-202)
```python
if not hasattr(cmbagent, 'groupchat'):
    Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
    cmbagent.groupchat = Dummy()

cmbagent.display_cost()

results = {
    'chat_history': cmbagent.chat_result.chat_history,
    'final_context': cmbagent.final_context,
    ...
}

results['initialization_time'] = initialization_time
results['execution_time'] = execution_time

# Save timing
timing_report = {...}
with open(timing_path, 'w') as f:
    json.dump(timing_report, f, indent=2)

# Collect outputs
try:
    workflow_outputs = output_manager.finalize(write_manifest=True)
    results['outputs'] = workflow_outputs.to_dict()
except Exception as e:
    results['outputs'] = None

# Cleanup empty dirs
for folder in [...]:
    if os.path.exists(folder) and not os.listdir(folder):
        os.rmdir(folder)
```

### Proposed Unified Implementation

```python
# workflows/core/finalization.py

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import os


@dataclass
class FinalizationConfig:
    """Configuration for workflow finalization."""
    save_cost_report: bool = True
    save_timing_report: bool = True
    collect_outputs: bool = True
    cleanup_empty_dirs: bool = True
    cost_name_append: Optional[str] = None


class WorkflowFinalizer:
    """
    Handles all workflow finalization tasks.

    Usage:
        finalizer = WorkflowFinalizer(
            cmbagent=cmbagent,
            timer=timer,
            output_manager=output_manager,
            work_dir=work_dir
        )

        results = finalizer.finalize()
    """

    def __init__(
        self,
        cmbagent: 'CMBAgent',
        timer: 'WorkflowTimer',
        output_manager: 'WorkflowOutputManager',
        work_dir: str,
        run_id: str,
        config: Optional[FinalizationConfig] = None
    ):
        self.cmbagent = cmbagent
        self.timer = timer
        self.output_manager = output_manager
        self.work_dir = work_dir
        self.run_id = run_id
        self.config = config or FinalizationConfig()

    def ensure_groupchat(self) -> None:
        """Ensure groupchat attribute exists for display_cost."""
        if not hasattr(self.cmbagent, 'groupchat'):
            Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
            self.cmbagent.groupchat = Dummy()

    def display_cost(self) -> Optional['pd.DataFrame']:
        """Display and save cost report."""
        self.ensure_groupchat()
        return self.cmbagent.display_cost(name_append=self.config.cost_name_append)

    def collect_outputs(self) -> Dict[str, Any]:
        """Collect workflow outputs."""
        try:
            workflow_outputs = self.output_manager.finalize(write_manifest=True)
            print(f"\nCollected {workflow_outputs.total_files} output files")
            return {
                'outputs': workflow_outputs.to_dict(),
                'run_id': self.run_id
            }
        except Exception as e:
            print(f"\nWarning: Could not collect outputs: {e}")
            return {
                'outputs': None,
                'run_id': self.run_id
            }

    def cleanup_empty_dirs(self) -> None:
        """Remove empty output directories."""
        final_context = self.cmbagent.final_context
        base_dir = final_context.get('work_dir', self.work_dir)

        dirs_to_check = [
            os.path.join(base_dir, final_context.get('database_path', 'data')),
            os.path.join(base_dir, final_context.get('codebase_path', 'codebase')),
            os.path.join(base_dir, 'time')
        ]

        for folder in dirs_to_check:
            try:
                if os.path.exists(folder) and not os.listdir(folder):
                    os.rmdir(folder)
            except OSError:
                pass

    def build_base_results(self) -> Dict[str, Any]:
        """Build base results dictionary."""
        return {
            'chat_history': self.cmbagent.chat_result.chat_history,
            'final_context': self.cmbagent.final_context,
            **self.timer.to_dict()
        }

    def finalize(
        self,
        extra_results: Optional[Dict[str, Any]] = None,
        phase_suffix: str = "",
        step: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Complete all finalization tasks and return results.

        Args:
            extra_results: Additional fields to add to results
            phase_suffix: Suffix for timing report filename
            step: Step number for step-specific reports

        Returns:
            Complete results dictionary
        """
        # Display cost
        if self.config.save_cost_report:
            self.display_cost()

        # Save timing
        if self.config.save_timing_report:
            self.timer.save_report(self.work_dir, phase_suffix, step)

        # Build results
        results = self.build_base_results()

        # Collect outputs
        if self.config.collect_outputs:
            output_info = self.collect_outputs()
            results.update(output_info)

        # Cleanup
        if self.config.cleanup_empty_dirs:
            self.cleanup_empty_dirs()

        # Add extra results
        if extra_results:
            results.update(extra_results)

        return results
```

---

## Summary: Files to Create

| File | Purpose | Patterns Unified |
|------|---------|------------------|
| `workflows/core/__init__.py` | Package exports | - |
| `workflows/core/initialization.py` | Workflow init | Pattern 1 |
| `workflows/core/config.py` | Agent configs | Pattern 2 |
| `workflows/core/factory.py` | CMBAgent creation | Pattern 3 |
| `workflows/core/timing.py` | Timing management | Pattern 4 |
| `workflows/core/finalization.py` | Results & cleanup | Pattern 5 |

Total estimated lines: ~400 (vs ~600 duplicated across workflows)
