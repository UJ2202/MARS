# Enhanced DAG Workflow Capturing - Architecture Document

## Executive Summary

This document describes the architecture for capturing fine-grained execution events within CMBAgent's workflow system. The design extends the existing DAG infrastructure to provide complete traceability, artifact linkage, and skill extraction capabilities for large autonomous research workflows.

## Design Philosophy

### Core Principles

1. **Hierarchical Abstraction**
   - Keep DAG at stage/task level (coarse-grained)
   - Store execution details as events (fine-grained)
   - Link artifacts (files, messages) to both

2. **Non-Intrusive Enhancement**
   - Existing DAG system remains unchanged
   - Events captured in parallel, not in series
   - Backward compatible with non-enhanced workflows

3. **Performance First**
   - Async event writing
   - Separate tables for events and DAG
   - Efficient indexing strategy
   - Optional sampling for high-volume scenarios

4. **Mode Agnostic**
   - Same event capture for all execution modes
   - Consistent schema across one_shot, planning_and_control, etc.
   - Mode-specific metadata in JSON fields

## System Architecture

### Three-Tier Model

```
┌─────────────────────────────────────────────────────────────────┐
│                        TIER 1: STAGES                           │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│  │ Planning │───▶│ Step 0   │───▶│ Step 1   │───▶│Terminator│ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│                                                                  │
│  • DAGNode table (existing)                                     │
│  • High-level workflow structure                                │
│  • Enhanced with execution_summary in meta field                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ has_many
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TIER 2: EXECUTION EVENTS                     │
│                                                                  │
│  Event Sequence within "Step 0":                                │
│  ┌──────────────────┐                                           │
│  │ 1. planner_call  │ (start: 10:00:00, duration: 5s)          │
│  └────────┬─────────┘                                           │
│           │ parent_event_id                                     │
│  ┌────────▼─────────┐                                           │
│  │ 2. tool_call     │ (analyze_dependencies)                    │
│  └──────────────────┘                                           │
│  ┌──────────────────┐                                           │
│  │ 3. engineer_call │ (start: 10:00:05, duration: 30s)         │
│  └────────┬─────────┘                                           │
│           │ parent_event_id                                     │
│  ┌────────▼─────────┐                                           │
│  │ 4. code_exec     │ (execute: plot_data.py)                   │
│  └────────┬─────────┘                                           │
│           │ created                                             │
│  ┌────────▼─────────┐                                           │
│  │ 5. file_gen      │ (output: results.png)                     │
│  └──────────────────┘                                           │
│  ┌──────────────────┐                                           │
│  │ 6. handoff       │ (engineer → executor)                     │
│  └──────────────────┘                                           │
│  ┌──────────────────┐                                           │
│  │ 7. executor_call │ (start: 10:00:35, duration: 10s)         │
│  └──────────────────┘                                           │
│                                                                  │
│  • ExecutionEvent table (NEW)                                   │
│  • Captures all actions within a stage                          │
│  • Supports nesting (parent_event_id)                           │
│  • Links to DAGNode (node_id)                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ references
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       TIER 3: ARTIFACTS                          │
│                                                                  │
│  Files:                           Messages:                      │
│  ┌─────────────────┐             ┌──────────────────┐          │
│  │ results.png     │◄─┐          │ planner→engineer │          │
│  │ event_id: 5     │  │          │ event_id: 3      │          │
│  │ node_id: step_0 │  │          │ node_id: step_0  │          │
│  └─────────────────┘  │          └──────────────────┘          │
│  ┌─────────────────┐  │          ┌──────────────────┐          │
│  │ analysis.csv    │  │          │ engineer→executor│          │
│  │ event_id: 4     │  │          │ event_id: 6      │          │
│  │ node_id: step_0 │  │          │ node_id: step_0  │          │
│  └─────────────────┘  │          └──────────────────┘          │
│                        │                                         │
│  • Enhanced File table (event_id, node_id added)                │
│  • Enhanced Message table (event_id, node_id added)             │
│  • Full traceability: artifact → event → node → workflow        │
└─────────────────────────────────────────────────────────────────┘
```

## Database Schema Design

### New Table: execution_events

```sql
CREATE TABLE execution_events (
    -- Identity
    id VARCHAR(36) PRIMARY KEY,                    -- UUID
    
    -- Relationships
    run_id VARCHAR(36) NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    node_id VARCHAR(36) REFERENCES dag_nodes(id) ON DELETE CASCADE,
    step_id VARCHAR(36) REFERENCES workflow_steps(id) ON DELETE SET NULL,
    session_id VARCHAR(36) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    parent_event_id VARCHAR(36) REFERENCES execution_events(id) ON DELETE SET NULL,
    
    -- Event Classification
    event_type VARCHAR(50) NOT NULL,               -- agent_call, tool_call, code_exec, file_gen, handoff
    event_subtype VARCHAR(50),                     -- start, complete, error, info
    
    -- Agent Context
    agent_name VARCHAR(100),                       -- engineer, planner, executor, etc.
    agent_role VARCHAR(50),                        -- primary, helper, validator
    
    -- Timing
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,                           -- Duration in milliseconds
    
    -- Execution Data
    inputs JSON,                                   -- Input parameters, context
    outputs JSON,                                  -- Results, return values
    error_message TEXT,                            -- Error if failed
    
    -- Metadata
    metadata JSON,                                 -- Model, tokens, cost, custom data
    execution_order INTEGER NOT NULL,              -- Sequence within node
    depth INTEGER DEFAULT 0,                       -- Nesting depth (0=top level)
    
    -- Status
    status VARCHAR(50) DEFAULT 'completed',        -- pending, running, completed, failed
    
    -- Indexes
    INDEX idx_events_run_order (run_id, execution_order),
    INDEX idx_events_node_order (node_id, execution_order),
    INDEX idx_events_type_subtype (event_type, event_subtype),
    INDEX idx_events_agent (agent_name),
    INDEX idx_events_timestamp (timestamp),
    INDEX idx_events_parent (parent_event_id),
    INDEX idx_events_session_timestamp (session_id, timestamp)
);
```

### Enhanced Existing Tables

```sql
-- Add to files table
ALTER TABLE files ADD COLUMN event_id VARCHAR(36) REFERENCES execution_events(id) ON DELETE SET NULL;
ALTER TABLE files ADD COLUMN node_id VARCHAR(36) REFERENCES dag_nodes(id) ON DELETE CASCADE;
CREATE INDEX idx_files_event ON files(event_id);
CREATE INDEX idx_files_node ON files(node_id);

-- Add to messages table
ALTER TABLE messages ADD COLUMN event_id VARCHAR(36) REFERENCES execution_events(id) ON DELETE SET NULL;
ALTER TABLE messages ADD COLUMN node_id VARCHAR(36) REFERENCES dag_nodes(id) ON DELETE CASCADE;
CREATE INDEX idx_messages_event ON messages(event_id);
CREATE INDEX idx_messages_node ON messages(node_id);
```

### DAGNode Metadata Enhancement

```json
{
  "execution_summary": {
    "total_events": 47,
    "event_types": {
      "agent_call": 8,
      "tool_call": 15,
      "code_exec": 12,
      "file_gen": 8,
      "handoff": 4
    },
    "agents_involved": ["planner", "engineer", "executor"],
    "agent_call_counts": {
      "planner": 1,
      "engineer": 5,
      "executor": 2
    },
    "files_generated": 8,
    "files_by_type": {
      "code": 3,
      "data": 2,
      "plot": 3
    },
    "timing": {
      "started_at": "2026-01-19T10:00:00Z",
      "completed_at": "2026-01-19T10:05:30Z",
      "duration_seconds": 330,
      "agent_time_breakdown": {
        "planner": 5,
        "engineer": 180,
        "executor": 45
      }
    },
    "cost_summary": {
      "total_tokens": 25000,
      "total_cost_usd": 0.75,
      "by_agent": {
        "planner": {"tokens": 5000, "cost": 0.15},
        "engineer": {"tokens": 15000, "cost": 0.45},
        "executor": {"tokens": 5000, "cost": 0.15}
      }
    },
    "success_metrics": {
      "completion_rate": 1.0,
      "error_count": 0,
      "retry_count": 2
    }
  }
}
```

## Event Type Taxonomy

### Primary Event Types

1. **agent_call**
   - Subtype: `start`, `complete`, `error`
   - Captures: Agent invocation, parameters, results
   - Metadata: model, temperature, max_tokens

2. **tool_call**
   - Subtype: `execute`, `result`, `error`
   - Captures: Function name, arguments, return value
   - Metadata: execution_time, tool_name

3. **code_exec**
   - Subtype: `submit`, `running`, `complete`, `error`
   - Captures: Code snippet, language, result, stdout/stderr
   - Metadata: execution_time, exit_code

4. **file_gen**
   - Subtype: `create`, `update`, `delete`
   - Captures: File path, size, type, content_hash
   - Metadata: mime_type, encoding

5. **handoff**
   - Subtype: `initiate`, `accept`, `reject`
   - Captures: From agent, to agent, context transferred
   - Metadata: handoff_reason, context_size

6. **approval_requested**
   - Subtype: `pending`, `approved`, `rejected`, `modified`
   - Captures: Approval context, user feedback
   - Metadata: requested_at, resolved_at

7. **state_transition**
   - Subtype: `workflow`, `step`, `node`
   - Captures: From state, to state, reason
   - Metadata: transition_type, triggered_by

### Event Relationships

```python
# Example: nested events
parent_event = ExecutionEvent(
    event_type="agent_call",
    agent_name="engineer",
    # ... other fields
)

child_event_1 = ExecutionEvent(
    event_type="tool_call",
    parent_event_id=parent_event.id,
    depth=1,
    # ... other fields
)

child_event_2 = ExecutionEvent(
    event_type="code_exec",
    parent_event_id=parent_event.id,
    depth=1,
    # ... other fields
)

grandchild_event = ExecutionEvent(
    event_type="file_gen",
    parent_event_id=child_event_2.id,
    depth=2,
    # ... other fields
)
```

## AG2 Integration Strategy

### Hook Points in AG2

```python
# 1. ConversableAgent message hooks
from autogen import ConversableAgent

class EnhancedAgent(ConversableAgent):
    def __init__(self, *args, event_captor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_captor = event_captor
        
    def _process_received_message(self, message, sender, silent):
        # HOOK: Capture incoming message
        if self.event_captor:
            self.event_captor.capture_agent_message(
                agent=self.name,
                sender=sender.name,
                message=message
            )
        return super()._process_received_message(message, sender, silent)

# 2. GroupChat transition hooks
from autogen import GroupChat

original_select_speaker = GroupChat.select_speaker

def enhanced_select_speaker(self, last_speaker, selector):
    # HOOK: Capture agent transition
    next_speaker = original_select_speaker(self, last_speaker, selector)
    if hasattr(self, 'event_captor'):
        self.event_captor.capture_handoff(
            from_agent=last_speaker.name,
            to_agent=next_speaker.name
        )
    return next_speaker

GroupChat.select_speaker = enhanced_select_speaker

# 3. Code execution hooks
from autogen.code_utils import execute_code

original_execute_code = execute_code

def enhanced_execute_code(code, **kwargs):
    # HOOK: Capture code execution
    start_time = time.time()
    result = original_execute_code(code, **kwargs)
    duration = time.time() - start_time
    
    if hasattr(current_agent, 'event_captor'):
        current_agent.event_captor.capture_code_execution(
            code=code,
            result=result,
            duration_ms=int(duration * 1000)
        )
    return result
```

### Event Capture Manager

```python
class EventCaptureManager:
    """
    Central manager for capturing execution events.
    Integrates with AG2 hooks and writes to database.
    """
    
    def __init__(self, db_session, run_id, session_id):
        self.db = db_session
        self.run_id = run_id
        self.session_id = session_id
        self.current_node_id = None
        self.current_step_id = None
        self.event_buffer = []
        self.execution_order = 0
        
    def set_context(self, node_id, step_id):
        """Update current execution context"""
        self.current_node_id = node_id
        self.current_step_id = step_id
        self.execution_order = 0
        
    def capture_agent_call(self, agent_name, message, context=None):
        """Capture agent invocation"""
        event = ExecutionEvent(
            run_id=self.run_id,
            node_id=self.current_node_id,
            step_id=self.current_step_id,
            session_id=self.session_id,
            event_type="agent_call",
            event_subtype="start",
            agent_name=agent_name,
            execution_order=self.execution_order,
            inputs={"message": message, "context": context},
            timestamp=datetime.now(timezone.utc)
        )
        self.execution_order += 1
        self.event_buffer.append(event)
        return event.id
        
    def flush_events(self):
        """Write buffered events to database"""
        if self.event_buffer:
            self.db.bulk_save_objects(self.event_buffer)
            self.db.commit()
            self.event_buffer.clear()
```

## Performance Optimization

### Async Event Writing

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AsyncEventWriter:
    """Asynchronous event writer to prevent blocking execution"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.queue = asyncio.Queue()
        
    async def write_event(self, event):
        """Non-blocking event write"""
        await self.queue.put(event)
        
    async def process_queue(self):
        """Background task to process event queue"""
        while True:
            event = await self.queue.get()
            await asyncio.to_thread(self._write_to_db, event)
            self.queue.task_done()
            
    def _write_to_db(self, event):
        """Actual database write"""
        self.db.add(event)
        self.db.commit()
```

### Event Sampling

```python
class EventSampler:
    """Sample events for high-volume scenarios"""
    
    def __init__(self, sample_rate=1.0):
        self.sample_rate = sample_rate  # 1.0 = capture all, 0.1 = 10%
        
    def should_capture(self, event_type):
        """Determine if event should be captured"""
        # Always capture critical events
        if event_type in ["agent_call", "handoff", "error"]:
            return True
        
        # Sample non-critical events
        return random.random() < self.sample_rate
```

### Indexing Strategy

```sql
-- Query: "Show all events for step_2"
-- Uses: idx_events_node_order (node_id, execution_order)
SELECT * FROM execution_events 
WHERE node_id = 'step_2_node_id' 
ORDER BY execution_order;

-- Query: "Show all engineer calls in last hour"
-- Uses: idx_events_agent, idx_events_timestamp
SELECT * FROM execution_events 
WHERE agent_name = 'engineer' 
AND timestamp > NOW() - INTERVAL '1 hour';

-- Query: "Show execution tree from root event"
-- Uses: idx_events_parent (recursive query)
WITH RECURSIVE event_tree AS (
    SELECT * FROM execution_events WHERE id = 'root_event_id'
    UNION ALL
    SELECT e.* FROM execution_events e
    INNER JOIN event_tree et ON e.parent_event_id = et.id
)
SELECT * FROM event_tree ORDER BY depth, execution_order;
```

## Mode-Specific Considerations

### one_shot Mode
- Minimal events: agent_call, code_exec, file_gen
- No handoffs (single agent)
- Fast execution, low event volume

### planning_and_control Mode
- Planning phase: planner agent_call, file_gen (plan.json)
- Control phase: Multiple agent_calls, handoffs
- Step-by-step execution with clear boundaries

### planning_and_control_context_carryover Mode
- Same as planning_and_control
- Additional context transfer events
- Track context evolution across steps

### deep_research Mode (Future)
- High event volume (1000s of events)
- Requires sampling or archiving strategy
- Sub-workflows create nested event trees

## Skill Extraction Architecture

### Pattern Matching

```python
class SkillExtractor:
    """Extract reusable skills from execution patterns"""
    
    def extract_pattern(self, node_ids: List[str]) -> Skill:
        """Extract skill from successful node execution"""
        # 1. Gather all events for these nodes
        events = self.get_events_for_nodes(node_ids)
        
        # 2. Identify common sequence
        sequence = self.find_common_sequence(events)
        
        # 3. Parameterize inputs/outputs
        params = self.extract_parameters(events)
        
        # 4. Create skill template
        skill = Skill(
            name=self.generate_name(sequence),
            pattern=sequence,
            parameters=params,
            success_rate=self.calculate_success_rate(node_ids),
            avg_duration=self.calculate_avg_duration(events)
        )
        
        return skill
```

### Skill Template

```json
{
  "skill_id": "plotting_workflow_v1",
  "name": "Generate Visualization from Data",
  "description": "Standard workflow for data analysis and plotting",
  "pattern": [
    {"agent": "engineer", "action": "load_data", "params": ["${data_file}"]},
    {"agent": "engineer", "action": "analyze", "params": ["${analysis_type}"]},
    {"agent": "engineer", "action": "plot", "params": ["${plot_type}", "${output_file}"]},
    {"agent": "executor", "action": "execute", "params": ["${code_file}"]}
  ],
  "parameters": {
    "data_file": {"type": "file", "required": true},
    "analysis_type": {"type": "string", "default": "statistical"},
    "plot_type": {"type": "string", "default": "line"},
    "output_file": {"type": "file", "required": true}
  },
  "success_metrics": {
    "completion_rate": 0.95,
    "avg_duration_seconds": 45,
    "avg_cost_usd": 0.12
  },
  "extracted_from": ["run_123_node_5", "run_456_node_3", "run_789_node_7"],
  "times_used": 15,
  "last_used": "2026-01-19T10:00:00Z"
}
```

## Security and Privacy Considerations

### Sensitive Data Handling
- Event inputs/outputs may contain sensitive data
- Option to hash or redact sensitive fields
- Configurable retention policies

### Access Control
- Events inherit session isolation
- Only session owner can access events
- Admin queries require authentication

## Monitoring and Observability

### Key Metrics
- Event write latency (target: < 50ms p95)
- Event queue depth (target: < 100 events)
- Database size growth rate
- Event capture coverage (target: 100%)

### Health Checks
```python
def health_check():
    metrics = {
        "event_queue_depth": event_writer.queue.qsize(),
        "avg_write_latency_ms": event_writer.get_avg_latency(),
        "events_last_minute": count_recent_events(60),
        "database_size_mb": get_db_size(),
        "capture_rate": calculate_capture_rate()
    }
    return metrics
```

## Future Extensions

### Distributed Tracing
- OpenTelemetry integration
- Span/trace IDs for distributed workflows
- Cross-service event correlation

### Real-time Analytics
- Stream events to analytics pipeline
- Live dashboards for running workflows
- Anomaly detection

### Event Replay
- Replay workflows from events
- Debugging and testing
- Skill validation

## References
- AG2 Documentation: https://github.com/ag2ai/ag2
- SQLAlchemy Async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- OpenTelemetry: https://opentelemetry.io/
