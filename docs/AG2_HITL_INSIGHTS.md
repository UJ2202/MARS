# AG2 HITL and Group Chat Insights

## Summary of AG2 Official Documentation

Based on the official AG2 documentation reviewed on January 29, 2026:

---

## Key Insights from AG2 Documentation

### 1. Human-in-the-Loop Core Concepts

#### The Three Human Input Modes

AG2 provides three `human_input_mode` settings for `ConversableAgent`:

| Mode | Behavior | Use Case |
|------|----------|----------|
| **ALWAYS** | Agent uses human input as its response after every message | Maximum oversight, teaching, critical decisions |
| **TERMINATE** | Agent asks for input only when terminating | Final approval, checkpoint review |
| **NEVER** | Agent never asks for human input | Fully autonomous agents |

#### When to Use HITL (per AG2 docs)

HITL is particularly valuable when:

- **Decisions require nuanced judgment** (e.g., financial compliance, legal matters)
- **Errors could have significant consequences** (e.g., financial transactions, safety-critical systems)
- **The process benefits from subjective input** (e.g., content approval, design choices)
- **Regulatory requirements mandate human oversight** (e.g., financial services, healthcare)

#### The Medical Analogy

AG2 documentation uses a hospital analogy:
- Doctors (AI agents) handle routine examinations and tests
- Senior specialists (humans) are consulted for serious/unusual conditions
- Specialists provide final approval for critical treatments
- Combines efficiency with judgment for important decisions

---

### 2. Group Chat Orchestration Patterns

#### Core Components

1. **Agents**: Conversable agents that perform specific tasks
2. **Patterns**: Define how agents take turns and interact
   - `AutoPattern`: Manager decides next speaker based on context
   - `RoundRobinPattern`: Fixed rotation between agents
   - `RandomPattern`: Random selection
   - `ManualPattern`: Explicit manual control
3. **Handoffs**: Control how agents pass control to each other
4. **Guardrails**: Safety mechanisms for agent behavior
5. **Context Variables**: Shared state across all agents

#### Pattern Selection

The AG2 documentation shows `AutoPattern` as the recommended default:

```python
pattern = AutoPattern(
    initial_agent=triage_agent,
    agents=[agent1, agent2, agent3],
    user_agent=user,
    group_manager_args={"llm_config": llm_config}
)
```

**Benefits of AutoPattern:**
- Manager automatically selects next speaker based on context
- More natural conversation flow
- Adapts to conversation dynamics
- No need to predefine turn order

---

### 3. Comparison with CMBAgent Implementation

#### What CMBAgent Does Well

✅ **Uses AutoPattern**: CMBAgent correctly uses `AutoPattern` for swarm orchestration
✅ **Context Variables**: Implements shared context via `ContextVariables`
✅ **Handoffs**: Uses `AgentTarget` and `TerminateTarget` for control flow
✅ **Human Agent**: Has `admin` agent with appropriate settings

#### Areas Aligned with AG2 Best Practices

| AG2 Recommendation | CMBAgent Implementation | Status |
|-------------------|------------------------|--------|
| Use `ALWAYS` for human agents | `admin` agent defaults to ALWAYS | ✅ Aligned |
| Use `NEVER` for autonomous agents | Most agents use NEVER | ✅ Aligned |
| Use AutoPattern for dynamic orchestration | Uses AutoPattern | ✅ Aligned |
| Specialized agents for tasks | Planner, engineer, researcher, etc. | ✅ Aligned |
| Context variables for shared state | ContextVariables in solve() | ✅ Aligned |

---

### 4. New Insights for HITL Phases

#### Insight 1: Simpler Human Agent Pattern

AG2's financial compliance example shows a simpler pattern:

```python
# Create human agent
human = ConversableAgent(
    name="human",
    human_input_mode="ALWAYS"
)

# AI agent that works with human
ai_agent = ConversableAgent(
    name="ai_assistant",
    system_message="Your instructions here",
    human_input_mode="NEVER",
    llm_config=llm_config
)

# Start conversation
response = human.run(
    recipient=ai_agent,
    message=initial_prompt
)
```

**Key Difference from CMBAgent:**
- AG2 example uses simpler two-agent pattern for HITL
- CMBAgent uses full swarm pattern even for HITL
- Both approaches valid, but AG2 shows HITL can be simpler

#### Insight 2: Progressive Approval Pattern

AG2's financial example shows **batch approval** pattern:
1. Agent processes multiple items
2. Flags suspicious items
3. **Presents ALL flagged items at once** for approval
4. Human provides single approval for all

**Application to CMBAgent:**
- HITLControlPhase could batch steps requiring approval
- Instead of approving each step individually, batch them
- More efficient for humans

#### Insight 3: Context-Based HITL

AG2 emphasizes HITL based on **context**, not just phase boundaries:

```python
# In system message
"If it seems suspicious (e.g., amount > $10,000), ask the human agent for approval.
Otherwise, approve it automatically."
```

**Application to CMBAgent:**
- Current `approval_mode="on_error"` is context-based ✅
- Could add `approval_mode="conditional"` based on context rules
- Agent decides when to escalate based on complexity/risk

---

### 5. Enhanced HITL Patterns from AG2

#### Pattern 1: Conditional Escalation

```python
# Agent decides when to escalate based on criteria
system_message = """
Process tasks autonomously. Escalate to human if:
- Cost exceeds $10,000
- Security risk detected
- Ambiguous requirements
- Legal implications present
"""
```

**Recommendation for CMBAgent:**
- Add `approval_mode="smart"` to HITLControlPhase
- Agent uses LLM to decide when human approval needed
- More flexible than fixed before_step/after_step

#### Pattern 2: Batch Approval

```python
# Collect items requiring approval
flagged_items = []
for item in items:
    if needs_human_review(item):
        flagged_items.append(item)

# Present all at once
if flagged_items:
    human_approval = await request_batch_approval(flagged_items)
```

**Recommendation for CMBAgent:**
- Add batch approval to HITLControlPhase
- Collect multiple steps requiring approval
- Present as single approval request

#### Pattern 3: Tiered Approval

```python
# Different approval levels based on severity
if risk_level == "high":
    approval_mode = "ALWAYS"  # Approve every action
elif risk_level == "medium":
    approval_mode = "TERMINATE"  # Review final result
else:
    approval_mode = "NEVER"  # Fully autonomous
```

**Recommendation for CMBAgent:**
- Add risk assessment to phases
- Dynamically adjust approval_mode based on risk
- More granular than current modes

---

### 6. User Agent in Group Chat

AG2 documentation emphasizes the `user_agent` parameter:

```python
pattern = AutoPattern(
    initial_agent=triage_agent,
    agents=[agent1, agent2, agent3],
    user_agent=user,  # Explicitly designate human agent
    group_manager_args={"llm_config": llm_config}
)
```

**Current CMBAgent Implementation:**
- Has `admin` agent but not always explicitly designated as user_agent
- Could benefit from explicit `user_agent` designation in patterns
- Would make human agent role clearer in orchestration

---

## Recommended Enhancements

Based on AG2 documentation review:

### 1. Add Smart Approval Mode

```python
@dataclass
class HITLControlPhaseConfig:
    # ... existing fields ...
    
    approval_mode: str = "before_step"
    # ADD NEW MODE:
    smart_approval_criteria: Optional[Dict[str, Any]] = None
    # Example: {"max_cost": 10000, "security_check": True}
```

### 2. Add Batch Approval

```python
class HITLControlPhase:
    async def execute(self, context):
        # Collect steps needing approval
        pending_approvals = []
        
        for step in steps:
            if self._needs_approval(step, context):
                pending_approvals.append(step)
            else:
                await self._execute_step(step)
        
        # Batch approval request
        if pending_approvals:
            approved = await self._request_batch_approval(pending_approvals)
```

### 3. Add Risk-Based Approval

```python
class HITLControlPhase:
    def _assess_risk(self, step, context):
        """Assess risk level of step."""
        risk_score = 0
        
        if "delete" in step.task.lower():
            risk_score += 0.5
        if "production" in context.work_dir:
            risk_score += 0.3
        if step.cost_estimate > 100:
            risk_score += 0.2
            
        return risk_score
    
    async def _execute_with_dynamic_approval(self, step, context):
        """Execute with risk-based approval."""
        risk = self._assess_risk(step, context)
        
        if risk > 0.7:
            # High risk: approve before execution
            if not await self._request_approval(step):
                return self._skip_step(step)
        
        result = await self._execute_step(step)
        
        if risk > 0.4:
            # Medium risk: review after execution
            await self._request_review(step, result)
```

### 4. Explicit User Agent

```python
# In WorkflowExecutor
def _setup_approval_manager(self):
    """Setup approval manager with explicit user agent."""
    if self.approval_manager:
        # Create or get admin agent as user_agent
        admin = self._get_or_create_admin_agent()
        
        # Register as user agent in pattern
        self.pattern.user_agent = admin.agent
```

---

## AG2 Pattern Examples Applicable to CMBAgent

### Example 1: Financial Compliance Pattern

From AG2 docs - applicable to CMBAgent:

```python
# Phase configuration
HITLControlPhaseConfig(
    approval_mode="smart",
    smart_criteria={
        "escalate_if": {
            "cost_exceeds": 10000,
            "keywords": ["delete", "production", "database"],
            "complexity_score": 0.8,
        },
        "auto_approve_if": {
            "cost_below": 1000,
            "low_risk": True,
        }
    }
)
```

### Example 2: Triage Pattern

From AG2 docs - already similar to CMBAgent control agent:

```python
# CMBAgent control agent acts like triage
# Routes to engineer, researcher, or other agents
# Similar to AG2's triage example
```

---

## Conclusion

### What CMBAgent Does Well

1. ✅ Correctly uses AG2's AutoPattern
2. ✅ Proper separation of agent responsibilities
3. ✅ Good use of ContextVariables
4. ✅ Handoff mechanisms aligned with AG2

### Opportunities for Enhancement

1. 🔄 Add smart/conditional approval mode
2. 🔄 Implement batch approval for efficiency
3. 🔄 Add risk-based dynamic approval
4. 🔄 Explicitly designate user_agent in patterns
5. 🔄 Simplify HITL for simple cases (not always need full swarm)

### Priority Recommendations

**High Priority:**
1. Add `approval_mode="smart"` with context-based escalation
2. Implement batch approval for multiple steps

**Medium Priority:**
3. Add risk assessment and dynamic approval levels
4. Explicit user_agent designation

**Low Priority:**
5. Simplified HITL patterns for two-agent scenarios

---

*Based on AG2 Documentation Review*
*January 29, 2026*
*AG2 Version: 0.10.4*
