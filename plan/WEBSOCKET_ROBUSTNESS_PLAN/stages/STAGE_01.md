# Stage 1: Database Schema - Sessions

**Phase:** 0 - Foundation
**Dependencies:** None
**Risk Level:** Low
**Estimated Time:** 2-3 hours

## Objectives

1. Create `session_states` table for persistent session storage
2. Add indexes for efficient querying
3. Create Alembic migration
4. Verify migration runs successfully

## Current State Analysis

### What We Have
- `sessions` table exists in `cmbagent/database/models.py`
- In-memory session storage in `_active_copilot_sessions` dict
- Basic session tracking but no state persistence

### What We Need
- `session_states` table to store serializable session data
- JSON columns for conversation history, context, plan data
- Status tracking for session lifecycle
- Version column for optimistic locking

## Pre-Stage Verification

### Check Prerequisites
1. Database connection works
2. Alembic is configured
3. Existing tables are accessible

### Test Current State
```bash
# Verify database exists
ls -la ~/.cmbagent/cmbagent.db

# Or check environment variable
echo $CMBAGENT_DATABASE_URL

# Test connection
cd /srv/projects/mas/mars/denario/cmbagent
python -c "from cmbagent.database import get_db_session; db = get_db_session(); print('DB OK')"
```

## Implementation Tasks

### Task 1: Create SessionState Model

**Objective:** Add SQLAlchemy model for session_states table

**File to Modify:** `cmbagent/database/models.py`

**Add after Session model (~line 47):**

```python
class SessionState(Base):
    """Persistent session state for resumable workflows"""
    __tablename__ = "session_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    mode = Column(String(50), nullable=False)  # copilot, planning-control, hitl-interactive

    # Serialized state (JSON)
    conversation_history = Column(JSON, nullable=True)  # List of message dicts
    context_variables = Column(JSON, nullable=True)     # Key-value context
    plan_data = Column(JSON, nullable=True)             # Plan structure if applicable

    # Progress tracking
    current_phase = Column(String(50), nullable=True)   # planning, execution, review
    current_step = Column(Integer, nullable=True)       # Current step number

    # Lifecycle
    status = Column(String(20), default="active", index=True)  # active, suspended, completed, expired
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Optimistic locking
    version = Column(Integer, default=1)

    # Relationships
    session = relationship("Session", back_populates="session_states")

    # Indexes
    __table_args__ = (
        Index("idx_session_states_session_status", "session_id", "status"),
        Index("idx_session_states_mode", "mode"),
        Index("idx_session_states_updated", "updated_at"),
    )
```

**Also update Session model to add relationship:**

```python
# In Session class, add:
session_states = relationship("SessionState", back_populates="session", cascade="all, delete-orphan")
```

**Verification:**
- [ ] Model added without syntax errors
- [ ] Import uuid at top if not present
- [ ] Relationship added to Session model

### Task 2: Create Alembic Migration

**Objective:** Generate migration file for the new table

**File to Create:** `cmbagent/database/migrations/versions/001_add_session_states.py`

```python
"""Add session_states table

Revision ID: 001_session_states
Revises: [previous_revision or None]
Create Date: 2026-02-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_session_states'
down_revision = None  # Update this to previous migration if exists
branch_labels = None
depends_on = None


def upgrade():
    # Create session_states table
    op.create_table(
        'session_states',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mode', sa.String(50), nullable=False),

        # JSON columns for state
        sa.Column('conversation_history', sa.JSON, nullable=True),
        sa.Column('context_variables', sa.JSON, nullable=True),
        sa.Column('plan_data', sa.JSON, nullable=True),

        # Progress
        sa.Column('current_phase', sa.String(50), nullable=True),
        sa.Column('current_step', sa.Integer, nullable=True),

        # Lifecycle
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),

        # Optimistic locking
        sa.Column('version', sa.Integer, server_default='1'),
    )

    # Create indexes
    op.create_index('idx_session_states_session_id', 'session_states', ['session_id'])
    op.create_index('idx_session_states_status', 'session_states', ['status'])
    op.create_index('idx_session_states_session_status', 'session_states', ['session_id', 'status'])
    op.create_index('idx_session_states_mode', 'session_states', ['mode'])
    op.create_index('idx_session_states_updated', 'session_states', ['updated_at'])


def downgrade():
    # Drop indexes first
    op.drop_index('idx_session_states_updated')
    op.drop_index('idx_session_states_mode')
    op.drop_index('idx_session_states_session_status')
    op.drop_index('idx_session_states_status')
    op.drop_index('idx_session_states_session_id')

    # Drop table
    op.drop_table('session_states')
```

**Verification:**
- [ ] Migration file created
- [ ] Revision ID is unique
- [ ] down_revision points to correct previous migration (or None)

### Task 3: Run Migration

**Objective:** Apply migration to database

**Commands:**
```bash
cd /srv/projects/mas/mars/denario/cmbagent

# Check current migration status
alembic current

# Run migration
alembic upgrade head

# Verify table exists
python -c "
from cmbagent.database import get_db_session
from cmbagent.database.models import SessionState
db = get_db_session()
# Try to query (should return empty, no error)
result = db.query(SessionState).first()
print('SessionState table exists and is queryable')
db.close()
"
```

**Verification:**
- [ ] Migration runs without errors
- [ ] Table exists in database
- [ ] Indexes created

### Task 4: Add Helper Methods to Model

**Objective:** Add convenience methods for serialization

**File to Modify:** `cmbagent/database/models.py`

**Add to SessionState class:**

```python
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "mode": self.mode,
            "conversation_history": self.conversation_history or [],
            "context_variables": self.context_variables or {},
            "plan_data": self.plan_data,
            "current_phase": self.current_phase,
            "current_step": self.current_step,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "version": self.version,
        }

    @classmethod
    def create_for_session(cls, session_id: str, mode: str, **kwargs):
        """Factory method to create new session state"""
        return cls(
            session_id=session_id,
            mode=mode,
            conversation_history=kwargs.get("conversation_history", []),
            context_variables=kwargs.get("context_variables", {}),
            plan_data=kwargs.get("plan_data"),
            current_phase=kwargs.get("current_phase", "init"),
            status="active",
        )
```

**Verification:**
- [ ] Methods added to model
- [ ] No syntax errors

## Files Summary

### Files to Modify
- `cmbagent/database/models.py` - Add SessionState model and Session relationship

### Files to Create
- `cmbagent/database/migrations/versions/001_add_session_states.py`

## Verification Criteria

### Must Pass
- [ ] Migration runs successfully (`alembic upgrade head`)
- [ ] `session_states` table exists in database
- [ ] Can insert and query SessionState records
- [ ] Foreign key to sessions table works
- [ ] Indexes are created

### Should Pass
- [ ] Model methods (to_dict, create_for_session) work
- [ ] Cascade delete works (delete session → delete session_states)

### Test Script
```python
# test_stage_1.py
from cmbagent.database import get_db_session
from cmbagent.database.models import Session, SessionState
import uuid

def test_session_state_crud():
    db = get_db_session()
    try:
        # Create parent session
        session = Session(
            id=str(uuid.uuid4()),
            name="Test Session",
            status="active"
        )
        db.add(session)
        db.commit()

        # Create session state
        state = SessionState.create_for_session(
            session_id=session.id,
            mode="copilot",
            conversation_history=[{"role": "user", "content": "Hello"}],
            context_variables={"key": "value"}
        )
        db.add(state)
        db.commit()

        # Query back
        loaded = db.query(SessionState).filter(SessionState.session_id == session.id).first()
        assert loaded is not None
        assert loaded.mode == "copilot"
        assert len(loaded.conversation_history) == 1
        print("✅ SessionState CRUD works")

        # Test cascade delete
        db.delete(session)
        db.commit()
        orphan = db.query(SessionState).filter(SessionState.id == state.id).first()
        assert orphan is None
        print("✅ Cascade delete works")

    finally:
        db.rollback()
        db.close()

if __name__ == "__main__":
    test_session_state_crud()
```

## Common Issues and Solutions

### Issue 1: Alembic not configured
**Symptom:** `alembic: command not found` or `FAILED: No module named 'alembic'`
**Solution:**
```bash
pip install alembic
alembic init cmbagent/database/migrations  # If not already initialized
```

### Issue 2: Foreign key constraint fails
**Symptom:** `FOREIGN KEY constraint failed`
**Solution:** Ensure sessions table exists and has compatible id column type (String(36))

### Issue 3: JSON column not supported
**Symptom:** `JSON type not supported` (SQLite)
**Solution:** SQLite supports JSON natively since 3.9. If older version, use TEXT column with json.dumps/loads

## Rollback Procedure

If Stage 1 causes issues:
```bash
# Rollback migration
alembic downgrade -1

# Or manually drop table
python -c "
from cmbagent.database.base import engine
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text('DROP TABLE IF EXISTS session_states'))
    conn.commit()
print('Table dropped')
"

# Revert model changes
git checkout cmbagent/database/models.py
```

## Success Criteria

Stage 1 is complete when:
1. ✅ `session_states` table exists in database
2. ✅ Can create, read, update SessionState records
3. ✅ Foreign key relationship to sessions works
4. ✅ Cascade delete works
5. ✅ All verification tests pass

## Next Stage

Once Stage 1 is verified complete, proceed to:
**Stage 2: Database Schema - Approvals & Connections**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-11
