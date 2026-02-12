# Durable Context System Guide

## Overview

The **DurableContext** system provides enhanced context management for copilot sessions with:
- **Deep copying** to prevent reference corruption
- **Context snapshots** for rollback capability
- **Versioning** to track changes over time  
- **Serialization** for persistence across restarts
- **Persistent vs ephemeral** data separation
- **Smart merge strategies** when integrating phase results
- **Protected keys** that cannot be overwritten

## Architecture

### Before (Simple Dict)

```python
class SwarmState:
    shared_context: Dict[str, Any] = field(default_factory=dict)  # ❌ Shallow copy issues

# Usage
orchestrator.state.shared_context['key'] = value  # ❌ Direct mutation
phase_context.shared_state = orchestrator.state.shared_context.copy()  # ❌ Shallow copy
```

**Problems:**
- Shallow copying causes nested object reference issues
- No versioning or history
- No persistence support
- Easy to accidentally overwrite critical data

### After (DurableContext)

```python
class SwarmState:
    context: DurableContext = None  # ✅ Enhanced context manager

# Usage
orchestrator.state.context.set('key', value, deep_copy=True)  # ✅ Deep copy
phase_context = orchestrator.state.context.get_phase_context()  # ✅ Independent copy
```

**Benefits:**
- Deep copying prevents corruption
- Snapshots enable rollback
- Serialization enables persistence
- Protected keys prevent accidents
- Change log for debugging

## Key Features

### 1. Deep Copying

All values are deep copied by default to prevent reference issues:

```python
# Store complex object
plan_data = {
    'steps': [{'id': 1, 'action': 'test'}],
    'metadata': {'author': 'copilot'}
}

ctx.set('plan', plan_data)  # Deep copied automatically
plan_data['steps'][0]['action'] = 'modified'  # Won't affect stored copy
```

### 2. Persistent vs Ephemeral Data

```python
# Persistent - survives phases and rounds
ctx.set('user_name', 'Alice')
ctx.set('project_root', '/srv/projects/myapp')

# Ephemeral - cleared after rounds
ctx.set_ephemeral('temp_file', '/tmp/xyz.json')
ctx.set_ephemeral('progress_percent', 45)

# Clear ephemeral data
ctx.clear_ephemeral()  # Persistent data unchanged
```

### 3. Protected Keys

Prevent accidental overwriting of critical data:

```python
# Protect session IDs
ctx.set('session_id', 'abc123', protected=True)
ctx.set('run_id', 'xyz789', protected=True)

# Setting to same value is idempotent (no error)
ctx.set('session_id', 'abc123', protected=True)  # ✅ OK

# Setting to different value raises error
ctx.set('session_id', 'different!')  # ❌ ValueError: Cannot overwrite protected key

# update() silently skips protected keys
ctx.update({
    'session_id': 'ignored',  # Skipped
    'normal_key': 'updated'   # Applied
})
```

**Key Behaviors:**
- **Idempotent**: Re-setting to same value succeeds silently
- **Protected**: Attempting to change raises ValueError
- **Update-safe**: `update()` skips protected keys instead of erroring
- **Delete-protected**: Cannot delete protected keys

### 4. Context Snapshots

Create checkpoints you can restore later:

```python
# Save state before risky operation
snapshot = ctx.create_snapshot('before_refactoring')

# Do something that might go wrong
try:
    dangerous_operation()
except Exception:
    # Rollback to snapshot
    ctx.restore_snapshot(snapshot.version)

# Or restore latest snapshot
ctx.restore_snapshot()  # Restores most recent
```

### 5. Phase Context Isolation

Phases get independent copies that won't corrupt orchestrator state:

```python
# Before phase invocation
snapshot = ctx.create_snapshot('before_planning_phase')
phase_context = ctx.get_phase_context()  # Deep copied

# Phase modifies its copy freely
phase_result = planning_phase.execute(phase_context)

# Merge results back with strategy
ctx.merge_phase_results(
    phase_result.context.shared_state,
    strategy='safe'  # Only add new keys, don't overwrite
)

# Create after-phase snapshot
ctx.create_snapshot('after_planning_phase')
```

### 6. Merge Strategies

Control how phase results integrate:

```python
# Strategy 1: Safe (default) - only add new keys
ctx.merge_phase_results(phase_results, strategy='safe')

# Strategy 2: Update - overwrite existing, add new
ctx.merge_phase_results(phase_results, strategy='update')

# Strategy 3: Replace - completely replace context
ctx.merge_phase_results(phase_results, strategy='replace')

# Strategy 4: Prefixed - add with namespace
ctx.merge_phase_results(
    phase_results,
    strategy='prefixed',
    prefix='planning_'
)
# Results in: planning_steps, planning_metadata, etc.
```

### 7. Persistence

Save/load context to survive restarts:

```python
# Save as JSON (human readable, but limited types)
orchestrator.save_context_to_disk('./context.json')

# Save as pickle (preserves complex objects)
orchestrator.save_context_to_disk('./context.pkl', use_pickle=True)

# Load from disk
orchestrator.load_context_from_disk('./context.json')
orchestrator.load_context_from_disk('./context.pkl', use_pickle=True)

# Context restored with all:
# - Data
# - Version history
# - Snapshots
# - Change log
```

### 8. Change Logging

Track what changed and when:

```python
changes = ctx.get_change_log()

for change in changes[-10:]:  # Last 10 changes
    print(f"{change['timestamp']}: {change['operation']}")
    print(f"  Version: {change['version']}")
    print(f"  Details: {change['details']}")

# Example output:
# 1707680400.123: set
#   Version: 5
#   Details: {'key': 'plan_steps', 'had_previous': False, 'protected': False}
# 1707680401.456: merge_phase_results
#   Version: 6
#   Details: {'strategy': 'safe', 'keys_merged': 12}
```

### 9. Versioning

Every change increments version number:

```python
print(ctx.version)  # 0

ctx.set('key1', 'value1')
print(ctx.version)  # 1

ctx.update({'key2': 'value2', 'key3': 'value3'})
print(ctx.version)  # 2

ctx.delete('key1')
print(ctx.version)  # 3

# Snapshots capture version
snapshot = ctx.create_snapshot('checkpoint')
print(snapshot.version)  # 3

# Restore to previous version
ctx.restore_snapshot(version=1)  # Back to 'key1' only
```

## Usage in SwarmOrchestrator

### Basic Access

```python
# Get values
user_name = orchestrator.get_context_value('user_name', default='Guest')
plan = orchestrator.get_context_value('plan_steps')

# Set values
orchestrator.set_context_value('project_root', '/srv/projects/myapp')
orchestrator.set_context_value('session_id', 'abc', protected=True)
orchestrator.set_context_value('progress', 50, ephemeral=True)
```

### Checkpoints

```python
# Create checkpoint
checkpoint = orchestrator.create_context_checkpoint('before_phase_invocation')

# Restore if needed
orchestrator.restore_context_checkpoint(checkpoint.version)

# Get all snapshots
snapshots = orchestrator.get_context_snapshots()
for snap in snapshots:
    print(f"{snap.reason}: version {snap.version}")
```

### Persistence

```python
# Save session state
orchestrator.save_context_to_disk(
    f'./sessions/{session_id}_context.pkl',
    use_pickle=True
)

# Later, restore session
orchestrator.load_context_from_disk(
    f'./sessions/{session_id}_context.pkl',
    use_pickle=True
)
```

## Session Lifecycle

### 1. Session Creation

```python
# SwarmOrchestrator.__init__() creates DurableContext
orchestrator = SwarmOrchestrator(config)

# Context initialized with protected keys
# - session_id
# - run_id
```

### 2. Task Execution Start

```python
await orchestrator.run(task="Build REST API", initial_context={
    'language': 'Python',
    'framework': 'FastAPI',
})

# initial_context deep copied into context
# initial_task protected from overwrites
```

### 3. Phase Invocation

```python
# Agent invokes phase tool
invoke_planning_phase(task="...")

# Orchestrator creates snapshot
snapshot = ctx.create_snapshot('before_planning_phase')

# Phase gets independent copy
phase_context = ctx.get_phase_context()

# Phase executes with its copy
# ... phase creates new CMBAgent, generates plan ...

# Results merged back (safe strategy)
ctx.merge_phase_results(results, strategy='safe')

# After-phase snapshot created
ctx.create_snapshot('after_planning_phase')
```

### 4. Session Continuation

```python
# User sends follow-up message with same copilotSessionId
# Backend finds existing orchestrator in _active_copilot_sessions
continued = await continue_copilot_sync(session_id, new_message)

# Context persists with all:
# - Previous conversation context
# - Phase outputs
# - Snapshots
# - Version history
```

### 5. Session Persistence (Optional)

```python
# Before shutdown, save session
orchestrator.save_context_to_disk(
    f'./checkpoints/session_{session_id}.pkl',
    use_pickle=True
)

# On restart, restore
orchestrator.load_context_from_disk(
    f'./checkpoints/session_{session_id}.pkl',
    use_pickle=True
)

# Continue where left off
await orchestrator.run(task="Continue previous work")
```

## Best Practices

### 1. Always Use Deep Copy for Complex Objects

```python
# ✅ Good - explicit deep copy
ctx.set('config', complex_config_dict, deep_copy=True)

# ❌ Avoid - shallow reference
ctx.set('config', complex_config_dict, deep_copy=False)
```

### 2. Protect Critical Keys

```python
# ✅ Protect session identifiers
ctx.set('session_id', session_id, protected=True)
ctx.set('initial_task', task, protected=True)
ctx.set('workflow_id', workflow_id, protected=True)
```

### 3. Use Ephemeral for Temporary Data

```python
# ✅ Ephemeral for temp data
ctx.set_ephemeral('temp_results', results)
ctx.set_ephemeral('progress_pct', 45)
ctx.clear_ephemeral()  # Clean up
```

### 4. Snapshot Before Risky Operations

```python
# ✅ Snapshot before phase invocations
snapshot = ctx.create_snapshot('before_control_phase')
try:
    execute_control_phase()
except Exception as e:
    ctx.restore_snapshot(snapshot.version)
    raise
```

### 5. Use Safe Merge Strategy

```python
# ✅ Safe - won't overwrite existing data
ctx.merge_phase_results(results, strategy='safe')

# ⚠️ Update - might overwrite important data
ctx.merge_phase_results(results, strategy='update')

# ❌ Replace - loses all existing data
ctx.merge_phase_results(results, strategy='replace')
```

### 6. Persist Long-Running Sessions

```python
# ✅ Save checkpoints periodically
if orchestrator.state.current_round % 10 == 0:
    orchestrator.save_context_to_disk(
        f'./checkpoints/round_{orchestrator.state.current_round}.json'
    )
```

## Debugging

### View Context State

```python
# Get full context as dict
ctx_dict = orchestrator.state.context.to_dict()
print(json.dumps(ctx_dict, indent=2))
```

### Inspect Changes

```python
# Get change log
changes = orchestrator.get_context_change_log()
for change in changes:
    print(f"{change['operation']} at version {change['version']}")
```

### Review Snapshots

```python
# Get all snapshots
snapshots = orchestrator.get_context_snapshots()
for snap in snapshots:
    print(f"v{snap.version}: {snap.reason} at {snap.timestamp}")
```

### Compare Versions

```python
# Save current state
current = orchestrator.state.context.to_dict()

# Restore old version
orchestrator.restore_context_checkpoint(version=5)
old = orchestrator.state.context.to_dict()

# Compare
added_keys = set(current['persistent']) - set(old['persistent'])
removed_keys = set(old['persistent']) - set(current['persistent'])
```

## Migration from Old Code

### Before

```python
# Old dict-based approach
orchestrator.state.shared_context['key'] = value
orchestrator.state.shared_context.update(data)
value = orchestrator.state.shared_context.get('key', default)
phase_ctx = orchestrator.state.shared_context.copy()
```

### After

```python
# New DurableContext approach
orchestrator.state.context.set('key', value)
orchestrator.state.context.update(data)
value = orchestrator.state.context.get('key', default)
phase_ctx = orchestrator.state.context.get_phase_context()

# Or use helper methods
orchestrator.set_context_value('key', value)
orchestrator.get_context_value('key', default)
```

## Summary

The DurableContext system makes copilot sessions:
- ✅ **More reliable** - deep copying prevents corruption
- ✅ **More traceable** - change logs and versioning
- ✅ **More resilient** - snapshots enable rollback
- ✅ **More persistent** - serialization survives restarts
- ✅ **More intelligent** - strategies for merging phase results

This provides a production-ready foundation for long-running, multi-phase copilot conversations.
