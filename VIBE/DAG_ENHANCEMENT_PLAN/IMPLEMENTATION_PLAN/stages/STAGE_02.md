# Stage 2: Database Schema and Models

**Phase:** 0 - Foundation
**Estimated Time:** 30-40 minutes
**Dependencies:** Stage 1 (AG2 Upgrade) must be complete
**Risk Level:** Medium

## Objectives

1. Design and implement SQLAlchemy database models for all entities
2. Create Alembic migrations for schema versioning
3. Add session-based isolation to all tables
4. Implement dual-write persistence (database + pickle files)
5. Create repository layer for data access
6. Set up database initialization and connection management

## Current State Analysis

### What We Have
- File-based persistence (pickle files, JSON files)
- Context saved as `context_step_N.pkl`
- Plans saved as `final_plan.json`
- Chat history as JSON files
- No structured queryable history

### What We Need
- SQLite database with complete schema
- SQLAlchemy ORM models
- Alembic for migrations
- Session-scoped data isolation
- Dual-write to DB + pickle
- Query interface for history

## Pre-Stage Verification

### Check Prerequisites
1. Stage 1 complete and verified
2. AG2 upgrade successful
3. All existing tests still passing
4. Current pickle file structure documented

### Expected State
- CMBAgent working with new AG2
- Ready to add database layer alongside existing persistence
- No breaking changes to current functionality

## Implementation Tasks

### Task 1: Install Database Dependencies
**Objective:** Add SQLAlchemy and Alembic to project

**Actions:**
- Update `pyproject.toml` dependencies section
- Add: `sqlalchemy>=2.0`, `alembic>=1.13`, `psycopg2-binary>=2.9` (PostgreSQL support)
- Install dependencies: `pip install -e .`

**Files to Modify:**
- `pyproject.toml` (dependencies section)

**Verification:**
- Dependencies install without conflicts
- Can import SQLAlchemy and Alembic
- `pip list` shows correct versions

### Task 2: Create Database Module Structure
**Objective:** Set up organized database code structure

**Create Directory Structure:**
```
cmbagent/
└── database/
    ├── __init__.py           # Package init, exports
    ├── base.py               # Base class and engine setup
    ├── models.py             # All SQLAlchemy models
    ├── repository.py         # Data access layer
    ├── session_manager.py    # Session lifecycle management
    ├── migrations/           # Alembic migrations
    │   ├── env.py
    │   ├── script.py.mako
    │   └── versions/
    └── alembic.ini           # Alembic configuration
```

**Verification:**
- Directory structure created
- All __init__.py files present
- Package importable

### Task 3: Define SQLAlchemy Models
**Objective:** Create all database models with session isolation

**Core Models to Create:**

**sessions table:**
- id (UUID, primary key)
- user_id (UUID, nullable for now)
- name (VARCHAR 255)
- created_at (TIMESTAMP)
- last_active_at (TIMESTAMP)
- status (VARCHAR 50: active, archived, deleted)
- metadata (JSONB)
- resource_limits (JSONB)

**projects table:**
- id (UUID, primary key)
- session_id (UUID, foreign key)
- name (VARCHAR 255)
- description (TEXT)
- created_at (TIMESTAMP)
- metadata (JSONB)

**workflow_runs table:**
- id (UUID, primary key)
- session_id (UUID, foreign key)
- project_id (UUID, foreign key)
- mode (VARCHAR 50: one_shot, planning_control, deep_research)
- agent (VARCHAR 100: engineer, researcher, etc.)
- model (VARCHAR 100: gpt-4, claude-3, etc.)
- status (VARCHAR 50: draft, planning, executing, paused, waiting_approval, completed, failed)
- started_at (TIMESTAMP)
- completed_at (TIMESTAMP, nullable)
- last_heartbeat_at (TIMESTAMP)
- checkpoint_frequency_minutes (INTEGER, default 10)
- task_description (TEXT)
- metadata (JSONB)

**workflow_steps table:**
- id (UUID, primary key)
- run_id (UUID, foreign key)
- session_id (UUID, foreign key)
- step_number (INTEGER)
- agent (VARCHAR 100)
- status (VARCHAR 50: pending, running, paused, waiting_approval, completed, failed, skipped)
- started_at (TIMESTAMP, nullable)
- completed_at (TIMESTAMP, nullable)
- progress_percentage (INTEGER, 0-100)
- inputs (JSONB)
- outputs (JSONB)
- error_message (TEXT, nullable)
- metadata (JSONB)

**dag_nodes table:**
- id (UUID, primary key)
- run_id (UUID, foreign key)
- session_id (UUID, foreign key)
- node_type (VARCHAR 50: planning, control, agent, approval, parallel_group, terminator)
- agent (VARCHAR 100, nullable)
- status (VARCHAR 50: pending, running, completed, failed, skipped)
- order_index (INTEGER)
- metadata (JSONB)

**dag_edges table:**
- id (SERIAL, primary key)
- from_node_id (UUID, foreign key)
- to_node_id (UUID, foreign key)
- dependency_type (VARCHAR 50: sequential, parallel, conditional)
- condition (TEXT, nullable)

**checkpoints table:**
- id (UUID, primary key)
- run_id (UUID, foreign key)
- step_id (UUID, foreign key, nullable)
- checkpoint_type (VARCHAR 50: step_complete, timed, manual, error, emergency)
- created_at (TIMESTAMP)
- context_snapshot (JSONB)
- pickle_file_path (VARCHAR 500)
- metadata (JSONB)

**messages table:**
- id (SERIAL, primary key)
- run_id (UUID, foreign key)
- step_id (UUID, foreign key, nullable)
- sender (VARCHAR 100)
- recipient (VARCHAR 100)
- content (TEXT)
- timestamp (TIMESTAMP)
- tokens (INTEGER, nullable)
- metadata (JSONB)

**cost_records table:**
- id (SERIAL, primary key)
- run_id (UUID, foreign key)
- step_id (UUID, foreign key, nullable)
- session_id (UUID, foreign key)
- model (VARCHAR 100)
- prompt_tokens (INTEGER)
- completion_tokens (INTEGER)
- total_tokens (INTEGER)
- cost_usd (NUMERIC(10, 6))
- timestamp (TIMESTAMP)

**approval_requests table:**
- id (UUID, primary key)
- run_id (UUID, foreign key)
- step_id (UUID, foreign key)
- status (VARCHAR 50: pending, approved, rejected, modified)
- requested_at (TIMESTAMP)
- resolved_at (TIMESTAMP, nullable)
- context_snapshot (JSONB)
- user_feedback (TEXT, nullable)
- resolution (VARCHAR 50, nullable)

**branches table:**
- id (UUID, primary key)
- parent_run_id (UUID, foreign key)
- parent_step_id (UUID, foreign key)
- child_run_id (UUID, foreign key)
- branch_name (VARCHAR 255)
- created_at (TIMESTAMP)
- hypothesis (TEXT, nullable)
- metadata (JSONB)

**workflow_metrics table:**
- id (SERIAL, primary key)
- run_id (UUID, foreign key)
- step_id (UUID, foreign key, nullable)
- timestamp (TIMESTAMP)
- metric_name (VARCHAR 100)
- metric_value (NUMERIC)
- metadata (JSONB)

**files table:**
- id (UUID, primary key)
- run_id (UUID, foreign key)
- step_id (UUID, foreign key, nullable)
- file_path (VARCHAR 1000)
- file_type (VARCHAR 50: code, data, plot, log, other)
- size_bytes (BIGINT)
- created_at (TIMESTAMP)
- metadata (JSONB)

**Files to Create:**
- `cmbagent/database/models.py` (all model classes)

**Verification:**
- All models defined with proper relationships
- Foreign keys correctly configured
- Indexes on session_id columns
- JSONB fields for flexible metadata

### Task 4: Create Database Base and Engine
**Objective:** Set up database connection and base configuration

**Implementation:**
- Create declarative base
- Configure engine (SQLite default, PostgreSQL support)
- Session factory setup
- Connection pooling configuration
- Database URL from environment variable

**Files to Create:**
- `cmbagent/database/base.py`

**Configuration:**
```python
DATABASE_URL = os.getenv(
    "CMBAGENT_DATABASE_URL",
    f"sqlite:///{BASE_WORK_DIR}/cmbagent.db"
)
```

**Verification:**
- Can create engine
- Can create session
- Database file created (SQLite)
- Connection works

### Task 5: Initialize Alembic
**Objective:** Set up database migration system

**Actions:**
- Run `alembic init cmbagent/database/migrations`
- Configure `alembic.ini` with database URL
- Update `env.py` to use models
- Create initial migration with all tables
- Run migration: `alembic upgrade head`

**Files to Create:**
- `cmbagent/database/migrations/env.py`
- `cmbagent/database/migrations/versions/001_initial_schema.py`
- `cmbagent/database/alembic.ini`

**Verification:**
- Alembic commands work
- Initial migration creates all tables
- Database schema matches models
- Can run `alembic current` successfully

### Task 6: Create Repository Layer
**Objective:** Data access layer with session isolation

**Implementation:**

```python
class WorkflowRepository:
    def __init__(self, db_session, session_id):
        self.db = db_session
        self.session_id = session_id

    def create_run(self, **kwargs):
        # Automatically add session_id
        run = WorkflowRun(session_id=self.session_id, **kwargs)
        self.db.add(run)
        self.db.commit()
        return run

    def get_run(self, run_id):
        # Automatically filter by session_id
        return self.db.query(WorkflowRun).filter(
            WorkflowRun.id == run_id,
            WorkflowRun.session_id == self.session_id
        ).first()

    def list_runs(self, status=None):
        query = self.db.query(WorkflowRun).filter(
            WorkflowRun.session_id == self.session_id
        )
        if status:
            query = query.filter(WorkflowRun.status == status)
        return query.all()

    # Similar methods for steps, checkpoints, etc.
```

**Files to Create:**
- `cmbagent/database/repository.py`

**Classes to Implement:**
- `WorkflowRepository` - workflow runs and steps
- `SessionRepository` - session management
- `DAGRepository` - DAG nodes and edges
- `CostRepository` - cost tracking
- `CheckpointRepository` - checkpoint management

**Verification:**
- Can create workflow runs
- Session isolation enforced
- CRUD operations work
- Relationships properly loaded

### Task 7: Implement Dual-Write Persistence
**Objective:** Write to both database and pickle files

**Implementation:**

```python
class DualPersistenceManager:
    def __init__(self, db_session, session_id, work_dir):
        self.repo = WorkflowRepository(db_session, session_id)
        self.work_dir = work_dir

    def save_checkpoint(self, run_id, step_id, context, checkpoint_type):
        # 1. Save to database (primary)
        checkpoint = self.repo.create_checkpoint(
            run_id=run_id,
            step_id=step_id,
            checkpoint_type=checkpoint_type,
            context_snapshot=self._serialize_context(context)
        )

        # 2. Save to pickle file (secondary)
        pickle_path = f"{self.work_dir}/context/context_step_{step_id}.pkl"
        with open(pickle_path, 'wb') as f:
            pickle.dump(context, f)

        # 3. Update checkpoint record with pickle path
        checkpoint.pickle_file_path = pickle_path
        self.repo.db.commit()

        return checkpoint

    def load_checkpoint(self, checkpoint_id):
        # Load from database first
        checkpoint = self.repo.get_checkpoint(checkpoint_id)

        # If pickle file exists, use it for full context
        if checkpoint.pickle_file_path and os.path.exists(checkpoint.pickle_file_path):
            with open(checkpoint.pickle_file_path, 'rb') as f:
                return pickle.load(f)

        # Otherwise deserialize from database
        return self._deserialize_context(checkpoint.context_snapshot)
```

**Files to Create:**
- `cmbagent/database/persistence.py`

**Verification:**
- Checkpoints written to both DB and pickle
- Can load from database
- Can fall back to pickle file
- Context properly serialized/deserialized

### Task 8: Update CMBAgent to Use Database
**Objective:** Integrate database into existing CMBAgent workflow

**Files to Modify:**
- `cmbagent/cmbagent.py` - Add database initialization
- `cmbagent/context.py` - Add database context fields
- `cmbagent/functions.py` - Add checkpoint calls

**Changes:**

In `cmbagent.py`:
```python
class CMBAgent:
    def __init__(self, ...):
        # Existing initialization
        ...

        # NEW: Database initialization
        from cmbagent.database import get_db_session, WorkflowRepository
        self.db_session = get_db_session()
        self.session_id = session_id or self._create_default_session()
        self.repo = WorkflowRepository(self.db_session, self.session_id)

        # NEW: Dual persistence manager
        from cmbagent.database.persistence import DualPersistenceManager
        self.persistence = DualPersistenceManager(
            self.db_session,
            self.session_id,
            self.work_dir
        )

    def planning_and_control_context_carryover(self, ...):
        # Existing code...

        # NEW: Create workflow run in database
        run = self.repo.create_run(
            mode="planning_control",
            agent=agent,
            model=model,
            status="planning",
            task_description=task
        )

        # Store run_id in context
        shared_context["run_id"] = str(run.id)

        # ... existing execution ...

        # NEW: Dual-write checkpoint
        self.persistence.save_checkpoint(
            run_id=run.id,
            step_id=None,  # Planning checkpoint
            context=shared_context,
            checkpoint_type="step_complete"
        )
```

**Verification:**
- Database operations don't break existing functionality
- Pickle files still written
- Database records created
- Can query workflow history

## Files to Create (Summary)

### New Files
```
cmbagent/database/
├── __init__.py
├── base.py
├── models.py
├── repository.py
├── persistence.py
├── session_manager.py
├── alembic.ini
└── migrations/
    ├── env.py
    ├── script.py.mako
    └── versions/
        └── 001_initial_schema.py
```

### Modified Files
- `pyproject.toml` - Add database dependencies
- `cmbagent/cmbagent.py` - Initialize database, create runs
- `cmbagent/context.py` - Add database-related context fields
- `cmbagent/functions.py` - Add checkpoint calls

## Verification Criteria

### Must Pass
- [ ] Database dependencies installed successfully
- [ ] All SQLAlchemy models defined with proper relationships
- [ ] Alembic migrations run successfully
- [ ] Database tables created with correct schema
- [ ] Repository layer works with session isolation
- [ ] Dual-write persistence (DB + pickle) functioning
- [ ] Existing pickle-only workflows still work
- [ ] `python tests/test_one_shot.py` passes
- [ ] Can create and query workflow runs in database

### Should Pass
- [ ] Session isolation enforced in queries
- [ ] Checkpoints saved to both DB and pickle
- [ ] Can load context from database
- [ ] Foreign key constraints working
- [ ] Indexes created on session_id columns

### Database Schema Verification
- [ ] Run `sqlite3 cmbagent.db ".schema"` and verify all tables
- [ ] Check foreign keys: `.foreign_keys ON` then check constraints
- [ ] Verify indexes: `.indexes` command shows session_id indexes
- [ ] Test session isolation with manual SQL queries

## Testing Checklist

### Unit Tests
```python
# Test repository CRUD operations
def test_workflow_repository_create():
    repo = WorkflowRepository(db_session, session_id)
    run = repo.create_run(mode="one_shot", agent="engineer")
    assert run.id is not None
    assert run.session_id == session_id

# Test session isolation
def test_session_isolation():
    repo1 = WorkflowRepository(db_session, session_id_1)
    repo2 = WorkflowRepository(db_session, session_id_2)

    run1 = repo1.create_run(mode="one_shot", agent="engineer")

    # Session 2 should not see session 1's run
    assert repo2.get_run(run1.id) is None

# Test dual persistence
def test_dual_persistence():
    persistence.save_checkpoint(run_id, step_id, context)

    # Check database
    checkpoint = repo.get_checkpoint(checkpoint_id)
    assert checkpoint is not None

    # Check pickle file
    assert os.path.exists(checkpoint.pickle_file_path)
```

### Integration Tests
```python
# Test full workflow with database
def test_planning_and_control_with_database():
    agent = CMBAgent(session_id="test_session")
    agent.planning_and_control("Test task")

    # Verify database records created
    runs = agent.repo.list_runs()
    assert len(runs) > 0
    assert runs[0].status in ["completed", "failed"]
```

## Common Issues and Solutions

### Issue 1: Alembic Import Error
**Symptom:** `ImportError: cannot import name 'Base' from cmbagent.database`
**Solution:** Ensure `env.py` correctly imports models, check PYTHONPATH

### Issue 2: Database Lock (SQLite)
**Symptom:** `database is locked` error
**Solution:** Use WAL mode: `PRAGMA journal_mode=WAL`

### Issue 3: JSONB Not Supported (SQLite)
**Symptom:** SQLite doesn't have native JSONB
**Solution:** Use `JSON` type with SQLAlchemy, stores as TEXT

### Issue 4: Session Isolation Not Working
**Symptom:** Cross-session data visible
**Solution:** Verify session_id passed to repository, check query filters

### Issue 5: Migration Conflicts
**Symptom:** Alembic detects unwanted changes
**Solution:** Autogenerate migrations carefully, review before applying

## Rollback Procedure

If database integration causes issues:

1. **Disable database writes:**
   ```python
   # In cmbagent.py
   USE_DATABASE = os.getenv("CMBAGENT_USE_DATABASE", "false") == "true"
   ```

2. **Revert code changes:**
   ```bash
   git checkout cmbagent/cmbagent.py cmbagent/functions.py
   ```

3. **Remove database file:**
   ```bash
   rm cmbagent.db
   ```

4. **Keep pickle files** - They still work independently

## Post-Stage Actions

### Documentation
- Document database schema in `ARCHITECTURE.md`
- Add database setup instructions to README
- Create database query examples

### Update Progress
- Mark Stage 2 complete in `PROGRESS.md`
- Note any deviations from plan
- Document time spent

### Prepare for Stage 3
- Database operational
- Session isolation working
- Ready to add state machine on top of database
- Stage 3 can proceed

## Success Criteria

Stage 2 is complete when:
1. All database models created and tested
2. Alembic migrations working
3. Dual-write persistence functioning
4. Session isolation enforced
5. Existing workflows still work
6. Database queries return correct data
7. Verification checklist 100% complete

## Estimated Time Breakdown

- Dependencies and setup: 5 min
- Model definitions: 10 min
- Alembic configuration: 5 min
- Repository layer: 8 min
- Dual persistence: 7 min
- CMBAgent integration: 10 min
- Testing and verification: 10 min
- Documentation: 5 min

**Total: 30-40 minutes**

## Next Stage

Once Stage 2 is verified complete, proceed to:
**Stage 3: State Machine Implementation**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
