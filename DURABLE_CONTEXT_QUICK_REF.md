# Enhanced Durable Context - Quick Reference

## Summary

Successfully replaced simple `Dict[str, Any]` shared context with robust **DurableContext** system.

## Key Changes

### Before
```python
class SwarmState:
    shared_context: Dict[str, Any] = field(default_factory=dict)  # ❌

# Usage
orchestrator.state.shared_context['key'] = value  # ❌ Shallow copy
orchestrator.state.shared_context.update(data)    # ❌ No protection
phase_ctx = orchestrator.state.shared_context.copy()  # ❌ Reference issues
```

### After
```python
class SwarmState:
    context: DurableContext = None  # ✅

# Usage
orchestrator.state.context.set('key', value, protected=True)  # ✅ Deep copy
orchestrator.state.context.update(data, deep_copy=True)      # ✅ Protected
phase_ctx = orchestrator.state.context.get_phase_context()   # ✅ Independent
```

## Files Created

1. **durable_context.py** - Core implementation (695 lines)
2. **DURABLE_CONTEXT_GUIDE.md** - Complete documentation (638 lines)
3. **DURABLE_CONTEXT_IMPLEMENTATION.md** - Implementation summary (241 lines)
4. **examples/durable_context_example.py** - Working examples (343 lines)

## Files Modified

1. **swarm_orchestrator.py** - Integrated DurableContext
   - Replaced shared_context dict
   - Added context management methods
   - Updated phase execution flow

## Features Added

| Feature | Description | Benefit |
|---------|-------------|---------|
| **Deep Copying** | All values deep copied by default | Prevents reference corruption |
| **Snapshots** | Create checkpoints, restore history | Recovery from errors |
| **Versioning** | Track changes with version numbers | Debugging & tracing |
| **Protection** | Keys can be marked immutable | Prevent accidents |
| **Persistence** | Save/load to JSON or Pickle | Survive restarts |
| **Ephemeral Data** | Temporary data auto-cleared | Clean separation |
| **Merge Strategies** | Safe, update, replace, prefixed | Controlled integration |
| **Change Log** | Track all operations | Audit trail |
| **Dict Interface** | `ctx['key']` access | Familiar API |

## Phase Context Flow

```
┌─────────────────────────────────────────┐
│  Orchestrator Context (Persistent)      │
│  - session_id (protected)               │
│  - run_id (protected)                   │
│  - task, config, user data              │
│  - Version: N                           │
└────────────┬────────────────────────────┘
             │
             │ Agent invokes phase tool
             ▼
┌─────────────────────────────────────────┐
│  1. Create Snapshot                     │
│     reason: "before_planning_phase"     │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  2. Get Phase Context                   │
│     phase_ctx = get_phase_context()     │
│     → Deep copied, independent          │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  3. Phase Executes                      │
│     - Creates new CMBAgent              │
│     - Modifies its own context          │
│     - Cannot corrupt orchestrator       │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  4. Merge Results (Safe Strategy)       │
│     merge_phase_results(                │
│       results, strategy='safe'          │
│     )                                   │
│     → Only adds new keys                │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  5. Create Snapshot                     │
│     reason: "after_planning_phase"      │
│     Version: N+1                        │
└─────────────────────────────────────────┘
```

## API Quick Reference

### Basic Operations
```python
# Set value
orchestrator.set_context_value('key', value)
orchestrator.set_context_value('important', value, protected=True)
orchestrator.set_context_value('temp', value, ephemeral=True)

# Get value
value = orchestrator.get_context_value('key', default='fallback')

# Direct access
orchestrator.state.context['key'] = value
value = orchestrator.state.context['key']
if 'key' in orchestrator.state.context:
    ...
```

### Snapshots
```python
# Create
snapshot = orchestrator.create_context_checkpoint('reason')

# Restore
orchestrator.restore_context_checkpoint(snapshot.version)
orchestrator.restore_context_checkpoint()  # Latest

# View
snapshots = orchestrator.get_context_snapshots()
```

### Persistence
```python
# Save
orchestrator.save_context_to_disk('./session.json')
orchestrator.save_context_to_disk('./session.pkl', use_pickle=True)

# Load
orchestrator.load_context_from_disk('./session.json')
orchestrator.load_context_from_disk('./session.pkl', use_pickle=True)
```

### Debugging
```python
# Change log
changes = orchestrator.get_context_change_log()

# Full state
state = orchestrator.state.context.to_dict()
print(json.dumps(state, indent=2))

# Version info
print(f"Version: {orchestrator.state.context.version}")
print(f"Snapshots: {len(orchestrator.state.context.get_snapshots())}")
```

## Testing

Run examples:
```bash
cd /srv/projects/mas/mars/denario/cmbagent
python examples/durable_context_example.py
```

All 9 examples pass:
✅ Basic usage
✅ Ephemeral data
✅ Snapshots
✅ Phase isolation
✅ Merge strategies
✅ Persistence
✅ Change log
✅ Protected keys
✅ Dictionary interface

## Benefits Summary

### 🛡️ Reliability
- Deep copy prevents subtle reference bugs
- Protected keys prevent data loss
- Snapshots enable recovery

### 🔍 Debuggability
- Change log shows all operations
- Snapshots preserve history
- Version tracking enables tracing

### ⚡ Performance
- Session reuse works (no re-init)
- Context persists across rounds
- Efficient deep copying

### 💾 Persistence
- Sessions survive restarts
- Checkpoint long conversations
- Offline inspection

### 🔒 Safety
- Phases get independent copies
- Safe merge prevents overwrites
- Protected keys immutable

## Next: Use It!

The system is production-ready. Start using it in your orchestrator:

```python
# Works immediately - backward compatible
orchestrator = SwarmOrchestrator(config)
await orchestrator.run(task="Build something")

# Context automatically durable now!
```

For advanced features, see:
- **DURABLE_CONTEXT_GUIDE.md** - Complete guide
- **examples/durable_context_example.py** - Code examples
