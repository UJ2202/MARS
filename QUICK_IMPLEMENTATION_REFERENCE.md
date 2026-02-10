# Unified Tracking System - Quick Implementation Reference

This document provides exact code snippets for implementing the unified tracking system.

---

## Stage 1: Wire Up AG2 Hooks

### File 1: `cmbagent/execution/ag2_hooks.py`

**Change 1**: Add global flag (after imports, line 11)
```python
from cmbagent.execution.event_capture import get_event_captor

# Track if hooks are already installed (idempotency)
_hooks_installed = False
```

**Change 2**: Update `install_ag2_hooks()` function (replace lines 146-166)
```python
def install_ag2_hooks() -> bool:
    """
    Install all AG2 hooks for event capture.
    Idempotent - safe to call multiple times.

    Returns:
        True if hooks installed successfully (or already installed)
    """
    global _hooks_installed

    # Check if already installed
    if _hooks_installed:
        print("[AG2 Hooks] Already installed, skipping")
        return True

    results = [
        patch_conversable_agent(),
        patch_group_chat(),
        patch_code_executor()
    ]

    success = all(results)
    if success:
        _hooks_installed = True
        print("[AG2 Hooks] All hooks installed successfully")
    else:
        print("[AG2 Hooks] Some hooks failed to install")

    return success
```

---

### File 2: `cmbagent/phases/execution_manager.py`

**Change 1**: Add imports (after line 44)
```python
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from enum import Enum

# NEW IMPORTS:
if TYPE_CHECKING:
    from cmbagent.execution.event_capture import EventCaptureManager
```

**Change 2**: Add event capture field to `__init__` (after line 142)
```python
# DAG node tracking
self._current_dag_node_id: Optional[str] = None
self._step_dag_node_ids: Dict[int, str] = {}  # step_number -> node_id

# NEW: Event capture manager
self._event_capture: Optional['EventCaptureManager'] = None

# Extract database objects from context if available
self._setup_database()
self._setup_event_capture()  # NEW: Setup event capture
```

**Change 3**: Add event capture methods (after `_setup_database()`, around line 156)
```python
def _setup_event_capture(self) -> None:
    """
    Set up AG2 event capture for this phase execution.
    Creates EventCaptureManager and installs AG2 hooks if not already installed.
    """
    shared = self.context.shared_state or {}

    # Check if event capture is disabled
    if not self.config.enable_database or not self._db_session:
        return

    try:
        from cmbagent.execution.event_capture import EventCaptureManager, set_event_captor
        from cmbagent.execution.ag2_hooks import install_ag2_hooks

        # Create event capture manager
        self._event_capture = EventCaptureManager(
            db_session=self._db_session,
            run_id=self.context.run_id,
            session_id=shared.get('_session_id', 'unknown'),
            enabled=True,
            websocket=None  # TODO: Add websocket if available in context
        )

        # Set context for this phase
        self._event_capture.set_context(
            node_id=self._current_dag_node_id,
            step_id=None  # Will be set per-step
        )

        # Set as global event captor
        set_event_captor(self._event_capture)

        # Install AG2 hooks (idempotent - safe to call multiple times)
        install_ag2_hooks()

        print(f"[PhaseExecutionManager] Event capture initialized for {self.phase.phase_type}")

    except Exception as e:
        print(f"[PhaseExecutionManager] Failed to setup event capture: {e}")
        self._event_capture = None

def _update_event_capture_context(self, step_id: Optional[str]) -> None:
    """
    Update event capture context for current step.

    Args:
        step_id: Current step ID (None for phase-level events)
    """
    if self._event_capture:
        node_id = self._step_dag_node_ids.get(self.current_step) if self.current_step else self._current_dag_node_id
        self._event_capture.set_context(
            node_id=node_id,
            step_id=step_id
        )

def _flush_event_capture(self) -> None:
    """Flush and clear event capture for this phase."""
    if self._event_capture:
        try:
            self._event_capture.flush()
            self._event_capture.close()

            # Clear global event captor (important: don't leak to next phase)
            from cmbagent.execution.event_capture import set_event_captor
            set_event_captor(None)

            print(f"[PhaseExecutionManager] Event capture flushed for {self.phase.phase_type}")
        except Exception as e:
            print(f"[PhaseExecutionManager] Error flushing event capture: {e}")
```

**Change 4**: Update `start_step()` (after line 398)
```python
# Log event
self._log_event(PhaseEventType.STEP_START, {
    'step_number': step_number,
    'description': description,
})

# NEW: Update event capture context for this step
self._update_event_capture_context(step_id=f"step_{step_number}")

print(f"\n--- Step {step_number}: {description} ---\n")
```

**Change 5**: Update `complete()` (after creating PhaseResult, around line 282)
```python
result = PhaseResult(
    status=PhaseStatus.COMPLETED,
    context=self.context,
    chat_history=chat_history or [],
    timing={
        'start': self.start_time,
        'end': self.end_time,
        'total': execution_time,
    }
)

# NEW: Flush event capture before returning
self._flush_event_capture()

return result
```

**Change 6**: Update `fail()` (after creating PhaseResult, around line 339)
```python
result = PhaseResult(
    status=PhaseStatus.FAILED,
    context=self.context,
    error=error,
    timing={
        'start': self.start_time,
        'end': self.end_time,
        'total': (self.end_time or 0) - (self.start_time or 0),
    }
)

# NEW: Flush event capture before returning
self._flush_event_capture()

return result
```

---

## Stage 2: Add managed_mode

### File 3: `cmbagent/cmbagent.py`

**Change 1**: Update `__init__` signature (around line 91)
```python
def __init__(
    self,
    task: str = "",
    work_dir: Union[str, pathlib.Path] = work_dir_default(),
    clear_work_dir: bool = False,
    llm_api_key: Optional[str] = None,
    llm_api_type: Optional[str] = None,
    temperature=0,
    top_p=1.0,
    timeout: int = 240,
    verbose: bool = False,
    path_to_apis: str = "prompts/",
    path_to_assistants: str = "prompts/",
    path_to_generated_output: str = ".",
    cache_seed: Optional[int] = 42,
    enable_mcp_client: bool = False,
    managed_mode: bool = False,  # NEW: Skip DB init when managed by parent
    parent_session_id: Optional[str] = None,  # NEW: Use parent's session
    parent_db_session: Optional[Any] = None,  # NEW: Use parent's DB session
):
```

**Change 2**: Refactor DB initialization (replace lines 213-289)
```python
# Database initialization (optional, controlled by environment variable and managed_mode)
self.use_database = os.getenv("CMBAGENT_USE_DATABASE", "true").lower() == "true"
self.db_session: Optional[Any] = None
self.session_id: Optional[str] = None
self.workflow_repo: Optional[Any] = None
self.persistence: Optional[Any] = None
self.dag_builder: Optional[Any] = None
self.dag_executor: Optional[Any] = None
self.dag_visualizer: Optional[Any] = None
self.workflow_sm: Optional[Any] = None
self.approval_manager: Optional[Any] = None
self.retry_manager: Optional[Any] = None
self.retry_metrics: Optional[Any] = None

# NEW: Skip DB initialization if in managed mode
if managed_mode:
    if cmbagent_debug:
        print(f"[CMBAgent] Running in managed_mode, skipping DB initialization")

    # Use parent's session/DB if provided
    self.session_id = parent_session_id
    self.db_session = parent_db_session

    # Note: workflow_repo, persistence, etc. are left as None
    # The parent phase manages all tracking/persistence
    self.use_database = False  # Disable DB operations in solve()

elif self.use_database:
    # EXISTING CODE: Full DB initialization
    try:
        from cmbagent.database import get_db_session, init_database
        from cmbagent.database.repository import WorkflowRepository
        from cmbagent.database.persistence import DualPersistenceManager
        from cmbagent.database.session_manager import SessionManager
        from cmbagent.database.dag_builder import DAGBuilder
        from cmbagent.database.dag_executor import DAGExecutor
        from cmbagent.database.dag_visualizer import DAGVisualizer
        from cmbagent.database.state_machine import StateMachine
        from cmbagent.database.approval_manager import ApprovalManager

        # Initialize database
        init_database()

        # Create database session
        self.db_session = get_db_session()

        # Get or create session
        session_manager = SessionManager(self.db_session)
        self.session_id = session_manager.get_or_create_default_session()

        # Create repositories
        self.workflow_repo = WorkflowRepository(self.db_session, self.session_id)

        # Create persistence manager
        self.persistence = DualPersistenceManager(
            self.db_session,
            self.session_id,
            self.work_dir
        )

        # Create DAG components
        self.dag_builder = DAGBuilder(self.db_session, self.session_id)
        self.dag_executor = DAGExecutor(self.db_session, self.session_id)
        self.dag_visualizer = DAGVisualizer(self.db_session)
        self.workflow_sm = StateMachine(self.db_session, "workflow_run")

        # Create approval manager
        self.approval_manager = ApprovalManager(self.db_session, self.session_id)

        # Create retry context manager and metrics
        from cmbagent.retry.retry_context_manager import RetryContextManager
        from cmbagent.retry.retry_metrics import RetryMetrics
        self.retry_manager = RetryContextManager(self.db_session, self.session_id)
        self.retry_metrics = RetryMetrics(self.db_session)

        if cmbagent_debug:
            print(f"Database initialized with session_id: {self.session_id}")
    except Exception as e:
        self.logger.warning(f"Failed to initialize database: {e}. Continuing without database.")
        self.use_database = False
        self.db_session = None
        self.session_id = None
        self.workflow_repo = None
        self.persistence = None
        self.dag_builder = None
        self.dag_executor = None
        self.dag_visualizer = None
        self.workflow_sm = None
        self.approval_manager = None
        self.retry_manager = None
        self.retry_metrics = None
```

---

### File 4: `cmbagent/phases/execution_manager.py`

**Change**: Add helper method (after `_flush_event_capture()`, around line 220)
```python
def get_managed_cmbagent_kwargs(self) -> Dict[str, Any]:
    """
    Get kwargs for creating a managed CMBAgent instance.

    Returns:
        Dictionary of kwargs to pass to CMBAgent.__init__
    """
    shared = self.context.shared_state or {}

    return {
        'managed_mode': True,
        'parent_session_id': shared.get('_session_id'),
        'parent_db_session': self._db_session,
    }
```

---

### Files 5-8: Phase Files (planning.py, control.py, hitl_control.py, hitl_planning.py)

**Pattern**: Update CMBAgent instantiation in each phase

**Example** (adapt to each phase's specific location):

```python
# OLD CODE (search for this pattern in each file):
cmbagent = CMBAgent(
    work_dir=context.work_dir,
    llm_api_key=context.api_keys.get('llm_api_key'),
    verbose=False,
    cache_seed=42,
)

# NEW CODE:
cmbagent = CMBAgent(
    work_dir=context.work_dir,
    llm_api_key=context.api_keys.get('llm_api_key'),
    verbose=False,
    cache_seed=42,
    **manager.get_managed_cmbagent_kwargs()  # NEW: Add this line
)
```

**Files to update**:
- `cmbagent/phases/planning.py` (search for `CMBAgent(`)
- `cmbagent/phases/control.py` (search for `CMBAgent(`)
- `cmbagent/phases/hitl_control.py` (search for `CMBAgent(`)
- `cmbagent/phases/hitl_planning.py` (search for `CMBAgent(`)

---

## Stage 3: Branching + Sub-Nodes

### File 9: `cmbagent/database/models.py`

**Change**: Update DAGNode model (around line 150)

```python
class DAGNode(Base):
    """Node in the workflow DAG (directed acyclic graph)."""
    __tablename__ = "dag_nodes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_node_id = Column(String(36), ForeignKey("dag_nodes.id", ondelete="CASCADE"), nullable=True, index=True)  # NEW
    node_type = Column(String(50), nullable=False, index=True)
    # Node types: planning, control, agent, approval, parallel_group, terminator, sub_agent, branch_point  # UPDATED
    agent = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    # Status: pending, running, completed, failed, skipped
    order_index = Column(Integer, nullable=False)
    depth = Column(Integer, nullable=False, default=0)  # NEW: Nesting level
    meta = Column(JSON, nullable=True)

    # Relationships
    run = relationship("WorkflowRun", back_populates="dag_nodes")
    session = relationship("Session", back_populates="dag_nodes")
    parent_node = relationship("DAGNode", remote_side=[id], backref="child_nodes")  # NEW
    outgoing_edges = relationship("DAGEdge", foreign_keys="DAGEdge.from_node_id", back_populates="from_node", cascade="all, delete-orphan")
    incoming_edges = relationship("DAGEdge", foreign_keys="DAGEdge.to_node_id", back_populates="to_node", cascade="all, delete-orphan")
    execution_events = relationship("ExecutionEvent", back_populates="node", cascade="all, delete-orphan")
    files = relationship("File", back_populates="node", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="node", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_dag_nodes_run_order", "run_id", "order_index"),
        Index("idx_dag_nodes_type_status", "node_type", "status"),
        Index("idx_dag_nodes_parent", "parent_node_id"),  # NEW
    )
```

---

### File 10: `cmbagent/database/repository.py`

**Change**: Add sub-node and branch methods to DAGRepository class

```python
def create_sub_node(
    self,
    parent_node_id: str,
    node_type: str,
    agent: str,
    status: str = "pending",
    meta: Optional[Dict[str, Any]] = None
) -> DAGNode:
    """
    Create a sub-node under a parent node.

    Args:
        parent_node_id: ID of parent node
        node_type: Type of sub-node (e.g., "sub_agent", "tool_call")
        agent: Agent name
        status: Initial status
        meta: Additional metadata

    Returns:
        Created DAGNode
    """
    parent = self.db.query(DAGNode).filter(DAGNode.id == parent_node_id).first()
    if not parent:
        raise ValueError(f"Parent node {parent_node_id} not found")

    # Calculate depth and order_index for sub-node
    depth = parent.depth + 1

    # Find max order_index among siblings
    siblings = self.db.query(DAGNode).filter(
        DAGNode.parent_node_id == parent_node_id
    ).all()
    order_index = max([s.order_index for s in siblings], default=-1) + 1

    node = DAGNode(
        run_id=parent.run_id,
        session_id=parent.session_id,
        parent_node_id=parent_node_id,
        node_type=node_type,
        agent=agent,
        status=status,
        order_index=order_index,
        depth=depth,
        meta=meta or {}
    )

    self.db.add(node)
    self.db.commit()
    self.db.refresh(node)

    return node

def create_branch_node(
    self,
    source_node_id: str,
    branch_name: str,
    hypothesis: Optional[str] = None
) -> DAGNode:
    """
    Create a branch node for alternative execution paths.

    Args:
        source_node_id: Node to branch from
        branch_name: Name of the branch (e.g., "redo_1", "alternative_a")
        hypothesis: Hypothesis for this branch

    Returns:
        Created branch node
    """
    from cmbagent.database.models import DAGEdge

    source = self.db.query(DAGNode).filter(DAGNode.id == source_node_id).first()
    if not source:
        raise ValueError(f"Source node {source_node_id} not found")

    # Create branch node at same level as source
    node = DAGNode(
        run_id=source.run_id,
        session_id=source.session_id,
        parent_node_id=source.parent_node_id,
        node_type="branch_point",
        agent=f"branch_{branch_name}",
        status="pending",
        order_index=source.order_index,
        depth=source.depth,
        meta={
            "branch_name": branch_name,
            "hypothesis": hypothesis,
            "source_node_id": source_node_id
        }
    )

    self.db.add(node)
    self.db.commit()
    self.db.refresh(node)

    # Create conditional edge from source to branch
    edge = DAGEdge(
        from_node_id=source_node_id,
        to_node_id=node.id,
        dependency_type="conditional",
        condition=f"branch_{branch_name}"
    )
    self.db.add(edge)
    self.db.commit()

    return node
```

---

### File 11: `cmbagent/phases/execution_manager.py`

**Change**: Add branching methods (after `add_plan_step_nodes()`, around line 641)

```python
def create_redo_branch(
    self,
    step_number: int,
    redo_number: int,
    hypothesis: Optional[str] = None
) -> Optional[str]:
    """
    Create a redo branch for a failed step.

    Args:
        step_number: Step being redone
        redo_number: Redo attempt number (1, 2, 3...)
        hypothesis: Hypothesis for why this redo will succeed

    Returns:
        Branch node ID if created, None on error
    """
    if not self.config.enable_dag or not self._dag_repo:
        return None

    try:
        step_node_id = self._step_dag_node_ids.get(step_number)
        if not step_node_id:
            print(f"[PhaseExecutionManager] Cannot create redo branch: step {step_number} node not found")
            return None

        # Create branch node
        branch_name = f"redo_{redo_number}"
        branch_node = self._dag_repo.create_branch_node(
            source_node_id=step_node_id,
            branch_name=branch_name,
            hypothesis=hypothesis or f"Retry attempt {redo_number}"
        )

        print(f"[PhaseExecutionManager] Created redo branch: step {step_number}, redo {redo_number}")
        return branch_node.id

    except Exception as e:
        print(f"[PhaseExecutionManager] Failed to create redo branch: {e}")
        return None

def record_sub_agent_call(
    self,
    step_number: int,
    agent_name: str,
    action: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Record a sub-agent call within a step.

    Args:
        step_number: Current step number
        agent_name: Name of sub-agent
        action: Action being performed
        metadata: Additional metadata

    Returns:
        Sub-node ID if created, None on error
    """
    if not self.config.enable_dag or not self._dag_repo:
        return None

    try:
        step_node_id = self._step_dag_node_ids.get(step_number)
        if not step_node_id:
            return None

        # Create sub-node
        sub_node = self._dag_repo.create_sub_node(
            parent_node_id=step_node_id,
            node_type="sub_agent",
            agent=agent_name,
            status="running",
            meta={
                "action": action,
                **(metadata or {})
            }
        )

        return sub_node.id

    except Exception as e:
        print(f"[PhaseExecutionManager] Failed to record sub-agent call: {e}")
        return None
```

---

### File 12: `cmbagent/phases/hitl_control.py`

**Change 1**: Add `max_redos` config (around line 53)
```python
# Execution parameters
max_rounds: int = 100
max_n_attempts: int = 3
max_redos: int = 2  # NEW: Configurable redo limit
```

**Change 2**: Update redo logic (search for hardcoded redo limit, usually a check like `if redo_count >= 2:`)

```python
# OLD CODE (find this pattern):
if redo_count >= 2:  # Hardcoded limit
    # Handle max redos...

# NEW CODE:
if redo_count >= self.config.max_redos:
    print(f"Maximum redo attempts ({self.config.max_redos}) reached for step {step_number}")
    # Handle max redos...

# Also create redo branch in DAG (add after redo is initiated):
manager.create_redo_branch(
    step_number=step_number,
    redo_number=redo_count + 1,
    hypothesis=human_feedback  # Use human's feedback as hypothesis
)
```

---

## Database Migration

### Option 1: Using Alembic

```bash
# Generate migration
alembic revision --autogenerate -m "Add parent_node_id and depth to dag_nodes for sub-node support"

# Apply migration
alembic upgrade head
```

### Option 2: Manual SQL (PostgreSQL)

```sql
-- Add columns
ALTER TABLE dag_nodes ADD COLUMN parent_node_id VARCHAR(36);
ALTER TABLE dag_nodes ADD COLUMN depth INTEGER NOT NULL DEFAULT 0;

-- Add foreign key
ALTER TABLE dag_nodes
ADD CONSTRAINT fk_parent_node
FOREIGN KEY (parent_node_id)
REFERENCES dag_nodes(id)
ON DELETE CASCADE;

-- Add index
CREATE INDEX idx_dag_nodes_parent ON dag_nodes(parent_node_id);
```

### Option 3: Manual SQL (SQLite)

```sql
-- SQLite doesn't support ALTER TABLE ADD FOREIGN KEY
-- Must recreate table

-- 1. Create new table with additional columns
CREATE TABLE dag_nodes_new (
    id VARCHAR(36) PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    parent_node_id VARCHAR(36),
    node_type VARCHAR(50) NOT NULL,
    agent VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    order_index INTEGER NOT NULL,
    depth INTEGER NOT NULL DEFAULT 0,
    meta TEXT,
    FOREIGN KEY (run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_node_id) REFERENCES dag_nodes(id) ON DELETE CASCADE
);

-- 2. Copy data
INSERT INTO dag_nodes_new (
    id, run_id, session_id, node_type, agent, status, order_index, depth, meta
)
SELECT
    id, run_id, session_id, node_type, agent, status, order_index, 0, meta
FROM dag_nodes;

-- 3. Drop old table
DROP TABLE dag_nodes;

-- 4. Rename new table
ALTER TABLE dag_nodes_new RENAME TO dag_nodes;

-- 5. Recreate indexes
CREATE INDEX idx_dag_nodes_run_order ON dag_nodes(run_id, order_index);
CREATE INDEX idx_dag_nodes_type_status ON dag_nodes(node_type, status);
CREATE INDEX idx_dag_nodes_parent ON dag_nodes(parent_node_id);
```

---

## Testing Commands

### Test Stage 1: Event Capture
```python
# test_event_capture.py
from cmbagent import CMBAgent

# Run simple task
agent = CMBAgent(work_dir="./test_work")
agent.solve("Write a Python function to calculate factorial")

# Check database
from cmbagent.database import get_db_session
from cmbagent.database.models import ExecutionEvent

db = get_db_session()
events = db.query(ExecutionEvent).all()
print(f"Captured {len(events)} events")
for event in events[:5]:
    print(f"  {event.event_type}: {event.agent_name}")
```

### Test Stage 2: managed_mode
```python
# test_managed_mode.py
from cmbagent import CMBAgent
from cmbagent.database import get_db_session

# Test 1: Normal mode creates DB session
agent1 = CMBAgent(work_dir="./test1")
assert agent1.db_session is not None
assert agent1.session_id is not None

# Test 2: Managed mode skips DB init
parent_db = get_db_session()
parent_session_id = "test_session"

agent2 = CMBAgent(
    work_dir="./test2",
    managed_mode=True,
    parent_db_session=parent_db,
    parent_session_id=parent_session_id
)
assert agent2.db_session == parent_db
assert agent2.session_id == parent_session_id
assert agent2.workflow_repo is None  # Not initialized
print("✅ managed_mode working correctly")
```

### Test Stage 3: Branching
```python
# test_branching.py
from cmbagent.database import get_db_session
from cmbagent.database.repository import DAGRepository

db = get_db_session()
repo = DAGRepository(db, "test_session")

# Create test node
node = repo.create_node(
    run_id="test_run",
    node_type="agent",
    agent="engineer",
    order_index=1,
    status="failed"
)

# Create redo branch
branch = repo.create_branch_node(
    source_node_id=node.id,
    branch_name="redo_1",
    hypothesis="Retry with more context"
)

assert branch.node_type == "branch_point"
assert branch.depth == node.depth
assert branch.meta["branch_name"] == "redo_1"
print("✅ Branching working correctly")
```

---

## Verification Checklist

### After Stage 1:
- [ ] AG2 hooks print "installed successfully" on first run
- [ ] AG2 hooks print "already installed" on subsequent runs
- [ ] ExecutionEvent records appear in database
- [ ] Events have correct run_id, node_id
- [ ] No duplicate events (check by event_type + timestamp)
- [ ] Performance impact < 10% (measure workflow duration)

### After Stage 2:
- [ ] Worker CMBAgent instances skip DB init (check logs)
- [ ] No new sessions created per CMBAgent
- [ ] Parent session_id propagates to child
- [ ] Events still captured (Stage 1 still works)
- [ ] Workflows complete successfully

### After Stage 3:
- [ ] Database migration applied successfully
- [ ] `parent_node_id` and `depth` columns exist
- [ ] Redo operations create branch nodes
- [ ] Branch nodes have correct `meta` (branch_name, hypothesis)
- [ ] `max_redos` configuration is respected
- [ ] DAG queries work (test recursive CTE)

---

## Rollback Plan

### Stage 1 Rollback:
```python
# In cmbagent/phases/execution_manager.py
# Comment out these lines:
# self._setup_event_capture()  # DISABLED
# self._update_event_capture_context()  # DISABLED
# self._flush_event_capture()  # DISABLED
```

### Stage 2 Rollback:
```python
# In all phase files, remove this line:
# **manager.get_managed_cmbagent_kwargs()  # REMOVED

# In cmbagent/cmbagent.py, ensure managed_mode defaults to False
# managed_mode: bool = False  # Keep this default
```

### Stage 3 Rollback:
```sql
-- Rollback database migration
alembic downgrade -1

-- Or manually:
ALTER TABLE dag_nodes DROP COLUMN parent_node_id;
ALTER TABLE dag_nodes DROP COLUMN depth;
```

---

## Performance Tuning

### If Event Capture is Slow:
```python
# In event_capture.py, increase buffer size
EventCaptureManager(
    db_session=self._db_session,
    run_id=self.context.run_id,
    session_id=shared.get('_session_id', 'unknown'),
    enabled=True,
    buffer_size=100,  # Increase from 50 to 100
    websocket=None
)
```

### If Database Grows Too Large:
```python
# Add retention policy
from datetime import datetime, timedelta

def cleanup_old_events(db, days=30):
    """Delete events older than N days."""
    cutoff = datetime.now() - timedelta(days=days)
    db.query(ExecutionEvent).filter(
        ExecutionEvent.timestamp < cutoff
    ).delete()
    db.commit()
```

### If Queries Are Slow:
```sql
-- Add additional indexes
CREATE INDEX idx_execution_events_run_agent ON execution_events(run_id, agent_name);
CREATE INDEX idx_execution_events_timestamp ON execution_events(timestamp DESC);
```

---

## Summary

**Files Modified**: 12 total
- Stage 1: 2 files
- Stage 2: 5 files
- Stage 3: 5 files

**Lines of Code**: ~600 new lines
- Stage 1: ~150 lines
- Stage 2: ~100 lines
- Stage 3: ~350 lines

**Estimated Implementation Time**:
- Stage 1: 2-4 hours
- Stage 2: 3-5 hours
- Stage 3: 6-10 hours
- Total: 11-19 hours (plus testing)

**Risk Level**:
- Stage 1: Low (activates existing code)
- Stage 2: Medium (refactors core initialization)
- Stage 3: Medium-High (database migration required)
