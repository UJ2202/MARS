# Unified Tracking/Event System - Implementation Summary

## Overview

This implementation plan unifies three disconnected tracking layers in CMBAgent:

1. **WorkflowCallbacks** (phase-level events) - Already working
2. **PhaseExecutionManager** (phase ↔ callback bridge) - Already working
3. **EventCaptureManager + AG2 Hooks** (low-level AG2 tracing) - **EXISTS BUT NEVER ACTIVATED**

**Core Problem**: Each `CMBAgent()` instance creates its own isolated DB session, disconnected from parent workflow tracking. AG2 agent calls, messages, and tool executions go completely untracked.

**Solution**: Activate existing infrastructure in 3 stages, with minimal code changes.

---

## Quick Start

### Documents in This Package

1. **UNIFIED_TRACKING_IMPLEMENTATION_PLAN.md** (this file's companion)
   - Detailed implementation plan with rationale
   - Stage-by-stage breakdown
   - Design decisions and trade-offs
   - Testing strategy and rollout plan

2. **UNIFIED_TRACKING_ARCHITECTURE_DIAGRAM.md**
   - Visual diagrams of current vs future state
   - Data flow examples
   - Before/after comparisons

3. **QUICK_IMPLEMENTATION_REFERENCE.md**
   - Exact code snippets for each change
   - Copy-paste ready implementations
   - Database migration scripts
   - Testing commands

### Recommended Reading Order

1. **Start here**: Read "Three-Stage Implementation" below (5 minutes)
2. **Architecture**: Skim UNIFIED_TRACKING_ARCHITECTURE_DIAGRAM.md (10 minutes)
3. **Implementation**: Use QUICK_IMPLEMENTATION_REFERENCE.md while coding (as needed)
4. **Full Context**: Read UNIFIED_TRACKING_IMPLEMENTATION_PLAN.md for design rationale (30 minutes)

---

## Three-Stage Implementation

### Stage 1: Wire Up AG2 Hooks (Activate Existing Infrastructure)

**Goal**: Capture all AG2 agent activity automatically

**What Changes**:
- `PhaseExecutionManager` creates `EventCaptureManager` and calls `install_ag2_hooks()`
- AG2 classes are monkey-patched to intercept calls
- All agent messages, tool calls, handoffs captured automatically

**Files Modified**: 2
- `cmbagent/execution/ag2_hooks.py` - Add idempotency flag
- `cmbagent/phases/execution_manager.py` - Add event capture setup/teardown

**Impact**:
- ✅ Low risk (existing code, just wiring it up)
- ✅ High value (complete visibility into agent execution)
- ✅ Phase files unchanged (automatic from PhaseExecutionManager)

**Verification**:
```python
# After implementation, check database
from cmbagent.database.models import ExecutionEvent
events = db.query(ExecutionEvent).all()
print(f"Captured {len(events)} events")
# Should see: agent_call, tool_call, message, handoff events
```

---

### Stage 2: Add `managed_mode` to CMBAgent (Eliminate Orphaned Sessions)

**Goal**: Worker CMBAgent instances reuse parent's DB session instead of creating new ones

**What Changes**:
- Add `managed_mode: bool = False` parameter to `CMBAgent.__init__`
- Skip DB initialization (lines 227-289) when `managed_mode=True`
- Phases pass `managed_mode=True` when creating worker instances

**Files Modified**: 5
- `cmbagent/cmbagent.py` - Add parameter, refactor DB init
- `cmbagent/phases/execution_manager.py` - Add helper method
- `cmbagent/phases/planning.py` - Pass `managed_mode=True`
- `cmbagent/phases/control.py` - Pass `managed_mode=True`
- `cmbagent/phases/hitl_control.py` - Pass `managed_mode=True`

**Impact**:
- ⚠️ Medium risk (refactoring core initialization)
- ✅ Medium value (eliminates orphaned sessions, cleaner DB)
- ✅ Backward compatible (default `managed_mode=False`)

**Verification**:
```python
# Check no new sessions created
sessions_before = db.query(Session).count()
# Run workflow with managed_mode=True
sessions_after = db.query(Session).count()
assert sessions_after == sessions_before + 1  # Only 1 parent session
```

---

### Stage 3: Extend DAGTracker for Branching (Advanced Features)

**Goal**: Support redo branches, sub-nodes for internal agent calls, configurable `max_redos`

**What Changes**:
- Add `parent_node_id` and `depth` columns to `DAGNode` model (requires migration)
- Add `create_sub_node()` and `create_branch_node()` to `DAGRepository`
- Add `create_redo_branch()` method to `PhaseExecutionManager`
- Make `max_redos` configurable in `HITLControlPhaseConfig`

**Files Modified**: 5
- `cmbagent/database/models.py` - Add columns to DAGNode
- `cmbagent/database/repository.py` - Add sub-node/branch methods
- `cmbagent/phases/execution_manager.py` - Add branching support
- `cmbagent/phases/hitl_control.py` - Add `max_redos` config, wire up branches
- **Database migration** - Add columns and indexes

**Impact**:
- ⚠️ Medium-high risk (database migration required)
- ✅ High value for HITL workflows (track redos, alternatives)
- ⚠️ Requires maintenance window for migration

**Verification**:
```python
# Check redo creates branch
manager.create_redo_branch(step_number=1, redo_number=1, hypothesis="Retry with more context")
branch = db.query(DAGNode).filter(DAGNode.node_type == "branch_point").first()
assert branch is not None
assert branch.meta["branch_name"] == "redo_1"
```

---

## What Gets Tracked After Implementation

### Before (Current State)
- ✅ Phase starts/completes (via WorkflowCallbacks)
- ✅ Step starts/completes (via PhaseExecutionManager)
- ❌ Agent calls (invisible)
- ❌ Messages between agents (invisible)
- ❌ Tool calls (invisible)
- ❌ Code execution (invisible)
- ❌ Handoffs (invisible)
- ❌ Redo attempts (not tracked as branches)

### After Stage 1
- ✅ Phase starts/completes
- ✅ Step starts/completes
- ✅ **Agent calls** (with inputs/outputs)
- ✅ **Messages between agents**
- ✅ **Tool calls** (with arguments/results)
- ✅ **Code execution** (with code/output)
- ✅ **Handoffs** (with context)
- ❌ Redo attempts (not yet tracked as branches)

### After Stage 2
- ✅ All of Stage 1
- ✅ **Single unified DB session** (no orphaned sessions)
- ✅ **All events linked to parent run**

### After Stage 3
- ✅ All of Stages 1 & 2
- ✅ **Redo attempts tracked as branches**
- ✅ **Sub-agent calls as sub-nodes**
- ✅ **Configurable max_redos**
- ✅ **Full execution tree** (hierarchical DAG)

---

## Database Schema Changes

### Current Schema
```
WorkflowRun
 └─ DAGNode (flat list)
     ├─ planning (node_type)
     ├─ step_1 (node_type)
     ├─ step_2 (node_type)
     └─ terminator (node_type)

No parent_node_id → Can't represent hierarchy
No depth → Can't query by level
No conditional edges → Can't represent branches
```

### After Stage 3
```
WorkflowRun
 └─ DAGNode (hierarchical tree)
     ├─ planning (depth=0, parent=null)
     ├─ step_1 (depth=0, parent=null)
     │   ├─ sub_agent: code_analyzer (depth=1, parent=step_1) ← NEW
     │   └─ sub_agent: file_editor (depth=1, parent=step_1)   ← NEW
     ├─ step_2 (depth=0, parent=null)
     │   └─ sub_agent: web_surfer (depth=1, parent=step_2)    ← NEW
     ├─ step_3 (depth=0, parent=null) [FAILED]
     │   └─ branch_point: redo_1 (depth=0, parent=null)       ← NEW
     │       └─ step_3_retry (depth=0, parent=null)           ← NEW
     └─ terminator (depth=0, parent=null)

parent_node_id → Represents hierarchy
depth → Nesting level
conditional edges → Branches from failed steps
```

---

## Key Benefits

### 1. Complete Audit Trail
- Track every agent decision
- Trace tool call failures
- Understand why plans succeed/fail
- Debug complex multi-agent workflows

### 2. Performance Analysis
- Measure agent response times
- Identify slow tools
- Optimize workflow bottlenecks
- Compare redo strategies

### 3. HITL Improvements
- Show human reviewer what agents did
- Justify redo decisions with hypothesis
- Compare alternative execution paths
- Archive failed attempts for learning

### 4. Minimal Disruption
- Leverage existing infrastructure
- No changes to AG2 itself
- Backward compatible
- Incremental rollout (stage by stage)

---

## Implementation Checklist

### Stage 1: Wire Up AG2 Hooks
- [ ] Read QUICK_IMPLEMENTATION_REFERENCE.md for exact code changes
- [ ] Update `ag2_hooks.py` to add idempotency flag
- [ ] Update `execution_manager.py` to setup/teardown event capture
- [ ] Test: Run simple workflow, check ExecutionEvent table
- [ ] Test: Verify AG2 hooks are idempotent (run twice, check logs)
- [ ] Deploy to staging
- [ ] Monitor performance (should be < 10% overhead)
- [ ] Deploy to production

### Stage 2: Add managed_mode
- [ ] Update `cmbagent.py` to add `managed_mode` parameter
- [ ] Update `execution_manager.py` to add helper method
- [ ] Update 4 phase files to pass `managed_mode=True`
- [ ] Test: Verify no new sessions created
- [ ] Test: Verify events still captured
- [ ] Deploy to staging
- [ ] Monitor session count, memory usage
- [ ] Deploy to production

### Stage 3: Branching + Sub-Nodes
- [ ] Update `models.py` to add `parent_node_id`, `depth` columns
- [ ] Create and test database migration script
- [ ] Update `repository.py` to add sub-node/branch methods
- [ ] Update `execution_manager.py` to add branching support
- [ ] Update `hitl_control.py` to wire up redo branches
- [ ] Test: Create sub-node, verify parent relationship
- [ ] Test: Create branch, verify conditional edge
- [ ] Test: max_redos configuration
- [ ] Deploy to staging with migration
- [ ] Monitor DAG complexity, query performance
- [ ] Deploy to production in maintenance window

---

## Rollout Timeline

### Week 1-2: Stage 1 (Low Risk)
- Implement and test locally (2 days)
- Deploy to staging (1 day)
- Monitor staging (3 days)
- Deploy to production (1 day)
- Monitor production (3 days)

### Week 3-5: Stage 2 (Medium Risk)
- Implement and test locally (3 days)
- Deploy to staging (1 day)
- Monitor staging (5 days)
- Deploy to production (1 day)
- Monitor production (5 days)

### Week 6-10: Stage 3 (Medium-High Risk)
- Implement and test locally (5 days)
- Create and test migration (2 days)
- Deploy to staging with migration (1 day)
- Monitor staging (7 days)
- Schedule production maintenance window
- Deploy to production with migration (1 day)
- Monitor production (5 days)

**Total Duration**: ~10 weeks with conservative monitoring intervals

---

## Success Metrics

### Stage 1 Success Criteria
- ✅ 100+ ExecutionEvent records per workflow
- ✅ All event types captured (agent_call, tool_call, message, handoff)
- ✅ < 10% performance overhead
- ✅ No duplicate events
- ✅ Zero errors in event capture

### Stage 2 Success Criteria
- ✅ No new sessions created per CMBAgent instance
- ✅ All events still captured (Stage 1 metrics maintained)
- ✅ Memory usage stable or reduced
- ✅ Zero broken workflows

### Stage 3 Success Criteria
- ✅ Database migration completes cleanly (< 1 hour)
- ✅ Redo operations create branch nodes
- ✅ Sub-nodes appear for internal agent calls
- ✅ max_redos configuration respected
- ✅ DAG queries complete in < 500ms

---

## Common Questions

### Q: Will this slow down my workflows?
**A**: Stage 1 adds ~2-5ms per event. For a 100-event workflow, that's ~500ms total overhead. For long-running workflows (hours/days), this is negligible (<1%).

### Q: What if I don't want event capture?
**A**: Set `enable_database=False` in PhaseExecutionConfig, or set env var `CMBAGENT_USE_DATABASE=false`.

### Q: Can I rollback after deployment?
**A**: Yes. Stage 1 and 2 can be rolled back by commenting out code. Stage 3 requires database migration rollback (see QUICK_IMPLEMENTATION_REFERENCE.md).

### Q: Will this break my existing workflows?
**A**: No. All changes are backward compatible. Default `managed_mode=False` preserves old behavior.

### Q: How much database space will this use?
**A**: Estimate 100-500 events per workflow run, ~1KB per event. For 1000 runs: ~100-500 MB. Add retention policy to archive old events.

### Q: Can I visualize the DAG?
**A**: Not included in this plan, but Stage 3 enables it. Query DAG with recursive CTEs, render with D3.js or React Flow.

---

## Getting Help

### If Event Capture Fails
1. Check logs for `[PhaseExecutionManager] Event capture initialized`
2. Verify `ExecutionEvent` table exists
3. Check database connection is valid
4. Verify `enable_database=True` in config

### If AG2 Hooks Fail
1. Check logs for `[AG2 Hooks] All hooks installed successfully`
2. Verify autogen version compatibility (hooks tested on autogen 0.2.x)
3. Check if monkey-patching is disabled (some environments block it)

### If managed_mode Doesn't Work
1. Verify `managed_mode=True` is passed to CMBAgent
2. Check `parent_db_session` is not None
3. Check logs for `[CMBAgent] Running in managed_mode`
4. Verify parent phase created PhaseExecutionManager

### If Branching Fails
1. Verify database migration applied successfully
2. Check `parent_node_id` and `depth` columns exist
3. Verify DAGRepository has `create_branch_node()` method
4. Check logs for `[PhaseExecutionManager] Created redo branch`

---

## Next Steps

1. **Read the implementation plan**: Review UNIFIED_TRACKING_IMPLEMENTATION_PLAN.md for full context
2. **Review architecture diagrams**: Understand data flow in UNIFIED_TRACKING_ARCHITECTURE_DIAGRAM.md
3. **Start with Stage 1**: Use QUICK_IMPLEMENTATION_REFERENCE.md for exact code changes
4. **Test thoroughly**: Run test_event_capture.py before deploying
5. **Monitor in staging**: Validate metrics before production
6. **Deploy incrementally**: Stage 1 → 2 → 3, with monitoring between

---

## Files in This Package

```
UNIFIED_TRACKING_IMPLEMENTATION_PLAN.md
├─ Executive Summary
├─ Three-Stage Implementation (detailed)
├─ Design Decisions
├─ Testing Strategy
└─ Rollout Plan

UNIFIED_TRACKING_ARCHITECTURE_DIAGRAM.md
├─ Current State (disconnected)
├─ Future State (unified)
├─ Stage-by-stage transformations
├─ Data flow examples
└─ Before/after comparisons

QUICK_IMPLEMENTATION_REFERENCE.md
├─ Exact code snippets for each change
├─ Database migration scripts
├─ Testing commands
├─ Verification checklist
└─ Rollback procedures

README_UNIFIED_TRACKING.md (this file)
├─ Quick start guide
├─ High-level overview
├─ Success metrics
└─ Getting help
```

---

## Summary

This implementation plan provides a **practical, minimal, and safe** approach to unifying CMBAgent's tracking system:

- **Stage 1**: Activate existing infrastructure (low risk, high value)
- **Stage 2**: Eliminate orphaned sessions (medium risk, medium value)
- **Stage 3**: Add advanced features (medium-high risk, high value for HITL)

Each stage is independently deployable and testable. The design preserves backward compatibility while enabling future extensibility.

**Total Effort**: ~11-19 hours implementation + 10 weeks careful rollout
**Total Files**: 12 files modified + 1 database migration
**Total Code**: ~600 new lines

**Recommended Approach**: Implement stages sequentially with production validation between stages.
