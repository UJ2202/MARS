# Stage 9: Branching and Play-from-Node

**Phase:** 2 - Optimization
**Estimated Time:** 35-45 minutes
**Dependencies:** Stages 1-8 (State Machine, DAG, Database, Checkpoints) must be complete
**Risk Level:** Medium

## Objectives

1. Implement workflow branching from any execution point
2. Enable play-from-node (resume from specific step)
3. Support alternative execution paths (hypothesis testing)
4. Create branch comparison and visualization
5. Add branch merging and conflict resolution
6. Implement checkpoint-based branching
7. Support what-if scenarios for scientific exploration

## Current State Analysis

### What We Have
- Linear workflow execution with checkpoints
- State machine tracking workflow progress
- Database storing all execution history
- Checkpoint system saving context at each step
- DAG representation of workflow structure

### What We Need
- Branch creation from any workflow node
- Fork workflow state to new branch
- Independent execution of branch without affecting parent
- Branch comparison tools
- Merge branch results back to parent
- UI visualization of branch tree
- Branch metadata tracking (hypothesis, rationale)

## Pre-Stage Verification

### Check Prerequisites
1. Stages 1-8 complete and verified
2. Checkpoint system working reliably
3. Database schema supports branches table
4. State machine allows PAUSED → BRANCHED transition
5. DAG structure supports branch points

### Expected State
- Workflows can be paused at any point
- Checkpoints contain complete resumable state
- Database can query branch relationships
- Ready to add branching capability

## Implementation Tasks

### Task 1: Design Branch Data Model
**Objective:** Define branch relationships and metadata

**Database Schema Extensions:**

Already exists in `branches` table from Stage 2, but verify:

```sql
branches (
    id UUID PRIMARY KEY,
    parent_run_id UUID,  -- Original workflow run
    parent_step_id UUID,  -- Branch point in parent
    child_run_id UUID,    -- New branched workflow
    branch_name VARCHAR(255),
    created_at TIMESTAMP,
    hypothesis TEXT,      -- Scientific hypothesis being tested
    status VARCHAR(50),   -- active, completed, merged, abandoned
    metadata JSONB        -- Additional branch info
)
```

**Additional Fields to Add:**

```sql
-- Add to workflow_runs table
ALTER TABLE workflow_runs ADD COLUMN branch_parent_id UUID;
ALTER TABLE workflow_runs ADD COLUMN is_branch BOOLEAN DEFAULT FALSE;
ALTER TABLE workflow_runs ADD COLUMN branch_depth INTEGER DEFAULT 0;
```

**Files to Modify:**
- `cmbagent/database/models.py`

**Verification:**
- Branch relationships properly defined
- Can query branch tree structure
- Circular branch references prevented

### Task 2: Implement Branch Creation
**Objective:** Fork workflow execution from any node

**Implementation:**

```python
class BranchManager:
    def __init__(self, db_session, run_id):
        self.db = db_session
        self.run_id = run_id
        self.repo = WorkflowRepository(db_session)

    def create_branch(
        self,
        step_id,
        branch_name,
        hypothesis=None,
        modifications=None
    ):
        """
        Create a new branch from a specific step

        Args:
            step_id: ID of step to branch from
            branch_name: Descriptive name for branch
            hypothesis: Scientific hypothesis being tested
            modifications: Dict of changes to apply to branch
                {
                    "context_changes": {...},
                    "parameter_overrides": {...},
                    "alternative_approach": "..."
                }

        Returns:
            new_run_id: ID of newly created branch workflow
        """
        # 1. Load parent run and step
        parent_run = self.repo.get_run(self.run_id)
        parent_step = self.repo.get_step(step_id)

        if not parent_step:
            raise ValueError(f"Step {step_id} not found")

        # 2. Load checkpoint at branch point
        checkpoint = self.repo.get_checkpoint_at_step(step_id)

        if not checkpoint:
            raise ValueError(f"No checkpoint found for step {step_id}")

        # 3. Create new workflow run (branch)
        branch_run = WorkflowRun(
            session_id=parent_run.session_id,
            project_id=parent_run.project_id,
            mode=parent_run.mode,
            agent=parent_run.agent,
            model=parent_run.model,
            status="draft",
            task_description=parent_run.task_description,
            is_branch=True,
            branch_parent_id=self.run_id,
            branch_depth=parent_run.branch_depth + 1,
            metadata={
                "branch_name": branch_name,
                "hypothesis": hypothesis,
                "branched_from_step": str(step_id),
                "modifications": modifications
            }
        )

        self.db.add(branch_run)
        self.db.commit()

        # 4. Create branch relationship record
        branch = Branch(
            parent_run_id=self.run_id,
            parent_step_id=step_id,
            child_run_id=branch_run.id,
            branch_name=branch_name,
            hypothesis=hypothesis,
            status="active",
            metadata=modifications
        )

        self.db.add(branch)
        self.db.commit()

        # 5. Copy execution history up to branch point
        self._copy_execution_history(
            parent_run_id=self.run_id,
            child_run_id=branch_run.id,
            up_to_step=step_id
        )

        # 6. Apply modifications to branch context
        if modifications:
            self._apply_modifications(branch_run.id, checkpoint, modifications)

        # 7. Create isolated work directory for branch
        self._create_branch_work_directory(branch_run.id, parent_run)

        logger.info(
            f"Created branch '{branch_name}' from step {step_id}. "
            f"New run ID: {branch_run.id}"
        )

        return str(branch_run.id)

    def _copy_execution_history(self, parent_run_id, child_run_id, up_to_step):
        """Copy steps, messages, and context up to branch point"""
        # Get all steps before branch point
        parent_steps = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == parent_run_id,
            WorkflowStep.step_number <= up_to_step.step_number
        ).all()

        # Copy steps to new run
        for parent_step in parent_steps:
            child_step = WorkflowStep(
                run_id=child_run_id,
                session_id=parent_step.session_id,
                step_number=parent_step.step_number,
                agent=parent_step.agent,
                status=parent_step.status,
                started_at=parent_step.started_at,
                completed_at=parent_step.completed_at,
                inputs=parent_step.inputs,
                outputs=parent_step.outputs,
                metadata={
                    **parent_step.metadata,
                    "copied_from_step": str(parent_step.id)
                }
            )
            self.db.add(child_step)

        # Copy DAG nodes
        parent_nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == parent_run_id
        ).all()

        node_id_mapping = {}  # parent_id -> child_id

        for parent_node in parent_nodes:
            child_node = DAGNode(
                run_id=child_run_id,
                session_id=parent_node.session_id,
                node_type=parent_node.node_type,
                agent=parent_node.agent,
                status="pending",  # Reset status for re-execution
                order_index=parent_node.order_index,
                metadata=parent_node.metadata
            )
            self.db.add(child_node)
            self.db.flush()

            node_id_mapping[parent_node.id] = child_node.id

        # Copy DAG edges with new node IDs
        parent_edges = self.db.query(DAGEdge).filter(
            DAGEdge.from_node_id.in_(node_id_mapping.keys())
        ).all()

        for parent_edge in parent_edges:
            child_edge = DAGEdge(
                from_node_id=node_id_mapping[parent_edge.from_node_id],
                to_node_id=node_id_mapping[parent_edge.to_node_id],
                dependency_type=parent_edge.dependency_type,
                condition=parent_edge.condition
            )
            self.db.add(child_edge)

        self.db.commit()

    def _apply_modifications(self, branch_run_id, checkpoint, modifications):
        """Apply modifications to branch execution context"""
        context = checkpoint.context_snapshot.copy()

        # Apply context changes
        if "context_changes" in modifications:
            context.update(modifications["context_changes"])

        # Apply parameter overrides
        if "parameter_overrides" in modifications:
            if "parameters" not in context:
                context["parameters"] = {}
            context["parameters"].update(modifications["parameter_overrides"])

        # Add alternative approach to context
        if "alternative_approach" in modifications:
            context["alternative_approach"] = modifications["alternative_approach"]

        # Save modified context as initial checkpoint for branch
        new_checkpoint = Checkpoint(
            run_id=branch_run_id,
            step_id=None,
            checkpoint_type="branch_initial",
            context_snapshot=context,
            metadata={
                "branched_at": datetime.utcnow().isoformat(),
                "modifications_applied": True
            }
        )

        self.db.add(new_checkpoint)
        self.db.commit()

    def _create_branch_work_directory(self, branch_run_id, parent_run):
        """Create isolated work directory for branch"""
        parent_work_dir = parent_run.metadata.get("work_dir")

        branch_work_dir = f"{parent_work_dir}/branches/{branch_run_id}"
        os.makedirs(branch_work_dir, exist_ok=True)

        # Copy relevant files from parent
        for subdir in ["data", "codebase"]:
            parent_subdir = f"{parent_work_dir}/{subdir}"
            branch_subdir = f"{branch_work_dir}/{subdir}"

            if os.path.exists(parent_subdir):
                shutil.copytree(parent_subdir, branch_subdir)

        # Update branch run metadata
        branch_run = self.repo.get_run(branch_run_id)
        branch_run.metadata["work_dir"] = branch_work_dir
        self.db.commit()
```

**Files to Create:**
- `cmbagent/branching/branch_manager.py`

**Verification:**
- Branch created successfully
- Execution history copied
- Work directory isolated
- Context modifications applied
- Database relationships correct

### Task 3: Implement Play-from-Node
**Objective:** Resume execution from any specific node

**Implementation:**

```python
class PlayFromNodeExecutor:
    def __init__(self, db_session, run_id):
        self.db = db_session
        self.run_id = run_id
        self.repo = WorkflowRepository(db_session)

    def play_from_node(self, node_id, context_override=None):
        """
        Resume workflow execution from a specific node

        Args:
            node_id: ID of DAG node to start from
            context_override: Optional dict to modify context before resuming

        Returns:
            execution_result: Result of resumed execution
        """
        # 1. Validate node exists and is in valid state
        node = self.repo.get_dag_node(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")

        # 2. Load checkpoint before this node
        checkpoint = self._find_checkpoint_before_node(node_id)

        if not checkpoint:
            raise ValueError(f"No checkpoint found before node {node_id}")

        # 3. Load context from checkpoint
        context = checkpoint.context_snapshot.copy()

        # Apply context override if provided
        if context_override:
            context.update(context_override)

        # 4. Mark all nodes after branch point as PENDING
        self._reset_downstream_nodes(node_id)

        # 5. Update workflow run status to EXECUTING
        run = self.repo.get_run(self.run_id)
        run.status = "executing"
        run.metadata["resumed_from_node"] = str(node_id)
        run.metadata["resumed_at"] = datetime.utcnow().isoformat()
        self.db.commit()

        # 6. Get DAG executor and resume from node
        from cmbagent.execution.dag_executor import DAGExecutor

        dag = self._build_dag_from_run(self.run_id)
        executor = DAGExecutor(dag, self.db, self.run_id)

        # Execute from this node onward
        result = executor.execute_from_node(node_id, context)

        return result

    def _find_checkpoint_before_node(self, node_id):
        """Find most recent checkpoint before this node"""
        node = self.repo.get_dag_node(node_id)

        # Get all checkpoints for this run
        checkpoints = self.db.query(Checkpoint).filter(
            Checkpoint.run_id == self.run_id
        ).order_by(Checkpoint.created_at.desc()).all()

        # Find checkpoint with step_number < node.order_index
        for checkpoint in checkpoints:
            if checkpoint.step_id:
                step = self.repo.get_step(checkpoint.step_id)
                if step.step_number < node.order_index:
                    return checkpoint

        # Fallback to initial checkpoint
        return checkpoints[-1] if checkpoints else None

    def _reset_downstream_nodes(self, start_node_id):
        """Reset all nodes after start_node to PENDING"""
        start_node = self.repo.get_dag_node(start_node_id)

        # Get all nodes with order_index >= start_node.order_index
        downstream_nodes = self.db.query(DAGNode).filter(
            DAGNode.run_id == self.run_id,
            DAGNode.order_index >= start_node.order_index
        ).all()

        for node in downstream_nodes:
            node.status = "pending"
            node.started_at = None
            node.completed_at = None
            node.error_message = None

        self.db.commit()
```

**Files to Create:**
- `cmbagent/branching/play_from_node.py`

**Verification:**
- Can resume from any node
- Context restored correctly
- Downstream nodes reset properly
- Execution continues normally

### Task 4: Implement Branch Comparison
**Objective:** Compare results between branches

**Implementation:**

```python
class BranchComparator:
    def __init__(self, db_session):
        self.db = db_session
        self.repo = WorkflowRepository(db_session)

    def compare_branches(self, run_id_1, run_id_2):
        """
        Compare two workflow branches

        Returns:
            comparison_result: Dict with detailed comparison
        """
        run1 = self.repo.get_run(run_id_1)
        run2 = self.repo.get_run(run_id_2)

        comparison = {
            "run_ids": [run_id_1, run_id_2],
            "branch_names": [
                run1.metadata.get("branch_name", "main"),
                run2.metadata.get("branch_name", "main")
            ],
            "status": [run1.status, run2.status],
            "execution_time": [
                self._get_execution_time(run1),
                self._get_execution_time(run2)
            ],
            "total_cost": [
                self._get_total_cost(run_id_1),
                self._get_total_cost(run_id_2)
            ],
            "step_comparison": self._compare_steps(run_id_1, run_id_2),
            "output_diff": self._compare_outputs(run_id_1, run_id_2),
            "metrics_comparison": self._compare_metrics(run_id_1, run_id_2)
        }

        return comparison

    def _compare_steps(self, run_id_1, run_id_2):
        """Compare steps between two runs"""
        steps1 = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id_1
        ).order_by(WorkflowStep.step_number).all()

        steps2 = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id_2
        ).order_by(WorkflowStep.step_number).all()

        comparison = []

        for i in range(max(len(steps1), len(steps2))):
            step1 = steps1[i] if i < len(steps1) else None
            step2 = steps2[i] if i < len(steps2) else None

            comparison.append({
                "step_number": i,
                "branch_1": {
                    "agent": step1.agent if step1 else None,
                    "status": step1.status if step1 else None,
                    "outputs": step1.outputs if step1 else None
                },
                "branch_2": {
                    "agent": step2.agent if step2 else None,
                    "status": step2.status if step2 else None,
                    "outputs": step2.outputs if step2 else None
                },
                "differs": (
                    step1 and step2 and
                    step1.outputs != step2.outputs
                )
            })

        return comparison

    def _compare_outputs(self, run_id_1, run_id_2):
        """Compare final outputs between branches"""
        run1 = self.repo.get_run(run_id_1)
        run2 = self.repo.get_run(run_id_2)

        work_dir_1 = run1.metadata.get("work_dir")
        work_dir_2 = run2.metadata.get("work_dir")

        outputs_1 = self._collect_outputs(work_dir_1)
        outputs_2 = self._collect_outputs(work_dir_2)

        diff = {
            "files_only_in_branch_1": [],
            "files_only_in_branch_2": [],
            "files_in_both": [],
            "content_diffs": {}
        }

        files1 = set(outputs_1.keys())
        files2 = set(outputs_2.keys())

        diff["files_only_in_branch_1"] = list(files1 - files2)
        diff["files_only_in_branch_2"] = list(files2 - files1)
        diff["files_in_both"] = list(files1 & files2)

        # Compare file contents for common files
        for file in diff["files_in_both"]:
            if outputs_1[file] != outputs_2[file]:
                diff["content_diffs"][file] = {
                    "branch_1_content": outputs_1[file][:500],  # First 500 chars
                    "branch_2_content": outputs_2[file][:500]
                }

        return diff

    def _compare_metrics(self, run_id_1, run_id_2):
        """Compare execution metrics between branches"""
        metrics1 = self.db.query(WorkflowMetric).filter(
            WorkflowMetric.run_id == run_id_1
        ).all()

        metrics2 = self.db.query(WorkflowMetric).filter(
            WorkflowMetric.run_id == run_id_2
        ).all()

        # Group by metric name
        metrics1_dict = {}
        for m in metrics1:
            if m.metric_name not in metrics1_dict:
                metrics1_dict[m.metric_name] = []
            metrics1_dict[m.metric_name].append(m.metric_value)

        metrics2_dict = {}
        for m in metrics2:
            if m.metric_name not in metrics2_dict:
                metrics2_dict[m.metric_name] = []
            metrics2_dict[m.metric_name].append(m.metric_value)

        comparison = {}
        all_metric_names = set(metrics1_dict.keys()) | set(metrics2_dict.keys())

        for metric_name in all_metric_names:
            vals1 = metrics1_dict.get(metric_name, [])
            vals2 = metrics2_dict.get(metric_name, [])

            comparison[metric_name] = {
                "branch_1": {
                    "count": len(vals1),
                    "avg": sum(vals1) / len(vals1) if vals1 else 0,
                    "min": min(vals1) if vals1 else 0,
                    "max": max(vals1) if vals1 else 0
                },
                "branch_2": {
                    "count": len(vals2),
                    "avg": sum(vals2) / len(vals2) if vals2 else 0,
                    "min": min(vals2) if vals2 else 0,
                    "max": max(vals2) if vals2 else 0
                }
            }

        return comparison

    def visualize_branch_tree(self, root_run_id):
        """Generate tree visualization of branches"""
        tree = self._build_branch_tree(root_run_id)
        return self._format_tree(tree)

    def _build_branch_tree(self, root_run_id, depth=0):
        """Recursively build branch tree structure"""
        run = self.repo.get_run(root_run_id)

        # Find child branches
        child_branches = self.db.query(Branch).filter(
            Branch.parent_run_id == root_run_id
        ).all()

        tree = {
            "run_id": root_run_id,
            "name": run.metadata.get("branch_name", "main"),
            "status": run.status,
            "depth": depth,
            "hypothesis": run.metadata.get("hypothesis"),
            "children": []
        }

        for branch in child_branches:
            child_tree = self._build_branch_tree(branch.child_run_id, depth + 1)
            tree["children"].append(child_tree)

        return tree
```

**Files to Create:**
- `cmbagent/branching/comparator.py`

**Verification:**
- Branch comparison returns detailed diff
- Metrics comparison accurate
- Tree visualization renders correctly
- Output file differences detected

### Task 5: Add Branch UI Components
**Objective:** Visualize and manage branches in UI

**Files to Create:**
- `cmbagent-ui/components/BranchTree.tsx` - Tree visualization
- `cmbagent-ui/components/BranchComparison.tsx` - Side-by-side comparison
- `cmbagent-ui/components/CreateBranchDialog.tsx` - Branch creation UI
- `cmbagent-ui/hooks/useBranching.ts` - Branch management hook

**Implementation Example:**

```typescript
// useBranching.ts
export function useBranching(runId: string) {
  const createBranch = async (
    stepId: string,
    branchName: string,
    hypothesis: string,
    modifications: any
  ) => {
    const response = await fetch(`/api/runs/${runId}/branch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        step_id: stepId,
        branch_name: branchName,
        hypothesis,
        modifications
      })
    });

    return await response.json();
  };

  const playFromNode = async (nodeId: string, contextOverride: any) => {
    const response = await fetch(`/api/runs/${runId}/play-from-node`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node_id: nodeId,
        context_override: contextOverride
      })
    });

    return await response.json();
  };

  const compareBranches = async (runId1: string, runId2: string) => {
    const response = await fetch(
      `/api/branches/compare?run_id_1=${runId1}&run_id_2=${runId2}`
    );

    return await response.json();
  };

  return { createBranch, playFromNode, compareBranches };
}
```

**Verification:**
- UI components render correctly
- Branch creation dialog works
- Tree visualization interactive
- Comparison view shows differences

### Task 6: Add API Endpoints
**Objective:** Expose branching functionality via REST API

**Files to Modify:**
- `backend/run.py`

**Endpoints to Add:**

```python
@app.post("/api/runs/{run_id}/branch")
async def create_branch(
    run_id: str,
    request: BranchRequest
):
    """Create a new branch from a specific step"""
    branch_manager = BranchManager(db_session, run_id)

    new_run_id = branch_manager.create_branch(
        step_id=request.step_id,
        branch_name=request.branch_name,
        hypothesis=request.hypothesis,
        modifications=request.modifications
    )

    return {"branch_run_id": new_run_id}

@app.post("/api/runs/{run_id}/play-from-node")
async def play_from_node(
    run_id: str,
    request: PlayFromNodeRequest
):
    """Resume execution from a specific node"""
    executor = PlayFromNodeExecutor(db_session, run_id)

    result = executor.play_from_node(
        node_id=request.node_id,
        context_override=request.context_override
    )

    return {"result": result}

@app.get("/api/branches/compare")
async def compare_branches(
    run_id_1: str,
    run_id_2: str
):
    """Compare two workflow branches"""
    comparator = BranchComparator(db_session)

    comparison = comparator.compare_branches(run_id_1, run_id_2)

    return comparison

@app.get("/api/runs/{run_id}/branch-tree")
async def get_branch_tree(run_id: str):
    """Get branch tree visualization"""
    comparator = BranchComparator(db_session)

    tree = comparator.visualize_branch_tree(run_id)

    return tree
```

**Verification:**
- API endpoints respond correctly
- Authentication/authorization working
- Error handling robust
- Response formats match UI expectations

### Task 7: Add CLI Commands
**Objective:** Support branching from CLI

**Files to Modify:**
- `cmbagent/cli.py`

**Commands to Add:**

```python
@cli.command()
@click.argument("run_id")
@click.argument("step_id")
@click.option("--name", required=True, help="Branch name")
@click.option("--hypothesis", help="Hypothesis being tested")
def branch(run_id, step_id, name, hypothesis):
    """Create a branch from a specific step"""
    from cmbagent.branching import BranchManager

    manager = BranchManager(get_db_session(), run_id)
    new_run_id = manager.create_branch(step_id, name, hypothesis)

    click.echo(f"Created branch: {new_run_id}")

@cli.command()
@click.argument("run_id")
@click.argument("node_id")
def play_from(run_id, node_id):
    """Resume execution from a specific node"""
    from cmbagent.branching import PlayFromNodeExecutor

    executor = PlayFromNodeExecutor(get_db_session(), run_id)
    result = executor.play_from_node(node_id)

    click.echo(f"Execution completed: {result.status}")

@cli.command()
@click.argument("run_id_1")
@click.argument("run_id_2")
def compare(run_id_1, run_id_2):
    """Compare two workflow branches"""
    from cmbagent.branching import BranchComparator

    comparator = BranchComparator(get_db_session())
    comparison = comparator.compare_branches(run_id_1, run_id_2)

    click.echo(json.dumps(comparison, indent=2))
```

**Verification:**
- CLI commands work as expected
- Error messages helpful
- Output formatted nicely

## Files to Create (Summary)

### New Files
```
cmbagent/branching/
├── __init__.py
├── branch_manager.py
├── play_from_node.py
└── comparator.py

cmbagent-ui/components/
├── BranchTree.tsx
├── BranchComparison.tsx
└── CreateBranchDialog.tsx

cmbagent-ui/hooks/
└── useBranching.ts
```

### Modified Files
- `cmbagent/database/models.py` - Add branch fields
- `cmbagent/cli.py` - Add branch commands
- `backend/run.py` - Add branch endpoints
- `cmbagent/execution/dag_executor.py` - Add execute_from_node method

## Verification Criteria

### Must Pass
- [ ] Can create branch from any step
- [ ] Branch has isolated work directory
- [ ] Execution history copied correctly
- [ ] Context modifications applied
- [ ] Play-from-node resumes execution correctly
- [ ] Downstream nodes reset properly
- [ ] Branch comparison shows accurate diff
- [ ] Branch tree visualization correct
- [ ] API endpoints functional
- [ ] CLI commands work

### Should Pass
- [ ] Multiple branches from same parent supported
- [ ] Nested branches (branch of branch) work
- [ ] Branch deletion doesn't affect parent
- [ ] UI components render branch tree interactively
- [ ] Comparison view highlights key differences

### Scientific Workflow Tests
- [ ] Test hypothesis A vs hypothesis B in branches
- [ ] Compare parameter sweep results across branches
- [ ] Verify branch isolation (no cross-contamination)

## Testing Checklist

### Unit Tests
```python
# Test branch creation
def test_create_branch():
    manager = BranchManager(db_session, run_id)
    branch_run_id = manager.create_branch(
        step_id="step_3",
        branch_name="test_alternative_method",
        hypothesis="Using method B will give better results"
    )

    assert branch_run_id is not None

    # Verify branch in database
    branch_run = repo.get_run(branch_run_id)
    assert branch_run.is_branch
    assert branch_run.branch_parent_id == run_id

# Test play-from-node
def test_play_from_node():
    executor = PlayFromNodeExecutor(db_session, run_id)

    result = executor.play_from_node(node_id="node_5")

    # Verify execution resumed
    assert result.status == "completed"

    # Verify downstream nodes re-executed
    nodes = repo.get_dag_nodes(run_id)
    node_5_onwards = [n for n in nodes if n.order_index >= 5]
    assert all(n.status == "completed" for n in node_5_onwards)

# Test branch comparison
def test_branch_comparison():
    comparator = BranchComparator(db_session)

    comparison = comparator.compare_branches(run_id_1, run_id_2)

    assert "step_comparison" in comparison
    assert "output_diff" in comparison
    assert "metrics_comparison" in comparison
```

### Integration Tests
```python
# Test full branching workflow
def test_full_branching_workflow():
    # 1. Run initial workflow
    agent = CMBAgent()
    result = agent.planning_and_control("Analyze CMB data")

    run_id = result.run_id

    # 2. Create branch at step 3
    manager = BranchManager(db_session, run_id)
    branch_id = manager.create_branch(
        step_id="step_3",
        branch_name="alternative_analysis",
        modifications={"parameter_overrides": {"method": "B"}}
    )

    # 3. Execute branch
    branch_agent = CMBAgent(run_id=branch_id)
    branch_result = branch_agent.resume()

    # 4. Compare branches
    comparator = BranchComparator(db_session)
    comparison = comparator.compare_branches(run_id, branch_id)

    # Verify differences captured
    assert comparison["output_diff"]["content_diffs"]
```

## Common Issues and Solutions

### Issue 1: Branch Work Directory Conflicts
**Symptom:** Branch overwrites parent files
**Solution:** Verify work directory isolation, check symlinks

### Issue 2: Context Not Properly Copied
**Symptom:** Branch starts with wrong context
**Solution:** Ensure checkpoint loaded correctly, verify serialization

### Issue 3: Downstream Nodes Not Reset
**Symptom:** Play-from-node uses old results
**Solution:** Check _reset_downstream_nodes logic, verify DB updates

### Issue 4: Circular Branch References
**Symptom:** Branch tree visualization infinite loop
**Solution:** Add depth limit, detect cycles in branch relationships

### Issue 5: Comparison Shows No Differences
**Symptom:** Branches appear identical when they're not
**Solution:** Check file path resolution, verify output collection

## Rollback Procedure

If branching causes issues:

1. **Disable branching features:**
   ```python
   ENABLE_BRANCHING = False
   ```

2. **Hide UI components:**
   ```typescript
   const SHOW_BRANCHING = false;
   ```

3. **Keep database schema** - No data loss, just disable functionality

4. **Linear workflow still works** - Branching is optional feature

## Post-Stage Actions

### Documentation
- Document branching workflow in user guide
- Create video tutorial for branch comparison
- Add branching examples to cookbook
- Update architecture diagram with branching flow

### Update Progress
- Mark Stage 9 complete in `PROGRESS.md`
- Document use cases discovered
- Note any performance considerations

### Prepare for Stage 10
- Branching working and tested
- Ready to expose CMBAgent as MCP server
- Stage 10 can proceed

## Success Criteria

Stage 9 is complete when:
1. Branch creation works from any step
2. Play-from-node resumes execution correctly
3. Branch comparison shows accurate differences
4. Branch tree visualization functional
5. Work directory isolation prevents conflicts
6. API endpoints and CLI commands working
7. UI components render and function properly
8. Verification checklist 100% complete

## Estimated Time Breakdown

- Branch data model and creation: 10 min
- Play-from-node implementation: 8 min
- Branch comparison and visualization: 10 min
- API endpoints: 5 min
- UI components: 10 min
- CLI commands: 3 min
- Testing and verification: 12 min
- Documentation: 7 min

**Total: 35-45 minutes**

## Next Stage

Once Stage 9 is verified complete, proceed to:
**Stage 10: MCP Server Interface**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
