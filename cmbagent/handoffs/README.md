# Handoffs Module

Modular handoff configuration system for CMBAgent multi-agent workflows.

## Overview

This module provides a clean, organized way to configure agent-to-agent transitions (handoffs) in the CMBAgent system. Each file handles a specific concern, making the code easier to understand, maintain, and extend.

## Module Structure

```
handoffs/
├── __init__.py              Main API entry point
├── agent_retrieval.py       Retrieve agent instances
├── planning_chain.py        Planning workflow handoffs
├── execution_chain.py       Execution workflow handoffs
├── rag_agents.py            RAG agent handoffs
├── context_agents.py        Context agent handoffs (CAMB, CLASS)
├── utility_agents.py        Utility agent handoffs
├── nested_chats.py          Nested conversation setup
├── message_limiting.py      Message history limiting
├── mode_specific.py         Mode-specific handoffs
├── hitl.py                  HITL handoff configurations
└── debug.py                 Debug utilities
```

## Quick Start

### Basic Usage

```python
from cmbagent.handoffs import register_all_hand_offs

# Standard handoffs (no HITL)
register_all_hand_offs(cmbagent_instance)
```

### With HITL (Human-in-the-Loop)

```python
# Mandatory human checkpoints
hitl_config = {
    'mandatory_checkpoints': ['after_planning', 'before_file_edit'],
}
register_all_hand_offs(cmbagent_instance, hitl_config=hitl_config)

# Smart approval (dynamic escalation)
hitl_config = {
    'smart_approval': True,
    'smart_criteria': {
        'escalate_keywords': ['delete', 'production', 'deploy'],
    }
}
register_all_hand_offs(cmbagent_instance, hitl_config=hitl_config)

# Hybrid (both)
hitl_config = {
    'mandatory_checkpoints': ['after_planning'],
    'smart_approval': True,
    'smart_criteria': {'escalate_keywords': ['delete', 'production']},
}
register_all_hand_offs(cmbagent_instance, hitl_config=hitl_config)
```

## Module Descriptions

### 1. `agent_retrieval.py`
Retrieves all agent instances from CMBAgent with error handling.

**Function:** `get_all_agents(cmbagent_instance) -> Dict`

### 2. `planning_chain.py`
Configures the planning workflow chain.

**Flow:**
```
task_improver → task_recorder → planner → formatter →
recorder → reviewer → formatter → recorder → planner (loop)
```

### 3. `execution_chain.py`
Configures execution workflows for different agent types.

**Flows:**
- **Engineer:** `engineer → engineer_nest → executor → control`
- **Researcher:** `researcher → formatter → executor → control`
- **Installer:** `installer → executor_bash → formatter`

### 4. `rag_agents.py`
Configures RAG (Retrieval-Augmented Generation) agents that fetch documentation.

**Agents:** CAMB, Classy_SZ, Cobaya, Planck

### 5. `context_agents.py`
Configures domain-specific context agents.

**Agents:** CAMB context, CLASS context

**Mode-aware:** Handoff destination changes based on mode (one_shot vs others)

### 6. `utility_agents.py`
Configures utility agents.

**Agents:** Summarizer, Terminator, AAS keyword finder

### 7. `nested_chats.py`
Sets up nested conversations for complex interactions.

**Nested Chats:**
- **Engineer nested chat:** Code execution sub-conversation
- **Idea maker nested chat:** Idea generation sub-conversation

### 8. `message_limiting.py`
Applies message history limiting to prevent context overflow.

Limits response formatters to 1 message (they only need latest context).

### 9. `mode_specific.py`
Configures handoffs based on operating mode.

**Modes:**
- **Chat mode:** `control → admin → chat_agent`
- **Standard mode:** `control → [engineer | researcher | terminator]` (LLM decides)

### 10. `hitl.py`
Configures HITL (Human-in-the-Loop) handoffs.

**Two types:**

**A. Mandatory Checkpoints** (always require human):
- `after_planning` - Review plan before execution
- `before_file_edit` - Approve file operations
- `before_execution` - Approve code execution
- `before_deploy` - Approve deployment

**B. Smart Approval** (LLM decides when to escalate):
- High-risk operations
- Uncertainty about approach
- Complex decisions
- Error recovery

### 11. `debug.py`
Debug utilities for handoff registration.

**Functions:**
- `is_debug_enabled()` - Check if debug mode is on
- `debug_print(message, indent)` - Print debug messages
- `debug_section(title)` - Print section headers

## Public API

### Main Function

```python
register_all_hand_offs(
    cmbagent_instance,
    hitl_config: Optional[Dict] = None
)
```

Registers all handoffs. Call this after creating CMBAgent instance.

**Args:**
- `cmbagent_instance`: CMBAgent instance to configure
- `hitl_config`: Optional HITL configuration (see HITL section)

### HITL Functions

```python
configure_hitl_checkpoints(
    cmbagent_instance,
    mandatory_checkpoints: List[str] = None,
    smart_approval: bool = False,
    smart_criteria: Dict = None,
)
```

Dynamically configure HITL after initial registration.

```python
disable_hitl_checkpoints(cmbagent_instance)
```

Disable all HITL and restore standard handoffs.

### Advanced

```python
get_all_agents(cmbagent_instance) -> Dict
```

Get dictionary of all agent instances. Useful for custom handoff logic.

## HITL Configuration Reference

### Mandatory Checkpoints

```python
hitl_config = {
    'mandatory_checkpoints': [
        'after_planning',      # Must review plan
        'before_file_edit',    # Must approve file edits
        'before_execution',    # Must approve code execution
        'before_deploy',       # Must approve deployment
    ]
}
```

**Mechanism:** Uses `set_after_work()` or `add_llm_conditions()` to force handoff to admin agent.

### Smart Approval

```python
hitl_config = {
    'smart_approval': True,
    'smart_criteria': {
        'escalate_keywords': [
            'delete', 'drop', 'truncate',
            'production', 'prod', 'live',
            'deploy', 'release', 'publish',
        ],
        'risk_threshold': 0.7,
    }
}
```

**Mechanism:** Adds LLM condition that evaluates context against criteria.

**Escalation triggers:**
- High-risk keywords detected
- Production environment changes
- Uncertainty about approach
- Complex decisions requiring judgment
- Repeated failures (3+)

## Usage Examples

### Example 1: High-Security Environment

```python
# Mandate approval for all critical operations
hitl_config = {
    'mandatory_checkpoints': [
        'after_planning',
        'before_file_edit',
        'before_execution',
        'before_deploy',
    ],
    'smart_approval': True,  # Extra safety net
}
register_all_hand_offs(cmbagent, hitl_config=hitl_config)
```

### Example 2: Autonomous with Safety Net

```python
# Mostly autonomous, catch risky operations
hitl_config = {
    'smart_approval': True,
    'smart_criteria': {
        'escalate_keywords': ['delete', 'production', 'database'],
    }
}
register_all_hand_offs(cmbagent, hitl_config=hitl_config)
```

### Example 3: Plan Review Only

```python
# Human reviews plan, then fully autonomous
hitl_config = {
    'mandatory_checkpoints': ['after_planning'],
}
register_all_hand_offs(cmbagent, hitl_config=hitl_config)
```

### Example 4: Dynamic Configuration

```python
from cmbagent.handoffs import configure_hitl_checkpoints

# Start without HITL
register_all_hand_offs(cmbagent)

# Enable HITL later
configure_hitl_checkpoints(
    cmbagent,
    mandatory_checkpoints=['before_file_edit'],
    smart_approval=True,
)

# Disable HITL
from cmbagent.handoffs import disable_hitl_checkpoints
disable_hitl_checkpoints(cmbagent)
```

## Debugging

### Enable Debug Mode

```python
from cmbagent import cmbagent_utils
cmbagent_utils.cmbagent_debug = True
```

Or in your config file:
```python
cmbagent_debug = True
```

### Debug Output

```
============================================================
REGISTERING AGENT HANDOFFS
============================================================
→ Retrieving agent instances...
  ✓ Retrieved 42 agents

→ Registering planning chain handoffs...
  ✓ Planning chain configured

→ Registering execution chain handoffs...
  ✓ Execution chain configured

→ Registering HITL handoffs...
  Config: {'mandatory_checkpoints': ['after_planning']}
  → Mandatory checkpoints: ['after_planning']
    ✓ after_planning: plan_reviewer → admin → control
  ✓ HITL handoffs configured

============================================================
ALL HANDOFFS REGISTERED SUCCESSFULLY
============================================================
```

### Verify Handoffs

```python
engineer = cmbagent.get_agent_object_from_name('engineer')
print(engineer.agent.handoffs)
print(engineer.agent.handoffs._llm_conditions)
```

## Handoff Types

### 1. Mandatory (set_after_work)

Agent ALWAYS hands off to specific target.

```python
agent.handoffs.set_after_work(AgentTarget(target_agent))
```

**Example:** `plan_reviewer → admin → control`

### 2. Conditional (add_llm_conditions)

LLM decides based on conversation context.

```python
agent.handoffs.add_llm_conditions([
    OnCondition(
        target=AgentTarget(target_agent),
        condition=StringLLMCondition(prompt="When X is detected")
    )
])
```

**Example:** `engineer → admin (if file editing detected)`

## Flow Diagrams

### Without HITL
```
control → [engineer | researcher | terminator]
           ↓
         result
```

### With Mandatory Checkpoint (after_planning)
```
plan_reviewer → admin (human) → control → [engineer | researcher]
                    ↓                          ↓
               approve/reject                result
```

### With Smart Approval
```
control → [engineer | researcher]
            ↓           ↓
          {risky?}    {risky?}
            ↓ yes       ↓ yes
          admin       admin
            ↓           ↓
          approve     approve
            ↓           ↓
          continue    continue
```

## Backward Compatibility

Old code using `from cmbagent.hand_offs import register_all_hand_offs` continues to work. The old `hand_offs.py` now redirects to the new modular structure.

## Migration Guide

### Old Code
```python
from cmbagent.hand_offs import register_all_hand_offs
register_all_hand_offs(cmbagent_instance)
```

### New Code (Recommended)
```python
from cmbagent.handoffs import register_all_hand_offs
register_all_hand_offs(cmbagent_instance)
```

Both work identically!

## Best Practices

1. **Start conservative**: Begin with mandatory checkpoints for critical operations
2. **Add smart gradually**: Enable smart approval after testing mandatory checkpoints
3. **Tune keywords**: Adjust escalation keywords based on your domain
4. **Use debug mode**: Enable during development to see handoff flow
5. **Test thoroughly**: Dry run workflows before production

## Common Patterns

### Pattern 1: Plan Review + Smart
```python
hitl_config = {
    'mandatory_checkpoints': ['after_planning'],
    'smart_approval': True,
}
```
**Use when:** Want to review strategy, trust agents during execution with safety net.

### Pattern 2: Critical Operations Only
```python
hitl_config = {
    'mandatory_checkpoints': ['before_file_edit', 'before_deploy'],
}
```
**Use when:** Autonomous planning, protect critical operations.

### Pattern 3: Full Autonomous with Safety
```python
hitl_config = {
    'smart_approval': True,
    'smart_criteria': {'escalate_keywords': ['delete', 'production']},
}
```
**Use when:** Trust agents, catch obviously risky operations.

## See Also

- [HANDOFFS_REFACTOR_GUIDE.md](../../docs/HANDOFFS_REFACTOR_GUIDE.md) - Detailed guide
- [HITL_HANDOFFS_QUICKREF.md](../../docs/HITL_HANDOFFS_QUICKREF.md) - Quick reference
- [AG2_HITL_INSIGHTS.md](../../docs/AG2_HITL_INSIGHTS.md) - AG2 best practices
- [HITL_PHASES_GUIDE.md](../../docs/HITL_PHASES_GUIDE.md) - HITL phases guide

## Contributing

When adding new handoff configurations:

1. Identify which module the new handoff belongs to
2. Add the handoff logic to the appropriate module
3. Export through `__init__.py` if it's public API
4. Update this README
5. Add examples and tests

## License

Same as parent project.
