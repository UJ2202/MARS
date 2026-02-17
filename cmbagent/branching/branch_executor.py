"""
Branch executor for executing workflow branches with new planning and context.

This module handles the execution of branches where:
1. Context from the parent workflow is preserved
2. A NEW planning phase is triggered with user's new instructions
3. The planner is aware of completed work and available files
"""

import os
import json
import logging
import contextvars
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable

from cmbagent.database.models import (
    WorkflowRun, WorkflowStep, DAGNode, Checkpoint, Branch
)

logger = logging.getLogger(__name__)


class BranchExecutor:
    """Executor for running workflow branches with context-aware new planning."""

    def __init__(self, db_session, branch_run_id: str):
        """
        Initialize branch executor.

        Args:
            db_session: SQLAlchemy database session
            branch_run_id: ID of the branch workflow run to execute
        """
        self.db = db_session
        self.branch_run_id = branch_run_id
        self._branch_run = None
        self._parent_run = None
        self._branch_record = None

    @property
    def branch_run(self) -> WorkflowRun:
        """Get branch workflow run."""
        if self._branch_run is None:
            self._branch_run = self.db.query(WorkflowRun).filter(
                WorkflowRun.id == self.branch_run_id
            ).first()
        return self._branch_run

    @property
    def parent_run(self) -> Optional[WorkflowRun]:
        """Get parent workflow run."""
        if self._parent_run is None and self.branch_run:
            self._parent_run = self.db.query(WorkflowRun).filter(
                WorkflowRun.id == self.branch_run.branch_parent_id
            ).first()
        return self._parent_run

    @property
    def branch_record(self) -> Optional[Branch]:
        """Get branch relationship record."""
        if self._branch_record is None:
            self._branch_record = self.db.query(Branch).filter(
                Branch.child_run_id == self.branch_run_id
            ).first()
        return self._branch_record

    def build_execution_context(self) -> Dict[str, Any]:
        """
        Build the complete execution context for the branch.

        This includes:
        - Augmented task with context summary
        - Plan instructions with branch-specific guidance
        - Work directory with copied files
        - Loaded context from checkpoint

        Returns:
            Dict containing all execution parameters
        """
        if not self.branch_run:
            raise ValueError(f"Branch run {self.branch_run_id} not found")

        # Get branch metadata
        branch_meta = self.branch_run.meta or {}
        branch_name = branch_meta.get("branch_name", "unnamed-branch")
        hypothesis = branch_meta.get("hypothesis", "")
        new_instructions = branch_meta.get("new_instructions", "")
        modifications = branch_meta.get("modifications", {})

        # Load checkpoint context
        checkpoint_context = self._load_checkpoint_context()

        # Build completed work summary
        completed_work_summary = self._build_completed_work_summary()

        # Build available files list
        available_files = self._get_available_files()

        # Build augmented task
        augmented_task = self._build_augmented_task(
            original_task=self.branch_run.task_description or "",
            completed_work_summary=completed_work_summary,
            available_files=available_files,
            new_instructions=new_instructions,
            hypothesis=hypothesis
        )

        # Build plan instructions
        plan_instructions = self._build_plan_instructions(
            branch_name=branch_name,
            hypothesis=hypothesis,
            new_instructions=new_instructions,
            completed_steps_count=len(self._get_completed_steps())
        )

        # Get work directory
        work_dir = branch_meta.get("work_dir", "")

        # Save context file in work directory for reference
        if work_dir and os.path.exists(work_dir):
            self._save_branch_context_file(work_dir, checkpoint_context, completed_work_summary)

        return {
            "augmented_task": augmented_task,
            "original_task": self.branch_run.task_description,
            "plan_instructions": plan_instructions,
            "work_dir": work_dir,
            "checkpoint_context": checkpoint_context,
            "branch_name": branch_name,
            "hypothesis": hypothesis,
            "new_instructions": new_instructions,
            "modifications": modifications,
            "completed_work_summary": completed_work_summary,
            "available_files": available_files,
            "parent_run_id": str(self.branch_run.branch_parent_id) if self.branch_run.branch_parent_id else None,
            "branch_run_id": self.branch_run_id
        }

    def _load_checkpoint_context(self) -> Dict[str, Any]:
        """Load context from the branch's initial checkpoint."""
        # First try to find branch_initial checkpoint
        checkpoint = self.db.query(Checkpoint).filter(
            Checkpoint.run_id == self.branch_run_id,
            Checkpoint.checkpoint_type == "branch_initial"
        ).first()

        if checkpoint and checkpoint.context_snapshot:
            return checkpoint.context_snapshot

        # Fallback: load from parent's checkpoint at branch point
        if self.branch_record:
            parent_checkpoint = self.db.query(Checkpoint).filter(
                Checkpoint.step_id == self.branch_record.parent_step_id
            ).order_by(Checkpoint.created_at.desc()).first()

            if parent_checkpoint and parent_checkpoint.context_snapshot:
                return parent_checkpoint.context_snapshot

        return {}

    def _get_completed_steps(self) -> List[WorkflowStep]:
        """Get list of completed steps from parent workflow up to branch point."""
        if not self.branch_record:
            return []

        parent_step = self.db.query(WorkflowStep).filter(
            WorkflowStep.id == self.branch_record.parent_step_id
        ).first()

        if not parent_step:
            return []

        # Get all completed steps up to and including branch point
        completed_steps = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == self.branch_record.parent_run_id,
            WorkflowStep.step_number <= parent_step.step_number,
            WorkflowStep.status == "completed"
        ).order_by(WorkflowStep.step_number).all()

        return completed_steps

    def _build_completed_work_summary(self) -> str:
        """Build a summary of completed work from parent workflow."""
        completed_steps = self._get_completed_steps()

        if not completed_steps:
            return "No previous steps completed."

        lines = []
        for step in completed_steps:
            step_desc = step.goal or step.summary or f"Step {step.step_number}"
            status_icon = "[DONE]"

            # Include summary if available
            if step.summary:
                lines.append(f"  - Step {step.step_number}: {step_desc}")
                lines.append(f"    Summary: {step.summary[:200]}...")
            else:
                lines.append(f"  - Step {step.step_number} {status_icon}: {step_desc}")

            # Include key outputs if available
            if step.outputs:
                outputs = step.outputs
                if isinstance(outputs, dict):
                    for key, value in list(outputs.items())[:3]:
                        if isinstance(value, str) and len(value) < 100:
                            lines.append(f"    Output [{key}]: {value}")

        return "\n".join(lines)

    def _get_available_files(self) -> List[Dict[str, str]]:
        """Get list of files available in branch work directory."""
        branch_meta = self.branch_run.meta or {}
        work_dir = branch_meta.get("work_dir", "")

        if not work_dir or not os.path.exists(work_dir):
            return []

        files = []
        for root, dirs, filenames in os.walk(work_dir):
            # Skip hidden directories and __pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']

            for filename in filenames:
                if filename.startswith('.'):
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, work_dir)

                # Get file info
                try:
                    stat = os.stat(filepath)
                    size_kb = stat.st_size / 1024
                    files.append({
                        "path": rel_path,
                        "size": f"{size_kb:.1f}KB",
                        "type": self._get_file_type(filename)
                    })
                except OSError:
                    pass

        return files[:50]  # Limit to 50 files

    def _get_file_type(self, filename: str) -> str:
        """Determine file type from extension."""
        ext = os.path.splitext(filename)[1].lower()
        type_map = {
            '.py': 'code',
            '.ipynb': 'notebook',
            '.csv': 'data',
            '.json': 'data',
            '.parquet': 'data',
            '.png': 'plot',
            '.jpg': 'plot',
            '.pdf': 'report',
            '.md': 'documentation',
            '.txt': 'text',
            '.html': 'report'
        }
        return type_map.get(ext, 'other')

    def _build_augmented_task(
        self,
        original_task: str,
        completed_work_summary: str,
        available_files: List[Dict[str, str]],
        new_instructions: str,
        hypothesis: str
    ) -> str:
        """
        Build augmented task string with full context for planner.

        This is the main mechanism for passing context to the planning phase.
        The planner will see this as the task and understand:
        - What the original goal was
        - What has already been done (DO NOT REPEAT)
        - What files are available
        - What new approach to try
        """
        # Format available files
        if available_files:
            files_list = "\n".join([
                f"  - {f['path']} ({f['type']}, {f['size']})"
                for f in available_files[:20]
            ])
            if len(available_files) > 20:
                files_list += f"\n  ... and {len(available_files) - 20} more files"
        else:
            files_list = "  (No files available yet)"

        # Build the augmented task
        augmented_task = f"""
=== BRANCH EXECUTION CONTEXT ===

This is a BRANCH workflow. You are continuing from a specific point in a previous
execution with NEW INSTRUCTIONS. Do not repeat work that has already been done.

=== ORIGINAL TASK ===
{original_task}

=== COMPLETED WORK (DO NOT REPEAT) ===
The following steps have already been completed successfully:
{completed_work_summary}

=== AVAILABLE FILES IN WORK DIRECTORY ===
These files are available from previous execution:
{files_list}

=== NEW INSTRUCTIONS FOR THIS BRANCH ===
{new_instructions if new_instructions else "(No specific new instructions - continue with original approach)"}

=== HYPOTHESIS BEING TESTED ===
{hypothesis if hypothesis else "(No specific hypothesis)"}

=== YOUR TASK ===
Based on the above context:
1. DO NOT repeat any steps that are already completed
2. Use the available files from previous execution
3. Follow the NEW INSTRUCTIONS to try a different approach
4. Plan and execute the remaining work to complete the original task

Continue from where the previous execution left off, applying the new instructions.
"""
        return augmented_task.strip()

    def _build_plan_instructions(
        self,
        branch_name: str,
        hypothesis: str,
        new_instructions: str,
        completed_steps_count: int
    ) -> str:
        """Build plan instructions for the planner."""
        instructions = f"""
IMPORTANT BRANCH CONTEXT:
- This is branch "{branch_name}" - an alternative execution path
- {completed_steps_count} steps have already been completed - DO NOT recreate them
- Files in the work directory are from the parent execution - USE them
- Focus on the NEW INSTRUCTIONS provided
"""

        if hypothesis:
            instructions += f"\nHYPOTHESIS TO TEST: {hypothesis}\n"

        if new_instructions:
            instructions += f"\nKEY CHANGES FOR THIS BRANCH:\n{new_instructions}\n"

        instructions += """
PLANNING GUIDELINES:
1. Start planning from Step 1, but acknowledge that prior work exists
2. Your first step should verify/load the existing work
3. Then proceed with the modified approach
4. Keep the plan focused on what's NEW or DIFFERENT
"""
        return instructions.strip()

    def _save_branch_context_file(
        self,
        work_dir: str,
        checkpoint_context: Dict[str, Any],
        completed_work_summary: str
    ):
        """Save branch context to a JSON file in work directory."""
        context_file = os.path.join(work_dir, ".branch_context.json")

        branch_meta = self.branch_run.meta or {}

        context_data = {
            "branch_run_id": self.branch_run_id,
            "parent_run_id": str(self.branch_run.branch_parent_id) if self.branch_run.branch_parent_id else None,
            "branch_name": branch_meta.get("branch_name"),
            "hypothesis": branch_meta.get("hypothesis"),
            "new_instructions": branch_meta.get("new_instructions"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_work_summary": completed_work_summary,
            "checkpoint_variables": {
                k: str(v)[:500] for k, v in checkpoint_context.items()
                if isinstance(v, (str, int, float, bool))
            }
        }

        try:
            with open(context_file, 'w') as f:
                json.dump(context_data, f, indent=2, default=str)
            logger.info(f"Saved branch context to {context_file}")
        except Exception as e:
            logger.error(f"Failed to save branch context file: {e}")

    def prepare_for_execution(self) -> Dict[str, Any]:
        """
        Prepare the branch for execution.

        This method:
        1. Builds the execution context
        2. Updates branch status to 'executing'
        3. Returns parameters needed to start execution

        Returns:
            Dict with execution parameters ready for task_executor
        """
        # Build execution context
        context = self.build_execution_context()

        # Update branch run status
        self.branch_run.status = "executing"
        self.branch_run.started_at = datetime.now(timezone.utc)

        if not self.branch_run.meta:
            self.branch_run.meta = {}
        self.branch_run.meta["execution_started_at"] = datetime.now(timezone.utc).isoformat()

        self.db.commit()

        # Update branch record status
        if self.branch_record:
            self.branch_record.status = "executing"
            self.db.commit()

        logger.info(f"Branch {self.branch_run_id} prepared for execution")

        return {
            "status": "ready_to_execute",
            "branch_run_id": self.branch_run_id,
            "task": context["augmented_task"],
            "original_task": context["original_task"],
            "plan_instructions": context["plan_instructions"],
            "work_dir": context["work_dir"],
            "branch_name": context["branch_name"],
            "hypothesis": context["hypothesis"],
            "parent_run_id": context["parent_run_id"],
            "config_overrides": {
                "plan_instructions": context["plan_instructions"],
                "work_dir": context["work_dir"]
            }
        }

    def get_execution_config(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get execution config with branch-specific overrides.

        Args:
            base_config: Base configuration from parent or default

        Returns:
            Config dict ready for execute_cmbagent_task
        """
        context = self.build_execution_context()

        # Start with base config
        config = base_config.copy()

        # Override with branch-specific settings
        config["workDir"] = context["work_dir"]
        config["planInstructions"] = context["plan_instructions"]

        # Apply any modifications from branch
        modifications = context.get("modifications", {})
        if "parameter_overrides" in modifications:
            config.update(modifications["parameter_overrides"])

        return config

    def execute_in_branch_context(
        self,
        fn: Callable[..., Any],
        db_session=None,
        *args,
        **kwargs,
    ) -> Any:
        """Run *fn* inside an isolated contextvars context for this branch.

        This ensures:
        - The EventCaptureManager is scoped to the branch run_id / session_id
        - The parent context's captor is untouched after the call
        - Thread-safety via ``contextvars.copy_context()``

        Args:
            fn: Callable that performs the branch workflow execution.
            db_session: Optional DB session for the EventCaptureManager.
                        Falls back to ``self.db`` if not provided.
            *args, **kwargs: Forwarded to *fn*.

        Returns:
            Whatever *fn* returns.
        """
        from cmbagent.execution.event_capture import (
            EventCaptureManager,
            set_event_captor,
        )

        session = db_session or self.db
        branch_session_id = self.branch_run.session_id if self.branch_run else ""

        ctx = contextvars.copy_context()

        def _run():
            captor = EventCaptureManager(
                db_session=session,
                run_id=self.branch_run_id,
                session_id=branch_session_id,
            )
            set_event_captor(captor)
            return fn(*args, **kwargs)

        return ctx.run(_run)
