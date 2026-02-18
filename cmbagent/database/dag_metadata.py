"""
DAG Node Metadata Enrichment

Generates execution summaries for DAG nodes from execution events.
"""

import logging
import structlog
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from cmbagent.database.models import DAGNode, ExecutionEvent, File, Message
from cmbagent.database.repository import EventRepository

logger = structlog.get_logger(__name__)


class DAGMetadataEnricher:
    """Enriches DAG node metadata with execution summaries."""

    def __init__(self, db_session: Session, session_id: str):
        self.db = db_session
        self.session_id = session_id
        self.event_repo = EventRepository(db_session, session_id)

    def enrich_node(self, node_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate execution summary for a DAG node.

        Args:
            node_id: DAG node ID
            run_id: Optional workflow run ID to filter events (prevents mixing data from multiple runs)

        Returns:
            Dictionary with execution summary
        """
        from cmbagent.database.models import DAGNode, ExecutionEvent, WorkflowRun

        # If no run_id provided, try to find it from the MOST RECENT node
        if not run_id:
            dag_node = self.db.query(DAGNode).join(WorkflowRun).filter(
                DAGNode.id == node_id
            ).order_by(WorkflowRun.started_at.desc()).first()

            if dag_node:
                run_id = dag_node.run_id
                logger.debug("auto_detected_run_id", run_id=run_id, node_id=node_id)

        # ALWAYS query with both node_id and run_id for accuracy
        if run_id:
            # Query directly with both node_id and run_id (REQUIRED)
            events = self.db.query(ExecutionEvent).filter(
                ExecutionEvent.node_id == node_id,
                ExecutionEvent.run_id == run_id
            ).all()
            logger.debug("events_found", event_count=len(events), node_id=node_id, run_id=run_id)
        else:
            # No run_id found - return empty to avoid wrong data
            logger.error("run_id_not_determined", node_id=node_id)
            events = []

        if not events:
            return self._empty_summary()

        # Filter out 'start' subtypes and internal events to avoid double counting
        filtered_events = [
            e for e in events
            if e.event_subtype not in ['start'] and e.event_type not in ['node_started', 'node_completed']
        ]

        # Get run_id from first event if not already set
        if not run_id:
            run_id = events[0].run_id if events else None

        # Calculate statistics on filtered events
        stats = self.event_repo.get_event_statistics(run_id) if run_id else {}

        # Get files generated
        files = self.db.query(File).filter(File.node_id == node_id).all()

        # Get messages
        messages = self.db.query(Message).filter(Message.node_id == node_id).all()

        # Build summary using filtered events
        summary = {
            "execution_summary": {
                "total_events": len(filtered_events),
                "raw_event_count": len(events),  # Include raw count for debugging
                "event_types": self._count_event_types(filtered_events),
                "agents_involved": list(set(e.agent_name for e in filtered_events if e.agent_name)),
                "agent_call_counts": self._count_agent_calls(filtered_events),
                "files_generated": len(files),
                "files_by_type": self._group_files_by_type(files),
                "messages_count": len(messages),
                "timing": self._calculate_timing(filtered_events),
                "cost_summary": self._calculate_cost(filtered_events),
                "success_metrics": self._calculate_success_metrics(filtered_events)
            }
        }

        return summary

    def update_node_metadata(self, node_id: str):
        """
        Update DAGNode.meta with execution summary.

        Args:
            node_id: DAG node ID
        """
        node = self.db.query(DAGNode).filter(DAGNode.id == node_id).first()
        if not node:
            return

        summary = self.enrich_node(node_id)

        # Merge with existing metadata
        meta = node.meta or {}
        meta.update(summary)

        node.meta = meta
        self.db.commit()

    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary structure."""
        return {
            "execution_summary": {
                "total_events": 0,
                "event_types": {},
                "agents_involved": [],
                "agent_call_counts": {},
                "files_generated": 0,
                "files_by_type": {},
                "messages_count": 0,
                "timing": {},
                "cost_summary": {},
                "success_metrics": {}
            }
        }

    def _count_event_types(self, events: List[ExecutionEvent]) -> Dict[str, int]:
        """Count events by type."""
        counts = {}
        for event in events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts

    def _count_agent_calls(self, events: List[ExecutionEvent]) -> Dict[str, int]:
        """Count agent invocations (only 'complete' or events without subtype to avoid double counting)."""
        counts = {}
        for event in events:
            if event.agent_name and event.event_type == "agent_call":
                # This should already be filtered, but double-check
                if event.event_subtype not in ['start']:
                    counts[event.agent_name] = counts.get(event.agent_name, 0) + 1
        return counts

    def _group_files_by_type(self, files: List[File]) -> Dict[str, int]:
        """Group files by type."""
        groups = {}
        for file in files:
            groups[file.file_type] = groups.get(file.file_type, 0) + 1
        return groups

    def _calculate_timing(self, events: List[ExecutionEvent]) -> Dict[str, Any]:
        """Calculate timing metrics."""
        if not events:
            return {}

        # Find earliest and latest timestamps
        timestamps = [e.timestamp for e in events if e.timestamp]
        if not timestamps:
            return {}

        started_at = min(timestamps)
        completed_at = max(timestamps)
        duration = (completed_at - started_at).total_seconds()

        # Calculate agent time breakdown
        agent_times = {}
        for event in events:
            if event.agent_name and event.duration_ms:
                agent_times[event.agent_name] = \
                    agent_times.get(event.agent_name, 0) + (event.duration_ms / 1000)

        return {
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": duration,
            "agent_time_breakdown": agent_times
        }

    def _calculate_cost(self, events: List[ExecutionEvent]) -> Dict[str, Any]:
        """Calculate cost metrics from event metadata."""
        total_tokens = 0
        total_cost = 0.0
        by_agent = {}

        for event in events:
            meta = event.meta or {}
            tokens = meta.get("tokens", 0)
            cost = meta.get("cost_usd", 0.0)

            total_tokens += tokens
            total_cost += cost

            if event.agent_name and (tokens > 0 or cost > 0):
                if event.agent_name not in by_agent:
                    by_agent[event.agent_name] = {"tokens": 0, "cost": 0.0}
                by_agent[event.agent_name]["tokens"] += tokens
                by_agent[event.agent_name]["cost"] += cost

        return {
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "by_agent": by_agent
        }

    def _calculate_success_metrics(self, events: List[ExecutionEvent]) -> Dict[str, Any]:
        """Calculate success/failure metrics."""
        completed = sum(1 for e in events if e.status == "completed")
        failed = sum(1 for e in events if e.status == "failed")
        errors = sum(1 for e in events if e.event_type == "error")

        total = len(events)
        completion_rate = completed / total if total > 0 else 0

        return {
            "completion_rate": completion_rate,
            "error_count": errors,
            "failed_count": failed,
            "completed_count": completed
        }
