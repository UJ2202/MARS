# Stage 8: Dependency Analysis and Parallel Execution

**Phase:** 2 - Optimization
**Estimated Time:** 40-50 minutes
**Dependencies:** Stages 1-7 (DAG Builder, State Machine, Execution Engine) must be complete
**Risk Level:** High

## Objectives

1. Implement LLM-based dependency analysis for workflow steps
2. Build topological sort algorithm for execution ordering
3. Create parallel execution groups from independent tasks
4. Implement isolated work directories for parallel tasks
5. Add resource management for concurrent agent execution
6. Optimize execution time through intelligent parallelization
7. Ensure thread-safe and process-safe concurrent operations

## Current State Analysis

### What We Have
- Sequential execution of all workflow steps
- DAG structure with nodes and edges
- State machine for workflow and step states
- Database persistence for all execution data
- Single work directory per workflow run

### What We Need
- Intelligent dependency detection using LLM
- Topological sort to identify parallelizable groups
- Parallel execution engine with worker pool
- Isolated work directories for each parallel task
- Resource allocation and management
- Deadlock prevention mechanisms
- Progress tracking for parallel operations

## Pre-Stage Verification

### Check Prerequisites
1. Stages 1-7 complete and verified
2. DAG builder creates valid directed graphs
3. State machine handles RUNNING state transitions
4. Database can store concurrent step executions
5. Current sequential execution working perfectly

### Expected State
- DAG nodes have dependency relationships defined
- Steps execute sequentially (one at a time)
- Work directory structure supports multiple subdirectories
- Ready to add parallel execution capability

## Implementation Tasks

### Task 1: Design Dependency Analysis Prompt
**Objective:** Create LLM prompt to analyze task dependencies

**Implementation:**

Create dependency analysis system that examines task descriptions and identifies:
- Data dependencies (task B needs output from task A)
- Resource dependencies (both tasks use same file/API)
- Logical dependencies (task B builds on concepts from task A)
- Independence (tasks can run in parallel)

**Prompt Template:**
```python
DEPENDENCY_ANALYSIS_PROMPT = """
You are analyzing a scientific workflow to identify task dependencies.

Given these tasks:
{task_list}

For each pair of tasks, determine:
1. DEPENDENT: Task B must wait for Task A to complete
2. INDEPENDENT: Tasks can execute in parallel
3. CONDITIONAL: Dependency exists only under certain conditions

Consider:
- Data flow (outputs → inputs)
- File system conflicts (same file writes)
- API rate limits (same external service)
- Scientific logic (conceptual dependencies)

Return JSON:
{
  "dependencies": [
    {"from": "task_1", "to": "task_2", "type": "data", "reason": "..."},
    {"from": "task_1", "to": "task_3", "type": "none", "reason": "independent"}
  ],
  "parallel_groups": [
    ["task_2", "task_3", "task_5"],
    ["task_4"]
  ]
}
"""
```

**Files to Create:**
- `cmbagent/execution/dependency_analyzer.py`

**Verification:**
- Prompt generates valid dependency analysis
- LLM correctly identifies independent tasks
- JSON output parseable and valid
- Analysis completes in reasonable time (<30s)

### Task 2: Implement Topological Sort
**Objective:** Order tasks respecting dependencies

**Implementation:**

```python
class DependencyGraph:
    def __init__(self):
        self.nodes = {}  # node_id -> Node
        self.edges = []  # (from_id, to_id)

    def add_node(self, node_id, metadata):
        self.nodes[node_id] = {
            "id": node_id,
            "metadata": metadata,
            "in_degree": 0,
            "dependencies": []
        }

    def add_edge(self, from_id, to_id, dependency_type):
        self.edges.append((from_id, to_id, dependency_type))
        self.nodes[to_id]["in_degree"] += 1
        self.nodes[to_id]["dependencies"].append(from_id)

    def topological_sort(self):
        """
        Returns execution levels (groups that can run in parallel)

        Level 0: [nodes with no dependencies]
        Level 1: [nodes depending only on level 0]
        Level 2: [nodes depending on level 0 and/or 1]
        ...
        """
        levels = []
        remaining_nodes = set(self.nodes.keys())
        completed_nodes = set()

        while remaining_nodes:
            # Find nodes with all dependencies satisfied
            ready_nodes = [
                node_id for node_id in remaining_nodes
                if all(dep in completed_nodes
                       for dep in self.nodes[node_id]["dependencies"])
            ]

            if not ready_nodes:
                # Circular dependency detected
                raise CircularDependencyError(
                    f"Circular dependency in nodes: {remaining_nodes}"
                )

            levels.append(ready_nodes)
            completed_nodes.update(ready_nodes)
            remaining_nodes -= set(ready_nodes)

        return levels

    def detect_cycles(self):
        """Detect circular dependencies using DFS"""
        visited = set()
        rec_stack = set()

        def visit(node_id):
            if node_id in rec_stack:
                return True  # Cycle detected
            if node_id in visited:
                return False

            visited.add(node_id)
            rec_stack.add(node_id)

            for dep_id in self.nodes[node_id]["dependencies"]:
                if visit(dep_id):
                    return True

            rec_stack.remove(node_id)
            return False

        for node_id in self.nodes:
            if visit(node_id):
                return True
        return False
```

**Files to Create:**
- `cmbagent/execution/dependency_graph.py`

**Verification:**
- Topological sort produces valid execution order
- Circular dependencies detected and reported
- Parallel groups correctly identified
- Algorithm handles complex DAGs (20+ nodes)

### Task 3: Create Parallel Execution Engine
**Objective:** Execute independent tasks concurrently

**Implementation:**

```python
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Queue
import asyncio

class ParallelExecutor:
    def __init__(self, max_workers=3, resource_limits=None):
        self.max_workers = max_workers
        self.resource_limits = resource_limits or {
            "max_memory_per_worker_mb": 2000,
            "max_disk_per_worker_mb": 5000
        }
        self.active_workers = {}
        self.result_queue = Queue()

    async def execute_dag_levels(self, levels, executor_func):
        """
        Execute DAG level by level, with parallelism within each level

        levels: [[node_1, node_2], [node_3], [node_4, node_5, node_6]]
        """
        results = {}

        for level_index, node_ids in enumerate(levels):
            logger.info(f"Executing level {level_index}: {len(node_ids)} tasks")

            if len(node_ids) == 1:
                # Single task - execute directly (no parallelism overhead)
                node_id = node_ids[0]
                result = await self._execute_single_task(node_id, executor_func)
                results[node_id] = result
            else:
                # Multiple tasks - execute in parallel
                level_results = await self._execute_parallel_tasks(
                    node_ids, executor_func
                )
                results.update(level_results)

            logger.info(f"Level {level_index} complete: {len(node_ids)} tasks finished")

        return results

    async def _execute_parallel_tasks(self, node_ids, executor_func):
        """Execute multiple tasks in parallel using ProcessPoolExecutor"""
        results = {}

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_node = {
                executor.submit(
                    self._isolated_task_wrapper,
                    node_id,
                    executor_func
                ): node_id
                for node_id in node_ids
            }

            # Collect results as they complete
            for future in as_completed(future_to_node):
                node_id = future_to_node[future]
                try:
                    result = future.result(timeout=3600)  # 1 hour max per task
                    results[node_id] = result
                    logger.info(f"Task {node_id} completed successfully")
                except Exception as e:
                    logger.error(f"Task {node_id} failed: {e}")
                    results[node_id] = {
                        "status": "failed",
                        "error": str(e)
                    }

        return results

    def _isolated_task_wrapper(self, node_id, executor_func):
        """
        Wrapper that runs in separate process with isolation
        """
        import os
        import psutil

        # Create isolated work directory
        work_dir = self._get_isolated_work_dir(node_id)
        os.makedirs(work_dir, exist_ok=True)

        # Set environment variables for isolation
        os.environ['CMBAGENT_WORK_DIR'] = work_dir
        os.environ['CMBAGENT_NODE_ID'] = node_id

        try:
            # Monitor resources
            process = psutil.Process()
            start_memory = process.memory_info().rss / 1024 / 1024

            # Execute task
            result = executor_func(node_id, work_dir)

            # Check resource usage
            end_memory = process.memory_info().rss / 1024 / 1024
            memory_used = end_memory - start_memory

            if memory_used > self.resource_limits["max_memory_per_worker_mb"]:
                logger.warning(
                    f"Task {node_id} exceeded memory limit: {memory_used} MB"
                )

            return {
                "status": "success",
                "result": result,
                "resources": {
                    "memory_mb": memory_used,
                    "work_dir": work_dir
                }
            }

        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "node_id": node_id
            }

    def _get_isolated_work_dir(self, node_id):
        """Create isolated work directory for parallel task"""
        base_dir = os.getenv("CMBAGENT_WORK_DIR", "/tmp/cmbagent")
        return f"{base_dir}/parallel_tasks/{node_id}"

    async def _execute_single_task(self, node_id, executor_func):
        """Execute single task without parallelism overhead"""
        work_dir = self._get_isolated_work_dir(node_id)
        os.makedirs(work_dir, exist_ok=True)

        return executor_func(node_id, work_dir)
```

**Files to Create:**
- `cmbagent/execution/parallel_executor.py`

**Verification:**
- Multiple tasks execute simultaneously
- Process isolation prevents interference
- Resource limits enforced
- Results collected correctly
- Exceptions handled gracefully

### Task 4: Implement Isolated Work Directories
**Objective:** Each parallel task has independent file system space

**Implementation:**

```python
class WorkDirectoryManager:
    def __init__(self, base_work_dir, run_id):
        self.base_dir = base_work_dir
        self.run_id = run_id
        self.node_dirs = {}

    def create_node_directory(self, node_id):
        """
        Create isolated directory structure for parallel task

        Structure:
        work_dir/
        └── runs/
            └── run_abc123/
                ├── sequential/          # Sequential execution artifacts
                └── parallel/            # Parallel execution artifacts
                    ├── node_1/
                    │   ├── data/
                    │   ├── codebase/
                    │   ├── logs/
                    │   └── outputs/
                    ├── node_2/
                    └── node_3/
        """
        node_dir = f"{self.base_dir}/runs/{self.run_id}/parallel/{node_id}"

        # Create subdirectories
        subdirs = ["data", "codebase", "logs", "outputs", "temp"]
        for subdir in subdirs:
            os.makedirs(f"{node_dir}/{subdir}", exist_ok=True)

        self.node_dirs[node_id] = node_dir

        return node_dir

    def merge_parallel_results(self, node_ids):
        """
        Merge outputs from parallel tasks into main work directory
        """
        main_output_dir = f"{self.base_dir}/runs/{self.run_id}/sequential"

        for node_id in node_ids:
            node_dir = self.node_dirs[node_id]

            # Copy outputs to main directory
            outputs = f"{node_dir}/outputs"
            if os.path.exists(outputs):
                for file in os.listdir(outputs):
                    src = f"{outputs}/{file}"
                    dst = f"{main_output_dir}/data/{node_id}_{file}"
                    shutil.copy2(src, dst)

        logger.info(f"Merged outputs from {len(node_ids)} parallel tasks")

    def cleanup_node_directory(self, node_id, keep_outputs=True):
        """Clean up temporary files, optionally keep outputs"""
        node_dir = self.node_dirs[node_id]

        # Remove temp files
        temp_dir = f"{node_dir}/temp"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        if not keep_outputs:
            shutil.rmtree(node_dir)
            del self.node_dirs[node_id]
```

**Files to Create:**
- `cmbagent/execution/work_directory_manager.py`

**Verification:**
- Each parallel task has isolated directory
- No file system conflicts between tasks
- Outputs merged correctly
- Cleanup works without data loss

### Task 5: Add Resource Management
**Objective:** Prevent resource exhaustion from parallel execution

**Implementation:**

```python
class ResourceManager:
    def __init__(self, max_concurrent_agents=3):
        self.max_concurrent = max_concurrent_agents
        self.semaphore = asyncio.Semaphore(max_concurrent_agents)
        self.active_tasks = {}
        self.resource_stats = {
            "total_memory_mb": psutil.virtual_memory().total / 1024 / 1024,
            "available_memory_mb": psutil.virtual_memory().available / 1024 / 1024,
            "total_disk_mb": psutil.disk_usage('/').total / 1024 / 1024,
            "available_disk_mb": psutil.disk_usage('/').free / 1024 / 1024
        }

    async def acquire(self, task_id, estimated_memory_mb=500):
        """Acquire resources for task execution"""
        # Check if resources available
        if not self._check_resources_available(estimated_memory_mb):
            raise ResourceExhaustedError(
                f"Insufficient resources for task {task_id}"
            )

        # Acquire semaphore slot
        await self.semaphore.acquire()

        self.active_tasks[task_id] = {
            "started_at": datetime.utcnow(),
            "estimated_memory_mb": estimated_memory_mb
        }

        logger.info(f"Resources acquired for task {task_id}")

    def release(self, task_id):
        """Release resources after task completion"""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]

        self.semaphore.release()
        logger.info(f"Resources released for task {task_id}")

    def _check_resources_available(self, estimated_memory_mb):
        """Check if system has enough resources"""
        available = psutil.virtual_memory().available / 1024 / 1024

        # Reserve 20% for system
        safe_available = available * 0.8

        # Check if current + estimated exceeds safe limit
        current_usage = sum(
            task["estimated_memory_mb"]
            for task in self.active_tasks.values()
        )

        return (current_usage + estimated_memory_mb) < safe_available

    def get_optimal_worker_count(self):
        """Calculate optimal number of parallel workers"""
        cpu_count = psutil.cpu_count()
        available_memory_gb = psutil.virtual_memory().available / 1024 / 1024 / 1024

        # Assume each agent needs ~2GB RAM
        memory_based = int(available_memory_gb / 2)

        # Conservative: min of CPU-based and memory-based
        return min(cpu_count - 1, memory_based, self.max_concurrent)
```

**Files to Create:**
- `cmbagent/execution/resource_manager.py`

**Verification:**
- Resource limits enforced
- System doesn't run out of memory
- Optimal worker count calculated correctly
- Graceful degradation under resource pressure

### Task 6: Integrate with DAG Executor
**Objective:** Update DAG executor to use parallel execution

**Files to Modify:**
- `cmbagent/execution/dag_executor.py`

**Changes:**

```python
class DAGExecutor:
    def __init__(self, dag, db_session, run_id):
        self.dag = dag
        self.db_session = db_session
        self.run_id = run_id

        # NEW: Parallel execution components
        self.dependency_analyzer = DependencyAnalyzer()
        self.parallel_executor = ParallelExecutor(max_workers=3)
        self.work_dir_manager = WorkDirectoryManager(BASE_WORK_DIR, run_id)
        self.resource_manager = ResourceManager()

    async def execute(self, mode="auto"):
        """
        Execute DAG with automatic parallelization

        mode:
          - "sequential": Force sequential execution
          - "parallel": Force parallel execution where possible
          - "auto": Automatically decide based on dependencies
        """
        # Analyze dependencies
        dependency_graph = self.dependency_analyzer.analyze(self.dag)

        # Detect cycles
        if dependency_graph.detect_cycles():
            raise CircularDependencyError("Circular dependency detected in workflow")

        # Get execution levels (topological sort)
        execution_levels = dependency_graph.topological_sort()

        logger.info(f"Execution plan: {len(execution_levels)} levels")
        for i, level in enumerate(execution_levels):
            logger.info(f"  Level {i}: {len(level)} tasks (parallel)")

        # Execute level by level
        if mode == "sequential":
            results = await self._execute_sequential(execution_levels)
        else:
            results = await self.parallel_executor.execute_dag_levels(
                execution_levels,
                self._execute_node_wrapper
            )

        return results

    def _execute_node_wrapper(self, node_id, work_dir):
        """
        Wrapper for executing a single node (used by parallel executor)
        """
        node = self.dag.get_node(node_id)

        # Update state to RUNNING
        self.db_session.execute(
            update(DAGNode)
            .where(DAGNode.id == node_id)
            .values(status="running", started_at=datetime.utcnow())
        )
        self.db_session.commit()

        try:
            # Execute agent
            result = self._execute_agent(node, work_dir)

            # Update state to COMPLETED
            self.db_session.execute(
                update(DAGNode)
                .where(DAGNode.id == node_id)
                .values(
                    status="completed",
                    completed_at=datetime.utcnow(),
                    outputs=result
                )
            )
            self.db_session.commit()

            return result

        except Exception as e:
            # Update state to FAILED
            self.db_session.execute(
                update(DAGNode)
                .where(DAGNode.id == node_id)
                .values(
                    status="failed",
                    completed_at=datetime.utcnow(),
                    error_message=str(e)
                )
            )
            self.db_session.commit()

            raise
```

**Verification:**
- DAG executor uses parallel execution
- Dependencies respected
- State updates persisted to database
- Errors handled gracefully

### Task 7: Add Execution Mode Configuration
**Objective:** Allow users to control parallelization

**Implementation:**

Add configuration options:

```python
# In cmbagent/config.py
class ExecutionConfig:
    # Parallel execution settings
    ENABLE_PARALLEL_EXECUTION = True
    MAX_PARALLEL_WORKERS = 3
    AUTO_DETECT_DEPENDENCIES = True

    # Resource limits
    MAX_MEMORY_PER_WORKER_MB = 2000
    MAX_DISK_PER_WORKER_MB = 5000

    # Execution modes
    EXECUTION_MODE = "auto"  # "auto", "sequential", "parallel"
```

**Files to Create:**
- `cmbagent/execution/config.py`

**Verification:**
- Configuration loaded correctly
- Users can override via environment variables
- Invalid configurations rejected

## Files to Create (Summary)

### New Files
```
cmbagent/execution/
├── dependency_analyzer.py
├── dependency_graph.py
├── parallel_executor.py
├── work_directory_manager.py
├── resource_manager.py
└── config.py
```

### Modified Files
- `cmbagent/execution/dag_executor.py` - Add parallel execution
- `cmbagent/cmbagent.py` - Add execution mode parameter
- `cmbagent/database/models.py` - Add parallel execution metadata

## Verification Criteria

### Must Pass
- [ ] Dependency analysis correctly identifies independent tasks
- [ ] Topological sort produces valid execution order
- [ ] Circular dependencies detected and reported
- [ ] Parallel execution runs multiple tasks simultaneously
- [ ] Process isolation prevents task interference
- [ ] Isolated work directories created for each parallel task
- [ ] Resource limits enforced (memory, disk, workers)
- [ ] Results from parallel tasks collected correctly
- [ ] Database correctly tracks parallel execution states
- [ ] Sequential execution still works (backward compatibility)

### Should Pass
- [ ] Parallel execution faster than sequential for independent tasks
- [ ] System doesn't run out of memory during parallel execution
- [ ] File system conflicts prevented
- [ ] Progress tracking works for parallel tasks
- [ ] WebSocket events sent for all parallel task state changes

### Performance Verification
- [ ] Workflow with 3 independent tasks: 3x faster with parallelism
- [ ] Workflow with 6 independent tasks: 3x faster (3 workers)
- [ ] Resource usage monitored and logged
- [ ] No performance regression for sequential workflows

## Testing Checklist

### Unit Tests
```python
# Test dependency analysis
def test_dependency_analysis():
    analyzer = DependencyAnalyzer()
    tasks = [
        {"id": "task_1", "description": "Load data from API"},
        {"id": "task_2", "description": "Process data using results from task_1"},
        {"id": "task_3", "description": "Generate plot independently"}
    ]

    graph = analyzer.analyze(tasks)

    # task_2 depends on task_1
    assert ("task_1", "task_2") in graph.edges

    # task_3 is independent
    assert ("task_1", "task_3") not in graph.edges

# Test topological sort
def test_topological_sort():
    graph = DependencyGraph()
    graph.add_node("A")
    graph.add_node("B")
    graph.add_node("C")
    graph.add_node("D")
    graph.add_edge("A", "B")
    graph.add_edge("A", "C")
    graph.add_edge("B", "D")
    graph.add_edge("C", "D")

    levels = graph.topological_sort()

    # Expected: [[A], [B, C], [D]]
    assert len(levels) == 3
    assert levels[0] == ["A"]
    assert set(levels[1]) == {"B", "C"}
    assert levels[2] == ["D"]

# Test parallel execution
@pytest.mark.asyncio
async def test_parallel_execution():
    executor = ParallelExecutor(max_workers=2)

    async def mock_task(node_id, work_dir):
        await asyncio.sleep(1)  # Simulate work
        return {"result": f"done_{node_id}"}

    levels = [["task_1", "task_2", "task_3"]]

    start = time.time()
    results = await executor.execute_dag_levels(levels, mock_task)
    duration = time.time() - start

    # Should take ~2 seconds (3 tasks, 2 workers)
    assert 1.5 < duration < 2.5
    assert len(results) == 3
```

### Integration Tests
```python
# Test full workflow with parallelization
def test_planning_and_control_with_parallelization():
    agent = CMBAgent(
        execution_mode="parallel",
        max_parallel_workers=3
    )

    # Task that generates independent subtasks
    task = """
    Analyze three different datasets independently:
    1. CMB temperature data
    2. CMB polarization data
    3. Galaxy survey data
    Then combine results.
    """

    start = time.time()
    result = agent.planning_and_control(task)
    duration = time.time() - start

    # Verify parallel execution occurred
    run = agent.repo.get_run(result.run_id)
    dag_nodes = run.dag_nodes

    # Should have parallel nodes
    parallel_nodes = [n for n in dag_nodes if n.status == "completed"]
    assert len(parallel_nodes) >= 3

    # Should be faster than sequential (rough check)
    # Sequential would take ~3x longer
    logger.info(f"Workflow completed in {duration}s")
```

## Common Issues and Solutions

### Issue 1: False Dependencies Detected
**Symptom:** LLM identifies dependencies that don't exist
**Solution:** Improve prompt with more examples, add manual override option

### Issue 2: Circular Dependency in Valid Workflow
**Symptom:** Circular dependency error on valid workflow
**Solution:** Review dependency analysis logic, check for bidirectional edges

### Issue 3: Process Deadlock
**Symptom:** Parallel execution hangs indefinitely
**Solution:** Add timeout to task execution, implement deadlock detection

### Issue 4: File System Conflicts
**Symptom:** Multiple tasks write to same file, causing corruption
**Solution:** Ensure work directory isolation, add file locking

### Issue 5: Memory Exhaustion
**Symptom:** System runs out of memory during parallel execution
**Solution:** Reduce max_workers, enforce stricter resource limits

### Issue 6: Slow Dependency Analysis
**Symptom:** LLM dependency analysis takes too long (>1 minute)
**Solution:** Use faster model, cache analysis results, limit task count

## Rollback Procedure

If parallel execution causes issues:

1. **Disable parallel execution:**
   ```python
   ENABLE_PARALLEL_EXECUTION = False
   ```

2. **Force sequential mode:**
   ```python
   agent = CMBAgent(execution_mode="sequential")
   ```

3. **Revert DAG executor changes:**
   ```bash
   git checkout cmbagent/execution/dag_executor.py
   ```

4. **Remove parallel execution code (keep directory structure):**
   - Delete parallel executor modules
   - Keep database schema (no data loss)

## Post-Stage Actions

### Documentation
- Document parallel execution configuration
- Add performance benchmarks to docs
- Create troubleshooting guide for parallel execution
- Update architecture diagram with parallel execution flow

### Update Progress
- Mark Stage 8 complete in `PROGRESS.md`
- Document performance improvements achieved
- Note any limitations discovered

### Prepare for Stage 9
- Parallel execution working and tested
- Ready to add branching and play-from-node
- Stage 9 can proceed

## Success Criteria

Stage 8 is complete when:
1. LLM-based dependency analysis working accurately
2. Topological sort correctly orders tasks
3. Parallel execution runs independent tasks concurrently
4. Isolated work directories prevent task interference
5. Resource management prevents system exhaustion
6. Performance improvement demonstrated (2-3x faster for parallel workflows)
7. Backward compatibility maintained (sequential mode still works)
8. Verification checklist 100% complete

## Estimated Time Breakdown

- Dependency analysis prompt design: 8 min
- Topological sort implementation: 7 min
- Parallel execution engine: 12 min
- Isolated work directories: 6 min
- Resource management: 8 min
- DAG executor integration: 10 min
- Configuration and testing: 12 min
- Documentation: 7 min

**Total: 40-50 minutes**

## Next Stage

Once Stage 8 is verified complete, proceed to:
**Stage 9: Branching and Play-from-Node**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
