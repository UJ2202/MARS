"""
Stream capture classes for intercepting stdout/stderr and AG2 events.
"""

import asyncio
import re
import time
import os
import json
from io import StringIO
from typing import Any, Dict, Optional

from fastapi import WebSocket


class AG2IOStreamCapture:
    """
    Custom AG2 IOStream that intercepts all AG2 events and forwards them to WebSocket.
    This captures all agent messages, tool calls, function responses, etc.
    """

    def __init__(self, websocket: WebSocket, task_id: str, send_event_func, loop=None):
        self.websocket = websocket
        self.task_id = task_id
        self.send_event = send_event_func
        self.loop = loop or asyncio.get_event_loop()
        self._original_print = print

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
                self._original_print(f"Error in AG2IOStreamCapture.print: {e}")
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
                self._original_print(f"Error in AG2IOStreamCapture.send: {e}")
            try:
                message.print(self._original_print)
            except:
                pass
        except Exception as e:
            self._original_print(f"Error in AG2IOStreamCapture.send: {e}")
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
                run_id=self.task_id
            )
        except Exception as e:
            print(f"Error sending structured event to WebSocket: {e}")

    def input(self, prompt: str = "", *, password: bool = False) -> str:
        """Handle input requests - not typically used in autonomous mode"""
        return ""


class StreamCapture:
    """Capture stdout/stderr and send to WebSocket with DAG tracking"""

    def __init__(self, websocket: WebSocket, task_id: str, send_event_func,
                 dag_tracker=None, loop=None, work_dir=None, mode=None):
        self.websocket = websocket
        self.task_id = task_id
        self.send_event = send_event_func
        self.buffer = StringIO()
        self.dag_tracker = dag_tracker
        self.loop = loop
        self.work_dir = work_dir
        self.mode = mode  # Track workflow mode (e.g., "hitl-interactive")
        print(f"[StreamCapture] Initialized with mode={mode}")
        self.current_step = 0
        self.planning_complete = False
        self.plan_buffer = []
        self.collecting_plan = False
        self.steps_added = False
        self.total_cost = 0.0
        self.last_cost_report_time = 0

    async def write(self, text: str):
        """Write text to buffer and send to WebSocket"""
        if text.strip():
            try:
                await self.send_event(
                    self.websocket,
                    "output",
                    {"message": text.strip()},
                    run_id=self.task_id
                )

                if self.dag_tracker:
                    await self._detect_progress(text)

                await self._detect_cost_updates(text)
                await self._detect_agent_activity(text)

            except Exception as e:
                print(f"Error sending to WebSocket: {e}")

        self.buffer.write(text)
        return len(text)

    async def _detect_cost_updates(self, text: str):
        """Detect cost information from output and emit WebSocket events"""
        text_lower = text.lower()
        
        # Only process when we have actual cost report files (with complete data)
        # Don't send incomplete "unknown" model data from real-time detection
        if 'cost report data saved to:' in text_lower:
            await self._parse_cost_report(text)

    async def _parse_cost_report(self, text: str):
        """Parse cost report JSON file and emit detailed cost events"""
        match = re.search(r'cost report data saved to: (.+\.json)', text, re.IGNORECASE)
        if match:
            cost_file = match.group(1).strip()
            print(f"📄 Parsing cost report file: {cost_file}")
            if os.path.exists(cost_file):
                try:
                    with open(cost_file, 'r') as f:
                        cost_data = json.load(f)

                    print(f"📊 Cost report has {len(cost_data)} entries")
                    
                    # Reset total cost to recalculate from report (avoid accumulation issues)
                    report_total_cost = 0.0
                    
                    # Send individual cost events for each agent/model entry
                    for entry in cost_data:
                        if entry.get('Agent') != 'Total':
                            agent_name = entry.get('Agent', 'unknown')
                            model_name = entry.get('Model', 'unknown')
                            cost_str = str(entry.get('Cost ($)', '$0.0'))
                            cost_value = float(cost_str.replace('$', ''))
                            
                            # Get token counts
                            prompt_tokens = int(float(str(entry.get('Prompt Tokens', 0))))
                            completion_tokens = int(float(str(entry.get('Completion Tokens', 0))))
                            total_tokens = int(float(str(entry.get('Total Tokens', 0))))
                            
                            report_total_cost += cost_value
                            
                            print(f"  🔸 Agent: {agent_name}, Model: {model_name}, Cost: ${cost_value:.6f}, Tokens: {total_tokens}")
                            
                            # Send cost update for this agent/model
                            await self.send_event(
                                self.websocket,
                                "cost_update",
                                {
                                    "run_id": self.task_id,
                                    "step_id": f"{agent_name}_step",
                                    "model": model_name,
                                    "tokens": total_tokens,
                                    "input_tokens": prompt_tokens,
                                    "output_tokens": completion_tokens,
                                    "cost_usd": cost_value,
                                    "total_cost_usd": report_total_cost
                                },
                                run_id=self.task_id
                            )
                            
                            # Save cost to database
                            try:
                                from cmbagent.database import CostRepository, get_db_session
                                from cmbagent.database.models import WorkflowRun
                                
                                db = get_db_session()
                                if db:
                                    try:
                                        # Get session_id from workflow run
                                        run = db.query(WorkflowRun).filter(WorkflowRun.id == self.task_id).first()
                                        if run:
                                            cost_repo = CostRepository(db, run.session_id)
                                            cost_repo.record_cost(
                                                run_id=self.task_id,
                                                model=model_name,
                                                prompt_tokens=prompt_tokens,
                                                completion_tokens=completion_tokens,
                                                cost_usd=cost_value,
                                                step_id=f"{agent_name}_step"
                                            )
                                    finally:
                                        db.close()
                            except Exception as db_err:
                                print(f"  ⚠️  Failed to save cost to database: {db_err}")
                    
                    print(f"✅ Total cost from report: ${report_total_cost:.6f}")
                    # Update our tracked total to match the report
                    self.total_cost = report_total_cost

                except Exception as e:
                    print(f"❌ Error parsing cost report: {e}")
                    import traceback
                    traceback.print_exc()

    async def _detect_agent_activity(self, text: str):
        """Detect agent messages, code blocks, and tool calls"""
        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        # Detect agent transitions/handoffs
        transition_patterns = [
            r'replyresult\s+transition\s*\(([^)]+)\):\s*(\w+)',
            r'(\w+)\s*\(to\s+(\w+)\)',
            r'^(\w+_?(?:agent|response_formatter|executor|context)?)\s*:',
            r'next speaker:\s*(\w+)',
        ]

        for pattern in transition_patterns:
            match = re.search(pattern, text_stripped, re.IGNORECASE)
            if match:
                groups = match.groups()
                agent_name = groups[-1] if len(groups) > 0 else "unknown"
                await self.send_event(
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

        # Detect code blocks
        code_block_pattern = r'```(\w*)\n([\s\S]*?)```'
        code_matches = re.findall(code_block_pattern, text_stripped)
        for language, code in code_matches:
            if code.strip():
                await self.send_event(
                    self.websocket,
                    "code_execution",
                    {
                        "agent": "executor" if "executor" in text_lower else "engineer",
                        "code": code.strip()[:2000],
                        "language": language or "python",
                        "result": None
                    },
                    run_id=self.task_id
                )

        # Detect function/tool calls
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
                await self.send_event(
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

        # Detect execution results
        if "exitcode:" in text_lower or "execution result:" in text_lower:
            exitcode_match = re.search(r'exitcode:\s*(\d+)', text_lower)
            exitcode = exitcode_match.group(1) if exitcode_match else "unknown"
            await self.send_event(
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

        # Detect LLM API calls
        if any(phrase in text_lower for phrase in ['cost (', 'prompt tokens:', 'completion tokens:']):
            model_match = re.search(r'cost\s*\(([^)]+)\)', text_lower)
            model = model_match.group(1) if model_match else "unknown"
            await self.send_event(
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
        text_lower = text.lower()
        text_stripped = text.strip()

        # Detect when plan file is written
        if "structured plan written to" in text_lower or "final_plan.json" in text_lower:
            self.collecting_plan = False

            if hasattr(self, 'work_dir') and self.work_dir:
                plan_file = os.path.join(self.work_dir, "planning", "final_plan.json")
                if os.path.exists(plan_file):
                    try:
                        with open(plan_file, 'r') as f:
                            plan_data = json.load(f)

                        steps = []
                        for i, sub_task in enumerate(plan_data.get('sub_tasks', []), 1):
                            sub_task_desc = sub_task.get('sub_task', '')
                            bullet_points = sub_task.get('bullet_points', [])
                            agent = sub_task.get('sub_task_agent', 'engineer')

                            full_description = sub_task_desc
                            if bullet_points:
                                full_description += "\n\nInstructions:\n" + "\n".join(
                                    f"• {bp}" for bp in bullet_points
                                )

                            steps.append({
                                "title": f"Step {i}: {agent}",
                                "description": full_description[:500] if full_description else '',
                                "task": sub_task_desc,
                                "agent": agent,
                                "goal": sub_task_desc,
                                "insights": "\n".join(bullet_points) if bullet_points else '',
                                "bullet_points": bullet_points
                            })

                        if steps and not self.steps_added:
                            # For HITL modes, DON'T auto-complete planning from stream detection
                            # The callback system handles plan completion after human approval
                            if self.mode and "hitl" in self.mode.lower():
                                print(f"[StreamCapture] Skipping auto-complete for HITL mode: {self.mode}")
                            else:
                                if "planning" in self.dag_tracker.node_statuses:
                                    for node in self.dag_tracker.nodes:
                                        if node["id"] == "planning":
                                            node["generated_plan"] = {
                                                "sub_tasks": plan_data.get('sub_tasks', []),
                                                "step_count": len(steps),
                                                "mode": plan_data.get('mode', 'planning_control'),
                                                "breakdown": plan_data.get('sub_task_breakdown', '')
                                            }
                                            break

                                # Add step nodes first, then mark planning as completed
                                # This ensures the UI receives a single dag_updated event with all data
                                await self.dag_tracker.add_step_nodes(steps)
                                self.steps_added = True
                                self.planning_complete = True

                                # Now mark planning as completed (this sends dag_updated with all nodes + plan data)
                                if "planning" in self.dag_tracker.node_statuses:
                                    await self.dag_tracker.update_node_status("planning", "completed")

                                first_exec = self.dag_tracker.get_node_by_step(1)
                                if first_exec:
                                    await self.dag_tracker.update_node_status(first_exec, "running")
                                    self.current_step = 1
                    except Exception as e:
                        print(f"Error reading plan file: {e}")

        # Detect start of plan output
        if any(phrase in text_lower for phrase in [
            "plan:", "execution plan:", "here is the plan", "generated plan"
        ]):
            self.collecting_plan = True
            self.plan_buffer = []

        # Collect plan lines
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
        # For HITL modes, skip this - callback system handles it after human approval
        if self.mode and "hitl" in self.mode.lower():
            # For HITL, don't auto-detect execution start from stream
            pass
        elif not self.steps_added and any(phrase in text_lower for phrase in [
            "executing step", "starting step 1", "running step 1", "beginning execution",
            "step 1 of", "executing plan", "control_starter", "transition (control)",
            "replyresult transition (control):", "control): engineer"
        ]):
            # Add generated_plan data to planning node
            if "planning" in self.dag_tracker.node_statuses:
                if self.plan_buffer:
                    for node in self.dag_tracker.nodes:
                        if node["id"] == "planning":
                            node["generated_plan"] = {
                                "steps": self.plan_buffer,
                                "step_count": len(self.plan_buffer)
                            }
                            break

            # Add step nodes first, then update planning status
            if self.plan_buffer and self.dag_tracker.mode in ["planning-control", "idea-generation"]:
                await self.dag_tracker.add_step_nodes(self.plan_buffer)
                self.steps_added = True
            elif self.dag_tracker.mode in ["planning-control", "idea-generation"] and not self.plan_buffer:
                default_steps = [{"title": "Step 1", "description": "Execute task", "task": ""}]
                await self.dag_tracker.add_step_nodes(default_steps)
                self.steps_added = True

            self.planning_complete = True
            self.collecting_plan = False

            # Mark planning as completed after adding all step nodes
            if "planning" in self.dag_tracker.node_statuses:
                await self.dag_tracker.update_node_status("planning", "completed")

            first_exec = self.dag_tracker.get_node_by_step(1)
            if first_exec:
                await self.dag_tracker.update_node_status(first_exec, "running")

        # Detect step transitions
        if "control_starter" in text_lower or ("timing_report_step_" in text_lower):
            step_timing_match = re.search(r'timing_report_step_(\d+)', text_lower)
            if step_timing_match:
                completed_step = int(step_timing_match.group(1))
                node_id = self.dag_tracker.get_node_by_step(completed_step)
                if node_id:
                    await self.dag_tracker.update_node_status(
                        node_id, "completed", work_dir=self.work_dir
                    )
                    next_node = self.dag_tracker.get_node_by_step(completed_step + 1)
                    if next_node:
                        await self.dag_tracker.update_node_status(next_node, "running")
                    self.current_step = completed_step + 1

        # Detect step transitions (Step 1, Step 2, etc.)
        step_match = re.search(r'(?:executing|running|starting|completed)\s*(?:step\s*)?(\d+)', text_lower)
        if step_match and self.planning_complete:
            step_num = int(step_match.group(1))
            if step_num > self.current_step:
                if self.current_step > 0:
                    prev_node = self.dag_tracker.get_node_by_step(self.current_step)
                    if prev_node:
                        await self.dag_tracker.update_node_status(
                            prev_node, "completed", work_dir=self.work_dir
                        )

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
                    await self.dag_tracker.update_node_status(
                        node_id, "completed", work_dir=self.work_dir
                    )

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
