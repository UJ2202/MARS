# Stage 4: File Tracking Overhaul

## Objectives
1. Consolidate dual file tracking systems (DAGTracker vs FileRegistry) into one
2. Add `session_id` to File model for multi-tenant isolation
3. Create FileRepository for consistent CRUD
4. Add deduplication (content hash check)
5. Fix phase attribution (explicit context, not post-hoc path guessing)
6. Add `generating_agent` tracking

## Dependencies
- Stage 1 (DAGTracker is sole owner of DAG and file tracking)

---

## Current State

### Two Competing File Tracking Systems

**System 1: DAGTracker.track_files_in_work_dir()** (`backend/execution/dag_tracker.py:681-869`)
- Scans 11 directories recursively
- Creates File DB records
- Classifies by extension/path
- **Missing**: session_id, content_hash, generating_agent, deduplication
- **Triggered**: On node completion + task_executor callbacks

**System 2: FileRegistry** (`cmbagent/execution/file_registry.py:110-595`)
- In-memory registry with optional DB persistence
- Thread-safe (RLock)
- Has content hashing, deduplication
- **Problem**: Separate from DAGTracker, not used consistently
- **Missing**: Not integrated into callback flow

**System 3: PhaseExecutionManager.track_file()** (`cmbagent/phases/execution_manager.py:1063-1088`)
- Appends to `self.files_created` list
- Manual tracking per phase
- **Problem**: Duplicates DAGTracker work

### File Model Gaps
**File**: `cmbagent/database/models.py:509-549`
- **Missing `session_id`**: Every other model has it, File doesn't
- **`content_hash` exists** but never populated by DAGTracker
- **`generating_agent` exists** but never populated by DAGTracker
- **`event_id` mostly NULL**: Not linked to generating event

### Phase Attribution Issue
**File**: `backend/execution/dag_tracker.py:789-800`
```python
# Current: guess phase from path (FRAGILE)
if 'planning' in rel_path:
    phase = "planning"
elif 'control' in rel_path:
    phase = "control"
else:
    phase = self.current_phase or "execution"
```
Files in shared directories (`data/`, `outputs/`) get wrong phase if `self.current_phase` changes.

---

## Implementation Tasks

### Task 4.1: Add session_id to File Model

**File**: `cmbagent/database/models.py`

```python
class File(Base):
    __tablename__ = "files"
    # ... existing fields ...

    # ADD:
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"),
                        nullable=True, index=True)

    # ADD relationship:
    session = relationship("Session")
```

Create Alembic migration for the new column.

### Task 4.2: Create FileRepository

**New file**: `cmbagent/database/file_repository.py`

```python
"""Consistent file CRUD operations with deduplication."""
import hashlib
import os
from typing import List, Optional
from cmbagent.database.models import File


class FileRepository:
    def __init__(self, db_session, session_id: str):
        self.db_session = db_session
        self.session_id = session_id

    def register_file(self, run_id: str, file_path: str, file_type: str,
                      node_id: str = None, step_id: str = None,
                      event_id: str = None, workflow_phase: str = None,
                      generating_agent: str = None,
                      is_final_output: bool = False) -> Optional[File]:
        """Register a file with deduplication by (run_id, file_path)."""

        # Check for duplicate
        existing = self.db_session.query(File).filter(
            File.run_id == run_id,
            File.file_path == file_path
        ).first()

        if existing:
            # Update metadata if changed
            if node_id and not existing.node_id:
                existing.node_id = node_id
            if step_id and not existing.step_id:
                existing.step_id = step_id
            if workflow_phase and existing.workflow_phase != workflow_phase:
                existing.workflow_phase = workflow_phase
            return existing

        # Compute content hash
        content_hash = None
        size_bytes = None
        if os.path.exists(file_path):
            size_bytes = os.path.getsize(file_path)
            if size_bytes < 50 * 1024 * 1024:  # Only hash files < 50MB
                content_hash = self._compute_hash(file_path)

        # Determine priority
        priority = self._classify_priority(file_type, is_final_output)

        file_record = File(
            run_id=run_id,
            session_id=self.session_id,
            node_id=node_id,
            step_id=step_id,
            event_id=event_id,
            file_path=file_path,
            file_type=file_type,
            size_bytes=size_bytes,
            workflow_phase=workflow_phase,
            is_final_output=is_final_output,
            content_hash=content_hash,
            generating_agent=generating_agent,
            priority=priority,
        )
        self.db_session.add(file_record)
        return file_record

    def list_files(self, run_id: str, file_type: str = None,
                   phase: str = None) -> List[File]:
        """List files for a run with optional filtering."""
        query = self.db_session.query(File).filter(
            File.run_id == run_id,
            File.session_id == self.session_id,
        )
        if file_type:
            query = query.filter(File.file_type == file_type)
        if phase:
            query = query.filter(File.workflow_phase == phase)
        return query.order_by(File.created_at).all()

    @staticmethod
    def _compute_hash(file_path: str) -> str:
        """Compute SHA-256 hash of file contents."""
        h = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _classify_priority(file_type: str, is_final_output: bool) -> str:
        if is_final_output:
            return "primary"
        if file_type in ("plot", "data", "code", "plan"):
            return "primary"
        elif file_type in ("report", "chat"):
            return "secondary"
        return "internal"
```

### Task 4.3: Update DAGTracker to Use FileRepository

**File**: `backend/execution/dag_tracker.py`

Replace raw DB writes in `track_files_in_work_dir()` with FileRepository:

```python
def track_files_in_work_dir(self, work_dir, node_id=None, step_id=None,
                             generating_agent=None, workflow_phase=None):
    """Scan and track files using FileRepository."""
    if not self.db_session:
        return

    from cmbagent.database.file_repository import FileRepository
    file_repo = FileRepository(self.db_session, self.session_id)

    # Use explicit phase instead of guessing from path
    phase = workflow_phase or self.current_phase or "execution"

    for dirpath, dirnames, filenames in os.walk(work_dir):
        # Skip hidden dirs, __pycache__
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']

        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            file_type = self._classify_file_type(file_path, work_dir)

            file_repo.register_file(
                run_id=self.run_id,
                file_path=file_path,
                file_type=file_type,
                node_id=node_id,
                step_id=step_id,
                generating_agent=generating_agent,
                workflow_phase=phase,
            )

    try:
        self.db_session.commit()
    except Exception as e:
        logger.error("file_tracking_failed", error=str(e))
        self.db_session.rollback()
```

### Task 4.4: Consolidate FileRegistry into FileRepository

**Decision**: Keep FileRepository as the single file tracking system. Remove or deprecate FileRegistry.

If FileRegistry has valuable in-memory caching features needed for performance:
- Extract the caching logic into FileRepository as an option
- Delete `cmbagent/execution/file_registry.py` if fully replaced

If FileRegistry is used directly by some phases:
- Update those phases to use callbacks instead (callbacks → task_executor → DAGTracker → FileRepository)

### Task 4.5: Explicit Phase Attribution

**File**: `backend/execution/task_executor.py`

Pass explicit phase to file tracking:
```python
def on_planning_complete_tracking(plan_info):
    dag_tracker.track_files_in_work_dir(
        task_work_dir, "planning",
        workflow_phase="planning"  # EXPLICIT, not guessed
    )

def on_step_complete_tracking(step_info):
    dag_tracker.track_files_in_work_dir(
        task_work_dir, f"step_{step_info.step_number}",
        workflow_phase="control",
        generating_agent=step_info.agent or "engineer"  # Track which agent generated files
    )
```

### Task 4.6: Remove PhaseExecutionManager File Tracking

**File**: `cmbagent/phases/execution_manager.py`

Remove duplicate file tracking:
- Remove `track_file()` method (line 1063-1088)
- Remove `_track_output_files()` method
- Remove `self.files_created` list

This is now handled exclusively by: callbacks → task_executor → DAGTracker → FileRepository.

---

## Cleanup Items
| Item | Lines Removed |
|------|--------------|
| PhaseExecutionManager file tracking | ~50 |
| FileRegistry (if fully deprecated) | ~500 |
| Raw DB writes in DAGTracker.track_files | ~100 (replaced by FileRepository) |
| **Total** | **~650** |

## Verification
```bash
# session_id in File model
python -c "from cmbagent.database.models import File; assert hasattr(File, 'session_id')"
# FileRepository works
python -c "from cmbagent.database.file_repository import FileRepository; print('OK')"
# Deduplication works
# (register same file twice, verify only one record)
# No file tracking in PhaseExecutionManager
grep -c "track_file\|files_created\|_track_output" cmbagent/phases/execution_manager.py  # 0
```

## Files Modified
| File | Action |
|------|--------|
| `cmbagent/database/models.py` | Add session_id to File |
| `cmbagent/database/file_repository.py` | NEW - FileRepository |
| `backend/execution/dag_tracker.py` | Use FileRepository, explicit phase |
| `backend/execution/task_executor.py` | Pass explicit phase to file tracking |
| `cmbagent/phases/execution_manager.py` | Remove file tracking code |
| `cmbagent/execution/file_registry.py` | DEPRECATE or DELETE |
| `cmbagent/database/migrations/` | NEW migration for session_id |
