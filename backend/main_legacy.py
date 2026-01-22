import asyncio
import json
import os
import sys
import time
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Dict, Any, Optional, List
import uuid
import mimetypes
import re

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# Import WebSocket event helpers
try:
    from websocket_events import (
        create_dag_created_event,
        create_dag_node_status_changed_event,
        create_workflow_started_event,
        create_workflow_completed_event,
        create_step_started_event,
        create_step_completed_event,
        WebSocketEvent,
        WebSocketEventType,
    )
except ImportError:
    # Define minimal stubs if import fails
    def create_dag_created_event(*args, **kwargs): return None
    def create_dag_node_status_changed_event(*args, **kwargs): return None
    def create_workflow_started_event(*args, **kwargs): return None
    def create_workflow_completed_event(*args, **kwargs): return None
    def create_step_started_event(*args, **kwargs): return None
    def create_step_completed_event(*args, **kwargs): return None
    class WebSocketEvent:
        def __init__(self, **kwargs): pass
    class WebSocketEventType:
        WORKFLOW_FAILED = "workflow_failed"

# Add the parent directory to the path to import cmbagent
sys.path.append(str(Path(__file__).parent.parent))
# Add the backend directory to the path to import services and credentials
sys.path.insert(0, str(Path(__file__).parent))

# Import services layer (Stage 1-9 integration)
try:
    from services import (
        workflow_service,
        connection_manager,
        execution_service,
    )
    SERVICES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Services not available: {e}")
    import traceback
    traceback.print_exc()
    SERVICES_AVAILABLE = False

try:
    import cmbagent
    from cmbagent.utils import get_api_keys_from_env
    from credentials import (
        test_all_credentials, 
        test_openai_credentials, 
        test_anthropic_credentials, 
        test_vertex_credentials,
        store_credentials_in_env,
        CredentialStorage,
        CredentialTest
    )
except ImportError as e:
    print(f"Error importing cmbagent: {e}")
    print("Make sure cmbagent is installed and accessible")
    sys.exit(1)

# Production-grade run_id resolution function
def resolve_run_id(run_id: str) -> str:
    """Resolve task_id to database run_id if available.
    
    This is the single source of truth for run_id resolution.
    All APIs should use this to convert frontend task_ids to database UUIDs.
    
    Args:
        run_id: Either a task_id or a db_run_id
        
    Returns:
        The database run_id (UUID) if found, otherwise the input run_id
    """
    if SERVICES_AVAILABLE and workflow_service:
        run_info = workflow_service.get_run_info(run_id)
        if run_info and run_info.get("db_run_id"):
            return run_info["db_run_id"]
    return run_id

app = FastAPI(title="CMBAgent API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3004"
    ],  # Next.js dev server on various ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active WebSocket connections with metadata
# Format: {task_id: {"websocket": WebSocket, "session_id": str, "run_id": str, "status": str}}
active_connections: Dict[str, Dict[str, Any]] = {}

# Track task to run_id mapping for database integration
task_to_run: Dict[str, str] = {}


class AG2IOStreamCapture:
    """
    Custom AG2 IOStream that intercepts all AG2 events and forwards them to WebSocket.
    This captures all agent messages, tool calls, function responses, etc.
    """

    def __init__(self, websocket: WebSocket, task_id: str, loop=None):
        self.websocket = websocket
        self.task_id = task_id
        self.loop = loop or asyncio.get_event_loop()
        self._original_print = print

    def print(self, *objects: Any, sep: str = " ", end: str = "\n", flush: bool = False) -> None:
        """Capture print calls and send to WebSocket"""
        message = sep.join(str(obj) for obj in objects)
        if message.strip():
            # Send to WebSocket asynchronously
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._send_output(message),
                    self.loop
                )
                # Don't wait for the result to avoid blocking
            except Exception as e:
                self._original_print(f"Error in AG2IOStreamCapture.print: {e}")
        # Also print to original stdout for debugging
        self._original_print(*objects, sep=sep, end=end, flush=flush)

    def send(self, message) -> None:
        """
        Capture AG2 events and forward to WebSocket.
        AG2 sends BaseEvent objects here with their own print() methods.
        """
        try:
            # Extract event information
            event_data = self._extract_event_data(message)
            if event_data:
                # Send structured event to WebSocket
                future = asyncio.run_coroutine_threadsafe(
                    self._send_structured_event(event_data),
                    self.loop
                )

            # Also call the original print method of the event
            message.print(self._original_print)
        except Exception as e:
            self._original_print(f"Error in AG2IOStreamCapture.send: {e}")
            # Fallback: try to print the message
            try:
                message.print(self._original_print)
            except:
                pass

    def _extract_event_data(self, event) -> Optional[Dict[str, Any]]:
        """Extract structured data from AG2 events"""
        try:
            event_type = type(event).__name__

            # Handle wrapped events (they have a 'content' field with the actual event)
            actual_event = getattr(event, 'content', event)

            data = {
                "event_type": event_type,
                "sender": getattr(actual_event, 'sender', None),
                "recipient": getattr(actual_event, 'recipient', None),
            }

            # Extract content based on event type
            if hasattr(actual_event, 'content'):
                content = actual_event.content
                if content is not None:
                    data["content"] = str(content)[:5000]  # Limit content size

            # Extract function/tool call info
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
            await send_ws_event(
                self.websocket,
                "output",
                {"message": message},
                run_id=self.task_id
            )
        except Exception as e:
            print(f"Error sending output to WebSocket: {e}")

    async def _send_structured_event(self, event_data: Dict[str, Any]):
        """Send structured AG2 event to WebSocket"""
        try:
            event_type = event_data.get("event_type", "SYSTEM")
            sender = event_data.get("sender", "SYSTEM")
            content = event_data.get("content", "")

            # Determine the appropriate WebSocket event type
            if "ToolCall" in event_type or "FunctionCall" in event_type:
                ws_event_type = "tool_call"
                data = {
                    "agent": sender,
                    "tool_name": event_data.get("function_name") or "SYSTE",
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

            await send_ws_event(
                self.websocket,
                ws_event_type,
                data,
                run_id=self.task_id
            )
        except Exception as e:
            print(f"Error sending structured event to WebSocket: {e}")

    def input(self, prompt: str = "", *, password: bool = False) -> str:
        """Handle input requests - not typically used in autonomous mode"""
        return ""


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


class TaskRequest(BaseModel):
    task: str
    config: Dict[str, Any] = {
        "model": "gpt-4o",
        "maxRounds": 25,
        "maxAttempts": 6,
        "agent": "engineer",
        "workDir": "~/Desktop/cmbdir"
    }

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class FileItem(BaseModel):
    name: str
    path: str
    type: str  # 'file' or 'directory'
    size: Optional[int] = None
    modified: Optional[float] = None
    mime_type: Optional[str] = None

class DirectoryListing(BaseModel):
    path: str
    items: List[FileItem]
    parent: Optional[str] = None

class ArxivFilterRequest(BaseModel):
    input_text: str
    work_dir: Optional[str] = None

class ArxivFilterResponse(BaseModel):
    status: str
    result: Dict[str, Any]
    message: str

class EnhanceInputRequest(BaseModel):
    input_text: str
    work_dir: Optional[str] = None
    max_workers: Optional[int] = 2
    max_depth: Optional[int] = 10

class EnhanceInputResponse(BaseModel):
    status: str
    enhanced_text: str
    processing_summary: Dict[str, Any]
    cost_breakdown: Dict[str, Any]
    message: str

class BranchRequest(BaseModel):
    step_id: str
    branch_name: str
    hypothesis: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None

class PlayFromNodeRequest(BaseModel):
    node_id: str
    context_override: Optional[Dict[str, Any]] = None

class StreamCapture:
    """Capture stdout/stderr and send to WebSocket"""

    def __init__(self, websocket: WebSocket, task_id: str, dag_tracker=None, loop=None, work_dir=None):
        self.websocket = websocket
        self.task_id = task_id
        self.buffer = StringIO()
        self.dag_tracker = dag_tracker
        self.loop = loop
        self.work_dir = work_dir  # Work directory to read plan files
        self.current_step = 0
        self.planning_complete = False
        self.plan_buffer = []  # Buffer to collect plan lines
        self.collecting_plan = False
        self.steps_added = False
        self.total_cost = 0.0  # Track cumulative cost
        self.last_cost_report_time = 0  # Throttle cost updates

    async def write(self, text: str):
        """Write text to buffer and send to WebSocket"""
        if text.strip():  # Only send non-empty lines
            try:
                await send_ws_event(
                    self.websocket,
                    "output",
                    {"message": text.strip()},
                    run_id=self.task_id
                )

                # Detect progress patterns and update DAG
                if self.dag_tracker:
                    await self._detect_progress(text)

                # Detect and emit cost updates
                await self._detect_cost_updates(text)

                # Detect agent messages, code blocks, and tool calls for detailed logging
                await self._detect_agent_activity(text)

            except Exception as e:
                print(f"Error sending to WebSocket: {e}")
        
        # Also write to buffer for later retrieval
        self.buffer.write(text)
        return len(text)
    
    async def _detect_cost_updates(self, text: str):
        """Detect cost information from output and emit WebSocket events"""
        import re
        import time
        
        text_lower = text.lower()
        
        # Detect cost output patterns from display_cost()
        # Format: "$0.12345678" or "Cost: $0.12345678"
        cost_pattern = r'\$([0-9]+\.[0-9]+)'
        
        # Detect specific cost lines from the table
        if 'cost ($)' in text_lower or '$' in text and any(x in text_lower for x in ['total', 'gpt', 'gemini', 'engineer', 'researcher']):
            costs = re.findall(cost_pattern, text)
            if costs:
                # Get the latest cost value
                try:
                    new_cost = float(costs[-1])
                    # Only emit if cost has changed and enough time has passed (throttle updates)
                    current_time = time.time()
                    if new_cost > self.total_cost and (current_time - self.last_cost_report_time) > 1.0:
                        cost_delta = new_cost - self.total_cost
                        self.total_cost = new_cost
                        self.last_cost_report_time = current_time
                        
                        # Emit cost_update event
                        await send_ws_event(
                            self.websocket,
                            "cost_update",
                            {
                                "run_id": self.task_id,
                                "step_id": f"step_{self.current_step}" if self.current_step > 0 else None,
                                "model": "unknown",  # Will be enhanced later
                                "tokens": 0,  # Will be enhanced later
                                "cost_usd": cost_delta,
                                "total_cost_usd": self.total_cost
                            },
                            run_id=self.task_id
                        )
                except (ValueError, IndexError):
                    pass
        
        # Detect cost report files and parse them
        if 'cost report data saved to:' in text_lower:
            await self._parse_cost_report(text)
    
    async def _parse_cost_report(self, text: str):
        """Parse cost report JSON file and emit detailed cost events"""
        import os
        import json
        import re
        
        # Extract file path from output
        match = re.search(r'cost report data saved to: (.+\.json)', text, re.IGNORECASE)
        if match:
            cost_file = match.group(1).strip()
            if os.path.exists(cost_file):
                try:
                    with open(cost_file, 'r') as f:
                        cost_data = json.load(f)
                    
                    # Calculate total cost from the report
                    total_cost = 0.0
                    for entry in cost_data:
                        if entry.get('Agent') != 'Total':
                            cost_str = str(entry.get('Cost ($)', '$0.0'))
                            cost_value = float(cost_str.replace('$', ''))
                            total_cost += cost_value
                    
                    # Emit comprehensive cost update
                    if total_cost > 0:
                        self.total_cost = total_cost
                        # Calculate total tokens, handling both int and float strings
                        total_tokens = 0
                        for e in cost_data:
                            if e.get('Agent') != 'Total':
                                tokens_val = e.get('Total Tokens', 0)
                                if tokens_val:
                                    total_tokens += int(float(str(tokens_val)))
                        
                        await send_ws_event(
                            self.websocket,
                            "cost_update",
                            {
                                "run_id": self.task_id,
                                "step_id": f"step_{self.current_step}" if self.current_step > 0 else None,
                                "model": "aggregate",
                                "tokens": total_tokens,
                                "cost_usd": total_cost,
                                "total_cost_usd": total_cost
                            },
                            run_id=self.task_id
                        )
                except Exception as e:
                    print(f"Error parsing cost report: {e}")

    async def _detect_agent_activity(self, text: str):
        """Detect agent messages, code blocks, and tool calls for comprehensive logging"""
        import re

        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        # Detect agent transitions/handoffs - e.g., "ReplyResult Transition (control): engineer"
        # or "engineer (to executor):" or similar patterns
        transition_patterns = [
            r'replyresult\s+transition\s*\(([^)]+)\):\s*(\w+)',  # AG2 swarm transitions
            r'(\w+)\s*\(to\s+(\w+)\)',  # agent (to agent) pattern
            r'^(\w+_?(?:agent|response_formatter|executor|context)?)\s*:',  # agent_name: message
            r'next speaker:\s*(\w+)',  # "Next speaker: agent_name"
        ]

        for pattern in transition_patterns:
            match = re.search(pattern, text_stripped, re.IGNORECASE)
            if match:
                groups = match.groups()
                agent_name = groups[-1] if len(groups) > 0 else "unknown"
                await send_ws_event(
                    self.websocket,
                    "agent_message",
                    {
                        "agent": agent_name,
                        "role": "transition",
                        "message": text_stripped,
                        "metadata": {"type": "handoff"}
                    },
                    run_id=self.task_id
                )
                break

        # Detect code blocks - ```python or ```bash etc
        code_block_pattern = r'```(\w*)\n([\s\S]*?)```'
        code_matches = re.findall(code_block_pattern, text_stripped)
        for language, code in code_matches:
            if code.strip():
                await send_ws_event(
                    self.websocket,
                    "code_execution",
                    {
                        "agent": "executor" if "executor" in text_lower else "engineer",
                        "code": code.strip()[:2000],  # Limit code length
                        "language": language or "python",
                        "result": None
                    },
                    run_id=self.task_id
                )

        # Detect function/tool calls - patterns like "function_call:" or "Tool call:"
        tool_patterns = [
            r'function_call\s*[:\(]\s*(\w+)',
            r'tool\s+call\s*[:\(]\s*(\w+)',
            r'calling\s+(\w+)\s*\(',
            r'(\w+_function)\s*\(',
        ]

        for pattern in tool_patterns:
            match = re.search(pattern, text_stripped, re.IGNORECASE)
            if match:
                tool_name = match.group(1)
                await send_ws_event(
                    self.websocket,
                    "tool_call",
                    {
                        "agent": "executor",
                        "tool_name": tool_name,
                        "arguments": {},
                        "result": None
                    },
                    run_id=self.task_id
                )
                break

        # Detect execution results - "exitcode:" patterns
        if "exitcode:" in text_lower or "execution result:" in text_lower:
            exitcode_match = re.search(r'exitcode:\s*(\d+)', text_lower)
            exitcode = exitcode_match.group(1) if exitcode_match else "unknown"
            await send_ws_event(
                self.websocket,
                "code_execution",
                {
                    "agent": "executor",
                    "code": "",
                    "language": "python",
                    "result": f"Exit code: {exitcode}\n{text_stripped[:500]}"
                },
                run_id=self.task_id
            )

        # Detect LLM API calls - cost output patterns indicate an LLM call
        if any(phrase in text_lower for phrase in ['cost (', 'prompt tokens:', 'completion tokens:']):
            # Extract model name if present
            model_match = re.search(r'cost\s*\(([^)]+)\)', text_lower)
            model = model_match.group(1) if model_match else "unknown"
            await send_ws_event(
                self.websocket,
                "agent_message",
                {
                    "agent": model,
                    "role": "llm_call",
                    "message": text_stripped,
                    "metadata": {"type": "cost_info"}
                },
                run_id=self.task_id
            )

    async def _detect_progress(self, text: str):
        """Detect execution progress from output and update DAG nodes"""
        import re
        import os
        import json
        text_lower = text.lower()
        text_stripped = text.strip()
        
        # Detect when plan file is written (better approach - read actual file)
        if "structured plan written to" in text_lower or "final_plan.json" in text_lower:
            self.collecting_plan = False
            
            # Try to read the plan file from the work directory
            if hasattr(self, 'work_dir') and self.work_dir:
                plan_file = os.path.join(self.work_dir, "planning", "final_plan.json")
                if os.path.exists(plan_file):
                    try:
                        with open(plan_file, 'r') as f:
                            plan_data = json.load(f)
                        
                        # Build DAG from actual plan data
                        plan_output = {
                            'number_of_steps_in_plan': len(plan_data.get('sub_tasks', [])),
                            'final_plan': plan_data
                        }
                        
                        # Convert sub_tasks to steps format
                        steps = []
                        for i, sub_task in enumerate(plan_data.get('sub_tasks', []), 1):
                            # The field is 'sub_task' not 'sub_task_description'
                            sub_task_desc = sub_task.get('sub_task', '')
                            bullet_points = sub_task.get('bullet_points', [])
                            agent = sub_task.get('sub_task_agent', 'engineer')

                            # Create comprehensive description from sub_task and bullet points
                            full_description = sub_task_desc
                            if bullet_points:
                                full_description += "\n\nInstructions:\n" + "\n".join(f"• {bp}" for bp in bullet_points)

                            steps.append({
                                "title": f"Step {i}: {agent}",
                                "description": full_description[:500] if full_description else '',
                                "task": sub_task_desc,
                                "agent": agent,
                                "goal": sub_task_desc,  # Primary objective
                                "insights": "\n".join(bullet_points) if bullet_points else '',  # Detailed instructions
                                "bullet_points": bullet_points  # Raw bullet points for UI display
                            })
                        
                        if steps and not self.steps_added:
                            # Mark planning as completed with the generated plan
                            if "planning" in self.dag_tracker.node_statuses:
                                # Store the plan in the planning node's metadata
                                for node in self.dag_tracker.nodes:
                                    if node["id"] == "planning":
                                        node["generated_plan"] = {
                                            "sub_tasks": plan_data.get('sub_tasks', []),
                                            "step_count": len(steps),
                                            "mode": plan_data.get('mode', 'planning_control'),
                                            "breakdown": plan_data.get('sub_task_breakdown', '')
                                        }
                                        break
                                await self.dag_tracker.update_node_status("planning", "completed")
                                print("Planning node marked as completed with generated plan")
                            
                            # Add step nodes
                            await self.dag_tracker.add_step_nodes(steps)
                            self.steps_added = True
                            self.planning_complete = True
                            print(f"Built DAG from plan file with {len(steps)} steps")
                            
                            # Mark first step as running
                            first_exec = self.dag_tracker.get_node_by_step(1)
                            if first_exec:
                                await self.dag_tracker.update_node_status(first_exec, "running")
                                self.current_step = 1
                                print(f"Step 1 ({first_exec}) marked as running")
                    except Exception as e:
                        print(f"Error reading plan file: {e}")
        
        # Detect start of plan output (fallback for text parsing)
        if any(phrase in text_lower for phrase in ["plan:", "execution plan:", "here is the plan", "generated plan"]):
            self.collecting_plan = True
            self.plan_buffer = []
        
        # Collect plan lines (look for numbered steps like "1.", "Step 1:", etc.)
        if self.collecting_plan:
            step_line_match = re.match(r'^(?:step\s*)?(\d+)[.:)\s]+(.+)', text_stripped, re.IGNORECASE)
            if step_line_match:
                step_num = int(step_line_match.group(1))
                step_desc = step_line_match.group(2).strip()
                self.plan_buffer.append({
                    "step_number": step_num,
                    "title": f"Step {step_num}",
                    "description": step_desc,
                    "task": step_desc
                })
        
        # Detect when planning is complete and execution starts
        if not self.steps_added and any(phrase in text_lower for phrase in [
            "executing step", "starting step 1", "running step 1", "beginning execution",
            "step 1 of", "executing plan", "control_starter", "transition (control)",
            "replyresult transition (control):", "control): engineer"
        ]):
            # Planning is complete
            if "planning" in self.dag_tracker.node_statuses:
                # Store collected plan in planning node
                if self.plan_buffer:
                    for node in self.dag_tracker.nodes:
                        if node["id"] == "planning":
                            node["generated_plan"] = {
                                "steps": self.plan_buffer,
                                "step_count": len(self.plan_buffer)
                            }
                            break
                await self.dag_tracker.update_node_status("planning", "completed")
            
            # Add step nodes from collected plan buffer if not already added
            if self.plan_buffer and self.dag_tracker.mode == "planning-control":
                await self.dag_tracker.add_step_nodes(self.plan_buffer)
                self.steps_added = True
            elif self.dag_tracker.mode == "planning-control" and not self.plan_buffer:
                # No steps collected, create default steps
                default_steps = [{"title": "Step 1", "description": "Execute task", "task": ""}]
                await self.dag_tracker.add_step_nodes(default_steps)
                self.steps_added = True
            
            self.planning_complete = True
            self.collecting_plan = False
            
            # Mark first step as running
            first_exec = self.dag_tracker.get_node_by_step(1)
            if first_exec:
                await self.dag_tracker.update_node_status(first_exec, "running")
                print(f"Step 1 ({first_exec}) marked as running")
        
        # Detect step transitions - look for control_starter pattern for each step
        if "control_starter" in text_lower or ("timing_report_step_" in text_lower):
            # Try to extract step number from "timing_report_step_X" pattern
            step_timing_match = re.search(r'timing_report_step_(\d+)', text_lower)
            if step_timing_match:
                completed_step = int(step_timing_match.group(1))
                # Mark that step as completed
                node_id = self.dag_tracker.get_node_by_step(completed_step)
                if node_id:
                    # Track files generated during this step, then mark as completed
                    await self.dag_tracker.update_node_status(node_id, "completed", work_dir=self.work_dir)
                    print(f"Step {completed_step} ({node_id}) marked as completed from timing report")

                    # Mark next step as running if exists
                    next_node = self.dag_tracker.get_node_by_step(completed_step + 1)
                    if next_node:
                        await self.dag_tracker.update_node_status(next_node, "running")
                        print(f"Step {completed_step + 1} ({next_node}) marked as running")
                    self.current_step = completed_step + 1

        # Detect step transitions (Step 1, Step 2, etc.)
        step_match = re.search(r'(?:executing|running|starting|completed)\s*(?:step\s*)?(\d+)', text_lower)
        if step_match and self.planning_complete:
            step_num = int(step_match.group(1))
            if step_num > self.current_step:
                # Mark previous step as completed (with file tracking)
                if self.current_step > 0:
                    prev_node = self.dag_tracker.get_node_by_step(self.current_step)
                    if prev_node:
                        await self.dag_tracker.update_node_status(prev_node, "completed", work_dir=self.work_dir)

                # Mark current step as running
                current_node = self.dag_tracker.get_node_by_step(step_num)
                if current_node:
                    await self.dag_tracker.update_node_status(current_node, "running")

                self.current_step = step_num

        # Detect step completion
        if "step completed" in text_lower or "completed step" in text_lower:
            step_complete_match = re.search(r'(?:step|completed step)\s*(\d+)', text_lower)
            if step_complete_match:
                completed_step = int(step_complete_match.group(1))
                node_id = self.dag_tracker.get_node_by_step(completed_step)
                if node_id:
                    # Track files generated during this step
                    await self.dag_tracker.update_node_status(node_id, "completed", work_dir=self.work_dir)
        
        # Detect idea generation phases
        if "idea_maker" in text_lower or "generating ideas" in text_lower:
            for node_id in self.dag_tracker.node_statuses:
                if "idea_maker" in node_id and self.dag_tracker.node_statuses[node_id] == "pending":
                    await self.dag_tracker.update_node_status(node_id, "running")
                    break
        
        if "idea_hater" in text_lower or "critiquing" in text_lower or "critique" in text_lower:
            for node_id in self.dag_tracker.node_statuses:
                if "idea_hater" in node_id and self.dag_tracker.node_statuses[node_id] == "pending":
                    await self.dag_tracker.update_node_status(node_id, "running")
                    break
    
    def flush(self):
        """Flush the buffer"""
        pass
    
    def getvalue(self):
        """Get the complete output"""
        return self.buffer.getvalue()


class DAGTracker:
    """Track DAG state and emit events for UI visualization using database"""
    
    def __init__(self, websocket: WebSocket, task_id: str, mode: str, run_id: str = None):
        self.websocket = websocket
        self.task_id = task_id
        self.mode = mode
        self.nodes = []
        self.edges = []
        self.current_step = 0
        self.node_statuses = {}
        self.db_session = None
        self.dag_builder = None
        self.dag_visualizer = None
        self.run_id = run_id  # Use provided run_id or create one
        self.session_id = None
        self.event_repo = None
        self.node_event_map = {}  # Map node_id to current event_id
        self.execution_order_counter = 0  # Track execution order across all events
        
        # Try to initialize database connection
        try:
            from cmbagent.database import get_db_session as get_session, init_database
            from cmbagent.database.dag_builder import DAGBuilder
            from cmbagent.database.dag_visualizer import DAGVisualizer
            from cmbagent.database.repository import WorkflowRepository, EventRepository
            from cmbagent.database.session_manager import SessionManager
            
            init_database()
            self.db_session = get_session()
            
            # Get or create session
            session_manager = SessionManager(self.db_session)
            self.session_id = session_manager.get_or_create_default_session()
            
            # Create workflow repository
            self.workflow_repo = WorkflowRepository(self.db_session, self.session_id)
            
            # Create event repository
            self.event_repo = EventRepository(self.db_session, self.session_id)
            
            # Only create a new workflow run if we don't have one from the service
            # IMPORTANT: If no run_id provided, use task_id to maintain consistency
            if not self.run_id:
                print(f"[DAGTracker] No run_id provided, using task_id: {task_id}")
                self.run_id = task_id
            
            self.dag_builder = DAGBuilder(self.db_session, self.session_id)
            self.dag_visualizer = DAGVisualizer(self.db_session)
            print(f"Database DAG system initialized with run_id: {self.run_id}")
        except Exception as e:
            print(f"Warning: Could not initialize database DAG system: {e}")
            import traceback
            traceback.print_exc()
            # Will fall back to in-memory tracking
    
    async def build_dag_from_plan(self, plan_output: Dict[str, Any]):
        """Build DAG in database from plan output after planning phase completes"""
        if not self.dag_builder or not self.run_id:
            print("Database not available, using in-memory DAG")
            return await self._build_inmemory_dag_from_plan(plan_output)
        
        try:
            # Convert CMBAgent plan format to DAGBuilder format
            number_of_steps = plan_output.get('number_of_steps_in_plan', 0)
            final_plan = plan_output.get('final_plan', '')
            
            # Parse final_plan to extract steps
            steps = []
            if isinstance(final_plan, str):
                # Parse text plan to extract steps
                import re
                step_matches = re.findall(r'(?:Step\s*)?(\d+)[.:]\s*(.+?)(?=(?:Step\s*)?\d+[.:]|$)', final_plan, re.IGNORECASE | re.DOTALL)
                for step_num, step_desc in step_matches:
                    steps.append({
                        "task": step_desc.strip(),
                        "agent": "engineer",
                        "depends_on": [f"step_{int(step_num)-1}"] if int(step_num) > 1 else ["planning"]
                    })
            
            # If no steps parsed, create default steps based on number_of_steps_in_plan
            if not steps and number_of_steps > 0:
                for i in range(number_of_steps):
                    steps.append({
                        "task": f"Execute step {i+1}",
                        "agent": "engineer",
                        "depends_on": [f"step_{i-1}"] if i > 0 else ["planning"]
                    })
            
            plan_dict = {"steps": steps}
            
            # Build DAG in database
            dag_nodes = self.dag_builder.build_from_plan(self.run_id, plan_dict)
            
            # Export for UI
            dag_export = self.dag_visualizer.export_for_ui(self.run_id)
            
            # Update local tracking
            self.nodes = dag_export.get("nodes", [])
            self.edges = dag_export.get("edges", [])
            for node in self.nodes:
                self.node_statuses[node["id"]] = node.get("status", "pending")
            
            # Emit dag_updated event with database data
            effective_run_id = self.run_id or self.task_id
            await send_ws_event(
                self.websocket,
                "dag_updated",
                {
                    "run_id": effective_run_id,
                    "nodes": self.nodes,
                    "edges": self.edges,
                    "levels": dag_export.get("levels", len(steps) + 2)
                },
                run_id=effective_run_id
            )
            
            print(f"Built DAG from plan with {len(steps)} steps in database")
            return dag_export
            
        except Exception as e:
            print(f"Error building DAG from plan: {e}")
            import traceback
            traceback.print_exc()
            return await self._build_inmemory_dag_from_plan(plan_output)
    
    async def _build_inmemory_dag_from_plan(self, plan_output: Dict[str, Any]):
        """Fallback: Build in-memory DAG from plan output"""
        number_of_steps = plan_output.get('number_of_steps_in_plan', 1)
        final_plan = plan_output.get('final_plan', '')
        
        # Parse steps from plan
        steps = []
        if isinstance(final_plan, str):
            import re
            step_matches = re.findall(r'(?:Step\s*)?(\d+)[.:]\s*(.+?)(?=(?:Step\s*)?\d+[.:]|$)', final_plan, re.IGNORECASE | re.DOTALL)
            for step_num, step_desc in step_matches:
                steps.append({
                    "title": f"Step {step_num}",
                    "description": step_desc.strip()[:200],
                    "task": step_desc.strip()
                })
        
        # If no steps parsed, create based on number_of_steps
        if not steps:
            for i in range(1, number_of_steps + 1):
                steps.append({
                    "title": f"Step {i}",
                    "description": f"Execute step {i}",
                    "task": f"Step {i}"
                })
        
        # Add step nodes using existing method
        await self.add_step_nodes(steps)
        
        return {"nodes": self.nodes, "edges": self.edges, "levels": len(steps) + 2}
        
    def create_dag_for_mode(self, task: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create initial DAG structure based on execution mode"""
        if self.mode == "planning-control":
            return self._create_planning_control_dag(task, config)
        elif self.mode == "idea-generation":
            return self._create_idea_generation_dag(task, config)
        elif self.mode == "one-shot":
            return self._create_one_shot_dag(task, config)
        elif self.mode == "ocr":
            return self._create_ocr_dag(task, config)
        elif self.mode == "arxiv":
            return self._create_arxiv_dag(task, config)
        elif self.mode == "enhance-input":
            return self._create_enhance_input_dag(task, config)
        else:
            return self._create_one_shot_dag(task, config)
    
    def _create_planning_control_dag(self, task: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create initial DAG for planning-control mode - just planning node"""
        # Start with just the planning node - steps will be added dynamically
        self.nodes = [
            {
                "id": "planning",
                "label": "Planning Phase",
                "type": "planning",
                "agent": "planner",
                "status": "pending",
                "step_number": 0,
                "description": "Analyzing task and creating execution plan",
                "task": task[:100] + "..." if len(task) > 100 else task
            }
        ]
        
        # No edges yet - will be added when steps are discovered
        self.edges = []
        
        # Initialize statuses
        for node in self.nodes:
            self.node_statuses[node["id"]] = "pending"
        
        return {"nodes": self.nodes, "edges": self.edges, "levels": 1}
    
    async def add_step_nodes(self, steps: list):
        """Dynamically add step nodes after planning completes"""
        # Add step nodes
        for i, step_info in enumerate(steps, 1):
            step_id = f"step_{i}"
            if isinstance(step_info, dict):
                # Extract full information from step
                description = step_info.get("description", "")
                task = step_info.get("task", "")
                agent = step_info.get("agent", "engineer")
                insights = step_info.get("insights", "")
                goal = step_info.get("goal", "")
                summary = step_info.get("summary", "")
                bullet_points = step_info.get("bullet_points", [])

                # Create comprehensive label with goal or description
                # Priority: goal > task > description (truncate label for display)
                label_source = goal or task or description
                if label_source:
                    # Truncate label for visual display but keep it meaningful
                    truncated_label = label_source.strip()[:80]
                    if len(label_source.strip()) > 80:
                        truncated_label += "..."
                    label = f"Step {i}: {truncated_label}"
                else:
                    label = step_info.get("title", f"Step {i}: {agent}")
            else:
                label = f"Step {i}"
                description = str(step_info)[:200] if step_info else ""
                task = str(step_info) if step_info else ""
                agent = "engineer"
                insights = ""
                goal = ""
                summary = ""
                bullet_points = []

            self.nodes.append({
                "id": step_id,
                "label": label,
                "type": "agent",
                "agent": agent,
                "status": "pending",
                "step_number": i,
                "description": description,
                "task": task,
                "insights": insights,
                "goal": goal,
                "summary": summary,
                "bullet_points": bullet_points
            })
            self.node_statuses[step_id] = "pending"
        
        # Add terminator node
        terminator_step = len(steps) + 1
        self.nodes.append({
            "id": "terminator",
            "label": "Completion",
            "type": "terminator",
            "agent": "system",
            "status": "pending",
            "step_number": terminator_step,
            "description": "Workflow completed"
        })
        self.node_statuses["terminator"] = "pending"
        
        # Create edges: planning -> step_1 -> step_2 -> ... -> terminator
        self.edges = [{"source": "planning", "target": "step_1"}]
        for i in range(1, len(steps)):
            self.edges.append({"source": f"step_{i}", "target": f"step_{i+1}"})
        self.edges.append({"source": f"step_{len(steps)}", "target": "terminator"})
        
        # Emit dag_updated event
        try:
            effective_run_id = self.run_id or self.task_id
            await send_ws_event(
                self.websocket,
                "dag_updated",
                {
                    "run_id": effective_run_id,
                    "nodes": self.nodes,
                    "edges": self.edges,
                    "levels": len(steps) + 2
                },
                run_id=effective_run_id
            )
        except Exception as e:
            print(f"Error sending DAG updated event: {e}")
    
    def _create_idea_generation_dag(self, task: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create DAG for idea-generation mode"""
        self.nodes = [
            {"id": "planning", "label": "Plan Generation", "type": "planning", "agent": "planner", "status": "pending", "step_number": 0},
            {"id": "idea_maker_1", "label": "Generate Ideas", "type": "agent", "agent": "idea_maker", "status": "pending", "step_number": 1},
            {"id": "idea_hater_1", "label": "Critique Ideas", "type": "agent", "agent": "idea_hater", "status": "pending", "step_number": 2},
            {"id": "idea_maker_2", "label": "Refine Ideas", "type": "agent", "agent": "idea_maker", "status": "pending", "step_number": 3},
            {"id": "idea_hater_2", "label": "Final Critique", "type": "agent", "agent": "idea_hater", "status": "pending", "step_number": 4},
            {"id": "idea_maker_3", "label": "Select Best Idea", "type": "agent", "agent": "idea_maker", "status": "pending", "step_number": 5},
            {"id": "terminator", "label": "Completion", "type": "terminator", "agent": "system", "status": "pending", "step_number": 6},
        ]
        self.edges = [
            {"source": "planning", "target": "idea_maker_1"},
            {"source": "idea_maker_1", "target": "idea_hater_1"},
            {"source": "idea_hater_1", "target": "idea_maker_2"},
            {"source": "idea_maker_2", "target": "idea_hater_2"},
            {"source": "idea_hater_2", "target": "idea_maker_3"},
            {"source": "idea_maker_3", "target": "terminator"},
        ]
        for node in self.nodes:
            self.node_statuses[node["id"]] = "pending"
        return {"nodes": self.nodes, "edges": self.edges, "levels": 7}
    
    def _create_one_shot_dag(self, task: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create DAG for one-shot mode"""
        agent = config.get("agent", "engineer")
        self.nodes = [
            {"id": "init", "label": "Initialize", "type": "planning", "status": "pending", "step_number": 0, "description": "Initialize agent"},
            {"id": "execute", "label": f"Execute ({agent})", "type": "agent", "agent": agent, "status": "pending", "step_number": 1, "description": "Execute task"},
            {"id": "terminator", "label": "Completion", "type": "terminator", "agent": "system", "status": "pending", "step_number": 2},
        ]
        self.edges = [
            {"source": "init", "target": "execute"},
            {"source": "execute", "target": "terminator"},
        ]
        for node in self.nodes:
            self.node_statuses[node["id"]] = "pending"
        
        # Persist nodes to database
        self._persist_dag_nodes_to_db()
        
        return {"nodes": self.nodes, "edges": self.edges, "levels": 3}
    
    def _create_ocr_dag(self, task: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create DAG for OCR mode"""
        self.nodes = [
            {"id": "init", "label": "Initialize OCR", "type": "planning", "status": "pending", "step_number": 0},
            {"id": "process", "label": "Process PDFs", "type": "agent", "agent": "ocr", "status": "pending", "step_number": 1},
            {"id": "output", "label": "Save Output", "type": "agent", "agent": "ocr", "status": "pending", "step_number": 2},
            {"id": "terminator", "label": "Completion", "type": "terminator", "agent": "system", "status": "pending", "step_number": 3},
        ]
        self.edges = [
            {"source": "init", "target": "process"},
            {"source": "process", "target": "output"},
            {"source": "output", "target": "terminator"},
        ]
        for node in self.nodes:
            self.node_statuses[node["id"]] = "pending"
        return {"nodes": self.nodes, "edges": self.edges, "levels": 4}
    
    def _create_arxiv_dag(self, task: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create DAG for arXiv filter mode"""
        self.nodes = [
            {"id": "init", "label": "Parse Text", "type": "planning", "status": "pending", "step_number": 0},
            {"id": "filter", "label": "Filter arXiv URLs", "type": "agent", "agent": "arxiv", "status": "pending", "step_number": 1},
            {"id": "download", "label": "Download Papers", "type": "agent", "agent": "arxiv", "status": "pending", "step_number": 2},
            {"id": "terminator", "label": "Completion", "type": "terminator", "agent": "system", "status": "pending", "step_number": 3},
        ]
        self.edges = [
            {"source": "init", "target": "filter"},
            {"source": "filter", "target": "download"},
            {"source": "download", "target": "terminator"},
        ]
        for node in self.nodes:
            self.node_statuses[node["id"]] = "pending"
        return {"nodes": self.nodes, "edges": self.edges, "levels": 4}
    
    def _create_enhance_input_dag(self, task: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create DAG for enhance-input mode"""
        self.nodes = [
            {"id": "init", "label": "Initialize", "type": "planning", "status": "pending", "step_number": 0},
            {"id": "enhance", "label": "Enhance Input", "type": "agent", "agent": "enhancer", "status": "pending", "step_number": 1},
            {"id": "terminator", "label": "Completion", "type": "terminator", "agent": "system", "status": "pending", "step_number": 2},
        ]
        self.edges = [
            {"source": "init", "target": "enhance"},
            {"source": "enhance", "target": "terminator"},
        ]
        for node in self.nodes:
            self.node_statuses[node["id"]] = "pending"
        return {"nodes": self.nodes, "edges": self.edges, "levels": 3}
    
    def _persist_dag_nodes_to_db(self):
        """Persist DAG nodes to database to satisfy foreign key constraints"""
        if not self.db_session or not self.run_id:
            return
        
        try:
            from cmbagent.database.models import DAGNode, DAGEdge
            
            # Create DAGNode records using the node["id"] as the DAGNode.id (primary key)
            for idx, node in enumerate(self.nodes):
                # Check if node already exists by its id (primary key)
                existing_node = self.db_session.query(DAGNode).filter(
                    DAGNode.id == node["id"]
                ).first()
                
                if not existing_node:
                    dag_node = DAGNode(
                        id=node["id"],  # Use the node id as the primary key
                        run_id=self.run_id,
                        session_id=self.session_id,
                        node_type=node.get("type", "agent"),
                        agent=node.get("agent", "unknown"),
                        status="pending",
                        order_index=node.get("step_number", idx),
                        meta=node
                    )
                    self.db_session.add(dag_node)
            
            # Create DAGEdge records
            for edge in self.edges:
                existing_edge = self.db_session.query(DAGEdge).filter(
                    DAGEdge.from_node_id == edge["source"],
                    DAGEdge.to_node_id == edge["target"]
                ).first()
                
                if not existing_edge:
                    dag_edge = DAGEdge(
                        from_node_id=edge["source"],
                        to_node_id=edge["target"],
                        dependency_type="sequential"
                    )
                    self.db_session.add(dag_edge)
            
            self.db_session.commit()
            print(f"Persisted {len(self.nodes)} nodes and {len(self.edges)} edges to database")
            
        except Exception as e:
            print(f"Error persisting DAG to database: {e}")
            import traceback
            traceback.print_exc()
            if self.db_session:
                self.db_session.rollback()
    
    async def emit_dag_created(self):
        """Emit DAG created event"""
        dag_data = self.create_dag_for_mode("", {})  # Will be called again with proper data
        effective_run_id = self.run_id or self.task_id
        try:
            await send_ws_event(
                self.websocket,
                "dag_created",
                {
                    "run_id": effective_run_id,
                    "nodes": self.nodes,
                    "edges": self.edges,
                    "levels": len(set(n.get("step_number", 0) for n in self.nodes))
                },
                run_id=effective_run_id
            )
        except Exception as e:
            print(f"Error sending DAG created event: {e}")
    
    async def update_node_status(self, node_id: str, new_status: str, error: str = None, work_dir: str = None):
        """Update a node's status and emit event, creating ExecutionEvent records in database.

        Args:
            node_id: The node ID to update
            new_status: The new status (running, completed, failed, etc.)
            error: Optional error message if status is failed
            work_dir: Optional work directory to scan for files when status is completed
        """
        old_status = self.node_statuses.get(node_id, "pending")
        self.node_statuses[node_id] = new_status
        effective_run_id = self.run_id or self.task_id

        # Get node info
        node_info = None
        for node in self.nodes:
            if node["id"] == node_id:
                node["status"] = new_status
                if error:
                    node["error"] = error
                node_info = node
                break

        # Track files when node completes (if work_dir provided)
        if new_status == "completed" and work_dir:
            self.track_files_in_work_dir(work_dir, node_id)
        
        # Create ExecutionEvent in database
        if self.event_repo and node_info:
            try:
                # Ensure DAG nodes exist in database first
                self._persist_dag_nodes_to_db()
                
                agent_name = node_info.get("agent", "unknown")
                # Use agent_call as event_type so UI recognizes it
                if new_status == "running":
                    event_type = "agent_call"
                    event_subtype = "started"
                elif new_status == "completed":
                    event_type = "agent_call"
                    event_subtype = "completed"
                elif new_status == "error":
                    event_type = "error"
                    event_subtype = "failed"
                else:
                    event_type = "agent_call"
                    event_subtype = "status_change"
                
                # Handle the status change events
                if new_status == "running":
                    # Node started - create a new execution event
                    from datetime import datetime, timezone
                    self.execution_order_counter += 1
                    event = self.event_repo.create_event(
                        run_id=self.run_id,
                        node_id=node_id,
                        event_type=event_type,
                        execution_order=self.execution_order_counter,
                        event_subtype="execution",
                        agent_name=agent_name,
                        status="running",
                        started_at=datetime.now(timezone.utc),
                        inputs={"node_info": node_info},
                        meta={"old_status": old_status, "new_status": new_status}
                    )
                    self.node_event_map[node_id] = event.id
                    print(f"Created ExecutionEvent {event.id} for node {node_id} (started)")
                    
                elif new_status in ["completed", "error"]:
                    # Node completed or failed - update existing event or create new one
                    event_id = self.node_event_map.get(node_id)
                    if event_id:
                        # Update existing event
                        from datetime import datetime, timezone
                        completed_at = datetime.now(timezone.utc)
                        started_at_event = self.event_repo.get_event(event_id)
                        duration_ms = None
                        if started_at_event and started_at_event.started_at:
                            # Ensure both datetimes are timezone-aware
                            started_at = started_at_event.started_at
                            if started_at.tzinfo is None:
                                started_at = started_at.replace(tzinfo=timezone.utc)
                            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
                        
                        event = self.event_repo.update_event(
                            event_id=event_id,
                            completed_at=completed_at,
                            duration_ms=duration_ms,
                            outputs={"status": new_status},
                            error_message=error,
                            status="completed" if new_status == "completed" else "failed"
                        )
                        print(f"Updated ExecutionEvent {event_id} for node {node_id} ({new_status})")
                    else:
                        # Create new event if none exists
                        from datetime import datetime, timezone
                        self.execution_order_counter += 1
                        event = self.event_repo.create_event(
                            run_id=self.run_id,
                            node_id=node_id,
                            event_type=event_type,
                            execution_order=self.execution_order_counter,
                            event_subtype="execution",
                            agent_name=agent_name,
                            status="completed" if new_status == "completed" else "failed",
                            started_at=datetime.now(timezone.utc),
                            completed_at=datetime.now(timezone.utc),
                            inputs={"node_info": node_info},
                            outputs={"status": new_status},
                            error_message=error,
                            meta={"old_status": old_status, "new_status": new_status}
                        )
                        print(f"Created ExecutionEvent {event.id} for node {node_id} ({new_status})")
                
            except Exception as e:
                print(f"Error creating ExecutionEvent for node {node_id}: {e}")
                import traceback
                traceback.print_exc()
                # Rollback the database session on error
                if self.db_session:
                    self.db_session.rollback()
        
        # Send WebSocket event with full node data
        try:
            data = {
                "node_id": node_id,
                "old_status": old_status,
                "new_status": new_status,
                "node": node_info  # Include full node info with generated_plan, etc.
            }
            if error:
                data["error"] = error
            await send_ws_event(
                self.websocket,
                "dag_node_status_changed",
                data,
                run_id=effective_run_id
            )
            
            # Also send full DAG update to refresh all node data in UI
            await send_ws_event(
                self.websocket,
                "dag_updated",
                {
                    "run_id": effective_run_id,
                    "nodes": self.nodes,
                    "edges": self.edges
                },
                run_id=effective_run_id
            )
        except Exception as e:
            print(f"Error sending DAG node status event: {e}")
    
    def get_node_by_step(self, step_number: int) -> Optional[str]:
        """Get node ID by step number"""
        for node in self.nodes:
            if node.get("step_number") == step_number:
                return node["id"]
        return None
    
    def get_first_node(self) -> Optional[str]:
        """Get the first node ID"""
        if self.nodes:
            return self.nodes[0]["id"]
        return None
    
    def get_last_node(self) -> Optional[str]:
        """Get the last node ID (terminator)"""
        for node in self.nodes:
            if node.get("type") == "terminator":
                return node["id"]
        return None
    
    def track_files_in_work_dir(self, work_dir: str, node_id: str = None, step_id: str = None):
        """
        Scan work directory and track generated files in the database.
        Links files to the current event, node, and step if available.

        Args:
            work_dir: The work directory to scan for files
            node_id: Optional node ID to link files to (e.g., "step_1", "planning")
            step_id: Optional step ID to link files to (database step record ID)
        """
        if not self.db_session or not self.run_id:
            return

        try:
            from cmbagent.database.models import File, WorkflowStep
            import os

            # Get current event for this node
            event_id = self.node_event_map.get(node_id) if node_id else None

            # If step_id not provided but node_id is like "step_N", try to find the step
            db_step_id = step_id
            if not db_step_id and node_id and node_id.startswith("step_"):
                try:
                    step_num = int(node_id.split("_")[1])
                    step = self.db_session.query(WorkflowStep).filter(
                        WorkflowStep.run_id == self.run_id,
                        WorkflowStep.step_number == step_num
                    ).first()
                    if step:
                        db_step_id = step.id
                except (ValueError, IndexError):
                    pass

            # Scan common output directories
            output_dirs = ["data", "codebase", "outputs", "chats", "cost", "time", "planning"]
            files_tracked = 0

            print(f"[DAGTracker] Scanning work_dir: {work_dir}")
            print(f"[DAGTracker] work_dir exists: {os.path.exists(work_dir)}")
            print(f"[DAGTracker] Using run_id: {self.run_id}, task_id: {self.task_id}")

            # Also list all directories/files directly in work_dir for debugging
            if os.path.exists(work_dir):
                try:
                    all_items = os.listdir(work_dir)
                    print(f"[DAGTracker] Contents of work_dir: {all_items}")
                except Exception as e:
                    print(f"[DAGTracker] Error listing work_dir: {e}")

            for output_dir_name in output_dirs:
                output_dir = os.path.join(work_dir, output_dir_name)
                exists = os.path.exists(output_dir)
                print(f"[DAGTracker] Checking {output_dir_name}/: exists={exists}")
                if not exists:
                    continue

                # Recursively find all files
                for root, dirs, files in os.walk(output_dir):
                    if files:
                        print(f"[DAGTracker] Found {len(files)} files in {root}: {files[:5]}{'...' if len(files) > 5 else ''}")
                    for filename in files:
                        file_path = os.path.join(root, filename)

                        # Check if file already tracked (by path and run_id)
                        existing_file = self.db_session.query(File).filter(
                            File.file_path == file_path,
                            File.run_id == self.run_id
                        ).first()

                        if existing_file:
                            # Update existing file with node/step if missing
                            if not existing_file.node_id and node_id:
                                existing_file.node_id = node_id
                            if not existing_file.step_id and db_step_id:
                                existing_file.step_id = db_step_id
                            continue

                        # Determine file type based on extension
                        file_ext = os.path.splitext(filename)[1].lower()
                        file_type = "code" if file_ext in [".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".go", ".rs"] else \
                                   "data" if file_ext in [".csv", ".json", ".pkl", ".npz", ".npy", ".parquet", ".yaml", ".yml"] else \
                                   "plot" if file_ext in [".png", ".jpg", ".jpeg", ".gif", ".pdf", ".svg", ".eps"] else \
                                   "text" if file_ext in [".txt", ".md", ".log", ".rst"] else \
                                   "other"

                        # Get file size
                        try:
                            file_size = os.path.getsize(file_path)
                        except:
                            file_size = 0

                        # Create File record with all available links
                        file_record = File(
                            run_id=self.run_id,
                            event_id=event_id,
                            node_id=node_id,
                            step_id=db_step_id,
                            file_path=file_path,
                            file_type=file_type,
                            size_bytes=file_size
                        )
                        self.db_session.add(file_record)
                        files_tracked += 1
                        print(f"[DAGTracker] Tracking file: {file_path} (type={file_type}, size={file_size})")

            self.db_session.commit()
            if files_tracked > 0:
                print(f"[DAGTracker] Tracked {files_tracked} new files in {work_dir} for node={node_id}, step_id={db_step_id}")

                # Send WebSocket event to notify UI of new files
                try:
                    import asyncio
                    effective_run_id = self.run_id or self.task_id
                    asyncio.create_task(send_ws_event(
                        self.websocket,
                        "files_updated",
                        {
                            "run_id": effective_run_id,
                            "node_id": node_id,
                            "step_id": db_step_id,
                            "files_tracked": files_tracked
                        },
                        run_id=effective_run_id
                    ))
                except Exception as ws_err:
                    print(f"[DAGTracker] Error sending files_updated event: {ws_err}")

            return files_tracked

        except Exception as e:
            print(f"[DAGTracker] Error tracking files: {e}")
            import traceback
            traceback.print_exc()
            if self.db_session:
                self.db_session.rollback()
            return 0


@app.get("/")
async def root():
    return {"message": "CMBAgent API is running"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/api/task/submit", response_model=TaskResponse)
async def submit_task(request: TaskRequest):
    """Submit a task for execution"""
    task_id = str(uuid.uuid4())

    return TaskResponse(
        task_id=task_id,
        status="submitted",
        message="Task submitted successfully. Connect to WebSocket for real-time updates."
    )

@app.get("/api/files/list")
async def list_directory(path: str = ""):
    """List files and directories in the specified path"""
    try:
        # Expand user path and resolve
        if path.startswith("~"):
            path = os.path.expanduser(path)

        if not path:
            path = os.path.expanduser("~/Desktop/cmbdir")

        path = os.path.abspath(path)

        # Security check - ensure path is within allowed directories
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Directory not found")

        if not os.path.isdir(path):
            raise HTTPException(status_code=400, detail="Path is not a directory")

        items = []
        try:
            for item_name in sorted(os.listdir(path)):
                item_path = os.path.join(path, item_name)

                # Skip hidden files
                if item_name.startswith('.'):
                    continue

                stat_info = os.stat(item_path)
                is_dir = os.path.isdir(item_path)

                file_item = FileItem(
                    name=item_name,
                    path=item_path,
                    type="directory" if is_dir else "file",
                    size=None if is_dir else stat_info.st_size,
                    modified=stat_info.st_mtime,
                    mime_type=None if is_dir else mimetypes.guess_type(item_path)[0]
                )
                items.append(file_item)
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")

        # Get parent directory
        parent = os.path.dirname(path) if path != "/" else None

        return DirectoryListing(
            path=path,
            items=items,
            parent=parent
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/content")
async def get_file_content(path: str):
    """Get the content of a file"""
    try:
        # Expand user path and resolve
        if path.startswith("~"):
            path = os.path.expanduser(path)

        path = os.path.abspath(path)

        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="File not found")

        if not os.path.isfile(path):
            raise HTTPException(status_code=400, detail="Path is not a file")

        # Check file size (limit to 10MB for safety)
        file_size = os.path.getsize(path)
        if file_size > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(status_code=413, detail="File too large")

        # Try to read as text first
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {
                "path": path,
                "content": content,
                "type": "text",
                "size": file_size,
                "mime_type": mimetypes.guess_type(path)[0]
            }
        except UnicodeDecodeError:
            # If it's not text, return file info only
            return {
                "path": path,
                "content": None,
                "type": "binary",
                "size": file_size,
                "mime_type": mimetypes.guess_type(path)[0],
                "message": "Binary file - content not displayed"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/files/clear-directory")
async def clear_directory(path: str):
    """Clear all contents of a directory"""
    try:
        # Expand user path
        if path.startswith("~"):
            path = os.path.expanduser(path)

        abs_path = os.path.abspath(path)

        # Security check - ensure path exists and is a directory
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Directory not found")

        if not os.path.isdir(abs_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")

        # Count items before deletion
        items_deleted = 0

        # Remove all contents
        import shutil
        for item in os.listdir(abs_path):
            item_path = os.path.join(abs_path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
            items_deleted += 1

        return {
            "message": f"Successfully cleared directory: {path}",
            "items_deleted": items_deleted,
            "path": abs_path
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing directory: {str(e)}")

@app.get("/api/files/images")
async def get_images(work_dir: str):
    """Get all image files from the working directory"""
    try:
        # Expand user path
        if work_dir.startswith("~"):
            work_dir = os.path.expanduser(work_dir)

        abs_path = os.path.abspath(work_dir)

        # Check if directory exists
        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            return {"images": [], "message": "Working directory not found"}

        # Common image extensions
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.tiff', '.tif'}

        images = []

        # Recursively search for image files
        for root, dirs, files in os.walk(abs_path):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()

                if file_ext in image_extensions:
                    # Get relative path from work_dir
                    rel_path = os.path.relpath(file_path, abs_path)

                    # Get file stats
                    stat = os.stat(file_path)

                    images.append({
                        "name": file,
                        "path": file_path,
                        "relative_path": rel_path,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "extension": file_ext,
                        "directory": os.path.dirname(rel_path) if os.path.dirname(rel_path) else "root"
                    })

        # Sort by modification time (newest first)
        images.sort(key=lambda x: x['modified'], reverse=True)

        return {
            "work_dir": work_dir,
            "images": images,
            "count": len(images)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scanning for images: {str(e)}")

@app.get("/api/files/serve-image")
async def serve_image(path: str):
    """Serve an image file"""
    try:
        # Security check - ensure path exists and is a file
        abs_path = os.path.abspath(path)

        if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
            raise HTTPException(status_code=404, detail="Image file not found")

        # Check if it's an image file
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.tiff', '.tif'}
        file_ext = os.path.splitext(abs_path)[1].lower()

        if file_ext not in image_extensions:
            raise HTTPException(status_code=400, detail="File is not an image")

        # Determine MIME type
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff'
        }

        mime_type = mime_types.get(file_ext, 'application/octet-stream')

        # Return the file
        return FileResponse(abs_path, media_type=mime_type)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving image: {str(e)}")

# API Credentials endpoints
@app.get("/api/credentials/test-all")
async def test_all_api_credentials():
    """Test all configured API credentials"""
    try:
        results = await test_all_credentials()
        return {
            "status": "success",
            "results": results,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing credentials: {str(e)}")

@app.post("/api/credentials/test")
async def test_specific_credentials(credentials: CredentialStorage):
    """Test specific credentials provided by the user"""
    try:
        results = {}
        
        if credentials.openai_key:
            results['openai'] = await test_openai_credentials(credentials.openai_key)
        
        if credentials.anthropic_key:
            results['anthropic'] = await test_anthropic_credentials(credentials.anthropic_key)
        
        if credentials.vertex_json:
            results['vertex'] = await test_vertex_credentials(credentials.vertex_json)
        
        return {
            "status": "success",
            "results": results,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing credentials: {str(e)}")

@app.post("/api/credentials/store")
async def store_api_credentials(credentials: CredentialStorage):
    """Store API credentials in environment variables (session only)"""
    try:
        updates = store_credentials_in_env(credentials)
        
        # Test the newly stored credentials
        test_results = await test_all_credentials()
        
        return {
            "status": "success",
            "message": "Credentials stored successfully",
            "updates": updates,
            "test_results": test_results,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing credentials: {str(e)}")

@app.get("/api/credentials/status")
async def get_credentials_status():
    """Get current status of all API credentials"""
    try:
        results = await test_all_credentials()
        
        # Create summary status
        summary = {
            "total": len(results),
            "valid": sum(1 for r in results.values() if r.status == "valid"),
            "invalid": sum(1 for r in results.values() if r.status == "invalid"),
            "not_configured": sum(1 for r in results.values() if r.status == "not_configured"),
            "errors": sum(1 for r in results.values() if r.status == "error")
        }
        
        return {
            "status": "success",
            "summary": summary,
            "results": results,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting credentials status: {str(e)}")

# arXiv Filter API endpoint
@app.post("/api/arxiv/filter", response_model=ArxivFilterResponse)
async def arxiv_filter_endpoint(request: ArxivFilterRequest):
    """
    Extract arXiv URLs from input text and download corresponding PDFs.
    
    Args:
        request: ArxivFilterRequest containing input_text and optional work_dir
        
    Returns:
        ArxivFilterResponse with download results and metadata
    """
    try:
        print(f"Processing arXiv filter request...")
        print(f"Input text length: {len(request.input_text)} characters")
        if request.work_dir:
            print(f"Work directory: {request.work_dir}")
        
        # Use work_dir from request or fall back to cmbagent's default
        work_dir = request.work_dir if request.work_dir else None
        
        # Call the arxiv_filter function
        result = cmbagent.arxiv_filter(
            input_text=request.input_text,
            work_dir=work_dir
        )
        
        # Create success response
        return ArxivFilterResponse(
            status="success",
            result=result,
            message=f"Successfully processed {result['downloads_successful']} downloads out of {len(result['urls_found'])} URLs found"
        )
        
    except Exception as e:
        print(f"Error in arxiv_filter_endpoint: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing arXiv filter request: {str(e)}"
        )

# Enhance Input API endpoint
@app.post("/api/enhance-input", response_model=EnhanceInputResponse)
async def enhance_input_endpoint(request: EnhanceInputRequest):
    """
    Enhance input text with contextual information from referenced arXiv papers.
    
    Args:
        request: EnhanceInputRequest containing input_text and processing options
        
    Returns:
        EnhanceInputResponse with enhanced text and cost breakdown
    """
    try:
        import os
        import json
        import tempfile
        
        print(f"Processing enhance-input request...")
        print(f"Input text length: {len(request.input_text)} characters")
        print(f"Max workers: {request.max_workers}")
        print(f"Max depth: {request.max_depth}")
        if request.work_dir:
            print(f"Work directory: {request.work_dir}")
        
        # Use work_dir from request or create a temporary one
        work_dir = request.work_dir
        if not work_dir:
            # Create a temporary directory for processing
            work_dir = tempfile.mkdtemp(prefix="enhance_input_")
            print(f"Created temporary work directory: {work_dir}")
        
        # Check if enhanced_input.md already exists to avoid re-processing
        enhanced_input_file = os.path.join(work_dir, "enhanced_input.md")
        if request.work_dir and os.path.exists(enhanced_input_file):
            # Read existing enhanced text if work_dir was provided and file exists
            with open(enhanced_input_file, 'r', encoding='utf-8') as f:
                enhanced_text = f.read()
            print("Using existing enhanced_input.md file")
        else:
            # Call the preprocess_task function
            enhanced_text = cmbagent.preprocess_task(
                text=request.input_text,
                work_dir=work_dir,
                max_workers=request.max_workers,
                max_depth=request.max_depth,
                clear_work_dir=False  # Don't clear when work_dir is provided
            )
        
        # Collect cost information
        cost_breakdown = {}
        processing_summary = {}
        
        # Try to read OCR costs if available
        ocr_cost_file = os.path.join(work_dir, "ocr_cost.json")
        if os.path.exists(ocr_cost_file):
            try:
                with open(ocr_cost_file, 'r') as f:
                    ocr_data = json.load(f)
                    cost_breakdown['ocr'] = {
                        'total_cost': ocr_data.get('total_cost_usd', 0),
                        'pages_processed': ocr_data.get('total_pages_processed', 0),
                        'files_processed': len(ocr_data.get('entries', []))
                    }
            except Exception as e:
                print(f"Warning: Could not read OCR cost file: {e}")
        
        # Try to read summary processing costs
        summaries_dir = os.path.join(work_dir, "summaries")
        if os.path.exists(summaries_dir):
            summary_cost_files = []
            for root, dirs, files in os.walk(summaries_dir):
                for file in files:
                    if file.startswith('cost_report_') and file.endswith('.json'):
                        summary_cost_files.append(os.path.join(root, file))
            
            total_summary_cost = 0
            all_agent_costs = []
            
            for cost_file in summary_cost_files:
                try:
                    with open(cost_file, 'r') as f:
                        cost_data = json.load(f)
                        # Each cost file contains an array of agent cost entries
                        if isinstance(cost_data, list):
                            for entry in cost_data:
                                if isinstance(entry, dict) and entry.get('Agent') != 'Total':
                                    cost_usd = entry.get('Cost ($)', 0)
                                    if isinstance(cost_usd, (int, float)) and not (isinstance(cost_usd, float) and (cost_usd != cost_usd or cost_usd == float('inf'))):  # Check for NaN/inf
                                        total_summary_cost += cost_usd
                                        all_agent_costs.append({
                                            'agent': entry.get('Agent', 'Unknown'),
                                            'cost': cost_usd,
                                            'model': entry.get('Model', 'N/A'),
                                            'prompt_tokens': entry.get('Prompt Tokens', 0),
                                            'completion_tokens': entry.get('Completion Tokens', 0),
                                            'total_tokens': entry.get('Total Tokens', 0)
                                        })
                except Exception as e:
                    print(f"Warning: Could not read summary cost file {cost_file}: {e}")
            
            if all_agent_costs:
                cost_breakdown['summarization'] = {
                    'total_cost': total_summary_cost,
                    'agents': all_agent_costs
                }
        
        # Calculate total cost
        total_cost = 0
        if 'ocr' in cost_breakdown:
            total_cost += cost_breakdown['ocr']['total_cost']
        if 'summarization' in cost_breakdown:
            total_cost += cost_breakdown['summarization']['total_cost']
        
        cost_breakdown['total'] = total_cost
        
        # Create processing summary
        processing_summary = {
            'enhanced_text_length': len(enhanced_text),
            'original_text_length': len(request.input_text),
            'enhancement_added': len(enhanced_text) > len(request.input_text),
            'work_dir': work_dir
        }
        
        # Create success response
        return EnhanceInputResponse(
            status="success",
            enhanced_text=enhanced_text,
            processing_summary=processing_summary,
            cost_breakdown=cost_breakdown,
            message=f"Successfully enhanced input text. Total cost: ${total_cost:.4f}"
        )
        
    except Exception as e:
        print(f"Error in enhance_input_endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing enhance-input request: {str(e)}"
        )

# Branching API endpoints
@app.post("/api/runs/{run_id}/branch")
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

@app.post("/api/runs/{run_id}/play-from-node")
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

@app.get("/api/branches/compare")
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

@app.get("/api/runs/{run_id}/branch-tree")
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

@app.get("/api/runs/{run_id}/resumable-nodes")
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

@app.get("/api/runs/{run_id}/history")
async def get_run_history(run_id: str, event_type: Optional[str] = None):
    """Get execution history for a workflow run.
    
    Args:
        run_id: The workflow run ID (can be task_id, will be resolved to db_run_id)
        event_type: Optional filter by event type
    """
    try:
        # Resolve task_id to database run_id
        effective_run_id = run_id
        if SERVICES_AVAILABLE:
            run_info = workflow_service.get_run_info(run_id)
            if run_info and run_info.get("db_run_id"):
                effective_run_id = run_info["db_run_id"]
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
            # Keep only 'complete' or events without subtypes
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
            
            print(f"[API] Found {len(events_data)} events for run_id={effective_run_id} (filtered from {len(events)} raw events)")
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

@app.get("/api/runs/{run_id}/files")
async def get_run_files(run_id: str):
    """Get all files generated during a workflow run.

    Args:
        run_id: The workflow run ID
    """
    try:
        effective_run_id = run_id
        if SERVICES_AVAILABLE:
            run_info = workflow_service.get_run_info(run_id)
            if run_info and run_info.get("db_run_id"):
                effective_run_id = run_info["db_run_id"]

        from cmbagent.database import get_db_session
        from cmbagent.database.models import File, DAGNode, WorkflowStep
        from cmbagent.database.session_manager import SessionManager
        from sqlalchemy.orm import joinedload

        db = get_db_session()
        session_manager = SessionManager(db)

        # Get or create session
        session_id = session_manager.get_or_create_default_session()

        # Query files directly by run_id - don't require node_id to be set
        # Use outerjoin to include files even if they don't have a node or step
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

@app.get("/api/nodes/{node_id}/events")
async def get_node_events(node_id: str, run_id: Optional[str] = None, event_type: Optional[str] = None, include_internal: bool = False):
    """Get execution events for a DAG node.
    
    Args:
        node_id: The DAG node ID
        run_id: Optional workflow run ID to filter events (RECOMMENDED to avoid getting events from multiple runs)
        event_type: Optional filter by event type
        include_internal: If True, include node_started/completed and 'start' subtype events (default: False)
    """
    try:
        from cmbagent.database import get_db_session
        from cmbagent.database.models import DAGNode, ExecutionEvent
        
        db = get_db_session()
        
        # CRITICAL: Resolve task_id to db_run_id before querying
        effective_run_id = None
        if run_id:
            effective_run_id = resolve_run_id(run_id)
            print(f"[API] Resolved task_id {run_id} to db_run_id {effective_run_id}")
        
        # If no run_id provided, try to find the node and get its run_id
        if not effective_run_id:
            # First try to find the MOST RECENT DAGNode with this node_id
            # (node_id can be reused across runs, so we need the latest one)
            from cmbagent.database.models import WorkflowRun
            dag_node = db.query(DAGNode).join(WorkflowRun).filter(
                DAGNode.id == node_id
            ).order_by(WorkflowRun.started_at.desc()).first()
            
            if dag_node:
                effective_run_id = dag_node.run_id
                print(f"[API] Found node {node_id} in run {effective_run_id} (most recent)")
            else:
                # If node_id is a name (not UUID), we have a problem - need run_id
                print(f"[API] WARNING: node_id '{node_id}' not found in any run")
        
        # CRITICAL: Always require run_id for accurate filtering
        if not effective_run_id:
            print(f"[API] ERROR: No run_id found for node {node_id}")
            return {
                "node_id": node_id,
                "total_events": 0,
                "events": [],
                "error": "run_id is required to fetch events. Please provide run_id parameter."
            }
        
        # Build query with MANDATORY run_id filter to avoid wrong data
        query = db.query(ExecutionEvent).filter(
            ExecutionEvent.node_id == node_id,
            ExecutionEvent.run_id == effective_run_id  # REQUIRED: Prevent cross-run contamination
        )
        print(f"[API] Filtering events for node {node_id} in run {effective_run_id} (resolved from {run_id})")
        
        if event_type:
            query = query.filter(ExecutionEvent.event_type == event_type)
        
        events = query.order_by(ExecutionEvent.execution_order).all()
        
        print(f"[API] Raw events for node {node_id}: {len(events)}")
        
        # Filter out internal events and duplicate 'start' events unless requested
        if not include_internal:
            # Remove node lifecycle events
            events = [e for e in events if e.event_type not in ['node_started', 'node_completed']]
            # Remove 'start' subtypes to avoid double counting (keep only 'complete' or None)
            events = [e for e in events if e.event_subtype not in ['start']]
        
        print(f"[API] Filtered events for node {node_id}: {len(events)}")
        
        print(f"[API] Filtered events for node {node_id}: {len(events)}")
        
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
        
        print(f"[API] Returning {len(events_data)} events for node {node_id}")
        
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

@app.get("/api/nodes/{node_id}/execution-summary")
async def get_node_execution_summary(node_id: str, run_id: Optional[str] = None):
    """Get execution summary for a DAG node.
    
    Args:
        node_id: The DAG node ID
        run_id: Optional workflow run ID (recommended to avoid mixing data from multiple runs)
    """
    try:
        from cmbagent.database import get_db_session
        from cmbagent.database.models import DAGNode
        from cmbagent.database.dag_metadata import DAGMetadataEnricher
        from cmbagent.database.session_manager import SessionManager
        
        db = get_db_session()
        
        # If no run_id provided, try to find it from the MOST RECENT node
        if not run_id:
            from cmbagent.database.models import WorkflowRun
            dag_node = db.query(DAGNode).join(WorkflowRun).filter(
                DAGNode.id == node_id
            ).order_by(WorkflowRun.started_at.desc()).first()
            
            if dag_node:
                run_id = dag_node.run_id
                print(f"[API] Found node {node_id} in run {run_id} (most recent)")
        
        session_manager = SessionManager(db)
        
        # Get or create session
        session_id = session_manager.get_or_create_default_session()
        
        enricher = DAGMetadataEnricher(db, session_id)
        
        summary = enricher.enrich_node(node_id, run_id=run_id)
        db.close()
        
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/nodes/{node_id}/files")
async def get_node_files(node_id: str, run_id: Optional[str] = None):
    """Get files generated by a DAG node.
    
    Args:
        node_id: The DAG node ID
        run_id: Optional workflow run ID (recommended to avoid mixing data from multiple runs)
    """
    try:
        from cmbagent.database import get_db_session
        from cmbagent.database.models import File, DAGNode, WorkflowRun
        
        db = get_db_session()
        
        # If no run_id provided, try to find it from the MOST RECENT node
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

@app.get("/api/events/{event_id}/tree")
async def get_event_tree(event_id: str):
    """Get event tree (nested events) from root event."""
    try:
        from cmbagent.database import get_db_session
        from cmbagent.database.repository import EventRepository
        from cmbagent.database.session_manager import SessionManager
        
        db = get_db_session()
        session_manager = SessionManager(db)
        
        # Get or create session
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

@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()
    
    # Register connection with connection manager if available
    if SERVICES_AVAILABLE:
        await connection_manager.connect(websocket, task_id)
    else:
        active_connections[task_id] = websocket

    try:
        # Wait for task data
        data = await websocket.receive_json()
        task = data.get("task", "")
        config = data.get("config", {})

        if not task:
            await send_ws_event(websocket, "error", {"message": "No task provided"}, run_id=task_id)
            return

        # Create workflow run in database if services available
        if SERVICES_AVAILABLE:
            mode = config.get("mode", "one-shot")
            # Extract mode-specific primary agent and model for database tracking
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
            
            run_result = workflow_service.create_workflow_run(
                task_id=task_id,
                task_description=task,
                mode=mode,
                agent=agent,
                model=model,
                config=config
            )
            print(f"Created workflow run: {run_result}")

        # Send initial status
        await send_ws_event(websocket, "status", {"message": "Starting CMBAgent execution..."}, run_id=task_id)

        # Create background task for execution
        execution_task = asyncio.create_task(
            execute_cmbagent_task(websocket, task_id, task, config)
        )

        # Handle both execution and client messages
        while True:
            done, pending = await asyncio.wait(
                [execution_task, asyncio.create_task(websocket.receive_json())],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Check if execution completed
            if execution_task in done:
                # Execution finished
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
            await send_ws_event(websocket, "error", {"message": f"Execution error: {str(e)}"}, run_id=task_id)
        except:
            pass
    finally:
        # Disconnect from connection manager if available
        if SERVICES_AVAILABLE:
            await connection_manager.disconnect(task_id)
        elif task_id in active_connections:
            del active_connections[task_id]


async def handle_client_message(websocket: WebSocket, task_id: str, message: dict):
    """Handle messages from client (e.g., approval responses, pause, resume)
    
    Integrates with Stage 3 (State Machine), Stage 5 (WebSocket Protocol),
    and Stage 6 (HITL Approval System).
    """
    msg_type = message.get("type")

    if msg_type == "ping":
        # Respond with pong
        if SERVICES_AVAILABLE:
            await connection_manager.send_pong(task_id)
        else:
            await send_ws_event(websocket, "pong", {}, run_id=task_id)

    elif msg_type == "resolve_approval":
        # Handle approval resolution (Stage 6: HITL)
        approval_id = message.get("approval_id")
        resolution = message.get("resolution")
        feedback = message.get("feedback")

        try:
            from cmbagent.database import get_db_session
            from cmbagent.database.models import WorkflowRun, ApprovalRequest
            from cmbagent.database.approval_manager import ApprovalManager

            db = get_db_session()
            try:
                # Get approval request to find session_id
                approval = db.query(ApprovalRequest).filter(
                    ApprovalRequest.id == approval_id
                ).first()

                if not approval:
                    print(f"Approval {approval_id} not found")
                    return

                # Get workflow run to find session_id
                run = db.query(WorkflowRun).filter(
                    WorkflowRun.id == approval.run_id
                ).first()

                if not run:
                    print(f"Workflow run {approval.run_id} not found")
                    return

                # Create approval manager and resolve
                approval_manager = ApprovalManager(db, str(run.session_id))
                resolved = approval_manager.resolve_approval(
                    approval_id=approval_id,
                    resolution=resolution,
                    user_feedback=feedback
                )

                print(f"Approval {approval_id} resolved as {resolution}")

            finally:
                db.close()

        except Exception as e:
            print(f"Error resolving approval: {e}")

    elif msg_type == "pause":
        # Handle workflow pause request (Stage 3: State Machine)
        print(f"Pause requested for task {task_id}")
        
        if SERVICES_AVAILABLE:
            # Use workflow service for database-backed pause
            result = workflow_service.pause_workflow(task_id)
            print(f"[Pause] workflow_service.pause_workflow result: {result}")
            execution_service.set_paused(task_id, True)
            print(f"[Pause] execution_service.is_paused({task_id}): {execution_service.is_paused(task_id)}")
            await connection_manager.send_workflow_paused(task_id, result.get("message", "Workflow paused"))
            print(f"[Pause] Sent workflow_paused event to task {task_id}")
        else:
            await send_ws_event(
                websocket, 
                "workflow_paused", 
                {"message": "Workflow paused", "status": "paused"}, 
                run_id=task_id
            )

    elif msg_type == "resume":
        # Handle workflow resume request (Stage 3: State Machine)
        print(f"Resume requested for task {task_id}")
        
        if SERVICES_AVAILABLE:
            # Use workflow service for database-backed resume
            result = workflow_service.resume_workflow(task_id)
            execution_service.set_paused(task_id, False)
            await connection_manager.send_workflow_resumed(task_id, result.get("message", "Workflow resumed"))
        else:
            await send_ws_event(
                websocket, 
                "workflow_resumed", 
                {"message": "Workflow resumed", "status": "executing"}, 
                run_id=task_id
            )

    elif msg_type == "cancel":
        # Handle workflow cancel request (Stage 3: State Machine)
        print(f"Cancel requested for task {task_id}")
        
        if SERVICES_AVAILABLE:
            # Use workflow service for database-backed cancel
            result = workflow_service.cancel_workflow(task_id)
            execution_service.set_cancelled(task_id, True)
            await connection_manager.send_workflow_cancelled(task_id, result.get("message", "Workflow cancelled"))
        else:
            await send_ws_event(
                websocket, 
                "workflow_cancelled", 
                {"message": "Workflow cancelled", "status": "cancelled"}, 
                run_id=task_id
            )

    elif msg_type == "request_state":
        # Request current state (Stage 5: WebSocket reconnection support)
        print(f"State request for task {task_id}")
        if SERVICES_AVAILABLE:
            run_info = workflow_service.get_run_info(task_id)
            if run_info:
                await connection_manager.send_status(task_id, run_info.get("status", "unknown"))
            # Replay missed events
            since_timestamp = message.get("since")
            await connection_manager.replay_missed_events(task_id, since_timestamp)

    else:
        print(f"Unknown message type: {msg_type}")

async def execute_cmbagent_task(websocket: WebSocket, task_id: str, task: str, config: Dict[str, Any]):
    """Execute CMBAgent task with real-time output streaming.
    
    Integrates with:
    - Stage 3: State Machine (pause/resume/cancel via workflow_service)
    - Stage 5: WebSocket Protocol (standardized events)
    - Stage 7: Retry Mechanism (via execution_service)
    """

    # Get work directory from config or use default
    work_dir = config.get("workDir", "~/Desktop/cmbdir")
    if work_dir.startswith("~"):
        work_dir = os.path.expanduser(work_dir)

    # Create a subdirectory for this specific task
    task_work_dir = os.path.join(work_dir, task_id)
    os.makedirs(task_work_dir, exist_ok=True)
    
    # Set up environment variables to disable display and enable debug if needed
    os.environ["CMBAGENT_DEBUG"] = "false"
    os.environ["CMBAGENT_DISABLE_DISPLAY"] = "true"
    
    # Initialize DAG tracker (will be populated inside try block)
    dag_tracker = None
    
    try:
        # Send status update
        await send_ws_event(websocket, "status", {"message": "Initializing CMBAgent..."}, run_id=task_id)
        
        # Get API keys from environment
        api_keys = get_api_keys_from_env()
        
        # Map frontend config to CMBAgent parameters
        mode = config.get("mode", "one-shot")
        engineer_model = config.get("model", "gpt-4o")
        max_rounds = config.get("maxRounds", 25)
        max_attempts = config.get("maxAttempts", 6)
        agent = config.get("agent", "engineer")
        default_formatter_model = config.get("defaultFormatterModel", "o3-mini-2025-01-31")
        default_llm_model = config.get("defaultModel", "gpt-4.1-2025-04-14")
        
        # Debug: Log the received config
        print(f"DEBUG: Received config: {config}")
        print(f"DEBUG: defaultModel = {default_llm_model}")
        print(f"DEBUG: defaultFormatterModel = {default_formatter_model}")

        # Get run_id from workflow service if available
        db_run_id = None
        if SERVICES_AVAILABLE:
            # First check if we already have run_info from earlier workflow creation
            run_info = workflow_service.get_run_info(task_id)
            if run_info:
                db_run_id = run_info.get("db_run_id")
                print(f"DEBUG: Using db_run_id from workflow service: {db_run_id}")

        # Create DAG tracker for this execution, passing the run_id from workflow service
        dag_tracker = DAGTracker(websocket, task_id, mode, run_id=db_run_id)
        dag_data = dag_tracker.create_dag_for_mode(task, config)
        effective_run_id = dag_tracker.run_id or task_id
        
        # Emit DAG created event
        await send_ws_event(
            websocket,
            "dag_created",
            {
                "run_id": effective_run_id,
                "nodes": dag_tracker.nodes,
                "edges": dag_tracker.edges,
                "levels": dag_data.get("levels", 1)
            },
            run_id=effective_run_id
        )
        print(f"DEBUG: Emitted DAG with {len(dag_tracker.nodes)} nodes")

        # Planning & Control specific parameters
        planner_model = config.get("plannerModel", "gpt-4.1-2025-04-14")
        plan_reviewer_model = config.get("planReviewerModel", "o3-mini-2025-01-31")
        researcher_model = config.get("researcherModel", "gpt-4.1-2025-04-14")
        max_plan_steps = config.get("maxPlanSteps", 6 if mode == "idea-generation" else 2)
        n_plan_reviews = config.get("nPlanReviews", 1)
        plan_instructions = config.get("planInstructions", "")
        
        # Idea Generation specific parameters
        idea_maker_model = config.get("ideaMakerModel", "gpt-4.1-2025-04-14")
        idea_hater_model = config.get("ideaHaterModel", "o3-mini-2025-01-31")
        
        # OCR specific parameters
        save_markdown = config.get("saveMarkdown", True)
        save_json = config.get("saveJson", True)
        save_text = config.get("saveText", False)
        max_workers = config.get("maxWorkers", 4)
        ocr_output_dir = config.get("ocrOutputDir", None)
        
        await send_ws_event(websocket, "output", {"message": f"🚀 Starting CMBAgent in {mode.replace('-', ' ').title()} mode"}, run_id=task_id)
        await send_ws_event(websocket, "output", {"message": f"🚀 Default LLM Model: {default_llm_model}"}, run_id=task_id)
        await send_ws_event(websocket, "output", {"message": f"🚀 Default Formatter Model: {default_formatter_model}"}, run_id=task_id)
        await send_ws_event(websocket, "output", {"message": f"📋 Task: {task}"}, run_id=task_id)

        # Update first node to running
        first_node = dag_tracker.get_first_node()
        if first_node:
            await dag_tracker.update_node_status(first_node, "running")

        if mode == "planning-control":
            await send_ws_event(websocket, "output", {"message": f"⚙️ Configuration: Planner={planner_model}, Engineer={engineer_model}, Researcher={researcher_model}, Plan Reviewer={plan_reviewer_model}"}, run_id=task_id)
        elif mode == "idea-generation":
            await send_ws_event(websocket, "output", {"message": f"⚙️ Configuration: Idea Maker={idea_maker_model}, Idea Hater={idea_hater_model}, Planner={planner_model}, Plan Reviewer={plan_reviewer_model}"}, run_id=task_id)
        elif mode == "ocr":
            await send_ws_event(websocket, "output", {"message": f"⚙️ Configuration: Save Markdown={save_markdown}, Save JSON={save_json}, Save Text={save_text}, Max Workers={max_workers}"}, run_id=task_id)
        elif mode == "arxiv":
            await send_ws_event(websocket, "output", {"message": f"⚙️ Configuration: arXiv Filter mode - Scanning text for arXiv URLs and downloading papers"}, run_id=task_id)
        elif mode == "enhance-input":
            max_depth = config.get("maxDepth", 10)
            await send_ws_event(websocket, "output", {"message": f"⚙️ Configuration: Enhance Input mode - Max Workers={max_workers}, Max Depth={max_depth}"}, run_id=task_id)
        else:
            await send_ws_event(websocket, "output", {"message": f"⚙️ Configuration: Agent={agent}, Model={engineer_model}, MaxRounds={max_rounds}, MaxAttempts={max_attempts}"}, run_id=task_id)
        
        start_time = time.time()
        
        # Execute the one_shot function in a separate thread to avoid blocking
        loop = asyncio.get_event_loop()
        
        # Create a custom stdout/stderr capture with DAG tracking
        stream_capture = StreamCapture(websocket, task_id, dag_tracker=dag_tracker, loop=loop, work_dir=task_work_dir)
        
        # Create WebSocket-based callbacks for DAG updates
        from cmbagent.callbacks import create_websocket_callbacks, merge_callbacks, create_print_callbacks, WorkflowCallbacks
        
        def ws_send_event(event_type: str, data: Dict[str, Any]):
            """Send WebSocket event from sync context"""
            asyncio.run_coroutine_threadsafe(
                send_ws_event(websocket, event_type, data, run_id=task_id),
                loop
            )
        
        # Create pause check callback that blocks while paused
        def sync_pause_check():
            """Synchronous pause check - blocks while paused."""
            if SERVICES_AVAILABLE:
                while execution_service.is_paused(task_id):
                    if execution_service.is_cancelled(task_id):
                        raise Exception("Workflow cancelled by user")
                    time.sleep(0.5)
        
        def should_continue():
            """Check if workflow should continue."""
            if SERVICES_AVAILABLE:
                if execution_service.is_cancelled(task_id):
                    return False
            return True
        
        # Create callbacks that emit WebSocket events
        ws_callbacks = create_websocket_callbacks(ws_send_event, task_id)
        
        # Add event tracking callbacks that create ExecutionEvent records
        def create_execution_event(event_type: str, agent_name: str, **kwargs):
            """Helper to create ExecutionEvent from callbacks"""
            if dag_tracker and dag_tracker.event_repo and dag_tracker.db_session:
                try:
                    from datetime import datetime, timezone
                    dag_tracker.execution_order_counter += 1
                    
                    # Get current node_id from DAG tracker
                    current_node_id = None
                    for node_id, status in dag_tracker.node_statuses.items():
                        if status == "running":
                            current_node_id = node_id
                            break
                    
                    # Ensure DAG nodes exist before creating events
                    dag_tracker._persist_dag_nodes_to_db()
                    
                    event = dag_tracker.event_repo.create_event(
                        run_id=dag_tracker.run_id,
                        node_id=current_node_id,
                        event_type=event_type,
                        execution_order=dag_tracker.execution_order_counter,
                        agent_name=agent_name,
                        **kwargs
                    )
                    print(f"✓ Created {event_type} event for {agent_name} @ node {current_node_id} (order: {dag_tracker.execution_order_counter})")
                except Exception as e:
                    print(f"✗ Error creating {event_type} event for {agent_name}: {e}")
                    print(f"   Kwargs: {list(kwargs.keys())}")
                    import traceback
                    traceback.print_exc()
                    # Rollback on error
                    if dag_tracker.db_session:
                        dag_tracker.db_session.rollback()
            else:
                print(f"⚠ Cannot create event - tracker not ready (repo: {dag_tracker.event_repo is not None if dag_tracker else False})")
        
        # Callbacks for fine-grained event tracking
        # Note: WorkflowCallbacks are synchronous, called from thread pool
        def on_agent_msg(agent, role, content, metadata):
            print(f"💬 [{agent}] {content[:100] if content else 'None'}")
            try:
                import re
                
                # Detect code blocks in message
                code_blocks = re.findall(r'```(\w*)\n([\s\S]*?)```', content) if content else []
                
                # Extract tool calls from metadata if present
                tool_calls = []
                if metadata and 'tool_calls' in metadata:
                    tool_calls = metadata['tool_calls']
                
                # Detect file references in content
                file_refs = re.findall(r'(?:file|path|saved|written|created)\s*[:"`]\s*([\w/.-]+\.\w+)', content or "", re.IGNORECASE)
                
                # Track the main message with rich metadata
                create_execution_event(
                    event_type="agent_call",
                    agent_name=agent,
                    event_subtype="message",
                    status="completed",
                    inputs={
                        "role": role, 
                        "message": content[:500] if content else "",
                        "sender": metadata.get('sender') if metadata else None
                    },
                    outputs={
                        "full_content": content if content and len(content) <= 3000 else (content[:3000] + "..." if content else "")
                    },
                    meta=dict(
                        metadata or {},
                        has_code=len(code_blocks) > 0,
                        has_tool_calls=len(tool_calls) > 0,
                        file_references=file_refs if file_refs else [],
                        content_length=len(content) if content else 0
                    )
                )
                
                # If code blocks detected, track them separately for skill extraction
                if code_blocks:
                    for language, code in code_blocks:
                        create_execution_event(
                            event_type="code_exec",
                            agent_name=agent,
                            event_subtype="generated",
                            status="completed",
                            inputs={"code": code.strip()[:2000], "context": content[:200] if content else ""},
                            meta={
                                "language": language or "python", 
                                "source": "agent_message",
                                "code_length": len(code)
                            }
                        )
            except Exception as e:
                print(f"Error creating agent_call event: {e}")
                import traceback
                traceback.print_exc()
        
        def on_code_exec(agent, code, language, result):
            print(f"💻 [{agent}] Code execution ({language})")
            try:
                import re
                import os
                
                # Detect file operations in code (writes, reads, both)
                file_writes = re.findall(r'(?:with\s+open|open)\(["\']([^"\']+)["\']\s*,\s*["\']w', code) if code else []
                file_reads = re.findall(r'(?:with\s+open|open)\(["\']([^"\']+)["\']\s*,\s*["\']r', code) if code else []
                
                # Detect imports for dependency tracking
                imports = re.findall(r'^(?:from|import)\s+([\w.]+)', code or "", re.MULTILINE)
                
                # Track execution with comprehensive metadata
                create_execution_event(
                    event_type="code_exec",
                    agent_name=agent,
                    event_subtype="executed",
                    status="completed" if result and not "error" in str(result).lower() else "failed",
                    inputs={
                        "language": language, 
                        "code": code[:2000] if code else "",
                        "code_hash": str(hash(code)) if code else None
                    },
                    outputs={
                        "result": result[:2000] if result else None,
                        "result_preview": result[:500] if result else None
                    },
                    meta={
                        "language": language,
                        "files_written": file_writes if file_writes else [],
                        "files_read": file_reads if file_reads else [],
                        "imports": list(set(imports)) if imports else [],
                        "code_length": len(code) if code else 0,
                        "has_error": "error" in str(result).lower() if result else False
                    }
                )
                
                # Track file generation separately with content capture
                if file_writes:
                    for file_path in file_writes:
                        # Try to read file content if it exists
                        file_content = None
                        file_size = None
                        try:
                            if os.path.exists(file_path):
                                file_size = os.path.getsize(file_path)
                                # Only read small files (< 1MB)
                                if file_size < 1024 * 1024:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        file_content = f.read()[:5000]  # First 5KB
                        except Exception as read_err:
                            print(f"⚠ Could not read file {file_path}: {read_err}")
                        
                        create_execution_event(
                            event_type="file_gen",
                            agent_name=agent,
                            event_subtype="created",
                            status="completed",
                            inputs={
                                "code_snippet": code[:500] if code else "",
                                "generation_context": f"Generated by {agent} during {language} execution"
                            },
                            outputs={
                                "file_path": file_path,
                                "file_content": file_content,
                                "file_size": file_size
                            },
                            meta={
                                "file_path": file_path, 
                                "source": "code_execution",
                                "language": language,
                                "has_content": file_content is not None
                            }
                        )
            except Exception as e:
                print(f"Error creating code_exec event: {e}")
                import traceback
                traceback.print_exc()
        
        def on_tool(agent, tool_name, arguments, result):
            print(f"🔧 [{agent}] Tool: {tool_name}")
            try:
                import re
                import os
                import json
                
                # Extract file information from tool results if present
                file_paths = []
                if result and isinstance(result, str):
                    # Look for file path patterns in results (multiple patterns)
                    file_matches = re.findall(
                        r'(?:saved to|written to|created file|file path|output file|generated|file:)\s*[:"`]?\s*([^\s,;\n"]+)',
                        result,
                        re.IGNORECASE
                    )
                    if file_matches:
                        file_paths = [f.strip('"\' ') for f in file_matches]
                
                # Serialize arguments safely
                args_str = "{}"
                args_dict = {}
                try:
                    if isinstance(arguments, dict):
                        args_dict = arguments
                        args_str = json.dumps(arguments, default=str)[:500]
                    else:
                        args_str = str(arguments)[:500]
                except:
                    args_str = str(arguments)[:500]
                
                # Track tool call with comprehensive metadata
                create_execution_event(
                    event_type="tool_call",
                    agent_name=agent,
                    event_subtype="invoked",
                    status="completed" if result else "failed",
                    inputs={
                        "tool": tool_name,
                        "args": args_str,
                        "args_keys": list(args_dict.keys()) if args_dict else []
                    },
                    outputs={
                        "result": str(result)[:2000] if result else None,
                        "result_preview": str(result)[:500] if result else None,
                        "files_generated": file_paths if file_paths else []
                    },
                    meta={
                        "tool_name": tool_name,
                        "has_files": len(file_paths) > 0,
                        "file_count": len(file_paths),
                        "result_length": len(str(result)) if result else 0
                    }
                )
                
                # If files were generated, track them with content
                if file_paths:
                    for file_path in file_paths:
                        # Try to read file content if it exists
                        file_content = None
                        file_size = None
                        file_ext = None
                        try:
                            if os.path.exists(file_path):
                                file_size = os.path.getsize(file_path)
                                file_ext = os.path.splitext(file_path)[1]
                                # Only read small text files
                                if file_size < 1024 * 1024 and file_ext in ['.py', '.txt', '.json', '.yaml', '.yml', '.md', '.csv']:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        file_content = f.read()[:5000]
                        except Exception as read_err:
                            print(f"⚠ Could not read file {file_path}: {read_err}")
                        
                        create_execution_event(
                            event_type="file_gen",
                            agent_name=agent,
                            event_subtype="created",
                            status="completed",
                            inputs={
                                "tool": tool_name,
                                "tool_args": args_str,
                                "generation_context": f"Generated by tool {tool_name} called by {agent}"
                            },
                            outputs={
                                "file_path": file_path,
                                "file_content": file_content,
                                "file_size": file_size,
                                "file_extension": file_ext
                            },
                            meta={
                                "file_path": file_path,
                                "source": "tool_call",
                                "tool": tool_name,
                                "has_content": file_content is not None,
                                "file_type": file_ext
                            }
                        )
            except Exception as e:
                print(f"Error creating tool_call event: {e}")
                import traceback
                traceback.print_exc()
        
        event_tracking_callbacks = WorkflowCallbacks(
            on_agent_message=on_agent_msg,
            on_code_execution=on_code_exec,
            on_tool_call=on_tool
        )
        
        # Add pause support to callbacks
        pause_callbacks = WorkflowCallbacks(
            should_continue=should_continue,
            on_pause_check=sync_pause_check
        )
        # Merge all callbacks
        workflow_callbacks = merge_callbacks(ws_callbacks, create_print_callbacks(), pause_callbacks, event_tracking_callbacks)
        
        def run_cmbagent():
            # Redirect stdout and stderr to our custom capture
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            
            # Create a custom stream wrapper that captures writes
            class StreamWrapper:
                def __init__(self, original, capture, loop):
                    self.original = original
                    self.capture = capture
                    self.loop = loop
                    
                def write(self, text):
                    # Write to original for debugging
                    if self.original:
                        self.original.write(text)
                    # Send to WebSocket
                    if text.strip():
                        asyncio.run_coroutine_threadsafe(
                            self.capture.write(text), self.loop
                        )
                    return len(text)
                
                def flush(self):
                    if self.original:
                        self.original.flush()
                
                def isatty(self):
                    return False
            
            try:
                # Redirect stdout and stderr
                sys.stdout = StreamWrapper(original_stdout, stream_capture, loop)
                sys.stderr = StreamWrapper(original_stderr, stream_capture, loop)
                
                # Also replace built-in print for good measure
                def custom_print(*args, **kwargs):
                    output = " ".join(str(arg) for arg in args)
                    # Run the async write in the event loop
                    asyncio.run_coroutine_threadsafe(
                        stream_capture.write(output + "\n"), loop
                    )
                    # Also print to original stdout for debugging
                    if original_stdout:
                        original_stdout.write(output + "\n")
                        original_stdout.flush()
                
                # Replace built-in print
                import builtins
                original_print = builtins.print
                builtins.print = custom_print

                # Set up custom AG2 IOStream to capture all agent events
                try:
                    from autogen.io.base import IOStream
                    ag2_iostream = AG2IOStreamCapture(websocket, task_id, loop)
                    IOStream.set_global_default(ag2_iostream)
                    print(f"[DEBUG] AG2 IOStream capture enabled for task {task_id}")
                except ImportError as e:
                    print(f"[DEBUG] Could not set AG2 IOStream: {e}")
                except Exception as e:
                    print(f"[DEBUG] Error setting AG2 IOStream: {e}")

                # Execute CMBAgent based on mode
                if mode == "planning-control":
                    results = cmbagent.planning_and_control_context_carryover(
                        task=task,
                        max_rounds_control=max_rounds,
                        max_n_attempts=max_attempts,
                        max_plan_steps=max_plan_steps,
                        n_plan_reviews=n_plan_reviews,
                        engineer_model=engineer_model,
                        researcher_model=researcher_model,
                        planner_model=planner_model,
                        plan_reviewer_model=plan_reviewer_model,
                        plan_instructions=plan_instructions if plan_instructions.strip() else None,
                        work_dir=task_work_dir,
                        api_keys=api_keys,
                        clear_work_dir=False,
                        default_formatter_model=default_formatter_model,
                        default_llm_model=default_llm_model,
                        callbacks=workflow_callbacks  # Re-enabled for testing with debug logs
                    )
                elif mode == "idea-generation":
                    # Idea Generation mode - uses planning_and_control_context_carryover with idea agents
                    results = cmbagent.planning_and_control_context_carryover(
                        task=task,
                        max_rounds_control=max_rounds,
                        max_n_attempts=max_attempts,
                        max_plan_steps=max_plan_steps,
                        n_plan_reviews=n_plan_reviews,
                        idea_maker_model=idea_maker_model,
                        idea_hater_model=idea_hater_model,
                        planner_model=planner_model,
                        plan_reviewer_model=plan_reviewer_model,
                        plan_instructions=plan_instructions if plan_instructions.strip() else None,
                        work_dir=task_work_dir,
                        api_keys=api_keys,
                        clear_work_dir=False,
                        default_formatter_model=default_formatter_model,
                        default_llm_model=default_llm_model,
                        callbacks=workflow_callbacks  # Use callbacks for DAG tracking
                    )
                elif mode == "ocr":
                    # OCR mode - process PDFs with Mistral OCR
                    import os
                    
                    # task should be the path to PDF file or folder
                    pdf_path = task.strip()
                    
                    # Expand user path if needed
                    if pdf_path.startswith("~"):
                        pdf_path = os.path.expanduser(pdf_path)
                    
                    # Check if path exists
                    if not os.path.exists(pdf_path):
                        raise ValueError(f"Path does not exist: {pdf_path}")
                    
                    # Use OCR output directory if specified, otherwise use default logic
                    output_dir = ocr_output_dir if ocr_output_dir and ocr_output_dir.strip() else None
                    
                    if os.path.isfile(pdf_path):
                        # Single PDF file
                        results = cmbagent.process_single_pdf(
                            pdf_path=pdf_path,
                            save_markdown=save_markdown,
                            save_json=save_json,
                            save_text=save_text,
                            output_dir=output_dir,
                            work_dir=task_work_dir
                        )
                    elif os.path.isdir(pdf_path):
                        # Folder containing PDFs
                        results = cmbagent.process_folder(
                            folder_path=pdf_path,
                            save_markdown=save_markdown,
                            save_json=save_json,
                            save_text=save_text,
                            output_dir=output_dir,
                            max_workers=max_workers,
                            work_dir=task_work_dir
                        )
                    else:
                        raise ValueError(f"Path is neither a file nor a directory: {pdf_path}")
                elif mode == "arxiv":
                    # arXiv Filter mode - scan text for arXiv URLs and download papers
                    results = cmbagent.arxiv_filter(
                        input_text=task,
                        work_dir=task_work_dir
                    )
                elif mode == "enhance-input":
                    # Enhance Input mode - enhance input text with contextual information
                    max_depth = config.get("maxDepth", 10)
                    results = cmbagent.preprocess_task(
                        text=task,
                        work_dir=task_work_dir,
                        max_workers=max_workers,
                        clear_work_dir=False
                    )
                else:
                    # One Shot mode
                    results = cmbagent.one_shot(
                        task=task,
                        max_rounds=max_rounds,
                        max_n_attempts=max_attempts,
                        engineer_model=engineer_model,
                        agent=agent,
                        work_dir=task_work_dir,
                        api_keys=api_keys,
                        clear_work_dir=False,
                        default_formatter_model=default_formatter_model,
                        default_llm_model=default_llm_model
                    )
                
                return results
                
            finally:
                # Restore original print and streams
                builtins.print = original_print
                sys.stdout = original_stdout
                sys.stderr = original_stderr
        
        # Run CMBAgent in executor to avoid blocking the event loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_cmbagent)
            
            # Wait for completion with periodic status updates and pause/cancel checks
            while not future.done():
                await asyncio.sleep(1)
                
                # Check if cancelled (Stage 3: State Machine)
                if SERVICES_AVAILABLE and execution_service.is_cancelled(task_id):
                    print(f"Task {task_id} cancelled, attempting to stop execution")
                    future.cancel()  # Try to cancel the future
                    await send_ws_event(websocket, "workflow_cancelled", {"message": "Workflow cancelled by user"}, run_id=task_id)
                    return
                
                # Check if paused (Stage 3: State Machine) - wait until resumed
                if SERVICES_AVAILABLE:
                    await execution_service.wait_if_paused(task_id)
                
                await send_ws_event(websocket, "heartbeat", {"timestamp": time.time()}, run_id=task_id)

            # Get the results
            results = future.result()

        execution_time = time.time() - start_time
        
        # Update DAG nodes to completed status and track files
        if dag_tracker and dag_tracker.node_statuses:
            for node_id in dag_tracker.node_statuses:
                if node_id != "terminator":
                    await dag_tracker.update_node_status(node_id, "completed")
                    # Track files generated for this node
                    dag_tracker.track_files_in_work_dir(task_work_dir, node_id)
            # Mark terminator as completed last
            if "terminator" in dag_tracker.node_statuses:
                await dag_tracker.update_node_status("terminator", "completed")

        # Mark workflow as completed in database
        if SERVICES_AVAILABLE:
            workflow_service.complete_workflow(task_id)

        # Send completion status
        await send_ws_event(websocket, "output", {"message": f"✅ Task completed in {execution_time:.2f} seconds"}, run_id=task_id)

        # Send final results
        await send_ws_event(websocket, "result", {
            "execution_time": execution_time,
            "chat_history": getattr(results, 'chat_history', []) if hasattr(results, 'chat_history') else [],
            "final_context": getattr(results, 'final_context', {}) if hasattr(results, 'final_context') else {},
            "work_dir": task_work_dir,
            "base_work_dir": work_dir,
            "mode": mode
        }, run_id=task_id)

        await send_ws_event(websocket, "complete", {"message": "Task execution completed successfully"}, run_id=task_id)

    except Exception as e:
        error_msg = f"Error executing CMBAgent task: {str(e)}"
        print(error_msg)

        # Update DAG nodes to failed status
        if dag_tracker and dag_tracker.node_statuses:
            for node_id in dag_tracker.node_statuses:
                await dag_tracker.update_node_status(node_id, "failed", error=error_msg)

        # Mark workflow as failed in database
        if SERVICES_AVAILABLE:
            workflow_service.fail_workflow(task_id, error_msg)

        await send_ws_event(websocket, "error", {"message": error_msg}, run_id=task_id)
