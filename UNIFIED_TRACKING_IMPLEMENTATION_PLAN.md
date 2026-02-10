IM# Unified Tracking/Event System Implementation Plan

## Executive Summary

This plan unifies three disconnected tracking layers in CMBAgent:
1. **WorkflowCallbacks** (phase-level events)
2. **PhaseExecutionManager** (phase ↔ callback bridge)
3. **EventCaptureManager + AG2 Hooks** (low-level AG2 tracing - EXISTS BUT NEVER ACTIVATED)

The core problem: Each `CMBAgent()` instance creates orphaned DB sessions isolated from parent workflow tracking. AG2 hooks exist but are never installed.

## Three-Stage Implementation

### Stage 1: Wire up AG2 hooks + EventCaptureManager
**Goal**: Activate existing but dormant event capture infrastructure
**Complexity**: Low (infrastructure already exists)
**Files**: 5 phase files + 2 infrastructure files

### Stage 2: Add `managed_mode` to CMBAgent
**Goal**: Skip DB init when CMBAgent is managed by a parent phase
**Complexity**: Medium (careful refactoring needed)
**Files**: 1 core file (cmbagent.py)

### Stage 3: Extend DAGTracker for branching
**Goal**: Support sub-nodes, branches, redo operations
**Complexity**: Medium (new features on existing foundation)
**Files**: 3 files (dag_tracker.py, dag_builder.py, hitl_control.py)

---

## Stage 1: Wire Up AG2 Hooks + EventCaptureManager

### Problem Statement
- `EventCaptureManager` exists (`execution/event_capture.py`) but is never instantiated
- `install_ag2_hooks()` exists (`execution/ag2_hooks.py`) but is never called
- `set_event_captor()` global function exists but is never used
- AG2 agent calls, messages, tool calls go untracked

### Solution Architecture

#### 1.1 Add Event Capture Setup to PhaseExecutionManager

**File**: `cmbagent/phases/execution_manager.py`

**Location**: Add new methods after line 141 (after `_setup_database`)

```python
# =========================================================================
# Event Capture Integration (AG2 Hooks)
# =========================================================================

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

        # Set as global event captor (thread-local would be better, but global works for now)
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
    if hasattr(self, '_event_capture') and self._event_capture:
        node_id = self._step_dag_node_ids.get(self.current_step) if self.current_step else self._current_dag_node_id
        self._event_capture.set_context(
            node_id=node_id,
            step_id=step_id
        )

def _flush_event_capture(self) -> None:
    """Flush and clear event capture for this phase."""
    if hasattr(self, '_event_capture') and self._event_capture:
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

**Location**: Update `__init__` to call setup (after line 145)

```python
# Extract database objects from context if available
self._setup_database()
self._setup_event_capture()  # NEW: Setup event capture
```

**Location**: Update `start_step` to set event context (after line 398)

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

**Location**: Update `complete` to flush events (after line 282)

```python
return PhaseResult(
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
```

**Location**: Update `fail` to flush events (after line 339)

```python
return PhaseResult(
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
```

#### 1.2 Make AG2 Hooks Idempotent

**File**: `cmbagent/execution/ag2_hooks.py`

**Location**: Add global flag at module level (after line 11)

```python
from cmbagent.execution.event_capture import get_event_captor

# Global flag to track if hooks are installed
_hooks_installed = False
```

**Location**: Update `install_ag2_hooks()` function (replace lines 146-166)

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

#### 1.3 Wire Up Event Capture in All Phases

The following phases need event capture integration. Since PhaseExecutionManager now handles it automatically, **NO CHANGES NEEDED** in phase files! The manager handles everything.

Phases that will automatically get event capture:
- `cmbagent/phases/planning.py` ✅
- `cmbagent/phases/control.py` ✅
- `cmbagent/phases/hitl_control.py` ✅
- `cmbagent/phases/hitl_planning.py` ✅
- `cmbagent/phases/copilot_phase.py` ✅
- `cmbagent/phases/idea_generation.py` ✅
- `cmbagent/phases/one_shot.py` ✅

**Verification**: After Stage 1, run a simple workflow and check:
1. AG2 hooks print "installed successfully"
2. `ExecutionEvent` records appear in database
3. Agent calls, messages, tool calls are captured
4. No duplicate events

---

## Stage 2: Add `managed_mode` to CMBAgent

### Problem Statement
- Each `CMBAgent()` instance creates its own isolated DB session (lines 227-289 in cmbagent.py)
- Worker CMBAgent instances inside phases can't contribute to parent DAG
- Need a way to tell CMBAgent "you're being managed by a parent phase, don't init DB"

### Solution Architecture

#### 2.1 Add `managed_mode` Parameter to CMBAgent.__init__

**File**: `cmbagent/cmbagent.py`

**Location**: Add parameter to `__init__` signature (around line 91)

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

**Location**: Update database initialization block (replace lines 213-289)

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
    # EXISTING CODE: Full DB initialization (lines 228-289)
    try:
        from cmbagent.database import get_db_session, init_database
        from cmbagent.database.repository import WorkflowRepository
        # ... rest of existing DB init code ...
    except Exception as e:
        self.logger.warning(f"Failed to initialize database: {e}. Continuing without database.")
        self.use_database = False
        # ... rest of existing error handling ...
```

#### 2.2 Update Phases to Pass `managed_mode=True`

**File**: `cmbagent/phases/planning.py`

**Location**: Update CMBAgent instantiation (around line 122)

```python
# Initialize CMBAgent for planning
cmbagent = CMBAgent(
    work_dir=context.work_dir,
    llm_api_key=context.api_keys.get('llm_api_key'),
    verbose=False,
    cache_seed=42,
    managed_mode=True,  # NEW: Managed by PlanningPhase
    parent_session_id=manager._db_session and getattr(manager, '_session_id', None),
    parent_db_session=manager._db_session,
)
```

**File**: `cmbagent/phases/control.py`

**Location**: Update CMBAgent instantiation (search for "CMBAgent(" in the file)

```python
# Initialize CMBAgent for control execution
cmbagent = CMBAgent(
    work_dir=context.work_dir,
    llm_api_key=context.api_keys.get('llm_api_key'),
    verbose=False,
    cache_seed=42,
    managed_mode=True,  # NEW: Managed by ControlPhase
    parent_session_id=manager._db_session and getattr(manager, '_session_id', None),
    parent_db_session=manager._db_session,
)
```

**File**: `cmbagent/phases/hitl_control.py`

**Location**: Update CMBAgent instantiation (search for "CMBAgent(" in the file)

```python
# Initialize CMBAgent for HITL execution
cmbagent = CMBAgent(
    work_dir=context.work_dir,
    llm_api_key=context.api_keys.get('llm_api_key'),
    verbose=False,
    cache_seed=42,
    managed_mode=True,  # NEW: Managed by HITLControlPhase
    parent_session_id=manager._db_session and getattr(manager, '_session_id', None),
    parent_db_session=manager._db_session,
)
```

**File**: `cmbagent/phases/hitl_planning.py`

**Location**: Update CMBAgent instantiation (search for "CMBAgent(" in the file)

```python
# Initialize CMBAgent for HITL planning
cmbagent = CMBAgent(
    work_dir=context.work_dir,
    llm_api_key=context.api_keys.get('llm_api_key'),
    verbose=False,
    cache_seed=42,
    managed_mode=True,  # NEW: Managed by HITLPlanningPhase
    parent_session_id=manager._db_session and getattr(manager, '_session_id', None),
    parent_db_session=manager._db_session,
)
```

#### 2.3 Add Helper to PhaseExecutionManager

**File**: `cmbagent/phases/execution_manager.py`

**Location**: Add helper method after `_setup_event_capture` (around line 220)

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

Then phases can simplify their code:

```python
# Initialize CMBAgent with managed mode
cmbagent = CMBAgent(
    work_dir=context.work_dir,
    llm_api_key=context.api_keys.get('llm_api_key'),
    verbose=False,
    cache_seed=42,
    **manager.get_managed_cmbagent_kwargs()  # Clean!
)
```

**Verification**: After Stage 2, check:
1. Worker CMBAgent instances skip DB init
2. No orphaned sessions in database
3. All events still captured via AG2 hooks
4. Parent phase DAG remains unified

---

## Stage 3: Extend DAGTracker for Branching

### Problem Statement
- Current DAGTracker (`orchestrator/dag_tracker.py`) is phase-level only
- Need sub-nodes for internal agent calls within a step
- Need branch nodes for HITL redo operations
- `max_redos` is hardcoded, should be configurable

### Solution Architecture

#### 3.1 Add Sub-Node Support to DAGNode

**File**: `cmbagent/database/models.py`

**Location**: Update DAGNode model (around line 150)

```python
class DAGNode(Base):
    """Node in the workflow DAG (directed acyclic graph)."""
    __tablename__ = "dag_nodes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_node_id = Column(String(36), ForeignKey("dag_nodes.id", ondelete="CASCADE"), nullable=True, index=True)  # NEW: For sub-nodes
    node_type = Column(String(50), nullable=False, index=True)
    # Node types: planning, control, agent, approval, parallel_group, terminator, sub_agent, branch_point
    agent = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    # Status: pending, running, completed, failed, skipped
    order_index = Column(Integer, nullable=False)
    depth = Column(Integer, nullable=False, default=0)  # NEW: Nesting level (0=top-level, 1=sub-node, etc.)
    meta = Column(JSON, nullable=True)

    # Relationships
    run = relationship("WorkflowRun", back_populates="dag_nodes")
    session = relationship("Session", back_populates="dag_nodes")
    parent_node = relationship("DAGNode", remote_side=[id], backref="child_nodes")  # NEW: Parent/child relationship
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

**Note**: This requires a database migration. Create migration file after implementation.

#### 3.2 Extend DAGRepository for Sub-Nodes

**File**: `cmbagent/database/repository.py` (or wherever DAGRepository is defined)

**Location**: Add new method to DAGRepository class

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
    source = self.db.query(DAGNode).filter(DAGNode.id == source_node_id).first()
    if not source:
        raise ValueError(f"Source node {source_node_id} not found")

    # Create branch node at same level as source
    node = DAGNode(
        run_id=source.run_id,
        session_id=source.session_id,
        parent_node_id=source.parent_node_id,  # Same parent as source
        node_type="branch_point",
        agent=f"branch_{branch_name}",
        status="pending",
        order_index=source.order_index,  # Same order as source (parallel)
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

#### 3.3 Update PhaseExecutionManager for Branching

**File**: `cmbagent/phases/execution_manager.py`

**Location**: Add new method after `add_plan_step_nodes` (around line 641)

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

#### 3.4 Add `max_redos` Configuration

**File**: `cmbagent/phases/hitl_control.py`

**Location**: Update `HITLControlPhaseConfig` (around line 33)

```python
@dataclass
class HITLControlPhaseConfig(PhaseConfig):
    """
    Configuration for HITL control/execution phase.

    Attributes:
        max_rounds: Maximum conversation rounds per step
        max_n_attempts: Maximum attempts per step before failure
        max_redos: Maximum number of redo attempts per step (NEW)
        execute_all_steps: Whether to execute all plan steps
        # ... rest of attributes ...
    """
    phase_type: str = "hitl_control"

    # Execution parameters
    max_rounds: int = 100
    max_n_attempts: int = 3
    max_redos: int = 2  # NEW: Configurable redo limit

    # ... rest of config ...
```

**Location**: Update redo logic to use `max_redos` (search for hardcoded redo limit in the file)

```python
# OLD CODE (search for this pattern):
# if redo_count >= 2:  # Hardcoded limit

# NEW CODE:
if redo_count >= self.config.max_redos:
    print(f"Maximum redo attempts ({self.config.max_redos}) reached for step {step_number}")
    # ... rest of max redo handling ...

# Also create redo branch in DAG
manager.create_redo_branch(
    step_number=step_number,
    redo_number=redo_count + 1,
    hypothesis=human_feedback  # Use human's feedback as hypothesis
)
```

#### 3.5 Update Orchestrator DAGTracker (Optional)

**File**: `cmbagent/orchestrator/dag_tracker.py`

This file is for phase-level orchestration DAG. The sub-node/branching work is primarily in the database DAG. However, for consistency, you can add branch support:

**Location**: Add method after `mark_skipped` (around line 192)

```python
def add_branch(
    self,
    phase_id: str,
    branch_name: str,
    branch_config: Dict[str, Any],
    hypothesis: Optional[str] = None
) -> PhaseNode:
    """
    Add a branch from an existing phase.

    Args:
        phase_id: ID of phase to branch from
        branch_name: Unique name for this branch
        branch_config: Configuration for branch phase
        hypothesis: Hypothesis for why this branch will succeed

    Returns:
        New PhaseNode for the branch
    """
    if phase_id not in self.nodes:
        raise ValueError(f"Phase {phase_id} not found in DAG")

    source = self.nodes[phase_id]
    branch_id = f"{phase_id}_branch_{branch_name}"

    # Create branch node with same dependencies as source
    branch_node = PhaseNode(
        id=branch_id,
        phase_name=f"{source.phase_name} (Branch: {branch_name})",
        config=branch_config,
        dependencies=source.dependencies.copy()
    )

    # Add metadata
    branch_node.metrics['branch_source'] = phase_id
    branch_node.metrics['hypothesis'] = hypothesis

    self.nodes[branch_id] = branch_node

    # Update dependents
    for dep_id in branch_node.dependencies:
        self.nodes[dep_id].dependents.append(branch_id)

    return branch_node
```

**Verification**: After Stage 3, check:
1. Redo operations create branch nodes in DAG
2. Sub-agent calls appear as sub-nodes
3. `max_redos` configuration works
4. DAG visualization shows branches
5. Database queries can reconstruct full execution tree

---

## Database Migration Required

After implementing Stage 3 changes to DAGNode model:

```bash
# If using Alembic for migrations
alembic revision --autogenerate -m "Add parent_node_id and depth to dag_nodes for sub-node support"
alembic upgrade head
```

If not using Alembic, manually add columns:

```sql
ALTER TABLE dag_nodes ADD COLUMN parent_node_id VARCHAR(36);
ALTER TABLE dag_nodes ADD COLUMN depth INTEGER NOT NULL DEFAULT 0;
ALTER TABLE dag_nodes ADD FOREIGN KEY (parent_node_id) REFERENCES dag_nodes(id) ON DELETE CASCADE;
CREATE INDEX idx_dag_nodes_parent ON dag_nodes(parent_node_id);
```

---

## Testing Strategy

### Stage 1 Tests
```python
def test_event_capture_activation():
    """Test that AG2 hooks are installed and events are captured."""
    # Run simple planning phase
    # Check ExecutionEvent table has records
    # Verify no duplicate events
    # Verify hooks are idempotent

def test_event_context_scoping():
    """Test that event capture context is scoped per-step."""
    # Run control phase with multiple steps
    # Verify events have correct node_id and step_id
    # Verify no event leakage between steps
```

### Stage 2 Tests
```python
def test_managed_mode_skips_db_init():
    """Test that managed_mode prevents DB initialization."""
    # Create CMBAgent with managed_mode=True
    # Verify db_session, workflow_repo, etc. are None
    # Verify solve() still works

def test_managed_mode_uses_parent_session():
    """Test that managed CMBAgent uses parent's session."""
    # Create parent session
    # Create CMBAgent with managed_mode=True and parent_session_id
    # Verify session_id matches parent
```

### Stage 3 Tests
```python
def test_redo_creates_branch():
    """Test that redo operations create branch nodes."""
    # Run HITL control with redo
    # Verify branch node created in DAG
    # Verify branch connects to source node

def test_sub_agent_nodes():
    """Test that sub-agent calls create sub-nodes."""
    # Mock EventCaptureManager to trigger sub-node creation
    # Verify sub-nodes have correct parent_node_id and depth

def test_max_redos_configurable():
    """Test that max_redos configuration is respected."""
    # Set max_redos=1 in config
    # Trigger multiple redos
    # Verify stops after 1 redo
```

---

## Rollout Plan

### Phase 1: Stage 1 Only (Low Risk)
- Deploy Stage 1 changes
- Monitor production for:
  - Performance impact of hooks
  - Event capture rate
  - Database growth
- Verify no breaking changes
- **Duration**: 1-2 weeks

### Phase 2: Stage 2 (Medium Risk)
- Deploy Stage 2 changes
- Monitor for:
  - Orphaned sessions eliminated
  - No broken workflows
  - Memory/resource usage stable
- **Duration**: 2-3 weeks

### Phase 3: Stage 3 (Medium-High Risk)
- Requires database migration
- Deploy to staging first
- Run migration in maintenance window
- Monitor DAG complexity, query performance
- **Duration**: 3-4 weeks

---

## Key Design Decisions

### 1. Why Global Event Captor?
**Decision**: Use global `_global_event_captor` variable instead of thread-local storage.

**Rationale**:
- Simpler implementation
- CMBAgent workflows are typically sequential, not concurrent
- If concurrency needed later, can upgrade to `threading.local()`

**Risk**: If multiple workflows run concurrently in same process, events may mix. Mitigated by flushing after each phase.

### 2. Why managed_mode Instead of Dependency Injection?
**Decision**: Add `managed_mode` boolean flag instead of complex DI framework.

**Rationale**:
- Minimal code changes
- Backward compatible (default `managed_mode=False`)
- Clear intent: "this agent is managed by parent"

**Alternative**: Could inject repositories as parameters, but creates verbose code and breaks backward compatibility.

### 3. Why Extend Database DAG vs Orchestrator DAG?
**Decision**: Extend database DAGNode model for sub-nodes/branches instead of just orchestrator DAGTracker.

**Rationale**:
- Database is source of truth for execution history
- Enables querying full execution tree
- Supports UI visualization of detailed DAG
- Orchestrator DAG is for phase-level planning, DB DAG is for execution tracking

### 4. Why Not Use AG2's Native Event Listeners?
**Decision**: Use monkey-patching hooks instead of AG2's event listener API (if it exists).

**Rationale**:
- Monkey-patching captures EVERYTHING automatically
- No need to modify CMBAgent.solve() internals
- Works with any AG2 version that has ConversableAgent

**Risk**: Monkey patches may break with AG2 updates. Mitigated by version pinning and thorough testing.

---

## Performance Considerations

### Event Capture Overhead
- Each event capture adds ~2-5ms overhead
- For a 100-event workflow: ~200-500ms total
- **Acceptable** for long-running research workflows (hours/days)

### Database Growth
- Events grow linearly with workflow complexity
- Estimate: 100-500 events per workflow run
- ExecutionEvent records: ~1KB each
- **Mitigation**: Add retention policy to archive old events

### Query Performance
- Sub-node queries require recursive CTEs
- Add index on `parent_node_id` (included in Stage 3)
- **Recommendation**: Limit sub-node depth to 3 levels

---

## Future Enhancements (Out of Scope)

### 1. Thread-Safe Event Capture
Use `threading.local()` instead of global variable for concurrent workflows.

### 2. Event Streaming to External Systems
Stream events to Kafka, DataDog, etc. for real-time monitoring.

### 3. DAG Visualization UI
Build React component to render interactive DAG with sub-nodes and branches.

### 4. Automatic Branch Pruning
Prune failed branches from DAG to reduce clutter.

### 5. Smart Redo Suggestions
Use ML to suggest likely-to-succeed redo strategies based on error patterns.

---

## Summary of File Changes

### Stage 1: Wire Up AG2 Hooks
- ✏️ `cmbagent/phases/execution_manager.py` (3 new methods + 5 small updates)
- ✏️ `cmbagent/execution/ag2_hooks.py` (add idempotency flag)
- ✅ All phase files (no changes - automatic from PhaseExecutionManager)

### Stage 2: managed_mode
- ✏️ `cmbagent/cmbagent.py` (__init__ signature + DB init refactor)
- ✏️ `cmbagent/phases/execution_manager.py` (add helper method)
- ✏️ 4 phase files (pass managed_mode=True)

### Stage 3: Branching
- ✏️ `cmbagent/database/models.py` (add parent_node_id, depth to DAGNode)
- ✏️ `cmbagent/database/repository.py` (add create_sub_node, create_branch_node)
- ✏️ `cmbagent/phases/execution_manager.py` (add redo_branch methods)
- ✏️ `cmbagent/phases/hitl_control.py` (add max_redos config)
- ✏️ `cmbagent/orchestrator/dag_tracker.py` (optional: add branch support)
- 🗄️ Database migration (add columns + indexes)

**Total**: 9 files modified, 1 migration, ~500 lines of new code

---

## Conclusion

This plan provides a **minimal, practical, and safe** approach to unifying the tracking system:

1. **Stage 1** activates existing infrastructure (low risk, high value)
2. **Stage 2** eliminates orphaned sessions (medium risk, medium value)
3. **Stage 3** adds advanced features (medium-high risk, high value for HITL)

Each stage is independently deployable and testable. The design preserves backward compatibility while enabling future extensibility.

**Recommended Approach**: Implement stages sequentially with production validation between stages.
