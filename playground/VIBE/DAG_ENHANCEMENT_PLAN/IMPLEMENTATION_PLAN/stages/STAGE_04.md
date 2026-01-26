# Stage 4: DAG Builder and Storage

**Phase:** 1 - Planning and Control Enhancement
**Estimated Time:** 35-45 minutes
**Dependencies:** Stage 3 (State Machine) must be complete
**Risk Level:** High

## Objectives

1. Parse planning output into directed acyclic graph (DAG) structure
2. Store DAG nodes and edges in database
3. Implement topological sort for execution order
4. Support parallel execution groups (nodes with no dependencies)
5. Create DAG executor with dependency resolution
6. Add DAG visualization data export for UI

## Current State Analysis

### What We Have
- Sequential execution only (Step 1 → Step 2 → Step 3)
- Plans as JSON text in final_plan.json
- No dependency tracking
- No parallel execution capability
- Control agent manually sequences steps

### What We Need
- DAG representation of workflow plan
- Database storage of nodes and edges
- Automatic dependency resolution
- Parallel execution support
- Execution order from topological sort
- DAG data for UI visualization

## Pre-Stage Verification

### Check Prerequisites
1. Stage 3 complete and verified
2. State machine working correctly
3. Database models for dag_nodes and dag_edges exist
4. Can create and transition workflow_steps
5. State transitions logged properly

### Expected State
- State machine enforcing valid transitions
- Workflow runs tracked in database
- Ready to add graph-based execution
- No breaking changes to current workflows

## Implementation Tasks

### Task 1: Design DAG Node Types
**Objective:** Define node types and their properties

**Implementation:**

Create node type enum:
```python
from enum import Enum

class DAGNodeType(str, Enum):
    """Types of nodes in execution DAG"""
    PLANNING = "planning"           # Initial planning step
    CONTROL = "control"             # Orchestration logic
    AGENT = "agent"                 # Agent execution (engineer, researcher, etc.)
    APPROVAL = "approval"           # Human approval gate
    PARALLEL_GROUP = "parallel_group"  # Container for parallel tasks
    TERMINATOR = "terminator"       # End of workflow
```

Define node metadata structure:
```python
class DAGNodeMetadata:
    """Metadata for DAG nodes"""
    agent: Optional[str]           # Agent to execute (for AGENT nodes)
    task_description: Optional[str]  # Task for this node
    depends_on: List[str]          # List of node IDs this depends on
    parallel_group: Optional[str]  # Group ID for parallel execution
    approval_required: bool        # Whether approval needed
    retry_config: dict             # Retry settings
    estimated_duration: Optional[int]  # Estimated time in seconds
```

**Files to Create:**
- `cmbagent/database/dag_types.py`

**Verification:**
- Node types cover all workflow scenarios
- Metadata structure comprehensive
- Can serialize to JSONB for database storage

### Task 2: Implement DAG Builder
**Objective:** Parse plan JSON into DAG structure

**Implementation:**

```python
from typing import List, Dict, Set
from cmbagent.database.models import DAGNode, DAGEdge
from cmbagent.database.dag_types import DAGNodeType

class DAGBuilder:
    """Builds DAG from planning output"""

    def __init__(self, db_session, session_id):
        self.db = db_session
        self.session_id = session_id

    def build_from_plan(self, run_id: str, plan: dict) -> Dict[str, DAGNode]:
        """
        Build DAG from plan JSON

        Args:
            run_id: Workflow run ID
            plan: Plan dictionary from planner agent

        Returns:
            Dictionary of node_id -> DAGNode
        """
        nodes = {}
        edges = []

        # Create planning node
        planning_node = self._create_node(
            run_id=run_id,
            node_type=DAGNodeType.PLANNING,
            order_index=0,
            metadata={"phase": "planning"}
        )
        nodes["planning"] = planning_node

        # Parse plan steps
        steps = plan.get("steps", [])
        previous_node_id = "planning"

        for idx, step in enumerate(steps):
            # Determine if parallel execution
            is_parallel = step.get("parallel", False)
            depends_on = step.get("depends_on", [previous_node_id])

            # Create agent node
            node_id = f"step_{idx}"
            agent_node = self._create_node(
                run_id=run_id,
                node_type=DAGNodeType.AGENT,
                agent=step.get("agent", "engineer"),
                order_index=idx + 1,
                metadata={
                    "task": step.get("task"),
                    "depends_on": depends_on,
                    "parallel_group": step.get("parallel_group"),
                    "approval_required": step.get("approval_required", False)
                }
            )
            nodes[node_id] = agent_node

            # Create edges from dependencies
            for dep_id in depends_on:
                if dep_id in nodes:
                    edge = self._create_edge(
                        from_node_id=nodes[dep_id].id,
                        to_node_id=agent_node.id,
                        dependency_type="sequential" if not is_parallel else "parallel"
                    )
                    edges.append(edge)

            # Update previous for sequential steps
            if not is_parallel:
                previous_node_id = node_id

        # Create terminator node
        terminator = self._create_node(
            run_id=run_id,
            node_type=DAGNodeType.TERMINATOR,
            order_index=len(steps) + 1,
            metadata={"phase": "completion"}
        )
        nodes["terminator"] = terminator

        # Connect last step(s) to terminator
        for node_id, node in nodes.items():
            if node.node_type == DAGNodeType.AGENT:
                # Check if this node has no outgoing edges
                has_outgoing = any(
                    e.from_node_id == node.id for e in edges
                )
                if not has_outgoing:
                    edge = self._create_edge(
                        from_node_id=node.id,
                        to_node_id=terminator.id,
                        dependency_type="sequential"
                    )
                    edges.append(edge)

        # Commit to database
        self.db.commit()

        return nodes

    def _create_node(self, run_id: str, node_type: str, order_index: int,
                     agent: str = None, metadata: dict = None) -> DAGNode:
        """Create and persist DAG node"""
        node = DAGNode(
            run_id=run_id,
            session_id=self.session_id,
            node_type=node_type,
            agent=agent,
            status="pending",
            order_index=order_index,
            metadata=metadata or {}
        )
        self.db.add(node)
        self.db.flush()  # Get ID without committing
        return node

    def _create_edge(self, from_node_id: str, to_node_id: str,
                     dependency_type: str) -> DAGEdge:
        """Create and persist DAG edge"""
        edge = DAGEdge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            dependency_type=dependency_type
        )
        self.db.add(edge)
        self.db.flush()
        return edge

    def validate_dag(self, nodes: Dict[str, DAGNode]) -> bool:
        """
        Validate DAG is acyclic

        Returns:
            True if valid DAG, False if cycles detected
        """
        # Build adjacency list
        graph = {}
        for node_id, node in nodes.items():
            graph[node.id] = []

        edges = self.db.query(DAGEdge).filter(
            DAGEdge.from_node_id.in_([n.id for n in nodes.values()])
        ).all()

        for edge in edges:
            graph[edge.from_node_id].append(edge.to_node_id)

        # Detect cycles using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(node_id):
            visited.add(node_id)
            rec_stack.add(node_id)

            for neighbor in graph.get(node_id, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node_id)
            return False

        for node_id in graph:
            if node_id not in visited:
                if has_cycle(node_id):
                    return False

        return True
```

**Files to Create:**
- `cmbagent/database/dag_builder.py`

**Verification:**
- Can parse plan JSON to DAG
- Nodes created in database
- Edges created in database
- DAG validation detects cycles
- Handles sequential dependencies
- Handles parallel groups

### Task 3: Implement Topological Sort
**Objective:** Determine execution order respecting dependencies

**Implementation:**

```python
from collections import defaultdict, deque
from typing import List, Set, Dict

class TopologicalSorter:
    """Computes execution order for DAG"""

    def __init__(self, db_session):
        self.db = db_session

    def sort(self, run_id: str) -> List[List[str]]:
        """
        Topological sort returning execution levels

        Args:
            run_id: Workflow run ID

        Returns:
            List of lists - each inner list is a level that can execute in parallel
            Example: [["planning"], ["step_1", "step_2"], ["step_3"], ["terminator"]]
        """
        # Load nodes and edges
        nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id
        ).all()

        edges = self.db.query(DAGEdge).join(
            DAGNode, DAGEdge.from_node_id == DAGNode.id
        ).filter(
            DAGNode.run_id == run_id
        ).all()

        # Build adjacency list and in-degree map
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        node_map = {node.id: node for node in nodes}

        for node in nodes:
            in_degree[node.id] = 0

        for edge in edges:
            graph[edge.from_node_id].append(edge.to_node_id)
            in_degree[edge.to_node_id] += 1

        # Kahn's algorithm for topological sort by levels
        levels = []
        queue = deque([node_id for node_id in in_degree if in_degree[node_id] == 0])

        while queue:
            # All nodes in queue have no dependencies - can execute in parallel
            current_level = []
            level_size = len(queue)

            for _ in range(level_size):
                node_id = queue.popleft()
                current_level.append(node_id)

                # Reduce in-degree for neighbors
                for neighbor_id in graph[node_id]:
                    in_degree[neighbor_id] -= 1
                    if in_degree[neighbor_id] == 0:
                        queue.append(neighbor_id)

            levels.append(current_level)

        # Verify all nodes processed (no cycles)
        total_processed = sum(len(level) for level in levels)
        if total_processed != len(nodes):
            raise ValueError("Cycle detected in DAG - cannot sort")

        return levels

    def get_execution_order(self, run_id: str) -> List[Dict]:
        """
        Get execution order with node details

        Returns:
            List of execution levels with node metadata
        """
        levels = self.sort(run_id)
        node_map = {
            node.id: node for node in self.db.query(DAGNode).filter(
                DAGNode.run_id == run_id
            ).all()
        }

        execution_order = []
        for level_idx, level in enumerate(levels):
            level_info = {
                "level": level_idx,
                "nodes": [
                    {
                        "id": node_id,
                        "type": node_map[node_id].node_type,
                        "agent": node_map[node_id].agent,
                        "metadata": node_map[node_id].metadata
                    }
                    for node_id in level
                ],
                "parallel": len(level) > 1
            }
            execution_order.append(level_info)

        return execution_order
```

**Files to Create:**
- `cmbagent/database/topological_sort.py`

**Verification:**
- Correctly computes execution levels
- Handles parallel execution groups
- Detects cycles and raises error
- Returns node details with execution order
- Works with complex DAGs

### Task 4: Create DAG Executor
**Objective:** Execute DAG respecting dependencies and parallel groups

**Implementation:**

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
from cmbagent.database.topological_sort import TopologicalSorter
from cmbagent.database.state_machine import StateMachine
from cmbagent.database.states import StepState

class DAGExecutor:
    """Executes workflow DAG with parallel execution support"""

    def __init__(self, db_session, session_id, max_parallel: int = 3):
        self.db = db_session
        self.session_id = session_id
        self.max_parallel = max_parallel
        self.sorter = TopologicalSorter(db_session)
        self.step_sm = StateMachine(db_session, "workflow_step")

    def execute(self, run_id: str, agent_executor_func):
        """
        Execute DAG for workflow run

        Args:
            run_id: Workflow run ID
            agent_executor_func: Function to execute agent nodes
                                 Signature: func(node_id, agent, task) -> result
        """
        # Get execution order
        execution_order = self.sorter.get_execution_order(run_id)

        # Execute level by level
        for level_info in execution_order:
            level_nodes = level_info["nodes"]
            is_parallel = level_info["parallel"]

            if is_parallel and len(level_nodes) <= self.max_parallel:
                # Execute nodes in parallel
                self._execute_parallel(level_nodes, agent_executor_func)
            else:
                # Execute nodes sequentially
                self._execute_sequential(level_nodes, agent_executor_func)

    def _execute_sequential(self, nodes: List[Dict], agent_executor_func):
        """Execute nodes one at a time"""
        for node_info in nodes:
            self._execute_node(node_info, agent_executor_func)

    def _execute_parallel(self, nodes: List[Dict], agent_executor_func):
        """Execute nodes in parallel using thread pool"""
        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            futures = [
                executor.submit(self._execute_node, node_info, agent_executor_func)
                for node_info in nodes
            ]

            # Wait for all to complete
            for future in futures:
                future.result()  # Raises exception if node failed

    def _execute_node(self, node_info: Dict, agent_executor_func):
        """Execute single DAG node"""
        node_id = node_info["id"]
        node_type = node_info["type"]

        # Skip planning and terminator nodes
        if node_type in ["planning", "terminator"]:
            return

        # For AGENT nodes, execute via agent
        if node_type == "agent":
            # Create workflow_step
            step = self._create_step_for_node(node_id, node_info)

            # Transition to RUNNING
            self.step_sm.transition_to(
                step.id,
                StepState.RUNNING,
                reason=f"Executing DAG node {node_id}"
            )

            try:
                # Execute agent
                agent = node_info["agent"]
                task = node_info["metadata"].get("task")
                result = agent_executor_func(node_id, agent, task)

                # Store result
                step.outputs = result
                self.db.commit()

                # Transition to COMPLETED
                self.step_sm.transition_to(
                    step.id,
                    StepState.COMPLETED,
                    reason="Node execution successful"
                )

            except Exception as e:
                # Transition to FAILED
                step.error_message = str(e)
                self.db.commit()

                self.step_sm.transition_to(
                    step.id,
                    StepState.FAILED,
                    reason=f"Node execution failed: {str(e)}"
                )
                raise

        # For APPROVAL nodes, wait for approval
        elif node_type == "approval":
            self._handle_approval_node(node_id, node_info)

    def _create_step_for_node(self, node_id: str, node_info: Dict):
        """Create workflow_step for DAG node"""
        from cmbagent.database.models import WorkflowStep

        # Get node from database
        node = self.db.query(DAGNode).filter(DAGNode.id == node_id).first()

        step = WorkflowStep(
            run_id=node.run_id,
            session_id=self.session_id,
            step_number=node.order_index,
            agent=node.agent,
            status=StepState.PENDING,
            inputs=node.metadata
        )
        self.db.add(step)
        self.db.commit()
        return step

    def _handle_approval_node(self, node_id: str, node_info: Dict):
        """Handle approval node - will be implemented in Stage 6"""
        # Placeholder for now
        pass
```

**Files to Create:**
- `cmbagent/database/dag_executor.py`

**Verification:**
- Executes nodes in correct order
- Respects dependencies
- Supports parallel execution
- Creates workflow_steps for nodes
- Handles node failures
- Updates node status in database

### Task 5: Add DAG Visualization Export
**Objective:** Export DAG data for UI visualization

**Implementation:**

```python
class DAGVisualizer:
    """Exports DAG data for visualization"""

    def __init__(self, db_session):
        self.db = db_session

    def export_for_ui(self, run_id: str) -> Dict:
        """
        Export DAG in format suitable for UI visualization

        Returns:
            Dictionary with nodes and edges for graph rendering
        """
        nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id
        ).all()

        edges = self.db.query(DAGEdge).join(
            DAGNode, DAGEdge.from_node_id == DAGNode.id
        ).filter(
            DAGNode.run_id == run_id
        ).all()

        # Get execution levels for positioning
        sorter = TopologicalSorter(self.db)
        levels = sorter.sort(run_id)
        node_levels = {}
        for level_idx, level_nodes in enumerate(levels):
            for node_id in level_nodes:
                node_levels[node_id] = level_idx

        # Format nodes for UI
        ui_nodes = []
        for node in nodes:
            ui_nodes.append({
                "id": str(node.id),
                "type": node.node_type,
                "agent": node.agent,
                "status": node.status,
                "level": node_levels.get(node.id, 0),
                "label": self._get_node_label(node),
                "metadata": node.metadata
            })

        # Format edges for UI
        ui_edges = []
        for edge in edges:
            ui_edges.append({
                "id": str(edge.id),
                "from": str(edge.from_node_id),
                "to": str(edge.to_node_id),
                "type": edge.dependency_type
            })

        return {
            "nodes": ui_nodes,
            "edges": ui_edges,
            "levels": len(levels)
        }

    def _get_node_label(self, node: DAGNode) -> str:
        """Generate human-readable label for node"""
        if node.node_type == "planning":
            return "Planning"
        elif node.node_type == "terminator":
            return "Complete"
        elif node.node_type == "agent":
            agent_name = node.agent or "Agent"
            return f"{agent_name.title()}"
        elif node.node_type == "approval":
            return "Approval Required"
        else:
            return node.node_type.title()

    def export_mermaid(self, run_id: str) -> str:
        """
        Export DAG as Mermaid diagram syntax

        Returns:
            Mermaid diagram string
        """
        nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == run_id
        ).all()

        edges = self.db.query(DAGEdge).join(
            DAGNode, DAGEdge.from_node_id == DAGNode.id
        ).filter(
            DAGNode.run_id == run_id
        ).all()

        mermaid = ["graph TD"]

        # Add nodes
        for node in nodes:
            label = self._get_node_label(node)
            node_style = self._get_mermaid_style(node.node_type)
            mermaid.append(f"    {node.id}[{label}]{node_style}")

        # Add edges
        for edge in edges:
            arrow = "-->" if edge.dependency_type == "sequential" else "-..->"
            mermaid.append(f"    {edge.from_node_id} {arrow} {edge.to_node_id}")

        return "\n".join(mermaid)

    def _get_mermaid_style(self, node_type: str) -> str:
        """Get Mermaid styling for node type"""
        styles = {
            "planning": ":::planning",
            "agent": ":::agent",
            "approval": ":::approval",
            "terminator": ":::terminator"
        }
        return styles.get(node_type, "")
```

**Files to Create:**
- `cmbagent/database/dag_visualizer.py`

**Verification:**
- Exports DAG in UI-friendly format
- Includes node levels for layout
- Includes node status for coloring
- Can export as Mermaid diagram
- JSON serializable

### Task 6: Integrate DAG into CMBAgent Workflow
**Objective:** Use DAG builder and executor in planning_and_control

**Implementation:**

Update `cmbagent/cmbagent.py`:
```python
from cmbagent.database.dag_builder import DAGBuilder
from cmbagent.database.dag_executor import DAGExecutor
from cmbagent.database.dag_visualizer import DAGVisualizer

class CMBAgent:
    def planning_and_control_context_carryover(self, task, agent="engineer", model="gpt-4o", ...):
        # ... existing run creation ...

        # Transition to PLANNING
        self.workflow_sm.transition_to(run.id, WorkflowState.PLANNING)

        # Execute planning phase
        plan = self._execute_planning(run, task)

        # Build DAG from plan
        dag_builder = DAGBuilder(self.db_session, self.session_id)
        dag_nodes = dag_builder.build_from_plan(run.id, plan)

        # Validate DAG
        if not dag_builder.validate_dag(dag_nodes):
            raise ValueError("Invalid plan: cyclic dependencies detected")

        # Export DAG for UI
        dag_viz = DAGVisualizer(self.db_session)
        dag_data = dag_viz.export_for_ui(run.id)
        # TODO: Send dag_data via WebSocket to UI

        # Transition to EXECUTING
        self.workflow_sm.transition_to(run.id, WorkflowState.EXECUTING)

        # Execute DAG
        dag_executor = DAGExecutor(self.db_session, self.session_id)

        def execute_agent_node(node_id, agent_name, task):
            # Execute agent and return result
            return self._execute_agent(agent_name, task, run.id)

        dag_executor.execute(run.id, execute_agent_node)

        # Transition to COMPLETED
        self.workflow_sm.transition_to(run.id, WorkflowState.COMPLETED)

        return run
```

**Files to Modify:**
- `cmbagent/cmbagent.py` (integrate DAG workflow)

**Verification:**
- Plans converted to DAGs
- DAGs validated for cycles
- DAG execution respects dependencies
- Parallel nodes can execute concurrently
- DAG data exported for UI

## Files to Create (Summary)

### New Files
```
cmbagent/database/
├── dag_types.py              # Node types and metadata
├── dag_builder.py            # Build DAG from plan
├── topological_sort.py       # Execution order computation
├── dag_executor.py           # DAG execution engine
└── dag_visualizer.py         # Export DAG for UI
```

### Modified Files
- `cmbagent/cmbagent.py` - Integrate DAG workflow

## Verification Criteria

### Must Pass
- [ ] DAG node types defined
- [ ] DAGBuilder parses plans to DAGs
- [ ] DAG nodes stored in database
- [ ] DAG edges stored in database
- [ ] Topological sort computes correct execution order
- [ ] DAGExecutor executes nodes in order
- [ ] Parallel nodes execute concurrently
- [ ] Cycle detection works
- [ ] DAG validation prevents invalid graphs
- [ ] DAG data exported for UI visualization
- [ ] `python tests/test_one_shot.py` passes

### Should Pass
- [ ] Complex DAGs with branching handled
- [ ] Parallel execution limited by max_parallel
- [ ] Node failures halt execution properly
- [ ] Can export Mermaid diagrams
- [ ] Execution levels computed correctly

### DAG Testing
```python
# Test DAG builder
def test_dag_builder():
    plan = {
        "steps": [
            {"agent": "engineer", "task": "Task 1", "depends_on": ["planning"]},
            {"agent": "researcher", "task": "Task 2", "depends_on": ["step_0"]},
        ]
    }
    builder = DAGBuilder(db_session, session_id)
    nodes = builder.build_from_plan(run_id, plan)
    assert len(nodes) > 0
    assert builder.validate_dag(nodes) == True

# Test topological sort
def test_topological_sort():
    sorter = TopologicalSorter(db_session)
    levels = sorter.sort(run_id)
    assert len(levels) > 0
    assert levels[0] == ["planning"]

# Test parallel execution
def test_parallel_execution():
    plan = {
        "steps": [
            {"agent": "engineer", "task": "A", "parallel": True, "parallel_group": "g1"},
            {"agent": "researcher", "task": "B", "parallel": True, "parallel_group": "g1"},
        ]
    }
    # Should execute A and B in same level
    builder = DAGBuilder(db_session, session_id)
    nodes = builder.build_from_plan(run_id, plan)
    sorter = TopologicalSorter(db_session)
    levels = sorter.sort(run_id)
    # Find level with both nodes
    has_parallel_level = any(len(level) >= 2 for level in levels)
    assert has_parallel_level

# Test cycle detection
def test_cycle_detection():
    # Manually create cycle: A -> B -> C -> A
    # Should fail validation
    # ... create nodes and edges ...
    builder = DAGBuilder(db_session, session_id)
    assert builder.validate_dag(nodes) == False
```

## Testing Checklist

### Unit Tests
```python
# Test DAG node creation
def test_create_dag_node():
    builder = DAGBuilder(db_session, session_id)
    node = builder._create_node(run_id, "agent", 1, agent="engineer")
    assert node.id is not None
    assert node.node_type == "agent"

# Test DAG edge creation
def test_create_dag_edge():
    builder = DAGBuilder(db_session, session_id)
    edge = builder._create_edge(node1.id, node2.id, "sequential")
    assert edge.id is not None

# Test visualization export
def test_dag_visualization():
    viz = DAGVisualizer(db_session)
    data = viz.export_for_ui(run_id)
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 0
```

### Integration Tests
```python
# Test full DAG workflow
def test_dag_workflow():
    agent = CMBAgent(session_id="test")
    result = agent.planning_and_control("Create multi-step analysis")

    # Verify DAG created
    nodes = agent.db_session.query(DAGNode).filter(
        DAGNode.run_id == result.run_id
    ).all()
    assert len(nodes) > 0

    # Verify execution order
    sorter = TopologicalSorter(agent.db_session)
    levels = sorter.sort(result.run_id)
    assert len(levels) > 2  # At least planning, steps, terminator
```

## Common Issues and Solutions

### Issue 1: Cycle Detection False Positives
**Symptom:** Valid DAG reported as having cycles
**Solution:** Review cycle detection algorithm, ensure proper visited/recursion tracking

### Issue 2: Parallel Execution Hangs
**Symptom:** Workflow stalls during parallel execution
**Solution:** Check for deadlocks, ensure proper thread pool cleanup

### Issue 3: Node Dependencies Not Resolved
**Symptom:** Nodes execute before dependencies complete
**Solution:** Verify topological sort implementation, check edge directions

### Issue 4: Database Lock During Parallel Execution
**Symptom:** SQLite database locked error
**Solution:** Use WAL mode, or serialize database writes

### Issue 5: DAG Too Large for Visualization
**Symptom:** UI crashes with large DAGs
**Solution:** Implement pagination or collapsible groups

## Rollback Procedure

If DAG implementation causes issues:

1. **Feature flag to disable:**
   ```python
   USE_DAG_EXECUTION = os.getenv("CMBAGENT_USE_DAG", "false") == "true"
   ```

2. **Fall back to sequential execution:**
   ```python
   # Execute steps one by one (old way)
   for step in plan["steps"]:
       execute_step(step)
   ```

3. **Keep DAG tables** - May be useful for debugging

4. **Document issues** for future resolution

## Post-Stage Actions

### Documentation
- Document DAG architecture in ARCHITECTURE.md
- Add DAG builder usage examples
- Create DAG visualization guide
- Document parallel execution limits

### Update Progress
- Mark Stage 4 complete in PROGRESS.md
- Note any deviations from plan
- Document time spent
- Update DAG implementation lessons

### Prepare for Stage 5
- DAG execution operational
- Parallel execution working
- Ready to enhance WebSocket protocol for DAG updates
- Stage 5 can proceed

## Success Criteria

Stage 4 is complete when:
1. Plans converted to DAG structure
2. DAG stored in database
3. Topological sort determines execution order
4. Parallel execution works correctly
5. Cycle detection prevents invalid DAGs
6. DAG data exported for UI
7. Verification checklist 100% complete

## Estimated Time Breakdown

- DAG types and metadata: 5 min
- DAG builder implementation: 10 min
- Topological sort: 8 min
- DAG executor: 10 min
- Visualization export: 5 min
- CMBAgent integration: 7 min
- Testing and verification: 10 min
- Documentation: 5 min

**Total: 35-45 minutes**

## Next Stage

Once Stage 4 is verified complete, proceed to:
**Stage 5: Enhanced WebSocket Protocol**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
