# Stage 4: Connection Manager Consolidation

**Phase:** 1 - Core Infrastructure
**Dependencies:** Stage 3 (Session Manager)
**Risk Level:** Medium
**Estimated Time:** 3-4 hours

## Objectives

1. Consolidate duplicate connection managers into single source of truth
2. Add async lock for thread safety
3. Add connection limits and health monitoring
4. Remove deprecated `WebSocketManager`

## Current State Analysis

### What We Have

**Two competing connection managers:**

1. `backend/websocket_manager.py:27-273`
   - Class: `WebSocketManager`
   - Global: `ws_manager`
   - Problem: Calls `await websocket.accept()` in connect() - duplicate accept

2. `backend/services/connection_manager.py:71-374`
   - Class: `ConnectionManager`
   - Global: `connection_manager`
   - Note: Does NOT call accept() - expects it to be called already

### What We Need
- Single `ConnectionManager` as the only connection tracking system
- Async lock to prevent race conditions
- Connection limits to prevent resource exhaustion
- Health monitoring for stale connection cleanup

## Implementation Tasks

### Task 1: Update ConnectionManager with Thread Safety

**Objective:** Add async lock and connection limits

**File to Modify:** `backend/services/connection_manager.py`

**Replace the class with:**

```python
"""
Connection Manager for CMBAgent Backend.

This module provides the single source of truth for WebSocket connection management.
All connection tracking should use this manager.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Import event types (with fallback)
try:
    from websocket_events import (
        WebSocketEvent,
        WebSocketEventType,
    )
    from event_queue import event_queue
except ImportError:
    # Define minimal stubs if import fails
    class WebSocketEventType:
        WORKFLOW_STARTED = "workflow_started"
        WORKFLOW_STATE_CHANGED = "workflow_state_changed"
        WORKFLOW_COMPLETED = "workflow_completed"
        WORKFLOW_FAILED = "workflow_failed"
        WORKFLOW_PAUSED = "workflow_paused"
        WORKFLOW_RESUMED = "workflow_resumed"
        OUTPUT = "output"
        PONG = "pong"
        ERROR = "error"

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

    class _EventQueue:
        def push(self, *args, **kwargs): pass
        def get_since(self, *args, **kwargs): return []
        def get_all_events(self, *args, **kwargs): return []

    event_queue = _EventQueue()


class ConnectionManager:
    """
    Single source of truth for WebSocket connection management.

    Features:
    - Async-safe with lock protection
    - Connection limits to prevent exhaustion
    - Metadata tracking for debugging
    - Event queue integration for reliable delivery
    """

    def __init__(self, max_connections: int = 100, db_factory=None):
        """
        Initialize the connection manager.

        Args:
            max_connections: Maximum allowed simultaneous connections
            db_factory: Optional database factory for connection persistence
        """
        self._connections: Dict[str, WebSocket] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._max_connections = max_connections
        self._db_factory = db_factory

        logger.info("ConnectionManager initialized (max_connections=%d)", max_connections)

    async def connect(
        self,
        websocket: WebSocket,
        task_id: str,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Register a WebSocket connection.

        NOTE: websocket.accept() must be called BEFORE calling this method.

        Args:
            websocket: FastAPI WebSocket instance (already accepted)
            task_id: Task identifier for this connection
            session_id: Optional session identifier

        Returns:
            True if connection registered, False if limit reached
        """
        async with self._lock:
            # Check connection limit
            if len(self._connections) >= self._max_connections:
                logger.warning(
                    "Connection limit reached (%d), rejecting task %s",
                    self._max_connections, task_id
                )
                return False

            # Handle reconnection - close existing connection for same task_id
            if task_id in self._connections:
                old_ws = self._connections[task_id]
                logger.info("Replacing existing connection for task %s", task_id)
                try:
                    await old_ws.close(code=1000, reason="Reconnection")
                except Exception:
                    pass  # Old connection might already be closed

            # Register new connection
            self._connections[task_id] = websocket
            self._metadata[task_id] = {
                "session_id": session_id,
                "connected_at": datetime.now(timezone.utc),
                "last_activity": datetime.now(timezone.utc),
            }

            logger.info(
                "Connection registered: task=%s, session=%s, total=%d",
                task_id, session_id, len(self._connections)
            )

            # Persist to database if available
            if self._db_factory:
                try:
                    self._persist_connection(task_id, session_id)
                except Exception as e:
                    logger.warning("Failed to persist connection: %s", e)

            return True

    async def disconnect(self, task_id: str):
        """
        Unregister a connection.

        Args:
            task_id: Task identifier
        """
        async with self._lock:
            if task_id in self._connections:
                del self._connections[task_id]
            if task_id in self._metadata:
                del self._metadata[task_id]

            logger.info(
                "Connection disconnected: task=%s, remaining=%d",
                task_id, len(self._connections)
            )

            # Remove from database if available
            if self._db_factory:
                try:
                    self._remove_connection(task_id)
                except Exception as e:
                    logger.warning("Failed to remove connection from DB: %s", e)

    def is_connected(self, task_id: str) -> bool:
        """Check if a task has an active connection."""
        return task_id in self._connections

    async def send_event(
        self,
        task_id: str,
        event_type: str,
        data: Dict[str, Any],
        queue_if_disconnected: bool = True
    ) -> bool:
        """
        Send an event to a connected client.

        Args:
            task_id: Task identifier
            event_type: Type of event
            data: Event data
            queue_if_disconnected: Whether to queue if client disconnected

        Returns:
            True if sent or queued successfully
        """
        event = WebSocketEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            run_id=task_id,
            data=data
        )

        # Always queue for replay on reconnection
        if queue_if_disconnected:
            try:
                event_queue.push(task_id, event)
            except Exception:
                pass

        # Try to send to active connection
        async with self._lock:
            if task_id not in self._connections:
                return queue_if_disconnected

            websocket = self._connections[task_id]
            if task_id in self._metadata:
                self._metadata[task_id]["last_activity"] = datetime.now(timezone.utc)

        try:
            event_dict = event.dict() if hasattr(event, 'dict') else {
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": task_id,
                "data": data
            }
            await websocket.send_json(event_dict)
            return True

        except Exception as e:
            logger.warning("Failed to send event to %s: %s", task_id, e)
            await self.disconnect(task_id)
            return queue_if_disconnected

    async def send_json(self, task_id: str, data: Dict[str, Any]) -> bool:
        """
        Send raw JSON data to a client.

        Args:
            task_id: Task identifier
            data: JSON-serializable data

        Returns:
            True if sent successfully
        """
        async with self._lock:
            if task_id not in self._connections:
                return False
            websocket = self._connections[task_id]

        try:
            await websocket.send_json(data)
            return True
        except Exception as e:
            logger.warning("Failed to send JSON to %s: %s", task_id, e)
            await self.disconnect(task_id)
            return False

    # ==================== Convenience Methods ====================

    async def send_output(self, task_id: str, message: str):
        """Send output message"""
        await self.send_event(task_id, "output", {"message": message})

    async def send_status(self, task_id: str, status: str, message: str = None):
        """Send status update"""
        await self.send_event(task_id, "workflow_state_changed", {
            "status": status,
            "message": message or status
        })

    async def send_error(self, task_id: str, error_type: str, message: str):
        """Send error event"""
        await self.send_event(task_id, "error", {
            "error_type": error_type,
            "message": message
        })

    async def send_pong(self, task_id: str):
        """Send pong response (not queued)"""
        await self.send_event(task_id, "pong", {}, queue_if_disconnected=False)

    async def send_workflow_paused(self, task_id: str, message: str = "Workflow paused"):
        """Send workflow paused event"""
        await self.send_event(task_id, "workflow_paused", {
            "message": message,
            "status": "paused"
        })

    async def send_workflow_resumed(self, task_id: str, message: str = "Workflow resumed"):
        """Send workflow resumed event"""
        await self.send_event(task_id, "workflow_resumed", {
            "message": message,
            "status": "executing"
        })

    async def send_workflow_cancelled(self, task_id: str, message: str = "Workflow cancelled"):
        """Send workflow cancelled event"""
        await self.send_event(task_id, "workflow_failed", {
            "message": message,
            "status": "cancelled"
        })

    async def replay_missed_events(self, task_id: str, since_timestamp: float = None):
        """Replay events missed during disconnection"""
        try:
            if since_timestamp:
                events = event_queue.get_events_since(task_id, since_timestamp)
            else:
                events = event_queue.get_all_events(task_id)

            for event in events:
                await self.send_event(
                    task_id,
                    event.event_type if hasattr(event, 'event_type') else event.get('event_type'),
                    event.data if hasattr(event, 'data') else event.get('data', {}),
                    queue_if_disconnected=False
                )
        except Exception as e:
            logger.error("Failed to replay events for %s: %s", task_id, e)

    # ==================== Stats & Monitoring ====================

    async def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        async with self._lock:
            return {
                "active_connections": len(self._connections),
                "max_connections": self._max_connections,
                "connections": list(self._connections.keys())
            }

    def get_websocket(self, task_id: str) -> Optional[WebSocket]:
        """Get WebSocket for a task (for legacy compatibility)"""
        return self._connections.get(task_id)

    # ==================== Database Persistence ====================

    def _persist_connection(self, task_id: str, session_id: Optional[str]):
        """Persist connection to database"""
        if not self._db_factory:
            return

        from cmbagent.database.models import ActiveConnection
        import socket

        db = self._db_factory()
        try:
            # Upsert connection record
            existing = db.query(ActiveConnection).filter(
                ActiveConnection.task_id == task_id
            ).first()

            if existing:
                existing.session_id = session_id
                existing.last_heartbeat = datetime.now(timezone.utc)
                existing.server_instance = socket.gethostname()
            else:
                conn = ActiveConnection(
                    task_id=task_id,
                    session_id=session_id,
                    server_instance=socket.gethostname()
                )
                db.add(conn)

            db.commit()
        finally:
            db.close()

    def _remove_connection(self, task_id: str):
        """Remove connection from database"""
        if not self._db_factory:
            return

        from cmbagent.database.models import ActiveConnection

        db = self._db_factory()
        try:
            db.query(ActiveConnection).filter(
                ActiveConnection.task_id == task_id
            ).delete()
            db.commit()
        finally:
            db.close()


# Global connection manager instance
connection_manager = ConnectionManager(max_connections=100)
```

### Task 2: Deprecate WebSocketManager

**Objective:** Mark old manager as deprecated, redirect to new one

**File to Modify:** `backend/websocket_manager.py`

**Add deprecation warning at top:**

```python
"""
DEPRECATED: WebSocketManager

This module is deprecated. Use backend/services/connection_manager.py instead.

The ConnectionManager provides:
- Thread-safe operations with async locks
- Connection limits
- Proper event queue integration
- No duplicate websocket.accept() calls

Migration:
    # Old:
    from backend.websocket_manager import ws_manager
    await ws_manager.connect(websocket, run_id)

    # New:
    from backend.services.connection_manager import connection_manager
    await connection_manager.connect(websocket, task_id)
"""

import warnings
warnings.warn(
    "websocket_manager.py is deprecated. Use services/connection_manager.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Keep old implementation for backward compatibility but redirect
from services.connection_manager import connection_manager as _cm

class WebSocketManager:
    """DEPRECATED: Use ConnectionManager from services/connection_manager.py"""

    def __init__(self):
        warnings.warn("WebSocketManager is deprecated", DeprecationWarning)
        self.active_connections = _cm._connections

    async def connect(self, websocket, run_id):
        warnings.warn("Use connection_manager.connect() instead", DeprecationWarning)
        # NOTE: Do NOT call websocket.accept() here - it's already called by handler
        return await _cm.connect(websocket, run_id)

    async def disconnect(self, run_id):
        return await _cm.disconnect(run_id)

    async def send_event(self, run_id, event):
        return await _cm.send_event(run_id, event.event_type, event.data)


# Deprecated global instance
ws_manager = WebSocketManager()
```

### Task 3: Update WebSocket Handler

**Objective:** Use only the consolidated connection manager

**File to Modify:** `backend/websocket/handlers.py`

**Update imports and usage:**

```python
# Remove or comment out:
# from backend.websocket_manager import ws_manager

# Ensure only services connection_manager is used:
from services.connection_manager import connection_manager

# In websocket_endpoint function, ensure:
# 1. websocket.accept() is called first
# 2. Then connection_manager.connect() is called (no accept inside)
```

### Task 4: Update Services Export

**Objective:** Ensure connection_manager is properly exported

**File to Modify:** `backend/services/__init__.py`

```python
from services.connection_manager import (
    ConnectionManager,
    connection_manager
)
from services.session_manager import (
    SessionManager,
    get_session_manager
)
# ... other exports
```

## Verification Criteria

### Must Pass
- [ ] Only one connection manager is used
- [ ] Async lock prevents race conditions
- [ ] Connection limit enforced
- [ ] No duplicate `websocket.accept()` calls
- [ ] Legacy code still works via deprecation wrapper

### Test Script
```python
# test_stage_4.py
import asyncio
from unittest.mock import MagicMock, AsyncMock
from backend.services.connection_manager import ConnectionManager

async def test_connection_manager():
    cm = ConnectionManager(max_connections=5)

    # Create mock websockets
    ws1 = MagicMock()
    ws1.send_json = AsyncMock()
    ws1.close = AsyncMock()

    ws2 = MagicMock()
    ws2.send_json = AsyncMock()
    ws2.close = AsyncMock()

    # Test connect
    result = await cm.connect(ws1, "task_1", "session_1")
    assert result is True
    assert cm.is_connected("task_1")
    print("✅ Connect works")

    # Test send_event
    result = await cm.send_event("task_1", "output", {"message": "Hello"})
    assert result is True
    assert ws1.send_json.called
    print("✅ Send event works")

    # Test reconnection (same task_id)
    result = await cm.connect(ws2, "task_1")
    assert result is True
    assert ws1.close.called  # Old connection closed
    print("✅ Reconnection works")

    # Test disconnect
    await cm.disconnect("task_1")
    assert not cm.is_connected("task_1")
    print("✅ Disconnect works")

    # Test connection limit
    mocks = []
    for i in range(5):
        ws = MagicMock()
        ws.send_json = AsyncMock()
        mocks.append(ws)
        result = await cm.connect(ws, f"limit_task_{i}")
        assert result is True

    # 6th should fail
    ws6 = MagicMock()
    result = await cm.connect(ws6, "limit_task_6")
    assert result is False
    print("✅ Connection limit works")

    # Cleanup
    for i in range(5):
        await cm.disconnect(f"limit_task_{i}")

    stats = await cm.get_stats()
    assert stats["active_connections"] == 0
    print("✅ Stats works")

    print("\n✅ All ConnectionManager tests passed!")

if __name__ == "__main__":
    asyncio.run(test_connection_manager())
```

## Common Issues and Solutions

### Issue 1: Circular imports
**Symptom:** `ImportError: cannot import name X`
**Solution:** Use lazy imports inside functions

### Issue 2: Existing code breaks
**Symptom:** Code using `ws_manager` fails
**Solution:** Deprecation wrapper maintains backward compatibility

## Rollback Procedure

```bash
git checkout backend/websocket_manager.py
git checkout backend/services/connection_manager.py
git checkout backend/websocket/handlers.py
```

## Success Criteria

Stage 4 is complete when:
1. ✅ Single ConnectionManager is the source of truth
2. ✅ Async lock prevents race conditions
3. ✅ Connection limit enforced (default 100)
4. ✅ Old code works via deprecation wrapper
5. ✅ All tests pass

## Next Stage

Once Stage 4 is verified complete, proceed to:
**Stage 5: Approval Manager Refactor**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-11
