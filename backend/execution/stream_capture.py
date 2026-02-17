"""
Stream capture classes for intercepting stdout/stderr and AG2 events.

StreamCapture: Relay stdout to WebSocket and log file. Zero detection logic.
AG2IOStreamCapture: Intercept AG2 events and forward to WebSocket.
"""

import asyncio
import os
from io import StringIO
from typing import Any, Dict, Optional

from fastapi import WebSocket
from core.logging import get_logger

logger = get_logger(__name__)


class AG2IOStreamCapture:
    """
    Custom AG2 IOStream that intercepts all AG2 events and forwards them to WebSocket.
    This captures all agent messages, tool calls, function responses, etc.
    """

    def __init__(self, websocket: WebSocket, task_id: str, send_event_func, loop=None, session_id: str = None):
        self.websocket = websocket
        self.task_id = task_id
        self.send_event = send_event_func
        self.loop = loop or asyncio.get_event_loop()
        self._original_print = print
        self.session_id = session_id

    def print(self, *objects: Any, sep: str = " ", end: str = "\n", flush: bool = False) -> None:
        """Capture print calls and send to WebSocket"""
        message = sep.join(str(obj) for obj in objects)
        if message.strip():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._send_output(message),
                    self.loop
                )
            except Exception as e:
                logger.warning("ag2_iostream_print_error", error=str(e))
        self._original_print(*objects, sep=sep, end=end, flush=flush)

    def send(self, message) -> None:
        """
        Capture AG2 events and forward to WebSocket.
        AG2 sends BaseEvent objects here with their own print() methods.
        """
        try:
            event_data = self._extract_event_data(message)
            if event_data:
                future = asyncio.run_coroutine_threadsafe(
                    self._send_structured_event(event_data),
                    self.loop
                )
            message.print(self._original_print)
        except AttributeError as e:
            # Silently ignore fileno-related errors - AG2 checking for terminal capabilities
            if 'fileno' not in str(e):
                logger.warning("ag2_iostream_send_error", error=str(e))
            try:
                message.print(self._original_print)
            except:
                pass
        except Exception as e:
            logger.warning("ag2_iostream_send_error", error=str(e))
            try:
                message.print(self._original_print)
            except:
                pass

    def _extract_event_data(self, event) -> Optional[Dict[str, Any]]:
        """Extract structured data from AG2 events"""
        try:
            event_type = type(event).__name__
            actual_event = getattr(event, 'content', event)

            data = {
                "event_type": event_type,
                "sender": getattr(actual_event, 'sender', None),
                "recipient": getattr(actual_event, 'recipient', None),
            }

            if hasattr(actual_event, 'content'):
                content = actual_event.content
                if content is not None:
                    data["content"] = str(content)[:5000]

            if hasattr(actual_event, 'function_call'):
                fc = actual_event.function_call
                if fc:
                    data["function_name"] = getattr(fc, 'name', None)
                    data["function_arguments"] = getattr(fc, 'arguments', None)

            if hasattr(actual_event, 'tool_calls'):
                tool_calls = actual_event.tool_calls
                if tool_calls:
                    data["tool_calls"] = []
                    for tc in tool_calls:
                        tc_data = {
                            "id": getattr(tc, 'id', None),
                            "name": getattr(tc.function, 'name', None) if hasattr(tc, 'function') else None,
                            "arguments": getattr(tc.function, 'arguments', None) if hasattr(tc, 'function') else None,
                        }
                        data["tool_calls"].append(tc_data)

            if hasattr(actual_event, 'tool_responses'):
                tool_responses = actual_event.tool_responses
                if tool_responses:
                    data["tool_responses"] = []
                    for tr in tool_responses:
                        tr_data = {
                            "tool_call_id": getattr(tr, 'tool_call_id', None),
                            "content": str(getattr(tr, 'content', ''))[:2000],
                        }
                        data["tool_responses"].append(tr_data)

            return data
        except Exception as e:
            return {"event_type": "unknown", "error": str(e)}

    async def _send_output(self, message: str):
        """Send output message to WebSocket"""
        try:
            await self.send_event(
                self.websocket,
                "output",
                {"message": message},
                run_id=self.task_id,
                session_id=self.session_id
            )
        except Exception as e:
            logger.warning("ws_output_send_failed", error=str(e))

    async def _send_structured_event(self, event_data: Dict[str, Any]):
        """Send structured AG2 event to WebSocket"""
        try:
            event_type = event_data.get("event_type", "SYSTEM")
            sender = event_data.get("sender", "SYSTEM")
            content = event_data.get("content", "")

            if "ToolCall" in event_type or "FunctionCall" in event_type:
                ws_event_type = "tool_call"
                data = {
                    "agent": sender,
                    "tool_name": event_data.get("function_name") or "SYSTEM",
                    "arguments": event_data.get("function_arguments") or event_data.get("tool_calls", []),
                    "result": None
                }
            elif "ToolResponse" in event_type or "FunctionResponse" in event_type:
                ws_event_type = "tool_call"
                data = {
                    "agent": sender,
                    "tool_name": event_data.get("name", "SYSTEM"),
                    "arguments": {},
                    "result": content
                }
            elif "Text" in event_type or "Received" in event_type:
                ws_event_type = "agent_message"
                data = {
                    "agent": sender,
                    "role": "assistant",
                    "message": content,
                    "metadata": {"recipient": event_data.get("recipient")}
                }
            else:
                ws_event_type = "agent_message"
                data = {
                    "agent": sender or "system",
                    "role": "system",
                    "message": f"[{event_type}] {content}" if content else f"[{event_type}]",
                    "metadata": event_data
                }

            await self.send_event(
                self.websocket,
                ws_event_type,
                data,
                run_id=self.task_id,
                session_id=self.session_id
            )
        except Exception as e:
            logger.warning("ws_structured_event_failed", error=str(e))

    def input(self, prompt: str = "", *, password: bool = False) -> str:
        """Handle input requests - not typically used in autonomous mode"""
        return ""


class StreamCapture:
    """Relay stdout to WebSocket and log file. Zero detection logic."""

    def __init__(self, websocket: WebSocket, task_id: str, send_event_func,
                 loop=None, work_dir=None, session_id: str = None):
        self.websocket = websocket
        self.task_id = task_id
        self.send_event = send_event_func
        self.buffer = StringIO()
        self.loop = loop
        self.session_id = session_id

        # File-based console log persistence
        self._log_file = None
        if work_dir:
            try:
                log_dir = os.path.join(work_dir, "logs")
                os.makedirs(log_dir, exist_ok=True)
                log_path = os.path.join(log_dir, "console_output.log")
                self._log_file = open(log_path, "a", encoding="utf-8")
            except Exception as e:
                logger.warning("console_log_file_open_failed", error=str(e))

    async def write(self, text: str):
        """Write text to buffer and send to WebSocket."""
        if text.strip():
            try:
                await self.send_event(
                    self.websocket,
                    "output",
                    {"message": text.strip()},
                    run_id=self.task_id,
                    session_id=self.session_id
                )
            except Exception as e:
                logger.warning("ws_stream_send_failed", error=str(e))

        self.buffer.write(text)

        if self._log_file:
            try:
                self._log_file.write(text)
                self._log_file.flush()
            except Exception:
                pass

        return len(text)

    def flush(self):
        pass

    def getvalue(self):
        return self.buffer.getvalue()

    def close(self):
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None
