# API Reference for Tests - Actual Signatures

This document lists the actual API signatures found in the codebase for reference when writing tests.

## Stage 1-2: Foundation ✅

### Session Repository
```python
SessionRepository(db: DBSession, session_id: str)
.create_session(name: str, user_id: Optional[str] = None, **kwargs) -> Session
```

### Workflow Repository
```python
WorkflowRepository(db: DBSession, session_id: str)
.create_run(mode: str, task_description: str, agent: str, model: str, **kwargs) -> WorkflowRun
.create_step(run_id: str, step_number: int, agent: str, **kwargs) -> WorkflowStep
  # Note: task_description goes in kwargs, not as 4th positional arg
```

## Stage 3-4: State Machine & DAG

### State Machine
```python
StateMachine(db: DBSession, session_id: str)
.transition_to(entity_type: str, entity_id: str, new_state: str, reason: str)
  # entity_type must be "workflow_run" or "workflow_step", NOT the entity ID
```

### DAG Components
These need to be imported from specific modules, not from `cmbagent.database`:
```python
from cmbagent.database.dag_builder import DAGBuilder
from cmbagent.database.topological_sort import TopologicalSorter
from cmbagent.database.dag_visualizer import DAGVisualizer
```

### DAG Repository
```python
DAGRepository(db: DBSession, session_id: str)
.create_node(run_id: str, node_id: str, node_type: str, agent: str, **kwargs) -> DAGNode
  # All params after run_id and node_id go as kwargs
```

## Stage 5: WebSocket

### Event Types
Import from correct path:
```python
from backend.websocket_events import WebSocketEventType  # Not EventType
from backend.websocket_events import create_workflow_started, create_step_completed
  # Note function names without _event suffix
```

## Stage 6: HITL Approval

Import from specific modules:
```python
from cmbagent.database.approval_types import ApprovalMode, ApprovalResolution
from cmbagent.database.approval_manager import ApprovalManager
```

## Stage 7: Retry Mechanism

### Error Analyzer
```python
ErrorAnalyzer().analyze_error(error_msg: str, traceback: str) -> dict
  # Returns dict, not object with .category attribute
  # Access as: result["category"]
```

### Retry Context
```python
RetryContext(
    current_attempt: int,
    max_attempts: int,
    original_task: str,  # Not original_task_description
    common_error: str,   # Required field
    error_category: str,
    previous_attempts: List,
    suggestions: List[str],
    strategy: str,
    backoff_seconds: int
)
```

### Retry Metrics
```python
RetryMetrics(db: DBSession)  # Only takes db, no session_id
```

## Stage 8: Parallel Execution

### Work Directory Manager
```python
WorkDirectoryManager(base_dir: str, run_id: str)  # Requires run_id
```

### Resource Manager
```python
ResourceManager(max_parallel_tasks: int)  # Not max_concurrent
```

## Stage 9: Branching

All repository methods follow the pattern of taking positional args then kwargs.

---

## Common Patterns

1. **Repository Pattern**: `Repository(db, session_id)`
2. **Create Methods**: First few args positional, rest as `**kwargs`
3. **Import Paths**: Many components not exported in `__init__.py`, import directly from module
