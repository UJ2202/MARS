"""
Play-from-node executor for resuming workflow execution from specific nodes.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from cmbagent.database.models import DAGNode, WorkflowStep, Checkpoint, WorkflowRun

logger = logging.getLogger(__name__)


class PlayFromNodeExecutor:
    """Executor for resuming workflow execution from a specific node."""

    def __init__(self, db_session, run_id: str):
        """
        Initialize play-from-node executor.

        Args:
            db_session: SQLAlchemy database session
            run_id: ID of the workflow run
        """
        self.db = db_session
        self.run_id = run_id

    def play_from_node(
        self,
        node_id: str,
        context_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resume workflow execution from a specific node.

        Args:
            node_id: ID of DAG node to start from
            context_override: Optional dict to modify context before resuming

        Returns:
            execution_result: Result of resumed execution with status and context
        """
        # 0. First validate the workflow run exists
        run = self.db.query(WorkflowRun).filter(WorkflowRun.id == self.run_id).first()
        if not run:
            raise ValueError(f"Workflow run {self.run_id} not found")

        # 1. Validate node exists and belongs to this run
        node = DAGNode.resolve_node_id(self.db, node_id, self.run_id)
        if not node:
            raise ValueError(f"Node {node_id} not found in run {self.run_id}")

        # Use the resolved DB node ID for subsequent queries
        db_node_id = node.id

        # 2. Load checkpoint before this node
        checkpoint = self._find_checkpoint_before_node(node_id)

        if not checkpoint:
            logger.warning(f"No checkpoint found before node {node_id}, using empty context")
            context = {}
        else:
            context = (checkpoint.context_snapshot or {}).copy()

        # Apply context override if provided
        if context_override:
            context.update(context_override)

        # 3. Mark all nodes after branch point as PENDING
        self._reset_downstream_nodes(db_node_id)

        # 4. Update workflow run status to EXECUTING
        run.status = "executing"
        if not run.meta:
            run.meta = {}
        run.meta["resumed_from_node"] = str(node_id)
        run.meta["resumed_at"] = datetime.now(timezone.utc).isoformat()
        self.db.commit()

        # 5. Return context and node info for execution
        # Note: Actual execution will be handled by DAGExecutor
        result = {
            "status": "ready_to_execute",
            "run_id": self.run_id,
            "node_id": node_id,
            "context": context,
            "message": f"Workflow ready to resume from node {node_id}"
        }

        logger.info(f"Prepared workflow {self.run_id} to resume from node {node_id}")

        return result

    def _find_checkpoint_before_node(self, node_id: str) -> Optional[Checkpoint]:
        """Find most recent checkpoint before this node."""
        node = DAGNode.resolve_node_id(self.db, node_id, self.run_id)

        if not node:
            return None

        # Get all checkpoints for this run
        checkpoints = self.db.query(Checkpoint).filter(
            Checkpoint.run_id == self.run_id
        ).order_by(Checkpoint.created_at.desc()).all()

        # Find checkpoint with step_number < node.order_index
        for checkpoint in checkpoints:
            if checkpoint.step_id:
                step = self.db.query(WorkflowStep).filter(WorkflowStep.id == checkpoint.step_id).first()
                if step and step.step_number < node.order_index:
                    return checkpoint

        # Fallback to initial checkpoint
        return checkpoints[-1] if checkpoints else None

    def _reset_downstream_nodes(self, start_node_id: str):
        """Reset all nodes after start_node to PENDING."""
        start_node = self.db.query(DAGNode).filter(
            DAGNode.id == start_node_id,
            DAGNode.run_id == self.run_id
        ).first()

        if not start_node:
            # Try resolving as original node ID
            start_node = DAGNode.resolve_node_id(self.db, start_node_id, self.run_id)

        if not start_node:
            logger.warning(f"Start node {start_node_id} not found")
            return

        # Get all nodes with order_index >= start_node.order_index
        downstream_nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == self.run_id,
            DAGNode.order_index >= start_node.order_index
        ).all()

        for node in downstream_nodes:
            node.status = "pending"
            if node.meta:
                node.meta["reset_at"] = datetime.now(timezone.utc).isoformat()
                node.meta["reset_for_replay"] = True

        # Also reset corresponding workflow steps
        for node in downstream_nodes:
            # Find corresponding step by order_index (if it exists)
            steps = self.db.query(WorkflowStep).filter(
                WorkflowStep.run_id == self.run_id,
                WorkflowStep.step_number >= start_node.order_index
            ).all()

            for step in steps:
                step.status = "pending"
                if step.meta:
                    step.meta["reset_at"] = datetime.now(timezone.utc).isoformat()

        self.db.commit()
        logger.info(f"Reset {len(downstream_nodes)} nodes to PENDING status")

    def get_resumable_nodes(self) -> list[Dict[str, Any]]:
        """
        Get list of nodes that can be resumed from.

        Returns:
            List of nodes with their status and metadata
        """
        nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == self.run_id
        ).order_by(DAGNode.order_index).all()

        resumable_nodes = []
        for node in nodes:
            # Check if there's a checkpoint before this node
            checkpoint = self._find_checkpoint_before_node(node.id)

            # Return original node ID from meta if available
            original_id = node.id
            if node.meta and isinstance(node.meta, dict) and "id" in node.meta:
                original_id = node.meta["id"]

            resumable_nodes.append({
                "node_id": original_id,
                "order_index": node.order_index,
                "node_type": node.node_type,
                "agent": node.agent,
                "status": node.status,
                "has_checkpoint": checkpoint is not None,
                "can_resume": checkpoint is not None or node.order_index == 0
            })

        return resumable_nodes
