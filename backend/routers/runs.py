"""
Workflow run history and files endpoints.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException

from core.logging import get_logger
logger = get_logger(__name__)

router = APIRouter(prefix="/api/runs", tags=["Runs"])

# Import services at runtime
_services_available = None
_workflow_service = None


def _check_services():
    """Check if services are available."""
    global _services_available, _workflow_service
    if _services_available is None:
        try:
            from services import workflow_service
            _workflow_service = workflow_service
            _services_available = True
        except ImportError:
            _services_available = False
    return _services_available


def _resolve_run_id(run_id: str) -> str:
    """Resolve task_id to database run_id if available."""
    if _check_services() and _workflow_service:
        run_info = _workflow_service.get_run_info(run_id)
        if run_info and run_info.get("db_run_id"):
            return run_info["db_run_id"]
    return run_id


@router.get("/{run_id}/history")
async def get_run_history(run_id: str, event_type: Optional[str] = None):
    """Get execution history for a workflow run.

    Args:
        run_id: The workflow run ID (can be task_id, will be resolved to db_run_id)
        event_type: Optional filter by event type
    """
    try:
        # Resolve task_id to database run_id
        effective_run_id = _resolve_run_id(run_id)
        if _check_services():
            logger.debug("resolved_run_id", task_id=run_id, db_run_id=effective_run_id)

        events_data = []

        # Try to get events from database first
        try:
            from cmbagent.database import get_db_session
            from cmbagent.database.models import ExecutionEvent

            db = get_db_session()

            # Query without session filtering to get all events for this run
            query = db.query(ExecutionEvent).filter(ExecutionEvent.run_id == effective_run_id)

            if event_type:
                query = query.filter(ExecutionEvent.event_type == event_type)

            events = query.order_by(ExecutionEvent.execution_order).all()

            # Filter out 'start' subtypes to avoid double counting
            filtered_events = [
                e for e in events
                if e.event_subtype != 'start' and e.event_type not in ['node_started', 'node_completed']
            ]

            # Convert to JSON-serializable format
            events_data = [
                {
                    "id": e.id,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "event_type": e.event_type,
                    "event_subtype": e.event_subtype,
                    "node_id": e.node_id,
                    "agent_name": e.agent_name,
                    "description": e.meta.get('description') if e.meta and isinstance(e.meta, dict) else None,
                    "meta": e.meta,
                    "inputs": e.inputs,
                    "outputs": e.outputs,
                    "error_message": e.error_message,
                    "status": e.status,
                    "duration_ms": e.duration_ms
                }
                for e in filtered_events
            ]

            logger.debug("events_found", run_id=effective_run_id, count=len(events_data))
            db.close()
        except Exception as db_err:
            logger.error("db_query_failed", run_id=effective_run_id, error=str(db_err), exc_info=True)

        # If no database events found, try the in-memory event queue
        if not events_data:
            try:
                from event_queue import event_queue

                ws_events = event_queue.get_all_events(run_id)
                logger.debug("event_queue_events_found", run_id=run_id, count=len(ws_events))

                # Convert WebSocket events to history format
                for idx, ws_event in enumerate(ws_events):
                    event_data = ws_event.data or {}
                    event_dict = {
                        "id": f"ws_{idx}",
                        "timestamp": ws_event.timestamp,
                        "event_type": ws_event.event_type,
                        "event_subtype": None,
                        "node_id": event_data.get('node_id'),
                        "agent_name": event_data.get('agent'),
                        "description": event_data.get('message') or event_data.get('status'),
                        "meta": event_data,
                        "inputs": event_data.get('inputs'),
                        "outputs": event_data.get('outputs') or event_data.get('result'),
                        "error_message": event_data.get('error'),
                        "status": event_data.get('status'),
                        "duration_ms": None
                    }

                    # Filter by event_type if specified
                    if not event_type or event_dict["event_type"] == event_type:
                        events_data.append(event_dict)

            except Exception as queue_err:
                logger.warning("event_queue_query_failed", error=str(queue_err))

        return {
            "run_id": run_id,
            "resolved_run_id": effective_run_id,
            "total_events": len(events_data),
            "events": events_data
        }

    except Exception as e:
        logger.error("run_history_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}/files")
async def get_run_files(run_id: str):
    """Get all files generated during a workflow run.

    Args:
        run_id: The workflow run ID
    """
    try:
        effective_run_id = _resolve_run_id(run_id)

        from cmbagent.database import get_db_session
        from cmbagent.database.models import File, DAGNode, WorkflowStep
        from cmbagent.database.session_manager import SessionManager
        from sqlalchemy.orm import joinedload

        db = get_db_session()
        session_manager = SessionManager(db)

        # Get or create session
        session_id = session_manager.get_or_create_default_session()

        # Query files directly by run_id
        files = db.query(File).outerjoin(
            DAGNode, File.node_id == DAGNode.id
        ).outerjoin(
            WorkflowStep, File.step_id == WorkflowStep.id
        ).filter(
            File.run_id == effective_run_id
        ).all()

        # If no files found with effective_run_id, try with original run_id
        if not files and effective_run_id != run_id:
            files = db.query(File).outerjoin(
                DAGNode, File.node_id == DAGNode.id
            ).outerjoin(
                WorkflowStep, File.step_id == WorkflowStep.id
            ).filter(
                File.run_id == run_id
            ).all()

        # Convert to JSON-serializable format with step information
        files_data = []
        for f in files:
            file_data = {
                "id": f.id,
                "file_path": f.file_path,
                "file_name": f.file_path.split('/')[-1] if f.file_path else None,
                "file_type": f.file_type,
                "size_bytes": f.size_bytes,
                "node_id": f.node_id,
                "step_id": f.step_id,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "event_id": f.event_id
            }
            # Add agent_name from node if available
            if f.node and hasattr(f.node, 'agent'):
                file_data["agent_name"] = f.node.agent
            # Add step info if available
            if f.step:
                file_data["step_number"] = f.step.step_number
                file_data["step_goal"] = f.step.goal
            files_data.append(file_data)

        db.close()

        return {
            "run_id": run_id,
            "resolved_run_id": effective_run_id,
            "total_files": len(files_data),
            "files": files_data
        }

    except Exception as e:
        logger.error("run_files_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}/costs")
async def get_run_costs(run_id: str):
    """Get cost breakdown for a workflow run from the database.

    Args:
        run_id: The workflow run ID (can be task_id, will be resolved to db_run_id)
    
    Returns:
        Cost summary including total cost, tokens, and breakdowns by model and step
    """
    try:
        # Resolve task_id to database run_id
        effective_run_id = _resolve_run_id(run_id)
        if _check_services():
            logger.debug("resolved_run_id", task_id=run_id, db_run_id=effective_run_id)

        from cmbagent.database import get_db_session
        from cmbagent.database.models import CostRecord

        db = get_db_session()

        # Query cost records for this run
        cost_records = db.query(CostRecord).filter(
            CostRecord.run_id == effective_run_id
        ).order_by(CostRecord.timestamp).all()

        # Calculate totals and breakdowns
        total_cost = 0.0
        total_tokens = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        
        model_breakdown = {}
        step_breakdown = {}
        
        for record in cost_records:
            # Totals
            total_cost += float(record.cost_usd)
            total_tokens += record.total_tokens
            total_prompt_tokens += record.prompt_tokens
            total_completion_tokens += record.completion_tokens
            
            # Model breakdown
            if record.model not in model_breakdown:
                model_breakdown[record.model] = {
                    "model": record.model,
                    "cost": 0.0,
                    "tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "call_count": 0
                }
            model_breakdown[record.model]["cost"] += float(record.cost_usd)
            model_breakdown[record.model]["tokens"] += record.total_tokens
            model_breakdown[record.model]["prompt_tokens"] += record.prompt_tokens
            model_breakdown[record.model]["completion_tokens"] += record.completion_tokens
            model_breakdown[record.model]["call_count"] += 1
            
            # Step breakdown
            step_id = record.step_id or "unknown"
            if step_id not in step_breakdown:
                step_breakdown[step_id] = {
                    "step_id": step_id,
                    "cost": 0.0,
                    "tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0
                }
            step_breakdown[step_id]["cost"] += float(record.cost_usd)
            step_breakdown[step_id]["tokens"] += record.total_tokens
            step_breakdown[step_id]["prompt_tokens"] += record.prompt_tokens
            step_breakdown[step_id]["completion_tokens"] += record.completion_tokens

        db.close()

        return {
            "run_id": run_id,
            "resolved_run_id": effective_run_id,
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "record_count": len(cost_records),
            "model_breakdown": list(model_breakdown.values()),
            "step_breakdown": list(step_breakdown.values())
        }

    except Exception as e:
        logger.error("run_costs_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}/console-log")
async def get_console_log(
    run_id: str,
    tail: Optional[int] = None,
    work_dir: Optional[str] = None,
):
    """Get persisted console output log for a workflow run.

    Reads the console_output.log file written in real-time during execution.

    Args:
        run_id: The workflow run ID (task_id)
        tail: If set, return only the last N lines
        work_dir: Optional base work directory override
    """
    import os

    base_dir = work_dir or os.path.expanduser("~/Desktop/cmbdir")
    log_path = os.path.join(base_dir, run_id, "logs", "console_output.log")

    if not os.path.exists(log_path):
        raise HTTPException(
            status_code=404,
            detail=f"Console log not found for run {run_id}"
        )

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        all_lines = content.splitlines()
        lines = all_lines[-tail:] if tail and tail > 0 else all_lines

        return {
            "run_id": run_id,
            "log_path": log_path,
            "total_lines": len(all_lines),
            "returned_lines": len(lines),
            "content": "\n".join(lines),
        }
    except Exception as e:
        logger.error("console_log_read_failed", run_id=run_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}/dag")
async def get_run_dag(run_id: str):
    """Get DAG structure (nodes and edges) for a workflow run.

    Returns the persisted DAG graph data that can be rendered
    by the DAGVisualization component.

    Args:
        run_id: The workflow run ID (can be task_id, will be resolved to db_run_id)
    """
    try:
        effective_run_id = _resolve_run_id(run_id)

        from cmbagent.database import get_db_session
        from cmbagent.database.models import DAGNode, DAGEdge

        db = get_db_session()
        try:
            nodes = db.query(DAGNode).filter(
                DAGNode.run_id == effective_run_id
            ).order_by(DAGNode.order_index).all()

            node_ids = [n.id for n in nodes]

            edges = []
            if node_ids:
                edges = db.query(DAGEdge).filter(
                    DAGEdge.from_node_id.in_(node_ids)
                ).all()

            nodes_data = [
                {
                    "id": n.id,
                    "label": (n.meta or {}).get("label", n.agent or f"Step {n.order_index + 1}"),
                    "type": n.node_type,
                    "status": n.status,
                    "agent": n.agent,
                    "stepNumber": n.order_index + 1,
                    "description": (n.meta or {}).get("description"),
                    "task": (n.meta or {}).get("task"),
                    "summary": (n.meta or {}).get("summary"),
                }
                for n in nodes
            ]

            edges_data = [
                {
                    "id": f"e{e.from_node_id}-{e.to_node_id}",
                    "source": e.from_node_id,
                    "target": e.to_node_id,
                    "type": e.dependency_type,
                }
                for e in edges
            ]

            return {
                "run_id": run_id,
                "resolved_run_id": effective_run_id,
                "nodes": nodes_data,
                "edges": edges_data,
            }
        finally:
            db.close()

    except Exception as e:
        logger.error("run_dag_failed", run_id=run_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
