# CMBAgent Folder Structure

## cmbagent/ (Core Python Package)

```
cmbagent/
├── __init__.py              # Package exports & entry points
├── cmbagent.py              # CMBAgent class (main orchestrator)
├── cli.py                   # CLI entry point (`cmbagent` command)
│
├── workflows/               # Workflow execution functions
│   ├── planning_control.py  # planning_and_control_context_carryover, planning_and_control
│   ├── one_shot.py          # one_shot, human_in_the_loop
│   ├── control.py           # control (execute from existing plan)
│   └── utils.py             # clean_work_dir, load_context, load_plan
│
├── agents/                  # 50+ specialized agents
│   ├── planner/             # Planning agent
│   ├── engineer/            # Code generation agent
│   ├── researcher/          # Research agent
│   ├── executor/            # Code execution agent
│   ├── rag_agents/          # RAG-based agents (CAMB, CLASS, Cobaya, etc.)
│   └── *_response_formatter/ # Output formatters
│
├── managers/                # Agent & resource managers
│   ├── agent_manager.py     # import_non_rag_agents
│   ├── assistant_manager.py # OpenAI assistant management
│   └── cost_manager.py      # Cost tracking
│
├── processing/              # Document processing
│   ├── content_parser.py    # Markdown parsing
│   ├── document_summarizer.py # Summarization
│   └── task_preprocessor.py # Task preprocessing with arXiv
│
├── keywords/                # Keyword extraction
│   └── keyword_finder.py    # get_keywords, get_aas_keywords
│
├── database/                # Database & persistence
│   ├── models.py            # SQLAlchemy models
│   ├── repository.py        # Data access layer
│   ├── dag_builder.py       # DAG construction
│   ├── dag_executor.py      # DAG execution
│   ├── approval_manager.py  # HITL approval handling
│   └── session_manager.py   # Session management
│
├── branching/               # Workflow branching
│   ├── branch_manager.py    # Branch operations
│   └── play_from_node.py    # Resume from specific node
│
├── retry/                   # Retry logic
│   ├── retry_context_manager.py
│   └── retry_metrics.py
│
├── config/                  # Configuration
│   └── workflow_config.py   # WorkflowConfig dataclass
│
├── callbacks.py             # Workflow event callbacks
├── functions.py             # Agent function registrations
├── hand_offs.py             # Agent hand-off logic
├── rag_utils.py             # RAG agent utilities
├── utils.py                 # General utilities & defaults
├── vlm_utils.py             # Vision-language model utils
└── ocr.py                   # PDF OCR functionality
```

## backend/ (FastAPI Server)

```
backend/
├── main.py                  # FastAPI app entry point
├── run.py                   # Server runner
│
├── routers/                 # API endpoints
│   ├── arxiv.py             # /arxiv - Paper downloads
│   ├── branching.py         # /branching - Workflow branching
│   ├── enhance.py           # /enhance - Task enhancement
│   ├── nodes.py             # /nodes - DAG node operations
│   └── runs.py              # /runs - Workflow run management
│
├── services/                # Business logic
│   ├── execution_service.py # Task execution orchestration
│   └── workflow_service.py  # Workflow operations
│
├── execution/               # Execution handling
│   ├── task_executor.py     # Async task execution
│   └── dag_tracker.py       # DAG state tracking
│
├── websocket/               # WebSocket handling
│   └── handlers.py          # WS message handlers
│
├── websocket_manager.py     # WebSocket connection management
├── websocket_events.py      # Event definitions
├── event_queue.py           # Event queue for real-time updates
│
├── models/                  # Pydantic models (API schemas)
│   └── *.py                 # Request/response models
│
└── core/                    # Core utilities
    └── *.py                 # Config, dependencies
```

## Key Entry Points

| Entry Point | Location | Description |
|-------------|----------|-------------|
| `cmbagent.one_shot()` | `cmbagent/workflows/one_shot.py` | Single-shot task execution |
| `cmbagent.planning_and_control_context_carryover()` | `cmbagent/workflows/planning_control.py` | Full workflow with context |
| `cmbagent.CMBAgent` | `cmbagent/cmbagent.py` | Main agent orchestrator class |
| `cmbagent` CLI | `cmbagent/cli.py` | Command-line interface |
| FastAPI server | `backend/main.py` | REST/WebSocket API server |

## Import Patterns

```python
# Main workflow functions
from cmbagent import one_shot, planning_and_control_context_carryover, deep_research

# CMBAgent class
from cmbagent import CMBAgent

# Callbacks for event tracking
from cmbagent import WorkflowCallbacks, create_websocket_callbacks

# Utilities
from cmbagent import work_dir_default, get_keywords
```
