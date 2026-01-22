"""
WebSocket Manager for CMBAgent

This module provides a stateless WebSocket connection manager that:
- Stores all state in the database
- Sends current state on reconnection
- Manages event delivery through the event queue
- Handles client messages (pause, resume, etc.)
"""

import asyncio
import json
from typing import Dict, Optional
import datetime
from fastapi import WebSocket

from backend.websocket_events import (
    WebSocketEvent,
    WebSocketEventType,
    create_workflow_state_changed_event,
    create_dag_created_event,
    create_error_event
)
from backend.event_queue import event_queue


class WebSocketManager:
    """Manages WebSocket connections (stateless)"""

    def __init__(self):
        # Only track active connections, no state
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, run_id: str):
        """
        Accept WebSocket connection and send current state

        Args:
            websocket: FastAPI WebSocket connection
            run_id: Workflow run ID
        """
        await websocket.accept()
        self.active_connections[run_id] = websocket

        # Send connection event
        event = WebSocketEvent(
            event_type=WebSocketEventType.CONNECTED,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            data={"message": "Connected to workflow"}
        )
        await self.send_event(run_id, event)

        # Send current state from database
        await self.send_current_state(run_id)

    async def disconnect(self, run_id: str):
        """
        Handle disconnection

        Args:
            run_id: Workflow run ID
        """
        if run_id in self.active_connections:
            del self.active_connections[run_id]

    async def send_current_state(self, run_id: str):
        """
        Send current workflow state from database
        Called on new connection to synchronize client

        Args:
            run_id: Workflow run ID
        """
        try:
            # Import here to avoid circular dependencies
            from cmbagent.database import get_db_session
            from cmbagent.database.models import WorkflowRun

            db = get_db_session()
            try:
                # Load workflow from database
                run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()

                if not run:
                    await self.send_event(run_id, create_error_event(
                        run_id=run_id,
                        error_type="NotFound",
                        message=f"Run {run_id} not found"
                    ))
                    return

                # Send workflow state
                await self.send_event(
                    run_id,
                    create_workflow_state_changed_event(
                        run_id=run_id,
                        status=run.status,
                        started_at=run.started_at,
                        completed_at=run.completed_at,
                        error=run.error
                    )
                )

                # Send DAG if exists
                try:
                    from cmbagent.database.dag_visualizer import DAGVisualizer
                    viz = DAGVisualizer(db)
                    dag_data = viz.export_for_ui(run_id)

                    if dag_data.get("nodes"):
                        await self.send_event(
                            run_id,
                            create_dag_created_event(
                                run_id=run_id,
                                nodes=dag_data["nodes"],
                                edges=dag_data["edges"],
                                levels=dag_data.get("levels", 0)
                            )
                        )
                except ImportError:
                    # DAG visualizer not available, skip
                    pass
                except Exception as e:
                    print(f"Warning: Could not load DAG for run {run_id}: {e}")

                # Send queued events (missed during disconnect)
                queued_events = event_queue.get_all_events(run_id)
                for event in queued_events:
                    await self.send_event(run_id, event)

            finally:
                db.close()

        except ImportError:
            # Database not available, send basic connection message
            print(f"Warning: Database not available, cannot send current state for run {run_id}")
        except Exception as e:
            print(f"Error sending current state for run {run_id}: {e}")
            await self.send_event(run_id, create_error_event(
                run_id=run_id,
                error_type="StateLoadError",
                message=f"Error loading current state: {str(e)}"
            ))

    async def send_event(self, run_id: str, event: WebSocketEvent):
        """
        Send event to connected client

        Args:
            run_id: Workflow run ID
            event: WebSocket event to send
        """
        # Queue event for later retrieval
        event_queue.push(run_id, event)

        # Send to active connection if exists
        if run_id in self.active_connections:
            try:
                websocket = self.active_connections[run_id]
                # Use model_dump() for Pydantic v2 or dict() for v1
                try:
                    event_dict = event.model_dump()
                except AttributeError:
                    event_dict = event.dict()
                await websocket.send_text(json.dumps(event_dict, default=str))
            except Exception as e:
                print(f"Error sending event to WebSocket for run {run_id}: {e}")
                # Connection broken, remove from active
                await self.disconnect(run_id)

    async def broadcast_event(self, event: WebSocketEvent):
        """
        Broadcast event to all connected clients for this run

        Args:
            event: WebSocket event to broadcast
        """
        if event.run_id:
            await self.send_event(event.run_id, event)

    async def handle_client_message(self, run_id: str, message: dict):
        """
        Handle messages from client

        Args:
            run_id: Workflow run ID
            message: Message dictionary from client
        """
        msg_type = message.get("type")

        if msg_type == "ping":
            # Respond with pong
            await self.send_event(run_id, WebSocketEvent(
                event_type=WebSocketEventType.PONG,
                timestamp=datetime.utcnow(),
                run_id=run_id,
                data={}
            ))

        elif msg_type == "request_state":
            # Re-send current state
            await self.send_current_state(run_id)

        elif msg_type == "pause":
            # Pause workflow
            try:
                from cmbagent.database import get_db_session
                from cmbagent.database.workflow_controller import WorkflowController

                db = get_db_session()
                try:
                    controller = WorkflowController(db, message.get("session_id"))
                    controller.pause_workflow(run_id)

                    # Send paused event
                    await self.send_event(run_id, WebSocketEvent(
                        event_type=WebSocketEventType.WORKFLOW_PAUSED,
                        timestamp=datetime.utcnow(),
                        run_id=run_id,
                        data={"message": "Workflow paused"}
                    ))
                finally:
                    db.close()
            except ImportError:
                await self.send_event(run_id, create_error_event(
                    run_id=run_id,
                    error_type="FeatureNotAvailable",
                    message="Workflow control not available (database not configured)"
                ))
            except Exception as e:
                await self.send_event(run_id, create_error_event(
                    run_id=run_id,
                    error_type="PauseError",
                    message=f"Error pausing workflow: {str(e)}"
                ))

        elif msg_type == "resume":
            # Resume workflow
            try:
                from cmbagent.database import get_db_session
                from cmbagent.database.workflow_controller import WorkflowController

                db = get_db_session()
                try:
                    controller = WorkflowController(db, message.get("session_id"))
                    controller.resume_workflow(run_id)

                    # Send resumed event
                    await self.send_event(run_id, WebSocketEvent(
                        event_type=WebSocketEventType.WORKFLOW_RESUMED,
                        timestamp=datetime.utcnow(),
                        run_id=run_id,
                        data={"message": "Workflow resumed"}
                    ))
                finally:
                    db.close()
            except ImportError:
                await self.send_event(run_id, create_error_event(
                    run_id=run_id,
                    error_type="FeatureNotAvailable",
                    message="Workflow control not available (database not configured)"
                ))
            except Exception as e:
                await self.send_event(run_id, create_error_event(
                    run_id=run_id,
                    error_type="ResumeError",
                    message=f"Error resuming workflow: {str(e)}"
                ))


# Global WebSocket manager instance
ws_manager = WebSocketManager()
