# CMBAgent Enhancement Implementation Plan

## Overview
This document provides a comprehensive, stage-by-stage implementation plan for enhancing CMBAgent with advanced features including HITL, parallel execution, DAG visualization, policy management, and modern infrastructure.

**Total Stages:** 15 stages organized into 5 phases
**Estimated Total Time:** 5 hours of focused implementation
**Current Stage:** 0 (Not Started)

## How to Use This Plan

### For Each Stage:
1. Read `STAGE_XX.md` in this directory
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

### Phase 0: Foundation (Stages 1-2) - ~30 min
**Goal:** Upgrade AG2 and establish database infrastructure

- **Stage 1:** AG2 Upgrade and Compatibility Testing
- **Stage 2:** Database Schema and Models

### Phase 1: Core Infrastructure (Stages 3-5) - ~60 min
**Goal:** Build state machine, DAG system, and enhanced streaming

- **Stage 3:** State Machine Implementation
- **Stage 4:** DAG Builder and Storage System
- **Stage 5:** Enhanced WebSocket Protocol

### Phase 2: Execution Control (Stages 6-9) - ~90 min
**Goal:** Implement HITL, retry logic, parallel execution, and branching

- **Stage 6:** Human-in-the-Loop Approval System
- **Stage 7:** Context-Aware Retry Mechanism
- **Stage 8:** Dependency Analysis and Parallel Execution
- **Stage 9:** Branching and Play-from-Node

### Phase 3: Integration (Stages 10-12) - ~60 min
**Goal:** MCP integration and plugin system

- **Stage 10:** MCP Server Interface
- **Stage 11:** MCP Client for External Tools
- **Stage 12:** Enhanced Agent Registry

### Phase 4: Observability & Policy (Stages 13-15) - ~60 min
**Goal:** Cost tracking, observability, and policy enforcement

- **Stage 13:** Enhanced Cost Tracking and Session Management
- **Stage 14:** Observability and Metrics
- **Stage 15:** Open Policy Agent Integration

## Directory Structure

```
IMPLEMENTATION_PLAN/
├── README.md                    # This file - master plan
├── PROGRESS.md                  # Track completion status
├── ARCHITECTURE.md              # Technical architecture decisions
├── VERIFICATION_CHECKLIST.md   # Master verification checklist
├── stages/
│   ├── STAGE_01.md             # AG2 upgrade
│   ├── STAGE_02.md             # Database schema
│   ├── STAGE_03.md             # State machine
│   ├── STAGE_04.md             # DAG system
│   ├── STAGE_05.md             # WebSocket enhancement
│   ├── STAGE_06.md             # HITL system
│   ├── STAGE_07.md             # Context-aware retry
│   ├── STAGE_08.md             # Parallel execution
│   ├── STAGE_09.md             # Branching
│   ├── STAGE_10.md             # MCP server
│   ├── STAGE_11.md             # MCP client
│   ├── STAGE_12.md             # Agent registry
│   ├── STAGE_13.md             # Cost tracking
│   ├── STAGE_14.md             # Observability
│   └── STAGE_15.md             # Policy enforcement
├── code_changes/
│   ├── new_files.txt           # List of new files to create
│   ├── modified_files.txt      # List of files to modify
│   └── file_dependencies.txt   # File dependency graph
├── testing/
│   ├── test_scenarios.md       # Test scenarios per stage
│   ├── integration_tests.md    # End-to-end test plan
│   └── rollback_procedures.md  # How to rollback each stage
└── references/
    ├── current_architecture.md # Current system analysis
    ├── ag2_migration_notes.md  # AG2 upgrade notes
    └── database_schema.sql     # Database design
```

## Critical Success Factors

### 1. Backward Compatibility
- All existing workflows must continue to work
- Pickle file checkpoints must remain loadable
- Current CLI interface preserved
- Work directory structure backward compatible

### 2. Incremental Deployment
- Each stage can be feature-flagged
- No breaking changes without migration path
- Old and new systems can coexist
- Graceful degradation if features disabled

### 3. Verification at Each Stage
- Unit tests pass
- Integration tests pass
- Manual verification completed
- Documentation updated

### 4. Database First
- All new state in database
- Pickle files deprecated gradually
- Queryable history
- Atomic operations

### 5. Policy Last
- Build features first
- Add policy layer at end
- Default permissive policies
- Easy override mechanism

## Stage Dependencies

```
Stage 1 (AG2 Upgrade)
  ↓
Stage 2 (Database)
  ↓
Stage 3 (State Machine) ←─────┐
  ↓                            │
Stage 4 (DAG System)           │
  ↓                            │
Stage 5 (WebSocket)            │
  ↓                            │
Stage 6 (HITL) ←───────────────┤
  ↓                            │
Stage 7 (Retry)                │
  ↓                            │
Stage 8 (Parallel) ←───────────┤
  ↓                            │
Stage 9 (Branching)            │
  ↓                            │
Stage 10 (MCP Server)          │
  ↓                            │
Stage 11 (MCP Client)          │
  ↓                            │
Stage 12 (Registry)            │
  ↓                            │
Stage 13 (Cost Tracking)       │
  ↓                            │
Stage 14 (Observability)       │
  ↓                            │
Stage 15 (Policy) ←────────────┘
```

## Risk Management

### High-Risk Stages
- **Stage 1:** AG2 upgrade may break existing code
- **Stage 8:** Parallel execution has race condition risks
- **Stage 15:** Policy enforcement may block legitimate actions

### Mitigation
- Comprehensive testing after each stage
- Feature flags to disable new functionality
- Rollback procedures documented
- Backup before each stage

## Quick Reference Commands

### Start New Stage
```bash
# Review stage details
cat IMPLEMENTATION_PLAN/stages/STAGE_XX.md

# Update progress
# Edit IMPLEMENTATION_PLAN/PROGRESS.md
```

### Verify Stage Completion
```bash
# Run stage-specific tests (defined in each STAGE_XX.md)
python tests/test_stage_XX.py

# Check verification criteria
# Review "Verification Criteria" section in STAGE_XX.md
```

### Resume from Checkpoint
```bash
# Provide to Claude:
# 1. Current stage from PROGRESS.md
# 2. Path to IMPLEMENTATION_PLAN/README.md
# 3. Any blockers or issues encountered
```

## Important Notes

1. **Do Not Skip Stages:** Each stage builds on previous ones
2. **Verify Before Proceeding:** Run all verification tests
3. **Document Issues:** Note any problems in PROGRESS.md
4. **Commit Frequently:** Commit after each stage completion
5. **Test Backward Compatibility:** Ensure old workflows still work

## Support and Troubleshooting

### Common Issues
- **AG2 breaking changes:** See `references/ag2_migration_notes.md`
- **Database migration failures:** See `testing/rollback_procedures.md`
- **Test failures:** Check stage-specific troubleshooting in `STAGE_XX.md`

### Getting Help
- Review architecture decisions in `ARCHITECTURE.md`
- Check current system analysis in `references/current_architecture.md`
- Verify file dependencies in `code_changes/file_dependencies.txt`

## Next Steps

1. Review `PROGRESS.md` to check current status
2. Read `ARCHITECTURE.md` for technical overview
3. Start with `stages/STAGE_01.md` if beginning fresh
4. Follow stage-by-stage implementation
5. Update `PROGRESS.md` after each stage

---

**Last Updated:** 2026-01-14
**Plan Version:** 1.0
**Status:** Ready for implementation
