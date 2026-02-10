"""
Phase and Workflow API endpoints.

This module provides REST API endpoints for the phase-based workflow system:
- Phase type listing and information
- Workflow definition CRUD operations
- Workflow execution
- Run status monitoring
"""

import uuid
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks

from models.phase_schemas import (
    PhaseDefinitionResponse,
    PhaseTypeInfo,
    PhaseConfigSchemaResponse,
    WorkflowDefinitionCreate,
    WorkflowDefinitionResponse,
    WorkflowListItemResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
    WorkflowRunStatusResponse,
    PhaseExecutionResponse,
    WorkflowValidationRequest,
    WorkflowValidationResponse,
    PhaseStatusEnum,
)

router = APIRouter(prefix="/api/phases", tags=["Phases & Workflows"])


# =============================================================================
# In-memory storage (would be database in production)
# =============================================================================

# Storage for custom workflow definitions
custom_workflows: Dict[str, Dict[str, Any]] = {}

# Storage for active workflow runs
workflow_runs: Dict[str, Dict[str, Any]] = {}


# =============================================================================
# Phase Type Endpoints
# =============================================================================

@router.get("/types", response_model=List[PhaseTypeInfo])
async def list_phase_types():
    """
    List all available phase types.

    Returns information about each registered phase type including
    display name and required agents.
    """
    from cmbagent.phases import PhaseRegistry

    return [
        PhaseTypeInfo(
            type=info['type'],
            display_name=info['display_name'],
            required_agents=info['required_agents'],
        )
        for info in PhaseRegistry.list_all_info()
    ]


@router.get("/types/{phase_type}", response_model=PhaseTypeInfo)
async def get_phase_type(phase_type: str):
    """
    Get details of a specific phase type.

    Args:
        phase_type: The phase type identifier (e.g., "planning", "control")
    """
    from cmbagent.phases import PhaseRegistry

    if not PhaseRegistry.is_registered(phase_type):
        raise HTTPException(
            status_code=404,
            detail=f"Phase type '{phase_type}' not found. Available: {PhaseRegistry.list_all()}"
        )

    info = PhaseRegistry.get_info(phase_type)
    return PhaseTypeInfo(
        type=info['type'],
        display_name=info['display_name'],
        required_agents=info['required_agents'],
    )


@router.get("/types/{phase_type}/config-schema", response_model=PhaseConfigSchemaResponse)
async def get_phase_config_schema(phase_type: str):
    """
    Get JSON schema for phase configuration.

    Returns the configuration schema for a specific phase type,
    useful for building dynamic configuration UIs.
    """
    from cmbagent.phases import PhaseRegistry

    if not PhaseRegistry.is_registered(phase_type):
        raise HTTPException(status_code=404, detail=f"Phase type '{phase_type}' not found")

    # Get config class schema
    phase_class = PhaseRegistry.get(phase_type)
    config_class = getattr(phase_class, 'config_class', None)

    if config_class:
        # Generate schema from dataclass
        import dataclasses
        schema = {
            "type": "object",
            "properties": {}
        }
        for f in dataclasses.fields(config_class):
            schema["properties"][f.name] = {
                "type": _python_type_to_json(f.type),
                "default": f.default if f.default != dataclasses.MISSING else None
            }
        return PhaseConfigSchemaResponse(phase_type=phase_type, schema=schema)

    return PhaseConfigSchemaResponse(phase_type=phase_type, schema={})


def _python_type_to_json(python_type) -> str:
    """Convert Python type to JSON schema type."""
    type_str = str(python_type)
    if 'int' in type_str:
        return 'integer'
    elif 'float' in type_str:
        return 'number'
    elif 'bool' in type_str:
        return 'boolean'
    elif 'str' in type_str:
        return 'string'
    elif 'List' in type_str or 'list' in type_str:
        return 'array'
    elif 'Dict' in type_str or 'dict' in type_str:
        return 'object'
    return 'string'


# =============================================================================
# Workflow Definition Endpoints
# =============================================================================

@router.get("/workflows", response_model=List[WorkflowListItemResponse])
async def list_workflows(include_system: bool = True):
    """
    List all available workflow definitions.

    Args:
        include_system: Whether to include system-defined workflows
    """
    from cmbagent.workflows import list_workflows as list_system_workflows

    workflows = []

    # Add system workflows
    if include_system:
        for wf in list_system_workflows():
            workflows.append(WorkflowListItemResponse(
                id=wf['id'],
                name=wf['name'],
                description=wf['description'],
                num_phases=wf['num_phases'],
                is_system=wf['is_system'],
            ))

    # Add custom workflows
    for wf_id, wf in custom_workflows.items():
        workflows.append(WorkflowListItemResponse(
            id=wf_id,
            name=wf['name'],
            description=wf['description'],
            num_phases=len(wf['phases']),
            is_system=False,
        ))

    return workflows


@router.get("/workflows/{workflow_id}", response_model=WorkflowDefinitionResponse)
async def get_workflow(workflow_id: str):
    """
    Get a workflow definition by ID.

    Args:
        workflow_id: The workflow identifier
    """
    from cmbagent.workflows import SYSTEM_WORKFLOWS

    # Check system workflows
    if workflow_id in SYSTEM_WORKFLOWS:
        wf = SYSTEM_WORKFLOWS[workflow_id]
        return WorkflowDefinitionResponse(
            id=wf.id,
            name=wf.name,
            description=wf.description,
            phases=wf.phases,
            version=wf.version,
            is_system=wf.is_system,
            created_by=wf.created_by,
        )

    # Check custom workflows
    if workflow_id in custom_workflows:
        wf = custom_workflows[workflow_id]
        return WorkflowDefinitionResponse(
            id=workflow_id,
            name=wf['name'],
            description=wf['description'],
            phases=wf['phases'],
            version=wf.get('version', 1),
            is_system=False,
            created_by=wf.get('created_by'),
        )

    raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")


@router.post("/workflows", response_model=WorkflowDefinitionResponse)
async def create_workflow(workflow: WorkflowDefinitionCreate):
    """
    Create a new custom workflow definition.

    The workflow is validated before creation to ensure all
    phase types are valid and configurations are correct.
    """
    from cmbagent.phases import PhaseRegistry

    # Validate phase types
    for phase_def in workflow.phases:
        if not PhaseRegistry.is_registered(phase_def.type):
            raise HTTPException(
                status_code=400,
                detail=f"Unknown phase type: {phase_def.type}"
            )

    # Generate ID
    workflow_id = f"custom_{uuid.uuid4().hex[:8]}"

    # Store workflow
    custom_workflows[workflow_id] = {
        'name': workflow.name,
        'description': workflow.description,
        'phases': [{'type': p.type, 'config': p.config} for p in workflow.phases],
        'version': 1,
        'created_at': datetime.now().isoformat(),
    }

    return WorkflowDefinitionResponse(
        id=workflow_id,
        name=workflow.name,
        description=workflow.description,
        phases=[{'type': p.type, 'config': p.config} for p in workflow.phases],
        version=1,
        is_system=False,
    )


@router.put("/workflows/{workflow_id}", response_model=WorkflowDefinitionResponse)
async def update_workflow(workflow_id: str, workflow: WorkflowDefinitionCreate):
    """
    Update a custom workflow definition.

    System workflows cannot be modified.
    """
    from cmbagent.workflows import SYSTEM_WORKFLOWS

    if workflow_id in SYSTEM_WORKFLOWS:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify system workflows"
        )

    if workflow_id not in custom_workflows:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    # Update workflow
    existing = custom_workflows[workflow_id]
    custom_workflows[workflow_id] = {
        'name': workflow.name,
        'description': workflow.description,
        'phases': [{'type': p.type, 'config': p.config} for p in workflow.phases],
        'version': existing.get('version', 1) + 1,
        'created_at': existing.get('created_at'),
        'updated_at': datetime.now().isoformat(),
    }

    return WorkflowDefinitionResponse(
        id=workflow_id,
        name=workflow.name,
        description=workflow.description,
        phases=[{'type': p.type, 'config': p.config} for p in workflow.phases],
        version=custom_workflows[workflow_id]['version'],
        is_system=False,
    )


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """
    Delete a custom workflow definition.

    System workflows cannot be deleted.
    """
    from cmbagent.workflows import SYSTEM_WORKFLOWS

    if workflow_id in SYSTEM_WORKFLOWS:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete system workflows"
        )

    if workflow_id not in custom_workflows:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    del custom_workflows[workflow_id]
    return {"success": True, "message": f"Workflow '{workflow_id}' deleted"}


@router.post("/workflows/validate", response_model=WorkflowValidationResponse)
async def validate_workflow(request: WorkflowValidationRequest):
    """
    Validate a workflow definition.

    Checks that all phase types are valid and configurations
    are compatible with each other.
    """
    from cmbagent.phases import PhaseRegistry

    errors = []
    warnings = []

    if not request.phases:
        errors.append("Workflow must have at least one phase")

    for i, phase_def in enumerate(request.phases):
        # Check phase type exists
        if not PhaseRegistry.is_registered(phase_def.type):
            errors.append(f"Phase {i+1}: Unknown phase type '{phase_def.type}'")
            continue

        # Validate configuration
        try:
            phase = PhaseRegistry.create_from_dict({
                'type': phase_def.type,
                'config': phase_def.config
            })
        except Exception as e:
            errors.append(f"Phase {i+1} ({phase_def.type}): Invalid config - {e}")

    # Check for common issues
    phase_types = [p.type for p in request.phases]

    if 'control' in phase_types and 'planning' not in phase_types:
        warnings.append("Control phase without planning phase - ensure plan is provided externally")

    return WorkflowValidationResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


# =============================================================================
# Workflow Execution Endpoints
# =============================================================================

@router.post("/workflows/{workflow_id}/run", response_model=WorkflowRunResponse)
async def run_workflow(
    workflow_id: str,
    request: WorkflowRunRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a workflow run.

    The workflow executes asynchronously in the background.
    Use the returned run_id to check status or connect via WebSocket.
    """
    from cmbagent.workflows import SYSTEM_WORKFLOWS, WorkflowDefinition, WorkflowExecutor
    from cmbagent.utils import get_api_keys_from_env
    import os

    # Get workflow definition
    if workflow_id in SYSTEM_WORKFLOWS:
        workflow_def = SYSTEM_WORKFLOWS[workflow_id]
    elif workflow_id in custom_workflows:
        wf = custom_workflows[workflow_id]
        workflow_def = WorkflowDefinition(
            id=workflow_id,
            name=wf['name'],
            description=wf['description'],
            phases=wf['phases'],
        )
    else:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    # Generate run ID
    run_id = str(uuid.uuid4())

    # Setup work directory
    work_dir = request.work_dir or "~/cmbagent_workdir"
    work_dir = os.path.abspath(os.path.expanduser(work_dir))

    # Get API keys
    api_keys = get_api_keys_from_env()

    # Initialize run record
    workflow_runs[run_id] = {
        'run_id': run_id,
        'workflow_id': workflow_id,
        'workflow_name': workflow_def.name,
        'task': request.task,
        'work_dir': work_dir,
        'status': 'pending',
        'current_phase': 0,
        'total_phases': len(workflow_def.phases),
        'phase_results': [],
        'created_at': datetime.now().isoformat(),
        'config_overrides': request.config_overrides,
    }

    # Start execution in background
    background_tasks.add_task(
        _execute_workflow_background,
        run_id,
        workflow_def,
        request.task,
        work_dir,
        api_keys,
        request.config_overrides,
    )

    return WorkflowRunResponse(
        run_id=run_id,
        workflow_id=workflow_id,
        workflow_name=workflow_def.name,
        status="pending",
        message=f"Workflow run started. Monitor progress at /api/phases/runs/{run_id}",
        num_phases=len(workflow_def.phases),
    )


async def _execute_workflow_background(
    run_id: str,
    workflow_def,
    task: str,
    work_dir: str,
    api_keys: Dict[str, str],
    config_overrides: Optional[Dict[str, Any]] = None,
):
    """Background task to execute a workflow."""
    from cmbagent.workflows import WorkflowExecutor

    # Update status
    workflow_runs[run_id]['status'] = 'running'
    workflow_runs[run_id]['started_at'] = datetime.now().isoformat()

    try:
        # Create executor
        executor = WorkflowExecutor(
            workflow=workflow_def,
            task=task,
            work_dir=work_dir,
            api_keys=api_keys,
        )

        # Run workflow
        result = await executor.run()

        # Update run record with success
        workflow_runs[run_id]['status'] = 'completed'
        workflow_runs[run_id]['completed_at'] = datetime.now().isoformat()
        workflow_runs[run_id]['result'] = result.to_dict()
        workflow_runs[run_id]['phase_timings'] = result.phase_timings

        # Update phase results
        workflow_runs[run_id]['phase_results'] = [
            {
                'phase_id': r.context.phase_id,
                'phase_type': r.context.phase_id.split('_')[-1] if '_' in r.context.phase_id else r.context.phase_id,
                'status': r.status.value,
                'error': r.error,
                'timing': r.timing,
            }
            for r in executor.results
        ]

    except Exception as e:
        import traceback
        workflow_runs[run_id]['status'] = 'failed'
        workflow_runs[run_id]['error'] = str(e)
        workflow_runs[run_id]['traceback'] = traceback.format_exc()
        workflow_runs[run_id]['completed_at'] = datetime.now().isoformat()


@router.get("/runs/{run_id}", response_model=WorkflowRunStatusResponse)
async def get_run_status(run_id: str):
    """
    Get the status of a workflow run.

    Returns current phase, completion status, and results.
    """
    if run_id not in workflow_runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    run = workflow_runs[run_id]

    return WorkflowRunStatusResponse(
        run_id=run_id,
        workflow_id=run['workflow_id'],
        status=run['status'],
        current_phase=run.get('current_phase', 0),
        total_phases=run['total_phases'],
        phase_results=[
            PhaseExecutionResponse(
                phase_id=pr.get('phase_id', f"phase_{i}"),
                phase_type=pr.get('phase_type', 'unknown'),
                display_name=pr.get('display_name', pr.get('phase_type', 'Unknown')),
                status=PhaseStatusEnum(pr.get('status', 'pending')),
                error=pr.get('error'),
                timing=pr.get('timing'),
            )
            for i, pr in enumerate(run.get('phase_results', []))
        ],
        total_time=run.get('phase_timings', {}).get('total'),
    )


@router.get("/runs/{run_id}/phases")
async def get_run_phases(run_id: str):
    """Get detailed phase execution info for a run."""
    if run_id not in workflow_runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    return workflow_runs[run_id].get('phase_results', [])


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str):
    """
    Request to stop a running workflow.

    The workflow will stop after the current phase completes.
    """
    if run_id not in workflow_runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    run = workflow_runs[run_id]
    if run['status'] not in ['pending', 'running']:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot stop run with status '{run['status']}'"
        )

    # Mark for stopping (would need to implement actual stopping mechanism)
    run['stop_requested'] = True
    run['status'] = 'stopping'

    return {"success": True, "message": "Stop requested"}


@router.get("/runs")
async def list_runs(
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    """
    List workflow runs.

    Args:
        workflow_id: Filter by workflow ID
        status: Filter by status (pending, running, completed, failed)
        limit: Maximum number of runs to return
    """
    runs = list(workflow_runs.values())

    # Apply filters
    if workflow_id:
        runs = [r for r in runs if r['workflow_id'] == workflow_id]
    if status:
        runs = [r for r in runs if r['status'] == status]

    # Sort by creation time (newest first)
    runs.sort(key=lambda r: r.get('created_at', ''), reverse=True)

    # Apply limit
    runs = runs[:limit]

    return [
        {
            'run_id': r['run_id'],
            'workflow_id': r['workflow_id'],
            'workflow_name': r['workflow_name'],
            'status': r['status'],
            'created_at': r.get('created_at'),
            'completed_at': r.get('completed_at'),
        }
        for r in runs
    ]
