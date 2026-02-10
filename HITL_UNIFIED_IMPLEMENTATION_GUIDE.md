# HITL Unified Implementation Guide
## Feedback • Redo • Branching Architecture

**Version:** 1.0
**Date:** 2025-02-10
**Status:** Design Document

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Core Concepts](#core-concepts)
3. [Unified Architecture](#unified-architecture)
4. [Feedback System](#feedback-system)
5. [Redo System](#redo-system)
6. [Branching System](#branching-system)
7. [Integration & Interactions](#integration--interactions)
8. [Implementation Roadmap](#implementation-roadmap)
9. [Code Examples](#code-examples)
10. [Testing Strategy](#testing-strategy)

---

## Executive Summary

This document provides a unified architecture for three interconnected HITL features:

| Feature | Purpose | Status | Priority |
|---------|---------|--------|----------|
| **Feedback** | User guidance flows through phases and steps | ❌ Broken in control phase | 🔴 Critical |
| **Redo** | Retry steps/phases with new approach | ❌ Not implemented | 🔴 Critical |
| **Branching** | Explore alternative execution paths | ⚪ Not designed | 🟡 Important |

**Key Insight:** These three features are not independent - they form a coherent execution model:

```
Step N (baseline)
  ↓ [user provides feedback]
Step N+1 (with feedback context)
  ↓ [user requests redo with new guidance]
Step N+1 Branch A (redo with approach A)
  ↓ [user wants to try another approach]
Step N+1 Branch B (alternative approach B)
  ↓ [user compares results]
Select winning branch → continue
```

---

## Core Concepts

### 1. Execution Graph Model

**Current Model (Linear):**
```
Plan → Step 1 → Step 2 → Step 3 → Complete
```

**Proposed Model (DAG with Branches):**
```
                    ┌─ Branch A ─┐
Plan → Step 1 → Step 2             → Step 4 → Complete
                    └─ Branch B ─┘
                    └─ Branch C ─┘
```

**Key Changes:**
- Each execution point is a **node** in a DAG
- Nodes can have multiple children (branches)
- Feedback and context flow through edges
- Each branch has independent execution state

### 2. Context Inheritance Model

**Context Flows:**
```
Global Context (workflow-level)
  ↓ inherits
Phase Context (planning/control)
  ↓ inherits
Step Context (specific step)
  ↓ inherits + diverges
Branch Context (alternative execution)
```

**Inheritance Rules:**
- Child contexts inherit parent state
- Modifications in child don't affect parent (copy-on-write)
- Feedback accumulates down inheritance chain
- Branches share parent but diverge at branch point

### 3. State Machine Integration

**Execution States:**
```
┌─────────┐
│ PENDING │ → Initial state
└────┬────┘
     ↓
┌─────────┐
│ RUNNING │ → Currently executing
└────┬────┘
     ↓
┌──────────┬───────────┬──────────┐
│ SUCCESS  │  WAITING  │  FAILED  │
└────┬─────┴─────┬─────┴────┬─────┘
     ↓           ↓          ↓
┌─────────┐  ┌──────┐  ┌──────┐
│COMPLETE │  │REVIEW│  │RETRY │
└─────────┘  └──┬───┘  └──┬───┘
                ↓         ↓
            ┌───────┐  ┌────────┐
            │APPROVE│  │ REDO   │
            │REJECT │  │ BRANCH │
            │BRANCH │  └────────┘
            └───────┘
```

**State Transitions:**
- **REDO:** Same step, new attempt (increments retry counter)
- **BRANCH:** Same step, parallel alternative (creates new branch)
- **APPROVE:** Move to next step
- **REJECT:** Abort workflow or step

---

## Unified Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────┐
│                  Workflow Executor                       │
│  • Phase sequencing                                      │
│  • Branch coordination                                   │
│  • Context management                                    │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│              Execution Graph Manager                     │
│  • DAG node creation                                     │
│  • Branch tracking                                       │
│  • Context inheritance                                   │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│               Feedback Accumulator                       │
│  • Collect user feedback                                 │
│  • Inject into agent context                             │
│  • Propagate through branches                            │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│                Phase Executors                           │
│  • HITLPlanningPhase                                     │
│  • HITLControlPhase                                      │
│  • Support redo & branching                              │
└─────────────────────────────────────────────────────────┘
```

### Data Models

#### 1. Execution Node
```python
@dataclass
class ExecutionNode:
    """
    Represents a single execution point in the workflow.
    Can be a phase, step, or branch point.
    """
    id: str  # e.g., "phase_1_step_2_branch_a"
    type: NodeType  # PHASE_START, STEP, BRANCH_POINT, BRANCH, CHECKPOINT
    parent_id: Optional[str]  # Parent node
    children_ids: List[str]  # Child nodes (multiple for branches)

    # Execution state
    status: ExecutionStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    attempts: int

    # Context and feedback
    context_snapshot: Dict[str, Any]
    accumulated_feedback: str
    user_feedback: List[Dict[str, Any]]

    # Branch metadata
    branch_id: Optional[str]
    branch_name: Optional[str]
    is_branch: bool
    branch_reason: Optional[str]  # Why branch was created

    # Results
    result: Optional[Any]
    error: Optional[str]
    metrics: Dict[str, Any]

class NodeType(Enum):
    PHASE_START = "phase_start"
    PHASE_END = "phase_end"
    STEP = "step"
    BRANCH_POINT = "branch_point"
    BRANCH = "branch"
    MERGE_POINT = "merge_point"
    CHECKPOINT = "checkpoint"

class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
```

#### 2. Branch Metadata
```python
@dataclass
class BranchMetadata:
    """
    Tracks information about a branch.
    """
    branch_id: str
    branch_name: str
    created_at: datetime
    created_from_node: str  # Parent node
    created_by: str  # "user" or "system"
    creation_reason: BranchReason

    # Branch configuration
    description: str
    alternative_approach: Optional[str]
    user_guidance: Optional[str]

    # Branch state
    status: BranchStatus
    execution_path: List[str]  # Node IDs in this branch

    # Comparison
    is_winning_branch: Optional[bool]
    comparison_metrics: Dict[str, Any]

class BranchReason(Enum):
    USER_REQUESTED = "user_requested"
    REDO_WITH_ALTERNATIVE = "redo_with_alternative"
    AB_TEST = "ab_test"
    ERROR_RECOVERY = "error_recovery"
    ROLLBACK_AND_BRANCH = "rollback_and_branch"

class BranchStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    MERGED = "merged"
    SELECTED = "selected"
```

#### 3. Feedback Context
```python
@dataclass
class FeedbackContext:
    """
    Accumulates user feedback across execution.
    """
    # Hierarchical feedback
    workflow_feedback: str  # Global guidance
    phase_feedback: Dict[str, str]  # Per phase
    step_feedback: Dict[int, List[FeedbackItem]]  # Per step
    branch_feedback: Dict[str, str]  # Per branch

    # Timeline
    feedback_history: List[FeedbackItem]

    def get_accumulated_for_step(self, phase: str, step: int, branch: Optional[str]) -> str:
        """Get all feedback relevant to this execution point."""
        parts = []

        # Global feedback
        if self.workflow_feedback:
            parts.append(f"## Workflow Guidance\n{self.workflow_feedback}\n")

        # Phase feedback
        if phase in self.phase_feedback:
            parts.append(f"## Phase Guidance\n{self.phase_feedback[phase]}\n")

        # Previous steps feedback
        for prev_step in range(1, step):
            if prev_step in self.step_feedback:
                for item in self.step_feedback[prev_step]:
                    parts.append(f"## Step {prev_step} Notes\n{item.feedback}\n")

        # Current step feedback (from previous attempts)
        if step in self.step_feedback:
            for item in self.step_feedback[step]:
                parts.append(f"## Previous Attempt Feedback\n{item.feedback}\n")

        # Branch-specific feedback
        if branch and branch in self.branch_feedback:
            parts.append(f"## Branch Guidance\n{self.branch_feedback[branch]}\n")

        return "\n".join(parts)

@dataclass
class FeedbackItem:
    """Single piece of user feedback."""
    timestamp: datetime
    source: str  # "planning_iteration", "before_step", "after_step", "on_error"
    phase: str
    step: Optional[int]
    branch: Optional[str]
    feedback: str
    applied: bool  # Has this feedback been injected into an agent?
```

#### 4. Execution Graph
```python
class ExecutionGraph:
    """
    Manages the DAG of execution nodes.
    Supports branching, redo, and navigation.
    """

    def __init__(self):
        self.nodes: Dict[str, ExecutionNode] = {}
        self.branches: Dict[str, BranchMetadata] = {}
        self.root_node_id: Optional[str] = None
        self.current_node_id: Optional[str] = None
        self.active_branches: Set[str] = set()

    def create_node(
        self,
        node_type: NodeType,
        parent_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        **kwargs
    ) -> ExecutionNode:
        """Create a new node in the graph."""
        node_id = self._generate_node_id(node_type, parent_id, branch_id)

        node = ExecutionNode(
            id=node_id,
            type=node_type,
            parent_id=parent_id,
            children_ids=[],
            branch_id=branch_id,
            is_branch=branch_id is not None,
            status=ExecutionStatus.PENDING,
            **kwargs
        )

        self.nodes[node_id] = node

        # Link to parent
        if parent_id and parent_id in self.nodes:
            self.nodes[parent_id].children_ids.append(node_id)

        return node

    def create_branch(
        self,
        from_node_id: str,
        branch_name: str,
        reason: BranchReason,
        description: str,
        user_guidance: Optional[str] = None,
    ) -> BranchMetadata:
        """Create a new branch from an existing node."""
        branch_id = f"branch_{len(self.branches) + 1}_{uuid.uuid4().hex[:8]}"

        branch = BranchMetadata(
            branch_id=branch_id,
            branch_name=branch_name,
            created_at=datetime.now(),
            created_from_node=from_node_id,
            created_by="user",
            creation_reason=reason,
            description=description,
            alternative_approach=user_guidance,
            user_guidance=user_guidance,
            status=BranchStatus.ACTIVE,
            execution_path=[from_node_id],
        )

        self.branches[branch_id] = branch
        self.active_branches.add(branch_id)

        return branch

    def get_execution_path(self, node_id: str) -> List[ExecutionNode]:
        """Get the full execution path from root to this node."""
        path = []
        current = self.nodes.get(node_id)

        while current:
            path.insert(0, current)
            current = self.nodes.get(current.parent_id) if current.parent_id else None

        return path

    def get_branch_alternatives(self, node_id: str) -> List[ExecutionNode]:
        """Get all branches that diverged from this node."""
        node = self.nodes.get(node_id)
        if not node:
            return []

        # Find all children that are branches
        alternatives = []
        for child_id in node.children_ids:
            child = self.nodes[child_id]
            if child.is_branch:
                alternatives.append(child)

        return alternatives

    def compare_branches(self, branch_ids: List[str]) -> Dict[str, Any]:
        """Compare results from multiple branches."""
        comparison = {
            'branches': {},
            'metrics_comparison': {},
            'recommendations': [],
        }

        for branch_id in branch_ids:
            branch = self.branches.get(branch_id)
            if not branch:
                continue

            # Get all nodes in this branch
            branch_nodes = [n for n in self.nodes.values() if n.branch_id == branch_id]

            # Aggregate metrics
            branch_metrics = {}
            for node in branch_nodes:
                if node.metrics:
                    for key, value in node.metrics.items():
                        branch_metrics[key] = branch_metrics.get(key, 0) + value

            comparison['branches'][branch_id] = {
                'name': branch.branch_name,
                'status': branch.status.value,
                'execution_path': branch.execution_path,
                'metrics': branch_metrics,
                'final_result': branch_nodes[-1].result if branch_nodes else None,
            }

        # Simple recommendation logic
        if len(branch_ids) >= 2:
            # Compare based on success rate, errors, etc.
            # This is simplified - real logic would be more sophisticated
            comparison['recommendations'].append(
                f"Branch comparison complete. Review metrics to select winning branch."
            )

        return comparison
```

---

## Feedback System

### Architecture

```
User Input (via UI/approval manager)
    ↓
FeedbackAccumulator.collect()
    ↓
FeedbackContext.add_feedback()
    ↓
[Feedback stored with metadata: phase, step, branch, timing]
    ↓
Phase/Step Execution Start
    ↓
FeedbackContext.get_accumulated_for_step()
    ↓
CMBAgent.inject_to_agents(feedback)
    ↓
Agent executes with feedback context
```

### Implementation

#### 1. Fix Control Phase Feedback Injection

**File:** `cmbagent/phases/hitl_control.py`

**Current Code (lines 299-356):**
```python
# Step execution loop
cmbagent = CMBAgent(
    cache_seed=42,
    work_dir=control_dir,
    agent_llm_configs=agent_llm_configs,
    mode="planning_and_control_context_carryover",
    api_keys=api_keys,
)

# ❌ NO FEEDBACK INJECTION HERE!

cmbagent.solve(
    task=context.task,
    initial_agent=starter_agent,
    max_rounds=self.config.max_rounds,
    shared_context=step_shared_context,
    step=step_num,
)
```

**Fixed Code:**
```python
# Step execution loop
cmbagent = CMBAgent(
    cache_seed=42,
    work_dir=control_dir,
    agent_llm_configs=agent_llm_configs,
    mode="planning_and_control_context_carryover",
    api_keys=api_keys,
)

# ✅ INJECT ACCUMULATED FEEDBACK
if self._accumulated_feedback:
    feedback_instructions = self._format_feedback_for_agents(
        self._accumulated_feedback,
        step_num,
    )

    cmbagent.inject_to_agents(
        ["engineer", "researcher", "control"],
        feedback_instructions,
        mode="append"
    )

    print(f"→ Injected {len(self._accumulated_feedback)} chars of feedback into agents")

cmbagent.solve(
    task=context.task,
    initial_agent=starter_agent,
    max_rounds=self.config.max_rounds,
    shared_context=step_shared_context,
    step=step_num,
)
```

**Add Helper Method:**
```python
def _format_feedback_for_agents(self, feedback: str, step_num: int) -> str:
    """Format accumulated feedback for agent injection."""
    return f"""

## Human Guidance and Feedback

You are executing Step {step_num}. The human has provided the following guidance
and feedback throughout the workflow. Please take this into account:

{feedback}

**Important:** This feedback represents the human's expectations and concerns.
Make sure your implementation addresses these points.
"""
```

#### 2. Enhance Feedback Collection

**Add to `hitl_control.py`:**
```python
class FeedbackCollector:
    """Collects and manages feedback during control phase execution."""

    def __init__(self):
        self.feedback_items: List[FeedbackItem] = []
        self._accumulated: str = ""

    def add_feedback(
        self,
        feedback: str,
        source: str,
        phase: str,
        step: Optional[int] = None,
        branch: Optional[str] = None,
    ):
        """Add new feedback item."""
        item = FeedbackItem(
            timestamp=datetime.now(),
            source=source,
            phase=phase,
            step=step,
            branch=branch,
            feedback=feedback,
            applied=False,
        )
        self.feedback_items.append(item)

        # Update accumulated string
        step_label = f"Step {step}" if step else "Phase"
        if self._accumulated:
            self._accumulated += f"\n\n**{step_label} - {source}:** {feedback}"
        else:
            self._accumulated = f"**{step_label} - {source}:** {feedback}"

    def get_accumulated(self, up_to_step: Optional[int] = None) -> str:
        """Get accumulated feedback up to a certain step."""
        if up_to_step is None:
            return self._accumulated

        parts = []
        for item in self.feedback_items:
            if item.step is None or item.step <= up_to_step:
                parts.append(f"**{item.source}:** {item.feedback}")

        return "\n\n".join(parts)

    def mark_applied(self, step: int):
        """Mark all feedback up to this step as applied."""
        for item in self.feedback_items:
            if item.step is not None and item.step <= step:
                item.applied = True
```

#### 3. Propagate Feedback Through Phases

**File:** `cmbagent/phases/context.py`

**Add to WorkflowContext:**
```python
@dataclass
class WorkflowContext:
    # ... existing fields ...

    # NEW: Centralized feedback management
    feedback_context: Optional['FeedbackContext'] = None

    def add_workflow_feedback(self, feedback: str):
        """Add workflow-level feedback."""
        if not self.feedback_context:
            self.feedback_context = FeedbackContext()
        self.feedback_context.workflow_feedback = feedback

    def add_phase_feedback(self, phase: str, feedback: str):
        """Add phase-level feedback."""
        if not self.feedback_context:
            self.feedback_context = FeedbackContext()
        self.feedback_context.phase_feedback[phase] = feedback
```

---

## Redo System

### Architecture

```
Step N Execution → FAILED or User Unsatisfied
    ↓
User Action: "Redo"
    ↓
Option 1: Simple Redo (same approach, new attempt)
Option 2: Redo with Feedback (guided redo)
Option 3: Branch (try alternative approach in parallel)
    ↓
ExecutionGraph.create_redo_node() or .create_branch()
    ↓
Re-execute with:
  - Incremented attempt counter
  - New guidance (if provided)
  - Same parent context
    ↓
Compare with previous attempt
```

### Types of Redo

#### 1. Step Redo (In-Place Retry)
```
Step 2 [attempt 1] → FAILED
    ↓ redo
Step 2 [attempt 2] → SUCCESS
    ↓
Step 3
```

**Use Case:** Transient errors, quick fixes

#### 2. Branch Redo (Alternative Approach)
```
Step 2 [baseline attempt] → Suboptimal result
    ↓ branch redo
Step 2 [Branch A: approach A]
Step 2 [Branch B: approach B]
    ↓ compare
Select best → Step 3
```

**Use Case:** Try different algorithms, approaches, or parameters

#### 3. Rollback and Redo
```
Step 1 → Step 2 → Step 3 → Bad result detected
    ↓ rollback to Step 2
Step 2 [redo with new insights] → Step 3' → Good result
```

**Use Case:** Late discovery of issues, need to backtrack

### Implementation

#### 1. Fix Step-Level Redo in Control Phase

**File:** `cmbagent/phases/hitl_control.py`

**Current Code (lines 230-505):**
```python
for step_num in steps_to_execute:  # ❌ For loop can't loop back
    # ... execute step ...

    # After-step review
    review_result = await self._request_step_review(...)
    if review_result is None:  # Redo
        pass  # ❌ Does nothing!
```

**Fixed Code:**
```python
# Configuration
@dataclass
class HITLControlPhaseConfig(PhaseConfig):
    # ... existing fields ...
    max_step_redos: int = 3  # NEW: limit redo attempts per step
    allow_branch_on_redo: bool = True  # NEW: allow branching during redo

# Execution
step_index = 0
step_redo_counts = {}  # Track redos per step

while step_index < len(steps_to_execute):
    step_num = steps_to_execute[step_index]
    step = plan_steps[step_num - 1]
    step_redo_requested = False
    step_branch_requested = False

    # Get current attempt count
    current_attempt = step_redo_counts.get(step_num, 0)

    # ... execute step ...

    # After-step review
    if self.config.approval_mode in ["after_step", "both"]:
        review_result = await self._request_step_review(
            approval_manager,
            context,
            step,
            step_num,
            step_result,
            manager,
            current_attempt=current_attempt,
        )

        if review_result is None:  # Redo
            # Check if redo limit reached
            if current_attempt >= self.config.max_step_redos:
                print(f"⚠ Max redos ({self.config.max_step_redos}) reached for step {step_num}")
                print(f"→ Moving to next step")
            else:
                step_redo_requested = True
                step_redo_counts[step_num] = current_attempt + 1
                print(f"→ Redoing step {step_num} (attempt {current_attempt + 1})")

                # Check for new guidance
                if hasattr(review_result, 'user_feedback') and review_result.user_feedback:
                    redo_feedback = review_result.user_feedback
                    self._feedback_collector.add_feedback(
                        feedback=redo_feedback,
                        source="redo_guidance",
                        phase="control",
                        step=step_num,
                    )
                    print(f"   New guidance: {redo_feedback}")

        elif isinstance(review_result, dict) and review_result.get('branch_requested'):
            # User wants to try alternative approach in parallel
            step_branch_requested = True
            branch_guidance = review_result.get('branch_guidance', '')
            # Handle branching (see Branching System section)

    # Control loop progression
    if step_redo_requested:
        # Don't increment step_index - loop back to redo same step
        continue
    elif step_branch_requested:
        # Create branch, but also move to next step on main path
        # (parallel execution)
        pass

    # Normal case: move to next step
    step_index += 1
```

#### 2. Add Redo UI Options

**Update approval options to include redo with reason:**
```python
def _build_step_review_message(self, step: Dict, step_num: int, result: Dict, current_attempt: int) -> str:
    """Build message for step review with redo information."""

    redo_info = ""
    if current_attempt > 0:
        redo_info = f"\n**Note:** This is attempt #{current_attempt + 1} for this step."

    return f"""**Step {step_num} Review**

**Task:** {step.get('sub_task', 'Unknown')}

**Status:** Completed{redo_info}

**Options:**
- **Continue**: Proceed to next step
- **Redo**: Re-execute this step (attempts remaining: {self.config.max_step_redos - current_attempt})
- **Redo with Guidance**: Re-execute with additional instructions
- **Branch**: Create alternative approach in parallel
- **Abort**: Cancel the workflow
"""
```

#### 3. Phase-Level Redo

**File:** `cmbagent/workflows/composer.py`

**Add after phase completion:**
```python
async def run(self) -> WorkflowContext:
    phase_index = 0
    phase_redo_counts = {}
    max_phase_redos = 2

    while phase_index < len(self.phases):
        phase = self.phases[phase_index]

        # Execute phase
        result = await phase.execute(phase_context)

        # Check if phase requests redo
        if hasattr(result, 'redo_requested') and result.redo_requested:
            current_attempts = phase_redo_counts.get(phase_index, 0)

            if current_attempts >= max_phase_redos:
                print(f"⚠ Max phase redos reached for {phase.display_name}")
                phase_index += 1
            else:
                phase_redo_counts[phase_index] = current_attempts + 1
                print(f"→ Redoing phase: {phase.display_name}")

                # Preserve feedback from failed attempt
                if hasattr(result, 'redo_feedback'):
                    phase_context.add_phase_feedback(
                        phase.phase_type,
                        result.redo_feedback
                    )

                # Don't increment phase_index - redo same phase
                continue

        # Normal: move to next phase
        phase_index += 1
```

---

## Branching System

### Concepts

#### 1. Branch Types

**A. Alternative Approach Branch**
```
Step 2
  ├─ Baseline: Use libraries A, B
  ├─ Branch A: Use library C
  └─ Branch B: Use custom implementation
```

**B. Exploratory Branch**
```
Step 3: Data analysis
  ├─ Branch A: Full dataset
  ├─ Branch B: Sample dataset
  └─ Branch C: Filtered dataset
```

**C. Rollback Branch**
```
Step 1 → Step 2 → Step 3 [issue found]
         ↓
      [Branch from Step 2 with new approach]
         ↓
      Step 3' [alternative]
```

**D. Parallel Execution Branch**
```
Step 1
  ├─ Branch A: Steps 2a → 3a → 4a
  └─ Branch B: Steps 2b → 3b → 4b
  ↓
Merge: Compare and select best
```

#### 2. Branch Lifecycle

```
1. CREATE
   ├─ User requests branch at node N
   ├─ System creates branch metadata
   └─ Copy context from parent node

2. EXECUTE
   ├─ Branch runs independently
   ├─ Has own execution_graph nodes
   └─ Can accumulate branch-specific feedback

3. COMPARE
   ├─ User triggers comparison
   ├─ System shows results side-by-side
   └─ User evaluates alternatives

4. SELECT/MERGE
   ├─ User selects winning branch
   ├─ OR system merges insights from branches
   └─ Continue from selected branch

5. CLEANUP
   ├─ Non-selected branches marked abandoned
   └─ Winning branch becomes main path
```

### Implementation

#### 1. Core Branching Infrastructure

**File:** `cmbagent/execution/branching.py` (NEW FILE)

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid
from datetime import datetime


class BranchManager:
    """
    Manages branches in workflow execution.
    Coordinates with ExecutionGraph for node creation.
    """

    def __init__(self, execution_graph: 'ExecutionGraph'):
        self.execution_graph = execution_graph
        self.branches: Dict[str, BranchMetadata] = {}
        self.active_branches: Set[str] = set()

    def create_branch_from_step(
        self,
        step_num: int,
        branch_name: str,
        alternative_approach: str,
        user_guidance: Optional[str] = None,
        reason: BranchReason = BranchReason.USER_REQUESTED,
    ) -> str:
        """
        Create a new branch starting from a specific step.

        Returns:
            branch_id: Unique identifier for the new branch
        """
        # Get the current execution node for this step
        current_node_id = self._find_node_for_step(step_num)

        if not current_node_id:
            raise ValueError(f"Cannot find node for step {step_num}")

        # Create branch metadata
        branch_id = f"branch_{step_num}_{uuid.uuid4().hex[:8]}"

        branch_meta = BranchMetadata(
            branch_id=branch_id,
            branch_name=branch_name,
            created_at=datetime.now(),
            created_from_node=current_node_id,
            created_by="user",
            creation_reason=reason,
            description=f"Alternative approach for step {step_num}",
            alternative_approach=alternative_approach,
            user_guidance=user_guidance,
            status=BranchStatus.ACTIVE,
            execution_path=[current_node_id],
            comparison_metrics={},
        )

        self.branches[branch_id] = branch_meta
        self.active_branches.add(branch_id)

        # Create branch point node in execution graph
        branch_point_node = self.execution_graph.create_node(
            node_type=NodeType.BRANCH_POINT,
            parent_id=current_node_id,
        )

        print(f"✓ Created branch: {branch_name} (id: {branch_id})")
        print(f"  Branching from step {step_num}")
        print(f"  Alternative approach: {alternative_approach}")

        return branch_id

    def execute_branch(
        self,
        branch_id: str,
        executor_func,  # Function to execute the branch steps
        context: PhaseContext,
    ) -> Any:
        """
        Execute a branch independently.

        Args:
            branch_id: The branch to execute
            executor_func: Function that executes steps (e.g., _execute_step)
            context: Phase context (will be copied for branch)

        Returns:
            Branch execution result
        """
        branch = self.branches.get(branch_id)
        if not branch:
            raise ValueError(f"Branch {branch_id} not found")

        print(f"\n{'='*60}")
        print(f"EXECUTING BRANCH: {branch.branch_name}")
        print(f"{'='*60}\n")

        # Copy context for this branch
        branch_context = context.copy()
        branch_context.branch_id = branch_id

        # Add branch-specific guidance to context
        if branch.user_guidance:
            if not hasattr(branch_context, 'feedback_context'):
                branch_context.feedback_context = FeedbackContext()
            branch_context.feedback_context.branch_feedback[branch_id] = branch.user_guidance

        # Execute branch steps
        # The executor_func should be the step execution logic
        result = executor_func(branch_context)

        # Update branch status
        branch.status = BranchStatus.COMPLETED
        branch.comparison_metrics = result.get('metrics', {})

        return result

    def compare_branches(
        self,
        step_num: int,
        include_baseline: bool = True,
    ) -> Dict[str, Any]:
        """
        Compare all branches created from a specific step.

        Args:
            step_num: The step where branches diverged
            include_baseline: Whether to include the original (non-branched) result

        Returns:
            Comparison data structure
        """
        # Find all branches from this step
        relevant_branches = [
            b for b in self.branches.values()
            if self._get_step_from_node(b.created_from_node) == step_num
        ]

        if not relevant_branches:
            return {'error': f'No branches found for step {step_num}'}

        comparison = {
            'step': step_num,
            'branch_count': len(relevant_branches),
            'branches': {},
            'metrics_comparison': {},
            'recommendations': [],
        }

        # Collect data from each branch
        for branch in relevant_branches:
            branch_data = {
                'name': branch.branch_name,
                'approach': branch.alternative_approach,
                'status': branch.status.value,
                'created_at': branch.created_at.isoformat(),
                'execution_path': branch.execution_path,
                'metrics': branch.comparison_metrics,
            }

            # Get final result from last node in branch
            if branch.execution_path:
                last_node_id = branch.execution_path[-1]
                last_node = self.execution_graph.nodes.get(last_node_id)
                if last_node:
                    branch_data['result'] = last_node.result
                    branch_data['error'] = last_node.error

            comparison['branches'][branch.branch_id] = branch_data

        # Generate comparison metrics
        comparison['metrics_comparison'] = self._compare_branch_metrics(relevant_branches)

        # Generate recommendations
        comparison['recommendations'] = self._generate_branch_recommendations(relevant_branches)

        return comparison

    def select_branch(
        self,
        branch_id: str,
        reason: str = "User selected",
    ) -> None:
        """
        Mark a branch as the winning branch.
        Other branches from the same branch point will be abandoned.
        """
        branch = self.branches.get(branch_id)
        if not branch:
            raise ValueError(f"Branch {branch_id} not found")

        # Mark this branch as selected
        branch.status = BranchStatus.SELECTED
        branch.is_winning_branch = True

        # Abandon other branches from the same step
        step = self._get_step_from_node(branch.created_from_node)
        for other_branch in self.branches.values():
            if (other_branch.branch_id != branch_id and
                self._get_step_from_node(other_branch.created_from_node) == step and
                other_branch.status == BranchStatus.ACTIVE):
                other_branch.status = BranchStatus.ABANDONED

        self.active_branches.discard(branch_id)

        print(f"✓ Selected branch: {branch.branch_name}")
        print(f"  Reason: {reason}")

    def merge_branch_insights(
        self,
        branch_ids: List[str],
    ) -> str:
        """
        Merge insights from multiple branches into consolidated feedback.
        Useful when you want to take best ideas from multiple approaches.
        """
        insights = []

        for branch_id in branch_ids:
            branch = self.branches.get(branch_id)
            if not branch:
                continue

            insights.append(f"**From {branch.branch_name}:**")

            if branch.alternative_approach:
                insights.append(f"- Approach: {branch.alternative_approach}")

            # Extract key learnings from branch execution
            if branch.execution_path:
                for node_id in branch.execution_path:
                    node = self.execution_graph.nodes.get(node_id)
                    if node and node.user_feedback:
                        for feedback_item in node.user_feedback:
                            insights.append(f"- {feedback_item.get('feedback', '')}")

        merged = "\n".join(insights)

        print(f"✓ Merged insights from {len(branch_ids)} branches")

        return merged

    def _find_node_for_step(self, step_num: int) -> Optional[str]:
        """Find the execution node corresponding to a step number."""
        for node_id, node in self.execution_graph.nodes.items():
            if node.type == NodeType.STEP and node.metadata.get('step_num') == step_num:
                return node_id
        return None

    def _get_step_from_node(self, node_id: str) -> Optional[int]:
        """Extract step number from a node."""
        node = self.execution_graph.nodes.get(node_id)
        if node:
            return node.metadata.get('step_num')
        return None

    def _compare_branch_metrics(self, branches: List[BranchMetadata]) -> Dict[str, Any]:
        """Compare metrics across branches."""
        # Simplified comparison - real implementation would be more sophisticated
        metric_names = set()
        for branch in branches:
            metric_names.update(branch.comparison_metrics.keys())

        comparison = {}
        for metric_name in metric_names:
            values = {}
            for branch in branches:
                if metric_name in branch.comparison_metrics:
                    values[branch.branch_id] = branch.comparison_metrics[metric_name]
            comparison[metric_name] = values

        return comparison

    def _generate_branch_recommendations(self, branches: List[BranchMetadata]) -> List[str]:
        """Generate recommendations for branch selection."""
        recommendations = []

        # Check completion status
        completed = [b for b in branches if b.status == BranchStatus.COMPLETED]
        failed = [b for b in branches if b.status == BranchStatus.FAILED]

        if len(completed) == 1:
            recommendations.append(
                f"✓ Only one branch completed successfully: {completed[0].branch_name}"
            )
        elif len(completed) > 1:
            recommendations.append(
                f"⚡ {len(completed)} branches completed. Compare metrics to select best approach."
            )

        if failed:
            recommendations.append(
                f"⚠ {len(failed)} branches failed: {', '.join(b.branch_name for b in failed)}"
            )

        # Compare metrics (simplified)
        if len(completed) >= 2:
            # Example: Compare execution time if available
            times = []
            for branch in completed:
                if 'execution_time' in branch.comparison_metrics:
                    times.append((branch, branch.comparison_metrics['execution_time']))

            if times:
                fastest = min(times, key=lambda x: x[1])
                recommendations.append(
                    f"⚡ Fastest execution: {fastest[0].branch_name} ({fastest[1]:.2f}s)"
                )

        return recommendations
```

#### 2. Integrate Branching with Control Phase

**File:** `cmbagent/phases/hitl_control.py`

**Add to HITLControlPhase:**
```python
class HITLControlPhase(Phase):

    def __init__(self, config: HITLControlPhaseConfig = None):
        # ... existing init ...
        self.branch_manager: Optional[BranchManager] = None

    async def execute(self, context: PhaseContext) -> PhaseResult:
        # ... existing setup ...

        # Initialize branch manager
        if not hasattr(context, 'execution_graph'):
            context.execution_graph = ExecutionGraph()
        self.branch_manager = BranchManager(context.execution_graph)

        # ... rest of execution ...

        # In step execution loop, after step review:
        if self.config.approval_mode in ["after_step", "both"]:
            review_result = await self._request_step_review(
                approval_manager,
                context,
                step,
                step_num,
                step_result,
                manager
            )

            # Handle branch request
            if isinstance(review_result, dict) and review_result.get('action') == 'branch':
                branch_name = review_result.get('branch_name', f'Alternative {step_num}')
                branch_approach = review_result.get('approach', '')
                branch_guidance = review_result.get('guidance', '')

                # Create branch
                branch_id = self.branch_manager.create_branch_from_step(
                    step_num=step_num,
                    branch_name=branch_name,
                    alternative_approach=branch_approach,
                    user_guidance=branch_guidance,
                )

                # Ask user if they want to execute branch now or continue
                should_execute_branch = await self._ask_branch_execution_preference(
                    approval_manager,
                    branch_id,
                    step_num,
                )

                if should_execute_branch:
                    # Execute branch in parallel or sequentially
                    branch_result = await self._execute_branch(
                        branch_id,
                        step_num,
                        context,
                        manager,
                    )

                    # Show comparison
                    comparison = self.branch_manager.compare_branches(step_num)

                    # Let user select winning branch
                    selected_branch = await self._select_winning_branch(
                        approval_manager,
                        comparison,
                    )

                    if selected_branch:
                        self.branch_manager.select_branch(selected_branch)

    async def _execute_branch(
        self,
        branch_id: str,
        step_num: int,
        context: PhaseContext,
        manager: PhaseExecutionManager,
    ) -> Dict[str, Any]:
        """Execute a branch independently."""
        def executor(branch_context):
            # This is similar to normal step execution
            # but with branch context
            result = self._execute_single_step(
                step_num,
                branch_context,
                manager,
                branch_id=branch_id,
            )
            return result

        return self.branch_manager.execute_branch(
            branch_id,
            executor,
            context,
        )

    async def _select_winning_branch(
        self,
        approval_manager,
        comparison: Dict[str, Any],
    ) -> Optional[str]:
        """Present branch comparison and let user select winner."""
        message = self._format_branch_comparison(comparison)

        branch_ids = list(comparison['branches'].keys())
        options = [f"select_{bid}" for bid in branch_ids]
        options.append("merge_insights")
        options.append("continue_baseline")

        approval_request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"branch_selection_{comparison['step']}",
            checkpoint_type="branch_selection",
            context_snapshot=comparison,
            message=message,
            options=options,
        )

        resolved = await approval_manager.wait_for_approval_async(
            str(approval_request.id),
            timeout_seconds=1800,
        )

        if resolved.resolution.startswith("select_"):
            return resolved.resolution.replace("select_", "")
        elif resolved.resolution == "merge_insights":
            # Merge insights from all branches
            merged = self.branch_manager.merge_branch_insights(branch_ids)
            # Add merged insights as feedback
            self._accumulated_feedback += f"\n\n## Branch Insights\n{merged}"
            return None
        else:
            # Continue with baseline
            return None
```

#### 3. UI Integration for Branching

**File:** `cmbagent-ui/components/BranchingPanel.tsx` (NEW FILE)

```typescript
interface BranchingPanelProps {
  stepNum: number;
  branches: BranchMetadata[];
  onCreateBranch: (branchName: string, approach: string, guidance: string) => void;
  onCompareBranches: () => void;
  onSelectBranch: (branchId: string) => void;
}

export function BranchingPanel({
  stepNum,
  branches,
  onCreateBranch,
  onCompareBranches,
  onSelectBranch,
}: BranchingPanelProps) {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [branchName, setBranchName] = useState('');
  const [approach, setApproach] = useState('');
  const [guidance, setGuidance] = useState('');

  const handleCreate = () => {
    onCreateBranch(branchName, approach, guidance);
    setShowCreateForm(false);
    // Reset form
  };

  return (
    <div className="branching-panel">
      <h3>Step {stepNum} - Branch Management</h3>

      {/* Create Branch Button */}
      <button onClick={() => setShowCreateForm(true)}>
        + Create Alternative Branch
      </button>

      {/* Create Branch Form */}
      {showCreateForm && (
        <div className="branch-form">
          <input
            placeholder="Branch name (e.g., 'Try ML approach')"
            value={branchName}
            onChange={(e) => setBranchName(e.target.value)}
          />
          <textarea
            placeholder="Alternative approach description"
            value={approach}
            onChange={(e) => setApproach(e.target.value)}
          />
          <textarea
            placeholder="Guidance for this branch (optional)"
            value={guidance}
            onChange={(e) => setGuidance(e.target.value)}
          />
          <button onClick={handleCreate}>Create Branch</button>
          <button onClick={() => setShowCreateForm(false)}>Cancel</button>
        </div>
      )}

      {/* Active Branches */}
      {branches.length > 0 && (
        <div className="branch-list">
          <h4>Active Branches:</h4>
          {branches.map(branch => (
            <div key={branch.branch_id} className="branch-item">
              <span className="branch-name">{branch.branch_name}</span>
              <span className="branch-status">{branch.status}</span>
              <button onClick={() => onSelectBranch(branch.branch_id)}>
                Select as Main
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Compare Button */}
      {branches.length > 1 && (
        <button onClick={onCompareBranches}>
          Compare {branches.length} Branches
        </button>
      )}
    </div>
  );
}
```

---

## Integration & Interactions

### How Feedback, Redo, and Branching Work Together

#### Scenario 1: Feedback-Guided Redo

```
Step 2 executes → User unsatisfied
  ↓
User provides feedback: "Use JSON format instead of XML"
  ↓
User clicks "Redo"
  ↓
Feedback is accumulated
  ↓
Step 2 re-executes with feedback injected into agents
  ↓
Agents see: "Previous attempt feedback: Use JSON format instead of XML"
  ↓
Step 2 completes with JSON format → Success
```

#### Scenario 2: Branch Comparison with Feedback

```
Step 3: Data processing
  ↓
User: "I want to try two approaches"
  ↓
Branch A: Use Pandas (User guidance: "Optimize for speed")
Branch B: Use Polars (User guidance: "Optimize for memory")
  ↓
Both branches execute in parallel
  ↓
System compares: Branch A (faster), Branch B (less memory)
  ↓
User reviews comparison, provides feedback:
  "Speed is more important for our use case"
  ↓
User selects Branch A
  ↓
Branch A feedback propagates to Step 4:
  "Selected fast processing approach. Continue optimizing for speed."
```

#### Scenario 3: Rollback, Redo, and Branch

```
Step 1 → Step 2 → Step 3 → Step 4 (discovers step 2 was wrong)
  ↓
User: "Go back to Step 2"
  ↓
System restores context at Step 2
  ↓
User: "Redo Step 2, but I want to try two different fixes"
  ↓
Branch A: Fix with approach A (User feedback: "Use validation")
Branch B: Fix with approach B (User feedback: "Use sanitization")
  ↓
Both branches execute Steps 2-4
  ↓
Compare final results
  ↓
Branch B wins
  ↓
Continue from Branch B's Step 4
```

### Data Flow Diagram

```
┌─────────────────────────────────────────────┐
│            User Interactions                 │
│  • Provide feedback                         │
│  • Request redo                             │
│  • Create branch                            │
│  • Select branch                            │
└────────────────┬────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────┐
│         Approval Manager                     │
│  • Collect user input                       │
│  • Create approval requests                  │
│  • Resolve approvals                        │
└────────────────┬────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────┐
│       Workflow Coordinator                   │
│  • Route actions to appropriate handler     │
│  • Feedback → FeedbackAccumulator           │
│  • Redo → RedoHandler                       │
│  • Branch → BranchManager                   │
└──────┬──────────────┬──────────────┬────────┘
       ↓              ↓              ↓
┌─────────────┐  ┌──────────┐  ┌────────────┐
│  Feedback   │  │   Redo   │  │  Branch    │
│ Accumulator │  │ Handler  │  │  Manager   │
└──────┬──────┘  └────┬─────┘  └──────┬─────┘
       ↓              ↓                ↓
       └──────────────┴────────────────┘
                      ↓
           ┌──────────────────────┐
           │  Execution Graph     │
           │  • Nodes             │
           │  • Branches          │
           │  • Context           │
           └──────────┬───────────┘
                      ↓
           ┌──────────────────────┐
           │  Phase Executors     │
           │  • Planning          │
           │  • Control           │
           └──────────┬───────────┘
                      ↓
           ┌──────────────────────┐
           │     CMBAgent         │
           │  (with feedback)     │
           └──────────────────────┘
```

### State Management

```python
class WorkflowState:
    """
    Central state management for workflow execution.
    Coordinates feedback, redo, and branching.
    """

    def __init__(self):
        self.execution_graph = ExecutionGraph()
        self.feedback_context = FeedbackContext()
        self.branch_manager = BranchManager(self.execution_graph)
        self.current_node_id: Optional[str] = None
        self.redo_stack: List[str] = []  # For rollback

    def handle_feedback(
        self,
        feedback: str,
        source: str,
        step: Optional[int] = None,
        branch: Optional[str] = None,
    ):
        """Handle new user feedback."""
        self.feedback_context.add_feedback(
            feedback=feedback,
            source=source,
            step=step,
            branch=branch,
        )

        # Mark feedback as needing injection
        # Will be picked up by next execution

    def handle_redo(
        self,
        step_num: int,
        with_feedback: Optional[str] = None,
    ) -> str:
        """Handle redo request for a step."""
        current_node = self.execution_graph.nodes[self.current_node_id]

        # Add redo feedback if provided
        if with_feedback:
            self.handle_feedback(
                feedback=with_feedback,
                source="redo_guidance",
                step=step_num,
            )

        # Increment attempt counter
        current_node.attempts += 1

        # Return node to re-execute
        return self.current_node_id

    def handle_branch(
        self,
        step_num: int,
        branch_name: str,
        approach: str,
        guidance: Optional[str] = None,
    ) -> str:
        """Handle branch creation request."""
        branch_id = self.branch_manager.create_branch_from_step(
            step_num=step_num,
            branch_name=branch_name,
            alternative_approach=approach,
            user_guidance=guidance,
        )

        # Add branch guidance as feedback
        if guidance:
            self.handle_feedback(
                feedback=guidance,
                source="branch_guidance",
                step=step_num,
                branch=branch_id,
            )

        return branch_id

    def get_execution_context(
        self,
        step_num: int,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get complete execution context for a step.
        Includes accumulated feedback, parent context, and branch-specific data.
        """
        context = {
            'step_num': step_num,
            'branch_id': branch_id,
        }

        # Add accumulated feedback
        context['feedback'] = self.feedback_context.get_accumulated_for_step(
            phase="control",
            step=step_num,
            branch=branch_id,
        )

        # Add parent context from execution graph
        if self.current_node_id:
            path = self.execution_graph.get_execution_path(self.current_node_id)
            if path:
                parent_context = path[-1].context_snapshot
                context['parent'] = parent_context

        # Add branch-specific context
        if branch_id:
            branch = self.branch_manager.branches.get(branch_id)
            if branch:
                context['branch_approach'] = branch.alternative_approach
                context['branch_guidance'] = branch.user_guidance

        return context
```

---

## Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)

**Priority: 🔴 Critical**

1. **Fix Control Phase Feedback Injection**
   - File: `cmbagent/phases/hitl_control.py`
   - Add feedback injection after CMBAgent creation
   - Est: 2-3 hours

2. **Fix Step-Level Redo**
   - File: `cmbagent/phases/hitl_control.py`
   - Convert for loop to while loop
   - Add redo counter and limits
   - Est: 4-6 hours

3. **Fix Planning Phase Early Exit**
   - File: `cmbagent/phases/hitl_planning.py`
   - Adjust approval logic to support iterative refinement
   - Est: 2-3 hours

### Phase 2: Core Infrastructure (Week 2)

**Priority: 🟡 Important**

1. **Create Execution Graph**
   - New file: `cmbagent/execution/graph.py`
   - Implement ExecutionNode and ExecutionGraph classes
   - Integrate with existing DAG tracker
   - Est: 1-2 days

2. **Create Feedback System**
   - New file: `cmbagent/execution/feedback.py`
   - Implement FeedbackContext and FeedbackCollector
   - Integrate with phases
   - Est: 1 day

3. **Add Phase-Level Redo**
   - File: `cmbagent/workflows/composer.py`
   - Modify phase execution loop
   - Add redo request handling
   - Est: 1 day

### Phase 3: Branching System (Week 3-4)

**Priority: 🟢 Enhancement**

1. **Create Branch Manager**
   - New file: `cmbagent/execution/branching.py`
   - Implement BranchManager and metadata classes
   - Est: 2-3 days

2. **Integrate with Control Phase**
   - File: `cmbagent/phases/hitl_control.py`
   - Add branch creation UI
   - Implement branch execution logic
   - Add branch comparison
   - Est: 2-3 days

3. **UI Components**
   - New file: `cmbagent-ui/components/BranchingPanel.tsx`
   - Create branch visualization
   - Add branch comparison UI
   - Est: 2-3 days

### Phase 4: Testing & Polish (Week 5)

1. **Integration Testing**
   - Test feedback →redo → branching flows
   - Test rollback scenarios
   - Test branch comparison and selection
   - Est: 3-5 days

2. **Documentation**
   - User guide for branching
   - API documentation
   - Example workflows
   - Est: 2-3 days

3. **Performance Optimization**
   - Optimize context copying for branches
   - Add caching for branch comparisons
   - Est: 1-2 days

---

## Code Examples

### Example 1: Complete Flow with Feedback, Redo, and Branching

```python
# User starts workflow
workflow = hitl_interactive_workflow(
    task="Build a data processing pipeline",
    max_human_iterations=3,
    approval_mode="both",
)

# Planning Phase
# Iteration 1: Generate plan
# User: "Add more validation steps" (revise)
# Iteration 2: Generate revised plan
# User: "Perfect!" (approve)

# Control Phase
# Step 1: Data ingestion
# User: (before-step) "Make sure to handle UTF-8 encoding"
# [feedback injected into agent]
# Step 1 executes with encoding consideration
# User: (after-step) "Good!" (continue)

# Step 2: Data validation
# User: (before-step) "I want to try two validation approaches"
# User: (create branch A) "Use Pydantic schemas"
# User: (create branch B) "Use Cerberus validators"
# [Both branches execute]
# [System shows comparison: Branch A faster, Branch B more flexible]
# User: "Select Branch A" (optimizing for speed)

# Step 3: Data transformation
# [executes with context from Branch A]
# User: (after-step) "The output format is wrong" (redo)
# User provides feedback: "Use ISO date format"
# [feedback injected]
# Step 3 re-executes with new guidance
# User: "Excellent!" (continue)

# Step 4: Data export
# [executes with accumulated feedback from all previous steps]
# Complete!
```

### Example 2: Rollback and Branch

```python
# Workflow in progress
# Step 1 → Step 2 → Step 3 → Step 4 [issue discovered]

# User realizes Step 2's approach was fundamentally wrong
user_action = {
    'action': 'rollback_and_branch',
    'rollback_to_step': 2,
    'branches': [
        {
            'name': 'Try SQL approach',
            'approach': 'Use SQL queries for filtering',
            'guidance': 'Focus on performance',
        },
        {
            'name': 'Try pandas approach',
            'approach': 'Use pandas DataFrame operations',
            'guidance': 'Focus on flexibility',
        }
    ]
}

# System:
# 1. Saves current state as checkpoint
# 2. Rolls back to Step 2
# 3. Creates two branches from Step 2
# 4. Executes both branches through Steps 2-4
# 5. Compares results
# 6. User selects winner
# 7. Continues from winning branch
```

### Example 3: API Usage

```python
from cmbagent.execution import WorkflowState, BranchManager
from cmbagent.workflows import hitl_interactive_workflow

# Initialize
state = WorkflowState()

# Add workflow-level feedback
state.handle_feedback(
    feedback="Prioritize code quality over speed",
    source="workflow_start",
)

# During execution, handle user actions
if user_action == "redo":
    state.handle_redo(
        step_num=current_step,
        with_feedback=user_feedback,
    )

if user_action == "branch":
    branch_id = state.handle_branch(
        step_num=current_step,
        branch_name=user_input['branch_name'],
        approach=user_input['approach'],
        guidance=user_input['guidance'],
    )

    # Execute branch
    branch_result = await execute_branch(branch_id)

    # Compare
    comparison = state.branch_manager.compare_branches(current_step)

    # Present to user
    present_comparison_ui(comparison)

    # Get selection
    selected = await get_user_selection()
    state.branch_manager.select_branch(selected)

# Get context for next execution
context = state.get_execution_context(
    step_num=next_step,
    branch_id=active_branch,
)

# Context includes all accumulated feedback
inject_feedback_into_agents(context['feedback'])
```

---

## Testing Strategy

### Unit Tests

```python
# test_feedback_accumulation.py
def test_feedback_accumulation():
    """Test that feedback accumulates correctly across steps."""
    feedback_ctx = FeedbackContext()

    # Add feedback at different points
    feedback_ctx.add_workflow_feedback("Use async/await")
    feedback_ctx.add_step_feedback(1, "Handle edge cases")
    feedback_ctx.add_step_feedback(2, "Add logging")

    # Get accumulated feedback for step 3
    accumulated = feedback_ctx.get_accumulated_for_step("control", 3, None)

    assert "async/await" in accumulated
    assert "edge cases" in accumulated
    assert "logging" in accumulated


# test_redo_logic.py
def test_step_redo_increments_counter():
    """Test that redo increments attempt counter."""
    node = ExecutionNode(id="step_1", type=NodeType.STEP, attempts=0)

    # First redo
    node.attempts += 1
    assert node.attempts == 1

    # Second redo
    node.attempts += 1
    assert node.attempts == 2


def test_redo_respects_max_limit():
    """Test that redo stops at max attempts."""
    max_redos = 3
    step_redo_counts = {}
    step_num = 1

    for _ in range(5):  # Try more than max
        current = step_redo_counts.get(step_num, 0)
        if current >= max_redos:
            break
        step_redo_counts[step_num] = current + 1

    assert step_redo_counts[step_num] == max_redos


# test_branching.py
def test_branch_creation():
    """Test creating a branch from a step."""
    graph = ExecutionGraph()
    branch_mgr = BranchManager(graph)

    # Create parent node
    node = graph.create_node(NodeType.STEP, metadata={'step_num': 2})

    # Create branch
    branch_id = branch_mgr.create_branch_from_step(
        step_num=2,
        branch_name="Alternative",
        alternative_approach="Try different algorithm",
    )

    assert branch_id in branch_mgr.branches
    assert branch_mgr.branches[branch_id].branch_name == "Alternative"


def test_branch_comparison():
    """Test comparing multiple branches."""
    graph = ExecutionGraph()
    branch_mgr = BranchManager(graph)

    # Create branches
    branch_a = branch_mgr.create_branch_from_step(2, "A", "Approach A")
    branch_b = branch_mgr.create_branch_from_step(2, "B", "Approach B")

    # Add metrics
    branch_mgr.branches[branch_a].comparison_metrics = {'time': 10, 'accuracy': 0.9}
    branch_mgr.branches[branch_b].comparison_metrics = {'time': 15, 'accuracy': 0.95}

    # Compare
    comparison = branch_mgr.compare_branches(2)

    assert len(comparison['branches']) == 2
    assert 'time' in comparison['metrics_comparison']
```

### Integration Tests

```python
# test_hitl_control_feedback.py
@pytest.mark.asyncio
async def test_feedback_injection_in_control_phase():
    """Test that feedback is properly injected into agents."""
    phase = HITLControlPhase(config=HITLControlPhaseConfig())

    # Setup context with feedback
    context = PhaseContext(
        run_id="test",
        phase_id="control_test",
        task="Test task",
        work_dir="/tmp/test",
    )
    context.shared_state['hitl_feedback'] = "Use JSON format"
    context.shared_state['plan_steps'] = [
        {'sub_task': 'Step 1', 'sub_task_agent': 'engineer'}
    ]

    # Mock CMBAgent to capture injected instructions
    injected_instructions = []

    with patch('cmbagent.cmbagent.CMBAgent') as MockAgent:
        mock_instance = MockAgent.return_value
        mock_instance.inject_to_agents = lambda agents, instructions, mode: \
            injected_instructions.append(instructions)

        # Execute phase
        result = await phase.execute(context)

        # Verify feedback was injected
        assert len(injected_instructions) > 0
        assert "JSON format" in injected_instructions[0]


# test_redo_workflow.py
@pytest.mark.asyncio
async def test_step_redo_workflow():
    """Test complete step redo workflow."""
    # Setup
    workflow = hitl_interactive_workflow(
        task="Test redo",
        approval_mode="after_step",
        max_step_redos=2,
    )

    # Mock approval manager to simulate redo request
    mock_approval = MockApprovalManager()
    mock_approval.set_response("redo", feedback="Try a different approach")

    # Execute workflow
    result = await workflow.run(approval_manager=mock_approval)

    # Verify redo was performed
    assert result['step_results'][0]['attempts'] >= 2
    assert "different approach" in result['step_feedback']


# test_branching_workflow.py
@pytest.mark.asyncio
async def test_branch_creation_and_selection():
    """Test creating and selecting branches."""
    # Setup
    workflow = hitl_interactive_workflow(
        task="Test branching",
        approval_mode="after_step",
    )

    # Mock approval to request branching
    mock_approval = MockApprovalManager()
    mock_approval.set_response("branch", {
        'branch_name': 'Alternative A',
        'approach': 'Use ML',
        'guidance': 'Focus on accuracy',
    })

    # Execute
    result = await workflow.run(approval_manager=mock_approval)

    # Verify branch was created
    assert 'branches' in result
    assert len(result['branches']) >= 1
    assert result['branches'][0]['name'] == 'Alternative A'
```

### End-to-End Tests

```python
# test_complete_workflow.py
@pytest.mark.asyncio
@pytest.mark.e2e
async def test_complete_hitl_workflow_with_all_features():
    """
    Test complete workflow using feedback, redo, and branching.
    This simulates a real user session.
    """
    # Setup
    workflow_def = WorkflowDefinition(
        id="test_complete",
        name="Complete HITL Test",
        description="Test all HITL features",
        phases=[
            {
                "type": "hitl_planning",
                "config": {
                    "max_human_iterations": 3,
                    "require_explicit_approval": True,
                }
            },
            {
                "type": "hitl_control",
                "config": {
                    "approval_mode": "both",
                    "max_step_redos": 2,
                    "allow_branching": True,
                }
            }
        ]
    )

    # Mock user interactions
    user_scenario = [
        # Planning Phase
        ('planning_iter_1', 'revise', "Add more validation"),
        ('planning_iter_2', 'approve', None),

        # Control Phase
        ('step_1_before', 'approve', "Use UTF-8 encoding"),
        ('step_1_after', 'continue', None),
        ('step_2_before', 'approve', None),
        ('step_2_after', 'redo', "Output format is wrong"),
        ('step_2_after', 'continue', None),
        ('step_3_before', 'branch', {
            'branch_name': 'Try ML',
            'approach': 'Use machine learning',
        }),
        ('step_3_branch_compare', 'select_branch_1', None),
        ('step_4_before', 'approve', None),
        ('step_4_after', 'continue', None),
    ]

    mock_approval = ScenarioApprovalManager(user_scenario)

    # Execute
    executor = WorkflowExecutor(
        workflow=workflow_def,
        task="Build a data pipeline",
        work_dir="/tmp/test_workflow",
        api_keys={},
        approval_manager=mock_approval,
    )

    result = await executor.run()

    # Verify complete workflow
    assert result.phase_timings['total'] > 0
    assert 'planning_feedback_history' in result.shared_state
    assert len(result.shared_state['planning_feedback_history']) >= 1
    assert 'step_feedback' in result.shared_state
    assert 'branches' in result.shared_state

    # Verify feedback was used
    feedback_used = result.shared_state.get('feedback_injection_log', [])
    assert len(feedback_used) > 0

    # Verify redo occurred
    step_2_result = next(r for r in result['step_results'] if r['step'] == 2)
    assert step_2_result['attempts'] >= 2

    # Verify branch was created and selected
    branches = result.shared_state.get('branches', {})
    assert len(branches) >= 1
    assert any(b['is_winning_branch'] for b in branches.values())
```

---

## Conclusion

This unified implementation guide provides a comprehensive architecture for:

1. **Feedback System**: Ensures user guidance flows through all phases and steps
2. **Redo System**: Allows retry of steps/phases with improved approaches
3. **Branching System**: Enables exploration of alternative execution paths

### Key Benefits

✅ **User Control**: Maximum visibility and control over workflow execution
✅ **Flexibility**: Adapt to changing requirements mid-execution
✅ **Exploration**: Try multiple approaches and compare results
✅ **Persistence**: Feedback and context flow through entire workflow
✅ **Transparency**: Complete execution graph shows all decisions

### Implementation Priority

1. **🔴 Week 1**: Fix critical feedback and redo bugs
2. **🟡 Week 2-3**: Build core infrastructure (execution graph, feedback system)
3. **🟢 Week 4-5**: Add branching capabilities
4. **⚪ Week 6**: Testing, documentation, polish

### Next Steps

1. Review this architecture with team
2. Prioritize features based on user needs
3. Begin Phase 1 implementation (critical fixes)
4. Iterate based on user feedback

---

**Document Status**: Ready for Implementation
**Last Updated**: 2025-02-10
**Contact**: Development Team
