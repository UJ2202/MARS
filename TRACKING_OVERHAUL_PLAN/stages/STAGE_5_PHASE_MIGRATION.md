# Stage 5: Phase Migration

## Objectives
1. Ensure ALL phases use PhaseExecutionManager consistently
2. Simplify PhaseExecutionManager (remove DAG/DB/file logic already moved in prior stages)
3. Fix phases missing manager integration (IdeaGeneration, HITLCheckpoint, OneShot)
4. Standardize the phase lifecycle pattern across all phases
5. Skip copilot phase (will be revamped later)

## Dependencies
- Stage 0 (callback contract)
- Stage 1 (DAG creation removed from manager)
- Stage 4 (file tracking removed from manager)

---

## Current State

### Phase Integration Matrix

| Phase | File | Uses PhaseExecutionManager | Uses Callbacks | Status |
|-------|------|---------------------------|----------------|--------|
| PlanningPhase | `phases/planning.py` | YES (line 25) | YES | OK |
| ControlPhase | `phases/control.py` | YES (line 29) | YES | OK |
| HITLPlanningPhase | `phases/hitl_planning.py` | YES (line 28) | YES | OK |
| HITLControlPhase | `phases/hitl_control.py` | YES (line 29) | YES | OK |
| IdeaGenerationPhase | `phases/idea_generation.py` | **NO** (line 79) | PARTIAL (line 96) | BROKEN |
| HITLCheckpointPhase | `phases/hitl_checkpoint.py` | **NO** (line 63) | **NO** | BROKEN |
| OneShotPhase | `phases/one_shot.py` | **NO** (line 75) | PARTIAL (line 124) | PARTIAL |
| CopilotPhase | `phases/copilot_phase.py` | SKIP | SKIP | SKIP (later) |

### PhaseExecutionManager After Prior Stages
After Stages 0, 1, 3, 4, the manager should only do:
- Invoke callbacks at lifecycle points (start, complete, fail, step transitions)
- Track timing
- Handle pause/cancel checks
- Set up event capture context (via contextvars)

**NOT** do (already removed):
- DAG creation (Stage 1)
- DB writes (Stage 0/1)
- File tracking (Stage 4)

---

## Implementation Tasks

### Task 5.1: Finalize PhaseExecutionManager Simplification

**File**: `cmbagent/phases/execution_manager.py`

After DAG removal (Stage 1) and file tracking removal (Stage 4), verify the manager is clean:

```python
class PhaseExecutionManager:
    """
    Cross-cutting concern coordinator for phase execution.

    Responsibilities (ONLY these):
    - Invoke callbacks at lifecycle points
    - Track timing
    - Handle pause/cancel via should_continue
    - Set up event capture context
    - Error handling at phase boundaries
    """

    def __init__(self, context, phase, config=None):
        self.context = context
        self.phase = phase
        self.config = config or PhaseExecutionConfig()
        self.start_time = None
        self.end_time = None
        self.current_step = None
        self.is_cancelled = False

    def start(self):
        """Signal phase start via callbacks."""
        self.start_time = time.time()
        if self.config.enable_callbacks and self.context.callbacks:
            self.context.callbacks.invoke_phase_change(
                self.phase.phase_type, None
            )
        self._setup_event_capture()
        logger.info("PHASE_START: %s", self.phase.phase_type)

    def complete(self, output=None):
        """Signal phase completion via callbacks."""
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        if self.config.enable_callbacks and self.context.callbacks:
            # Phase-level completion callback - app handles DAG update
            pass  # Phase completion is implicit - step callbacks drive DAG
        self._teardown_event_capture()
        logger.info("PHASE_COMPLETE: %s (%.1fs)", self.phase.phase_type, duration)
        return output

    def fail(self, error, output=None):
        """Signal phase failure via callbacks."""
        self.end_time = time.time()
        if self.config.enable_callbacks and self.context.callbacks:
            step_info = StepInfo(
                step_number=self.current_step or 0,
                error=str(error),
                status=StepStatus.FAILED,
            )
            self.context.callbacks.invoke_step_failed(step_info)
        self._teardown_event_capture()
        logger.error("PHASE_FAILED: %s - %s", self.phase.phase_type, error)
        return output

    def start_step(self, step_number, description="", agent=None):
        """Signal step start via callbacks."""
        self.current_step = step_number
        if self.config.enable_callbacks and self.context.callbacks:
            step_info = StepInfo(
                step_number=step_number,
                goal=description,
                description=description,
                agent=agent,
                status=StepStatus.RUNNING,
                started_at=time.time(),
            )
            self.context.callbacks.invoke_step_start(step_info)

    def complete_step(self, step_number, output=None):
        """Signal step completion via callbacks."""
        if self.config.enable_callbacks and self.context.callbacks:
            step_info = StepInfo(
                step_number=step_number,
                status=StepStatus.COMPLETED,
                output=output,
            )
            self.context.callbacks.invoke_step_complete(step_info)

    def fail_step(self, step_number, error):
        """Signal step failure via callbacks."""
        if self.config.enable_callbacks and self.context.callbacks:
            step_info = StepInfo(
                step_number=step_number,
                error=str(error),
                status=StepStatus.FAILED,
            )
            self.context.callbacks.invoke_step_failed(step_info)

    def check_should_continue(self):
        """Check pause/cancel via callbacks."""
        if self.context.callbacks:
            if self.context.callbacks.on_pause_check:
                self.context.callbacks.on_pause_check()
            if self.context.callbacks.should_continue:
                if not self.context.callbacks.should_continue():
                    raise WorkflowCancelled("Cancelled by user")

    def _setup_event_capture(self):
        from cmbagent.execution.event_capture import EventCaptureManager, set_event_captor
        # Set up session-scoped captor via contextvars
        shared = self.context.shared_state or {}
        db_session = shared.get('_db_session')
        if db_session:
            captor = EventCaptureManager(
                db_session=db_session,
                run_id=self.context.run_id,
                session_id=shared.get('session_id', ''),
            )
            set_event_captor(captor)

    def _teardown_event_capture(self):
        from cmbagent.execution.event_capture import get_event_captor, set_event_captor
        captor = get_event_captor()
        if captor:
            captor.flush()
            set_event_captor(None)
```

### Task 5.2: Fix IdeaGenerationPhase

**File**: `cmbagent/phases/idea_generation.py`

Currently does NOT use PhaseExecutionManager. Add it:

```python
class IdeaGenerationPhase(Phase):
    phase_type = "idea_generation"
    display_name = "Idea Generation"

    def execute(self, context):
        manager = PhaseExecutionManager(context, self)
        manager.start()

        try:
            # Idea maker step
            manager.start_step(1, "Generate ideas", agent="idea_maker")
            ideas = self._generate_ideas(context)
            manager.complete_step(1, output=ideas)

            # Idea hater/critic step
            manager.start_step(2, "Critique ideas", agent="idea_hater")
            critiqued = self._critique_ideas(context, ideas)
            manager.complete_step(2, output=critiqued)

            return manager.complete(output=critiqued)
        except Exception as e:
            return manager.fail(error=e)
```

### Task 5.3: Fix HITLCheckpointPhase

**File**: `cmbagent/phases/hitl_checkpoint.py`

Currently has NO PhaseExecutionManager and NO approval tracking:

```python
class HITLCheckpointPhase(Phase):
    phase_type = "hitl_checkpoint"
    display_name = "Human Review"

    def execute(self, context):
        manager = PhaseExecutionManager(context, self)
        manager.start()

        try:
            manager.start_step(1, "Awaiting human approval")

            # Request approval
            approval_result = self._request_approval(context)

            if approval_result.approved:
                manager.complete_step(1, output={"approved": True})
            else:
                manager.complete_step(1, output={"approved": False, "feedback": approval_result.feedback})

            return manager.complete(output=approval_result)
        except Exception as e:
            return manager.fail(error=e)
```

### Task 5.4: Fix OneShotPhase

**File**: `cmbagent/phases/one_shot.py`

Currently has partial callbacks but no PhaseExecutionManager:

```python
class OneShotPhase(Phase):
    phase_type = "one_shot"
    display_name = "One-Shot Execution"

    def execute(self, context):
        manager = PhaseExecutionManager(context, self)
        manager.start()

        try:
            manager.start_step(1, f"Execute with {self.agent}", agent=self.agent)

            result = self._run_agent(context)

            manager.complete_step(1, output=result)
            return manager.complete(output=result)
        except Exception as e:
            return manager.fail(error=e)
```

### Task 5.5: Simplify PhaseExecutionConfig

**File**: `cmbagent/phases/execution_manager.py`

Remove flags that no longer apply:
```python
@dataclass
class PhaseExecutionConfig:
    enable_callbacks: bool = True
    enable_pause_check: bool = True
    auto_checkpoint: bool = False
    checkpoint_interval: int = 300
    # REMOVED: enable_database (no longer relevant)
    # REMOVED: enable_dag (no longer relevant)
    # REMOVED: enable_file_tracking (no longer relevant)
```

### Task 5.6: Verify Phase Registry

**File**: `cmbagent/phases/registry.py`

Ensure all phases are registered:
```python
PHASE_REGISTRY = {
    "planning": PlanningPhase,
    "control": ControlPhase,
    "one_shot": OneShotPhase,
    "idea_generation": IdeaGenerationPhase,
    "hitl_planning": HITLPlanningPhase,
    "hitl_control": HITLControlPhase,
    "hitl_checkpoint": HITLCheckpointPhase,
    # copilot: SKIPPED for now
}
```

---

## Cleanup Items
| Item | Lines Removed |
|------|--------------|
| PhaseExecutionManager DAG/DB/file code (if not already in prior stages) | ~400 |
| Stale flags in PhaseExecutionConfig | ~15 |
| **Total** | **~415** |

## Verification
```bash
# All phases use PhaseExecutionManager
for f in planning.py control.py one_shot.py idea_generation.py hitl_planning.py hitl_control.py hitl_checkpoint.py; do
  echo "$f: $(grep -c 'PhaseExecutionManager' cmbagent/phases/$f)"
done
# All should print >= 1

# Manager has no DAG/DB/file code
grep -c "dag_repo\|db_session\|track_file\|create_node" cmbagent/phases/execution_manager.py  # 0

# HITL regression
# (manual test: run HITL workflow end-to-end)
```

## Files Modified
| File | Action |
|------|--------|
| `cmbagent/phases/execution_manager.py` | Final simplification |
| `cmbagent/phases/idea_generation.py` | Add PhaseExecutionManager |
| `cmbagent/phases/hitl_checkpoint.py` | Add PhaseExecutionManager |
| `cmbagent/phases/one_shot.py` | Add PhaseExecutionManager |
| `cmbagent/phases/registry.py` | Verify all registered |
