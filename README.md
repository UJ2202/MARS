# MARS - Multi-Agent Research System

A multi-agent system for autonomous discovery in cosmology and astrophysics research. Built by cosmologists, powered by [AG2](https://github.com/ag2ai/ag2) (AutoGen 2). MARS orchestrates 50+ specialized AI agents that plan, execute code, retrieve research papers, and collaborate to solve complex scientific problems.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Docker Deployment](#docker-deployment)
- [Project Structure](#project-structure)
- [Backend API](#backend-api)
- [Frontend UI](#frontend-ui)
- [Agent System](#agent-system)
- [Workflow Types](#workflow-types)
- [Database](#database)
- [External Tools](#external-tools)
- [Testing](#testing)
- [License](#license)

---

## Architecture Overview

MARS is composed of three main layers:

```
┌─────────────────────────────────────────────────┐
│                  Frontend (UI)                   │
│           Next.js 14 / React 18 / TailwindCSS    │
│     Real-time updates via Socket.IO, DAG viz     │
├─────────────────────────────────────────────────┤
│                 Backend (API)                    │
│          FastAPI / Uvicorn / WebSockets           │
│   REST endpoints, task execution, event stream   │
├─────────────────────────────────────────────────┤
│              Agent Framework (Core)              │
│           AG2 multi-agent orchestration           │
│   50+ specialized agents, DAG execution, RAG     │
├─────────────────────────────────────────────────┤
│               Storage & Data                     │
│     SQLAlchemy (SQLite/PostgreSQL) + Alembic      │
│       File tracking, cost records, events        │
└─────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 14, React 18, TailwindCSS | Web UI with real-time updates |
| Backend | FastAPI, Uvicorn | REST API and WebSocket server |
| Agent Framework | AG2 (AutoGen 2) | Multi-agent orchestration |
| Real-Time | WebSockets, Socket.IO | Live task updates and streaming |
| Database | SQLAlchemy, SQLite / PostgreSQL | Persistence and tracking |
| DAG Visualization | @xyflow/react | Interactive graph rendering |
| Science | CAMB, CLASS, Cobaya, Astropy | Astronomy and cosmology tools |
| External Tools | CrewAI, LangChain | Tool integration layer |
| Containerization | Docker, Docker Compose | Production deployment |

---

## Prerequisites

- **Python** >= 3.12
- **Node.js** >= 18
- **npm** >= 9
- **Git**
- At least one LLM API key (OpenAI, Anthropic, Gemini, etc.)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/CMBAgents/cmbagent.git
cd cmbagent
```

### 2. Install Python dependencies

```bash
# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install the core package in editable mode
pip install -e .
```

#### Optional dependency groups

```bash
# Astronomy/astrophysics (CAMB, Astropy, HEALPy, emcee)
pip install -e ".[astro]"

# Data science and visualization (scipy, matplotlib, xgboost, etc.)
pip install -e ".[data]"

# Jupyter notebook support
pip install -e ".[jupyter]"

# Install everything
pip install -e ".[astro,data,jupyter]"
```

### 3. Install frontend dependencies

```bash
cd cmbagent-ui
npm install
cd ..
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Required - at least one LLM provider key
OPENAI_API_KEY=your-openai-api-key

# Optional - additional LLM providers
ANTHROPIC_API_KEY=your-anthropic-api-key
GEMINI_API_KEY=your-gemini-api-key
PERPLEXITY_API_KEY=your-perplexity-api-key
MISTRAL_API_KEY=your-mistral-api-key

# Optional - Backend configuration
CMBAGENT_CORS_ORIGINS=http://localhost:3000,http://localhost:3001  # Comma-separated list of allowed CORS origins
```

### Frontend Configuration

Create `cmbagent-ui/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

This tells the UI where to find the backend API. Adjust if your backend runs on a different host or port.

---

## Running the Application

MARS requires both the backend and frontend to be running.

### Start the Backend

```bash
cd backend
python run.py
```

The backend starts on `http://localhost:8000`:
- **REST API**: `http://localhost:8000`
- **Swagger Docs**: `http://localhost:8000/docs`
- **WebSocket**: `ws://localhost:8000/ws/{task_id}`

### Start the Frontend (UI)

In a separate terminal:

```bash
cd cmbagent-ui
npm run dev
```

The UI starts on `http://localhost:3000` and opens automatically in your browser.

### Both Running

Once both are up:
1. Open `http://localhost:3000` in your browser
2. Configure your API credentials via the credentials modal in the UI
3. Create a new task or session to begin

---

## Docker Deployment

### Using Docker Compose (recommended)

```bash
# Set your API keys in .env, then:
docker-compose up --build
```

This starts the full application:
- **UI**: `http://localhost:3000`
- **API**: `http://localhost:8000`

### Using Docker directly

```bash
# Standard build
docker build -t mars .
docker run -p 3000:3000 -p 8000:8000 \
  -e OPENAI_API_KEY=your-key \
  mars

# Hugging Face Spaces build
docker build -f Dockerfile.nextjs -t mars-hf .
docker run -p 7860:7860 -p 8000:8000 \
  -e OPENAI_API_KEY=your-key \
  mars-hf
```

---

## Project Structure

```
mars/
├── backend/                    # FastAPI backend application
│   ├── run.py                 # Backend entry point
│   ├── main.py                # FastAPI app assembly
│   ├── core/                  # App configuration and initialization
│   ├── routers/               # API endpoint handlers
│   │   ├── runs.py            #   Task run management
│   │   ├── sessions.py        #   Session management
│   │   ├── phases.py          #   Workflow phase execution
│   │   ├── tasks.py           #   Task creation and status
│   │   ├── copilot.py         #   Copilot endpoints
│   │   ├── files.py           #   File management
│   │   ├── branching.py       #   Branching workflows
│   │   ├── arxiv.py           #   ArXiv paper retrieval
│   │   ├── nodes.py           #   DAG node management
│   │   ├── enhance.py         #   Task enhancement
│   │   ├── credentials.py     #   API credential management
│   │   └── health.py          #   Health check
│   ├── models/                # Pydantic request/response schemas
│   ├── services/              # Business logic layer
│   ├── execution/             # Task execution engine
│   ├── websocket/             # WebSocket handlers and events
│   └── callbacks/             # Event callback handlers
│
├── cmbagent/                  # Core Python package (agent library)
│   ├── agents/                # 50+ specialized agent definitions
│   ├── orchestrator/          # Agent orchestration and group chat
│   ├── handoffs/              # Agent-to-agent transition config
│   ├── external_tools/        # External tool integrations
│   ├── database/              # SQLAlchemy models and migrations
│   │   └── migrations/        #   Alembic migration scripts
│   ├── dag/                   # DAG builder, executor, tracker
│   ├── processing/            # Document processing and OCR
│   └── cli.py                 # CLI entry point
│
├── cmbagent-ui/               # Next.js frontend application
│   ├── app/                   # Next.js app directory (pages)
│   ├── components/            # React components
│   │   ├── dag/               #   DAG visualization
│   │   ├── SessionManager/    #   Session management UI
│   │   ├── branching/         #   Branching workflow UI
│   │   ├── metrics/           #   Performance metrics display
│   │   ├── ApprovalChatPanel  #   Human-in-the-loop approval
│   │   ├── CopilotView        #   Copilot interface
│   │   ├── FileBrowser        #   File browser
│   │   ├── ConsoleOutput      #   Console output streaming
│   │   ├── ModelSelector      #   Model selection
│   │   └── ...                #   And more
│   ├── contexts/              # React context providers
│   ├── hooks/                 # Custom React hooks
│   ├── lib/                   # Utility functions
│   └── types/                 # TypeScript type definitions
│
├── tests/                     # Test suite
├── examples/                  # Usage examples
├── data/                      # Data files
├── evals/                     # Evaluation datasets
│
├── pyproject.toml             # Python project configuration
├── docker-compose.yml         # Docker Compose setup
├── Dockerfile                 # Standard Docker build
├── Dockerfile.nextjs          # Hugging Face Spaces Docker build
├── alembic.ini                # Database migration config
└── LICENSE                    # Apache 2.0
```

---

## Backend API

The backend is a FastAPI application providing REST endpoints and WebSocket connections.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/tasks` | Create a new task |
| `GET` | `/tasks/{id}` | Get task status |
| `POST` | `/runs` | Start a task run |
| `GET` | `/runs/{id}` | Get run details |
| `POST` | `/sessions` | Create a session |
| `GET` | `/sessions` | List sessions |
| `POST` | `/phases/{id}/execute` | Execute a workflow phase |
| `GET` | `/files/{run_id}` | List files for a run |
| `POST` | `/enhance` | Enhance a task description |
| `POST` | `/credentials` | Set API credentials |
| `WS` | `/ws/{task_id}` | WebSocket for real-time updates |

Full interactive API documentation is available at `http://localhost:8000/docs` when the backend is running.

### WebSocket Events

Connect to `ws://localhost:8000/ws/{task_id}` to receive real-time events:

- **status** - Task status changes
- **output** - Agent output streaming
- **dag_update** - DAG execution progress
- **approval_request** - Human-in-the-loop approval requests
- **cost_update** - Token usage and cost tracking
- **file_created** - New file notifications
- **error** - Error events

---

## Frontend UI

The UI is a Next.js 14 application with the following features:

- **Task Management** - Create, monitor, and manage research tasks
- **Real-Time Streaming** - Live agent output via WebSocket
- **DAG Visualization** - Interactive graph showing task dependencies and execution flow
- **Session Management** - Create and manage research sessions with context persistence
- **Human-in-the-Loop** - Approval panel for reviewing and approving agent plans
- **Copilot Mode** - Interactive copilot interface for guided research
- **File Browser** - Browse and download files generated by agents
- **Branching Workflows** - Create and manage branching execution paths
- **Metrics Dashboard** - Token usage, cost tracking, and performance metrics
- **Model Selection** - Choose between different LLM providers
- **Credentials Management** - Configure API keys through the UI

---

## Agent System

MARS includes 50+ specialized agents organized by function:

### Planning Agents
| Agent | Purpose |
|-------|---------|
| `planner` | Creates research plans and task breakdowns |
| `task_improver` | Refines and enhances task descriptions |
| `plan_recorder` | Records and persists plans |
| `plan_reviewer` | Reviews plans for quality and completeness |
| `plan_setter` | Sets active plan for execution |

### Execution Agents
| Agent | Purpose |
|-------|---------|
| `engineer` | Writes and modifies code |
| `researcher` | Conducts research and analysis |
| `executor` | Executes code in sandboxed environment |
| `executor_bash` | Executes shell commands |
| `installer` | Installs required packages |

### Domain-Specific Agents (Cosmology)
| Agent | Purpose |
|-------|---------|
| `camb_context` | CAMB power spectrum context |
| `classy_context` | CLASS cosmology context |
| `cobaya_response_formatter` | Cobaya inference formatting |
| `rag_agents` | Retrieval-augmented generation for domain data |
| `retrieve_assistant` | Document retrieval |

### Utility Agents
| Agent | Purpose |
|-------|---------|
| `summarizer` | Summarizes results and outputs |
| `terminator` | Handles task completion |
| `idea_maker` | Generates research ideas |
| `idea_hater` | Critically evaluates ideas |
| `web_surfer` | Web browsing and search |
| `perplexity` | Perplexity AI search |
| `copilot_control` | Copilot workflow control |

---

## Workflow Types

MARS supports multiple workflow types for different research scenarios:

| Workflow | Description |
|----------|-------------|
| `planning_and_control` | Standard two-phase: plan first, then execute |
| `deep_research` | Planning with context carryover across phases |
| `one_shot` | Single-pass task execution without planning |
| `human_in_the_loop` | Interactive workflow with approval checkpoints |
| `copilot` | Guided research with copilot assistance |
| `copilot_async` | Async copilot for longer tasks |
| `quick_task` | Fast execution for simple tasks |
| `planned_task` | Execute from a pre-defined plan |
| `interactive_session` | Real-time interactive mode |
| `control` | Execute from an existing plan |

---

## Database

MARS uses SQLAlchemy with Alembic for database management.

### Default: SQLite

Out of the box, MARS uses SQLite (`cmbagent.db` in the project root). No additional setup required.

### Production: PostgreSQL

For production deployments, configure PostgreSQL:

1. Install PostgreSQL and create a database
2. Update the database URL in the backend configuration
3. Run migrations:

```bash
alembic upgrade head
```

### Database Tables

| Table | Purpose |
|-------|---------|
| `runs` | Workflow execution records |
| `sessions` | User sessions and context |
| `phases` | Phase execution records |
| `nodes` | DAG nodes and dependencies |
| `approvals` | Human-in-the-loop approval records |
| `files` | Tracked input/output files |
| `cost_records` | Token usage and cost tracking |
| `events` | Execution events and logs |

### Running Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "description of change"

# Rollback one migration
alembic downgrade -1
```

---

## External Tools

MARS integrates 30+ external tools through CrewAI and LangChain adapters:

### Research Tools
- **ArXiv** - Search and download academic papers
- **Wikipedia** - Query Wikipedia articles
- **DuckDuckGo** - Web search
- **Perplexity** - AI-powered search

### Code and File Tools
- **Python REPL** - Execute Python code
- **Shell** - Execute shell commands
- **File operations** - Read, write, and manage files
- **Code analysis** - Code search and analysis

### Web Tools
- **Web scraping** - Extract content from web pages
- **HTTP requests** - Make API calls
- **GitHub search** - Search GitHub repositories

---

## Testing

```bash
# Run all tests
pytest

# Run tests excluding slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_specific.py
```

---

## Logs

Backend logs are written to:

```
~/.cmbagent/logs/backend.log
```

---

## License

[Apache License 2.0](LICENSE)

---

## Links

- **Repository**: [github.com/CMBAgents/cmbagent](https://github.com/CMBAgents/cmbagent)
- **Maintainer**: CMBAgents (boris.bolliet@cmbagent.community)
