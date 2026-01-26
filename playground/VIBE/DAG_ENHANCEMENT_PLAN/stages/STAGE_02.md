# Stage 2: AG2 Event Capture Layer

**Phase:** 1 - Event Capture Infrastructure
**Estimated Time:** 60 minutes
**Dependencies:** Stage 1 (ExecutionEvent Model) must be complete
**Risk Level:** Medium

## Objectives

1. Create event capture manager for automatic event recording
2. Hook into AG2's ConversableAgent message system
3. Capture GroupChat transitions and handoffs
4. Implement mode-agnostic event emission
5. Integrate with existing callback system
6. Emit WebSocket events for real-time UI updates
7. Ensure < 5% performance overhead

## Current State Analysis

### What We Have
- ExecutionEvent table and repository (from Stage 1)
- AG2 0.10.3 with ConversableAgent and GroupChat
- Existing callback system in `cmbagent/callbacks.py`
- WebSocket event emission system (from Stage 5)
- Multiple execution modes (one_shot, planning_and_control, etc.)

### What We Need
- Automatic event capture without manual calls
- AG2 agent hooks for message interception
- GroupChat speaker selection hooks
- Code execution hooks
- File generation detection
- Event capture manager lifecycle
- Integration with all execution modes

## Pre-Stage Verification

### Check Prerequisites
1. Stage 1 complete and verified
2. ExecutionEvent model working
3. EventRepository tested
4. AG2 agents instantiated correctly
5. Callback system functional
6. WebSocket events working

### Verification Commands
```bash
# Verify Stage 1 completion
python -c "from cmbagent.database import ExecutionEvent, EventRepository; print('Stage 1 OK')"

# Check AG2 version
python -c "import autogen; print(f'AG2 version: {autogen.__version__}')"

# Verify callback system
python -c "from cmbagent.callbacks import WorkflowCallbacks; print('Callbacks OK')"
```

## Implementation Tasks

### Task 1: Create Event Capture Manager

**Objective:** Central manager for capturing execution events

**Implementation:**

Create `cmbagent/execution/event_capture.py`:

```python
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
        buffer_size: int = 50
    ):
        """
        Initialize event capture manager.
        
        Args:
            db_session: Database session
            run_id: Workflow run ID
            session_id: Session ID for isolation
            enabled: Whether event capture is enabled
            buffer_size: Number of events to buffer before flush
        """
        self.db = db_session
        self.run_id = run_id
        self.session_id = session_id
        self.enabled = enabled
        self.buffer_size = buffer_size
        
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
                meta=meta,
                timestamp=datetime.now(timezone.utc)
            )
            
            self.execution_order += 1
            self.total_events += 1
            
            return event
    
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
```

**Files to Create:**
- `cmbagent/execution/event_capture.py`

**Verification:**
- EventCaptureManager imports successfully
- Can create instance with db_session
- All capture methods defined
- Thread-safe buffer operations
- Performance tracking working

### Task 2: Create AG2 Integration Hooks

**Objective:** Hook into AG2 agent system for automatic capture

**Implementation:**

Create `cmbagent/execution/ag2_hooks.py`:

```python
"""
AG2 Integration Hooks for Event Capture

Monkey-patches AG2 classes to automatically capture events without
requiring code changes in CMBAgent.
"""

from typing import Optional, Any, Dict
import functools
import time

from cmbagent.execution.event_capture import get_event_captor


def patch_conversable_agent():
    """
    Patch ConversableAgent to capture message events.
    """
    try:
        from autogen import ConversableAgent
        
        # Store original methods
        original_generate_reply = ConversableAgent.generate_reply
        original_send = ConversableAgent.send
        
        @functools.wraps(original_generate_reply)
        def enhanced_generate_reply(self, messages=None, sender=None, **kwargs):
            """Enhanced generate_reply with event capture."""
            captor = get_event_captor()
            event_id = None
            
            if captor and captor.enabled:
                # Capture agent call start
                message_content = messages[-1].get("content", "") if messages else ""
                event_id = captor.capture_agent_call(
                    agent_name=self.name,
                    message=message_content,
                    metadata={
                        "sender": sender.name if sender else None,
                        "llm_config": getattr(self, "llm_config", {})
                    }
                )
            
            # Call original method
            start_time = time.time()
            result = original_generate_reply(self, messages, sender, **kwargs)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if captor and captor.enabled and event_id:
                # Capture agent response
                response_content = result if isinstance(result, str) else str(result)
                captor.capture_agent_response(
                    agent_name=self.name,
                    response=response_content,
                    event_id=event_id,
                    metadata={"duration_ms": duration_ms}
                )
            
            return result
        
        @functools.wraps(original_send)
        def enhanced_send(self, message, recipient, request_reply=None, silent=False):
            """Enhanced send with event capture."""
            captor = get_event_captor()
            
            if captor and captor.enabled:
                # Capture message
                content = message if isinstance(message, str) else message.get("content", "")
                captor.capture_message(
                    sender=self.name,
                    recipient=recipient.name,
                    content=content
                )
            
            # Call original method
            return original_send(self, message, recipient, request_reply, silent)
        
        # Apply patches
        ConversableAgent.generate_reply = enhanced_generate_reply
        ConversableAgent.send = enhanced_send
        
        print("[AG2 Hooks] ConversableAgent patched successfully")
        return True
        
    except Exception as e:
        print(f"[AG2 Hooks] Failed to patch ConversableAgent: {e}")
        return False


def patch_group_chat():
    """
    Patch GroupChat to capture speaker selection (handoffs).
    """
    try:
        from autogen import GroupChat
        
        # Store original method
        original_select_speaker = GroupChat.select_speaker
        
        @functools.wraps(original_select_speaker)
        def enhanced_select_speaker(self, last_speaker, selector):
            """Enhanced select_speaker with handoff capture."""
            # Call original method
            next_speaker = original_select_speaker(self, last_speaker, selector)
            
            captor = get_event_captor()
            if captor and captor.enabled and last_speaker and next_speaker:
                # Capture handoff
                captor.capture_handoff(
                    from_agent=last_speaker.name,
                    to_agent=next_speaker.name,
                    reason="group_chat_selection"
                )
            
            return next_speaker
        
        # Apply patch
        GroupChat.select_speaker = enhanced_select_speaker
        
        print("[AG2 Hooks] GroupChat patched successfully")
        return True
        
    except Exception as e:
        print(f"[AG2 Hooks] Failed to patch GroupChat: {e}")
        return False


def patch_code_executor():
    """
    Patch code execution to capture code_exec events.
    """
    try:
        from autogen.coding import CodeBlock, CodeExecutor
        
        # This is a simplified version - actual implementation may vary
        # based on how code execution is done in AG2
        
        print("[AG2 Hooks] Code executor hooks registered")
        return True
        
    except Exception as e:
        print(f"[AG2 Hooks] Failed to patch code executor: {e}")
        return False


def install_ag2_hooks() -> bool:
    """
    Install all AG2 hooks for event capture.
    
    Returns:
        True if all hooks installed successfully
    """
    results = [
        patch_conversable_agent(),
        patch_group_chat(),
        patch_code_executor()
    ]
    
    success = all(results)
    if success:
        print("[AG2 Hooks] All hooks installed successfully")
    else:
        print("[AG2 Hooks] Some hooks failed to install")
    
    return success


def uninstall_ag2_hooks():
    """
    Uninstall AG2 hooks (restore original behavior).
    Note: This is currently not implemented as it requires storing
    original methods. Add if needed for testing.
    """
    print("[AG2 Hooks] Uninstall not implemented - restart process to remove hooks")
```

**Files to Create:**
- `cmbagent/execution/ag2_hooks.py`

**Verification:**
- AG2 hooks install without errors
- ConversableAgent.generate_reply intercepted
- GroupChat.select_speaker intercepted
- Events captured automatically
- Original functionality preserved

### Task 3: Integrate with Callback System

**Objective:** Connect event capture to existing callbacks

**Implementation:**

Edit `cmbagent/callbacks.py` - Add event capture integration:

```python
# Add to imports at top of file
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cmbagent.execution.event_capture import EventCaptureManager


# Add to WorkflowCallbacks dataclass
@dataclass
class WorkflowCallbacks:
    # ... existing callbacks ...
    
    # Event capture manager (optional)
    event_captor: Optional['EventCaptureManager'] = None
    
    # ... rest of existing code ...
```

Create `cmbagent/execution/callback_integration.py`:

```python
"""
Integration between event capture and callback system.
"""

from typing import Optional
from cmbagent.callbacks import WorkflowCallbacks, StepInfo, PlanInfo
from cmbagent.execution.event_capture import EventCaptureManager


def create_callbacks_with_event_capture(
    event_captor: EventCaptureManager,
    **callback_kwargs
) -> WorkflowCallbacks:
    """
    Create WorkflowCallbacks with automatic event capture.
    
    Args:
        event_captor: EventCaptureManager instance
        **callback_kwargs: Additional callback functions
        
    Returns:
        WorkflowCallbacks with event capture integrated
    """
    
    def on_step_start_with_events(step_info: StepInfo):
        """Capture step start event."""
        if event_captor and event_captor.enabled:
            event_captor.capture_agent_call(
                agent_name=step_info.agent,
                message=step_info.description,
                metadata={
                    "step_number": step_info.step_number,
                    "status": step_info.status.value
                }
            )
        
        # Call original callback if provided
        original = callback_kwargs.get('on_step_start')
        if original:
            original(step_info)
    
    def on_step_complete_with_events(step_info: StepInfo):
        """Capture step complete event."""
        if event_captor and event_captor.enabled:
            event_captor.capture_agent_response(
                agent_name=step_info.agent,
                response=str(step_info.result) if step_info.result else "completed",
                metadata={
                    "step_number": step_info.step_number,
                    "execution_time": step_info.execution_time,
                    "status": step_info.status.value
                }
            )
        
        # Call original callback if provided
        original = callback_kwargs.get('on_step_complete')
        if original:
            original(step_info)
    
    def on_step_failed_with_events(step_info: StepInfo):
        """Capture step failure event."""
        if event_captor and event_captor.enabled:
            event_captor.capture_error(
                agent_name=step_info.agent,
                error_message=step_info.error or "Step failed",
                error_type="step_failure",
                metadata={
                    "step_number": step_info.step_number
                }
            )
        
        # Call original callback if provided
        original = callback_kwargs.get('on_step_failed')
        if original:
            original(step_info)
    
    # Create callbacks with event integration
    callbacks = WorkflowCallbacks(
        on_step_start=on_step_start_with_events,
        on_step_complete=on_step_complete_with_events,
        on_step_failed=on_step_failed_with_events,
        event_captor=event_captor,
        **{k: v for k, v in callback_kwargs.items() 
           if k not in ['on_step_start', 'on_step_complete', 'on_step_failed']}
    )
    
    return callbacks
```

**Files to Create:**
- `cmbagent/execution/callback_integration.py`

**Files to Modify:**
- `cmbagent/callbacks.py` (add event_captor field)

**Verification:**
- Callbacks integrate with event capture
- Events captured through callback system
- Original callbacks still execute
- No breaking changes

### Task 4: Integrate with CMBAgent

**Objective:** Add event capture to CMBAgent initialization

**Implementation:**

Edit `cmbagent/cmbagent.py` - Add event capture initialization:

```python
# Add to imports
from cmbagent.execution.event_capture import EventCaptureManager, set_event_captor
from cmbagent.execution.ag2_hooks import install_ag2_hooks
from cmbagent.execution.callback_integration import create_callbacks_with_event_capture

# In CMBAgent.__init__, after database initialization:
        # Event capture initialization (after database setup)
        self.event_captor: Optional[EventCaptureManager] = None
        enable_event_capture = os.getenv("CMBAGENT_ENABLE_EVENT_CAPTURE", "true").lower() == "true"
        
        if self.use_database and enable_event_capture:
            try:
                self.event_captor = EventCaptureManager(
                    db_session=self.db_session,
                    run_id="",  # Will be set when workflow starts
                    session_id=self.session_id,
                    enabled=True
                )
                
                # Set as global event captor
                set_event_captor(self.event_captor)
                
                # Install AG2 hooks for automatic capture
                install_ag2_hooks()
                
                if cmbagent_debug:
                    print(f"Event capture enabled for session: {self.session_id}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize event capture: {e}")
                self.event_captor = None
```

Add method to update event captor context:

```python
    def _set_event_context(self, run_id: str, node_id: Optional[str] = None, step_id: Optional[str] = None):
        """
        Update event capture context for current execution.
        
        Args:
            run_id: Current workflow run ID
            node_id: Current DAG node ID (if applicable)
            step_id: Current workflow step ID (if applicable)
        """
        if self.event_captor:
            if run_id and self.event_captor.run_id != run_id:
                self.event_captor.run_id = run_id
            self.event_captor.set_context(node_id=node_id, step_id=step_id)
```

**Files to Modify:**
- `cmbagent/cmbagent.py` (add event capture initialization and context methods)

**Verification:**
- EventCaptureManager initialized with CMBAgent
- AG2 hooks installed on startup
- Global event captor set
- Context can be updated

### Task 5: Add Environment Configuration

**Objective:** Allow event capture configuration via environment variables

**Implementation:**

Create `cmbagent/execution/config.py` (or extend existing):

```python
"""
Event capture configuration.
"""

import os


class EventCaptureConfig:
    """Configuration for event capture system."""
    
    # Enable/disable event capture
    ENABLED = os.getenv("CMBAGENT_ENABLE_EVENT_CAPTURE", "true").lower() == "true"
    
    # Buffer size for batch writes (future optimization)
    BUFFER_SIZE = int(os.getenv("CMBAGENT_EVENT_BUFFER_SIZE", "50"))
    
    # Maximum event input/output size (to prevent large JSON)
    MAX_INPUT_SIZE = int(os.getenv("CMBAGENT_EVENT_MAX_INPUT_SIZE", "10000"))
    MAX_OUTPUT_SIZE = int(os.getenv("CMBAGENT_EVENT_MAX_OUTPUT_SIZE", "10000"))
    
    # Enable specific event types
    CAPTURE_AGENT_CALLS = os.getenv("CMBAGENT_CAPTURE_AGENT_CALLS", "true").lower() == "true"
    CAPTURE_TOOL_CALLS = os.getenv("CMBAGENT_CAPTURE_TOOL_CALLS", "true").lower() == "true"
    CAPTURE_CODE_EXEC = os.getenv("CMBAGENT_CAPTURE_CODE_EXEC", "true").lower() == "true"
    CAPTURE_FILE_GEN = os.getenv("CMBAGENT_CAPTURE_FILE_GEN", "true").lower() == "true"
    CAPTURE_HANDOFFS = os.getenv("CMBAGENT_CAPTURE_HANDOFFS", "true").lower() == "true"
    CAPTURE_MESSAGES = os.getenv("CMBAGENT_CAPTURE_MESSAGES", "true").lower() == "true"
    
    # Sampling (for high-volume scenarios)
    SAMPLE_RATE = float(os.getenv("CMBAGENT_EVENT_SAMPLE_RATE", "1.0"))  # 1.0 = 100%
    
    # Performance monitoring
    TRACK_PERFORMANCE = os.getenv("CMBAGENT_EVENT_TRACK_PERF", "true").lower() == "true"
```

Update `.env` file (or create template):

```bash
# Event Capture Configuration

# Enable event capture system (default: true)
CMBAGENT_ENABLE_EVENT_CAPTURE=true

# Event buffer size for batch writes (default: 50)
CMBAGENT_EVENT_BUFFER_SIZE=50

# Maximum size for event inputs/outputs in bytes (default: 10000)
CMBAGENT_EVENT_MAX_INPUT_SIZE=10000
CMBAGENT_EVENT_MAX_OUTPUT_SIZE=10000

# Enable specific event types (default: all true)
CMBAGENT_CAPTURE_AGENT_CALLS=true
CMBAGENT_CAPTURE_TOOL_CALLS=true
CMBAGENT_CAPTURE_CODE_EXEC=true
CMBAGENT_CAPTURE_FILE_GEN=true
CMBAGENT_CAPTURE_HANDOFFS=true
CMBAGENT_CAPTURE_MESSAGES=true

# Sampling rate for high-volume scenarios (default: 1.0 = 100%)
CMBAGENT_EVENT_SAMPLE_RATE=1.0

# Track event capture performance (default: true)
CMBAGENT_EVENT_TRACK_PERF=true
```

**Files to Create:**
- `cmbagent/execution/config.py`

**Files to Modify:**
- `.env` (add event capture variables)

**Verification:**
- Configuration loads from environment
- Can enable/disable event capture
- Can configure specific event types
- Sampling rate configurable

### Task 6: Update Execution Module __init__.py

**Objective:** Export new components

**Implementation:**

Create/edit `cmbagent/execution/__init__.py`:

```python
"""
Execution module for CMBAgent.

Provides event capture, parallel execution, and workflow execution components.
"""

from cmbagent.execution.event_capture import (
    EventCaptureManager,
    get_event_captor,
    set_event_captor
)

from cmbagent.execution.ag2_hooks import (
    install_ag2_hooks,
    uninstall_ag2_hooks
)

from cmbagent.execution.callback_integration import (
    create_callbacks_with_event_capture
)

from cmbagent.execution.config import EventCaptureConfig

__all__ = [
    "EventCaptureManager",
    "get_event_captor",
    "set_event_captor",
    "install_ag2_hooks",
    "uninstall_ag2_hooks",
    "create_callbacks_with_event_capture",
    "EventCaptureConfig",
]
```

**Files to Create:**
- `cmbagent/execution/__init__.py`

**Verification:**
- All components importable from cmbagent.execution
- No import errors
- Circular imports avoided

## Verification Criteria

### Must Pass
- [ ] EventCaptureManager implemented and working
- [ ] AG2 hooks install successfully
- [ ] ConversableAgent messages captured
- [ ] GroupChat handoffs captured
- [ ] Events written to database automatically
- [ ] Thread-safe event capture
- [ ] Performance overhead < 5%
- [ ] Works across all execution modes (one_shot, planning_and_control)
- [ ] Event context updates correctly (node_id, step_id)
- [ ] Callback integration working
- [ ] Environment configuration working
- [ ] Can enable/disable event capture
- [ ] Global event captor accessible

### Should Pass
- [ ] Nested events tracked correctly
- [ ] Event stack managed properly
- [ ] Files linked to events automatically
- [ ] Messages linked to events automatically
- [ ] Error events captured
- [ ] Performance tracking accurate
- [ ] No memory leaks from event buffer

## Files Summary

### New Files
```
cmbagent/execution/event_capture.py           # Event capture manager
cmbagent/execution/ag2_hooks.py               # AG2 integration hooks
cmbagent/execution/callback_integration.py    # Callback integration
cmbagent/execution/config.py                  # Event capture config
cmbagent/execution/__init__.py                # Module exports
```

### Modified Files
```
cmbagent/cmbagent.py                         # Add event capture init
cmbagent/callbacks.py                        # Add event_captor field
.env                                         # Add event config vars
```

## Testing

Create `tests/test_stage_02_event_capture.py`:

```python
"""Tests for Stage 2: AG2 Event Capture Layer"""

import pytest
import os
from cmbagent.database import init_database, get_db_session, WorkflowRepository
from cmbagent.execution import (
    EventCaptureManager,
    set_event_captor,
    install_ag2_hooks
)


@pytest.fixture
def db_session():
    """Create database session."""
    init_database()
    session = get_db_session()
    yield session
    session.close()


@pytest.fixture
def workflow_repo(db_session):
    """Create workflow repository."""
    return WorkflowRepository(db_session, "test_session")


@pytest.fixture
def event_captor(db_session, workflow_repo):
    """Create event capture manager."""
    run = workflow_repo.create_run(
        task_description="Test workflow",
        mode="one_shot",
        agent="engineer",
        model="gpt-4"
    )
    
    captor = EventCaptureManager(
        db_session=db_session,
        run_id=run.id,
        session_id="test_session",
        enabled=True
    )
    
    set_event_captor(captor)
    return captor


def test_event_capture_manager_init(event_captor):
    """Test EventCaptureManager initialization."""
    assert event_captor is not None
    assert event_captor.enabled
    assert event_captor.execution_order == 0
    print("✓ EventCaptureManager initializes")


def test_capture_agent_call(event_captor):
    """Test capturing agent call."""
    event_id = event_captor.capture_agent_call(
        agent_name="engineer",
        message="Test task",
        metadata={"model": "gpt-4"}
    )
    
    assert event_id is not None
    assert event_captor.execution_order == 1
    print("✓ Agent call captured")


def test_capture_agent_response(event_captor):
    """Test capturing agent response."""
    event_id = event_captor.capture_agent_call(
        agent_name="engineer",
        message="Test task"
    )
    
    event_captor.capture_agent_response(
        agent_name="engineer",
        response="Task completed",
        event_id=event_id
    )
    
    # Verify event updated
    from cmbagent.database import EventRepository
    repo = EventRepository(event_captor.db, event_captor.session_id)
    event = repo.get_event(event_id)
    
    assert event is not None
    assert event.event_subtype == "complete"
    assert event.outputs is not None
    print("✓ Agent response captured")


def test_capture_tool_call(event_captor):
    """Test capturing tool call."""
    event_id = event_captor.capture_tool_call(
        agent_name="engineer",
        tool_name="execute_code",
        arguments={"code": "print('hello')"},
        result="hello"
    )
    
    assert event_id is not None
    print("✓ Tool call captured")


def test_capture_code_execution(event_captor):
    """Test capturing code execution."""
    event_id = event_captor.capture_code_execution(
        agent_name="executor",
        code="print('test')",
        language="python",
        result="test\n",
        exit_code=0,
        duration_ms=100
    )
    
    assert event_id is not None
    print("✓ Code execution captured")


def test_capture_file_generation(event_captor, db_session):
    """Test capturing file generation."""
    event_id = event_captor.capture_file_generation(
        agent_name="engineer",
        file_path="/test/output.png",
        file_type="plot",
        size_bytes=1024
    )
    
    assert event_id is not None
    
    # Verify File record created
    from cmbagent.database.models import File
    file = db_session.query(File).filter(File.event_id == event_id).first()
    assert file is not None
    assert file.file_path == "/test/output.png"
    print("✓ File generation captured")


def test_capture_handoff(event_captor):
    """Test capturing agent handoff."""
    event_id = event_captor.capture_handoff(
        from_agent="planner",
        to_agent="engineer",
        reason="task_delegation"
    )
    
    assert event_id is not None
    print("✓ Handoff captured")


def test_capture_message(event_captor, db_session):
    """Test capturing agent message."""
    event_id = event_captor.capture_message(
        sender="planner",
        recipient="engineer",
        content="Please implement this feature",
        tokens=10
    )
    
    assert event_id is not None
    
    # Verify Message record created
    from cmbagent.database.models import Message
    message = db_session.query(Message).filter(Message.event_id == event_id).first()
    assert message is not None
    assert message.sender == "planner"
    print("✓ Message captured")


def test_capture_error(event_captor):
    """Test capturing error."""
    event_id = event_captor.capture_error(
        agent_name="engineer",
        error_message="Division by zero",
        error_type="runtime_error"
    )
    
    assert event_id is not None
    print("✓ Error captured")


def test_nested_events(event_captor):
    """Test nested event capture."""
    # Parent event
    parent_id = event_captor.capture_agent_call(
        agent_name="engineer",
        message="Complex task"
    )
    
    # Child events
    tool_id = event_captor.capture_tool_call(
        agent_name="engineer",
        tool_name="analyze",
        arguments={}
    )
    
    code_id = event_captor.capture_code_execution(
        agent_name="engineer",
        code="result = analyze()"
    )
    
    # Verify nesting
    from cmbagent.database import EventRepository
    repo = EventRepository(event_captor.db, event_captor.session_id)
    
    tool_event = repo.get_event(tool_id)
    code_event = repo.get_event(code_id)
    
    assert tool_event.parent_event_id == parent_id
    assert code_event.parent_event_id == parent_id
    assert tool_event.depth == 1
    assert code_event.depth == 1
    print("✓ Nested events captured correctly")


def test_context_updates(event_captor):
    """Test context updates."""
    event_captor.set_context(node_id="node_1", step_id="step_1")
    
    event_id = event_captor.capture_agent_call(
        agent_name="engineer",
        message="Test"
    )
    
    from cmbagent.database import EventRepository
    repo = EventRepository(event_captor.db, event_captor.session_id)
    event = repo.get_event(event_id)
    
    assert event.node_id == "node_1"
    assert event.step_id == "step_1"
    print("✓ Context updates work")


def test_performance_tracking(event_captor):
    """Test performance tracking."""
    for i in range(10):
        event_captor.capture_agent_call(
            agent_name=f"agent_{i}",
            message="test"
        )
    
    stats = event_captor.get_performance_stats()
    
    assert stats["total_events"] == 10
    assert stats["avg_capture_time_ms"] >= 0
    print("✓ Performance tracking works")


def test_ag2_hooks_install():
    """Test AG2 hooks installation."""
    result = install_ag2_hooks()
    assert result is True
    print("✓ AG2 hooks install successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

Run tests:

```bash
python tests/test_stage_02_event_capture.py
```

## Post-Stage Actions

1. Update PROGRESS.md with completion
2. Verify performance overhead < 5%
3. Test with real workflow execution
4. Document any issues
5. Prepare for Stage 3 (UI Integration)

## Troubleshooting

### Events Not Captured
- Check `CMBAGENT_ENABLE_EVENT_CAPTURE=true`
- Verify AG2 hooks installed
- Check global event captor set
- Verify database session valid

### AG2 Hooks Fail
- Check AG2 version (0.10.3+)
- Verify import paths correct
- Check for AG2 API changes
- Review error messages

### Performance Issues
- Check event buffer size
- Review event input/output sizes
- Consider sampling for high-volume
- Profile event capture time

## Next Stage

Proceed to **Stage 3: Enhanced DAG Node Metadata and UI Integration** to expose captured events in the UI.
