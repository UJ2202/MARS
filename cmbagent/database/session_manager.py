"""
Session lifecycle management for CMBAgent.
"""

import uuid
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from cmbagent.database.base import get_db_session
from cmbagent.database.repository import SessionRepository


class SessionManager:
    """Manages user sessions and session lifecycle."""

    def __init__(self, db_session: Optional[DBSession] = None):
        """
        Initialize session manager.

        Args:
            db_session: Optional database session (creates new one if not provided)
        """
        self.db = db_session or get_db_session()
        self.repo = SessionRepository(self.db, session_id="system")  # System session for creating sessions

    def create_session(
        self,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Create a new session.

        Args:
            name: Optional session name
            user_id: Optional user ID

        Returns:
            Session ID
        """
        if name is None:
            name = f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        session = self.repo.create_session(
            name=name,
            user_id=user_id,
            status="active",
        )

        return session.id

    def get_or_create_default_session(self) -> str:
        """
        Get or create the default session.
        
        This method ensures a consistent default session is used across
        the application by looking for a session with a specific name/ID.

        Returns:
            Session ID
        """
        # Use a fixed session ID for the default session
        DEFAULT_SESSION_ID = "default_session"
        
        # Try to find the default session by ID
        default_session = self.repo.get_session(DEFAULT_SESSION_ID)
        
        if default_session:
            # Update activity and return existing default session
            self.repo.update_last_active(DEFAULT_SESSION_ID)
            return DEFAULT_SESSION_ID
        
        # Create the default session with fixed ID
        # Note: We need to create it directly with the specific ID
        from cmbagent.database.models import Session
        session = Session(
            id=DEFAULT_SESSION_ID,
            name="Default Session",
            status="active",
            created_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc)
        )
        self.db.add(session)
        self.db.commit()
        
        return DEFAULT_SESSION_ID

    def get_session(self, session_id: str):
        """
        Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session object or None
        """
        return self.repo.get_session(session_id)

    def update_session_activity(self, session_id: str):
        """
        Update session's last active timestamp.

        Args:
            session_id: Session ID
        """
        self.repo.update_last_active(session_id)

    def close(self):
        """Close database connection."""
        if self.db:
            self.db.close()
