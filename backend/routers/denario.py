"""
Denario Research Paper wizard endpoints.

Provides staged execution of the 4-phase Denario workflow
(idea → method → experiment → paper) where each stage is triggered
individually by the user after review/edit.
"""

import asyncio
import io
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks

from models.denario_schemas import (
    DenarioCreateRequest,
    DenarioCreateResponse,
    DenarioExecuteRequest,
    DenarioStageResponse,
    DenarioStageContentResponse,
    DenarioContentUpdateRequest,
    DenarioRefineRequest,
    DenarioRefineResponse,
    DenarioTaskStateResponse,
    DenarioRecentTaskResponse,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/denario", tags=["Denario"])


# Stage definitions
STAGE_DEFS = [
    {"number": 1, "name": "idea_generation", "phase_type": "denario_idea", "shared_key": "research_idea", "file": "idea.md"},
    {"number": 2, "name": "method_development", "phase_type": "denario_method", "shared_key": "methodology", "file": "methods.md"},
    {"number": 3, "name": "experiment_execution", "phase_type": "denario_experiment", "shared_key": "results", "file": "results.md"},
    {"number": 4, "name": "paper_generation", "phase_type": "denario_paper", "shared_key": None, "file": None},
]


# Track running background tasks
_running_tasks: Dict[str, asyncio.Task] = {}

# Shared console buffers for stage execution (thread-safe)
# Key: "task_id:stage_num", Value: list of output lines
_console_buffers: Dict[str, List[str]] = {}
_console_lock = threading.Lock()


# =============================================================================
# Helpers
# =============================================================================

_db_initialized = False

def _get_db():
    """Get a database session, ensuring schema is up to date."""
    global _db_initialized
    if not _db_initialized:
        from cmbagent.database.base import init_database
        init_database()
        _db_initialized = True
    from cmbagent.database.base import get_db_session
    return get_db_session()


def _get_stage_repo(db, session_id: str = "denario"):
    from cmbagent.database.repository import TaskStageRepository
    return TaskStageRepository(db, session_id=session_id)


def _get_cost_repo(db, session_id: str = "denario"):
    from cmbagent.database.repository import CostRepository
    return CostRepository(db, session_id=session_id)


def _get_work_dir(task_id: str) -> str:
    """Get the work directory for a denario task."""
    from core.config import settings
    base = os.path.expanduser(settings.default_work_dir)
    return os.path.join(base, "denario_tasks", task_id)


def _get_session_id_for_task(task_id: str, db) -> str:
    """Look up the session_id for a denario task from its WorkflowRun."""
    from cmbagent.database.models import WorkflowRun
    run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
    if run:
        return run.session_id
    return "denario"  # fallback for legacy tasks


def build_shared_state(task_id: str, up_to_stage: int, db, session_id: str = "denario") -> Dict[str, Any]:
    """Reconstruct shared_state from completed stages' output_data['shared'].

    This accumulates context (research_idea, methodology, results, etc.)
    from all completed stages prior to the one being executed.
    """
    repo = _get_stage_repo(db, session_id=session_id)
    stages = repo.list_stages(parent_run_id=task_id)
    shared: Dict[str, Any] = {}
    for stage in stages:
        if stage.stage_number < up_to_stage and stage.status == "completed":
            if stage.output_data and "shared" in stage.output_data:
                shared.update(stage.output_data["shared"])
    return shared


def _stage_to_response(stage) -> DenarioStageResponse:
    return DenarioStageResponse(
        stage_number=stage.stage_number,
        stage_name=stage.stage_name,
        status=stage.status,
        started_at=stage.started_at.isoformat() if stage.started_at else None,
        completed_at=stage.completed_at.isoformat() if stage.completed_at else None,
        error=stage.error_message,
    )


# Auto-generated files in input_files/ that should NOT be listed as "uploaded data"
_AUTO_GENERATED_FILES = {
    "data_description.md", "idea.md", "methods.md", "results.md",
}
_AUTO_GENERATED_DIRS = {"plots", "paper"}


def _build_file_context(work_dir: str) -> str:
    """Scan input_files/ for user-uploaded data files and build context string.

    Returns a string describing uploaded files with absolute paths and previews
    for text files. This gets appended to data_description so LLM agents know
    about the files and can reference them in code.
    """
    input_dir = os.path.join(work_dir, "input_files")
    if not os.path.isdir(input_dir):
        return ""

    uploaded_files = []
    for entry in os.listdir(input_dir):
        if entry in _AUTO_GENERATED_FILES:
            continue
        if entry in _AUTO_GENERATED_DIRS:
            continue
        full_path = os.path.join(input_dir, entry)
        if not os.path.isfile(full_path):
            continue
        uploaded_files.append((entry, full_path))

    if not uploaded_files:
        return ""

    lines = ["\n\n---\n## Uploaded Data Files\n"]
    lines.append("The following data files have been uploaded and are available at the paths below.\n")

    for name, path in sorted(uploaded_files):
        size = os.path.getsize(path)
        size_str = f"{size}" if size < 1024 else f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/1024/1024:.1f}MB"
        lines.append(f"### `{name}` ({size_str})")
        lines.append(f"**Absolute path:** `{path}`\n")

        # For text-readable files, include a preview
        text_exts = {'.csv', '.txt', '.md', '.json', '.tsv', '.dat'}
        ext = os.path.splitext(name)[1].lower()
        if ext in text_exts and size < 10 * 1024 * 1024:  # Skip previews for files >10MB
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    preview_lines = []
                    for i, line in enumerate(f):
                        if i >= 15:
                            preview_lines.append("... (truncated)")
                            break
                        preview_lines.append(line.rstrip())
                if preview_lines:
                    lines.append("**Preview (first 15 lines):**")
                    lines.append("```")
                    lines.extend(preview_lines)
                    lines.append("```\n")
            except Exception:
                pass

    lines.append("Use the absolute paths above to read these files in your code.\n")
    return "\n".join(lines)


class _ConsoleCapture:
    """Thread-safe stdout/stderr capture that stores output in a shared buffer."""

    def __init__(self, buf_key: str, original_stream):
        self._buf_key = buf_key
        self._original = original_stream

    def write(self, text: str):
        # Always write to original stream too
        if self._original:
            self._original.write(text)
        # Store in shared buffer (line by line)
        if text and text.strip():
            with _console_lock:
                if self._buf_key not in _console_buffers:
                    _console_buffers[self._buf_key] = []
                _console_buffers[self._buf_key].append(text.rstrip())

    def flush(self):
        if self._original:
            self._original.flush()

    def fileno(self):
        if self._original:
            return self._original.fileno()
        raise io.UnsupportedOperation("fileno")

    def isatty(self):
        return False


def _get_console_lines(buf_key: str, since_index: int = 0) -> List[str]:
    """Get console output lines since a given index."""
    with _console_lock:
        buf = _console_buffers.get(buf_key, [])
        return buf[since_index:]


def _clear_console_buffer(buf_key: str):
    """Remove a console buffer once done."""
    with _console_lock:
        _console_buffers.pop(buf_key, None)


# =============================================================================
# POST /api/denario/create
# =============================================================================

@router.post("/create", response_model=DenarioCreateResponse)
async def create_denario_task(request: DenarioCreateRequest):
    """Create a new Denario research task with 4 pending stages."""
    task_id = str(uuid.uuid4())
    work_dir = _get_work_dir(task_id)
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.join(work_dir, "input_files"), exist_ok=True)

    # Create a proper session via SessionManager (matches AI-Weekly, etc.)
    from services.session_manager import get_session_manager
    sm = get_session_manager()
    session_id = sm.create_session(
        mode="denario-research",
        config={"task_id": task_id, "work_dir": work_dir},
        name=f"Denario: {request.task[:60]}",
    )

    db = _get_db()
    try:
        # Create parent WorkflowRun
        from cmbagent.database.models import WorkflowRun

        parent_run = WorkflowRun(
            id=task_id,
            session_id=session_id,
            mode="denario-research",
            agent="planner",
            model="gpt-4o",
            status="executing",
            task_description=request.task,
            started_at=datetime.now(timezone.utc),
            meta={
                "work_dir": work_dir,
                "data_description": request.data_description or "",
                "config": request.config or {},
                "session_id": session_id,
            },
        )
        db.add(parent_run)
        db.flush()

        # Create 4 pending TaskStage records
        repo = _get_stage_repo(db, session_id=session_id)
        stage_responses = []
        for sdef in STAGE_DEFS:
            stage = repo.create_stage(
                parent_run_id=task_id,
                stage_number=sdef["number"],
                stage_name=sdef["name"],
                status="pending",
                input_data={"task": request.task, "data_description": request.data_description},
            )
            stage_responses.append(_stage_to_response(stage))

        db.commit()

        # Write data description to input_files/
        if request.data_description:
            desc_path = os.path.join(work_dir, "input_files", "data_description.md")
            with open(desc_path, "w") as f:
                f.write(request.data_description)

        logger.info("denario_task_created task_id=%s session_id=%s", task_id, session_id)
        return DenarioCreateResponse(
            task_id=task_id,
            work_dir=work_dir,
            stages=stage_responses,
        )
    except Exception as e:
        db.rollback()
        logger.error("denario_create_failed error=%s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# =============================================================================
# POST /api/denario/{task_id}/stages/{num}/execute
# =============================================================================

@router.post("/{task_id}/stages/{stage_num}/execute")
async def execute_stage(task_id: str, stage_num: int, request: DenarioExecuteRequest = None):
    """Trigger execution of a single Denario phase.

    Runs the phase asynchronously in the background. Connect to
    the WebSocket /ws/denario/{task_id}/{stage_num} for streaming output.
    """
    if stage_num < 1 or stage_num > 4:
        raise HTTPException(status_code=400, detail="stage_num must be 1-4")

    # Check not already running
    bg_key = f"{task_id}:{stage_num}"
    if bg_key in _running_tasks and not _running_tasks[bg_key].done():
        raise HTTPException(status_code=409, detail="Stage is already executing")

    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        if not stages:
            raise HTTPException(status_code=404, detail="Task not found")

        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        if stage.status == "running":
            # Check if the background task is actually alive
            if bg_key in _running_tasks and not _running_tasks[bg_key].done():
                raise HTTPException(status_code=409, detail="Stage is already running")
            # Otherwise it's a stale "running" from a previous server session -- allow retry

        if stage.status == "completed":
            raise HTTPException(status_code=409, detail="Stage is already completed")

        # Validate prerequisites: all previous stages must be completed
        for s in stages:
            if s.stage_number < stage_num and s.status != "completed":
                raise HTTPException(
                    status_code=400,
                    detail=f"Stage {s.stage_number} ({s.stage_name}) must be completed first"
                )

        # Get parent run metadata
        from cmbagent.database.models import WorkflowRun
        parent_run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent_run:
            raise HTTPException(status_code=404, detail="Parent workflow run not found")

        work_dir = parent_run.meta.get("work_dir") if parent_run.meta else _get_work_dir(task_id)
        task_description = parent_run.task_description or ""
        data_description = (parent_run.meta or {}).get("data_description") or ""

        # Enhance data_description with uploaded file context
        file_context = _build_file_context(work_dir)
        if file_context:
            data_description = data_description + file_context

        # Build shared state from completed stages
        shared_state = build_shared_state(task_id, stage_num, db, session_id=session_id)
        shared_state.setdefault("data_description", data_description)

        # Mark stage as running
        repo.update_stage_status(stage.id, "running")

        config_overrides = (request.config_overrides if request else None) or {}
    finally:
        db.close()

    # Launch background execution
    task = asyncio.create_task(
        _run_phase(task_id, stage_num, task_description, work_dir, shared_state, config_overrides)
    )
    _running_tasks[bg_key] = task

    return {"status": "executing", "stage_num": stage_num, "task_id": task_id}


async def _run_phase(
    task_id: str,
    stage_num: int,
    task_description: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Execute a Denario phase in the background."""
    from cmbagent.phases.base import PhaseContext, PhaseStatus

    sdef = STAGE_DEFS[stage_num - 1]
    phase_type = sdef["phase_type"]
    buf_key = f"{task_id}:{stage_num}"

    # Initialize console buffer
    with _console_lock:
        _console_buffers[buf_key] = [f"Starting {sdef['name']}..."]

    # Import phase classes
    phase_classes = {
        "denario_idea": "cmbagent.task_framework.phases.idea.DenarioIdeaPhase",
        "denario_method": "cmbagent.task_framework.phases.method.DenarioMethodPhase",
        "denario_experiment": "cmbagent.task_framework.phases.experiment.DenarioExperimentPhase",
        "denario_paper": "cmbagent.task_framework.phases.paper.DenarioPaperPhase",
    }

    try:
        # Dynamic import of the phase class
        module_path, class_name = phase_classes[phase_type].rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        PhaseClass = getattr(module, class_name)

        # Build config
        config_kwargs = {"parent_run_id": task_id, **config_overrides}
        if phase_type == "denario_idea":
            config_kwargs["data_description"] = shared_state.get("data_description") or task_description
        phase = PhaseClass(PhaseClass.config_class(**config_kwargs))

        # Build PhaseContext
        context = PhaseContext(
            workflow_id=f"denario-{task_id}",
            run_id=task_id,
            phase_id=f"stage-{stage_num}",
            task=task_description,
            work_dir=work_dir,
            shared_state=shared_state,
            api_keys={},
            callbacks=None,
        )

        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(
                f"Phase {phase_type} initialized, executing..."
            )

        # Run the phase with stdout/stderr capture
        # The phase calls planning_and_control_context_carryover via asyncio.to_thread,
        # which runs in a thread pool. We capture stdout from that thread.
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        capture_out = _ConsoleCapture(buf_key, original_stdout)
        capture_err = _ConsoleCapture(buf_key, original_stderr)

        try:
            sys.stdout = capture_out
            sys.stderr = capture_err
            result = await phase.execute(context)
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

        # Persist result to DB
        db = _get_db()
        try:
            sid = _get_session_id_for_task(task_id, db)
            repo = _get_stage_repo(db, session_id=sid)
            stages = repo.list_stages(parent_run_id=task_id)
            stage = next((s for s in stages if s.stage_number == stage_num), None)
            if stage:
                if result.status == PhaseStatus.COMPLETED:
                    repo.update_stage_status(
                        stage.id,
                        "completed",
                        output_data=result.context.output_data,
                        output_files=list((result.context.output_data or {}).get("artifacts", {}).values()),
                    )
                    logger.info("denario_stage_completed task=%s stage=%d", task_id, stage_num)
                    with _console_lock:
                        _console_buffers.setdefault(buf_key, []).append(
                            f"Stage {stage_num} ({sdef['name']}) completed successfully."
                        )
                else:
                    repo.update_stage_status(
                        stage.id,
                        "failed",
                        error_message=result.error or "Phase failed",
                    )
                    logger.error("denario_stage_failed task=%s stage=%d error=%s", task_id, stage_num, result.error)
                    with _console_lock:
                        _console_buffers.setdefault(buf_key, []).append(
                            f"Stage {stage_num} failed: {result.error}"
                        )
            db.commit()
        finally:
            db.close()

    except Exception as e:
        logger.error("denario_phase_exception task=%s stage=%d error=%s", task_id, stage_num, e, exc_info=True)
        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(
                f"Error: {e}"
            )
        # Mark stage as failed
        db = _get_db()
        try:
            sid = _get_session_id_for_task(task_id, db)
            repo = _get_stage_repo(db, session_id=sid)
            stages = repo.list_stages(parent_run_id=task_id)
            stage = next((s for s in stages if s.stage_number == stage_num), None)
            if stage:
                repo.update_stage_status(stage.id, "failed", error_message=str(e))
            db.commit()
        finally:
            db.close()
    finally:
        bg_key = f"{task_id}:{stage_num}"
        _running_tasks.pop(bg_key, None)
        # Don't clear buffer here - WS endpoint needs to read remaining lines
        # Buffer is cleared after WS sends final event or after a timeout


# =============================================================================
# GET /api/denario/{task_id}/stages/{num}/content
# =============================================================================

@router.get("/{task_id}/stages/{stage_num}/content", response_model=DenarioStageContentResponse)
async def get_stage_content(task_id: str, stage_num: int):
    """Get the output content and shared_state for a completed stage."""
    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        content = None
        shared = None
        if stage.output_data:
            shared = stage.output_data.get("shared")
            # Try to get main content from the shared_state key
            sdef = STAGE_DEFS[stage_num - 1]
            if sdef["shared_key"] and shared:
                content = shared.get(sdef["shared_key"])

            # Fallback: read from the .md file on disk
            if not content and sdef["file"]:
                from cmbagent.database.models import WorkflowRun
                parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
                work_dir = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
                file_path = os.path.join(work_dir, "input_files", sdef["file"])
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        content = f.read()

        return DenarioStageContentResponse(
            stage_number=stage.stage_number,
            stage_name=stage.stage_name,
            status=stage.status,
            content=content,
            shared_state=shared,
            output_files=stage.output_files,
        )
    finally:
        db.close()


# =============================================================================
# PUT /api/denario/{task_id}/stages/{num}/content
# =============================================================================

@router.put("/{task_id}/stages/{stage_num}/content")
async def update_stage_content(task_id: str, stage_num: int, request: DenarioContentUpdateRequest):
    """Save user edits to a stage's content.

    Updates both the markdown file on disk and the output_data['shared']
    in the database so the next stage reads the edited version.
    """
    if stage_num < 1 or stage_num > 4:
        raise HTTPException(status_code=400, detail="stage_num must be 1-4")

    sdef = STAGE_DEFS[stage_num - 1]

    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        if stage.status != "completed":
            raise HTTPException(status_code=400, detail="Can only edit completed stages")

        # Update output_data['shared'][field]
        output_data = stage.output_data or {}
        shared = output_data.get("shared", {})
        shared[request.field] = request.content
        output_data["shared"] = shared

        repo.update_stage_status(stage.id, "completed", output_data=output_data)

        # Also update the .md file on disk
        if sdef["file"]:
            from cmbagent.database.models import WorkflowRun
            parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            work_dir = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
            file_path = os.path.join(work_dir, "input_files", sdef["file"])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(request.content)

        db.commit()
        return {"status": "saved", "field": request.field}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# =============================================================================
# POST /api/denario/{task_id}/stages/{num}/refine
# =============================================================================

@router.post("/{task_id}/stages/{stage_num}/refine", response_model=DenarioRefineResponse)
async def refine_stage_content(task_id: str, stage_num: int, request: DenarioRefineRequest):
    """Use LLM to refine stage content based on user instruction.

    This is a single LLM call (not a full phase execution).
    Returns the refined content for the user to review and apply.
    """
    import asyncio
    import concurrent.futures

    prompt = (
        "You are helping a researcher refine their work. "
        "Below is their current content, followed by their edit request.\n\n"
        f"--- CURRENT CONTENT ---\n{request.content}\n\n"
        f"--- USER REQUEST ---\n{request.message}\n\n"
        "Please provide the refined version of the content. "
        "Return ONLY the refined content, no explanations or preamble."
    )

    try:
        def _call_llm():
            from cmbagent.utils import get_api_keys_from_env
            from openai import OpenAI

            api_keys = get_api_keys_from_env()
            client = OpenAI(api_key=api_keys.get("openai"))
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.7,
            )
            return response.choices[0].message.content

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            refined = await loop.run_in_executor(executor, _call_llm)

        return DenarioRefineResponse(
            refined_content=refined,
            message="Content refined successfully",
        )
    except Exception as e:
        logger.error("denario_refine_failed error=%s", e)
        raise HTTPException(status_code=500, detail=f"Refinement failed: {str(e)}")


# =============================================================================
# GET /api/denario/{task_id}/stages/{num}/console  (REST fallback for console)
# =============================================================================

@router.get("/{task_id}/stages/{stage_num}/console")
async def get_stage_console(task_id: str, stage_num: int, since: int = 0):
    """Get console output lines for a running stage (REST polling fallback).

    Args:
        since: Line index to start from (for incremental fetching)
    """
    buf_key = f"{task_id}:{stage_num}"
    lines = _get_console_lines(buf_key, since_index=since)
    return {
        "lines": lines,
        "next_index": since + len(lines),
        "stage_num": stage_num,
    }


# =============================================================================
# GET /api/denario/recent  (must be before /{task_id} to avoid route conflict)
# =============================================================================

@router.get("/recent", response_model=list[DenarioRecentTaskResponse])
async def list_recent_tasks():
    """List incomplete Denario tasks for the resume flow."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        # Find denario runs that are not completed/failed
        runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.mode == "denario-research",
                WorkflowRun.parent_run_id.is_(None),  # Only parent runs
                WorkflowRun.status.in_(["executing", "draft", "planning"]),
            )
            .order_by(WorkflowRun.started_at.desc())
            .limit(20)
            .all()
        )

        result = []
        for run in runs:
            repo = _get_stage_repo(db, session_id=run.session_id)
            progress = repo.get_task_progress(parent_run_id=run.id)
            current_stage = None
            stages = repo.list_stages(parent_run_id=run.id)
            for s in stages:
                if s.status != "completed":
                    current_stage = s.stage_number
                    break

            result.append(DenarioRecentTaskResponse(
                task_id=run.id,
                task=run.task_description or "",
                status=run.status,
                created_at=run.started_at.isoformat() if run.started_at else None,
                current_stage=current_stage,
                progress_percent=progress.get("progress_percent", 0.0),
            ))

        return result
    finally:
        db.close()


# =============================================================================
# GET /api/denario/{task_id}
# =============================================================================

@router.get("/{task_id}", response_model=DenarioTaskStateResponse)
async def get_task_state(task_id: str):
    """Get full task state for resume - all stages, costs, and progress."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        repo = _get_stage_repo(db, session_id=parent.session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        progress = repo.get_task_progress(parent_run_id=task_id)

        # Get cost info
        total_cost = None
        try:
            cost_repo = _get_cost_repo(db, session_id=parent.session_id)
            cost_info = cost_repo.get_task_total_cost(parent_run_id=task_id)
            total_cost = cost_info.get("total_cost_usd")
        except Exception:
            pass

        # Determine current stage
        current_stage = None
        for s in stages:
            if s.status == "running":
                current_stage = s.stage_number
                break
        if current_stage is None:
            # Find first non-completed stage
            for s in stages:
                if s.status != "completed":
                    current_stage = s.stage_number
                    break

        return DenarioTaskStateResponse(
            task_id=task_id,
            task=parent.task_description or "",
            status=parent.status,
            work_dir=(parent.meta or {}).get("work_dir"),
            created_at=parent.started_at.isoformat() if parent.started_at else None,
            stages=[_stage_to_response(s) for s in stages],
            current_stage=current_stage,
            progress_percent=progress.get("progress_percent", 0.0),
            total_cost_usd=total_cost,
        )
    finally:
        db.close()
