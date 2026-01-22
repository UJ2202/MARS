# Step Model Analysis and Issues

## Current Problem

You are **CORRECT** - the current `WorkflowStep` model has a fundamental design flaw:

### Current (Incorrect) Design:
```python
class WorkflowStep(Base):
    id = Column(String(36), primary_key=True)
    step_number = Column(Integer, nullable=False)
    agent = Column(String(100), nullable=False)  # ❌ WRONG - stores single agent
    status = Column(String(50), nullable=False)
    inputs = Column(JSON, nullable=True)
    outputs = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)
```

### What's Wrong:
1. **`agent` field is misleading**: It stores a single agent name, but each step is actually executed by **multiple agents**
2. **Missing `goal` field**: Steps should have a clear goal/description, not just an agent name
3. **Agent workflow is hidden**: The actual agents working on each step are tracked in `ExecutionEvent` but the step model doesn't reflect this

## Correct Design (What It Should Be)

### WorkflowStep Should Store:
```python
class WorkflowStep(Base):
    id = Column(String(36), primary_key=True)
    step_number = Column(Integer, nullable=False)
    goal = Column(Text, nullable=False)  # ✅ STEP GOAL/DESCRIPTION
    status = Column(String(50), nullable=False)
    inputs = Column(JSON, nullable=True)
    outputs = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)
    
    # Relationships
    execution_events = relationship("ExecutionEvent", ...)  # ✅ Multiple agent executions
```

### ExecutionEvent Already Correctly Tracks Individual Agent Work:
```python
class ExecutionEvent(Base):
    id = Column(String(36), primary_key=True)
    step_id = Column(String(36), ForeignKey("workflow_steps.id"))
    agent_name = Column(String(100), nullable=True)  # ✅ CORRECT - individual agent
    agent_role = Column(String(50), nullable=True)  # primary, helper, validator
    event_type = Column(String(50), nullable=False)  # agent_call, tool_call, etc.
    inputs = Column(JSON, nullable=True)
    outputs = Column(JSON, nullable=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
```

## How It Works (Correct Architecture):

### Step 1: Research Literature
**Goal**: "Research relevant CMB papers and identify key findings"

**Agents working on this step** (tracked in ExecutionEvent):
- Event 1: `literature_researcher` (primary) - searches papers
- Event 2: `data_retriever` (helper) - downloads papers
- Event 3: `summarizer` (helper) - summarizes findings
- Event 4: `validator` (validator) - validates results

### Step 2: Analyze Data
**Goal**: "Analyze CMB power spectrum and identify anomalies"

**Agents working on this step** (tracked in ExecutionEvent):
- Event 1: `data_analyst` (primary) - performs analysis
- Event 2: `code_executor` (helper) - runs analysis scripts
- Event 3: `visualizer` (helper) - creates plots
- Event 4: `validator` (validator) - checks results

## Required Changes

### 1. Database Migration
Change `WorkflowStep.agent` to `WorkflowStep.goal`:
```sql
ALTER TABLE workflow_steps RENAME COLUMN agent TO goal;
ALTER TABLE workflow_steps ALTER COLUMN goal TYPE TEXT;
```

### 2. Update All Code References
- Replace `step.agent` with `step.goal`
- Update step creation to provide goals instead of agent names
- Update UI to display step goals properly

### 3. Query Pattern Changes
**Before (Incorrect)**:
```python
step = WorkflowStep(
    step_number=1,
    agent="literature_researcher",  # ❌ WRONG
    ...
)
```

**After (Correct)**:
```python
step = WorkflowStep(
    step_number=1,
    goal="Research relevant CMB papers",  # ✅ CORRECT
    ...
)

# Agents are tracked separately in ExecutionEvent
event = ExecutionEvent(
    step_id=step.id,
    agent_name="literature_researcher",  # ✅ CORRECT
    agent_role="primary",
    ...
)
```

## Benefits of Correct Design

1. **Clear Semantics**: Steps represent "what to do" (goals), not "who does it" (agents)
2. **Multiple Agents**: Each step can have multiple agents collaborating
3. **Agent Workflow Visibility**: ExecutionEvents show the actual agent interactions
4. **Better UI**: Can show step goals with agent workflow timeline beneath
5. **Flexibility**: Can add/remove agents from a step without changing step definition

## Current State in Database

From inspection, all 108 workflow steps in the database currently have:
- `agent` field populated (incorrect - should be `goal`)
- Some execution events with agent workflow (correct structure exists)

The ExecutionEvent structure is already correct - we just need to:
1. Rename/repurpose the `agent` column to `goal` in WorkflowStep
2. Update all code that creates/reads WorkflowStep
3. Update UI to show step goals with agent execution timeline
