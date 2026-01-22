# Stage 5: Enhanced WebSocket Protocol

**Phase:** 1 - Planning and Control Enhancement
**Estimated Time:** 30-40 minutes
**Dependencies:** Stage 4 (DAG Builder) must be complete
**Risk Level:** Medium

## Objectives

1. Design structured WebSocket event protocol with typed messages
2. Implement automatic reconnection with exponential backoff
3. Make backend WebSocket handler completely stateless
4. Add event queue for reliable message delivery
5. Support real-time DAG visualization updates
6. Enable workflow state synchronization across disconnects

## Current State Analysis

### What We Have
- Basic WebSocket connection in backend
- Simple message passing (unstructured)
- No reconnection handling
- State lost on disconnect
- No message queuing
- Manual console output streaming

### What We Need
- Typed event protocol (workflow_started, step_completed, etc.)
- Automatic reconnection in UI
- Stateless backend (all state in database)
- Message queue for missed events
- Real-time DAG updates
- Robust long-running workflow support

## Pre-Stage Verification

### Check Prerequisites
1. Stage 4 complete and verified
2. DAG execution working
3. State machine operational
4. Database storing all workflow state
5. FastAPI backend running

### Expected State
- WebSocket basic functionality working
- Can send messages to UI
- DAG data available in database
- Ready to enhance protocol
- No breaking changes to existing WebSocket usage

## Implementation Tasks

### Task 1: Define WebSocket Event Types
**Objective:** Create typed event schema for all messages

**Implementation:**

Create event type definitions:
```python
from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class WebSocketEventType(str, Enum):
    """Types of WebSocket events"""
    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTED = "reconnected"

    # Workflow lifecycle events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_STATE_CHANGED = "workflow_state_changed"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"

    # Step execution events
    STEP_STARTED = "step_started"
    STEP_PROGRESS = "step_progress"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"

    # DAG events
    DAG_CREATED = "dag_created"
    DAG_UPDATED = "dag_updated"
    DAG_NODE_STATUS_CHANGED = "dag_node_status_changed"

    # Agent events
    AGENT_MESSAGE = "agent_message"
    AGENT_THINKING = "agent_thinking"
    AGENT_TOOL_CALL = "agent_tool_call"

    # Approval events
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RECEIVED = "approval_received"

    # Cost and metrics
    COST_UPDATE = "cost_update"
    METRIC_UPDATE = "metric_update"

    # File events
    FILE_CREATED = "file_created"
    FILE_UPDATED = "file_updated"

    # Error events
    ERROR_OCCURRED = "error_occurred"

    # Heartbeat
    HEARTBEAT = "heartbeat"
    PONG = "pong"

class WebSocketEvent(BaseModel):
    """Base WebSocket event"""
    event_type: WebSocketEventType
    timestamp: datetime
    run_id: Optional[str] = None
    session_id: Optional[str] = None
    data: Dict[str, Any] = {}

    class Config:
        use_enum_values = True

# Specific event data models
class WorkflowStartedData(BaseModel):
    run_id: str
    task_description: str
    agent: str
    model: str

class StepProgressData(BaseModel):
    step_id: str
    step_number: int
    progress_percentage: int
    message: str

class DAGCreatedData(BaseModel):
    run_id: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    levels: int

class DAGNodeStatusChangedData(BaseModel):
    node_id: str
    old_status: str
    new_status: str

class CostUpdateData(BaseModel):
    run_id: str
    step_id: Optional[str]
    model: str
    tokens: int
    cost_usd: float
    total_cost_usd: float

class ErrorOccurredData(BaseModel):
    error_type: str
    message: str
    step_id: Optional[str] = None
    traceback: Optional[str] = None
```

**Files to Create:**
- `backend/websocket_events.py`

**Verification:**
- All event types defined
- Pydantic models validate correctly
- Events serialize to JSON
- Type hints provide IDE support

### Task 2: Implement Event Queue
**Objective:** Queue events for reliable delivery across reconnections

**Implementation:**

```python
from collections import deque
from threading import Lock
from typing import Dict, List
import time

class EventQueue:
    """Thread-safe event queue for WebSocket messages"""

    def __init__(self, max_size: int = 1000, retention_seconds: int = 300):
        """
        Args:
            max_size: Maximum events to keep in queue
            retention_seconds: How long to keep events (default 5 minutes)
        """
        self.max_size = max_size
        self.retention_seconds = retention_seconds
        self.queues: Dict[str, deque] = {}  # run_id -> deque of events
        self.lock = Lock()

    def push(self, run_id: str, event: WebSocketEvent):
        """Add event to queue for run_id"""
        with self.lock:
            if run_id not in self.queues:
                self.queues[run_id] = deque(maxlen=self.max_size)

            # Add timestamp if not present
            if not hasattr(event, 'queued_at'):
                event.queued_at = time.time()

            self.queues[run_id].append(event)

            # Cleanup old events
            self._cleanup_old_events(run_id)

    def get_events_since(self, run_id: str, since_timestamp: float) -> List[WebSocketEvent]:
        """Get all events since timestamp"""
        with self.lock:
            if run_id not in self.queues:
                return []

            events = []
            for event in self.queues[run_id]:
                if event.queued_at > since_timestamp:
                    events.append(event)

            return events

    def get_all_events(self, run_id: str) -> List[WebSocketEvent]:
        """Get all queued events for run_id"""
        with self.lock:
            if run_id not in self.queues:
                return []
            return list(self.queues[run_id])

    def clear(self, run_id: str):
        """Clear queue for run_id"""
        with self.lock:
            if run_id in self.queues:
                del self.queues[run_id]

    def _cleanup_old_events(self, run_id: str):
        """Remove events older than retention period"""
        now = time.time()
        cutoff = now - self.retention_seconds

        queue = self.queues[run_id]
        while queue and queue[0].queued_at < cutoff:
            queue.popleft()

# Global event queue instance
event_queue = EventQueue()
```

**Files to Create:**
- `backend/event_queue.py`

**Verification:**
- Events queued correctly
- Thread-safe operation
- Old events cleaned up
- Can retrieve events since timestamp
- Queue size limited

### Task 3: Create Stateless WebSocket Handler
**Objective:** Backend reads all state from database, no in-memory state

**Implementation:**

Update FastAPI WebSocket handler:
```python
from fastapi import WebSocket, WebSocketDisconnect
from backend.websocket_events import WebSocketEvent, WebSocketEventType
from backend.event_queue import event_queue
from cmbagent.database import get_db_session
from cmbagent.database.models import WorkflowRun
import json
import time

class WebSocketManager:
    """Manages WebSocket connections (stateless)"""

    def __init__(self):
        # Only track active connections, no state
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, run_id: str):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections[run_id] = websocket

        # Send connection event
        event = WebSocketEvent(
            event_type=WebSocketEventType.CONNECTED,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            data={"message": "Connected to workflow"}
        )
        await self.send_event(run_id, event)

        # Send current state from database
        await self.send_current_state(run_id)

    async def disconnect(self, run_id: str):
        """Handle disconnection"""
        if run_id in self.active_connections:
            del self.active_connections[run_id]

    async def send_current_state(self, run_id: str):
        """
        Send current workflow state from database
        Called on new connection to synchronize client
        """
        db = get_db_session()
        try:
            # Load workflow from database
            run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()

            if not run:
                await self.send_event(run_id, WebSocketEvent(
                    event_type=WebSocketEventType.ERROR_OCCURRED,
                    timestamp=datetime.utcnow(),
                    run_id=run_id,
                    data={"error_type": "NotFound", "message": f"Run {run_id} not found"}
                ))
                return

            # Send workflow state
            await self.send_event(run_id, WebSocketEvent(
                event_type=WebSocketEventType.WORKFLOW_STATE_CHANGED,
                timestamp=datetime.utcnow(),
                run_id=run_id,
                data={
                    "status": run.status,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None
                }
            ))

            # Send DAG if exists
            from cmbagent.database.dag_visualizer import DAGVisualizer
            viz = DAGVisualizer(db)
            dag_data = viz.export_for_ui(run_id)

            if dag_data["nodes"]:
                await self.send_event(run_id, WebSocketEvent(
                    event_type=WebSocketEventType.DAG_CREATED,
                    timestamp=datetime.utcnow(),
                    run_id=run_id,
                    data=dag_data
                ))

            # Send queued events (missed during disconnect)
            queued_events = event_queue.get_all_events(run_id)
            for event in queued_events:
                await self.send_event(run_id, event)

        finally:
            db.close()

    async def send_event(self, run_id: str, event: WebSocketEvent):
        """Send event to connected client"""
        # Queue event for later retrieval
        event_queue.push(run_id, event)

        # Send to active connection if exists
        if run_id in self.active_connections:
            try:
                websocket = self.active_connections[run_id]
                await websocket.send_text(event.json())
            except Exception as e:
                # Connection broken, remove from active
                await self.disconnect(run_id)

    async def broadcast_event(self, event: WebSocketEvent):
        """Broadcast event to all connected clients for this run"""
        if event.run_id:
            await self.send_event(event.run_id, event)

# Global WebSocket manager
ws_manager = WebSocketManager()

# FastAPI endpoint
@app.websocket("/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    await ws_manager.connect(websocket, run_id)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle client messages (ping, pause, resume, etc.)
            await handle_client_message(run_id, message)

    except WebSocketDisconnect:
        await ws_manager.disconnect(run_id)

async def handle_client_message(run_id: str, message: dict):
    """Handle messages from client"""
    msg_type = message.get("type")

    if msg_type == "ping":
        # Respond with pong
        await ws_manager.send_event(run_id, WebSocketEvent(
            event_type=WebSocketEventType.PONG,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            data={}
        ))

    elif msg_type == "request_state":
        # Re-send current state
        await ws_manager.send_current_state(run_id)

    elif msg_type == "pause":
        # Pause workflow
        from cmbagent.database.workflow_controller import WorkflowController
        db = get_db_session()
        try:
            controller = WorkflowController(db, message.get("session_id"))
            controller.pause_workflow(run_id)
        finally:
            db.close()

    elif msg_type == "resume":
        # Resume workflow
        from cmbagent.database.workflow_controller import WorkflowController
        db = get_db_session()
        try:
            controller = WorkflowController(db, message.get("session_id"))
            controller.resume_workflow(run_id)
        finally:
            db.close()
```

**Files to Modify:**
- `backend/run.py` (update WebSocket handler)

**Verification:**
- WebSocket accepts connections
- Sends current state on connect
- Queued events delivered
- No in-memory state (all from DB)
- Handles disconnections gracefully
- Client messages processed correctly

### Task 4: Implement Auto-Reconnection in UI
**Objective:** UI automatically reconnects on connection loss

**Implementation:**

Create React hook for resilient WebSocket:
```typescript
// cmbagent-ui/hooks/useResilientWebSocket.ts

import { useState, useEffect, useRef, useCallback } from 'react';

interface WebSocketMessage {
  event_type: string;
  timestamp: string;
  run_id?: string;
  session_id?: string;
  data: any;
}

interface UseResilientWebSocketOptions {
  runId: string;
  onMessage: (message: WebSocketMessage) => void;
  onConnectionChange?: (connected: boolean) => void;
  maxReconnectAttempts?: number;
  initialReconnectDelay?: number;
  maxReconnectDelay?: number;
}

export function useResilientWebSocket({
  runId,
  onMessage,
  onConnectionChange,
  maxReconnectAttempts = 999,
  initialReconnectDelay = 1000,
  maxReconnectDelay = 30000,
}: UseResilientWebSocketOptions) {
  const [connected, setConnected] = useState(false);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const lastMessageTimestamp = useRef<number>(Date.now());

  const connect = useCallback(() => {
    const wsUrl = `ws://localhost:8000/ws/${runId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
      setReconnectAttempt(0);
      onConnectionChange?.(true);

      // Request current state on reconnect
      if (reconnectAttempt > 0) {
        ws.send(JSON.stringify({
          type: 'request_state',
          since: lastMessageTimestamp.current
        }));
      }

      // Start heartbeat
      startHeartbeat(ws);
    };

    ws.onmessage = (event) => {
      const message: WebSocketMessage = JSON.parse(event.data);
      lastMessageTimestamp.current = Date.now();
      onMessage(message);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket closed');
      setConnected(false);
      onConnectionChange?.(false);

      // Attempt reconnection
      if (reconnectAttempt < maxReconnectAttempts) {
        const delay = Math.min(
          initialReconnectDelay * Math.pow(2, reconnectAttempt),
          maxReconnectDelay
        );

        console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempt + 1})`);

        reconnectTimeoutRef.current = setTimeout(() => {
          setReconnectAttempt(prev => prev + 1);
          connect();
        }, delay);
      }
    };

    wsRef.current = ws;
  }, [runId, reconnectAttempt, onMessage, onConnectionChange]);

  const startHeartbeat = (ws: WebSocket) => {
    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000); // Ping every 30 seconds

    // Store interval for cleanup
    wsRef.current.heartbeatInterval = interval;
  };

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      // Cleanup on unmount
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        if (wsRef.current.heartbeatInterval) {
          clearInterval(wsRef.current.heartbeatInterval);
        }
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    connected,
    reconnectAttempt,
    sendMessage,
  };
}
```

**Files to Create:**
- `cmbagent-ui/hooks/useResilientWebSocket.ts`

**Verification:**
- Automatic reconnection on disconnect
- Exponential backoff working
- Heartbeat keeps connection alive
- Can request missed events
- Connection status tracked

### Task 5: Integrate Event Emission with State Machine
**Objective:** Emit WebSocket events on all state changes

**Implementation:**

Update state machine to emit WebSocket events:
```python
from backend.websocket_manager import ws_manager
from backend.websocket_events import WebSocketEvent, WebSocketEventType
from datetime import datetime

# In state_machine.py
class StateMachine:
    def transition_to(self, entity_id: str, new_state: str, reason: Optional[str] = None, transitioned_by: str = "system"):
        # ... existing validation ...

        # Get entity to access run_id
        entity = self.db.query(self.model_class).filter(
            self.model_class.id == entity_id
        ).first()

        # ... perform transition ...

        # Emit WebSocket event
        if self.entity_type == "workflow_run":
            event_type = WebSocketEventType.WORKFLOW_STATE_CHANGED
            run_id = str(entity.id)
        else:  # workflow_step
            event_type = WebSocketEventType.STEP_COMPLETED if new_state == "completed" else WebSocketEventType.STEP_STARTED
            run_id = str(entity.run_id)

        event = WebSocketEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            session_id=str(entity.session_id),
            data={
                "entity_type": self.entity_type,
                "entity_id": str(entity_id),
                "from_state": current_state,
                "to_state": new_state,
                "reason": reason
            }
        )

        # Send via WebSocket (async-safe way)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(ws_manager.broadcast_event(event))
        except RuntimeError:
            # No event loop running (sync context)
            # Queue for later delivery
            from backend.event_queue import event_queue
            event_queue.push(run_id, event)
```

**Files to Modify:**
- `cmbagent/database/state_machine.py` (add WebSocket emission)
- `cmbagent/database/dag_executor.py` (emit DAG events)

**Verification:**
- State changes emit WebSocket events
- Events queued for delivery
- UI receives real-time updates
- Events include all necessary data

### Task 6: Add DAG Real-Time Updates
**Objective:** Stream DAG node status changes to UI

**Implementation:**

Update DAG executor to emit events:
```python
# In dag_executor.py
class DAGExecutor:
    def _execute_node(self, node_info: Dict, agent_executor_func):
        node_id = node_info["id"]
        run_id = node_info["run_id"]

        # Emit node status change: pending -> running
        self._emit_dag_node_event(
            run_id=run_id,
            node_id=node_id,
            old_status="pending",
            new_status="running"
        )

        try:
            # ... execute node ...

            # Emit node status change: running -> completed
            self._emit_dag_node_event(
                run_id=run_id,
                node_id=node_id,
                old_status="running",
                new_status="completed"
            )

        except Exception as e:
            # Emit node status change: running -> failed
            self._emit_dag_node_event(
                run_id=run_id,
                node_id=node_id,
                old_status="running",
                new_status="failed",
                error=str(e)
            )
            raise

    def _emit_dag_node_event(self, run_id: str, node_id: str,
                             old_status: str, new_status: str,
                             error: str = None):
        """Emit DAG node status change event"""
        from backend.websocket_events import WebSocketEvent, WebSocketEventType
        from backend.event_queue import event_queue
        from datetime import datetime

        event = WebSocketEvent(
            event_type=WebSocketEventType.DAG_NODE_STATUS_CHANGED,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            data={
                "node_id": node_id,
                "old_status": old_status,
                "new_status": new_status,
                "error": error
            }
        )

        event_queue.push(run_id, event)
```

**Files to Modify:**
- `cmbagent/database/dag_executor.py` (add event emission)

**Verification:**
- DAG node status changes emit events
- UI can visualize node progress
- Real-time DAG updates working
- Node errors reported to UI

## Files to Create (Summary)

### New Files
```
backend/
├── websocket_events.py          # Event type definitions
├── event_queue.py               # Event queue for reliable delivery
└── websocket_manager.py         # Stateless WebSocket manager

cmbagent-ui/hooks/
└── useResilientWebSocket.ts     # Auto-reconnecting WebSocket hook
```

### Modified Files
- `backend/run.py` - Update WebSocket handler
- `cmbagent/database/state_machine.py` - Emit WebSocket events
- `cmbagent/database/dag_executor.py` - Emit DAG events

## Verification Criteria

### Must Pass
- [ ] WebSocket event types defined
- [ ] Event queue stores events reliably
- [ ] Backend WebSocket handler is stateless
- [ ] UI auto-reconnects on disconnect
- [ ] Current state synced on reconnect
- [ ] Missed events delivered from queue
- [ ] State machine emits WebSocket events
- [ ] DAG node changes emit events
- [ ] Heartbeat prevents timeout
- [ ] Can pause/resume via WebSocket

### Should Pass
- [ ] Exponential backoff working
- [ ] Events properly typed (Pydantic validation)
- [ ] Old events cleaned from queue
- [ ] Multiple clients can connect
- [ ] Connection status visible in UI

### WebSocket Testing
```python
# Test event queue
def test_event_queue():
    queue = EventQueue()
    event = WebSocketEvent(event_type="test", timestamp=datetime.utcnow())
    queue.push("run_123", event)
    events = queue.get_all_events("run_123")
    assert len(events) == 1

# Test event emission
async def test_event_emission():
    await ws_manager.send_event("run_123", event)
    # Verify event in queue
    events = event_queue.get_all_events("run_123")
    assert len(events) > 0

# Test reconnection
async def test_reconnection():
    # Connect
    await ws_manager.connect(websocket, "run_123")
    # Disconnect
    await ws_manager.disconnect("run_123")
    # Reconnect
    await ws_manager.connect(websocket, "run_123")
    # Should receive current state
```

## Testing Checklist

### Unit Tests
```python
# Test WebSocket event serialization
def test_event_serialization():
    event = WebSocketEvent(
        event_type=WebSocketEventType.WORKFLOW_STARTED,
        timestamp=datetime.utcnow(),
        run_id="test",
        data={"task": "Test"}
    )
    json_str = event.json()
    assert "workflow_started" in json_str

# Test event queue thread safety
def test_event_queue_thread_safety():
    queue = EventQueue()
    # Push from multiple threads
    # Verify no data corruption
```

### Integration Tests
```typescript
// Test auto-reconnection
test('auto reconnects on disconnect', async () => {
  const { connected } = useResilientWebSocket({
    runId: 'test',
    onMessage: jest.fn()
  });

  // Simulate disconnect
  // Wait for reconnection
  // Verify connected === true
});

// Test event delivery
test('receives events from backend', async () => {
  const onMessage = jest.fn();
  useResilientWebSocket({ runId: 'test', onMessage });

  // Send event from backend
  // Verify onMessage called
});
```

## Common Issues and Solutions

### Issue 1: Events Lost During Reconnection
**Symptom:** Client misses events during disconnect
**Solution:** Event queue retains events, send on reconnect

### Issue 2: WebSocket Connection Timeout
**Symptom:** Connection dropped after inactivity
**Solution:** Implement heartbeat (ping/pong every 30s)

### Issue 3: Race Condition on State Sync
**Symptom:** UI shows stale state after reconnect
**Solution:** Request current state immediately on reconnect

### Issue 4: Memory Leak from Event Queue
**Symptom:** Event queue grows unbounded
**Solution:** Implement event cleanup based on age

### Issue 5: CORS Issues with WebSocket
**Symptom:** WebSocket connection refused
**Solution:** Configure CORS in FastAPI, allow WebSocket origins

## Rollback Procedure

If enhanced WebSocket causes issues:

1. **Keep old WebSocket code path:**
   ```python
   USE_ENHANCED_WS = os.getenv("CMBAGENT_ENHANCED_WS", "false") == "true"
   ```

2. **Fall back to simple messages:**
   ```python
   # Old way: simple string messages
   await websocket.send_text(f"Step {step_num} completed")
   ```

3. **Disable auto-reconnection in UI:**
   ```typescript
   // Use basic WebSocket without auto-reconnect
   const ws = new WebSocket(url);
   ```

4. **Document issues** for future resolution

## Post-Stage Actions

### Documentation
- Document WebSocket event protocol
- Add event type reference
- Create WebSocket integration guide
- Document reconnection behavior

### Update Progress
- Mark Stage 5 complete in PROGRESS.md
- Note any deviations from plan
- Document time spent
- Update WebSocket lessons learned

### Prepare for Stage 6
- WebSocket protocol enhanced
- Real-time updates working
- Ready to add approval system
- Stage 6 can proceed

## Success Criteria

Stage 5 is complete when:
1. Structured event protocol implemented
2. Auto-reconnection working in UI
3. Backend WebSocket handler stateless
4. Event queue reliably delivers messages
5. DAG updates stream in real-time
6. State synchronized across disconnects
7. Verification checklist 100% complete

## Estimated Time Breakdown

- Event type definitions: 5 min
- Event queue implementation: 7 min
- Stateless WebSocket handler: 10 min
- UI auto-reconnection hook: 8 min
- State machine event emission: 5 min
- DAG real-time updates: 5 min
- Testing and verification: 8 min
- Documentation: 2 min

**Total: 30-40 minutes**

## Next Stage

Once Stage 5 is verified complete, proceed to:
**Stage 6: Human-in-the-Loop Approval System**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
