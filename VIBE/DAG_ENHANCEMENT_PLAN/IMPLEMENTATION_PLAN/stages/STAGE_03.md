# Stage 3: State Machine Implementation

**Phase:** 0 - Foundation
**Estimated Time:** 25-35 minutes
**Dependencies:** Stage 2 (Database Schema) must be complete
**Risk Level:** Medium

## Objectives

1. Implement formal state machine for workflow_runs and workflow_steps
2. Define all valid states and transitions with guards
3. Add state transition history tracking to database
4. Create state machine manager with event emission
5. Integrate state machine with existing workflow execution
6. Support pause/resume functionality at state level

## Current State Analysis

### What We Have
- Informal status tracking via string fields
- No formal state validation
- Status changes not audited
- Cannot safely pause/resume
- No state transition guards

### What We Need
- Formal state machine with defined transitions
- State validation before transitions
- Audit trail of all state changes
- Event emission on state transitions
- Pause/resume support built into states
- Rollback capability for failed transitions

## Pre-Stage Verification

### Check Prerequisites
1. Stage 2 complete and verified
2. Database models created and working
3. workflow_runs and workflow_steps tables exist
4. Session isolation functioning
5. Existing workflows can write to database

### Expected State
- Can create workflow_runs in database
- Can query workflow status
- Ready to add state machine logic
- No breaking changes to current execution

## Implementation Tasks

### Task 1: Define State Enumerations
**Objective:** Create formal state definitions for workflows and steps

**Implementation:**

Create workflow states enum:
```python
from enum import Enum

class WorkflowState(str, Enum):
    """Valid states for workflow_runs"""
    DRAFT = "draft"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepState(str, Enum):
    """Valid states for workflow_steps"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
```

**Files to Create:**
- `cmbagent/database/states.py`

**Verification:**
- Enums defined correctly
- States match database VARCHAR constraints
- Can import and use enum values
- String serialization works

### Task 2: Define State Transition Rules
**Objective:** Specify all valid state transitions and guards

**Implementation:**

Create transition rule configuration:
```python
WORKFLOW_TRANSITIONS = {
    WorkflowState.DRAFT: {
        "allowed_next": [WorkflowState.PLANNING, WorkflowState.CANCELLED],
        "guards": {
            WorkflowState.PLANNING: lambda run: run.task_description is not None,
        }
    },
    WorkflowState.PLANNING: {
        "allowed_next": [WorkflowState.EXECUTING, WorkflowState.FAILED, WorkflowState.CANCELLED],
        "guards": {
            WorkflowState.EXECUTING: lambda run: has_valid_plan(run),
        }
    },
    WorkflowState.EXECUTING: {
        "allowed_next": [
            WorkflowState.PAUSED,
            WorkflowState.WAITING_APPROVAL,
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED
        ],
        "guards": {}
    },
    WorkflowState.PAUSED: {
        "allowed_next": [WorkflowState.EXECUTING, WorkflowState.CANCELLED],
        "guards": {}
    },
    WorkflowState.WAITING_APPROVAL: {
        "allowed_next": [WorkflowState.EXECUTING, WorkflowState.CANCELLED],
        "guards": {
            WorkflowState.EXECUTING: lambda run: has_approval(run),
        }
    },
    WorkflowState.COMPLETED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    },
    WorkflowState.FAILED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    },
    WorkflowState.CANCELLED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    }
}

STEP_TRANSITIONS = {
    StepState.PENDING: {
        "allowed_next": [StepState.RUNNING, StepState.SKIPPED, StepState.CANCELLED],
        "guards": {}
    },
    StepState.RUNNING: {
        "allowed_next": [
            StepState.PAUSED,
            StepState.WAITING_APPROVAL,
            StepState.COMPLETED,
            StepState.FAILED,
            StepState.CANCELLED
        ],
        "guards": {}
    },
    StepState.PAUSED: {
        "allowed_next": [StepState.RUNNING, StepState.CANCELLED],
        "guards": {}
    },
    StepState.WAITING_APPROVAL: {
        "allowed_next": [StepState.RUNNING, StepState.CANCELLED],
        "guards": {}
    },
    StepState.COMPLETED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    },
    StepState.FAILED: {
        "allowed_next": [StepState.RUNNING],  # Can retry
        "guards": {}
    },
    StepState.SKIPPED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    },
    StepState.CANCELLED: {
        "allowed_next": [],  # Terminal state
        "guards": {}
    }
}
```

**Files to Create:**
- `cmbagent/database/transitions.py`

**Verification:**
- All states covered
- Transition rules logical
- Terminal states identified
- Guards defined for critical transitions

### Task 3: Create State History Table
**Objective:** Track all state transitions for audit trail

**Implementation:**

Add new model to `cmbagent/database/models.py`:
```python
class StateHistory(Base):
    __tablename__ = "state_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(50), nullable=False)  # "workflow_run" or "workflow_step"
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)

    from_state = Column(String(50), nullable=True)  # Null for initial state
    to_state = Column(String(50), nullable=False)
    transition_reason = Column(Text, nullable=True)
    transitioned_by = Column(String(100), nullable=True)  # User or system

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    metadata = Column(JSON, default=dict)

    # Indexes
    __table_args__ = (
        Index("idx_state_history_entity", "entity_type", "entity_id"),
        Index("idx_state_history_session", "session_id"),
    )
```

Create Alembic migration:
```bash
alembic revision -m "Add state_history table"
alembic upgrade head
```

**Files to Modify:**
- `cmbagent/database/models.py` (add StateHistory model)

**Files to Create:**
- `cmbagent/database/migrations/versions/002_add_state_history.py`

**Verification:**
- StateHistory table created
- Indexes on entity lookups
- Can record state transitions
- Can query state history

### Task 4: Implement State Machine Manager
**Objective:** Create central state machine logic with validation

**Implementation:**

```python
from typing import Optional, Callable
from cmbagent.database.states import WorkflowState, StepState
from cmbagent.database.transitions import WORKFLOW_TRANSITIONS, STEP_TRANSITIONS
from cmbagent.database.models import WorkflowRun, WorkflowStep, StateHistory

class StateMachineError(Exception):
    """Raised when invalid state transition attempted"""
    pass

class StateMachine:
    """Manages state transitions for workflows and steps"""

    def __init__(self, db_session, entity_type: str):
        """
        Args:
            db_session: SQLAlchemy session
            entity_type: "workflow_run" or "workflow_step"
        """
        self.db = db_session
        self.entity_type = entity_type

        if entity_type == "workflow_run":
            self.model_class = WorkflowRun
            self.state_class = WorkflowState
            self.transitions = WORKFLOW_TRANSITIONS
        elif entity_type == "workflow_step":
            self.model_class = WorkflowStep
            self.state_class = StepState
            self.transitions = STEP_TRANSITIONS
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

    def transition_to(
        self,
        entity_id: str,
        new_state: str,
        reason: Optional[str] = None,
        transitioned_by: str = "system"
    ) -> None:
        """
        Transition entity to new state with validation

        Args:
            entity_id: UUID of workflow_run or workflow_step
            new_state: Target state
            reason: Optional reason for transition
            transitioned_by: Who/what triggered transition

        Raises:
            StateMachineError: If transition invalid
        """
        # Load entity
        entity = self.db.query(self.model_class).filter(
            self.model_class.id == entity_id
        ).first()

        if not entity:
            raise StateMachineError(f"{self.entity_type} {entity_id} not found")

        current_state = entity.status
        new_state_enum = self.state_class(new_state)

        # Validate transition
        self._validate_transition(entity, current_state, new_state_enum)

        # Update entity state
        entity.status = new_state

        # Record in state history
        state_history = StateHistory(
            entity_type=self.entity_type,
            entity_id=entity_id,
            session_id=entity.session_id,
            from_state=current_state,
            to_state=new_state,
            transition_reason=reason,
            transitioned_by=transitioned_by
        )
        self.db.add(state_history)

        # Commit transaction
        self.db.commit()

    def _validate_transition(self, entity, current_state: str, new_state: str) -> None:
        """
        Validate state transition is allowed

        Raises:
            StateMachineError: If transition not allowed
        """
        current_state_enum = self.state_class(current_state)
        transition_rules = self.transitions.get(current_state_enum)

        if not transition_rules:
            raise StateMachineError(
                f"No transition rules for state: {current_state}"
            )

        allowed_next = transition_rules["allowed_next"]
        if new_state not in allowed_next:
            raise StateMachineError(
                f"Invalid transition: {current_state} -> {new_state}. "
                f"Allowed: {[s.value for s in allowed_next]}"
            )

        # Check guards
        guards = transition_rules.get("guards", {})
        guard_func = guards.get(new_state)
        if guard_func and not guard_func(entity):
            raise StateMachineError(
                f"Guard failed for transition: {current_state} -> {new_state}"
            )

    def get_allowed_transitions(self, entity_id: str) -> list:
        """Get list of valid next states for entity"""
        entity = self.db.query(self.model_class).filter(
            self.model_class.id == entity_id
        ).first()

        if not entity:
            return []

        current_state_enum = self.state_class(entity.status)
        transition_rules = self.transitions.get(current_state_enum, {})
        return [s.value for s in transition_rules.get("allowed_next", [])]

    def can_transition_to(self, entity_id: str, new_state: str) -> bool:
        """Check if transition to new_state is valid"""
        try:
            entity = self.db.query(self.model_class).filter(
                self.model_class.id == entity_id
            ).first()

            if not entity:
                return False

            current_state = entity.status
            new_state_enum = self.state_class(new_state)

            self._validate_transition(entity, current_state, new_state_enum)
            return True
        except StateMachineError:
            return False

    def get_state_history(self, entity_id: str) -> list:
        """Get full state transition history for entity"""
        return self.db.query(StateHistory).filter(
            StateHistory.entity_type == self.entity_type,
            StateHistory.entity_id == entity_id
        ).order_by(StateHistory.created_at).all()
```

**Files to Create:**
- `cmbagent/database/state_machine.py`

**Verification:**
- Can transition between valid states
- Invalid transitions raise StateMachineError
- Guards are checked
- State history recorded
- Can query allowed transitions

### Task 5: Add Event Emission on State Changes
**Objective:** Emit events for WebSocket broadcasting

**Implementation:**

Add event emitter to state machine:
```python
from typing import Callable, Dict, List

class EventEmitter:
    """Simple event emitter for state changes"""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def on(self, event_name: str, callback: Callable):
        """Register event listener"""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def emit(self, event_name: str, **kwargs):
        """Emit event to all listeners"""
        listeners = self._listeners.get(event_name, [])
        for listener in listeners:
            try:
                listener(**kwargs)
            except Exception as e:
                # Log error but don't fail state transition
                print(f"Event listener error: {e}")

# Update StateMachine class
class StateMachine:
    def __init__(self, db_session, entity_type: str, event_emitter: Optional[EventEmitter] = None):
        # ... existing init ...
        self.event_emitter = event_emitter or EventEmitter()

    def transition_to(self, entity_id: str, new_state: str, reason: Optional[str] = None, transitioned_by: str = "system"):
        # ... existing validation ...

        # Emit event BEFORE transition
        self.event_emitter.emit(
            "state_changing",
            entity_type=self.entity_type,
            entity_id=entity_id,
            from_state=current_state,
            to_state=new_state,
            reason=reason
        )

        # ... perform transition ...

        # Emit event AFTER transition
        self.event_emitter.emit(
            "state_changed",
            entity_type=self.entity_type,
            entity_id=entity_id,
            from_state=current_state,
            to_state=new_state,
            reason=reason
        )
```

**Files to Modify:**
- `cmbagent/database/state_machine.py` (add EventEmitter)

**Verification:**
- Events emitted on state changes
- Listeners can register callbacks
- Errors in listeners don't break transitions
- Can use for WebSocket broadcasting

### Task 6: Integrate with CMBAgent Workflow
**Objective:** Use state machine in existing workflow execution

**Implementation:**

Update `cmbagent/cmbagent.py`:
```python
from cmbagent.database.state_machine import StateMachine
from cmbagent.database.states import WorkflowState, StepState

class CMBAgent:
    def __init__(self, ...):
        # ... existing init ...

        # State machines
        self.workflow_sm = StateMachine(self.db_session, "workflow_run")
        self.step_sm = StateMachine(self.db_session, "workflow_step")

    def planning_and_control_context_carryover(self, task, agent="engineer", model="gpt-4o", ...):
        # Create workflow run (in DRAFT state)
        run = self.repo.create_run(
            mode="planning_control",
            agent=agent,
            model=model,
            status=WorkflowState.DRAFT,
            task_description=task
        )

        # Transition to PLANNING
        self.workflow_sm.transition_to(
            run.id,
            WorkflowState.PLANNING,
            reason="Starting planning phase"
        )

        try:
            # Execute planning
            plan = self._execute_planning(run)

            # Transition to EXECUTING
            self.workflow_sm.transition_to(
                run.id,
                WorkflowState.EXECUTING,
                reason="Planning complete, starting execution"
            )

            # Execute control loop
            for step_num in range(len(plan.steps)):
                # Create step (in PENDING state)
                step = self.repo.create_step(
                    run_id=run.id,
                    step_number=step_num,
                    status=StepState.PENDING
                )

                # Transition to RUNNING
                self.step_sm.transition_to(
                    step.id,
                    StepState.RUNNING,
                    reason=f"Executing step {step_num}"
                )

                # Execute step
                result = self._execute_step(step)

                # Transition to COMPLETED
                self.step_sm.transition_to(
                    step.id,
                    StepState.COMPLETED,
                    reason="Step execution successful"
                )

            # All steps done, workflow complete
            self.workflow_sm.transition_to(
                run.id,
                WorkflowState.COMPLETED,
                reason="All steps completed successfully"
            )

        except Exception as e:
            # Transition to FAILED
            self.workflow_sm.transition_to(
                run.id,
                WorkflowState.FAILED,
                reason=f"Error: {str(e)}"
            )
            raise
```

**Files to Modify:**
- `cmbagent/cmbagent.py` (add state machine usage)
- `cmbagent/functions.py` (update control loop with state transitions)

**Verification:**
- Workflow transitions through states correctly
- Steps transition through states correctly
- State history recorded in database
- Can query state at any point
- Invalid transitions blocked

### Task 7: Implement Pause/Resume Functionality
**Objective:** Support pausing and resuming workflows

**Implementation:**

Add pause/resume methods:
```python
class WorkflowController:
    """Controls workflow execution with pause/resume"""

    def __init__(self, db_session, session_id):
        self.db = db_session
        self.session_id = session_id
        self.workflow_sm = StateMachine(db_session, "workflow_run")
        self.step_sm = StateMachine(db_session, "workflow_step")

    def pause_workflow(self, run_id: str, reason: str = "User requested pause"):
        """Pause running workflow"""
        run = self.db.query(WorkflowRun).filter(
            WorkflowRun.id == run_id,
            WorkflowRun.session_id == self.session_id
        ).first()

        if not run:
            raise ValueError(f"Run {run_id} not found in session")

        # Can only pause if currently executing
        if run.status != WorkflowState.EXECUTING:
            raise StateMachineError(
                f"Cannot pause workflow in state: {run.status}"
            )

        # Transition workflow to PAUSED
        self.workflow_sm.transition_to(run_id, WorkflowState.PAUSED, reason)

        # Pause currently running steps
        running_steps = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id,
            WorkflowStep.status == StepState.RUNNING
        ).all()

        for step in running_steps:
            self.step_sm.transition_to(
                step.id,
                StepState.PAUSED,
                reason="Workflow paused"
            )

    def resume_workflow(self, run_id: str, reason: str = "User requested resume"):
        """Resume paused workflow"""
        run = self.db.query(WorkflowRun).filter(
            WorkflowRun.id == run_id,
            WorkflowRun.session_id == self.session_id
        ).first()

        if not run:
            raise ValueError(f"Run {run_id} not found in session")

        # Can only resume if currently paused
        if run.status != WorkflowState.PAUSED:
            raise StateMachineError(
                f"Cannot resume workflow in state: {run.status}"
            )

        # Transition workflow back to EXECUTING
        self.workflow_sm.transition_to(run_id, WorkflowState.EXECUTING, reason)

        # Resume paused steps
        paused_steps = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id,
            WorkflowStep.status == StepState.PAUSED
        ).all()

        for step in paused_steps:
            self.step_sm.transition_to(
                step.id,
                StepState.RUNNING,
                reason="Workflow resumed"
            )
```

**Files to Create:**
- `cmbagent/database/workflow_controller.py`

**Verification:**
- Can pause executing workflows
- Can resume paused workflows
- Cannot pause/resume from invalid states
- Steps paused/resumed with workflow
- State transitions recorded

## Files to Create (Summary)

### New Files
```
cmbagent/database/
├── states.py                    # State enumerations
├── transitions.py               # Transition rules and guards
├── state_machine.py             # StateMachine and EventEmitter
└── workflow_controller.py       # Pause/resume functionality
```

### New Migrations
```
cmbagent/database/migrations/versions/
└── 002_add_state_history.py     # StateHistory table
```

### Modified Files
- `cmbagent/database/models.py` - Add StateHistory model
- `cmbagent/cmbagent.py` - Integrate state machine
- `cmbagent/functions.py` - Add state transitions in control loop

## Verification Criteria

### Must Pass
- [ ] State enumerations defined for workflows and steps
- [ ] Transition rules cover all states
- [ ] StateHistory table created via migration
- [ ] StateMachine validates transitions correctly
- [ ] Invalid transitions raise StateMachineError
- [ ] Guards checked before transitions
- [ ] State history recorded in database
- [ ] Events emitted on state changes
- [ ] Can pause executing workflow
- [ ] Can resume paused workflow
- [ ] `python tests/test_one_shot.py` passes

### Should Pass
- [ ] All state transitions logged
- [ ] Can query state history
- [ ] Can get allowed next states
- [ ] Event listeners work correctly
- [ ] Terminal states cannot transition
- [ ] Workflow and step states synchronized

### State Machine Testing
```python
# Test valid transition
def test_valid_transition():
    sm = StateMachine(db_session, "workflow_run")
    run = create_test_run(status="draft")
    sm.transition_to(run.id, "planning", reason="Test")
    assert run.status == "planning"

# Test invalid transition
def test_invalid_transition():
    sm = StateMachine(db_session, "workflow_run")
    run = create_test_run(status="completed")
    with pytest.raises(StateMachineError):
        sm.transition_to(run.id, "planning")

# Test guard
def test_transition_guard():
    sm = StateMachine(db_session, "workflow_run")
    run = create_test_run(status="draft", task_description=None)
    with pytest.raises(StateMachineError):
        sm.transition_to(run.id, "planning")  # Guard fails

# Test pause/resume
def test_pause_resume():
    controller = WorkflowController(db_session, session_id)
    run = create_test_run(status="executing")
    controller.pause_workflow(run.id)
    assert run.status == "paused"
    controller.resume_workflow(run.id)
    assert run.status == "executing"
```

## Testing Checklist

### Unit Tests
```python
# Test state enumerations
def test_workflow_states():
    assert WorkflowState.DRAFT == "draft"
    assert WorkflowState.EXECUTING == "executing"

# Test transition validation
def test_transition_validation():
    sm = StateMachine(db_session, "workflow_run")
    assert sm.can_transition_to(run_id, "planning") == True
    assert sm.can_transition_to(run_id, "completed") == False

# Test state history
def test_state_history_recording():
    sm = StateMachine(db_session, "workflow_run")
    sm.transition_to(run_id, "planning")
    history = sm.get_state_history(run_id)
    assert len(history) == 1
    assert history[0].to_state == "planning"

# Test event emission
def test_event_emission():
    events_received = []
    emitter = EventEmitter()
    emitter.on("state_changed", lambda **kwargs: events_received.append(kwargs))

    sm = StateMachine(db_session, "workflow_run", emitter)
    sm.transition_to(run_id, "planning")

    assert len(events_received) == 1
    assert events_received[0]["to_state"] == "planning"
```

### Integration Tests
```python
# Test workflow with state machine
def test_workflow_state_transitions():
    agent = CMBAgent(session_id="test")
    result = agent.planning_and_control("Test task")

    # Verify state progression
    run = agent.repo.get_run(result.run_id)
    assert run.status in ["completed", "failed"]

    # Verify state history
    history = agent.workflow_sm.get_state_history(run.id)
    states = [h.to_state for h in history]
    assert "planning" in states
    assert "executing" in states

# Test pause/resume integration
def test_pause_resume_workflow():
    agent = CMBAgent(session_id="test")
    # Start workflow in background
    run_id = agent.start_workflow_async("Long task")

    # Pause
    agent.pause_workflow(run_id)
    run = agent.repo.get_run(run_id)
    assert run.status == "paused"

    # Resume
    agent.resume_workflow(run_id)
    run = agent.repo.get_run(run_id)
    assert run.status == "executing"
```

## Common Issues and Solutions

### Issue 1: Transition Validation Too Strict
**Symptom:** Valid workflows blocked by state machine
**Solution:** Review transition rules, ensure all valid paths covered

### Issue 2: State History Growing Too Large
**Symptom:** Database bloat from state history
**Solution:** Add archival process for old state history, keep only recent

### Issue 3: Event Listener Errors Breaking Workflow
**Symptom:** Workflow fails when event listener crashes
**Solution:** Event emitter catches exceptions, logs but doesn't propagate

### Issue 4: Pause/Resume Race Conditions
**Symptom:** Workflow resumes before fully paused
**Solution:** Use database transactions, ensure atomic state changes

### Issue 5: Guards Not Properly Checked
**Symptom:** Invalid transitions allowed
**Solution:** Ensure guards return boolean, test all guard functions

## Rollback Procedure

If state machine causes issues:

1. **Feature flag to disable:**
   ```python
   USE_STATE_MACHINE = os.getenv("CMBAGENT_USE_STATE_MACHINE", "true") == "true"
   ```

2. **Revert to simple status updates:**
   ```python
   # Instead of state machine
   run.status = "executing"
   db_session.commit()
   ```

3. **Keep state history table** - Useful for debugging

4. **Document blocking issues** for future fix

## Post-Stage Actions

### Documentation
- Document state machine architecture
- Add state diagram to ARCHITECTURE.md
- Create state transition reference guide
- Document pause/resume API

### Update Progress
- Mark Stage 3 complete in PROGRESS.md
- Note any deviations from plan
- Document time spent
- Update state machine lessons learned

### Prepare for Stage 4
- State machine operational
- Valid transitions enforced
- Ready to build DAG executor on top
- Stage 4 can proceed

## Success Criteria

Stage 3 is complete when:
1. State machine validates all transitions
2. State history tracked in database
3. Events emitted on state changes
4. Pause/resume functionality working
5. Existing workflows use state machine
6. All state transitions logged
7. Verification checklist 100% complete

## Estimated Time Breakdown

- State definitions: 5 min
- Transition rules: 5 min
- State history table: 3 min
- State machine implementation: 10 min
- Event emission: 3 min
- CMBAgent integration: 5 min
- Pause/resume: 5 min
- Testing and verification: 7 min
- Documentation: 2 min

**Total: 25-35 minutes**

## Next Stage

Once Stage 3 is verified complete, proceed to:
**Stage 4: DAG Builder and Storage**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
