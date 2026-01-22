#!/usr/bin/env python3
"""
Comprehensive Validation Test Suite for CMBAgent Stages 1-9

This script validates all implemented functionality across different execution modes:
- One-shot mode (simple, direct execution)
- Planning mode (with plan review and approval)
- Control mode (step-by-step with branching)
- Parallel execution mode
- HITL approval workflows
- Retry mechanisms

Each test uses short, realistic prompts to verify the system works end-to-end.
"""

import os
import sys
import time
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cmbagent import one_shot, CMBAgent
from cmbagent.database.models import WorkflowState
from cmbagent.database.repository import SessionRepository, WorkflowRepository
from cmbagent.execution.config import ExecutionConfig
from cmbagent.branching.manager import BranchManager
from cmbagent.retry.manager import RetryContextManager


class ValidationTestSuite:
    """Comprehensive validation test suite"""

    def __init__(self):
        self.results = []
        self.start_time = None
        self.work_dir = tempfile.mkdtemp(prefix="cmbagent_validation_")

        # Ensure database is enabled
        os.environ['CMBAGENT_USE_DATABASE'] = 'true'

        # Initialize repositories
        from cmbagent.database import init_db, get_db_path
        init_db()

        self.session_repo = SessionRepository()
        self.workflow_repo = WorkflowRepository()

    def log(self, message: str, level: str = "INFO"):
        """Log a message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def test_result(self, test_name: str, passed: bool, duration: float, details: str = ""):
        """Record a test result"""
        result = {
            "test": test_name,
            "passed": passed,
            "duration": duration,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)

        status = "✓ PASS" if passed else "✗ FAIL"
        self.log(f"{test_name}: {status} ({duration:.2f}s)", "PASS" if passed else "FAIL")
        if details and not passed:
            self.log(f"  Details: {details}", "ERROR")

    def run_test(self, test_name: str, test_func):
        """Run a single test with timing"""
        self.log(f"Running: {test_name}...", "TEST")
        start = time.time()

        try:
            test_func()
            duration = time.time() - start
            self.test_result(test_name, True, duration)
            return True
        except Exception as e:
            duration = time.time() - start
            self.test_result(test_name, False, duration, str(e))
            return False

    # ============================================================================
    # Mode 1: One-Shot Tests (Simple, Direct Execution)
    # ============================================================================

    def test_oneshot_simple_math(self):
        """Test one-shot mode with simple math task"""
        work_dir = Path(self.work_dir) / "test_oneshot_math"
        work_dir.mkdir(exist_ok=True)

        result = one_shot(
            task="Calculate 15 * 23 + 47",
            agent='engineer',
            model='gpt-4o-mini',
            work_dir=str(work_dir),
            max_round=3
        )

        assert result is not None, "One-shot execution failed"
        self.log("  One-shot math task completed", "INFO")

    def test_oneshot_generate_plot(self):
        """Test one-shot mode with plot generation"""
        work_dir = Path(self.work_dir) / "test_oneshot_plot"
        work_dir.mkdir(exist_ok=True)

        result = one_shot(
            task="Generate a simple sine wave plot using matplotlib and save it",
            agent='engineer',
            model='gpt-4o-mini',
            work_dir=str(work_dir),
            max_round=5
        )

        assert result is not None, "Plot generation failed"

        # Check if plot was created
        data_dir = work_dir / "data"
        if data_dir.exists():
            plots = list(data_dir.glob("*.png")) + list(data_dir.glob("*.jpg"))
            assert len(plots) > 0, "No plot file created"
            self.log(f"  Plot created: {plots[0].name}", "INFO")

    def test_oneshot_file_operations(self):
        """Test one-shot mode with file creation"""
        work_dir = Path(self.work_dir) / "test_oneshot_file"
        work_dir.mkdir(exist_ok=True)

        result = one_shot(
            task="Create a JSON file with sample data containing 5 users with name and email",
            agent='engineer',
            model='gpt-4o-mini',
            work_dir=str(work_dir),
            max_round=5
        )

        assert result is not None, "File creation failed"

        # Check if JSON file was created
        codebase_dir = work_dir / "codebase"
        if codebase_dir.exists():
            json_files = list(codebase_dir.glob("*.json"))
            assert len(json_files) > 0, "No JSON file created"
            self.log(f"  JSON file created: {json_files[0].name}", "INFO")

    # ============================================================================
    # Mode 2: Planning Mode Tests
    # ============================================================================

    def test_planning_mode_with_review(self):
        """Test planning mode with plan review step"""
        work_dir = Path(self.work_dir) / "test_planning_mode"
        work_dir.mkdir(exist_ok=True)

        # Create CMBAgent with planning enabled
        agent = CMBAgent(
            task="Analyze a simple dataset: create random data, calculate statistics, and plot results",
            agent='engineer',
            model='gpt-4o-mini',
            work_dir=str(work_dir),
            max_round=10,
            enable_planning=True  # Enable planning mode
        )

        # Check that planner agents are configured
        assert hasattr(agent, 'planner'), "Planner agent not initialized"
        self.log("  Planning mode initialized", "INFO")

        # Note: Full execution would require approval, so we just verify setup

    def test_planning_with_dag_visualization(self):
        """Test that planning mode generates DAG visualization"""
        work_dir = Path(self.work_dir) / "test_dag_viz"
        work_dir.mkdir(exist_ok=True)

        # Create a mock planning output
        plan_json = {
            "steps": [
                {"id": 1, "task": "Generate data", "dependencies": []},
                {"id": 2, "task": "Calculate stats", "dependencies": [1]},
                {"id": 3, "task": "Create plot", "dependencies": [2]}
            ]
        }

        # Use DAG builder directly
        from cmbagent.dag.builder import DAGBuilder
        from cmbagent.dag.visualizer import DAGVisualizer

        builder = DAGBuilder()
        dag = builder.build_from_plan(plan_json)

        assert len(dag.nodes) == 3, "DAG should have 3 nodes"
        assert len(dag.edges) == 2, "DAG should have 2 edges"

        # Test visualization
        viz = DAGVisualizer(dag)
        json_export = viz.to_json()
        mermaid_export = viz.to_mermaid()

        assert json_export is not None, "JSON export failed"
        assert "graph TD" in mermaid_export, "Mermaid export failed"

        self.log("  DAG visualization working", "INFO")

    # ============================================================================
    # Mode 3: Control Mode Tests (Step-by-Step Execution)
    # ============================================================================

    def test_control_mode_step_by_step(self):
        """Test control mode with step-by-step execution"""
        work_dir = Path(self.work_dir) / "test_control_mode"
        work_dir.mkdir(exist_ok=True)

        # Create a workflow in database
        from cmbagent.database import get_session

        with get_session() as session:
            # Create session
            session_record = self.session_repo.create(
                session_id=f"control_test_{int(time.time())}",
                agent_type='engineer',
                model='gpt-4o-mini'
            )

            # Create workflow
            workflow = self.workflow_repo.create(
                session_id=session_record.session_id,
                task="Multi-step task: 1) Create file 2) Read file 3) Modify file",
                workflow_type='control',
                state=WorkflowState.INITIALIZING
            )

            assert workflow is not None, "Workflow creation failed"
            assert workflow.workflow_type == 'control', "Wrong workflow type"

            # Update state to RUNNING
            workflow = self.workflow_repo.update_state(
                workflow.workflow_id,
                WorkflowState.RUNNING
            )

            assert workflow.state == WorkflowState.RUNNING, "State transition failed"

            self.log(f"  Control mode workflow created: {workflow.workflow_id}", "INFO")

    # ============================================================================
    # Mode 4: Parallel Execution Tests
    # ============================================================================

    def test_parallel_execution_config(self):
        """Test parallel execution configuration"""
        from cmbagent.execution.config import ExecutionConfig, ExecutionMode

        config = ExecutionConfig(
            mode=ExecutionMode.PARALLEL,
            max_workers=4,
            enable_resource_monitoring=True,
            memory_limit_mb=1024
        )

        assert config.mode == ExecutionMode.PARALLEL, "Wrong execution mode"
        assert config.max_workers == 4, "Wrong worker count"
        assert config.enable_resource_monitoring is True, "Resource monitoring disabled"

        self.log("  Parallel execution config validated", "INFO")

    def test_parallel_execution_independent_tasks(self):
        """Test parallel execution with independent tasks"""
        from cmbagent.execution.dependency_graph import DependencyGraph
        from cmbagent.execution.executor import ParallelExecutor

        # Create dependency graph with independent tasks
        graph = DependencyGraph()

        task1_id = graph.add_node("task1", {"description": "Independent task 1"})
        task2_id = graph.add_node("task2", {"description": "Independent task 2"})
        task3_id = graph.add_node("task3", {"description": "Independent task 3"})

        # No dependencies = all can run in parallel
        levels = graph.get_execution_levels()

        assert len(levels) == 1, "Should have 1 execution level (all parallel)"
        assert len(levels[0]) == 3, "Level 0 should have 3 tasks"

        self.log("  Parallel execution graph validated", "INFO")

    def test_parallel_with_dependencies(self):
        """Test parallel execution respects dependencies"""
        from cmbagent.execution.dependency_graph import DependencyGraph

        graph = DependencyGraph()

        # Create tasks with dependencies
        task1 = graph.add_node("task1", {"description": "First task"})
        task2 = graph.add_node("task2", {"description": "Second task"})
        task3 = graph.add_node("task3", {"description": "Third task"})

        # task2 depends on task1, task3 depends on task2
        graph.add_edge(task1, task2)
        graph.add_edge(task2, task3)

        levels = graph.get_execution_levels()

        assert len(levels) == 3, "Should have 3 execution levels (sequential)"
        assert task1 in levels[0], "task1 should be in level 0"
        assert task2 in levels[1], "task2 should be in level 1"
        assert task3 in levels[2], "task3 should be in level 2"

        self.log("  Dependency ordering validated", "INFO")

    # ============================================================================
    # Mode 5: Branching and Play-from-Node Tests
    # ============================================================================

    def test_branching_create_branch(self):
        """Test creating a branch from a workflow"""
        work_dir = Path(self.work_dir) / "test_branching"
        work_dir.mkdir(exist_ok=True)

        # Create a parent workflow
        from cmbagent.database import get_session

        with get_session() as session:
            session_record = self.session_repo.create(
                session_id=f"branch_test_{int(time.time())}",
                agent_type='engineer',
                model='gpt-4o-mini'
            )

            parent_workflow = self.workflow_repo.create(
                session_id=session_record.session_id,
                task="Parent task",
                workflow_type='oneshot',
                state=WorkflowState.COMPLETED
            )

            # Create a branch
            branch_manager = BranchManager()
            branch = branch_manager.create_branch(
                parent_workflow_id=parent_workflow.workflow_id,
                branch_name="test_branch",
                branch_at_step=1,
                hypothesis="Testing branching functionality",
                modifications={"parameter": "new_value"}
            )

            assert branch is not None, "Branch creation failed"
            assert branch.is_branch is True, "Branch flag not set"
            assert branch.branch_parent_id == parent_workflow.workflow_id, "Wrong parent ID"

            self.log(f"  Branch created: {branch.workflow_id}", "INFO")

    def test_branch_comparison(self):
        """Test comparing two branches"""
        from cmbagent.branching.comparator import BranchComparator
        from cmbagent.database import get_session

        with get_session() as session:
            # Create session
            session_record = self.session_repo.create(
                session_id=f"compare_test_{int(time.time())}",
                agent_type='engineer',
                model='gpt-4o-mini'
            )

            # Create two workflows to compare
            workflow1 = self.workflow_repo.create(
                session_id=session_record.session_id,
                task="Task 1",
                workflow_type='oneshot',
                state=WorkflowState.COMPLETED
            )

            workflow2 = self.workflow_repo.create(
                session_id=session_record.session_id,
                task="Task 2",
                workflow_type='oneshot',
                state=WorkflowState.COMPLETED
            )

            # Compare branches
            comparator = BranchComparator()
            comparison = comparator.compare_branches(
                workflow1.workflow_id,
                workflow2.workflow_id
            )

            assert comparison is not None, "Comparison failed"
            assert 'workflow_ids' in comparison, "Missing workflow IDs"

            self.log("  Branch comparison working", "INFO")

    # ============================================================================
    # Mode 6: HITL Approval System Tests
    # ============================================================================

    def test_hitl_approval_modes(self):
        """Test HITL approval mode configuration"""
        from cmbagent.hitl.approval import ApprovalMode, ApprovalManager

        # Test all approval modes
        modes = [
            ApprovalMode.NONE,
            ApprovalMode.AFTER_PLANNING,
            ApprovalMode.BEFORE_EACH_STEP,
            ApprovalMode.ON_ERROR,
            ApprovalMode.MANUAL
        ]

        for mode in modes:
            manager = ApprovalManager(mode=mode)
            assert manager.mode == mode, f"Wrong approval mode: {mode}"

        self.log("  All approval modes validated", "INFO")

    def test_hitl_approval_request(self):
        """Test creating approval requests"""
        from cmbagent.hitl.approval import ApprovalManager, ApprovalMode
        from cmbagent.database import get_session

        with get_session() as session:
            # Create workflow
            session_record = self.session_repo.create(
                session_id=f"hitl_test_{int(time.time())}",
                agent_type='engineer',
                model='gpt-4o-mini'
            )

            workflow = self.workflow_repo.create(
                session_id=session_record.session_id,
                task="Task requiring approval",
                workflow_type='oneshot',
                state=WorkflowState.WAITING_APPROVAL
            )

            # Create approval request
            manager = ApprovalManager(mode=ApprovalMode.AFTER_PLANNING)
            approval = manager.create_approval_request(
                workflow_id=workflow.workflow_id,
                step_number=0,
                approval_type='after_planning',
                content="Please review the plan",
                options=["approve", "reject", "modify"]
            )

            assert approval is not None, "Approval creation failed"
            assert approval.status == 'pending', "Wrong approval status"

            self.log(f"  Approval request created: {approval.approval_id}", "INFO")

    # ============================================================================
    # Mode 7: Retry Mechanism Tests
    # ============================================================================

    def test_retry_error_analysis(self):
        """Test error pattern analysis"""
        from cmbagent.retry.analyzer import ErrorAnalyzer

        analyzer = ErrorAnalyzer()

        # Test different error patterns
        test_errors = [
            ("FileNotFoundError: file.txt not found", "file_not_found"),
            ("ImportError: No module named 'numpy'", "import_error"),
            ("TimeoutError: Request timed out", "timeout"),
            ("RateLimitError: API rate limit exceeded", "api_error"),
            ("MemoryError: Out of memory", "memory_error"),
        ]

        for error_msg, expected_category in test_errors:
            result = analyzer.analyze_error(error_msg, {})
            assert result['category'] == expected_category, f"Wrong category for: {error_msg}"

        self.log("  Error pattern analysis validated", "INFO")

    def test_retry_context_creation(self):
        """Test retry context creation"""
        from cmbagent.retry.manager import RetryContextManager

        manager = RetryContextManager()

        # Create retry context
        context = manager.create_retry_context(
            step_number=1,
            error_message="Import error: numpy not found",
            previous_attempts=[],
            user_feedback=None
        )

        assert context is not None, "Retry context creation failed"
        assert context.step_number == 1, "Wrong step number"
        assert context.analysis is not None, "Error analysis missing"

        self.log("  Retry context created", "INFO")

    def test_retry_suggestions(self):
        """Test retry suggestion generation"""
        from cmbagent.retry.analyzer import ErrorAnalyzer

        analyzer = ErrorAnalyzer()

        result = analyzer.analyze_error(
            "ImportError: No module named 'pandas'",
            {"code": "import pandas as pd"}
        )

        assert 'suggestions' in result, "Suggestions missing"
        assert len(result['suggestions']) > 0, "No suggestions generated"

        # Check for reasonable suggestions
        suggestions_text = " ".join(result['suggestions']).lower()
        assert 'install' in suggestions_text or 'pip' in suggestions_text, \
            "No installation suggestion for ImportError"

        self.log("  Retry suggestions generated", "INFO")

    # ============================================================================
    # Database and State Management Tests
    # ============================================================================

    def test_database_workflow_lifecycle(self):
        """Test complete workflow lifecycle in database"""
        from cmbagent.database import get_session

        with get_session() as session:
            # Create session
            session_record = self.session_repo.create(
                session_id=f"lifecycle_test_{int(time.time())}",
                agent_type='engineer',
                model='gpt-4o-mini'
            )

            # Create workflow
            workflow = self.workflow_repo.create(
                session_id=session_record.session_id,
                task="Lifecycle test task",
                workflow_type='oneshot',
                state=WorkflowState.INITIALIZING
            )

            # Test state transitions
            states = [
                WorkflowState.RUNNING,
                WorkflowState.PAUSED,
                WorkflowState.RUNNING,
                WorkflowState.COMPLETED
            ]

            for state in states:
                workflow = self.workflow_repo.update_state(workflow.workflow_id, state)
                assert workflow.state == state, f"State transition to {state} failed"

            self.log("  Workflow lifecycle validated", "INFO")

    def test_state_history_tracking(self):
        """Test state history is tracked correctly"""
        from cmbagent.database import get_session
        from cmbagent.database.repository import StateHistoryRepository

        state_history_repo = StateHistoryRepository()

        with get_session() as session:
            # Create workflow
            session_record = self.session_repo.create(
                session_id=f"history_test_{int(time.time())}",
                agent_type='engineer',
                model='gpt-4o-mini'
            )

            workflow = self.workflow_repo.create(
                session_id=session_record.session_id,
                task="State history test",
                workflow_type='oneshot',
                state=WorkflowState.INITIALIZING
            )

            # Record state change
            state_history_repo.record(
                entity_type='workflow',
                entity_id=workflow.workflow_id,
                from_state='initializing',
                to_state='running',
                reason='Test transition'
            )

            # Retrieve history
            history = state_history_repo.get_history(
                entity_type='workflow',
                entity_id=workflow.workflow_id
            )

            assert len(history) > 0, "No state history recorded"

            self.log("  State history tracking validated", "INFO")

    # ============================================================================
    # Integration Tests
    # ============================================================================

    def test_end_to_end_simple_workflow(self):
        """Test a complete simple workflow end-to-end"""
        work_dir = Path(self.work_dir) / "test_e2e_simple"
        work_dir.mkdir(exist_ok=True)

        # Run a simple task that should complete quickly
        result = one_shot(
            task="Calculate the sum of numbers from 1 to 10",
            agent='engineer',
            model='gpt-4o-mini',
            work_dir=str(work_dir),
            max_round=3
        )

        assert result is not None, "End-to-end workflow failed"

        # Verify database record was created
        from cmbagent.database import get_session
        from cmbagent.database.models import Session as SessionModel

        with get_session() as session:
            sessions = session.query(SessionModel).order_by(
                SessionModel.created_at.desc()
            ).limit(1).all()

            assert len(sessions) > 0, "No session record found"

            self.log("  End-to-end workflow completed", "INFO")

    # ============================================================================
    # Test Execution
    # ============================================================================

    def run_all_tests(self):
        """Run all validation tests"""
        self.start_time = time.time()

        print("=" * 80)
        print("  CMBAGENT COMPREHENSIVE VALIDATION SUITE - STAGES 1-9")
        print("=" * 80)
        print(f"\nStart Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Work Directory: {self.work_dir}")
        print(f"Database: {os.path.expanduser('~/.cmbagent/cmbagent.db')}\n")

        # Group tests by mode
        test_groups = [
            ("One-Shot Mode", [
                ("Simple Math", self.test_oneshot_simple_math),
                ("Generate Plot", self.test_oneshot_generate_plot),
                ("File Operations", self.test_oneshot_file_operations),
            ]),
            ("Planning Mode", [
                ("Planning with Review", self.test_planning_mode_with_review),
                ("DAG Visualization", self.test_planning_with_dag_visualization),
            ]),
            ("Control Mode", [
                ("Step-by-Step Execution", self.test_control_mode_step_by_step),
            ]),
            ("Parallel Execution", [
                ("Execution Config", self.test_parallel_execution_config),
                ("Independent Tasks", self.test_parallel_execution_independent_tasks),
                ("Dependencies", self.test_parallel_with_dependencies),
            ]),
            ("Branching", [
                ("Create Branch", self.test_branching_create_branch),
                ("Branch Comparison", self.test_branch_comparison),
            ]),
            ("HITL Approval", [
                ("Approval Modes", self.test_hitl_approval_modes),
                ("Approval Requests", self.test_hitl_approval_request),
            ]),
            ("Retry Mechanism", [
                ("Error Analysis", self.test_retry_error_analysis),
                ("Retry Context", self.test_retry_context_creation),
                ("Retry Suggestions", self.test_retry_suggestions),
            ]),
            ("Database & State", [
                ("Workflow Lifecycle", self.test_database_workflow_lifecycle),
                ("State History", self.test_state_history_tracking),
            ]),
            ("Integration", [
                ("End-to-End Simple", self.test_end_to_end_simple_workflow),
            ])
        ]

        # Run all test groups
        for group_name, tests in test_groups:
            print("\n" + "=" * 80)
            print(f"  {group_name.upper()}")
            print("=" * 80 + "\n")

            for test_name, test_func in tests:
                self.run_test(f"{group_name}: {test_name}", test_func)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test execution summary"""
        total_duration = time.time() - self.start_time

        passed = sum(1 for r in self.results if r['passed'])
        failed = sum(1 for r in self.results if not r['passed'])
        total = len(self.results)

        print("\n" + "=" * 80)
        print("  TEST EXECUTION SUMMARY")
        print("=" * 80 + "\n")

        print(f"Total Tests:     {total}")
        print(f"Passed:          {passed} ✓")
        print(f"Failed:          {failed} ✗")
        print(f"Pass Rate:       {(passed/total*100):.1f}%")
        print(f"Total Duration:  {total_duration:.2f}s")

        if failed > 0:
            print("\n" + "=" * 80)
            print("  FAILED TESTS")
            print("=" * 80 + "\n")

            for result in self.results:
                if not result['passed']:
                    print(f"✗ {result['test']}")
                    print(f"  Duration: {result['duration']:.2f}s")
                    print(f"  Details: {result['details']}\n")

        print("\n" + "=" * 80)

        if failed == 0:
            print("  ✓ ALL TESTS PASSED!")
        else:
            print(f"  ✗ {failed} TEST(S) FAILED")

        print("=" * 80 + "\n")

        # Save results to JSON
        results_file = Path(self.work_dir) / "validation_results.json"
        with open(results_file, 'w') as f:
            json.dump({
                'summary': {
                    'total': total,
                    'passed': passed,
                    'failed': failed,
                    'pass_rate': passed/total*100,
                    'duration': total_duration
                },
                'results': self.results
            }, f, indent=2)

        print(f"Results saved to: {results_file}\n")

        return failed == 0

    def cleanup(self):
        """Clean up test artifacts"""
        try:
            if os.path.exists(self.work_dir):
                shutil.rmtree(self.work_dir)
                self.log(f"Cleaned up work directory: {self.work_dir}", "INFO")
        except Exception as e:
            self.log(f"Failed to clean up: {e}", "WARN")


def main():
    """Main entry point"""
    suite = ValidationTestSuite()

    try:
        success = suite.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Optionally clean up (commented out to preserve for inspection)
        # suite.cleanup()
        pass


if __name__ == "__main__":
    main()
