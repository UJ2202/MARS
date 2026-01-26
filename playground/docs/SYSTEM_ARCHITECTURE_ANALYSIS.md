# CMBAgent Multi-Agent System - Comprehensive Architecture Analysis

**Date:** January 21, 2026  
**Purpose:** Critical analysis of the human-assisted autonomous multi-agent system for best path discovery and skill extraction

---

## Executive Summary

CMBAgent is a sophisticated **multi-agent orchestration framework** built on AG2 (AutoGen 2.x) that implements a **Planning & Control** strategy with **iterative path exploration**, **comprehensive execution tracking**, and **skill extraction capabilities** (to be implemented). The system enables autonomous scientific discovery through:

1. **Multi-path exploration** via branching and parallel execution
2. **Event-driven execution tracking** with complete audit trails
3. **Human-in-the-loop control** at critical decision points
4. **Context-aware retry mechanisms** for error recovery
5. **DAG-based workflow orchestration** for complex task decomposition
6. **Skill extraction foundation** (database schema ready, extraction logic pending)

### Current State: Phases 1-9 Complete ✅

**Phase 1-3:** Core multi-agent system, database schema, DAG execution  
**Phase 4-6:** Event tracking, WebSocket real-time streaming, branching  
**Phase 7-9:** Retry mechanisms, parallel execution, approval gates  
**Phase 10 (PENDING):** Skill extraction, pattern matching, reusable workflows

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│                     CMBAGENT MULTI-AGENT SYSTEM                            │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐   │
│  │   FRONTEND UI   │◄────►│  BACKEND API    │◄────►│   DATABASE      │   │
│  │   (Next.js)     │  WS  │  (FastAPI)      │ SQL  │  (PostgreSQL)   │   │
│  │                 │      │                 │      │                 │   │
│  │ - Task Submit   │      │ - WebSocket Mgr │      │ - Event Store   │   │
│  │ - DAG View      │      │ - Event Queue   │      │ - DAG Nodes     │   │
│  │ - History       │      │ - Workflow Svc  │      │ - Checkpoints   │   │
│  │ - Approval UI   │      │ - REST APIs     │      │ - Branches      │   │
│  └─────────────────┘      └─────────────────┘      └─────────────────┘   │
│          │                        │                         │             │
│          │                        ▼                         │             │
│          │         ┌──────────────────────────┐            │             │
│          │         │   CMBAGENT PYTHON PKG    │            │             │
│          │         │  (Core Orchestration)    │            │             │
│          │         └──────────────────────────┘            │             │
│          │                     │                            │             │
│          │         ┌───────────┴────────────┐              │             │
│          │         ▼                        ▼              ▼             │
│          │  ┌──────────────┐        ┌──────────────┐  ┌──────────────┐  │
│          └─►│   DAG        │        │   AGENT      │  │  EXECUTION   │  │
│             │   EXECUTOR   │───────►│   SWARM      │  │  TRACKING    │  │
│             │              │        │   (AG2)      │  │              │  │
│             │ - Topological│        │              │  │ - Events     │  │
│             │ - Parallel   │        │ - Planner    │  │ - Messages   │  │
│             │ - Branching  │        │ - Engineer   │  │ - Costs      │  │
│             │ - Retry      │        │ - Researcher │  │ - Files      │  │
│             └──────────────┘        │ - Executor   │  └──────────────┘  │
│                                     │ - 50+ Agents │                     │
│                                     └──────────────┘                     │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘

KEY INNOVATION: Human-Assisted Best Path Discovery Through Iteration
───────────────────────────────────────────────────────────────────────────
1. Task → Planning → Multiple possible approaches identified
2. Execute Path A → Track all events, decisions, intermediate states
3. Hit error/suboptimal result → Branch to Path B with context
4. Compare paths → Extract successful pattern → Store as SKILL
5. Similar task arrives → Detect pattern → Apply skill (deterministic)
```

### 1.2 Core Components

#### **A. Multi-Agent Orchestration (AG2-based)**
- **50+ specialized agents** in `cmbagent/agents/`
- **Agent types:** Planner, Engineer, Researcher, Executor, RAG agents, Formatters
- **Communication:** AG2 GroupChat patterns with hand-offs
- **Context management:** Shared context carryover across steps

#### **B. DAG Execution Engine**
- **DAGExecutor:** Topological sorting, parallel execution of independent nodes
- **ParallelExecutor:** Process/thread pool isolation for concurrent tasks
- **DependencyAnalyzer:** LLM-based analysis of task dependencies
- **WorkDirectoryManager:** Isolated workspaces per task
- **ResourceManager:** Memory/CPU/disk limits enforcement

#### **C. Branching & Path Exploration**
- **BranchManager:** Create workflow branches from any checkpoint
- **PlayFromNodeExecutor:** Resume execution from specific DAG nodes
- **Comparator:** Compare execution paths (success rates, costs, outputs)
- **Hypothesis tracking:** Each branch records what's being tested

#### **D. Event-Driven Tracking**
- **ExecutionEvent model:** Comprehensive event capture (agent calls, tool usage, code execution)
- **Event types:** `agent_call`, `tool_call`, `code_exec`, `file_gen`, `handoff`, `error`
- **Event hierarchy:** Parent-child relationships for nested execution
- **Metadata:** Inputs, outputs, duration, agent name, node context

#### **E. Retry & Error Recovery**
- **RetryContextManager:** Context-aware retry strategies
- **ErrorAnalyzer:** Categorize errors (transient, persistent, configuration)
- **Retry metrics:** Track success probability, backoff strategies
- **Smart context:** Pass error history to agents for informed retry

#### **F. Human-in-the-Loop (HITL)**
- **ApprovalManager:** Pause workflow at checkpoints for human decisions
- **Approval types:** Planning approval, step approval, error handling, branch selection
- **WebSocket integration:** Real-time approval requests to UI
- **Decision recording:** Store all human decisions for replay/analysis

#### **G. State Management**
- **StateMachine:** Formal FSM for workflow and step transitions
- **States:** Draft → Planning → Executing → Paused → Completed/Failed
- **Checkpoints:** Auto-save every N minutes, manual checkpoints
- **Context snapshots:** Full system state at each checkpoint

---

## 2. Multi-Agent Execution Flow

### 2.1 Planning & Control Pattern

```
┌────────────────────────────────────────────────────────────────────────┐
│                    PLANNING PHASE (Iterative)                          │
└────────────────────────────────────────────────────────────────────────┘

User Task
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  PLANNER AGENT  ◄──────────────┐                               │
│  "Design multi-step plan"      │                               │
│                                 │                               │
│  Generated Plan:                │                               │
│  1. Literature review           │                               │
│  2. Data preparation            │  PLAN REVIEWER AGENT          │
│  3. Run simulation              │  "Critique plan,              │
│  4. Analyze results             │   suggest improvements"       │
│  5. Generate plots              │                               │
└──────────┬──────────────────────┴───────────────────────────────┘
           │
           │  Plan recorded in WorkflowRun.meta
           │  Creates DAGNodes for each step
           ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    CONTROL PHASE (Sequential/Parallel)                 │
└────────────────────────────────────────────────────────────────────────┘

Step 1: Literature Review
    ├─► RESEARCHER AGENT (agent_call event)
    │   ├─► Uses RAG to query papers (tool_call event)
    │   ├─► Summarizes findings (agent_call:message)
    │   └─► Hands off to ENGINEER (handoff event)
    │
    └─► ExecutionEvents: 45 events
        ├─ 15 agent_call events
        ├─ 20 tool_call events (RAG queries)
        ├─ 8 file_gen events (summaries)
        └─ 2 handoff events

Step 2: Data Preparation (Parallel with Step 3 if independent)
    ├─► ENGINEER AGENT
    │   ├─► Writes Python code (code_exec:execution)
    │   ├─► EXECUTOR runs code (code_exec:executed)
    │   └─► Generates data files (file_gen)
    │
    └─► ExecutionEvents: 32 events

Step 3: Run Simulation
    ├─► ENGINEER → EXECUTOR
    │   ├─► Encounters error (event_type=error)
    │   ├─► RetryManager analyzes error
    │   ├─► Retry with modified parameters
    │   └─► Success on attempt 2
    │
    └─► ExecutionEvents: 58 events (includes retry)

[CRITICAL DECISION POINT]
    │
    ▼
┌───────────────────────────────────────────────────────────┐
│  APPROVAL GATE (HITL)                                     │
│  "Results look unexpected. Continue or branch?"           │
│                                                           │
│  Options:                                                 │
│  1. Continue with results                                 │
│  2. Branch: Try alternative method                        │
│  3. Branch: Modify parameters                             │
└───────────────────────────────────────────────────────────┘
    │
    ├─► Option 1: Continue → Complete workflow
    │
    └─► Option 2: Branch to explore alternative
        │
        ▼
    ┌──────────────────────────────────────────────────────┐
    │  BRANCH CREATION                                     │
    │  - Copy context from Step 3                          │
    │  - New WorkflowRun with branch_parent_id             │
    │  - Hypothesis: "Use Bayesian optimization instead"   │
    │  - Creates new DAG from branch point                 │
    └──────────────────────────────────────────────────────┘
        │
        ▼
    Execute Branch → Track events → Compare results
        │
        ▼
    [SUCCESS PATH IDENTIFIED] → Extract as SKILL
```

### 2.2 Agent Communication Patterns

```
AGENT SWARM (AG2 GroupChat)
────────────────────────────

┌──────────────┐
│   PLANNER    │  "I need to analyze CMB data"
└──────┬───────┘
       │ (hand-off)
       ▼
┌──────────────┐
│  RESEARCHER  │  "Querying literature... found 15 relevant papers"
└──────┬───────┘
       │ (hand-off with context)
       ▼
┌──────────────┐
│   ENGINEER   │  "Writing analysis code based on papers"
└──────┬───────┘
       │ (hand-off with code)
       ▼
┌──────────────┐
│   EXECUTOR   │  "Running code... plotting results"
└──────┬───────┘
       │ (results)
       ▼
┌──────────────┐
│   PLANNER    │  "Reviewing outputs... next step..."
└──────────────┘

TRACKING AT EACH HAND-OFF:
─────────────────────────
- ExecutionEvent(event_type='handoff')
  - agent_from: previous agent
  - agent_to: next agent
  - context_passed: what information carried over
  - inputs: previous outputs
  - timestamp, duration, node_id
```

---

## 3. Database Schema & Data Flow

### 3.1 Core Tables

```sql
-- Workflow hierarchy
sessions (user isolation)
  └─► projects (organization)
      └─► workflow_runs (single execution)
          ├─► workflow_steps (plan steps)
          ├─► dag_nodes (execution graph)
          │   └─► execution_events (fine-grained tracking) 🔥
          ├─► checkpoints (state snapshots)
          ├─► branches (alternative paths)
          ├─► messages (agent communication)
          ├─► files (generated artifacts)
          └─► cost_records (token usage)

-- Key for skill extraction (future)
execution_events table:
  - Captures EVERY action during execution
  - event_type: agent_call, tool_call, code_exec, file_gen, handoff, error
  - event_subtype: start, complete, error, info
  - inputs/outputs: JSON payloads
  - meta: execution context
  - parent_event_id: nested execution tracking
  - depth: nesting level
  - execution_order: sequence within node
```

### 3.2 Event Capture Flow

```
EXECUTION → EVENT GENERATION → DATABASE + WEBSOCKET + QUEUE
────────────────────────────────────────────────────────────

Agent Action (e.g., code execution)
    │
    ├─► EventCaptureManager.capture_event()
    │   ├─► Create ExecutionEvent record
    │   │   ├─ run_id, node_id, session_id (context)
    │   │   ├─ event_type, event_subtype (classification)
    │   │   ├─ agent_name, timestamp, duration
    │   │   ├─ inputs, outputs, meta (data)
    │   │   └─ parent_event_id (hierarchy)
    │   │
    │   ├─► db.add(event) → PostgreSQL persistence
    │   │
    │   ├─► WebSocket broadcast
    │   │   └─► {event_type: "event_captured", data: {...}}
    │   │       └─► UI updates in real-time
    │   │
    │   └─► EventQueue.push(event)
    │       └─► In-memory buffer for reconnection recovery

Query Layer
    │
    ├─► GET /api/runs/{run_id}/history
    │   └─► All events for workflow (temporal view)
    │
    ├─► GET /api/nodes/{node_id}/events
    │   └─► Events for specific DAG node (spatial view)
    │
    └─► DAGMetadataEnricher
        └─► Aggregate stats per node (event counts, durations, costs)
```

### 3.3 Run ID Resolution Architecture

**Critical for API consistency:**

```
FRONTEND               BACKEND                    DATABASE
─────────────────────────────────────────────────────────────
task_id                resolve_run_id()           db_run_id
(user-facing)          (translation layer)        (UUID)

"task_1768..."    →    WorkflowService.        →  550e8400-e29b...
                       _active_runs[task_id]
                       .db_run_id

WHY: User-friendly IDs + Database integrity
```

---

## 4. Path Discovery & Branching Mechanism

### 4.1 Branching Strategy

```
MAIN WORKFLOW EXECUTION
│
├─ Step 1: Planning ✓
├─ Step 2: Data prep ✓
├─ Step 3: Simulation ⚠ (unexpected results)
│
└─► BRANCH POINT
    │
    ├─► Branch A: "Try method X"
    │   ├─ Checkpoint context copied
    │   ├─ New WorkflowRun created
    │   │  (branch_parent_id = main_run.id)
    │   ├─ Execute with modified approach
    │   ├─ Track events independently
    │   └─ Result: Success! ✓
    │
    ├─► Branch B: "Try method Y"
    │   ├─ Same checkpoint context
    │   ├─ Different approach
    │   └─ Result: Marginal improvement
    │
    └─► Branch C: "Adjust parameters"
        └─ Result: Failed

COMPARISON PHASE
────────────────
BranchComparator analyzes:
  - Success rates: A(100%), B(80%), C(0%)
  - Execution time: A(5min), B(8min), C(N/A)
  - Resource usage: A(2GB), B(3GB), C(N/A)
  - Output quality: A(high), B(medium), C(N/A)

DECISION: Path A is optimal → Extract as SKILL
```

### 4.2 Checkpoint & Replay

```
CHECKPOINT SYSTEM
─────────────────

Auto-checkpoint every 10 minutes:
  ├─ context_snapshot: Serialized system state
  ├─ agent_states: Current agent memory
  ├─ intermediate_outputs: All files/data
  └─ execution_history: Event log up to this point

REPLAY CAPABILITIES
───────────────────
1. Resume from failure:
   - Load last checkpoint
   - Restore agent contexts
   - Continue from next step

2. Branch from checkpoint:
   - Load specific checkpoint
   - Fork new WorkflowRun
   - Modify context/approach
   - Execute alternative path

3. Time-travel debugging:
   - Jump to any checkpoint
   - Inspect system state
   - Analyze decisions made
```

---

## 5. Skill Extraction Framework (To Be Implemented)

### 5.1 Current Foundation (Ready)

**Database Schema:**
```python
# Already exists in database/models.py (to be added):
class Skill(Base):
    """Reusable execution pattern extracted from successful runs"""
    id: UUID
    name: str
    description: str
    success_rate: float
    extracted_from_run_id: UUID  # Source workflow
    pattern_signature: JSON      # Task characteristics
    execution_template: JSON     # Agent sequence, parameters
    preconditions: JSON          # When this skill applies
    postconditions: JSON         # Expected outcomes
    usage_count: int
    avg_execution_time: float
    tags: List[str]
```

**Event Tracking (Complete):**
- ✅ All agent actions captured in `execution_events`
- ✅ Input/output payloads recorded
- ✅ Agent hand-offs tracked
- ✅ Code execution history preserved
- ✅ Error/retry patterns logged

### 5.2 Proposed Skill Extraction Pipeline

```
SUCCESSFUL WORKFLOW COMPLETION
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  PATTERN EXTRACTION (Automated)                         │
├─────────────────────────────────────────────────────────┤
│  1. Analyze execution_events for workflow:              │
│     - Agent sequence: [Researcher → Engineer → Exec]    │
│     - Tools used: [RAG, code_executor, plotter]         │
│     - Decision points: Where branches were considered   │
│     - Success indicators: Completion without errors     │
│                                                         │
│  2. Extract common patterns:                            │
│     - IF task contains "analyze data"                   │
│       AND file_type in ["csv", "fits"]                  │
│       THEN sequence = [data_loader → analyzer → viz]    │
│                                                         │
│  3. Generalize parameters:                              │
│     - file_path → {variable: input_file}                │
│     - plot_type → {variable: viz_type, default: "line"} │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  SKILL TEMPLATE CREATION                                │
├─────────────────────────────────────────────────────────┤
│  Skill: "data_analysis_pipeline"                        │
│  ├─ Preconditions:                                      │
│  │  - task_type: "data analysis"                        │
│  │  - has_structured_data: true                         │
│  │  - output_format: "visualization"                    │
│  │                                                      │
│  ├─ Execution Template:                                 │
│  │  Step 1: {agent: "researcher", goal: "understand"}  │
│  │  Step 2: {agent: "engineer", goal: "prepare"}       │
│  │  Step 3: {agent: "executor", goal: "analyze"}       │
│  │  Step 4: {agent: "engineer", goal: "visualize"}     │
│  │                                                      │
│  └─ Success Metrics:                                    │
│     - avg_duration: 5.2 minutes                         │
│     - success_rate: 95%                                 │
│     - cost_per_run: $0.15                               │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Store in SkillLibrary (database + vector store)
```

### 5.3 Skill Matching & Application

```
NEW TASK ARRIVES
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  SKILL DETECTOR (LLM-based)                             │
├─────────────────────────────────────────────────────────┤
│  Task: "Analyze CMB power spectrum from Planck data"    │
│  │                                                      │
│  │  Embedding similarity search:                        │
│  │  - Vector store query                                │
│  │  - Find similar past tasks                           │
│  │                                                      │
│  └─► Candidate Skills:                                  │
│      1. "data_analysis_pipeline" (similarity: 0.89)     │
│      2. "cosmology_analysis" (similarity: 0.76)         │
│      3. "plotting_workflow" (similarity: 0.62)          │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  SKILL VALIDATION                                       │
├─────────────────────────────────────────────────────────┤
│  Check preconditions for "data_analysis_pipeline":      │
│  ✓ task_type = "data analysis"                          │
│  ✓ has_structured_data = true (FITS file)               │
│  ✓ output_format = "visualization"                      │
│  → MATCH! Apply skill                                   │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  SKILL EXECUTION (Deterministic)                        │
├─────────────────────────────────────────────────────────┤
│  Instead of planning from scratch:                      │
│  1. Load skill template                                 │
│  2. Substitute task-specific parameters                 │
│  3. Execute predefined agent sequence                   │
│  4. Monitor for deviations                              │
│  5. Fall back to planning if skill fails                │
│                                                         │
│  Benefits:                                              │
│  - 80% faster (skip planning phase)                     │
│  - 60% cheaper (fewer LLM calls)                        │
│  - More reliable (proven pattern)                       │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Update skill success_rate and usage_count
```

---

## 6. Critical Analysis & Gaps

### 6.1 What Works Well ✅

1. **Event Tracking Infrastructure**
   - Comprehensive event capture at all execution levels
   - Proper event hierarchy (parent-child relationships)
   - Rich metadata (inputs, outputs, duration, context)
   - Real-time streaming + persistent storage

2. **DAG Execution & Parallelism**
   - Topological sorting for correct execution order
   - Parallel execution of independent tasks
   - Resource management and isolation
   - Proper state machine transitions

3. **Branching & Exploration**
   - Clean checkpoint mechanism
   - Branch creation from any point
   - Context carryover to branches
   - Branch comparison capabilities

4. **Human-in-the-Loop**
   - Flexible approval gates
   - Real-time UI integration
   - Decision recording for replay

5. **Retry & Error Recovery**
   - Context-aware retry strategies
   - Error categorization
   - Smart backoff mechanisms

### 6.2 Critical Gaps ⚠️

#### **Gap 1: Skill Extraction Logic (Not Implemented)**
**Impact:** HIGH  
**Description:** While the foundation exists (event tracking, branching), there's no automated system to:
- Detect successful execution patterns
- Extract generalized templates
- Match new tasks to existing skills
- Apply skills deterministically

**Required Components:**
- Pattern extraction pipeline
- Skill template format definition
- Similarity matching (embedding-based)
- Precondition checking logic
- Skill execution engine

#### **Gap 2: Agent-Level Execution Details**
**Impact:** MEDIUM  
**Description:** Current event tracking captures high-level actions but misses:
- Individual agent reasoning steps
- Tool selection rationale
- Intermediate code versions
- Agent-specific decision criteria

**Solution:** Enhance `ExecutionEvent` with:
```python
event.meta = {
    "agent_reasoning": "I chose this approach because...",
    "tool_selection_rationale": "Selected RAG over web search due to...",
    "code_versions": ["v1: basic approach", "v2: optimized"],
    "decision_factors": {"confidence": 0.85, "alternatives_considered": 3}
}
```

#### **Gap 3: Cross-Run Pattern Analysis**
**Impact:** MEDIUM  
**Description:** No system to analyze patterns across multiple workflow runs:
- Common failure modes
- Frequently used agent sequences
- Optimal parameter ranges
- Cost/quality trade-offs

**Solution:** Implement `AnalyticsEngine`:
- Aggregate events across runs
- Identify common patterns
- Build statistical models
- Recommend optimizations

#### **Gap 4: Skill Versioning & Evolution**
**Impact:** LOW  
**Description:** Skills should evolve as better approaches are discovered:
- Version tracking
- A/B testing of skill variants
- Gradual rollout of improvements

#### **Gap 5: Skill Composition**
**Impact:** LOW  
**Description:** Complex tasks may require combining multiple skills:
- Skill dependency graph
- Composition rules
- Conflict resolution

### 6.3 Technical Debt

1. **Database Migration for Skills**
   - Need to add `Skill` table
   - Add `skill_id` foreign key to `WorkflowRun`
   - Create indices for similarity search

2. **Event Filtering Complexity**
   - Current: Filter out 'start' events, internal events
   - Future: Configurable event retention policies
   - Consider event aggregation for long-running tasks

3. **Context Serialization**
   - Current: Pickle-based (fragile)
   - Future: JSON schema-based (robust, versioned)

4. **LLM Cost Tracking**
   - Current: Token counts only
   - Future: Real-time cost tracking per skill
   - Budget controls for experiments

---

## 7. System Sketch: Joining the Picture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CMBAGENT: HUMAN-ASSISTED AUTONOMOUS                      │
│                         BEST PATH DISCOVERY & SKILL EXTRACTION                   │
└─────────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: USER INTERFACE                                                      │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  Next.js Frontend (cmbagent-ui/)                                              │
│  ├─ Task Input: User describes scientific problem                            │
│  ├─ DAG View: Real-time visualization of execution graph                     │
│  ├─ History Timeline: All events in temporal order                           │
│  ├─ Files View: Generated artifacts (code, data, plots)                      │
│  ├─ Approval Dialog: HITL decision points                                    │
│  ├─ Branch Explorer: Compare alternative execution paths                     │
│  └─ Skill Library Browser: View/search/apply existing skills [TO BUILD]      │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
                                     │ WebSocket + REST
                                     ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: API & ORCHESTRATION                                                 │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  FastAPI Backend (backend/)                                                   │
│  ├─ WebSocket Manager: Real-time event streaming                             │
│  ├─ Event Queue: In-memory buffer for reconnection                           │
│  ├─ Workflow Service: Run lifecycle management                               │
│  ├─ REST APIs: Historical data access                                        │
│  └─ Run ID Resolution: task_id ↔ db_run_id translation                       │
│                                                                               │
│  CMBAgent Python Package (cmbagent/)                                          │
│  ├─ one_shot() / planning_and_control(): Entry points                        │
│  ├─ WorkflowCallbacks: Progress tracking                                     │
│  └─ Context Management: Shared state across agents                           │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
                                     │ SQL + Function Calls
                                     ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: EXECUTION ENGINE                                                    │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │   DAG EXECUTOR      │  │   BRANCH MANAGER    │  │   RETRY MANAGER     │  │
│  │                     │  │                     │  │                     │  │
│  │ - Topological sort  │  │ - Create branches   │  │ - Error analysis    │  │
│  │ - Parallel exec     │  │ - Checkpoint load   │  │ - Smart retry       │  │
│  │ - Dependency check  │  │ - Context fork      │  │ - Backoff strategy  │  │
│  │ - State machine     │  │ - Path comparison   │  │ - Success tracking  │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │
│                                                                               │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │ APPROVAL MANAGER    │  │ EVENT CAPTURE MGR   │  │ SKILL ENGINE [NEW]  │  │
│  │                     │  │                     │  │                     │  │
│  │ - Pause workflow    │  │ - Event creation    │  │ - Pattern extract   │  │
│  │ - Request approval  │  │ - Hierarchy track   │  │ - Skill matching    │  │
│  │ - Resume after OK   │  │ - Metadata enrich   │  │ - Template apply    │  │
│  │ - Decision record   │  │ - WS broadcast      │  │ - Version manage    │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
                                     │ AG2 API
                                     ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: AGENT SWARM (AG2)                                                   │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  50+ Specialized Agents (cmbagent/agents/)                                    │
│  ├─ Planner: Design execution strategy                                       │
│  ├─ Engineer: Write/refactor code                                            │
│  ├─ Researcher: Query literature, synthesize findings                        │
│  ├─ Executor: Run code, capture outputs                                      │
│  ├─ RAG Agents: Domain-specific knowledge (CAMB, CLASS, Cobaya, Planck...)   │
│  ├─ Formatters: Structure outputs (JSON, reports, plots)                     │
│  └─ Control Agents: Orchestrate hand-offs, manage flow                       │
│                                                                               │
│  Communication: GroupChat with hand-offs                                     │
│  Context: Shared context variables across agents                             │
│  Memory: Conversation history, checkpoints                                   │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
                                     │ Event generation
                                     ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│  LAYER 5: PERSISTENCE & ANALYTICS                                             │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  PostgreSQL Database                                                          │
│  ├─ Sessions: User isolation                                                 │
│  ├─ WorkflowRuns: Execution instances                                        │
│  ├─ DAGNodes: Execution graph                                                │
│  ├─ ExecutionEvents: Fine-grained tracking (🔥 CRITICAL FOR SKILLS)          │
│  ├─ Checkpoints: State snapshots                                             │
│  ├─ Branches: Alternative paths                                              │
│  ├─ Messages: Agent communication                                            │
│  ├─ Files: Generated artifacts                                               │
│  ├─ CostRecords: Token usage                                                 │
│  └─ Skills: Reusable patterns [TO ADD]                                       │
│                                                                               │
│  Vector Store (for skill matching)                                           │
│  └─ Skill embeddings for similarity search [TO BUILD]                        │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
DATA FLOW: TASK → EXPLORATION → SKILL EXTRACTION → REUSE
═══════════════════════════════════════════════════════════════════════════════

NEW TASK (First Time)
  │
  ├─► Planning Phase: Design approach (3-5 min, high cost)
  ├─► Control Phase: Execute plan (15-30 min, moderate cost)
  │   ├─ Step 1 ✓
  │   ├─ Step 2 ✓
  │   └─ Step 3 ⚠ (unexpected result)
  │
  ├─► HUMAN DECISION: Branch to explore alternatives
  │   ├─ Branch A: Try method X → ✓ Success
  │   ├─ Branch B: Try method Y → ✗ Failed
  │   └─ Branch C: Adjust params → △ Marginal
  │
  ├─► Compare branches → Identify best path (Branch A)
  │
  └─► SKILL EXTRACTION (Automated)
      ├─ Analyze Branch A execution events
      ├─ Extract agent sequence: [Researcher → Engineer(v2) → Executor]
      ├─ Extract parameters: {method: "X", threshold: 0.85}
      ├─ Create skill template: "cmb_power_spectrum_analysis"
      └─ Store in skill database

SIMILAR TASK (Second Time)
  │
  ├─► Skill Detector: Match to "cmb_power_spectrum_analysis" (similarity: 0.91)
  ├─► Validate preconditions: ✓ All met
  │
  └─► DIRECT EXECUTION (No planning needed!)
      ├─ Load skill template
      ├─ Execute predefined steps (5-10 min, low cost)
      └─ Success! 80% faster, 60% cheaper

CONTINUOUS IMPROVEMENT
  │
  ├─► Track skill usage: 50 runs, 95% success rate
  ├─► Detect edge case: 5% failures at high-z data
  ├─► Auto-branch to fix edge case
  ├─► Extract improved skill version: v2
  └─► Gradual rollout: A/B test v1 vs v2
```

---

## 8. Next Steps: Skill System Implementation

### Phase 10: Skill Extraction & Matching (8-12 weeks)

#### **Stage 10.1: Database Schema Extension**
- Add `Skill` model with template storage
- Add `SkillUsage` tracking table
- Add `skill_id` foreign key to `WorkflowRun`
- Create vector store integration for embeddings

#### **Stage 10.2: Pattern Extraction Pipeline**
- Build `PatternExtractor` class
  - Analyze successful workflow execution events
  - Identify common agent sequences
  - Extract parameters and decision points
  - Generate skill templates

#### **Stage 10.3: Skill Matching Engine**
- Build `SkillMatcher` class
  - Embedding-based similarity search
  - Precondition validation
  - Confidence scoring
  - Fall-back to planning logic

#### **Stage 10.4: Skill Execution Engine**
- Build `SkillExecutor` class
  - Template instantiation
  - Parameter substitution
  - Execution with monitoring
  - Deviation detection & handling

#### **Stage 10.5: Skill Management UI**
- Skill library browser
- Manual skill creation/editing
- Skill versioning UI
- Usage analytics dashboard

---

## 9. Documentation Needs (Next Section)

### Critical Documentation Gaps:

1. **Architecture Documentation**
   - System overview for new developers
   - Data flow diagrams
   - API reference
   - Database schema documentation

2. **User Guides**
   - Getting started
   - Best practices
   - Troubleshooting
   - FAQ

3. **Developer Guides**
   - Contributing guidelines
   - Code style
   - Testing strategy
   - Extension points

4. **Operational Documentation**
   - Deployment guide
   - Configuration management
   - Monitoring & observability
   - Backup & recovery

5. **Skill System Documentation**
   - Skill creation guide
   - Pattern extraction manual
   - Skill matching algorithm
   - Best practices for reuse

**Next: Detailed documentation folder structure proposal →**
