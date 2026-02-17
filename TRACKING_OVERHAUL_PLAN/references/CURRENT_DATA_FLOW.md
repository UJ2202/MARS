# Current Data Flow Reference

## The Working HITL Flow (Reference Implementation)

This documents THE working flow that all other modes should model after.

### Execution Path

```
1. User submits task via WebSocket
   → backend/websocket/handlers.py:handle_run()
   → backend/execution/task_executor.py:execute_cmbagent_task()

2. task_executor creates infrastructure:
   → DAGTracker(mode="hitl-interactive")
   → dag_tracker.create_dag_for_mode(task, config)
   → Emits WS "dag_created" with initial nodes

3. task_executor creates callbacks:
   → create_websocket_callbacks(ws_send_event, task_id)  # WS events
   → event_tracking_callbacks (on_planning_complete, on_step_start/complete/fail)
   → pause_callbacks (should_continue, on_pause_check)
   → merge_callbacks(ws_callbacks, print_callbacks, pause_callbacks, event_tracking_callbacks)

4. task_executor launches ThreadPoolExecutor:
   → sys.stdout = StreamWrapper(stream_capture)
   → AG2 IOStream set to AG2IOStreamCapture
   → Calls hitl_workflow.hitl_interactive_workflow()

5. HITL workflow (cmbagent/phases/hitl_planning.py):
   → PhaseExecutionManager.start()
      → Invokes callbacks.on_phase_change("planning", None)
   → Agent generates plan
   → CMBAgent.display_cost() writes cost/*.json
   → Invokes callbacks.on_planning_complete(plan_info)
      → task_executor: dag_tracker.add_step_nodes(steps)
      → task_executor: dag_tracker.update_node_status("planning", "completed")
   → WebSocketApprovalManager.request_approval()
      → WS "approval_needed" to frontend
      → Waits for human response
   → PhaseExecutionManager.complete()

6. HITL workflow (cmbagent/phases/hitl_control.py):
   → For each step:
      → Invokes callbacks.on_step_start(step_info)
         → task_executor: dag_tracker.update_node_status("step_N", "running")
      → Agent executes step
      → Optional: WebSocketApprovalManager.request_approval()
      → Invokes callbacks.on_step_complete(step_info)
         → task_executor: dag_tracker.update_node_status("step_N", "completed")
         → task_executor: dag_tracker.track_files_in_work_dir()

7. Completion:
   → CMBAgent.display_cost() writes final cost/*.json
   → task_executor: dag_tracker marks all nodes completed
   → WS "result" + "complete" events emitted
```

### Why HITL Works and Others Don't

1. **Single DAG ownership**: DAGTracker is the ONLY thing creating/updating nodes
2. **Callback-driven**: All state changes go through callbacks → task_executor → DAGTracker
3. **StreamCapture skips auto-complete**: Lines 490-493 intentionally skip for HITL
4. **No PhaseExecutionManager DAG creation**: HITL workflow doesn't use PhaseExecutionManager's DAG features

### What Non-HITL Modes Do Wrong

| Mode | Problem | Root Cause |
|------|---------|------------|
| planning-control | Duplicate WS events, conflicting node IDs | StreamCapture auto-detects AND callbacks fire |
| one-shot | Missing step transitions | No callbacks wired, relies on StreamCapture regex |
| idea-generation | Idea maker/hater nodes not updating | Hardcoded regex in StreamCapture |
| OCR | Fixed pipeline nodes never update | No callback support in OCR workflow |
