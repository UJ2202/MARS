# Phase-Based Workflows - Default Implementation

## Overview

CMBAgent now uses **phase-based workflows exclusively** as the default and only implementation. The legacy workflow system has been deprecated and is kept only for reference in `backend/main_legacy.py`.

## Architecture

All workflows now use the phase-based execution system which provides:
- Structured phase/step tracking
- Enhanced callback system
- Better logging and debugging
- DAG creation and visualization
- File tracking across phases
- Checkpoint support for pause/resume/cancel

## Implementation

### Workflow Module

The main entry point is [cmbagent/workflows/__init__.py](../cmbagent/workflows/__init__.py), which exports:

**Function API** (all use phase-based implementation):
- `planning_and_control_context_carryover` - Full workflow with context carryover
- `planning_and_control` - Simpler workflow
- `one_shot` - Single-shot task execution
- `control` - Control workflow from existing plan
- `idea_generation` - Idea generation workflow
- `idea_to_execution` - Full idea to execution workflow
- `human_in_the_loop` - Interactive workflow

**WorkflowExecutor API**:
- `WorkflowExecutor` - Execute workflows from definitions
- `WorkflowDefinition` - Define custom workflows
- `SYSTEM_WORKFLOWS` - Pre-defined workflow templates

### Backend Integration

[backend/execution/task_executor.py](../backend/execution/task_executor.py) always uses phase-based workflows:

```python
# Always using phase-based workflow
print(f"[TaskExecutor] Using phase-based workflow for {mode}")

results = cmbagent.planning_and_control_context_carryover(
    task=task,
    # ... parameters
)
```

## Legacy Code

The legacy implementation in `backend/main_legacy.py` is marked as reference only:

```python
"""
LEGACY FILE - REFERENCE ONLY
================================
This file contains the old legacy implementation and is kept for reference only.
The system now exclusively uses phase-based workflows.

DO NOT IMPORT OR USE THIS FILE IN PRODUCTION CODE.
"""
```

Legacy function-based workflows in:
- `cmbagent/workflows/planning_control.py`
- `cmbagent/workflows/one_shot.py`
- `cmbagent/workflows/control.py`

These are also kept for reference only and should not be imported or used in new code.

## Migration Complete

The migration from legacy to phase-based workflows is complete:
- ✅ All workflows use phase-based implementation
- ✅ UI no longer has phase toggle (removed experimental feature)
- ✅ Backend always uses phase-based execution
- ✅ Environment variable `CMBAGENT_USE_PHASES` is no longer needed
- ✅ Config option `usePhases` removed from UI
- ✅ Legacy files marked as reference only

## Benefits

The phase-based system provides:

1. **Better Structure**:
   - Clear phase boundaries
   - Defined phase transitions
   - Reusable phase components

2. **Enhanced Logging**:
   - Phase-level events
   - Step-level tracking
   - Agent message logging
   - Code execution logging

3. **Database Integration**:
   - DAG creation and tracking
   - File tracking per phase
   - Checkpoint support
   - Event history

4. **Developer Experience**:
   - Centralized PhaseExecutionManager
   - Easier to add new phases
   - Better error handling
   - Consistent callbacks across workflows

## What Was Changed

### Frontend Changes

1. **Config State Update** ([TaskInput.tsx](../cmbagent-ui/components/TaskInput.tsx)):
   - Added `usePhases: false` to the config state object
   - This boolean flag controls whether phase-based workflows are enabled

2. **UI Toggle Added**:
   - Added a checkbox in the Advanced Settings section
   - Visible only for `planning-control` and `idea-generation` modes
   - Located after the "Plan Reviews" option
   - Includes tooltip: "Use the new phase-based execution system for improved callbacks, logging, and DAG tracking (experimental)"
   - Marked with 🧪 to indicate experimental status

### Backend Changes

1. **Planning-Control Mode** ([task_executor.py](../backend/execution/task_executor.py)):
   - Reads `usePhases` from config
   - Falls back to `CMBAGENT_USE_PHASES` environment variable if not set
   - Sets environment variable when enabled: `os.environ["CMBAGENT_USE_PHASES"] = "1"`

2. **Idea-Generation Mode**:
   - Added same `usePhases` logic for consistency
   - Ensures both modes can use phase-based workflows

## How to Use

### Via UI Toggle (Recommended)

1. Open the CMBAgent web interface
2. Select either **Planning & Control** or **Idea Generation** mode
3. Click the **Settings** button to open Advanced Settings
4. Check the box **"Use Phase-Based Workflow (Experimental)"** 🧪
5. Submit your task as normal

The task will now run using the phase-based implementation with:
- Enhanced callback system
- Improved logging and stdio output
- DAG creation and tracking
- File tracking across phases
- Checkpoint support for pause/resume

### Via Environment Variable (Alternative)

You can also enable phases globally by setting:
```bash
export CMBAGENT_USE_PHASES=1
```

The UI toggle will override this setting. If the toggle is unchecked, phases will be disabled even if the environment variable is set to "1".

## Implementation Details

### Configuration Flow

```
User checks toggle in UI
    ↓
Frontend sends config with usePhases: true
    ↓
Backend reads config.get("usePhases")
    ↓
Backend sets os.environ["CMBAGENT_USE_PHASES"] = "1"
    ↓
planning_and_control_context_carryover checks should_use_phases()
    ↓
Delegates to planning_and_control_context_carryover_phases()
    ↓
Uses PhaseExecutionManager for execution
```

### Code Locations

- **UI Toggle**: [cmbagent-ui/components/TaskInput.tsx](../cmbagent-ui/components/TaskInput.tsx) (lines ~925-940)
- **Config State**: [cmbagent-ui/components/TaskInput.tsx](../cmbagent-ui/components/TaskInput.tsx) (line ~78)
- **Backend Planning-Control**: [backend/execution/task_executor.py](../backend/execution/task_executor.py) (lines ~430-435)
- **Backend Idea-Generation**: [backend/execution/task_executor.py](../backend/execution/task_executor.py) (lines ~458-462)
- **Phase Selection Logic**: [cmbagent/workflows/__init__.py](../cmbagent/workflows/__init__.py) (lines ~96-99)
- **Environment Check**: [cmbagent/workflows/phase_wrappers.py](../cmbagent/workflows/phase_wrappers.py) (line ~733)

## Benefits of Phase-Based Workflows

When enabled, you get:

1. **Better Logging**:
   - Structured phase/step tracking
   - Clear start/complete events
   - Agent message logging
   - Code execution logging

2. **Enhanced Callbacks**:
   - `planning_start` and `planning_complete`
   - `control_start` and `control_complete`
   - `step_start` and `step_complete`
   - Consistent across all workflows

3. **Database Integration**:
   - DAG creation and tracking (same as legacy)
   - File tracking per phase
   - Checkpoint support

4. **Developer Experience**:
   - Centralized PhaseExecutionManager
   - Easier to add new phases
   - Better error handling
   - Pause/resume/cancel support

## Testing

To verify the integration works:

1. **Test with Toggle OFF** (legacy mode):
   ```
   Submit a task with the toggle unchecked
   → Should use legacy implementation
   → Check logs for standard output format
   ```

2. **Test with Toggle ON** (phase mode):
   ```
   Submit a task with the toggle checked
   → Should use phase-based implementation
   → Check logs for "[TaskExecutor] Using PHASE-BASED workflow"
   → Verify structured phase callbacks appear
   ```

3. **Compare Outputs**:
   - Both modes should produce similar results
   - Phase mode should have better structured logging
   - DAG creation should work in both modes

## Known Limitations

- Currently only available for `planning-control` and `idea-generation` modes
- Other modes (`one-shot`, `ocr`, `arxiv`, `enhance-input`) use legacy implementations
- Phase-based workflows are experimental and may have edge cases

## Future Improvements

- Add phase support for `one-shot` mode
- Add phase support for other specialized modes
- Remove "experimental" tag once stable
- Add metrics and monitoring for phase execution

## Related Documentation

- [Phase Development Guide](./PHASE_DEVELOPMENT_GUIDE.md) - How to create new phases
- [Phase Architecture](./PHASE_ARCHITECTURE.md) - Overall system design
- [Phase Implementation](./PHASE_IMPLEMENTATION.md) - Technical details
