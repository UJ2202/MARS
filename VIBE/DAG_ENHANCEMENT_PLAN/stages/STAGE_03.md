# Stage 3: Enhanced DAG Node Metadata and UI Integration

**Phase:** 2 - Visualization and Skill Extraction
**Estimated Time:** 60 minutes
**Dependencies:** Stages 1 & 2 must be complete
**Risk Level:** Medium

## Objectives

1. Enrich DAGNode.meta with execution summaries from events
2. Create API endpoints for retrieving execution traces
3. Implement UI components for expandable stage nodes
4. Create execution timeline visualization
5. Display file/message associations in UI
6. Show execution metrics (time, tokens, cost) per stage
7. Enable real-time updates of execution events

## Current State Analysis

### What We Have
- ExecutionEvent table with all event data (from Stage 1)
- Automatic event capture from AG2 (from Stage 2)
- DAGNode table with meta field for JSON data
- Existing DAG visualization in UI (`components/dag/DAGVisualization.tsx`)
- WebSocket real-time updates (from Stage 5)

### What We Need
- API endpoints to retrieve events for a node
- Enhanced DAGNode.meta with execution summary
- UI component to show execution timeline
- Expandable node details in DAG view
- File/message association display
- Real-time event streaming to UI

## Pre-Stage Verification

### Check Prerequisites
1. Stages 1 & 2 complete and verified
2. Events being captured in database
3. DAGNode.meta field available
4. UI DAG visualization working
5. WebSocket connection functional

### Verification Commands
```bash
# Check event capture working
python -c "from cmbagent.execution import get_event_captor; print('Event capture OK' if get_event_captor() else 'Not initialized')"

# Verify events in database
python -c "from cmbagent.database import get_db_session, ExecutionEvent; print(f'Events: {get_db_session().query(ExecutionEvent).count()}')"
```

## Implementation Tasks

### Task 1: Create DAG Metadata Enrichment

**Objective:** Automatically enrich DAGNode.meta with execution summary

**Implementation:**

Create `cmbagent/database/dag_metadata.py`:

```python
"""
DAG Node Metadata Enrichment

Generates execution summaries for DAG nodes from execution events.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from cmbagent.database.models import DAGNode, ExecutionEvent, File, Message
from cmbagent.database.repository import EventRepository


class DAGMetadataEnricher:
    """Enriches DAG node metadata with execution summaries."""
    
    def __init__(self, db_session: Session, session_id: str):
        self.db = db_session
        self.session_id = session_id
        self.event_repo = EventRepository(db_session, session_id)
    
    def enrich_node(self, node_id: str) -> Dict[str, Any]:
        """
        Generate execution summary for a DAG node.
        
        Args:
            node_id: DAG node ID
            
        Returns:
            Dictionary with execution summary
        """
        # Get all events for this node
        events = self.event_repo.list_events_for_node(node_id)
        
        if not events:
            return self._empty_summary()
        
        # Calculate statistics
        stats = self.event_repo.get_event_statistics(events[0].run_id)
        
        # Get files generated
        files = self.db.query(File).filter(File.node_id == node_id).all()
        
        # Get messages
        messages = self.db.query(Message).filter(Message.node_id == node_id).all()
        
        # Build summary
        summary = {
            "execution_summary": {
                "total_events": len(events),
                "event_types": self._count_event_types(events),
                "agents_involved": list(set(e.agent_name for e in events if e.agent_name)),
                "agent_call_counts": self._count_agent_calls(events),
                "files_generated": len(files),
                "files_by_type": self._group_files_by_type(files),
                "messages_count": len(messages),
                "timing": self._calculate_timing(events),
                "cost_summary": self._calculate_cost(events),
                "success_metrics": self._calculate_success_metrics(events)
            }
        }
        
        return summary
    
    def update_node_metadata(self, node_id: str):
        """
        Update DAGNode.meta with execution summary.
        
        Args:
            node_id: DAG node ID
        """
        node = self.db.query(DAGNode).filter(DAGNode.id == node_id).first()
        if not node:
            return
        
        summary = self.enrich_node(node_id)
        
        # Merge with existing metadata
        meta = node.meta or {}
        meta.update(summary)
        
        node.meta = meta
        self.db.commit()
    
    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary structure."""
        return {
            "execution_summary": {
                "total_events": 0,
                "event_types": {},
                "agents_involved": [],
                "agent_call_counts": {},
                "files_generated": 0,
                "files_by_type": {},
                "messages_count": 0,
                "timing": {},
                "cost_summary": {},
                "success_metrics": {}
            }
        }
    
    def _count_event_types(self, events: List[ExecutionEvent]) -> Dict[str, int]:
        """Count events by type."""
        counts = {}
        for event in events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts
    
    def _count_agent_calls(self, events: List[ExecutionEvent]) -> Dict[str, int]:
        """Count agent invocations."""
        counts = {}
        for event in events:
            if event.agent_name and event.event_type == "agent_call":
                counts[event.agent_name] = counts.get(event.agent_name, 0) + 1
        return counts
    
    def _group_files_by_type(self, files: List[File]) -> Dict[str, int]:
        """Group files by type."""
        groups = {}
        for file in files:
            groups[file.file_type] = groups.get(file.file_type, 0) + 1
        return groups
    
    def _calculate_timing(self, events: List[ExecutionEvent]) -> Dict[str, Any]:
        """Calculate timing metrics."""
        if not events:
            return {}
        
        # Find earliest and latest timestamps
        timestamps = [e.timestamp for e in events if e.timestamp]
        if not timestamps:
            return {}
        
        started_at = min(timestamps)
        completed_at = max(timestamps)
        duration = (completed_at - started_at).total_seconds()
        
        # Calculate agent time breakdown
        agent_times = {}
        for event in events:
            if event.agent_name and event.duration_ms:
                agent_times[event.agent_name] = \
                    agent_times.get(event.agent_name, 0) + (event.duration_ms / 1000)
        
        return {
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": duration,
            "agent_time_breakdown": agent_times
        }
    
    def _calculate_cost(self, events: List[ExecutionEvent]) -> Dict[str, Any]:
        """Calculate cost metrics from event metadata."""
        total_tokens = 0
        total_cost = 0.0
        by_agent = {}
        
        for event in events:
            meta = event.meta or {}
            tokens = meta.get("tokens", 0)
            cost = meta.get("cost_usd", 0.0)
            
            total_tokens += tokens
            total_cost += cost
            
            if event.agent_name and (tokens > 0 or cost > 0):
                if event.agent_name not in by_agent:
                    by_agent[event.agent_name] = {"tokens": 0, "cost": 0.0}
                by_agent[event.agent_name]["tokens"] += tokens
                by_agent[event.agent_name]["cost"] += cost
        
        return {
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "by_agent": by_agent
        }
    
    def _calculate_success_metrics(self, events: List[ExecutionEvent]) -> Dict[str, Any]:
        """Calculate success/failure metrics."""
        completed = sum(1 for e in events if e.status == "completed")
        failed = sum(1 for e in events if e.status == "failed")
        errors = sum(1 for e in events if e.event_type == "error")
        
        total = len(events)
        completion_rate = completed / total if total > 0 else 0
        
        return {
            "completion_rate": completion_rate,
            "error_count": errors,
            "failed_count": failed,
            "completed_count": completed
        }
```

**Files to Create:**
- `cmbagent/database/dag_metadata.py`

**Verification:**
- DAGMetadataEnricher creates summaries
- Execution summary has all fields
- Node metadata updates correctly

### Task 2: Create Backend API Endpoints

**Objective:** Add endpoints for retrieving execution events

**Implementation:**

Edit `backend/main.py` - Add event retrieval endpoints:

```python
# Add to imports
from cmbagent.database import EventRepository
from cmbagent.database.dag_metadata import DAGMetadataEnricher

# Add new endpoint for node events
@app.get("/api/nodes/{node_id}/events")
async def get_node_events(node_id: str, event_type: Optional[str] = None):
    """Get execution events for a DAG node."""
    try:
        db = get_db_session()
        session_id = get_or_create_session(db)
        event_repo = EventRepository(db, session_id)
        
        events = event_repo.list_events_for_node(node_id, event_type=event_type)
        
        # Convert to JSON-serializable format
        events_data = [
            {
                "id": e.id,
                "event_type": e.event_type,
                "event_subtype": e.event_subtype,
                "agent_name": e.agent_name,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "duration_ms": e.duration_ms,
                "execution_order": e.execution_order,
                "depth": e.depth,
                "inputs": e.inputs,
                "outputs": e.outputs,
                "error_message": e.error_message,
                "status": e.status,
                "meta": e.meta,
                "parent_event_id": e.parent_event_id
            }
            for e in events
        ]
        
        db.close()
        
        return {
            "node_id": node_id,
            "total_events": len(events_data),
            "events": events_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/nodes/{node_id}/execution-summary")
async def get_node_execution_summary(node_id: str):
    """Get execution summary for a DAG node."""
    try:
        db = get_db_session()
        session_id = get_or_create_session(db)
        enricher = DAGMetadataEnricher(db, session_id)
        
        summary = enricher.enrich_node(node_id)
        db.close()
        
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/nodes/{node_id}/files")
async def get_node_files(node_id: str):
    """Get files generated by a DAG node."""
    try:
        db = get_db_session()
        
        files = db.query(File).filter(File.node_id == node_id).all()
        
        files_data = [
            {
                "id": f.id,
                "file_path": f.file_path,
                "file_type": f.file_type,
                "size_bytes": f.size_bytes,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "event_id": f.event_id
            }
            for f in files
        ]
        
        db.close()
        
        return {
            "node_id": node_id,
            "total_files": len(files_data),
            "files": files_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/events/{event_id}/tree")
async def get_event_tree(event_id: str):
    """Get event tree (nested events) from root event."""
    try:
        db = get_db_session()
        session_id = get_or_create_session(db)
        event_repo = EventRepository(db, session_id)
        
        tree = event_repo.get_event_tree(event_id)
        
        tree_data = [
            {
                "id": e.id,
                "event_type": e.event_type,
                "agent_name": e.agent_name,
                "execution_order": e.execution_order,
                "depth": e.depth,
                "parent_event_id": e.parent_event_id
            }
            for e in tree
        ]
        
        db.close()
        
        return {
            "root_event_id": event_id,
            "total_events": len(tree_data),
            "tree": tree_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Files to Modify:**
- `backend/main.py` (add event endpoints)

**Verification:**
- Endpoints return event data
- JSON serialization works
- Error handling correct

### Task 3: Create UI Execution Timeline Component

**Objective:** Visualize execution events as timeline

**Implementation:**

Create `cmbagent-ui/components/dag/ExecutionTimeline.tsx`:

```typescript
import React from 'react';
import { format } from 'date-fns';

interface ExecutionEvent {
  id: string;
  event_type: string;
  event_subtype?: string;
  agent_name?: string;
  timestamp: string;
  duration_ms?: number;
  execution_order: number;
  depth: number;
  status: string;
  inputs?: any;
  outputs?: any;
  error_message?: string;
}

interface ExecutionTimelineProps {
  events: ExecutionEvent[];
  onEventClick?: (event: ExecutionEvent) => void;
}

export default function ExecutionTimeline({ events, onEventClick }: ExecutionTimelineProps) {
  const getEventColor = (eventType: string) => {
    const colors: Record<string, string> = {
      agent_call: 'bg-blue-500',
      tool_call: 'bg-purple-500',
      code_exec: 'bg-green-500',
      file_gen: 'bg-yellow-500',
      handoff: 'bg-orange-500',
      error: 'bg-red-500',
    };
    return colors[eventType] || 'bg-gray-500';
  };

  const getEventIcon = (eventType: string) => {
    const icons: Record<string, string> = {
      agent_call: '🤖',
      tool_call: '🔧',
      code_exec: '💻',
      file_gen: '📄',
      handoff: '↔️',
      error: '❌',
    };
    return icons[eventType] || '•';
  };

  return (
    <div className="execution-timeline p-4">
      <h3 className="text-lg font-semibold mb-4">Execution Timeline</h3>
      
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gray-300" />
        
        {/* Events */}
        <div className="space-y-4">
          {events.map((event, index) => (
            <div
              key={event.id}
              className={`relative flex items-start cursor-pointer hover:bg-gray-50 p-2 rounded`}
              style={{ marginLeft: `${event.depth * 20}px` }}
              onClick={() => onEventClick?.(event)}
            >
              {/* Event dot */}
              <div className={`absolute left-4 w-4 h-4 rounded-full ${getEventColor(event.event_type)} flex items-center justify-center text-white text-xs z-10`}>
                {getEventIcon(event.event_type)}
              </div>
              
              {/* Event content */}
              <div className="ml-12 flex-1">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="font-medium">{event.event_type}</span>
                    {event.event_subtype && (
                      <span className="ml-2 text-sm text-gray-500">({event.event_subtype})</span>
                    )}
                    {event.agent_name && (
                      <span className="ml-2 text-sm text-blue-600">@ {event.agent_name}</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500">
                    {event.timestamp && format(new Date(event.timestamp), 'HH:mm:ss.SSS')}
                  </div>
                </div>
                
                {event.duration_ms && (
                  <div className="text-xs text-gray-500 mt-1">
                    Duration: {event.duration_ms}ms
                  </div>
                )}
                
                {event.error_message && (
                  <div className="text-xs text-red-600 mt-1">
                    Error: {event.error_message}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {events.length === 0 && (
        <div className="text-center text-gray-500 py-8">
          No execution events yet
        </div>
      )}
    </div>
  );
}
```

**Files to Create:**
- `cmbagent-ui/components/dag/ExecutionTimeline.tsx`

**Verification:**
- Timeline renders events
- Events colored by type
- Nested events indented
- Click handler works

### Task 4: Enhance DAGVisualization Component

**Objective:** Make nodes expandable to show execution details

**Implementation:**

Edit `cmbagent-ui/components/dag/DAGVisualization.tsx`:

```typescript
// Add import
import ExecutionTimeline from './ExecutionTimeline';
import { useState } from 'react';

// Add state for selected node and events
const [selectedNode, setSelectedNode] = useState<string | null>(null);
const [nodeEvents, setNodeEvents] = useState<any[]>([]);
const [showTimeline, setShowTimeline] = useState(false);

// Add function to fetch node events
const fetchNodeEvents = async (nodeId: string) => {
  try {
    const response = await fetch(`http://localhost:8000/api/nodes/${nodeId}/events`);
    const data = await response.json();
    setNodeEvents(data.events || []);
    setSelectedNode(nodeId);
    setShowTimeline(true);
  } catch (error) {
    console.error('Failed to fetch node events:', error);
  }
};

// Add to node onClick handler
const handleNodeClick = (nodeId: string) => {
  onNodeSelect?.(nodeId);
  fetchNodeEvents(nodeId);
};

// Add timeline panel
{showTimeline && (
  <div className="absolute right-0 top-0 w-96 h-full bg-white border-l shadow-lg overflow-y-auto z-50">
    <div className="p-4 border-b flex justify-between items-center">
      <h2 className="font-semibold">Node Details: {selectedNode}</h2>
      <button onClick={() => setShowTimeline(false)} className="text-gray-500 hover:text-gray-700">
        ✕
      </button>
    </div>
    <ExecutionTimeline 
      events={nodeEvents}
      onEventClick={(event) => console.log('Event clicked:', event)}
    />
  </div>
)}
```

**Files to Modify:**
- `cmbagent-ui/components/dag/DAGVisualization.tsx`

**Verification:**
- Clicking node shows timeline
- Timeline panel slides in
- Events load correctly

### Task 5: Add WebSocket Event Streaming

**Objective:** Stream execution events to UI in real-time

**Implementation:**

Edit `backend/websocket_events.py` - Add event streaming:

```python
# Add new event type
class EventCaptured(BaseModel):
    """Event captured during execution"""
    event_id: str
    node_id: Optional[str]
    event_type: str
    event_subtype: Optional[str]
    agent_name: Optional[str]
    timestamp: str
    execution_order: int

async def emit_event_captured(
    websocket: WebSocket,
    event_id: str,
    node_id: Optional[str],
    event_type: str,
    run_id: str,
    **kwargs
):
    """Emit event_captured event."""
    await send_ws_event(
        websocket,
        "event_captured",
        EventCaptured(
            event_id=event_id,
            node_id=node_id,
            event_type=event_type,
            **kwargs
        ).dict(),
        run_id=run_id
    )
```

Integrate with EventCaptureManager:

```python
# In cmbagent/execution/event_capture.py
# Add websocket parameter to __init__
def __init__(self, ..., websocket=None):
    self.websocket = websocket

# In _create_event, add:
if self.websocket:
    asyncio.create_task(self._emit_event_websocket(event))

async def _emit_event_websocket(self, event):
    """Emit event via WebSocket."""
    from backend.websocket_events import emit_event_captured
    await emit_event_captured(
        self.websocket,
        event_id=event.id,
        node_id=event.node_id,
        event_type=event.event_type,
        event_subtype=event.event_subtype,
        agent_name=event.agent_name,
        timestamp=event.timestamp.isoformat(),
        execution_order=event.execution_order,
        run_id=self.run_id
    )
```

**Files to Modify:**
- `backend/websocket_events.py`
- `cmbagent/execution/event_capture.py`

**Verification:**
- Events stream to UI in real-time
- Timeline updates live
- No significant lag

## Verification Criteria

### Must Pass
- [ ] DAGMetadataEnricher generates summaries
- [ ] API endpoints return event data
- [ ] ExecutionTimeline component renders
- [ ] Nodes expandable in DAG view
- [ ] Events displayed in timeline
- [ ] Files/messages linked to events
- [ ] Real-time event streaming works
- [ ] Performance acceptable (< 100ms UI updates)

## Files Summary

### New Files
```
cmbagent/database/dag_metadata.py
cmbagent-ui/components/dag/ExecutionTimeline.tsx
```

### Modified Files
```
backend/main.py
backend/websocket_events.py
cmbagent/execution/event_capture.py
cmbagent-ui/components/dag/DAGVisualization.tsx
```

## Next Stage

Proceed to **Stage 4: Skill Extraction and Pattern Recognition** to enable learning from captured workflows.
