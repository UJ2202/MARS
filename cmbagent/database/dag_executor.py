"""
DAG Executor - Execute Workflow DAG with Parallel Support

This module executes DAG nodes in the correct order, supporting parallel execution
of independent nodes with advanced features:
- LLM-based dependency analysis
- Isolated work directories
- Resource management
- Configurable execution modes
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Callable, Any, Optional
from sqlalchemy.orm import Session

from cmbagent.database.models import DAGNode, WorkflowStep
from cmbagent.database.topological_sort import TopologicalSorter
from cmbagent.database.state_machine import StateMachine
from cmbagent.database.states import StepState, WorkflowState

# Import new parallel execution components
from cmbagent.execution.dependency_analyzer import DependencyAnalyzer
from cmbagent.execution.parallel_executor import ParallelExecutor
from cmbagent.execution.work_directory_manager import WorkDirectoryManager
from cmbagent.execution.resource_manager import ResourceManager
from cmbagent.execution.config import ExecutionConfig, get_config

logger = logging.getLogger(__name__)


class DAGExecutor:
    """Executes workflow DAG with parallel execution support"""

    def __init__(
        self,
        db_session: Session,
        session_id: str,
        max_parallel: int = 3,
        work_dir: Optional[str] = None,
        config: Optional[ExecutionConfig] = None,
        emit_event_callback: Optional[Callable] = None
    ):
        """
        Initialize DAG executor

        Args:
            db_session: SQLAlchemy database session
            session_id: Current session ID
            max_parallel: Maximum number of parallel executions (default: 3)
            work_dir: Base work directory for task execution
            config: Execution configuration (uses global config if None)
            emit_event_callback: Optional callback for emitting DAG node events.
                Signature: (run_id: str, node_id: str, old_status: str, new_status: str, error: Optional[str]) -> None
        """
        self.db = db_session
        self.session_id = session_id
        self.max_parallel = max_parallel
        self.work_dir = work_dir or "/tmp/cmbagent"
        self._emit_event_callback = emit_event_callback

        # Load configuration
        self.config = config or get_config()

        # Initialize existing components
        self.sorter = TopologicalSorter(db_session)
        self.step_sm = StateMachine(db_session, "workflow_step")
        self.workflow_sm = StateMachine(db_session, "workflow_run")

        # Initialize new parallel execution components (Stage 8)
        self.dependency_analyzer = None
        self.parallel_executor = None
        self.work_dir_manager = None
        self.resource_manager = None

        # Initialize if parallel execution enabled
        if self.config.enable_parallel_execution:
            try:
                self.dependency_analyzer = DependencyAnalyzer()
                self.parallel_executor = ParallelExecutor(
                    max_workers=self.config.max_parallel_workers,
                    resource_limits={
                        "max_memory_per_worker_mb": self.config.max_memory_per_worker_mb,
                        "max_disk_per_worker_mb": self.config.max_disk_per_worker_mb,
                        "timeout_seconds": self.config.task_timeout_seconds
                    },
                    use_processes=self.config.use_process_pool
                )
                self.resource_manager = ResourceManager(
                    max_concurrent_agents=self.config.max_parallel_workers
                )
                logger.info("Advanced parallel execution components initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize parallel execution components: {e}")
                logger.warning("Falling back to basic parallel execution")
                self.config.enable_parallel_execution = False

    def execute(
        self,
        run_id: str,
        agent_executor_func: Callable[[str, str, str], Any]
    ) -> Dict[str, Any]:
        """
        Execute DAG for workflow run

        Args:
            run_id: Workflow run ID
            agent_executor_func: Function to execute agent nodes
                                 Signature: func(node_id, agent, task) -> result

        Returns:
            Dictionary with execution results
        """
        logger.info(f"Starting DAG execution for run {run_id}")

        # Get execution order
        try:
            execution_order = self.sorter.get_execution_order(run_id)
        except Exception as e:
            logger.error(f"Failed to compute execution order: {e}")
            raise

        results = {
            "run_id": run_id,
            "levels_executed": 0,
            "nodes_executed": 0,
            "nodes_failed": 0,
            "level_results": []
        }

        # Execute level by level
        for level_info in execution_order:
            level_idx = level_info["level"]
            level_nodes = level_info["nodes"]
            is_parallel = level_info["parallel"]

            logger.info(
                f"Executing level {level_idx} with {len(level_nodes)} nodes "
                f"(parallel={is_parallel})"
            )

            try:
                if is_parallel and len(level_nodes) <= self.max_parallel:
                    # Execute nodes in parallel
                    level_result = self._execute_parallel(
                        level_nodes,
                        agent_executor_func
                    )
                else:
                    # Execute nodes sequentially
                    level_result = self._execute_sequential(
                        level_nodes,
                        agent_executor_func
                    )

                results["level_results"].append(level_result)
                results["levels_executed"] += 1
                results["nodes_executed"] += level_result["nodes_completed"]
                results["nodes_failed"] += level_result["nodes_failed"]

                # Stop if any node in level failed (unless configured otherwise)
                if level_result["nodes_failed"] > 0:
                    logger.warning(
                        f"Level {level_idx} had {level_result['nodes_failed']} failures"
                    )
                    # For now, continue execution (can be made configurable)

            except Exception as e:
                logger.error(f"Level {level_idx} execution failed: {e}")
                results["error"] = str(e)
                break

        logger.info(
            f"DAG execution complete: {results['nodes_executed']} nodes executed, "
            f"{results['nodes_failed']} failed"
        )

        return results

    def execute_with_enhanced_parallelism(
        self,
        run_id: str,
        agent_executor_func: Callable[[str, str, str], Any]
    ) -> Dict[str, Any]:
        """
        Execute DAG with enhanced parallel execution (Stage 8 features)

        Uses:
        - LLM-based dependency analysis
        - Isolated work directories
        - Resource management
        - Advanced parallel execution

        Args:
            run_id: Workflow run ID
            agent_executor_func: Function to execute agent nodes

        Returns:
            Dictionary with execution results
        """
        logger.info(f"Starting enhanced DAG execution for run {run_id}")

        # Initialize work directory manager
        if self.config.create_isolated_directories:
            self.work_dir_manager = WorkDirectoryManager(self.work_dir, run_id)

        # Get execution order
        try:
            execution_order = self.sorter.get_execution_order(run_id)
        except Exception as e:
            logger.error(f"Failed to compute execution order: {e}")
            raise

        results = {
            "run_id": run_id,
            "levels_executed": 0,
            "nodes_executed": 0,
            "nodes_failed": 0,
            "level_results": [],
            "execution_mode": self.config.execution_mode
        }

        # Execute level by level with enhanced parallelism
        for level_info in execution_order:
            level_idx = level_info["level"]
            level_nodes = level_info["nodes"]
            is_parallel = level_info["parallel"]

            # Determine execution mode for this level
            should_parallelize = (
                is_parallel and
                len(level_nodes) > 1 and
                len(level_nodes) <= self.config.max_parallel_workers and
                self.config.execution_mode != "sequential"
            )

            logger.info(
                f"Executing level {level_idx} with {len(level_nodes)} nodes "
                f"(parallel={should_parallelize})"
            )

            try:
                if should_parallelize and self.parallel_executor:
                    # Use enhanced parallel execution
                    level_result = self._execute_parallel_enhanced(
                        level_nodes,
                        agent_executor_func,
                        run_id
                    )
                else:
                    # Use sequential execution
                    level_result = self._execute_sequential(
                        level_nodes,
                        agent_executor_func
                    )

                results["level_results"].append(level_result)
                results["levels_executed"] += 1
                results["nodes_executed"] += level_result["nodes_completed"]
                results["nodes_failed"] += level_result["nodes_failed"]

                # Handle failures
                if level_result["nodes_failed"] > 0:
                    logger.warning(
                        f"Level {level_idx} had {level_result['nodes_failed']} failures"
                    )

            except Exception as e:
                logger.error(f"Level {level_idx} execution failed: {e}")
                results["error"] = str(e)
                break

        # Merge parallel results if work directory manager was used
        if self.work_dir_manager and self.config.merge_parallel_results:
            try:
                all_node_ids = [
                    node["id"] for level in execution_order
                    for node in level["nodes"]
                ]
                self.work_dir_manager.merge_parallel_results(
                    all_node_ids,
                    preserve_structure=self.config.preserve_node_structure
                )
            except Exception as e:
                logger.warning(f"Failed to merge parallel results: {e}")

        # Cleanup if configured
        if self.work_dir_manager and self.config.cleanup_temp_files:
            self.work_dir_manager.cleanup_all(keep_outputs=self.config.keep_outputs)

        logger.info(
            f"Enhanced DAG execution complete: {results['nodes_executed']} nodes executed, "
            f"{results['nodes_failed']} failed"
        )

        return results

    def _execute_parallel_enhanced(
        self,
        nodes: List[Dict[str, Any]],
        agent_executor_func: Callable,
        run_id: str
    ) -> Dict[str, Any]:
        """
        Execute nodes using enhanced parallel executor (Stage 8)

        Args:
            nodes: List of node info dictionaries
            agent_executor_func: Function to execute agent nodes
            run_id: Workflow run ID

        Returns:
            Dictionary with execution results for this level
        """
        level_result = {
            "nodes_completed": 0,
            "nodes_failed": 0,
            "node_results": []
        }

        # Create isolated work directories
        if self.work_dir_manager:
            for node_info in nodes:
                self.work_dir_manager.create_node_directory(node_info["id"])

        # Create node executor wrapper
        def node_executor_wrapper(node_id: str) -> Any:
            """Wrapper to execute single node"""
            # Find node info
            node_info = next((n for n in nodes if n["id"] == node_id), None)
            if not node_info:
                raise ValueError(f"Node {node_id} not found")

            # Execute node
            return self._execute_node(node_info, agent_executor_func)

        # Extract node IDs
        node_ids = [node["id"] for node in nodes]

        # Execute in parallel using ParallelExecutor
        try:
            parallel_results = self.parallel_executor.execute_dag_levels_sync(
                levels=[node_ids],  # Single level
                executor_func=node_executor_wrapper,
                skip_single_task_parallelism=True
            )

            # Process results
            for node_id, result in parallel_results.items():
                level_result["node_results"].append(result.get("result", result))
                if result.get("status") == "success":
                    level_result["nodes_completed"] += 1
                else:
                    level_result["nodes_failed"] += 1

        except Exception as e:
            logger.error(f"Enhanced parallel execution failed: {e}")
            # Fallback to sequential
            logger.info("Falling back to sequential execution")
            return self._execute_sequential(nodes, agent_executor_func)

        return level_result

    def _execute_sequential(
        self,
        nodes: List[Dict[str, Any]],
        agent_executor_func: Callable
    ) -> Dict[str, Any]:
        """
        Execute nodes one at a time

        Args:
            nodes: List of node info dictionaries
            agent_executor_func: Function to execute agent nodes

        Returns:
            Dictionary with execution results for this level
        """
        level_result = {
            "nodes_completed": 0,
            "nodes_failed": 0,
            "node_results": []
        }

        for node_info in nodes:
            try:
                result = self._execute_node(node_info, agent_executor_func)
                level_result["node_results"].append(result)
                if result["status"] == "completed":
                    level_result["nodes_completed"] += 1
                else:
                    level_result["nodes_failed"] += 1
            except Exception as e:
                logger.error(f"Node {node_info['id']} failed: {e}")
                level_result["nodes_failed"] += 1
                level_result["node_results"].append({
                    "node_id": node_info["id"],
                    "status": "failed",
                    "error": str(e)
                })

        return level_result

    def _execute_parallel(
        self,
        nodes: List[Dict[str, Any]],
        agent_executor_func: Callable
    ) -> Dict[str, Any]:
        """
        Execute nodes in parallel using thread pool

        Args:
            nodes: List of node info dictionaries
            agent_executor_func: Function to execute agent nodes

        Returns:
            Dictionary with execution results for this level
        """
        level_result = {
            "nodes_completed": 0,
            "nodes_failed": 0,
            "node_results": []
        }

        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            # Submit all nodes for execution
            future_to_node = {
                executor.submit(
                    self._execute_node,
                    node_info,
                    agent_executor_func
                ): node_info
                for node_info in nodes
            }

            # Wait for all to complete
            for future in as_completed(future_to_node):
                node_info = future_to_node[future]
                try:
                    result = future.result()
                    level_result["node_results"].append(result)
                    if result["status"] == "completed":
                        level_result["nodes_completed"] += 1
                    else:
                        level_result["nodes_failed"] += 1
                except Exception as e:
                    logger.error(f"Node {node_info['id']} failed: {e}")
                    level_result["nodes_failed"] += 1
                    level_result["node_results"].append({
                        "node_id": node_info["id"],
                        "status": "failed",
                        "error": str(e)
                    })

        return level_result

    def _execute_node(
        self,
        node_info: Dict[str, Any],
        agent_executor_func: Callable
    ) -> Dict[str, Any]:
        """
        Execute single DAG node

        Args:
            node_info: Node information dictionary
            agent_executor_func: Function to execute agent nodes

        Returns:
            Dictionary with node execution result
        """
        node_id = node_info["id"]
        node_type = node_info["type"]

        logger.debug(f"Executing node {node_id} (type={node_type})")

        # Skip planning and terminator nodes
        if node_type in ["planning", "terminator"]:
            logger.debug(f"Skipping {node_type} node {node_id}")
            return {
                "node_id": node_id,
                "node_type": node_type,
                "status": "skipped"
            }

        # For AGENT nodes, execute via agent
        if node_type == "agent":
            return self._execute_agent_node(node_id, node_info, agent_executor_func)

        # For APPROVAL nodes, wait for approval (placeholder)
        elif node_type == "approval":
            return self._handle_approval_node(node_id, node_info)

        # Unknown node type
        else:
            logger.warning(f"Unknown node type: {node_type}")
            return {
                "node_id": node_id,
                "node_type": node_type,
                "status": "skipped",
                "reason": "unknown_node_type"
            }

    def _execute_agent_node(
        self,
        node_id: str,
        node_info: Dict[str, Any],
        agent_executor_func: Callable
    ) -> Dict[str, Any]:
        """
        Execute an agent node

        Args:
            node_id: Node ID
            node_info: Node information
            agent_executor_func: Function to execute agent

        Returns:
            Node execution result
        """
        # Create workflow_step for this node
        step = self._create_step_for_node(node_id, node_info)

        # Get node from database
        node = self.db.query(DAGNode).filter(DAGNode.id == node_id).first()

        # Emit node status change: pending -> running
        self._emit_dag_node_event(
            run_id=str(node.run_id),
            node_id=node_id,
            old_status="pending",
            new_status="running"
        )

        # Transition to RUNNING
        self.step_sm.transition_to(
            step.id,
            StepState.RUNNING,
            reason=f"Executing DAG node {node_id}"
        )

        # Update node status
        node.status = "running"
        self.db.commit()

        try:
            # Execute agent
            agent = node_info["agent"]
            task = node_info["metadata"].get("task_description", "")

            logger.info(f"Executing agent '{agent}' for node {node_id}")
            result = agent_executor_func(node_id, agent, task)

            # Store result
            step.outputs = result if isinstance(result, dict) else {"result": result}
            self.db.commit()

            # Transition to COMPLETED
            self.step_sm.transition_to(
                step.id,
                StepState.COMPLETED,
                reason="Node execution successful"
            )

            # Update node status
            node.status = "completed"
            self.db.commit()

            # Emit node status change: running -> completed
            self._emit_dag_node_event(
                run_id=str(node.run_id),
                node_id=node_id,
                old_status="running",
                new_status="completed"
            )

            logger.info(f"Node {node_id} completed successfully")

            return {
                "node_id": node_id,
                "node_type": "agent",
                "agent": agent,
                "status": "completed",
                "step_id": step.id,
                "result": result
            }

        except Exception as e:
            logger.error(f"Node {node_id} execution failed: {e}")

            # Transition to FAILED
            step.error_message = str(e)
            self.db.commit()

            self.step_sm.transition_to(
                step.id,
                StepState.FAILED,
                reason=f"Node execution failed: {str(e)}"
            )

            # Update node status
            node.status = "failed"
            self.db.commit()

            # Emit node status change: running -> failed
            self._emit_dag_node_event(
                run_id=str(node.run_id),
                node_id=node_id,
                old_status="running",
                new_status="failed",
                error=str(e)
            )

            return {
                "node_id": node_id,
                "node_type": "agent",
                "agent": node_info["agent"],
                "status": "failed",
                "step_id": step.id,
                "error": str(e)
            }

    def _create_step_for_node(
        self,
        node_id: str,
        node_info: Dict[str, Any]
    ) -> WorkflowStep:
        """
        Create workflow_step for DAG node

        Args:
            node_id: Node ID
            node_info: Node information

        Returns:
            Created WorkflowStep instance
        """
        # Get node from database
        node = self.db.query(DAGNode).filter(DAGNode.id == node_id).first()

        step = WorkflowStep(
            run_id=node.run_id,
            session_id=self.session_id,
            step_number=node.order_index,
            agent=node.agent,
            status=StepState.PENDING,
            inputs=node.meta
        )
        self.db.add(step)
        self.db.commit()

        return step

    def _handle_approval_node(
        self,
        node_id: str,
        node_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle approval node - placeholder for Stage 6 (HITL)

        Args:
            node_id: Node ID
            node_info: Node information

        Returns:
            Node execution result
        """
        logger.info(f"Approval node {node_id} - skipping (HITL not yet implemented)")

        return {
            "node_id": node_id,
            "node_type": "approval",
            "status": "skipped",
            "reason": "hitl_not_implemented"
        }

    def pause_execution(self, run_id: str) -> bool:
        """
        Pause DAG execution (placeholder)

        Args:
            run_id: Workflow run ID

        Returns:
            True if paused successfully
        """
        # This will be implemented with proper pause/resume in later stages
        logger.warning("Pause execution not yet fully implemented")
        return False

    def resume_execution(self, run_id: str) -> bool:
        """
        Resume DAG execution (placeholder)

        Args:
            run_id: Workflow run ID

        Returns:
            True if resumed successfully
        """
        # This will be implemented with proper pause/resume in later stages
        logger.warning("Resume execution not yet fully implemented")
        return False

    def _emit_dag_node_event(
        self,
        run_id: str,
        node_id: str,
        old_status: str,
        new_status: str,
        error: Optional[str] = None
    ) -> None:
        """
        Emit DAG node status change event via callback.

        Args:
            run_id: Workflow run ID
            node_id: Node ID
            old_status: Previous status
            new_status: New status
            error: Optional error message
        """
        if not self._emit_event_callback:
            return
        try:
            self._emit_event_callback(run_id, node_id, old_status, new_status, error)
        except Exception as e:
            # Don't fail DAG execution if event emission fails
            logger.warning(f"Failed to emit DAG node event for {node_id}: {e}")
