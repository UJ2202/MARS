"""
Branch comparator for comparing results between workflow branches.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from cmbagent.database.models import (
    WorkflowRun, WorkflowStep, Branch,
    WorkflowMetric, CostRecord
)

logger = logging.getLogger(__name__)


class BranchComparator:
    """Comparator for analyzing differences between workflow branches."""

    def __init__(self, db_session):
        """
        Initialize branch comparator.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session

    def compare_branches(self, run_id_1: str, run_id_2: str) -> Dict[str, Any]:
        """
        Compare two workflow branches.

        Args:
            run_id_1: First run ID
            run_id_2: Second run ID

        Returns:
            comparison_result: Dict with detailed comparison
        """
        run1 = self.db.query(WorkflowRun).filter(WorkflowRun.id == run_id_1).first()
        run2 = self.db.query(WorkflowRun).filter(WorkflowRun.id == run_id_2).first()

        if not run1 or not run2:
            raise ValueError(f"One or both runs not found: {run_id_1}, {run_id_2}")

        comparison = {
            "run_ids": [run_id_1, run_id_2],
            "branch_names": [
                run1.meta.get("branch_name", "main") if run1.meta else "main",
                run2.meta.get("branch_name", "main") if run2.meta else "main"
            ],
            "status": [run1.status, run2.status],
            "execution_time": [
                self._get_execution_time(run1),
                self._get_execution_time(run2)
            ],
            "total_cost": [
                self._get_total_cost(run_id_1),
                self._get_total_cost(run_id_2)
            ],
            "step_comparison": self._compare_steps(run_id_1, run_id_2),
            "output_diff": self._compare_outputs(run_id_1, run_id_2),
            "metrics_comparison": self._compare_metrics(run_id_1, run_id_2)
        }

        return comparison

    def _get_execution_time(self, run: WorkflowRun) -> Optional[float]:
        """Get execution time in seconds."""
        if run.started_at and run.completed_at:
            delta = run.completed_at - run.started_at
            return delta.total_seconds()
        return None

    def _get_total_cost(self, run_id: str) -> float:
        """Get total cost for a run."""
        cost_records = self.db.query(CostRecord).filter(
            CostRecord.run_id == run_id
        ).all()

        total_cost = sum(float(record.cost_usd) for record in cost_records)
        return total_cost

    def _compare_steps(self, run_id_1: str, run_id_2: str) -> List[Dict[str, Any]]:
        """Compare steps between two runs."""
        steps1 = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id_1
        ).order_by(WorkflowStep.step_number).all()

        steps2 = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id_2
        ).order_by(WorkflowStep.step_number).all()

        comparison = []

        max_steps = max(len(steps1), len(steps2))
        for i in range(max_steps):
            step1 = steps1[i] if i < len(steps1) else None
            step2 = steps2[i] if i < len(steps2) else None

            comparison.append({
                "step_number": i + 1,
                "branch_1": {
                    "agent": step1.agent if step1 else None,
                    "status": step1.status if step1 else None,
                    "outputs": step1.outputs if step1 else None,
                    "error": step1.error_message if step1 else None
                },
                "branch_2": {
                    "agent": step2.agent if step2 else None,
                    "status": step2.status if step2 else None,
                    "outputs": step2.outputs if step2 else None,
                    "error": step2.error_message if step2 else None
                },
                "differs": (
                    step1 and step2 and
                    step1.outputs != step2.outputs
                )
            })

        return comparison

    def _compare_outputs(self, run_id_1: str, run_id_2: str) -> Dict[str, Any]:
        """Compare final outputs between branches."""
        run1 = self.db.query(WorkflowRun).filter(WorkflowRun.id == run_id_1).first()
        run2 = self.db.query(WorkflowRun).filter(WorkflowRun.id == run_id_2).first()

        work_dir_1 = run1.meta.get("work_dir") if run1.meta else None
        work_dir_2 = run2.meta.get("work_dir") if run2.meta else None

        if not work_dir_1 or not work_dir_2:
            return {
                "error": "Work directories not found for one or both runs",
                "work_dir_1": work_dir_1,
                "work_dir_2": work_dir_2
            }

        outputs_1 = self._collect_outputs(work_dir_1)
        outputs_2 = self._collect_outputs(work_dir_2)

        diff = {
            "files_only_in_branch_1": [],
            "files_only_in_branch_2": [],
            "files_in_both": [],
            "content_diffs": {}
        }

        files1 = set(outputs_1.keys())
        files2 = set(outputs_2.keys())

        diff["files_only_in_branch_1"] = sorted(list(files1 - files2))
        diff["files_only_in_branch_2"] = sorted(list(files2 - files1))
        diff["files_in_both"] = sorted(list(files1 & files2))

        # Compare file contents for common files
        for file in diff["files_in_both"]:
            if outputs_1[file] != outputs_2[file]:
                diff["content_diffs"][file] = {
                    "branch_1_size": len(outputs_1[file]),
                    "branch_2_size": len(outputs_2[file]),
                    "branch_1_preview": outputs_1[file][:500],  # First 500 chars
                    "branch_2_preview": outputs_2[file][:500]
                }

        return diff

    def _collect_outputs(self, work_dir: str) -> Dict[str, str]:
        """Collect all output files from a work directory."""
        outputs = {}

        if not os.path.exists(work_dir):
            logger.warning(f"Work directory does not exist: {work_dir}")
            return outputs

        # Collect files from data and codebase directories
        for subdir in ["data", "codebase"]:
            subdir_path = os.path.join(work_dir, subdir)
            if os.path.exists(subdir_path):
                for root, _, files in os.walk(subdir_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, work_dir)

                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                outputs[rel_path] = f.read()
                        except Exception as e:
                            logger.debug(f"Could not read {file_path}: {e}")
                            outputs[rel_path] = f"<binary or unreadable: {e}>"

        return outputs

    def _compare_metrics(self, run_id_1: str, run_id_2: str) -> Dict[str, Any]:
        """Compare execution metrics between branches."""
        metrics1 = self.db.query(WorkflowMetric).filter(
            WorkflowMetric.run_id == run_id_1
        ).all()

        metrics2 = self.db.query(WorkflowMetric).filter(
            WorkflowMetric.run_id == run_id_2
        ).all()

        # Group by metric name
        metrics1_dict = {}
        for m in metrics1:
            if m.metric_name not in metrics1_dict:
                metrics1_dict[m.metric_name] = []
            metrics1_dict[m.metric_name].append(float(m.metric_value))

        metrics2_dict = {}
        for m in metrics2:
            if m.metric_name not in metrics2_dict:
                metrics2_dict[m.metric_name] = []
            metrics2_dict[m.metric_name].append(float(m.metric_value))

        comparison = {}
        all_metric_names = set(metrics1_dict.keys()) | set(metrics2_dict.keys())

        for metric_name in all_metric_names:
            vals1 = metrics1_dict.get(metric_name, [])
            vals2 = metrics2_dict.get(metric_name, [])

            comparison[metric_name] = {
                "branch_1": {
                    "count": len(vals1),
                    "avg": sum(vals1) / len(vals1) if vals1 else 0,
                    "min": min(vals1) if vals1 else 0,
                    "max": max(vals1) if vals1 else 0
                },
                "branch_2": {
                    "count": len(vals2),
                    "avg": sum(vals2) / len(vals2) if vals2 else 0,
                    "min": min(vals2) if vals2 else 0,
                    "max": max(vals2) if vals2 else 0
                }
            }

        return comparison

    def visualize_branch_tree(self, root_run_id: str) -> Dict[str, Any]:
        """
        Generate tree visualization of branches.

        Args:
            root_run_id: Root run ID to start from

        Returns:
            Tree structure with branches
        """
        tree = self._build_branch_tree(root_run_id)
        return tree

    def _build_branch_tree(self, root_run_id: str, depth: int = 0) -> Dict[str, Any]:
        """Recursively build branch tree structure."""
        run = self.db.query(WorkflowRun).filter(WorkflowRun.id == root_run_id).first()

        if not run:
            return {}

        # Find child branches
        child_branches = self.db.query(Branch).filter(
            Branch.parent_run_id == root_run_id
        ).all()

        tree = {
            "run_id": root_run_id,
            "name": run.meta.get("branch_name", "main") if run.meta else "main",
            "status": run.status,
            "depth": depth,
            "hypothesis": run.meta.get("hypothesis") if run.meta else None,
            "is_branch": run.is_branch,
            "branch_depth": run.branch_depth,
            "children": []
        }

        for branch in child_branches:
            child_tree = self._build_branch_tree(branch.child_run_id, depth + 1)
            if child_tree:
                tree["children"].append(child_tree)

        return tree

    def _format_tree(self, tree: Dict[str, Any], prefix: str = "") -> str:
        """Format tree as ASCII art."""
        if not tree:
            return ""

        lines = []
        name = tree.get("name", "unknown")
        status = tree.get("status", "unknown")
        hypothesis = tree.get("hypothesis", "")

        line = f"{prefix}{name} ({status})"
        if hypothesis:
            line += f" - {hypothesis[:50]}"
        lines.append(line)

        children = tree.get("children", [])
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            child_prefix = prefix + ("└── " if is_last else "├── ")
            cont_prefix = prefix + ("    " if is_last else "│   ")

            child_lines = self._format_tree(child, cont_prefix)
            lines.append(child_prefix + child_lines.split('\n')[0])
            for child_line in child_lines.split('\n')[1:]:
                if child_line:
                    lines.append(child_line)

        return '\n'.join(lines)

    def get_branch_summary(self, run_id: str) -> Dict[str, Any]:
        """
        Get summary information for a branch.

        Args:
            run_id: Run ID to summarize

        Returns:
            Summary dict with key metrics
        """
        run = self.db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()

        if not run:
            raise ValueError(f"Run {run_id} not found")

        steps = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id
        ).all()

        summary = {
            "run_id": run_id,
            "branch_name": run.meta.get("branch_name", "main") if run.meta else "main",
            "status": run.status,
            "is_branch": run.is_branch,
            "branch_depth": run.branch_depth,
            "hypothesis": run.meta.get("hypothesis") if run.meta else None,
            "total_steps": len(steps),
            "completed_steps": len([s for s in steps if s.status == "completed"]),
            "failed_steps": len([s for s in steps if s.status == "failed"]),
            "execution_time": self._get_execution_time(run),
            "total_cost": self._get_total_cost(run_id),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None
        }

        return summary
