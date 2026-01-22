"""
Dual-write persistence manager.

Writes to both database (primary) and pickle files (secondary/backup).
"""

import os
import pickle
import json
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from cmbagent.database.repository import (
    WorkflowRepository,
    CheckpointRepository,
)


class DualPersistenceManager:
    """Manages dual persistence to database and pickle files."""

    def __init__(self, db_session: DBSession, session_id: str, work_dir: str):
        """
        Initialize persistence manager.

        Args:
            db_session: SQLAlchemy database session
            session_id: Session ID for isolation
            work_dir: Working directory for pickle files
        """
        self.db = db_session
        self.session_id = session_id
        self.work_dir = Path(work_dir)
        self.workflow_repo = WorkflowRepository(db_session, session_id)
        self.checkpoint_repo = CheckpointRepository(db_session, session_id)

        # Ensure context directory exists
        self.context_dir = self.work_dir / "context"
        self.context_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(
        self,
        run_id: str,
        context: Dict[str, Any],
        checkpoint_type: str = "step_complete",
        step_id: Optional[str] = None,
    ) -> str:
        """
        Save checkpoint to both database and pickle file.

        Args:
            run_id: Workflow run ID
            context: Context dictionary to save
            checkpoint_type: Type of checkpoint
            step_id: Optional step ID

        Returns:
            Checkpoint ID
        """
        # 1. Save to pickle file first (secondary/backup)
        checkpoint_id = self._generate_checkpoint_id()
        pickle_path = self.context_dir / f"context_{checkpoint_id}.pkl"

        with open(pickle_path, 'wb') as f:
            pickle.dump(context, f)

        # 2. Save to database (primary)
        try:
            checkpoint = self.checkpoint_repo.create_checkpoint(
                run_id=run_id,
                step_id=step_id,
                checkpoint_type=checkpoint_type,
                context_snapshot=self._serialize_context_for_db(context),
                pickle_file_path=str(pickle_path),
            )
            return checkpoint.id
        except Exception as e:
            # If database save fails, we still have the pickle file
            print(f"Warning: Failed to save checkpoint to database: {e}")
            # Create a fallback record in a JSON file
            fallback_path = self.context_dir / f"checkpoint_{checkpoint_id}.json"
            with open(fallback_path, 'w') as f:
                json.dump({
                    "checkpoint_id": checkpoint_id,
                    "run_id": run_id,
                    "step_id": step_id,
                    "checkpoint_type": checkpoint_type,
                    "pickle_file_path": str(pickle_path),
                    "created_at": datetime.utcnow().isoformat(),
                }, f, indent=2)
            return checkpoint_id

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint from database or pickle file.

        Args:
            checkpoint_id: Checkpoint ID to load

        Returns:
            Context dictionary or None if not found
        """
        # Try to load from database first
        checkpoint = self.checkpoint_repo.get_checkpoint(checkpoint_id)

        if checkpoint:
            # If pickle file exists, prefer it (full context)
            if checkpoint.pickle_file_path and os.path.exists(checkpoint.pickle_file_path):
                try:
                    with open(checkpoint.pickle_file_path, 'rb') as f:
                        return pickle.load(f)
                except Exception as e:
                    print(f"Warning: Failed to load from pickle {checkpoint.pickle_file_path}: {e}")

            # Fallback to database context_snapshot
            if checkpoint.context_snapshot:
                return self._deserialize_context_from_db(checkpoint.context_snapshot)

        # Final fallback: try to find pickle file directly
        pickle_path = self.context_dir / f"context_{checkpoint_id}.pkl"
        if pickle_path.exists():
            try:
                with open(pickle_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"Warning: Failed to load from fallback pickle {pickle_path}: {e}")

        return None

    def save_context_step(
        self,
        run_id: str,
        step_number: int,
        context: Dict[str, Any],
        step_id: Optional[str] = None,
    ) -> str:
        """
        Save context for a specific step (legacy compatibility).

        Args:
            run_id: Workflow run ID
            step_number: Step number
            context: Context to save
            step_id: Optional step ID

        Returns:
            Checkpoint ID
        """
        # Save with step-specific filename for backward compatibility
        pickle_path = self.context_dir / f"context_step_{step_number}.pkl"

        with open(pickle_path, 'wb') as f:
            pickle.dump(context, f)

        # Also save to database
        try:
            checkpoint = self.checkpoint_repo.create_checkpoint(
                run_id=run_id,
                step_id=step_id,
                checkpoint_type="step_complete",
                context_snapshot=self._serialize_context_for_db(context),
                pickle_file_path=str(pickle_path),
                meta={"step_number": step_number},
            )
            return checkpoint.id
        except Exception as e:
            print(f"Warning: Failed to save step context to database: {e}")
            # Pickle file is still saved
            return f"step_{step_number}"

    def load_context_step(self, step_number: int) -> Optional[Dict[str, Any]]:
        """
        Load context for a specific step (legacy compatibility).

        Args:
            step_number: Step number to load

        Returns:
            Context dictionary or None
        """
        pickle_path = self.context_dir / f"context_step_{step_number}.pkl"

        if pickle_path.exists():
            try:
                with open(pickle_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"Warning: Failed to load step {step_number} context: {e}")

        return None

    def _generate_checkpoint_id(self) -> str:
        """Generate a unique checkpoint ID."""
        import uuid
        return str(uuid.uuid4())

    def _serialize_context_for_db(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize context for database storage.

        Only stores JSON-serializable subset of context.
        Full context is in pickle file.

        Args:
            context: Full context dictionary

        Returns:
            JSON-serializable subset
        """
        # Extract only JSON-serializable fields
        serializable = {}

        for key, value in context.items():
            try:
                # Test if value is JSON serializable
                json.dumps(value)
                serializable[key] = value
            except (TypeError, ValueError):
                # Skip non-serializable values
                # Store type information instead
                serializable[f"__{key}__type"] = str(type(value).__name__)

        return serializable

    def _deserialize_context_from_db(self, context_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deserialize context from database.

        Note: This is a partial context. Full context should be loaded from pickle.

        Args:
            context_snapshot: JSON data from database

        Returns:
            Partial context dictionary
        """
        # Filter out type markers
        context = {}
        for key, value in context_snapshot.items():
            if not key.startswith("__") or not key.endswith("__type"):
                context[key] = value

        return context

    def cleanup_old_checkpoints(self, run_id: str, keep_last: int = 10):
        """
        Clean up old checkpoints, keeping only the most recent.

        Args:
            run_id: Workflow run ID
            keep_last: Number of checkpoints to keep
        """
        checkpoints = self.checkpoint_repo.list_checkpoints(run_id)

        if len(checkpoints) > keep_last:
            # Sort by creation time (newest first)
            checkpoints.sort(key=lambda x: x.created_at, reverse=True)

            # Delete old checkpoints
            for checkpoint in checkpoints[keep_last:]:
                # Delete pickle file if exists
                if checkpoint.pickle_file_path and os.path.exists(checkpoint.pickle_file_path):
                    try:
                        os.remove(checkpoint.pickle_file_path)
                    except Exception as e:
                        print(f"Warning: Failed to delete pickle {checkpoint.pickle_file_path}: {e}")

                # Delete database record
                try:
                    self.db.delete(checkpoint)
                except Exception as e:
                    print(f"Warning: Failed to delete checkpoint {checkpoint.id}: {e}")

            self.db.commit()
