"""
Workflow branching and DAG management endpoints.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks

from models.schemas import BranchRequest, PlayFromNodeRequest, BranchExecuteRequest

from core.logging import get_logger
logger = get_logger(__name__)

router = APIRouter(tags=["Branching"])


@router.post("/api/runs/{run_id}/branch")
async def create_branch(run_id: str, request: BranchRequest, background_tasks: BackgroundTasks):
    """
    Create a new branch from a specific DAG node.

    The branch will have access to all context from the parent workflow up to the
    branch point. If new_instructions are provided, a NEW planning phase will be
    triggered that:
    1. Is aware of all completed work (will not repeat it)
    2. Has access to all files generated so far
    3. Will create a new plan based on the new instructions
    """
    try:
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import BranchManager, BranchExecutor

        db_session = get_session()
        branch_manager = BranchManager(db_session, run_id)

        new_run_id = branch_manager.create_branch(
            node_id=request.node_id,
            branch_name=request.branch_name,
            hypothesis=request.hypothesis,
            new_instructions=request.new_instructions,
            modifications=request.modifications
        )

        result = {
            "status": "success",
            "branch_run_id": new_run_id,
            "message": f"Branch '{request.branch_name}' created successfully"
        }

        # If execute_immediately is set, prepare and return execution context
        if request.execute_immediately:
            branch_executor = BranchExecutor(db_session, new_run_id)
            execution_context = branch_executor.prepare_for_execution()
            result["execution_context"] = execution_context
            result["status"] = "ready_to_execute"
            result["message"] = f"Branch '{request.branch_name}' created and ready for execution"

        db_session.close()

        return result
    except Exception as e:
        logger.error("branch_create_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error creating branch: {str(e)}"
        )


@router.post("/api/branches/{branch_run_id}/execute")
async def execute_branch(branch_run_id: str, request: BranchExecuteRequest = None):
    """
    Execute a branch workflow.

    This endpoint prepares the branch for execution and returns the execution
    context needed to start the workflow. The actual execution is triggered
    via WebSocket connection.
    """
    try:
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import BranchExecutor

        db_session = get_session()
        branch_executor = BranchExecutor(db_session, branch_run_id)

        # Prepare execution context
        execution_context = branch_executor.prepare_for_execution()

        # Apply config overrides if provided
        if request and request.config_overrides:
            execution_context["config_overrides"].update(request.config_overrides)

        db_session.close()

        return {
            "status": "ready_to_execute",
            "branch_run_id": branch_run_id,
            "execution_context": execution_context,
            "message": "Branch prepared for execution. Connect via WebSocket to start."
        }
    except Exception as e:
        logger.error("branch_execution_prepare_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error preparing branch execution: {str(e)}"
        )


@router.get("/api/branches/{branch_run_id}/context")
async def get_branch_context(branch_run_id: str):
    """
    Get the execution context for a branch.

    Returns the augmented task, plan instructions, and all context
    that will be passed to the planning phase.
    """
    try:
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import BranchExecutor

        db_session = get_session()
        branch_executor = BranchExecutor(db_session, branch_run_id)

        context = branch_executor.build_execution_context()

        db_session.close()

        return {
            "status": "success",
            "context": context
        }
    except Exception as e:
        logger.error("branch_context_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error getting branch context: {str(e)}"
        )


@router.post("/api/runs/{run_id}/play-from-node")
async def play_from_node(run_id: str, request: PlayFromNodeRequest):
    """Resume execution from a specific node."""
    try:
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import PlayFromNodeExecutor

        db_session = get_session()
        executor = PlayFromNodeExecutor(db_session, run_id)

        result = executor.play_from_node(
            node_id=request.node_id,
            context_override=request.context_override
        )

        db_session.close()

        return {
            "status": "success",
            "result": result,
            "message": "Workflow prepared for resumption"
        }
    except Exception as e:
        logger.error("play_from_node_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error resuming from node: {str(e)}"
        )


@router.get("/api/branches/compare")
async def compare_branches(run_id_1: str, run_id_2: str):
    """Compare two workflow branches."""
    try:
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import BranchComparator

        db_session = get_session()
        comparator = BranchComparator(db_session)

        comparison = comparator.compare_branches(run_id_1, run_id_2)

        db_session.close()

        return {
            "status": "success",
            "comparison": comparison
        }
    except Exception as e:
        logger.error("branch_compare_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error comparing branches: {str(e)}"
        )


@router.get("/api/runs/{run_id}/branch-tree")
async def get_branch_tree(run_id: str):
    """Get branch tree visualization."""
    try:
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import BranchComparator

        db_session = get_session()
        comparator = BranchComparator(db_session)

        tree = comparator.visualize_branch_tree(run_id)

        db_session.close()

        return {
            "status": "success",
            "tree": tree
        }
    except Exception as e:
        logger.error("branch_tree_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error getting branch tree: {str(e)}"
        )


@router.get("/api/runs/{run_id}/resumable-nodes")
async def get_resumable_nodes(run_id: str):
    """Get list of nodes that can be resumed from."""
    try:
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import PlayFromNodeExecutor

        db_session = get_session()
        executor = PlayFromNodeExecutor(db_session, run_id)

        nodes = executor.get_resumable_nodes()

        db_session.close()

        return {
            "status": "success",
            "nodes": nodes
        }
    except Exception as e:
        logger.error("resumable_nodes_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error getting resumable nodes: {str(e)}"
        )
