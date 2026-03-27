# RFP Proposal Generator — End-to-End Integration Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Directory Structure](#3-directory-structure)
4. [The 7-Stage Pipeline](#4-the-7-stage-pipeline)
5. [Phase-Based Execution Engine](#5-phase-based-execution-engine)
6. [Shared State & Context Flow](#6-shared-state--context-flow)
7. [Backend API Reference](#7-backend-api-reference)
8. [Database Layer](#8-database-layer)
9. [Phase Classes & Prompts](#9-phase-classes--prompts)
10. [Frontend UI](#10-frontend-ui)
11. [File Upload & PDF Extraction](#11-file-upload--pdf-extraction)
12. [Console Output & Real-Time Streaming](#12-console-output--real-time-streaming)
13. [Task Resumption](#13-task-resumption)
14. [Cost Tracking](#14-cost-tracking)
15. [Configuration & Model Defaults](#15-configuration--model-defaults)
16. [End-to-End User Flow](#16-end-to-end-user-flow)
17. [Error Handling](#17-error-handling)

---

## 1. Overview

The RFP Proposal Generator is a **7-stage, human-in-the-loop AI workflow** in MARS. It transforms an RFP document into a complete technical proposal through interactive stages:

1. **Requirements Analysis** → 2. **Tools & Technology** → 3. **Cloud & Infrastructure** → 4. **Implementation Plan** → 5. **Architecture Design** → 6. **Execution Strategy** → 7. **Proposal Compilation**

Each stage uses a dedicated **Phase class** (`cmbagent/phases/rfp/`) with a **generate → review** cycle (2 LLM calls per stage by default). Users can review, edit, and refine AI output between every stage.

**Key technologies:**
- **Backend:** Python, FastAPI, SQLAlchemy, asyncio
- **Phase System:** `RfpPhaseBase` → 7 phase subclasses with generate→review cycles
- **Frontend:** React, TypeScript, Next.js
- **Real-time:** WebSocket + REST polling
- **Default LLM:** GPT-5.3 (configurable per stage via `STAGE_MODEL_MAP`)
- **Mode:** `"rfp-proposal"`

---

## 2. Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React/Next.js)                      │
│                                                                       │
│  TaskList.tsx ──► RfpProposalTask.tsx (8-step wizard)                 │
│                    ├── RfpSetupPanel.tsx       (Step 0)               │
│                    ├── RfpReviewPanel.tsx      (Steps 1–6)            │
│                    ├── RfpExecutionPanel.tsx   (per-stage monitoring) │
│                    └── RfpProposalPanel.tsx    (Step 7)               │
│                                                                       │
│  useRfpTask.ts ── state management, API calls, WebSocket             │
└───────────┬──────────────────────────────┬────────────────────────────┘
            │ REST API                     │ WebSocket
            ▼                              ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                              │
│                                                                       │
│  routers/rfp.py ── REST endpoints + phase-based execution engine     │
│    _run_rfp_stage():                                                  │
│      1. _load_phase_class(stage_num)  ── dynamic importlib load      │
│      2. PhaseClass(config=...)        ── instantiate phase            │
│      3. PhaseContext(task, work_dir, shared_state)                    │
│      4. await phase.execute(ctx)      ── generate → review cycle     │
│      5. Extract output, track cost, update DB                        │
│                                                                       │
│  main.py          ── WebSocket /ws/rfp/{task_id}/{stage_num}         │
│  services/pdf_extractor.py ── rich PDF extraction (text+tables+images)│
└───────────┬──────────────────────────────┬────────────────────────────┘
            │                              │
            ▼                              ▼
┌────────────────────────┐    ┌─────────────────────────────────────────┐
│     DATABASE (SQLite)  │    │   PHASE CLASSES (cmbagent/phases/rfp/)  │
│                        │    │                                         │
│  WorkflowRun           │    │  base.py ── RfpPhaseBase                │
│  TaskStage (×7)        │    │    ├── system_prompt (property)         │
│  Session               │    │    ├── review_system_prompt (property)  │
│  CostRecord            │    │    ├── build_user_prompt(ctx) (method)  │
│                        │    │    └── execute(ctx) → PhaseResult       │
│  TaskStageRepository   │    │        ├── Generation pass (1 LLM call) │
│  CostRepository        │    │        └── Review pass(es) (n LLM calls)│
└────────────────────────┘    └─────────────────────────────────────────┘
```

---

## 3. Directory Structure

```
backend/
├── main.py                    # FastAPI app + WS endpoints (/ws/rfp/{task_id}/{stage_num})
├── models/
│   └── rfp_schemas.py         # Pydantic request/response schemas
├── routers/
│   ├── __init__.py            # Router registration
│   ├── rfp.py                 # RFP REST API + execution engine (~950 lines)
│   └── files.py               # File upload/download endpoint
├── services/
│   ├── pdf_extractor.py       # Rich PDF extraction (text, tables, images)
│   └── session_manager.py     # Session lifecycle

cmbagent/phases/rfp/
├── __init__.py                # Imports all phase classes
├── base.py                    # RfpPhaseBase — generate→review cycle engine
├── requirements_phase.py      # Stage 1: RfpRequirementsPhase
├── tools_phase.py             # Stage 2: RfpToolsPhase
├── cloud_phase.py             # Stage 3: RfpCloudPhase
├── implementation_phase.py    # Stage 4: RfpImplementationPhase
├── architecture_phase.py      # Stage 5: RfpArchitecturePhase
├── execution_phase.py         # Stage 6: RfpExecutionPhase
└── proposal_phase.py          # Stage 7: RfpProposalPhase

mars-ui/
├── app/tasks/page.tsx         # Task routing ("rfp-proposal" → RfpProposalTask)
├── types/rfp.ts               # TypeScript types and constants
├── hooks/useRfpTask.ts        # React hook for all RFP state management
└── components/
    ├── tasks/
    │   ├── TaskList.tsx        # Task catalog (lists "RFP Proposal Generator")
    │   └── RfpProposalTask.tsx # Main 8-step wizard container
    └── rfp/
        ├── RfpSetupPanel.tsx   # Step 0: RFP content + file upload
        ├── RfpReviewPanel.tsx  # Steps 1–6: edit/preview + refinement chat
        ├── RfpExecutionPanel.tsx # Per-stage execution monitoring
        └── RfpProposalPanel.tsx # Step 7: final proposal + downloads

cmbagent_workdir/sessions/{session_id}/tasks/{task_id}/input_files/
├── rfp_input.md               # Original RFP text
├── rfp_context.md             # Additional context (optional)
├── requirements.md            # Stage 1 output
├── tools.md                   # Stage 2 output
├── cloud.md                   # Stage 3 output
├── implementation.md          # Stage 4 output
├── architecture.md            # Stage 5 output
├── execution.md               # Stage 6 output
├── proposal.md                # Stage 7 output (final proposal)
└── [user-uploaded files]      # PDFs, DOCX, etc.
```

---

## 4. The 7-Stage Pipeline

### Stage 1 — Requirements Analysis

**Phase class:** `RfpRequirementsPhase` in `cmbagent/phases/rfp/requirements_phase.py`

**What it extracts:**
1. Functional Requirements
2. Non-Functional Requirements (performance, security, scalability, compliance)
3. Stakeholders
4. Constraints (budget, timeline, technology, regulatory)
5. Success Criteria
6. Risk Factors and mitigation strategies
7. Assumptions
8. Deliverables
9. Budget Analysis (critical for downstream cost-aware stages)

**Input:** `rfp_content` (user's RFP text) + `rfp_context` (optional) + uploaded file content
**Output:** `shared_state.requirements_analysis` → `requirements.md`

### Stage 2 — Tools & Technology Selection

**Phase class:** `RfpToolsPhase` in `cmbagent/phases/rfp/tools_phase.py`

**What it produces:**
- Head-to-head **comparison table** per tool category (Recommended vs Alternatives)
- **Security assessment** per tool (CVE history, compliance certs, encryption)
- Cost estimates (Monthly + Annual, USD only)
- Security Summary Matrix across all tools
- Total Tool Cost Summary
- Cost Optimization Recommendations

**Input:** `requirements_analysis` from Stage 1
**Output:** `shared_state.tools_technology` → `tools.md`

### Stage 3 — Cloud & Infrastructure Planning

**Phase class:** `RfpCloudPhase` in `cmbagent/phases/rfp/cloud_phase.py`

**What it produces:**
- Cloud Provider Comparison Matrix (AWS vs Azure vs GCP)
- Selected provider justification with data-backed reasons
- Why other providers were NOT selected
- Compute, storage, networking, security architecture
- Managed Services Comparison across providers
- Detailed cost breakdown (Monthly + Annual, USD only)
- Cost optimization strategy

**Input:** `requirements_analysis` + `tools_technology`
**Output:** `shared_state.cloud_infrastructure` → `cloud.md`

### Stage 4 — Implementation Plan

**Phase class:** `RfpImplementationPhase` in `cmbagent/phases/rfp/implementation_phase.py`

**What it produces:** Project phases, timeline, sprint planning, team composition, resource allocation, dependencies, risk mitigation, quality gates, communication plan, budget breakdown.

**Input:** `requirements_analysis` + `tools_technology` + `cloud_infrastructure`
**Output:** `shared_state.implementation_plan` → `implementation.md`

### Stage 5 — Architecture Design

**Phase class:** `RfpArchitecturePhase` in `cmbagent/phases/rfp/architecture_phase.py`

**What it produces:** High-level architecture, component design, data architecture, integration patterns, security architecture, deployment architecture, scalability design, monitoring & observability, ADRs.

**Input:** All 4 prior shared_state keys
**Output:** `shared_state.architecture_design` → `architecture.md`

### Stage 6 — Execution Strategy

**Phase class:** `RfpExecutionPhase` in `cmbagent/phases/rfp/execution_phase.py`

**What it produces:** Kickoff & onboarding, dev methodology, environment strategy, testing strategy, CI/CD, release management, go-live plan, post-launch support, knowledge transfer, KPIs, governance.

**Input:** All 5 prior shared_state keys
**Output:** `shared_state.execution_strategy` → `execution.md`

### Stage 7 — Proposal Compilation

**Phase class:** `RfpProposalPhase` in `cmbagent/phases/rfp/proposal_phase.py`

**What it produces:** Complete professional proposal document:
- Cover Page, Executive Summary, Understanding of Requirements
- Proposed Solution, Technology Stack, Cloud Infrastructure
- System Architecture, Implementation Approach, Execution Plan
- Risk Management, Pricing Summary & TCO, Team & Qualifications
- Terms & Assumptions
- **Appendices:** Detailed cost breakdowns, technology evaluation matrices, glossary (20-30+ entries), references (10-15+ citations)

**Input:** All 6 prior shared_state keys
**Output:** `proposal.md` (final compiled proposal)

---

## 5. Phase-Based Execution Engine

### Phase Class Hierarchy

```
Phase (cmbagent/phases/base.py)             # Abstract base
  └── RfpPhaseBase (cmbagent/phases/rfp/base.py)  # Generate→review engine
        ├── RfpRequirementsPhase             # Stage 1
        ├── RfpToolsPhase                    # Stage 2
        ├── RfpCloudPhase                    # Stage 3
        ├── RfpImplementationPhase           # Stage 4
        ├── RfpArchitecturePhase             # Stage 5
        ├── RfpExecutionPhase                # Stage 6
        └── RfpProposalPhase                 # Stage 7
```

### RfpPhaseBase — Core Execution

Each phase subclass provides:
- `phase_type` — Registry identifier (e.g., `"rfp_requirements"`)
- `display_name` — Human-readable name
- `shared_output_key` — Output key in shared_state dict
- `output_filename` — File to save output to
- `system_prompt` — Expert persona for generation pass
- `review_system_prompt` — Reviewer persona for review pass (inherited from base)
- `build_user_prompt(context)` — Constructs the prompt from shared_state

### Generate → Review Cycle

```
RfpPhaseBase.execute(context)
  │
  ├── 1. Build user prompt via self.build_user_prompt(context)
  │
  ├── 2. Generation pass (1 LLM call):
  │     system = self.system_prompt
  │     user   = self.build_user_prompt(context)
  │     → content (draft)
  │
  ├── 3. Review pass(es) (n_reviews × 1 LLM call each):
  │     system = self.review_system_prompt
  │     user   = "Draft document:\n\n{content}"
  │     → content (improved)
  │
  ├── 4. Save to disk: {work_dir}/input_files/{output_filename}
  │
  └── 5. Return PhaseResult with:
        output_data = {
          "shared": { shared_output_key: content },
          "artifacts": { "model": model },
          "cost": { "prompt_tokens": X, "completion_tokens": Y }
        }
```

**Default config:** model=`gpt-4o`, temperature=`0.7`, max_completion_tokens=`16384`, n_reviews=`1`

With `n_reviews=1`, each stage makes **2 LLM calls** (1 generate + 1 review). Total for 7 stages: **14 LLM calls**.

### Review System Prompt

The shared review prompt (in `RfpPhaseBase`) enforces:
1. Fix factual errors, strengthen weak sections
2. Ensure all cost figures are present and consistent
3. Verify comparison tables for every tool/technology
4. Verify security comparisons for major tools and services
5. Replace ALL placeholder text (`[Insert ...]`) with actual content
6. Ensure USD-only currency
7. Verify cost tables have Monthly + Annual columns (Annual = Monthly × 12)
8. Verify appendices contain real content (not just descriptions)
9. Polish to enterprise-quality prose

### Dynamic Phase Loading

The router loads phases dynamically via `importlib` to avoid circular imports:

```python
_PHASE_CLASSES = {
    1: "cmbagent.phases.rfp.requirements_phase:RfpRequirementsPhase",
    2: "cmbagent.phases.rfp.tools_phase:RfpToolsPhase",
    # ... stages 3-7
}

def _load_phase_class(stage_num):
    import importlib
    ref = _PHASE_CLASSES[stage_num]
    module_path, cls_name = ref.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name)
```

### Stage Execution Flow (`_run_rfp_stage`)

```python
async def _run_rfp_stage(task_id, stage_num, work_dir, rfp_content,
                          rfp_context, shared_state, config_overrides, session_id):
    # 1. Set up console capture (stdout → WebSocket buffer)
    sys.stdout = _ConsoleCapture(buf_key, old_stdout)

    # 2. Load and instantiate Phase class
    PhaseClass = _load_phase_class(stage_num)
    phase = PhaseClass(config=PhaseClass.config_class(model=model, n_reviews=n_reviews))

    # 3. Build PhaseContext with accumulated shared_state
    ctx = PhaseContext(
        workflow_id=f"rfp_{task_id}",
        task=rfp_content,
        work_dir=work_dir,
        shared_state={**shared_state, "rfp_context": rfp_context},
    )

    # 4. Execute phase (generate → review cycle)
    result = await phase.execute(ctx)

    # 5. Extract content from result
    content = result.context.output_data["shared"][shared_key]

    # 6. Track cost
    cost_repo.record_cost(parent_run_id=task_id, model=model, ...)

    # 7. Save to file + update DB stage status
    repo.update_stage_status(stage.id, status="completed", output_data=output_data)
```

---

## 6. Shared State & Context Flow

Each stage reads from all prior stages and writes its own output:

```
Stage 1 → { requirements_analysis }
Stage 2 → { requirements_analysis, tools_technology }
Stage 3 → { requirements_analysis, tools_technology, cloud_infrastructure }
Stage 4 → { ..., implementation_plan }
Stage 5 → { ..., architecture_design }
Stage 6 → { ..., execution_strategy }
Stage 7 → reads all 6 keys → writes proposal.md
```

**Reconstruction:** `build_shared_state()` queries all completed `TaskStage` records and merges their `output_data["shared"]` dicts:

```python
def build_shared_state(task_id, up_to_stage, db, session_id="rfp"):
    repo = _get_stage_repo(db, session_id)
    stages = repo.list_stages(parent_run_id=task_id)
    shared = {}
    for stage in stages:
        if stage.stage_number < up_to_stage and stage.status == "completed":
            if stage.output_data and "shared" in stage.output_data:
                shared.update(stage.output_data["shared"])
    return shared
```

**Human edits flow forward:** When a user edits a stage's content, both the DB and filesystem are updated. The next stage reads the edited version.

---

## 7. Backend API Reference

All endpoints are prefixed with `/api/rfp/`. Source: `backend/routers/rfp.py`.

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/rfp/create` | Create new task with 7 pending stages |
| PATCH | `/{task_id}/description` | Update RFP text/context (for auto-created tasks) |
| GET | `/api/rfp/recent` | List incomplete tasks for resume flow |
| GET | `/{task_id}` | Full task state (stages, progress %, cost) |
| POST | `/{task_id}/stages/{N}/execute` | Execute stage in background |
| GET | `/{task_id}/stages/{N}/content` | Get stage output content |
| PUT | `/{task_id}/stages/{N}/content` | Save user edits |
| POST | `/{task_id}/stages/{N}/refine` | LLM refinement of content |
| GET | `/{task_id}/stages/{N}/console` | Console output (polling) |
| POST | `/{task_id}/reset-from/{N}` | Reset stage N+ back to pending |
| GET | `/{task_id}/download/{filename}` | Download artifact file |
| DELETE | `/{task_id}` | Delete task + work directory |

### WebSocket Endpoint

**URL:** `ws://host/ws/rfp/{task_id}/{stage_num}`

| Event | When |
|-------|------|
| `status` | On connection |
| `console_output` | Every 1s with new console lines |
| `stage_completed` | Stage finished successfully |
| `stage_failed` | Stage failed with error |

### Pydantic Schemas (`backend/models/rfp_schemas.py`)

| Schema | Type | Fields |
|--------|------|--------|
| `RfpCreateRequest` | Request | `task`, `rfp_context?`, `config?`, `work_dir?` |
| `RfpExecuteRequest` | Request | `config_overrides?` |
| `RfpContentUpdateRequest` | Request | `content`, `field` |
| `RfpRefineRequest` | Request | `message`, `content` |
| `RfpCreateResponse` | Response | `task_id`, `work_dir`, `stages[]` |
| `RfpStageContentResponse` | Response | `stage_number`, `status`, `content`, `shared_state` |
| `RfpRefineResponse` | Response | `refined_content`, `message` |
| `RfpTaskStateResponse` | Response | Full task state with stages, progress, cost |
| `RfpRecentTaskResponse` | Response | Summary for resume flow |

---

## 8. Database Layer

Source: `cmbagent/database/models.py`, `cmbagent/database/repository.py`

### Models

**WorkflowRun** — Parent record for an RFP task:

| Column | RFP Usage |
|--------|-----------|
| `id` | Task UUID |
| `session_id` | FK → Session |
| `mode` | `"rfp-proposal"` |
| `agent` | `"phase_orchestrator"` |
| `model` | `"gpt-4o"` |
| `status` | `"executing"` → `"completed"` / `"failed"` |
| `task_description` | User's RFP text |
| `meta` | `{ work_dir, rfp_context, config, session_id, orchestration: "phase-based" }` |

**TaskStage** — Individual stage tracking (7 per task):

| Column | Description |
|--------|-------------|
| `id` | UUID primary key |
| `parent_run_id` | FK → WorkflowRun.id |
| `stage_number` | 1–7 |
| `stage_name` | `requirements_analysis`, `tools_technology`, etc. |
| `status` | `pending` → `running` → `completed` / `failed` |
| `output_data` | `{ shared: { key: content }, artifacts: { model }, cost: { tokens } }` |
| `output_files` | List of generated file names |
| `error_message` | Error text if failed |

**CostRecord** — Per-LLM-call cost tracking:

| Column | Description |
|--------|-------------|
| `parent_run_id` | FK → WorkflowRun.id |
| `model` | Model used (e.g., `"gpt-4o"`) |
| `prompt_tokens` | Input tokens |
| `completion_tokens` | Output tokens |
| `cost_usd` | Calculated cost |

### Repositories

**TaskStageRepository:** `create_stage()`, `list_stages()`, `update_stage_status()`, `get_task_progress()`
**CostRepository:** `record_cost()`, `get_task_total_cost()`, `get_session_cost()`

---

## 9. Phase Classes & Prompts

Source: `cmbagent/phases/rfp/`

### Phase Properties

| Stage | Phase Class | phase_type | shared_output_key | output_filename | System Prompt Persona |
|-------|-------------|------------|-------------------|-----------------|-----------------------|
| 1 | `RfpRequirementsPhase` | `rfp_requirements` | `requirements_analysis` | `requirements.md` | Expert Business Analyst (15+ years) |
| 2 | `RfpToolsPhase` | `rfp_tools` | `tools_technology` | `tools.md` | Senior Solutions Architect & Technology Evaluator (20+ years) |
| 3 | `RfpCloudPhase` | `rfp_cloud` | `cloud_infrastructure` | `cloud.md` | Cloud Infrastructure Architect (20+ years, AWS/Azure/GCP) |
| 4 | `RfpImplementationPhase` | `rfp_implementation` | `implementation_plan` | `implementation.md` | Senior Project Manager & Delivery Lead |
| 5 | `RfpArchitecturePhase` | `rfp_architecture` | `architecture_design` | `architecture.md` | Principal System Architect |
| 6 | `RfpExecutionPhase` | `rfp_execution` | `execution_strategy` | `execution.md` | Delivery Executive & Program Manager |
| 7 | `RfpProposalPhase` | `rfp_proposal` | `proposal_compilation` | `proposal.md` | World-Class Proposal Writer (Fortune 500, $10M–$500M) |

### Prompt Quality Rules (enforced across phases)

- **USD only** — All costs must be in USD ($), never INR/EUR/GBP
- **Cost table format** — Both Monthly and Annual columns, Annual = Monthly × 12, no empty cells
- **No placeholders** — Zero bracket-enclosed placeholder text (`[Insert ...]` forbidden)
- **Comparison tables** — Every tool/technology must have head-to-head comparison vs alternatives
- **Security assessment** — CVE history, compliance certs, encryption features per tool
- **Budget awareness** — All recommendations must fit within the RFP's stated budget

---

## 10. Frontend UI

### Type Definitions (`mars-ui/types/rfp.ts`)

Key types: `RfpTaskState`, `RfpStage`, `RfpWizardStep` (0–7), `RfpStageConfig`

Constants: `RFP_STEP_LABELS`, `RFP_WIZARD_STEP_TO_STAGE`, `RFP_STAGE_SHARED_KEYS`, `RFP_STAGE_NAMES`, `RFP_AVAILABLE_MODELS` (9 models)

### State Management Hook (`mars-ui/hooks/useRfpTask.ts`)

`useRfpTask()` provides: `taskId`, `taskState`, `currentStep`, `isExecuting`, `editableContent`, `consoleOutput`, `uploadedFiles`, `lastExtractedText`

Actions: `createTask()`, `executeStage()`, `fetchStageContent()`, `saveStageContent()`, `refineContent()`, `uploadFile()`, `resumeTask()`, `deleteTask()`, `resetFromStage()`

### Wizard Container (`mars-ui/components/tasks/RfpProposalTask.tsx`)

8-step wizard with `Stepper` navigation:

| Step | Component | Stage |
|------|-----------|-------|
| 0 | `RfpSetupPanel` | (no stage) |
| 1–6 | `RfpReviewPanel` | Stages 1–6 |
| 7 | `RfpProposalPanel` | Stage 7 |

### Panel Components

- **RfpSetupPanel** — File upload (above textarea), RFP content textarea (auto-populated from PDF), additional context, "Analyze Requirements" button
- **RfpReviewPanel** — 60% editor/preview + 40% refinement chat, auto-save (1s debounce), stage execution monitoring
- **RfpProposalPanel** — Success banner, proposal preview, download links for all 7 artifacts

---

## 11. File Upload & PDF Extraction

### Upload Flow

`POST /api/files/upload` → saves file to `input_files/` → extracts text from PDFs → returns `extracted_text` in response

### Rich PDF Extraction (`backend/services/pdf_extractor.py`)

Uses PyMuPDF (fitz) to extract:
- **Text** — Block-level extraction with table region deduplication
- **Tables** — `page.find_tables()` → markdown table format
- **Images** — Dimensions, format descriptions
- Output cap: 500KB

### File Context Injection

`_build_rfp_context()` scans uploaded files (excluding auto-generated .md files) and builds a context string appended to `rfp_context` before each stage execution.

---

## 12. Console Output & Real-Time Streaming

### Capture

`_ConsoleCapture` intercepts stdout/stderr during stage execution → thread-safe buffer keyed by `{task_id}:{stage_num}`

### Delivery

1. **REST polling** — `GET /api/rfp/{task_id}/stages/{N}/console?since=X` every 2 seconds
2. **WebSocket** — `ws://host/ws/rfp/{task_id}/{N}` sends `console_output` events every 1 second, `stage_completed`/`stage_failed` on finish

---

## 13. Task Resumption

`GET /api/rfp/recent` → lists incomplete tasks → user selects → `resumeTask(taskId)` loads full state and sets wizard position based on stage statuses (running → reconnect WS, completed → advance, pending/failed → stop).

---

## 14. Cost Tracking

Each LLM call's token usage is recorded via `CostRepository`:
- Input tokens × $0.002/1K + output tokens × $0.008/1K (GPT-4.1 pricing)
- Per-stage cost stored in `output_data["cost"]`
- Total cost exposed via `GET /api/rfp/{task_id}` → `total_cost_usd`
- Displayed in header bar, execution panel, and proposal success banner

---

## 15. Configuration & Model Defaults

### Stage Definitions (`STAGE_DEFS`)

| Stage | Name | Shared Key | Output File |
|-------|------|------------|-------------|
| 1 | `requirements_analysis` | `requirements_analysis` | `requirements.md` |
| 2 | `tools_technology` | `tools_technology` | `tools.md` |
| 3 | `cloud_infrastructure` | `cloud_infrastructure` | `cloud.md` |
| 4 | `implementation_plan` | `implementation_plan` | `implementation.md` |
| 5 | `architecture_design` | `architecture_design` | `architecture.md` |
| 6 | `execution_strategy` | `execution_strategy` | `execution.md` |
| 7 | `proposal_compilation` | `proposal_compilation` | `proposal.md` |

### Phase Config Defaults (`RfpPhaseConfig`)

| Parameter | Default | Notes |
|-----------|---------|-------|
| `model` | `gpt-4o` | Configurable via `config_overrides` or `STAGE_MODEL_MAP` |
| `temperature` | `0.7` | Balanced creativity/consistency (omitted for reasoning models like o3-mini) |
| `max_completion_tokens` | `16384` | Sufficient for detailed markdown |
| `n_reviews` | `1` | 1 review pass (2 LLM calls total per stage) |
| `review_model` | `None` (same as model) | Can use a different model for review |

### Stage-to-Model Map (`STAGE_MODEL_MAP`)

All stages use `gpt-4o` for consistent, reliable results.  Users can override per-stage via `config_overrides` in the execute request.

| Stage | Model |
|-------|-------|
| 1. Requirements Analysis | `gpt-4o` |
| 2. Tools & Technology | `gpt-4o` |
| 3. Cloud & Infrastructure | `gpt-4o` |
| 4. Implementation Plan | `gpt-4o` |
| 5. Architecture Design | `gpt-4o` |
| 6. Execution Strategy | `gpt-4o` |
| 7. Proposal Compilation | `gpt-4o` |

> **Azure deployment:** Ensure `AZURE_OPENAI_DEPLOYMENT` is set to your gpt-4o deployment name.

### Available Models (10)

GPT-5.3, GPT-4.1, GPT-4.1 Mini, GPT-4o, GPT-4o Mini, o3-mini, Gemini 2.5 Pro, Gemini 2.5 Flash, Claude Sonnet 4, Claude 3.5 Sonnet

---

## 16. End-to-End User Flow

### Step 0: Setup
1. User selects "RFP Proposal Generator" on Tasks page
2. Uploads RFP document (PDF auto-extracted to textarea) + optional context
3. Clicks "Analyze Requirements" → `POST /api/rfp/create` + `executeStage(1)`

### Steps 1–6: Iterative Review
1. Stage executes in background (`_run_rfp_stage` → `phase.execute()`)
2. Live console output via WebSocket
3. On completion: split-view editor (60%) + refinement chat (40%)
4. User reviews, edits, refines → clicks "Next" → saves edits → triggers next stage

### Step 7: Proposal Compilation
1. `executeStage(7)` — all 6 prior outputs injected into prompt
2. LLM compiles comprehensive proposal with all sections + appendices
3. Success banner + proposal preview + download links for all 7 artifacts

---

## 17. Error Handling

Stages fail for: LLM errors (empty response, API failure), infrastructure issues (rate limits, network), or data issues (missing shared state).

| Error | Fix |
|-------|-----|
| `openai.AuthenticationError` | Set valid `OPENAI_API_KEY` |
| `openai.RateLimitError` | Wait and retry, or use different model |
| Empty response | Retry (transient API issue) |
| `Stage N must be completed first` | Complete prior stages (strict ordering enforced) |
| Large prompt truncation (stages 5-7) | Use model with larger context (GPT-4.1 = 1M tokens) |

Failures are: stored in `TaskStage.error_message`, logged with full traceback, sent via WebSocket as `stage_failed` event, shown in UI with Retry button.
