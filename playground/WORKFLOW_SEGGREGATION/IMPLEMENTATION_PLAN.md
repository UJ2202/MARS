# Workflow Refactoring Implementation Plan

## Quick Reference

| Document | Purpose |
|----------|---------|
| [WORKFLOW_ABSTRACTION.md](./WORKFLOW_ABSTRACTION.md) | High-level architecture & patterns |
| [COMMON_PATTERNS.md](./COMMON_PATTERNS.md) | Detailed pattern implementations |
| [PHASE_EXECUTION_STRATEGY.md](./PHASE_EXECUTION_STRATEGY.md) | Phase decomposition strategy |

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

**Goal:** Create the foundational classes without breaking existing code.

#### 1.1 Create Package Structure

```bash
cmbagent/workflows/
├── __init__.py              # Existing - add new exports
├── one_shot.py              # Existing
├── control.py               # Existing
├── planning_control.py      # Existing
├── utils.py                 # Existing
└── core/                    # NEW
    ├── __init__.py
    ├── initialization.py    # WorkflowInitResult, initialize_workflow()
    ├── config.py            # AgentConfigBuilder
    ├── factory.py           # CMBAgentFactory, CMBAgentConfig
    ├── timing.py            # WorkflowTimer, TimingPhase
    └── finalization.py      # WorkflowFinalizer, FinalizationConfig
```

#### 1.2 Implementation Order

1. **timing.py** - No dependencies, pure utility
2. **config.py** - Depends only on cmbagent.utils
3. **initialization.py** - Depends on timing, config
4. **factory.py** - Depends on timing
5. **finalization.py** - Depends on timing, factory

#### 1.3 Deliverables

- [ ] `workflows/core/timing.py` with tests
- [ ] `workflows/core/config.py` with tests
- [ ] `workflows/core/initialization.py` with tests
- [ ] `workflows/core/factory.py` with tests
- [ ] `workflows/core/finalization.py` with tests

---

### Phase 2: Migrate Simple Workflows (Week 2)

**Goal:** Refactor `one_shot` and `control` using new infrastructure.

#### 2.1 Refactor one_shot

**Current:** 177 lines in `one_shot.py:27-204`

**Target:** ~60 lines using core abstractions

```python
def one_shot(task, agent='engineer', max_rounds=50, work_dir=work_dir_default,
             api_keys=None, **kwargs) -> Dict[str, Any]:
    """Execute a single-shot task with a specified agent."""

    # 1. Initialize (replaces lines 73-91)
    init = initialize_workflow(
        work_dir=work_dir,
        api_keys=api_keys,
        phase="execution",
        agent=agent
    )

    # 2. Configure agents (replaces lines 88-91)
    agent_configs = one_shot_agent_configs(
        init.api_keys,
        kwargs.get('engineer_model', default_agents_llm_model['engineer']),
        kwargs.get('researcher_model', default_agents_llm_model['researcher']),
        kwargs.get('plot_judge_model', default_agents_llm_model['plot_judge']),
        kwargs.get('camb_context_model', default_agents_llm_model['camb_context'])
    )

    # 3. Create agent (replaces lines 93-110)
    timer = WorkflowTimer()
    cmbagent, _ = CMBAgentFactory.create(
        work_dir=init.work_dir,
        agent_configs=agent_configs,
        api_keys=init.api_keys,
        config=CMBAgentConfig(mode="one_shot", clear_work_dir=kwargs.get('clear_work_dir', False))
    )

    # 4. Execute (replaces lines 112-145)
    with timer.phase("execution"):
        cmbagent.solve(task, max_rounds=max_rounds, initial_agent=agent, mode="one_shot",
                       shared_context={'max_n_attempts': kwargs.get('max_n_attempts', 3)})

    # 5. Finalize (replaces lines 147-202)
    finalizer = WorkflowFinalizer(
        cmbagent=cmbagent, timer=timer, output_manager=init.output_manager,
        work_dir=init.work_dir, run_id=init.run_id
    )

    return finalizer.finalize(extra_results={
        'engineer': cmbagent.get_agent_object_from_name('engineer'),
        'researcher': cmbagent.get_agent_object_from_name('researcher'),
    })
```

#### 2.2 Refactor control

**Current:** 151 lines in `control.py:19-170`

**Target:** ~50 lines using core abstractions

#### 2.3 Deliverables

- [ ] Refactored `one_shot()` function
- [ ] Refactored `control()` function
- [ ] Tests passing for both
- [ ] Backward compatibility verified

---

### Phase 3: Phase Classes (Week 3)

**Goal:** Create phase execution classes for complex workflows.

#### 3.1 Create Phase Package

```bash
cmbagent/workflows/
└── phases/                  # NEW
    ├── __init__.py
    ├── base.py              # WorkflowPhase, PhaseResult
    ├── planning.py          # PlanningPhase
    └── control.py           # ControlPhase
```

#### 3.2 Implementation

1. **base.py** - Abstract base class with common lifecycle
2. **planning.py** - PlanningPhase implementation
3. **control.py** - ControlPhase with step loop

#### 3.3 Deliverables

- [ ] `workflows/phases/base.py` with tests
- [ ] `workflows/phases/planning.py` with tests
- [ ] `workflows/phases/control.py` with tests

---

### Phase 4: Orchestrator & Complex Workflows (Week 4)

**Goal:** Create orchestrator and refactor complex workflows.

#### 4.1 Create Orchestrator

```bash
cmbagent/workflows/
└── orchestrator.py          # NEW - WorkflowOrchestrator, WorkflowConfig
```

#### 4.2 Refactor planning_and_control

**Current:** 251 lines in `planning_control.py:645-896`

**Target:** ~30 lines using orchestrator

```python
def planning_and_control(task, max_rounds_planning=50, max_rounds_control=100,
                         work_dir=work_dir_default, api_keys=None, **kwargs):
    """Execute planning and control workflow without context carryover."""

    init = initialize_workflow(work_dir=work_dir, api_keys=api_keys)

    orchestrator = WorkflowOrchestrator(
        work_dir=init.work_dir,
        api_keys=init.api_keys,
        callbacks=init.callbacks,
        config=WorkflowConfig(
            max_rounds_planning=max_rounds_planning,
            max_rounds_control=max_rounds_control,
            max_plan_steps=kwargs.get('max_plan_steps', 3)
        ),
        **kwargs
    )

    return orchestrator.run(task)
```

#### 4.3 Refactor planning_and_control_context_carryover

**Current:** 610 lines in `planning_control.py:32-642`

**Target:** ~40 lines using orchestrator

#### 4.4 Deliverables

- [ ] `workflows/orchestrator.py` with tests
- [ ] Refactored `planning_and_control()`
- [ ] Refactored `planning_and_control_context_carryover()`
- [ ] All tests passing
- [ ] Integration tests

---

### Phase 5: Documentation & Cleanup (Week 5)

**Goal:** Complete documentation and remove deprecated code.

#### 5.1 Documentation

- [ ] Update module docstrings
- [ ] Create migration guide for external users
- [ ] Update CLAUDE.md with new architecture

#### 5.2 Cleanup

- [ ] Remove duplicate code
- [ ] Archive old implementations
- [ ] Update type hints
- [ ] Add comprehensive logging

---

## File Changes Summary

### New Files (Create)

| File | Lines | Purpose |
|------|-------|---------|
| `workflows/core/__init__.py` | ~20 | Package exports |
| `workflows/core/timing.py` | ~80 | Timing management |
| `workflows/core/config.py` | ~60 | Agent configuration |
| `workflows/core/initialization.py` | ~70 | Workflow init |
| `workflows/core/factory.py` | ~80 | CMBAgent factory |
| `workflows/core/finalization.py` | ~100 | Finalization |
| `workflows/phases/__init__.py` | ~10 | Package exports |
| `workflows/phases/base.py` | ~120 | Base phase class |
| `workflows/phases/planning.py` | ~150 | Planning phase |
| `workflows/phases/control.py` | ~180 | Control phase |
| `workflows/orchestrator.py` | ~120 | Orchestrator |

**Total new code:** ~990 lines

### Modified Files (Refactor)

| File | Before | After | Reduction |
|------|--------|-------|-----------|
| `workflows/one_shot.py` | 302 | ~120 | -60% |
| `workflows/control.py` | 170 | ~80 | -53% |
| `workflows/planning_control.py` | 900 | ~100 | -89% |

**Total refactored:** ~600 lines removed

### Net Change

- **New code:** +990 lines
- **Removed:** -600 lines
- **Net:** +390 lines

But with:
- 0 duplicated patterns (was 10+)
- 5+ testable units (was 1)
- Easy extensibility

---

## Testing Strategy

### Unit Tests

```python
# tests/workflows/core/test_timing.py
def test_workflow_timer_phase_tracking():
    timer = WorkflowTimer()
    with timer.phase("test"):
        time.sleep(0.1)
    assert timer.get_duration("test") >= 0.1

# tests/workflows/core/test_config.py
def test_agent_config_builder():
    configs = (AgentConfigBuilder(api_keys)
               .add('engineer', 'gpt-4o')
               .add_defaults(['researcher'])
               .build())
    assert 'engineer' in configs
    assert 'researcher' in configs
```

### Integration Tests

```python
# tests/workflows/test_one_shot_refactored.py
def test_one_shot_produces_same_results():
    """Verify refactored one_shot matches original behavior."""
    task = "Write a simple hello world script"

    # Run with refactored code
    result = one_shot(task, agent='engineer', work_dir=tmp_dir)

    assert 'chat_history' in result
    assert 'final_context' in result
    assert result.get('success', True)
```

---

## Rollback Strategy

Each phase maintains backward compatibility:

1. **Phase 1:** New code in `core/` only - no changes to existing
2. **Phase 2:** Refactored functions call same APIs - tests verify
3. **Phase 3:** Phase classes are additive - existing code untouched
4. **Phase 4:** Orchestrator wraps phases - can fall back to old code

If issues arise:
```python
# In __init__.py, switch between implementations
USE_NEW_IMPLEMENTATION = os.getenv("CMBAGENT_USE_NEW_WORKFLOWS", "true").lower() == "true"

if USE_NEW_IMPLEMENTATION:
    from .planning_control_v2 import planning_and_control_context_carryover
else:
    from .planning_control import planning_and_control_context_carryover
```

---

## Success Criteria

1. **All existing tests pass** without modification
2. **Code coverage** for new modules > 80%
3. **No performance regression** (< 5% overhead)
4. **Reduced duplication** from ~600 lines to 0
5. **Clear documentation** for new architecture
