"""
Event Capture Manager for AG2 Workflow Tracing

Automatically captures all execution events from AG2 agents including:
- Agent calls and messages
- Tool/function invocations
- Code execution
- File generation
- Agent handoffs
- State transitions
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from threading import Lock
import time
import asyncio

from cmbagent.database import EventRepository, ExecutionEvent
from cmbagent.database.models import File, Message


class EventCaptureManager:
    """
    Central manager for capturing execution events.
    Thread-safe and designed for minimal performance overhead.
    """
    
    def __init__(
        self,
        db_session: Session,
        run_id: str,
        session_id: str,
        enabled: bool = True,
        buffer_size: int = 50,
        websocket = None
    ):
        """
        Initialize event capture manager.
        
        Args:
            db_session: Database session
            run_id: Workflow run ID
            session_id: Session ID for isolation
            enabled: Whether event capture is enabled
            buffer_size: Number of events to buffer before flush
            websocket: Optional WebSocket connection for real-time streaming
        """
        self.db = db_session
        self.run_id = run_id
        self.session_id = session_id
        self.enabled = enabled
        self.buffer_size = buffer_size
        self.websocket = websocket
        
        # Event repository
        self.event_repo = EventRepository(db_session, session_id)
        
        # Context tracking
        self.current_node_id: Optional[str] = None
        self.current_step_id: Optional[str] = None
        self.execution_order = 0
        
        # Event buffer for batch writes
        self.event_buffer: List[ExecutionEvent] = []
        self.buffer_lock = Lock()
        
        # Performance tracking
        self.total_events = 0
        self.total_capture_time_ms = 0
        
        # Event ID stack for nested events
        self.event_stack: List[str] = []
    
    def set_context(self, node_id: Optional[str] = None, step_id: Optional[str] = None):
        """
        Update current execution context.
        
        Args:
            node_id: Current DAG node ID
            step_id: Current workflow step ID
        """
        if node_id:
            self.current_node_id = node_id
            self.execution_order = 0  # Reset order for new node
        
        if step_id:
            self.current_step_id = step_id
    
    def capture_agent_call(
        self,
        agent_name: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Capture agent invocation.
        
        Args:
            agent_name: Name of the agent being called
            message: Message/task being sent to agent
            context: Execution context
            metadata: Additional metadata (model, temperature, etc.)
            
        Returns:
            Event ID if captured, None otherwise
        """
        if not self.enabled:
            return None
        
        start_time = time.time()
        
        try:
            event = self._create_event(
                event_type="agent_call",
                event_subtype="start",
                agent_name=agent_name,
                inputs={
                    "message": message,
                    "context": context or {}
                },
                meta=metadata or {}
            )
            
            # Push to event stack for nested tracking
            self.event_stack.append(event.id)
            
            self._track_performance(start_time)
            return event.id
            
        except Exception as e:
            print(f"Error capturing agent_call event: {e}")
            return None
    
    def capture_agent_response(
        self,
        agent_name: str,
        response: str,
        event_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Capture agent response/completion.
        
        Args:
            agent_name: Name of the agent
            response: Agent's response
            event_id: Original agent_call event ID
            metadata: Additional metadata (tokens, cost, etc.)
        """
        if not self.enabled:
            return
        
        try:
            if event_id:
                # Update existing event
                self.event_repo.update_event(
                    event_id,
                    event_subtype="complete",
                    completed_at=datetime.now(timezone.utc),
                    outputs={"response": response},
                    meta=metadata or {}
                )
                
                # Pop from event stack
                if self.event_stack and self.event_stack[-1] == event_id:
                    self.event_stack.pop()
            else:
                # Create new complete event
                self._create_event(
                    event_type="agent_call",
                    event_subtype="complete",
                    agent_name=agent_name,
                    outputs={"response": response},
                    meta=metadata or {}
                )
        
        except Exception as e:
            print(f"Error capturing agent response: {e}")
    
    def capture_tool_call(
        self,
        agent_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Capture tool/function invocation.
        
        Args:
            agent_name: Agent calling the tool
            tool_name: Name of the tool/function
            arguments: Tool arguments
            result: Tool result (if available)
            metadata: Additional metadata
            
        Returns:
            Event ID if captured
        """
        if not self.enabled:
            return None
        
        try:
            parent_event_id = self.event_stack[-1] if self.event_stack else None
            
            event = self._create_event(
                event_type="tool_call",
                event_subtype="execute",
                agent_name=agent_name,
                parent_event_id=parent_event_id,
                depth=len(self.event_stack),
                inputs={
                    "tool_name": tool_name,
                    "arguments": arguments
                },
                outputs={"result": result} if result is not None else None,
                meta=metadata or {}
            )
            
            return event.id
            
        except Exception as e:
            print(f"Error capturing tool_call event: {e}")
            return None
    
    def capture_code_execution(
        self,
        agent_name: str,
        code: str,
        language: str = "python",
        result: Optional[str] = None,
        exit_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Capture code execution.
        
        Args:
            agent_name: Agent executing the code
            code: Code being executed
            language: Programming language
            result: Execution result (stdout/stderr)
            exit_code: Exit code
            duration_ms: Execution duration in milliseconds
            metadata: Additional metadata
            
        Returns:
            Event ID if captured
        """
        if not self.enabled:
            return None
        
        try:
            parent_event_id = self.event_stack[-1] if self.event_stack else None
            
            meta = metadata or {}
            meta.update({
                "language": language,
                "exit_code": exit_code,
                "code_length": len(code)
            })
            
            event = self._create_event(
                event_type="code_exec",
                event_subtype="complete" if exit_code == 0 else "error",
                agent_name=agent_name,
                parent_event_id=parent_event_id,
                depth=len(self.event_stack),
                inputs={"code": code[:1000]},  # Truncate long code
                outputs={"result": result[:5000] if result else None},  # Truncate output
                duration_ms=duration_ms,
                meta=meta
            )
            
            return event.id
            
        except Exception as e:
            print(f"Error capturing code_exec event: {e}")
            return None
    
    def capture_file_generation(
        self,
        agent_name: str,
        file_path: str,
        file_type: str,
        size_bytes: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Capture file generation.
        
        Args:
            agent_name: Agent that generated the file
            file_path: Path to generated file
            file_type: Type of file (code, data, plot, etc.)
            size_bytes: File size in bytes
            metadata: Additional metadata
            
        Returns:
            Event ID if captured
        """
        if not self.enabled:
            return None
        
        try:
            parent_event_id = self.event_stack[-1] if self.event_stack else None
            
            event = self._create_event(
                event_type="file_gen",
                event_subtype="create",
                agent_name=agent_name,
                parent_event_id=parent_event_id,
                depth=len(self.event_stack),
                inputs={
                    "file_path": file_path,
                    "file_type": file_type
                },
                meta={
                    "size_bytes": size_bytes,
                    **(metadata or {})
                }
            )
            
            # Create File record with event linkage
            file_record = File(
                run_id=self.run_id,
                step_id=self.current_step_id,
                event_id=event.id,
                node_id=self.current_node_id,
                file_path=file_path,
                file_type=file_type,
                size_bytes=size_bytes
            )
            self.db.add(file_record)
            self.db.commit()
            
            return event.id
            
        except Exception as e:
            print(f"Error capturing file_gen event: {e}")
            return None
    
    def capture_handoff(
        self,
        from_agent: str,
        to_agent: str,
        context: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None
    ) -> Optional[str]:
        """
        Capture agent handoff/transition.
        
        Args:
            from_agent: Source agent
            to_agent: Destination agent
            context: Context being transferred
            reason: Reason for handoff
            
        Returns:
            Event ID if captured
        """
        if not self.enabled:
            return None
        
        try:
            event = self._create_event(
                event_type="handoff",
                event_subtype="transfer",
                agent_name=from_agent,
                inputs={
                    "from_agent": from_agent,
                    "to_agent": to_agent,
                    "context": context or {}
                },
                meta={"reason": reason} if reason else {}
            )
            
            return event.id
            
        except Exception as e:
            print(f"Error capturing handoff event: {e}")
            return None
    
    def capture_message(
        self,
        sender: str,
        recipient: str,
        content: str,
        tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Capture agent-to-agent message.
        
        Args:
            sender: Message sender
            recipient: Message recipient
            content: Message content
            tokens: Token count
            metadata: Additional metadata
            
        Returns:
            Event ID if captured
        """
        if not self.enabled:
            return None
        
        try:
            parent_event_id = self.event_stack[-1] if self.event_stack else None
            
            event = self._create_event(
                event_type="agent_call",
                event_subtype="message",
                agent_name=recipient,
                parent_event_id=parent_event_id,
                depth=len(self.event_stack),
                inputs={
                    "sender": sender,
                    "recipient": recipient,
                    "content": content[:1000]  # Truncate long messages
                },
                meta={
                    "tokens": tokens,
                    **(metadata or {})
                }
            )
            
            # Create Message record with event linkage
            message_record = Message(
                run_id=self.run_id,
                step_id=self.current_step_id,
                event_id=event.id,
                node_id=self.current_node_id,
                sender=sender,
                recipient=recipient,
                content=content,
                tokens=tokens
            )
            self.db.add(message_record)
            self.db.commit()
            
            return event.id
            
        except Exception as e:
            print(f"Error capturing message event: {e}")
            return None
    
    def capture_error(
        self,
        agent_name: str,
        error_message: str,
        error_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Capture error event.
        
        Args:
            agent_name: Agent where error occurred
            error_message: Error message
            error_type: Type of error
            metadata: Additional metadata
            
        Returns:
            Event ID if captured
        """
        if not self.enabled:
            return None
        
        try:
            parent_event_id = self.event_stack[-1] if self.event_stack else None
            
            event = self._create_event(
                event_type="error",
                event_subtype=error_type or "runtime_error",
                agent_name=agent_name,
                parent_event_id=parent_event_id,
                depth=len(self.event_stack),
                error_message=error_message,
                status="failed",
                meta=metadata or {}
            )
            
            return event.id
            
        except Exception as e:
            print(f"Error capturing error event: {e}")
            return None
    
    def _create_event(
        self,
        event_type: str,
        event_subtype: Optional[str] = None,
        agent_name: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        depth: int = 0,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        status: str = "completed",
        duration_ms: Optional[int] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> ExecutionEvent:
        """
        Internal method to create an execution event.
        
        Returns:
            Created ExecutionEvent instance
        """
        with self.buffer_lock:
            event = self.event_repo.create_event(
                run_id=self.run_id,
                node_id=self.current_node_id,
                step_id=self.current_step_id,
                parent_event_id=parent_event_id,
                event_type=event_type,
                event_subtype=event_subtype,
                agent_name=agent_name,
                execution_order=self.execution_order,
                depth=depth,
                inputs=inputs,
                outputs=outputs,
                error_message=error_message,
                status=status,
                duration_ms=duration_ms,
                meta=meta
            )
            
            self.execution_order += 1
            self.total_events += 1
            
            # Emit event via WebSocket if available
            if self.websocket:
                try:
                    asyncio.create_task(self._emit_event_websocket(event))
                except RuntimeError:
                    # If no event loop, skip websocket emission
                    pass
            
            return event
    
    async def _emit_event_websocket(self, event: ExecutionEvent):
        """Emit event via WebSocket."""
        try:
            # Import here to avoid circular dependencies
            import sys
            from pathlib import Path
            backend_path = Path(__file__).parent.parent.parent / "backend"
            if str(backend_path) not in sys.path:
                sys.path.insert(0, str(backend_path))
            
            from websocket_events import create_event_captured_event
            from websocket_manager import send_ws_event
            
            ws_event = create_event_captured_event(
                run_id=self.run_id,
                event_id=event.id,
                event_type=event.event_type,
                execution_order=event.execution_order,
                timestamp=event.timestamp.isoformat() if event.timestamp else datetime.now(timezone.utc).isoformat(),
                node_id=event.node_id,
                event_subtype=event.event_subtype,
                agent_name=event.agent_name,
                depth=event.depth
            )
            
            await send_ws_event(
                self.websocket,
                ws_event.event_type,
                ws_event.data,
                run_id=self.run_id
            )
        except Exception as e:
            # Silently ignore websocket errors to not break event capture
            pass
    
    def _track_performance(self, start_time: float):
        """Track performance of event capture."""
        elapsed_ms = int((time.time() - start_time) * 1000)
        self.total_capture_time_ms += elapsed_ms
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics.
        
        Returns:
            Dictionary with performance metrics
        """
        avg_capture_time_ms = (
            self.total_capture_time_ms / self.total_events
            if self.total_events > 0 else 0
        )
        
        return {
            "total_events": self.total_events,
            "total_capture_time_ms": self.total_capture_time_ms,
            "avg_capture_time_ms": avg_capture_time_ms,
            "enabled": self.enabled,
            "current_node_id": self.current_node_id,
            "current_step_id": self.current_step_id,
            "execution_order": self.execution_order
        }
    
    def flush(self):
        """Flush any remaining buffered events."""
        # Currently events are written immediately, but this can be
        # enhanced for batching in future
        pass
    
    def close(self):
        """Close the event capture manager."""
        self.flush()
        self.enabled = False


# Global event capture manager instance (optional)
_global_event_captor: Optional[EventCaptureManager] = None


def get_event_captor() -> Optional[EventCaptureManager]:
    """Get the global event captor instance."""
    return _global_event_captor


def set_event_captor(captor: Optional[EventCaptureManager]):
    """Set the global event captor instance."""
    global _global_event_captor
    _global_event_captor = captor
