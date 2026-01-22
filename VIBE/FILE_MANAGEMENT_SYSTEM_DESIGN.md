# CMBAgent File Management System - Production-Grade Design

## Document Version: 1.0
## Date: 2026-01-21
## Status: Design Review

---

## Executive Summary

This document outlines a comprehensive redesign of CMBAgent's file management system to properly track, categorize, and present all generated artifacts across different execution modes. The current system has critical gaps that cause files to be lost or not displayed to users.

---

## Part 1: Current State Analysis

### 1.1 The Core Problem

**Files are generated but not properly captured or returned as outputs.**

Current flow:
```
Task → Execution → Files Created → ??? → User sees incomplete results
```

The `???` represents multiple failure points where files get lost.

### 1.2 File Generation Points (Complete Map)

| Mode | Phase | Directory | Files Created |
|------|-------|-----------|---------------|
| `one_shot` | execution | `work_dir/data/` | CSV, JSON, plots |
| `one_shot` | execution | `work_dir/codebase/` | Python scripts |
| `one_shot` | reporting | `work_dir/time/` | timing_report_*.json |
| `one_shot` | reporting | `work_dir/cost/` | cost_report_*.json |
| `planning_and_control` | planning | `work_dir/planning/` | final_plan.json |
| `planning_and_control` | planning | `work_dir/planning/chats/` | chat history |
| `planning_and_control` | control | `work_dir/control/data/` | Step outputs |
| `planning_and_control` | control | `work_dir/control/codebase/` | Step code |
| `planning_and_control` | control | `work_dir/control/time/` | Per-step timing |
| `planning_and_control` | context | `work_dir/context/` | context_step_*.pkl |
| `parallel_execution` | node | `work_dir/runs/{run_id}/parallel/{node_id}/` | Isolated outputs |
| `deep_research` | docs | `work_dir/docs/` | Downloaded documents |
| `deep_research` | summaries | `work_dir/summaries/` | Analysis summaries |

### 1.3 Current Tracking Gaps

#### Gap 1: Hardcoded Directory List
```python
# backend/main.py:1506
output_dirs = ["data", "codebase", "outputs", "chats", "cost", "time", "planning"]
```
**Missing:** `control/`, `context/`, `docs/`, `summaries/`, `runs/`

#### Gap 2: No Code Executor Integration
AG2's `LocalCommandLineCodeExecutor` creates files but nothing captures them:
```python
# When code runs: plt.savefig('plot.png')
# File is created but NOT tracked
```

#### Gap 3: No Final Output Aggregation
Results returned to user:
```python
return {
    'chat_history': [...],
    'final_context': {...},  # Contains work_dir path, but NO file list
    # NO 'outputs' or 'artifacts' field!
}
```

#### Gap 4: Parallel Execution Scattering
Files created in isolated directories:
```
work_dir/runs/run_abc/parallel/node_1/data/plot1.png
work_dir/runs/run_abc/parallel/node_2/data/plot2.png
```
These may never be collected.

---

## Part 2: Production-Grade Design

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FILE MANAGEMENT SYSTEM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                     CAPTURE LAYER                                   │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │     │
│  │  │ FileWatcher  │  │ CodeExecutor │  │ ExplicitCapture          │ │     │
│  │  │ (watchdog)   │  │ Wrapper      │  │ (manual registration)    │ │     │
│  │  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘ │     │
│  └─────────┼─────────────────┼───────────────────────┼───────────────┘     │
│            │                 │                       │                      │
│            ▼                 ▼                       ▼                      │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                     REGISTRY LAYER                                  │     │
│  │  ┌──────────────────────────────────────────────────────────────┐ │     │
│  │  │                    FileRegistry                               │ │     │
│  │  │  - In-memory index (fast lookups)                            │ │     │
│  │  │  - File classification engine                                │ │     │
│  │  │  - Deduplication                                             │ │     │
│  │  │  - Phase/Step association                                    │ │     │
│  │  └──────────────────────────┬───────────────────────────────────┘ │     │
│  └─────────────────────────────┼─────────────────────────────────────┘     │
│                                │                                            │
│                                ▼                                            │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                     PERSISTENCE LAYER                               │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │     │
│  │  │ Database     │  │ WebSocket    │  │ OutputCollector          │ │     │
│  │  │ (File model) │  │ (real-time)  │  │ (final aggregation)      │ │     │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘ │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                     OUTPUT LAYER                                    │     │
│  │  ┌──────────────────────────────────────────────────────────────┐ │     │
│  │  │                    WorkflowOutputs                            │ │     │
│  │  │  - Primary outputs (user deliverables)                       │ │     │
│  │  │  - Secondary outputs (debugging/monitoring)                  │ │     │
│  │  │  - Codebase snapshot                                         │ │     │
│  │  │  - Execution artifacts                                       │ │     │
│  │  └──────────────────────────────────────────────────────────────┘ │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Components

#### 2.2.1 FileRegistry (Central Brain)

```python
# cmbagent/execution/file_registry.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum
from pathlib import Path
import hashlib
import os

class FileCategory(Enum):
    """Primary categorization of files."""
    PLAN = "plan"              # Workflow plans
    CODE = "code"              # Generated source code
    DATA = "data"              # Data files (CSV, JSON, etc.)
    PLOT = "plot"              # Visualizations
    REPORT = "report"          # Timing, cost, analysis reports
    CHAT = "chat"              # Conversation history
    CONTEXT = "context"        # Pickled context files
    LOG = "log"                # Execution logs
    OTHER = "other"            # Uncategorized

class OutputPriority(Enum):
    """Determines if file is shown as primary output."""
    PRIMARY = "primary"        # User deliverables (plots, data, code)
    SECONDARY = "secondary"    # Supporting files (reports, logs)
    INTERNAL = "internal"      # System files (context, temp)

@dataclass
class TrackedFile:
    """Complete metadata for a tracked file."""
    id: str
    path: str
    relative_path: str
    filename: str
    category: FileCategory
    priority: OutputPriority
    size_bytes: int
    content_hash: str

    # Workflow context
    run_id: str
    phase: str                 # planning, control, execution
    step_number: Optional[int] = None
    node_id: Optional[str] = None

    # Generation context
    generating_agent: Optional[str] = None
    generating_code_hash: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Flags
    is_final_output: bool = False
    is_user_facing: bool = False


class FileRegistry:
    """
    Central registry for all workflow files.

    Design principles:
    1. Single source of truth for file tracking
    2. Fast in-memory lookups with database persistence
    3. Deterministic file classification
    4. Thread-safe for parallel execution
    """

    def __init__(
        self,
        work_dir: str,
        run_id: str,
        db_session,
        websocket=None
    ):
        self.work_dir = Path(work_dir)
        self.run_id = run_id
        self.db = db_session
        self.websocket = websocket

        # In-memory indices for fast access
        self._files_by_id: Dict[str, TrackedFile] = {}
        self._files_by_path: Dict[str, TrackedFile] = {}
        self._files_by_category: Dict[FileCategory, List[str]] = {c: [] for c in FileCategory}
        self._files_by_phase: Dict[str, List[str]] = {}
        self._files_by_step: Dict[int, List[str]] = {}

        # Deduplication
        self._seen_hashes: Set[str] = set()

        # Thread safety
        self._lock = threading.RLock()

        # Current context (set by workflow engine)
        self._current_phase: str = "execution"
        self._current_step: Optional[int] = None
        self._current_node: Optional[str] = None
        self._current_agent: Optional[str] = None

    def set_context(
        self,
        phase: str = None,
        step: int = None,
        node_id: str = None,
        agent: str = None
    ):
        """Update current execution context for file association."""
        with self._lock:
            if phase: self._current_phase = phase
            if step is not None: self._current_step = step
            if node_id: self._current_node = node_id
            if agent: self._current_agent = agent

    def register_file(
        self,
        path: str,
        category: FileCategory = None,
        is_final_output: bool = None,
        generating_code: str = None
    ) -> Optional[TrackedFile]:
        """
        Register a file with the registry.

        Args:
            path: Absolute or relative path to file
            category: Override automatic classification
            is_final_output: Override automatic priority
            generating_code: Code that generated this file (for linking)

        Returns:
            TrackedFile if registered, None if duplicate or invalid
        """
        with self._lock:
            # Normalize path
            abs_path = self._normalize_path(path)
            if not os.path.exists(abs_path):
                return None

            # Check for duplicates
            rel_path = os.path.relpath(abs_path, self.work_dir)
            if rel_path in self._files_by_path:
                return self._files_by_path[rel_path]

            # Compute hash for deduplication
            content_hash = self._compute_hash(abs_path)

            # Classify file
            if category is None:
                category = self._classify_file(abs_path, rel_path)

            # Determine priority
            priority = self._determine_priority(category, rel_path, is_final_output)

            # Create tracked file
            file_id = str(uuid.uuid4())
            tracked = TrackedFile(
                id=file_id,
                path=abs_path,
                relative_path=rel_path,
                filename=os.path.basename(abs_path),
                category=category,
                priority=priority,
                size_bytes=os.path.getsize(abs_path),
                content_hash=content_hash,
                run_id=self.run_id,
                phase=self._current_phase,
                step_number=self._current_step,
                node_id=self._current_node,
                generating_agent=self._current_agent,
                generating_code_hash=hashlib.md5(generating_code.encode()).hexdigest() if generating_code else None,
                is_final_output=(priority == OutputPriority.PRIMARY),
                is_user_facing=(priority in [OutputPriority.PRIMARY, OutputPriority.SECONDARY])
            )

            # Store in indices
            self._files_by_id[file_id] = tracked
            self._files_by_path[rel_path] = tracked
            self._files_by_category[category].append(file_id)
            self._files_by_phase.setdefault(self._current_phase, []).append(file_id)
            if self._current_step is not None:
                self._files_by_step.setdefault(self._current_step, []).append(file_id)

            # Persist to database
            self._persist_to_db(tracked)

            # Emit WebSocket event
            self._emit_file_created(tracked)

            return tracked

    def _classify_file(self, abs_path: str, rel_path: str) -> FileCategory:
        """
        Classify file based on path and extension.

        Classification rules (in order of precedence):
        1. Explicit filename patterns (final_plan.json → PLAN)
        2. Directory location (codebase/ → CODE)
        3. File extension (.png → PLOT)
        """
        filename = os.path.basename(abs_path)
        ext = os.path.splitext(filename)[1].lower()

        # Rule 1: Explicit patterns
        if filename == 'final_plan.json' or filename.endswith('_plan.json'):
            return FileCategory.PLAN
        if filename.startswith('timing_report') or filename.startswith('cost_report'):
            return FileCategory.REPORT

        # Rule 2: Directory location
        parts = rel_path.split(os.sep)
        if 'codebase' in parts:
            return FileCategory.CODE
        if 'chats' in parts:
            return FileCategory.CHAT
        if 'context' in parts:
            return FileCategory.CONTEXT
        if 'time' in parts or 'cost' in parts:
            return FileCategory.REPORT

        # Rule 3: Extension
        if ext in ['.py', '.js', '.ts', '.java', '.cpp', '.go', '.rs']:
            return FileCategory.CODE
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.pdf', '.eps']:
            return FileCategory.PLOT
        if ext in ['.csv', '.json', '.pkl', '.npz', '.npy', '.parquet', '.yaml', '.yml']:
            return FileCategory.DATA
        if ext in ['.md', '.rst', '.txt']:
            return FileCategory.REPORT
        if ext in ['.log']:
            return FileCategory.LOG

        return FileCategory.OTHER

    def _determine_priority(
        self,
        category: FileCategory,
        rel_path: str,
        override: bool = None
    ) -> OutputPriority:
        """Determine output priority for display ordering."""
        if override is not None:
            return OutputPriority.PRIMARY if override else OutputPriority.SECONDARY

        # Primary outputs (user deliverables)
        if category in [FileCategory.PLOT, FileCategory.DATA, FileCategory.CODE]:
            # But not if in internal directories
            if 'context' not in rel_path and 'temp' not in rel_path:
                return OutputPriority.PRIMARY

        if category == FileCategory.PLAN:
            return OutputPriority.PRIMARY

        # Secondary outputs
        if category in [FileCategory.REPORT, FileCategory.CHAT]:
            return OutputPriority.SECONDARY

        # Internal
        return OutputPriority.INTERNAL

    def get_final_outputs(self) -> Dict[str, List[TrackedFile]]:
        """
        Get organized final outputs for user presentation.

        Returns:
            {
                'primary': [...],   # Main deliverables
                'code': [...],      # Generated code
                'data': [...],      # Data files
                'plots': [...],     # Visualizations
                'reports': [...]    # Analysis reports
            }
        """
        with self._lock:
            outputs = {
                'primary': [],
                'code': [],
                'data': [],
                'plots': [],
                'reports': []
            }

            for file_id, tracked in self._files_by_id.items():
                if tracked.priority == OutputPriority.PRIMARY:
                    outputs['primary'].append(tracked)

                if tracked.category == FileCategory.CODE:
                    outputs['code'].append(tracked)
                elif tracked.category == FileCategory.DATA:
                    outputs['data'].append(tracked)
                elif tracked.category == FileCategory.PLOT:
                    outputs['plots'].append(tracked)
                elif tracked.category == FileCategory.REPORT:
                    outputs['reports'].append(tracked)

            return outputs

    def get_outputs_for_step(self, step_number: int) -> List[TrackedFile]:
        """Get all outputs generated during a specific step."""
        with self._lock:
            file_ids = self._files_by_step.get(step_number, [])
            return [self._files_by_id[fid] for fid in file_ids]

    def scan_work_directory(self) -> int:
        """
        Full scan of work directory for any untracked files.
        Called at workflow end to catch any missed files.

        Returns:
            Number of newly registered files
        """
        count = 0
        for root, dirs, files in os.walk(self.work_dir):
            # Skip hidden and temp directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'temp' and d != '__pycache__']

            for filename in files:
                if filename.startswith('.'):
                    continue

                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, self.work_dir)

                if rel_path not in self._files_by_path:
                    if self.register_file(abs_path):
                        count += 1

        return count
```

#### 2.2.2 TrackedCodeExecutor (AG2 Integration)

```python
# cmbagent/execution/tracked_code_executor.py

from autogen.coding import LocalCommandLineCodeExecutor
from autogen.coding.base import CodeBlock, CodeResult
import os
import time
from pathlib import Path
from typing import List, Set

class TrackedCodeExecutor(LocalCommandLineCodeExecutor):
    """
    Code executor that tracks all files generated during execution.

    Wraps AG2's LocalCommandLineCodeExecutor to:
    1. Snapshot directory before execution
    2. Execute code normally
    3. Detect new files after execution
    4. Register new files with FileRegistry
    """

    def __init__(
        self,
        *args,
        file_registry: 'FileRegistry' = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.file_registry = file_registry
        self._execution_count = 0

    def execute_code_blocks(
        self,
        code_blocks: List[CodeBlock]
    ) -> CodeResult:
        """Execute code blocks while tracking generated files."""

        # Snapshot before
        before_files = self._snapshot_directory()
        code_text = "\n".join(block.code for block in code_blocks)

        # Execute
        start_time = time.time()
        result = super().execute_code_blocks(code_blocks)
        execution_time = time.time() - start_time

        # Snapshot after
        after_files = self._snapshot_directory()

        # Detect new files
        new_files = after_files - before_files

        # Register each new file
        if self.file_registry and new_files:
            for file_path in new_files:
                self.file_registry.register_file(
                    path=file_path,
                    generating_code=code_text
                )

        self._execution_count += 1

        return result

    def _snapshot_directory(self) -> Set[str]:
        """Get all files in work_dir recursively."""
        files = set()
        work_path = Path(self.work_dir)

        if not work_path.exists():
            return files

        for item in work_path.rglob('*'):
            if item.is_file() and not item.name.startswith('.'):
                files.add(str(item))

        return files
```

#### 2.2.3 FileWatcher (Real-Time Monitoring)

```python
# cmbagent/execution/file_watcher.py

import os
import time
import threading
from pathlib import Path
from typing import Callable, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

class WorkflowFileHandler(FileSystemEventHandler):
    """Handler for file system events during workflow execution."""

    def __init__(
        self,
        file_registry: 'FileRegistry',
        ignore_patterns: Set[str] = None
    ):
        self.file_registry = file_registry
        self.ignore_patterns = ignore_patterns or {
            '.pyc', '.pyo', '__pycache__', '.git', '.DS_Store',
            '.tmp', '.temp', '.swp', '.swo'
        }
        self._debounce_map = {}
        self._debounce_seconds = 0.5

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return

        path = event.src_path

        # Ignore patterns
        if any(p in path for p in self.ignore_patterns):
            return

        # Debounce rapid events (e.g., file write + close)
        if self._should_debounce(path):
            return

        # Register file
        self.file_registry.register_file(path)

    def on_modified(self, event):
        """Handle file modification events (for size updates)."""
        if event.is_directory:
            return

        # Could update file size/hash here if needed
        pass

    def _should_debounce(self, path: str) -> bool:
        """Prevent duplicate events for same file."""
        now = time.time()
        last_time = self._debounce_map.get(path, 0)

        if now - last_time < self._debounce_seconds:
            return True

        self._debounce_map[path] = now
        return False


class FileWatcher:
    """
    Real-time file system watcher for workflow execution.

    Uses watchdog for cross-platform file monitoring.
    Designed to be started at workflow begin and stopped at end.
    """

    def __init__(
        self,
        work_dir: str,
        file_registry: 'FileRegistry'
    ):
        self.work_dir = work_dir
        self.file_registry = file_registry
        self.observer = None
        self._running = False

    def start(self):
        """Start watching the work directory."""
        if self._running:
            return

        # Ensure directory exists
        os.makedirs(self.work_dir, exist_ok=True)

        # Create observer
        self.observer = Observer()
        handler = WorkflowFileHandler(self.file_registry)

        # Watch recursively
        self.observer.schedule(handler, self.work_dir, recursive=True)
        self.observer.start()
        self._running = True

    def stop(self):
        """Stop watching."""
        if not self._running:
            return

        self.observer.stop()
        self.observer.join(timeout=5)
        self._running = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
```

#### 2.2.4 OutputCollector (Final Aggregation)

```python
# cmbagent/execution/output_collector.py

from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional
import json
import os
from pathlib import Path

@dataclass
class WorkflowOutputs:
    """
    Final outputs from a workflow execution.
    This is what gets returned to the user.
    """
    # Primary outputs (what user asked for)
    primary_outputs: List[Dict[str, Any]]

    # Categorized outputs
    plans: List[Dict[str, Any]]
    code_files: List[Dict[str, Any]]
    data_files: List[Dict[str, Any]]
    plots: List[Dict[str, Any]]
    reports: List[Dict[str, Any]]

    # Metadata
    total_files: int
    total_size_bytes: int
    work_dir: str

    # Per-step breakdown (for planning_and_control)
    outputs_by_step: Dict[int, List[Dict[str, Any]]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class OutputCollector:
    """
    Collects and organizes final outputs at workflow completion.

    Responsibilities:
    1. Query FileRegistry for all tracked files
    2. Organize into categories
    3. Generate manifest file
    4. Return structured outputs
    """

    def __init__(self, file_registry: 'FileRegistry', work_dir: str):
        self.file_registry = file_registry
        self.work_dir = work_dir

    def collect(self) -> WorkflowOutputs:
        """
        Collect all outputs from the workflow.

        Called at workflow completion before returning to user.
        """
        # First, do a final scan to catch any missed files
        self.file_registry.scan_work_directory()

        # Get organized outputs
        organized = self.file_registry.get_final_outputs()

        # Convert to serializable format
        def to_dict(tracked_file):
            return {
                'id': tracked_file.id,
                'path': tracked_file.relative_path,
                'filename': tracked_file.filename,
                'category': tracked_file.category.value,
                'size_bytes': tracked_file.size_bytes,
                'phase': tracked_file.phase,
                'step_number': tracked_file.step_number,
                'is_final_output': tracked_file.is_final_output
            }

        # Build outputs by step
        outputs_by_step = {}
        all_files = list(self.file_registry._files_by_id.values())
        for f in all_files:
            if f.step_number is not None:
                outputs_by_step.setdefault(f.step_number, []).append(to_dict(f))

        # Calculate totals
        total_size = sum(f.size_bytes for f in all_files)

        # Create WorkflowOutputs
        outputs = WorkflowOutputs(
            primary_outputs=[to_dict(f) for f in organized['primary']],
            plans=[to_dict(f) for f in all_files if f.category.value == 'plan'],
            code_files=[to_dict(f) for f in organized['code']],
            data_files=[to_dict(f) for f in organized['data']],
            plots=[to_dict(f) for f in organized['plots']],
            reports=[to_dict(f) for f in organized['reports']],
            total_files=len(all_files),
            total_size_bytes=total_size,
            work_dir=self.work_dir,
            outputs_by_step=outputs_by_step
        )

        # Write manifest file
        self._write_manifest(outputs)

        return outputs

    def _write_manifest(self, outputs: WorkflowOutputs):
        """Write outputs manifest to work directory."""
        manifest_path = os.path.join(self.work_dir, 'outputs_manifest.json')
        with open(manifest_path, 'w') as f:
            f.write(outputs.to_json())
```

---

## Part 3: Integration Points

### 3.1 Integration with CMBAgent

```python
# In cmbagent/cmbagent.py - modify __init__ and run methods

class CMBAgent:
    def __init__(self, ...):
        # ... existing code ...

        # Initialize file management system
        self.file_registry = None
        self.file_watcher = None
        self.output_collector = None

    def _init_file_tracking(self, run_id: str):
        """Initialize file tracking for a workflow run."""
        from cmbagent.execution.file_registry import FileRegistry
        from cmbagent.execution.file_watcher import FileWatcher
        from cmbagent.execution.output_collector import OutputCollector

        self.file_registry = FileRegistry(
            work_dir=self.work_dir,
            run_id=run_id,
            db_session=self.db_session,
            websocket=self.websocket
        )

        self.file_watcher = FileWatcher(
            work_dir=self.work_dir,
            file_registry=self.file_registry
        )
        self.file_watcher.start()

        self.output_collector = OutputCollector(
            file_registry=self.file_registry,
            work_dir=self.work_dir
        )

    def _finalize_file_tracking(self) -> 'WorkflowOutputs':
        """Finalize file tracking and collect outputs."""
        if self.file_watcher:
            self.file_watcher.stop()

        if self.output_collector:
            return self.output_collector.collect()

        return None
```

### 3.2 Integration with one_shot()

```python
def one_shot(task, agent='engineer', model='gpt-4o', work_dir=work_dir_default, ...):
    # ... existing setup ...

    # Initialize file tracking
    run_id = str(uuid.uuid4())
    cmbagent_instance._init_file_tracking(run_id)
    cmbagent_instance.file_registry.set_context(phase='execution')

    # ... execution ...

    # Finalize and collect outputs
    workflow_outputs = cmbagent_instance._finalize_file_tracking()

    # Add outputs to results
    results['outputs'] = workflow_outputs.to_dict() if workflow_outputs else None
    results['run_id'] = run_id

    return results
```

### 3.3 Integration with planning_and_control()

```python
def planning_and_control(task, model='gpt-4o', work_dir=work_dir_default, ...):
    # Initialize file tracking
    run_id = str(uuid.uuid4())
    file_registry = FileRegistry(work_dir=work_dir, run_id=run_id, ...)
    file_watcher = FileWatcher(work_dir=work_dir, file_registry=file_registry)
    file_watcher.start()

    # Planning phase
    file_registry.set_context(phase='planning')
    # ... planning execution ...

    # Explicitly register plan file
    plan_path = os.path.join(work_dir, "planning/final_plan.json")
    file_registry.register_file(plan_path, is_final_output=True)

    # Control phase
    for step_number, step in enumerate(plan['sub_tasks'], 1):
        file_registry.set_context(phase='control', step=step_number)
        # ... step execution ...

    # Finalize
    file_watcher.stop()
    output_collector = OutputCollector(file_registry, work_dir)
    workflow_outputs = output_collector.collect()

    results['outputs'] = workflow_outputs.to_dict()
    return results
```

### 3.4 Integration with base_agent.py

```python
# In base_agent.py - use TrackedCodeExecutor

from cmbagent.execution.tracked_code_executor import TrackedCodeExecutor
from cmbagent.execution.file_registry import get_global_registry

class BaseAgent:
    def _create_code_executor(self):
        file_registry = get_global_registry()  # Global registry for current run

        return TrackedCodeExecutor(
            work_dir=self.work_dir,
            timeout=self.info["timeout"],
            file_registry=file_registry,
            execution_policies=execution_policies
        )
```

---

## Part 4: Critical Failure Analysis

### 4.1 Potential Failure Points

| Failure Point | Risk Level | Mitigation |
|---------------|------------|------------|
| **File created before watcher starts** | HIGH | Do initial scan at watcher start |
| **Race condition: file created during scan** | MEDIUM | Use file hash deduplication |
| **Large files cause memory issues** | MEDIUM | Stream hash computation, don't load full file |
| **Parallel execution file conflicts** | HIGH | Use run_id in file tracking, merge properly |
| **Watchdog misses events** | MEDIUM | Final scan at workflow end |
| **Database write fails** | LOW | Use transactions, retry logic |
| **WebSocket disconnects** | LOW | Buffer events, resend on reconnect |
| **File deleted after creation** | LOW | Check existence before registration |
| **Symlinks cause infinite loops** | LOW | Skip symlinks in scan |
| **Permission denied on files** | LOW | Try/catch, log warning, continue |

### 4.2 Detailed Failure Scenarios

#### Scenario 1: File Created Before Watcher Starts
```
Timeline:
1. Workflow starts
2. Directory created
3. Files created by setup code  <-- MISSED!
4. FileWatcher starts
5. More files created  <-- Captured
```

**Mitigation:**
```python
class FileWatcher:
    def start(self):
        # Initial scan BEFORE starting observer
        self.file_registry.scan_work_directory()

        # Now start watching
        self.observer.start()
```

#### Scenario 2: Parallel Execution Scattering
```
Timeline:
1. Parallel tasks start in isolated directories
2. Task 1 creates: runs/run_abc/parallel/node_1/data/plot1.png
3. Task 2 creates: runs/run_abc/parallel/node_2/data/plot2.png
4. Tasks complete
5. Main workflow continues
6. Files never merged/tracked  <-- LOST!
```

**Mitigation:**
```python
class FileRegistry:
    def merge_parallel_outputs(self, node_dirs: List[str]):
        """Merge outputs from parallel nodes into main registry."""
        for node_dir in node_dirs:
            for root, dirs, files in os.walk(node_dir):
                for f in files:
                    path = os.path.join(root, f)
                    # Copy to main data directory
                    rel_path = os.path.relpath(path, node_dir)
                    dest_path = os.path.join(self.work_dir, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(path, dest_path)
                    # Register in main registry
                    self.register_file(dest_path)
```

#### Scenario 3: Database Failure During High-Volume File Creation
```
Timeline:
1. Code execution generates 100 files rapidly
2. Each file triggers database INSERT
3. Database connection pool exhausted
4. Some files not persisted  <-- LOST!
```

**Mitigation:**
```python
class FileRegistry:
    def __init__(self, ...):
        self._pending_batch = []
        self._batch_size = 50
        self._batch_lock = threading.Lock()

    def register_file(self, path: str, ...):
        # Add to in-memory index immediately
        tracked = self._create_tracked_file(path)
        self._add_to_indices(tracked)

        # Batch database writes
        with self._batch_lock:
            self._pending_batch.append(tracked)
            if len(self._pending_batch) >= self._batch_size:
                self._flush_batch()

    def _flush_batch(self):
        """Persist pending files to database."""
        if not self._pending_batch:
            return

        try:
            # Bulk insert
            self.db.bulk_save_objects([
                self._to_db_model(f) for f in self._pending_batch
            ])
            self.db.commit()
            self._pending_batch = []
        except Exception as e:
            self.db.rollback()
            # Log error but don't lose in-memory tracking
            logger.error(f"Failed to persist files: {e}")
```

### 4.3 Feasibility Assessment

| Component | Complexity | Risk | Dependencies | Recommendation |
|-----------|------------|------|--------------|----------------|
| **FileRegistry** | Medium | Low | None | ✅ Implement first |
| **TrackedCodeExecutor** | Low | Low | FileRegistry | ✅ Implement second |
| **FileWatcher (watchdog)** | Medium | Medium | watchdog lib | ⚠️ Optional - final scan may suffice |
| **OutputCollector** | Low | Low | FileRegistry | ✅ Implement third |
| **Database schema changes** | Low | Low | Alembic migration | ✅ Minor changes only |
| **WebSocket events** | Low | Low | Existing infra | ✅ Add new event types |
| **UI changes** | Medium | Low | Existing DAGFilesView | ✅ Enhance existing |

### 4.4 What Could Go Wrong

1. **Performance Impact**
   - File system watching adds overhead
   - Hash computation for large files is slow
   - **Mitigation:** Make FileWatcher optional, use async hashing

2. **Complexity Creep**
   - Four new classes to maintain
   - Integration points across codebase
   - **Mitigation:** Keep interfaces simple, document thoroughly

3. **Edge Cases**
   - Files created then deleted
   - Circular symlinks
   - Very long paths (Windows limit)
   - **Mitigation:** Defensive coding, skip problematic files

4. **Backward Compatibility**
   - Old runs won't have outputs field
   - UI must handle missing data
   - **Mitigation:** Graceful fallback in UI

---

## Part 5: Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

**Goal:** Basic file tracking without real-time monitoring

**Tasks:**
1. Create `cmbagent/execution/file_registry.py`
   - FileCategory enum
   - OutputPriority enum
   - TrackedFile dataclass
   - FileRegistry class (without watchdog)

2. Create `cmbagent/execution/tracked_code_executor.py`
   - Wrap LocalCommandLineCodeExecutor
   - Snapshot before/after execution
   - Register new files

3. Update `base_agent.py`
   - Use TrackedCodeExecutor instead of LocalCommandLineCodeExecutor

4. Create `cmbagent/execution/output_collector.py`
   - WorkflowOutputs dataclass
   - OutputCollector class
   - Manifest file generation

**Deliverables:**
- Files tracked during code execution
- Outputs returned in results
- Manifest file generated

### Phase 2: Integration (Week 2)

**Goal:** Full integration with workflow modes

**Tasks:**
1. Update `one_shot()` function
   - Initialize FileRegistry at start
   - Finalize and collect outputs at end
   - Add `outputs` to return value

2. Update `planning_and_control()` function
   - Phase-aware context setting
   - Explicit plan file registration
   - Per-step file tracking

3. Update backend `main.py`
   - Update DAGTracker to use FileRegistry
   - Fix hardcoded directory list
   - Add WebSocket events for file tracking

4. Database migration
   - Add `workflow_phase` column to File model
   - Add `is_final_output` column
   - Add `generation_source` column

**Deliverables:**
- All modes tracked properly
- Plan files captured
- Per-step outputs available

### Phase 3: Real-Time Monitoring (Week 3) - OPTIONAL

**Goal:** Real-time file detection

**Tasks:**
1. Create `cmbagent/execution/file_watcher.py`
   - WorkflowFileHandler
   - FileWatcher with watchdog

2. Integrate FileWatcher
   - Start at workflow begin
   - Stop at workflow end
   - Initial scan before watching

3. Add WebSocket real-time events
   - FILE_CREATED event
   - FILE_UPDATED event

**Deliverables:**
- Real-time file notifications
- UI updates as files created

### Phase 4: UI Enhancement (Week 4)

**Goal:** Better file presentation

**Tasks:**
1. Update DAGFilesView
   - Group by category
   - Group by step
   - Show primary outputs prominently

2. Add Outputs tab to results
   - Show primary outputs
   - Categorized file lists
   - Download all as ZIP

3. Add file preview improvements
   - Better plot rendering
   - Code syntax highlighting
   - Data table preview

**Deliverables:**
- Enhanced file browser
- Clear output presentation

---

## Part 6: Testing Strategy

### 6.1 Unit Tests

```python
# tests/test_file_registry.py

def test_file_classification():
    registry = FileRegistry(work_dir='/tmp/test', run_id='test-123')

    # Test code classification
    assert registry._classify_file('/tmp/test/codebase/script.py', 'codebase/script.py') == FileCategory.CODE

    # Test plot classification
    assert registry._classify_file('/tmp/test/data/plot.png', 'data/plot.png') == FileCategory.PLOT

    # Test plan classification
    assert registry._classify_file('/tmp/test/planning/final_plan.json', 'planning/final_plan.json') == FileCategory.PLAN

def test_deduplication():
    registry = FileRegistry(work_dir='/tmp/test', run_id='test-123')

    # Create test file
    test_file = '/tmp/test/data/test.csv'
    os.makedirs('/tmp/test/data', exist_ok=True)
    with open(test_file, 'w') as f:
        f.write('a,b,c\n1,2,3')

    # Register twice
    result1 = registry.register_file(test_file)
    result2 = registry.register_file(test_file)

    # Should return same object
    assert result1.id == result2.id
    assert len(registry._files_by_id) == 1

def test_code_executor_tracking():
    registry = FileRegistry(work_dir='/tmp/test', run_id='test-123')
    executor = TrackedCodeExecutor(work_dir='/tmp/test', file_registry=registry)

    # Execute code that creates a file
    code = CodeBlock(code="with open('output.txt', 'w') as f: f.write('hello')", language='python')
    result = executor.execute_code_blocks([code])

    # File should be tracked
    assert 'output.txt' in [f.filename for f in registry._files_by_id.values()]
```

### 6.2 Integration Tests

```python
# tests/test_file_tracking_integration.py

def test_one_shot_outputs():
    """Test that one_shot returns proper outputs."""
    result = cmbagent.one_shot(
        task="Create a simple plot",
        agent='engineer',
        model='gpt-4o-mini',
        work_dir='/tmp/test_oneshot'
    )

    assert 'outputs' in result
    assert result['outputs'] is not None
    assert 'primary_outputs' in result['outputs']
    assert 'plots' in result['outputs']

def test_planning_and_control_outputs():
    """Test that planning_and_control tracks all phases."""
    result = cmbagent.planning_and_control(
        task="Analyze data and create report",
        model='gpt-4o-mini',
        work_dir='/tmp/test_pac'
    )

    assert 'outputs' in result
    outputs = result['outputs']

    # Check plan was captured
    assert len(outputs['plans']) > 0
    assert any('final_plan' in p['filename'] for p in outputs['plans'])

    # Check per-step breakdown
    assert 'outputs_by_step' in outputs
```

---

## Part 7: Risks and Mitigations Summary

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Files missed during rapid creation | Medium | High | Final scan + deduplication |
| Performance degradation | Low | Medium | Optional watchdog, async operations |
| Database overload | Low | Medium | Batch writes, transactions |
| Memory issues with large files | Low | Low | Stream hashing, size limits |
| Breaking existing workflows | Medium | High | Backward-compatible API, feature flags |
| Complex debugging | Medium | Medium | Comprehensive logging, manifest files |

---

## Part 8: Success Criteria

1. **All files captured:** 100% of generated files tracked in database
2. **Proper categorization:** Files correctly classified by type and priority
3. **Step association:** Files linked to correct workflow step
4. **Outputs returned:** `outputs` field in all workflow results
5. **UI display:** Files visible in DAGFilesView immediately
6. **Performance:** <5% overhead on workflow execution time
7. **Reliability:** No file tracking failures in 100 consecutive runs

---

## Appendix A: Database Schema Changes

```sql
-- Add new columns to files table
ALTER TABLE files ADD COLUMN workflow_phase VARCHAR(50);
ALTER TABLE files ADD COLUMN is_final_output BOOLEAN DEFAULT FALSE;
ALTER TABLE files ADD COLUMN generation_source VARCHAR(50);
ALTER TABLE files ADD COLUMN content_hash VARCHAR(64);
ALTER TABLE files ADD COLUMN generating_code_hash VARCHAR(64);

-- Add index for fast lookups
CREATE INDEX idx_files_phase ON files(run_id, workflow_phase);
CREATE INDEX idx_files_final_output ON files(run_id, is_final_output);
```

## Appendix B: New WebSocket Events

```typescript
// New event types
interface FileCreatedEvent {
  event_type: 'file_created';
  data: {
    file_id: string;
    file_path: string;
    filename: string;
    category: string;
    priority: string;
    size_bytes: number;
    phase: string;
    step_number?: number;
    is_final_output: boolean;
  };
}

interface OutputsCollectedEvent {
  event_type: 'outputs_collected';
  data: {
    run_id: string;
    total_files: number;
    primary_outputs: number;
    manifest_path: string;
  };
}
```

## Appendix C: Configuration Options

```python
# cmbagent/config.py

FILE_TRACKING_CONFIG = {
    # Enable/disable real-time watching (can disable for performance)
    'enable_file_watcher': True,

    # Maximum file size to hash (skip larger files)
    'max_hash_size_bytes': 100 * 1024 * 1024,  # 100MB

    # Batch size for database writes
    'db_batch_size': 50,

    # Debounce time for file events (seconds)
    'event_debounce_seconds': 0.5,

    # Directories to always scan (in addition to watchdog)
    'always_scan_dirs': ['data', 'codebase', 'planning', 'control'],

    # File patterns to ignore
    'ignore_patterns': ['.pyc', '.pyo', '__pycache__', '.git', '.tmp'],

    # Maximum files to track per run (safety limit)
    'max_files_per_run': 10000,
}
```
