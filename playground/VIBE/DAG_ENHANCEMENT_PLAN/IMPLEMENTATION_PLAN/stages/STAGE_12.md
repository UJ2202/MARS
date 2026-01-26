# Stage 12: Enhanced Agent Registry

**Phase:** 4 - Advanced Features
**Estimated Time:** 40-50 minutes
**Dependencies:** Stages 1-11 complete
**Risk Level:** Medium

## Objectives

1. Implement plugin system for dynamic agent registration
2. Add hot-reload capability for agent development
3. Create simplified agent API for easier agent creation
4. Build agent marketplace infrastructure
5. Add agent versioning and dependency management
6. Implement agent discovery and search
7. Create agent templates and scaffolding tools

## Current State Analysis

### What We Have
- 50+ hardcoded agents in `cmbagent/agents/` directory
- Each agent has `.py` and `.yaml` configuration
- Static imports in `hand_offs.py`
- Manual agent registration
- No versioning or dependency management
- Difficult to add new agents without code changes

### What We Need
- Dynamic agent loading from plugins
- Hot-reload during development
- Simple agent API (decorators, minimal boilerplate)
- Agent registry with metadata
- Version management
- Marketplace-ready infrastructure
- Agent discovery and search

## Pre-Stage Verification

### Check Prerequisites
1. Stages 1-11 complete and verified
2. Database schema includes agent metadata tables
3. MCP integration operational
4. Current agent system documented

### Expected State
- All existing agents working
- Agent hand-offs functioning
- Ready to add registry layer
- Tests passing

## Implementation Tasks

### Task 1: Design Plugin System Architecture
**Objective:** Define plugin loading and registration mechanism

**Actions:**
- Research Python plugin patterns (entry points, importlib)
- Design plugin structure and conventions
- Define plugin manifest format
- Plan hot-reload mechanism

**Design Decisions:**

**Plugin Directory Structure:**
```
plugins/
├── my_agent/
│   ├── manifest.yaml          # Plugin metadata
│   ├── agent.py               # Agent implementation
│   ├── config.yaml            # Agent configuration
│   ├── requirements.txt       # Dependencies
│   ├── README.md              # Documentation
│   └── tests/                 # Tests
│       └── test_agent.py
```

**Manifest Format:**
```yaml
name: my_custom_agent
version: 1.0.0
author: Research Team
description: Custom agent for specific analysis
agent_type: researcher
entry_point: agent:MyCustomAgent
dependencies:
  - numpy>=1.24
  - scipy>=1.10
cmbagent_version: ">=0.2.0"
api_version: "1.0"
tags: [cosmology, data-analysis, research]
capabilities:
  - file_operations
  - plotting
  - llm_calls
resources:
  max_memory_mb: 2048
  max_disk_mb: 5000
```

**Verification:**
- Plugin structure documented
- Manifest schema defined
- Entry point mechanism chosen
- Hot-reload strategy planned

### Task 2: Create Agent Registry Database Schema
**Objective:** Add tables for agent metadata and versions

**Database Models:**

**agents_registry table:**
- id (UUID, primary key)
- name (VARCHAR 255, unique)
- display_name (VARCHAR 255)
- description (TEXT)
- agent_type (VARCHAR 100: researcher, engineer, planner, custom)
- status (VARCHAR 50: active, deprecated, experimental)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
- metadata (JSONB)

**agent_versions table:**
- id (UUID, primary key)
- agent_id (UUID, foreign key)
- version (VARCHAR 50)
- entry_point (VARCHAR 500)
- plugin_path (VARCHAR 1000)
- dependencies (JSONB)
- is_active (BOOLEAN)
- is_default (BOOLEAN)
- created_at (TIMESTAMP)
- metadata (JSONB)

**agent_tags table:**
- id (SERIAL, primary key)
- agent_id (UUID, foreign key)
- tag (VARCHAR 100)

**agent_capabilities table:**
- id (SERIAL, primary key)
- agent_id (UUID, foreign key)
- capability (VARCHAR 100)
- enabled (BOOLEAN)

**agent_usage_stats table:**
- id (SERIAL, primary key)
- agent_id (UUID, foreign key)
- version_id (UUID, foreign key)
- session_id (UUID, foreign key)
- run_id (UUID, foreign key)
- invocation_count (INTEGER)
- total_cost_usd (NUMERIC(10, 6))
- total_tokens (INTEGER)
- avg_response_time_ms (INTEGER)
- last_used_at (TIMESTAMP)

**Files to Create:**
- `cmbagent/database/migrations/versions/012_agent_registry.py`
- Add models to `cmbagent/database/models.py`

**Verification:**
- Migration runs successfully
- Tables created with correct schema
- Indexes on name, version, tags
- Can query agent metadata

### Task 3: Implement Agent Registry Core
**Objective:** Build registry for agent discovery and loading

**Implementation:**

```python
# cmbagent/registry/agent_registry.py
from typing import Dict, List, Optional, Type
import importlib.util
import yaml
from pathlib import Path
from dataclasses import dataclass

@dataclass
class AgentMetadata:
    name: str
    version: str
    display_name: str
    description: str
    agent_type: str
    author: str
    entry_point: str
    plugin_path: Path
    dependencies: List[str]
    tags: List[str]
    capabilities: List[str]
    resources: Dict[str, int]
    api_version: str

class AgentRegistry:
    """Central registry for all agents (built-in and plugins)."""

    def __init__(self, db_session):
        self.db = db_session
        self._agents: Dict[str, AgentMetadata] = {}
        self._loaded_instances: Dict[str, object] = {}
        self._plugin_directories: List[Path] = []

    def register_plugin_directory(self, path: Path):
        """Register directory to scan for plugins."""
        self._plugin_directories.append(path)

    def discover_plugins(self) -> List[AgentMetadata]:
        """Scan plugin directories and discover agents."""
        discovered = []

        for plugin_dir in self._plugin_directories:
            if not plugin_dir.exists():
                continue

            for agent_path in plugin_dir.iterdir():
                if not agent_path.is_dir():
                    continue

                manifest_path = agent_path / "manifest.yaml"
                if not manifest_path.exists():
                    continue

                try:
                    metadata = self._load_manifest(manifest_path, agent_path)
                    discovered.append(metadata)
                except Exception as e:
                    logger.error(f"Failed to load plugin {agent_path}: {e}")

        return discovered

    def _load_manifest(self, manifest_path: Path, plugin_path: Path) -> AgentMetadata:
        """Load and validate plugin manifest."""
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)

        # Validate required fields
        required = ["name", "version", "entry_point"]
        for field in required:
            if field not in manifest:
                raise ValueError(f"Missing required field: {field}")

        return AgentMetadata(
            name=manifest["name"],
            version=manifest["version"],
            display_name=manifest.get("display_name", manifest["name"]),
            description=manifest.get("description", ""),
            agent_type=manifest.get("agent_type", "custom"),
            author=manifest.get("author", "Unknown"),
            entry_point=manifest["entry_point"],
            plugin_path=plugin_path,
            dependencies=manifest.get("dependencies", []),
            tags=manifest.get("tags", []),
            capabilities=manifest.get("capabilities", []),
            resources=manifest.get("resources", {}),
            api_version=manifest.get("api_version", "1.0")
        )

    def register_agent(self, metadata: AgentMetadata):
        """Register agent in registry and database."""
        # Register in memory
        self._agents[metadata.name] = metadata

        # Register in database
        from cmbagent.database.models import AgentsRegistry, AgentVersions

        agent = self.db.query(AgentsRegistry).filter(
            AgentsRegistry.name == metadata.name
        ).first()

        if not agent:
            agent = AgentsRegistry(
                name=metadata.name,
                display_name=metadata.display_name,
                description=metadata.description,
                agent_type=metadata.agent_type,
                status="active"
            )
            self.db.add(agent)
            self.db.flush()

        # Add version
        version = AgentVersions(
            agent_id=agent.id,
            version=metadata.version,
            entry_point=metadata.entry_point,
            plugin_path=str(metadata.plugin_path),
            dependencies=metadata.dependencies,
            is_active=True,
            is_default=True
        )
        self.db.add(version)

        # Add tags
        for tag in metadata.tags:
            self._add_tag(agent.id, tag)

        # Add capabilities
        for cap in metadata.capabilities:
            self._add_capability(agent.id, cap)

        self.db.commit()

    def load_agent(self, name: str, version: Optional[str] = None) -> object:
        """Load and instantiate agent."""
        # Check if already loaded
        cache_key = f"{name}:{version or 'default'}"
        if cache_key in self._loaded_instances:
            return self._loaded_instances[cache_key]

        # Get metadata
        metadata = self._agents.get(name)
        if not metadata:
            raise ValueError(f"Agent not found: {name}")

        # Load module
        agent_module_path = metadata.plugin_path / "agent.py"
        spec = importlib.util.spec_from_file_location(
            f"plugin_{name}",
            agent_module_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get agent class from entry point
        module_name, class_name = metadata.entry_point.split(":")
        agent_class = getattr(module, class_name)

        # Instantiate agent
        agent_instance = agent_class()

        # Cache instance
        self._loaded_instances[cache_key] = agent_instance

        return agent_instance

    def search_agents(
        self,
        query: Optional[str] = None,
        agent_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        capabilities: Optional[List[str]] = None
    ) -> List[AgentMetadata]:
        """Search agents by criteria."""
        results = list(self._agents.values())

        if query:
            results = [
                a for a in results
                if query.lower() in a.name.lower() or
                   query.lower() in a.description.lower()
            ]

        if agent_type:
            results = [a for a in results if a.agent_type == agent_type]

        if tags:
            results = [
                a for a in results
                if any(tag in a.tags for tag in tags)
            ]

        if capabilities:
            results = [
                a for a in results
                if all(cap in a.capabilities for cap in capabilities)
            ]

        return results

    def list_agents(self) -> List[AgentMetadata]:
        """List all registered agents."""
        return list(self._agents.values())

    def get_agent_metadata(self, name: str) -> Optional[AgentMetadata]:
        """Get metadata for specific agent."""
        return self._agents.get(name)

    def unregister_agent(self, name: str):
        """Unregister agent from registry."""
        if name in self._agents:
            del self._agents[name]

        # Remove from cache
        cache_keys = [k for k in self._loaded_instances.keys() if k.startswith(f"{name}:")]
        for key in cache_keys:
            del self._loaded_instances[key]

        # Update database status
        from cmbagent.database.models import AgentsRegistry
        agent = self.db.query(AgentsRegistry).filter(
            AgentsRegistry.name == name
        ).first()

        if agent:
            agent.status = "deprecated"
            self.db.commit()
```

**Files to Create:**
- `cmbagent/registry/__init__.py`
- `cmbagent/registry/agent_registry.py`
- `cmbagent/registry/exceptions.py`

**Verification:**
- Can discover plugins
- Can register agents
- Can load agent instances
- Search functionality works
- Database records created correctly

### Task 4: Implement Hot-Reload System
**Objective:** Enable agent code changes without restart

**Implementation:**

```python
# cmbagent/registry/hot_reload.py
import os
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class AgentReloadHandler(FileSystemEventHandler):
    """Watch agent files and trigger reload on changes."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self._last_reload = {}
        self._debounce_seconds = 1.0

    def on_modified(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only reload for Python files in plugin directories
        if file_path.suffix != ".py":
            return

        # Debounce: prevent multiple reloads for same file
        now = time.time()
        last = self._last_reload.get(file_path, 0)
        if now - last < self._debounce_seconds:
            return

        self._last_reload[file_path] = now

        # Find agent name from path
        agent_name = self._get_agent_name_from_path(file_path)
        if not agent_name:
            return

        logger.info(f"Hot-reloading agent: {agent_name}")

        try:
            # Unregister old version
            self.registry.unregister_agent(agent_name)

            # Re-discover and register
            plugin_dir = file_path.parent
            manifest_path = plugin_dir / "manifest.yaml"
            metadata = self.registry._load_manifest(manifest_path, plugin_dir)
            self.registry.register_agent(metadata)

            logger.info(f"Successfully reloaded: {agent_name}")

        except Exception as e:
            logger.error(f"Failed to reload {agent_name}: {e}")

    def _get_agent_name_from_path(self, file_path: Path) -> Optional[str]:
        """Extract agent name from file path."""
        # Assume path like: plugins/my_agent/agent.py
        for plugin_dir in self.registry._plugin_directories:
            if plugin_dir in file_path.parents:
                relative = file_path.relative_to(plugin_dir)
                return relative.parts[0] if relative.parts else None
        return None

class HotReloadManager:
    """Manage hot-reload watchers for agent plugins."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.observer = Observer()
        self.handler = AgentReloadHandler(registry)
        self._watching = False

    def start(self):
        """Start watching plugin directories."""
        if self._watching:
            return

        for plugin_dir in self.registry._plugin_directories:
            if plugin_dir.exists():
                self.observer.schedule(
                    self.handler,
                    str(plugin_dir),
                    recursive=True
                )
                logger.info(f"Hot-reload enabled for: {plugin_dir}")

        self.observer.start()
        self._watching = True

    def stop(self):
        """Stop watching."""
        if self._watching:
            self.observer.stop()
            self.observer.join()
            self._watching = False
```

**Files to Create:**
- `cmbagent/registry/hot_reload.py`

**Dependencies:**
- Add `watchdog>=3.0` to `pyproject.toml`

**Verification:**
- File changes detected
- Agent reloaded successfully
- No memory leaks from multiple reloads
- Works with multiple plugin directories

### Task 5: Create Simplified Agent API
**Objective:** Make agent creation easier with decorators and helpers

**Implementation:**

```python
# cmbagent/registry/simple_agent.py
from typing import Callable, Optional, List, Dict, Any
from functools import wraps
import inspect

class SimpleAgent:
    """Simplified agent API for quick agent creation."""

    def __init__(
        self,
        name: str,
        description: str = "",
        agent_type: str = "custom",
        model: str = "gpt-4o"
    ):
        self.name = name
        self.description = description
        self.agent_type = agent_type
        self.model = model
        self._tools = {}
        self._system_message = ""

    def tool(self, func: Callable) -> Callable:
        """Decorator to register tool function."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Register tool
        self._tools[func.__name__] = {
            "function": func,
            "description": func.__doc__ or "",
            "signature": inspect.signature(func)
        }

        return wrapper

    def system_message(self, message: str):
        """Set system message for agent."""
        self._system_message = message
        return self

    def build(self):
        """Build AG2 agent from configuration."""
        from ag2 import ConversableAgent

        # Create agent
        agent = ConversableAgent(
            name=self.name,
            system_message=self._system_message or self.description,
            llm_config={
                "model": self.model,
                "temperature": 0.7
            }
        )

        # Register tools
        for tool_name, tool_info in self._tools.items():
            agent.register_for_llm(
                name=tool_name,
                description=tool_info["description"]
            )(tool_info["function"])

        return agent

# Convenience decorator
def agent(
    name: str,
    description: str = "",
    agent_type: str = "custom",
    model: str = "gpt-4o"
):
    """Decorator for creating simple agents."""
    def decorator(cls):
        # Store metadata
        cls._agent_metadata = {
            "name": name,
            "description": description,
            "agent_type": agent_type,
            "model": model
        }
        return cls
    return decorator

# Example usage in plugin:
"""
from cmbagent.registry import SimpleAgent

my_agent = SimpleAgent(
    name="data_processor",
    description="Process scientific data",
    agent_type="researcher"
)

@my_agent.tool
def load_data(file_path: str) -> dict:
    '''Load data from file.'''
    import pandas as pd
    return pd.read_csv(file_path).to_dict()

@my_agent.tool
def analyze_data(data: dict) -> dict:
    '''Analyze data and return statistics.'''
    # Analysis logic
    return {"mean": ..., "std": ...}

# Build the agent
agent_instance = my_agent.system_message(
    "You are a data processing expert."
).build()
"""
```

**Files to Create:**
- `cmbagent/registry/simple_agent.py`
- `cmbagent/registry/templates/` (agent templates)

**Verification:**
- SimpleAgent API works
- Tools registered correctly
- Built agents function properly
- Decorator syntax clean and intuitive

### Task 6: Implement Agent Scaffolding Tool
**Objective:** CLI tool to generate agent boilerplate

**Implementation:**

```python
# cmbagent/registry/scaffold.py
import click
from pathlib import Path
import yaml

@click.command()
@click.argument("agent_name")
@click.option("--type", default="custom", help="Agent type")
@click.option("--description", default="", help="Agent description")
@click.option("--author", default="", help="Author name")
@click.option("--output-dir", default="plugins", help="Output directory")
def scaffold_agent(agent_name, type, description, author, output_dir):
    """Generate agent plugin boilerplate."""

    output_path = Path(output_dir) / agent_name
    output_path.mkdir(parents=True, exist_ok=True)

    # Create manifest.yaml
    manifest = {
        "name": agent_name,
        "version": "0.1.0",
        "author": author,
        "description": description,
        "agent_type": type,
        "entry_point": "agent:CustomAgent",
        "dependencies": [],
        "api_version": "1.0",
        "tags": [],
        "capabilities": ["file_operations", "llm_calls"]
    }

    with open(output_path / "manifest.yaml", "w") as f:
        yaml.dump(manifest, f)

    # Create agent.py from template
    agent_code = f'''"""
{agent_name} - {description}
"""
from cmbagent.registry import SimpleAgent

agent = SimpleAgent(
    name="{agent_name}",
    description="{description}",
    agent_type="{type}"
)

@agent.tool
def example_tool(input_data: str) -> str:
    """Example tool function."""
    # Implement your tool logic here
    return f"Processed: {{input_data}}"

class CustomAgent:
    """Main agent class."""

    def __init__(self):
        self.agent = agent.system_message(
            f"You are a {{description}} agent."
        ).build()

    def run(self, task: str) -> str:
        """Execute agent task."""
        return self.agent.generate_reply(
            messages=[{{"role": "user", "content": task}}]
        )
'''

    with open(output_path / "agent.py", "w") as f:
        f.write(agent_code)

    # Create README.md
    readme = f"""# {agent_name}

{description}

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```python
from cmbagent.registry import AgentRegistry

registry = AgentRegistry(db_session)
agent = registry.load_agent("{agent_name}")
result = agent.run("Your task here")
```

## Development

Edit `agent.py` to implement your agent logic.
Hot-reload is enabled in development mode.
"""

    with open(output_path / "README.md", "w") as f:
        f.write(readme)

    # Create requirements.txt
    with open(output_path / "requirements.txt", "w") as f:
        f.write("# Add your dependencies here\n")

    # Create tests/test_agent.py
    (output_path / "tests").mkdir(exist_ok=True)
    test_code = f"""import pytest
from agent import CustomAgent

def test_agent_initialization():
    agent = CustomAgent()
    assert agent is not None

def test_example_tool():
    agent = CustomAgent()
    result = agent.run("Test task")
    assert result is not None
"""

    with open(output_path / "tests" / "test_agent.py", "w") as f:
        f.write(test_code)

    click.echo(f"Created agent plugin: {output_path}")
    click.echo(f"Next steps:")
    click.echo(f"  1. cd {output_path}")
    click.echo(f"  2. Edit agent.py to implement your agent")
    click.echo(f"  3. Add dependencies to requirements.txt")
    click.echo(f"  4. Test with: pytest tests/")
```

**Add to CLI:**
- Integrate into `cmbagent/cli.py`
- Add `cmbagent scaffold <agent_name>` command

**Files to Create:**
- `cmbagent/registry/scaffold.py`
- Update `cmbagent/cli.py`

**Verification:**
- Scaffold command generates correct structure
- Generated agent is valid and loadable
- Tests run successfully
- Documentation clear

### Task 7: Create Agent Marketplace Infrastructure
**Objective:** Infrastructure for sharing and discovering agents

**Implementation:**

**API Endpoints:**
```python
# backend/api/marketplace.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

@router.get("/agents")
async def list_agents(
    query: Optional[str] = None,
    agent_type: Optional[str] = None,
    tags: Optional[str] = None,  # Comma-separated
    page: int = 1,
    page_size: int = 20
):
    """List available agents with search and filters."""
    registry = get_agent_registry()

    tag_list = tags.split(",") if tags else None
    agents = registry.search_agents(
        query=query,
        agent_type=agent_type,
        tags=tag_list
    )

    # Pagination
    start = (page - 1) * page_size
    end = start + page_size
    paginated = agents[start:end]

    return {
        "total": len(agents),
        "page": page,
        "page_size": page_size,
        "agents": [
            {
                "name": a.name,
                "display_name": a.display_name,
                "description": a.description,
                "agent_type": a.agent_type,
                "version": a.version,
                "author": a.author,
                "tags": a.tags,
                "capabilities": a.capabilities
            }
            for a in paginated
        ]
    }

@router.get("/agents/{agent_name}")
async def get_agent_details(agent_name: str):
    """Get detailed information about an agent."""
    registry = get_agent_registry()
    metadata = registry.get_agent_metadata(agent_name)

    if not metadata:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get usage statistics
    stats = get_agent_usage_stats(agent_name)

    return {
        "metadata": metadata.__dict__,
        "usage_stats": stats
    }

@router.post("/agents/{agent_name}/install")
async def install_agent(agent_name: str, version: Optional[str] = None):
    """Install agent from marketplace."""
    # This would download from marketplace registry
    # For now, just verify agent exists
    registry = get_agent_registry()

    try:
        agent = registry.load_agent(agent_name, version)
        return {"status": "installed", "agent": agent_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Files to Create:**
- `backend/api/marketplace.py`
- `cmbagent-ui/src/components/AgentMarketplace.tsx`
- `cmbagent-ui/src/components/AgentCard.tsx`

**Verification:**
- API endpoints work
- Can search and filter agents
- Agent details displayed correctly
- Install mechanism functional

### Task 8: Migrate Built-in Agents to Registry
**Objective:** Register all existing 50+ agents in registry

**Implementation:**

```python
# cmbagent/registry/builtin.py
def register_builtin_agents(registry: AgentRegistry):
    """Register all built-in CMBAgent agents."""

    builtin_agents = [
        {
            "name": "engineer",
            "display_name": "Engineer Agent",
            "description": "Code generation and engineering tasks",
            "agent_type": "engineer",
            "entry_point": "cmbagent.agents.engineer.engineer:EngineerAgent",
            "version": "1.0.0",
            "tags": ["coding", "engineering", "execution"],
            "capabilities": ["code_generation", "file_operations", "testing"]
        },
        {
            "name": "researcher",
            "display_name": "Researcher Agent",
            "description": "Research and analysis tasks",
            "agent_type": "researcher",
            "entry_point": "cmbagent.agents.researcher.researcher:ResearcherAgent",
            "version": "1.0.0",
            "tags": ["research", "analysis", "literature"],
            "capabilities": ["literature_search", "data_analysis", "reporting"]
        },
        # ... register all 50+ agents
    ]

    for agent_info in builtin_agents:
        metadata = AgentMetadata(
            name=agent_info["name"],
            version=agent_info["version"],
            display_name=agent_info["display_name"],
            description=agent_info["description"],
            agent_type=agent_info["agent_type"],
            author="CMBAgent Core Team",
            entry_point=agent_info["entry_point"],
            plugin_path=Path("cmbagent/agents") / agent_info["name"],
            dependencies=[],
            tags=agent_info["tags"],
            capabilities=agent_info["capabilities"],
            resources={},
            api_version="1.0"
        )

        registry.register_agent(metadata)
```

**Files to Create:**
- `cmbagent/registry/builtin.py`

**Verification:**
- All built-in agents registered
- Can load agents through registry
- Backward compatibility maintained
- Hand-offs still work

## Files to Create (Summary)

### New Files
```
cmbagent/registry/
├── __init__.py
├── agent_registry.py
├── hot_reload.py
├── simple_agent.py
├── scaffold.py
├── builtin.py
├── exceptions.py
└── templates/
    └── basic_agent/
        ├── manifest.yaml.template
        ├── agent.py.template
        └── README.md.template

backend/api/
└── marketplace.py

cmbagent-ui/src/components/
├── AgentMarketplace.tsx
└── AgentCard.tsx
```

### Modified Files
- `cmbagent/database/models.py` - Add registry models
- `cmbagent/database/migrations/versions/012_agent_registry.py` - Migration
- `cmbagent/cli.py` - Add scaffold command
- `cmbagent/cmbagent.py` - Use registry for agent loading
- `pyproject.toml` - Add watchdog dependency

## Verification Criteria

### Must Pass
- [ ] Agent registry database tables created
- [ ] Plugin discovery works for multiple directories
- [ ] Agents can be registered and loaded dynamically
- [ ] Hot-reload triggers on file changes
- [ ] SimpleAgent API creates functional agents
- [ ] Scaffold command generates valid agent structure
- [ ] All built-in agents registered in registry
- [ ] Existing workflows still work
- [ ] Agent search and filtering functional

### Should Pass
- [ ] Marketplace API endpoints operational
- [ ] Agent versioning tracked correctly
- [ ] Usage statistics recorded
- [ ] No memory leaks from hot-reload
- [ ] Plugin dependencies validated
- [ ] Agent capabilities enforced

### Nice to Have
- [ ] UI for agent marketplace
- [ ] Agent ratings and reviews
- [ ] Automated testing for plugins
- [ ] Agent dependency resolution

## Testing Checklist

### Unit Tests
```python
def test_agent_registry_discovery():
    registry = AgentRegistry(db_session)
    registry.register_plugin_directory(Path("test_plugins"))
    agents = registry.discover_plugins()
    assert len(agents) > 0

def test_agent_loading():
    registry = AgentRegistry(db_session)
    agent = registry.load_agent("test_agent")
    assert agent is not None

def test_hot_reload():
    # Modify agent file
    # Verify registry detects change
    # Verify agent reloaded

def test_simple_agent_api():
    agent = SimpleAgent("test", "Test agent")

    @agent.tool
    def test_tool(x: int) -> int:
        return x * 2

    built = agent.build()
    assert built is not None

def test_agent_search():
    results = registry.search_agents(
        query="research",
        tags=["cosmology"]
    )
    assert len(results) > 0
```

### Integration Tests
```python
def test_plugin_to_execution():
    # Create plugin
    scaffold_agent("test_agent", output_dir="test_plugins")

    # Register plugin
    registry.discover_plugins()

    # Load and execute
    agent = registry.load_agent("test_agent")
    result = agent.run("test task")

    assert result is not None
```

## Common Issues and Solutions

### Issue 1: Plugin Import Errors
**Symptom:** Cannot import plugin module
**Solution:** Verify plugin path, check Python path, ensure __init__.py present

### Issue 2: Hot-Reload Not Triggering
**Symptom:** File changes not detected
**Solution:** Check watchdog installed, verify file system events, check debounce timing

### Issue 3: Agent Conflicts
**Symptom:** Multiple agents with same name
**Solution:** Implement versioning, namespace plugins, add conflict detection

### Issue 4: Missing Dependencies
**Symptom:** Plugin fails to load due to missing packages
**Solution:** Validate requirements.txt, install dependencies, add dependency checking

### Issue 5: Memory Leaks from Reload
**Symptom:** Memory usage grows with reloads
**Solution:** Properly unload modules, clear caches, use weak references

## Rollback Procedure

If registry system causes issues:

1. **Disable dynamic loading:**
   ```python
   USE_AGENT_REGISTRY = os.getenv("CMBAGENT_USE_REGISTRY", "false") == "true"
   ```

2. **Revert to static imports:**
   ```bash
   git checkout cmbagent/cmbagent.py cmbagent/hand_offs.py
   ```

3. **Keep database tables** - May be useful for future attempt

4. **Document issues** - Note specific problems encountered

## Post-Stage Actions

### Documentation
- Document plugin development guide
- Create agent marketplace documentation
- Add examples for SimpleAgent API
- Update architecture documentation

### Update Progress
- Mark Stage 12 complete in PROGRESS.md
- Note any deviations from plan
- Document time spent

### Prepare for Stage 13
- Agent registry operational
- Plugin system working
- Ready to add enhanced cost tracking
- Stage 13 can proceed

## Success Criteria

Stage 12 is complete when:
1. Agent registry fully functional
2. Plugin system discovers and loads agents
3. Hot-reload works without issues
4. SimpleAgent API enables easy agent creation
5. Scaffold tool generates valid agents
6. Built-in agents registered and working
7. Marketplace infrastructure operational
8. All tests passing
9. Verification checklist 100% complete

## Estimated Time Breakdown

- Architecture design: 5 min
- Database schema and models: 8 min
- Agent registry core implementation: 12 min
- Hot-reload system: 8 min
- SimpleAgent API: 7 min
- Scaffolding tool: 5 min
- Marketplace infrastructure: 8 min
- Built-in agent migration: 5 min
- Testing and verification: 10 min
- Documentation: 5 min

**Total: 40-50 minutes**

## Next Stage

Once Stage 12 is verified complete, proceed to:
**Stage 13: Enhanced Cost Tracking and Session Management**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
