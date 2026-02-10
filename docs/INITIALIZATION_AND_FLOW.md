# CMBAgent Initialization and Execution Flow

> **Complete Guide to How CMBAgent Initializes, Configures, and Executes Tasks**

---

## Table of Contents

1. [Initialization Overview](#initialization-overview)
2. [Configuration Sources](#configuration-sources)
3. [CMBAgent Initialization Flow](#cmbagent-initialization-flow)
4. [Agent Initialization](#agent-initialization)
5. [LLM Configuration Resolution](#llm-configuration-resolution)
6. [RAG and Vector Store Setup](#rag-and-vector-store-setup)
7. [Database Initialization](#database-initialization)
8. [Hand-offs and Functions Registration](#hand-offs-and-functions-registration)
9. [Workflow Execution Flow](#workflow-execution-flow)
10. [Backend and Frontend Initialization](#backend-and-frontend-initialization)
11. [Complete Sequence Diagrams](#complete-sequence-diagrams)

---

## Initialization Overview

When CMBAgent starts, it goes through multiple initialization phases:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INITIALIZATION PHASES                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Phase 1: Configuration Loading                                             │
│  ├── Environment variables                                                  │
│  ├── Default settings (utils.py)                                           │
│  ├── User-provided parameters                                               │
│  └── Agent YAML files                                                       │
│                                                                              │
│  Phase 2: LLM Configuration                                                 │
│  ├── API keys resolution                                                    │
│  ├── Model selection per agent                                              │
│  └── Config list assembly                                                   │
│                                                                              │
│  Phase 3: Database Setup (Optional)                                         │
│  ├── Engine creation                                                        │
│  ├── Session initialization                                                 │
│  ├── Repository creation                                                    │
│  └── DAG/State machine setup                                                │
│                                                                              │
│  Phase 4: MCP Client Setup (Optional)                                       │
│  ├── Load client_config.yaml                                                │
│  ├── Connect to enabled servers                                             │
│  └── Discover tools                                                         │
│                                                                              │
│  Phase 5: Agent Instantiation                                               │
│  ├── Import RAG agents                                                      │
│  ├── Import non-RAG agents                                                  │
│  ├── Create agent instances                                                 │
│  └── Apply LLM configs per agent                                            │
│                                                                              │
│  Phase 6: RAG Setup (If enabled)                                            │
│  ├── Setup CMBAGENT_DATA                                                    │
│  ├── Check/create OpenAI assistants                                         │
│  └── Push vector stores                                                     │
│                                                                              │
│  Phase 7: Agent Wiring                                                      │
│  ├── Set agent instructions from YAML                                       │
│  ├── Register hand-offs                                                     │
│  └── Register functions                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Sources

Configuration comes from multiple sources with the following priority (highest to lowest):

### Priority Order

```
1. User-provided parameters (CMBAgent constructor)
       ↓ overrides
2. Environment variables
       ↓ overrides  
3. Default settings in utils.py
       ↓ overrides
4. Agent YAML files
```

### Source: Environment Variables

**File:** Environment (shell, `.env`, Docker)

```bash
# LLM API Keys
OPENAI_API_KEY=sk-...              # Primary OpenAI key
ANTHROPIC_API_KEY=sk-ant-...       # Anthropic Claude
GEMINI_API_KEY=...                 # Google Gemini
PERPLEXITY_API_KEY=pplx-...        # Perplexity AI

# Database
DATABASE_URL=postgresql://...       # Database connection string
CMBAGENT_USE_DATABASE=true         # Enable/disable database (default: true)

# Data paths
CMBAGENT_DATA=/path/to/data        # Path to RAG data files

# Debug flags
CMBAGENT_DEBUG=false               # Enable debug output
CMBAGENT_DISABLE_DISPLAY=false     # Disable logo/display

# MCP tokens
GITHUB_TOKEN=ghp_...               # For GitHub MCP server
BRAVE_API_KEY=...                  # For Brave search MCP
```

**Loaded in:** `cmbagent/utils.py`, `cmbagent/cmbagent_utils.py`

```python
# cmbagent/cmbagent_utils.py
cmbagent_debug = os.getenv("CMBAGENT_DEBUG", "false").lower() == "true"
cmbagent_disable_display = os.getenv("CMBAGENT_DISABLE_DISPLAY", "false").lower() == "true"
```

### Source: Default Settings (`cmbagent/utils.py`)

```python
# Path configuration
path_to_basedir = os.path.dirname(os.path.abspath(__file__))
path_to_apis = os.path.join(path_to_basedir, "apis")
path_to_assistants = os.path.join(path_to_basedir, "agents/rag_agents/")
path_to_agents = os.path.join(path_to_basedir, "agents/")

# Working directory - defaults to current directory
work_dir_default = os.path.join(os.getcwd(), "cmbagent_workdir")

# LLM defaults
default_temperature = 0.00001
default_top_p = 0.05
default_max_round = 50

# Default models
default_llm_model = "gpt-4o"
default_formatter_model = "gpt-4o-mini"

# Per-agent model defaults
default_agents_llm_model = {
    'planner': 'gpt-4o',
    'plan_reviewer': 'gpt-4o',
    'engineer': 'gpt-4o',
    'researcher': 'gpt-4o',
    'idea_maker': 'gpt-4o',
    'idea_hater': 'gpt-4o',
    'camb_context': 'gpt-4o',
    'classy_context': 'gpt-4o',
    'web_surfer': 'gpt-4o',
    'retrieve_assistant': 'gpt-4o',
    'plot_judge': 'gpt-4o-mini',
}

# Default LLM config list template
default_llm_config_list = [
    {
        "model": "gpt-4o",
        "api_key": os.getenv("OPENAI_API_KEY"),
        "api_type": "openai",
    }
]

# Default agent LLM configs (empty, filled per agent)
default_agent_llm_configs = {}

# RAG chunking strategy
default_chunking_strategy = {
    "type": "static",
    "static": {
        "max_chunk_size_tokens": 200,
        "chunk_overlap_tokens": 100
    }
}

# File search settings
file_search_max_num_results = 20  # Max results from vector store search
```

### Source: Agent YAML Files (`cmbagent/agents/{agent}/{agent}.yaml`)

Each agent has a YAML file defining:

```yaml
# Example: agents/engineer/engineer.yaml

name: "engineer"              # Agent name (must match filename)

instructions: |               # System prompt for the agent
    You are the engineer agent.
    
    You provide single self-consistent Python code...
    
    **RESPONSE FORMAT:**
    ...

description: |                # Short description (for display/selection)
    Engineer agent, to provide Python code.

# For RAG agents only (agents/rag_agents/*.yaml):
assistant_config:
    assistant_id: "asst_..."  # OpenAI Assistant ID (auto-filled)
    tools:
        - type: file_search
          file_search:
            max_num_results: 20
    tool_resources:
        file_search:
            vector_store_ids: []  # Filled during push_vector_stores
    temperature: 0.0
    top_p: 0.05

# For executor agents:
human_input_mode: "NEVER"
max_consecutive_auto_reply: 10
timeout: 600
code_execution_config: false
```

### Source: User Parameters (Constructor)

```python
CMBAgent(
    # LLM Configuration
    cache_seed=None,                    # Cache seed for reproducibility
    temperature=default_temperature,    # LLM temperature
    top_p=default_top_p,                # LLM top_p
    timeout=1200,                       # Request timeout
    max_round=default_max_round,        # Max conversation rounds
    
    # Model Selection
    platform='oai',                     # Platform hint
    model='gpt4o',                      # Default model hint
    llm_api_key=None,                   # Override API key
    llm_api_type=None,                  # Override API type
    
    # Agent Configuration
    agent_list=['camb', 'classy_sz', 'cobaya', 'planck'],  # RAG agents to load
    agent_instructions={},              # Override agent instructions
    agent_descriptions=None,            # Override agent descriptions
    agent_temperature=None,             # Per-agent temperature
    agent_top_p=None,                   # Per-agent top_p
    agent_llm_configs={},               # Per-agent LLM configs
    
    # Feature Flags
    make_vector_stores=False,           # Create/update vector stores
    skip_executor=False,                # Skip executor agent
    skip_memory=True,                   # Skip memory agent
    skip_rag_agents=True,               # Skip all RAG agents
    skip_rag_software_formatter=True,   # Skip RAG formatter
    
    # Working Directory
    work_dir=work_dir_default,          # Output directory
    clear_work_dir=True,                # Clear on init
    
    # Workflow Mode
    mode="planning_and_control",        # Workflow mode
    chat_agent=None,                    # Chat mode agent
    
    # Database & HITL
    approval_config=None,               # HITL configuration
    
    # External Tools
    enable_ag2_free_tools=True,         # LangChain/CrewAI tools
    enable_mcp_client=False,            # MCP server connections
    
    # API Keys Dictionary
    api_keys=None,                      # Dict of API keys
    
    # Other
    verbose=False,                      # Verbose output
    reset_assistant=[],                 # Reset specific assistants
    
    **kwargs                            # Additional params
)
```

---

## CMBAgent Initialization Flow

### Complete `__init__` Flow

```python
# File: cmbagent/cmbagent.py

class CMBAgent:
    def __init__(self, ...):
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 1: PARAMETER PROCESSING
        # ═══════════════════════════════════════════════════════════════════
        
        # 1.1 Override default_llm_config_list if custom model specified
        if default_llm_model != default_llm_model_default:
            default_llm_config_list = [get_model_config(default_llm_model, api_keys)]
        
        # 1.2 Store kwargs and flags
        self.kwargs = kwargs
        self.enable_ag2_free_tools = enable_ag2_free_tools
        self.enable_mcp_client = enable_mcp_client
        self.skip_executor = skip_executor
        self.skip_rag_agents = skip_rag_agents
        
        # 1.3 If making vector stores, enable RAG agents
        if make_vector_stores is not False:
            self.skip_rag_agents = False
        
        # 1.4 Store agent list (which RAG agents to include)
        self.agent_list = agent_list
        
        # 1.5 Add memory agent if not skipped
        if not self.skip_memory and 'memory' not in agent_list:
            self.agent_list.append('memory')
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 2: WORKING DIRECTORY SETUP
        # ═══════════════════════════════════════════════════════════════════
        
        # 2.1 Clean up default work_dir if custom one specified
        if work_dir != work_dir_default:
            work_dir_default_path = Path(work_dir_default)
            work_dir_path = Path(work_dir)
            if not work_dir_default_path.resolve() in work_dir_path.resolve().parents:
                shutil.rmtree(work_dir_default, ignore_errors=True)
        
        # 2.2 Convert to absolute path and store
        self.work_dir = os.path.abspath(os.path.expanduser(work_dir))
        
        # 2.3 Clear work directory if requested
        if clear_work_dir:
            self.clear_work_dir()
        
        # 2.4 Add to Python path for imports
        sys.path.append(self.work_dir)
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 3: DATABASE INITIALIZATION (OPTIONAL)
        # ═══════════════════════════════════════════════════════════════════
        
        # 3.1 Check if database is enabled
        self.use_database = os.getenv("CMBAGENT_USE_DATABASE", "true").lower() == "true"
        
        if self.use_database:
            try:
                # 3.2 Import database modules
                from cmbagent.database import (
                    get_db_session, init_database,
                    WorkflowRepository, DualPersistenceManager,
                    SessionManager, DAGBuilder, DAGExecutor,
                    DAGVisualizer, StateMachine, ApprovalManager
                )
                from cmbagent.retry import RetryContextManager, RetryMetrics
                
                # 3.3 Initialize database tables
                init_database()
                
                # 3.4 Create database session
                self.db_session = get_db_session()
                
                # 3.5 Get or create user session
                session_manager = SessionManager(self.db_session)
                self.session_id = session_manager.get_or_create_default_session()
                
                # 3.6 Create repositories
                self.workflow_repo = WorkflowRepository(self.db_session, self.session_id)
                
                # 3.7 Create persistence manager
                self.persistence = DualPersistenceManager(
                    self.db_session, self.session_id, self.work_dir
                )
                
                # 3.8 Create DAG components
                self.dag_builder = DAGBuilder(self.db_session, self.session_id)
                self.dag_executor = DAGExecutor(self.db_session, self.session_id)
                self.dag_visualizer = DAGVisualizer(self.db_session)
                self.workflow_sm = StateMachine(self.db_session, "workflow_run")
                
                # 3.9 Create approval manager
                self.approval_manager = ApprovalManager(self.db_session, self.session_id)
                
                # 3.10 Create retry components
                self.retry_manager = RetryContextManager(self.db_session, self.session_id)
                self.retry_metrics = RetryMetrics(self.db_session)
                
            except Exception as e:
                # Fallback: continue without database
                self.use_database = False
                self.db_session = None
                # ... set all to None
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 4: MCP CLIENT INITIALIZATION (OPTIONAL)
        # ═══════════════════════════════════════════════════════════════════
        
        if self.enable_mcp_client:
            try:
                from cmbagent.mcp import MCPClientManager, MCPToolIntegration
                import asyncio
                
                # 4.1 Create MCP client manager (loads client_config.yaml)
                self.mcp_client_manager = MCPClientManager()
                
                # 4.2 Connect to all enabled MCP servers
                asyncio.run(self.mcp_client_manager.connect_all())
                
                # 4.3 Create tool integration helper
                self.mcp_tool_integration = MCPToolIntegration(self.mcp_client_manager)
                
            except Exception as e:
                self.enable_mcp_client = False
                self.mcp_client_manager = None
                self.mcp_tool_integration = None
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 5: LLM CONFIGURATION
        # ═══════════════════════════════════════════════════════════════════
        
        # 5.1 Copy default config list
        llm_config_list = default_llm_config_list.copy()
        
        # 5.2 Override API key if provided
        if llm_api_key is not None:
            llm_config_list[0]['api_key'] = llm_api_key
        
        if llm_api_type is not None:
            llm_config_list[0]['api_type'] = llm_api_type
        
        # 5.3 Store keys
        self.llm_api_key = llm_config_list[0]['api_key']
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # 5.4 Build master LLM config
        self.llm_config = {
            "cache_seed": cache_seed,
            "temperature": temperature,
            "top_p": top_p,
            "config_list": llm_config_list,
            "timeout": timeout,
            "check_every_ms": None,
        }
        
        # 5.5 Copy and merge agent-specific configs
        self.agent_llm_configs = default_agent_llm_configs.copy()
        self.agent_llm_configs.update(agent_llm_configs)
        
        # 5.6 If api_keys dict provided, update configs
        if api_keys is not None:
            self.llm_config["config_list"][0] = get_model_config(
                self.llm_config["config_list"][0]["model"], api_keys
            )
            for agent in self.agent_llm_configs.keys():
                self.agent_llm_configs[agent] = get_model_config(
                    self.agent_llm_configs[agent]["model"], api_keys
                )
        
        self.api_keys = api_keys
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 6: AGENT INITIALIZATION
        # ═══════════════════════════════════════════════════════════════════
        
        # 6.1 Initialize all agents
        self.init_agents(
            agent_llm_configs=self.agent_llm_configs,
            default_formatter_model=default_formatter_model
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 7: RAG SETUP (IF ENABLED)
        # ═══════════════════════════════════════════════════════════════════
        
        if not self.skip_rag_agents:
            # 7.1 Setup data directory
            setup_cmbagent_data()
            
            # 7.2 Check/create OpenAI assistants
            self.check_assistants(reset_assistant=reset_assistant)
            
            # 7.3 Push vector stores
            push_vector_stores(self, make_vector_stores, chunking_strategy, verbose)
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 8: AGENT CONFIGURATION
        # ═══════════════════════════════════════════════════════════════════
        
        # 8.1 Set planner instructions (template, currently placeholder)
        self.set_planner_instructions()
        
        # 8.2 Configure each agent
        for agent in self.agents:
            agent.agent_type = self.agent_type
            
            # Get overrides
            instructions = agent_instructions.get(agent.name)
            description = agent_descriptions.get(agent.name) if agent_descriptions else None
            
            agent_kwargs = {}
            if instructions: agent_kwargs['instructions'] = instructions
            if description: agent_kwargs['description'] = description
            
            if agent.name not in self.non_rag_agent_names:
                # RAG agent setup
                if self.skip_rag_agents:
                    continue
                    
                vector_ids = self.vector_store_ids.get(agent.name)
                temperature = agent_temperature.get(agent.name) if agent_temperature else None
                top_p = agent_top_p.get(agent.name) if agent_top_p else None
                
                if vector_ids: agent_kwargs['vector_store_ids'] = vector_ids
                agent_kwargs['agent_temperature'] = temperature or default_temperature
                agent_kwargs['agent_top_p'] = top_p or default_top_p
                
                # Set agent (may trigger vector store creation)
                result = agent.set_agent(**agent_kwargs)
                
                if result == 1:  # Vector store not found
                    push_vector_stores(self, [agent.name.removesuffix('_agent')], ...)
                    agent_kwargs['vector_store_ids'] = self.vector_store_ids[agent.name]
                    agent.set_agent(**agent_kwargs)
            else:
                # Non-RAG agent setup
                agent.set_agent(**agent_kwargs)
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 9: HAND-OFFS REGISTRATION
        # ═══════════════════════════════════════════════════════════════════
        
        register_all_hand_offs(self)
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 10: FUNCTIONS REGISTRATION
        # ═══════════════════════════════════════════════════════════════════
        
        register_functions_to_agents(self)
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 11: SHARED CONTEXT INITIALIZATION
        # ═══════════════════════════════════════════════════════════════════
        
        self.shared_context = shared_context_default.copy()
        if shared_context is not None:
            self.shared_context.update(shared_context)
```

---

## Agent Initialization

### `init_agents()` Method Flow

```python
# File: cmbagent/cmbagent.py

def init_agents(self, agent_llm_configs=None, default_formatter_model=...):
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 1: IMPORT AGENT CLASSES
    # ═══════════════════════════════════════════════════════════════════
    
    # 1.1 Import RAG agents from agents/rag_agents/
    imported_rag_agents = import_rag_agents()
    # Returns: {
    #     'CambAgentAgent': {
    #         'agent_class': CambAgentAgent,
    #         'agent_name': 'camb_agent'
    #     },
    #     'ClassySzAgentAgent': {...},
    #     ...
    # }
    
    # 1.2 Import non-RAG agents from agents/*/ (excluding rag_agents)
    imported_non_rag_agents = import_non_rag_agents()
    # Returns: {
    #     'EngineerAgent': {
    #         'agent_class': EngineerAgent,
    #         'agent_name': 'engineer'
    #     },
    #     'PlannerAgent': {...},
    #     'ExecutorAgent': {...},
    #     ...
    # }
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 2: BUILD AGENT CLASS REGISTRY
    # ═══════════════════════════════════════════════════════════════════
    
    self.agent_classes = {}      # name -> class
    self.rag_agent_names = []    # ['camb_agent', 'classy_sz_agent', ...]
    self.non_rag_agent_names = [] # ['engineer', 'planner', 'executor', ...]
    
    # 2.1 Register RAG agents
    for k in imported_rag_agents.keys():
        name = imported_rag_agents[k]['agent_name']
        cls = imported_rag_agents[k]['agent_class']
        self.agent_classes[name] = cls
        self.rag_agent_names.append(name)
    
    # 2.2 Register non-RAG agents
    for k in imported_non_rag_agents.keys():
        name = imported_non_rag_agents[k]['agent_name']
        cls = imported_non_rag_agents[k]['agent_class']
        self.agent_classes[name] = cls
        self.non_rag_agent_names.append(name)
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 3: FILTER AGENTS
    # ═══════════════════════════════════════════════════════════════════
    
    # 3.1 If agent_list is None, use all agents
    if self.agent_list is None:
        self.agent_list = list(self.agent_classes.keys())
    
    # 3.2 Keep only agents in agent_list OR non-RAG agents (always needed)
    self.agent_classes = {
        k: v for k, v in self.agent_classes.items()
        if k in self.agent_list or k in self.non_rag_agent_names
    }
    
    # 3.3 Remove skipped agents
    if self.skip_memory:
        self.agent_classes.pop('session_summarizer', None)
    
    if self.skip_executor:
        self.agent_classes.pop('executor', None)
    
    if self.skip_rag_software_formatter:
        self.agent_classes.pop('rag_software_formatter', None)
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 4: INSTANTIATE AGENTS
    # ═══════════════════════════════════════════════════════════════════
    
    self.agents = []
    
    for agent_name, agent_class in self.agent_classes.items():
        
        # 4.1 Determine LLM config for this agent
        if agent_name in agent_llm_configs:
            # Use agent-specific config
            llm_config = copy.deepcopy(self.llm_config)
            llm_config['config_list'][0].update(agent_llm_configs[agent_name])
            clean_llm_config(llm_config)
        else:
            # Use default config
            llm_config = copy.deepcopy(self.llm_config)
        
        # 4.2 Create agent instance
        agent_instance = agent_class(
            llm_config=llm_config,
            agent_type=self.agent_type,
            work_dir=self.work_dir
        )
        
        self.agents.append(agent_instance)
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 5: REMOVE RAG AGENTS IF SKIPPED
    # ═══════════════════════════════════════════════════════════════════
    
    if self.skip_rag_agents:
        self.agents = [
            agent for agent in self.agents
            if agent.name.replace('_agent', '') not in self.rag_agent_names
        ]
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 6: UPDATE FORMATTER MODELS
    # ═══════════════════════════════════════════════════════════════════
    
    for agent in self.agents:
        if "formatter" in agent.name:
            # Formatters use cheaper/faster model
            agent.llm_config['config_list'][0].update(
                get_model_config(default_formatter_model, self.api_keys)
            )
        
        # Clean up any inconsistent config params
        clean_llm_config(agent.llm_config)
    
    # Store agent names for reference
    self.agent_names = [agent.name for agent in self.agents]
```

### Agent Import Functions

```python
# File: cmbagent/rag_utils.py

def import_rag_agents():
    """Import all RAG agent classes from agents/rag_agents/"""
    imported_rag_agents = {}
    
    for filename in os.listdir(path_to_assistants):
        if filename.endswith(".py") and filename != "__init__.py" and filename[0] != ".":
            # camb_agent.py -> camb_agent
            module_name = filename[:-3]
            
            # camb_agent -> CambAgentAgent
            class_name = ''.join([
                part.capitalize() for part in module_name.split('_')
            ]) + 'Agent'
            
            # Import the module
            module_path = f"cmbagent.agents.rag_agents.{module_name}"
            module = importlib.import_module(module_path)
            
            # Get the class
            agent_class = getattr(module, class_name)
            
            imported_rag_agents[class_name] = {
                'agent_class': agent_class,
                'agent_name': module_name
            }
    
    return imported_rag_agents
```

```python
# File: cmbagent/managers/agent_manager.py

def import_non_rag_agents():
    """Import all non-RAG agent classes from agents/*/"""
    imported_non_rag_agents = {}
    
    for dir_name in os.listdir(path_to_agents):
        dir_path = os.path.join(path_to_agents, dir_name)
        
        # Skip non-directories and special folders
        if not os.path.isdir(dir_path):
            continue
        if dir_name in ['rag_agents', '__pycache__']:
            continue
        
        # Look for matching .py file
        py_file = os.path.join(dir_path, f"{dir_name}.py")
        if os.path.exists(py_file):
            # engineer -> EngineerAgent
            class_name = ''.join([
                part.capitalize() for part in dir_name.split('_')
            ]) + 'Agent'
            
            module_path = f"cmbagent.agents.{dir_name}.{dir_name}"
            module = importlib.import_module(module_path)
            agent_class = getattr(module, class_name)
            
            imported_non_rag_agents[class_name] = {
                'agent_class': agent_class,
                'agent_name': dir_name
            }
    
    return imported_non_rag_agents
```

---

## LLM Configuration Resolution

### Configuration Priority Chain

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LLM CONFIG RESOLUTION ORDER                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. User provides agent_llm_configs for specific agent                      │
│     └── CMBAgent(agent_llm_configs={'engineer': {'model': 'gpt-4o'}})       │
│                                                                              │
│  2. Falls back to default_agent_llm_configs for that agent                  │
│     └── default_agents_llm_model['engineer'] = 'gpt-4o'                     │
│                                                                              │
│  3. Falls back to default_llm_model                                         │
│     └── default_llm_model = 'gpt-4o'                                        │
│                                                                              │
│  4. Falls back to hardcoded default in utils.py                             │
│     └── "gpt-4o"                                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### `get_model_config()` Function

```python
# File: cmbagent/utils.py

def get_model_config(model_name: str, api_keys: dict = None) -> dict:
    """
    Build LLM config dict for a given model.
    
    Args:
        model_name: Model identifier (e.g., 'gpt-4o', 'claude-3-opus')
        api_keys: Dict with API keys {'openai': '...', 'anthropic': '...'}
    
    Returns:
        Config dict with model, api_key, api_type
    """
    
    if api_keys is None:
        api_keys = get_api_keys_from_env()
    
    # Determine provider from model name
    if model_name.startswith('gpt') or model_name.startswith('o1') or model_name.startswith('o3'):
        return {
            'model': model_name,
            'api_key': api_keys.get('openai', os.getenv('OPENAI_API_KEY')),
            'api_type': 'openai'
        }
    
    elif model_name.startswith('claude'):
        return {
            'model': model_name,
            'api_key': api_keys.get('anthropic', os.getenv('ANTHROPIC_API_KEY')),
            'api_type': 'anthropic'
        }
    
    elif model_name.startswith('gemini'):
        return {
            'model': model_name,
            'api_key': api_keys.get('google', os.getenv('GEMINI_API_KEY')),
            'api_type': 'google'
        }
    
    # Default to OpenAI
    return {
        'model': model_name,
        'api_key': api_keys.get('openai', os.getenv('OPENAI_API_KEY')),
        'api_type': 'openai'
    }

def get_api_keys_from_env() -> dict:
    """Get all API keys from environment variables."""
    return {
        'openai': os.getenv('OPENAI_API_KEY'),
        'anthropic': os.getenv('ANTHROPIC_API_KEY'),
        'google': os.getenv('GEMINI_API_KEY'),
        'perplexity': os.getenv('PERPLEXITY_API_KEY'),
    }
```

### `clean_llm_config()` Function

```python
# File: cmbagent/utils.py

def clean_llm_config(llm_config: dict):
    """
    Remove inconsistent parameters from LLM config.
    Modifies config in place.
    
    Rules:
    - Remove 'reasoning_effort' for non-o1/o3 models
    - Remove 'temperature' if in config_list (move to top level)
    - Handle provider-specific params
    """
    config = llm_config['config_list'][0]
    model = config.get('model', '')
    
    # reasoning_effort only for o1/o3 models
    if 'reasoning_effort' in config:
        if not (model.startswith('o1') or model.startswith('o3')):
            del config['reasoning_effort']
    
    # Temperature in config_list should be at top level
    if 'temperature' in config:
        temp = config.pop('temperature')
        llm_config['temperature'] = temp
```

---

## RAG and Vector Store Setup

### Vector Store Push Flow

```python
# File: cmbagent/rag_utils.py

def push_vector_stores(cmbagent_instance, make_vector_stores, chunking_strategy, verbose=False):
    """
    Create/update OpenAI vector stores for RAG agents.
    
    Flow:
    1. Identify which agents need vector stores
    2. Delete existing vector stores with same name
    3. Create new vector stores
    4. Upload files from CMBAGENT_DATA/data/{agent}/
    5. Store vector store IDs for agent configuration
    """
    
    if make_vector_stores == False:
        return
    
    client = OpenAI(api_key=cmbagent_instance.llm_api_key)
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 1: IDENTIFY RAG AGENTS
    # ═══════════════════════════════════════════════════════════════════
    
    store_names = []
    rag_agents = []
    
    for agent in cmbagent_instance.agents:
        # Filter by make_vector_stores list if provided
        if type(make_vector_stores) == list:
            if agent.info['name'] not in make_vector_stores:
                if agent.info['name'].replace('_agent', '') not in make_vector_stores:
                    continue
        
        # Check if agent has file_search configured
        if 'assistant_config' in agent.info:
            if 'file_search' in agent.info['assistant_config']['tool_resources'].keys():
                store_names.append(f"{agent.info['name']}_store")
                rag_agents.append(agent)
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 2: GET EXISTING VECTOR STORES
    # ═══════════════════════════════════════════════════════════════════
    
    headers = {
        "Authorization": f"Bearer {cmbagent_instance.llm_api_key}",
        "OpenAI-Beta": "assistants=v2"
    }
    url = "https://api.openai.com/v1/vector_stores"
    response = requests.get(url, headers=headers)
    vector_stores = response.json()
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 3: FOR EACH AGENT, DELETE OLD AND CREATE NEW
    # ═══════════════════════════════════════════════════════════════════
    
    vector_store_ids = {}
    
    for vector_store_name, rag_agent in zip(store_names, rag_agents):
        
        # 3.1 Find and delete existing stores with this name
        matching_ids = [
            store['id'] for store in vector_stores['data']
            if store['name'] == vector_store_name
        ]
        
        for store_id in matching_ids:
            delete_url = f"{url}/{store_id}"
            requests.delete(delete_url, headers=headers)
        
        # 3.2 Get chunking strategy for this agent
        agent_chunking = chunking_strategy.get(
            rag_agent.name,
            default_chunking_strategy
        )
        
        # 3.3 Create new vector store
        vector_store = client.vector_stores.create(
            name=vector_store_name,
            chunking_strategy=agent_chunking
        )
        
        # 3.4 Get data directory
        # CMBAGENT_DATA/data/{agent_name_without_agent_suffix}/
        data_dir = os.getenv('CMBAGENT_DATA') + "/data/" + \
                   vector_store_name.removesuffix('_agent_store')
        
        # 3.5 Collect files to upload
        file_paths = []
        for root, dirs, files in os.walk(data_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if not file.startswith('.') and not file.endswith(('.ipynb', '.yaml', '.txt')):
                    file_paths.append(os.path.join(root, file))
        
        # 3.6 Upload files in batches
        file_streams = [open(path, 'rb') for path in file_paths]
        file_batch = client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=file_streams
        )
        
        # 3.7 Store vector store ID
        vector_store_ids[rag_agent.name] = vector_store.id
        
        # 3.8 Update agent YAML file
        update_yaml_preserving_format(
            f"{path_to_assistants}/{rag_agent.name.replace('_agent', '')}.yaml",
            rag_agent.name,
            vector_store.id,
            field='vector_store_ids'
        )
    
    cmbagent_instance.vector_store_ids = vector_store_ids
```

### Assistant Check Flow

```python
# File: cmbagent/cmbagent.py

def check_assistants(self, reset_assistant=[]):
    """
    Verify OpenAI assistants exist and have correct configuration.
    Creates new assistants if missing.
    Updates model if changed.
    """
    
    client = OpenAI(api_key=self.openai_api_key)
    
    # Get list of existing assistants
    available = client.beta.assistants.list(order="desc", limit="100")
    assistant_names = [d.name for d in available.data]
    assistant_ids = [d.id for d in available.data]
    assistant_models = [d.model for d in available.data]
    
    for agent in self.agents:
        if agent.name not in self.non_rag_agent_names:
            
            if agent.name in assistant_names:
                idx = assistant_names.index(agent.name)
                existing_id = assistant_ids[idx]
                existing_model = assistant_models[idx]
                
                # Check if model needs update
                requested_model = agent.llm_config['config_list'][0]['model']
                if existing_model != requested_model:
                    client.beta.assistants.update(
                        assistant_id=existing_id,
                        model=requested_model
                    )
                
                # Check if agent should be reset
                if reset_assistant and agent.name.replace('_agent', '') in reset_assistant:
                    client.beta.assistants.delete(existing_id)
                    new_assistant = self.create_assistant(client, agent)
                    agent.info['assistant_config']['assistant_id'] = new_assistant.id
                else:
                    # Sync assistant_id in YAML with OpenAI
                    yaml_id = agent.info['assistant_config']['assistant_id']
                    if yaml_id != existing_id:
                        agent.info['assistant_config']['assistant_id'] = existing_id
                        update_yaml_preserving_format(
                            f"{path_to_assistants}/{agent.name.replace('_agent', '')}.yaml",
                            agent.name,
                            existing_id,
                            field='assistant_id'
                        )
            else:
                # Create new assistant
                new_assistant = self.create_assistant(client, agent)
                agent.info['assistant_config']['assistant_id'] = new_assistant.id
```

---

## Database Initialization

### Database Connection Setup

```python
# File: cmbagent/database/base.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()
_engine = None
_SessionLocal = None

def get_engine():
    """Get or create database engine."""
    global _engine
    
    if _engine is None:
        # Get database URL from environment
        database_url = os.getenv(
            'DATABASE_URL',
            'sqlite:///./cmbagent.db'  # Default to SQLite
        )
        
        # Create engine with appropriate settings
        if database_url.startswith('postgresql'):
            _engine = create_engine(
                database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10
            )
        else:
            # SQLite
            _engine = create_engine(
                database_url,
                connect_args={'check_same_thread': False}
            )
    
    return _engine

def get_db_session():
    """Get a new database session."""
    global _SessionLocal
    
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine()
        )
    
    return _SessionLocal()

def init_database():
    """Create all database tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
```

### Session Manager

```python
# File: cmbagent/database/session_manager.py

class SessionManager:
    """Manages user sessions for workflow isolation."""
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    def get_or_create_default_session(self) -> str:
        """Get existing default session or create one."""
        
        # Try to find existing active session
        existing = self.db_session.query(Session).filter(
            Session.status == 'active',
            Session.name == 'default'
        ).first()
        
        if existing:
            # Update last_active timestamp
            existing.last_active_at = datetime.now(timezone.utc)
            self.db_session.commit()
            return existing.id
        
        # Create new session
        new_session = Session(
            name='default',
            status='active',
            created_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc)
        )
        self.db_session.add(new_session)
        self.db_session.commit()
        
        return new_session.id
```

---

## Hand-offs and Functions Registration

### Hand-offs Registration

```python
# File: cmbagent/hand_offs.py

def register_all_hand_offs(cmbagent_instance):
    """
    Register all agent-to-agent transitions.
    Called after all agents are instantiated.
    """
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 1: GET ALL AGENT REFERENCES
    # ═══════════════════════════════════════════════════════════════════
    
    # Planning agents
    task_improver = cmbagent_instance.get_agent_object_from_name('task_improver')
    task_recorder = cmbagent_instance.get_agent_object_from_name('task_recorder')
    planner = cmbagent_instance.get_agent_object_from_name('planner')
    planner_response_formatter = cmbagent_instance.get_agent_object_from_name('planner_response_formatter')
    plan_recorder = cmbagent_instance.get_agent_object_from_name('plan_recorder')
    plan_reviewer = cmbagent_instance.get_agent_object_from_name('plan_reviewer')
    reviewer_response_formatter = cmbagent_instance.get_agent_object_from_name('reviewer_response_formatter')
    review_recorder = cmbagent_instance.get_agent_object_from_name('review_recorder')
    
    # Execution agents
    engineer = cmbagent_instance.get_agent_object_from_name('engineer')
    engineer_response_formatter = cmbagent_instance.get_agent_object_from_name('engineer_response_formatter')
    researcher = cmbagent_instance.get_agent_object_from_name('researcher')
    researcher_response_formatter = cmbagent_instance.get_agent_object_from_name('researcher_response_formatter')
    executor = cmbagent_instance.get_agent_object_from_name('executor')
    researcher_executor = cmbagent_instance.get_agent_object_from_name('researcher_executor')
    executor_bash = cmbagent_instance.get_agent_object_from_name('executor_bash')
    
    # Control agents
    control = cmbagent_instance.get_agent_object_from_name('control')
    terminator = cmbagent_instance.get_agent_object_from_name('terminator')
    
    # ... get all other agents
    
    mode = cmbagent_instance.mode
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 2: REGISTER PLANNING CHAIN
    # ═══════════════════════════════════════════════════════════════════
    
    task_improver.agent.handoffs.set_after_work(AgentTarget(task_recorder.agent))
    task_recorder.agent.handoffs.set_after_work(AgentTarget(planner.agent))
    planner.agent.handoffs.set_after_work(AgentTarget(planner_response_formatter.agent))
    planner_response_formatter.agent.handoffs.set_after_work(AgentTarget(plan_recorder.agent))
    plan_recorder.agent.handoffs.set_after_work(AgentTarget(plan_reviewer.agent))
    plan_reviewer.agent.handoffs.set_after_work(AgentTarget(reviewer_response_formatter.agent))
    reviewer_response_formatter.agent.handoffs.set_after_work(AgentTarget(review_recorder.agent))
    review_recorder.agent.handoffs.set_after_work(AgentTarget(planner.agent))  # Loop back
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 3: REGISTER EXECUTION CHAINS
    # ═══════════════════════════════════════════════════════════════════
    
    # Engineer chain
    engineer.agent.handoffs.set_after_work(AgentTarget(engineer_response_formatter.agent))
    # engineer_response_formatter -> executor (registered in functions)
    
    # Researcher chain
    researcher.agent.handoffs.set_after_work(AgentTarget(researcher_response_formatter.agent))
    researcher_response_formatter.agent.handoffs.set_after_work(AgentTarget(researcher_executor.agent))
    
    # Executor chains
    executor_bash.agent.handoffs.set_after_work(AgentTarget(executor_response_formatter.agent))
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 4: MODE-SPECIFIC ROUTING
    # ═══════════════════════════════════════════════════════════════════
    
    if mode == "one_shot":
        # In one-shot mode, go back to engineer after RAG
        camb_response_formatter.agent.handoffs.set_after_work(AgentTarget(engineer.agent))
        classy_response_formatter.agent.handoffs.set_after_work(AgentTarget(engineer.agent))
    else:
        # In planning mode, go back to control
        camb_response_formatter.agent.handoffs.set_after_work(AgentTarget(control.agent))
        classy_response_formatter.agent.handoffs.set_after_work(AgentTarget(control.agent))
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 5: REGISTER RAG AGENT CHAINS (IF ENABLED)
    # ═══════════════════════════════════════════════════════════════════
    
    if not cmbagent_instance.skip_rag_agents:
        camb = cmbagent_instance.get_agent_object_from_name('camb_agent')
        classy_sz = cmbagent_instance.get_agent_object_from_name('classy_sz_agent')
        cobaya = cmbagent_instance.get_agent_object_from_name('cobaya_agent')
        
        camb.agent.handoffs.set_after_work(AgentTarget(camb_response_formatter.agent))
        classy_sz.agent.handoffs.set_after_work(AgentTarget(classy_sz_response_formatter.agent))
        cobaya.agent.handoffs.set_after_work(AgentTarget(cobaya_response_formatter.agent))
```

### Functions Registration

```python
# File: cmbagent/functions/registration.py

def register_functions_to_agents(cmbagent_instance):
    """
    Register callable functions with appropriate agents.
    These functions can be called by agents during execution.
    """
    
    # ═══════════════════════════════════════════════════════════════════
    # PLANNING FUNCTIONS
    # ═══════════════════════════════════════════════════════════════════
    
    from cmbagent.functions.planning import (
        record_improved_task,
        record_plan,
        save_final_plan,
        record_review,
        get_plan_status,
    )
    
    task_improver = cmbagent_instance.get_agent_from_name('task_improver')
    task_recorder = cmbagent_instance.get_agent_from_name('task_recorder')
    plan_recorder = cmbagent_instance.get_agent_from_name('plan_recorder')
    review_recorder = cmbagent_instance.get_agent_from_name('review_recorder')
    
    # Register with agents
    task_recorder.register_for_llm()(record_improved_task)
    plan_recorder.register_for_llm()(record_plan)
    plan_recorder.register_for_llm()(save_final_plan)
    review_recorder.register_for_llm()(record_review)
    
    # ═══════════════════════════════════════════════════════════════════
    # EXECUTION CONTROL FUNCTIONS
    # ═══════════════════════════════════════════════════════════════════
    
    from cmbagent.functions.execution_control import (
        record_status,
        transfer_to_agent,
        terminate_workflow,
    )
    
    control = cmbagent_instance.get_agent_from_name('control')
    control.register_for_llm()(record_status)
    control.register_for_llm()(transfer_to_agent)
    
    terminator = cmbagent_instance.get_agent_from_name('terminator')
    terminator.register_for_llm()(terminate_workflow)
    
    # ═══════════════════════════════════════════════════════════════════
    # STATUS FUNCTIONS
    # ═══════════════════════════════════════════════════════════════════
    
    from cmbagent.functions.status import (
        update_step_status,
        get_current_step,
        mark_step_complete,
        mark_step_failed,
    )
    
    # Register with execution agents
    engineer = cmbagent_instance.get_agent_from_name('engineer')
    researcher = cmbagent_instance.get_agent_from_name('researcher')
    
    for agent in [control, engineer, researcher]:
        agent.register_for_llm()(update_step_status)
        agent.register_for_llm()(get_current_step)
    
    # ═══════════════════════════════════════════════════════════════════
    # IDEAS FUNCTIONS
    # ═══════════════════════════════════════════════════════════════════
    
    from cmbagent.functions.ideas import (
        record_idea,
        record_critique,
        save_idea,
    )
    
    idea_maker = cmbagent_instance.get_agent_from_name('idea_maker')
    idea_hater = cmbagent_instance.get_agent_from_name('idea_hater')
    idea_saver = cmbagent_instance.get_agent_from_name('idea_saver')
    
    idea_maker.register_for_llm()(record_idea)
    idea_hater.register_for_llm()(record_critique)
    idea_saver.register_for_llm()(save_idea)
    
    # ═══════════════════════════════════════════════════════════════════
    # KEYWORD FUNCTIONS
    # ═══════════════════════════════════════════════════════════════════
    
    from cmbagent.functions.keywords import (
        find_aas_keywords,
        extract_keywords,
    )
    
    aas_keyword_finder = cmbagent_instance.get_agent_from_name('aas_keyword_finder')
    aas_keyword_finder.register_for_llm()(find_aas_keywords)
    aas_keyword_finder.register_for_llm()(extract_keywords)
```

---

## Workflow Execution Flow

### `solve()` Method

```python
# File: cmbagent/cmbagent.py

def solve(self, task, initial_agent='task_improver', shared_context=None,
          mode="default", step=None, max_rounds=10):
    """
    Execute a task using the multi-agent system.
    
    This is the main entry point for task execution.
    """
    
    self.step = step  # For context carryover workflow
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 1: PREPARE SHARED CONTEXT
    # ═══════════════════════════════════════════════════════════════════
    
    this_shared_context = copy.deepcopy(self.shared_context)
    
    if mode == "one_shot" or mode == "chat":
        # One-shot mode: single step, no planning
        one_shot_context = {
            'final_plan': "Step 1: solve the main task.",
            'current_status': "In progress",
            'current_plan_step_number': 1,
            'current_sub_task': "solve the main task.",
            'current_instructions': "solve the main task.",
            'agent_for_sub_task': initial_agent,
            'feedback_left': 0,
            'number_of_steps_in_plan': 1,
            'maximum_number_of_steps_in_plan': 1,
            'researcher_append_instructions': '',
            'engineer_append_instructions': '',
            'perplexity_append_instructions': '',
            'idea_maker_append_instructions': '',
            'idea_hater_append_instructions': '',
        }
        
        this_shared_context.update(one_shot_context)
        this_shared_context.update(shared_context or {})
    else:
        # Planning mode: merge user context
        if shared_context is not None:
            this_shared_context.update(shared_context)
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 2: SETUP WORKING DIRECTORY
    # ═══════════════════════════════════════════════════════════════════
    
    if self.clear_work_dir_bool:
        self.clear_work_dir()
    
    # Create subdirectories
    database_path = os.path.join(self.work_dir, this_shared_context.get("database_path", "data"))
    codebase_path = os.path.join(self.work_dir, this_shared_context.get("codebase_path", "codebase"))
    chat_path = os.path.join(self.work_dir, "chats")
    time_path = os.path.join(self.work_dir, "time")
    cost_path = os.path.join(self.work_dir, "cost")
    
    os.makedirs(database_path, exist_ok=True)
    os.makedirs(codebase_path, exist_ok=True)
    os.makedirs(chat_path, exist_ok=True)
    os.makedirs(time_path, exist_ok=True)
    os.makedirs(cost_path, exist_ok=True)
    
    # Add codebase to Python path
    sys.path.append(codebase_path)
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 3: RESET AGENTS
    # ═══════════════════════════════════════════════════════════════════
    
    for agent in self.agents:
        try:
            agent.agent.reset()
        except:
            pass
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 4: INITIALIZE CONTEXT
    # ═══════════════════════════════════════════════════════════════════
    
    this_shared_context['main_task'] = task
    this_shared_context['improved_main_task'] = task
    this_shared_context['work_dir'] = self.work_dir
    
    # Create AG2 context variables
    context_variables = ContextVariables(data=this_shared_context)
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 5: CREATE AGENT PATTERN
    # ═══════════════════════════════════════════════════════════════════
    
    agent_pattern = AutoPattern(
        agents=[agent.agent for agent in self.agents],
        initial_agent=self.get_agent_from_name(initial_agent),
        context_variables=context_variables,
        group_manager_args={
            "llm_config": self.llm_config,
            "name": "main_cmbagent_chat"
        },
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 6: EXECUTE GROUP CHAT
    # ═══════════════════════════════════════════════════════════════════
    
    chat_result, context_variables, last_agent = initiate_group_chat(
        pattern=agent_pattern,
        messages=this_shared_context['main_task'],
        max_rounds=max_rounds,
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 7: STORE RESULTS
    # ═══════════════════════════════════════════════════════════════════
    
    self.final_context = copy.deepcopy(context_variables)
    self.last_agent = last_agent
    self.chat_result = chat_result
```

### Planning and Control Workflow

```python
# File: cmbagent/workflows/planning_control.py

def planning_and_control_context_carryover(task, ...):
    """
    Full workflow with context carryover between steps.
    """
    
    # ═══════════════════════════════════════════════════════════════════
    # PHASE 1: SETUP
    # ═══════════════════════════════════════════════════════════════════
    
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)
    
    if clear_work_dir:
        clean_work_dir(work_dir)
    
    context_dir = os.path.join(work_dir, "context")
    os.makedirs(context_dir, exist_ok=True)
    
    # Initialize output manager
    run_id = str(uuid.uuid4())
    output_manager = WorkflowOutputManager(work_dir=work_dir, run_id=run_id)
    
    # Get API keys
    if api_keys is None:
        api_keys = get_api_keys_from_env()
    
    # Initialize callbacks
    if callbacks is None:
        callbacks = create_null_callbacks()
    
    # Invoke workflow start callback
    callbacks.invoke_workflow_start(task, {...})
    
    # ═══════════════════════════════════════════════════════════════════
    # PHASE 2: PLANNING
    # ═══════════════════════════════════════════════════════════════════
    
    callbacks.invoke_planning_start(task, {...})
    
    # Create CMBAgent for planning
    planner_config = get_model_config(planner_model, api_keys)
    plan_reviewer_config = get_model_config(plan_reviewer_model, api_keys)
    
    planning_cmbagent = CMBAgent(
        work_dir=os.path.join(work_dir, "planning"),
        agent_llm_configs={
            'planner': planner_config,
            'plan_reviewer': plan_reviewer_config,
        },
        clear_work_dir=True,
        api_keys=api_keys,
        approval_config=approval_config,
    )
    
    # Execute planning
    planning_cmbagent.solve(
        task,
        max_rounds=max_rounds_planning,
        initial_agent="task_improver",  # Starts planning chain
        shared_context={
            'feedback_left': n_plan_reviews,
            'maximum_number_of_steps_in_plan': max_plan_steps,
            'planner_append_instructions': plan_instructions,
            'hardware_constraints': hardware_constraints,
        }
    )
    
    planning_output = copy.deepcopy(planning_cmbagent.final_context)
    callbacks.invoke_planning_complete(PlanInfo(...))
    
    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3: CONTROL (PER STEP)
    # ═══════════════════════════════════════════════════════════════════
    
    # Determine start step
    if restart_at_step > 0:
        start_step = restart_at_step
        # Load context from previous run
        planning_output = load_context(os.path.join(context_dir, f"step_{restart_at_step-1}.pkl"))
    else:
        start_step = 1
    
    final_plan = planning_output['final_plan']
    num_steps = len(final_plan)
    
    for step_num in range(start_step, num_steps + 1):
        
        step_info = StepInfo(
            step_number=step_num,
            goal=final_plan[step_num - 1]['sub_task'],
            status=StepStatus.RUNNING
        )
        callbacks.invoke_step_start(step_info)
        
        # Prepare step context
        step_context = copy.deepcopy(planning_output)
        step_context['current_plan_step_number'] = step_num
        step_context['current_sub_task'] = final_plan[step_num - 1]['sub_task']
        step_context['agent_for_sub_task'] = final_plan[step_num - 1]['sub_task_agent']
        step_context['current_instructions'] = format_bullet_points(
            final_plan[step_num - 1]['bullet_points']
        )
        
        # Add previous steps summary
        if step_num > 1:
            step_context['previous_steps_execution_summary'] = load_context(
                os.path.join(context_dir, f"step_{step_num-1}.pkl")
            ).get('previous_steps_execution_summary', '')
        
        # Create CMBAgent for this step
        engineer_config = get_model_config(engineer_model, api_keys)
        researcher_config = get_model_config(researcher_model, api_keys)
        
        step_cmbagent = CMBAgent(
            work_dir=os.path.join(work_dir, f"step_{step_num}"),
            agent_llm_configs={
                'engineer': engineer_config,
                'researcher': researcher_config,
            },
            clear_work_dir=True,
            api_keys=api_keys,
        )
        
        # Execute with retry
        attempt = 0
        success = False
        
        while attempt < max_n_attempts and not success:
            attempt += 1
            step_context['n_attempts'] = attempt
            
            try:
                step_cmbagent.solve(
                    task,
                    max_rounds=max_rounds_control,
                    initial_agent="control",
                    shared_context=step_context,
                    step=step_num,
                )
                
                # Check for success
                if step_cmbagent.final_context.get('current_status') == 'completed':
                    success = True
                    
            except Exception as e:
                if attempt >= max_n_attempts:
                    step_info.status = StepStatus.FAILED
                    step_info.error = str(e)
                    callbacks.invoke_step_failed(step_info)
                    raise
        
        # Save context for next step
        with open(os.path.join(context_dir, f"step_{step_num}.pkl"), 'wb') as f:
            pickle.dump(step_cmbagent.final_context, f)
        
        # Update planning output for next step
        planning_output.update(step_cmbagent.final_context)
        
        # Append to summary
        planning_output['previous_steps_execution_summary'] += (
            f"\n\n--- Step {step_num} ---\n" +
            step_cmbagent.final_context.get('step_summary', '')
        )
        
        step_info.status = StepStatus.COMPLETED
        callbacks.invoke_step_complete(step_info)
    
    # ═══════════════════════════════════════════════════════════════════
    # PHASE 4: COMPLETION
    # ═══════════════════════════════════════════════════════════════════
    
    total_time = time.time() - workflow_start_time
    
    callbacks.invoke_workflow_complete(planning_output, total_time)
    
    return {
        'chat_history': planning_output.get('chat_history', []),
        'final_context': planning_output,
    }
```

---

## Backend and Frontend Initialization

### Backend Startup (`backend/main.py`)

```python
# File: backend/main.py

# 1. Add paths
sys.path.append(str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

# 2. Import components
from core.app import create_app
from routers import register_routers
from websocket.handlers import websocket_endpoint as ws_handler
from execution.task_executor import execute_cmbagent_task

# 3. Create FastAPI app
app = create_app()

# 4. Register routers
register_routers(app)

# 5. WebSocket endpoint
@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await ws_handler(websocket, task_id, execute_cmbagent_task)
```

```python
# File: backend/core/app.py

def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="CMBAgent API",
        description="Multi-agent system for autonomous discovery",
        version="0.0.1",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Startup event
    @app.on_event("startup")
    async def startup():
        # Initialize database if enabled
        if os.getenv("CMBAGENT_USE_DATABASE", "true").lower() == "true":
            from cmbagent.database import init_database
            init_database()
    
    return app
```

### Router Registration

```python
# File: backend/routers/__init__.py

def register_routers(app: FastAPI):
    """Register all API routers."""
    
    from routers.tasks import router as tasks_router
    from routers.workflows import router as workflows_router
    from routers.steps import router as steps_router
    from routers.files import router as files_router
    from routers.costs import router as costs_router
    from routers.approvals import router as approvals_router
    from routers.dag import router as dag_router
    from routers.health import router as health_router
    
    app.include_router(health_router, prefix="/api", tags=["Health"])
    app.include_router(tasks_router, prefix="/api/tasks", tags=["Tasks"])
    app.include_router(workflows_router, prefix="/api/workflows", tags=["Workflows"])
    app.include_router(steps_router, prefix="/api/steps", tags=["Steps"])
    app.include_router(files_router, prefix="/api/files", tags=["Files"])
    app.include_router(costs_router, prefix="/api/costs", tags=["Costs"])
    app.include_router(approvals_router, prefix="/api/approvals", tags=["Approvals"])
    app.include_router(dag_router, prefix="/api/dag", tags=["DAG"])
```

### WebSocket Handler

```python
# File: backend/websocket/handlers.py

async def websocket_endpoint(
    websocket: WebSocket,
    task_id: str,
    execute_func: Callable
):
    """
    Handle WebSocket connection for task execution.
    """
    
    await websocket.accept()
    
    try:
        # Receive task configuration
        data = await websocket.receive_json()
        task = data.get('task')
        config = data.get('config', {})
        
        # Send status update
        await send_ws_event(websocket, 'status', {
            'message': 'Task received, starting execution...'
        })
        
        # Execute task with streaming output
        await execute_func(
            websocket=websocket,
            task_id=task_id,
            task=task,
            config=config
        )
        
        # Send completion
        await send_ws_event(websocket, 'complete', {
            'task_id': task_id
        })
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await send_ws_event(websocket, 'error', {
            'message': str(e)
        })
    finally:
        await websocket.close()
```

### Frontend Initialization (`cmbagent-ui/`)

```typescript
// File: cmbagent-ui/app/providers.tsx

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <WebSocketProvider>
      {children}
    </WebSocketProvider>
  );
}
```

```typescript
// File: cmbagent-ui/contexts/WebSocketContext.tsx

export function WebSocketProvider({ children }: { children: ReactNode }) {
  // State initialization
  const [connected, setConnected] = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<string | null>(null);
  const [dagData, setDAGData] = useState<DAGData | null>(null);
  const [consoleOutput, setConsoleOutput] = useState<string[]>([]);
  const [results, setResults] = useState<any | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [costSummary, setCostSummary] = useState<CostSummary>({...});
  
  // WebSocket ref
  const wsRef = useRef<WebSocket | null>(null);
  
  // Connect function
  const connect = useCallback(async (taskId: string, task: string, config: any) => {
    // Close existing connection
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    
    // Create new WebSocket
    const ws = new WebSocket(getWsUrl(`/ws/${taskId}`));
    wsRef.current = ws;
    
    ws.onopen = () => {
      setConnected(true);
      setCurrentRunId(taskId);
      ws.send(JSON.stringify({ task, config }));
    };
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      handleWebSocketMessage(message);
    };
    
    ws.onclose = () => {
      setConnected(false);
      setIsRunning(false);
    };
  }, []);
  
  // Message handler
  const handleWebSocketMessage = (message: WebSocketEvent) => {
    switch (message.type) {
      case 'output':
        setConsoleOutput(prev => [...prev, message.data]);
        break;
        
      case 'dag_created':
        setDAGData(message.data);
        break;
        
      case 'dag_node_status_changed':
        updateDAGNode(message.data.node_id, message.data.status);
        break;
        
      case 'step_started':
        setWorkflowStatus(`Step ${message.data.step_number}: ${message.data.goal}`);
        break;
        
      case 'cost_update':
        setCostSummary(message.data);
        break;
        
      case 'result':
        setResults(message.data);
        break;
        
      case 'complete':
        setIsRunning(false);
        break;
        
      case 'error':
        setConsoleOutput(prev => [...prev, `❌ Error: ${message.message}`]);
        break;
    }
  };
  
  return (
    <WebSocketContext.Provider value={{
      connected,
      connect,
      disconnect,
      sendMessage,
      currentRunId,
      consoleOutput,
      results,
      isRunning,
      workflowStatus,
      dagData,
      costSummary,
      // ... other values
    }}>
      {children}
    </WebSocketContext.Provider>
  );
}
```

---

## Complete Sequence Diagrams

### Full Initialization Sequence

```
┌──────────────┐    ┌─────────────┐    ┌───────────────┐    ┌─────────────┐
│    User      │    │  CMBAgent   │    │    Agents     │    │   OpenAI    │
└──────┬───────┘    └──────┬──────┘    └───────┬───────┘    └──────┬──────┘
       │                   │                   │                   │
       │ CMBAgent(...)     │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ Parse parameters  │                   │
       │                   │──────────┐        │                   │
       │                   │          │        │                   │
       │                   │<─────────┘        │                   │
       │                   │                   │                   │
       │                   │ Setup work_dir    │                   │
       │                   │──────────┐        │                   │
       │                   │          │        │                   │
       │                   │<─────────┘        │                   │
       │                   │                   │                   │
       │                   │ Init database     │                   │
       │                   │──────────┐        │                   │
       │                   │          │        │                   │
       │                   │<─────────┘        │                   │
       │                   │                   │                   │
       │                   │ Build LLM config  │                   │
       │                   │──────────┐        │                   │
       │                   │          │        │                   │
       │                   │<─────────┘        │                   │
       │                   │                   │                   │
       │                   │ init_agents()     │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ Load YAML configs │
       │                   │                   │──────────┐        │
       │                   │                   │          │        │
       │                   │                   │<─────────┘        │
       │                   │                   │                   │
       │                   │ Agent instances   │                   │
       │                   │<──────────────────│                   │
       │                   │                   │                   │
       │                   │ check_assistants()│                   │
       │                   │────────────────────────────────────-->│
       │                   │                   │                   │
       │                   │                   │    List assistants│
       │                   │<────────────────────────────────────── │
       │                   │                   │                   │
       │                   │ push_vector_stores()                  │
       │                   │────────────────────────────────────-->│
       │                   │                   │                   │
       │                   │                   │  Create stores    │
       │                   │<────────────────────────────────────── │
       │                   │                   │                   │
       │                   │ Set agents (YAML) │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │ register_hand_offs│                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │ register_functions│                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │ CMBAgent ready    │                   │                   │
       │<──────────────────│                   │                   │
       │                   │                   │                   │
```

### Task Execution Sequence

```
┌──────────────┐    ┌─────────────┐    ┌───────────────┐    ┌─────────────┐
│    User      │    │  CMBAgent   │    │    Agents     │    │     LLM     │
└──────┬───────┘    └──────┬──────┘    └───────┬───────┘    └──────┬──────┘
       │                   │                   │                   │
       │ solve(task)       │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ Prepare context   │                   │
       │                   │──────────┐        │                   │
       │                   │          │        │                   │
       │                   │<─────────┘        │                   │
       │                   │                   │                   │
       │                   │ Create AutoPattern│                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │ initiate_group_chat                   │
       │                   │──────────────────────────────────────>│
       │                   │                   │                   │
       │                   │                   │ Agent 1 response  │
       │                   │                   │<──────────────────│
       │                   │                   │                   │
       │                   │                   │ Hand-off          │
       │                   │                   │──────────┐        │
       │                   │                   │          │        │
       │                   │                   │<─────────┘        │
       │                   │                   │                   │
       │                   │                   │ Agent 2 response  │
       │                   │                   │<──────────────────│
       │                   │                   │                   │
       │                   │                   │ ... (continues)   │
       │                   │                   │                   │
       │                   │                   │ terminator        │
       │                   │                   │<──────────────────│
       │                   │                   │                   │
       │                   │ final_context     │                   │
       │                   │<──────────────────│                   │
       │                   │                   │                   │
       │ Results           │                   │                   │
       │<──────────────────│                   │                   │
       │                   │                   │                   │
```

### WebSocket Flow (Frontend to Backend)

```
┌──────────────┐    ┌─────────────┐    ┌───────────────┐    ┌─────────────┐
│   Frontend   │    │   Backend   │    │   CMBAgent    │    │     LLM     │
└──────┬───────┘    └──────┬──────┘    └───────┬───────┘    └──────┬──────┘
       │                   │                   │                   │
       │ WS Connect        │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │ Send {task, cfg}  │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ execute_cmbagent  │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │ status: started   │                   │                   │
       │<──────────────────│                   │                   │
       │                   │                   │                   │
       │                   │                   │ LLM calls         │
       │                   │                   │──────────────────>│
       │                   │                   │                   │
       │ output: ...       │ callback: output  │                   │
       │<──────────────────│<──────────────────│                   │
       │                   │                   │                   │
       │ dag_created       │ callback: dag     │                   │
       │<──────────────────│<──────────────────│                   │
       │                   │                   │                   │
       │ step_started      │ callback: step    │                   │
       │<──────────────────│<──────────────────│                   │
       │                   │                   │                   │
       │                   │                   │ ... execution ... │
       │                   │                   │                   │
       │ cost_update       │ callback: cost    │                   │
       │<──────────────────│<──────────────────│                   │
       │                   │                   │                   │
       │ step_completed    │ callback: step    │                   │
       │<──────────────────│<──────────────────│                   │
       │                   │                   │                   │
       │ result: {...}     │ callback: result  │                   │
       │<──────────────────│<──────────────────│                   │
       │                   │                   │                   │
       │ complete          │                   │                   │
       │<──────────────────│                   │                   │
       │                   │                   │                   │
       │ WS Close          │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
```

---

## Quick Reference: Where Things Come From

| Item | Source | File |
|------|--------|------|
| Default models | `default_agents_llm_model` | `cmbagent/utils.py` |
| API keys | Environment variables | `OPENAI_API_KEY`, etc. |
| Agent instructions | YAML files | `agents/{name}/{name}.yaml` |
| Agent classes | Python files | `agents/{name}/{name}.py` |
| Hand-off logic | Registration | `cmbagent/hand_offs.py` |
| Functions | Registration | `cmbagent/functions/registration.py` |
| Shared context | Default + user | `cmbagent/context.py` |
| Work directory | `work_dir` param or `os.getcwd() + /cmbagent_workdir` | `cmbagent/utils.py` |
| Database URL | `DATABASE_URL` env | Environment |
| Vector store data | `CMBAGENT_DATA/data/{agent}/` | Environment |
| MCP config | YAML file | `cmbagent/mcp/client_config.yaml` |
| Frontend config | `lib/config.ts` | `cmbagent-ui/lib/config.ts` |
| Backend port | Uvicorn | Default 8000 |
| Frontend port | Next.js | Default 3000 |

---

*Documentation for CMBAgent Initialization and Flow*  
*Last updated: January 2026*
