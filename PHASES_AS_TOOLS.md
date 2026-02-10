# Phases as Tools - Ultimate Composability

## The Vision

**What if phases could invoke each other as tools?**

This creates ultimate flexibility where:
- Agents orchestrate workflows dynamically
- Phases are composable building blocks
- Workflows emerge from agent reasoning, not hardcoded sequences

## Current Architecture (Rigid)

```
Workflow Definition
  ↓
Phase 1: Research
  ↓
Phase 2: Planning
  ↓
Phase 3: Execution
  ↓
Done
```

**Problems:**
- Sequence is hardcoded
- Can't adapt to task needs
- No branching or conditionals
- Can't reuse phases in different contexts

## New Architecture (Fluid)

```
Agent with Phase Tools
  ↓
Agent analyzes task
  ↓
Agent invokes: research_phase("topic")
  ↓
Agent decides: needs planning
  ↓
Agent invokes: planning_phase(task)
  ↓
Agent decides: execute specific steps
  ↓
Agent invokes: execution_phase(plan)
  ↓
Agent decides: verify quality
  ↓
Agent invokes: review_phase(code)
  ↓
Done
```

**Benefits:**
- Sequence emerges from reasoning
- Adapts to task complexity
- Can branch, loop, skip phases
- Phases reusable everywhere

## Powerful Examples

### Example 1: Adaptive Workflow

```
User: "Build a REST API for user management"

Agent [analyzes]: This is complex, need research first
Agent [calls]: invoke_research_phase("REST API best practices", depth="quick")
Agent [reads results]: Okay, understood patterns

Agent [decides]: Need structured approach
Agent [calls]: invoke_planning_phase("Build user management API", max_steps=5)
Agent [gets plan with 5 steps]

Agent [decides]: Execute plan
Agent [calls]: invoke_execution_phase(plan, mode="sequential")
Agent [steps execute one by one]

Agent [decides]: Should verify correctness
Agent [calls]: invoke_testing_phase("./src/api", test_types=["unit", "integration"])
Agent [gets test results]: 2 tests failing

Agent [decides]: Need to fix issues
Agent [calls]: invoke_copilot_phase("Fix failing tests", mode="autonomous")
Agent [fixes applied]

Agent [decides]: Re-run tests
Agent [calls]: invoke_testing_phase("./src/api")
Agent [gets results]: All passing!

Agent [decides]: Generate API docs
Agent [calls]: invoke_documentation_phase("./src/api", doc_type="api")
Agent [docs generated]

Agent: "Done! Built user management API with tests and documentation."
```

**Notice:** The agent dynamically chose:
- Research first
- Then plan
- Then execute
- Saw test failures → invoked copilot to fix
- Re-ran tests
- Generated docs
All without hardcoded workflow!

### Example 2: Branching Workflow

```
User: "Optimize the database queries"

Agent [analyzes]: Should we research first or dive in?
Agent [decides]: Check current performance first

Agent [calls]: invoke_research_phase("current db performance", depth="quick")
Agent [findings]: Performance is bad, multiple issues

Agent [decides]: Two parallel approaches
Thread 1: invoke_research_phase("database optimization techniques")
Thread 2: invoke_research_phase("query profiling tools")

Agent [consolidates findings]

Agent [decides]: Need expert plan
Agent [calls]: invoke_planning_phase("Optimize DB with profiling + indexing")

Agent [decides]: Execute and monitor
Agent [calls]: invoke_execution_phase(plan, mode="sequential")

Agent [after each step]:
  → invoke_testing_phase("db_tests")
  → Check performance metrics
  → If improved enough: stop
  → Else: continue

Agent: "Optimized! 3x performance improvement."
```

**Notice:** The agent:
- Decided to check first
- Ran parallel research
- Created plan based on findings
- Monitored after each step
- Stopped when goal achieved

### Example 3: Phase Chaining

```
User: "Research quantum computing and create a comprehensive guide"

Agent [decides]: This is multi-phase workflow
Agent [calls]: chain_phases([
    {
        "phase": "deep_research",
        "topic": "quantum computing fundamentals",
        "focus_areas": ["qubits", "superposition", "entanglement"]
    },
    {
        "phase": "research",
        "query": "quantum computing applications",
        "depth": "deep"
    },
    {
        "phase": "planning",
        "task": "Structure comprehensive quantum computing guide"
    },
    {
        "phase": "execution",
        "plan": "$previous"  # Use plan from planning phase
    },
    {
        "phase": "review",
        "target": "guide content",
        "criteria": ["accuracy", "completeness", "clarity"]
    },
    {
        "phase": "documentation",
        "target": "final guide",
        "doc_type": "user_guide"
    }
], pass_context=True)
```

**Result:** Each phase feeds into the next automatically!

### Example 4: Error Recovery

```
User: "Implement feature X"

Agent [calls]: invoke_planning_phase("Implement feature X")
Agent [gets plan]

Agent [calls]: invoke_execution_phase(plan)
Agent [step 3 fails with error]

Agent [decides]: Error occurred, need to understand
Agent [calls]: invoke_research_phase("error message: ${error}")
Agent [gets solution]

Agent [decides]: Revise plan based on findings
Agent [calls]: invoke_planning_phase("Implement feature X with ${solution}")
Agent [gets updated plan]

Agent [calls]: invoke_execution_phase(updated_plan)
Agent [all steps succeed]

Agent: "Feature X implemented (had to adjust approach after error)"
```

**Notice:** Agent handled error by:
- Researching the problem
- Revising the plan
- Executing revised plan

## Implementation Architecture

### 1. Phase Tool Functions (✅ Created)

`cmbagent/functions/phase_tools.py`:
- Each phase has a tool function
- Tool returns JSON with phase invocation request
- Agent can call any phase as a tool

### 2. Phase Executor (TODO)

```python
class PhaseOrchestrator:
    """Executes phases requested by agent tools."""

    async def execute_phase_tool_call(self, tool_call, context):
        """Execute a phase based on tool call."""
        action = json.loads(tool_call.result)
        phase_name = action["phase"]

        # Get phase class from registry
        phase_class = PHASE_REGISTRY[phase_name]

        # Create phase instance with config from tool call
        phase_config = self._build_phase_config(action)
        phase = phase_class(phase_config)

        # Execute phase
        result = await phase.execute(context)

        # Return result to agent
        return result
```

### 3. Context Passing (TODO)

```python
class ContextPipeline:
    """Manages context flow between phases."""

    def __init__(self):
        self.phase_results = {}

    def store_result(self, phase_name, result):
        """Store phase result for later reference."""
        self.phase_results[phase_name] = result

    def resolve_references(self, config):
        """Resolve $previous and ${var} references."""
        # Replace "$previous" with last phase's output
        # Replace "${var}" with specific stored values
        return resolved_config
```

### 4. Agent with Phase Tools (TODO)

```python
# In the orchestrator agent setup
def setup_orchestrator_agent(cmbagent_instance):
    """Setup an agent that can orchestrate phases."""
    from cmbagent.functions.phase_tools import PHASE_TOOLS, get_phase_tools_description

    orchestrator = cmbagent_instance.get_agent_from_name('orchestrator')

    # Register all phase tools
    for tool in PHASE_TOOLS:
        register_function(tool, caller=orchestrator, executor=orchestrator)

    # Update instructions
    orchestrator.system_message += get_phase_tools_description()
```

## Real-World Use Cases

### Use Case 1: Adaptive Development

```
User: "Add a new feature"

If simple:
  → invoke_copilot_phase("add feature")

If moderate:
  → invoke_planning_phase("add feature")
  → invoke_execution_phase(plan)

If complex:
  → invoke_research_phase("similar features")
  → invoke_deep_research_phase("design patterns")
  → invoke_planning_phase("add feature with patterns")
  → invoke_review_phase("plan")  # validate plan
  → invoke_execution_phase(plan)
  → invoke_testing_phase(code)
  → invoke_review_phase("implementation")
  → invoke_documentation_phase(code)
```

### Use Case 2: Research Pipeline

```
User: "Research topic X and create action plan"

invoke_research_phase("topic X overview")
→ invoke_deep_research_phase("topic X", focus=key_areas)
→ invoke_research_phase("industry applications")
→ invoke_planning_phase("create action plan from research")
→ invoke_documentation_phase("research summary + plan")
```

### Use Case 3: Iterative Development

```
User: "Build and refine feature Y"

Loop:
  1. invoke_planning_phase or invoke_copilot_phase
  2. invoke_execution_phase
  3. invoke_testing_phase
  4. invoke_review_phase

  If review says needs work:
    → invoke_research_phase("how to improve X")
    → GOTO 1 with new insights

  Else:
    → invoke_documentation_phase
    → Done
```

### Use Case 4: Quality Pipeline

```
User: "Implement feature with high quality bar"

chain_phases([
    {"phase": "research", "query": "feature requirements"},
    {"phase": "planning", "task": "implement with quality"},
    {"phase": "review", "target": "plan"},  # Review plan first!
    {"phase": "execution", "plan": "$previous"},
    {"phase": "testing", "code_path": "$code"},
    {"phase": "review", "target": "code", "criteria": ["security", "performance"]},
    {"phase": "documentation", "target": "$code"}
])
```

## Benefits of Phases as Tools

### 1. **Ultimate Flexibility**
- Workflows not hardcoded
- Agent adapts to task
- Can branch, loop, retry

### 2. **Composability**
- Phases are reusable
- Mix and match freely
- Build complex from simple

### 3. **Intelligence**
- Agent reasons about what's needed
- Learns from results
- Adjusts approach

### 4. **Natural Flow**
- No rigid sequences
- Emerges from task requirements
- Mirrors human problem-solving

### 5. **Error Handling**
- Can recover from failures
- Research errors
- Retry with new approach

### 6. **Efficiency**
- Only run needed phases
- Skip unnecessary steps
- Parallel when possible

## Comparison

### Hardcoded Workflow
```python
workflow = [
    ResearchPhase(),
    PlanningPhase(),
    ExecutionPhase(),
]

# MUST run all three, in order, no exceptions
```

**Rigid, Inefficient, Cannot Adapt**

### Phases as Tools
```python
agent_with_phase_tools.solve(task)

# Agent decides:
# - Which phases to invoke
# - In what order
# - How many times
# - When to stop
```

**Flexible, Efficient, Adaptive**

## Implementation Status

✅ **Phase tool functions created**
- All major phases have tool wrappers
- Proper annotations and docs
- Chain function for sequences

⬜ **Phase orchestrator needed**
- Execute phases from tool calls
- Manage context between phases
- Handle errors and retries

⬜ **Context pipeline needed**
- Store phase results
- Resolve $previous references
- Pass data between phases

⬜ **Agent setup needed**
- Register phase tools with agent
- Update agent instructions
- Enable dynamic orchestration

⬜ **Testing needed**
- Test single phase invocation
- Test phase chaining
- Test context passing
- Test error recovery

## Next Steps

1. ✅ Design architecture
2. ✅ Create phase tool functions
3. ⬜ Implement PhaseOrchestrator
4. ⬜ Implement ContextPipeline
5. ⬜ Setup orchestrator agent
6. ⬜ Test workflows
7. ⬜ Documentation

## Vision

Imagine:

```
User: "Build a production-ready authentication system"

Agent [thinks]: This is major undertaking
Agent [decides]: Multi-phase approach

Phase 1: Research
  → invoke_deep_research_phase("auth systems",
      focus=["JWT", "OAuth", "security"])
  → invoke_research_phase("industry standards")

Phase 2: Design
  → invoke_planning_phase("design auth system",
      informed_by=research_results)
  → invoke_review_phase("architecture plan")
  → If issues: research more, revise

Phase 3: Build
  → invoke_execution_phase(approved_plan, mode="sequential")
  → For each step:
      - invoke_testing_phase(code)
      - invoke_review_phase(code, criteria=["security"])
      - Fix issues before next step

Phase 4: Verify
  → invoke_testing_phase(entire_system, types=all)
  → invoke_review_phase("full system", criteria=production_ready)

Phase 5: Document
  → invoke_documentation_phase(system, type="api")
  → invoke_documentation_phase(system, type="user_guide")
  → invoke_documentation_phase(system, type="technical")

Agent: "Production-ready auth system complete!"
```

**The agent orchestrated a complex, multi-phase workflow autonomously!**

## Summary

**Phases as Tools = Ultimate Composability**

- ✅ Flexible workflows
- ✅ Adaptive to task
- ✅ Reusable phases
- ✅ Intelligent orchestration
- ✅ Error recovery
- ✅ Natural and fluent

This is the future of agent systems - not rigid workflows, but intelligent orchestration of composable capabilities.
