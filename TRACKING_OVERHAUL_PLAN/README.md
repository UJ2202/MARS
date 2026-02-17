# Tracking System Overhaul Plan

## Overview

Complete overhaul of the workflow tracking infrastructure across cmbagent (library) and backend (app). The system has organically grown from supporting a single `planning-and-control` mode to 8+ workflow types with 2 orchestrators, creating fragmented and buggy tracking code.

## Goals

1. **Production-grade robustness** for multi-day autonomous research runs
2. **Generalized design** where adding a new workflow requires zero tracking code
3. **Clear library/app boundary** - cmbagent is a library, backend is an app built on it
4. **Each cross-cutting concern has a dedicated stage** - DAG, cost, events, files each get focused attention
5. **Code cleanup** - remove all dead code, duplicate paths, and stale patterns
6. **Future-proof** for branch-from-node, racing branches, and concurrent sessions
7. **Copilot excluded** - will be revamped separately

## Plan Structure

```
TRACKING_OVERHAUL_PLAN/
  README.md                       # This file
  PROGRESS.md                     # Stage-by-stage progress tracker
  ARCHITECTURE.md                 # Target architecture with boundary diagrams
  SUMMARY.md                      # Analysis findings and bug inventory
  stages/
    STAGE_0_FOUNDATION.md         # Bug fixes + callback contract + boundary types
    STAGE_1_DAG_OVERHAUL.md       # Template-based DAG factory, remove mode branches
    STAGE_2_COST_TRACKING.md      # JSON source of truth, CostCollector, remove stdout parsing
    STAGE_3_EVENT_TRACKING.md     # contextvars, thread-safety, AG2 hooks completion
    STAGE_4_FILE_TRACKING.md      # FileRepository, session_id, deduplication, phase attribution
    STAGE_5_PHASE_MIGRATION.md    # All phases use PhaseExecutionManager consistently
    STAGE_6_WORKFLOW_MIGRATION.md # Strip StreamCapture, add callbacks to all workflows
    STAGE_7_ROBUSTNESS.md         # Error handling, retry, transactions, dead code
    STAGE_8_BRANCHING.md          # Branch isolation, racing branch groundwork
    STAGE_9_SAMPLE_WORKFLOW.md    # Sample complex workflow + extensibility tests
  references/
    CURRENT_DATA_FLOW.md          # How data flows today (working HITL as reference)
    BOUNDARY_VIOLATIONS.md        # Complete list of library/app boundary violations
    BUG_INVENTORY.md              # All known bugs with code references
  tests/
    TEST_PLAN.md                  # Verification strategy per stage
```

## Guiding Principles

- **HITL DAG flow is the reference implementation** - it works, keep that pattern
- **DAGTracker IS the DAG state owner** - don't fight it, generalize it
- **Callbacks are the boundary contract** - library emits events, app handles them
- **Cost JSON files are source of truth** - don't parse stdout for cost data
- **One path per concern** - eliminate all duplicate tracking paths
- **contextvars for session isolation** - replace global singletons
- **One concern per stage** - each stage is testable in isolation

## Stages

| Stage | Name | Focus | Dependencies |
|-------|------|-------|-------------|
| 0 | Foundation | Bug fixes, callback contract, boundary types | None |
| 1 | DAG Overhaul | Template factory, remove mode branches, single DAG owner | Stage 0 |
| 2 | Cost Tracking | JSON source of truth, CostCollector, remove stdout parsing | Stage 0 |
| 3 | Event Tracking | contextvars, thread-safety, AG2 hook completion | Stage 0 |
| 4 | File Tracking | FileRepository, session_id, deduplication | Stage 1 |
| 5 | Phase Migration | All phases use PhaseExecutionManager | Stages 0, 1, 4 |
| 6 | Workflow Migration | Strip StreamCapture, callbacks in all workflows | Stages 1, 5 |
| 7 | Robustness | Error handling, retry, dead code cleanup | Stages 0-6 |
| 8 | Branching | Branch isolation, racing branch groundwork | All prior |
| 9 | Sample Workflow | Extensibility validation, deep-research example | All prior |

Each stage is independently testable and has rollback procedures.

## Dependency Graph

```
Stage 0 (Foundation)
  ├── Stage 1 (DAG) ──────────────────┐
  ├── Stage 2 (Cost)                   │
  ├── Stage 3 (Events)                 │
  │                                    ▼
  │                              Stage 4 (Files)
  │                                    │
  │                                    ▼
  │                              Stage 5 (Phase Migration)
  │                                    │
  │                                    ▼
  └──────────────────────────── Stage 6 (Workflow Migration)
                                       │
                                       ▼
                                 Stage 7 (Robustness)
                                       │
                                       ▼
                                 Stage 8 (Branching)
                                       │
                                       ▼
                                 Stage 9 (Sample Workflow)
```

Note: Stages 1, 2, 3 can run in parallel after Stage 0.
