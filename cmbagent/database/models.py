"""
SQLAlchemy models for CMBAgent database schema.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, BigInteger, Text, Boolean,
    ForeignKey, Index, TIMESTAMP, Numeric, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from cmbagent.database.base import Base


def get_json_type():
    """Get appropriate JSON type for current database."""
    # PostgreSQL uses JSONB, SQLite uses JSON
    try:
        return JSONB
    except:
        return JSON


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
    projects = relationship("Project", back_populates="session", cascade="all, delete-orphan")
    workflow_runs = relationship("WorkflowRun", back_populates="session", cascade="all, delete-orphan")
    workflow_steps = relationship("WorkflowStep", back_populates="session", cascade="all, delete-orphan")
    dag_nodes = relationship("DAGNode", back_populates="session", cascade="all, delete-orphan")
    cost_records = relationship("CostRecord", back_populates="session", cascade="all, delete-orphan")
    execution_events = relationship("ExecutionEvent", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sessions_user_status", "user_id", "status"),
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

    # Relationships
    session = relationship("Session", back_populates="workflow_runs")
    project = relationship("Project", back_populates="workflow_runs")
    workflow_steps = relationship("WorkflowStep", back_populates="run", cascade="all, delete-orphan")
    dag_nodes = relationship("DAGNode", back_populates="run", cascade="all, delete-orphan")
    checkpoints = relationship("Checkpoint", back_populates="run", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="run", cascade="all, delete-orphan")
    cost_records = relationship("CostRecord", back_populates="run", cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="run", cascade="all, delete-orphan")
    parent_branches = relationship("Branch", foreign_keys="Branch.parent_run_id", back_populates="parent_run")
    child_branches = relationship("Branch", foreign_keys="Branch.child_run_id", back_populates="child_run")
    workflow_metrics = relationship("WorkflowMetric", back_populates="run", cascade="all, delete-orphan")
    files = relationship("File", back_populates="run", cascade="all, delete-orphan")
    execution_events = relationship("ExecutionEvent", back_populates="run", cascade="all, delete-orphan")

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
    node_type = Column(String(50), nullable=False, index=True)
    # Node types: planning, control, agent, approval, parallel_group, terminator
    agent = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    # Status: pending, running, completed, failed, skipped
    order_index = Column(Integer, nullable=False)
    meta = Column(JSON, nullable=True)

    # Relationships
    run = relationship("WorkflowRun", back_populates="dag_nodes")
    session = relationship("Session", back_populates="dag_nodes")
    outgoing_edges = relationship("DAGEdge", foreign_keys="DAGEdge.from_node_id", back_populates="from_node", cascade="all, delete-orphan")
    incoming_edges = relationship("DAGEdge", foreign_keys="DAGEdge.to_node_id", back_populates="to_node", cascade="all, delete-orphan")
    execution_events = relationship("ExecutionEvent", back_populates="node", cascade="all, delete-orphan")
    files = relationship("File", back_populates="node", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="node", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_dag_nodes_run_order", "run_id", "order_index"),
        Index("idx_dag_nodes_type_status", "node_type", "status"),
    )


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
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0.0)
    timestamp = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    run = relationship("WorkflowRun", back_populates="cost_records")
    step = relationship("WorkflowStep", back_populates="cost_records")
    session = relationship("Session", back_populates="cost_records")

    __table_args__ = (
        Index("idx_cost_records_run_timestamp", "run_id", "timestamp"),
        Index("idx_cost_records_session_timestamp", "session_id", "timestamp"),
        Index("idx_cost_records_model", "model"),
    )


class ApprovalRequest(Base):
    """Human-in-the-loop approval requests."""
    __tablename__ = "approval_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(36), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    # Status: pending, approved, rejected, modified
    requested_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(TIMESTAMP, nullable=True)
    context_snapshot = Column(JSON, nullable=True)
    user_feedback = Column(Text, nullable=True)
    resolution = Column(String(50), nullable=True)

    # Relationships
    run = relationship("WorkflowRun", back_populates="approval_requests")
    step = relationship("WorkflowStep", back_populates="approval_requests")

    __table_args__ = (
        Index("idx_approval_requests_status", "status"),
        Index("idx_approval_requests_run_requested", "run_id", "requested_at"),
    )


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

    # Relationships
    parent_run = relationship("WorkflowRun", foreign_keys=[parent_run_id], back_populates="parent_branches")
    parent_step = relationship("WorkflowStep", foreign_keys=[parent_step_id], back_populates="parent_branches")
    child_run = relationship("WorkflowRun", foreign_keys=[child_run_id], back_populates="child_branches")

    __table_args__ = (
        Index("idx_branches_parent_run", "parent_run_id"),
        Index("idx_branches_child_run", "child_run_id"),
    )


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
