# IT Tasks Flow Diagram

## End-to-End Execution Flow

```
┌─────────────┐
│   Browser   │
│  (UI Form)  │
└──────┬──────┘
       │
       │ 1. User fills form and clicks "Generate"
       ▼
┌─────────────────────────────────┐
│  AIWeeklyTask Component         │
│  - handleGenerate()             │
└──────┬──────────────────────────┘
       │
       │ 2. POST /api/tasks/ai-weekly/execute
       │    { parameters: { dateFrom, dateTo, topics, sources } }
       ▼
┌──────────────────────────────────────┐
│  Backend: tasks.py                   │
│  execute_ai_weekly_report()          │
│  - Generate task_id                  │
│  - Build task_description            │
│  - Store in active_tasks             │
│  - Return { task_id, websocket_url } │
└──────┬───────────────────────────────┘
       │
       │ 3. Response: { task_id: "ai_weekly_abc123", websocket_url: "/ws/ai_weekly_abc123" }
       ▼
┌─────────────────────────────────┐
│  AIWeeklyTask Component         │
│  - Receive task_id              │
└──────┬──────────────────────────┘
       │
       │ 4. GET /api/tasks/tasks/{task_id}/config
       ▼
┌──────────────────────────────────────┐
│  Backend: tasks.py                   │
│  get_task_config()                   │
│  - Return task description           │
│  - Return config (mode, steps, etc)  │
└──────┬───────────────────────────────┘
       │
       │ 5. Response: { description: "...", config: { mode: "planning-control", ... } }
       ▼
┌─────────────────────────────────┐
│  WebSocketContext               │
│  connect(task_id, desc, config) │
└──────┬──────────────────────────┘
       │
       │ 6. WebSocket connection to /ws/{task_id}
       ▼
┌──────────────────────────────────────┐
│  Backend: websocket_endpoint         │
│  - Accept WebSocket                  │
│  - Call execute_cmbagent_task()      │
└──────┬───────────────────────────────┘
       │
       │ 7. Start execution
       ▼
┌──────────────────────────────────────┐
│  task_executor.py                    │
│  execute_cmbagent_task()             │
│  - Create DAGTracker                 │
│  - Create initial DAG                │
│  - Send dag_created event            │
└──────┬───────────────────────────────┘
       │
       │ 8. DAG Created Event
       │    { event_type: "dag_created", nodes: [...], edges: [...] }
       ▼
┌─────────────────────────────────┐
│  WebSocketContext               │
│  - Update dagData state         │
└──────┬──────────────────────────┘
       │
       │ 9. State update triggers re-render
       ▼
┌─────────────────────────────────┐
│  AIWeeklyTask Component         │
│  - DAGWorkspace shows DAG       │
│  - ConsoleOutput shows logs     │
└──────┬──────────────────────────┘
       │
       │ Meanwhile, backend continues execution...
       ▼
┌──────────────────────────────────────┐
│  task_executor.py                    │
│  - Call planning_and_control...      │
│  - DAGTracker monitors execution     │
└──────┬───────────────────────────────┘
       │
       │ 10. As workflow progresses
       ▼
┌──────────────────────────────────────┐
│  DAGTracker                          │
│  - Planning phase starts             │
│    → update_node_status("planning")  │
│  - Planner creates sub-tasks         │
│    → add_dynamic_nodes()             │
│  - Each agent executes               │
│    → update_node_status()            │
│  - Console output                    │
│    → send_ws_event("output", ...)    │
└──────┬───────────────────────────────┘
       │
       │ 11. Real-time events stream
       │     - dag_updated (nodes change status)
       │     - output (console logs)
       │     - step_progress (workflow progress)
       ▼
┌─────────────────────────────────┐
│  WebSocketContext               │
│  - Update dagData               │
│  - Append to consoleOutput      │
└──────┬──────────────────────────┘
       │
       │ 12. UI updates in real-time
       ▼
┌─────────────────────────────────┐
│  DAGWorkspace                   │
│  - Nodes change color           │
│    (pending → running → completed)
│  - Progress bar updates         │
│  - Stats panel updates          │
└─────────────────────────────────┘
       
┌─────────────────────────────────┐
│  ConsoleOutput                  │
│  - New log lines appear         │
│  - Auto-scrolls to bottom       │
└─────────────────────────────────┘
       │
       │ 13. Workflow completes
       ▼
┌──────────────────────────────────────┐
│  task_executor.py                    │
│  - Workflow finished                 │
│  - Send workflow_completed event     │
│  - Store result in database          │
└──────┬───────────────────────────────┘
       │
       │ 14. Completion Event
       │     { event_type: "workflow_completed", result: {...} }
       ▼
┌─────────────────────────────────┐
│  AIWeeklyTask Component         │
│  - useEffect detects completion │
│  - Poll /api/tasks/status/...   │
│  - Display formatted result     │
└─────────────────────────────────┘
```

## Component Responsibilities

### Frontend

#### AIWeeklyTask.tsx
- Collect user input (dates, topics, sources)
- Create task via REST API
- Fetch task configuration
- Connect WebSocket via useWebSocketContext
- Display execution view with DAG + logs
- Handle task completion and result display

#### WebSocketContext.tsx
- Manage WebSocket connection lifecycle
- Maintain dagData state (nodes, edges)
- Maintain consoleOutput state (log array)
- Provide connect(), disconnect() functions
- Handle incoming events and update state
- Provide workflow status tracking

#### DAGWorkspace.tsx
- Render DAG visualization (graph view)
- Show execution timeline
- Display stats panel (progress, duration, node counts)
- Support search, filtering, minimap, fullscreen
- Handle node selection and interactions

#### ConsoleOutput.tsx
- Render log lines
- Auto-scroll to bottom
- Syntax highlighting
- Copy/export functionality

### Backend

#### routers/tasks.py
- Define REST endpoints for task creation
- Build task descriptions and configurations
- Store task metadata in active_tasks dict
- Return task_id and websocket_url
- Provide config endpoint for WebSocket setup

#### websocket/handlers.py
- Accept WebSocket connections
- Call execute_cmbagent_task()
- Route messages between client and executor

#### execution/task_executor.py
- Execute CMBAgent workflow
- Create and manage DAGTracker
- Send WebSocket events (dag_created, dag_updated, output)
- Handle workflow completion
- Integrate with database for persistence

#### execution/dag_tracker.py
- Create initial DAG structure based on mode
- Monitor workflow execution
- Update node statuses in real-time
- Emit DAG events to WebSocket
- Store DAG data in database
- Support dynamic node addition (during planning)

## Data Flow

### Task Creation (REST)
```
POST /api/tasks/ai-weekly/execute
Request: { tool: "ai-weekly", parameters: {...} }
Response: { task_id: "...", status: "ready", websocket_url: "/ws/..." }
```

### Config Fetch (REST)
```
GET /api/tasks/tasks/{task_id}/config
Response: { 
  task_id: "...",
  description: "Generate comprehensive AI Tech Weekly Report...",
  config: { mode: "planning-control", maxPlanSteps: 6, ... }
}
```

### WebSocket Connection
```
Client → Server: CONNECT /ws/{task_id}
Server → Client: { event_type: "connected", data: {...} }
Server → Client: { event_type: "dag_created", nodes: [...], edges: [...] }
```

### Real-time Updates
```
Server → Client: { event_type: "output", data: { message: "🚀 Starting..." } }
Server → Client: { event_type: "dag_updated", nodes: [...], edges: [...] }
Server → Client: { event_type: "step_progress", data: { step: 1, total: 6 } }
Server → Client: { event_type: "workflow_completed", data: { result: {...} } }
```

### State Updates (Frontend)
```
WebSocket Event → WebSocketContext state update
                → React re-render
                → DAGWorkspace updates (node colors, positions)
                → ConsoleOutput adds new lines
```

## Error Handling

### Task Creation Error
```
User clicks Generate
  → POST fails (network error, validation)
    → setError(message)
    → Display error in UI
    → Stay in config view
```

### WebSocket Connection Error
```
connect() called
  → WebSocket fails to connect
    → WebSocketContext sets error state
    → Display connection error banner
    → Provide "Retry" button
```

### Workflow Execution Error
```
Workflow running
  → Agent throws exception
    → DAGTracker catches error
    → Sets node status to "failed"
    → Sends error event
      → WebSocketContext updates dagData
      → UI shows failed node in red
      → Console shows error message
```

### Disconnection
```
WebSocket disconnects
  → WebSocketContext detects disconnection
  → Shows "Reconnecting..." banner
  → Attempts automatic reconnect
  → On reconnect, server sends current state
    → DAG data restored from database
    → Console output restored
    → UI synchronized with current workflow state
```

## Performance Considerations

- **DAG Updates**: Debounced to avoid excessive re-renders
- **Console Output**: Limited to last 1000 lines, older lines truncated
- **WebSocket Batching**: Multiple events can be batched in single message
- **Database Persistence**: All DAG state persisted for reconnection support
- **Lazy Loading**: DAG history and files tabs load on demand
