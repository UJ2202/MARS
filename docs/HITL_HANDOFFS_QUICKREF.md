# HITL Handoffs - Quick Reference

## TL;DR

**AG2 supports both mandatory and dynamic human checkpoints using native handoffs!**

---

## Basic Usage

### No HITL (Standard Mode)
```python
from cmbagent.hand_offs import register_all_hand_offs

register_all_hand_offs(cmbagent_instance)
```

### With Mandatory Checkpoints
```python
hitl_config = {
    'mandatory_checkpoints': ['after_planning', 'before_file_edit']
}
register_all_hand_offs(cmbagent_instance, hitl_config=hitl_config)
```

### With Smart Approval
```python
hitl_config = {
    'smart_approval': True,
    'smart_criteria': {
        'escalate_keywords': ['delete', 'production', 'deploy'],
    }
}
register_all_hand_offs(cmbagent_instance, hitl_config=hitl_config)
```

### Hybrid (Both)
```python
hitl_config = {
    'mandatory_checkpoints': ['after_planning'],
    'smart_approval': True,
    'smart_criteria': {
        'escalate_keywords': ['delete', 'production'],
    }
}
register_all_hand_offs(cmbagent_instance, hitl_config=hitl_config)
```

---

## Available Mandatory Checkpoints

| Checkpoint | What It Does | Flow |
|------------|--------------|------|
| `after_planning` | Human reviews plan before execution | `plan_reviewer → admin → control` |
| `before_file_edit` | Human approves file operations | `engineer → admin (on file ops) → engineer` |
| `before_execution` | Human approves code execution | `engineer → admin (on exec) → engineer` |
| `before_deploy` | Human approves deployment | `control → admin (on deploy) → control` |

---

## Smart Approval Triggers

Agent escalates to human when:
- **High-risk keywords** detected (configurable)
- **Production environment** changes
- **Data deletion** or irreversible operations
- **Uncertainty** about approach
- **Complex decisions** requiring judgment
- **Repeated failures** (3+ attempts)

---

## Configuration Options

```python
hitl_config = {
    # List of mandatory checkpoints
    'mandatory_checkpoints': [
        'after_planning',
        'before_file_edit',
        'before_execution',
        'before_deploy',
    ],

    # Enable smart approval
    'smart_approval': True,  # or False

    # Smart approval criteria
    'smart_criteria': {
        # Keywords that trigger escalation
        'escalate_keywords': [
            'delete', 'drop', 'truncate',
            'production', 'prod', 'live',
            'deploy', 'release', 'publish',
        ],

        # Risk threshold (0.0 - 1.0)
        'risk_threshold': 0.7,
    }
}
```

---

## Use Cases

### Use Case 1: High-Security Environment
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
```

### Use Case 2: Autonomous with Safety Net
```python
# Mostly autonomous, but catch risky ops
hitl_config = {
    'smart_approval': True,
    'smart_criteria': {
        'escalate_keywords': ['delete', 'production', 'database'],
    }
}
```

### Use Case 3: Plan Review Only
```python
# Human reviews plan, then fully autonomous
hitl_config = {
    'mandatory_checkpoints': ['after_planning'],
}
```

### Use Case 4: File Operations Only
```python
# Only require approval for file edits
hitl_config = {
    'mandatory_checkpoints': ['before_file_edit'],
}
```

---

## Dynamic Configuration

### Enable HITL After Initialization
```python
from cmbagent.hand_offs import configure_hitl_checkpoints

# Start without HITL
register_all_hand_offs(cmbagent)

# Enable HITL later
configure_hitl_checkpoints(
    cmbagent,
    mandatory_checkpoints=['before_file_edit'],
    smart_approval=True,
)
```

### Disable HITL
```python
from cmbagent.hand_offs import disable_hitl_checkpoints

disable_hitl_checkpoints(cmbagent)
```

---

## Debugging

### Enable Debug Output
```python
from cmbagent import hand_offs
hand_offs.cmbagent_debug = True
```

### Check Handoffs
```python
engineer = cmbagent.get_agent_object_from_name('engineer')
print(engineer.agent.handoffs)
print(engineer.agent.handoffs._llm_conditions)
```

---

## Admin Agent Configuration

```python
admin = cmbagent.get_agent_object_from_name('admin')

# Configure human input mode
admin.agent.human_input_mode = "ALWAYS"      # Prompt after every message
admin.agent.human_input_mode = "TERMINATE"   # Prompt at checkpoints only
admin.agent.human_input_mode = "NEVER"       # Disabled
```

---

## Handoff Mechanisms

### Mandatory (set_after_work)
Always hands off to target agent:
```python
agent.handoffs.set_after_work(AgentTarget(target_agent))
```

### Conditional (add_llm_conditions)
LLM decides based on context:
```python
agent.handoffs.add_llm_conditions([
    OnCondition(
        target=AgentTarget(target_agent),
        condition=StringLLMCondition(prompt="When X is detected")
    )
])
```

---

## Comparison

### Old Approach (External Approval)
```python
approval_manager = context.shared_state.get('_approval_manager')
approval_request = approval_manager.create_approval_request(...)
resolved = await approval_manager.wait_for_approval_async(...)
```
❌ Approval outside agent conversation
❌ Fixed approval points
❌ No dynamic escalation

### New Approach (AG2 Handoffs)
```python
hitl_config = {
    'mandatory_checkpoints': ['after_planning'],
    'smart_approval': True,
}
register_all_hand_offs(cmbagent, hitl_config=hitl_config)
```
✅ Admin agent in conversation
✅ Dynamic escalation
✅ Agent decides when to escalate

---

## Integration with HITLControlPhase

```python
from cmbagent.phases.hitl_control import HITLControlPhaseConfig

config = HITLControlPhaseConfig(
    approval_mode='before_step',
    # NEW: AG2 handoff config
    mandatory_human_checkpoints=['after_planning', 'before_file_edit'],
    smart_approval=True,
    smart_criteria={
        'escalate_keywords': ['delete', 'production'],
    }
)
```

---

## Examples

### Example 1: Science Computing
```python
# Allow autonomous work, but catch destructive operations
hitl_config = {
    'smart_approval': True,
    'smart_criteria': {
        'escalate_keywords': [
            'delete', 'remove', 'drop',
            'overwrite', 'truncate',
        ],
    }
}
```

### Example 2: Financial System
```python
# High security: mandate approval for everything critical
hitl_config = {
    'mandatory_checkpoints': [
        'after_planning',
        'before_file_edit',
        'before_execution',
        'before_deploy',
    ],
    'smart_approval': True,
    'smart_criteria': {
        'escalate_keywords': [
            'payment', 'charge', 'refund',
            'transaction', 'transfer',
            'production', 'live',
        ],
    }
}
```

### Example 3: Code Assistant
```python
# Review code, but let agent work autonomously
hitl_config = {
    'mandatory_checkpoints': ['after_planning'],
    'smart_approval': False,
}
```

---

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

### Hybrid (Both)
```
plan_reviewer → admin (human) → control → engineer
                    ↓                        ↓
               approve/reject              {risky?}
                                              ↓ yes
                                            admin
                                              ↓
                                          approve
                                              ↓
                                          continue
```

---

## Common Patterns

### Pattern 1: Plan Review + Smart
```python
hitl_config = {
    'mandatory_checkpoints': ['after_planning'],
    'smart_approval': True,
}
```
**Use when:** Want to review strategy, but trust agents during execution with safety net.

### Pattern 2: Critical Operations Only
```python
hitl_config = {
    'mandatory_checkpoints': ['before_file_edit', 'before_deploy'],
}
```
**Use when:** Autonomous planning, but protect critical operations.

### Pattern 3: Full Autonomous with Safety
```python
hitl_config = {
    'smart_approval': True,
    'smart_criteria': {
        'escalate_keywords': ['delete', 'production'],
    }
}
```
**Use when:** Trust agents, but catch obviously risky operations.

---

## Tips

1. **Start conservative**: Begin with mandatory checkpoints
2. **Add smart gradually**: Enable smart approval after testing
3. **Tune keywords**: Adjust based on your domain
4. **Use debug mode**: During development, enable debug output
5. **Test thoroughly**: Dry run workflows before production

---

## FAQ

**Q: Can I use both systems (handoffs + approval_manager)?**
A: Yes! They complement each other.

**Q: What happens if admin agent is not configured?**
A: Mandatory checkpoints will fail. Ensure admin agent exists.

**Q: Can I customize admin agent behavior?**
A: Yes! Set `human_input_mode` on admin agent.

**Q: How do I know which handoffs are active?**
A: Enable debug mode: `hand_offs.cmbagent_debug = True`

**Q: Can I change HITL config mid-workflow?**
A: Use `configure_hitl_checkpoints()` for dynamic changes.

**Q: What if I want different checkpoints per task?**
A: Pass different `hitl_config` when registering handoffs.

---

## See Also

- Full guide: `docs/HANDOFFS_REFACTOR_GUIDE.md`
- AG2 insights: `docs/AG2_HITL_INSIGHTS.md`
- HITL phases: `docs/HITL_PHASES_GUIDE.md`
- Source code: `cmbagent/hand_offs.py`

---

**Quick Start:**
```python
from cmbagent.hand_offs import register_all_hand_offs

hitl_config = {
    'mandatory_checkpoints': ['after_planning'],
    'smart_approval': True,
}

register_all_hand_offs(cmbagent_instance, hitl_config=hitl_config)
```

**That's it!** 🚀
