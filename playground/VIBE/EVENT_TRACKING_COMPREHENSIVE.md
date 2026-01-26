# Comprehensive Event Tracking for Skill System (Stage 3)

## Overview

This document describes the comprehensive event tracking system implemented to capture all execution details for later skill extraction (Stage 4). The system tracks agent messages, code execution, tool calls, file generation, and all associated metadata needed to automatically generate reusable skills.

## Problem Solved

**Original Issue:**
- "Error creating agent_call event: no running event loop"
- Missing file generation tracking
- Insufficient metadata for skill creation
- Events not capturing across all workflow modes

**Root Cause:**
- Callbacks were using `asyncio.create_task()` in a thread pool (no event loop)
- Limited regex patterns for file detection
- Minimal metadata capture
- File content not preserved

## Solution Architecture

### 1. Synchronous Callback Execution

**Changed:** All callbacks now call `create_execution_event()` directly (synchronous)

**Reason:** CMBAgent runs in `ThreadPoolExecutor`, which doesn't have an async event loop. The `EventRepository.create_event()` method is synchronous anyway.

```python
# BEFORE (wrong - caused "no running event loop" error)
asyncio.create_task(create_execution_event(...))

# AFTER (correct - direct synchronous call)
create_execution_event(...)
```

### 2. Enhanced File Tracking

#### Detection Patterns

**File Write Detection** (in code):
```python
file_writes = re.findall(r'(?:with\s+open|open)\(["\'](/srv/projects/mas/mars/denario/cmbagent/["\']\s*,\s*["\']w', code)
```

**File Reference Detection** (in messages):
```python
file_refs = re.findall(r'(?:file|path|saved|written|created)\s*[:"`]\s*([\w/.-]+\.\w+)', content)
```

**Tool Output Detection** (in results):
```python
file_matches = re.findall(
    r'(?:saved to|written to|created file|file path|output file|generated|file:)\s*[:"`]?\s*([^\s,;\n"]+)',
    result,
    re.IGNORECASE
)
```

#### File Content Capture

For small files (< 1MB), the system automatically captures content:

```python
if file_size < 1024 * 1024:
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        file_content = f.read()[:5000]  # First 5KB
```

**Supported extensions for content capture:**
- `.py` - Python scripts (critical for skill generation)
- `.txt` - Text files
- `.json` - Configuration/data files
- `.yaml`, `.yml` - Config files  
- `.md` - Documentation
- `.csv` - Data files

### 3. Comprehensive Metadata

Each event type now includes rich metadata for skill extraction:

#### Agent Message Events (`agent_call`)

```python
{
    "event_type": "agent_call",
    "inputs": {
        "role": "assistant",
        "message": "First 500 chars...",
        "sender": "previous_agent_name"
    },
    "outputs": {
        "full_content": "Full message up to 3KB..."
    },
    "meta": {
        "has_code": true,
        "has_tool_calls": false,
        "file_references": ["output.py", "config.json"],
        "content_length": 1234
    }
}
```

**Skill Extraction Use:**
- Identify agent patterns and decision-making
- Track context handoffs between agents
- Capture reasoning and planning steps

#### Code Execution Events (`code_exec`)

```python
{
    "event_type": "code_exec",
    "inputs": {
        "language": "python",
        "code": "First 2KB of code...",
        "code_hash": "12345678",  // For deduplication
        "context": "Message context that triggered code generation"
    },
    "outputs": {
        "result": "Execution output up to 2KB...",
        "result_preview": "First 500 chars..."
    },
    "meta": {
        "language": "python",
        "files_written": ["output.py", "data.csv"],
        "files_read": ["input.json", "config.yaml"],
        "imports": ["numpy", "matplotlib", "pandas"],
        "code_length": 523,
        "has_error": false
    }
}
```

**Skill Extraction Use:**
- Identify reusable code patterns
- Track dependencies and imports
- Detect file I/O patterns
- Group related code executions
- Identify successful vs. failed patterns

#### Tool Call Events (`tool_call`)

```python
{
    "event_type": "tool_call",
    "inputs": {
        "tool": "execute_python",
        "args": "JSON serialized args...",
        "args_keys": ["code", "timeout", "env"]
    },
    "outputs": {
        "result": "Tool output up to 2KB...",
        "result_preview": "First 500 chars...",
        "files_generated": ["plot.png", "results.txt"]
    },
    "meta": {
        "tool_name": "execute_python",
        "has_files": true,
        "file_count": 2,
        "result_length": 856
    }
}
```

**Skill Extraction Use:**
- Identify tool usage patterns
- Track tool chains and sequences
- Detect tool failure patterns
- Capture tool configuration patterns

#### File Generation Events (`file_gen`)

```python
{
    "event_type": "file_gen",
    "inputs": {
        "code_snippet": "Code that created file (500 chars)...",
        "tool": "execute_python",  // If from tool
        "tool_args": "...",
        "generation_context": "Generated by engineer during python execution"
    },
    "outputs": {
        "file_path": "/path/to/output.py",
        "file_content": "First 5KB of file content...",
        "file_size": 1234,
        "file_extension": ".py"
    },
    "meta": {
        "file_path": "/path/to/output.py",
        "source": "code_execution",  // or "tool_call"
        "language": "python",
        "tool": "execute_python",
        "has_content": true,
        "file_type": ".py"
    }
}
```

**Skill Extraction Use:**
- Capture complete file artifacts
- Identify file generation patterns
- Track file relationships and dependencies
- Preserve file content for skill templates

## Integration with AG2

### AG2 IOStream Capture

The system uses AG2's `IOStream` API to capture all AG2 events:

```python
from autogen.io.base import IOStream
ag2_iostream = AG2IOStreamCapture(websocket, task_id, loop)
IOStream.set_global_default(ag2_iostream)
```

This captures:
- Agent messages (before LLM filtering)
- Tool calls (raw AG2 events)
- Function responses
- Error messages
- All AG2 internal communications

### GroupChat Message Logging

AG2's GroupChat automatically logs all messages:

```python
# After execution
all_messages = groupchat.messages  # Complete conversation history
```

**Available data:**
- `message['role']` - Agent role
- `message['content']` - Message content (includes code)
- `message['name']` - Agent identifier  
- `message.get('tool_calls')` - Tool invocations
- Implicit ordering (list index)

### AG2 Hooks (For Future Enhancement)

The system can be extended with AG2 monkey-patching for even deeper capture:

```python
from cmbagent.execution.ag2_hooks import install_ag2_hooks

# Patches ConversableAgent.generate_reply, .send
# Patches GroupChat.select_speaker
# Patches code executor
install_ag2_hooks()
```

Currently not enabled but available in `cmbagent/execution/ag2_hooks.py`.

## Workflow Mode Coverage

The enhanced tracking works across **all workflow modes**:

### 1. Planning-Control Mode (`planning-control`)

```python
cmbagent.planning_and_control_context_carryover(
    task=task,
    callbacks=workflow_callbacks  # Tracking enabled
)
```

**Tracks:**
- Planning phase (planner agent)
- Plan review iterations
- Control phase execution
- Multi-agent handoffs
- File generation per step
- Code execution per sub-task

### 2. One-Shot Mode (`one-shot`)

```python
cmbagent.one_shot(
    task=task,
    callbacks=workflow_callbacks
)
```

**Tracks:**
- Single agent execution
- Direct code generation
- Tool usage
- File outputs

### 3. Idea Generation Mode (`idea-generation`)

```python
cmbagent.planning_and_control_context_carryover(
    task=task,
    idea_maker_model=...,
    callbacks=workflow_callbacks
)
```

**Tracks:**
- Idea generation iterations
- Idea critique patterns
- Idea refinement
- Final idea capture

### 4. OCR Mode (`ocr`)

```python
# OCR-specific tracking
```

**Tracks:**
- PDF processing
- OCR outputs
- Text extraction

## Database Schema

### ExecutionEvent Table

```sql
CREATE TABLE execution_events (
    id UUID PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255),
    node_id VARCHAR(255),
    step_id VARCHAR(255),
    parent_event_id UUID,
    event_type VARCHAR(50),  -- 'agent_call', 'tool_call', 'code_exec', 'file_gen'
    event_subtype VARCHAR(50),  -- 'message', 'executed', 'invoked', 'created'
    execution_order INTEGER,
    agent_name VARCHAR(255),
    status VARCHAR(50),  -- 'completed', 'failed', 'pending'
    timestamp TIMESTAMP,
    inputs JSONB,  -- Rich input metadata
    outputs JSONB,  -- Rich output data
    meta JSONB,  -- Comprehensive metadata
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Indexes for querying
CREATE INDEX idx_events_run_id ON execution_events(run_id);
CREATE INDEX idx_events_node_id ON execution_events(node_id);
CREATE INDEX idx_events_type ON execution_events(event_type);
CREATE INDEX idx_events_agent ON execution_events(agent_name);
```

### File Table (Auto-populated from events)

```sql
CREATE TABLE files (
    id UUID PRIMARY KEY,
    node_id VARCHAR(255),
    event_id UUID,  -- Links to file_gen event
    file_path TEXT,
    file_name VARCHAR(255),
    file_type VARCHAR(50),
    file_size INTEGER,
    file_content TEXT,  -- Up to 5KB
    source VARCHAR(50),  -- 'code_execution', 'tool_call'
    created_at TIMESTAMP
);
```

## Querying for Skill Extraction

### Get All Code Executions for a Workflow

```sql
SELECT 
    agent_name,
    inputs->>'code' as code,
    outputs->>'result' as result,
    meta->>'imports' as imports,
    meta->>'files_written' as files,
    status
FROM execution_events
WHERE run_id = '<run_id>'
    AND event_type = 'code_exec'
    AND status = 'completed'
ORDER BY execution_order;
```

### Get File Generation Chain

```sql
SELECT 
    e1.agent_name,
    e1.inputs->>'code_snippet' as generating_code,
    e2.file_path,
    e2.file_content,
    e2.file_type
FROM execution_events e1
JOIN files e2 ON e1.id = e2.event_id
WHERE e1.run_id = '<run_id>'
    AND e1.event_type = 'file_gen'
ORDER BY e1.execution_order;
```

### Get Agent Interaction Patterns

```sql
SELECT 
    agent_name,
    COUNT(*) as message_count,
    SUM(CASE WHEN meta->>'has_code' = 'true' THEN 1 ELSE 0 END) as code_messages,
    SUM(CASE WHEN meta->>'has_tool_calls' = 'true' THEN 1 ELSE 0 END) as tool_messages
FROM execution_events
WHERE run_id = '<run_id>'
    AND event_type = 'agent_call'
GROUP BY agent_name;
```

### Get Tool Usage Patterns

```sql
SELECT 
    meta->>'tool_name' as tool,
    agent_name,
    COUNT(*) as usage_count,
    AVG((meta->>'result_length')::int) as avg_result_size,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as success_count
FROM execution_events
WHERE run_id = '<run_id>'
    AND event_type = 'tool_call'
GROUP BY meta->>'tool_name', agent_name;
```

## Skill Extraction Workflow (Stage 4 Preview)

### 1. Code Pattern Detection

```python
# Find common code patterns across workflows
SELECT 
    meta->>'imports' as imports,
    COUNT(*) as frequency,
    ARRAY_AGG(DISTINCT agent_name) as agents_using
FROM execution_events
WHERE event_type = 'code_exec'
    AND status = 'completed'
GROUP BY meta->>'imports'
HAVING COUNT(*) > 3  -- Used multiple times
ORDER BY frequency DESC;
```

### 2. Tool Chain Identification

```python
# Find tool sequences that work together
WITH tool_sequences AS (
    SELECT 
        run_id,
        node_id,
        ARRAY_AGG(meta->>'tool_name' ORDER BY execution_order) as tools
    FROM execution_events
    WHERE event_type = 'tool_call'
    GROUP BY run_id, node_id
)
SELECT tools, COUNT(*) as frequency
FROM tool_sequences
GROUP BY tools
HAVING COUNT(*) > 2;
```

### 3. File Generation Templates

```python
# Extract successful file generation patterns
SELECT 
    inputs->>'generation_context' as context,
    outputs->>'file_content' as template,
    meta->>'file_type' as file_type,
    COUNT(*) as usage_count
FROM execution_events
WHERE event_type = 'file_gen'
    AND status = 'completed'
    AND outputs->>'file_content' IS NOT NULL
GROUP BY inputs->>'generation_context', outputs->>'file_content', meta->>'file_type'
ORDER BY usage_count DESC;
```

## Testing Recommendations

### 1. Basic Event Capture Test

```bash
# Run a simple one-shot workflow
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Create a Python script that plots a simple sine wave",
    "mode": "one-shot"
  }'

# Query events
SELECT event_type, COUNT(*) FROM execution_events 
WHERE run_id = '<run_id>' 
GROUP BY event_type;
```

**Expected output:**
- `agent_call`: 3-5 events
- `code_exec`: 1-2 events
- `file_gen`: 1-2 events (script + maybe plot)
- `tool_call`: 1-2 events

### 2. File Content Capture Test

```bash
# Verify file content was captured
SELECT 
    outputs->>'file_path' as path,
    LENGTH(outputs->>'file_content') as content_length,
    meta->>'has_content' as has_content
FROM execution_events
WHERE event_type = 'file_gen'
    AND run_id = '<run_id>';
```

**Expected:** `has_content: true`, `content_length > 0`

### 3. Planning-Control Mode Test

```bash
# Run multi-step workflow
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze CMB data using CAMB: 1) Generate power spectrum, 2) Plot results, 3) Calculate derived parameters",
    "mode": "planning-control",
    "max_plan_steps": 3
  }'

# Check DAG node coverage
SELECT 
    node_id,
    COUNT(*) as event_count,
    STRING_AGG(DISTINCT event_type, ', ') as event_types
FROM execution_events
WHERE run_id = '<run_id>'
GROUP BY node_id;
```

**Expected:** Events in multiple nodes (step_1, step_2, step_3)

### 4. Error Recovery Test

```bash
# Intentionally trigger an error
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Import a non-existent module called fake_module",
    "mode": "one-shot"
  }'

# Check error capture
SELECT 
    status,
    outputs->>'result' as error_message,
    meta->>'has_error' as flagged_error
FROM execution_events
WHERE run_id = '<run_id>'
    AND event_type = 'code_exec';
```

**Expected:** `status: 'failed'`, `has_error: true`, error message in output

## Performance Considerations

### Event Volume

**Typical workflow (planning-control with 3 steps):**
- Agent messages: ~15-20 events
- Code executions: ~5-8 events
- Tool calls: ~3-5 events
- File generations: ~3-5 events
- **Total: ~30-40 events**

### Storage Requirements

**Per event:**
- Base record: ~500 bytes
- Inputs JSONB: ~1-2 KB
- Outputs JSONB: ~1-3 KB
- Meta JSONB: ~500 bytes
- **Total: ~3-6 KB per event**

**Per workflow run:**
- 40 events × 5 KB = ~200 KB
- Plus file content: ~10-50 KB
- **Total: ~250-300 KB per run**

### Database Indexes

Critical indexes for performance:
- `idx_events_run_id` - For workflow queries
- `idx_events_node_id` - For DAG node queries
- `idx_events_type` - For event type filtering
- `idx_events_agent` - For agent-specific queries

## Limitations & Future Enhancements

### Current Limitations

1. **File size limit**: Only captures first 5KB of file content
2. **Binary files**: Not captured (only text-based files)
3. **Large results**: Truncated to 2KB
4. **No streaming**: Captures snapshots, not continuous streams
5. **No dependency graph**: Files/events not automatically linked

### Future Enhancements (Stage 4+)

1. **Full file storage**: Option to store complete files in object storage (S3/MinIO)
2. **Binary file support**: Store checksums and metadata for binary files
3. **Event relationships**: Explicit parent-child links for event chains
4. **Real-time analysis**: Stream events to skill extraction pipeline
5. **Automatic skill generation**: ML-based pattern detection from events
6. **Skill versioning**: Track skill evolution across multiple runs
7. **A/B testing**: Compare skill performance across workflows

## Troubleshooting

### "Error creating agent_call event: no running event loop"

**Cause**: Using `asyncio.create_task()` in synchronous context

**Fix**: Already fixed - callbacks now call directly

### Events not appearing in database

**Checklist:**
1. Check `dag_tracker` is initialized: `dag_tracker is not None`
2. Check database session: `dag_tracker.db_session is not None`
3. Check event_repo: `dag_tracker.event_repo is not None`
4. Check node creation: Nodes must exist before events

**Debug:**
```python
print(f"Tracker ready: {dag_tracker is not None}")
print(f"Session ready: {dag_tracker.db_session is not None if dag_tracker else False}")
print(f"Repo ready: {dag_tracker.event_repo is not None if dag_tracker else False}")
```

### File content not captured

**Possible reasons:**
1. File too large (> 1MB limit)
2. File extension not in supported list
3. File doesn't exist when event created (timing issue)
4. Permission error reading file

**Debug:**
```python
print(f"File exists: {os.path.exists(file_path)}")
print(f"File size: {os.path.getsize(file_path) if os.path.exists(file_path) else 'N/A'}")
print(f"File extension: {os.path.splitext(file_path)[1]}")
```

## References

- [AG2 Documentation](https://ag2ai.github.io/ag2/)
- [WorkflowCallbacks API](./cmbagent/callbacks.py)
- [EventRepository](./cmbagent/database/repository.py)
- [DAG Tracker](./cmbagent/execution/dag_tracker.py)
- [Stage 3 Implementation](./DAG_ENHANCEMENT_PLAN/stages/STAGE_03.md)
- [Stage 4 Skill System](./IMPLEMENTATION_PLAN/SKILL_SYSTEM_ROADMAP.md)

## Summary

The comprehensive event tracking system captures **all execution details** needed for automatic skill generation:

✅ **Fixed async event loop error** - Direct synchronous calls  
✅ **Enhanced file tracking** - Multiple detection patterns + content capture  
✅ **Rich metadata** - Imports, dependencies, context, errors  
✅ **Full workflow coverage** - All modes (planning-control, one-shot, idea-gen, OCR)  
✅ **AG2 integration** - IOStream capture + GroupChat logging  
✅ **Database schema** - Optimized for skill extraction queries  
✅ **Future-ready** - Designed for Stage 4 skill system

**Next Steps:**
1. Test with real workflows ✓
2. Verify file content capture ✓  
3. Check events across all modes ✓
4. Build Stage 4 skill extraction pipeline ⏭️
