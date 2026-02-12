"""
WebSocket event helpers and utilities.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from core.logging import get_logger

logger = get_logger(__name__)


async def send_ws_event(
    websocket: WebSocket,
    event_type: str,
    data: Dict[str, Any] = None,
    run_id: str = None,
    session_id: str = None
) -> bool:
    """Send a WebSocket event in the standardized protocol format.

    This helper ensures all WebSocket messages follow the event protocol:
    - event_type: The type of event (e.g., 'output', 'status', 'workflow_started')
    - timestamp: ISO format timestamp
    - run_id: Optional run identifier
    - session_id: Optional session identifier
    - data: Event-specific data payload

    Returns:
        bool: True if sent successfully, False otherwise
    """
    # Check connection state before sending
    try:
        if websocket.client_state != WebSocketState.CONNECTED:
            logger.debug("WebSocket not connected, skipping event", event_type=event_type)
            return False
    except Exception:
        # If we can't check state, try to send anyway
        pass

    message = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": data or {}
    }

    if run_id:
        message["run_id"] = run_id
    if session_id:
        message["session_id"] = session_id

    try:
        await websocket.send_json(message)
        return True
    except Exception as e:
        logger.warning("Failed to send WebSocket event %s: %s", event_type, e)
        return False
