# Stage 1: ExecutionEvent Model and Database Schema

**Phase:** 1 - Event Capture Infrastructure
**Estimated Time:** 60 minutes
**Dependencies:** Stages 1-4 from main implementation plan must be complete
**Risk Level:** Low

## Objectives

1. Create ExecutionEvent SQLAlchemy model with comprehensive event tracking
2. Enhance File and Message models with event/node linkage
3. Create Alembic migration for schema changes
4. Implement repository methods for event access
5. Add event querying and filtering capabilities
6. Support nested events (parent-child relationships)
7. Ensure backward compatibility with existing schema

## Current State Analysis

### What We Have
- DAGNode table tracking stage-level nodes
- File table tracking generated files (linked to run_id, step_id)
- Message table tracking agent messages (linked to run_id, step_id)
- No fine-grained execution event tracking
- No linkage between files/messages and specific actions

### What We Need
- ExecutionEvent table for all execution actions
- File.event_id and File.node_id for traceability
- Message.event_id and Message.node_id for traceability
- Support for nested events (agent → tool → code → file)
- Efficient querying by node, agent, type, timestamp

## Pre-Stage Verification

### Check Prerequisites
1. Stage 2 (Database Schema) complete and verified
2. Stage 4 (DAG System) complete and verified
3. Alembic migrations working correctly
4. Can create DAGNodes and query them
5. Database session management working

### Verification Commands
```bash
# Check current database schema
python -c "from cmbagent.database import init_database; init_database()"

# Check Alembic status
cd cmbagent/database && alembic current

# Verify DAGNode table exists
python -c "from cmbagent.database.models import DAGNode; print('DAGNode model available')"
```

## Implementation Tasks

### Task 1: Create ExecutionEvent Model

**Objective:** Define comprehensive event tracking model

**Implementation:**

Edit `cmbagent/database/models.py` - Add new ExecutionEvent model:

```python
class ExecutionEvent(Base):
    """
    Fine-grained execution event tracking for workflow traceability.
    
    Captures all actions within a workflow stage including agent calls,
    tool invocations, code execution, file generation, and agent handoffs.
    Supports nested events for hierarchical action tracking.
    """
    __tablename__ = "execution_events"
    
    # Identity
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # Relationships
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), 
                   nullable=False, index=True)
    node_id = Column(String(36), ForeignKey("dag_nodes.id", ondelete="CASCADE"), 
                    nullable=True, index=True)
    step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="SET NULL"), 
                    nullable=True, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), 
                       nullable=False, index=True)
    parent_event_id = Column(String(36), ForeignKey("execution_events.id", ondelete="SET NULL"), 
                            nullable=True, index=True)
    
    # Event Classification
    event_type = Column(String(50), nullable=False, index=True)
    # Types: agent_call, tool_call, code_exec, file_gen, handoff, 
    #        approval_requested, state_transition, error, info
    event_subtype = Column(String(50), nullable=True)
    # Subtypes: start, complete, error, info, pending, approved, rejected
    
    # Agent Context
    agent_name = Column(String(100), nullable=True, index=True)
    agent_role = Column(String(50), nullable=True)  # primary, helper, validator
    
    # Timing
    timestamp = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc), 
                      index=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    duration_ms = Column(Integer, nullable=True)  # Duration in milliseconds
    
    # Execution Data
    inputs = Column(JSON, nullable=True)  # Input parameters, context
    outputs = Column(JSON, nullable=True)  # Results, return values
    error_message = Column(Text, nullable=True)
    
    # Metadata
    meta = Column(JSON, nullable=True)
    # Contains: model, tokens, cost, temperature, custom data
    execution_order = Column(Integer, nullable=False)  # Sequence within node
    depth = Column(Integer, nullable=False, default=0)  # Nesting depth (0=top level)
    
    # Status
    status = Column(String(50), nullable=False, default="completed")
    # Status: pending, running, completed, failed, skipped
    
    # Relationships
    run = relationship("WorkflowRun", back_populates="execution_events")
    node = relationship("DAGNode", back_populates="execution_events")
    step = relationship("WorkflowStep", back_populates="execution_events")
    session = relationship("Session", back_populates="execution_events")
    
    # Self-referential for nested events
    child_events = relationship("ExecutionEvent", 
                               back_populates="parent_event",
                               cascade="all, delete-orphan")
    parent_event = relationship("ExecutionEvent", 
                               remote_side=[id],
                               back_populates="child_events")
    
    # Files and messages created by this event
    files = relationship("File", back_populates="event", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="event", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_events_run_order", "run_id", "execution_order"),
        Index("idx_events_node_order", "node_id", "execution_order"),
        Index("idx_events_type_subtype", "event_type", "event_subtype"),
        Index("idx_events_session_timestamp", "session_id", "timestamp"),
        Index("idx_events_parent", "parent_event_id"),
    )
    
    def __repr__(self):
        return (f"<ExecutionEvent(id={self.id}, type={self.event_type}, "
                f"agent={self.agent_name}, order={self.execution_order})>")
```

**Files to Modify:**
- `cmbagent/database/models.py` (add ExecutionEvent class)

**Verification:**
- ExecutionEvent model imports successfully
- All fields defined with correct types
- Relationships defined correctly
- Indexes specified

### Task 2: Enhance Existing Models

**Objective:** Add event and node linkage to File and Message models

**Implementation:**

Edit `cmbagent/database/models.py` - Enhance File model:

```python
# In the File class, add these columns:
event_id = Column(String(36), ForeignKey("execution_events.id", ondelete="SET NULL"), 
                 nullable=True, index=True)
node_id = Column(String(36), ForeignKey("dag_nodes.id", ondelete="CASCADE"), 
                nullable=True, index=True)

# Add relationships:
event = relationship("ExecutionEvent", back_populates="files")
node = relationship("DAGNode", back_populates="files")

# Add to __table_args__:
Index("idx_files_event", "event_id"),
Index("idx_files_node", "node_id"),
```

Edit `cmbagent/database/models.py` - Enhance Message model:

```python
# In the Message class, add these columns:
event_id = Column(String(36), ForeignKey("execution_events.id", ondelete="SET NULL"), 
                 nullable=True, index=True)
node_id = Column(String(36), ForeignKey("dag_nodes.id", ondelete="CASCADE"), 
                nullable=True, index=True)

# Add relationships:
event = relationship("ExecutionEvent", back_populates="messages")
node = relationship("DAGNode", back_populates="messages")

# Add to __table_args__:
Index("idx_messages_event", "event_id"),
Index("idx_messages_node", "node_id"),
```

Edit `cmbagent/database/models.py` - Enhance Session model:

```python
# In the Session class relationships, add:
execution_events = relationship("ExecutionEvent", back_populates="session", 
                               cascade="all, delete-orphan")
```

Edit `cmbagent/database/models.py` - Enhance WorkflowRun model:

```python
# In the WorkflowRun class relationships, add:
execution_events = relationship("ExecutionEvent", back_populates="run", 
                               cascade="all, delete-orphan")
```

Edit `cmbagent/database/models.py` - Enhance WorkflowStep model:

```python
# In the WorkflowStep class relationships, add:
execution_events = relationship("ExecutionEvent", back_populates="step", 
                               cascade="all, delete-orphan")
```

Edit `cmbagent/database/models.py` - Enhance DAGNode model:

```python
# In the DAGNode class relationships, add:
execution_events = relationship("ExecutionEvent", back_populates="node", 
                               cascade="all, delete-orphan")
files = relationship("File", back_populates="node", cascade="all, delete-orphan")
messages = relationship("Message", back_populates="node", cascade="all, delete-orphan")
```

**Files to Modify:**
- `cmbagent/database/models.py` (enhance File, Message, Session, WorkflowRun, WorkflowStep, DAGNode)

**Verification:**
- All new columns added
- Relationships bidirectional
- Foreign keys correct
- Indexes added

### Task 3: Create Alembic Migration

**Objective:** Generate migration for schema changes

**Implementation:**

Generate new migration:

```bash
cd cmbagent/database
alembic revision --autogenerate -m "add_execution_events_and_enhance_artifacts"
```

Review and edit the generated migration file to ensure:

```python
"""add_execution_events_and_enhance_artifacts

Revision ID: <generated>
Revises: <previous_revision>
Create Date: 2026-01-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON

# revision identifiers
revision = '<generated>'
down_revision = '<previous_revision>'
branch_labels = None
depends_on = None


def upgrade():
    # Create execution_events table
    op.create_table('execution_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('node_id', sa.String(length=36), nullable=True),
        sa.Column('step_id', sa.String(length=36), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('parent_event_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_subtype', sa.String(length=50), nullable=True),
        sa.Column('agent_name', sa.String(length=100), nullable=True),
        sa.Column('agent_role', sa.String(length=50), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('inputs', JSON(), nullable=True),
        sa.Column('outputs', JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('meta', JSON(), nullable=True),
        sa.Column('execution_order', sa.Integer(), nullable=False),
        sa.Column('depth', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['workflow_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['dag_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['workflow_steps.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_event_id'], ['execution_events.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for execution_events
    op.create_index('idx_events_run_order', 'execution_events', ['run_id', 'execution_order'])
    op.create_index('idx_events_node_order', 'execution_events', ['node_id', 'execution_order'])
    op.create_index('idx_events_type_subtype', 'execution_events', ['event_type', 'event_subtype'])
    op.create_index('idx_events_session_timestamp', 'execution_events', ['session_id', 'timestamp'])
    op.create_index('idx_events_parent', 'execution_events', ['parent_event_id'])
    op.create_index(op.f('ix_execution_events_run_id'), 'execution_events', ['run_id'])
    op.create_index(op.f('ix_execution_events_node_id'), 'execution_events', ['node_id'])
    op.create_index(op.f('ix_execution_events_step_id'), 'execution_events', ['step_id'])
    op.create_index(op.f('ix_execution_events_session_id'), 'execution_events', ['session_id'])
    op.create_index(op.f('ix_execution_events_event_type'), 'execution_events', ['event_type'])
    op.create_index(op.f('ix_execution_events_agent_name'), 'execution_events', ['agent_name'])
    op.create_index(op.f('ix_execution_events_timestamp'), 'execution_events', ['timestamp'])
    
    # Add event_id and node_id to files table
    with op.batch_alter_table('files', schema=None) as batch_op:
        batch_op.add_column(sa.Column('event_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('node_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_files_event_id', 'execution_events', ['event_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_files_node_id', 'dag_nodes', ['node_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index('idx_files_event', ['event_id'])
        batch_op.create_index('idx_files_node', ['node_id'])
    
    # Add event_id and node_id to messages table
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('event_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('node_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_messages_event_id', 'execution_events', ['event_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_messages_node_id', 'dag_nodes', ['node_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index('idx_messages_event', ['event_id'])
        batch_op.create_index('idx_messages_node', ['node_id'])


def downgrade():
    # Remove indexes from messages
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_index('idx_messages_node')
        batch_op.drop_index('idx_messages_event')
        batch_op.drop_constraint('fk_messages_node_id', type_='foreignkey')
        batch_op.drop_constraint('fk_messages_event_id', type_='foreignkey')
        batch_op.drop_column('node_id')
        batch_op.drop_column('event_id')
    
    # Remove indexes from files
    with op.batch_alter_table('files', schema=None) as batch_op:
        batch_op.drop_index('idx_files_node')
        batch_op.drop_index('idx_files_event')
        batch_op.drop_constraint('fk_files_node_id', type_='foreignkey')
        batch_op.drop_constraint('fk_files_event_id', type_='foreignkey')
        batch_op.drop_column('node_id')
        batch_op.drop_column('event_id')
    
    # Drop execution_events table and indexes
    op.drop_index('ix_execution_events_timestamp', table_name='execution_events')
    op.drop_index('ix_execution_events_agent_name', table_name='execution_events')
    op.drop_index('ix_execution_events_event_type', table_name='execution_events')
    op.drop_index('ix_execution_events_session_id', table_name='execution_events')
    op.drop_index('ix_execution_events_step_id', table_name='execution_events')
    op.drop_index('ix_execution_events_node_id', table_name='execution_events')
    op.drop_index('ix_execution_events_run_id', table_name='execution_events')
    op.drop_index('idx_events_parent', table_name='execution_events')
    op.drop_index('idx_events_session_timestamp', table_name='execution_events')
    op.drop_index('idx_events_type_subtype', table_name='execution_events')
    op.drop_index('idx_events_node_order', table_name='execution_events')
    op.drop_index('idx_events_run_order', table_name='execution_events')
    op.drop_table('execution_events')
```

Apply migration:

```bash
alembic upgrade head
```

**Files to Create:**
- `cmbagent/database/migrations/versions/<timestamp>_add_execution_events.py`

**Verification:**
- Migration generates without errors
- `alembic upgrade head` succeeds
- `alembic current` shows new revision
- Database tables created correctly
- Can rollback with `alembic downgrade -1`

### Task 4: Create Event Repository

**Objective:** Implement data access layer for events

**Implementation:**

Edit `cmbagent/database/repository.py` - Add EventRepository class:

```python
class EventRepository:
    """Repository for execution event operations."""
    
    def __init__(self, db_session: Session, session_id: str):
        """
        Initialize event repository.
        
        Args:
            db_session: SQLAlchemy database session
            session_id: Current session ID for isolation
        """
        self.db = db_session
        self.session_id = session_id
    
    def create_event(
        self,
        run_id: str,
        event_type: str,
        execution_order: int,
        node_id: Optional[str] = None,
        step_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        **kwargs
    ) -> ExecutionEvent:
        """
        Create a new execution event.
        
        Args:
            run_id: Workflow run ID
            event_type: Type of event (agent_call, tool_call, etc.)
            execution_order: Sequence number within node
            node_id: Optional DAG node ID
            step_id: Optional workflow step ID
            parent_event_id: Optional parent event ID for nesting
            **kwargs: Additional event fields
            
        Returns:
            Created ExecutionEvent instance
        """
        event = ExecutionEvent(
            run_id=run_id,
            session_id=self.session_id,
            node_id=node_id,
            step_id=step_id,
            parent_event_id=parent_event_id,
            event_type=event_type,
            execution_order=execution_order,
            timestamp=datetime.now(timezone.utc),
            **kwargs
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
    
    def get_event(self, event_id: str) -> Optional[ExecutionEvent]:
        """Get event by ID."""
        return self.db.query(ExecutionEvent).filter(
            ExecutionEvent.id == event_id,
            ExecutionEvent.session_id == self.session_id
        ).first()
    
    def list_events_for_run(
        self,
        run_id: str,
        event_type: Optional[str] = None,
        agent_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[ExecutionEvent]:
        """
        List events for a workflow run.
        
        Args:
            run_id: Workflow run ID
            event_type: Optional filter by event type
            agent_name: Optional filter by agent name
            limit: Optional limit on results
            
        Returns:
            List of ExecutionEvent instances
        """
        query = self.db.query(ExecutionEvent).filter(
            ExecutionEvent.run_id == run_id,
            ExecutionEvent.session_id == self.session_id
        )
        
        if event_type:
            query = query.filter(ExecutionEvent.event_type == event_type)
        
        if agent_name:
            query = query.filter(ExecutionEvent.agent_name == agent_name)
        
        query = query.order_by(ExecutionEvent.execution_order)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def list_events_for_node(
        self,
        node_id: str,
        event_type: Optional[str] = None
    ) -> List[ExecutionEvent]:
        """
        List events for a DAG node.
        
        Args:
            node_id: DAG node ID
            event_type: Optional filter by event type
            
        Returns:
            List of ExecutionEvent instances
        """
        query = self.db.query(ExecutionEvent).filter(
            ExecutionEvent.node_id == node_id,
            ExecutionEvent.session_id == self.session_id
        )
        
        if event_type:
            query = query.filter(ExecutionEvent.event_type == event_type)
        
        return query.order_by(ExecutionEvent.execution_order).all()
    
    def get_child_events(self, parent_event_id: str) -> List[ExecutionEvent]:
        """
        Get all child events of a parent event.
        
        Args:
            parent_event_id: Parent event ID
            
        Returns:
            List of child ExecutionEvent instances
        """
        return self.db.query(ExecutionEvent).filter(
            ExecutionEvent.parent_event_id == parent_event_id,
            ExecutionEvent.session_id == self.session_id
        ).order_by(ExecutionEvent.execution_order).all()
    
    def get_event_tree(self, root_event_id: str) -> List[ExecutionEvent]:
        """
        Get full event tree from root event (recursive query).
        
        Args:
            root_event_id: Root event ID
            
        Returns:
            List of all events in tree, ordered by depth and execution_order
        """
        # Use recursive CTE for event tree
        from sqlalchemy import text
        
        query = text("""
            WITH RECURSIVE event_tree AS (
                SELECT * FROM execution_events 
                WHERE id = :root_id AND session_id = :session_id
                UNION ALL
                SELECT e.* FROM execution_events e
                INNER JOIN event_tree et ON e.parent_event_id = et.id
                WHERE e.session_id = :session_id
            )
            SELECT * FROM event_tree ORDER BY depth, execution_order
        """)
        
        result = self.db.execute(
            query, 
            {"root_id": root_event_id, "session_id": self.session_id}
        )
        
        # Convert to ExecutionEvent objects
        events = []
        for row in result:
            event = self.db.query(ExecutionEvent).filter(
                ExecutionEvent.id == row.id
            ).first()
            if event:
                events.append(event)
        
        return events
    
    def update_event(self, event_id: str, **kwargs):
        """Update event fields."""
        event = self.get_event(event_id)
        if event:
            for key, value in kwargs.items():
                if hasattr(event, key):
                    setattr(event, key, value)
            self.db.commit()
            self.db.refresh(event)
            return event
        return None
    
    def delete_event(self, event_id: str):
        """Delete an event."""
        event = self.get_event(event_id)
        if event:
            self.db.delete(event)
            self.db.commit()
            return True
        return False
    
    def get_event_statistics(self, run_id: str) -> Dict[str, Any]:
        """
        Get statistics about events for a run.
        
        Args:
            run_id: Workflow run ID
            
        Returns:
            Dictionary with event statistics
        """
        from sqlalchemy import func
        
        events = self.list_events_for_run(run_id)
        
        stats = {
            "total_events": len(events),
            "event_types": {},
            "agents_involved": set(),
            "agent_call_counts": {},
            "avg_duration_ms": 0,
            "total_duration_ms": 0
        }
        
        total_duration = 0
        duration_count = 0
        
        for event in events:
            # Count event types
            stats["event_types"][event.event_type] = \
                stats["event_types"].get(event.event_type, 0) + 1
            
            # Track agents
            if event.agent_name:
                stats["agents_involved"].add(event.agent_name)
                stats["agent_call_counts"][event.agent_name] = \
                    stats["agent_call_counts"].get(event.agent_name, 0) + 1
            
            # Calculate durations
            if event.duration_ms:
                total_duration += event.duration_ms
                duration_count += 1
        
        stats["agents_involved"] = list(stats["agents_involved"])
        stats["total_duration_ms"] = total_duration
        if duration_count > 0:
            stats["avg_duration_ms"] = total_duration / duration_count
        
        return stats
```

**Files to Modify:**
- `cmbagent/database/repository.py` (add EventRepository class)

**Verification:**
- EventRepository imports successfully
- All CRUD methods defined
- Can create and query events
- Nested event queries work
- Statistics calculation works

### Task 5: Update Database __init__.py

**Objective:** Export new components

**Implementation:**

Edit `cmbagent/database/__init__.py`:

```python
from cmbagent.database.models import (
    # ... existing imports ...
    ExecutionEvent,  # NEW
)

from cmbagent.database.repository import (
    # ... existing imports ...
    EventRepository,  # NEW
)

__all__ = [
    # ... existing exports ...
    "ExecutionEvent",
    "EventRepository",
]
```

**Files to Modify:**
- `cmbagent/database/__init__.py`

**Verification:**
- Can import ExecutionEvent from cmbagent.database
- Can import EventRepository from cmbagent.database
- No import errors

## Verification Criteria

### Must Pass
- [ ] ExecutionEvent model defined with all fields
- [ ] File and Message models enhanced with event_id and node_id
- [ ] Alembic migration created and applied successfully
- [ ] execution_events table exists in database
- [ ] files.event_id and files.node_id columns exist
- [ ] messages.event_id and messages.node_id columns exist
- [ ] All indexes created correctly
- [ ] EventRepository class implemented
- [ ] Can create ExecutionEvent instances
- [ ] Can query events by run_id, node_id, event_type
- [ ] Nested events (parent_event_id) working
- [ ] Event tree query (recursive) working
- [ ] Event statistics calculation working
- [ ] All relationships bidirectional
- [ ] Session isolation enforced

### Should Pass
- [ ] Migration can rollback cleanly
- [ ] Foreign key constraints enforced
- [ ] Cascade deletes work correctly
- [ ] Index usage verified with EXPLAIN
- [ ] No breaking changes to existing code

## Files Summary

### New Files
```
cmbagent/database/migrations/versions/<timestamp>_add_execution_events.py
```

### Modified Files
```
cmbagent/database/models.py          # Add ExecutionEvent, enhance File/Message
cmbagent/database/repository.py      # Add EventRepository
cmbagent/database/__init__.py        # Export new components
```

## Testing

Create `tests/test_stage_01_execution_events.py`:

```python
"""Tests for Stage 1: ExecutionEvent Model and Database Schema"""

import pytest
from datetime import datetime, timezone
from cmbagent.database import (
    init_database, get_db_session,
    WorkflowRepository, EventRepository,
    ExecutionEvent, File, Message
)


@pytest.fixture
def db_session():
    """Create database session for testing."""
    init_database()
    session = get_db_session()
    yield session
    session.close()


@pytest.fixture
def workflow_repo(db_session):
    """Create workflow repository."""
    return WorkflowRepository(db_session, "test_session")


@pytest.fixture
def event_repo(db_session):
    """Create event repository."""
    return EventRepository(db_session, "test_session")


def test_execution_event_model(db_session, workflow_repo, event_repo):
    """Test ExecutionEvent model creation and basic operations."""
    # Create a workflow run
    run = workflow_repo.create_run(
        task_description="Test workflow",
        mode="one_shot",
        agent="engineer",
        model="gpt-4"
    )
    
    # Create an execution event
    event = event_repo.create_event(
        run_id=run.id,
        event_type="agent_call",
        event_subtype="start",
        agent_name="engineer",
        execution_order=0,
        inputs={"message": "test"},
        meta={"model": "gpt-4"}
    )
    
    assert event.id is not None
    assert event.run_id == run.id
    assert event.event_type == "agent_call"
    assert event.agent_name == "engineer"
    assert event.execution_order == 0
    print("✓ ExecutionEvent model creation works")


def test_nested_events(db_session, workflow_repo, event_repo):
    """Test nested event relationships."""
    run = workflow_repo.create_run(
        task_description="Test workflow",
        mode="one_shot",
        agent="engineer",
        model="gpt-4"
    )
    
    # Create parent event
    parent = event_repo.create_event(
        run_id=run.id,
        event_type="agent_call",
        agent_name="engineer",
        execution_order=0,
        depth=0
    )
    
    # Create child events
    child1 = event_repo.create_event(
        run_id=run.id,
        event_type="tool_call",
        parent_event_id=parent.id,
        execution_order=1,
        depth=1
    )
    
    child2 = event_repo.create_event(
        run_id=run.id,
        event_type="code_exec",
        parent_event_id=parent.id,
        execution_order=2,
        depth=1
    )
    
    # Get child events
    children = event_repo.get_child_events(parent.id)
    assert len(children) == 2
    assert children[0].id == child1.id
    assert children[1].id == child2.id
    print("✓ Nested events work correctly")


def test_event_tree_query(db_session, workflow_repo, event_repo):
    """Test recursive event tree query."""
    run = workflow_repo.create_run(
        task_description="Test workflow",
        mode="one_shot",
        agent="engineer",
        model="gpt-4"
    )
    
    # Create event tree
    root = event_repo.create_event(
        run_id=run.id,
        event_type="agent_call",
        execution_order=0,
        depth=0
    )
    
    child1 = event_repo.create_event(
        run_id=run.id,
        event_type="tool_call",
        parent_event_id=root.id,
        execution_order=1,
        depth=1
    )
    
    grandchild = event_repo.create_event(
        run_id=run.id,
        event_type="file_gen",
        parent_event_id=child1.id,
        execution_order=2,
        depth=2
    )
    
    # Get full tree
    tree = event_repo.get_event_tree(root.id)
    assert len(tree) >= 3  # At least root, child, grandchild
    print("✓ Event tree query works")


def test_file_event_linkage(db_session, workflow_repo, event_repo):
    """Test File model enhancement with event_id and node_id."""
    run = workflow_repo.create_run(
        task_description="Test workflow",
        mode="one_shot",
        agent="engineer",
        model="gpt-4"
    )
    
    event = event_repo.create_event(
        run_id=run.id,
        event_type="file_gen",
        execution_order=0
    )
    
    # Create file with event linkage
    file = File(
        run_id=run.id,
        event_id=event.id,
        file_path="/test/output.png",
        file_type="plot",
        size_bytes=1024
    )
    db_session.add(file)
    db_session.commit()
    
    # Query file by event
    files = db_session.query(File).filter(File.event_id == event.id).all()
    assert len(files) == 1
    assert files[0].file_path == "/test/output.png"
    print("✓ File-Event linkage works")


def test_message_event_linkage(db_session, workflow_repo, event_repo):
    """Test Message model enhancement with event_id and node_id."""
    run = workflow_repo.create_run(
        task_description="Test workflow",
        mode="one_shot",
        agent="engineer",
        model="gpt-4"
    )
    
    event = event_repo.create_event(
        run_id=run.id,
        event_type="agent_call",
        agent_name="engineer",
        execution_order=0
    )
    
    # Create message with event linkage
    message = Message(
        run_id=run.id,
        event_id=event.id,
        sender="planner",
        recipient="engineer",
        content="Test message"
    )
    db_session.add(message)
    db_session.commit()
    
    # Query message by event
    messages = db_session.query(Message).filter(Message.event_id == event.id).all()
    assert len(messages) == 1
    assert messages[0].content == "Test message"
    print("✓ Message-Event linkage works")


def test_event_statistics(db_session, workflow_repo, event_repo):
    """Test event statistics calculation."""
    run = workflow_repo.create_run(
        task_description="Test workflow",
        mode="one_shot",
        agent="engineer",
        model="gpt-4"
    )
    
    # Create multiple events
    event_repo.create_event(
        run_id=run.id,
        event_type="agent_call",
        agent_name="engineer",
        execution_order=0,
        duration_ms=1000
    )
    
    event_repo.create_event(
        run_id=run.id,
        event_type="code_exec",
        agent_name="engineer",
        execution_order=1,
        duration_ms=2000
    )
    
    event_repo.create_event(
        run_id=run.id,
        event_type="file_gen",
        execution_order=2,
        duration_ms=500
    )
    
    # Get statistics
    stats = event_repo.get_event_statistics(run.id)
    
    assert stats["total_events"] == 3
    assert stats["event_types"]["agent_call"] == 1
    assert stats["event_types"]["code_exec"] == 1
    assert stats["event_types"]["file_gen"] == 1
    assert "engineer" in stats["agents_involved"]
    assert stats["agent_call_counts"]["engineer"] == 2
    assert stats["total_duration_ms"] == 3500
    assert stats["avg_duration_ms"] > 0
    print("✓ Event statistics calculation works")


def test_event_querying(db_session, workflow_repo, event_repo):
    """Test various event query methods."""
    run = workflow_repo.create_run(
        task_description="Test workflow",
        mode="planning_and_control",
        agent="planner",
        model="gpt-4"
    )
    
    # Create events for different agents
    event_repo.create_event(
        run_id=run.id,
        event_type="agent_call",
        agent_name="planner",
        execution_order=0
    )
    
    event_repo.create_event(
        run_id=run.id,
        event_type="agent_call",
        agent_name="engineer",
        execution_order=1
    )
    
    event_repo.create_event(
        run_id=run.id,
        event_type="tool_call",
        agent_name="engineer",
        execution_order=2
    )
    
    # Query all events for run
    all_events = event_repo.list_events_for_run(run.id)
    assert len(all_events) == 3
    
    # Query by event type
    agent_calls = event_repo.list_events_for_run(run.id, event_type="agent_call")
    assert len(agent_calls) == 2
    
    # Query by agent name
    engineer_events = event_repo.list_events_for_run(run.id, agent_name="engineer")
    assert len(engineer_events) == 2
    
    print("✓ Event querying works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

Run tests:

```bash
python tests/test_stage_01_execution_events.py
```

## Post-Stage Actions

1. Update PROGRESS.md with completion status
2. Document any issues encountered
3. Verify backward compatibility
4. Prepare for Stage 2 (AG2 Event Capture Layer)

## Troubleshooting

### Migration Fails
- Check Alembic configuration
- Verify database connection
- Review migration SQL manually
- Try `alembic downgrade` and reapply

### Foreign Key Errors
- Ensure referenced tables exist
- Check cascade rules
- Verify ON DELETE behaviors

### Import Errors
- Verify __init__.py exports
- Check circular imports
- Ensure models defined before relationships

## Next Stage

Proceed to **Stage 2: AG2 Event Capture Layer** to implement automatic event capture from AG2 agent interactions.
