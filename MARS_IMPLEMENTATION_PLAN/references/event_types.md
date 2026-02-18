# WebSocket Event Types Reference

Complete catalog of WebSocket events used by the MARS UI. All events are defined in `types/websocket-events.ts`.

**CRITICAL: These event types must NOT be changed during the UI overhaul.**

## Event Format

All events follow this structure:
```typescript
interface WebSocketEvent {
  event_type: WebSocketEventType | string
  timestamp: string        // ISO 8601
  run_id?: string
  session_id?: string
  data: Record<string, any>
}
```

## Event Categories

### Connection Events
| Event | Description | UI Action |
|-------|-------------|-----------|
| `connected` | WebSocket connected | Update connection status |
| `disconnected` | WebSocket disconnected | Show reconnect UI |
| `reconnected` | Successfully reconnected | Clear error state |

### Workflow Lifecycle
| Event | Description | Data Type | UI Action |
|-------|-------------|-----------|-----------|
| `workflow_started` | Workflow begins | `WorkflowStartedData` | Set isRunning=true, show run_id |
| `workflow_state_changed` | Status changes | `WorkflowStateChangedData` | Update workflowStatus |
| `workflow_paused` | Workflow paused | `{ run_id }` | Update status, show toast |
| `workflow_resumed` | Workflow resumed | `{ run_id }` | Update status, show toast |
| `workflow_completed` | Workflow done | `{ run_id, result }` | Set isRunning=false, show results |
| `workflow_failed` | Workflow error | `{ run_id, error }` | Set isRunning=false, show error |

### Step Execution
| Event | Description | Data Type | UI Action |
|-------|-------------|-----------|-----------|
| `step_started` | Step begins | `StepStartedData` | Update DAG node, add console |
| `step_progress` | Step progress | `StepProgressData` | Update progress bar |
| `step_completed` | Step done | `StepCompletedData` | Update DAG node to completed |
| `step_failed` | Step error | `StepFailedData` | Update DAG node to failed |

### Retry Events
| Event | Description | Data Type |
|-------|-------------|-----------|
| `step_retry_started` | Retry begins | `StepRetryStartedData` |
| `step_retry_backoff` | Waiting before retry | backoff_seconds, attempt |
| `step_retry_succeeded` | Retry worked | step_id, attempt |
| `step_retry_exhausted` | All retries failed | step_id, max_attempts |

### DAG Events
| Event | Description | Data Type | UI Action |
|-------|-------------|-----------|-----------|
| `dag_created` | Full DAG received | `DAGCreatedData` | Render DAG visualization |
| `dag_updated` | DAG structure changed | nodes, edges | Update DAG |
| `dag_node_status_changed` | Node status change | `DAGNodeStatusChangedData` | Update node color/icon |

### Branch Events
| Event | Description | Data Type |
|-------|-------------|-----------|
| `branch_created` | Branch created | `BranchCreatedData` |
| `branch_executing` | Branch running | `BranchExecutingData` |
| `branch_completed` | Branch done | `BranchCompletedData` |
| `branch_failed` | Branch error | `BranchFailedData` |

### Agent Events
| Event | Description | Data Type | UI Action |
|-------|-------------|-----------|-----------|
| `agent_message` | Agent output | `AgentMessageData` | Add to console, copilot chat |
| `agent_thinking` | Agent reasoning | agent, message | Show thinking indicator |
| `agent_tool_call` | Tool invocation | agent, tool_name, arguments | Show in console |
| `code_execution` | Code execution | `CodeExecutionData` | Show code block in console |
| `tool_call` | Tool call details | `ToolCallData` | Show in console |

### Approval Events
| Event | Description | Data Type | UI Action |
|-------|-------------|-----------|-----------|
| `approval_requested` | Needs user approval | `ApprovalRequestedData` | Show ApprovalChatPanel |
| `approval_received` | Approval processed | `ApprovalReceivedData` | Clear pending approval |

### Cost & Metrics
| Event | Description | Data Type | UI Action |
|-------|-------------|-----------|-----------|
| `cost_update` | Token/cost update | `CostUpdateData` | Update costSummary |
| `metric_update` | General metric | key, value | Log to console |

### File Events
| Event | Description | Data Type | UI Action |
|-------|-------------|-----------|-----------|
| `file_created` | New file | filename, path | Increment filesUpdatedCounter |
| `file_updated` | File modified | filename, path | Increment filesUpdatedCounter |
| `files_updated` | Batch update | `FilesUpdatedData` | Refresh files view |

### Error Events
| Event | Description | Data Type |
|-------|-------------|-----------|
| `error_occurred` | Runtime error | `ErrorOccurredData` |

### Heartbeat
| Event | Description |
|-------|-------------|
| `heartbeat` | Server heartbeat |
| `pong` | Response to ping |

### Legacy Events
| Event | Description |
|-------|-------------|
| `output` | Legacy console output |
| `status` | Legacy status update |
| `result` | Legacy result |
| `complete` | Legacy completion |

## Data Type Definitions

```typescript
interface WorkflowStartedData {
  run_id: string
  task_description: string
  agent: string
  model: string
  work_dir?: string
}

interface StepStartedData {
  step_id: string
  step_number: number
  step_description: string
  agent: string
}

interface StepProgressData {
  step_id: string
  step_number: number
  progress_percentage: number
  message: string
}

interface StepCompletedData {
  step_id: string
  step_number: number
  result?: string
  output?: string
}

interface StepFailedData {
  step_id: string
  step_number: number
  error: string
  traceback?: string
}

interface DAGCreatedData {
  run_id: string
  nodes: DAGNodeData[]
  edges: DAGEdgeData[]
  levels: number
}

interface DAGNodeData {
  id: string
  label: string
  type: string
  status: string
  agent?: string
  step_number?: number
  metadata?: Record<string, any>
}

interface DAGEdgeData {
  source: string
  target: string
  type?: string
}

interface ApprovalRequestedData {
  approval_id: string
  step_id: string
  action: string
  description: string
  message?: string
  context: Record<string, any>
  options?: string[]
  checkpoint_type?: string
}

interface CostUpdateData {
  run_id: string
  agent?: string
  step_id?: string
  model: string
  tokens: number
  input_tokens?: number
  output_tokens?: number
  cost_usd: number
  total_cost_usd: number
}

interface AgentMessageData {
  agent: string
  message: string
  role: string
}

interface FilesUpdatedData {
  run_id: string
  node_id?: string
  step_id?: string
  files_tracked: number
}
```

---

**Last Updated:** 2026-02-18
