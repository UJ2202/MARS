# WebSocket Events Reference

This document lists all WebSocket events emitted by the backend and expected by the UI.

## Event Structure

All events follow this structure:

```typescript
interface WebSocketEvent {
  event_type: string;
  timestamp: string;        // ISO 8601 format
  run_id?: string;          // Workflow run ID
  session_id?: string;      // Session ID
  data: Record<string, any>;// Event-specific payload
}
```

## Connection Events

### `connected`
Sent when WebSocket connection established.
```json
{
  "event_type": "connected",
  "data": { "message": "Connected to workflow" }
}
```

### `disconnected`
Sent when connection closes (not always received).

### `reconnected`
Sent when client reconnects after disconnect.

### `heartbeat` / `pong`
Keepalive messages. UI should send `ping`, backend responds with `pong`.

## Workflow Lifecycle Events

### `workflow_started`
```json
{
  "event_type": "workflow_started",
  "run_id": "uuid",
  "data": {
    "run_id": "uuid",
    "task_description": "string",
    "agent": "engineer",
    "model": "gpt-4o",
    "work_dir": "/path/to/work"
  }
}
```

### `workflow_state_changed`
```json
{
  "event_type": "workflow_state_changed",
  "run_id": "uuid",
  "data": {
    "status": "executing",
    "started_at": "2026-01-16T10:00:00Z",
    "completed_at": null
  }
}
```

### `workflow_paused`
```json
{
  "event_type": "workflow_paused",
  "run_id": "uuid",
  "data": { "reason": "User requested" }
}
```

### `workflow_resumed`
```json
{
  "event_type": "workflow_resumed",
  "run_id": "uuid",
  "data": {}
}
```

### `workflow_completed`
```json
{
  "event_type": "workflow_completed",
  "run_id": "uuid",
  "data": {
    "final_result": "...",
    "total_cost": 0.0245,
    "total_duration_seconds": 125.5
  }
}
```

### `workflow_failed`
```json
{
  "event_type": "workflow_failed",
  "run_id": "uuid",
  "data": {
    "error": "Error message",
    "traceback": "..."
  }
}
```

## Step Execution Events

### `step_started`
```json
{
  "event_type": "step_started",
  "run_id": "uuid",
  "data": {
    "step_id": "uuid",
    "step_number": 1,
    "step_description": "Analyze requirements",
    "agent": "engineer"
  }
}
```

### `step_progress`
```json
{
  "event_type": "step_progress",
  "run_id": "uuid",
  "data": {
    "step_id": "uuid",
    "step_number": 1,
    "progress_percentage": 50,
    "message": "Processing..."
  }
}
```

### `step_completed`
```json
{
  "event_type": "step_completed",
  "run_id": "uuid",
  "data": {
    "step_id": "uuid",
    "step_number": 1,
    "result": "...",
    "output": "..."
  }
}
```

### `step_failed`
```json
{
  "event_type": "step_failed",
  "run_id": "uuid",
  "data": {
    "step_id": "uuid",
    "step_number": 1,
    "error": "Error message",
    "traceback": "..."
  }
}
```

## Retry Events

### `step_retry_started`
```json
{
  "event_type": "step_retry_started",
  "run_id": "uuid",
  "data": {
    "step_id": "uuid",
    "step_number": 1,
    "attempt_number": 2,
    "max_attempts": 3,
    "error_category": "NETWORK",
    "error_pattern": "ConnectionError",
    "success_probability": 0.75,
    "strategy": "exponential_backoff",
    "suggestions": ["Check network", "Retry later"],
    "has_user_feedback": false
  }
}
```

### `step_retry_backoff`
```json
{
  "event_type": "step_retry_backoff",
  "run_id": "uuid",
  "data": {
    "step_id": "uuid",
    "backoff_seconds": 5,
    "next_attempt_at": "2026-01-16T10:00:05Z"
  }
}
```

### `step_retry_succeeded`
```json
{
  "event_type": "step_retry_succeeded",
  "run_id": "uuid",
  "data": {
    "step_id": "uuid",
    "attempt_number": 2
  }
}
```

### `step_retry_exhausted`
```json
{
  "event_type": "step_retry_exhausted",
  "run_id": "uuid",
  "data": {
    "step_id": "uuid",
    "total_attempts": 3,
    "final_error": "..."
  }
}
```

## DAG Events

### `dag_created`
```json
{
  "event_type": "dag_created",
  "run_id": "uuid",
  "data": {
    "run_id": "uuid",
    "nodes": [
      {
        "id": "node_1",
        "label": "Planning",
        "type": "planning",
        "status": "pending",
        "agent": "planner",
        "step_number": 0
      }
    ],
    "edges": [
      { "source": "node_1", "target": "node_2" }
    ],
    "levels": 4
  }
}
```

### `dag_updated`
Full DAG refresh (rare).

### `dag_node_status_changed`
```json
{
  "event_type": "dag_node_status_changed",
  "run_id": "uuid",
  "data": {
    "node_id": "node_1",
    "old_status": "pending",
    "new_status": "running",
    "error": null
  }
}
```

## Agent Events

### `agent_message`
```json
{
  "event_type": "agent_message",
  "run_id": "uuid",
  "data": {
    "agent": "engineer",
    "message": "Analyzing the code...",
    "role": "assistant"
  }
}
```

### `agent_thinking`
```json
{
  "event_type": "agent_thinking",
  "run_id": "uuid",
  "data": {
    "agent": "engineer",
    "thinking": true
  }
}
```

### `agent_tool_call`
```json
{
  "event_type": "agent_tool_call",
  "run_id": "uuid",
  "data": {
    "agent": "engineer",
    "tool_name": "execute_code",
    "arguments": {}
  }
}
```

## Approval Events

### `approval_requested`
```json
{
  "event_type": "approval_requested",
  "run_id": "uuid",
  "data": {
    "approval_id": "uuid",
    "step_id": "uuid",
    "action": "Execute generated code",
    "description": "Review and approve the following code...",
    "context": {
      "current_step": { "number": 3, "description": "...", "agent": "engineer" },
      "previous_output": "...",
      "proposed_action": "..."
    },
    "options": [
      { "id": "approve", "label": "Approve", "action": "approve" },
      { "id": "reject", "label": "Reject", "action": "reject" }
    ],
    "checkpoint_type": "before_step"
  }
}
```

### `approval_received`
```json
{
  "event_type": "approval_received",
  "run_id": "uuid",
  "data": {
    "approval_id": "uuid",
    "approved": true,
    "feedback": "Looks good"
  }
}
```

## Cost and Metrics Events

### `cost_update`
```json
{
  "event_type": "cost_update",
  "run_id": "uuid",
  "data": {
    "run_id": "uuid",
    "step_id": "uuid",
    "model": "gpt-4o",
    "tokens": 1500,
    "cost_usd": 0.0045,
    "total_cost_usd": 0.0245
  }
}
```

### `metric_update`
```json
{
  "event_type": "metric_update",
  "run_id": "uuid",
  "data": {
    "name": "memory_usage_mb",
    "value": 512,
    "unit": "MB"
  }
}
```

## File Events

### `file_created`
```json
{
  "event_type": "file_created",
  "run_id": "uuid",
  "data": {
    "file_path": "/path/to/file.py",
    "file_type": "python"
  }
}
```

### `file_updated`
```json
{
  "event_type": "file_updated",
  "run_id": "uuid",
  "data": {
    "file_path": "/path/to/file.py"
  }
}
```

## Error Events

### `error_occurred`
```json
{
  "event_type": "error_occurred",
  "run_id": "uuid",
  "data": {
    "error_type": "ValidationError",
    "message": "Invalid input provided",
    "step_id": "uuid",
    "traceback": "..."
  }
}
```

## Legacy Events (Backward Compatibility)

### `output`
Simple text output (deprecated, use `agent_message`).
```json
{
  "type": "output",
  "data": "Processing step 1..."
}
```

### `status`
Status message (deprecated, use `workflow_state_changed`).
```json
{
  "type": "status",
  "message": "Running..."
}
```

### `result`
Final result (deprecated, use `workflow_completed`).
```json
{
  "type": "result",
  "data": { ... }
}
```

### `complete`
Workflow complete signal (deprecated).
```json
{
  "type": "complete"
}
```

---

**Last Updated:** 2026-01-16
