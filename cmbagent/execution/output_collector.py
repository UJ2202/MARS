"""
Output Collector - Aggregates and organizes workflow outputs.

This module collects all outputs from a workflow execution and
organizes them for presentation to the user.
"""

import os
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from cmbagent.execution.file_registry import FileRegistry, TrackedFile

logger = logging.getLogger(__name__)


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
    run_id: str
    total_files: int
    total_size_bytes: int
    work_dir: str
    collected_at: str

    # Per-step breakdown (for planning_and_control)
    outputs_by_step: Dict[int, List[Dict[str, Any]]]

    # Per-phase breakdown
    outputs_by_phase: Dict[str, List[Dict[str, Any]]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def empty(cls, run_id: str, work_dir: str) -> 'WorkflowOutputs':
        """Create an empty WorkflowOutputs instance."""
        return cls(
            primary_outputs=[],
            plans=[],
            code_files=[],
            data_files=[],
            plots=[],
            reports=[],
            run_id=run_id,
            total_files=0,
            total_size_bytes=0,
            work_dir=work_dir,
            collected_at=datetime.now(timezone.utc).isoformat(),
            outputs_by_step={},
            outputs_by_phase={}
        )


class OutputCollector:
    """
    Collects and organizes final outputs at workflow completion.

    Responsibilities:
    1. Query FileRegistry for all tracked files
    2. Organize into categories
    3. Generate manifest file
    4. Return structured outputs
    """

    def __init__(
        self,
        file_registry: 'FileRegistry',
        work_dir: str,
        run_id: str = None
    ):
        """
        Initialize the OutputCollector.

        Args:
            file_registry: FileRegistry instance with tracked files
            work_dir: Working directory for the workflow
            run_id: Workflow run ID
        """
        self.file_registry = file_registry
        self.work_dir = Path(work_dir)
        self.run_id = run_id or (file_registry.run_id if file_registry else "unknown")

    def collect(self, write_manifest: bool = True) -> WorkflowOutputs:
        """
        Collect all outputs from the workflow.

        Called at workflow completion before returning to user.

        Args:
            write_manifest: Whether to write outputs_manifest.json

        Returns:
            WorkflowOutputs with all collected outputs
        """
        if not self.file_registry:
            logger.warning("No FileRegistry available, returning empty outputs")
            return WorkflowOutputs.empty(self.run_id, str(self.work_dir))

        # First, do a final scan to catch any missed files
        new_files = self.file_registry.scan_work_directory()
        logger.info(f"Final scan found {new_files} additional files")

        # Get organized outputs from registry
        organized = self.file_registry.get_final_outputs()
        all_files = self.file_registry.get_all_files()

        # Convert TrackedFile to dict
        def to_dict(tracked_file: 'TrackedFile') -> Dict[str, Any]:
            return {
                'id': tracked_file.id,
                'path': tracked_file.relative_path,
                'filename': tracked_file.filename,
                'category': tracked_file.category.value,
                'priority': tracked_file.priority.value,
                'size_bytes': tracked_file.size_bytes,
                'phase': tracked_file.phase,
                'step_number': tracked_file.step_number,
                'is_final_output': tracked_file.is_final_output,
                'content_hash': tracked_file.content_hash,
                'generating_agent': tracked_file.generating_agent
            }

        # Build outputs by step
        outputs_by_step: Dict[int, List[Dict[str, Any]]] = {}
        for f in all_files:
            if f.step_number is not None:
                outputs_by_step.setdefault(f.step_number, []).append(to_dict(f))

        # Build outputs by phase
        outputs_by_phase: Dict[str, List[Dict[str, Any]]] = {}
        for f in all_files:
            outputs_by_phase.setdefault(f.phase, []).append(to_dict(f))

        # Calculate totals
        total_size = sum(f.size_bytes for f in all_files)

        # Get plans from all files
        plans = [to_dict(f) for f in all_files if f.category.value == 'plan']

        # Create WorkflowOutputs
        outputs = WorkflowOutputs(
            primary_outputs=[to_dict(f) for f in organized['primary']],
            plans=plans,
            code_files=[to_dict(f) for f in organized['code']],
            data_files=[to_dict(f) for f in organized['data']],
            plots=[to_dict(f) for f in organized['plots']],
            reports=[to_dict(f) for f in organized['reports']],
            run_id=self.run_id,
            total_files=len(all_files),
            total_size_bytes=total_size,
            work_dir=str(self.work_dir),
            collected_at=datetime.now(timezone.utc).isoformat(),
            outputs_by_step=outputs_by_step,
            outputs_by_phase=outputs_by_phase
        )

        # Write manifest file
        if write_manifest:
            self._write_manifest(outputs)

        logger.info(
            f"Collected {outputs.total_files} files "
            f"({outputs.total_size_bytes} bytes) across "
            f"{len(outputs_by_phase)} phases"
        )

        return outputs

    def _write_manifest(self, outputs: WorkflowOutputs):
        """Write outputs manifest to work directory."""
        manifest_path = self.work_dir / 'outputs_manifest.json'
        try:
            with open(manifest_path, 'w') as f:
                f.write(outputs.to_json())
            logger.info(f"Wrote outputs manifest to {manifest_path}")
        except Exception as e:
            logger.error(f"Failed to write manifest: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of outputs without full file details."""
        if not self.file_registry:
            return {'total_files': 0, 'error': 'No FileRegistry available'}

        stats = self.file_registry.get_statistics()
        return {
            'run_id': self.run_id,
            'work_dir': str(self.work_dir),
            **stats
        }


class WorkflowOutputManager:
    """
    High-level manager for workflow file tracking and output collection.

    This class provides a simple interface for initializing file tracking
    at workflow start and collecting outputs at workflow end.
    """

    def __init__(
        self,
        work_dir: str,
        run_id: str,
        db_session=None,
        websocket_callback=None
    ):
        """
        Initialize the output manager.

        Args:
            work_dir: Working directory for the workflow
            run_id: Unique workflow run identifier
            db_session: Optional database session
            websocket_callback: Optional WebSocket callback
        """
        from cmbagent.execution.file_registry import FileRegistry, set_global_registry

        self.work_dir = Path(work_dir)
        self.run_id = run_id

        # Create work directory if needed
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Initialize FileRegistry
        self.file_registry = FileRegistry(
            work_dir=str(self.work_dir),
            run_id=run_id,
            db_session=db_session,
            websocket_callback=websocket_callback
        )

        # Set as global registry for this run
        set_global_registry(self.file_registry)

        # Initialize OutputCollector
        self.output_collector = OutputCollector(
            file_registry=self.file_registry,
            work_dir=str(self.work_dir),
            run_id=run_id
        )

        logger.info(f"WorkflowOutputManager initialized for run {run_id}")

    def set_phase(self, phase: str):
        """Set the current workflow phase."""
        self.file_registry.set_context(phase=phase)

    def set_step(self, step_number: int):
        """Set the current step number."""
        self.file_registry.set_context(step=step_number)

    def set_node(self, node_id: str):
        """Set the current node ID."""
        self.file_registry.set_context(node_id=node_id)

    def set_agent(self, agent_name: str):
        """Set the current agent name."""
        self.file_registry.set_context(agent=agent_name)

    def register_file(self, path: str, **kwargs):
        """Register a file with the registry."""
        return self.file_registry.register_file(path, **kwargs)

    def finalize(self, write_manifest: bool = True) -> WorkflowOutputs:
        """
        Finalize file tracking and collect all outputs.

        Should be called at workflow completion.

        Args:
            write_manifest: Whether to write the manifest file

        Returns:
            WorkflowOutputs with all collected outputs
        """
        from cmbagent.execution.file_registry import set_global_registry

        # Collect outputs
        outputs = self.output_collector.collect(write_manifest=write_manifest)

        # Clear global registry
        set_global_registry(None)

        return outputs

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - finalize on exit."""
        self.finalize()
        return False


def create_output_manager(
    work_dir: str,
    run_id: str = None,
    db_session=None,
    websocket_callback=None
) -> WorkflowOutputManager:
    """
    Factory function to create a WorkflowOutputManager.

    Args:
        work_dir: Working directory
        run_id: Optional run ID (generated if not provided)
        db_session: Optional database session
        websocket_callback: Optional WebSocket callback

    Returns:
        WorkflowOutputManager instance
    """
    import uuid
    if run_id is None:
        run_id = str(uuid.uuid4())

    return WorkflowOutputManager(
        work_dir=work_dir,
        run_id=run_id,
        db_session=db_session,
        websocket_callback=websocket_callback
    )
