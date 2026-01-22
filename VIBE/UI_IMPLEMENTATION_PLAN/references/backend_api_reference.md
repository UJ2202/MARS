# Backend API Reference

This document lists all REST API endpoints available from the CMBAgent backend.

## Base URL

Development: `http://localhost:8000`

## Authentication

Currently no authentication required for local development.

---

## Health & Status

### GET /api/health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## Credentials

### GET /api/credentials/status
Check if API credentials are configured.

**Response:**
```json
{
  "openai": true,
  "anthropic": false,
  "gemini": false
}
```

### POST /api/credentials/store
Store API credentials.

**Request Body:**
```json
{
  "openai_api_key": "sk-...",
  "anthropic_api_key": "sk-ant-...",
  "gemini_api_key": "..."
}
```

**Response:**
```json
{
  "success": true,
  "message": "Credentials stored"
}
```

---

## Workflow Execution

### POST /api/run
Start a new workflow run.

**Request Body:**
```json
{
  "task": "Analyze the data and create a visualization",
  "agent": "engineer",
  "model": "gpt-4o",
  "work_dir": "./work/project_xyz",
  "context_file": null,
  "planning": false,
  "plan_steps": 3,
  "max_rounds": 10
}
```

**Response:**
```json
{
  "run_id": "uuid",
  "status": "started"
}
```

### GET /api/runs/{run_id}
Get workflow run details.

**Response:**
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "task_description": "...",
  "status": "executing",
  "agent": "engineer",
  "model": "gpt-4o",
  "started_at": "2026-01-16T10:00:00Z",
  "completed_at": null,
  "total_cost": 0.0245,
  "step_count": 5
}
```

### POST /api/runs/{run_id}/pause
Pause a running workflow.

**Response:**
```json
{
  "success": true,
  "status": "paused"
}
```

### POST /api/runs/{run_id}/resume
Resume a paused workflow.

**Response:**
```json
{
  "success": true,
  "status": "executing"
}
```

### POST /api/runs/{run_id}/cancel
Cancel a workflow.

**Response:**
```json
{
  "success": true,
  "status": "cancelled"
}
```

---

## Branching (Stage 9)

### POST /api/runs/{run_id}/branch
Create a new branch from a workflow run.

**Request Body:**
```json
{
  "branch_point_step_id": "uuid",
  "name": "experiment-higher-lr",
  "hypothesis": "Increasing learning rate will improve results"
}
```

**Response:**
```json
{
  "branch_id": "uuid",
  "run_id": "uuid",
  "name": "experiment-higher-lr",
  "created_at": "2026-01-16T10:00:00Z"
}
```

### POST /api/runs/{run_id}/play-from-node
Resume execution from a specific node (creates implicit branch).

**Request Body:**
```json
{
  "node_id": "uuid",
  "branch_name": "retry-from-step-3",
  "hypothesis": "Fix validation error"
}
```

**Response:**
```json
{
  "new_run_id": "uuid",
  "branch_id": "uuid",
  "resuming_from_step": 3
}
```

### GET /api/branches/compare
Compare two branches.

**Query Parameters:**
- `branch_a`: Branch ID A
- `branch_b`: Branch ID B

**Response:**
```json
{
  "branch_a": {
    "branch_id": "uuid",
    "name": "main",
    "total_steps": 10,
    "completed_steps": 10,
    "total_cost": 0.0245,
    "final_status": "completed"
  },
  "branch_b": {
    "branch_id": "uuid",
    "name": "experiment-1",
    "total_steps": 10,
    "completed_steps": 8,
    "total_cost": 0.0198,
    "final_status": "failed"
  },
  "differences": [
    {
      "step_number": 5,
      "description_a": "Train model",
      "description_b": "Train model with higher LR",
      "status_a": "completed",
      "status_b": "failed",
      "output_differs": true
    }
  ]
}
```

### GET /api/runs/{run_id}/branch-tree
Get branch hierarchy for a workflow.

**Response:**
```json
{
  "branches": [
    {
      "branch_id": "uuid",
      "run_id": "uuid",
      "name": "main",
      "is_main": true,
      "status": "completed",
      "children": [
        {
          "branch_id": "uuid",
          "run_id": "uuid",
          "name": "experiment-1",
          "parent_branch_id": "uuid",
          "hypothesis": "Test hypothesis",
          "status": "failed",
          "children": []
        }
      ]
    }
  ]
}
```

### GET /api/runs/{run_id}/resumable-nodes
Get list of nodes that can be resumed from.

**Response:**
```json
{
  "nodes": [
    {
      "step_id": "uuid",
      "step_number": 3,
      "description": "Process data",
      "status": "completed",
      "completed_at": "2026-01-16T10:05:00Z"
    }
  ]
}
```

---

## Approvals

### POST /api/approvals/{approval_id}/respond
Submit approval response.

**Request Body:**
```json
{
  "action": "approve",
  "feedback": "Looks good, proceed"
}
```

**Response:**
```json
{
  "success": true,
  "workflow_resumed": true
}
```

### GET /api/runs/{run_id}/approvals
Get approval history for a run.

**Response:**
```json
{
  "approvals": [
    {
      "approval_id": "uuid",
      "checkpoint_type": "before_step",
      "action": "Execute code",
      "status": "resolved",
      "resolution": {
        "action": "approve",
        "feedback": "...",
        "resolved_at": "2026-01-16T10:03:00Z"
      }
    }
  ]
}
```

---

## Files

### GET /api/files/list
List directory contents.

**Query Parameters:**
- `path`: Directory path (default: work_dir)

**Response:**
```json
{
  "files": [
    {
      "name": "output.py",
      "path": "/work/output.py",
      "type": "file",
      "size": 1234,
      "modified": "2026-01-16T10:00:00Z"
    }
  ]
}
```

### GET /api/files/content
Get file content.

**Query Parameters:**
- `path`: File path

**Response:**
```json
{
  "content": "# Python code...",
  "encoding": "utf-8"
}
```

### DELETE /api/files/clear-directory
Clear work directory.

**Query Parameters:**
- `path`: Directory path

**Response:**
```json
{
  "success": true,
  "deleted_count": 15
}
```

### GET /api/files/images
List images in work directory.

**Response:**
```json
{
  "images": [
    {
      "name": "plot.png",
      "path": "/work/data/plot.png",
      "size": 45678
    }
  ]
}
```

### GET /api/files/serve-image
Serve image file.

**Query Parameters:**
- `path`: Image path

**Response:** Binary image data

---

## Sessions & History

### GET /api/sessions
List all sessions.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 10)
- `status`: Filter by status

**Response:**
```json
{
  "sessions": [
    {
      "id": "uuid",
      "name": "Session 1",
      "status": "active",
      "workflow_count": 5,
      "total_cost": 0.125,
      "created_at": "2026-01-15T10:00:00Z",
      "last_active_at": "2026-01-16T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_items": 25,
    "total_pages": 3
  }
}
```

### GET /api/sessions/{session_id}/runs
List workflow runs in a session.

**Response:**
```json
{
  "runs": [
    {
      "id": "uuid",
      "task_description": "...",
      "status": "completed",
      "agent": "engineer",
      "model": "gpt-4o",
      "total_cost": 0.0245,
      "step_count": 10,
      "started_at": "2026-01-16T10:00:00Z",
      "completed_at": "2026-01-16T10:05:00Z"
    }
  ]
}
```

### GET /api/runs/{run_id}/steps
List steps in a workflow run.

**Response:**
```json
{
  "steps": [
    {
      "id": "uuid",
      "step_number": 1,
      "description": "Analyze requirements",
      "agent": "engineer",
      "status": "completed",
      "cost": 0.0023,
      "started_at": "2026-01-16T10:00:00Z",
      "completed_at": "2026-01-16T10:00:30Z",
      "retry_count": 0
    }
  ]
}
```

---

## Metrics

### GET /api/runs/{run_id}/metrics
Get metrics for a workflow run.

**Response:**
```json
{
  "cost_summary": {
    "total_cost": 0.0245,
    "total_tokens": 15000,
    "input_tokens": 10000,
    "output_tokens": 5000,
    "model_breakdown": [...],
    "agent_breakdown": [...],
    "step_breakdown": [...]
  },
  "execution_metrics": {
    "total_duration_seconds": 125.5,
    "planning_duration_seconds": 15.2,
    "execution_duration_seconds": 110.3,
    "avg_step_duration_seconds": 12.5,
    "slowest_step_seconds": 35.2,
    "fastest_step_seconds": 5.1
  }
}
```

---

## WebSocket

### WS /ws/{run_id}
WebSocket connection for real-time updates.

See [websocket_events.md](./websocket_events.md) for event documentation.

**Client Messages:**
```json
{ "type": "ping" }
{ "type": "request_state" }
{ "type": "pause" }
{ "type": "resume" }
```

---

**Last Updated:** 2026-01-16
