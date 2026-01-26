# CMBAgent Workflow Abstraction Analysis

## Executive Summary

This document analyzes the CMBAgent workflow system to identify common patterns and proposes abstractions to organize long phases into reusable, manageable methods.

---

## 1. Current Workflow Architecture

### 1.1 Workflow Types

| Workflow | File | Lines | Purpose |
|----------|------|-------|---------|
| `one_shot` | `workflows/one_shot.py:27-204` | 177 | Single agent execution |
| `human_in_the_loop` | `workflows/one_shot.py:207-302` | 95 | Interactive chat mode |
| `planning_and_control` | `workflows/planning_control.py:645-896` | 251 | Plan once, execute once |
| `planning_and_control_context_carryover` | `workflows/planning_control.py:32-642` | 610 | Full multi-step with context |
| `control` | `workflows/control.py:19-170` | 151 | Execute from existing plan |

### 1.2 Core Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    WORKFLOW ENTRY POINT                         │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: INITIALIZATION                                        │
│  ├── Create work directories                                    │
│  ├── Initialize API keys                                        │
│  ├── Configure model configs                                    │
│  ├── Initialize output manager                                  │
│  └── Initialize callbacks                                       │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: AGENT SETUP                                           │
│  ├── Create CMBAgent instance                                   │
│  ├── Configure agent LLM configs                                │
│  └── Track initialization time                                  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: EXECUTION                                             │
│  ├── Build shared context                                       │
│  ├── Call cmbagent.solve()                                      │
│  └── Track execution time                                       │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4: FINALIZATION                                          │
│  ├── Display cost report                                        │
│  ├── Save timing report                                         │
│  ├── Collect outputs                                            │
│  └── Cleanup empty directories                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Identified Common Patterns

### 2.1 Pattern: Work Directory Setup (DUPLICATED 5x)

**Current Code (repeated in every workflow):**
```python
work_dir = os.path.abspath(os.path.expanduser(work_dir))
os.makedirs(work_dir, exist_ok=True)

# Initialize file tracking system
run_id = str(uuid.uuid4())
output_manager = WorkflowOutputManager(
    work_dir=work_dir,
    run_id=run_id
)
```

**Locations:**
- `one_shot.py:74-82`
- `one_shot.py:235` (human_in_the_loop doesn't use output_manager)
- `planning_control.py:107-123`
- `planning_control.py:705-714`
- `control.py:79-80`

---

### 2.2 Pattern: API Key Initialization (DUPLICATED 5x)

**Current Code:**
```python
if api_keys is None:
    api_keys = get_api_keys_from_env()
```

**Locations:**
- `one_shot.py:85-86`
- `one_shot.py:238-239`
- `planning_control.py:125-126`
- `planning_control.py:722-723`
- `control.py:94-95`

---

### 2.3 Pattern: Model Config Setup (DUPLICATED 5x)

**Current Code:**
```python
engineer_config = get_model_config(engineer_model, api_keys)
researcher_config = get_model_config(researcher_model, api_keys)
# ... more configs
```

**Locations:**
- `one_shot.py:88-91`
- `one_shot.py:240-241`
- `planning_control.py:163-164` (planning)
- `planning_control.py:375-380` (control)
- `planning_control.py:725-726`, `802-805`
- `control.py:98-102`

---

### 2.4 Pattern: CMBAgent Instantiation (DUPLICATED 6x)

**Current Code:**
```python
cmbagent = CMBAgent(
    cache_seed=42,
    work_dir=work_dir,
    default_llm_model=default_llm_model,
    default_formatter_model=default_formatter_model,
    agent_llm_configs={...},
    api_keys=api_keys,
    # ... other params
)
```

**Locations:**
- `one_shot.py:93-107`
- `one_shot.py:243-253`
- `planning_control.py:174-185` (planning phase)
- `planning_control.py:408-425` (control loop)
- `planning_control.py:728-738`, `811-823`
- `control.py:107-119`

---

### 2.5 Pattern: Timing Tracking (DUPLICATED 8x)

**Current Code:**
```python
start_time = time.time()
# ... execution ...
end_time = time.time()
execution_time = end_time - start_time
```

**Locations:** Throughout all workflow files for both initialization and execution phases.

---

### 2.6 Pattern: Groupchat Dummy Fix (DUPLICATED 5x)

**Current Code:**
```python
if not hasattr(cmbagent, 'groupchat'):
    Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
    cmbagent.groupchat = Dummy()
```

**Locations:**
- `one_shot.py:147-149`
- `one_shot.py:284-286`
- `planning_control.py:244-246`, `568-571`, `762-765`, `866-868`
- `control.py:154-157`

---

### 2.7 Pattern: Timing Report Save (DUPLICATED 5x)

**Current Code:**
```python
timing_report = {
    'initialization_time': initialization_time,
    'execution_time': execution_time,
    'total_time': initialization_time + execution_time
}
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
timing_path = os.path.join(work_dir, f"time/timing_report_{timestamp}.json")
with open(timing_path, 'w') as f:
    json.dump(timing_report, f, indent=2)
```

**Locations:**
- `one_shot.py:167-177`
- `one_shot.py:290-298`
- `planning_control.py:351-363`, `550-564`, `775-787`, `848-863`
- `control.py:142-152`

---

### 2.8 Pattern: Empty Directory Cleanup (DUPLICATED 5x)

**Current Code:**
```python
database_full_path = os.path.join(results['final_context']['work_dir'], results['final_context']['database_path'])
codebase_full_path = os.path.join(results['final_context']['work_dir'], results['final_context']['codebase_path'])
time_full_path = os.path.join(results['final_context']['work_dir'], 'time')
for folder in [database_full_path, codebase_full_path, time_full_path]:
    try:
        if os.path.exists(folder) and not os.listdir(folder):
            os.rmdir(folder)
    except OSError:
        pass
```

**Locations:**
- `one_shot.py:194-202`
- `planning_control.py:368-372`, `620-625`, `791-797`, `873-882`
- `control.py:161-167`

---

### 2.9 Pattern: Output Collection & Finalization (DUPLICATED 4x)

**Current Code:**
```python
try:
    workflow_outputs = output_manager.finalize(write_manifest=True)
    results['outputs'] = workflow_outputs.to_dict()
    results['run_id'] = run_id
    print(f"\nCollected {workflow_outputs.total_files} output files")
except Exception as e:
    print(f"\nWarning: Could not collect outputs: {e}")
    results['outputs'] = None
    results['run_id'] = run_id
```

**Locations:**
- `one_shot.py:182-191`
- `planning_control.py:632-641`, `884-893`

---

### 2.10 Pattern: Results Dictionary Building (DUPLICATED 5x)

**Current Code:**
```python
results = {
    'chat_history': cmbagent.chat_result.chat_history,
    'final_context': cmbagent.final_context
}
results['initialization_time'] = initialization_time
results['execution_time'] = execution_time
```

**Locations:** In every workflow function.

---

## 3. Proposed Abstractions

### 3.1 WorkflowContext Class

```python
@dataclass
class WorkflowContext:
    """Encapsulates all workflow execution context."""
    work_dir: str
    run_id: str
    api_keys: Dict[str, str]
    output_manager: WorkflowOutputManager
    callbacks: WorkflowCallbacks
    timing: WorkflowTiming

    @classmethod
    def create(cls, work_dir: str, api_keys: Optional[Dict] = None,
               callbacks: Optional[WorkflowCallbacks] = None) -> 'WorkflowContext':
        """Factory method to create initialized context."""
        work_dir = os.path.abspath(os.path.expanduser(work_dir))
        os.makedirs(work_dir, exist_ok=True)

        if api_keys is None:
            api_keys = get_api_keys_from_env()

        run_id = str(uuid.uuid4())
        output_manager = WorkflowOutputManager(work_dir=work_dir, run_id=run_id)

        if callbacks is None:
            callbacks = create_null_callbacks()

        return cls(
            work_dir=work_dir,
            run_id=run_id,
            api_keys=api_keys,
            output_manager=output_manager,
            callbacks=callbacks,
            timing=WorkflowTiming()
        )
```

### 3.2 WorkflowTiming Class

```python
@dataclass
class WorkflowTiming:
    """Track timing across workflow phases."""
    phases: Dict[str, float] = field(default_factory=dict)
    _current_phase: Optional[str] = None
    _phase_start: Optional[float] = None

    def start_phase(self, phase_name: str) -> None:
        """Start timing a phase."""
        self._current_phase = phase_name
        self._phase_start = time.time()

    def end_phase(self) -> float:
        """End current phase and return duration."""
        if self._phase_start is None:
            return 0.0
        duration = time.time() - self._phase_start
        if self._current_phase:
            self.phases[self._current_phase] = duration
        self._phase_start = None
        return duration

    def save_report(self, path: str) -> None:
        """Save timing report to JSON."""
        report = {
            **self.phases,
            'total_time': sum(self.phases.values())
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(report, f, indent=2)
```

### 3.3 AgentConfigBuilder Class

```python
class AgentConfigBuilder:
    """Builder for agent LLM configurations."""

    def __init__(self, api_keys: Dict[str, str]):
        self.api_keys = api_keys
        self.configs: Dict[str, Dict] = {}

    def add(self, agent_name: str, model: str) -> 'AgentConfigBuilder':
        """Add agent configuration."""
        self.configs[agent_name] = get_model_config(model, self.api_keys)
        return self

    def add_defaults(self, agents: List[str]) -> 'AgentConfigBuilder':
        """Add default configurations for common agents."""
        for agent in agents:
            if agent in default_agents_llm_model:
                self.add(agent, default_agents_llm_model[agent])
        return self

    def build(self) -> Dict[str, Dict]:
        """Return the built configuration."""
        return self.configs
```

### 3.4 CMBAgentFactory Class

```python
class CMBAgentFactory:
    """Factory for creating CMBAgent instances with common configurations."""

    @staticmethod
    def create(
        ctx: WorkflowContext,
        agent_configs: Dict[str, Dict],
        mode: str = "planning_and_control",
        clear_work_dir: bool = False,
        default_llm_model: str = default_llm_model_default,
        default_formatter_model: str = default_formatter_model_default,
        approval_config: Optional[Any] = None,
        **kwargs
    ) -> 'CMBAgent':
        """Create a configured CMBAgent instance."""
        from cmbagent.cmbagent import CMBAgent

        ctx.timing.start_phase('initialization')

        cmbagent = CMBAgent(
            cache_seed=42,
            work_dir=ctx.work_dir,
            default_llm_model=default_llm_model,
            default_formatter_model=default_formatter_model,
            agent_llm_configs=agent_configs,
            api_keys=ctx.api_keys,
            mode=mode,
            clear_work_dir=clear_work_dir,
            approval_config=approval_config,
            **kwargs
        )

        ctx.timing.end_phase()
        return cmbagent

    @staticmethod
    def ensure_groupchat(cmbagent: 'CMBAgent') -> None:
        """Ensure groupchat attribute exists (fixes display_cost bug)."""
        if not hasattr(cmbagent, 'groupchat'):
            Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
            cmbagent.groupchat = Dummy()
```

### 3.5 WorkflowFinalizer Class

```python
class WorkflowFinalizer:
    """Handles workflow finalization tasks."""

    def __init__(self, ctx: WorkflowContext):
        self.ctx = ctx

    def display_cost(self, cmbagent: 'CMBAgent', name_append: Optional[str] = None) -> pd.DataFrame:
        """Display and save cost report."""
        CMBAgentFactory.ensure_groupchat(cmbagent)
        return cmbagent.display_cost(name_append=name_append)

    def save_timing_report(self, phase_name: str = "") -> str:
        """Save timing report and return path."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{phase_name}" if phase_name else ""
        timing_path = os.path.join(self.ctx.work_dir, f"time/timing_report{suffix}_{timestamp}.json")
        self.ctx.timing.save_report(timing_path)
        print(f"\nTiming report saved to: {timing_path}")
        return timing_path

    def collect_outputs(self) -> Optional[Dict]:
        """Collect and finalize outputs."""
        try:
            workflow_outputs = self.ctx.output_manager.finalize(write_manifest=True)
            print(f"\nCollected {workflow_outputs.total_files} output files")
            return {
                'outputs': workflow_outputs.to_dict(),
                'run_id': self.ctx.run_id
            }
        except Exception as e:
            print(f"\nWarning: Could not collect outputs: {e}")
            return {'outputs': None, 'run_id': self.ctx.run_id}

    def cleanup_empty_dirs(self, final_context: Dict) -> None:
        """Remove empty output directories."""
        work_dir = final_context.get('work_dir', self.ctx.work_dir)
        paths = [
            os.path.join(work_dir, final_context.get('database_path', 'data')),
            os.path.join(work_dir, final_context.get('codebase_path', 'codebase')),
            os.path.join(work_dir, 'time')
        ]
        for folder in paths:
            try:
                if os.path.exists(folder) and not os.listdir(folder):
                    os.rmdir(folder)
            except OSError:
                pass

    def build_results(
        self,
        cmbagent: 'CMBAgent',
        extra_fields: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Build standard results dictionary."""
        results = {
            'chat_history': cmbagent.chat_result.chat_history,
            'final_context': cmbagent.final_context,
            **self.ctx.timing.phases
        }

        # Add output collection
        output_info = self.collect_outputs()
        results.update(output_info)

        # Add extra fields
        if extra_fields:
            results.update(extra_fields)

        return results
```

### 3.6 PhaseExecutor Base Class

```python
from abc import ABC, abstractmethod

class PhaseExecutor(ABC):
    """Base class for workflow phase execution."""

    def __init__(self, ctx: WorkflowContext):
        self.ctx = ctx
        self.cmbagent: Optional['CMBAgent'] = None

    @abstractmethod
    def configure_agents(self) -> Dict[str, Dict]:
        """Return agent configurations for this phase."""
        pass

    @abstractmethod
    def build_shared_context(self, task: str, **kwargs) -> Dict[str, Any]:
        """Build shared context for execution."""
        pass

    @abstractmethod
    def get_initial_agent(self) -> str:
        """Return the initial agent name."""
        pass

    def execute(
        self,
        task: str,
        max_rounds: int = 50,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the phase."""
        # Setup
        agent_configs = self.configure_agents()
        shared_context = self.build_shared_context(task, **kwargs)

        # Create agent
        self.cmbagent = CMBAgentFactory.create(
            ctx=self.ctx,
            agent_configs=agent_configs,
            **kwargs
        )

        # Execute
        self.ctx.timing.start_phase('execution')
        self.cmbagent.solve(
            task,
            max_rounds=max_rounds,
            initial_agent=self.get_initial_agent(),
            shared_context=shared_context
        )
        self.ctx.timing.end_phase()

        return self.cmbagent.final_context
```

---

## 4. Refactored Workflow Examples

### 4.1 Refactored `one_shot`

```python
def one_shot(
    task: str,
    agent: str = 'engineer',
    max_rounds: int = 50,
    work_dir: str = work_dir_default,
    api_keys: Optional[Dict] = None,
    **kwargs
) -> Dict[str, Any]:
    """Execute a single-shot task with a specified agent."""

    # 1. Initialize context
    ctx = WorkflowContext.create(work_dir, api_keys)
    ctx.output_manager.set_phase("execution")
    ctx.output_manager.set_agent(agent)

    # 2. Build agent configs
    agent_configs = (
        AgentConfigBuilder(ctx.api_keys)
        .add_defaults(['engineer', 'researcher', 'plot_judge', 'camb_context'])
        .build()
    )

    # 3. Create and execute
    cmbagent = CMBAgentFactory.create(
        ctx=ctx,
        agent_configs=agent_configs,
        mode="one_shot",
        **kwargs
    )

    ctx.timing.start_phase('execution')
    cmbagent.solve(task, max_rounds=max_rounds, initial_agent=agent, mode="one_shot")
    ctx.timing.end_phase()

    # 4. Finalize
    finalizer = WorkflowFinalizer(ctx)
    finalizer.display_cost(cmbagent)
    finalizer.save_timing_report()
    finalizer.cleanup_empty_dirs(cmbagent.final_context)

    return finalizer.build_results(cmbagent, extra_fields={
        'engineer': cmbagent.get_agent_object_from_name('engineer'),
        'researcher': cmbagent.get_agent_object_from_name('researcher'),
    })
```

### 4.2 Refactored `planning_and_control_context_carryover`

```python
def planning_and_control_context_carryover(
    task: str,
    max_rounds_planning: int = 50,
    max_rounds_control: int = 100,
    max_plan_steps: int = 3,
    work_dir: str = work_dir_default,
    callbacks: Optional[WorkflowCallbacks] = None,
    **kwargs
) -> Dict[str, Any]:
    """Execute planning and control workflow with context carryover."""

    # 1. Initialize context
    ctx = WorkflowContext.create(work_dir, kwargs.get('api_keys'), callbacks)
    ctx.callbacks.invoke_workflow_start(task, {'max_plan_steps': max_plan_steps})

    # 2. Planning phase
    planning_executor = PlanningPhaseExecutor(ctx, **kwargs)
    plan_result = planning_executor.execute(task, max_rounds=max_rounds_planning)

    # 3. Control phase (step loop)
    control_executor = ControlPhaseExecutor(ctx, plan_result, **kwargs)
    for step in range(1, plan_result['number_of_steps_in_plan'] + 1):
        ctx.callbacks.invoke_phase_change("control", step)
        step_result = control_executor.execute_step(task, step, max_rounds_control)

        if step_result.get('failed'):
            ctx.callbacks.invoke_workflow_failed(step_result['error'], step)
            break

    # 4. Finalize
    finalizer = WorkflowFinalizer(ctx)
    ctx.callbacks.invoke_workflow_complete(control_executor.final_context, ctx.timing.total)

    return finalizer.build_results(control_executor.cmbagent)
```

---

## 5. Implementation Roadmap

### Phase 1: Core Abstractions (Foundation)
1. Create `workflows/core/context.py` - WorkflowContext, WorkflowTiming
2. Create `workflows/core/config.py` - AgentConfigBuilder
3. Create `workflows/core/factory.py` - CMBAgentFactory
4. Create `workflows/core/finalizer.py` - WorkflowFinalizer

### Phase 2: Migrate Existing Workflows
1. Refactor `one_shot` to use new abstractions
2. Refactor `human_in_the_loop` to use new abstractions
3. Refactor `control` to use new abstractions
4. Test all refactored workflows

### Phase 3: Complex Workflow Refactoring
1. Create `PlanningPhaseExecutor` class
2. Create `ControlPhaseExecutor` class
3. Refactor `planning_and_control`
4. Refactor `planning_and_control_context_carryover`

### Phase 4: Validation & Documentation
1. Add unit tests for new abstractions
2. Integration tests for refactored workflows
3. Update API documentation
4. Migration guide for external users

---

## 6. Benefits of Proposed Abstractions

| Benefit | Description |
|---------|-------------|
| **DRY** | Eliminates ~400 lines of duplicated code |
| **Testability** | Each component can be unit tested independently |
| **Extensibility** | Easy to add new workflow types by extending base classes |
| **Maintainability** | Single point of change for common patterns |
| **Consistency** | All workflows behave the same way |
| **Debugging** | Easier to trace issues with clear phase boundaries |

---

## 7. Metrics

| Metric | Before | After (Estimated) |
|--------|--------|-------------------|
| Total lines in workflows | ~1,300 | ~800 |
| Duplicated patterns | 10+ | 0 |
| Files to modify for timing change | 5 | 1 |
| Files to modify for output format | 5 | 1 |
| Test coverage potential | Low | High |
