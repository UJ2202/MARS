# CMBAgent Major Refactoring: Execution Roadmap

> **Strategic Plan for 3 Major Tasks**

---

## Task Overview

| # | Task | Complexity | Dependencies |
|---|------|------------|--------------|
| 1 | Config to UI | Medium | None (foundational) |
| 2 | Phase Architecture | High | Partial dependency on #1 |
| 3 | Copilot Phase | Medium | Hard dependency on #2 |

---

## Dependency Analysis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DEPENDENCY GRAPH                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────┐                                                      │
│   │  1. CONFIG TO UI │  ◄─── Start Here (no dependencies)                   │
│   │                  │                                                       │
│   │  • DB Schema     │                                                       │
│   │  • API Endpoints │                                                       │
│   │  • Config Service│                                                       │
│   │  • UI Components │                                                       │
│   └────────┬─────────┘                                                       │
│            │                                                                 │
│            │ provides: ConfigurationService, DB tables                       │
│            │                                                                 │
│            ▼                                                                 │
│   ┌──────────────────┐                                                      │
│   │  2. PHASES       │  ◄─── Uses config for phase settings                 │
│   │                  │                                                       │
│   │  • Phase Base    │                                                       │
│   │  • Phase Registry│                                                       │
│   │  • Workflow      │                                                       │
│   │    Composer      │                                                       │
│   │  • Migration     │                                                       │
│   └────────┬─────────┘                                                       │
│            │                                                                 │
│            │ provides: Phase infrastructure, WorkflowExecutor                │
│            │                                                                 │
│            ▼                                                                 │
│   ┌──────────────────┐                                                      │
│   │  3. COPILOT      │  ◄─── CopilotPhase extends Phase                     │
│   │                  │                                                       │
│   │  • Conversation  │                                                       │
│   │    Manager       │                                                       │
│   │  • Intent Router │                                                       │
│   │  • Streaming     │                                                       │
│   │  • CopilotPhase  │                                                       │
│   └──────────────────┘                                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Recommended Approach: Parallel Tracks

Instead of pure sequential execution, I recommend **parallel tracks with sync points**:

```
Week 1    Week 2    Week 3    Week 4    Week 5    Week 6    Week 7    Week 8
  │         │         │         │         │         │         │         │
  ▼         ▼         ▼         ▼         ▼         ▼         ▼         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TRACK A: CONFIG TO UI                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ [DB Schema]──[Config Service]──[API]──[UI Components]──[Integration]────────│
│     ▲              │                        │                                │
│     │              │                        │                                │
│   START            │                        ▼                                │
│                    │              ┌─────────────────┐                        │
│                    │              │ SYNC POINT 1    │                        │
│                    │              │ Config can load │                        │
│                    │              │ from DB         │                        │
│                    ▼              └─────────────────┘                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ TRACK B: PHASE ARCHITECTURE                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│           [Base Phase]──[Phases]──[Registry]──[Composer]──[Migration]────────│
│                 │            │                     │                         │
│                 │            │                     ▼                         │
│                 │            │           ┌─────────────────┐                 │
│                 │            │           │ SYNC POINT 2    │                 │
│                 │            │           │ Phases work with│                 │
│                 │            │           │ new config      │                 │
│                 │            ▼           └─────────────────┘                 │
│                 │   ┌────────────────┐                                       │
│                 │   │ CAN START HERE │                                       │
│                 │   │ Week 2 (in     │                                       │
│                 │   │ parallel)      │                                       │
│                 │   └────────────────┘                                       │
│                 ▼                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ TRACK C: COPILOT                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                              [Conversation]──[Router]──[Streaming]──[Phase]──│
│                                    │                          │              │
│                                    │                          ▼              │
│                           ┌────────────────┐        ┌─────────────────┐      │
│                           │ CAN START HERE │        │ SYNC POINT 3    │      │
│                           │ Week 3         │        │ Full integration│      │
│                           └────────────────┘        └─────────────────┘      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Execution Plan

### Phase 0: Preparation (2-3 days)

Before starting, set up the foundation:

```bash
# Create directory structure
mkdir -p cmbagent/phases
mkdir -p cmbagent/assistant
mkdir -p cmbagent/config/service
mkdir -p backend/routers/config
mkdir -p cmbagent-ui/components/config
mkdir -p cmbagent-ui/components/assistant
```

Create placeholder files to establish structure:

```
cmbagent/
├── phases/
│   ├── __init__.py
│   ├── base.py           # Phase, PhaseContext, PhaseResult
│   ├── registry.py       # PhaseRegistry
│   ├── planning.py       # PlanningPhase
│   ├── control.py        # ControlPhase
│   ├── one_shot.py       # OneShotPhase
│   └── hitl.py           # HITLCheckpointPhase
├── assistant/
│   ├── __init__.py
│   ├── conversation.py   # ConversationManager
│   ├── router.py         # IntentRouter
│   ├── streaming.py      # StreamingHandler
│   └── tools.py          # AssistantToolRegistry
├── config/
│   └── service/
│       ├── __init__.py
│       ├── config_service.py
│       ├── models.py     # Pydantic models
│       └── defaults.py   # Default values
```

---

### Track A: Config to UI

#### Week 1: Database & Service Layer

**Day 1-2: Database Schema**
```python
# Priority: Create these tables first
# 1. global_configs
# 2. agent_configs  
# 3. model_registry
# 4. credentials
```

**Day 3-4: Configuration Service**
```python
# cmbagent/config/service/config_service.py
class ConfigurationService:
    def get_effective_global_config(user_id=None) -> GlobalConfig
    def get_effective_agent_config(agent_name, user_id=None) -> AgentConfig
    def build_cmbagent_config(...) -> CMBAgentBuildConfig
```

**Day 5: YAML Migration Script**
```python
# scripts/migrate_yaml_to_db.py
# One-time migration from YAML files to database
```

#### Week 2: API Endpoints

**Day 1-2: Config API**
```python
# backend/routers/config/global_config.py
# backend/routers/config/agent_config.py
# backend/routers/config/credentials.py
```

**Day 3-4: Model Registry API**
```python
# backend/routers/config/models.py
# Populate with known models (OpenAI, Anthropic, etc.)
```

**Day 5: Integration Tests**
```python
# tests/test_config_api.py
```

#### Week 3: UI Components

**Day 1-2: Settings Page Layout**
```tsx
// cmbagent-ui/app/settings/page.tsx
// cmbagent-ui/components/config/SettingsTabs.tsx
```

**Day 3: Agent Config Modal**
```tsx
// cmbagent-ui/components/config/AgentConfigModal.tsx
// cmbagent-ui/components/config/ModelSelector.tsx
```

**Day 4-5: Credentials Manager**
```tsx
// cmbagent-ui/components/config/CredentialsManager.tsx
```

#### Week 4: CMBAgent Integration

**Day 1-2: Modify CMBAgent.__init__**
```python
# Add config_service parameter
# Load from DB instead of hardcoded defaults
```

**Day 3-5: Testing & Polish**
- End-to-end testing
- Fix edge cases
- Documentation

---

### Track B: Phase Architecture

#### Week 2: Core Phase Infrastructure (Parallel with Track A Week 2)

**Day 1-2: Base Classes**
```python
# cmbagent/phases/base.py
class Phase(ABC):
    async def execute(self, context: PhaseContext) -> PhaseResult

class PhaseContext:
    # Input/output data flowing between phases

class PhaseResult:
    # Result of phase execution
```

**Day 3: Phase Registry**
```python
# cmbagent/phases/registry.py
class PhaseRegistry:
    @classmethod
    def register(cls, phase_type: str)
    @classmethod
    def create(cls, phase_type: str, config: PhaseConfig) -> Phase
```

**Day 4-5: Extract PlanningPhase**
```python
# cmbagent/phases/planning.py
# Extract planning logic from planning_control.py
```

#### Week 3: More Phases & Composer

**Day 1-2: ControlPhase**
```python
# cmbagent/phases/control.py
# Extract control loop logic
```

**Day 3: OneShotPhase & HITLCheckpointPhase**
```python
# cmbagent/phases/one_shot.py
# cmbagent/phases/hitl.py
```

**Day 4-5: WorkflowComposer**
```python
# cmbagent/workflows/composer.py
class WorkflowDefinition:
    phases: List[Dict]

class WorkflowExecutor:
    async def run() -> WorkflowContext
```

#### Week 4: Database & Migration

**Day 1-2: Phase DB Tables**
```sql
-- phase_definitions
-- workflow_definitions  
-- phase_executions
```

**Day 3-4: Migration**
```python
# Keep old workflow functions as thin wrappers
# Route to new phase-based execution
```

**Day 5: Testing**

---

### Track C: Copilot Phase

#### Week 3: Core Components (Parallel with Track B Week 3)

**Day 1-2: ConversationManager**
```python
# cmbagent/assistant/conversation.py
class ConversationManager:
    async def chat(message: str) -> AsyncIterator[str]
```

**Day 3: IntentRouter**
```python
# cmbagent/assistant/router.py
class IntentRouter:
    async def classify(message: str) -> ClassifiedIntent
```

**Day 4-5: AssistantToolRegistry**
```python
# cmbagent/assistant/tools.py
# Wrap existing tools for assistant use
```

#### Week 4: Streaming & Integration

**Day 1-2: StreamingHandler**
```python
# cmbagent/assistant/streaming.py
class StreamingResponseHandler:
    async def stream_llm_response(...)
    async def stream_tool_call(...)
```

**Day 3: CopilotPhase**
```python
# cmbagent/phases/copilot.py
class CopilotPhase(Phase):
    async def execute(context) -> PhaseResult
```

**Day 4-5: WebSocket Token Streaming**
```python
# Modify backend/websocket_manager.py
# Add token-level streaming
```

#### Week 5: UI & Polish

**Day 1-3: Chat UI**
```tsx
// cmbagent-ui/components/assistant/ChatInput.tsx
// cmbagent-ui/components/assistant/MessageStream.tsx
// cmbagent-ui/components/assistant/ToolCallDisplay.tsx
```

**Day 4-5: Integration Testing**

---

## Milestone Checkpoints

### Checkpoint 1 (End of Week 2)
- [ ] Config can be loaded from database
- [ ] Phase base classes implemented
- [ ] At least one phase (Planning) extracted

### Checkpoint 2 (End of Week 4)
- [ ] UI can configure agents and credentials
- [ ] All phases extracted and working
- [ ] WorkflowComposer can run phase sequences
- [ ] ConversationManager working standalone

### Checkpoint 3 (End of Week 6)
- [ ] CMBAgent uses ConfigurationService
- [ ] Old workflows wrapped with new phase system
- [ ] CopilotPhase integrated with phase system
- [ ] Token streaming working

### Checkpoint 4 (End of Week 8)
- [ ] Full UI for all configurations
- [ ] Workflow composer UI (optional)
- [ ] Chat UI for Copilot
- [ ] All documentation updated

---

## Risk Mitigation

### Risk 1: Breaking Existing Functionality
**Mitigation:**
- Keep old functions as wrappers during transition
- Comprehensive test coverage before migration
- Feature flags for new vs old code paths

```python
# Example: Wrapper pattern
def planning_and_control_context_carryover(...):
    """Legacy function - wraps new phase system."""
    if USE_NEW_PHASES:
        return _run_with_phases(...)
    else:
        return _legacy_implementation(...)
```

### Risk 2: Scope Creep
**Mitigation:**
- Strict MVP for each component
- Cut features, not quality
- Weekly scope reviews

### Risk 3: Integration Issues
**Mitigation:**
- Integration tests at each sync point
- Continuous integration pipeline
- Daily builds

---

## Recommended Starting Order

### Week 1 (Parallel Start)

**You working on:**
1. **Morning**: Database schema for configs (Track A)
2. **Afternoon**: Phase base classes (Track B)

This gives you:
- Foundation for both tracks
- Early validation of architecture
- Unblocks rest of work

### Week 2

**Track A**: Config Service + API
**Track B**: Extract PlanningPhase + Registry

### Week 3

**Track A**: UI Components start
**Track B**: ControlPhase + OneShotPhase
**Track C**: ConversationManager (can start!)

### Week 4+

Full parallel execution with sync points.

---

## Quick Wins (Start Today)

### 1. Create Directory Structure
```bash
mkdir -p cmbagent/{phases,assistant,config/service}
touch cmbagent/phases/{__init__,base,registry}.py
touch cmbagent/assistant/{__init__,conversation,router}.py
touch cmbagent/config/service/{__init__,config_service}.py
```

### 2. Stub Out Phase Base
```python
# cmbagent/phases/base.py - minimal version
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class PhaseContext:
    task: str
    work_dir: str
    shared_state: Dict[str, Any]

@dataclass  
class PhaseResult:
    success: bool
    context: PhaseContext
    error: str = None

class Phase(ABC):
    @abstractmethod
    async def execute(self, context: PhaseContext) -> PhaseResult:
        pass
```

### 3. Create Config Tables
```sql
-- Run this today to have tables ready
CREATE TABLE global_configs (...);
CREATE TABLE agent_configs (...);
```

---

## Summary

| Priority | Task | Start | Duration | Blocks |
|----------|------|-------|----------|--------|
| 1 | Config DB + Service | Week 1 | 2 weeks | Nothing |
| 2 | Phase Base + Registry | Week 1 | 1 week | Nothing |
| 3 | Extract Phases | Week 2 | 2 weeks | Phase Base |
| 4 | Config UI | Week 3 | 2 weeks | Config API |
| 5 | Conversation Manager | Week 3 | 1 week | Nothing |
| 6 | CopilotPhase | Week 4 | 1 week | Phases |
| 7 | Integration | Week 5-6 | 2 weeks | All above |
| 8 | Polish & Docs | Week 7-8 | 2 weeks | Integration |

**Total: ~8 weeks** for all three major tasks working in parallel.

**If you want to go faster**: Focus only on phases first (4 weeks), then add config and copilot incrementally.

---

## My Recommendation

**Start with Track B (Phases) as the backbone:**

1. Phases give you the architecture for everything else
2. Config can be added to phases later
3. Copilot is just another phase once infrastructure exists

**Minimal viable sequence:**
```
Week 1-2: Phase infrastructure
Week 3-4: Extract all phases + Composer  
Week 5-6: Add CopilotPhase
Week 7-8: Config to UI (enhances existing)
```

This gives you working software sooner and lets you iterate on config UI with a stable phase system underneath.

---

*Execution Roadmap v1.0*  
*January 2026*
