# Stage 8: Branching & Future-Proofing

## Objectives
1. Ensure branch-from-node works with template-based DAG system
2. Isolate tracking per branch (event capture, cost, files all branch-scoped)
3. Add racing branch DB model groundwork
4. Add branch point DAG visualization

## Dependencies
- All prior stages complete

---

## Implementation Tasks

### Task 8.1: Verify DAG Cloning with Templates

**File**: `cmbagent/branching/branch_manager.py`

Template-based nodes use string IDs in-memory but UUID IDs in DB.
Cloning operates at DB level (UUID-based), so it should work.

Verify:
- `_copy_execution_history()` (lines 159-252) clones correctly
- New branch gets its own DAGTracker with fresh in-memory state
- Cloned nodes before branch point keep completed status, after branch point reset to pending

### Task 8.2: Branch-Scoped Event Capture

Using contextvars (Stage 3), branches are automatically isolated:
```python
import contextvars

def execute_branch(branch_run_id, session_id, db_session, ...):
    ctx = contextvars.copy_context()

    def run_branch():
        branch_captor = EventCaptureManager(db_session, branch_run_id, session_id)
        set_event_captor(branch_captor)
        # ... execute branch workflow ...

    ctx.run(run_branch)
    # Parent context's captor is untouched
```

### Task 8.3: Branch Cost Tracking

Each branch already gets its own `work_dir`. Cost JSON files are written per-work_dir.
CostCollector (Stage 2) reads per-branch, so costs are automatically isolated.

Add comparison method:
```python
# cmbagent/branching/comparator.py
def compare_costs(self, parent_run_id, branch_run_ids):
    results = {}
    for run_id in [parent_run_id] + branch_run_ids:
        costs = self.db_session.query(CostRecord).filter(
            CostRecord.run_id == run_id
        ).all()
        results[run_id] = {
            "total_cost": sum(float(c.cost_usd) for c in costs),
            "total_tokens": sum(c.total_tokens for c in costs),
        }
    return results
```

### Task 8.4: Racing Branch DB Model

**File**: `cmbagent/database/models.py`

Add to Branch model:
```python
class Branch(Base):
    # ... existing fields ...
    racing_group_id = Column(String(36), nullable=True, index=True)
    racing_priority = Column(Integer, nullable=True)
    racing_status = Column(String(20), nullable=True)  # racing, won, lost, cancelled
```

Add new table:
```python
class RacingGroup(Base):
    __tablename__ = "racing_groups"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    parent_run_id = Column(String(36), ForeignKey("workflow_runs.id"), nullable=False)
    parent_step_id = Column(String(36), ForeignKey("workflow_steps.id"), nullable=False)
    strategy = Column(String(50), default="first_complete")  # first_complete, best_score
    status = Column(String(20), default="racing")  # racing, resolved, cancelled
    winner_branch_id = Column(String(36), ForeignKey("branches.id"), nullable=True)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
```

### Task 8.5: Branch Point DAG Visualization

**File**: `backend/execution/dag_tracker.py`

```python
async def add_branch_point(self, step_id, branch_names):
    node = {
        "id": f"branch_at_{step_id}", "type": "branch_point",
        "label": "Branch Point", "status": "completed",
        "branches": branch_names,
    }
    self.nodes.append(node)
    self.node_statuses[node["id"]] = "completed"
    self.edges.append({"source": step_id, "target": node["id"]})
    await self.send_event(self.websocket, "dag_updated",
                          {"run_id": self.run_id, "nodes": self.nodes, "edges": self.edges},
                          run_id=self.run_id)
```

---

## Files Modified
| File | Action |
|------|--------|
| `cmbagent/branching/branch_manager.py` | Verify cloning |
| `cmbagent/branching/comparator.py` | Add cost comparison |
| `cmbagent/database/models.py` | Racing model additions |
| `backend/execution/dag_tracker.py` | Branch point visualization |
