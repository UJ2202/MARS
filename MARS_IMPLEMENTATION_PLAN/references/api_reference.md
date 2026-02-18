# REST API Reference

All API endpoints used by the MARS UI. These endpoints are provided by the backend at `http://localhost:8000` and proxied via Next.js rewrites through `/api/*`.

**CRITICAL: These endpoints must NOT be changed during the UI overhaul.**

## Endpoints

### Tasks

#### `POST /api/tasks`
Submit a new task for execution.

**Request Body:**
```json
{
  "task": "string - task description",
  "config": {
    "mode": "one-shot | planning-control | idea-generation | ocr | arxiv | enhance-input | hitl-interactive | copilot",
    "model": "string - LLM model ID",
    "agent": "engineer | researcher",
    "maxRounds": "number",
    "maxAttempts": "number",
    "maxPlanSteps": "number",
    "enablePlanning": "boolean",
    "approvalMode": "none | before_step | after_step | both",
    "hitlVariant": "full_interactive | planning_only | error_recovery",
    "toolApproval": "auto | prompt | deny",
    "session_id": "string? - for session continuation",
    "copilotSessionId": "string? - for copilot session continuation"
  }
}
```

**Triggered by:** `WebSocketContext.connect()` via WebSocket initial message

---

### Sessions

#### `GET /api/sessions`
List all sessions.

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "string",
      "name": "string",
      "mode": "string",
      "status": "active | suspended | completed | failed",
      "current_phase": "string?",
      "current_step": "number?",
      "created_at": "ISO 8601 string",
      "updated_at": "ISO 8601 string"
    }
  ]
}
```

**Used by:** SessionList, SessionScreen

#### `GET /api/sessions/{session_id}`
Get detailed session information.

**Response:**
```json
{
  "session_id": "string",
  "name": "string",
  "mode": "string",
  "status": "string",
  "current_phase": "string?",
  "current_step": "number?",
  "created_at": "string?",
  "updated_at": "string?",
  "conversation_history": [
    {
      "role": "user | assistant | system",
      "content": "string",
      "agent": "string?",
      "timestamp": "string?"
    }
  ],
  "context_variables": {},
  "plan_data": "any?",
  "config": {}
}
```

**Used by:** SessionDetailPanel, handleResumeSessionFromList

#### `GET /api/sessions/{session_id}/history`
Get session conversation history.

**Query Parameters:**
- `limit`: number (default: 500)

**Response:**
```json
{
  "messages": [
    {
      "role": "string",
      "content": "string",
      "agent": "string?",
      "timestamp": "string?"
    }
  ]
}
```

**Used by:** handleViewSessionLogs

#### `POST /api/sessions/{session_id}/resume`
Mark session as active for resumption.

**Used by:** handleResumeSessionFromList

---

### Runs

#### `GET /api/runs/{run_id}/dag`
Get DAG graph data for a run.

**Response:**
```json
{
  "run_id": "string",
  "nodes": [
    {
      "id": "string",
      "label": "string",
      "type": "string",
      "status": "string",
      "agent": "string?",
      "step_number": "number?",
      "metadata": {}
    }
  ],
  "edges": [
    {
      "source": "string",
      "target": "string",
      "type": "string?"
    }
  ]
}
```

#### `GET /api/runs/{run_id}/files`
Get files produced by a run.

#### `GET /api/runs/{run_id}/costs`
Get cost tracking data for a run.

#### `POST /api/runs/{run_id}/play-from-node`
Resume execution from a specific DAG node.

**Request Body:**
```json
{
  "node_id": "string",
  "context_override": null
}
```

#### `POST /api/runs/{run_id}/branch`
Create an experimental branch from a node.

**Request Body:**
```json
{
  "node_id": "string",
  "branch_name": "string",
  "hypothesis": "string?",
  "new_instructions": "string?",
  "execute_immediately": "boolean"
}
```

---

### Approvals

#### `POST /api/approvals/{approval_id}`
Submit approval response (sent via WebSocket, not REST).

**WebSocket Message:**
```json
{
  "type": "resolve_approval",
  "approval_id": "string",
  "resolution": "approve | reject | modify | submit",
  "feedback": "string",
  "modifications": "string"
}
```

---

## WebSocket Connection

**URL Pattern:** `ws://localhost:8000/ws/{taskId}`

**Connection:** Established by `WebSocketContext.connect()` when a task is submitted.

**Initial Message (sent by UI):**
```json
{
  "task_id": "string",
  "task": "string - task description",
  "config": { /* same as POST /api/tasks config */ }
}
```

**Messages FROM Backend:** See `event_types.md` for full catalog.

**Messages TO Backend:**
- `{ "type": "pause", "run_id": "string" }` - Pause workflow
- `{ "type": "resume", "run_id": "string" }` - Resume workflow
- `{ "type": "resolve_approval", ... }` - Approval response
- `{ "type": "ping" }` - Heartbeat

---

**Last Updated:** 2026-02-18
