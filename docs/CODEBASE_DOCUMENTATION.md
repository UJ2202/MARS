# CMBAgent Codebase Documentation

> **Multi-Agent System for Autonomous Scientific Discovery**  
> Built by cosmologists, powered by AG2 (formerly AutoGen)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Agent System](#agent-system)
5. [Workflow System](#workflow-system)
6. [Database Layer](#database-layer)
7. [Backend API](#backend-api)
8. [Frontend UI](#frontend-ui)
9. [External Integrations](#external-integrations)
10. [Configuration](#configuration)
11. [Usage Examples](#usage-examples)
12. [Development Guide](#development-guide)

---

## Overview

CMBAgent is a sophisticated multi-agent system designed for autonomous scientific discovery. Originally built for cosmological data analysis, it's a general-purpose framework for complex, multi-step research tasks that can span hours or days.

### Key Features

- **Multi-Agent Orchestration**: 45+ specialized agents working together
- **Planning & Control**: Automatic task decomposition and execution
- **RAG Integration**: OpenAI Assistants API for domain knowledge
- **Database Persistence**: PostgreSQL/SQLite for state management
- **Human-in-the-Loop**: Approval checkpoints for critical decisions
- **Real-time Monitoring**: WebSocket-based live updates
- **Cost Tracking**: Token usage and cost reporting
- **Retry & Recovery**: Intelligent failure handling
- **Branching**: Experimental workflow exploration

### Technology Stack

| Layer | Technology |
|-------|------------|
| Core Framework | AG2 (AutoGen) |
| Backend API | FastAPI + Uvicorn |
| Database | SQLAlchemy + PostgreSQL/SQLite |
| Frontend | Next.js + React + TypeScript |
| Styling | Tailwind CSS |
| Real-time | WebSockets |

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
│  ┌─────────┐ ┌─────────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │TaskInput│ │ConsoleOutput│ │DAGViewer │ │WorkflowDashboard│  │
│  └─────────┘ └─────────────┘ └──────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │ WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│  ┌──────────┐ ┌───────────────┐ ┌────────────┐ ┌─────────────┐ │
│  │  Routers │ │WebSocket Hdlr │ │TaskExecutor│ │  Services   │ │
│  └──────────┘ └───────────────┘ └────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CMBAgent Core                                 │
│  ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌──────────────────────┐│
│  │ CMBAgent │ │ Agents  │ │Workflows │ │  Database/Callbacks  ││
│  └──────────┘ └─────────┘ └──────────┘ └──────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
│  ┌──────────┐ ┌─────────────┐ ┌───────────┐ ┌───────────────┐  │
│  │ OpenAI   │ │ Anthropic   │ │  Google   │ │  MCP Servers  │  │
│  └──────────┘ └─────────────┘ └───────────┘ └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
cmbagent/
├── cmbagent/                    # Core Python package
│   ├── __init__.py              # Package exports
│   ├── cmbagent.py              # Main CMBAgent class
│   ├── base_agent.py            # Base agent classes
│   ├── callbacks.py             # Workflow event callbacks
│   ├── context.py               # Shared context definitions
│   ├── hand_offs.py             # Agent transition logic
│   ├── functions.py             # Function registration shim
│   ├── rag_utils.py             # RAG/vector store utilities
│   ├── utils.py                 # General utilities
│   ├── cli.py                   # Command-line interface
│   │
│   ├── agents/                  # Agent definitions
│   │   ├── engineer/            # Engineer agent
│   │   ├── planner/             # Planner agent
│   │   ├── researcher/          # Researcher agent
│   │   ├── executor/            # Code executor
│   │   ├── control/             # Control agent
│   │   ├── rag_agents/          # RAG-enabled agents
│   │   └── ...                  # 45+ agent directories
│   │
│   ├── workflows/               # Workflow orchestration
│   │   ├── __init__.py
│   │   ├── planning_control.py  # Planning & control workflows
│   │   ├── one_shot.py          # Single-step execution
│   │   ├── control.py           # Control-only workflow
│   │   └── utils.py             # Workflow utilities
│   │
│   ├── functions/               # Agent callable functions
│   │   ├── registration.py      # Function registration
│   │   ├── execution_control.py # Control flow functions
│   │   ├── planning.py          # Planning functions
│   │   ├── ideas.py             # Idea management
│   │   ├── keywords.py          # Keyword extraction
│   │   └── status.py            # Status tracking
│   │
│   ├── database/                # Database layer
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── repository.py        # Data access layer
│   │   ├── state_machine.py     # State transitions
│   │   ├── dag_builder.py       # DAG construction
│   │   ├── dag_executor.py      # DAG execution
│   │   ├── approval_manager.py  # HITL approvals
│   │   └── ...
│   │
│   ├── execution/               # Execution management
│   │   ├── output_collector.py  # Output aggregation
│   │   ├── file_registry.py     # File tracking
│   │   ├── tracked_code_executor.py
│   │   └── ...
│   │
│   ├── external_tools/          # Third-party integrations
│   │   ├── ag2_free_tools.py    # LangChain/CrewAI tools
│   │   ├── langchain_tools.py
│   │   ├── crewai_tools.py
│   │   └── tool_adapter.py
│   │
│   ├── mcp/                     # Model Context Protocol
│   │   ├── client_manager.py    # MCP client
│   │   ├── tool_integration.py  # Tool integration
│   │   └── client_config.yaml   # Server configs
│   │
│   ├── retry/                   # Retry handling
│   │   ├── retry_context_manager.py
│   │   ├── error_analyzer.py
│   │   └── retry_metrics.py
│   │
│   ├── branching/               # Workflow branching
│   │   ├── branch_manager.py
│   │   ├── comparator.py
│   │   └── play_from_node.py
│   │
│   ├── processing/              # Content processing
│   ├── keywords/                # Keyword extraction
│   ├── managers/                # Agent management
│   └── gui/                     # Streamlit GUI
│
├── backend/                     # FastAPI backend
│   ├── main.py                  # App entry point
│   ├── core/                    # App configuration
│   ├── routers/                 # API endpoints
│   ├── websocket/               # WebSocket handlers
│   ├── execution/               # Task execution
│   └── services/                # Business logic
│
├── cmbagent-ui/                 # Next.js frontend
│   ├── app/                     # Next.js app router
│   ├── components/              # React components
│   ├── contexts/                # React contexts
│   ├── hooks/                   # Custom hooks
│   ├── lib/                     # Utilities
│   └── types/                   # TypeScript types
│
├── tests/                       # Test suite
├── examples/                    # Usage examples
├── data/                        # Data files
└── evals/                       # Evaluation scripts
```

---

## Core Components

### CMBAgent Class (`cmbagent/cmbagent.py`)

The central orchestrator that manages agents, workflows, and execution.

```python
class CMBAgent:
    def __init__(
        self,
        cache_seed=None,
        temperature=0.00001,
        top_p=0.05,
        timeout=1200,
        max_round=50,
        platform='oai',
        model='gpt4o',
        llm_api_key=None,
        make_vector_stores=False,
        agent_list=['camb', 'classy_sz', 'cobaya', 'planck'],
        verbose=False,
        agent_instructions={},
        agent_llm_configs={},
        work_dir=work_dir_default,
        clear_work_dir=True,
        mode="planning_and_control",
        approval_config=None,
        enable_ag2_free_tools=True,
        enable_mcp_client=False,
        **kwargs
    )
```

#### Key Methods

| Method | Description |
|--------|-------------|
| `solve(task, initial_agent, shared_context, mode, max_rounds)` | Execute a task with specified agent and mode |
| `init_agents(agent_llm_configs, default_formatter_model)` | Initialize all agents dynamically |
| `display_cost(name_append)` | Display and save cost report |
| `clear_work_dir()` | Clear working directory |
| `get_agent_from_name(name)` | Get agent instance by name |
| `check_assistants(reset_assistant)` | Verify/create OpenAI assistants |

#### Initialization Flow

```
CMBAgent.__init__()
    │
    ├── Initialize database (optional)
    │   ├── init_database()
    │   ├── Create session
    │   ├── Create repositories
    │   ├── Create DAG components
    │   └── Create approval/retry managers
    │
    ├── Initialize MCP client (optional)
    │   ├── MCPClientManager()
    │   └── connect_all()
    │
    ├── init_agents()
    │   ├── import_rag_agents()
    │   ├── import_non_rag_agents()
    │   └── Instantiate agent classes
    │
    ├── Setup RAG (if enabled)
    │   ├── setup_cmbagent_data()
    │   ├── check_assistants()
    │   └── push_vector_stores()
    │
    ├── register_all_hand_offs()
    │
    └── register_functions_to_agents()
```

### Base Agent (`cmbagent/base_agent.py`)

Base class for all agents with different agent type setups:

```python
class BaseAgent:
    def __init__(self, llm_config, agent_id, work_dir, agent_type, **kwargs)
    
    # Agent setup methods
    def set_gpt_assistant_agent()    # RAG agents with OpenAI Assistants
    def set_assistant_agent()         # Conversable swarm agents
    def set_code_agent()              # Code execution agents
    def set_admin_agent()             # User proxy agents

class CmbAgentSwarmAgent(ConversableAgent):
    """Swarm-compatible agent extending AG2's ConversableAgent"""
    pass

class CmbAgentUserProxyAgent(UserProxyAgent):
    """Custom user proxy with redefined descriptions"""
    DEFAULT_USER_PROXY_AGENT_DESCRIPTIONS = {...}
```

### Shared Context (`cmbagent/context.py`)

Global state passed between agents:

```python
shared_context = {
    # Task information
    "main_task": None,
    "improved_main_task": None,
    
    # Plan state
    "plans": [],
    "reviews": [],
    "proposed_plan": None,
    "recommendations": None,
    "feedback_left": 1,
    "final_plan": None,
    "number_of_steps_in_plan": None,
    "maximum_number_of_steps_in_plan": 5,
    
    # Current execution state
    "current_plan_step_number": None,
    "current_sub_task": None,
    "agent_for_sub_task": None,
    "current_status": None,
    "current_instructions": None,
    "previous_steps_execution_summary": "\n",
    
    # File paths
    "database_path": "data/",
    "codebase_path": "codebase/",
    "work_dir": None,
    
    # Agent transfer flags
    "transfer_to_engineer": False,
    "transfer_to_researcher": False,
    "transfer_to_camb_agent": False,
    # ... more transfer flags
    
    # Append instructions per agent
    "planner_append_instructions": None,
    "engineer_append_instructions": None,
    "researcher_append_instructions": None,
    
    # Perplexity integration
    "perplexity_query": None,
    "perplexity_response": None,
    "perplexity_citations": None,
    
    # Retry handling
    "n_attempts": 0,
    "max_n_attempts": 3,
    
    # Plot evaluation
    "evaluate_plots": False,
    "latest_plot_path": None,
    "vlm_plot_analysis": None,
    
    # Domain-specific context
    "camb_context": None,
    "classy_context": None,
    "AAS_keywords_string": None,
}
```

---

## Agent System

### Agent Types

#### 1. Core Orchestration Agents

| Agent | File | Purpose |
|-------|------|---------|
| `planner` | `agents/planner/` | Creates multi-step execution plans |
| `plan_reviewer` | `agents/plan_reviewer/` | Reviews and critiques plans |
| `control` | `agents/control/` | Orchestrates plan execution |
| `terminator` | `agents/terminator/` | Signals task completion |
| `admin` | `agents/admin/` | Human interaction proxy |

#### 2. Execution Agents

| Agent | File | Purpose |
|-------|------|---------|
| `engineer` | `agents/engineer/` | Writes Python code |
| `researcher` | `agents/researcher/` | Gathers information, writes reports |
| `executor` | `agents/executor/` | Executes Python code |
| `executor_bash` | `agents/executor_bash/` | Executes bash commands |
| `installer` | `agents/installer/` | Installs Python packages |

#### 3. Idea Generation Agents

| Agent | File | Purpose |
|-------|------|---------|
| `idea_maker` | `agents/idea_maker/` | Generates research ideas |
| `idea_hater` | `agents/idea_hater/` | Critiques ideas |
| `idea_saver` | `agents/idea_saver/` | Persists approved ideas |

#### 4. Web & Search Agents

| Agent | File | Purpose |
|-------|------|---------|
| `perplexity` | `agents/perplexity/` | Web search via Perplexity API |
| `web_surfer` | `agents/web_surfer/` | Web browsing |
| `retrieve_assistant` | `agents/retrieve_assistant/` | RAG retrieval |

#### 5. Domain-Specific Agents (RAG)

| Agent | File | Purpose |
|-------|------|---------|
| `camb_agent` | `agents/rag_agents/camb_agent.py` | CAMB cosmology code knowledge |
| `classy_sz_agent` | `agents/rag_agents/classy_sz_agent.py` | CLASS-SZ code knowledge |
| `cobaya_agent` | `agents/rag_agents/cobaya_agent.py` | Cobaya sampling framework |
| `planck_agent` | `agents/rag_agents/planck_agent.py` | Planck mission data |

#### 6. Response Formatter Agents

Each major agent has a formatter that structures its output:
- `engineer_response_formatter`
- `researcher_response_formatter`
- `planner_response_formatter`
- `idea_maker_response_formatter`
- etc.

#### 7. Utility Agents

| Agent | Purpose |
|-------|---------|
| `summarizer` | Document summarization |
| `plot_judge` | Evaluates plot quality |
| `plot_debugger` | Fixes plot issues |
| `aas_keyword_finder` | Finds AAS keywords |
| `session_summarizer` | Summarizes sessions |

### Agent Definition Structure

Each agent has its own directory with:

```
agents/{agent_name}/
├── {agent_name}.py      # Python class definition
└── {agent_name}.yaml    # Configuration and instructions
```

#### Example: Engineer Agent

**`engineer.py`**:
```python
import os
from cmbagent.base_agent import BaseAgent

class EngineerAgent(BaseAgent):
    def __init__(self, llm_config=None, **kwargs):
        agent_id = os.path.splitext(os.path.abspath(__file__))[0]
        super().__init__(llm_config=llm_config, agent_id=agent_id, **kwargs)

    def set_agent(self, **kwargs):
        super().set_assistant_agent(**kwargs)
```

**`engineer.yaml`**:
```yaml
name: "engineer"

instructions: |
    You are the engineer agent.
    
    You provide single self-consistent Python code, ready to be executed.
    
    **RESPONSE FORMAT:**
    
    **Code Explanation:**
    <concise explanation>
    
    **Python Code:**
    ```python
    <code>
    ```
    
    **IMPORTANT:**
    - Return one and only one Python code block
    - Focus on one step at a time
    - When a plot is requested, save to PNG at dpi>=300
    - Do not use .show() for plots
    - Write detailed docstrings
    - Avoid f-strings when possible
    ...

description: |
    Engineer agent, to provide Python code.
```

### Hand-offs (`cmbagent/hand_offs.py`)

Defines agent-to-agent transitions:

```python
def register_all_hand_offs(cmbagent_instance):
    # Get agent instances
    planner = cmbagent_instance.get_agent_object_from_name('planner')
    engineer = cmbagent_instance.get_agent_object_from_name('engineer')
    researcher = cmbagent_instance.get_agent_object_from_name('researcher')
    control = cmbagent_instance.get_agent_object_from_name('control')
    # ... get all agents
    
    # Define hand-off chains
    planner.agent.handoffs.set_after_work(AgentTarget(planner_response_formatter.agent))
    planner_response_formatter.agent.handoffs.set_after_work(AgentTarget(plan_recorder.agent))
    plan_recorder.agent.handoffs.set_after_work(AgentTarget(plan_reviewer.agent))
    
    engineer.agent.handoffs.set_after_work(AgentTarget(engineer_response_formatter.agent))
    engineer_response_formatter.agent.handoffs.set_after_work(AgentTarget(executor.agent))
    
    researcher.agent.handoffs.set_after_work(AgentTarget(researcher_response_formatter.agent))
    researcher_response_formatter.agent.handoffs.set_after_work(AgentTarget(researcher_executor.agent))
    
    # Mode-specific routing
    if mode == "one_shot":
        camb_response_formatter.agent.handoffs.set_after_work(AgentTarget(engineer.agent))
    else:
        camb_response_formatter.agent.handoffs.set_after_work(AgentTarget(control.agent))
```

### Functions Registration (`cmbagent/functions/`)

Agents can call registered functions:

```python
# registration.py
def register_functions_to_agents(cmbagent_instance):
    """Register callable functions with appropriate agents."""
    
    # Planning functions
    register_planning_functions(cmbagent_instance)
    
    # Execution control functions
    register_execution_control_functions(cmbagent_instance)
    
    # Status functions
    register_status_functions(cmbagent_instance)
    
    # Ideas functions
    register_ideas_functions(cmbagent_instance)
    
    # Keywords functions
    register_keywords_functions(cmbagent_instance)
```

---

## Workflow System

### Workflow Types (`cmbagent/workflows/`)

#### 1. Planning and Control with Context Carryover

The flagship workflow for deep research:

```python
def planning_and_control_context_carryover(
    task,
    max_rounds_planning=50,
    max_rounds_control=100,
    max_plan_steps=3,
    n_plan_reviews=1,
    plan_instructions='',
    engineer_instructions='',
    researcher_instructions='',
    hardware_constraints='',
    max_n_attempts=3,
    planner_model=...,
    engineer_model=...,
    researcher_model=...,
    work_dir=work_dir_default,
    api_keys=None,
    restart_at_step=-1,
    clear_work_dir=False,
    approval_config=None,
    callbacks=None,
):
    """
    Execute planning and control workflow with context carryover.
    
    Flow:
    1. Planning Phase
       - task_improver improves the task
       - planner creates a multi-step plan
       - plan_reviewer reviews the plan
       - Iterate until plan is approved
    
    2. Control Phase (per step)
       - control routes to appropriate agent
       - agent executes the step
       - executor runs any code
       - context is saved and carried over
       - Retry on failure up to max_n_attempts
    
    3. Completion
       - terminator signals completion
       - Results are collected and returned
    """
```

#### 2. Planning and Control (Simple)

```python
def planning_and_control(
    task,
    max_rounds_planning=50,
    max_rounds_control=100,
    ...
):
    """
    Planning and control without context carryover between steps.
    Simpler but less suitable for long-running tasks.
    """
```

#### 3. One-Shot

```python
def one_shot(
    task,
    initial_agent='engineer',
    max_rounds=10,
    ...
):
    """
    Single-step task execution.
    No planning phase - directly executes with specified agent.
    """
```

#### 4. Human-in-the-Loop

```python
def human_in_the_loop(
    task,
    approval_points=['plan', 'code', 'results'],
    ...
):
    """
    Interactive workflow with human approval at checkpoints.
    """
```

#### 5. Control (from existing plan)

```python
def control(
    task,
    plan=None,  # Path to plan JSON
    ...
):
    """
    Execute from an existing plan file.
    Skips planning phase entirely.
    """
```

### Workflow Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      PLANNING PHASE                              │
│                                                                  │
│  task_improver ──► planner ──► planner_response_formatter       │
│                        │                                         │
│                        ▼                                         │
│                   plan_recorder ──► plan_reviewer               │
│                        │                 │                       │
│                        ▼                 ▼                       │
│                   reviewer_response_formatter                    │
│                        │                                         │
│                        ▼                                         │
│                   review_recorder ──► (back to planner if needed)│
│                        │                                         │
│                        ▼                                         │
│                   PLAN APPROVED                                  │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CONTROL PHASE (per step)                    │
│                                                                  │
│  control ──► engineer/researcher/rag_agent                      │
│                   │                                              │
│                   ▼                                              │
│              response_formatter                                  │
│                   │                                              │
│                   ▼                                              │
│              executor (if code)                                  │
│                   │                                              │
│                   ▼                                              │
│         [SUCCESS] ──► next step / terminator                    │
│         [FAILURE] ──► retry (up to max_n_attempts)              │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      COMPLETION                                  │
│                                                                  │
│  terminator ──► Results collected                               │
│                   │                                              │
│                   ▼                                              │
│              Output files organized                              │
│              Cost report generated                               │
│              Context saved                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Callbacks (`cmbagent/callbacks.py`)

Event hooks for workflow monitoring:

```python
@dataclass
class WorkflowCallbacks:
    # Planning phase
    on_planning_start: Optional[Callable[[str, Dict], None]] = None
    on_planning_complete: Optional[Callable[[PlanInfo], None]] = None
    
    # Step execution
    on_step_start: Optional[Callable[[StepInfo], None]] = None
    on_step_complete: Optional[Callable[[StepInfo], None]] = None
    on_step_failed: Optional[Callable[[StepInfo], None]] = None
    
    # Workflow lifecycle
    on_workflow_start: Optional[Callable[[str, Dict], None]] = None
    on_workflow_complete: Optional[Callable[[Dict, float], None]] = None
    on_workflow_failed: Optional[Callable[[str, Optional[int]], None]] = None
    
    # Progress updates
    on_progress: Optional[Callable[[str, Dict], None]] = None

# Factory functions
def create_null_callbacks() -> WorkflowCallbacks
def create_print_callbacks() -> WorkflowCallbacks
def create_websocket_callbacks(websocket, task_id) -> WorkflowCallbacks
def create_database_callbacks(db_session, run_id) -> WorkflowCallbacks
def merge_callbacks(*callbacks) -> WorkflowCallbacks
```

---

## Database Layer

### Models (`cmbagent/database/models.py`)

SQLAlchemy models for persistence:

```python
class Session(Base):
    """User session for isolating workflow data."""
    __tablename__ = "sessions"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="active")  # active, archived, deleted
    created_at = Column(TIMESTAMP)
    last_active_at = Column(TIMESTAMP)

class Project(Base):
    """Project container for organizing workflow runs."""
    __tablename__ = "projects"
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.id"))
    name = Column(String(255))
    description = Column(Text)

class WorkflowRun(Base):
    """A single workflow execution."""
    __tablename__ = "workflow_runs"
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.id"))
    project_id = Column(String(36), ForeignKey("projects.id"))
    mode = Column(String(50))  # one_shot, planning_control, deep_research
    agent = Column(String(100))  # initial agent
    model = Column(String(100))  # LLM model
    status = Column(String(50))  # draft, planning, executing, completed, failed
    task_description = Column(Text)
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    # Branching
    branch_parent_id = Column(String(36), ForeignKey("workflow_runs.id"))
    is_branch = Column(Boolean, default=False)
    branch_depth = Column(Integer, default=0)

class WorkflowStep(Base):
    """A single step within a workflow run."""
    __tablename__ = "workflow_steps"
    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"))
    step_number = Column(Integer)
    goal = Column(Text)  # Step goal/description
    summary = Column(Text)  # What was accomplished
    status = Column(String(50))  # pending, running, completed, failed
    progress_percentage = Column(Integer, default=0)
    inputs = Column(JSON)
    outputs = Column(JSON)
    error_message = Column(Text)

class DAGNode(Base):
    """Node in the workflow DAG."""
    __tablename__ = "dag_nodes"
    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"))
    node_type = Column(String(50))  # planning, control, agent, approval
    agent = Column(String(100))
    status = Column(String(50))  # pending, running, completed, failed
    order_index = Column(Integer)

class DAGEdge(Base):
    """Edge connecting DAG nodes."""
    __tablename__ = "dag_edges"
    from_node_id = Column(String(36), ForeignKey("dag_nodes.id"))
    to_node_id = Column(String(36), ForeignKey("dag_nodes.id"))
    dependency_type = Column(String(50))  # sequential, parallel, conditional
    condition = Column(Text)

class Checkpoint(Base):
    """State snapshot for recovery."""
    __tablename__ = "checkpoints"
    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"))
    step_id = Column(String(36), ForeignKey("workflow_steps.id"))
    context_snapshot = Column(JSON)
    created_at = Column(TIMESTAMP)

class Message(Base):
    """Agent conversation messages."""
    __tablename__ = "messages"
    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"))
    step_id = Column(String(36), ForeignKey("workflow_steps.id"))
    agent = Column(String(100))
    role = Column(String(50))  # user, assistant, system
    content = Column(Text)
    created_at = Column(TIMESTAMP)

class CostRecord(Base):
    """Token usage and cost tracking."""
    __tablename__ = "cost_records"
    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"))
    agent = Column(String(100))
    model = Column(String(100))
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_cost = Column(Numeric(10, 6))
    created_at = Column(TIMESTAMP)

class ApprovalRequest(Base):
    """Human-in-the-loop approval requests."""
    __tablename__ = "approval_requests"
    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"))
    step_id = Column(String(36), ForeignKey("workflow_steps.id"))
    checkpoint_type = Column(String(50))  # plan, code, results
    status = Column(String(50))  # pending, approved, rejected
    request_data = Column(JSON)
    response_data = Column(JSON)
    requested_at = Column(TIMESTAMP)
    resolved_at = Column(TIMESTAMP)

class File(Base):
    """Tracked output files."""
    __tablename__ = "files"
    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"))
    step_id = Column(String(36), ForeignKey("workflow_steps.id"))
    filename = Column(String(255))
    relative_path = Column(String(1024))
    category = Column(String(50))  # code, data, plot, report
    size_bytes = Column(BigInteger)
    content_hash = Column(String(64))
    generating_agent = Column(String(100))

class ExecutionEvent(Base):
    """Execution trace events."""
    __tablename__ = "execution_events"
    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("workflow_runs.id"))
    step_id = Column(String(36), ForeignKey("workflow_steps.id"))
    node_id = Column(String(36), ForeignKey("dag_nodes.id"))
    event_type = Column(String(50))
    agent = Column(String(100))
    details = Column(JSON)
    created_at = Column(TIMESTAMP)
```

### Repository Layer (`cmbagent/database/repository.py`)

Data access abstraction:

```python
class WorkflowRepository:
    def __init__(self, db_session, session_id)
    
    # Workflow Run operations
    def create_run(self, mode, agent, model, task_description) -> WorkflowRun
    def get_run(self, run_id) -> WorkflowRun
    def update_run_status(self, run_id, status)
    def list_runs(self, status=None, limit=100) -> List[WorkflowRun]
    
    # Step operations
    def create_step(self, run_id, step_number, goal) -> WorkflowStep
    def update_step_status(self, step_id, status, summary=None)
    def get_steps_for_run(self, run_id) -> List[WorkflowStep]
    
    # Message operations
    def add_message(self, run_id, step_id, agent, role, content) -> Message
    def get_messages_for_step(self, step_id) -> List[Message]

class DAGRepository:
    def create_node(self, run_id, node_type, agent, order_index) -> DAGNode
    def create_edge(self, from_node_id, to_node_id, dependency_type) -> DAGEdge
    def get_dag_for_run(self, run_id) -> Dict[str, List]

class CostRepository:
    def record_cost(self, run_id, agent, model, prompt_tokens, completion_tokens, cost)
    def get_cost_summary(self, run_id) -> Dict
    def get_cost_by_model(self, run_id) -> List[Dict]
    def get_cost_by_agent(self, run_id) -> List[Dict]
```

### State Machine (`cmbagent/database/state_machine.py`)

Workflow state transitions:

```python
class StateMachine:
    def __init__(self, db_session, entity_type)
    
    def transition(self, entity_id, from_state, to_state) -> bool
    def get_current_state(self, entity_id) -> str
    def get_valid_transitions(self, current_state) -> List[str]
    def get_state_history(self, entity_id) -> List[StateHistory]

# Valid workflow states
class WorkflowState(Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"

# Valid step states
class StepState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
```

### DAG Components

```python
# dag_builder.py
class DAGBuilder:
    """Constructs execution DAG from plan."""
    def build_from_plan(self, run_id, plan_steps) -> List[DAGNode]
    def add_approval_node(self, run_id, before_node_id, checkpoint_type)

# dag_executor.py
class DAGExecutor:
    """Executes DAG nodes in order."""
    def execute_node(self, node_id) -> Dict
    def get_ready_nodes(self, run_id) -> List[DAGNode]
    def mark_node_complete(self, node_id, outputs)
    def mark_node_failed(self, node_id, error)

# dag_visualizer.py
class DAGVisualizer:
    """Generates DAG visualization data."""
    def get_dag_json(self, run_id) -> Dict
    def get_mermaid_diagram(self, run_id) -> str
```

### Approval Manager (`cmbagent/database/approval_manager.py`)

Human-in-the-loop control:

```python
class ApprovalManager:
    def __init__(self, db_session, session_id)
    
    def request_approval(
        self, 
        run_id, 
        step_id, 
        checkpoint_type,  # 'plan', 'code', 'results'
        data
    ) -> ApprovalRequest
    
    def wait_for_approval(
        self, 
        request_id, 
        timeout=None
    ) -> ApprovalResolution
    
    def approve(self, request_id, feedback=None)
    def reject(self, request_id, reason=None)
    def get_pending_requests(self, run_id=None) -> List[ApprovalRequest]

# Approval configuration
@dataclass
class ApprovalConfig:
    mode: ApprovalMode  # NONE, PLAN_ONLY, CODE_ONLY, ALL
    checkpoints: List[CheckpointType]
    timeout_seconds: Optional[int]
    default_action: str  # 'approve', 'reject', 'wait'
```

---

## Backend API

### Main Entry Point (`backend/main.py`)

```python
from fastapi import FastAPI, WebSocket
from core.app import create_app
from routers import register_routers
from websocket.handlers import websocket_endpoint as ws_handler
from execution.task_executor import execute_cmbagent_task

app = create_app()
register_routers(app)

@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await ws_handler(websocket, task_id, execute_cmbagent_task)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Router Structure (`backend/routers/`)

```
routers/
├── __init__.py          # Router registration
├── tasks.py             # Task CRUD operations
├── workflows.py         # Workflow management
├── steps.py             # Step operations
├── files.py             # File operations
├── costs.py             # Cost tracking
├── approvals.py         # HITL approvals
├── dag.py               # DAG operations
├── branches.py          # Branching operations
└── health.py            # Health checks
```

### WebSocket Events (`backend/websocket/`)

Event types sent to frontend:

```python
# Workflow events
"workflow_started"
"workflow_completed"
"workflow_failed"
"workflow_paused"

# DAG events
"dag_created"
"dag_node_status_changed"

# Step events
"step_started"
"step_completed"
"step_failed"
"step_progress"

# Output events
"output"              # Console output
"result"              # Final results
"error"               # Error messages

# HITL events
"approval_requested"
"approval_resolved"

# Cost events
"cost_update"

# File events
"files_updated"

# Connection events
"heartbeat"
"complete"
```

### Task Executor (`backend/execution/task_executor.py`)

```python
async def execute_cmbagent_task(
    websocket: WebSocket,
    task_id: str,
    task: str,
    config: Dict
):
    """
    Execute CMBAgent task with WebSocket updates.
    
    1. Parse configuration
    2. Create CMBAgent instance
    3. Set up callbacks for WebSocket events
    4. Execute workflow
    5. Stream results back
    """
```

---

## Frontend UI

### App Structure (`cmbagent-ui/`)

```
cmbagent-ui/
├── app/
│   ├── layout.tsx       # Root layout
│   ├── page.tsx         # Main page
│   ├── providers.tsx    # Context providers
│   └── tasks/           # Task-related pages
│
├── components/
│   ├── TaskInput.tsx           # Task configuration form
│   ├── ConsoleOutput.tsx       # Real-time console
│   ├── ResultDisplay.tsx       # Results viewer
│   ├── Header.tsx              # App header
│   ├── TopNavigation.tsx       # Top nav
│   ├── FileBrowser.tsx         # File browser
│   ├── ApprovalDialog.tsx      # HITL dialog
│   ├── CredentialsModal.tsx    # API key management
│   │
│   ├── workflow/               # Workflow components
│   │   ├── WorkflowDashboard.tsx
│   │   ├── StepProgress.tsx
│   │   └── ...
│   │
│   ├── dag/                    # DAG visualization
│   │   ├── DAGWorkspace.tsx
│   │   ├── DAGNode.tsx
│   │   ├── DAGEdge.tsx
│   │   └── ...
│   │
│   ├── metrics/                # Cost/metrics display
│   │   ├── MetricsDashboard.tsx
│   │   ├── CostChart.tsx
│   │   └── ...
│   │
│   ├── branching/              # Branch management
│   ├── retry/                  # Retry UI
│   └── tables/                 # Data tables
│
├── contexts/
│   └── WebSocketContext.tsx    # WebSocket state management
│
├── hooks/
│   ├── useWebSocket.ts         # WebSocket hook
│   └── useEventHandler.ts      # Event processing
│
├── lib/
│   ├── config.ts               # Configuration
│   └── utils.ts                # Utilities
│
└── types/
    ├── websocket-events.ts     # Event types
    ├── cost.ts                 # Cost types
    ├── branching.ts            # Branch types
    └── tables.ts               # Table types
```

### WebSocket Context (`contexts/WebSocketContext.tsx`)

Central state management for real-time updates:

```typescript
interface WebSocketContextValue {
  // Connection state
  connected: boolean;
  isConnecting: boolean;
  lastError: string | null;
  
  // Actions
  connect: (taskId: string, task: string, config: any) => Promise<void>;
  sendMessage: (message: any) => void;
  disconnect: () => void;
  
  // Current run
  currentRunId: string | null;
  
  // Workflow state
  workflowStatus: string | null;
  
  // DAG state
  dagData: { nodes: DAGNodeData[]; edges: DAGEdgeData[] } | null;
  updateDAGNode: (nodeId: string, status: string) => void;
  
  // Approval state
  pendingApproval: ApprovalRequestedData | null;
  clearApproval: () => void;
  
  // Console output
  consoleOutput: string[];
  addConsoleOutput: (output: string) => void;
  clearConsole: () => void;
  
  // Results
  results: any | null;
  
  // Running state
  isRunning: boolean;
  
  // Cost tracking
  costSummary: CostSummary;
  costTimeSeries: CostTimeSeries[];
  
  // Files
  filesUpdatedCounter: number;
}
```

### Key Components

#### TaskInput

```tsx
// Configuration options
interface TaskConfig {
  task: string;
  mode: 'one_shot' | 'planning_control' | 'deep_research';
  initial_agent: string;
  max_rounds: number;
  max_plan_steps: number;
  engineer_model: string;
  researcher_model: string;
  planner_model: string;
  approval_mode: 'none' | 'plan_only' | 'all';
}
```

#### DAGWorkspace

Visualizes workflow execution as directed acyclic graph.

```tsx
interface DAGNodeData {
  id: string;
  type: string;  // 'planning', 'agent', 'approval'
  agent?: string;
  status: string;  // 'pending', 'running', 'completed', 'failed'
  position: { x: number; y: number };
}

interface DAGEdgeData {
  id: string;
  source: string;
  target: string;
  type: string;  // 'sequential', 'parallel'
}
```

---

## External Integrations

### AG2 Free Tools (`cmbagent/external_tools/ag2_free_tools.py`)

LangChain and CrewAI tool integration:

```python
class AG2FreeToolsLoader:
    def __init__(self):
        self.interop = Interoperability()
    
    def load_langchain_tools(self, tool_names=None) -> List:
        """
        Load free LangChain tools:
        - DuckDuckGo Search (free, no API key)
        - Wikipedia (free)
        - ArXiv (free)
        - File operations (ReadFile, WriteFile, ListDirectory)
        """
    
    def load_crewai_tools(self, tool_names=None) -> List:
        """
        Load free CrewAI tools:
        - Web scraping
        - Code analysis
        - Directory operations
        """
    
    def register_with_agent(self, agent, tools):
        """Register tools with an AG2 agent."""
```

### MCP Client (`cmbagent/mcp/`)

Model Context Protocol integration:

```python
class MCPClientManager:
    """Manages connections to MCP servers."""
    
    def __init__(self, config_path=None):
        self.sessions = {}
        self.tools_cache = {}
    
    async def connect_to_server(self, server_name) -> bool:
        """Connect to a single MCP server."""
    
    async def connect_all(self) -> Dict[str, bool]:
        """Connect to all enabled servers."""
    
    async def list_tools(self, server_name=None) -> List[Dict]:
        """List available tools from connected servers."""
    
    async def call_tool(self, server_name, tool_name, arguments) -> Any:
        """Execute a tool on an MCP server."""
    
    async def disconnect_all(self):
        """Cleanup all connections."""

class MCPToolIntegration:
    """Integrates MCP tools with AG2 agents."""
    
    def __init__(self, client_manager):
        self.client_manager = client_manager
    
    def get_ag2_tools(self) -> List:
        """Convert MCP tools to AG2 format."""
    
    def register_with_agent(self, agent):
        """Register all MCP tools with an agent."""
```

**MCP Configuration** (`client_config.yaml`):

```yaml
settings:
  auto_discover_tools: true
  connection_timeout: 30

mcp_servers:
  github:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
  
  filesystem:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
  
  brave_search:
    enabled: false
    command: "npx"
    args: ["-y", "@anthropic/mcp-server-brave-search"]
    env:
      BRAVE_API_KEY: "${BRAVE_API_KEY}"
```

---

## Configuration

### Environment Variables

```bash
# LLM API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
PERPLEXITY_API_KEY=...

# Database
DATABASE_URL=postgresql://user:pass@host:5432/cmbagent
CMBAGENT_USE_DATABASE=true  # or false for no persistence

# MCP
GITHUB_TOKEN=ghp_...

# Debug
CMBAGENT_DEBUG=false
CMBAGENT_DISABLE_DISPLAY=false

# Data paths
CMBAGENT_DATA=/path/to/cmbagent/data
```

### Agent LLM Configuration

```python
# Per-agent model configuration
agent_llm_configs = {
    'engineer': {
        'model': 'gpt-4o',
        'api_key': os.getenv('OPENAI_API_KEY'),
        'api_type': 'openai',
    },
    'researcher': {
        'model': 'claude-3-opus-20240229',
        'api_key': os.getenv('ANTHROPIC_API_KEY'),
        'api_type': 'anthropic',
    },
    'planner': {
        'model': 'gemini-2.0-flash',
        'api_key': os.getenv('GEMINI_API_KEY'),
        'api_type': 'google',
    },
}

# Create agent with custom configs
cmbagent = CMBAgent(agent_llm_configs=agent_llm_configs)
```

### Default Settings (`cmbagent/utils.py`)

```python
# Default parameters
default_temperature = 0.00001
default_top_p = 0.05
default_max_round = 50

# Default models
default_llm_model = "gpt-4o"
default_formatter_model = "gpt-4o-mini"

default_agents_llm_model = {
    'planner': 'gpt-4o',
    'plan_reviewer': 'gpt-4o',
    'engineer': 'gpt-4o',
    'researcher': 'gpt-4o',
    'idea_maker': 'gpt-4o',
    'idea_hater': 'gpt-4o',
    'camb_context': 'gpt-4o',
    'plot_judge': 'gpt-4o-mini',
}

# Chunking for RAG
default_chunking_strategy = {
    "type": "static",
    "static": {
        "max_chunk_size_tokens": 200,
        "chunk_overlap_tokens": 100
    }
}
```

---

## Usage Examples

### Basic One-Shot Execution

```python
from cmbagent import CMBAgent

cmbagent = CMBAgent()

task = """
Draw two random numbers from normal distribution, compute their sum.
Print the result clearly.
"""

cmbagent.solve(
    task,
    max_rounds=10,
    initial_agent='engineer',
    mode='one_shot'
)

# Display cost report
cmbagent.display_cost()
```

### Planning and Control

```python
from cmbagent import CMBAgent

cmbagent = CMBAgent()

task = """
1. Load the dataset from 'data.csv'
2. Perform exploratory data analysis
3. Train a linear regression model
4. Evaluate and save results
"""

cmbagent.solve(
    task,
    max_rounds=100,
    initial_agent='planner',
    shared_context={
        'maximum_number_of_steps_in_plan': 4,
        'feedback_left': 1,
    }
)
```

### Deep Research Workflow

```python
from cmbagent import planning_and_control_context_carryover

results = planning_and_control_context_carryover(
    task="Analyze the latest CMB data from Planck and compute power spectrum",
    max_plan_steps=5,
    max_n_attempts=3,
    planner_model='gpt-4o',
    engineer_model='gpt-4o',
    researcher_model='gpt-4o-mini',
    work_dir='./research_output',
    clear_work_dir=True,
)

print(f"Final context: {results['final_context']}")
print(f"Chat history length: {len(results['chat_history'])}")
```

### With Custom Agent Configurations

```python
import os
from cmbagent import CMBAgent

cmbagent = CMBAgent(
    agent_llm_configs={
        'engineer': {
            'model': 'claude-3-opus-20240229',
            'api_key': os.getenv('ANTHROPIC_API_KEY'),
            'api_type': 'anthropic',
        },
        'researcher': {
            'model': 'gemini-2.0-flash',
            'api_key': os.getenv('GEMINI_API_KEY'),
            'api_type': 'google',
        },
    },
    work_dir='./custom_output',
    verbose=True,
)
```

### With Callbacks

```python
from cmbagent import CMBAgent, planning_and_control_context_carryover
from cmbagent.callbacks import WorkflowCallbacks, StepInfo, PlanInfo

def on_step_start(step: StepInfo):
    print(f"Starting step {step.step_number}: {step.goal}")

def on_step_complete(step: StepInfo):
    print(f"Completed step {step.step_number} in {step.execution_time:.2f}s")

def on_planning_complete(plan: PlanInfo):
    print(f"Plan created with {plan.num_steps} steps")

callbacks = WorkflowCallbacks(
    on_step_start=on_step_start,
    on_step_complete=on_step_complete,
    on_planning_complete=on_planning_complete,
)

results = planning_and_control_context_carryover(
    task="Analyze stock data and create visualizations",
    callbacks=callbacks,
)
```

### Human-in-the-Loop

```python
from cmbagent import planning_and_control_context_carryover
from cmbagent.database.approval_types import ApprovalConfig, ApprovalMode

approval_config = ApprovalConfig(
    mode=ApprovalMode.ALL,  # Approve at every checkpoint
    timeout_seconds=3600,    # 1 hour timeout
)

results = planning_and_control_context_carryover(
    task="Create and execute a trading strategy",
    approval_config=approval_config,
)
```

### Resume from Step

```python
from cmbagent import planning_and_control_context_carryover

# Resume from step 3 (e.g., after failure)
results = planning_and_control_context_carryover(
    task="Long running research task",
    work_dir='./previous_run',
    restart_at_step=3,
    clear_work_dir=False,  # Don't clear, resume
)
```

---

## Development Guide

### Adding a New Agent

1. **Create agent directory**:
```bash
mkdir cmbagent/agents/my_agent
```

2. **Create Python class** (`my_agent.py`):
```python
import os
from cmbagent.base_agent import BaseAgent

class MyAgentAgent(BaseAgent):
    def __init__(self, llm_config=None, **kwargs):
        agent_id = os.path.splitext(os.path.abspath(__file__))[0]
        super().__init__(llm_config=llm_config, agent_id=agent_id, **kwargs)

    def set_agent(self, **kwargs):
        super().set_assistant_agent(**kwargs)
```

3. **Create YAML config** (`my_agent.yaml`):
```yaml
name: "my_agent"

instructions: |
    You are a specialized agent for [purpose].
    
    Your responsibilities:
    - Task 1
    - Task 2
    
    Response format:
    ...

description: |
    My agent description for display.
```

4. **Register hand-offs** in `hand_offs.py`:
```python
my_agent = cmbagent_instance.get_agent_object_from_name('my_agent')
my_agent.agent.handoffs.set_after_work(AgentTarget(some_other_agent.agent))
```

5. **Add to agent list** (if needed for specific workflows)

### Adding a New Function

1. **Create function** in `functions/` module:
```python
# functions/my_functions.py
def my_custom_function(param1: str, param2: int) -> str:
    """
    Description of what this function does.
    
    Args:
        param1: Description
        param2: Description
    
    Returns:
        Description of return value
    """
    # Implementation
    return result
```

2. **Register with agents** in `registration.py`:
```python
from cmbagent.functions.my_functions import my_custom_function

def register_my_functions(cmbagent_instance):
    engineer = cmbagent_instance.get_agent_object_from_name('engineer')
    engineer.agent.register_for_llm()(my_custom_function)
```

### Adding a New Workflow

1. **Create workflow function** in `workflows/`:
```python
# workflows/my_workflow.py
def my_workflow(
    task,
    param1=default_value,
    **kwargs
):
    """
    Description of workflow.
    
    Args:
        task: The task to execute
        param1: Description
    
    Returns:
        Dictionary with results
    """
    from cmbagent.cmbagent import CMBAgent
    
    cmbagent = CMBAgent(**kwargs)
    
    # Custom workflow logic
    
    return results
```

2. **Export in `__init__.py`**:
```python
from cmbagent.workflows.my_workflow import my_workflow

__all__ = [..., 'my_workflow']
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_engineer.py

# Run with verbose output
pytest -v tests/test_researcher_engineer_3steps.py
```

### Running the Full Stack

```bash
# Terminal 1: Start backend
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend
cd cmbagent-ui
npm install
npm run dev

# Or use CLI
cmbagent run --next
```

### Docker

```bash
# Build and run with Docker Compose
docker-compose up --build

# Access UI at http://localhost:3000
# API at http://localhost:8000
```

---

## Appendix

### Key Files Quick Reference

| Purpose | File |
|---------|------|
| Main class | `cmbagent/cmbagent.py` |
| Base agent | `cmbagent/base_agent.py` |
| Hand-offs | `cmbagent/hand_offs.py` |
| Shared context | `cmbagent/context.py` |
| Callbacks | `cmbagent/callbacks.py` |
| DB models | `cmbagent/database/models.py` |
| Workflows | `cmbagent/workflows/planning_control.py` |
| Backend entry | `backend/main.py` |
| Frontend entry | `cmbagent-ui/app/page.tsx` |
| WebSocket context | `cmbagent-ui/contexts/WebSocketContext.tsx` |

### Supported LLM Providers

| Provider | API Type | Example Model |
|----------|----------|---------------|
| OpenAI | `openai` | `gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini` |
| Anthropic | `anthropic` | `claude-3-opus`, `claude-3-sonnet` |
| Google | `google` | `gemini-2.0-flash`, `gemini-1.5-pro` |
| Azure OpenAI | `azure` | Azure-deployed models |

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "Vector store not found" | Set `make_vector_stores=True` |
| "Agent not found" | Check agent is in `agent_list` |
| Database connection error | Check `DATABASE_URL` env var |
| WebSocket disconnects | Check heartbeat, increase timeout |
| Cost not tracked | Ensure `client.total_usage_summary` exists |

---

*Documentation generated for CMBAgent v0.0.1post64*
*Last updated: January 2026*
