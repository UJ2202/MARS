"""
Workflow run history and files endpoints.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException

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
            print(f"[API] Resolved task_id {run_id} to db_run_id {effective_run_id}")

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

            print(f"[API] Found {len(events_data)} events for run_id={effective_run_id}")
            db.close()
        except Exception as db_err:
            print(f"Database query failed for run_id={effective_run_id}: {db_err}")
            import traceback
            traceback.print_exc()

        # If no database events found, try the in-memory event queue
        if not events_data:
            try:
                from event_queue import event_queue

                ws_events = event_queue.get_all_events(run_id)
                print(f"Found {len(ws_events)} events in event queue for run {run_id}")

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
                print(f"Event queue query failed: {queue_err}")

        return {
            "run_id": run_id,
            "resolved_run_id": effective_run_id,
            "total_events": len(events_data),
            "events": events_data
        }

    except Exception as e:
        print(f"Error getting run history: {str(e)}")
        import traceback
        traceback.print_exc()
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
        print(f"Error getting run files: {str(e)}")
        import traceback
        traceback.print_exc()
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
            print(f"[API] Resolved task_id {run_id} to db_run_id {effective_run_id}")

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
        print(f"Error getting run costs: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
