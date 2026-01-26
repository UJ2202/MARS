# IT Tasks DAG Integration

## Overview

IT Tasks (AI Weekly, Release Notes, Code Review) now integrate with the existing DAG workflow visualization system. Each task execution creates a real-time workflow DAG with live logs visible in the UI.

## Architecture

### Backend Flow

```
User Submit → REST POST /api/tasks/{tool}/execute
           → Task Created (returns task_id)
           → Frontend GET /api/tasks/tasks/{task_id}/config
           → Frontend connects WebSocket /ws/{task_id}
           → execute_cmbagent_task() starts
           → DAGTracker creates initial DAG
           → Planning & Control workflow executes
           → DAG nodes update in real-time
           → Console logs streamed via WebSocket
           → Final result available in database
```

### Component Structure

#### Backend (`backend/routers/tasks.py`)
- **POST /api/tasks/ai-weekly/execute** - Create AI Weekly task
- **POST /api/tasks/release-notes/execute** - Create Release Notes task  
- **POST /api/tasks/code-review/execute** - Create Code Review task
- **GET /api/tasks/tasks/{task_id}/config** - Get task description and config for WebSocket execution
- **GET /api/tasks/status/{task_id}** - Legacy HTTP polling endpoint

All tasks now return status "ready" with a `websocket_url` field directing the client to connect via WebSocket.

#### Frontend (`cmbagent-ui/components/tasks/AIWeeklyTask.tsx`)
- Uses `useWebSocketContext` hook for real-time connection
- Displays two-view mode:
  - **Config View**: Form for task parameters
  - **Execution View**: DAG visualization + Console output
- Integrates `DAGWorkspace` component from existing system
- Displays `ConsoleOutput` for real-time logs

### WebSocket Integration

The IT Tasks now use the same WebSocket infrastructure as the main CMBAgent system:

1. **WebSocketContext** (`contexts/WebSocketContext.tsx`)
   - Manages connection state
   - Provides `dagData` (nodes, edges)
   - Provides `consoleOutput` array
   - Provides `connect()`, `disconnect()` functions
   - Tracks workflow status and results

2. **DAGWorkspace** (`components/dag/DAGWorkspace.tsx`)
   - Full DAG visualization with tabs (graph, timeline, history, files, cost)
   - Stats panel showing progress
   - Search and filtering
   - Minimap and fullscreen modes

3. **ConsoleOutput** (`components/ConsoleOutput.tsx`)
   - Real-time log display
   - Auto-scrolling
   - Syntax highlighting

### DAG Creation

When a task executes, the `DAGTracker` creates an initial DAG structure:

```typescript
// Planning & Control Mode DAG
{
  nodes: [
    { id: "planning", label: "Planning Phase", type: "planning", status: "pending" }
  ],
  edges: [],
  levels: 1
}
```

As the workflow progresses:
- Planner creates sub-tasks → New nodes added dynamically
- Each agent execution → Node status updates ("running", "completed", "failed")
- Progress logs → Console output streamed
- Workflow completes → All nodes show final states

## Usage Example

### Frontend Code
```typescript
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { DAGWorkspace } from '@/components/dag'
import ConsoleOutput from '@/components/ConsoleOutput'

const MyTask = () => {
  const { connect, dagData, consoleOutput, isRunning } = useWebSocketContext()
  
  const handleStart = async () => {
    // 1. Create task via REST
    const res = await fetch('/api/tasks/ai-weekly/execute', {
      method: 'POST',
      body: JSON.stringify({ tool: 'ai-weekly', parameters: {...} })
    })
    const { task_id } = await res.json()
    
    // 2. Get config
    const config = await fetch(`/api/tasks/tasks/${task_id}/config`)
    const { description, config: taskConfig } = await config.json()
    
    // 3. Connect WebSocket
    await connect(task_id, description, taskConfig)
  }
  
  return (
    <div>
      <button onClick={handleStart}>Start</button>
      <DAGWorkspace dagData={dagData} />
      <ConsoleOutput output={consoleOutput} />
    </div>
  )
}
```

### Backend Code
```python
@router.post("/my-task/execute")
async def execute_my_task(request: ToolExecutionRequest):
    task_id = f"my_task_{uuid.uuid4()}"
    
    # Build detailed task description
    task_description = "..."
    
    # Store task info
    active_tasks[task_id] = {
        'status': 'ready',
        'task_description': task_description,
        'parameters': request.parameters
    }
    
    # Return with WebSocket URL
    return ToolExecutionResponse(
        task_id=task_id,
        status="ready",
        websocket_url=f"/ws/{task_id}"
    )

def get_task_config(task_id: str, params: Dict) -> Dict:
    return {
        'mode': 'planning-control',
        'maxPlanSteps': 6,
        'work_dir': f"~/Desktop/cmbdir/{task_id}"
    }
```

## Benefits

✅ **Real-time Visualization**: See workflow DAG as it executes
✅ **Live Logs**: Console output streams in real-time
✅ **Database Integration**: All DAG data persists in database
✅ **Reconnection Support**: Refresh page and state restores from DB
✅ **Consistent UX**: Same DAG UI as main CMBAgent system
✅ **Cost Tracking**: Automatic token usage tracking in DAG view
✅ **History**: All workflow runs saved with full replay capability

## Migration from Polling

**Old Approach** (Background Tasks + Polling):
```python
# ❌ Old way - Background task with polling
background_tasks.add_task(run_workflow, task_id, task, params)
# Frontend polls /api/tasks/status/{task_id} every 5 seconds
```

**New Approach** (WebSocket with DAG):
```python
# ✅ New way - WebSocket with real-time DAG
return {"task_id": task_id, "websocket_url": f"/ws/{task_id}"}
# Frontend connects WebSocket, gets real-time DAG updates
```

## Task Types

### AI Weekly Report
- **Mode**: planning-control
- **Steps**: 6 (ArXiv search, GitHub releases, blogs, analyze, summarize, format)
- **Duration**: 3-5 minutes
- **Output**: Structured newsletter with headlines and sections

### Release Notes
- **Mode**: planning-control  
- **Steps**: 5 (Git history, PRs, categorize, highlights, format)
- **Duration**: 2-4 minutes
- **Output**: Professional release notes with statistics

### Code Review
- **Mode**: planning-control
- **Steps**: 7 (Parse, security, quality, performance, best practices, recommendations, report)
- **Duration**: 4-6 minutes
- **Output**: Comprehensive review with scores and issues

## Future Enhancements

- [ ] Result parsing from workflow output (structured data extraction)
- [ ] Custom DAG layouts per task type
- [ ] Approval gates for tasks requiring human input
- [ ] Parallel execution of independent sub-tasks
- [ ] Task templates and favorites
- [ ] Scheduled/recurring tasks
- [ ] Export DAG as image/PDF
