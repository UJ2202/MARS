"""
Shared fixtures for WebSocket robustness test suite.

Provides:
- In-memory SQLite database for isolated tests
- SessionManager with test DB
- WebSocketApprovalManager with test DB
- Mock WebSocket for connection tests
"""

import asyncio
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure the project root and backend are importable
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


@pytest.fixture
def db_tables(db_engine):
    """Create all tables in the test database."""
    from cmbagent.database.base import Base
    from cmbagent.database.models import (  # noqa: F401 - import for side-effects
        Session, SessionState, Project, WorkflowRun, WorkflowStep,
        DAGNode, DAGEdge, Checkpoint, Message, CostRecord,
        ApprovalRequest, ActiveConnection, Branch, WorkflowMetric,
        File, StateHistory, ExecutionEvent,
    )
    Base.metadata.create_all(db_engine)
    yield db_engine
    Base.metadata.drop_all(db_engine)


@pytest.fixture
def db_session_factory(db_tables):
    """Return a session factory bound to the test engine."""
    factory = sessionmaker(
        bind=db_tables,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    return factory


@pytest.fixture
def db_session(db_session_factory):
    """Return a database session that is cleaned up after the test."""
    session = db_session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def db_factory(db_session_factory):
    """Return a callable that creates new DB sessions (for service injection)."""
    return db_session_factory


# ---------------------------------------------------------------------------
# SessionManager fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def session_manager(db_factory):
    """A SessionManager using the test database factory."""
    from backend.services.session_manager import SessionManager
    return SessionManager(db_factory=db_factory)


# ---------------------------------------------------------------------------
# WebSocketApprovalManager fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ws_events():
    """Capture WebSocket events sent by the approval manager."""
    events: List[Dict[str, Any]] = []

    def send(event_type: str, data: dict):
        events.append({"event_type": event_type, "data": data})

    return events, send


@pytest.fixture
def approval_manager(ws_events, db_factory):
    """WebSocketApprovalManager with test DB and captured events."""
    from cmbagent.database.websocket_approval_manager import WebSocketApprovalManager

    events, send = ws_events
    mgr = WebSocketApprovalManager(send, run_id="test-run-001", db_factory=db_factory)
    yield mgr, events

    # Clean up class-level state
    WebSocketApprovalManager._pending.clear()


# ---------------------------------------------------------------------------
# Mock WebSocket
# ---------------------------------------------------------------------------

class MockWebSocket:
    """A mock WebSocket that records sent messages."""

    def __init__(self):
        self.sent: List[dict] = []
        self.closed = False
        self._accept_called = False

    async def accept(self):
        self._accept_called = True

    async def send_json(self, data: dict):
        if self.closed:
            raise RuntimeError("WebSocket is closed")
        self.sent.append(data)

    async def receive_json(self):
        # Block forever (test should not call this without setup)
        await asyncio.sleep(9999)

    async def close(self, code: int = 1000, reason: str = ""):
        self.closed = True


@pytest.fixture
def mock_websocket():
    """Return a fresh MockWebSocket."""
    return MockWebSocket()


# ---------------------------------------------------------------------------
# ConnectionManager fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def connection_manager(db_factory):
    """A ConnectionManager with test DB factory."""
    from backend.services.connection_manager import ConnectionManager
    return ConnectionManager(max_connections=10, db_factory=db_factory)


# ---------------------------------------------------------------------------
# Helper: create a workflow run so FK constraints pass for approvals
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_session_and_run(db_session):
    """Create a session + workflow run in the test DB for FK references."""
    from cmbagent.database.models import Session as SessionModel, WorkflowRun

    session = SessionModel(
        id="test-session-001",
        name="Test Session",
        status="active",
    )
    db_session.add(session)
    db_session.flush()

    run = WorkflowRun(
        id="test-run-001",
        session_id="test-session-001",
        mode="copilot",
        agent="engineer",
        model="gpt-4",
        status="executing",
    )
    db_session.add(run)
    db_session.commit()

    return session, run
