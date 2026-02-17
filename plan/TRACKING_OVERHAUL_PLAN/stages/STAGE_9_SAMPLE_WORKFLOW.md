# Stage 9: Extensibility Validation - Sample Complex Workflow

## Objectives
1. Prove the new system supports adding complex workflows with minimal code
2. Create a sample "deep-research" workflow with dynamic planning and multiple control stages
3. Show that ZERO tracking code is needed in the new workflow
4. Document the exact steps and files needed to add a new workflow

---

## What Adding a New Workflow Requires (Target State)

After all prior stages, adding a new workflow should require ONLY these steps:

1. **Create phase class(es)** in `cmbagent/phases/` (using PhaseExecutionManager)
2. **Create workflow orchestration** in `cmbagent/workflows/` (wiring phases together)
3. **Add DAG template mapping** (one line in `MODE_TO_TEMPLATE`)
4. **Add mode routing** in `backend/execution/task_executor.py` (call the workflow)

**Zero changes needed in**:
- StreamCapture (relay only)
- EventCaptureManager (session-scoped via contextvars)
- Cost tracking (reads JSON automatically)
- File tracking (scans work_dir automatically)
- DAG state management (callbacks drive DAGTracker)

---

## Sample: "deep-research" Workflow

A complex workflow with:
- **Phase 1**: Literature review (researcher agent)
- **Phase 2**: Planning (planner agent, generates dynamic sub-tasks)
- **Phase 3**: Multi-step execution (engineer agent, dynamic steps from plan)
- **Phase 4**: Synthesis (researcher agent, combines step outputs)

### Step 1: Create Phase Classes

**File**: `cmbagent/phases/literature_review.py`
```python
from cmbagent.phases.base import Phase, PhaseResult
from cmbagent.phases.execution_manager import PhaseExecutionManager


class LiteratureReviewPhase(Phase):
    """Research phase that reviews existing literature before planning."""
    phase_type = "literature_review"
    display_name = "Literature Review"

    def execute(self, context):
        manager = PhaseExecutionManager(context, self)
        manager.start()

        try:
            manager.start_step(1, "Review existing literature", agent="researcher")
            # ... run researcher agent with RAG ...
            review_result = self._run_researcher(context)
            manager.complete_step(1, output=review_result)

            # Add findings to context for downstream phases
            context.shared_state["literature_findings"] = review_result

            return manager.complete(output=review_result)
        except Exception as e:
            return manager.fail(error=e)

    def _run_researcher(self, context):
        """Run researcher agent for literature review."""
        # Standard CMBAgent pattern - create researcher, run conversation
        # ... implementation ...
        return {"papers": [], "key_findings": [], "summary": ""}
```

**File**: `cmbagent/phases/synthesis.py`
```python
from cmbagent.phases.base import Phase
from cmbagent.phases.execution_manager import PhaseExecutionManager


class SynthesisPhase(Phase):
    """Combine outputs from all steps into final result."""
    phase_type = "synthesis"
    display_name = "Result Synthesis"

    def execute(self, context):
        manager = PhaseExecutionManager(context, self)
        manager.start()

        try:
            manager.start_step(1, "Synthesize results", agent="researcher")
            # ... combine all step outputs ...
            synthesis = self._synthesize(context)
            manager.complete_step(1, output=synthesis)

            return manager.complete(output=synthesis)
        except Exception as e:
            return manager.fail(error=e)

    def _synthesize(self, context):
        # Gather outputs from previous phases
        step_outputs = context.shared_state.get("step_outputs", [])
        literature = context.shared_state.get("literature_findings", {})
        # ... create synthesis ...
        return {"synthesis": "", "conclusions": []}
```

### Step 2: Create Workflow Orchestration

**File**: `cmbagent/workflows/deep_research.py`
```python
"""
Deep research workflow: Literature Review → Planning → Multi-step Control → Synthesis

Callbacks drive all tracking automatically:
- Phase start/complete → DAGTracker updates nodes
- Step start/complete → DAGTracker updates nodes
- Cost → CostCollector reads JSON files
- Files → DAGTracker scans work_dir
- Events → EventCaptureManager via AG2 hooks
"""
from cmbagent.workflows.composer import WorkflowExecutor
from cmbagent.phases.literature_review import LiteratureReviewPhase
from cmbagent.phases.planning import PlanningPhase
from cmbagent.phases.control import ControlPhase
from cmbagent.phases.synthesis import SynthesisPhase


def deep_research_workflow(
    task,
    max_rounds_control=25,
    max_plan_steps=10,
    researcher_model="gpt-4.1-2025-04-14",
    engineer_model="gpt-4o",
    planner_model="gpt-4.1-2025-04-14",
    work_dir=None,
    api_keys=None,
    callbacks=None,
    **kwargs
):
    """Execute deep research workflow.

    This is ~50 lines of orchestration.
    ZERO tracking code needed - callbacks handle everything.
    """

    # Define phase pipeline
    phases = [
        LiteratureReviewPhase(
            researcher_model=researcher_model,
            api_keys=api_keys,
        ),
        PlanningPhase(
            planner_model=planner_model,
            max_plan_steps=max_plan_steps,
            api_keys=api_keys,
        ),
        ControlPhase(
            engineer_model=engineer_model,
            max_rounds=max_rounds_control,
            api_keys=api_keys,
        ),
        SynthesisPhase(
            researcher_model=researcher_model,
            api_keys=api_keys,
        ),
    ]

    # Execute pipeline - WorkflowExecutor handles:
    # - Creating PhaseContext with callbacks
    # - Running phases in sequence
    # - Context carryover between phases
    # - Error handling and retry
    executor = WorkflowExecutor(
        phases=phases,
        task=task,
        work_dir=work_dir,
        callbacks=callbacks,
    )

    return executor.run()
```

### Step 3: Add DAG Template Mapping (ONE LINE)

**File**: `backend/execution/dag_tracker.py`

```python
MODE_TO_TEMPLATE = {
    # ... existing modes ...

    # NEW: one line
    "deep-research": ("plan-execute", {
        "planning": {"label": "Literature Review + Planning",
                     "description": "Review literature and create research plan"},
    }),
}
```

That's it. The `plan-execute` template starts with a planning node, then dynamically adds step nodes when planning completes (via `add_step_nodes()` callback). The synthesis step is added as the final dynamic step.

### Step 4: Add Mode Routing (ONE elif BLOCK)

**File**: `backend/execution/task_executor.py`

```python
elif mode == "deep-research":
    from cmbagent.workflows.deep_research import deep_research_workflow
    results = deep_research_workflow(
        task=task,
        max_rounds_control=max_rounds,
        max_plan_steps=max_plan_steps,
        researcher_model=researcher_model,
        engineer_model=engineer_model,
        planner_model=planner_model,
        work_dir=task_work_dir,
        api_keys=api_keys,
        callbacks=workflow_callbacks,  # Callbacks drive ALL tracking
    )
```

### What Happens Automatically (Zero Code Needed)

| Concern | What Happens | Driven By |
|---------|-------------|-----------|
| **DAG** | Planning node created → steps added dynamically → all tracked | Template + `add_step_nodes()` callback |
| **Cost** | `display_cost()` writes JSON → CostCollector reads → DB + WS | Library JSON + CostCollector |
| **Events** | AG2 hooks capture all LLM calls, tool calls, handoffs | EventCaptureManager via contextvars |
| **Files** | Scanned after each step completion | DAGTracker.track_files_in_work_dir() |
| **WS Events** | Step transitions, agent messages, cost updates | Callbacks → task_executor bridge |
| **Session** | State saved on phase changes | Session manager callbacks |
| **Pause/Cancel** | Checked via `should_continue()` | Pause callbacks |

---

## Test: Verify Extensibility

**File**: `tests/test_extensibility.py`

```python
"""Test that adding a new workflow requires zero tracking code."""
import pytest
from unittest.mock import MagicMock, patch
from backend.execution.dag_tracker import MODE_TO_TEMPLATE, DAG_TEMPLATES, DAGTracker
from cmbagent.callbacks import WorkflowCallbacks, merge_callbacks


class TestNewWorkflowAddition:
    """Verify the new system supports adding workflows with minimal effort."""

    def test_template_mapping_is_one_line(self):
        """Adding a mode only requires one dict entry."""
        # Before: mode not supported
        assert "test-workflow" not in MODE_TO_TEMPLATE

        # Add: one line
        MODE_TO_TEMPLATE["test-workflow"] = ("plan-execute", {
            "planning": {"label": "Test Planning"}
        })

        # After: mode supported
        assert "test-workflow" in MODE_TO_TEMPLATE

        # Cleanup
        del MODE_TO_TEMPLATE["test-workflow"]

    def test_dag_created_from_template(self):
        """DAG is created correctly from template without custom method."""
        MODE_TO_TEMPLATE["test-workflow"] = ("plan-execute", {
            "planning": {"label": "Test Planning"}
        })

        tracker = DAGTracker(
            websocket=None, task_id="test", mode="test-workflow",
            send_event_func=lambda *a, **k: None
        )
        dag = tracker.create_dag_for_mode("test task", {"agent": "engineer"})

        assert len(dag["nodes"]) == 1
        assert dag["nodes"][0]["id"] == "planning"
        assert dag["nodes"][0]["label"] == "Test Planning"
        assert "planning" in tracker.node_statuses

        del MODE_TO_TEMPLATE["test-workflow"]

    def test_dynamic_steps_added_via_callback(self):
        """Steps are dynamically added when planning completes."""
        MODE_TO_TEMPLATE["test-workflow"] = ("plan-execute", {})

        tracker = DAGTracker(
            websocket=None, task_id="test", mode="test-workflow",
            send_event_func=MagicMock()
        )
        tracker.create_dag_for_mode("test task", {})

        # Simulate planning complete callback adding steps
        import asyncio
        steps = [
            {"title": "Step 1: Research", "description": "Do research", "agent": "researcher"},
            {"title": "Step 2: Implement", "description": "Write code", "agent": "engineer"},
            {"title": "Step 3: Validate", "description": "Run tests", "agent": "engineer"},
        ]
        asyncio.run(tracker.add_step_nodes(steps))

        # Verify steps were added
        assert len(tracker.nodes) == 5  # planning + 3 steps + terminator
        assert "step_1" in tracker.node_statuses
        assert "step_2" in tracker.node_statuses
        assert "step_3" in tracker.node_statuses
        assert "terminator" in tracker.node_statuses

        del MODE_TO_TEMPLATE["test-workflow"]

    def test_fixed_pipeline_no_dynamic_steps(self):
        """Fixed pipeline modes don't need add_step_nodes."""
        tracker = DAGTracker(
            websocket=None, task_id="test", mode="one-shot",
            send_event_func=lambda *a, **k: None
        )
        dag = tracker.create_dag_for_mode("test task", {"agent": "engineer"})

        # Should have all nodes from template
        node_ids = [n["id"] for n in dag["nodes"]]
        assert "init" in node_ids
        assert "execute" in node_ids
        assert "terminator" in node_ids

    def test_callbacks_dont_need_workflow_awareness(self):
        """Callbacks work generically - no workflow-specific code needed."""
        events = []

        callbacks = WorkflowCallbacks(
            on_phase_change=lambda phase, step: events.append(("phase", phase, step)),
            on_step_start=lambda si: events.append(("step_start", si.step_number)),
            on_step_complete=lambda si: events.append(("step_complete", si.step_number)),
        )

        # Simulate a custom workflow using generic callbacks
        callbacks.invoke_phase_change("planning", None)
        from cmbagent.callbacks import StepInfo, StepStatus
        callbacks.invoke_step_start(StepInfo(step_number=1, status=StepStatus.RUNNING))
        callbacks.invoke_step_complete(StepInfo(step_number=1, status=StepStatus.COMPLETED))

        assert len(events) == 3
        assert events[0] == ("phase", "planning", None)
        assert events[1] == ("step_start", 1)
        assert events[2] == ("step_complete", 1)

    def test_complex_workflow_with_4_phases(self):
        """Test that a 4-phase workflow works end-to-end with tracking."""
        events = []

        callbacks = WorkflowCallbacks(
            on_phase_change=lambda p, s: events.append(("phase", p)),
            on_step_start=lambda si: events.append(("step_start", si.step_number)),
            on_step_complete=lambda si: events.append(("step_complete", si.step_number)),
            on_planning_complete=lambda pi: events.append(("planning_done",)),
        )

        # Simulate deep-research workflow lifecycle
        # Phase 1: Literature review
        callbacks.invoke_phase_change("literature_review", None)
        from cmbagent.callbacks import StepInfo, StepStatus, PlanInfo
        callbacks.invoke_step_start(StepInfo(step_number=1, status=StepStatus.RUNNING))
        callbacks.invoke_step_complete(StepInfo(step_number=1, status=StepStatus.COMPLETED))

        # Phase 2: Planning
        callbacks.invoke_phase_change("planning", None)
        plan = PlanInfo(steps=[
            {"title": "Step 1", "description": "Research", "agent": "researcher"},
            {"title": "Step 2", "description": "Implement", "agent": "engineer"},
        ])
        callbacks.invoke_planning_complete(plan)

        # Phase 3: Control (dynamic steps)
        callbacks.invoke_phase_change("control", 1)
        callbacks.invoke_step_start(StepInfo(step_number=1, status=StepStatus.RUNNING))
        callbacks.invoke_step_complete(StepInfo(step_number=1, status=StepStatus.COMPLETED))
        callbacks.invoke_step_start(StepInfo(step_number=2, status=StepStatus.RUNNING))
        callbacks.invoke_step_complete(StepInfo(step_number=2, status=StepStatus.COMPLETED))

        # Phase 4: Synthesis
        callbacks.invoke_phase_change("synthesis", None)
        callbacks.invoke_step_start(StepInfo(step_number=1, status=StepStatus.RUNNING))
        callbacks.invoke_step_complete(StepInfo(step_number=1, status=StepStatus.COMPLETED))

        # Verify complete lifecycle was tracked
        phase_events = [e for e in events if e[0] == "phase"]
        assert len(phase_events) == 4
        assert phase_events[0] == ("phase", "literature_review")
        assert phase_events[1] == ("phase", "planning")
        assert phase_events[2] == ("phase", "control")
        assert phase_events[3] == ("phase", "synthesis")
```

---

## Summary: What It Takes to Add a New Workflow

| Step | Where | Lines of Code | Example |
|------|-------|--------------|---------|
| 1. Phase class(es) | `cmbagent/phases/` | ~30-50 per phase | Standard pattern with PhaseExecutionManager |
| 2. Workflow function | `cmbagent/workflows/` | ~50 | Wire phases with WorkflowExecutor |
| 3. DAG template | `backend/execution/dag_tracker.py` | 1-3 | `MODE_TO_TEMPLATE["x"] = ("plan-execute", {...})` |
| 4. Mode routing | `backend/execution/task_executor.py` | ~10 | `elif mode == "x": results = ...` |
| **Total** | | **~100-160** | **Zero tracking code** |

## Files Created
| File | Action |
|------|--------|
| `cmbagent/phases/literature_review.py` | SAMPLE phase |
| `cmbagent/phases/synthesis.py` | SAMPLE phase |
| `cmbagent/workflows/deep_research.py` | SAMPLE workflow |
| `tests/test_extensibility.py` | Extensibility validation tests |
