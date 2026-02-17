# Stage 2: Cost Tracking Overhaul

## Objectives
1. Establish cost JSON files as the single source of truth
2. Create CostCollector (app layer) that reads JSON directly - no stdout parsing
3. Remove all cost-from-stdout detection in StreamCapture
4. Fix cost data accuracy (no 70/30 token estimation, no model concatenation)
5. Delete dead CostManager class

## Dependencies
- Stage 0 (callback contract, boundary enforcement)

---

## Current State

### Three Parallel Cost Paths (BROKEN)
1. **Library writes JSON** - `cmbagent.py:display_cost()` writes to `work_dir/cost/cost_report_*.json` (ACCURATE)
2. **StreamCapture parses stdout** - `stream_capture.py:255-344` regex matches on "cost report data saved to:" and reads the JSON file (FRAGILE, also does DB writes from app into library)
3. **Callbacks estimate costs** - `callbacks.py:622-624` uses 70/30 prompt/completion split estimation (INACCURATE)

### Dead Code
- `cmbagent/managers/cost_manager.py` - ~295 lines, CostManager class never instantiated anywhere

### Known Bugs
- **Model concatenation**: `cmbagent.py:543` (fixed in Stage 0)
- **70/30 estimation**: `callbacks.py:622-624` stores fake token split
- **StreamCapture DB imports**: `stream_capture.py:316` imports library's CostRepository from app (reverse concern)

---

## Implementation Tasks

### Task 2.1: Create CostCollector (App Layer)

**New file**: `backend/execution/cost_collector.py`

```python
"""
Cost collector that reads JSON files written by cmbagent's display_cost().
Single path for cost data to reach database and WebSocket.
"""
import json
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class CostCollector:
    """Reads cost JSON from work_dir/cost/ and persists to database."""

    def __init__(self, db_session, session_id: str, run_id: str):
        self.db_session = db_session
        self.session_id = session_id
        self.run_id = run_id
        self._processed_files = set()

    def collect_from_callback(self, cost_data: Dict[str, Any],
                               ws_send_func=None) -> None:
        """Process cost data received via on_cost_update callback."""
        json_path = cost_data.get("cost_json_path")
        records = cost_data.get("records", [])

        if json_path and json_path in self._processed_files:
            return  # Already processed (idempotent)

        if json_path:
            self._processed_files.add(json_path)

        if not records and json_path and os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    records = json.load(f)
            except Exception as e:
                logger.error("cost_json_read_failed", path=json_path, error=str(e))
                return

        self._persist_records(records)
        if ws_send_func:
            self._emit_ws_events(records, ws_send_func)

    def collect_from_work_dir(self, work_dir: str, ws_send_func=None) -> None:
        """Scan work_dir/cost/ for any unprocessed JSON files."""
        cost_dir = os.path.join(work_dir, "cost")
        if not os.path.isdir(cost_dir):
            return

        for fname in sorted(os.listdir(cost_dir)):
            if fname.endswith(".json"):
                json_path = os.path.join(cost_dir, fname)
                if json_path not in self._processed_files:
                    self.collect_from_callback(
                        {"cost_json_path": json_path},
                        ws_send_func=ws_send_func
                    )

    def _persist_records(self, records: List[Dict]) -> None:
        """Persist cost records with ACTUAL token counts from JSON."""
        if not self.db_session:
            return

        try:
            from cmbagent.database.models import CostRecord

            for entry in records:
                if entry.get("Agent") == "Total":
                    continue

                cost_str = str(entry.get("Cost ($)", "$0.0"))
                cost_value = float(cost_str.replace("$", ""))

                record = CostRecord(
                    run_id=self.run_id,
                    session_id=self.session_id,
                    model=entry.get("Model", "unknown"),
                    prompt_tokens=int(float(str(entry.get("Prompt Tokens", 0)))),
                    completion_tokens=int(float(str(entry.get("Completion Tokens", 0)))),
                    total_tokens=int(float(str(entry.get("Total Tokens", 0)))),
                    cost_usd=cost_value,
                )
                self.db_session.add(record)

            self.db_session.commit()
        except Exception as e:
            logger.error("cost_persist_failed", error=str(e))
            if self.db_session:
                self.db_session.rollback()

    def _emit_ws_events(self, records, ws_send_func) -> None:
        """Emit cost_update WS events with real data."""
        total_cost = 0.0
        for entry in records:
            if entry.get("Agent") == "Total":
                continue
            cost_value = float(str(entry.get("Cost ($)", "$0.0")).replace("$", ""))
            total_cost += cost_value
            ws_send_func("cost_update", {
                "run_id": self.run_id,
                "agent": entry.get("Agent", "unknown"),
                "model": entry.get("Model", "unknown"),
                "tokens": int(float(str(entry.get("Total Tokens", 0)))),
                "input_tokens": int(float(str(entry.get("Prompt Tokens", 0)))),
                "output_tokens": int(float(str(entry.get("Completion Tokens", 0)))),
                "cost_usd": cost_value,
                "total_cost_usd": total_cost,
            })
```

### Task 2.2: Add Cost Callback Invocation in Library

**File**: `cmbagent/cmbagent.py` - in `display_cost()` after writing JSON (around line 668):

```python
# After json.dump(cost_data, f, indent=2):
if hasattr(self, '_callbacks') and self._callbacks:
    self._callbacks.invoke_cost_update({
        "cost_json_path": json_path,
        "total_cost": float(df["Cost ($)"].sum()) if not df.empty else 0,
        "total_tokens": int(df["Total Tokens"].sum()) if not df.empty else 0,
        "records": cost_data,
    })
print(f"Cost report data saved to: {json_path}")
```

### Task 2.3: Wire CostCollector in task_executor

**File**: `backend/execution/task_executor.py`

Create CostCollector and wire it into the DAG tracking callbacks:
```python
from backend.execution.cost_collector import CostCollector

cost_collector = CostCollector(
    db_session=dag_tracker.db_session,
    session_id=session_id,
    run_id=effective_run_id
)

def on_cost_update_tracking(cost_data):
    cost_collector.collect_from_callback(cost_data, ws_send_func=ws_send_event)
```

### Task 2.4: Remove Cost Detection from StreamCapture

**File**: `backend/execution/stream_capture.py`

Delete entirely:
- `_detect_cost_updates()` (lines 255-344) - ~90 lines of stdout cost detection
- `_parse_cost_report()` (lines 264-344) - reads JSON from path found in stdout (now done by CostCollector)

Remove cost-related instance variables:
- `self.total_cost`
- `self.last_cost_report_time`

Remove `await self._detect_cost_updates(text)` call from `write()` (line 237).

### Task 2.5: Delete Dead CostManager

**File**: `cmbagent/managers/cost_manager.py` - DELETE entirely (~295 lines)

Verify no imports:
```bash
grep -rn "CostManager" cmbagent/ --include="*.py" | grep -v __pycache__ | grep -v cost_manager.py
```

Update `cmbagent/managers/__init__.py` to remove any CostManager export.

### Task 2.6: Remove 70/30 Token Estimation

**File**: `backend/callbacks/app_callbacks.py` (after Stage 0 move)

Find the cost callback that estimates tokens:
```python
# REMOVE this pattern:
estimated_prompt = int(total_tokens * 0.7)
estimated_completion = int(total_tokens * 0.3)
```

CostCollector now provides actual token counts from JSON files.

---

## Cleanup Items
| Item | Lines Removed |
|------|--------------|
| `cmbagent/managers/cost_manager.py` | ~295 (DELETE) |
| StreamCapture cost detection | ~90 |
| Token estimation in callbacks | ~15 |
| **Total** | **~400** |

## Verification
```bash
# CostManager gone
test ! -f cmbagent/managers/cost_manager.py
# No cost detection in StreamCapture
grep -c "_detect_cost\|_parse_cost\|total_cost" backend/execution/stream_capture.py  # 0
# Cost JSON files still written
ls /tmp/test_work_dir/cost/cost_report_*.json
# CostCollector reads actual tokens
python -c "from backend.execution.cost_collector import CostCollector; print('OK')"
```

## Files Modified
| File | Action |
|------|--------|
| `backend/execution/cost_collector.py` | NEW - JSON-based cost collection |
| `backend/execution/stream_capture.py` | Remove cost detection (~90 lines) |
| `backend/execution/task_executor.py` | Wire CostCollector |
| `backend/callbacks/app_callbacks.py` | Remove token estimation |
| `cmbagent/cmbagent.py` | Add cost callback invocation |
| `cmbagent/managers/cost_manager.py` | DELETE |
| `cmbagent/managers/__init__.py` | Remove CostManager export |
