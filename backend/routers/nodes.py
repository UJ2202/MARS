"""
DAG node events and files endpoints.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["Nodes"])

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


@router.get("/nodes/{node_id}/events")
async def get_node_events(
    node_id: str,
    run_id: Optional[str] = None,
    event_type: Optional[str] = None,
    include_internal: bool = False
):
    """Get execution events for a DAG node.

    Args:
        node_id: The DAG node ID
        run_id: Optional workflow run ID to filter events (RECOMMENDED)
        event_type: Optional filter by event type
        include_internal: If True, include node_started/completed events
    """
    try:
        from cmbagent.database import get_db_session
        from cmbagent.database.models import DAGNode, ExecutionEvent

        db = get_db_session()

        # Resolve task_id to db_run_id before querying
        effective_run_id = None
        if run_id:
            effective_run_id = _resolve_run_id(run_id)
            print(f"[API] Resolved task_id {run_id} to db_run_id {effective_run_id}")

        # If no run_id provided, try to find the node and get its run_id
        if not effective_run_id:
            from cmbagent.database.models import WorkflowRun
            dag_node = db.query(DAGNode).join(WorkflowRun).filter(
                DAGNode.id == node_id
            ).order_by(WorkflowRun.started_at.desc()).first()

            if dag_node:
                effective_run_id = dag_node.run_id
                print(f"[API] Found node {node_id} in run {effective_run_id} (most recent)")

        # Require run_id for accurate filtering
        if not effective_run_id:
            print(f"[API] ERROR: No run_id found for node {node_id}")
            return {
                "node_id": node_id,
                "total_events": 0,
                "events": [],
                "error": "run_id is required to fetch events."
            }

        # Build query with mandatory run_id filter
        query = db.query(ExecutionEvent).filter(
            ExecutionEvent.node_id == node_id,
            ExecutionEvent.run_id == effective_run_id
        )

        if event_type:
            query = query.filter(ExecutionEvent.event_type == event_type)

        events = query.order_by(ExecutionEvent.execution_order).all()

        # Filter out internal events unless requested
        if not include_internal:
            events = [e for e in events if e.event_type not in ['node_started', 'node_completed']]
            events = [e for e in events if e.event_subtype not in ['start']]

        # Convert to JSON-serializable format
        events_data = [
            {
                "id": e.id,
                "event_type": e.event_type,
                "event_subtype": e.event_subtype,
                "agent_name": e.agent_name,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "duration_ms": e.duration_ms,
                "execution_order": e.execution_order,
                "depth": e.depth,
                "inputs": e.inputs,
                "outputs": e.outputs,
                "error_message": e.error_message,
                "status": e.status,
                "meta": e.meta,
                "parent_event_id": e.parent_event_id
            }
            for e in events
        ]

        db.close()

        return {
            "node_id": node_id,
            "total_events": len(events_data),
            "events": events_data
        }

    except Exception as e:
        print(f"[API] Error getting node events for {node_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes/{node_id}/execution-summary")
async def get_node_execution_summary(node_id: str, run_id: Optional[str] = None):
    """Get execution summary for a DAG node.

    Args:
        node_id: The DAG node ID
        run_id: Optional workflow run ID
    """
    try:
        from cmbagent.database import get_db_session
        from cmbagent.database.models import DAGNode
        from cmbagent.database.dag_metadata import DAGMetadataEnricher
        from cmbagent.database.session_manager import SessionManager

        db = get_db_session()

        # If no run_id provided, try to find it from the most recent node
        if not run_id:
            from cmbagent.database.models import WorkflowRun
            dag_node = db.query(DAGNode).join(WorkflowRun).filter(
                DAGNode.id == node_id
            ).order_by(WorkflowRun.started_at.desc()).first()

            if dag_node:
                run_id = dag_node.run_id
                print(f"[API] Found node {node_id} in run {run_id} (most recent)")

        session_manager = SessionManager(db)
        session_id = session_manager.get_or_create_default_session()

        enricher = DAGMetadataEnricher(db, session_id)

        summary = enricher.enrich_node(node_id, run_id=run_id)
        db.close()

        return summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes/{node_id}/files")
async def get_node_files(node_id: str, run_id: Optional[str] = None):
    """Get files generated by a DAG node.

    Args:
        node_id: The DAG node ID
        run_id: Optional workflow run ID
    """
    try:
        from cmbagent.database import get_db_session
        from cmbagent.database.models import File, DAGNode, WorkflowRun

        db = get_db_session()

        # If no run_id provided, try to find it from the most recent node
        if not run_id:
            dag_node = db.query(DAGNode).join(WorkflowRun).filter(
                DAGNode.id == node_id
            ).order_by(WorkflowRun.started_at.desc()).first()

            if dag_node:
                run_id = dag_node.run_id

        # Filter files by both node_id and run_id if available
        query = db.query(File).filter(File.node_id == node_id)
        if run_id:
            query = query.filter(File.run_id == run_id)

        files = query.all()

        files_data = [
            {
                "id": f.id,
                "file_path": f.file_path,
                "file_type": f.file_type,
                "size_bytes": f.size_bytes,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "event_id": f.event_id
            }
            for f in files
        ]

        db.close()

        return {
            "node_id": node_id,
            "total_files": len(files_data),
            "files": files_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/{event_id}/tree")
async def get_event_tree(event_id: str):
    """Get event tree (nested events) from root event."""
    try:
        from cmbagent.database import get_db_session
        from cmbagent.database.repository import EventRepository
        from cmbagent.database.session_manager import SessionManager

        db = get_db_session()
        session_manager = SessionManager(db)
        session_id = session_manager.get_or_create_default_session()

        event_repo = EventRepository(db, session_id)

        tree = event_repo.get_event_tree(event_id)

        tree_data = [
            {
                "id": e.id,
                "event_type": e.event_type,
                "agent_name": e.agent_name,
                "execution_order": e.execution_order,
                "depth": e.depth,
                "parent_event_id": e.parent_event_id
            }
            for e in tree
        ]

        db.close()

        return {
            "root_event_id": event_id,
            "total_events": len(tree_data),
            "tree": tree_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
