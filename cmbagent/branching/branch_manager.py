"""
Branch manager for creating and managing workflow branches.
"""

import os
import shutil
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from cmbagent.database.models import (
    WorkflowRun, WorkflowStep, DAGNode, DAGEdge,
    Branch, Checkpoint
)

logger = logging.getLogger(__name__)


class BranchManager:
    """Manager for creating workflow branches from specific steps."""

    def __init__(self, db_session, run_id: str):
        """
        Initialize branch manager.

        Args:
            db_session: SQLAlchemy database session
            run_id: ID of the workflow run to branch from
        """
        self.db = db_session
        self.run_id = run_id

    def create_branch(
        self,
        node_id: str,
        branch_name: str,
        hypothesis: Optional[str] = None,
        new_instructions: Optional[str] = None,
        modifications: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new branch from a specific DAG node.

        Args:
            node_id: ID of DAG node to branch from (e.g., "step_1", "planning")
            branch_name: Descriptive name for branch
            hypothesis: Scientific hypothesis being tested
            new_instructions: New instructions for the branch planning phase.
                These instructions will be passed to the planner along with
                context from completed work. The planner will create a NEW
                plan based on these instructions while being aware of what
                has already been done.
            modifications: Dict of changes to apply to branch
                {
                    "context_changes": {...},
                    "parameter_overrides": {...},
                    "alternative_approach": "..."
                }

        Returns:
            new_run_id: ID of newly created branch workflow
        """
        # 1. Load parent run
        parent_run = self.db.query(WorkflowRun).filter(WorkflowRun.id == self.run_id).first()
        if not parent_run:
            raise ValueError(f"Run {self.run_id} not found")

        # 2. Find DAG node to get step number
        dag_node = DAGNode.resolve_node_id(self.db, node_id, self.run_id)

        if not dag_node:
            raise ValueError(f"DAG node {node_id} not found for run {self.run_id}")

        # 3. Find corresponding WorkflowStep by step_number matching order_index
        # DAG node order_index corresponds to WorkflowStep step_number
        parent_step = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == self.run_id,
            WorkflowStep.step_number == dag_node.order_index
        ).first()

        # If no WorkflowStep found, create a minimal one to track branch point
        if not parent_step:
            logger.warning(f"No WorkflowStep found for node {node_id} (order_index={dag_node.order_index}), creating placeholder")
            parent_step = WorkflowStep(
                run_id=self.run_id,
                session_id=parent_run.session_id,
                step_number=dag_node.order_index,
                goal=f"Branch point at {node_id}",
                summary=f"Branch created from DAG node {node_id}",
                status=dag_node.status or "pending",
                meta={"created_for_branch": True, "dag_node_id": node_id}
            )
            self.db.add(parent_step)
            self.db.commit()
            self.db.refresh(parent_step)

        # 4. Load checkpoint at branch point
        checkpoint = self.db.query(Checkpoint).filter(
            Checkpoint.step_id == str(parent_step.id)
        ).order_by(Checkpoint.created_at.desc()).first()

        if not checkpoint:
            logger.warning(f"No checkpoint found for step {parent_step.id} (node {node_id}), will create initial checkpoint")
            # Create a minimal checkpoint if none exists
            checkpoint = Checkpoint(
                run_id=self.run_id,
                step_id=str(parent_step.id),
                checkpoint_type="manual",
                context_snapshot={},
                meta={"created_for_branch": True, "dag_node_id": node_id}
            )
            self.db.add(checkpoint)
            self.db.commit()
            self.db.refresh(checkpoint)

        # 5. Create new workflow run (branch)
        branch_run = WorkflowRun(
            session_id=parent_run.session_id,
            project_id=parent_run.project_id,
            mode=parent_run.mode,
            agent=parent_run.agent,
            model=parent_run.model,
            status="draft",
            task_description=parent_run.task_description,
            is_branch=True,
            branch_parent_id=self.run_id,
            branch_depth=parent_run.branch_depth + 1,
            meta={
                "branch_name": branch_name,
                "hypothesis": hypothesis,
                "new_instructions": new_instructions,
                "branched_from_node": node_id,
                "branched_from_step": str(parent_step.id),
                "modifications": modifications or {}
            }
        )

        self.db.add(branch_run)
        self.db.commit()
        self.db.refresh(branch_run)

        # 6. Create branch relationship record
        branch = Branch(
            parent_run_id=self.run_id,
            parent_step_id=str(parent_step.id),
            child_run_id=branch_run.id,
            branch_name=branch_name,
            hypothesis=hypothesis,
            status="active",
            meta={"dag_node_id": node_id, **(modifications or {})}
        )

        self.db.add(branch)
        self.db.commit()

        # 7. Copy execution history up to branch point
        self._copy_execution_history(
            parent_run_id=self.run_id,
            child_run_id=branch_run.id,
            up_to_step=parent_step
        )

        # 8. Apply modifications to branch context
        if modifications:
            self._apply_modifications(branch_run.id, checkpoint, modifications)

        # 9. Create isolated work directory for branch
        self._create_branch_work_directory(branch_run.id, parent_run)

        logger.info(
            f"Created branch '{branch_name}' from node {node_id} (step {parent_step.id}). "
            f"New run ID: {branch_run.id}"
        )

        return str(branch_run.id)

    def _copy_execution_history(
        self,
        parent_run_id: str,
        child_run_id: str,
        up_to_step: WorkflowStep
    ):
        """Copy steps, messages, and context up to branch point."""
        # Get all steps before branch point
        parent_steps = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == parent_run_id,
            WorkflowStep.step_number <= up_to_step.step_number
        ).all()

        # Copy steps to new run
        for parent_step in parent_steps:
            child_step = WorkflowStep(
                run_id=child_run_id,
                session_id=parent_step.session_id,
                step_number=parent_step.step_number,
                goal=parent_step.goal,
                summary=parent_step.summary,
                status=parent_step.status,
                started_at=parent_step.started_at,
                completed_at=parent_step.completed_at,
                inputs=parent_step.inputs,
                outputs=parent_step.outputs,
                meta={
                    **(parent_step.meta or {}),
                    "copied_from_step": str(parent_step.id)
                }
            )
            self.db.add(child_step)

        # Copy DAG nodes, preserving status for nodes at or before branch point
        parent_nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == parent_run_id
        ).all()

        node_id_mapping = {}  # parent_id -> child_id
        branch_order = up_to_step.step_number

        for parent_node in parent_nodes:
            # Nodes at or before the branch point keep their completed status;
            # nodes after are reset to pending for re-execution.
            if parent_node.order_index <= branch_order:
                status = parent_node.status or "completed"
            else:
                status = "pending"

            child_node = DAGNode(
                run_id=child_run_id,
                session_id=parent_node.session_id,
                node_type=parent_node.node_type,
                agent=parent_node.agent,
                status=status,
                order_index=parent_node.order_index,
                meta=parent_node.meta
            )
            self.db.add(child_node)
            self.db.flush()

            node_id_mapping[parent_node.id] = child_node.id

        # Copy DAG edges with new node IDs
        if node_id_mapping:
            parent_edges = self.db.query(DAGEdge).filter(
                DAGEdge.from_node_id.in_(list(node_id_mapping.keys()))
            ).all()

            for parent_edge in parent_edges:
                if (parent_edge.from_node_id in node_id_mapping and
                    parent_edge.to_node_id in node_id_mapping):
                    child_edge = DAGEdge(
                        from_node_id=node_id_mapping[parent_edge.from_node_id],
                        to_node_id=node_id_mapping[parent_edge.to_node_id],
                        dependency_type=parent_edge.dependency_type,
                        condition=parent_edge.condition
                    )
                    self.db.add(child_edge)

        self.db.commit()

    def _apply_modifications(
        self,
        branch_run_id: str,
        checkpoint: Checkpoint,
        modifications: Dict[str, Any]
    ):
        """Apply modifications to branch execution context."""
        context = (checkpoint.context_snapshot or {}).copy()

        # Apply context changes
        if "context_changes" in modifications:
            context.update(modifications["context_changes"])

        # Apply parameter overrides
        if "parameter_overrides" in modifications:
            if "parameters" not in context:
                context["parameters"] = {}
            context["parameters"].update(modifications["parameter_overrides"])

        # Add alternative approach to context
        if "alternative_approach" in modifications:
            context["alternative_approach"] = modifications["alternative_approach"]

        # Save modified context as initial checkpoint for branch
        new_checkpoint = Checkpoint(
            run_id=branch_run_id,
            step_id=None,
            checkpoint_type="branch_initial",
            context_snapshot=context,
            meta={
                "branched_at": datetime.now(timezone.utc).isoformat(),
                "modifications_applied": True
            }
        )

        self.db.add(new_checkpoint)
        self.db.commit()

    def _create_branch_work_directory(
        self,
        branch_run_id: str,
        parent_run: WorkflowRun
    ):
        """Create isolated work directory for branch."""
        parent_work_dir = parent_run.meta.get("work_dir") if parent_run.meta else None

        if not parent_work_dir:
            logger.warning(f"Parent run {parent_run.id} has no work_dir in metadata")
            return

        branch_work_dir = f"{parent_work_dir}/branches/{branch_run_id}"
        os.makedirs(branch_work_dir, exist_ok=True)

        # Copy relevant files from parent
        for subdir in ["data", "codebase"]:
            parent_subdir = f"{parent_work_dir}/{subdir}"
            branch_subdir = f"{branch_work_dir}/{subdir}"

            if os.path.exists(parent_subdir):
                try:
                    shutil.copytree(parent_subdir, branch_subdir)
                    logger.info(f"Copied {subdir} from parent to branch")
                except Exception as e:
                    logger.error(f"Error copying {subdir}: {e}")

        # Update branch run metadata
        branch_run = self.db.query(WorkflowRun).filter(WorkflowRun.id == branch_run_id).first()
        if branch_run:
            if not branch_run.meta:
                branch_run.meta = {}
            branch_run.meta["work_dir"] = branch_work_dir
            self.db.commit()

    def get_branch_tree(self, root_run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the branch tree for a workflow run.

        Args:
            root_run_id: Root run ID (defaults to self.run_id)

        Returns:
            Tree structure showing all branches
        """
        if root_run_id is None:
            root_run_id = self.run_id

        return self._build_branch_tree(root_run_id)

    def _build_branch_tree(self, run_id: str, depth: int = 0) -> Dict[str, Any]:
        """Recursively build branch tree structure."""
        run = self.db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()

        if not run:
            return {}

        # Find child branches
        child_branches = self.db.query(Branch).filter(
            Branch.parent_run_id == run_id
        ).all()

        tree = {
            "run_id": run_id,
            "name": run.meta.get("branch_name", "main") if run.meta else "main",
            "status": run.status,
            "depth": depth,
            "hypothesis": run.meta.get("hypothesis") if run.meta else None,
            "is_branch": run.is_branch,
            "children": []
        }

        for branch in child_branches:
            child_tree = self._build_branch_tree(branch.child_run_id, depth + 1)
            tree["children"].append(child_tree)

        return tree
