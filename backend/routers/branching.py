"""
Workflow branching and DAG management endpoints.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException

from models.schemas import BranchRequest, PlayFromNodeRequest

router = APIRouter(tags=["Branching"])


@router.post("/api/runs/{run_id}/branch")
async def create_branch(run_id: str, request: BranchRequest):
    """Create a new branch from a specific step."""
    try:
        from cmbagent.database import get_db_session as get_session
        from cmbagent.branching import BranchManager

        db_session = get_session()
        branch_manager = BranchManager(db_session, run_id)

        new_run_id = branch_manager.create_branch(
            step_id=request.step_id,
            branch_name=request.branch_name,
            hypothesis=request.hypothesis,
            modifications=request.modifications
        )

        db_session.close()

        return {
            "status": "success",
            "branch_run_id": new_run_id,
            "message": f"Branch '{request.branch_name}' created successfully"
        }
    except Exception as e:
        print(f"Error creating branch: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating branch: {str(e)}"
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
        print(f"Error in play-from-node: {str(e)}")
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
        print(f"Error comparing branches: {str(e)}")
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
        print(f"Error getting branch tree: {str(e)}")
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
        print(f"Error getting resumable nodes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting resumable nodes: {str(e)}"
        )
