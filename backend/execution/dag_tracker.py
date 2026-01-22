"""
DAG Tracker for workflow visualization and state management.
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import WebSocket


class DAGTracker:
    """Track DAG state and emit events for UI visualization using database."""

    def __init__(self, websocket: WebSocket, task_id: str, mode: str,
                 send_event_func, run_id: str = None):
        self.websocket = websocket
        self.task_id = task_id
        self.mode = mode
        self.send_event = send_event_func
        self.nodes = []
        self.edges = []
        self.current_step = 0
        self.node_statuses = {}
        self.db_session = None
        self.dag_builder = None
        self.dag_visualizer = None
        self.run_id = run_id
        self.session_id = None
        self.event_repo = None
        self.node_event_map = {}
        self.execution_order_counter = 0

        # Try to initialize database connection
        try:
            from cmbagent.database import get_db_session as get_session, init_database
            from cmbagent.database.dag_builder import DAGBuilder
            from cmbagent.database.dag_visualizer import DAGVisualizer
            from cmbagent.database.repository import WorkflowRepository, EventRepository
            from cmbagent.database.session_manager import SessionManager

            init_database()
            self.db_session = get_session()

            session_manager = SessionManager(self.db_session)
            self.session_id = session_manager.get_or_create_default_session()

            self.workflow_repo = WorkflowRepository(self.db_session, self.session_id)
            self.event_repo = EventRepository(self.db_session, self.session_id)

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

    def create_dag_for_mode(self, task: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create initial DAG structure based on execution mode."""
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
        """Create initial DAG for planning-control mode."""
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
        self.edges = []

        for node in self.nodes:
            self.node_statuses[node["id"]] = "pending"

        return {"nodes": self.nodes, "edges": self.edges, "levels": 1}

    def _create_idea_generation_dag(self, task: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create DAG for idea-generation mode."""
        self.nodes = [
            {"id": "planning", "label": "Plan Generation", "type": "planning",
             "agent": "planner", "status": "pending", "step_number": 0},
            {"id": "idea_maker_1", "label": "Generate Ideas", "type": "agent",
             "agent": "idea_maker", "status": "pending", "step_number": 1},
            {"id": "idea_hater_1", "label": "Critique Ideas", "type": "agent",
             "agent": "idea_hater", "status": "pending", "step_number": 2},
            {"id": "idea_maker_2", "label": "Refine Ideas", "type": "agent",
             "agent": "idea_maker", "status": "pending", "step_number": 3},
            {"id": "idea_hater_2", "label": "Final Critique", "type": "agent",
             "agent": "idea_hater", "status": "pending", "step_number": 4},
            {"id": "idea_maker_3", "label": "Select Best Idea", "type": "agent",
             "agent": "idea_maker", "status": "pending", "step_number": 5},
            {"id": "terminator", "label": "Completion", "type": "terminator",
             "agent": "system", "status": "pending", "step_number": 6},
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
        """Create DAG for one-shot mode."""
        agent = config.get("agent", "engineer")
        self.nodes = [
            {"id": "init", "label": "Initialize", "type": "planning",
             "status": "pending", "step_number": 0, "description": "Initialize agent"},
            {"id": "execute", "label": f"Execute ({agent})", "type": "agent",
             "agent": agent, "status": "pending", "step_number": 1, "description": "Execute task"},
            {"id": "terminator", "label": "Completion", "type": "terminator",
             "agent": "system", "status": "pending", "step_number": 2},
        ]
        self.edges = [
            {"source": "init", "target": "execute"},
            {"source": "execute", "target": "terminator"},
        ]
        for node in self.nodes:
            self.node_statuses[node["id"]] = "pending"

        self._persist_dag_nodes_to_db()

        return {"nodes": self.nodes, "edges": self.edges, "levels": 3}

    def _create_ocr_dag(self, task: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create DAG for OCR mode."""
        self.nodes = [
            {"id": "init", "label": "Initialize OCR", "type": "planning",
             "status": "pending", "step_number": 0},
            {"id": "process", "label": "Process PDFs", "type": "agent",
             "agent": "ocr", "status": "pending", "step_number": 1},
            {"id": "output", "label": "Save Output", "type": "agent",
             "agent": "ocr", "status": "pending", "step_number": 2},
            {"id": "terminator", "label": "Completion", "type": "terminator",
             "agent": "system", "status": "pending", "step_number": 3},
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
        """Create DAG for arXiv filter mode."""
        self.nodes = [
            {"id": "init", "label": "Parse Text", "type": "planning",
             "status": "pending", "step_number": 0},
            {"id": "filter", "label": "Filter arXiv URLs", "type": "agent",
             "agent": "arxiv", "status": "pending", "step_number": 1},
            {"id": "download", "label": "Download Papers", "type": "agent",
             "agent": "arxiv", "status": "pending", "step_number": 2},
            {"id": "terminator", "label": "Completion", "type": "terminator",
             "agent": "system", "status": "pending", "step_number": 3},
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
        """Create DAG for enhance-input mode."""
        self.nodes = [
            {"id": "init", "label": "Initialize", "type": "planning",
             "status": "pending", "step_number": 0},
            {"id": "enhance", "label": "Enhance Input", "type": "agent",
             "agent": "enhancer", "status": "pending", "step_number": 1},
            {"id": "terminator", "label": "Completion", "type": "terminator",
             "agent": "system", "status": "pending", "step_number": 2},
        ]
        self.edges = [
            {"source": "init", "target": "enhance"},
            {"source": "enhance", "target": "terminator"},
        ]
        for node in self.nodes:
            self.node_statuses[node["id"]] = "pending"
        return {"nodes": self.nodes, "edges": self.edges, "levels": 3}

    def _persist_dag_nodes_to_db(self):
        """Persist DAG nodes to database to satisfy foreign key constraints."""
        if not self.db_session or not self.run_id:
            return

        try:
            from cmbagent.database.models import DAGNode, DAGEdge

            for idx, node in enumerate(self.nodes):
                existing_node = self.db_session.query(DAGNode).filter(
                    DAGNode.id == node["id"]
                ).first()

                if not existing_node:
                    dag_node = DAGNode(
                        id=node["id"],
                        run_id=self.run_id,
                        session_id=self.session_id,
                        node_type=node.get("type", "agent"),
                        agent=node.get("agent", "unknown"),
                        status="pending",
                        order_index=node.get("step_number", idx),
                        meta=node
                    )
                    self.db_session.add(dag_node)

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

    async def add_step_nodes(self, steps: list):
        """Dynamically add step nodes after planning completes."""
        for i, step_info in enumerate(steps, 1):
            step_id = f"step_{i}"
            if isinstance(step_info, dict):
                description = step_info.get("description", "")
                task = step_info.get("task", "")
                agent = step_info.get("agent", "engineer")
                insights = step_info.get("insights", "")
                goal = step_info.get("goal", "")
                summary = step_info.get("summary", "")
                bullet_points = step_info.get("bullet_points", [])

                label_source = goal or task or description
                if label_source:
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

        # Create edges
        self.edges = [{"source": "planning", "target": "step_1"}]
        for i in range(1, len(steps)):
            self.edges.append({"source": f"step_{i}", "target": f"step_{i+1}"})
        self.edges.append({"source": f"step_{len(steps)}", "target": "terminator"})

        # Emit dag_updated event
        try:
            effective_run_id = self.run_id or self.task_id
            await self.send_event(
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

    async def emit_dag_created(self):
        """Emit DAG created event."""
        effective_run_id = self.run_id or self.task_id
        try:
            await self.send_event(
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

    async def update_node_status(self, node_id: str, new_status: str,
                                  error: str = None, work_dir: str = None):
        """Update a node's status and emit event."""
        old_status = self.node_statuses.get(node_id, "pending")
        self.node_statuses[node_id] = new_status
        effective_run_id = self.run_id or self.task_id

        node_info = None
        for node in self.nodes:
            if node["id"] == node_id:
                node["status"] = new_status
                if error:
                    node["error"] = error
                node_info = node
                break

        if new_status == "completed" and work_dir:
            self.track_files_in_work_dir(work_dir, node_id)

        # Create ExecutionEvent in database
        if self.event_repo and node_info:
            try:
                self._persist_dag_nodes_to_db()

                agent_name = node_info.get("agent", "unknown")

                if new_status == "running":
                    self.execution_order_counter += 1
                    event = self.event_repo.create_event(
                        run_id=self.run_id,
                        node_id=node_id,
                        event_type="agent_call",
                        execution_order=self.execution_order_counter,
                        event_subtype="execution",
                        agent_name=agent_name,
                        status="running",
                        started_at=datetime.now(timezone.utc),
                        inputs={"node_info": node_info},
                        meta={"old_status": old_status, "new_status": new_status}
                    )
                    self.node_event_map[node_id] = event.id

                elif new_status in ["completed", "error"]:
                    event_id = self.node_event_map.get(node_id)
                    if event_id:
                        completed_at = datetime.now(timezone.utc)
                        started_at_event = self.event_repo.get_event(event_id)
                        duration_ms = None
                        if started_at_event and started_at_event.started_at:
                            started_at = started_at_event.started_at
                            if started_at.tzinfo is None:
                                started_at = started_at.replace(tzinfo=timezone.utc)
                            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

                        self.event_repo.update_event(
                            event_id=event_id,
                            completed_at=completed_at,
                            duration_ms=duration_ms,
                            outputs={"status": new_status},
                            error_message=error,
                            status="completed" if new_status == "completed" else "failed"
                        )
                    else:
                        self.execution_order_counter += 1
                        self.event_repo.create_event(
                            run_id=self.run_id,
                            node_id=node_id,
                            event_type="agent_call",
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

            except Exception as e:
                print(f"Error creating ExecutionEvent for node {node_id}: {e}")
                import traceback
                traceback.print_exc()
                if self.db_session:
                    self.db_session.rollback()

        # Send WebSocket event
        try:
            data = {
                "node_id": node_id,
                "old_status": old_status,
                "new_status": new_status,
                "node": node_info
            }
            if error:
                data["error"] = error
            await self.send_event(
                self.websocket,
                "dag_node_status_changed",
                data,
                run_id=effective_run_id
            )

            await self.send_event(
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
        """Get node ID by step number."""
        for node in self.nodes:
            if node.get("step_number") == step_number:
                return node["id"]
        return None

    def get_first_node(self) -> Optional[str]:
        """Get the first node ID."""
        if self.nodes:
            return self.nodes[0]["id"]
        return None

    def get_last_node(self) -> Optional[str]:
        """Get the last node ID (terminator)."""
        for node in self.nodes:
            if node.get("type") == "terminator":
                return node["id"]
        return None

    def track_files_in_work_dir(self, work_dir: str, node_id: str = None, step_id: str = None):
        """Scan work directory and track generated files in the database."""
        if not self.db_session or not self.run_id:
            return

        try:
            from cmbagent.database.models import File, WorkflowStep

            event_id = self.node_event_map.get(node_id) if node_id else None

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

            # Extended directory list to track all output locations
            output_dirs = [
                "data", "codebase", "outputs", "chats", "cost", "time",
                "planning", "control", "context", "docs", "summaries", "runs"
            ]
            files_tracked = 0

            if not os.path.exists(work_dir):
                return 0

            for output_dir_name in output_dirs:
                output_dir = os.path.join(work_dir, output_dir_name)
                if not os.path.exists(output_dir):
                    continue

                for root, dirs, files in os.walk(output_dir):
                    # Skip hidden and cache directories
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']

                    for filename in files:
                        # Skip hidden files
                        if filename.startswith('.'):
                            continue

                        file_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(file_path, work_dir)

                        existing_file = self.db_session.query(File).filter(
                            File.file_path == file_path,
                            File.run_id == self.run_id
                        ).first()

                        if existing_file:
                            if not existing_file.node_id and node_id:
                                existing_file.node_id = node_id
                            if not existing_file.step_id and db_step_id:
                                existing_file.step_id = db_step_id
                            continue

                        # Classify file by extension and path
                        file_ext = os.path.splitext(filename)[1].lower()
                        rel_parts = rel_path.lower().split(os.sep)

                        # Explicit pattern matching first
                        if filename == 'final_plan.json' or filename.endswith('_plan.json'):
                            file_type = "plan"
                        elif filename.startswith('timing_report') or filename.startswith('cost_report'):
                            file_type = "report"
                        # Directory-based classification
                        elif 'codebase' in rel_parts:
                            file_type = "code"
                        elif 'chats' in rel_parts:
                            file_type = "chat"
                        elif 'context' in rel_parts:
                            file_type = "context"
                        elif 'time' in rel_parts or 'cost' in rel_parts:
                            file_type = "report"
                        elif 'planning' in rel_parts and file_ext == '.json':
                            file_type = "plan"
                        # Extension-based classification
                        elif file_ext in [".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".rb", ".sh"]:
                            file_type = "code"
                        elif file_ext in [".csv", ".json", ".pkl", ".pickle", ".npz", ".npy", ".parquet", ".yaml", ".yml", ".h5", ".hdf5", ".fits"]:
                            file_type = "data"
                        elif file_ext in [".png", ".jpg", ".jpeg", ".gif", ".pdf", ".svg", ".eps", ".bmp", ".tiff"]:
                            file_type = "plot"
                        elif file_ext in [".txt", ".md", ".rst", ".html"]:
                            file_type = "report"
                        elif file_ext in [".log"]:
                            file_type = "log"
                        else:
                            file_type = "other"

                        # Determine workflow phase from path
                        workflow_phase = None
                        if 'planning' in rel_parts:
                            workflow_phase = "planning"
                        elif 'control' in rel_parts:
                            workflow_phase = "control"
                        else:
                            workflow_phase = "execution"

                        # Determine if this is a final output (primary deliverable)
                        is_final_output = file_type in ["plot", "data", "code", "plan"]
                        if 'context' in rel_parts or 'temp' in rel_parts:
                            is_final_output = False

                        # Determine priority
                        if is_final_output:
                            priority = "primary"
                        elif file_type in ["report", "chat"]:
                            priority = "secondary"
                        else:
                            priority = "internal"

                        try:
                            file_size = os.path.getsize(file_path)
                        except:
                            file_size = 0

                        file_record = File(
                            run_id=self.run_id,
                            event_id=event_id,
                            node_id=node_id,
                            step_id=db_step_id,
                            file_path=file_path,
                            file_type=file_type,
                            size_bytes=file_size,
                            workflow_phase=workflow_phase,
                            is_final_output=is_final_output,
                            priority=priority
                        )
                        self.db_session.add(file_record)
                        files_tracked += 1

            self.db_session.commit()
            if files_tracked > 0:
                print(f"[DAGTracker] Tracked {files_tracked} new files")

                try:
                    effective_run_id = self.run_id or self.task_id
                    asyncio.create_task(self.send_event(
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

    async def build_dag_from_plan(self, plan_output: Dict[str, Any]):
        """Build DAG in database from plan output after planning phase completes."""
        if not self.dag_builder or not self.run_id:
            print("Database not available, using in-memory DAG")
            return await self._build_inmemory_dag_from_plan(plan_output)

        try:
            import re

            number_of_steps = plan_output.get('number_of_steps_in_plan', 0)
            final_plan = plan_output.get('final_plan', '')

            steps = []
            if isinstance(final_plan, str):
                step_matches = re.findall(
                    r'(?:Step\s*)?(\d+)[.:]\s*(.+?)(?=(?:Step\s*)?\d+[.:]|$)',
                    final_plan, re.IGNORECASE | re.DOTALL
                )
                for step_num, step_desc in step_matches:
                    steps.append({
                        "task": step_desc.strip(),
                        "agent": "engineer",
                        "depends_on": [f"step_{int(step_num)-1}"] if int(step_num) > 1 else ["planning"]
                    })

            if not steps and number_of_steps > 0:
                for i in range(number_of_steps):
                    steps.append({
                        "task": f"Execute step {i+1}",
                        "agent": "engineer",
                        "depends_on": [f"step_{i-1}"] if i > 0 else ["planning"]
                    })

            plan_dict = {"steps": steps}

            dag_nodes = self.dag_builder.build_from_plan(self.run_id, plan_dict)
            dag_export = self.dag_visualizer.export_for_ui(self.run_id)

            self.nodes = dag_export.get("nodes", [])
            self.edges = dag_export.get("edges", [])
            for node in self.nodes:
                self.node_statuses[node["id"]] = node.get("status", "pending")

            effective_run_id = self.run_id or self.task_id
            await self.send_event(
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
        """Fallback: Build in-memory DAG from plan output."""
        import re

        number_of_steps = plan_output.get('number_of_steps_in_plan', 1)
        final_plan = plan_output.get('final_plan', '')

        steps = []
        if isinstance(final_plan, str):
            step_matches = re.findall(
                r'(?:Step\s*)?(\d+)[.:]\s*(.+?)(?=(?:Step\s*)?\d+[.:]|$)',
                final_plan, re.IGNORECASE | re.DOTALL
            )
            for step_num, step_desc in step_matches:
                steps.append({
                    "title": f"Step {step_num}",
                    "description": step_desc.strip()[:200],
                    "task": step_desc.strip()
                })

        if not steps:
            for i in range(1, number_of_steps + 1):
                steps.append({
                    "title": f"Step {i}",
                    "description": f"Execute step {i}",
                    "task": f"Step {i}"
                })

        await self.add_step_nodes(steps)

        return {"nodes": self.nodes, "edges": self.edges, "levels": len(steps) + 2}
