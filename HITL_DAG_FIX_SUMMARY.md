# HITL Workflow DAG Fix Summary

## Problem
The HITL (Human-in-the-Loop) workflow DAG was stuck showing only two default nodes (planning and human_review_plan) and not adding the actual execution step nodes after planning completed.

## Root Cause
The issue was that the mode "hitl-interactive" was not included in the mode checks that determine when to add step nodes to the DAG. The code was only checking for "planning-control" and "idea-generation" modes.

## Files Changed

### 1. `backend/execution/stream_capture.py`
**Changes:**
- Line 519: Added "step 1 approval required", "hitl planning", "human review" to detection patterns
- Line 532: Added "hitl-interactive" to mode check for adding step nodes from plan buffer
- Line 535: Added "hitl-interactive" to mode check for adding default steps

**Reason:** Stream capture is responsible for detecting when planning completes and adding step nodes. Without HITL mode in the checks, step nodes were never added for HITL workflows.

### 2. `backend/execution/task_executor.py`
**Changes:**
- Line 113: Added "hitl-interactive" to the initial phase setting

**Reason:** HITL workflows need to start in the "planning" phase (not "execution" phase) so that the DAG tracker properly handles the planning→execution transition.

### 3. `backend/main_legacy.py`
**Changes:**
- Line 780: Added "hitl-interactive" to mode check for adding step nodes from plan buffer
- Line 783: Added "hitl-interactive" to mode check for adding default steps

**Reason:** For consistency with stream_capture.py, ensuring the same logic applies in the legacy code path.

## How It Works Now

1. **Initialization (task_executor.py)**
   - HITL workflows now correctly start in "planning" phase
   - DAG is initialized with planning and human_review_plan nodes

2. **Plan Detection (stream_capture.py)**
   - When final_plan.json is written, the code reads it and extracts steps
   - OR when output patterns like "executing step 1" or "step 1 approval required" are detected
   - The code now recognizes "hitl-interactive" mode and adds step nodes

3. **Step Node Addition (dag_tracker.py)**
   - The `add_step_nodes` method creates step_1, step_2, ... nodes
   - For HITL mode, steps are connected from "human_review_plan" → "step_1" → "step_2" → ... → "terminator"
   - For regular planning-control mode, steps connect from "planning" → "step_1" → ...

4. **Execution**
   - As steps execute, the DAG tracker updates each node's status
   - The UI shows the complete workflow graph with all steps visible

## Testing
To verify the fix works:
1. Start a HITL interactive workflow
2. Complete the planning phase
3. Verify that the DAG shows all step nodes (not just planning and human_review_plan)
4. Verify that step nodes transition through pending → running → completed states

## Related Code
- `backend/execution/dag_tracker.py`: `_create_hitl_dag()` - Creates initial HITL DAG structure
- `backend/execution/dag_tracker.py`: `add_step_nodes()` - Adds step nodes dynamically after planning
- `cmbagent/phases/hitl_control.py`: HITL control phase implementation
- `cmbagent/phases/hitl_planning.py`: HITL planning phase implementation

## Comparison with Planning-Control Workflow
The planning-control workflow (which was working correctly) follows the same pattern:
1. Creates "planning" node initially
2. Detects plan completion
3. Adds step nodes dynamically
4. Connects: planning → step_1 → step_2 → ... → terminator

The HITL workflow now follows the same pattern, with an extra approval node:
1. Creates "planning" and "human_review_plan" nodes initially
2. Detects plan completion and approval
3. Adds step nodes dynamically
4. Connects: planning → human_review_plan → step_1 → step_2 → ... → terminator
