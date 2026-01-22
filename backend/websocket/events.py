"""
WebSocket event helpers and utilities.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import WebSocket


async def send_ws_event(
    websocket: WebSocket,
    event_type: str,
    data: Dict[str, Any] = None,
    run_id: str = None,
    session_id: str = None
):
    """Send a WebSocket event in the standardized protocol format.

    This helper ensures all WebSocket messages follow the event protocol:
    - event_type: The type of event (e.g., 'output', 'status', 'workflow_started')
    - timestamp: ISO format timestamp
    - run_id: Optional run identifier
    - session_id: Optional session identifier
    - data: Event-specific data payload
    """
    message = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": data or {}
    }

    if run_id:
        message["run_id"] = run_id
    if session_id:
        message["session_id"] = session_id

    await websocket.send_json(message)
