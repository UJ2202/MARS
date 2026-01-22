"""
Connection Manager for CMBAgent Backend.

This module provides WebSocket connection management that integrates
with the Stage 5 WebSocket protocol and event system.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import WebSocket

# Try to import from parent directory
try:
    from websocket_events import (
        WebSocketEvent,
        WebSocketEventType,
        create_workflow_started_event,
        create_workflow_state_changed_event,
        create_workflow_completed_event,
        create_dag_created_event,
        create_dag_node_status_changed_event,
        create_error_event,
    )
    from event_queue import event_queue
except ImportError:
    # Define minimal stubs if import fails
    class WebSocketEvent:
        def __init__(self, event_type=None, timestamp=None, run_id=None, session_id=None, data=None, **kwargs):
            self.event_type = event_type
            self.timestamp = timestamp or datetime.now(timezone.utc)
            self.run_id = run_id
            self.session_id = session_id
            self.data = data or {}
        
        def dict(self):
            return {
                "event_type": self.event_type.value if hasattr(self.event_type, 'value') else self.event_type,
                "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, 'isoformat') else str(self.timestamp),
                "run_id": self.run_id,
                "session_id": self.session_id,
                "data": self.data
            }
    
    class WebSocketEventType:
        WORKFLOW_STARTED = "workflow_started"
        WORKFLOW_STATE_CHANGED = "workflow_state_changed"
        WORKFLOW_COMPLETED = "workflow_completed"
        WORKFLOW_FAILED = "workflow_failed"
        WORKFLOW_PAUSED = "workflow_paused"
        WORKFLOW_RESUMED = "workflow_resumed"
        DAG_CREATED = "dag_created"
        DAG_NODE_STATUS_CHANGED = "dag_node_status_changed"
        ERROR = "error"
        OUTPUT = "output"
        PONG = "pong"
        STATUS = "status"
    
    def create_workflow_started_event(*args, **kwargs): return None
    def create_workflow_state_changed_event(*args, **kwargs): return None
    def create_workflow_completed_event(*args, **kwargs): return None
    def create_dag_created_event(*args, **kwargs): return None
    def create_dag_node_status_changed_event(*args, **kwargs): return None
    def create_error_event(*args, **kwargs): return None
    
    class EventQueue:
        def push(self, *args, **kwargs): pass
        def get_since(self, *args, **kwargs): return []
    event_queue = EventQueue()


class ConnectionManager:
    """
    Manages WebSocket connections with event queue integration.
    
    This is a stateless manager that:
    - Tracks active WebSocket connections
    - Sends events through the standardized protocol
    - Integrates with the event queue for reliable delivery
    - Supports reconnection with event replay
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        # Track active connections: {task_id: WebSocket}
        self._connections: Dict[str, WebSocket] = {}
        # Track connection metadata: {task_id: {connected_at, last_message_at, ...}}
        self._connection_meta: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str) -> bool:
        """
        Register a WebSocket connection (already accepted).
        
        Args:
            websocket: FastAPI WebSocket instance (already accepted)
            task_id: Task identifier for this connection
            
        Returns:
            True if connection registered successfully
        """
        try:
            # Note: websocket.accept() should already be called by the endpoint
            self._connections[task_id] = websocket
            self._connection_meta[task_id] = {
                "connected_at": datetime.now(timezone.utc),
                "last_message_at": datetime.now(timezone.utc),
            }
            
            print(f"[ConnectionManager] Registered connection for task {task_id}")
            return True
            
        except Exception as e:
            print(f"[ConnectionManager] Error registering connection: {e}")
            return False
    
    async def disconnect(self, task_id: str):
        """
        Handle disconnection for a task.
        
        Args:
            task_id: Task identifier
        """
        if task_id in self._connections:
            del self._connections[task_id]
        if task_id in self._connection_meta:
            del self._connection_meta[task_id]
    
    def is_connected(self, task_id: str) -> bool:
        """Check if a task has an active connection."""
        return task_id in self._connections
    
    async def send_event(
        self,
        task_id: str,
        event: WebSocketEvent,
        queue_if_disconnected: bool = True
    ) -> bool:
        """
        Send a WebSocket event to a client.
        
        Args:
            task_id: Task identifier
            event: WebSocket event to send
            queue_if_disconnected: Whether to queue event if client is disconnected
            
        Returns:
            True if event was sent or queued successfully
        """
        # Always queue the event for replay on reconnection
        if queue_if_disconnected:
            event_queue.push(task_id, event)
        
        # Try to send to active connection
        if task_id in self._connections:
            try:
                websocket = self._connections[task_id]
                
                # Serialize event to JSON
                try:
                    event_dict = event.model_dump()
                except AttributeError:
                    event_dict = event.dict()
                
                # Convert datetime to ISO string
                if isinstance(event_dict.get("timestamp"), datetime):
                    event_dict["timestamp"] = event_dict["timestamp"].isoformat() + "Z"
                
                await websocket.send_json(event_dict)
                
                # Update last message timestamp
                if task_id in self._connection_meta:
                    self._connection_meta[task_id]["last_message_at"] = datetime.now(timezone.utc)
                
                return True
                
            except Exception as e:
                print(f"[ConnectionManager] Error sending event: {e}")
                # Connection broken, clean up
                await self.disconnect(task_id)
                return False
        
        return queue_if_disconnected  # Event was queued
    
    async def send_json(self, task_id: str, data: Dict[str, Any]) -> bool:
        """
        Send raw JSON data (for backward compatibility).
        
        Args:
            task_id: Task identifier
            data: JSON-serializable dictionary
            
        Returns:
            True if sent successfully
        """
        if task_id in self._connections:
            try:
                websocket = self._connections[task_id]
                await websocket.send_json(data)
                return True
            except Exception as e:
                print(f"[ConnectionManager] Error sending JSON: {e}")
                await self.disconnect(task_id)
                return False
        return False
    
    async def send_output(self, task_id: str, message: str):
        """
        Send an output message (convenience method).
        
        Args:
            task_id: Task identifier
            message: Output message text
        """
        event = WebSocketEvent(
            event_type=WebSocketEventType.AGENT_MESSAGE,
            timestamp=datetime.now(timezone.utc),
            run_id=task_id,
            data={"message": message}
        )
        await self.send_event(task_id, event)
    
    async def send_status(self, task_id: str, status: str, message: str = None):
        """
        Send a status update.
        
        Args:
            task_id: Task identifier
            status: Status string
            message: Optional status message
        """
        event = WebSocketEvent(
            event_type=WebSocketEventType.WORKFLOW_STATE_CHANGED,
            timestamp=datetime.now(timezone.utc),
            run_id=task_id,
            data={"status": status, "message": message or status}
        )
        await self.send_event(task_id, event)
    
    async def send_error(self, task_id: str, error_type: str, message: str, traceback: str = None):
        """
        Send an error event.
        
        Args:
            task_id: Task identifier
            error_type: Type of error
            message: Error message
            traceback: Optional traceback string
        """
        event = create_error_event(
            run_id=task_id,
            error_type=error_type,
            message=message,
            traceback=traceback
        )
        await self.send_event(task_id, event)
    
    async def send_workflow_started(
        self,
        task_id: str,
        task_description: str,
        agent: str,
        model: str
    ):
        """Send workflow started event."""
        event = create_workflow_started_event(
            run_id=task_id,
            task_description=task_description,
            agent=agent,
            model=model
        )
        await self.send_event(task_id, event)
    
    async def send_workflow_completed(self, task_id: str, results: Dict[str, Any] = None):
        """Send workflow completed event."""
        event = create_workflow_completed_event(
            run_id=task_id,
            results=results or {}
        )
        await self.send_event(task_id, event)
    
    async def send_dag_created(
        self,
        task_id: str,
        nodes: list,
        edges: list,
        levels: int = 1
    ):
        """Send DAG created event."""
        event = create_dag_created_event(
            run_id=task_id,
            nodes=nodes,
            edges=edges,
            levels=levels
        )
        await self.send_event(task_id, event)
    
    async def send_dag_node_status_changed(
        self,
        task_id: str,
        node_id: str,
        old_status: str,
        new_status: str
    ):
        """Send DAG node status change event."""
        event = create_dag_node_status_changed_event(
            run_id=task_id,
            node_id=node_id,
            old_status=old_status,
            new_status=new_status
        )
        await self.send_event(task_id, event)
    
    async def send_workflow_paused(self, task_id: str, message: str = "Workflow paused"):
        """Send workflow paused event."""
        event = WebSocketEvent(
            event_type=WebSocketEventType.WORKFLOW_PAUSED,
            timestamp=datetime.now(timezone.utc),
            run_id=task_id,
            data={"message": message, "status": "paused"}
        )
        await self.send_event(task_id, event)
    
    async def send_workflow_resumed(self, task_id: str, message: str = "Workflow resumed"):
        """Send workflow resumed event."""
        event = WebSocketEvent(
            event_type=WebSocketEventType.WORKFLOW_RESUMED,
            timestamp=datetime.now(timezone.utc),
            run_id=task_id,
            data={"message": message, "status": "executing"}
        )
        await self.send_event(task_id, event)
    
    async def send_workflow_cancelled(self, task_id: str, message: str = "Workflow cancelled"):
        """Send workflow cancelled event."""
        event = WebSocketEvent(
            event_type=WebSocketEventType.WORKFLOW_FAILED,
            timestamp=datetime.now(timezone.utc),
            run_id=task_id,
            data={"message": message, "status": "cancelled"}
        )
        await self.send_event(task_id, event)
    
    async def send_pong(self, task_id: str):
        """Send pong response to ping."""
        event = WebSocketEvent(
            event_type=WebSocketEventType.PONG,
            timestamp=datetime.now(timezone.utc),
            run_id=task_id,
            data={}
        )
        await self.send_event(task_id, event, queue_if_disconnected=False)
    
    async def replay_missed_events(self, task_id: str, since_timestamp: float = None):
        """
        Replay events that were missed during disconnection.
        
        Args:
            task_id: Task identifier
            since_timestamp: Replay events after this timestamp
        """
        if since_timestamp:
            events = event_queue.get_events_since(task_id, since_timestamp)
        else:
            events = event_queue.get_all_events(task_id)
        
        for event in events:
            await self.send_event(task_id, event, queue_if_disconnected=False)
    
    def get_websocket(self, task_id: str) -> Optional[WebSocket]:
        """Get the WebSocket instance for a task (for legacy compatibility)."""
        return self._connections.get(task_id)


# Global connection manager instance
connection_manager = ConnectionManager()
