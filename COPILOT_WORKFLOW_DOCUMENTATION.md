# CMBAgent Copilot Workflow - Complete Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Component Deep Dive](#component-deep-dive)
4. [Execution Flow](#execution-flow)
5. [HITL (Human-in-the-Loop) Mechanisms](#hitl-mechanisms)
6. [Known Issues & Gaps](#known-issues--gaps)
7. [Configuration Reference](#configuration-reference)

---

## Overview

The Copilot workflow is a **unified multi-agent orchestration system** that provides a flexible assistant capable of:
- Intelligent task routing based on complexity
- Dynamic phase invocation (phases as tools)
- Human-in-the-loop approval gates
- Conversational mode with human feedback in every turn
- Tool approval with session-level auto-allow

### Key Design Principles
- **Single Swarm Architecture**: All agents loaded into one unified swarm
- **Phases as Tools**: Agents can invoke phases dynamically (e.g., `invoke_planning_phase`)
- **Round Management**: Max rounds with pause/continue support
- **Intelligent Routing**: LLM-based task analysis via `copilot_control` agent

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Next.js)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  CopilotView.tsx ─────► WebSocketContext.tsx ─────► ApprovalChatPanel.tsx   │
│       │                        │                           │                │
│       │                        │ connect(taskId)           │                │
│       ▼                        ▼                           ▼                │
│  Submit Task ────────► ws://backend/ws/{task_id} ◄───── Resolve Approval    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ WebSocket
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            BACKEND (FastAPI)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  main.py                                                                    │
│     │                                                                       │
│     └──► @app.websocket("/ws/{task_id}")                                    │
│              │                                                              │
│              ▼                                                              │
│  websocket/handlers.py::websocket_endpoint()                                │
│              │                                                              │
│              ├──► Creates workflow run in DB                                │
│              │                                                              │
│              └──► execute_cmbagent_task() ◄─ execution/task_executor.py     │
│                        │                                                    │
│                        │ if mode == "copilot":                              │
│                        ▼                                                    │
│              ┌─────────────────────────────────────────┐                    │
│              │   cmbagent.workflows.copilot.copilot()  │                    │
│              └─────────────────────────────────────────┘                    │
│                        │                                                    │
│                        ▼                                                    │
│              ┌─────────────────────────────────────────┐                    │
│              │       SwarmOrchestrator                 │                    │
│              │  ┌─────────────────────────────────┐    │                    │
│              │  │  SwarmConfig                    │    │                    │
│              │  │  - max_rounds                   │    │                    │
│              │  │  - available_agents             │    │                    │
│              │  │  - enable_phase_tools           │    │                    │
│              │  │  - intelligent_routing          │    │                    │
│              │  │  - tool_approval                │    │                    │
│              │  │  - conversational               │    │                    │
│              │  └─────────────────────────────────┘    │                    │
│              │                                         │                    │
│              │  ┌─────────────────────────────────┐    │                    │
│              │  │  SwarmState                     │    │                    │
│              │  │  - DurableContext               │    │                    │
│              │  │  - conversation_history         │    │                    │
│              │  │  - phases_executed              │    │                    │
│              │  └─────────────────────────────────┘    │                    │
│              └─────────────────────────────────────────┘                    │
│                        │                                                    │
│                        ▼                                                    │
│              ┌─────────────────────────────────────────┐                    │
│              │       _execute_swarm_loop()             │                    │
│              │                                         │                    │
│              │  Routing Decision (copilot_control):    │                    │
│              │  ┌───────────────────────────────────┐  │                    │
│              │  │ route_type:                       │  │                    │
│              │  │  - "direct" → Agent execution     │  │                    │
│              │  │  - "clarify" → HITL checkpoint    │  │                    │
│              │  │  - "propose" → Present options    │  │                    │
│              │  │  - "phase" → Not used (deprecated)│  │                    │
│              │  └───────────────────────────────────┘  │                    │
│              └─────────────────────────────────────────┘                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Deep Dive

### 1. Entry Points

#### `cmbagent/workflows/copilot.py`
The main workflow entry point that wraps `SwarmOrchestrator`.

```python
def copilot(
    task: str,
    available_agents: List[str] = None,      # ["engineer", "researcher", ...]
    enable_planning: bool = True,             # Auto-plan complex tasks
    use_dynamic_routing: bool = True,         # LLM-based routing
    approval_mode: str = "after_step",        # HITL timing
    tool_approval: str = "none",              # Tool permission mode
    intelligent_routing: str = "balanced",    # Clarification behavior
    conversational: bool = False,             # Human in every turn
    approval_manager=None,                    # WebSocket approval manager
    ...
) -> Dict[str, Any]
```

#### `cmbagent/workflows/swarm_copilot.py`
Alternative entry point with similar API but slightly different defaults.

---

### 2. SwarmOrchestrator (`cmbagent/orchestrator/swarm_orchestrator.py`)

The core orchestration engine that manages:

#### SwarmConfig (lines 129-194)
```python
@dataclass
class SwarmConfig:
    max_rounds: int = 100                    # Max conversation rounds
    auto_continue: bool = False              # Auto-continue on max rounds
    available_agents: List[str] = [...]      # Agents to load
    enable_phase_tools: bool = True          # Phases as callable tools
    use_copilot_control: bool = True         # LLM-based routing
    intelligent_routing: str = "balanced"    # "aggressive"|"balanced"|"minimal"
    approval_mode: str = "after_step"        # HITL timing
    conversational: bool = False             # Human every turn
    tool_approval: str = "none"              # "prompt"|"auto_allow_all"|"none"
```

#### Execution Loop (lines 697-741)
```python
async def _execute_swarm_loop(self):
    if self._is_conversational:
        return await self._execute_conversational_loop()

    while self.state.status == SwarmStatus.RUNNING:
        if self.state.should_pause_for_continuation():
            return await self._handle_continuation()

        round_result = await self._execute_round()

        # Handle clarification flow
        if round_result.get('status') == 'clarification_needed':
            self.state.status = SwarmStatus.WAITING_INPUT
            return self._build_final_result(round_result)

        if self._is_task_complete(round_result):
            self.state.status = SwarmStatus.COMPLETED
            break

        self.state.increment_round()
```

#### Routing Decision (lines 1428-1517)
```python
async def _get_routing_decision(self, message: str) -> Dict[str, Any]:
    # Mode instruction based on intelligent_routing setting
    mode_guide = {
        'minimal': 'Use DIRECT mode: Prefer immediate action',
        'balanced': 'Use BALANCED mode: Prefer action, clarify only essential gaps',
        'aggressive': 'Use CAUTIOUS mode: Ask questions for ambiguity',
    }

    # Call copilot_control agent for analysis
    routing_result = await self._cmbagent.solve(...)

    return self._parse_routing_result(routing_result)
```

#### Heuristic Routing (lines 1519-1593)
When LLM routing fails or is disabled:
```python
def _heuristic_routing(self, message: str) -> Dict[str, Any]:
    # Detect vague patterns
    vague_patterns = ['fix it', 'make it work', 'improve this', ...]

    # Detect generic actions without specifics
    generic_actions = [('create', 'script'), ('write', 'code'), ...]

    # E.g., "write python script" with <= 5 words → clarify
    if action in words and target in words and word_count <= 5:
        return {
            'route_type': 'clarify',
            'clarifying_questions': [
                "What should this script do?",
                "What functionality do you need?",
            ],
            ...
        }
```

---

### 3. copilot_control Agent (`cmbagent/agents/copilot_control/copilot_control.yaml`)

The intelligent router that analyzes tasks:

```yaml
name: "copilot_control"

instructions: |
    You are the Copilot Control Agent - an intelligent task router.

    ## Decision Process
    1. Analyze the Task - What is being asked? How complex?
    2. Determine Complexity (0-100)
       - 0-30: Simple - single action
       - 31-60: Moderate - few steps
       - 61-100: Complex - multiple agents, requires planning

    3. Choose Route Type
       - one_shot: Task can be done in one go (PREFER THIS)
       - planned: Task needs planning (use sparingly)
       - clarify: Task is ambiguous, need more info
       - propose: Multiple valid approaches

    ## Important: Phases as Tools
    Agents have access to phase tools:
    - invoke_planning_phase(task, max_steps)
    - invoke_hitl_checkpoint(checkpoint_type, message)
    - invoke_idea_generation_phase(topic)
```

---

### 4. Phase Tools (`cmbagent/functions/phase_tools.py`)

Phases exposed as callable tools:

```python
def invoke_hitl_checkpoint_phase(
    checkpoint_type: str = "approval",    # "approval"|"review"|"confirm"
    message: str = "Please approve"
) -> str:
    """Invoke HITL checkpoint phase for human approval gate."""
    return json.dumps({
        "phase": "hitl_checkpoint",
        "config": {
            "checkpoint_type": checkpoint_type,
            "message": message,
        },
        "status": "phase_invocation_requested"
    })
```

**Important**: These functions return JSON indicating a phase should be invoked. The orchestrator must intercept and execute the actual phase.

---

### 5. Phase Registry (`cmbagent/phases/registry.py`)

Available phases:
- `planning` - Generate structured plans
- `control` - Execute plan steps
- `one_shot` - Single agent execution
- `hitl_checkpoint` - Human approval gates
- `hitl_planning` - Interactive planning with feedback
- `hitl_control` - Step execution with approval
- `idea_generation` - Brainstorming
- `copilot` - Flexible assistant

---

### 6. HITL Checkpoint Phase (`cmbagent/phases/hitl_checkpoint.py`)

```python
class HITLCheckpointPhase(Phase):
    async def execute(self, context: PhaseContext) -> PhaseResult:
        # Get approval manager from context
        approval_manager = context.shared_state.get('_approval_manager')

        if not approval_manager:
            # Auto-approve if no manager
            return PhaseResult(status=COMPLETED, ...)

        # Create approval request
        approval_request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=context.phase_id,
            checkpoint_type=self.config.checkpoint_type,
            message=message,
            options=["approve", "reject", "modify"],
        )

        # Wait for approval (blocking)
        resolved = await approval_manager.wait_for_approval_async(...)
```

---

### 7. HITL Handoffs (`cmbagent/handoffs/hitl.py`)

#### WebSocket Integration
```python
def configure_admin_for_websocket(admin_agent, approval_manager, run_id: str):
    """Override admin's get_human_input to use WebSocket."""

    def websocket_human_input_sync(prompt: str) -> str:
        # Create approval request
        approval_request = approval_manager.create_approval_request(...)

        # Wait for WebSocket approval (blocking)
        resolved = loop.run_until_complete(
            approval_manager.wait_for_approval_async(...)
        )

        if resolved.resolution in ["continue", "approved"]:
            return ""  # Continue
        elif resolved.resolution == "provide_instructions":
            return resolved.user_feedback
        else:
            return "TERMINATE"

    admin_agent.agent.get_human_input = websocket_human_input_sync
```

#### Tool Approval with Auto-Allow
```python
def configure_admin_for_copilot_tool_approval(
    admin_agent, approval_manager, run_id: str, permission_manager
):
    """Claude Code-like tool approval with [Allow for Session]."""

    def copilot_tool_approval_sync(prompt: str) -> str:
        category = permission_manager.classify_from_prompt(prompt)

        # Check auto-allow
        if permission_manager.is_allowed(category):
            return ""  # Auto-continue

        # Send WebSocket approval with options:
        # [allow] [allow_session] [deny] [edit]
        approval_request = approval_manager.create_approval_request(
            options=["allow", "allow_session", "deny", "edit"]
        )

        if resolution == "allow_session":
            permission_manager.allow_for_session(category)
```

---

### 8. WebSocket Approval Manager

Located at `cmbagent/database/websocket_approval_manager.py`:

```python
class WebSocketApprovalManager:
    _pending: Dict[str, asyncio.Event] = {}
    _resolved: Dict[str, ResolvedApproval] = {}

    def create_approval_request(self, ...):
        # Send approval_requested event via WebSocket
        self._ws_send_event("approval_requested", {...})

        # Create async event for waiting
        self._pending[approval_id] = asyncio.Event()
        return ApprovalRequest(id=approval_id, ...)

    async def wait_for_approval_async(self, approval_id, timeout_seconds=1800):
        # Wait for resolve() to be called
        await asyncio.wait_for(
            self._pending[approval_id].wait(),
            timeout=timeout_seconds
        )
        return self._resolved[approval_id]

    @classmethod
    def resolve(cls, approval_id, resolution, user_feedback, modifications):
        # Called from WebSocket handler when user responds
        cls._resolved[approval_id] = ResolvedApproval(...)
        cls._pending[approval_id].set()  # Unblock wait
```

---

### 9. Backend Task Executor (`backend/execution/task_executor.py`)

Lines 605-674 - Copilot mode execution:
```python
elif mode == "copilot":
    from cmbagent.workflows.copilot import copilot
    from cmbagent.database.websocket_approval_manager import WebSocketApprovalManager

    # Create WebSocket-based approval manager
    copilot_approval_manager = WebSocketApprovalManager(ws_send_event, task_id)

    results = copilot(
        task=task,
        available_agents=config.get("availableAgents", ["engineer", "researcher"]),
        enable_planning=config.get("enablePlanning", True),
        tool_approval=config.get("toolApproval", "none"),
        intelligent_routing=config.get("intelligentRouting", "balanced"),
        approval_manager=copilot_approval_manager,
        ...
    )
```

---

### 10. Frontend WebSocket Context (`cmbagent-ui/contexts/WebSocketContext.tsx`)

Handles WebSocket events:
```typescript
const { handleEvent } = useEventHandler({
    onApprovalRequested: (data: ApprovalRequestedData) => {
        setPendingApproval(data);
    },
    onApprovalReceived: () => {
        clearApproval();
    },
    onAgentMessage: (data: AgentMessageData) => {
        setAgentMessages(prev => [...prev, data]);
    },
    ...
});
```

---

## Execution Flow

### Standard (Non-Conversational) Flow

```
1. User submits task via UI
   │
2. WebSocket connects to /ws/{task_id}
   │
3. task_executor.py receives task + config
   │
4. Creates WebSocketApprovalManager
   │
5. Calls copilot() workflow
   │
6. SwarmOrchestrator.initialize()
   │   - Loads agents
   │   - Registers phase tools
   │   - Sets up tool approval (if enabled)
   │
7. SwarmOrchestrator.run(task)
   │
8. _execute_swarm_loop():
   │
   ├─► Round 1: _execute_round()
   │       │
   │       ├─► _build_initial_message()
   │       │
   │       ├─► _execute_with_routing()
   │       │       │
   │       │       ├─► _get_routing_decision()
   │       │       │       │
   │       │       │       └─► copilot_control analyzes task
   │       │       │               │
   │       │       │               └─► Returns: {route_type, primary_agent, ...}
   │       │       │
   │       │       ├─► If route_type == "clarify":
   │       │       │       └─► _handle_clarification_request()
   │       │       │               │
   │       │       │               ├─► Creates approval_request
   │       │       │               │
   │       │       │               └─► WAITS for user response
   │       │       │
   │       │       └─► Else: _execute_with_agent(primary_agent)
   │       │               │
   │       │               └─► Agent executes (may invoke phase tools)
   │       │
   │       └─► Returns round_result
   │
   ├─► Check if task complete → Exit
   │
   ├─► Increment round
   │
   └─► Loop to Round 2...
```

### Conversational Flow (human in every turn)

```
1. _execute_conversational_loop():
   │
   ├─► Round N:
   │       │
   │       ├─► Agent Turn: _execute_with_routing()
   │       │       │
   │       │       └─► Agent acts, produces result
   │       │
   │       └─► Human Turn: _get_human_turn()
   │               │
   │               ├─► Creates approval_request with:
   │               │       - Round summary
   │               │       - "What would you like to do?"
   │               │       - Options: [submit, continue, done, exit]
   │               │
   │               ├─► WAITS for user response
   │               │
   │               └─► Returns: {action, message}
   │                       │
   │                       ├─► action == "done" → Exit
   │                       ├─► action == "new_task" → Update task
   │                       └─► action == "continue" → Incorporate feedback
   │
   └─► Loop to Round N+1...
```

---

## HITL Mechanisms

### 1. Clarification Requests (Heuristic Routing)

**Location**: `swarm_orchestrator.py:1519-1593`

**Trigger**: Vague/ambiguous tasks detected by heuristics

**Detection Patterns**:
- `word_count < 5` with generic actions like `('write', 'script')`
- Vague patterns: `'fix it'`, `'make it work'`, `'improve this'`
- High ratio of vague words: `'it'`, `'this'`, `'something'`

**Behavior by Mode**:
| `intelligent_routing` | Clarification Threshold |
|-----------------------|------------------------|
| `"minimal"`           | Almost never           |
| `"balanced"`          | Essential gaps only    |
| `"aggressive"`        | Frequent clarification |

### 2. Tool Approval (Claude Code-style)

**Location**: `hitl.py:427-555`

**Modes** (`tool_approval` config):
- `"none"` - No tool approval
- `"prompt"` - Ask before dangerous ops, with "Allow for Session"
- `"auto_allow_all"` - Auto-approve everything

**Categories**:
- `bash` - Shell commands
- `code_exec` - Code execution
- `install` - Package installation
- `file_write` - File modifications

### 3. Phase Checkpoints

**Location**: `phases/hitl_checkpoint.py`

**Checkpoint Types**:
- `after_planning` - Review plan before execution
- `before_step` - Approve each step
- `after_step` - Review step results
- `custom` - Ad-hoc checkpoints

### 4. Agent Handoffs to Admin

**Location**: `handoffs/hitl.py:219-288`

**Mandatory Checkpoints**:
```python
if 'after_planning' in checkpoints:
    agents['plan_reviewer'].agent.handoffs.set_after_work(
        AgentTarget(admin.agent)
    )
```

**Smart Approval** (LLM decides when to escalate):
```python
escalation_prompt = """
Escalate to admin if:
- HIGH RISK OPERATIONS: delete, production, deploy
- UNCERTAINTY about approach
- COMPLEX DECISIONS requiring judgment
- ERROR RECOVERY needed
"""
agents['engineer'].agent.handoffs.add_llm_conditions([
    OnCondition(
        target=AgentTarget(admin.agent),
        condition=StringLLMCondition(prompt=escalation_prompt)
    )
])
```

---

## Known Issues & Gaps

### Issue 1: Clarification Not Triggering in Your Logs

**Root Cause**: The task "Write a Python script. Generate a plan to clarify requirements" was processed as follows:

1. Because task contained "Generate a plan", it went directly to `invoke_planning_phase`
2. Planning phase completed (with an error: `'bool' object is not callable'`)
3. After planning, control passed to `engineer` agent
4. Engineer output text: "Please specify requirements" but **did NOT call `invoke_hitl_checkpoint_phase`**

**Why Engineer Didn't Call HITL**:
- Engineer instructions mention the tool but don't specify **when** to use it
- No explicit instruction: "If requirements are unclear, call `invoke_hitl_checkpoint_phase`"
- The engineer just outputs text instead of invoking the tool

### Issue 2: Phase Tools Return JSON, Don't Execute

**Location**: `phase_tools.py:191-213`

```python
def invoke_hitl_checkpoint_phase(...) -> str:
    return json.dumps({
        "status": "phase_invocation_requested"  # Just returns JSON!
    })
```

The actual execution happens in `swarm_orchestrator.py:436-541` when the orchestrator calls `_execute_phase_as_tool()`. But if an agent just calls the function directly, it only gets back JSON string—it doesn't actually pause for HITL.

### Issue 3: Planning Phase Error

Your logs show: `{"status": "error", "phase": "planning", "error": "'bool' object is not callable"}`

This error likely occurred in the planning phase code where a bool was mistakenly called as a function. This needs investigation in `phases/planning.py`.

### Issue 4: `intelligent_routing: "balanced"` Prefers Action

When set to `"balanced"`:
- The system logs: `"Use BALANCED mode: Prefer action, clarify only essential gaps"`
- Clarification threshold is higher (requires <=5 words AND vague patterns)
- Generic "write python script" (3 words) should trigger clarification, but...
- The task had extra text ("No further details provided. Generate a plan") making it longer

---

## Configuration Reference

### Copilot Config Options

```python
copilot(
    # Core
    task: str,                              # Task description

    # Agents
    available_agents: List[str] = [         # Agents to load
        "engineer", "researcher", "web_surfer",
        "executor", "planner", "copilot_control", ...
    ],

    # Models
    engineer_model: str = "gpt-4o",
    researcher_model: str = "gpt-4o",
    planner_model: str = "gpt-4o",
    control_model: str = "gpt-4o",          # For routing

    # Routing
    enable_planning: bool = True,           # Auto-plan complex tasks
    use_dynamic_routing: bool = True,       # Use LLM routing
    complexity_threshold: int = 50,         # Word count for "complex"
    intelligent_routing: str = "balanced",  # "aggressive"|"balanced"|"minimal"

    # Execution
    max_rounds: int = 100,                  # Max rounds before pause
    max_plan_steps: int = 5,
    max_n_attempts: int = 3,
    continuous_mode: bool = False,          # Auto-continue
    auto_continue: bool = False,

    # HITL
    approval_mode: str = "after_step",      # "none"|"before_step"|"after_step"|"both"|"conversational"
    auto_approve_simple: bool = True,       # Skip HITL for simple tasks
    conversational: bool = False,           # Human in every turn

    # Tool Approval
    tool_approval: str = "none",            # "none"|"prompt"|"auto_allow_all"

    # Phase Tools
    enable_phase_tools: bool = True,        # Phases as callable tools

    # WebSocket
    approval_manager=None,                  # WebSocketApprovalManager
    callbacks=None,                         # WorkflowCallbacks
)
```

### Approval Mode Behaviors

| `approval_mode` | Behavior |
|-----------------|----------|
| `"none"` | No HITL checkpoints |
| `"before_step"` | Approve each step before execution |
| `"after_step"` | Review each step after completion |
| `"both"` | Both before and after |
| `"conversational"` | Human in every turn |

### Intelligent Routing Modes

| Mode | Behavior |
|------|----------|
| `"minimal"` | Almost never clarify, direct action |
| `"balanced"` | Clarify only essential gaps, prefer action |
| `"aggressive"` | Frequent clarification, propose approaches |

---

## Files Reference

| File | Purpose |
|------|---------|
| `cmbagent/workflows/copilot.py` | Main entry point |
| `cmbagent/workflows/swarm_copilot.py` | Alternative entry point |
| `cmbagent/orchestrator/swarm_orchestrator.py` | Core orchestration engine |
| `cmbagent/agents/copilot_control/copilot_control.yaml` | Intelligent router agent |
| `cmbagent/functions/phase_tools.py` | Phase tools definitions |
| `cmbagent/phases/registry.py` | Phase registry |
| `cmbagent/phases/hitl_checkpoint.py` | HITL checkpoint phase |
| `cmbagent/phases/planning.py` | Planning phase |
| `cmbagent/handoffs/hitl.py` | HITL handoffs & WebSocket integration |
| `cmbagent/handoffs/__init__.py` | Handoff registration |
| `cmbagent/database/websocket_approval_manager.py` | WebSocket approval manager |
| `backend/execution/task_executor.py` | Backend task execution |
| `backend/websocket/handlers.py` | WebSocket handlers |
| `cmbagent-ui/contexts/WebSocketContext.tsx` | Frontend WebSocket context |
---

## Dynamic Workflow Architecture (Proposed)

### Current Architecture: Static Multi-Agent with Phases

**Problem Identified**: The current workflow uses **rigid keyword-based routing** and **predefined phase invocation** which prevents dynamic, context-aware decision making like Claude/GitHub Copilot.

#### Current Flow (Static)

```
User Input: "Write a Python script with plan"
                    ↓
    [copilot_control - keyword matching]
                    ↓
    Detects "plan" keyword → Route to "planner" agent
                    ↓
    [planner agent] → Automatically calls invoke_planning_phase
                    ↓
    [Planning phase executes entire workflow]
                    ↓
    Returns to engineer
                    ↓
    Engineer outputs text: "Please specify requirements"
                    ↓
    (NO HITL TOOL CALLED - just text output)
                    ↓
    Execution continues/fails
```

**Key Issues**:
1. ❌ **Keyword matching** (`"plan"` → planner agent) - brittle
2. ❌ **Prescriptive phases** ("use planning when 5+ steps") - no agent judgment
3. ❌ **Separated workflows** (planning is a "phase" separate from thinking)
4. ❌ **Multiple specialized agents** (planner/engineer/researcher) - forces premature role assignment
5. ❌ **HITL not invoked** - agents output text instead of calling `invoke_hitl_checkpoint_phase`

#### How Claude/Modern AI Assistants Work (Dynamic)

```
User Input: "Build a REST API with authentication"
                    ↓
    [Single Intelligent Agent with Tools & Context]
                    ↓
    Agent reasoning:
    "I need to understand the project structure first..."
                    ↓
    [Agent uses read_file tool to explore]
                    ↓
    Agent: "I see FastAPI is used. For auth, I should clarify the approach..."
                    ↓
    [Agent uses ask_user tool] ← THIS IS HITL!
                    ↓
    Display UI prompt: "Prefer JWT or OAuth2?"
                    ↓
    User responds: "JWT"
                    ↓
    Agent: "I'll implement JWT. Starting with user model..."
                    ↓
    [Agent uses edit_file tool]
                    ↓
    Agent shows progress naturally
                    ↓
    User can interrupt/continue anytime
```

**Key Differences**:
- ✅ **Context-driven decisions** (not keyword matching)
- ✅ **Tools available** (agent decides when to use)
- ✅ **Continuous thinking** (no separate "planning phase")
- ✅ **Single intelligent agent** (not multiple roles)
- ✅ **Natural HITL** (`ask_user` is just another tool)
- ✅ **Progressive refinement** (read → think → act → refine)

### Proposed Dynamic Architecture

#### Core Principles

1. **Single Intelligent Agent Model**
   - One agent that can handle planning, research, engineering
   - No forced role specialization
   - Agent adapts tools to task needs

2. **Tools Not Phases**
   ```python
   # Instead of:
   invoke_planning_phase(task)  # Entire phase workflow
   
   # Use:
   tools = [
       ask_user(question),      # HITL when clarification needed
       read_file(path),         # Context gathering
       edit_file(path),          # Implementation
       run_command(cmd),        # Execution
       create_plan(steps),      # Planning when useful (not mandatory)
   ]
   # Agent decides WHEN to use each tool
   ```

3. **Context-Aware Decision Making**
   ```python
   # Not: "if 'plan' in message: goto planner"
   # But: Agent analyzes full context and decides next action
   
   Agent reasoning:
   - Is task clear? (No → use ask_user)
   - What files exist? (use read_file)
   - What's the best approach? (think → decide)
   - Risky operation? (use ask_user for approval)
   ```

4. **Natural Checkpoints**
   - Agent uses `ask_user` tool when:
     - Task ambiguous → clarification
     - Risky operation → approval
     - Multiple approaches → user preference
   - Not: "after every step" or "before every step"
   - But: **when it makes sense**

#### Proposed Flow Examples

##### Flow 1: Complex Task with Natural Clarification

```
User: "Write a Python script"
                ↓
Agent analyzes: "Too vague - need purpose"
                ↓
Agent uses ask_user tool:
  "What should this script do? Please describe its purpose."
                ↓
[UI displays prompt, user responds]
                ↓
User: "Parse CSV and generate reports"
                ↓
Agent: "I'll create a CSV parser with report generation..."
                ↓
Agent uses read_file to check existing code
                ↓
Agent: "This will create new files. Proceed?"
                ↓
[Uses ask_user for approval]
                ↓
User approves
                ↓
Agent uses edit_file to implement
                ↓
Agent: "Script created at scripts/csv_parser.py"
```

##### Flow 2: Simple Task (No HITL Needed)

```
User: "Add type hints to calculate_total function in utils.py"
                ↓
Agent: "Clear task - I know what to do"
                ↓
Agent uses read_file(utils.py)
                ↓
Agent: "Found function, adding type hints..."
                ↓
Agent uses edit_file with changes
                ↓
Agent: "Added type hints. Function signature:
       def calculate_total(items: List[float]) -> float"
                ↓
[No approval needed - low risk change]
```

##### Flow 3: Conversational to Implementation

```
User: "I want to build a task management system"
                ↓
Agent: "Let me understand your requirements..."
                ↓
Agent uses ask_user:
  "What features do you need? (e.g., tasks, priorities, deadlines)"
                ↓
[Conversation mode - user can chat freely]
                ↓
User: "Tasks with priorities, due dates, and categories"
                ↓
Agent: "Would you like a CLI or web interface?"
                ↓
User: "Web with React"
                ↓
Agent: "Great. Should I create the project structure?"
                ↓
User: "Yes, implement it"
                ↓
Agent: "Switching to implementation mode..."
                ↓
Agent uses create_plan (internal planning, not a phase):
  - Setup React project
  - Create backend API
  - Implement task CRUD
  ...
                ↓
Agent: "Starting implementation. Creating backend..."
                ↓
[Agent works through plan, showing progress]
                ↓
Agent uses edit_file multiple times
                ↓
User: "Wait, use TypeScript not JavaScript"
                ↓
[User interrupts - conversation mode]
                ↓
Agent: "Switching to TypeScript. Updating configs..."
                ↓
[Continues with modification]
```

### Implementation Strategy

#### Phase 1: Add Dynamic HITL Tool (High Priority)

Make `ask_user` a primary tool that agents use naturally:

```python
# cmbagent/functions/hitl_tools.py (NEW)
@register_tool
def ask_user(question: str, options: List[str] = None) -> str:
    """
    Ask the user a question and wait for response.
    Use this when:
    - Task is ambiguous
    - Need user preference between approaches
    - Confirming risky operations
    
    Args:
        question: Question to ask user
        options: Optional list of predefined choices
        
    Returns:
        User's response
    """
    # Trigger WebSocket HITL checkpoint
    # Wait for user response
    # Return response to agent
    pass
```

**Agent instructions update**:
```yaml
# Instead of prescriptive:
"If task ambiguous, call invoke_hitl_checkpoint"

# Natural usage:
"You have an ask_user tool. Use it whenever you need 
clarification, approval, or user preference. It's async 
and will wait for user response."
```

#### Phase 2: Merge Agent Roles (Medium Priority)

Instead of `copilot_control` → `planner` → `engineer`:

```yaml
# main_agent.yaml
name: "main_agent"
instructions: |
  You are an intelligent coding assistant capable of:
  - Research and information gathering
  - Code writing and debugging
  - Planning and breaking down complex tasks
  - Interactive problem solving
  
  Available tools:
  - ask_user(question) - Get input/approval from user
  - read_file(path) - Read file contents
  - edit_file(path, changes) - Modify files
  - list_directory(path) - Explore structure
  - run_command(cmd) - Execute commands
  - search_codebase(query) - Find relevant code
  
  Your workflow:
  1. Analyze the task in full context
  2. Gather any needed information (read files, ask user)
  3. Make incremental progress
  4. Show results and check if user satisfied
  
  Use ask_user when:
  - Task purpose unclear
  - Multiple valid approaches exist
  - Operation has significant impact
  - User might want to review intermediate state
```

#### Phase 3: Remove Static Routing (Low Priority)

```python
# swarm_orchestrator.py

# REMOVE: Keyword-based routing
# if "plan" in message: route_to_planner()

# ADD: Always start with main agent
# Agent decides if it needs to:
#   - ask_user for clarification
#   - read files for context
#   - plan internally
#   - execute directly
```

### Comparison: Current vs Proposed

| Aspect | Current (Static) | Proposed (Dynamic) |
|--------|------------------|-------------------|
| **Routing** | Keyword matching | Agent reasoning |
| **Agents** | Multiple specialized | Single intelligent |
| **Planning** | Separate phase | Tool/internal reasoning |
| **HITL** | Phase invocation | Natural tool usage |
| **Clarification** | Conditional routing | Agent-initiated when needed |
| **Flow** | Prescribed (plan→execute) | Adaptive (context-driven) |
| **User Interaction** | Checkpoint gates | Continuous conversation |
| **Complexity** | Higher (multiple agents, phases) | Lower (tools abstraction) |

### Migration Path

**Option A: Gradual Evolution** (Recommended)
1. Add `ask_user` tool alongside existing phases
2. Update agent instructions to prefer `ask_user` over text output
3. Remove keyword routing for common cases
4. Merge agent roles over time

**Option B: Clean Rewrite**
1. Create new `dynamic_copilot.py` workflow
2. Single agent with tool-based architecture
3. Keep current workflow as fallback
4. Migrate users gradually

### Benefits of Dynamic Architecture

1. **More Natural UX**
   - Conversations flow naturally
   - No artificial "phase" boundaries
   - User can interrupt/redirect anytime

2. **Better Adaptability**
   - Agent adjusts to task complexity dynamically
   - No rigid "if complex then plan" rules
   - Learns from context, not keywords

3. **Simpler Codebase**
   - Fewer abstractions (no complex phase system)
   - One agent model vs multi-agent coordination
   - Tools are simpler than phases

4. **Closer to Claude/Copilot UX**
   - Industry standard interaction model
   - Users have intuition from other AI tools
   - Reduced learning curve

---

## Answering "Is Your Desired Flow Possible?"

### User's Desired Flows

#### ✅ Flow 1: Complex Task with Clarification → Plan → Approval → Execute
```
User Input →  Clarify if needed  →  Create Plan  →  Plan Approval  →  Execute
```
**Status**: ✅ Possible with dynamic architecture
- Agent uses `ask_user` when task unclear (natural clarification)
- Agent creates plan internally (or as tool output, not separate phase)
- Agent uses `ask_user` to show plan and get approval
- Agent executes with progress updates

#### ✅ Flow 2: Simple Task → Execute → Satisfaction Check
```
User Input →  Execute Task  →  Ask User for Satisfaction
```
**Status**: ✅ Possible with dynamic architecture
- Agent recognizes simple task, executes directly
- After completion, agent uses `ask_user`: "Does this meet your needs?"
- User can approve or request changes
- Agent adapts based on feedback

#### ✅ Flow 3: Conversation → Implementation → Interrupt → Continue
```
User Input →  Conversation  →  User: "implement"  →  Execute  →  User pauses  →  Continue
```
**Status**: ✅ Naturally supported with dynamic architecture
- Initial conversation uses `ask_user` fluidly
- When user says "implement", agent switches to execution
- User can interrupt anytime (just send message)
- Agent pauses, processes input, continues adapting

### Key Insight

**All three flows become natural with dynamic architecture** because:
- Flow adapts to task and user input
- No predetermined "this is a complex task → must use planning phase"
- User control is continuous (not checkpoint-based)
- Agent makes contextual decisions about when to ask, plan, execute

---