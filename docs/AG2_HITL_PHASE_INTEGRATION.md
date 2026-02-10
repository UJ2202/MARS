# AG2 HITL Handoffs - Phase Integration Guide

## Overview

All **HITL phases** now support AG2-native handoff configurations. This enables both manual approval systems (WebSocket-based) and AG2-native dynamic escalation to work together.

---

## Updated Phases

### 1. HITLPlanningPhase ✅
**File:** `cmbagent/phases/hitl_planning.py`

**New Config Options:**
```python
use_ag2_handoffs: bool = False
ag2_mandatory_checkpoints: List[str] = ['after_planning']
ag2_smart_approval: bool = False
ag2_smart_criteria: Dict = {}
```

### 2. HITLControlPhase ✅
**File:** `cmbagent/phases/hitl_control.py`

**New Config Options:**
```python
use_ag2_handoffs: bool = False
ag2_mandatory_checkpoints: List[str] = []
ag2_smart_approval: bool = False
ag2_smart_criteria: Dict = {}
```

---

## Usage Examples

### Example 1: Planning Phase with Mandatory Approval

```python
from cmbagent.phases.hitl_planning import HITLPlanningPhase, HITLPlanningPhaseConfig
from cmbagent.workflows.composer import WorkflowExecutor, WorkflowDefinition

# Configure planning phase with AG2 HITL
planning_config = HITLPlanningPhaseConfig(
    max_rounds=50,
    max_plan_steps=5,

    # Enable AG2 HITL handoffs
    use_ag2_handoffs=True,
    ag2_mandatory_checkpoints=['after_planning'],  # Human MUST review plan
)

# Create workflow
workflow_def = WorkflowDefinition(
    id='hitl_workflow',
    name='HITL Workflow with AG2 Handoffs',
    description='Planning with mandatory human approval',
    phases=[
        {'type': 'hitl_planning', 'config': planning_config.to_dict()},
    ]
)

# Execute
executor = WorkflowExecutor(
    workflow=workflow_def,
    task="Build a data pipeline",
    work_dir="~/output",
    api_keys=api_keys,
)

result = await executor.run()
```

**What happens:**
1. Planner generates plan
2. Plan reviewer reviews plan
3. **Plan reviewer hands off to admin (human) - MANDATORY**
4. Human approves/rejects
5. If approved, continues to next phase

---

### Example 2: Control Phase with Smart Approval

```python
from cmbagent.phases.hitl_control import HITLControlPhase, HITLControlPhaseConfig

# Configure control phase with smart approval
control_config = HITLControlPhaseConfig(
    max_rounds=100,
    approval_mode='before_step',  # WebSocket-based approval

    # Enable AG2 smart approval (dynamic escalation)
    use_ag2_handoffs=True,
    ag2_smart_approval=True,
    ag2_smart_criteria={
        'escalate_keywords': ['delete', 'production', 'deploy', 'drop'],
        'risk_threshold': 0.7,
    }
)

# Create workflow
workflow_def = WorkflowDefinition(
    id='smart_control',
    name='Control with Smart Approval',
    description='Execution with dynamic escalation',
    phases=[
        {'type': 'hitl_control', 'config': control_config.to_dict()},
    ]
)

result = await executor.run()
```

**What happens:**
1. WebSocket approval before each step (**existing behavior**)
2. During step execution, if risky operation detected (**NEW**):
   - Engineer/control agent hands off to admin
   - Human reviews and approves
   - Execution continues
3. **Example scenarios that trigger escalation:**
   - Engineer says: "delete all files in /data/production"
   - Control detects: "deploy to production environment"
   - Engineer uncertain: "should I truncate this database table?"

---

### Example 3: Hybrid (Mandatory + Smart)

```python
from cmbagent.phases.hitl_planning import HITLPlanningPhaseConfig
from cmbagent.phases.hitl_control import HITLControlPhaseConfig

# Planning: Mandatory plan review
planning_config = HITLPlanningPhaseConfig(
    use_ag2_handoffs=True,
    ag2_mandatory_checkpoints=['after_planning'],
)

# Control: Mandatory file edit approval + smart escalation
control_config = HITLControlPhaseConfig(
    approval_mode='before_step',

    use_ag2_handoffs=True,
    ag2_mandatory_checkpoints=['before_file_edit', 'before_execution'],
    ag2_smart_approval=True,
    ag2_smart_criteria={
        'escalate_keywords': ['delete', 'production', 'database'],
    }
)

workflow_def = WorkflowDefinition(
    id='full_hitl',
    name='Full HITL with AG2',
    description='Complete human oversight',
    phases=[
        {'type': 'hitl_planning', 'config': planning_config.to_dict()},
        {'type': 'hitl_control', 'config': control_config.to_dict()},
    ]
)

result = await executor.run()
```

**What happens:**
1. **Planning Phase:**
   - Plan generated → plan_reviewer → **admin (MANDATORY)** → approved → continue

2. **Control Phase:**
   - **WebSocket approval before each step** (approval_mode='before_step')
   - **During execution:**
     - Before file edit → **admin (MANDATORY - AG2)** → approved → continue
     - Before code execution → **admin (MANDATORY - AG2)** → approved → continue
     - Risky operation detected → **admin (DYNAMIC - AG2)** → approved → continue

---

## Configuration Reference

### Mandatory Checkpoints

Available checkpoints for `ag2_mandatory_checkpoints`:

| Checkpoint | What It Does | When Used |
|------------|--------------|-----------|
| `after_planning` | Review plan before execution | Planning phase |
| `before_file_edit` | Approve file operations | Control phase |
| `before_execution` | Approve code execution | Control phase |
| `before_deploy` | Approve deployment | Control phase |

**Example:**
```python
ag2_mandatory_checkpoints=['after_planning', 'before_file_edit']
```

### Smart Criteria

Configuration for `ag2_smart_criteria`:

```python
ag2_smart_criteria={
    'escalate_keywords': [
        'delete', 'drop', 'truncate',        # Data operations
        'production', 'prod', 'live',         # Environment
        'deploy', 'release', 'publish',       # Deployment
        'remove', 'rm', 'uninstall',          # Removal
    ],
    'risk_threshold': 0.7,  # Not currently used, reserved for future
}
```

**Escalation triggers:**
1. **Keywords detected** in agent messages
2. **High-risk operations** (production changes, data deletion)
3. **Uncertainty** about correct approach
4. **Complex decisions** requiring judgment
5. **Error recovery** (3+ failed attempts)

---

## Integration with Existing Approval System

The AG2 handoffs **complement** the existing WebSocket-based approval system:

### Two-Layer Approval Model

#### Layer 1: WebSocket-Based (Existing)
- **Level:** Phase-level
- **Mechanism:** `approval_manager.create_approval_request()`
- **When:** Before/after steps, on errors (configurable)
- **UI:** WebSocket events to frontend

#### Layer 2: AG2 Handoffs (New)
- **Level:** Agent-level (inside conversation)
- **Mechanism:** `agent.handoffs` with conditions
- **When:** Mandatory checkpoints + dynamic escalation
- **UI:** Admin agent participates in conversation

### How They Work Together

**Scenario: File editing in control phase**

```python
control_config = HITLControlPhaseConfig(
    approval_mode='before_step',          # WebSocket approval
    use_ag2_handoffs=True,
    ag2_mandatory_checkpoints=['before_file_edit'],  # AG2 approval
)
```

**Flow:**
```
1. WebSocket: "About to execute step 3?"
   → User approves via UI

2. Step execution starts
   → Engineer agent works

3. Engineer detects file edit needed
   → AG2 handoff: engineer → admin

4. WebSocket (or console): "About to edit config.yaml?"
   → User approves

5. Engineer continues
   → File edited

6. Step completes
```

**Benefits:**
- **Structured approval** at phase boundaries (WebSocket)
- **Dynamic approval** during execution (AG2)
- **Fine-grained control** over risky operations

---

## Best Practices

### 1. Start Simple
Begin with mandatory checkpoints only:

```python
use_ag2_handoffs=True,
ag2_mandatory_checkpoints=['after_planning'],
```

### 2. Add Smart Approval Gradually
Once comfortable, enable dynamic escalation:

```python
use_ag2_handoffs=True,
ag2_mandatory_checkpoints=['after_planning'],
ag2_smart_approval=True,
ag2_smart_criteria={'escalate_keywords': ['delete', 'production']},
```

### 3. Tune Keywords
Adjust based on your domain:

**Science/Research:**
```python
'escalate_keywords': ['delete', 'overwrite', 'clear', 'remove']
```

**Financial:**
```python
'escalate_keywords': ['payment', 'charge', 'refund', 'transaction', 'production']
```

**DevOps:**
```python
'escalate_keywords': ['deploy', 'production', 'delete', 'drop', 'scale']
```

### 4. Combine Approval Modes
Use WebSocket for structure, AG2 for dynamics:

```python
# Structured checkpoints
approval_mode='before_step',

# Dynamic escalation
use_ag2_handoffs=True,
ag2_smart_approval=True,
```

### 5. Test Without AG2 First
Disable AG2 handoffs during development:

```python
use_ag2_handoffs=False,  # Use only WebSocket approvals
```

Then enable for production:

```python
use_ag2_handoffs=True,
```

---

## Admin Agent Configuration

The `admin` agent is your human interface. Configure its behavior:

### In Phase Config (Future Enhancement)
```python
admin_human_input_mode='ALWAYS',  # Prompt after every message
# or
admin_human_input_mode='TERMINATE',  # Prompt only at checkpoints
```

### Manual Configuration (Current)
```python
# In your workflow code
admin = cmbagent.get_agent_object_from_name('admin')
admin.agent.human_input_mode = "TERMINATE"  # Checkpoints only
```

---

## Debugging

### Enable Debug Output
```python
from cmbagent import cmbagent_utils
cmbagent_utils.cmbagent_debug = True
```

**Output:**
```
============================================================
REGISTERING AGENT HANDOFFS
============================================================
→ Retrieving agent instances...
  ✓ Retrieved 42 agents

→ Registering HITL handoffs...
  Config: {'mandatory_checkpoints': ['after_planning'], 'smart_approval': True}
  → Mandatory checkpoints: ['after_planning']
    ✓ after_planning: plan_reviewer → admin → control
  → Smart approval enabled with criteria: {'escalate_keywords': ['delete']}
    ✓ Smart approval conditions added to control and engineer agents
  ✓ HITL handoffs configured
============================================================
```

### Verify Handoffs
```python
# After CMBAgent initialization
engineer = cmbagent.get_agent_object_from_name('engineer')
print("Engineer handoffs:", engineer.agent.handoffs)
```

---

## Migration Guide

### Old Way (WebSocket Only)
```python
control_config = HITLControlPhaseConfig(
    approval_mode='before_step',
    allow_step_skip=True,
)
```

### New Way (WebSocket + AG2)
```python
control_config = HITLControlPhaseConfig(
    # Keep existing WebSocket approval
    approval_mode='before_step',
    allow_step_skip=True,

    # Add AG2 handoffs
    use_ag2_handoffs=True,
    ag2_smart_approval=True,
    ag2_smart_criteria={'escalate_keywords': ['delete', 'production']},
)
```

**Result:** No breaking changes, additive enhancement!

---

## Common Patterns

### Pattern 1: Research Workflow
```python
# Planning: Must review plan
# Execution: Catch destructive operations
planning_config = HITLPlanningPhaseConfig(
    use_ag2_handoffs=True,
    ag2_mandatory_checkpoints=['after_planning'],
)

control_config = HITLControlPhaseConfig(
    use_ag2_handoffs=True,
    ag2_smart_approval=True,
    ag2_smart_criteria={
        'escalate_keywords': ['delete', 'remove', 'clear'],
    }
)
```

### Pattern 2: Production Deployment
```python
# High security: approve everything critical
control_config = HITLControlPhaseConfig(
    approval_mode='before_step',
    use_ag2_handoffs=True,
    ag2_mandatory_checkpoints=['before_file_edit', 'before_execution', 'before_deploy'],
    ag2_smart_approval=True,
    ag2_smart_criteria={'escalate_keywords': ['production', 'deploy', 'release']},
)
```

### Pattern 3: Autonomous with Safety Net
```python
# No structured approvals, but catch risky operations
control_config = HITLControlPhaseConfig(
    approval_mode='on_error',  # Only approve on errors
    use_ag2_handoffs=True,
    ag2_smart_approval=True,
    ag2_smart_criteria={'escalate_keywords': ['delete', 'production']},
)
```

---

## FAQ

**Q: Do I need to change existing code?**
A: No! The new fields default to `use_ag2_handoffs=False`. Existing code works unchanged.

**Q: Can I use AG2 handoffs without WebSocket approval?**
A: Yes! Set `approval_mode='never'` and use only AG2 handoffs:
```python
HITLControlPhaseConfig(
    approval_mode='never',
    use_ag2_handoffs=True,
    ag2_smart_approval=True,
)
```

**Q: What's the difference between WebSocket and AG2 approval?**
A:
- **WebSocket:** Phase-level, structured, UI-based
- **AG2:** Agent-level, dynamic, conversation-based

**Q: Can agents bypass mandatory checkpoints?**
A: No! Mandatory checkpoints use `set_after_work()` which is enforced by AG2.

**Q: How do I know when smart approval triggers?**
A: Enable debug mode to see handoff decisions in real-time.

**Q: Can I configure different checkpoints per step?**
A: Currently, checkpoints apply to all steps. For per-step control, use WebSocket approval mode.

---

## Next Steps

1. **Test basic integration:** Enable `use_ag2_handoffs=True` with mandatory checkpoints
2. **Try smart approval:** Add keywords relevant to your domain
3. **Tune criteria:** Adjust after observing what triggers escalations
4. **Combine both systems:** Use WebSocket for structure, AG2 for dynamics
5. **Monitor and refine:** Use debug mode to optimize configuration

---

## See Also

- **Handoffs README:** `cmbagent/handoffs/README.md`
- **Quick Reference:** `docs/HITL_HANDOFFS_QUICKREF.md`
- **Refactor Guide:** `docs/HANDOFFS_REFACTOR_GUIDE.md`
- **Complete Summary:** `docs/HANDOFFS_COMPLETE_SUMMARY.md`

---

**Status:** ✅ Integrated and ready to use!
**Breaking Changes:** ❌ None
**Backward Compatible:** ✅ Yes
