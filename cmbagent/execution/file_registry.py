"""
File Registry - Central tracking system for all workflow files.

DEPRECATED: Use cmbagent.database.file_repository.FileRepository for DB-backed
file tracking (Stage 4). This in-memory registry is kept for backward
compatibility with output_collector and tracked_code_executor until Stage 6
(Workflow Migration) consolidates all consumers.

This module provides the core file management system for CMBAgent,
enabling proper tracking, categorization, and aggregation of all
generated artifacts across different execution modes.
"""

import os
import uuid
import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import logging

logger = logging.getLogger(__name__)


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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'path': self.path,
            'relative_path': self.relative_path,
            'filename': self.filename,
            'category': self.category.value,
            'priority': self.priority.value,
            'size_bytes': self.size_bytes,
            'content_hash': self.content_hash,
            'run_id': self.run_id,
            'phase': self.phase,
            'step_number': self.step_number,
            'node_id': self.node_id,
            'generating_agent': self.generating_agent,
            'generating_code_hash': self.generating_code_hash,
            'created_at': self.created_at,
            'is_final_output': self.is_final_output,
            'is_user_facing': self.is_user_facing
        }


# Global registry instance for the current run
_global_registry: Optional['FileRegistry'] = None
_registry_lock = threading.Lock()


def get_global_registry() -> Optional['FileRegistry']:
    """Get the global FileRegistry instance for the current run."""
    return _global_registry


def set_global_registry(registry: Optional['FileRegistry']) -> None:
    """Set the global FileRegistry instance."""
    global _global_registry
    with _registry_lock:
        _global_registry = registry


class FileRegistry:
    """
    Central registry for all workflow files.

    Design principles:
    1. Single source of truth for file tracking
    2. Fast in-memory lookups with optional database persistence
    3. Deterministic file classification
    4. Thread-safe for parallel execution
    """

    # Directories that should be scanned for files
    TRACKED_DIRECTORIES = [
        "data", "codebase", "outputs", "chats", "cost", "time",
        "planning", "control", "context", "docs", "summaries", "runs"
    ]

    # File extension to category mapping
    CODE_EXTENSIONS = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rs', '.rb', '.sh', '.bash'}
    PLOT_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.pdf', '.eps', '.bmp', '.tiff'}
    DATA_EXTENSIONS = {'.csv', '.json', '.pkl', '.pickle', '.npz', '.npy', '.parquet', '.yaml', '.yml', '.h5', '.hdf5', '.fits'}
    REPORT_EXTENSIONS = {'.md', '.rst', '.txt', '.html'}
    LOG_EXTENSIONS = {'.log'}

    def __init__(
        self,
        work_dir: str,
        run_id: str,
        db_session=None,
        websocket_callback=None
    ):
        """
        Initialize the FileRegistry.

        Args:
            work_dir: Working directory for the workflow
            run_id: Unique identifier for the workflow run
            db_session: Optional SQLAlchemy session for persistence
            websocket_callback: Optional callback for WebSocket notifications
        """
        self.work_dir = Path(work_dir)
        self.run_id = run_id
        self.db = db_session
        self.websocket_callback = websocket_callback

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

        logger.info(f"FileRegistry initialized for run {run_id} in {work_dir}")

    def set_context(
        self,
        phase: str = None,
        step: int = None,
        node_id: str = None,
        agent: str = None
    ):
        """Update current execution context for file association."""
        with self._lock:
            if phase is not None:
                self._current_phase = phase
            if step is not None:
                self._current_step = step
            if node_id is not None:
                self._current_node = node_id
            if agent is not None:
                self._current_agent = agent

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
                logger.debug(f"File does not exist: {abs_path}")
                return None

            # Check for duplicates by path
            rel_path = os.path.relpath(abs_path, self.work_dir)
            if rel_path in self._files_by_path:
                return self._files_by_path[rel_path]

            # Get file size
            try:
                size_bytes = os.path.getsize(abs_path)
            except OSError:
                size_bytes = 0

            # Compute hash for deduplication (skip large files)
            content_hash = self._compute_hash(abs_path, size_bytes)

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
                size_bytes=size_bytes,
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

            # Persist to database if available
            if self.db:
                self._persist_to_db(tracked)

            # Emit WebSocket event
            if self.websocket_callback:
                self._emit_file_created(tracked)

            logger.debug(f"Registered file: {rel_path} ({category.value}, {priority.value})")
            return tracked

    def _normalize_path(self, path: str) -> str:
        """Normalize path to absolute."""
        path = Path(path)
        if not path.is_absolute():
            path = self.work_dir / path
        return str(path.resolve())

    def _compute_hash(self, path: str, size_bytes: int, max_size: int = 100 * 1024 * 1024) -> str:
        """
        Compute content hash for deduplication.

        Args:
            path: File path
            size_bytes: File size
            max_size: Skip hashing files larger than this (100MB default)
        """
        if size_bytes > max_size:
            # For large files, use size + mtime as pseudo-hash
            try:
                mtime = os.path.getmtime(path)
                return f"large:{size_bytes}:{mtime}"
            except OSError:
                return f"large:{size_bytes}:unknown"

        try:
            hash_md5 = hashlib.md5()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except (IOError, OSError) as e:
            logger.warning(f"Failed to hash file {path}: {e}")
            return f"error:{size_bytes}"

    def _classify_file(self, abs_path: str, rel_path: str) -> FileCategory:
        """
        Classify file based on path and extension.

        Classification rules (in order of precedence):
        1. Explicit filename patterns (final_plan.json -> PLAN)
        2. Directory location (codebase/ -> CODE)
        3. File extension (.png -> PLOT)
        """
        filename = os.path.basename(abs_path)
        ext = os.path.splitext(filename)[1].lower()

        # Rule 1: Explicit patterns
        if filename == 'final_plan.json' or filename.endswith('_plan.json'):
            return FileCategory.PLAN
        if filename.startswith('timing_report') or filename.startswith('cost_report'):
            return FileCategory.REPORT
        if filename == 'outputs_manifest.json':
            return FileCategory.REPORT

        # Rule 2: Directory location
        parts = rel_path.lower().split(os.sep)
        if 'codebase' in parts:
            return FileCategory.CODE
        if 'chats' in parts:
            return FileCategory.CHAT
        if 'context' in parts:
            return FileCategory.CONTEXT
        if 'time' in parts or 'cost' in parts:
            return FileCategory.REPORT
        if 'planning' in parts and filename.endswith('.json'):
            return FileCategory.PLAN

        # Rule 3: Extension
        if ext in self.CODE_EXTENSIONS:
            return FileCategory.CODE
        if ext in self.PLOT_EXTENSIONS:
            return FileCategory.PLOT
        if ext in self.DATA_EXTENSIONS:
            return FileCategory.DATA
        if ext in self.REPORT_EXTENSIONS:
            return FileCategory.REPORT
        if ext in self.LOG_EXTENSIONS:
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
            rel_lower = rel_path.lower()
            if 'context' not in rel_lower and 'temp' not in rel_lower and '__pycache__' not in rel_lower:
                return OutputPriority.PRIMARY

        if category == FileCategory.PLAN:
            return OutputPriority.PRIMARY

        # Secondary outputs
        if category in [FileCategory.REPORT, FileCategory.CHAT]:
            return OutputPriority.SECONDARY

        # Internal
        return OutputPriority.INTERNAL

    def _persist_to_db(self, tracked: TrackedFile):
        """Persist tracked file to database."""
        try:
            from cmbagent.database.models import File

            file_record = File(
                id=tracked.id,
                run_id=tracked.run_id,
                step_id=None,  # Will be set if we have step context
                node_id=tracked.node_id,
                file_path=tracked.relative_path,
                file_type=tracked.category.value,
                size_bytes=tracked.size_bytes,
                workflow_phase=tracked.phase,
                is_final_output=tracked.is_final_output,
                content_hash=tracked.content_hash,
                generating_agent=tracked.generating_agent,
                generating_code_hash=tracked.generating_code_hash,
                priority=tracked.priority.value,
                meta={
                    'created_at': tracked.created_at,
                    'is_user_facing': tracked.is_user_facing
                }
            )
            self.db.add(file_record)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to persist file to DB: {e}")
            if self.db:
                self.db.rollback()

    def _emit_file_created(self, tracked: TrackedFile):
        """Emit WebSocket event for file creation."""
        try:
            self.websocket_callback({
                'event_type': 'file_created',
                'data': {
                    'file_id': tracked.id,
                    'file_path': tracked.relative_path,
                    'filename': tracked.filename,
                    'category': tracked.category.value,
                    'priority': tracked.priority.value,
                    'size_bytes': tracked.size_bytes,
                    'phase': tracked.phase,
                    'step_number': tracked.step_number,
                    'is_final_output': tracked.is_final_output
                }
            })
        except Exception as e:
            logger.warning(f"Failed to emit WebSocket event: {e}")

    def get_file_by_id(self, file_id: str) -> Optional[TrackedFile]:
        """Get a tracked file by its ID."""
        with self._lock:
            return self._files_by_id.get(file_id)

    def get_file_by_path(self, path: str) -> Optional[TrackedFile]:
        """Get a tracked file by its relative path."""
        with self._lock:
            rel_path = os.path.relpath(self._normalize_path(path), self.work_dir)
            return self._files_by_path.get(rel_path)

    def get_files_by_category(self, category: FileCategory) -> List[TrackedFile]:
        """Get all files of a specific category."""
        with self._lock:
            file_ids = self._files_by_category.get(category, [])
            return [self._files_by_id[fid] for fid in file_ids if fid in self._files_by_id]

    def get_files_by_phase(self, phase: str) -> List[TrackedFile]:
        """Get all files from a specific workflow phase."""
        with self._lock:
            file_ids = self._files_by_phase.get(phase, [])
            return [self._files_by_id[fid] for fid in file_ids if fid in self._files_by_id]

    def get_files_by_step(self, step_number: int) -> List[TrackedFile]:
        """Get all outputs generated during a specific step."""
        with self._lock:
            file_ids = self._files_by_step.get(step_number, [])
            return [self._files_by_id[fid] for fid in file_ids if fid in self._files_by_id]

    def get_all_files(self) -> List[TrackedFile]:
        """Get all tracked files."""
        with self._lock:
            return list(self._files_by_id.values())

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

    def scan_work_directory(self, force_rescan: bool = False) -> int:
        """
        Full scan of work directory for any untracked files.
        Called at workflow end to catch any missed files.

        Args:
            force_rescan: If True, re-scan even already tracked files

        Returns:
            Number of newly registered files
        """
        count = 0

        if not self.work_dir.exists():
            logger.warning(f"Work directory does not exist: {self.work_dir}")
            return 0

        # Scan all tracked directories
        for dir_name in self.TRACKED_DIRECTORIES:
            dir_path = self.work_dir / dir_name
            if not dir_path.exists():
                continue

            for root, dirs, files in os.walk(dir_path):
                # Skip hidden and temp directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']

                for filename in files:
                    if filename.startswith('.'):
                        continue

                    abs_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(abs_path, self.work_dir)

                    if not force_rescan and rel_path in self._files_by_path:
                        continue

                    if self.register_file(abs_path):
                        count += 1

        # Also scan root level files (like outputs_manifest.json)
        for item in self.work_dir.iterdir():
            if item.is_file() and not item.name.startswith('.'):
                rel_path = item.name
                if not force_rescan and rel_path in self._files_by_path:
                    continue
                if self.register_file(str(item)):
                    count += 1

        logger.info(f"Scanned work directory, found {count} new files")
        return count

    def get_statistics(self) -> Dict[str, Any]:
        """Get file tracking statistics."""
        with self._lock:
            total_size = sum(f.size_bytes for f in self._files_by_id.values())

            by_category = {cat.value: len(ids) for cat, ids in self._files_by_category.items()}
            by_priority = {
                'primary': len([f for f in self._files_by_id.values() if f.priority == OutputPriority.PRIMARY]),
                'secondary': len([f for f in self._files_by_id.values() if f.priority == OutputPriority.SECONDARY]),
                'internal': len([f for f in self._files_by_id.values() if f.priority == OutputPriority.INTERNAL])
            }
            by_phase = {phase: len(ids) for phase, ids in self._files_by_phase.items()}

            return {
                'total_files': len(self._files_by_id),
                'total_size_bytes': total_size,
                'by_category': by_category,
                'by_priority': by_priority,
                'by_phase': by_phase,
                'unique_hashes': len(self._seen_hashes)
            }

    def clear(self):
        """Clear all tracked files (for testing)."""
        with self._lock:
            self._files_by_id.clear()
            self._files_by_path.clear()
            for cat in FileCategory:
                self._files_by_category[cat] = []
            self._files_by_phase.clear()
            self._files_by_step.clear()
            self._seen_hashes.clear()
