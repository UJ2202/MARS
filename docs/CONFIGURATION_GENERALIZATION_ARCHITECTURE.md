# Configuration Generalization Architecture

> **Design Document: Moving All Configuration to UI**

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Target Architecture](#target-architecture)
4. [Configuration Categories](#configuration-categories)
5. [Database Schema Design](#database-schema-design)
6. [Backend API Design](#backend-api-design)
7. [Frontend Components Design](#frontend-components-design)
8. [Runtime Configuration Loading](#runtime-configuration-loading)
9. [Migration Strategy](#migration-strategy)
10. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

### Goal

Transform CMBAgent from a code-configured system to a fully UI-configurable system where:

1. **All settings** are editable through the web interface
2. **Agent configurations** (instructions, models, temperature) are stored in database
3. **Workflow parameters** are adjustable per-run
4. **Hand-off patterns** can be customized visually
5. **API keys** are managed securely through UI
6. **Presets/templates** allow saving and reusing configurations

### Benefits

- No code changes required to adjust behavior
- Non-technical users can customize the system
- Easy A/B testing of different configurations
- Audit trail of configuration changes
- Multi-tenant support with per-user configurations

---

## Current State Analysis

### Configuration Sources Today

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT CONFIGURATION SOURCES                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────┐   ┌────────────────────────────────────┐      │
│  │ Environment Variables    │   │ Python Code (utils.py)             │      │
│  ├──────────────────────────┤   ├────────────────────────────────────┤      │
│  │ OPENAI_API_KEY           │   │ default_llm_model = "gpt-4.1"      │      │
│  │ ANTHROPIC_API_KEY        │   │ default_temperature = 0.00001     │      │
│  │ GEMINI_API_KEY           │   │ default_top_p = 0.05              │      │
│  │ DATABASE_URL             │   │ default_max_round = 50            │      │
│  │ CMBAGENT_DATA            │   │ default_agents_llm_model = {...}  │      │
│  │ CMBAGENT_DEBUG           │   │ default_chunking_strategy = {...} │      │
│  └──────────────────────────┘   └────────────────────────────────────┘      │
│                                                                              │
│  ┌──────────────────────────┐   ┌────────────────────────────────────┐      │
│  │ Agent YAML Files         │   │ CMBAgent Constructor               │      │
│  ├──────────────────────────┤   ├────────────────────────────────────┤      │
│  │ agents/engineer/         │   │ CMBAgent(                          │      │
│  │   engineer.yaml:         │   │   temperature=0.1,                 │      │
│  │     name: "engineer"     │   │   agent_llm_configs={...},         │      │
│  │     instructions: "..."  │   │   agent_instructions={...},        │      │
│  │     description: "..."   │   │   skip_rag_agents=True,            │      │
│  │                          │   │   mode="planning_and_control",     │      │
│  │ agents/rag_agents/       │   │   ...                              │      │
│  │   camb.yaml:             │   │ )                                  │      │
│  │     assistant_config:    │   │                                    │      │
│  │       assistant_id: ...  │   │                                    │      │
│  │       temperature: ...   │   │                                    │      │
│  └──────────────────────────┘   └────────────────────────────────────┘      │
│                                                                              │
│  ┌──────────────────────────┐   ┌────────────────────────────────────┐      │
│  │ Shared Context           │   │ Workflow Config (code)             │      │
│  ├──────────────────────────┤   ├────────────────────────────────────┤      │
│  │ context.py:              │   │ workflow_config.py:                │      │
│  │   feedback_left: 1       │   │   max_rounds_planning: 50          │      │
│  │   max_n_attempts: 3      │   │   max_plan_steps: 3                │      │
│  │   evaluate_plots: False  │   │   n_plan_reviews: 1                │      │
│  │   database_path: "data/" │   │   planner_model: "gpt-4o"          │      │
│  └──────────────────────────┘   └────────────────────────────────────┘      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Problems with Current Approach

| Problem | Impact |
|---------|--------|
| Hardcoded in Python | Requires code deployment to change |
| YAML files scattered | Hard to manage 45+ agent configs |
| No version control for config changes | Can't track who changed what |
| No per-user customization | All users share same settings |
| API keys in environment | Security risk, hard to rotate |
| Constructor params complex | Too many options to remember |

---

## Target Architecture

### Unified Configuration System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TARGET: UI-DRIVEN CONFIGURATION                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        FRONTEND (React/Next.js)                      │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                       │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │    │
│  │  │ Global      │ │ Agent       │ │ Workflow    │ │ Credentials │     │    │
│  │  │ Settings    │ │ Config      │ │ Templates   │ │ Manager     │     │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │    │
│  │                                                                       │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │    │
│  │  │ Hand-off    │ │ Model       │ │ Context     │ │ Presets     │     │    │
│  │  │ Designer    │ │ Selector    │ │ Editor      │ │ Manager     │     │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │    │
│  │                                                                       │    │
│  └───────────────────────────────────┬─────────────────────────────────┘    │
│                                      │                                       │
│                                      ▼ REST API                              │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        BACKEND (FastAPI)                             │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────┐     │    │
│  │  │                 Configuration Service                        │     │    │
│  │  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐       │     │    │
│  │  │  │ ConfigManager │ │ AgentRegistry │ │ TemplateStore │       │     │    │
│  │  │  └───────────────┘ └───────────────┘ └───────────────┘       │     │    │
│  │  └─────────────────────────────────────────────────────────────┘     │    │
│  │                                                                       │    │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐               │    │
│  │  │ /api/config   │ │ /api/agents   │ │ /api/templates│               │    │
│  │  └───────────────┘ └───────────────┘ └───────────────┘               │    │
│  │                                                                       │    │
│  └───────────────────────────────────┬─────────────────────────────────┘    │
│                                      │                                       │
│                                      ▼                                       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        DATABASE (PostgreSQL)                         │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                       │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │    │
│  │  │ global_      │ │ agent_       │ │ workflow_    │ │ credentials  │ │    │
│  │  │ config       │ │ config       │ │ templates    │ │              │ │    │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ │    │
│  │                                                                       │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │    │
│  │  │ handoff_     │ │ model_       │ │ config_      │ │ user_        │ │    │
│  │  │ patterns     │ │ registry     │ │ presets      │ │ preferences  │ │    │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Categories

### Category 1: Global Settings

Settings that apply system-wide.

```typescript
interface GlobalConfig {
  // LLM Defaults
  default_llm_model: string;           // "gpt-4.1-2025-04-14"
  default_formatter_model: string;      // "o3-mini-2025-01-31"
  default_temperature: number;          // 0.00001
  default_top_p: number;                // 0.05
  default_timeout: number;              // 1200
  default_max_round: number;            // 50
  
  // Paths
  work_dir: string;                     // "./cmbagent_workdir"
  data_dir: string;                     // "$CMBAGENT_DATA"
  
  // Feature Flags
  enable_rag_agents: boolean;           // true
  enable_ag2_free_tools: boolean;       // true
  enable_mcp_client: boolean;           // false
  enable_database: boolean;             // true
  
  // Debug
  debug_mode: boolean;                  // false
  disable_display: boolean;             // false
  
  // RAG Settings
  file_search_max_num_results: number;  // 20
  chunking_strategy: ChunkingStrategy;
}

interface ChunkingStrategy {
  type: "static" | "auto";
  static?: {
    max_chunk_size_tokens: number;      // 200
    chunk_overlap_tokens: number;       // 100
  };
}
```

### Category 2: Agent Configuration

Per-agent settings.

```typescript
interface AgentConfig {
  id: string;                           // "engineer"
  
  // Identity
  name: string;                         // "engineer"
  description: string;                  // "Engineer agent to write code"
  category: AgentCategory;              // "execution" | "planning" | "rag" | "ideas" | "formatting"
  
  // LLM Settings
  model: string;                        // "gpt-4.1-2025-04-14"
  temperature: number;                  // 0.00001
  top_p: number;                        // 0.05
  timeout: number;                      // 600
  
  // Behavior
  instructions: string;                 // System prompt (markdown)
  enabled: boolean;                     // true
  
  // Agent-specific
  agent_type: AgentType;                // "assistant" | "code" | "rag" | "admin"
  human_input_mode?: HumanInputMode;    // "NEVER" | "ALWAYS" | "TERMINATE"
  max_consecutive_auto_reply?: number;  // 10
  
  // RAG-specific (for rag agents)
  assistant_config?: {
    assistant_id: string;
    vector_store_ids: string[];
    tools: ToolConfig[];
  };
  
  // Code execution (for executor agents)
  execution_policies?: {
    python: boolean;
    bash: boolean;
    // ... other languages
  };
  
  // Metadata
  created_at: Date;
  updated_at: Date;
  version: number;
}

type AgentCategory = "planning" | "execution" | "rag" | "ideas" | "formatting" | "control" | "utility";
type AgentType = "assistant" | "code" | "rag" | "admin";
type HumanInputMode = "NEVER" | "ALWAYS" | "TERMINATE";
```

### Category 3: Workflow Configuration

Settings for workflow execution.

```typescript
interface WorkflowConfig {
  id: string;
  name: string;                         // "Deep Research"
  
  // Planning Phase
  max_rounds_planning: number;          // 50
  max_plan_steps: number;               // 3
  n_plan_reviews: number;               // 1
  
  // Execution Phase  
  max_rounds_control: number;           // 100
  max_n_attempts: number;               // 3
  
  // Model Selection
  planner_model: string;
  plan_reviewer_model: string;
  engineer_model: string;
  researcher_model: string;
  
  // Context Settings
  initial_context: ContextConfig;
  
  // Execution Flags
  clear_work_dir: boolean;              // true
  evaluate_plots: boolean;              // false
  max_n_plot_evals: number;             // 1
  
  // Agent Selection
  enabled_agents: string[];             // ["planner", "engineer", ...]
  rag_agents: string[];                 // ["camb", "classy_sz"]
  
  // Instructions (appended to agent prompts)
  plan_instructions: string;
  engineer_instructions: string;
  researcher_instructions: string;
  hardware_constraints: string;
}

interface ContextConfig {
  feedback_left: number;                // 1
  maximum_number_of_steps_in_plan: number; // 5
  max_n_attempts: number;               // 3
  database_path: string;                // "data/"
  codebase_path: string;                // "codebase/"
  evaluate_plots: boolean;              // false
  max_n_plot_evals: number;             // 1
}
```

### Category 4: Hand-off Configuration

Define agent transition patterns.

```typescript
interface HandoffPattern {
  id: string;
  name: string;                         // "Planning Chain"
  description: string;
  
  // Static hand-offs
  static_handoffs: StaticHandoff[];
  
  // LLM-conditional hand-offs
  conditional_handoffs: ConditionalHandoff[];
  
  // Nested chat configurations
  nested_chats: NestedChatConfig[];
}

interface StaticHandoff {
  from_agent: string;
  to_agent: string;
  after_work: boolean;                  // true = set_after_work
}

interface ConditionalHandoff {
  from_agent: string;
  conditions: HandoffCondition[];
}

interface HandoffCondition {
  to_agent: string;
  condition_type: "llm" | "function";
  prompt?: string;                      // For LLM conditions
  function_name?: string;               // For function conditions
}

interface NestedChatConfig {
  trigger_agent: string;
  chat_agents: string[];
  max_turns: number;
  speaker_selection: "round_robin" | "auto";
}
```

### Category 5: Credentials

Secure API key storage.

```typescript
interface CredentialConfig {
  id: string;
  provider: CredentialProvider;
  api_key_encrypted: string;            // Encrypted at rest
  is_valid: boolean;
  last_validated_at: Date;
  created_at: Date;
  updated_at: Date;
}

type CredentialProvider = 
  | "openai" 
  | "anthropic" 
  | "google" 
  | "perplexity"
  | "github"
  | "brave";
```

### Category 6: Presets/Templates

Saved configuration bundles.

```typescript
interface ConfigPreset {
  id: string;
  name: string;                         // "Fast Research"
  description: string;
  
  // What this preset configures
  global_config?: Partial<GlobalConfig>;
  agent_configs?: Record<string, Partial<AgentConfig>>;
  workflow_config?: Partial<WorkflowConfig>;
  handoff_pattern_id?: string;
  
  // Metadata
  is_default: boolean;
  is_system: boolean;                   // Built-in vs user-created
  created_by: string;
  created_at: Date;
}
```

---

## Database Schema Design

### New Tables

```sql
-- =====================================================
-- CONFIGURATION TABLES
-- =====================================================

-- Global configuration (singleton per user/org)
CREATE TABLE global_configs (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) REFERENCES users(id),           -- NULL = system default
    
    -- LLM Defaults
    default_llm_model VARCHAR(100) NOT NULL DEFAULT 'gpt-4o',
    default_formatter_model VARCHAR(100) NOT NULL DEFAULT 'gpt-4o-mini',
    default_temperature DECIMAL(10,6) NOT NULL DEFAULT 0.00001,
    default_top_p DECIMAL(10,6) NOT NULL DEFAULT 0.05,
    default_timeout INTEGER NOT NULL DEFAULT 1200,
    default_max_round INTEGER NOT NULL DEFAULT 50,
    
    -- Paths
    work_dir VARCHAR(500) DEFAULT './cmbagent_workdir',
    
    -- Feature Flags
    enable_rag_agents BOOLEAN NOT NULL DEFAULT true,
    enable_ag2_free_tools BOOLEAN NOT NULL DEFAULT true,
    enable_mcp_client BOOLEAN NOT NULL DEFAULT false,
    debug_mode BOOLEAN NOT NULL DEFAULT false,
    
    -- RAG Settings
    file_search_max_num_results INTEGER NOT NULL DEFAULT 20,
    chunking_strategy JSONB DEFAULT '{"type": "static", "static": {"max_chunk_size_tokens": 200, "chunk_overlap_tokens": 100}}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id)
);

-- Agent configurations
CREATE TABLE agent_configs (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) REFERENCES users(id),           -- NULL = system default
    
    -- Identity
    agent_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    category VARCHAR(50) NOT NULL,                      -- planning, execution, rag, etc.
    
    -- LLM Settings
    model VARCHAR(100),
    temperature DECIMAL(10,6),
    top_p DECIMAL(10,6),
    timeout INTEGER,
    
    -- Behavior
    instructions TEXT,
    enabled BOOLEAN NOT NULL DEFAULT true,
    
    -- Agent-specific settings
    agent_type VARCHAR(50) NOT NULL,                    -- assistant, code, rag, admin
    human_input_mode VARCHAR(20),                       -- NEVER, ALWAYS, TERMINATE
    max_consecutive_auto_reply INTEGER,
    
    -- RAG-specific
    assistant_config JSONB,
    
    -- Code execution
    execution_policies JSONB,
    
    -- Versioning
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, agent_name)
);

-- Workflow templates
CREATE TABLE workflow_templates (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) REFERENCES users(id),
    
    name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Planning Phase
    max_rounds_planning INTEGER NOT NULL DEFAULT 50,
    max_plan_steps INTEGER NOT NULL DEFAULT 3,
    n_plan_reviews INTEGER NOT NULL DEFAULT 1,
    
    -- Execution Phase
    max_rounds_control INTEGER NOT NULL DEFAULT 100,
    max_n_attempts INTEGER NOT NULL DEFAULT 3,
    
    -- Model Selection (overrides agent defaults)
    model_overrides JSONB,                              -- {"planner": "gpt-4o", ...}
    
    -- Context Configuration
    initial_context JSONB,
    
    -- Execution Flags
    clear_work_dir BOOLEAN NOT NULL DEFAULT true,
    evaluate_plots BOOLEAN NOT NULL DEFAULT false,
    max_n_plot_evals INTEGER NOT NULL DEFAULT 1,
    
    -- Agent Selection
    enabled_agents JSONB,                               -- ["planner", "engineer", ...]
    rag_agents JSONB,                                   -- ["camb", "classy_sz"]
    
    -- Custom Instructions
    plan_instructions TEXT,
    engineer_instructions TEXT,
    researcher_instructions TEXT,
    hardware_constraints TEXT,
    
    -- Metadata
    is_default BOOLEAN NOT NULL DEFAULT false,
    is_system BOOLEAN NOT NULL DEFAULT false,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Hand-off patterns
CREATE TABLE handoff_patterns (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) REFERENCES users(id),
    
    name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Pattern definition
    static_handoffs JSONB NOT NULL DEFAULT '[]',
    conditional_handoffs JSONB NOT NULL DEFAULT '[]',
    nested_chats JSONB NOT NULL DEFAULT '[]',
    
    is_default BOOLEAN NOT NULL DEFAULT false,
    is_system BOOLEAN NOT NULL DEFAULT false,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Encrypted credentials
CREATE TABLE credentials (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    
    provider VARCHAR(50) NOT NULL,                      -- openai, anthropic, google, etc.
    api_key_encrypted BYTEA NOT NULL,                   -- Encrypted with server key
    
    is_valid BOOLEAN DEFAULT NULL,
    last_validated_at TIMESTAMP WITH TIME ZONE,
    validation_error TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, provider)
);

-- Configuration presets (bundles)
CREATE TABLE config_presets (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) REFERENCES users(id),
    
    name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- References to configurations
    global_config_overrides JSONB,
    agent_config_overrides JSONB,                       -- {"engineer": {"model": "gpt-4o"}, ...}
    workflow_template_id VARCHAR(36) REFERENCES workflow_templates(id),
    handoff_pattern_id VARCHAR(36) REFERENCES handoff_patterns(id),
    
    is_default BOOLEAN NOT NULL DEFAULT false,
    is_system BOOLEAN NOT NULL DEFAULT false,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Model registry (available models)
CREATE TABLE model_registry (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    
    provider VARCHAR(50) NOT NULL,                      -- openai, anthropic, google
    model_id VARCHAR(100) NOT NULL,                     -- gpt-4o-2024-11-20
    display_name VARCHAR(200) NOT NULL,                 -- GPT-4o (Nov 2024)
    
    -- Capabilities
    supports_function_calling BOOLEAN DEFAULT true,
    supports_vision BOOLEAN DEFAULT false,
    supports_structured_output BOOLEAN DEFAULT false,
    max_tokens INTEGER,
    
    -- Pricing (per 1M tokens)
    input_price_per_million DECIMAL(10,4),
    output_price_per_million DECIMAL(10,4),
    
    -- Availability
    is_available BOOLEAN NOT NULL DEFAULT true,
    deprecated_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(provider, model_id)
);

-- Configuration change audit log
CREATE TABLE config_audit_log (
    id BIGSERIAL PRIMARY KEY,
    
    user_id VARCHAR(36) REFERENCES users(id),
    config_type VARCHAR(50) NOT NULL,                   -- global, agent, workflow, handoff, credential
    config_id VARCHAR(36) NOT NULL,
    
    action VARCHAR(20) NOT NULL,                        -- create, update, delete
    old_value JSONB,
    new_value JSONB,
    change_reason TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_audit_config (config_type, config_id),
    INDEX idx_audit_user (user_id),
    INDEX idx_audit_time (created_at)
);

-- =====================================================
-- INDEXES
-- =====================================================

CREATE INDEX idx_agent_configs_user ON agent_configs(user_id);
CREATE INDEX idx_agent_configs_name ON agent_configs(agent_name);
CREATE INDEX idx_agent_configs_category ON agent_configs(category);
CREATE INDEX idx_workflow_templates_user ON workflow_templates(user_id);
CREATE INDEX idx_credentials_user ON credentials(user_id);
CREATE INDEX idx_presets_user ON config_presets(user_id);
```

---

## Backend API Design

### API Endpoints

```python
# =====================================================
# ROUTERS
# =====================================================

# backend/routers/config.py
router = APIRouter(prefix="/api/config", tags=["Configuration"])

# Global Configuration
@router.get("/global")
async def get_global_config(user_id: Optional[str] = None) -> GlobalConfigResponse

@router.put("/global")
async def update_global_config(config: GlobalConfigUpdate, user_id: Optional[str] = None) -> GlobalConfigResponse

@router.post("/global/reset")
async def reset_global_config(user_id: Optional[str] = None) -> GlobalConfigResponse


# backend/routers/agents.py
router = APIRouter(prefix="/api/agents", tags=["Agents"])

# Agent Configuration
@router.get("/")
async def list_agents(category: Optional[str] = None, enabled: Optional[bool] = None) -> List[AgentConfigResponse]

@router.get("/{agent_name}")
async def get_agent_config(agent_name: str) -> AgentConfigResponse

@router.put("/{agent_name}")
async def update_agent_config(agent_name: str, config: AgentConfigUpdate) -> AgentConfigResponse

@router.post("/{agent_name}/reset")
async def reset_agent_config(agent_name: str) -> AgentConfigResponse

@router.get("/{agent_name}/instructions")
async def get_agent_instructions(agent_name: str) -> AgentInstructionsResponse

@router.put("/{agent_name}/instructions")
async def update_agent_instructions(agent_name: str, instructions: str) -> AgentInstructionsResponse


# backend/routers/workflows.py  
router = APIRouter(prefix="/api/workflows", tags=["Workflows"])

# Workflow Templates
@router.get("/templates")
async def list_workflow_templates() -> List[WorkflowTemplateResponse]

@router.get("/templates/{template_id}")
async def get_workflow_template(template_id: str) -> WorkflowTemplateResponse

@router.post("/templates")
async def create_workflow_template(template: WorkflowTemplateCreate) -> WorkflowTemplateResponse

@router.put("/templates/{template_id}")
async def update_workflow_template(template_id: str, template: WorkflowTemplateUpdate) -> WorkflowTemplateResponse

@router.delete("/templates/{template_id}")
async def delete_workflow_template(template_id: str) -> None


# backend/routers/handoffs.py
router = APIRouter(prefix="/api/handoffs", tags=["Handoffs"])

# Hand-off Patterns
@router.get("/patterns")
async def list_handoff_patterns() -> List[HandoffPatternResponse]

@router.get("/patterns/{pattern_id}")
async def get_handoff_pattern(pattern_id: str) -> HandoffPatternResponse

@router.post("/patterns")
async def create_handoff_pattern(pattern: HandoffPatternCreate) -> HandoffPatternResponse

@router.put("/patterns/{pattern_id}")
async def update_handoff_pattern(pattern_id: str, pattern: HandoffPatternUpdate) -> HandoffPatternResponse

# Visualization
@router.get("/patterns/{pattern_id}/graph")
async def get_handoff_graph(pattern_id: str) -> HandoffGraphResponse


# backend/routers/credentials.py
router = APIRouter(prefix="/api/credentials", tags=["Credentials"])

# Credential Management
@router.get("/")
async def list_credentials() -> List[CredentialResponse]  # Never returns keys

@router.post("/")
async def create_credential(cred: CredentialCreate) -> CredentialResponse

@router.put("/{provider}")
async def update_credential(provider: str, cred: CredentialUpdate) -> CredentialResponse

@router.delete("/{provider}")
async def delete_credential(provider: str) -> None

@router.post("/{provider}/validate")
async def validate_credential(provider: str) -> ValidationResponse


# backend/routers/presets.py
router = APIRouter(prefix="/api/presets", tags=["Presets"])

# Configuration Presets
@router.get("/")
async def list_presets() -> List[PresetResponse]

@router.get("/{preset_id}")
async def get_preset(preset_id: str) -> PresetResponse

@router.post("/")
async def create_preset(preset: PresetCreate) -> PresetResponse

@router.post("/{preset_id}/apply")
async def apply_preset(preset_id: str) -> ApplyPresetResponse


# backend/routers/models.py
router = APIRouter(prefix="/api/models", tags=["Models"])

# Model Registry
@router.get("/")
async def list_models(provider: Optional[str] = None) -> List[ModelResponse]

@router.get("/available")
async def list_available_models() -> List[ModelResponse]  # Only those with valid credentials
```

### Configuration Service

```python
# backend/services/config_service.py

class ConfigurationService:
    """
    Central service for managing all configuration.
    Handles merging, validation, and caching.
    """
    
    def __init__(self, db_session, cache: Redis = None):
        self.db = db_session
        self.cache = cache
        self.crypto = CredentialCrypto()
    
    # =====================================================
    # RESOLUTION: Get effective configuration
    # =====================================================
    
    def get_effective_global_config(self, user_id: str = None) -> GlobalConfig:
        """
        Get effective global config with proper fallback chain.
        
        Priority:
        1. User-specific config (if user_id provided)
        2. System default config (user_id=NULL)
        3. Hardcoded defaults
        """
        # Try cache first
        cache_key = f"global_config:{user_id or 'default'}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return GlobalConfig.parse_raw(cached)
        
        # User config
        if user_id:
            user_config = self.db.query(GlobalConfigModel).filter_by(user_id=user_id).first()
            if user_config:
                return self._to_global_config(user_config)
        
        # System default
        system_config = self.db.query(GlobalConfigModel).filter_by(user_id=None).first()
        if system_config:
            return self._to_global_config(system_config)
        
        # Hardcoded defaults
        return GlobalConfig()  # Uses dataclass defaults
    
    def get_effective_agent_config(self, agent_name: str, user_id: str = None) -> AgentConfig:
        """
        Get effective agent config.
        
        Priority:
        1. User-specific agent config
        2. System default agent config
        3. YAML file (legacy fallback)
        4. Hardcoded defaults
        """
        # User config
        if user_id:
            user_config = self.db.query(AgentConfigModel).filter_by(
                user_id=user_id, agent_name=agent_name
            ).first()
            if user_config:
                return self._to_agent_config(user_config)
        
        # System default
        system_config = self.db.query(AgentConfigModel).filter_by(
            user_id=None, agent_name=agent_name
        ).first()
        if system_config:
            return self._to_agent_config(system_config)
        
        # YAML fallback
        yaml_config = self._load_from_yaml(agent_name)
        if yaml_config:
            return yaml_config
        
        # Hardcoded default
        return AgentConfig(agent_name=agent_name)
    
    def get_effective_workflow_config(
        self, 
        template_id: str = None, 
        overrides: dict = None
    ) -> WorkflowConfig:
        """
        Build workflow config from template + runtime overrides.
        """
        # Load template
        if template_id:
            template = self.db.query(WorkflowTemplateModel).get(template_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
            config = self._to_workflow_config(template)
        else:
            # Use default template
            config = WorkflowConfig()
        
        # Apply overrides
        if overrides:
            for key, value in overrides.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        return config
    
    # =====================================================
    # BUILD: Create CMBAgent-ready configuration
    # =====================================================
    
    def build_cmbagent_config(
        self,
        user_id: str = None,
        workflow_template_id: str = None,
        agent_overrides: dict = None,
        workflow_overrides: dict = None,
    ) -> CMBAgentBuildConfig:
        """
        Build complete configuration for CMBAgent initialization.
        
        Returns a structured config that can be passed to CMBAgent().
        """
        global_config = self.get_effective_global_config(user_id)
        workflow_config = self.get_effective_workflow_config(
            workflow_template_id, workflow_overrides
        )
        
        # Build agent_llm_configs
        agent_llm_configs = {}
        agent_instructions = {}
        
        for agent_name in self._get_all_agent_names():
            agent_config = self.get_effective_agent_config(agent_name, user_id)
            
            # Apply overrides
            if agent_overrides and agent_name in agent_overrides:
                for key, value in agent_overrides[agent_name].items():
                    setattr(agent_config, key, value)
            
            # Build LLM config
            if agent_config.model:
                agent_llm_configs[agent_name] = {
                    "model": agent_config.model,
                    "temperature": agent_config.temperature,
                    "top_p": agent_config.top_p,
                }
            
            # Collect instructions
            if agent_config.instructions:
                agent_instructions[agent_name] = agent_config.instructions
        
        # Get API keys
        api_keys = self._get_decrypted_api_keys(user_id)
        
        return CMBAgentBuildConfig(
            # LLM settings
            temperature=global_config.default_temperature,
            top_p=global_config.default_top_p,
            timeout=global_config.default_timeout,
            max_round=global_config.default_max_round,
            
            # Agent configs
            agent_llm_configs=agent_llm_configs,
            agent_instructions=agent_instructions,
            
            # Feature flags
            skip_rag_agents=not global_config.enable_rag_agents,
            enable_ag2_free_tools=global_config.enable_ag2_free_tools,
            enable_mcp_client=global_config.enable_mcp_client,
            
            # RAG agents
            agent_list=workflow_config.rag_agents,
            
            # API keys
            api_keys=api_keys,
            
            # Workflow settings
            max_rounds_planning=workflow_config.max_rounds_planning,
            max_rounds_control=workflow_config.max_rounds_control,
            max_plan_steps=workflow_config.max_plan_steps,
            n_plan_reviews=workflow_config.n_plan_reviews,
            max_n_attempts=workflow_config.max_n_attempts,
            
            # Context
            shared_context={
                "feedback_left": workflow_config.n_plan_reviews,
                "maximum_number_of_steps_in_plan": workflow_config.max_plan_steps,
                "max_n_attempts": workflow_config.max_n_attempts,
                "evaluate_plots": workflow_config.evaluate_plots,
                "max_n_plot_evals": workflow_config.max_n_plot_evals,
                "planner_append_instructions": workflow_config.plan_instructions,
                "engineer_append_instructions": workflow_config.engineer_instructions,
                "researcher_append_instructions": workflow_config.researcher_instructions,
                "hardware_constraints": workflow_config.hardware_constraints,
            },
        )
```

---

## Frontend Components Design

### Component Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CONFIGURATION UI COMPONENTS                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SettingsPage                                                               │
│  ├── SettingsTabs                                                           │
│  │   ├── GlobalSettingsTab                                                  │
│  │   │   ├── LLMDefaultsForm                                               │
│  │   │   │   ├── ModelSelector                                             │
│  │   │   │   ├── TemperatureSlider                                         │
│  │   │   │   └── TopPSlider                                                │
│  │   │   ├── FeatureFlagsForm                                              │
│  │   │   │   ├── ToggleSwitch (RAG)                                        │
│  │   │   │   ├── ToggleSwitch (AG2 Tools)                                  │
│  │   │   │   └── ToggleSwitch (MCP)                                        │
│  │   │   └── RAGSettingsForm                                               │
│  │   │                                                                       │
│  │   ├── AgentsTab                                                          │
│  │   │   ├── AgentList                                                      │
│  │   │   │   └── AgentCard (for each agent)                                │
│  │   │   └── AgentConfigModal                                              │
│  │   │       ├── BasicSettingsSection                                      │
│  │   │       │   ├── ModelSelector                                         │
│  │   │       │   ├── TemperatureSlider                                     │
│  │   │       │   └── EnableToggle                                          │
│  │   │       └── InstructionsEditor                                        │
│  │   │           └── MarkdownEditor                                        │
│  │   │                                                                       │
│  │   ├── WorkflowsTab                                                       │
│  │   │   ├── WorkflowTemplateList                                          │
│  │   │   └── WorkflowTemplateEditor                                        │
│  │   │       ├── PlanningSection                                           │
│  │   │       ├── ExecutionSection                                          │
│  │   │       ├── ModelOverridesSection                                     │
│  │   │       └── InstructionsSection                                       │
│  │   │                                                                       │
│  │   ├── HandoffsTab                                                        │
│  │   │   ├── HandoffPatternList                                            │
│  │   │   └── HandoffVisualEditor                                           │
│  │   │       ├── AgentFlowDiagram (React Flow)                             │
│  │   │       ├── StaticHandoffList                                         │
│  │   │       └── ConditionalHandoffList                                    │
│  │   │                                                                       │
│  │   ├── CredentialsTab                                                     │
│  │   │   ├── CredentialsList                                               │
│  │   │   │   └── CredentialCard                                            │
│  │   │   │       ├── StatusIndicator                                       │
│  │   │   │       ├── ValidateButton                                        │
│  │   │   │       └── UpdateKeyModal                                        │
│  │   │   └── AddCredentialModal                                            │
│  │   │                                                                       │
│  │   └── PresetsTab                                                         │
│  │       ├── PresetList                                                     │
│  │       ├── PresetCreator                                                  │
│  │       └── PresetApplyConfirm                                            │
│  │                                                                           │
│  └── SettingsFooter                                                         │
│      ├── SaveButton                                                         │
│      ├── ResetButton                                                        │
│      └── ExportImportButtons                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. ModelSelector

```tsx
// components/config/ModelSelector.tsx

interface ModelSelectorProps {
  value: string;
  onChange: (model: string) => void;
  provider?: string;  // Filter by provider
  label?: string;
}

export function ModelSelector({ value, onChange, provider, label }: ModelSelectorProps) {
  const { data: models } = useModels({ provider });
  
  // Group models by provider
  const groupedModels = useMemo(() => {
    return models?.reduce((acc, model) => {
      const group = acc[model.provider] || [];
      group.push(model);
      acc[model.provider] = group;
      return acc;
    }, {} as Record<string, Model[]>);
  }, [models]);
  
  return (
    <div className="space-y-2">
      {label && <Label>{label}</Label>}
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder="Select a model" />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(groupedModels || {}).map(([provider, models]) => (
            <SelectGroup key={provider}>
              <SelectLabel>{provider.toUpperCase()}</SelectLabel>
              {models.map((model) => (
                <SelectItem 
                  key={model.model_id} 
                  value={model.model_id}
                  disabled={!model.is_available}
                >
                  <div className="flex items-center justify-between w-full">
                    <span>{model.display_name}</span>
                    <span className="text-xs text-muted-foreground">
                      ${model.input_price_per_million}/M in
                    </span>
                  </div>
                </SelectItem>
              ))}
            </SelectGroup>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
```

#### 2. AgentConfigModal

```tsx
// components/config/AgentConfigModal.tsx

interface AgentConfigModalProps {
  agent: AgentConfig;
  open: boolean;
  onClose: () => void;
  onSave: (config: AgentConfigUpdate) => void;
}

export function AgentConfigModal({ agent, open, onClose, onSave }: AgentConfigModalProps) {
  const [config, setConfig] = useState<AgentConfigUpdate>(agent);
  const [activeTab, setActiveTab] = useState<"basic" | "instructions" | "advanced">("basic");
  
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Configure {agent.display_name || agent.agent_name}</DialogTitle>
          <DialogDescription>{agent.description}</DialogDescription>
        </DialogHeader>
        
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="basic">Basic</TabsTrigger>
            <TabsTrigger value="instructions">Instructions</TabsTrigger>
            <TabsTrigger value="advanced">Advanced</TabsTrigger>
          </TabsList>
          
          <TabsContent value="basic" className="space-y-4">
            {/* Enable/Disable */}
            <div className="flex items-center justify-between">
              <Label>Enabled</Label>
              <Switch 
                checked={config.enabled} 
                onCheckedChange={(v) => setConfig({...config, enabled: v})}
              />
            </div>
            
            {/* Model Selection */}
            <ModelSelector
              label="Model"
              value={config.model}
              onChange={(model) => setConfig({...config, model})}
            />
            
            {/* Temperature */}
            <div className="space-y-2">
              <div className="flex justify-between">
                <Label>Temperature</Label>
                <span className="text-sm text-muted-foreground">{config.temperature}</span>
              </div>
              <Slider
                value={[config.temperature * 100]}
                onValueChange={([v]) => setConfig({...config, temperature: v / 100})}
                min={0}
                max={200}
                step={1}
              />
            </div>
            
            {/* Top P */}
            <div className="space-y-2">
              <div className="flex justify-between">
                <Label>Top P</Label>
                <span className="text-sm text-muted-foreground">{config.top_p}</span>
              </div>
              <Slider
                value={[config.top_p * 100]}
                onValueChange={([v]) => setConfig({...config, top_p: v / 100})}
                min={0}
                max={100}
                step={1}
              />
            </div>
          </TabsContent>
          
          <TabsContent value="instructions" className="min-h-[400px]">
            <MarkdownEditor
              value={config.instructions}
              onChange={(instructions) => setConfig({...config, instructions})}
              placeholder="Enter system instructions for this agent..."
            />
          </TabsContent>
          
          <TabsContent value="advanced" className="space-y-4">
            {/* Timeout */}
            <div className="space-y-2">
              <Label>Timeout (seconds)</Label>
              <Input
                type="number"
                value={config.timeout}
                onChange={(e) => setConfig({...config, timeout: parseInt(e.target.value)})}
              />
            </div>
            
            {/* Agent-type specific settings */}
            {config.agent_type === "code" && (
              <ExecutionPoliciesEditor
                value={config.execution_policies}
                onChange={(policies) => setConfig({...config, execution_policies: policies})}
              />
            )}
            
            {config.agent_type === "rag" && (
              <RAGSettingsEditor
                value={config.assistant_config}
                onChange={(cfg) => setConfig({...config, assistant_config: cfg})}
              />
            )}
          </TabsContent>
        </Tabs>
        
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => onSave(config)}>Save Changes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

#### 3. HandoffVisualEditor

```tsx
// components/config/HandoffVisualEditor.tsx

import ReactFlow, { 
  Node, Edge, Controls, Background, 
  useNodesState, useEdgesState, addEdge 
} from 'reactflow';

interface HandoffVisualEditorProps {
  pattern: HandoffPattern;
  onChange: (pattern: HandoffPatternUpdate) => void;
}

export function HandoffVisualEditor({ pattern, onChange }: HandoffVisualEditorProps) {
  // Convert handoffs to nodes/edges
  const [nodes, setNodes, onNodesChange] = useNodesState(
    buildNodesFromPattern(pattern)
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    buildEdgesFromPattern(pattern)
  );
  
  const onConnect = useCallback((params) => {
    // Add new hand-off when user draws edge
    setEdges((eds) => addEdge({
      ...params,
      type: 'smoothstep',
      animated: true,
      data: { type: 'static' },
    }, eds));
    
    // Update pattern
    onChange({
      ...pattern,
      static_handoffs: [
        ...pattern.static_handoffs,
        { from_agent: params.source, to_agent: params.target, after_work: true }
      ]
    });
  }, [pattern, onChange]);
  
  return (
    <div className="h-[600px] border rounded-lg">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        fitView
      >
        <Controls />
        <Background />
      </ReactFlow>
      
      {/* Edge type selector for conditional handoffs */}
      <EdgeTypePanel 
        selectedEdge={selectedEdge}
        onUpdateEdge={handleUpdateEdge}
      />
    </div>
  );
}
```

#### 4. CredentialsManager

```tsx
// components/config/CredentialsManager.tsx

const PROVIDERS = [
  { id: 'openai', name: 'OpenAI', icon: OpenAIIcon },
  { id: 'anthropic', name: 'Anthropic', icon: AnthropicIcon },
  { id: 'google', name: 'Google', icon: GoogleIcon },
  { id: 'perplexity', name: 'Perplexity', icon: PerplexityIcon },
];

export function CredentialsManager() {
  const { data: credentials, refetch } = useCredentials();
  const validateMutation = useValidateCredential();
  const updateMutation = useUpdateCredential();
  
  return (
    <div className="space-y-4">
      {PROVIDERS.map((provider) => {
        const cred = credentials?.find(c => c.provider === provider.id);
        
        return (
          <Card key={provider.id}>
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center gap-3">
                <provider.icon className="h-6 w-6" />
                <CardTitle>{provider.name}</CardTitle>
              </div>
              <StatusBadge status={cred?.is_valid} />
            </CardHeader>
            
            <CardContent className="space-y-4">
              <div className="flex items-center gap-2">
                <Input
                  type="password"
                  placeholder={cred ? '••••••••••••••••' : 'Enter API key'}
                  className="flex-1"
                  onChange={(e) => setKey(provider.id, e.target.value)}
                />
                
                <Button 
                  variant="outline"
                  onClick={() => updateMutation.mutate({ 
                    provider: provider.id, 
                    api_key: keys[provider.id] 
                  })}
                >
                  Save
                </Button>
                
                <Button
                  variant="ghost"
                  onClick={() => validateMutation.mutate(provider.id)}
                  disabled={validateMutation.isLoading}
                >
                  {validateMutation.isLoading ? <Spinner /> : 'Validate'}
                </Button>
              </div>
              
              {cred?.validation_error && (
                <Alert variant="destructive">
                  <AlertDescription>{cred.validation_error}</AlertDescription>
                </Alert>
              )}
              
              {cred?.last_validated_at && (
                <p className="text-xs text-muted-foreground">
                  Last validated: {formatRelative(cred.last_validated_at)}
                </p>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
```

---

## Runtime Configuration Loading

### Modified CMBAgent Initialization

```python
# cmbagent/cmbagent.py

class CMBAgent:
    def __init__(
        self,
        # Traditional parameters (for backward compatibility)
        temperature=None,
        top_p=None,
        agent_llm_configs=None,
        agent_instructions=None,
        # ... other params
        
        # NEW: Configuration service
        config_service: ConfigurationService = None,
        user_id: str = None,
        workflow_template_id: str = None,
        preset_id: str = None,
        
        **kwargs
    ):
        # =====================================================
        # PHASE 0: CONFIGURATION RESOLUTION
        # =====================================================
        
        if config_service:
            # Load from database via service
            self._load_from_config_service(
                config_service, user_id, workflow_template_id, preset_id
            )
        else:
            # Fall back to traditional initialization
            self._load_from_params_and_defaults(
                temperature, top_p, agent_llm_configs, agent_instructions, **kwargs
            )
        
        # Continue with rest of initialization...
    
    def _load_from_config_service(
        self, 
        service: ConfigurationService,
        user_id: str,
        workflow_template_id: str,
        preset_id: str
    ):
        """Load configuration from database via ConfigurationService."""
        
        # If preset specified, apply it first
        if preset_id:
            preset = service.get_preset(preset_id)
            if preset.workflow_template_id:
                workflow_template_id = preset.workflow_template_id
        
        # Build complete configuration
        build_config = service.build_cmbagent_config(
            user_id=user_id,
            workflow_template_id=workflow_template_id,
        )
        
        # Apply to instance
        self.temperature = build_config.temperature
        self.top_p = build_config.top_p
        self.timeout = build_config.timeout
        self.max_round = build_config.max_round
        
        self.agent_llm_configs = build_config.agent_llm_configs
        self._agent_instructions = build_config.agent_instructions
        
        self.skip_rag_agents = build_config.skip_rag_agents
        self.enable_ag2_free_tools = build_config.enable_ag2_free_tools
        self.enable_mcp_client = build_config.enable_mcp_client
        
        self.agent_list = build_config.agent_list
        self.api_keys = build_config.api_keys
        
        # Store workflow config for solve()
        self._workflow_config = build_config.workflow_config
        self._initial_context = build_config.shared_context
```

### Modified Workflow Execution

```python
# cmbagent/workflows/planning_control.py

def planning_and_control_context_carryover(
    task: str,
    work_dir: str,
    
    # NEW: Config from UI
    config_service: ConfigurationService = None,
    user_id: str = None,
    workflow_template_id: str = None,
    
    # Traditional params (fallback)
    max_rounds_planning: int = None,
    max_plan_steps: int = None,
    # ... other params
    
    **kwargs
):
    # Load config
    if config_service:
        workflow_config = config_service.get_effective_workflow_config(
            template_id=workflow_template_id
        )
        
        # Use config values (can still be overridden by explicit params)
        max_rounds_planning = max_rounds_planning or workflow_config.max_rounds_planning
        max_plan_steps = max_plan_steps or workflow_config.max_plan_steps
        # ... etc
    else:
        # Use defaults
        max_rounds_planning = max_rounds_planning or 50
        max_plan_steps = max_plan_steps or 3
    
    # Create CMBAgent with config service
    cmbagent = CMBAgent(
        config_service=config_service,
        user_id=user_id,
        workflow_template_id=workflow_template_id,
        work_dir=work_dir,
        **kwargs
    )
    
    # Continue with workflow...
```

### Configuration Priority Chain

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONFIGURATION PRIORITY CHAIN                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Highest Priority                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Runtime Parameters (CMBAgent constructor / workflow function)     │   │
│  │    CMBAgent(temperature=0.5, ...)                                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 2. Active Preset (if applied)                                        │   │
│  │    User selected "Fast Research" preset                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 3. User Configuration (per-user overrides in database)               │   │
│  │    user_configs WHERE user_id = 'user123'                            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 4. System Defaults (database, user_id = NULL)                        │   │
│  │    Editable via admin UI                                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 5. YAML Files (legacy, read-only fallback)                           │   │
│  │    agents/engineer/engineer.yaml                                     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 6. Hardcoded Defaults (Python code)                                  │   │
│  │    default_temperature = 0.00001                                     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│  Lowest Priority                                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Migration Strategy

### Phase 1: Database Schema & API (Week 1-2)

1. Create new database tables
2. Implement ConfigurationService
3. Create API endpoints
4. Write migration script to load YAML → database

```python
# migration/import_yaml_to_db.py

def migrate_yaml_configs_to_database(db_session):
    """One-time migration from YAML files to database."""
    
    # Import all agent YAML files
    for agent_dir in Path("cmbagent/agents").iterdir():
        if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
            yaml_file = agent_dir / f"{agent_dir.name}.yaml"
            if yaml_file.exists():
                config = yaml.safe_load(yaml_file.read_text())
                
                agent_config = AgentConfigModel(
                    agent_name=config['name'],
                    instructions=config.get('instructions'),
                    description=config.get('description'),
                    category=categorize_agent(agent_dir.name),
                    agent_type=determine_agent_type(config),
                    # ... other fields
                )
                
                db_session.add(agent_config)
    
    # Import global settings from utils.py
    global_config = GlobalConfigModel(
        default_llm_model=default_llm_model,
        default_temperature=default_temperature,
        default_top_p=default_top_p,
        # ... other fields
    )
    db_session.add(global_config)
    
    # Import model registry
    for model in KNOWN_MODELS:
        db_session.add(ModelRegistryModel(**model))
    
    db_session.commit()
```

### Phase 2: Backend Integration (Week 2-3)

1. Modify CMBAgent to accept ConfigurationService
2. Update workflow functions
3. Add config resolution logic
4. Maintain backward compatibility

### Phase 3: Frontend Components (Week 3-5)

1. Build SettingsPage scaffold
2. Implement GlobalSettingsTab
3. Implement AgentsTab + AgentConfigModal
4. Implement WorkflowsTab
5. Implement CredentialsTab
6. Implement PresetsTab

### Phase 4: Hand-off Visual Editor (Week 5-6)

1. Build HandoffVisualEditor with React Flow
2. Implement pattern save/load
3. Connect to backend

### Phase 5: Testing & Polish (Week 6-7)

1. End-to-end testing
2. Configuration export/import
3. Documentation
4. Performance optimization (caching)

---

## Implementation Roadmap

### Milestone 1: Foundation (Weeks 1-2)

- [ ] Design and create database schema
- [ ] Implement SQLAlchemy models
- [ ] Create ConfigurationService
- [ ] Build CRUD API endpoints
- [ ] Write YAML → database migration

### Milestone 2: Core UI (Weeks 3-4)

- [ ] Create SettingsPage layout
- [ ] Build ModelSelector component
- [ ] Build GlobalSettingsTab
- [ ] Build AgentsTab with list view
- [ ] Build AgentConfigModal

### Milestone 3: Advanced UI (Weeks 4-5)

- [ ] Build InstructionsEditor (Markdown)
- [ ] Build WorkflowTemplateEditor
- [ ] Build CredentialsManager
- [ ] Build PresetsManager

### Milestone 4: Hand-off Designer (Week 5-6)

- [ ] Integrate React Flow
- [ ] Build HandoffVisualEditor
- [ ] Implement edge type editing
- [ ] Add nested chat configuration

### Milestone 5: Integration (Week 6-7)

- [ ] Modify CMBAgent for config service
- [ ] Update workflow functions
- [ ] Add caching layer
- [ ] Write integration tests
- [ ] Performance testing

### Milestone 6: Polish (Week 7-8)

- [ ] Configuration export/import (JSON)
- [ ] Audit logging UI
- [ ] Documentation
- [ ] User guide

---

## Summary

This architecture enables:

1. **All configuration in UI** - No more editing YAML or Python
2. **Per-user customization** - Users can have different settings
3. **Preset system** - Save and reuse configurations
4. **Visual hand-off editor** - Design agent flows graphically
5. **Secure credential management** - Encrypted storage, validation
6. **Audit trail** - Track all configuration changes
7. **Backward compatibility** - Existing code continues to work

The key insight is the **ConfigurationService** which acts as a single source of truth, merging configurations from multiple sources with proper priority resolution.

---

*Configuration Generalization Architecture*  
*Design Document v1.0*  
*January 2026*
