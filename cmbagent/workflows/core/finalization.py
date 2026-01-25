"""
Workflow finalization utilities for CMBAgent.

This module provides finalization logic that preserves the exact same
behavior as the original workflow implementations.
"""

import os
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

from cmbagent.workflows.core.timing import WorkflowTimer
from cmbagent.workflows.core.factory import CMBAgentFactory
from cmbagent.execution.output_collector import WorkflowOutputManager


@dataclass
class FinalizationConfig:
    """
    Configuration for workflow finalization.

    Attributes:
        display_cost: Whether to display cost report
        save_timing: Whether to save timing report
        collect_outputs: Whether to collect and finalize outputs
        cleanup_empty_dirs: Whether to remove empty directories
        timing_report_name: Base name for timing report file
        cost_name_append: Optional suffix for cost report
    """
    display_cost: bool = True
    save_timing: bool = True
    collect_outputs: bool = True
    cleanup_empty_dirs: bool = True
    timing_report_name: str = "timing_report"
    cost_name_append: Optional[str] = None


class WorkflowFinalizer:
    """
    Handles workflow finalization tasks.

    This class encapsulates the finalization patterns from:
    - one_shot.py (lines 147-202)
    - planning_control.py (lines 244-372, 568-625, 762-797, 848-893)
    - control.py (lines 142-167)

    All original behaviors are preserved:
    - Groupchat fix for display_cost
    - Cost display and saving
    - Timing report generation and saving
    - Output collection and manifest writing
    - Empty directory cleanup
    - Results dictionary building
    """

    def __init__(
        self,
        cmbagent: 'CMBAgent',
        timer: WorkflowTimer,
        output_manager: WorkflowOutputManager,
        work_dir: str,
        run_id: str,
    ):
        """
        Initialize the finalizer.

        Args:
            cmbagent: CMBAgent instance to finalize
            timer: WorkflowTimer with timing data
            output_manager: WorkflowOutputManager for output collection
            work_dir: Working directory path
            run_id: Unique run identifier
        """
        self.cmbagent = cmbagent
        self.timer = timer
        self.output_manager = output_manager
        self.work_dir = work_dir
        self.run_id = run_id

    def display_cost(self, name_append: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Display and save cost report.

        Preserves exact behavior from original workflows:
        - Ensures groupchat attribute exists
        - Calls cmbagent.display_cost()

        Args:
            name_append: Optional suffix for cost report filename

        Returns:
            Cost DataFrame or None
        """
        CMBAgentFactory.ensure_groupchat(self.cmbagent)
        return self.cmbagent.display_cost(name_append=name_append)

    def save_timing_report(
        self,
        filename_base: str = "timing_report",
        prefix: str = ""
    ) -> str:
        """
        Save timing report and return path.

        Preserves exact behavior from original workflows (e.g., one_shot.py lines 167-179).

        Args:
            filename_base: Base name for the timing file
            prefix: Optional prefix for timing keys

        Returns:
            Path to the saved timing report
        """
        timing_path = self.timer.save_report(self.work_dir, filename_base, prefix)
        print(f"\nTiming report saved to: {timing_path}")
        print(f"\nTask took {self.timer.execution_time:.4f} seconds")
        return timing_path

    def collect_outputs(self) -> Dict[str, Any]:
        """
        Collect and finalize outputs.

        Preserves exact behavior from one_shot.py lines 182-191.

        Returns:
            Dictionary with 'outputs' and 'run_id' keys
        """
        try:
            workflow_outputs = self.output_manager.finalize(write_manifest=True)
            print(f"\nCollected {workflow_outputs.total_files} output files")
            return {
                'outputs': workflow_outputs.to_dict(),
                'run_id': self.run_id
            }
        except Exception as e:
            print(f"\nWarning: Could not collect outputs: {e}")
            return {
                'outputs': None,
                'run_id': self.run_id
            }

    def cleanup_empty_dirs(self, final_context: Optional[Dict] = None) -> None:
        """
        Remove empty output directories.

        Preserves exact behavior from original workflows:
        - one_shot.py lines 194-202
        - planning_control.py lines 368-372, 620-625, 791-797, 873-882
        - control.py lines 161-167

        Args:
            final_context: Final context dictionary (uses cmbagent.final_context if None)
        """
        if final_context is None:
            final_context = self.cmbagent.final_context

        work_dir = final_context.get('work_dir', self.work_dir)

        paths = [
            os.path.join(work_dir, final_context.get('database_path', 'data')),
            os.path.join(work_dir, final_context.get('codebase_path', 'codebase')),
            os.path.join(work_dir, 'time')
        ]

        for folder in paths:
            try:
                if os.path.exists(folder) and not os.listdir(folder):
                    os.rmdir(folder)
            except OSError:
                pass  # Folder not empty or doesn't exist

    def build_results(
        self,
        extra_fields: Optional[Dict[str, Any]] = None,
        include_agents: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build standard results dictionary.

        Preserves exact behavior from original workflows.

        Args:
            extra_fields: Additional fields to add to results
            include_agents: List of agent names to include in results

        Returns:
            Results dictionary with chat_history, final_context, timing, etc.
        """
        results = {
            'chat_history': self.cmbagent.chat_result.chat_history,
            'final_context': self.cmbagent.final_context,
        }

        # Add timing information (matches original result building)
        results.update(self.timer.to_results_dict())

        # Add agent objects if requested
        if include_agents:
            for agent_name in include_agents:
                try:
                    results[agent_name] = self.cmbagent.get_agent_object_from_name(agent_name)
                except Exception:
                    results[agent_name] = None

        # Add extra fields
        if extra_fields:
            results.update(extra_fields)

        return results

    def finalize(
        self,
        config: Optional[FinalizationConfig] = None,
        extra_results: Optional[Dict[str, Any]] = None,
        include_agents: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Perform full finalization and return results.

        This is the main finalization method that performs all cleanup
        tasks and builds the final results dictionary.

        Args:
            config: FinalizationConfig (uses defaults if None)
            extra_results: Additional fields to add to results
            include_agents: List of agent names to include in results

        Returns:
            Complete results dictionary
        """
        if config is None:
            config = FinalizationConfig()

        # Display cost
        if config.display_cost:
            self.display_cost(name_append=config.cost_name_append)

        # Save timing report
        if config.save_timing:
            self.save_timing_report(filename_base=config.timing_report_name)

        # Build base results
        results = self.build_results(
            extra_fields=extra_results,
            include_agents=include_agents,
        )

        # Collect outputs
        if config.collect_outputs:
            output_info = self.collect_outputs()
            results.update(output_info)

        # Cleanup empty directories
        if config.cleanup_empty_dirs:
            self.cleanup_empty_dirs()

        return results


def finalize_one_shot(
    cmbagent: 'CMBAgent',
    timer: WorkflowTimer,
    output_manager: WorkflowOutputManager,
    work_dir: str,
    run_id: str,
) -> Dict[str, Any]:
    """
    Finalize one_shot workflow.

    This is a convenience function that performs full finalization
    for one_shot workflows with the exact same behavior as the original.

    Args:
        cmbagent: CMBAgent instance
        timer: WorkflowTimer with timing data
        output_manager: WorkflowOutputManager
        work_dir: Working directory
        run_id: Run identifier

    Returns:
        Complete results dictionary
    """
    finalizer = WorkflowFinalizer(
        cmbagent=cmbagent,
        timer=timer,
        output_manager=output_manager,
        work_dir=work_dir,
        run_id=run_id,
    )

    return finalizer.finalize(
        include_agents=[
            'engineer',
            'engineer_response_formatter',
            'researcher',
            'researcher_response_formatter',
            'plot_judge',
            'plot_debugger',
        ]
    )


def finalize_human_in_the_loop(
    cmbagent: 'CMBAgent',
    timer: WorkflowTimer,
    work_dir: str,
) -> Dict[str, Any]:
    """
    Finalize human_in_the_loop workflow.

    Args:
        cmbagent: CMBAgent instance
        timer: WorkflowTimer with timing data
        work_dir: Working directory

    Returns:
        Complete results dictionary
    """
    # Ensure groupchat exists
    CMBAgentFactory.ensure_groupchat(cmbagent)
    cmbagent.display_cost()

    results = {
        'chat_history': cmbagent.chat_result.chat_history,
        'final_context': cmbagent.final_context,
        'engineer': cmbagent.get_agent_object_from_name('engineer'),
        'engineer_nest': cmbagent.get_agent_object_from_name('engineer_nest'),
        'engineer_response_formatter': cmbagent.get_agent_object_from_name('engineer_response_formatter'),
        'researcher': cmbagent.get_agent_object_from_name('researcher'),
        'researcher_response_formatter': cmbagent.get_agent_object_from_name('researcher_response_formatter'),
    }

    results.update(timer.to_results_dict())

    # Save timing report (uses different format for human_in_the_loop)
    import datetime
    import json

    timing_report = timer.to_report()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timing_path = os.path.join(work_dir, f"timing_report_{timestamp}.json")

    with open(timing_path, 'w') as f:
        json.dump(timing_report, f, indent=2)

    return results


def finalize_control(
    cmbagent: 'CMBAgent',
    timer: WorkflowTimer,
) -> Dict[str, Any]:
    """
    Finalize control workflow.

    Args:
        cmbagent: CMBAgent instance
        timer: WorkflowTimer with timing data

    Returns:
        Complete results dictionary
    """
    import datetime
    import json

    results = {
        'chat_history': cmbagent.chat_result.chat_history,
        'final_context': cmbagent.final_context,
    }

    # Add timing with _control suffix (matches original)
    results['initialization_time_control'] = timer.get_duration('initialization')
    results['execution_time_control'] = timer.get_duration('execution')

    # Save timing report
    timing_report = {
        'initialization_time_control': timer.get_duration('initialization'),
        'execution_time_control': timer.get_duration('execution'),
        'total_time': timer.total_time,
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timing_path = os.path.join(
        results['final_context']['work_dir'],
        f"time/timing_report_control_{timestamp}.json"
    )

    os.makedirs(os.path.dirname(timing_path), exist_ok=True)
    with open(timing_path, 'w') as f:
        json.dump(timing_report, f, indent=2)

    # Ensure groupchat exists and display cost
    CMBAgentFactory.ensure_groupchat(cmbagent)
    cmbagent.display_cost()

    # Cleanup empty folders
    database_full_path = os.path.join(
        results['final_context']['work_dir'],
        results['final_context']['database_path']
    )
    codebase_full_path = os.path.join(
        results['final_context']['work_dir'],
        results['final_context']['codebase_path']
    )
    time_full_path = os.path.join(results['final_context']['work_dir'], 'time')

    for folder in [database_full_path, codebase_full_path, time_full_path]:
        try:
            if os.path.exists(folder) and not os.listdir(folder):
                os.rmdir(folder)
        except OSError:
            pass

    return results
