# Stage 6: Process-Based Isolation

**Phase:** 2 - Execution Isolation
**Dependencies:** Stage 4 (ConnectionManager)
**Risk Level:** High
**Estimated Time:** 6-8 hours

## Objectives

1. Create `IsolatedTaskExecutor` that runs tasks in separate processes
2. Implement IPC via multiprocessing.Queue for output routing
3. Eliminate global state pollution (`builtins.print`, `sys.stdout`, `IOStream`)
4. Maintain compatibility with all execution modes

## Current State Analysis

### The Root Problem

In `backend/execution/task_executor.py:450-472`:
```python
builtins.print = custom_print        # GLOBAL - affects ALL code
sys.stdout = StreamWrapper(...)       # GLOBAL - affects ALL code
IOStream.set_global_default(...)      # GLOBAL - affects ALL autogen code
```

When Task A and Task B run concurrently:
1. Task A sets globals → output goes to Task A's WebSocket
2. Task B sets globals → **OVERWRITES** Task A's settings
3. Task A's output now goes to Task B's WebSocket
4. When Task A finishes and restores globals → Task B's output goes to console

### The Solution

Each task runs in a **separate subprocess** with its own:
- `builtins.print`
- `sys.stdout` / `sys.stderr`
- `IOStream` global
- Complete memory isolation

Output flows via `multiprocessing.Queue` back to the main process.

## Implementation Tasks

### Task 1: Create IsolatedTaskExecutor

**Objective:** Implement process-based task execution

**File to Create:** `backend/execution/isolated_executor.py`

```python
"""
Isolated Task Executor

Executes CMBAgent tasks in separate subprocesses to prevent global state pollution.
Each task gets its own Python interpreter with isolated:
- builtins.print
- sys.stdout/stderr
- IOStream settings
- All global state

Output is routed via multiprocessing.Queue back to the main process for WebSocket delivery.
"""

import asyncio
import logging
import multiprocessing
import os
import queue
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from multiprocessing import Process, Queue
from typing import Any, Callable, Dict, Optional, Awaitable

logger = logging.getLogger(__name__)


class IsolatedTaskExecutor:
    """
    Execute tasks in isolated subprocesses.

    Benefits:
    - True process isolation (no global pollution)
    - Works with any library that modifies globals
    - Proper resource cleanup on task completion/failure
    - Task cancellation via process termination
    """

    def __init__(self, max_workers: int = 10):
        """
        Initialize the executor.

        Args:
            max_workers: Maximum concurrent task processes
        """
        self.max_workers = max_workers
        self._active_processes: Dict[str, Process] = {}
        self._process_lock = asyncio.Lock()

        # Set multiprocessing start method (spawn for isolation)
        try:
            multiprocessing.set_start_method('spawn', force=True)
        except RuntimeError:
            pass  # Already set

        logger.info("IsolatedTaskExecutor initialized (max_workers=%d)", max_workers)

    async def execute(
        self,
        task_id: str,
        task: str,
        config: Dict[str, Any],
        output_callback: Callable[[str, Dict[str, Any]], Awaitable[None]],
        work_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a task in an isolated subprocess.

        Args:
            task_id: Unique task identifier
            task: Task description
            config: Task configuration
            output_callback: Async callback for output events (event_type, data)
            work_dir: Working directory for the task

        Returns:
            Task result dictionary

        Raises:
            RuntimeError: If max workers exceeded or execution fails
        """
        async with self._process_lock:
            if len(self._active_processes) >= self.max_workers:
                raise RuntimeError(f"Max workers ({self.max_workers}) exceeded")

        # Create queues for IPC
        output_queue = Queue()
        result_queue = Queue()

        # Determine work directory
        if not work_dir:
            work_dir = os.path.expanduser(config.get("workDir", "~/Desktop/cmbdir"))
        task_work_dir = os.path.join(work_dir, task_id)
        os.makedirs(task_work_dir, exist_ok=True)

        # Start subprocess
        process = Process(
            target=_run_task_in_subprocess,
            args=(task_id, task, config, output_queue, result_queue, task_work_dir),
            daemon=True
        )
        process.start()

        async with self._process_lock:
            self._active_processes[task_id] = process

        logger.info("Started subprocess for task %s (pid=%d)", task_id, process.pid)

        try:
            # Monitor output queue and forward to callback
            result = await self._monitor_subprocess(
                task_id, process, output_queue, result_queue, output_callback
            )
            return result

        finally:
            async with self._process_lock:
                self._active_processes.pop(task_id, None)

            # Ensure process is terminated
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2.0)

            logger.info("Subprocess for task %s cleaned up", task_id)

    async def _monitor_subprocess(
        self,
        task_id: str,
        process: Process,
        output_queue: Queue,
        result_queue: Queue,
        output_callback: Callable
    ) -> Dict[str, Any]:
        """Monitor subprocess and handle output"""

        loop = asyncio.get_event_loop()

        while True:
            # Check for output (non-blocking)
            try:
                while True:
                    try:
                        event_type, data = output_queue.get_nowait()
                        await output_callback(event_type, data)
                    except queue.Empty:
                        break
            except Exception as e:
                logger.warning("Error processing output: %s", e)

            # Check if process finished
            if not process.is_alive():
                # Drain remaining output
                try:
                    while True:
                        event_type, data = output_queue.get_nowait()
                        await output_callback(event_type, data)
                except queue.Empty:
                    pass

                # Get result
                try:
                    result = result_queue.get(timeout=5.0)
                    if isinstance(result, Exception):
                        raise result
                    return result
                except queue.Empty:
                    # Process died without returning result
                    exit_code = process.exitcode
                    raise RuntimeError(f"Task process terminated unexpectedly (exit code: {exit_code})")

            # Yield control
            await asyncio.sleep(0.1)

    async def cancel(self, task_id: str) -> bool:
        """
        Cancel a running task.

        Args:
            task_id: Task identifier

        Returns:
            True if cancelled, False if not found
        """
        async with self._process_lock:
            process = self._active_processes.get(task_id)
            if not process:
                return False

        logger.info("Cancelling task %s", task_id)

        # Try graceful termination first
        process.terminate()
        process.join(timeout=5.0)

        if process.is_alive():
            # Force kill
            process.kill()
            process.join(timeout=2.0)

        return True

    async def get_active_tasks(self) -> list:
        """Get list of active task IDs"""
        async with self._process_lock:
            return list(self._active_processes.keys())


def _run_task_in_subprocess(
    task_id: str,
    task: str,
    config: Dict[str, Any],
    output_queue: Queue,
    result_queue: Queue,
    work_dir: str
):
    """
    Run task in isolated subprocess.

    This function runs in a SEPARATE PROCESS with completely isolated globals.
    It's safe to modify builtins.print, sys.stdout, etc. here.
    """

    import builtins

    # Store original streams
    original_print = builtins.print
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    def send_output(event_type: str, data: Dict[str, Any]):
        """Thread-safe output sending"""
        try:
            output_queue.put((event_type, data), timeout=1.0)
        except queue.Full:
            pass  # Drop if queue full

    def captured_print(*args, **kwargs):
        """Captured print that sends to queue"""
        message = " ".join(str(arg) for arg in args)
        send_output("output", {"message": message, "source": "print"})
        # Also print to actual stdout for debugging
        original_print(*args, **kwargs)

    class QueueWriter:
        """Stream writer that sends to queue"""
        def __init__(self, event_type: str):
            self.event_type = event_type
            self.buffer = ""

        def write(self, text):
            if text:
                self.buffer += text
                # Flush on newline
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if line.strip():
                        send_output(self.event_type, {"message": line, "source": "stream"})
            return len(text) if text else 0

        def flush(self):
            if self.buffer.strip():
                send_output(self.event_type, {"message": self.buffer, "source": "stream"})
                self.buffer = ""

        def fileno(self):
            raise AttributeError("QueueWriter has no fileno")

        def isatty(self):
            return False

    try:
        # Override globals (safe - isolated process!)
        builtins.print = captured_print
        sys.stdout = QueueWriter("output")
        sys.stderr = QueueWriter("error")

        # Set up AG2 IOStream if available
        try:
            from autogen.io.base import IOStream

            class QueueIOStream(IOStream):
                def print(self, *args, **kwargs):
                    message = " ".join(str(arg) for arg in args)
                    send_output("output", {"message": message, "source": "ag2"})

            IOStream.set_global_default(QueueIOStream())
        except ImportError:
            pass

        # Set environment
        os.environ["CMBAGENT_DEBUG"] = "false"
        os.environ["CMBAGENT_DISABLE_DISPLAY"] = "true"
        os.chdir(work_dir)

        send_output("status", {"message": "Starting task execution..."})

        # Import and execute CMBAgent
        result = _execute_cmbagent_task(task_id, task, config, work_dir, send_output)

        # Send success
        result_queue.put(result)

    except Exception as e:
        # Send error
        error_msg = str(e)
        tb = traceback.format_exc()

        send_output("error", {
            "message": error_msg,
            "traceback": tb,
            "error_type": type(e).__name__
        })

        result_queue.put(RuntimeError(f"Task failed: {error_msg}"))

    finally:
        # Restore (not strictly necessary as process is ending)
        builtins.print = original_print
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def _execute_cmbagent_task(
    task_id: str,
    task: str,
    config: Dict[str, Any],
    work_dir: str,
    send_output: Callable
) -> Dict[str, Any]:
    """
    Execute the actual CMBAgent task.

    This is separated out for clarity and to allow mode-specific handling.
    """
    import cmbagent
    from cmbagent.utils import get_api_keys_from_env

    api_keys = get_api_keys_from_env()
    mode = config.get("mode", "one-shot")

    send_output("output", {"message": f"Executing in {mode} mode..."})

    # Extract common config
    engineer_model = config.get("model", "gpt-4o")
    max_rounds = config.get("maxRounds", 25)
    max_attempts = config.get("maxAttempts", 6)
    default_formatter_model = config.get("defaultFormatterModel", "o3-mini-2025-01-31")
    default_llm_model = config.get("defaultModel", "gpt-4.1-2025-04-14")

    start_time = time.time()

    # Execute based on mode
    if mode == "one-shot":
        agent = config.get("agent", "engineer")
        results = cmbagent.one_shot(
            task=task,
            max_rounds=max_rounds,
            max_n_attempts=max_attempts,
            engineer_model=engineer_model,
            agent=agent,
            work_dir=work_dir,
            api_keys=api_keys,
            clear_work_dir=False,
            default_formatter_model=default_formatter_model,
            default_llm_model=default_llm_model
        )

    elif mode == "planning-control":
        planner_model = config.get("plannerModel", "gpt-4.1-2025-04-14")
        plan_reviewer_model = config.get("planReviewerModel", "o3-mini-2025-01-31")
        researcher_model = config.get("researcherModel", "gpt-4.1-2025-04-14")
        max_plan_steps = config.get("maxPlanSteps", 10)
        n_plan_reviews = config.get("nPlanReviews", 1)
        plan_instructions = config.get("planInstructions", "")

        results = cmbagent.planning_and_control_context_carryover(
            task=task,
            max_rounds_control=max_rounds,
            max_n_attempts=max_attempts,
            max_plan_steps=max_plan_steps,
            n_plan_reviews=n_plan_reviews,
            engineer_model=engineer_model,
            researcher_model=researcher_model,
            planner_model=planner_model,
            plan_reviewer_model=plan_reviewer_model,
            plan_instructions=plan_instructions if plan_instructions.strip() else None,
            work_dir=work_dir,
            api_keys=api_keys,
            clear_work_dir=False,
            default_formatter_model=default_formatter_model,
            default_llm_model=default_llm_model
        )

    elif mode == "idea-generation":
        idea_maker_model = config.get("ideaMakerModel", "gpt-4.1-2025-04-14")
        idea_hater_model = config.get("ideaHaterModel", "o3-mini-2025-01-31")
        planner_model = config.get("plannerModel", "gpt-4.1-2025-04-14")
        plan_reviewer_model = config.get("planReviewerModel", "o3-mini-2025-01-31")
        max_plan_steps = config.get("maxPlanSteps", 10)
        n_plan_reviews = config.get("nPlanReviews", 1)

        results = cmbagent.planning_and_control_context_carryover(
            task=task,
            max_rounds_control=max_rounds,
            max_n_attempts=max_attempts,
            max_plan_steps=max_plan_steps,
            n_plan_reviews=n_plan_reviews,
            idea_maker_model=idea_maker_model,
            idea_hater_model=idea_hater_model,
            planner_model=planner_model,
            plan_reviewer_model=plan_reviewer_model,
            work_dir=work_dir,
            api_keys=api_keys,
            clear_work_dir=False,
            default_formatter_model=default_formatter_model,
            default_llm_model=default_llm_model
        )

    elif mode == "ocr":
        pdf_path = task.strip()
        if pdf_path.startswith("~"):
            pdf_path = os.path.expanduser(pdf_path)

        save_markdown = config.get("saveMarkdown", True)
        save_json = config.get("saveJson", True)
        save_text = config.get("saveText", False)
        max_workers = config.get("maxWorkers", 4)
        ocr_output_dir = config.get("ocrOutputDir", None)

        if os.path.isfile(pdf_path):
            results = cmbagent.process_single_pdf(
                pdf_path=pdf_path,
                save_markdown=save_markdown,
                save_json=save_json,
                save_text=save_text,
                output_dir=ocr_output_dir,
                work_dir=work_dir
            )
        elif os.path.isdir(pdf_path):
            results = cmbagent.process_folder(
                folder_path=pdf_path,
                save_markdown=save_markdown,
                save_json=save_json,
                save_text=save_text,
                output_dir=ocr_output_dir,
                max_workers=max_workers,
                work_dir=work_dir
            )
        else:
            raise ValueError(f"Path not found: {pdf_path}")

    elif mode == "arxiv":
        results = cmbagent.arxiv_filter(
            input_text=task,
            work_dir=work_dir
        )

    elif mode == "enhance-input":
        max_workers = config.get("maxWorkers", 4)
        results = cmbagent.preprocess_task(
            text=task,
            work_dir=work_dir,
            max_workers=max_workers,
            clear_work_dir=False
        )

    else:
        # Fallback to one-shot for unknown modes
        send_output("output", {"message": f"Unknown mode '{mode}', using one-shot"})
        results = cmbagent.one_shot(
            task=task,
            max_rounds=max_rounds,
            max_n_attempts=max_attempts,
            engineer_model=engineer_model,
            work_dir=work_dir,
            api_keys=api_keys,
            clear_work_dir=False
        )

    execution_time = time.time() - start_time

    send_output("output", {"message": f"Task completed in {execution_time:.2f}s"})

    return {
        "status": "completed",
        "execution_time": execution_time,
        "work_dir": work_dir,
        "mode": mode,
        "results": results if isinstance(results, dict) else {}
    }


# Global executor instance
_executor: Optional[IsolatedTaskExecutor] = None


def get_isolated_executor() -> IsolatedTaskExecutor:
    """Get global isolated executor"""
    global _executor
    if _executor is None:
        _executor = IsolatedTaskExecutor(max_workers=10)
    return _executor
```

### Task 2: Update Task Executor to Use Isolated Executor

**Objective:** Replace global-polluting execution with isolated execution

**File to Modify:** `backend/execution/task_executor.py`

**Add at the top:**
```python
from execution.isolated_executor import get_isolated_executor

# Feature flag for gradual rollout
USE_ISOLATED_EXECUTION = True
```

**Replace the execute_cmbagent_task function with:**

```python
async def execute_cmbagent_task(
    websocket: WebSocket,
    task_id: str,
    task: str,
    config: Dict[str, Any]
):
    """
    Execute CMBAgent task with real-time output streaming.

    Uses isolated subprocess execution to prevent global state pollution.
    """

    if USE_ISOLATED_EXECUTION:
        await _execute_isolated(websocket, task_id, task, config)
    else:
        await _execute_legacy(websocket, task_id, task, config)


async def _execute_isolated(
    websocket: WebSocket,
    task_id: str,
    task: str,
    config: Dict[str, Any]
):
    """Execute task in isolated subprocess"""
    from services.connection_manager import connection_manager

    executor = get_isolated_executor()

    async def output_callback(event_type: str, data: Dict[str, Any]):
        """Forward subprocess output to WebSocket"""
        await send_ws_event(websocket, event_type, data, run_id=task_id)

    try:
        result = await executor.execute(
            task_id=task_id,
            task=task,
            config=config,
            output_callback=output_callback
        )

        # Send result
        await send_ws_event(websocket, "result", result, run_id=task_id)
        await send_ws_event(websocket, "complete", {"status": "success"}, run_id=task_id)

    except Exception as e:
        logger.error("Task %s failed: %s", task_id, e)
        await send_ws_event(websocket, "error", {
            "message": str(e),
            "error_type": type(e).__name__
        }, run_id=task_id)


async def _execute_legacy(websocket, task_id, task, config):
    """Original execution (kept for fallback)"""
    # ... existing code ...
```

### Task 3: Handle HITL Modes (copilot, hitl-interactive)

**Objective:** Support modes that require bidirectional communication

For HITL modes, the subprocess needs to communicate approval requests back to the main process. This requires additional IPC.

**Add to `isolated_executor.py`:**

```python
# Add approval queue to subprocess args
# In execute method, create:
approval_request_queue = Queue()
approval_response_queue = Queue()

# Pass to subprocess:
args = (task_id, task, config, output_queue, result_queue,
        approval_request_queue, approval_response_queue, work_dir)

# In _monitor_subprocess, add approval handling:
async def _monitor_subprocess(..., approval_request_queue, approval_response_queue):
    # ... existing code ...

    # Check for approval requests
    try:
        while True:
            try:
                approval_data = approval_request_queue.get_nowait()
                # Create approval and wait
                approval_manager = get_approval_manager()
                approval_id = await approval_manager.request_approval(...)

                # Send approval_required event
                await output_callback("approval_required", {
                    "approval_id": approval_id,
                    **approval_data
                })

                # Wait for resolution
                result = await approval_manager.wait_for_approval(approval_id)

                # Send back to subprocess
                approval_response_queue.put(result)

            except queue.Empty:
                break
    except Exception as e:
        logger.warning("Approval handling error: %s", e)
```

**Note:** Full HITL integration is complex. For initial implementation, HITL modes can fall back to legacy execution:

```python
# In execute_cmbagent_task:
mode = config.get("mode", "one-shot")
if mode in ["copilot", "hitl-interactive"] and USE_ISOLATED_EXECUTION:
    # HITL modes need bidirectional communication
    # Use legacy execution for now, or implement approval IPC
    logger.info("HITL mode %s using legacy execution", mode)
    await _execute_legacy(websocket, task_id, task, config)
else:
    await _execute_isolated(websocket, task_id, task, config)
```

## Verification Criteria

### Must Pass
- [ ] Two concurrent tasks execute without output mixing
- [ ] Subprocess isolation works (no global pollution)
- [ ] Output routes correctly to respective WebSockets
- [ ] Task cancellation works
- [ ] All non-HITL modes work

### Test Script
```python
# test_stage_6.py
import asyncio
from unittest.mock import AsyncMock
from backend.execution.isolated_executor import IsolatedTaskExecutor

async def test_isolated_execution():
    executor = IsolatedTaskExecutor(max_workers=5)

    outputs_1 = []
    outputs_2 = []

    async def callback_1(event_type, data):
        outputs_1.append((event_type, data))

    async def callback_2(event_type, data):
        outputs_2.append((event_type, data))

    # Run two tasks concurrently
    task1 = asyncio.create_task(executor.execute(
        task_id="test_1",
        task="print('TASK_ONE_OUTPUT')",
        config={"mode": "one-shot"},
        output_callback=callback_1
    ))

    task2 = asyncio.create_task(executor.execute(
        task_id="test_2",
        task="print('TASK_TWO_OUTPUT')",
        config={"mode": "one-shot"},
        output_callback=callback_2
    ))

    await asyncio.gather(task1, task2)

    # Verify isolation
    output_1_text = " ".join(str(d) for _, d in outputs_1)
    output_2_text = " ".join(str(d) for _, d in outputs_2)

    assert "TASK_ONE" in output_1_text
    assert "TASK_TWO" not in output_1_text
    assert "TASK_TWO" in output_2_text
    assert "TASK_ONE" not in output_2_text

    print("✅ Tasks are isolated - no output mixing!")

if __name__ == "__main__":
    asyncio.run(test_isolated_execution())
```

## Common Issues and Solutions

### Issue 1: Subprocess won't start on macOS
**Symptom:** `RuntimeError: context has already been set`
**Solution:** Call `set_start_method('spawn', force=True)` early in app startup

### Issue 2: Pickle errors
**Symptom:** `Can't pickle local object`
**Solution:** Only pass serializable data through queues

### Issue 3: High memory usage
**Symptom:** Each subprocess uses 200MB+
**Solution:** Expected due to CMBAgent imports. Limit max_workers.

## Rollback Procedure

```bash
# Set feature flag
# In task_executor.py:
USE_ISOLATED_EXECUTION = False

# Or fully rollback
git checkout backend/execution/task_executor.py
rm backend/execution/isolated_executor.py
```

## Success Criteria

Stage 6 is complete when:
1. ✅ IsolatedTaskExecutor created and working
2. ✅ Two concurrent tasks don't mix output
3. ✅ All non-HITL modes work correctly
4. ✅ Task cancellation works
5. ✅ Memory usage is acceptable

## Next Stage

Once Stage 6 is verified complete, proceed to:
**Stage 7: Output Channel Routing**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-11
