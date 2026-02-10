# Handoffs Refactor & HITL Integration Guide

## Overview

The `cmbagent/hand_offs.py` module has been completely refactored for better organization and now includes native AG2-based HITL (Human-in-the-Loop) handoff support.

## What Changed

### Before: Monolithic Function (347 lines)
- Single `register_all_hand_offs()` function
- All handoffs mixed together
- Hard to understand and maintain
- No HITL support

### After: Modular Structure (898 lines, but organized)
- **15 focused functions**, each handling a specific concern
- Clear sections with headers
- Built-in HITL handoff system
- Easy to extend and debug

---

## New Structure

### 1. **Agent Retrieval**
```python
_get_all_agents(cmbagent_instance) -> Dict
```
Centralized agent retrieval with error handling.

### 2. **Planning Chain**
```python
_register_planning_chain_handoffs(agents)
```
Handles: `task_improver → task_recorder → planner → formatter → recorder → reviewer`

### 3. **Execution Chain**
```python
_register_execution_chain_handoffs(agents)
```
Handles: `engineer`, `researcher`, `installer` execution flows

### 4. **RAG Agents**
```python
_register_rag_handoffs(agents, skip_rag)
```
Handles: `camb_agent`, `classy_sz_agent`, `cobaya_agent`, `planck_agent`

### 5. **Context Agents**
```python
_register_context_agent_handoffs(agents, mode)
```
Handles: `camb_context`, `classy_context` (mode-aware routing)

### 6. **Utility Agents**
```python
_register_utility_handoffs(agents)
```
Handles: `summarizer`, `terminator`, `aas_keyword_finder`

### 7. **Nested Chats**
```python
_setup_engineer_nested_chat(agents, cmbagent_instance)
_setup_idea_maker_nested_chat(agents, cmbagent_instance)
```
Creates sub-conversations for complex tasks.

### 8. **Message History Limiting**
```python
_apply_message_history_limiting(agents)
```
Prevents context overflow on formatters.

### 9. **Mode-Specific Handoffs**
```python
_register_chat_mode_handoffs(agents, cmbagent_instance)
_register_standard_mode_handoffs(agents)
```
Different behavior for chat vs standard modes.

### 10. **HITL Handoffs (NEW!)**
```python
_register_hitl_handoffs(agents, hitl_config)
_register_mandatory_hitl_checkpoints(agents, checkpoints)
_register_smart_hitl_approval(agents, criteria)
```
Native AG2-based human-in-the-loop integration.

---

## HITL Handoffs - How It Works

### Two Types of HITL

#### 1. **Mandatory Checkpoints**
Human MUST approve before proceeding.

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

**Mechanism**: Uses `set_after_work()` or `add_llm_conditions()` to force handoff to `admin` agent.

**Example Flow**:
```
plan_reviewer → admin (human) → control
```

#### 2. **Smart Approval (Dynamic)**
LLM decides when to escalate to human based on context.

```python
hitl_config = {
    'smart_approval': True,
    'smart_criteria': {
        'escalate_keywords': ['delete', 'production', 'deploy', 'critical'],
        'risk_threshold': 0.7,
    }
}
```

**Mechanism**: Uses `add_llm_conditions()` with context-aware prompts.

**Example Escalation Triggers**:
- High-risk keywords detected
- Multiple failures (3+)
- Uncertain about approach
- Complex architectural decisions
- Production environment changes

---

## Usage Examples

### Example 1: Basic HITL with Mandatory Checkpoints

```python
from cmbagent.cmbagent import CMBAgent
from cmbagent.hand_offs import register_all_hand_offs

# Create agent
cmbagent = CMBAgent(work_dir="~/output", api_keys=api_keys)

# Configure HITL with mandatory checkpoints
hitl_config = {
    'mandatory_checkpoints': ['after_planning', 'before_file_edit']
}

# Register handoffs
register_all_hand_offs(cmbagent, hitl_config=hitl_config)

# Now when the workflow runs:
# - Plan phase → human MUST review plan
# - Before file edits → human MUST approve
```

### Example 2: Smart Approval Only

```python
# Let LLM decide when to escalate
hitl_config = {
    'smart_approval': True,
    'smart_criteria': {
        'escalate_keywords': ['delete', 'production', 'database', 'deploy'],
        'risk_threshold': 0.7,
    }
}

register_all_hand_offs(cmbagent, hitl_config=hitl_config)

# Agents will automatically escalate to human when:
# - They detect risky operations (delete, production, etc.)
# - They're uncertain about the approach
# - Error recovery is needed
```

### Example 3: Hybrid (Mandatory + Smart)

```python
# Combine both approaches
hitl_config = {
    'mandatory_checkpoints': ['after_planning'],  # Always review plan
    'smart_approval': True,                       # Dynamic escalation during execution
    'smart_criteria': {
        'escalate_keywords': ['delete', 'drop', 'truncate', 'production'],
    }
}

register_all_hand_offs(cmbagent, hitl_config=hitl_config)
```

### Example 4: Dynamic Configuration

```python
from cmbagent.hand_offs import configure_hitl_checkpoints

# Initial setup without HITL
cmbagent = CMBAgent(work_dir="~/output", api_keys=api_keys)
register_all_hand_offs(cmbagent)

# Later, enable HITL dynamically
configure_hitl_checkpoints(
    cmbagent,
    mandatory_checkpoints=['before_file_edit'],
    smart_approval=True,
)

# To disable HITL
from cmbagent.hand_offs import disable_hitl_checkpoints
disable_hitl_checkpoints(cmbagent)
```

### Example 5: Using in HITL Phases

```python
from cmbagent.phases.hitl_control import HITLControlPhase, HITLControlPhaseConfig

# Configure phase with HITL handoffs
config = HITLControlPhaseConfig(
    approval_mode='before_step',
    mandatory_human_checkpoints=['after_planning', 'before_file_edit'],
    smart_approval=True,
    smart_criteria={'escalate_keywords': ['delete', 'production']},
)

phase = HITLControlPhase(config)

# In phase execution, configure handoffs:
def execute(self, context):
    cmbagent = CMBAgent(...)

    # Setup HITL handoffs
    hitl_config = {
        'mandatory_checkpoints': self.config.mandatory_human_checkpoints,
        'smart_approval': self.config.smart_approval,
        'smart_criteria': self.config.smart_criteria,
    }

    register_all_hand_offs(cmbagent, hitl_config=hitl_config)

    # Execute with HITL-aware handoffs
    cmbagent.solve(task=context.task, initial_agent='control')
```

---

## How Admin Agent Works

The `admin` agent is your human interface in the swarm:

### 1. **Setting human_input_mode**

```python
# In your phase or workflow setup
admin = cmbagent.get_agent_object_from_name('admin')

# Configure based on HITL needs
admin.agent.human_input_mode = "ALWAYS"      # Prompt after every message
# OR
admin.agent.human_input_mode = "TERMINATE"   # Prompt only at checkpoints
# OR
admin.agent.human_input_mode = "NEVER"       # No prompts (disabled)
```

### 2. **Receiving Handoffs**

When an agent hands off to `admin`:
- The agent's message is shown to the user
- User provides input/approval
- Admin hands off to the next agent (configured in handoffs)

### 3. **Return Flow**

After human approval, control returns to workflow:
```
engineer → admin (human reviews) → control (continues workflow)
```

---

## Mandatory Checkpoint Implementations

### `after_planning`
```python
# Overrides planning chain
plan_reviewer → admin → control
```

**What happens:**
1. Plan reviewer finishes reviewing plan
2. Hands off to admin (human)
3. Human sees the plan and approves/rejects
4. If approved, hands off to control to start execution

### `before_file_edit`
```python
# Adds condition to engineer
engineer.agent.handoffs.add_llm_conditions([
    OnCondition(
        target=AgentTarget(admin),
        condition="About to edit, create, delete, or modify any files"
    )
])
```

**What happens:**
1. Engineer detects it needs to edit files
2. LLM evaluates: "Am I about to edit files?"
3. If yes, hands off to admin (human)
4. Human approves/rejects the file operation
5. Returns to engineer to complete the task

### `before_execution`
Similar to `before_file_edit`, but for code execution.

### `before_deploy`
Applied to control agent for deployment operations.

---

## Smart Approval Prompt

The smart approval system injects this prompt into agents:

```
Escalate to admin (human) if ANY of these conditions are met:

1. HIGH RISK OPERATIONS detected:
   - Keywords: delete, production, deploy, critical, irreversible
   - Production environment changes
   - Data deletion or irreversible operations
   - Security-sensitive operations

2. UNCERTAINTY about correct approach:
   - Ambiguous requirements
   - Multiple valid solutions with trade-offs
   - Potential for significant negative impact

3. COMPLEX DECISIONS requiring judgment:
   - Architectural choices
   - Cost vs. benefit trade-offs
   - Ethical or policy considerations

4. ERROR RECOVERY:
   - Repeated failures (3+ attempts)
   - Unclear how to proceed
   - Need alternative strategy

IMPORTANT: When in doubt, escalate to admin. Better safe than sorry.
```

**How it works:**
- Added to `control` and `engineer` agents
- LLM evaluates conversation context against these criteria
- If any match, hands off to admin
- Otherwise, proceeds normally

---

## Debugging Handoffs

### Enable Debug Mode

Set `cmbagent_debug = True` in `cmbagent_utils.py` or:

```python
from cmbagent import hand_offs
hand_offs.cmbagent_debug = True
```

**Output:**
```
============================================================
REGISTERING AGENT HANDOFFS
============================================================
→ Retrieving agent instances...
  Retrieved 42 agents

→ Registering planning chain handoffs...
  ✓ Planning chain configured

→ Registering execution chain handoffs...
  ✓ Execution chain configured

→ Registering HITL handoffs...
  Config: {'mandatory_checkpoints': ['after_planning'], 'smart_approval': True}
  → Mandatory checkpoints: ['after_planning']
    ✓ after_planning: plan_reviewer → admin → control
  → Smart approval enabled with criteria: {'escalate_keywords': ['delete']}
    ✓ Smart approval conditions added to control and engineer agents
  ✓ HITL handoffs configured

============================================================
ALL HANDOFFS REGISTERED SUCCESSFULLY
============================================================
```

### Verify Handoffs

```python
# Check what handoffs are registered
engineer = cmbagent.get_agent_object_from_name('engineer')
print(engineer.agent.handoffs)

# Check conditions
print(engineer.agent.handoffs._llm_conditions)
```

---

## Migration from Old Code

### Old Way (Before Refactor)
```python
# Everything in one function
register_all_hand_offs(cmbagent_instance)
```

### New Way (After Refactor)
```python
# Without HITL (backward compatible)
register_all_hand_offs(cmbagent_instance)

# With HITL
hitl_config = {
    'mandatory_checkpoints': ['after_planning', 'before_file_edit'],
    'smart_approval': True,
    'smart_criteria': {'escalate_keywords': ['delete', 'production']},
}
register_all_hand_offs(cmbagent_instance, hitl_config=hitl_config)
```

**Result**: 100% backward compatible! Old code works without changes.

---

## Best Practices

### 1. **Start Conservative**
Begin with mandatory checkpoints for critical operations:
```python
hitl_config = {
    'mandatory_checkpoints': ['after_planning', 'before_file_edit', 'before_deploy'],
}
```

### 2. **Add Smart Approval Gradually**
Once comfortable, enable smart approval:
```python
hitl_config = {
    'mandatory_checkpoints': ['after_planning'],
    'smart_approval': True,
}
```

### 3. **Tune Smart Criteria**
Adjust keywords based on your domain:
```python
smart_criteria = {
    'escalate_keywords': [
        'delete', 'drop', 'truncate',      # Database operations
        'production', 'prod', 'live',       # Environment
        'deploy', 'release', 'publish',     # Deployment
        'payment', 'charge', 'refund',      # Financial
    ]
}
```

### 4. **Use Debug Mode During Development**
```python
from cmbagent import hand_offs
hand_offs.cmbagent_debug = True
```

### 5. **Test with Dry Runs**
```python
# Run workflow in test mode
cmbagent.solve(task="Test task", initial_agent='control', max_rounds=5)
# Verify admin handoffs occur where expected
```

---

## Comparison: Old vs New HITL

### Old Approach (Your Current HITLControlPhase)

```python
# Manual approval system (outside AG2)
approval_manager = context.shared_state.get('_approval_manager')
approval_request = approval_manager.create_approval_request(...)
resolved = await approval_manager.wait_for_approval_async(...)
```

**Issues:**
- Approval outside agent conversation
- Fixed approval points (before/after/both/on_error)
- No dynamic escalation
- Admin agent not part of swarm

### New Approach (AG2-Native Handoffs)

```python
# AG2-native handoffs (inside conversation)
hitl_config = {
    'mandatory_checkpoints': ['after_planning'],
    'smart_approval': True,
}
register_all_hand_offs(cmbagent, hitl_config=hitl_config)
```

**Benefits:**
- Admin agent is first-class swarm member
- Dynamic escalation (LLM decides)
- Agents decide when to escalate
- More flexible than fixed checkpoints

---

## Combining Both Approaches

You can use **both** systems together:

1. **Phase-level approval** (WebSocket-based): For structured checkpoints
2. **Handoff-based approval** (AG2-native): For dynamic escalation

```python
# In HITLControlPhase
class HITLControlPhase(Phase):
    async def execute(self, context):
        # Setup HITL handoffs (AG2-native)
        hitl_config = {
            'smart_approval': True,
            'smart_criteria': self.config.smart_criteria,
        }
        register_all_hand_offs(cmbagent, hitl_config=hitl_config)

        # Also use approval manager for structured checkpoints
        if self.config.approval_mode in ["before_step", "both"]:
            approval = await self._request_step_approval(...)
```

This gives you:
- Structured UI-based approval at phase boundaries
- Dynamic agent-driven escalation during execution

---

## Next Steps

### Integrate with HITLControlPhase

Modify `cmbagent/phases/hitl_control.py` to use AG2 handoffs:

```python
@dataclass
class HITLControlPhaseConfig(PhaseConfig):
    # Existing fields...

    # NEW: HITL handoff config
    use_ag2_handoffs: bool = True
    mandatory_checkpoints: List[str] = field(default_factory=list)
    smart_approval: bool = False
    smart_criteria: Dict = field(default_factory=dict)
```

Then in `execute()`:
```python
if self.config.use_ag2_handoffs:
    hitl_config = {
        'mandatory_checkpoints': self.config.mandatory_checkpoints,
        'smart_approval': self.config.smart_approval,
        'smart_criteria': self.config.smart_criteria,
    }
    register_all_hand_offs(cmbagent, hitl_config=hitl_config)
```

### Test the System

1. Create a test workflow with HITL
2. Trigger various scenarios (file edits, deployments, errors)
3. Verify admin handoffs occur correctly
4. Tune smart criteria based on results

### Update Documentation

Document the new HITL handoff system in:
- `HITL_PHASES_GUIDE.md`
- `HITL_WORKFLOW_INTEGRATION.md`
- User-facing documentation

---

## Summary

### What We Built

1. ✅ **Refactored `hand_offs.py`** into 15 modular functions
2. ✅ **Added HITL handoff system** with mandatory + smart approval
3. ✅ **AG2-native implementation** using handoffs and conditions
4. ✅ **Backward compatible** - old code still works
5. ✅ **Well-documented** with examples and best practices

### Key Benefits

- **More maintainable**: Easy to find and modify handoffs
- **More flexible**: Configure HITL behavior dynamically
- **More powerful**: Combines mandatory + smart approval
- **More AG2-native**: Uses handoffs instead of external approval system
- **Better UX**: Agents decide when to escalate, not rigid rules

### What's Next

Test it! Try it with your workflows and see how agents dynamically escalate to human when needed. The smart approval system should significantly reduce unnecessary human interruptions while catching truly risky operations.

---

**Questions? Check the inline documentation in `hand_offs.py` or reach out!**
