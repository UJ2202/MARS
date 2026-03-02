"""
SQLAlchemy models for CMBAgent database schema.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, BigInteger, Text, Boolean,
    ForeignKey, Index, TIMESTAMP, Numeric, CheckConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from cmbagent.database.base import Base


# Helper function to generate UUIDs
def generate_uuid():
    return str(uuid.uuid4())


class Session(Base):
    """User session for isolating workflow data."""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_active_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    status = Column(String(50), nullable=False, default="active", index=True)  # active, archived, deleted
    meta = Column(JSON, nullable=True)
    resource_limits = Column(JSON, nullable=True)

    # Relationships
    session_states = relationship("SessionState", back_populates="session", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="session", cascade="all, delete-orphan")
    workflow_runs = relationship("WorkflowRun", back_populates="session", cascade="all, delete-orphan")
    workflow_steps = relationship("WorkflowStep", back_populates="session", cascade="all, delete-orphan")
    dag_nodes = relationship("DAGNode", back_populates="session", cascade="all, delete-orphan")
    cost_records = relationship("CostRecord", back_populates="session", cascade="all, delete-orphan")
    execution_events = relationship("ExecutionEvent", back_populates="session", cascade="all, delete-orphan")
    files = relationship("File", back_populates="session", cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="session")

    __table_args__ = (
        Index("idx_sessions_user_status", "user_id", "status"),
    )


class SessionState(Base):
    """Persistent session state for resumable workflows"""
    __tablename__ = "session_states"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    mode = Column(String(50), nullable=False)  # copilot, planning-control, hitl-interactive

    # Serialized state (JSON)
    conversation_history = Column(JSON, nullable=True)  # List of message dicts
    context_variables = Column(JSON, nullable=True)     # Key-value context
    plan_data = Column(JSON, nullable=True)             # Plan structure if applicable

    # Progress tracking
    current_phase = Column(String(50), nullable=True)   # planning, execution, review
    current_step = Column(Integer, nullable=True)       # Current step number

    # Lifecycle
    status = Column(String(20), default="active", index=True)  # active, suspended, completed, expired
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Optimistic locking
    version = Column(Integer, default=1)

    # Relationships
    session = relationship("Session", back_populates="session_states")

    # Indexes
    __table_args__ = (
        Index("idx_session_states_session_status", "session_id", "status"),
        Index("idx_session_states_mode", "mode"),
        Index("idx_session_states_updated", "updated_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "mode": self.mode,
            "conversation_history": self.conversation_history or [],
            "context_variables": self.context_variables or {},
            "plan_data": self.plan_data,
            "current_phase": self.current_phase,
            "current_step": self.current_step,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "version": self.version,
        }

    @classmethod
    def create_for_session(cls, session_id: str, mode: str, **kwargs):
        """Factory method to create new session state"""
        return cls(
            session_id=session_id,
            mode=mode,
            conversation_history=kwargs.get("conversation_history", []),
            context_variables=kwargs.get("context_variables", {}),
            plan_data=kwargs.get("plan_data"),
            current_phase=kwargs.get("current_phase", "init"),
            status="active",
        )


class Project(Base):
    """Project container for organizing workflow runs."""
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    meta = Column(JSON, nullable=True)

    # Relationships
    session = relationship("Session", back_populates="projects")
    workflow_runs = relationship("WorkflowRun", back_populates="project", cascade="all, delete-orphan")


class WorkflowRun(Base):
    """A single workflow execution (one_shot, planning_control, etc)."""
    __tablename__ = "workflow_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    mode = Column(String(50), nullable=False, index=True)  # one_shot, planning_control, deep_research
    agent = Column(String(100), nullable=False, index=True)  # engineer, researcher, etc.
    model = Column(String(100), nullable=False)  # gpt-4, claude-3, etc.
    status = Column(String(50), nullable=False, default="draft", index=True)
    # Status values: draft, planning, executing, paused, waiting_approval, completed, failed
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    last_heartbeat_at = Column(TIMESTAMP, nullable=True)
    checkpoint_frequency_minutes = Column(Integer, nullable=False, default=10)
    task_description = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)

    # Branch fields
    branch_parent_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    is_branch = Column(Boolean, nullable=False, default=False)
    branch_depth = Column(Integer, nullable=False, default=0)

    # Task hierarchy fields (nullable - only set for task child workflows)
    parent_run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    stage_number = Column(Integer, nullable=True)  # 1-4 for task stages
    stage_name = Column(String(100), nullable=True)  # e.g., "idea_generation"

    # Relationships
    session = relationship("Session", back_populates="workflow_runs")
    project = relationship("Project", back_populates="workflow_runs")
    workflow_steps = relationship("WorkflowStep", back_populates="run", cascade="all, delete-orphan")
    dag_nodes = relationship("DAGNode", back_populates="run", cascade="all, delete-orphan")
    checkpoints = relationship("Checkpoint", back_populates="run", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="run", cascade="all, delete-orphan")
    cost_records = relationship("CostRecord", back_populates="run", cascade="all, delete-orphan", foreign_keys="CostRecord.run_id")
    approval_requests = relationship("ApprovalRequest", back_populates="run", cascade="all, delete-orphan")
    parent_branches = relationship("Branch", foreign_keys="Branch.parent_run_id", back_populates="parent_run")
    child_branches = relationship("Branch", foreign_keys="Branch.child_run_id", back_populates="child_run")
    workflow_metrics = relationship("WorkflowMetric", back_populates="run", cascade="all, delete-orphan")
    files = relationship("File", back_populates="run", cascade="all, delete-orphan")
    execution_events = relationship("ExecutionEvent", back_populates="run", cascade="all, delete-orphan")
    # Task hierarchy relationships
    parent_run = relationship("WorkflowRun", remote_side=[id], foreign_keys=[parent_run_id], backref="child_stage_runs")
    task_stages = relationship("TaskStage", back_populates="parent_run", cascade="all, delete-orphan", foreign_keys="TaskStage.parent_run_id")

    __table_args__ = (
        Index("idx_workflow_runs_session_status", "session_id", "status"),
        Index("idx_workflow_runs_agent_status", "agent", "status"),
    )


class WorkflowStep(Base):
    """A single step within a workflow run."""
    __tablename__ = "workflow_steps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    goal = Column(Text, nullable=False)  # Step goal/description - agents executing it are in ExecutionEvent
    summary = Column(Text, nullable=True)  # Human-readable summary of what was accomplished
    status = Column(String(50), nullable=False, default="pending", index=True)
    # Status: pending, running, paused, waiting_approval, completed, failed, skipped
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    progress_percentage = Column(Integer, nullable=False, default=0)
    inputs = Column(JSON, nullable=True)
    outputs = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)

    # Relationships
    run = relationship("WorkflowRun", back_populates="workflow_steps")
    session = relationship("Session", back_populates="workflow_steps")
    checkpoints = relationship("Checkpoint", back_populates="step", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="step", cascade="all, delete-orphan")
    cost_records = relationship("CostRecord", back_populates="step", cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="step", cascade="all, delete-orphan")
    parent_branches = relationship("Branch", foreign_keys="Branch.parent_step_id", back_populates="parent_step")
    workflow_metrics = relationship("WorkflowMetric", back_populates="step", cascade="all, delete-orphan")
    files = relationship("File", back_populates="step", cascade="all, delete-orphan")
    execution_events = relationship("ExecutionEvent", back_populates="step", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_workflow_steps_run_number", "run_id", "step_number"),
        Index("idx_workflow_steps_session_status", "session_id", "status"),
        CheckConstraint("progress_percentage >= 0 AND progress_percentage <= 100", name="check_progress_range"),
    )


class DAGNode(Base):
    """Node in the workflow DAG (directed acyclic graph)."""
    __tablename__ = "dag_nodes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_node_id = Column(String(36), ForeignKey("dag_nodes.id", ondelete="CASCADE"), nullable=True, index=True)
    node_type = Column(String(50), nullable=False, index=True)
    # Node types: planning, control, agent, approval, parallel_group, terminator, sub_agent, branch_point
    agent = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    # Status: pending, running, completed, failed, skipped
    order_index = Column(Integer, nullable=False)
    depth = Column(Integer, nullable=False, default=0)
    meta = Column(JSON, nullable=True)

    # Relationships
    run = relationship("WorkflowRun", back_populates="dag_nodes")
    session = relationship("Session", back_populates="dag_nodes")
    parent_node = relationship("DAGNode", remote_side=[id], backref="child_nodes")
    outgoing_edges = relationship("DAGEdge", foreign_keys="DAGEdge.from_node_id", back_populates="from_node", cascade="all, delete-orphan")
    incoming_edges = relationship("DAGEdge", foreign_keys="DAGEdge.to_node_id", back_populates="to_node", cascade="all, delete-orphan")
    execution_events = relationship("ExecutionEvent", back_populates="node", cascade="all, delete-orphan")
    files = relationship("File", back_populates="node", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="node", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_dag_nodes_run_order", "run_id", "order_index"),
        Index("idx_dag_nodes_type_status", "node_type", "status"),
        Index("idx_dag_nodes_parent", "parent_node_id"),
    )

    @staticmethod
    def resolve_node_id(db_session, original_node_id: str, run_id: str = None):
        """Resolve an original short node ID to its database record.

        DAG node IDs in the database are hashed to avoid cross-run collisions.
        The original short ID (e.g. 'planning', 'step_1') is stored in meta['id'].
        This method finds the DB record using either direct ID match or meta lookup.

        Args:
            db_session: SQLAlchemy session
            original_node_id: The original short node ID (e.g. 'planning', 'step_1')
            run_id: Optional run_id to scope the search

        Returns:
            DAGNode instance or None
        """
        from sqlalchemy import cast, String

        # First try direct ID match (works for old-style non-hashed IDs)
        query = db_session.query(DAGNode).filter(DAGNode.id == original_node_id)
        if run_id:
            query = query.filter(DAGNode.run_id == run_id)
        node = query.first()
        if node:
            return node

        # Try meta-based lookup for hashed IDs
        if run_id:
            nodes = db_session.query(DAGNode).filter(
                DAGNode.run_id == run_id
            ).all()
            for n in nodes:
                if n.meta and isinstance(n.meta, dict) and n.meta.get("id") == original_node_id:
                    return n

        return None

    @staticmethod
    def resolve_db_id(db_session, original_node_id: str, run_id: str = None) -> str:
        """Resolve an original short node ID to its database ID string.

        Convenience wrapper around resolve_node_id that returns just the ID.

        Returns:
            The database ID string, or the original_node_id if not found.
        """
        node = DAGNode.resolve_node_id(db_session, original_node_id, run_id)
        return node.id if node else original_node_id


class DAGEdge(Base):
    """Edge connecting nodes in the workflow DAG."""
    __tablename__ = "dag_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_node_id = Column(String(36), ForeignKey("dag_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    to_node_id = Column(String(36), ForeignKey("dag_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    dependency_type = Column(String(50), nullable=False, default="sequential")
    # Types: sequential, parallel, conditional
    condition = Column(Text, nullable=True)

    # Relationships
    from_node = relationship("DAGNode", foreign_keys=[from_node_id], back_populates="outgoing_edges")
    to_node = relationship("DAGNode", foreign_keys=[to_node_id], back_populates="incoming_edges")

    __table_args__ = (
        Index("idx_dag_edges_from_to", "from_node_id", "to_node_id"),
    )


class Checkpoint(Base):
    """Checkpoint for workflow state persistence."""
    __tablename__ = "checkpoints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=True, index=True)
    checkpoint_type = Column(String(50), nullable=False, index=True)
    # Types: step_complete, timed, manual, error, emergency
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    context_snapshot = Column(JSON, nullable=True)
    pickle_file_path = Column(String(500), nullable=True)
    meta = Column(JSON, nullable=True)

    # Relationships
    run = relationship("WorkflowRun", back_populates="checkpoints")
    step = relationship("WorkflowStep", back_populates="checkpoints")

    __table_args__ = (
        Index("idx_checkpoints_run_created", "run_id", "created_at"),
        Index("idx_checkpoints_type", "checkpoint_type"),
    )


class Message(Base):
    """Agent-to-agent messages within a workflow."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=True, index=True)
    event_id = Column(String(36), ForeignKey("execution_events.id", ondelete="SET NULL"), nullable=True, index=True)
    node_id = Column(String(36), ForeignKey("dag_nodes.id", ondelete="CASCADE"), nullable=True, index=True)
    sender = Column(String(100), nullable=False, index=True)
    recipient = Column(String(100), nullable=False, index=True)
    content = Column(Text, nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    tokens = Column(Integer, nullable=True)
    meta = Column(JSON, nullable=True)

    # Relationships
    run = relationship("WorkflowRun", back_populates="messages")
    step = relationship("WorkflowStep", back_populates="messages")
    event = relationship("ExecutionEvent", back_populates="messages")
    node = relationship("DAGNode", back_populates="messages")

    __table_args__ = (
        Index("idx_messages_run_timestamp", "run_id", "timestamp"),
        Index("idx_messages_sender_recipient", "sender", "recipient"),
        Index("idx_messages_event", "event_id"),
        Index("idx_messages_node", "node_id"),
    )


class CostRecord(Base):
    """Cost tracking for API calls."""
    __tablename__ = "cost_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(200), nullable=True, index=True)
    parent_run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0.0)
    timestamp = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    run = relationship("WorkflowRun", back_populates="cost_records", foreign_keys=[run_id])
    step = relationship("WorkflowStep", back_populates="cost_records")
    session = relationship("Session", back_populates="cost_records")

    __table_args__ = (
        Index("idx_cost_records_run_timestamp", "run_id", "timestamp"),
        Index("idx_cost_records_session_timestamp", "session_id", "timestamp"),
        Index("idx_cost_records_model", "model"),
    )


class ApprovalRequest(Base):
    """Persistent approval request for HITL workflows"""
    __tablename__ = "approval_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=True, index=True)

    # Request details
    approval_type = Column(String(50), nullable=False)  # plan_approval, step_approval, error_recovery, tool_call
    context = Column(JSON, nullable=False)              # What's being approved (serialized)

    # Resolution
    status = Column(String(20), default="pending", index=True)  # pending, resolved, expired, cancelled
    resolution = Column(String(20), nullable=True)              # approved, rejected, modified
    result = Column(JSON, nullable=True)                        # Resolution details

    # Timing
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Legacy fields for backwards compatibility
    requested_at = Column(TIMESTAMP, nullable=True)
    context_snapshot = Column(JSON, nullable=True)
    user_feedback = Column(Text, nullable=True)

    # Relationships
    run = relationship("WorkflowRun", back_populates="approval_requests")
    step = relationship("WorkflowStep", back_populates="approval_requests")
    session = relationship("Session", back_populates="approval_requests")

    # Indexes for efficient timeout queries
    __table_args__ = (
        Index("idx_approval_run_status", "run_id", "status"),
        Index("idx_approval_expires", "expires_at"),
        Index("idx_approval_session", "session_id"),
        Index("idx_approval_status", "status"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "step_id": self.step_id,
            "approval_type": self.approval_type,
            "context": self.context,
            "status": self.status,
            "resolution": self.resolution,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    @classmethod
    def create_pending(cls, run_id: str, approval_type: str, context: dict,
                       timeout_seconds: int = 300, session_id: str = None, step_id: str = None):
        """Factory method to create a pending approval request"""
        from datetime import datetime, timezone, timedelta
        return cls(
            run_id=run_id,
            session_id=session_id,
            step_id=step_id,
            approval_type=approval_type,
            context=context,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds),
        )


class ActiveConnection(Base):
    """Track active WebSocket connections for multi-instance deployment"""
    __tablename__ = "active_connections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(100), nullable=False, unique=True, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)

    # Server instance tracking (for routing in multi-instance setup)
    server_instance = Column(String(100), nullable=True)  # hostname or instance ID

    # Timing
    connected_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    last_heartbeat = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_connection_task_id", "task_id"),
        Index("idx_connection_heartbeat", "last_heartbeat"),
        Index("idx_connection_session", "session_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "server_instance": self.server_instance,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
        }


class Branch(Base):
    """Workflow branching for exploring alternative paths."""
    __tablename__ = "branches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    parent_run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False, index=True)
    child_run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_name = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    hypothesis = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="active")
    # Status: active, completed, merged, abandoned
    meta = Column(JSON, nullable=True)

    # Racing branch fields
    racing_group_id = Column(String(36), ForeignKey("racing_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    racing_priority = Column(Integer, nullable=True)
    racing_status = Column(String(20), nullable=True)  # racing, won, lost, cancelled

    # Relationships
    parent_run = relationship("WorkflowRun", foreign_keys=[parent_run_id], back_populates="parent_branches")
    parent_step = relationship("WorkflowStep", foreign_keys=[parent_step_id], back_populates="parent_branches")
    child_run = relationship("WorkflowRun", foreign_keys=[child_run_id], back_populates="child_branches")
    racing_group = relationship("RacingGroup", foreign_keys=[racing_group_id], back_populates="branches")

    __table_args__ = (
        Index("idx_branches_parent_run", "parent_run_id"),
        Index("idx_branches_child_run", "child_run_id"),
        Index("idx_branches_racing_group", "racing_group_id"),
    )


class RacingGroup(Base):
    """Group of racing branches competing to solve the same sub-problem."""
    __tablename__ = "racing_groups"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    parent_run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy = Column(String(50), nullable=False, default="first_complete")
    # Strategies: first_complete, best_score
    status = Column(String(20), nullable=False, default="racing")
    # Status: racing, resolved, cancelled
    winner_branch_id = Column(String(36), ForeignKey("branches.id", ondelete="SET NULL", use_alter=True), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(TIMESTAMP, nullable=True)
    meta = Column(JSON, nullable=True)

    # Relationships
    parent_run = relationship("WorkflowRun", foreign_keys=[parent_run_id])
    parent_step = relationship("WorkflowStep", foreign_keys=[parent_step_id])
    branches = relationship("Branch", back_populates="racing_group", foreign_keys="Branch.racing_group_id")


class WorkflowMetric(Base):
    """Performance and observability metrics."""
    __tablename__ = "workflow_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Numeric, nullable=False)
    meta = Column(JSON, nullable=True)

    # Relationships
    run = relationship("WorkflowRun", back_populates="workflow_metrics")
    step = relationship("WorkflowStep", back_populates="workflow_metrics")

    __table_args__ = (
        Index("idx_workflow_metrics_run_name", "run_id", "metric_name"),
        Index("idx_workflow_metrics_timestamp", "timestamp"),
    )


class File(Base):
    """Files generated or used by workflows."""
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=True, index=True)
    event_id = Column(String(36), ForeignKey("execution_events.id", ondelete="SET NULL"), nullable=True, index=True)
    node_id = Column(String(36), ForeignKey("dag_nodes.id", ondelete="CASCADE"), nullable=True, index=True)
    file_path = Column(String(1000), nullable=False)
    file_type = Column(String(50), nullable=False, index=True)
    # Types: plan, code, data, plot, report, chat, context, log, other
    size_bytes = Column(BigInteger, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))

    # New columns for enhanced file tracking
    workflow_phase = Column(String(50), nullable=True, index=True)
    # Phases: planning, control, execution
    is_final_output = Column(Boolean, nullable=False, default=False)
    content_hash = Column(String(64), nullable=True)
    generating_agent = Column(String(100), nullable=True)
    generating_code_hash = Column(String(64), nullable=True)
    priority = Column(String(20), nullable=True)
    # Priorities: primary, secondary, internal

    meta = Column(JSON, nullable=True)

    # Relationships
    run = relationship("WorkflowRun", back_populates="files")
    session = relationship("Session", back_populates="files")
    step = relationship("WorkflowStep", back_populates="files")
    event = relationship("ExecutionEvent", back_populates="files")
    node = relationship("DAGNode", back_populates="files")

    __table_args__ = (
        Index("idx_files_run_type", "run_id", "file_type"),
        Index("idx_files_created", "created_at"),
        Index("idx_files_event", "event_id"),
        Index("idx_files_node", "node_id"),
        Index("idx_files_phase", "run_id", "workflow_phase"),
        Index("idx_files_final_output", "run_id", "is_final_output"),
        Index("idx_files_session", "session_id"),
    )


class ExecutionEvent(Base):
    """
    Fine-grained execution event tracking for workflow traceability.
    
    Captures all actions within a workflow stage including agent calls,
    tool invocations, code execution, file generation, and agent handoffs.
    Supports nested events for hierarchical action tracking.
    """
    __tablename__ = "execution_events"
    
    # Identity
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # Relationships
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), 
                   nullable=False, index=True)
    node_id = Column(String(36), ForeignKey("dag_nodes.id", ondelete="CASCADE"), 
                    nullable=True, index=True)
    step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="SET NULL"), 
                    nullable=True, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), 
                       nullable=False, index=True)
    parent_event_id = Column(String(36), ForeignKey("execution_events.id", ondelete="SET NULL"), 
                            nullable=True, index=True)
    
    # Event Classification
    event_type = Column(String(50), nullable=False, index=True)
    # Types: agent_call, tool_call, code_exec, file_gen, handoff, 
    #        approval_requested, state_transition, error, info
    event_subtype = Column(String(50), nullable=True)
    # Subtypes: start, complete, error, info, pending, approved, rejected
    
    # Agent Context
    agent_name = Column(String(100), nullable=True, index=True)
    agent_role = Column(String(50), nullable=True)  # primary, helper, validator
    
    # Timing
    timestamp = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc), 
                      index=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    duration_ms = Column(Integer, nullable=True)  # Duration in milliseconds
    
    # Execution Data
    inputs = Column(JSON, nullable=True)  # Input parameters, context
    outputs = Column(JSON, nullable=True)  # Results, return values
    error_message = Column(Text, nullable=True)
    
    # Metadata
    meta = Column(JSON, nullable=True)
    # Contains: model, tokens, cost, temperature, custom data
    execution_order = Column(Integer, nullable=False)  # Sequence within node
    depth = Column(Integer, nullable=False, default=0)  # Nesting depth (0=top level)
    
    # Status
    status = Column(String(50), nullable=False, default="completed")
    # Status: pending, running, completed, failed, skipped
    
    # Relationships
    run = relationship("WorkflowRun", back_populates="execution_events")
    node = relationship("DAGNode", back_populates="execution_events")
    step = relationship("WorkflowStep", back_populates="execution_events")
    session = relationship("Session", back_populates="execution_events")
    
    # Self-referential for nested events
    child_events = relationship("ExecutionEvent", 
                               back_populates="parent_event",
                               cascade="all, delete-orphan")
    parent_event = relationship("ExecutionEvent", 
                               remote_side=[id],
                               back_populates="child_events")
    
    # Files and messages created by this event
    files = relationship("File", back_populates="event", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="event", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_events_run_order", "run_id", "execution_order"),
        Index("idx_events_node_order", "node_id", "execution_order"),
        Index("idx_events_type_subtype", "event_type", "event_subtype"),
        Index("idx_events_session_timestamp", "session_id", "timestamp"),
        Index("idx_events_parent", "parent_event_id"),
    )
    
    def __repr__(self):
        return (f"<ExecutionEvent(id={self.id}, type={self.event_type}, "
                f"agent={self.agent_name}, order={self.execution_order})>")


class TaskStage(Base):
    """Individual stage tracking within a multi-stage task workflow."""
    __tablename__ = "task_stages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    parent_run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    child_run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    stage_number = Column(Integer, nullable=False)
    stage_name = Column(String(100), nullable=False)  # idea_generation, method_development, experiment_execution, paper_generation
    status = Column(String(50), nullable=False, default="pending", index=True)
    # Status: pending, running, completed, failed, skipped
    input_data = Column(JSON, nullable=True)  # Context keys received
    output_data = Column(JSON, nullable=True)  # Context keys produced
    output_files = Column(JSON, nullable=True)  # List of file paths created
    error_message = Column(Text, nullable=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    meta = Column(JSON, nullable=True)

    # Relationships
    parent_run = relationship("WorkflowRun", foreign_keys=[parent_run_id], back_populates="task_stages")
    child_run = relationship("WorkflowRun", foreign_keys=[child_run_id])

    __table_args__ = (
        Index("idx_task_stages_parent_run", "parent_run_id"),
        Index("idx_task_stages_status", "status"),
        Index("idx_task_stages_parent_stage", "parent_run_id", "stage_number"),
    )


class StateHistory(Base):
    """Audit trail of all state transitions for workflows and steps."""
    __tablename__ = "state_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(50), nullable=False, index=True)  # "workflow_run" or "workflow_step"
    entity_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    from_state = Column(String(50), nullable=True)  # Null for initial state
    to_state = Column(String(50), nullable=False, index=True)
    transition_reason = Column(Text, nullable=True)
    transitioned_by = Column(String(100), nullable=True)  # User or system

    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    meta = Column(JSON, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_state_history_entity", "entity_type", "entity_id"),
        Index("idx_state_history_session", "session_id"),
        Index("idx_state_history_created", "created_at"),
    )
