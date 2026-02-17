"""
Database base configuration and connection management.
"""

import os
import logging
from pathlib import Path
from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

# Create declarative base
Base = declarative_base()

# Database URL from environment or default to SQLite
def get_database_url():
    """Get database URL from environment or use default SQLite."""
    default_db_dir = Path.home() / ".cmbagent"
    default_db_dir.mkdir(parents=True, exist_ok=True)
    default_url = f"sqlite:///{default_db_dir}/cmbagent.db"
    return os.getenv("CMBAGENT_DATABASE_URL", default_url)


# Global engine and session factory
_engine = None
_SessionFactory = None


def get_engine():
    """Get or create the global database engine."""
    global _engine
    if _engine is None:
        database_url = get_database_url()

        if database_url.startswith("sqlite"):
            # SQLite-specific configuration
            _engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False,  # Set to True for SQL debugging
            )

            # Enable WAL mode for better concurrency
            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        else:
            # PostgreSQL or other database
            _engine = create_engine(
                database_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False,
            )

    return _engine


def get_session_factory():
    """Get or create the global session factory."""
    global _SessionFactory
    if _SessionFactory is None:
        engine = get_engine()
        _SessionFactory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionFactory


def get_db_session():
    """Create a new database session."""
    SessionFactory = get_session_factory()
    return SessionFactory()


def _apply_schema_migrations(engine):
    """Apply missing column migrations for existing tables.

    create_all() only creates new tables; it does not alter existing ones.
    This function adds columns that were introduced after the initial schema.
    """
    insp = inspect(engine)

    # Map of table -> list of (column_name, sql_type) to ensure exist
    migrations = {
        "files": [
            ("session_id", "VARCHAR(36)"),
        ],
    }

    with engine.begin() as conn:
        for table, columns in migrations.items():
            if not insp.has_table(table):
                continue
            existing = {col["name"] for col in insp.get_columns(table)}
            for col_name, col_type in columns:
                if col_name not in existing:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                    ))
                    logger.info("Added column %s.%s", table, col_name)


def init_database():
    """Initialize database by creating all tables."""
    from cmbagent.database.models import (
        Session, SessionState, Project, WorkflowRun, WorkflowStep,
        DAGNode, DAGEdge, Checkpoint, Message,
        CostRecord, ApprovalRequest, ActiveConnection, Branch,
        RacingGroup, WorkflowMetric, File, StateHistory,
        ExecutionEvent,
    )

    engine = get_engine()
    Base.metadata.create_all(engine)

    # Add columns that were introduced after initial table creation
    _apply_schema_migrations(engine)

    return engine
