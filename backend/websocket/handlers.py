"""
WebSocket endpoint and message handlers.
"""

import asyncio
from typing import Any, Dict

from fastapi import WebSocket, WebSocketDisconnect

from websocket.events import send_ws_event

# Active connections storage (fallback when services not available)
active_connections: Dict[str, WebSocket] = {}

# Services will be loaded at runtime
_services_available = None
_workflow_service = None
_connection_manager = None
_execution_service = None


def _check_services():
    """Check if services are available and load them."""
    global _services_available, _workflow_service, _connection_manager, _execution_service
    if _services_available is None:
        try:
            from services import workflow_service, connection_manager, execution_service
            _workflow_service = workflow_service
            _connection_manager = connection_manager
            _execution_service = execution_service
            _services_available = True
        except ImportError:
            _services_available = False
    return _services_available


async def websocket_endpoint(websocket: WebSocket, task_id: str, execute_task_func):
    """Main WebSocket endpoint handler.

    Args:
        websocket: The WebSocket connection
        task_id: The task identifier
        execute_task_func: Function to execute CMBAgent task
    """
    await websocket.accept()

    # Register connection
    services_available = _check_services()
    if services_available:
        await _connection_manager.connect(websocket, task_id)
    else:
        active_connections[task_id] = websocket

    try:
        # Wait for task data
        data = await websocket.receive_json()
        task = data.get("task", "")
        config = data.get("config", {})

        # Debug logging
        print(f"[DEBUG] WebSocket received data for task {task_id}")
        print(f"[DEBUG] Task: {task[:100]}...")
        print(f"[DEBUG] Config mode: {config.get('mode', 'NOT SET')}")
        print(f"[DEBUG] Config keys: {list(config.keys())}")

        if not task:
            await send_ws_event(websocket, "error", {"message": "No task provided"}, run_id=task_id)
            return

        # Create workflow run in database if services available
        if services_available:
            mode = config.get("mode", "one-shot")
            # Extract mode-specific primary agent and model
            if mode == "planning-control":
                agent = "planner"
                model = config.get("plannerModel", config.get("model", "gpt-4o"))
            elif mode == "idea-generation":
                agent = "idea_maker"
                model = config.get("ideaMakerModel", config.get("model", "gpt-4o"))
            elif mode == "ocr":
                agent = "ocr"
                model = "mistral-ocr"
            elif mode == "arxiv":
                agent = "arxiv"
                model = "none"
            elif mode == "enhance-input":
                agent = "enhancer"
                model = config.get("defaultModel", "gpt-4o")
            else:  # one-shot
                agent = config.get("agent", "engineer")
                model = config.get("model", "gpt-4o")

            run_result = _workflow_service.create_workflow_run(
                task_id=task_id,
                task_description=task,
                mode=mode,
                agent=agent,
                model=model,
                config=config
            )
            print(f"Created workflow run: {run_result}")

        # Send initial status
        await send_ws_event(
            websocket, "status",
            {"message": "Starting CMBAgent execution..."},
            run_id=task_id
        )

        # Create background task for execution
        execution_task = asyncio.create_task(
            execute_task_func(websocket, task_id, task, config)
        )

        # Handle both execution and client messages
        while True:
            done, pending = await asyncio.wait(
                [execution_task, asyncio.create_task(websocket.receive_json())],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Check if execution completed
            if execution_task in done:
                break

            # Handle client message
            for task_result in done:
                if task_result != execution_task:
                    try:
                        client_msg = task_result.result()
                        await handle_client_message(websocket, task_id, client_msg)
                    except Exception as e:
                        print(f"Error handling client message: {e}")

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        print(f"Error in WebSocket endpoint: {e}")
        try:
            await send_ws_event(
                websocket, "error",
                {"message": f"Execution error: {str(e)}"},
                run_id=task_id
            )
        except:
            pass
    finally:
        # Disconnect
        if _check_services():
            await _connection_manager.disconnect(task_id)
        elif task_id in active_connections:
            del active_connections[task_id]


async def handle_client_message(websocket: WebSocket, task_id: str, message: dict):
    """Handle messages from client (e.g., approval responses, pause, resume).

    Integrates with Stage 3 (State Machine), Stage 5 (WebSocket Protocol),
    and Stage 6 (HITL Approval System).
    """
    msg_type = message.get("type")
    services_available = _check_services()

    if msg_type == "ping":
        if services_available:
            await _connection_manager.send_pong(task_id)
        else:
            await send_ws_event(websocket, "pong", {}, run_id=task_id)

    elif msg_type in ["resolve_approval", "approval_response"]:
        # Handle approval resolution (Stage 6: HITL)
        approval_id = message.get("approval_id")

        # Support both 'resolution' and 'approved' formats
        if "approved" in message:
            resolution = "approved" if message.get("approved") else "rejected"
        else:
            resolution = message.get("resolution", "rejected")

        feedback = message.get("feedback", "")
        modifications = message.get("modifications", "")

        # Combine feedback and modifications
        full_feedback = f"{feedback}\n\nModifications: {modifications}" if modifications else feedback

        # Try in-memory WebSocket approval manager first (for HITL workflows)
        try:
            from cmbagent.database.websocket_approval_manager import WebSocketApprovalManager

            if WebSocketApprovalManager.has_pending(approval_id):
                modifications_dict = {}
                if modifications:
                    try:
                        import json
                        modifications_dict = json.loads(modifications) if isinstance(modifications, str) else modifications
                    except (json.JSONDecodeError, TypeError):
                        modifications_dict = {"raw": modifications}

                WebSocketApprovalManager.resolve(
                    approval_id=approval_id,
                    resolution=resolution,
                    user_feedback=full_feedback,
                    modifications=modifications_dict,
                )

                print(f"✅ Approval {approval_id} resolved in-memory as {resolution}")

                await send_ws_event(
                    websocket, "approval_received",
                    {
                        "approval_id": approval_id,
                        "approved": resolution in ("approved", "modified"),
                        "resolution": resolution,
                        "feedback": full_feedback,
                    },
                    run_id=task_id,
                )
                return
        except ImportError:
            pass

        # Fall back to database-backed approval manager
        try:
            from cmbagent.database import get_db_session
            from cmbagent.database.models import WorkflowRun, ApprovalRequest
            from cmbagent.database.approval_manager import ApprovalManager

            db = get_db_session()
            try:
                approval = db.query(ApprovalRequest).filter(
                    ApprovalRequest.id == approval_id
                ).first()

                if not approval:
                    print(f"Approval {approval_id} not found")
                    await send_ws_event(
                        websocket, "error",
                        {"message": f"Approval {approval_id} not found"},
                        run_id=task_id
                    )
                    return

                run = db.query(WorkflowRun).filter(
                    WorkflowRun.id == approval.run_id
                ).first()

                if not run:
                    print(f"Workflow run {approval.run_id} not found")
                    return

                approval_manager = ApprovalManager(db, str(run.session_id))
                approval_manager.resolve_approval(
                    approval_id=approval_id,
                    resolution=resolution,
                    user_feedback=full_feedback
                )

                print(f"✅ Approval {approval_id} resolved via DB as {resolution}")

                # Send confirmation back to client
                await send_ws_event(
                    websocket, "approval_received",
                    {
                        "approval_id": approval_id,
                        "approved": resolution == "approved",
                        "feedback": full_feedback
                    },
                    run_id=task_id
                )

            finally:
                db.close()

        except Exception as e:
            print(f"Error resolving approval: {e}")
            await send_ws_event(
                websocket, "error",
                {"message": f"Failed to resolve approval: {str(e)}"},
                run_id=task_id
            )

    elif msg_type == "pause":
        print(f"Pause requested for task {task_id}")

        if services_available:
            result = _workflow_service.pause_workflow(task_id)
            _execution_service.set_paused(task_id, True)
            await _connection_manager.send_workflow_paused(
                task_id, result.get("message", "Workflow paused")
            )
        else:
            await send_ws_event(
                websocket,
                "workflow_paused",
                {"message": "Workflow paused", "status": "paused"},
                run_id=task_id
            )

    elif msg_type == "resume":
        print(f"Resume requested for task {task_id}")

        if services_available:
            result = _workflow_service.resume_workflow(task_id)
            _execution_service.set_paused(task_id, False)
            await _connection_manager.send_workflow_resumed(
                task_id, result.get("message", "Workflow resumed")
            )
        else:
            await send_ws_event(
                websocket,
                "workflow_resumed",
                {"message": "Workflow resumed", "status": "executing"},
                run_id=task_id
            )

    elif msg_type == "cancel":
        print(f"Cancel requested for task {task_id}")

        if services_available:
            result = _workflow_service.cancel_workflow(task_id)
            _execution_service.set_cancelled(task_id, True)
            await _connection_manager.send_workflow_cancelled(
                task_id, result.get("message", "Workflow cancelled")
            )
        else:
            await send_ws_event(
                websocket,
                "workflow_cancelled",
                {"message": "Workflow cancelled", "status": "cancelled"},
                run_id=task_id
            )

    elif msg_type == "request_state":
        print(f"State request for task {task_id}")
        if services_available:
            run_info = _workflow_service.get_run_info(task_id)
            if run_info:
                await _connection_manager.send_status(
                    task_id, run_info.get("status", "unknown")
                )
            # Replay missed events
            since_timestamp = message.get("since")
            await _connection_manager.replay_missed_events(task_id, since_timestamp)

    else:
        print(f"Unknown message type: {msg_type}")
