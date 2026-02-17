# Stage 9: Print Statement Migration

**Phase:** 3 - Logging System
**Dependencies:** Stage 8 (Logging Configuration)
**Risk Level:** Low
**Estimated Time:** 3-4 hours

## Objectives

1. Identify all print statements in backend and cmbagent
2. Replace with structured logger calls
3. Ensure no debug output goes to console in production
4. Maintain useful debugging information

## Current State Analysis

### Print Statement Count

```bash
# Count print statements
grep -rn "print(" backend/ --include="*.py" | grep -v test | wc -l
# ~30+ in backend

grep -rn "print(" cmbagent/ --include="*.py" | grep -v test | wc -l
# ~50+ in cmbagent
```

### High-Priority Files
- `backend/websocket/handlers.py` - ~10 prints
- `backend/execution/task_executor.py` - ~20 prints
- `backend/services/connection_manager.py` - ~5 prints
- `cmbagent/orchestrator/swarm_orchestrator.py` - ~30 prints

## Implementation Tasks

### Task 1: Create Migration Script

**File to Create:** `scripts/migrate_prints.py`

```python
#!/usr/bin/env python3
"""
Find and report all print statements for migration to structured logging.
"""

import ast
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List

@dataclass
class PrintLocation:
    file: str
    line: int
    code: str
    context: str  # Suggested log level

class PrintFinder(ast.NodeVisitor):
    def __init__(self, filename: str, source_lines: List[str]):
        self.filename = filename
        self.source_lines = source_lines
        self.prints: List[PrintLocation] = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == 'print':
            line_content = self.source_lines[node.lineno - 1].strip()

            # Guess log level from content
            content_lower = line_content.lower()
            if 'error' in content_lower or 'fail' in content_lower:
                level = 'ERROR'
            elif 'warn' in content_lower:
                level = 'WARNING'
            elif 'debug' in content_lower or '[debug]' in content_lower:
                level = 'DEBUG'
            else:
                level = 'INFO'

            self.prints.append(PrintLocation(
                file=self.filename,
                line=node.lineno,
                code=line_content,
                context=level
            ))

        self.generic_visit(node)

def find_prints(directory: str, exclude_tests: bool = True) -> List[PrintLocation]:
    results = []

    for path in Path(directory).rglob('*.py'):
        if exclude_tests and 'test' in str(path).lower():
            continue

        try:
            with open(path) as f:
                source = f.read()
                lines = source.splitlines()

            tree = ast.parse(source)
            finder = PrintFinder(str(path), lines)
            finder.visit(tree)
            results.extend(finder.prints)

        except SyntaxError as e:
            print(f"Syntax error in {path}: {e}")

    return results

def generate_migration_report(prints: List[PrintLocation]) -> str:
    report = ["# Print Statement Migration Report\n"]
    report.append(f"Total print statements found: {len(prints)}\n")

    # Group by file
    by_file = {}
    for p in prints:
        if p.file not in by_file:
            by_file[p.file] = []
        by_file[p.file].append(p)

    for file, file_prints in sorted(by_file.items()):
        report.append(f"\n## {file}\n")
        report.append(f"Count: {len(file_prints)}\n")

        for p in file_prints:
            report.append(f"\n### Line {p.line} ({p.context})")
            report.append(f"```python")
            report.append(f"{p.code}")
            report.append(f"```")
            report.append(f"Suggested: `logger.{p.context.lower()}(...)`\n")

    return "\n".join(report)

if __name__ == "__main__":
    prints = find_prints("backend")
    prints.extend(find_prints("cmbagent"))

    print(f"Found {len(prints)} print statements")

    # Generate report
    report = generate_migration_report(prints)
    with open("PRINT_MIGRATION_REPORT.md", "w") as f:
        f.write(report)

    print("Report written to PRINT_MIGRATION_REPORT.md")
```

### Task 2: Migrate Backend Print Statements

**File to Modify:** `backend/websocket/handlers.py`

```python
# BEFORE:
print(f"[DEBUG] WebSocket received data for task {task_id}")
print(f"[DEBUG] Task: {task[:100]}...")
print(f"[DEBUG] Config mode: {config.get('mode', 'NOT SET')}")

# AFTER:
from core.logging import get_logger, bind_context

logger = get_logger(__name__)

# In websocket_endpoint:
bind_context(task_id=task_id)
logger.debug("websocket_received_data",
    task_preview=task[:100] if task else None,
    mode=config.get("mode"),
    config_keys=list(config.keys())
)
```

```python
# BEFORE:
print(f"Created workflow run: {run_result}")

# AFTER:
logger.info("workflow_run_created", **run_result)
```

```python
# BEFORE:
print(f"[WebSocket] Execution completed successfully for task {task_id}")

# AFTER:
logger.info("execution_completed", status="success")
```

```python
# BEFORE:
print(f"Error in WebSocket endpoint: {e}")

# AFTER:
logger.error("websocket_endpoint_error", error=str(e), exc_info=True)
```

### Task 3: Migrate Task Executor Print Statements

**File to Modify:** `backend/execution/task_executor.py`

```python
# BEFORE:
print(f"[DEBUG] execute_cmbagent_task called")
print(f"[DEBUG] Task ID: {task_id}")
print(f"[DEBUG] Mode: {config.get('mode', 'NOT SET')}")

# AFTER:
logger = get_logger(__name__)

logger.debug("execute_task_started",
    mode=config.get("mode"),
    config_keys=list(config.keys())
)
```

```python
# BEFORE:
print(f"[ws_send_event] Attempting to send event: {event_type}")
print(f"[ws_send_event] Event data keys: {list(data.keys())}")

# AFTER:
logger.debug("ws_send_event",
    event_type=event_type,
    data_keys=list(data.keys())
)
```

```python
# BEFORE:
print(f"[TaskExecutor] Phase changed to: {phase}, step: {step_number}")

# AFTER:
logger.info("phase_changed", phase=phase, step=step_number)
```

### Task 4: Migrate Connection Manager Print Statements

**File to Modify:** `backend/services/connection_manager.py`

```python
# BEFORE:
print(f"[ConnectionManager] Registered connection for task {task_id}")

# AFTER:
logger.info("connection_registered", total_connections=len(self._connections))
```

```python
# BEFORE:
print(f"[ConnectionManager] Error sending event: {e}")

# AFTER:
logger.warning("send_event_failed", error=str(e))
```

### Task 5: Handle CMBAgent Core Prints (Optional)

For `cmbagent/` directory prints, consider:

1. **Keep as-is for subprocess isolation** - These run in isolated processes, so they don't pollute the main process. They get captured and forwarded via queue.

2. **Or add logging config to CMBAgent core:**
```python
# In cmbagent/__init__.py
from backend.core.logging import configure_logging
configure_logging(log_level="INFO")
```

### Task 6: Verify No Print Statements Remain

```bash
# After migration, count should be 0 (or very low for intentional user output)
grep -rn "print(" backend/ --include="*.py" | grep -v test | grep -v "# print" | wc -l
```

## Verification Criteria

### Must Pass
- [ ] No print statements in critical paths
- [ ] Logs include context (task_id, session_id)
- [ ] Error logs include stack traces
- [ ] Log levels appropriate (DEBUG for verbose, INFO for important)

### Test Script
```bash
#!/bin/bash
# test_stage_9.sh

echo "Counting remaining print statements..."

BACKEND_COUNT=$(grep -rn "print(" backend/ --include="*.py" | grep -v test | grep -v "# print" | wc -l)
echo "Backend: $BACKEND_COUNT prints remaining"

if [ "$BACKEND_COUNT" -gt 5 ]; then
    echo "❌ Too many print statements in backend"
    exit 1
fi

echo "✅ Print migration complete"

# Test that logging works
python -c "
from backend.core.logging import get_logger, bind_context
logger = get_logger('test')
bind_context(task_id='test123')
logger.info('test_message', key='value')
print('✅ Logging works correctly')
"
```

## Migration Patterns

### Pattern 1: Debug Print
```python
# Before
print(f"[DEBUG] Processing item: {item}")

# After
logger.debug("processing_item", item=item)
```

### Pattern 2: Error Print
```python
# Before
print(f"Error: {e}")

# After
logger.error("operation_failed", error=str(e), exc_info=True)
```

### Pattern 3: Status Print
```python
# Before
print(f"✅ Task {task_id} completed")

# After
logger.info("task_completed")
# Note: emoji removed, status clear from event name
```

### Pattern 4: Multi-line Debug
```python
# Before
print(f"Data received:")
print(f"  - Field1: {data['field1']}")
print(f"  - Field2: {data['field2']}")

# After
logger.debug("data_received",
    field1=data['field1'],
    field2=data['field2']
)
```

## Success Criteria

Stage 9 is complete when:
1. ✅ Backend print count < 5
2. ✅ All logs use structured format
3. ✅ Context binding works throughout
4. ✅ No user-visible output changes

## Next Stage

Once Stage 9 is verified complete, proceed to:
**Stage 10: Session Management API**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-11
