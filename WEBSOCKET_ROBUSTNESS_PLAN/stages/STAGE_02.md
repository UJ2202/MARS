# Stage 2: Database Schema - Approvals & Connections

**Phase:** 0 - Foundation
**Dependencies:** Stage 1 (session_states table)
**Risk Level:** Low
**Estimated Time:** 2-3 hours

## Objectives

1. Create `approval_requests` table for HITL approval persistence
2. Create `active_connections` table for multi-instance connection tracking
3. Add proper indexes for timeout queries
4. Create Alembic migration

## Current State Analysis

### What We Have
- `WebSocketApprovalManager` with class variables (in-memory, lost on restart)
- No tracking of which server instance holds a connection
- Approvals can hang forever if user disconnects

### What We Need
- Persistent approval requests with timeout
- Connection tracking for potential multi-instance deployment
- Cleanup mechanism for expired approvals

## Pre-Stage Verification

### Check Prerequisites
1. Stage 1 complete (session_states table exists)
2. Database connection works

```bash
# Verify Stage 1 complete
python -c "
from cmbagent.database import get_db_session
from cmbagent.database.models import SessionState
db = get_db_session()
print('SessionState table:', db.query(SessionState).count(), 'rows')
db.close()
"
```

## Implementation Tasks

### Task 1: Create ApprovalRequest Model

**Objective:** Add SQLAlchemy model for persistent approvals

**File to Modify:** `cmbagent/database/models.py`

**Add after SessionState model:**

```python
class ApprovalRequest(Base):
    """Persistent approval request for HITL workflows"""
    __tablename__ = "approval_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)

    # Request details
    approval_type = Column(String(50), nullable=False)  # plan_approval, step_approval, error_recovery, tool_call
    context = Column(JSON, nullable=False)              # What's being approved (serialized)

    # Resolution
    status = Column(String(20), default="pending", index=True)  # pending, resolved, expired, cancelled
    resolution = Column(String(20), nullable=True)              # approved, rejected, modified
    result = Column(JSON, nullable=True)                        # Resolution details

    # Timing
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    workflow_run = relationship("WorkflowRun", back_populates="approval_requests")
    session = relationship("Session", back_populates="approval_requests")

    # Indexes for efficient timeout queries
    __table_args__ = (
        Index("idx_approval_run_status", "run_id", "status"),
        Index("idx_approval_expires_pending", "expires_at", postgresql_where=text("status = 'pending'")),
        Index("idx_approval_session", "session_id"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "approval_type": self.approval_type,
            "context": self.context,
            "status": self.status,
            "resolution": self.resolution,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    @classmethod
    def create_pending(cls, run_id: str, approval_type: str, context: dict,
                       timeout_seconds: int = 300, session_id: str = None):
        """Factory method to create a pending approval request"""
        from datetime import datetime, timezone, timedelta
        return cls(
            run_id=run_id,
            session_id=session_id,
            approval_type=approval_type,
            context=context,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds),
        )
```

**Update WorkflowRun model to add relationship:**

```python
# In WorkflowRun class, add:
approval_requests = relationship("ApprovalRequest", back_populates="workflow_run", cascade="all, delete-orphan")
```

**Update Session model to add relationship:**

```python
# In Session class, add:
approval_requests = relationship("ApprovalRequest", back_populates="session")
```

### Task 2: Create ActiveConnection Model

**Objective:** Track WebSocket connections for multi-instance awareness

**File to Modify:** `cmbagent/database/models.py`

**Add after ApprovalRequest model:**

```python
class ActiveConnection(Base):
    """Track active WebSocket connections for multi-instance deployment"""
    __tablename__ = "active_connections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(100), nullable=False, unique=True, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)

    # Server instance tracking (for routing in multi-instance setup)
    server_instance = Column(String(100), nullable=True)  # hostname or instance ID

    # Timing
    connected_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    last_heartbeat = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_connection_heartbeat", "last_heartbeat"),
        Index("idx_connection_session", "session_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "server_instance": self.server_instance,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
        }
```

### Task 3: Create Alembic Migration

**Objective:** Generate migration file for new tables

**File to Create:** `cmbagent/database/migrations/versions/002_add_approvals_connections.py`

```python
"""Add approval_requests and active_connections tables

Revision ID: 002_approvals_connections
Revises: 001_session_states
Create Date: 2026-02-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '002_approvals_connections'
down_revision = '001_session_states'
branch_labels = None
depends_on = None


def upgrade():
    # Create approval_requests table
    op.create_table(
        'approval_requests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('workflow_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id', ondelete='SET NULL'), nullable=True),

        # Request details
        sa.Column('approval_type', sa.String(50), nullable=False),
        sa.Column('context', sa.JSON, nullable=False),

        # Resolution
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('resolution', sa.String(20), nullable=True),
        sa.Column('result', sa.JSON, nullable=True),

        # Timing
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Create indexes for approval_requests
    op.create_index('idx_approval_run_id', 'approval_requests', ['run_id'])
    op.create_index('idx_approval_session_id', 'approval_requests', ['session_id'])
    op.create_index('idx_approval_status', 'approval_requests', ['status'])
    op.create_index('idx_approval_run_status', 'approval_requests', ['run_id', 'status'])
    op.create_index('idx_approval_expires', 'approval_requests', ['expires_at'])

    # Create active_connections table
    op.create_table(
        'active_connections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(100), nullable=False, unique=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('server_instance', sa.String(100), nullable=True),
        sa.Column('connected_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('last_heartbeat', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes for active_connections
    op.create_index('idx_connection_task_id', 'active_connections', ['task_id'])
    op.create_index('idx_connection_session_id', 'active_connections', ['session_id'])
    op.create_index('idx_connection_heartbeat', 'active_connections', ['last_heartbeat'])


def downgrade():
    # Drop active_connections
    op.drop_index('idx_connection_heartbeat')
    op.drop_index('idx_connection_session_id')
    op.drop_index('idx_connection_task_id')
    op.drop_table('active_connections')

    # Drop approval_requests
    op.drop_index('idx_approval_expires')
    op.drop_index('idx_approval_run_status')
    op.drop_index('idx_approval_status')
    op.drop_index('idx_approval_session_id')
    op.drop_index('idx_approval_run_id')
    op.drop_table('approval_requests')
```

### Task 4: Run Migration

**Objective:** Apply migration to database

**Commands:**
```bash
cd /srv/projects/mas/mars/denario/cmbagent

# Check current state
alembic current

# Run migration
alembic upgrade head

# Verify tables exist
python -c "
from cmbagent.database import get_db_session
from cmbagent.database.models import ApprovalRequest, ActiveConnection
db = get_db_session()
print('ApprovalRequest table OK')
print('ActiveConnection table OK')
db.close()
"
```

## Files Summary

### Files to Modify
- `cmbagent/database/models.py` - Add ApprovalRequest and ActiveConnection models

### Files to Create
- `cmbagent/database/migrations/versions/002_add_approvals_connections.py`

## Verification Criteria

### Must Pass
- [ ] Migration runs successfully
- [ ] `approval_requests` table exists
- [ ] `active_connections` table exists
- [ ] Foreign keys work correctly
- [ ] Can insert and query records

### Test Script
```python
# test_stage_2.py
from cmbagent.database import get_db_session
from cmbagent.database.models import Session, WorkflowRun, ApprovalRequest, ActiveConnection
import uuid
from datetime import datetime, timezone, timedelta

def test_approval_requests():
    db = get_db_session()
    try:
        # Create parent records
        session = Session(id=str(uuid.uuid4()), name="Test", status="active")
        db.add(session)
        db.commit()

        run = WorkflowRun(
            id=str(uuid.uuid4()),
            session_id=session.id,
            task_description="Test task",
            status="executing"
        )
        db.add(run)
        db.commit()

        # Create approval request
        approval = ApprovalRequest.create_pending(
            run_id=run.id,
            approval_type="plan_approval",
            context={"plan": "test plan"},
            timeout_seconds=300,
            session_id=session.id
        )
        db.add(approval)
        db.commit()

        # Query back
        loaded = db.query(ApprovalRequest).filter(ApprovalRequest.run_id == run.id).first()
        assert loaded is not None
        assert loaded.status == "pending"
        assert loaded.expires_at > datetime.now(timezone.utc)
        print("✅ ApprovalRequest CRUD works")

        # Test timeout query
        pending = db.query(ApprovalRequest).filter(
            ApprovalRequest.status == "pending",
            ApprovalRequest.expires_at > datetime.now(timezone.utc)
        ).all()
        assert len(pending) == 1
        print("✅ Timeout query works")

        # Cleanup
        db.delete(run)  # Should cascade
        db.delete(session)
        db.commit()

    finally:
        db.rollback()
        db.close()

def test_active_connections():
    db = get_db_session()
    try:
        conn = ActiveConnection(
            task_id="test_task_123",
            server_instance="worker-1"
        )
        db.add(conn)
        db.commit()

        # Query by task_id
        loaded = db.query(ActiveConnection).filter(
            ActiveConnection.task_id == "test_task_123"
        ).first()
        assert loaded is not None
        print("✅ ActiveConnection CRUD works")

        # Update heartbeat
        loaded.last_heartbeat = datetime.now(timezone.utc)
        db.commit()
        print("✅ Heartbeat update works")

        # Cleanup
        db.delete(loaded)
        db.commit()

    finally:
        db.rollback()
        db.close()

if __name__ == "__main__":
    test_approval_requests()
    test_active_connections()
    print("\n✅ All Stage 2 tests passed!")
```

## Common Issues and Solutions

### Issue 1: workflow_runs table doesn't exist
**Symptom:** `FOREIGN KEY constraint failed` for run_id
**Solution:** Ensure workflow_runs table exists. Check existing migrations.

### Issue 2: Partial index syntax error
**Symptom:** Error with `postgresql_where` on SQLite
**Solution:** Remove partial index syntax for SQLite, use regular index:
```python
# Instead of partial index, use regular index
Index("idx_approval_expires", "expires_at")
```

## Rollback Procedure

```bash
# Rollback this migration only
alembic downgrade 001_session_states

# Or drop tables manually
python -c "
from cmbagent.database.base import engine
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text('DROP TABLE IF EXISTS active_connections'))
    conn.execute(text('DROP TABLE IF EXISTS approval_requests'))
    conn.commit()
"

# Revert model changes
git checkout cmbagent/database/models.py
```

## Success Criteria

Stage 2 is complete when:
1. ✅ `approval_requests` table exists with all columns
2. ✅ `active_connections` table exists with all columns
3. ✅ Can create approval requests with timeout
4. ✅ Can track connections with heartbeat
5. ✅ All verification tests pass

## Next Stage

Once Stage 2 is verified complete, proceed to:
**Stage 3: Session Manager Service**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-11
