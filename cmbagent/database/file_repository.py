"""
FileRepository - Consistent file CRUD operations with deduplication.

Single source of truth for file tracking. Replaces raw DB writes in
DAGTracker and the in-memory FileRegistry. All file registration goes
through this repository.
"""

import hashlib
import os
import logging
from typing import List, Optional

from cmbagent.database.models import File

logger = logging.getLogger(__name__)


class FileRepository:
    """Consistent file CRUD operations with deduplication."""

    def __init__(self, db_session, session_id: str):
        self.db_session = db_session
        self.session_id = session_id

    def register_file(
        self,
        run_id: str,
        file_path: str,
        file_type: str,
        node_id: str = None,
        step_id: str = None,
        event_id: str = None,
        workflow_phase: str = None,
        generating_agent: str = None,
        is_final_output: bool = False,
    ) -> Optional[File]:
        """Register a file with deduplication by (run_id, file_path).

        If the file already exists for this run, updates metadata fields
        that were previously null. Returns the existing or new File record.
        """
        existing = self.db_session.query(File).filter(
            File.run_id == run_id,
            File.file_path == file_path,
        ).first()

        if existing:
            # Update metadata if changed
            if node_id and not existing.node_id:
                existing.node_id = node_id
            if step_id and not existing.step_id:
                existing.step_id = step_id
            if event_id and not existing.event_id:
                existing.event_id = event_id
            if workflow_phase and existing.workflow_phase != workflow_phase:
                existing.workflow_phase = workflow_phase
            if generating_agent and not existing.generating_agent:
                existing.generating_agent = generating_agent
            return existing

        # Compute content hash and size
        content_hash = None
        size_bytes = None
        if os.path.exists(file_path):
            try:
                size_bytes = os.path.getsize(file_path)
            except OSError:
                size_bytes = 0
            if size_bytes and size_bytes < 50 * 1024 * 1024:  # Hash files < 50 MB
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

    def list_files(
        self,
        run_id: str,
        file_type: str = None,
        phase: str = None,
    ) -> List[File]:
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
    def _compute_hash(file_path: str) -> Optional[str]:
        """Compute SHA-256 hash of file contents."""
        try:
            h = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    @staticmethod
    def _classify_priority(file_type: str, is_final_output: bool) -> str:
        if is_final_output:
            return "primary"
        if file_type in ("plot", "data", "code", "plan"):
            return "primary"
        elif file_type in ("report", "chat"):
            return "secondary"
        return "internal"
