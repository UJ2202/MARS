# Unified Tracking System - Architecture Diagram

## Current State (Disconnected)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         WorkflowExecutor                             │
│                         (composer.py)                                │
└────────────┬────────────────────────────────────────────────────────┘
             │
             │ Creates PhaseContext with callbacks
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PhaseExecutionManager                           │
│                    (execution_manager.py)                            │
│                                                                       │
│  • Fires WorkflowCallbacks (step_start, step_complete, etc.)       │
│  • Creates DAG nodes per step in database                           │
│  • Gets DB session/repos from context.shared_state                  │
└────────────┬────────────────────────────────────────────────────────┘
             │
             │ Creates CMBAgent instances
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          CMBAgent                                    │
│                        (cmbagent.py)                                 │
│                                                                       │
│  ❌ PROBLEM: Creates its own isolated DB session/session_id        │
│  ❌ Lines 227-289: new get_db_session(), new session_id            │
│  ❌ Orphaned from parent workflow tracking                          │
│                                                                       │
│  ┌──────────────────────────────────────────────┐                  │
│  │         cmbagent.solve()                     │                   │
│  │    (AG2 agents execute here)                 │                   │
│  │                                               │                   │
│  │  • Agent calls, messages, tool calls         │                   │
│  │  • Code execution                             │                   │
│  │  • Handoffs                                   │                   │
│  │                                               │                   │
│  │  ❌ None of this is tracked!                 │                   │
│  └──────────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘

         DISCONNECTED INFRASTRUCTURE (exists but never used):

┌─────────────────────────────────────────────────────────────────────┐
│                     EventCaptureManager                              │
│                   (event_capture.py)                                 │
│                                                                       │
│  • capture_agent_call()                                             │
│  • capture_tool_call()                                               │
│  • capture_code_execution()                                          │
│  • capture_handoff()                                                 │
│                                                                       │
│  ❌ Never instantiated!                                             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      AG2 Hooks                                       │
│                    (ag2_hooks.py)                                    │
│                                                                       │
│  • patch_conversable_agent()                                         │
│  • patch_group_chat()                                                │
│  • install_ag2_hooks()                                               │
│                                                                       │
│  ❌ Never called!                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Future State (Unified) - After Implementation

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            WorkflowExecutor                               │
│                            (composer.py)                                  │
│                                                                            │
│  • Creates DB session, session_id, DAG repos                             │
│  • Stores in context.shared_state                                        │
│  • Creates WorkflowCallbacks (websocket + database)                      │
└────────────┬─────────────────────────────────────────────────────────────┘
             │
             │ PhaseContext (with shared DB session)
             │
             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         PhaseExecutionManager                             │
│                       (execution_manager.py)                              │
│                                                                            │
│  PHASE-LEVEL TRACKING:                                                   │
│  • Fires WorkflowCallbacks (step_start, step_complete, cost_update)     │
│  • Creates DAG nodes for each step                                        │
│  • Updates DAG node status (running → completed/failed)                  │
│                                                                            │
│  ✅ NEW: AGENT-LEVEL TRACKING:                                           │
│  • _setup_event_capture() → creates EventCaptureManager                 │
│  • set_event_captor(manager) → sets global singleton                    │
│  • install_ag2_hooks() → patches AG2 classes (idempotent)               │
│  • _update_event_capture_context() → sets node_id per step              │
│  • _flush_event_capture() → clears after phase completes                │
└────────────┬─────────────────────────────────────────────────────────────┘
             │
             │ Creates managed CMBAgent
             │
             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                            CMBAgent                                       │
│                          (cmbagent.py)                                    │
│                                                                            │
│  ✅ NEW: managed_mode=True                                               │
│  • Skips DB initialization (lines 227-289)                               │
│  • Uses parent_session_id and parent_db_session                          │
│  • No orphaned sessions!                                                  │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │              cmbagent.solve()                                  │     │
│  │         (AG2 agents execute here)                              │     │
│  │                                                                 │     │
│  │  ✅ Automatically tracked via monkey-patched methods:         │     │
│  │                                                                 │     │
│  │  • ConversableAgent.generate_reply() → capture_agent_call()   │     │
│  │  • ConversableAgent.send() → capture_message()                │     │
│  │  • GroupChat.select_speaker() → capture_handoff()             │     │
│  │  • [Code execution] → capture_code_execution()                │     │
│  │  • [Tool calls] → capture_tool_call()                         │     │
│  │                                                                 │     │
│  │  ✅ All events written to ExecutionEvent table                │     │
│  │  ✅ All events have correct run_id, node_id, step_id          │     │
│  └────────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────┘
             │
             │ Events captured by global singleton
             │
             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         EventCaptureManager                               │
│                        (event_capture.py)                                 │
│                                                                            │
│  ✅ NOW ACTIVE:                                                           │
│  • Created by PhaseExecutionManager per phase                            │
│  • set_context(node_id, step_id) → scopes events                        │
│  • capture_agent_call() → writes to ExecutionEvent                       │
│  • capture_tool_call() → writes to ExecutionEvent                        │
│  • capture_code_execution() → writes to ExecutionEvent                   │
│  • flush() → ensures all events persisted                                │
│  • close() → cleanup after phase                                         │
└──────────────────────────────────────────────────────────────────────────┘
             │
             │ Writes events to database
             │
             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Database (SQLAlchemy)                            │
│                                                                            │
│  ✅ UNIFIED DAG:                                                          │
│                                                                            │
│  WorkflowRun (run_id)                                                    │
│     │                                                                      │
│     ├─ DAGNode (planning) ──┬─ ExecutionEvent (plan_generated)          │
│     │                        └─ ExecutionEvent (agent_call: planner)     │
│     │                                                                      │
│     ├─ DAGNode (step_1) ──┬─ ExecutionEvent (agent_call: engineer)      │
│     │                      ├─ ExecutionEvent (tool_call: web_search)     │
│     │                      ├─ ExecutionEvent (code_exec: python)         │
│     │                      └─ ExecutionEvent (handoff: engineer→reviewer)│
│     │                                                                      │
│     ├─ DAGNode (step_2) ──┬─ ExecutionEvent (agent_call: researcher)    │
│     │   │                  └─ ExecutionEvent (message: researcher→...)   │
│     │   │                                                                 │
│     │   ✅ NEW: Sub-nodes (Stage 3):                                     │
│     │   ├─ DAGNode (sub_agent: web_surfer)                               │
│     │   │    └─ ExecutionEvent (tool_call: fetch_url)                    │
│     │   └─ DAGNode (sub_agent: retrieve_assistant)                       │
│     │        └─ ExecutionEvent (tool_call: search_docs)                  │
│     │                                                                      │
│     ├─ DAGNode (step_3) [FAILED]                                         │
│     │   │                                                                 │
│     │   ✅ NEW: Redo branch (Stage 3):                                   │
│     │   └─ DAGNode (branch_point: redo_1)                                │
│     │       └─ DAGNode (step_3_retry)                                    │
│     │           └─ ExecutionEvent (...)                                   │
│     │                                                                      │
│     └─ DAGNode (terminator)                                              │
│                                                                            │
│  ✅ COMPLETE TRACE: Phase → Step → Sub-agent → Tool call → Event       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Wire Up AG2 Hooks (Low-Level Capture)

```
BEFORE Stage 1:
┌─────────────────┐
│ CMBAgent.solve()│  ❌ No tracking
│                 │
│  AG2 agents     │  ❌ Agent calls invisible
│  execute here   │  ❌ Messages invisible
│                 │  ❌ Tool calls invisible
└─────────────────┘

AFTER Stage 1:
┌─────────────────────────────────────────────────────────────────┐
│                    PhaseExecutionManager                         │
│                                                                   │
│  manager._setup_event_capture()                                 │
│      ├─ Creates EventCaptureManager(db, run_id, session_id)    │
│      ├─ set_event_captor(manager) [global singleton]           │
│      └─ install_ag2_hooks() [idempotent, patches AG2]          │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AG2 (Monkey-patched)                          │
│                                                                   │
│  ConversableAgent.generate_reply()                              │
│      ├─ captor = get_event_captor()                            │
│      ├─ event_id = captor.capture_agent_call(...)              │
│      ├─ [ORIGINAL METHOD RUNS]                                  │
│      └─ captor.capture_agent_response(..., event_id)           │
│                                                                   │
│  ConversableAgent.send()                                         │
│      ├─ captor = get_event_captor()                            │
│      └─ captor.capture_message(sender, recipient, content)     │
│                                                                   │
│  GroupChat.select_speaker()                                      │
│      ├─ [ORIGINAL METHOD RUNS]                                  │
│      └─ captor.capture_handoff(from, to)                       │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼ All events flow to EventCaptureManager
             │
┌────────────────────────────────────────────────────────────────┐
│               ExecutionEvent Table (Database)                   │
│                                                                  │
│  run_id | node_id  | event_type  | agent_name  | inputs/outputs│
│  ────────────────────────────────────────────────────────────  │
│  abc123 | step_1   | agent_call  | engineer    | {...}         │
│  abc123 | step_1   | tool_call   | engineer    | {...}         │
│  abc123 | step_1   | message     | engineer    | {...}         │
│  abc123 | step_2   | agent_call  | researcher  | {...}         │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stage 2: managed_mode (Eliminate Orphaned Sessions)

```
BEFORE Stage 2:
┌──────────────────────────────────────────────────┐
│              PhaseExecutionManager                │
│  DB session: 0xABCD (from context)               │
│  Session ID: "session_parent"                    │
└──────────────┬───────────────────────────────────┘
               │
               │ Creates worker CMBAgent
               ▼
┌──────────────────────────────────────────────────┐
│                  CMBAgent                         │
│  ❌ Creates NEW db_session: 0xXYZ                │
│  ❌ Creates NEW session_id: "session_child"      │
│  ❌ Orphaned tracking!                           │
└──────────────────────────────────────────────────┘

Database:
  ├─ WorkflowRun (session_parent)  ← PhaseExecutionManager tracks this
  │   └─ DAGNode (step_1, step_2, ...)
  │
  └─ WorkflowRun (session_child)   ← CMBAgent creates this (ORPHANED!)
      └─ DAGNode (???) [Never connected to parent]


AFTER Stage 2:
┌──────────────────────────────────────────────────┐
│              PhaseExecutionManager                │
│  DB session: 0xABCD                              │
│  Session ID: "session_parent"                    │
└──────────────┬───────────────────────────────────┘
               │
               │ Creates managed CMBAgent
               │
               ▼
┌──────────────────────────────────────────────────┐
│                  CMBAgent                         │
│  ✅ managed_mode=True                            │
│  ✅ parent_db_session=0xABCD (reuses parent)    │
│  ✅ parent_session_id="session_parent"          │
│  ✅ NO orphaned sessions!                        │
│                                                   │
│  Lines 227-289 SKIPPED (DB init block)          │
└──────────────────────────────────────────────────┘

Database:
  └─ WorkflowRun (session_parent)  ← Single unified session!
      └─ DAGNode (planning)
      └─ DAGNode (step_1)
          └─ ExecutionEvent (agent_call: engineer)  ← Captured!
          └─ ExecutionEvent (tool_call: web_search) ← Captured!
      └─ DAGNode (step_2)
          └─ ExecutionEvent (...)
      └─ ...
```

---

## Stage 3: Branching + Sub-Nodes (Advanced DAG)

```
FLAT DAG (Before Stage 3):

planning → step_1 → step_2 → step_3 → terminator

All steps are top-level nodes. No visibility into:
  • Internal agent collaboration within a step
  • Redo attempts
  • Alternative execution paths


HIERARCHICAL DAG (After Stage 3):

planning
   │
   └─ ExecutionEvent (plan_generated)
   │
   ▼
step_1 (engineer task)
   │
   ├─ sub_agent: code_analyzer         ✅ NEW: Sub-nodes
   │   └─ ExecutionEvent (tool_call: analyze_file)
   │
   ├─ sub_agent: file_editor
   │   └─ ExecutionEvent (tool_call: edit_file)
   │
   └─ ExecutionEvent (agent_call: engineer)
   │
   ▼
step_2 (researcher task)
   │
   ├─ sub_agent: web_surfer            ✅ NEW: Sub-nodes
   │   └─ ExecutionEvent (tool_call: fetch_url)
   │
   └─ sub_agent: retrieve_assistant
       └─ ExecutionEvent (tool_call: search_docs)
   │
   ▼
step_3 (complex task) [FAILED ❌]
   │
   ├─ ExecutionEvent (error: timeout)
   │
   ├─ branch_point: redo_1              ✅ NEW: Redo branch
   │   │
   │   └─ step_3_retry_1 [SUCCESS ✅]
   │       └─ ExecutionEvent (...)
   │
   └─ [Original attempt archived]
   │
   ▼
terminator


Database Schema (Stage 3):

DAGNode:
  • id: UUID
  • run_id: FK → WorkflowRun
  • parent_node_id: FK → DAGNode (self-reference)  ✅ NEW
  • depth: Integer (0=top-level, 1=sub-node)       ✅ NEW
  • node_type: "planning" | "agent" | "sub_agent" | "branch_point" | ...
  • status: "pending" | "running" | "completed" | "failed"
  • meta: JSON (includes branch_name, hypothesis for branches)

DAGEdge:
  • from_node_id: FK → DAGNode
  • to_node_id: FK → DAGNode
  • dependency_type: "sequential" | "parallel" | "conditional"  ✅ NEW
  • condition: String (e.g., "branch_redo_1")                    ✅ NEW

Queries Enabled:
  1. Get all sub-nodes for step: WHERE parent_node_id = 'step_1'
  2. Get redo branches: WHERE node_type = 'branch_point'
  3. Get full execution tree: Recursive CTE on parent_node_id
  4. Get critical path: Filter successful branches, ignore failed redos
```

---

## Data Flow Example: Single Step Execution

```
1. User submits workflow
   ↓
2. WorkflowExecutor creates DB session, callbacks
   ↓
3. PhaseExecutionManager.start()
   ├─ Creates planning DAGNode
   ├─ Creates EventCaptureManager
   ├─ Installs AG2 hooks (once)
   └─ Invokes callbacks.invoke_phase_change("planning")
   ↓
4. Phase creates managed CMBAgent(managed_mode=True)
   ├─ Skips DB init
   └─ Uses parent's session
   ↓
5. cmbagent.solve() runs
   ├─ AG2 agent "planner" called
   │   ├─ Monkey-patched generate_reply() intercepts
   │   ├─ get_event_captor() → EventCaptureManager
   │   └─ capture_agent_call(agent="planner", message="...")
   │       └─ Writes ExecutionEvent to DB
   │
   ├─ Tool call: "web_search"
   │   ├─ Monkey-patched tool executor intercepts
   │   └─ capture_tool_call(agent="planner", tool="web_search")
   │       └─ Writes ExecutionEvent to DB
   │
   └─ Agent sends message to another agent
       ├─ Monkey-patched send() intercepts
       └─ capture_message(sender="planner", recipient="reviewer")
           └─ Writes ExecutionEvent to DB
   ↓
6. cmbagent.solve() completes
   ↓
7. PhaseExecutionManager.complete()
   ├─ Updates DAGNode status → "completed"
   ├─ Invokes callbacks.invoke_step_complete(...)
   ├─ Flushes EventCaptureManager
   ├─ Clears global event captor (set_event_captor(None))
   └─ Returns PhaseResult
   ↓
8. Database state:
   WorkflowRun (run_id=abc123)
    └─ DAGNode (id=node_1, type="planning", status="completed")
        ├─ ExecutionEvent (event_type="agent_call", agent="planner")
        ├─ ExecutionEvent (event_type="tool_call", agent="planner")
        └─ ExecutionEvent (event_type="message", sender="planner")
```

---

## Key Benefits of Unified System

### 1. Single Source of Truth
✅ All events flow to one database
✅ All events have correct run_id, node_id, step_id
✅ No orphaned sessions or isolated tracking

### 2. Complete Execution Trace
✅ Phase-level events (via WorkflowCallbacks)
✅ Step-level events (via PhaseExecutionManager)
✅ Agent-level events (via EventCaptureManager + AG2 hooks)
✅ Sub-agent events (via sub-nodes in DAG)

### 3. Branching Support
✅ Track redo attempts as branches
✅ Compare alternative execution paths
✅ Reconstruct full decision tree

### 4. Minimal Code Changes
✅ Leverage existing infrastructure (EventCaptureManager, AG2 hooks)
✅ PhaseExecutionManager handles everything automatically
✅ Phases don't need manual event capture code

### 5. Backward Compatible
✅ Default managed_mode=False preserves old behavior
✅ No breaking changes to public APIs
✅ Gradual rollout possible (Stage 1 → 2 → 3)

---

## Comparison: Before vs After

### Before (Disconnected)
```
Visibility:
  ✅ Phase starts/completes (via WorkflowCallbacks)
  ✅ Step starts/completes (via PhaseExecutionManager)
  ❌ Agent calls (invisible)
  ❌ Messages between agents (invisible)
  ❌ Tool calls (invisible)
  ❌ Code execution (invisible)
  ❌ Handoffs (invisible)

Tracking:
  ❌ Each CMBAgent creates orphaned DB session
  ❌ No unified DAG across phases
  ❌ EventCaptureManager exists but never used
  ❌ AG2 hooks exist but never installed

Debugging:
  ❌ Can't trace agent decisions
  ❌ Can't see why step failed
  ❌ Can't replay execution
```

### After (Unified)
```
Visibility:
  ✅ Phase starts/completes
  ✅ Step starts/completes
  ✅ Agent calls (with inputs/outputs)
  ✅ Messages between agents
  ✅ Tool calls (with arguments/results)
  ✅ Code execution (with code/result)
  ✅ Handoffs (with context)

Tracking:
  ✅ Single DB session for entire workflow
  ✅ Unified DAG with sub-nodes and branches
  ✅ EventCaptureManager active per phase
  ✅ AG2 hooks installed (idempotent)

Debugging:
  ✅ Full execution trace in database
  ✅ Query any event by run_id, node_id, agent
  ✅ Reconstruct entire execution tree
  ✅ Replay failed branches with different inputs
```
