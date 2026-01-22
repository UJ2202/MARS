# Enhanced DAG Workflow Capturing - Implementation Plan

## Overview
This document provides a comprehensive implementation plan for enhancing CMBAgent's DAG workflow system with fine-grained execution event capture, artifact tracking, and skill extraction capabilities. The enhancement builds upon existing Stages 1-9 to provide complete traceability for autonomous research workflows.

**Total Stages:** 4 stages organized into 2 phases
**Estimated Total Time:** 3-4 hours of focused implementation
**Current Stage:** 0 (Not Started)
**Dependencies:** Requires Stages 1-9 complete (especially Stage 4 - DAG System)

## Problem Statement

### Current Limitations
1. **Stage-Only Tracking**: DAG nodes only represent stages (planning → step_0 → step_1), missing:
   - Sub-agent calls within each stage
   - Tool/function invocations
   - Code execution events
   - File generation tied to specific actions
   - Agent handoffs and transitions

2. **Artifact Disconnect**: Files saved in task folders but not linked to:
   - Specific DAG nodes that created them
   - Agent that generated them
   - Execution event context

3. **No Execution Trace**: Cannot answer questions like:
   - "Which agent generated this file?"
   - "What was the execution flow within step_2?"
   - "How many times was the engineer agent called?"
   - "What was the sequence of events leading to failure?"

4. **Mode Inconsistency**: Different execution modes (one_shot, planning_and_control) save data differently

5. **Skill Extraction**: Cannot extract reusable patterns from successful workflows

## Solution Architecture

### Three-Tier Hierarchical Design

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 1: STAGE NODES (Existing DAGNode)                      │
│ • High-level workflow structure                             │
│ • Planning → Step_0 → Step_1 → Terminator                   │
│ • Enhanced with execution summary metadata                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Tier 2: EXECUTION EVENTS (New ExecutionEvent table)         │
│ • Agent invocations (engineer, planner, executor)           │
│ • Tool/function calls (execute_code, save_file)             │
│ • Agent handoffs (planner → engineer → executor)            │
│ • Code execution traces                                     │
│ • Nested event support (parent_event_id)                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Tier 3: ARTIFACTS (Enhanced File & Message tables)          │
│ • Files linked to events and nodes                          │
│ • Messages linked to events                                 │
│ • Full traceability chain                                   │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Non-Intrusive**: Keep existing DAG system unchanged, add alongside
2. **Performance**: Events in separate table, DAG stays clean
3. **Mode-Agnostic**: Works across all execution modes uniformly
4. **AG2-Native**: Leverage AG2's hook system for event capture
5. **Skill-Ready**: Structured for pattern extraction and repeatability

## How to Use This Plan

### For Each Stage:
1. Read `STAGE_XX.md` in the `stages/` directory
2. Review the stage objectives and verification criteria
3. Implement the stage following the guidelines
4. Run verification tests listed in the stage document
5. Mark stage as complete in `PROGRESS.md`
6. Move to next stage only after all verifications pass

### Resuming Implementation:
When resuming, provide:
- Current stage number (from `PROGRESS.md`)
- This README file location
- Claude will cross-verify previous stages and continue

## Stage Overview

### Phase 1: Event Capture Infrastructure (Stages 1-2) - ~2 hours
**Goal:** Build execution event tracking system

- **Stage 1:** ExecutionEvent Model and Database Schema
  - Create ExecutionEvent table with nested event support
  - Enhance File and Message tables with event/node linkage
  - Database migration for new schema
  - Repository layer for event access

- **Stage 2:** AG2 Event Capture Layer
  - Hook into AG2's ConversableAgent message system
  - Capture GroupChat transitions
  - Implement event interceptors for all agent actions
  - Mode-agnostic event emission
  - Integration with existing callback system

### Phase 2: Visualization and Skill Extraction (Stages 3-4) - ~2 hours
**Goal:** Enable workflow analysis and pattern extraction

- **Stage 3:** Enhanced DAG Node Metadata and UI Integration
  - Enrich DAGNode.meta with execution summaries
  - API endpoints for execution trace retrieval
  - UI components for expandable stage nodes
  - Execution timeline visualization
  - File/message association display

- **Stage 4:** Skill Extraction and Pattern Recognition
  - Query patterns from execution events
  - Extract successful workflows as reusable skills
  - Pattern matching algorithms
  - Skill templates and parameterization
  - Repeatability analysis

## Directory Structure

```
DAG_ENHANCEMENT_PLAN/
├── README.md                    # This file - master plan
├── PROGRESS.md                  # Track completion status
├── ARCHITECTURE.md              # Technical architecture decisions
├── stages/
│   ├── STAGE_01.md             # ExecutionEvent model and schema
│   ├── STAGE_02.md             # AG2 event capture layer
│   ├── STAGE_03.md             # Enhanced metadata and UI
│   └── STAGE_04.md             # Skill extraction system
├── references/
│   ├── current_dag_analysis.md # Current DAG system analysis
│   ├── ag2_hooks_reference.md  # AG2 hook system documentation
│   └── event_schema.md         # Event type definitions
└── tests/
    ├── test_scenarios.md       # Test scenarios per stage
    └── integration_tests.md    # End-to-end test plan
```

## Expected Outcomes

### After Stage 1 (Event Model)
- ExecutionEvent table tracks all actions within stages
- Files and messages linked to specific events and nodes
- Can query "what happened in step_2"
- Database supports nested events (agent → tool → code)

### After Stage 2 (Event Capture)
- All AG2 agent calls automatically captured
- GroupChat transitions tracked
- Mode-agnostic event emission working
- Real-time event streaming via WebSocket
- Zero impact on execution performance

### After Stage 3 (UI Integration)
- DAG nodes show execution summaries
- Clicking stage expands to show event timeline
- Files/messages linked to events in UI
- Can trace execution flow visually
- Execution metrics displayed (time, tokens, cost)

### After Stage 4 (Skill Extraction)
- Can extract patterns from successful workflows
- Query "show all plotting workflows"
- Generate reusable skill templates
- Analyze success/failure patterns
- Export skills for workflow library

## Benefits

### For Large Autonomous Workflows
- ✅ **Complete Traceability**: Every action documented
- ✅ **Debugging**: Trace failures to exact agent/event
- ✅ **Optimization**: Identify bottlenecks from timing data
- ✅ **Repeatability**: Extract and replay successful patterns
- ✅ **Audit Trail**: Full accountability for research workflows

### For Skill Development
- ✅ **Pattern Recognition**: Identify common successful sequences
- ✅ **Parameterization**: Abstract workflows into reusable skills
- ✅ **Validation**: Test skills across different contexts
- ✅ **Library Building**: Accumulate domain-specific skills

### For System Design
- ✅ **Performance**: Separate tables, minimal overhead
- ✅ **Scalability**: Handles 1000s of events per workflow
- ✅ **Flexibility**: JSON metadata for mode-specific data
- ✅ **Backward Compatible**: Existing DAG system unchanged

## Prerequisites

### Must Have Complete
- [x] Stage 1: AG2 Upgrade (0.10.3)
- [x] Stage 2: Database Schema (SQLAlchemy + Alembic)
- [x] Stage 3: State Machine
- [x] Stage 4: DAG Builder and Storage System
- [x] Stage 5: Enhanced WebSocket Protocol

### Should Have Complete (Recommended)
- [x] Stage 6: HITL Approval System
- [x] Stage 7: Context-Aware Retry
- [x] Stage 8: Parallel Execution
- [x] Stage 9: Branching

### System Requirements
- Python 3.10+
- SQLAlchemy 2.0+
- AG2 0.10.3+
- Working database (SQLite or PostgreSQL)
- Active WebSocket connection (for real-time updates)

## Risk Assessment

### Low Risk
- Adding new tables alongside existing schema
- AG2 hooks are non-breaking additions
- Can disable event capture via environment variable

### Medium Risk
- Performance impact if capturing too many events
  - **Mitigation**: Async event writing, batching, sampling
- Memory usage for long-running workflows
  - **Mitigation**: Event cleanup policies, archiving

### High Risk
- None identified

## Performance Considerations

### Event Volume Estimates
- **one_shot mode**: ~10-50 events per run
- **planning_and_control**: ~50-200 events per run
- **deep_research (future)**: ~500-2000 events per run

### Optimizations
1. **Async Event Writing**: Don't block execution
2. **Batch Inserts**: Group events, write in batches
3. **Event Sampling**: Optional sampling for high-volume scenarios
4. **Lazy Loading**: Load events only when needed
5. **Index Strategy**: Proper indexes on node_id, timestamp, event_type

## Success Metrics

- [ ] 100% event capture rate (no missed events)
- [ ] < 5% execution time overhead
- [ ] < 50ms average event write latency
- [ ] Can reconstruct full execution from events
- [ ] Skill extraction accuracy > 90%
- [ ] UI loads execution trace < 500ms

## Next Steps

1. **Read ARCHITECTURE.md** for technical details
2. **Review PROGRESS.md** to check current status
3. **Start with STAGE_01.md** when ready to implement
4. **Run tests after each stage** to ensure correctness
5. **Update PROGRESS.md** as stages complete

## Questions or Issues?

If you encounter issues during implementation:
1. Check the relevant STAGE_XX.md for troubleshooting
2. Review references/ directory for additional context
3. Verify all prerequisites are complete
4. Check database migrations applied correctly
5. Ensure AG2 0.10.3+ is installed

## Version History

- **v1.0** (2026-01-19): Initial plan creation
  - 4 stages across 2 phases
  - Hierarchical event design
  - AG2-native event capture
  - Skill extraction foundation
