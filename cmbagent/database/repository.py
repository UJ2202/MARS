"""
Repository layer for database access with session isolation.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session as DBSession

from cmbagent.database.models import (
    Session, Project, WorkflowRun, WorkflowStep,
    DAGNode, DAGEdge, Checkpoint, Message,
    CostRecord, ApprovalRequest, Branch,
    WorkflowMetric, File, ExecutionEvent,
)


class BaseRepository:
    """Base repository with common functionality."""

    def __init__(self, db: DBSession, session_id: str):
        self.db = db
        self.session_id = session_id

    def commit(self):
        """Commit the current transaction."""
        self.db.commit()

    def rollback(self):
        """Rollback the current transaction."""
        self.db.rollback()

    def refresh(self, obj):
        """Refresh an object from the database."""
        self.db.refresh(obj)


class SessionRepository(BaseRepository):
    """Repository for session management."""

    def create_session(self, name: str, user_id: Optional[str] = None, **kwargs) -> Session:
        """Create a new session."""
        session = Session(
            name=name,
            user_id=user_id,
            **kwargs
        )
        self.db.add(session)
        self.db.commit()
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        return self.db.query(Session).filter(Session.id == session_id).first()

    def list_sessions(self, user_id: Optional[str] = None, status: Optional[str] = None) -> List[Session]:
        """List sessions with optional filters."""
        query = self.db.query(Session)
        if user_id:
            query = query.filter(Session.user_id == user_id)
        if status:
            query = query.filter(Session.status == status)
        return query.order_by(Session.last_active_at.desc()).all()

    def update_last_active(self, session_id: str):
        """Update last active timestamp."""
        session = self.get_session(session_id)
        if session:
            session.last_active_at = datetime.now(timezone.utc)
            self.db.commit()


class WorkflowRepository(BaseRepository):
    """Repository for workflow runs and steps."""

    def create_run(self, **kwargs) -> WorkflowRun:
        """Create a new workflow run."""
        run = WorkflowRun(
            session_id=self.session_id,
            **kwargs
        )
        self.db.add(run)
        self.db.commit()
        return run

    def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        """Get workflow run by ID with session isolation."""
        return self.db.query(WorkflowRun).filter(
            WorkflowRun.id == run_id,
            WorkflowRun.session_id == self.session_id
        ).first()

    def list_runs(self, status: Optional[str] = None, agent: Optional[str] = None) -> List[WorkflowRun]:
        """List workflow runs with optional filters."""
        query = self.db.query(WorkflowRun).filter(
            WorkflowRun.session_id == self.session_id
        )
        if status:
            query = query.filter(WorkflowRun.status == status)
        if agent:
            query = query.filter(WorkflowRun.agent == agent)
        return query.order_by(WorkflowRun.started_at.desc()).all()

    def update_run_status(self, run_id: str, status: str, **kwargs):
        """Update workflow run status."""
        run = self.get_run(run_id)
        if run:
            run.status = status
            for key, value in kwargs.items():
                setattr(run, key, value)
            self.db.commit()

    def create_step(self, run_id: str, step_number: int, agent: str, **kwargs) -> WorkflowStep:
        """Create a new workflow step."""
        step = WorkflowStep(
            run_id=run_id,
            session_id=self.session_id,
            step_number=step_number,
            agent=agent,
            **kwargs
        )
        self.db.add(step)
        self.db.commit()
        return step

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """Get workflow step by ID."""
        return self.db.query(WorkflowStep).filter(
            WorkflowStep.id == step_id,
            WorkflowStep.session_id == self.session_id
        ).first()

    def list_steps(self, run_id: str) -> List[WorkflowStep]:
        """List all steps for a workflow run."""
        return self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id,
            WorkflowStep.session_id == self.session_id
        ).order_by(WorkflowStep.step_number).all()

    def update_step_status(self, step_id: str, status: str, **kwargs):
        """Update workflow step status."""
        step = self.get_step(step_id)
        if step:
            step.status = status
            for key, value in kwargs.items():
                setattr(step, key, value)
            self.db.commit()

    def update_step_progress(self, step_id: str, progress: int):
        """Update step progress percentage."""
        step = self.get_step(step_id)
        if step:
            step.progress_percentage = max(0, min(100, progress))
            self.db.commit()


class DAGRepository(BaseRepository):
    """Repository for DAG nodes and edges."""

    def create_node(self, run_id: str, node_type: str, order_index: int, **kwargs) -> DAGNode:
        """Create a new DAG node."""
        node = DAGNode(
            run_id=run_id,
            session_id=self.session_id,
            node_type=node_type,
            order_index=order_index,
            **kwargs
        )
        self.db.add(node)
        self.db.commit()
        return node

    def get_node(self, node_id: str) -> Optional[DAGNode]:
        """Get DAG node by ID."""
        return self.db.query(DAGNode).filter(
            DAGNode.id == node_id,
            DAGNode.session_id == self.session_id
        ).first()

    def list_nodes(self, run_id: str) -> List[DAGNode]:
        """List all nodes for a workflow run."""
        return self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id,
            DAGNode.session_id == self.session_id
        ).order_by(DAGNode.order_index).all()

    def update_node_status(self, node_id: str, status: str, **kwargs) -> Optional[DAGNode]:
        """Update the status of a DAG node.

        Args:
            node_id: The ID of the node to update
            status: New status (pending, running, completed, failed, skipped)
            **kwargs: Additional fields to update (e.g., meta)
                     Note: If 'meta' is provided, it will be merged with existing meta
                     rather than replacing it completely.

        Returns:
            Updated DAGNode or None if not found
        """
        node = self.get_node(node_id)
        if node:
            node.status = status
            for key, value in kwargs.items():
                if hasattr(node, key):
                    # Special handling for meta: merge instead of replace
                    if key == "meta" and value is not None:
                        existing_meta = node.meta or {}
                        # Merge new meta into existing meta
                        merged_meta = {**existing_meta, **value}
                        setattr(node, key, merged_meta)
                    else:
                        setattr(node, key, value)
            self.db.commit()
            self.db.refresh(node)
            return node
        return None

    def create_edge(self, from_node_id: str, to_node_id: str, dependency_type: str = "sequential", **kwargs) -> DAGEdge:
        """Create a new DAG edge."""
        edge = DAGEdge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            dependency_type=dependency_type,
            **kwargs
        )
        self.db.add(edge)
        self.db.commit()
        return edge

    def get_node_dependencies(self, node_id: str) -> List[DAGNode]:
        """Get all dependencies (incoming edges) for a node."""
        edges = self.db.query(DAGEdge).filter(DAGEdge.to_node_id == node_id).all()
        node_ids = [edge.from_node_id for edge in edges]
        return self.db.query(DAGNode).filter(DAGNode.id.in_(node_ids)).all()

    def get_node_dependents(self, node_id: str) -> List[DAGNode]:
        """Get all dependents (outgoing edges) for a node."""
        edges = self.db.query(DAGEdge).filter(DAGEdge.from_node_id == node_id).all()
        node_ids = [edge.to_node_id for edge in edges]
        return self.db.query(DAGNode).filter(DAGNode.id.in_(node_ids)).all()

    def create_sub_node(
        self,
        parent_node_id: str,
        node_type: str,
        agent: str,
        status: str = "pending",
        meta: Optional[Dict[str, Any]] = None
    ) -> DAGNode:
        """
        Create a sub-node under a parent node.

        Args:
            parent_node_id: ID of parent node
            node_type: Type of sub-node (e.g., "sub_agent", "tool_call")
            agent: Agent name
            status: Initial status
            meta: Additional metadata

        Returns:
            Created DAGNode
        """
        parent = self.db.query(DAGNode).filter(DAGNode.id == parent_node_id).first()
        if not parent:
            raise ValueError(f"Parent node {parent_node_id} not found")

        # Calculate depth and order_index for sub-node
        depth = parent.depth + 1

        # Find max order_index among siblings
        siblings = self.db.query(DAGNode).filter(
            DAGNode.parent_node_id == parent_node_id
        ).all()
        order_index = max([s.order_index for s in siblings], default=-1) + 1

        node = DAGNode(
            run_id=parent.run_id,
            session_id=parent.session_id,
            parent_node_id=parent_node_id,
            node_type=node_type,
            agent=agent,
            status=status,
            order_index=order_index,
            depth=depth,
            meta=meta or {}
        )

        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)

        return node

    def create_branch_node(
        self,
        source_node_id: str,
        branch_name: str,
        hypothesis: Optional[str] = None
    ) -> DAGNode:
        """
        Create a branch node for alternative execution paths.

        Args:
            source_node_id: Node to branch from
            branch_name: Name of the branch (e.g., "redo_1", "alternative_a")
            hypothesis: Hypothesis for this branch

        Returns:
            Created branch node
        """
        source = self.db.query(DAGNode).filter(DAGNode.id == source_node_id).first()
        if not source:
            raise ValueError(f"Source node {source_node_id} not found")

        # Create branch node at same level as source
        node = DAGNode(
            run_id=source.run_id,
            session_id=source.session_id,
            parent_node_id=source.parent_node_id,
            node_type="branch_point",
            agent=f"branch_{branch_name}",
            status="pending",
            order_index=source.order_index,
            depth=source.depth,
            meta={
                "branch_name": branch_name,
                "hypothesis": hypothesis,
                "source_node_id": source_node_id
            }
        )

        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)

        # Create conditional edge from source to branch
        edge = DAGEdge(
            from_node_id=source_node_id,
            to_node_id=node.id,
            dependency_type="conditional",
            condition=f"branch_{branch_name}"
        )
        self.db.add(edge)
        self.db.commit()

        return node


class CheckpointRepository(BaseRepository):
    """Repository for checkpoint management."""

    def create_checkpoint(self, run_id: str, checkpoint_type: str, **kwargs) -> Checkpoint:
        """Create a new checkpoint."""
        checkpoint = Checkpoint(
            run_id=run_id,
            checkpoint_type=checkpoint_type,
            **kwargs
        )
        self.db.add(checkpoint)
        self.db.commit()
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get checkpoint by ID."""
        return self.db.query(Checkpoint).filter(Checkpoint.id == checkpoint_id).first()

    def list_checkpoints(self, run_id: str, checkpoint_type: Optional[str] = None) -> List[Checkpoint]:
        """List checkpoints for a workflow run."""
        query = self.db.query(Checkpoint).filter(Checkpoint.run_id == run_id)
        if checkpoint_type:
            query = query.filter(Checkpoint.checkpoint_type == checkpoint_type)
        return query.order_by(Checkpoint.created_at.desc()).all()

    def get_latest_checkpoint(self, run_id: str) -> Optional[Checkpoint]:
        """Get the most recent checkpoint for a run."""
        return self.db.query(Checkpoint).filter(
            Checkpoint.run_id == run_id
        ).order_by(Checkpoint.created_at.desc()).first()


class CostRepository(BaseRepository):
    """Repository for cost tracking."""

    def record_cost(self, run_id: str, model: str, prompt_tokens: int, completion_tokens: int, cost_usd: float, **kwargs) -> CostRecord:
        """Record a cost entry."""
        cost_record = CostRecord(
            run_id=run_id,
            session_id=self.session_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
            **kwargs
        )
        self.db.add(cost_record)
        self.db.commit()
        return cost_record

    def get_run_cost(self, run_id: str) -> Dict[str, Any]:
        """Get total cost for a workflow run."""
        records = self.db.query(CostRecord).filter(CostRecord.run_id == run_id).all()
        total_cost = sum(r.cost_usd for r in records)
        total_tokens = sum(r.total_tokens for r in records)
        return {
            "total_cost_usd": float(total_cost),
            "total_tokens": total_tokens,
            "record_count": len(records),
        }

    def get_session_cost(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get total cost for the session."""
        query = self.db.query(CostRecord).filter(CostRecord.session_id == self.session_id)
        if start_date:
            query = query.filter(CostRecord.timestamp >= start_date)
        if end_date:
            query = query.filter(CostRecord.timestamp <= end_date)

        records = query.all()
        total_cost = sum(r.cost_usd for r in records)
        total_tokens = sum(r.total_tokens for r in records)

        # Group by model
        by_model = {}
        for record in records:
            if record.model not in by_model:
                by_model[record.model] = {"cost": 0, "tokens": 0, "count": 0}
            by_model[record.model]["cost"] += float(record.cost_usd)
            by_model[record.model]["tokens"] += record.total_tokens
            by_model[record.model]["count"] += 1

        return {
            "total_cost_usd": float(total_cost),
            "total_tokens": total_tokens,
            "record_count": len(records),
            "by_model": by_model,
        }


class MessageRepository(BaseRepository):
    """Repository for message storage."""

    def create_message(self, run_id: str, sender: str, recipient: str, content: str, **kwargs) -> Message:
        """Create a new message."""
        message = Message(
            run_id=run_id,
            sender=sender,
            recipient=recipient,
            content=content,
            **kwargs
        )
        self.db.add(message)
        self.db.commit()
        return message

    def list_messages(self, run_id: str, step_id: Optional[str] = None) -> List[Message]:
        """List messages for a workflow run."""
        query = self.db.query(Message).filter(Message.run_id == run_id)
        if step_id:
            query = query.filter(Message.step_id == step_id)
        return query.order_by(Message.timestamp).all()


class ApprovalRepository(BaseRepository):
    """Repository for approval requests."""

    def create_approval_request(self, run_id: str, step_id: str, **kwargs) -> ApprovalRequest:
        """Create a new approval request."""
        approval = ApprovalRequest(
            run_id=run_id,
            step_id=step_id,
            **kwargs
        )
        self.db.add(approval)
        self.db.commit()
        return approval

    def get_approval_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get approval request by ID."""
        return self.db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()

    def list_pending_approvals(self, run_id: Optional[str] = None) -> List[ApprovalRequest]:
        """List pending approval requests."""
        query = self.db.query(ApprovalRequest).filter(ApprovalRequest.status == "pending")
        if run_id:
            query = query.filter(ApprovalRequest.run_id == run_id)
        return query.order_by(ApprovalRequest.requested_at).all()

    def resolve_approval(self, approval_id: str, status: str, user_feedback: Optional[str] = None, resolution: Optional[str] = None):
        """Resolve an approval request."""
        approval = self.get_approval_request(approval_id)
        if approval:
            approval.status = status
            approval.resolved_at = datetime.now(timezone.utc)
            approval.user_feedback = user_feedback
            approval.resolution = resolution
            self.db.commit()


class EventRepository(BaseRepository):
    """Repository for execution event operations."""
    
    def create_event(
        self,
        run_id: str,
        event_type: str,
        execution_order: int,
        node_id: Optional[str] = None,
        step_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        **kwargs
    ) -> ExecutionEvent:
        """
        Create a new execution event.
        
        Args:
            run_id: Workflow run ID
            event_type: Type of event (agent_call, tool_call, etc.)
            execution_order: Sequence number within node
            node_id: Optional DAG node ID
            step_id: Optional workflow step ID
            parent_event_id: Optional parent event ID for nesting
            **kwargs: Additional event fields
            
        Returns:
            Created ExecutionEvent instance
        """
        event = ExecutionEvent(
            run_id=run_id,
            session_id=self.session_id,
            node_id=node_id,
            step_id=step_id,
            parent_event_id=parent_event_id,
            event_type=event_type,
            execution_order=execution_order,
            timestamp=datetime.now(timezone.utc),
            **kwargs
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
    
    def get_event(self, event_id: str) -> Optional[ExecutionEvent]:
        """Get event by ID."""
        return self.db.query(ExecutionEvent).filter(
            ExecutionEvent.id == event_id,
            ExecutionEvent.session_id == self.session_id
        ).first()
    
    def list_events_for_run(
        self,
        run_id: str,
        event_type: Optional[str] = None,
        agent_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[ExecutionEvent]:
        """
        List events for a workflow run.
        
        Args:
            run_id: Workflow run ID
            event_type: Optional filter by event type
            agent_name: Optional filter by agent name
            limit: Optional limit on results
            
        Returns:
            List of ExecutionEvent instances
        """
        query = self.db.query(ExecutionEvent).filter(
            ExecutionEvent.run_id == run_id,
            ExecutionEvent.session_id == self.session_id
        )
        
        if event_type:
            query = query.filter(ExecutionEvent.event_type == event_type)
        
        if agent_name:
            query = query.filter(ExecutionEvent.agent_name == agent_name)
        
        query = query.order_by(ExecutionEvent.execution_order)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def list_events_for_node(
        self,
        node_id: str,
        event_type: Optional[str] = None,
        filter_by_session: bool = False
    ) -> List[ExecutionEvent]:
        """
        List events for a DAG node.
        
        Args:
            node_id: DAG node ID
            event_type: Optional filter by event type
            filter_by_session: If True, filter by session_id (default: False)
                              Set to False to get all events for a node regardless of session
            
        Returns:
            List of ExecutionEvent instances
        """
        query = self.db.query(ExecutionEvent).filter(
            ExecutionEvent.node_id == node_id
        )
        
        # Only filter by session if explicitly requested
        if filter_by_session:
            query = query.filter(ExecutionEvent.session_id == self.session_id)
        
        if event_type:
            query = query.filter(ExecutionEvent.event_type == event_type)
        
        return query.order_by(ExecutionEvent.execution_order).all()
    
    def get_child_events(self, parent_event_id: str) -> List[ExecutionEvent]:
        """
        Get all child events of a parent event.
        
        Args:
            parent_event_id: Parent event ID
            
        Returns:
            List of child ExecutionEvent instances
        """
        return self.db.query(ExecutionEvent).filter(
            ExecutionEvent.parent_event_id == parent_event_id,
            ExecutionEvent.session_id == self.session_id
        ).order_by(ExecutionEvent.execution_order).all()
    
    def get_event_tree(self, root_event_id: str) -> List[ExecutionEvent]:
        """
        Get full event tree from root event (recursive query).
        
        Args:
            root_event_id: Root event ID
            
        Returns:
            List of all events in tree, ordered by depth and execution_order
        """
        # Use recursive CTE for event tree
        from sqlalchemy import text
        
        query = text("""
            WITH RECURSIVE event_tree AS (
                SELECT * FROM execution_events 
                WHERE id = :root_id AND session_id = :session_id
                UNION ALL
                SELECT e.* FROM execution_events e
                INNER JOIN event_tree et ON e.parent_event_id = et.id
                WHERE e.session_id = :session_id
            )
            SELECT * FROM event_tree ORDER BY depth, execution_order
        """)
        
        result = self.db.execute(
            query, 
            {"root_id": root_event_id, "session_id": self.session_id}
        )
        
        # Convert to ExecutionEvent objects
        events = []
        for row in result:
            event = self.db.query(ExecutionEvent).filter(
                ExecutionEvent.id == row.id
            ).first()
            if event:
                events.append(event)
        
        return events
    
    def update_event(self, event_id: str, **kwargs):
        """Update event fields."""
        event = self.get_event(event_id)
        if event:
            for key, value in kwargs.items():
                if hasattr(event, key):
                    setattr(event, key, value)
            self.db.commit()
            self.db.refresh(event)
            return event
        return None
    
    def delete_event(self, event_id: str):
        """Delete an event."""
        event = self.get_event(event_id)
        if event:
            self.db.delete(event)
            self.db.commit()
            return True
        return False
    
    def get_event_statistics(self, run_id: str) -> Dict[str, Any]:
        """
        Get statistics about events for a run.
        
        Args:
            run_id: Workflow run ID
            
        Returns:
            Dictionary with event statistics
        """
        from sqlalchemy import func
        
        events = self.list_events_for_run(run_id)
        
        stats = {
            "total_events": len(events),
            "event_types": {},
            "agents_involved": set(),
            "agent_call_counts": {},
            "avg_duration_ms": 0,
            "total_duration_ms": 0
        }
        
        total_duration = 0
        duration_count = 0
        
        for event in events:
            # Count event types
            stats["event_types"][event.event_type] = \
                stats["event_types"].get(event.event_type, 0) + 1
            
            # Track agents
            if event.agent_name:
                stats["agents_involved"].add(event.agent_name)
                stats["agent_call_counts"][event.agent_name] = \
                    stats["agent_call_counts"].get(event.agent_name, 0) + 1
            
            # Calculate durations
            if event.duration_ms:
                total_duration += event.duration_ms
                duration_count += 1
        
        stats["agents_involved"] = list(stats["agents_involved"])
        stats["total_duration_ms"] = total_duration
        if duration_count > 0:
            stats["avg_duration_ms"] = total_duration / duration_count
        
        return stats

