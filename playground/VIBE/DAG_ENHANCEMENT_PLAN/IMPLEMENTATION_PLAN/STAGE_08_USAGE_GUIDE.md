# Stage 8 Usage Guide: Parallel Execution

This guide explains how to use the new parallel execution features added in Stage 8.

## Quick Start

### Basic Usage

The simplest way to use parallel execution is through the enhanced DAG executor:

```python
from cmbagent.database.dag_executor import DAGExecutor
from cmbagent.execution.config import ExecutionConfig

# Create configuration with parallel execution enabled
config = ExecutionConfig(
    enable_parallel_execution=True,
    max_parallel_workers=3,
    execution_mode="auto"
)

# Create DAG executor with configuration
executor = DAGExecutor(
    db_session=db_session,
    session_id=session_id,
    work_dir="/path/to/work/dir",
    config=config
)

# Execute with enhanced parallelism
results = executor.execute_with_enhanced_parallelism(
    run_id=run_id,
    agent_executor_func=your_agent_function
)
```

### Using Environment Variables

Configure parallel execution via environment variables:

```bash
# Enable parallel execution
export CMBAGENT_ENABLE_PARALLEL=true

# Set max workers
export CMBAGENT_MAX_WORKERS=4

# Choose execution mode
export CMBAGENT_EXECUTION_MODE=auto  # auto, sequential, or parallel

# Set resource limits
export CMBAGENT_MAX_MEMORY_MB=2000
export CMBAGENT_TASK_TIMEOUT=3600

# Load configuration
config = ExecutionConfig.from_env()
```

## Configuration Options

### Execution Modes

1. **auto** (recommended): Automatically uses parallel execution for independent tasks
2. **sequential**: Forces sequential execution (useful for debugging)
3. **parallel**: Forces parallel execution even for dependent tasks (use with caution)

### Resource Limits

```python
config = ExecutionConfig(
    max_memory_per_worker_mb=2000,    # Max memory per parallel task
    max_disk_per_worker_mb=5000,       # Max disk space per task
    task_timeout_seconds=3600,         # Task timeout (1 hour)
    max_parallel_workers=3             # Max concurrent tasks
)
```

### Work Directory Settings

```python
config = ExecutionConfig(
    create_isolated_directories=True,  # Isolate parallel tasks
    merge_parallel_results=True,       # Merge results after execution
    preserve_node_structure=True,      # Keep node subdirectories
    cleanup_temp_files=True,           # Clean up temporary files
    keep_outputs=True,                 # Keep output files
    keep_logs=True                     # Keep log files
)
```

## Advanced Usage

### Using Individual Components

#### Dependency Analyzer

```python
from cmbagent.execution.dependency_analyzer import DependencyAnalyzer

analyzer = DependencyAnalyzer()

tasks = [
    {"id": "task_1", "description": "Load data", "agent": "engineer"},
    {"id": "task_2", "description": "Process data", "agent": "engineer"},
    {"id": "task_3", "description": "Plot results", "agent": "plotter"}
]

# Analyze dependencies
graph = analyzer.analyze(tasks)

# Get execution levels (parallel groups)
levels = graph.topological_sort()
print(f"Execution levels: {levels}")
```

#### Parallel Executor

```python
from cmbagent.execution.parallel_executor import ParallelExecutor

executor = ParallelExecutor(max_workers=3)

def task_function(task_id):
    # Your task implementation
    return {"result": f"completed_{task_id}"}

# Execute tasks in parallel
levels = [["task_1", "task_2", "task_3"]]
results = executor.execute_dag_levels_sync(
    levels=levels,
    executor_func=task_function
)
```

#### Work Directory Manager

```python
from cmbagent.execution.work_directory_manager import WorkDirectoryManager

manager = WorkDirectoryManager(
    base_work_dir="/tmp/cmbagent",
    run_id="run_abc123"
)

# Create isolated directories for parallel tasks
dir1 = manager.create_node_directory("node_1")
dir2 = manager.create_node_directory("node_2")

# After execution, merge results
manager.merge_parallel_results(["node_1", "node_2"])

# Cleanup
manager.cleanup_all(keep_outputs=True)
```

#### Resource Manager

```python
from cmbagent.execution.resource_manager import ResourceManager

manager = ResourceManager(max_concurrent_agents=3)

# Acquire resources
manager.acquire_sync("task_1", estimated_memory_mb=500)

# Do work...

# Release resources
manager.release("task_1")

# Check usage
stats = manager.get_usage_stats()
print(f"Active tasks: {stats['active_tasks']}")
```

## Performance Tuning

### Optimal Worker Count

The system automatically calculates optimal worker count based on:
- Available CPU cores
- Available memory (assumes 2GB per worker)
- Configured maximum workers

```python
from cmbagent.execution.resource_manager import ResourceManager

manager = ResourceManager()
optimal = manager.get_optimal_worker_count()
print(f"Recommended workers: {optimal}")
```

### Memory Management

For memory-intensive agents:

```python
config = ExecutionConfig(
    max_parallel_workers=2,           # Reduce workers
    max_memory_per_worker_mb=4000,    # Increase per-worker limit
)
```

For lightweight agents:

```python
config = ExecutionConfig(
    max_parallel_workers=5,           # More workers
    max_memory_per_worker_mb=1000,    # Lower per-worker limit
)
```

### Thread vs Process Pool

**ThreadPoolExecutor** (default, recommended):
- Lower overhead
- Shared memory
- Works with most agents
- Better for I/O-bound tasks

```python
config = ExecutionConfig(use_process_pool=False)
```

**ProcessPoolExecutor** (advanced):
- Process isolation
- No shared memory
- Requires pickle-able functions
- Better for CPU-bound tasks

```python
config = ExecutionConfig(use_process_pool=True)
```

## Troubleshooting

### Issue: Parallel execution not working

**Solution:** Check configuration:
```python
config = ExecutionConfig.from_env()
print(f"Parallel enabled: {config.enable_parallel_execution}")
print(f"Max workers: {config.max_parallel_workers}")
```

### Issue: Tasks running out of memory

**Solution:** Reduce parallel workers or increase memory limit:
```bash
export CMBAGENT_MAX_WORKERS=2
export CMBAGENT_MAX_MEMORY_MB=4000
```

### Issue: LLM dependency analysis failing

**Solution:** The system falls back to sequential dependencies. Check:
1. OpenAI API key is set: `export OPENAI_API_KEY=your_key`
2. Disable LLM analysis: `export CMBAGENT_USE_LLM_DEPS=false`

### Issue: ProcessPoolExecutor pickle errors

**Solution:** Switch to ThreadPoolExecutor:
```bash
export CMBAGENT_USE_PROCESS_POOL=false
```

## Monitoring and Debugging

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("cmbagent.execution")
logger.setLevel(logging.DEBUG)
```

### Check Resource Usage

```python
from cmbagent.execution.resource_manager import ResourceManager

manager = ResourceManager()
stats = manager.get_usage_stats()

print(f"System resources:")
print(f"  Memory: {stats['system_resources']['available_memory_mb']:.0f}MB available")
print(f"  CPU: {stats['system_resources']['cpu_percent']:.1f}% used")
print(f"Active tasks: {stats['active_tasks']}")
```

### View Directory Statistics

```python
from cmbagent.execution.work_directory_manager import WorkDirectoryManager

manager = WorkDirectoryManager("/tmp/cmbagent", "run_123")
stats = manager.get_directory_stats("node_1")

print(f"Total size: {stats['total_bytes'] / 1024 / 1024:.1f}MB")
for subdir, size in stats['subdirs'].items():
    print(f"  {subdir}: {size / 1024 / 1024:.1f}MB")
```

## Best Practices

1. **Start with auto mode:** Let the system decide when to parallelize
2. **Monitor resources:** Check memory usage for your typical workflows
3. **Use ThreadPoolExecutor:** Unless you have specific reasons for ProcessPoolExecutor
4. **Set reasonable timeouts:** Default 1 hour works for most cases
5. **Keep outputs:** Set `keep_outputs=True` for important results
6. **Test with sequential:** If issues arise, force sequential mode for debugging
7. **Cache dependency analysis:** Enable caching for repeated workflow patterns
8. **Review isolated directories:** Check work directory structure during development

## Examples

### Example 1: Data Analysis Workflow

```python
from cmbagent.execution.config import ExecutionConfig
from cmbagent.database.dag_executor import DAGExecutor

# Configure for data analysis (I/O-bound)
config = ExecutionConfig(
    max_parallel_workers=4,
    max_memory_per_worker_mb=1500,
    execution_mode="auto",
    use_process_pool=False
)

executor = DAGExecutor(db_session, session_id, config=config)
results = executor.execute_with_enhanced_parallelism(run_id, agent_func)
```

### Example 2: Heavy Computation Workflow

```python
# Configure for CPU-intensive tasks
config = ExecutionConfig(
    max_parallel_workers=2,
    max_memory_per_worker_mb=4000,
    task_timeout_seconds=7200,  # 2 hours
    execution_mode="auto"
)

executor = DAGExecutor(db_session, session_id, config=config)
results = executor.execute_with_enhanced_parallelism(run_id, agent_func)
```

### Example 3: Development/Debug Mode

```python
# Force sequential execution for debugging
config = ExecutionConfig(
    execution_mode="sequential",
    enable_parallel_execution=False
)

executor = DAGExecutor(db_session, session_id, config=config)
results = executor.execute(run_id, agent_func)  # Use original method
```

## Migration Guide

### From Basic DAG Executor

**Before (Stage 4):**
```python
executor = DAGExecutor(db_session, session_id, max_parallel=3)
results = executor.execute(run_id, agent_func)
```

**After (Stage 8):**
```python
config = ExecutionConfig(max_parallel_workers=3)
executor = DAGExecutor(db_session, session_id, config=config)
results = executor.execute_with_enhanced_parallelism(run_id, agent_func)
```

### Backward Compatibility

The original `execute()` method still works:
```python
# This still works exactly as before
executor = DAGExecutor(db_session, session_id)
results = executor.execute(run_id, agent_func)
```

## Performance Benchmarks

Expected speedup for different workflow patterns:

| Workflow Type | Tasks | Dependencies | Workers | Expected Speedup |
|--------------|-------|--------------|---------|-----------------|
| Fully parallel | 6 | None | 3 | 2-3x |
| Mixed dependencies | 10 | 50% dependent | 3 | 1.5-2x |
| Sequential | 5 | All sequential | 3 | 1x (no benefit) |
| Complex DAG | 15 | Partial dependencies | 4 | 2-2.5x |

## Further Reading

- [STAGE_08_SUMMARY.md](STAGE_08_SUMMARY.md) - Complete implementation summary
- [STAGE_08.md](stages/STAGE_08.md) - Original implementation plan
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview

---

**Need Help?**
- Check logs with `logging.DEBUG` level
- Review test examples in `tests/test_stage_08_parallel_execution.py`
- Consult the implementation source code for advanced use cases
