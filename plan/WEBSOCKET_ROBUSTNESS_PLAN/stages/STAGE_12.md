# Stage 12: Unit & Integration Tests

**Phase:** 5 - Testing & Deployment
**Dependencies:** Stages 1-11
**Risk Level:** Low
**Estimated Time:** 4-5 hours

## Objectives

1. Create comprehensive unit tests for new components
2. Add integration tests for key flows
3. Ensure all new code has test coverage
4. Set up test fixtures and utilities

## Implementation Tasks

### Task 1: Test Utilities and Fixtures

**File to Create:** `tests/conftest.py`

```python
"""
Test configuration and fixtures
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import Generator
import tempfile
import os

# Configure pytest for async
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    session.query = MagicMock()
    return session


@pytest.fixture
def mock_db_factory(mock_db_session):
    """Mock database factory"""
    def factory():
        return mock_db_session
    return factory


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection"""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    ws.receive_json = AsyncMock(return_value={"type": "ping"})
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def temp_work_dir():
    """Create temporary work directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_config():
    """Sample task configuration"""
    return {
        "mode": "one-shot",
        "model": "gpt-4o",
        "maxRounds": 10,
        "maxAttempts": 3,
        "workDir": "/tmp/test"
    }


@pytest.fixture
def sample_session_state():
    """Sample session state"""
    return {
        "session_id": "test-session-123",
        "mode": "copilot",
        "conversation_history": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ],
        "context_variables": {"key": "value"},
        "current_phase": "execution",
        "current_step": 1,
        "status": "active"
    }
```

### Task 2: Session Manager Tests

**File to Create:** `tests/test_session_manager.py`

```python
"""
Tests for SessionManager service
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from backend.services.session_manager import SessionManager


class TestSessionManager:
    """Tests for SessionManager"""

    @pytest.fixture
    def session_manager(self, mock_db_factory):
        return SessionManager(db_factory=mock_db_factory)

    def test_create_session_returns_uuid(self, session_manager, mock_db_session):
        """Test session creation returns valid UUID"""
        session_id = session_manager.create_session(
            mode="copilot",
            config={"model": "gpt-4"}
        )

        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        assert mock_db_session.add.called
        assert mock_db_session.commit.called

    def test_create_session_with_name(self, session_manager, mock_db_session):
        """Test session creation with custom name"""
        session_id = session_manager.create_session(
            mode="copilot",
            config={},
            name="My Custom Session"
        )

        assert session_id is not None

    def test_save_session_state(self, session_manager, mock_db_session):
        """Test saving session state"""
        # Mock query to return existing state
        mock_state = MagicMock()
        mock_state.version = 1
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_state

        success = session_manager.save_session_state(
            session_id="test-123",
            conversation_history=[{"role": "user", "content": "test"}],
            context_variables={"key": "value"},
            current_phase="execution",
            current_step=1
        )

        assert success is True
        assert mock_db_session.commit.called

    def test_save_session_state_not_found(self, session_manager, mock_db_session):
        """Test saving to non-existent session"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        success = session_manager.save_session_state(
            session_id="nonexistent",
            conversation_history=[],
            context_variables={},
            current_phase="init"
        )

        assert success is False

    def test_load_session_state(self, session_manager, mock_db_session, sample_session_state):
        """Test loading session state"""
        mock_state = MagicMock()
        mock_state.mode = sample_session_state["mode"]
        mock_state.conversation_history = sample_session_state["conversation_history"]
        mock_state.context_variables = sample_session_state["context_variables"]
        mock_state.current_phase = sample_session_state["current_phase"]
        mock_state.current_step = sample_session_state["current_step"]
        mock_state.status = sample_session_state["status"]
        mock_state.created_at = datetime.now(timezone.utc)
        mock_state.updated_at = datetime.now(timezone.utc)
        mock_state.version = 1

        mock_session = MagicMock()
        mock_session.meta = {}

        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_state, mock_session
        ]

        state = session_manager.load_session_state("test-123")

        assert state is not None
        assert state["mode"] == "copilot"
        assert len(state["conversation_history"]) == 2

    def test_suspend_session(self, session_manager, mock_db_session):
        """Test suspending a session"""
        mock_db_session.query.return_value.filter.return_value.update.return_value = 1

        success = session_manager.suspend_session("test-123")

        assert success is True
        assert mock_db_session.commit.called

    def test_resume_session(self, session_manager, mock_db_session):
        """Test resuming a session"""
        mock_db_session.query.return_value.filter.return_value.update.return_value = 1

        success = session_manager.resume_session("test-123")

        assert success is True

    def test_list_sessions(self, session_manager, mock_db_session):
        """Test listing sessions"""
        mock_row = (
            "session-1", "Name", datetime.now(), datetime.now(),
            "copilot", "active", "execution", datetime.now()
        )
        mock_db_session.query.return_value.join.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_row]

        sessions = session_manager.list_sessions()

        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "session-1"


class TestSessionManagerCleanup:
    """Tests for cleanup functionality"""

    @pytest.fixture
    def session_manager(self, mock_db_factory):
        return SessionManager(db_factory=mock_db_factory)

    def test_cleanup_expired_sessions(self, session_manager, mock_db_session):
        """Test cleanup removes expired sessions"""
        mock_db_session.query.return_value.filter.return_value.update.return_value = 5

        session_manager._cleanup_expired()

        # Should have called update for sessions, approvals, and connections
        assert mock_db_session.commit.called
```

### Task 3: Approval Manager Tests

**File to Create:** `tests/test_approval_manager.py`

```python
"""
Tests for RobustApprovalManager
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

from backend.services.approval_manager import (
    RobustApprovalManager,
    ApprovalTimeoutError,
    ApprovalExpiredError,
    ApprovalNotFoundError
)


class TestApprovalManager:
    """Tests for RobustApprovalManager"""

    @pytest.fixture
    def approval_manager(self, mock_db_factory):
        return RobustApprovalManager(
            db_factory=mock_db_factory,
            default_timeout=10,
            poll_interval=0.1
        )

    @pytest.mark.asyncio
    async def test_request_approval(self, approval_manager, mock_db_session):
        """Test creating approval request"""
        approval_id = await approval_manager.request_approval(
            run_id="run-123",
            approval_type="plan_approval",
            context={"plan": "test plan"}
        )

        assert approval_id is not None
        assert len(approval_id) == 36
        assert mock_db_session.add.called
        assert mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_resolve_approval(self, approval_manager, mock_db_session):
        """Test resolving approval"""
        mock_db_session.query.return_value.filter.return_value.update.return_value = 1

        success = await approval_manager.resolve_approval(
            approval_id="approval-123",
            resolution="approved",
            feedback="Looks good!"
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_resolve_already_resolved(self, approval_manager, mock_db_session):
        """Test idempotent resolution"""
        mock_db_session.query.return_value.filter.return_value.update.return_value = 0

        mock_approval = MagicMock()
        mock_approval.status = "resolved"
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_approval

        success = await approval_manager.resolve_approval(
            approval_id="approval-123",
            resolution="approved",
            feedback=""
        )

        assert success is False  # Already resolved

    @pytest.mark.asyncio
    async def test_wait_for_approval_resolved(self, approval_manager, mock_db_session):
        """Test waiting for already resolved approval"""
        mock_approval = MagicMock()
        mock_approval.status = "resolved"
        mock_approval.result = {"resolution": "approved", "feedback": "ok"}
        mock_approval.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_approval

        result = await approval_manager.wait_for_approval("approval-123")

        assert result["resolution"] == "approved"

    @pytest.mark.asyncio
    async def test_wait_for_approval_not_found(self, approval_manager, mock_db_session):
        """Test waiting for non-existent approval"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ApprovalNotFoundError):
            await approval_manager.wait_for_approval("nonexistent")

    def test_has_pending(self, approval_manager, mock_db_session):
        """Test checking pending status"""
        mock_approval = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_approval

        assert approval_manager.has_pending("approval-123") is True

        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        assert approval_manager.has_pending("approval-123") is False
```

### Task 4: Connection Manager Tests

**File to Create:** `tests/test_connection_manager.py`

```python
"""
Tests for ConnectionManager
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from backend.services.connection_manager import ConnectionManager


class TestConnectionManager:
    """Tests for ConnectionManager"""

    @pytest.fixture
    def connection_manager(self):
        return ConnectionManager(max_connections=5)

    @pytest.mark.asyncio
    async def test_connect(self, connection_manager, mock_websocket):
        """Test basic connection"""
        result = await connection_manager.connect(mock_websocket, "task-1")

        assert result is True
        assert connection_manager.is_connected("task-1")

    @pytest.mark.asyncio
    async def test_connect_limit(self, connection_manager, mock_websocket):
        """Test connection limit enforcement"""
        # Fill up connections
        for i in range(5):
            ws = MagicMock()
            ws.close = AsyncMock()
            await connection_manager.connect(ws, f"task-{i}")

        # 6th should fail
        result = await connection_manager.connect(mock_websocket, "task-6")
        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect(self, connection_manager, mock_websocket):
        """Test disconnection"""
        await connection_manager.connect(mock_websocket, "task-1")
        assert connection_manager.is_connected("task-1")

        await connection_manager.disconnect("task-1")
        assert not connection_manager.is_connected("task-1")

    @pytest.mark.asyncio
    async def test_reconnection(self, connection_manager, mock_websocket):
        """Test reconnection closes old connection"""
        old_ws = MagicMock()
        old_ws.close = AsyncMock()

        await connection_manager.connect(old_ws, "task-1")
        await connection_manager.connect(mock_websocket, "task-1")

        old_ws.close.assert_called_once()
        assert connection_manager.is_connected("task-1")

    @pytest.mark.asyncio
    async def test_send_event(self, connection_manager, mock_websocket):
        """Test sending events"""
        await connection_manager.connect(mock_websocket, "task-1")

        result = await connection_manager.send_event(
            "task-1",
            "output",
            {"message": "Hello"}
        )

        assert result is True
        mock_websocket.send_json.assert_called()

    @pytest.mark.asyncio
    async def test_send_event_disconnected(self, connection_manager):
        """Test sending to disconnected task"""
        result = await connection_manager.send_event(
            "nonexistent",
            "output",
            {"message": "Hello"},
            queue_if_disconnected=True
        )

        # Should return True because it was queued
        assert result is True

    @pytest.mark.asyncio
    async def test_get_stats(self, connection_manager, mock_websocket):
        """Test getting stats"""
        await connection_manager.connect(mock_websocket, "task-1")

        stats = await connection_manager.get_stats()

        assert stats["active_connections"] == 1
        assert stats["max_connections"] == 5
```

### Task 5: Isolated Executor Tests

**File to Create:** `tests/test_isolated_executor.py`

```python
"""
Tests for IsolatedTaskExecutor
"""

import pytest
import asyncio
from unittest.mock import AsyncMock

from backend.execution.isolated_executor import IsolatedTaskExecutor


class TestIsolatedExecutor:
    """Tests for IsolatedTaskExecutor"""

    @pytest.fixture
    def executor(self):
        return IsolatedTaskExecutor(max_workers=2)

    @pytest.mark.asyncio
    async def test_max_workers_limit(self, executor):
        """Test max workers limit"""
        outputs = []

        async def callback(event_type, data):
            outputs.append((event_type, data))

        # This is a simplified test - actual execution would require CMBAgent
        # For unit testing, we verify the executor initializes correctly
        assert executor.max_workers == 2

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self, executor):
        """Test cancelling non-existent task"""
        result = await executor.cancel("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_active_tasks(self, executor):
        """Test getting active task list"""
        tasks = await executor.get_active_tasks()
        assert tasks == []
```

### Task 6: Integration Tests

**File to Create:** `tests/test_integration.py`

```python
"""
Integration tests for the WebSocket robustness features
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Note: These tests require the full application stack
# Run with: pytest tests/test_integration.py -v


class TestSessionAPI:
    """Integration tests for session API"""

    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    def test_create_list_delete_session(self, client):
        """Test full session lifecycle via API"""
        # Create
        response = client.post("/api/sessions", json={
            "mode": "copilot",
            "config": {"model": "gpt-4"},
            "name": "Test Integration"
        })
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # List
        response = client.get("/api/sessions")
        assert response.status_code == 200
        sessions = response.json()["sessions"]
        assert any(s["session_id"] == session_id for s in sessions)

        # Get
        response = client.get(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["session_id"] == session_id

        # Delete
        response = client.delete(f"/api/sessions/{session_id}")
        assert response.status_code == 200

        # Verify deleted
        response = client.get(f"/api/sessions/{session_id}")
        assert response.status_code == 404
```

## Test Commands

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_session_manager.py -v

# Run with coverage
pytest tests/ --cov=backend --cov-report=html

# Run integration tests only
pytest tests/test_integration.py -v
```

## Verification Criteria

### Must Pass
- [ ] All unit tests pass
- [ ] Test coverage > 70% for new code
- [ ] Integration tests pass
- [ ] No test warnings

## Success Criteria

Stage 12 is complete when:
1. ✅ All test files created
2. ✅ Tests pass
3. ✅ Coverage > 70%
4. ✅ No regressions

## Next Stage

Once Stage 12 is verified complete, proceed to:
**Stage 13: Load Testing**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-11
