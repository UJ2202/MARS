# Implementation Plan Template Architecture

This document serves as a template for creating structured, stage-based implementation plans for any project.

---

## Directory Structure

```
PROJECT_IMPLEMENTATION_PLAN/
│
├── README.md                      # Master plan (entry point)
├── PROGRESS.md                    # Progress tracking
├── ARCHITECTURE.md                # Technical architecture decisions
├── SUMMARY.md                     # Quick reference summary
│
├── stages/                        # Individual stage documents
│   ├── STAGE_01.md
│   ├── STAGE_02.md
│   ├── STAGE_03.md
│   └── ...
│
├── references/                    # Supporting documentation
│   ├── api_reference.md
│   ├── event_types.md
│   ├── data_models.md
│   └── ...
│
└── tests/                         # Testing documentation
    ├── test_scenarios.md
    ├── integration_tests.md
    └── validation_guide.md
```

---

## File Templates

### 1. README.md (Master Plan)

```markdown
# [Project Name] Implementation Plan

## Overview
Brief description of what this plan achieves.

**Total Stages:** X stages organized into Y phases
**Current Stage:** 0 (Not Started)
**Dependencies:** [List any prerequisites]

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
- Any blockers encountered

## Stage Overview

### Phase 0: [Phase Name] (Stages X-Y)
**Goal:** [What this phase achieves]

- **Stage X:** [Stage Name]
- **Stage Y:** [Stage Name]

### Phase 1: [Phase Name] (Stages X-Y)
**Goal:** [What this phase achieves]

- **Stage X:** [Stage Name]
- **Stage Y:** [Stage Name]

[Continue for all phases...]

## Directory Structure

[Show the directory structure of files to be created]

## Stage Dependencies

```
Stage 1
  ↓
Stage 2 ──> Stage 3
              ↓
            Stage 4
[Show dependency graph]
```

## Critical Success Factors

1. **[Factor 1]:** Description
2. **[Factor 2]:** Description
3. **[Factor 3]:** Description

## Quick Reference Commands

```bash
# Common commands for the project
command1
command2
```

## Risk Management

### High-Risk Stages
- **Stage X:** [Why it's risky]

### Mitigation
- [Mitigation strategies]

---

**Last Updated:** YYYY-MM-DD
**Plan Version:** 1.0
**Status:** Ready for implementation
```

---

### 2. PROGRESS.md (Progress Tracker)

```markdown
# Implementation Progress Tracker

## Current Status
- **Current Stage:** 0 (Not Started)
- **Last Updated:** YYYY-MM-DD
- **Overall Progress:** 0/X stages complete (0%)

## Stage Completion Status

### Phase 0: [Phase Name]
- [ ] **Stage 1:** [Stage Name]
  - Status: Not Started
  - Started: N/A
  - Completed: N/A
  - Verified: No
  - Notes:

- [ ] **Stage 2:** [Stage Name]
  - Status: Not Started
  - Started: N/A
  - Completed: N/A
  - Verified: No
  - Notes:

[Continue for all stages...]

## Issues and Blockers

### Active Issues
None

### Resolved Issues
None

## Notes and Observations

### General Notes
- [Any relevant notes]

### Decisions Made
- [Record important decisions]

### Changes to Plan
- [Document any deviations from original plan]

## How to Update This File

### When Starting a Stage
```markdown
- [X] **Stage N:** Stage Name
  - Status: In Progress
  - Started: YYYY-MM-DD HH:MM
```

### When Completing a Stage
```markdown
- [X] **Stage N:** Stage Name
  - Status: Complete
  - Completed: YYYY-MM-DD HH:MM
  - Verified: Yes
  - Notes: [Summary of changes]
```
```

---

### 3. ARCHITECTURE.md (Technical Architecture)

```markdown
# [Project Name] Architecture

## Executive Summary
Brief overview of architectural decisions.

## Core Architectural Principles

### 1. [Principle Name]
- Description of principle
- Why it matters
- How it's implemented

### 2. [Principle Name]
- Description
- Rationale
- Implementation approach

[Continue for all principles...]

## High-Level Component Diagram

```
┌─────────────────────────────────────────┐
│              Layer 1                     │
│  (Description)                          │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────┴───────────────────────┐
│              Layer 2                     │
│  ┌──────────┐  ┌──────────┐            │
│  │Component │  │Component │            │
│  └──────────┘  └──────────┘            │
└─────────────────────────────────────────┘
```

## Data Flow Architecture

### [Flow Name]

```
Step 1
  ↓
Step 2
  ↓
Step 3
```

## Component Hierarchy

```
ParentComponent
├── ChildComponent1
│   ├── GrandchildComponent
│   └── GrandchildComponent
└── ChildComponent2
```

## State Management

### Global State
```typescript
interface GlobalState {
  property1: Type;
  property2: Type;
}
```

### Local State
- Component-specific state descriptions

## Technology Stack

### Core
- **Technology 1:** Purpose
- **Technology 2:** Purpose

### Libraries
- **Library 1:** Purpose
- **Library 2:** Purpose

## Security Considerations
- [Security items]

## Performance Considerations
- [Performance items]

---

**Version:** 1.0
**Last Updated:** YYYY-MM-DD
```

---

### 4. STAGE_XX.md (Individual Stage Template)

```markdown
# Stage X: [Stage Name]

**Phase:** [Phase Number] - [Phase Name]
**Dependencies:** [Previous stages that must be complete]
**Risk Level:** Low/Medium/High

## Objectives

1. [Objective 1]
2. [Objective 2]
3. [Objective 3]

## Current State Analysis

### What We Have
- [Existing item 1]
- [Existing item 2]

### What We Need
- [Needed item 1]
- [Needed item 2]

## Pre-Stage Verification

### Check Prerequisites
1. [Prerequisite 1]
2. [Prerequisite 2]

### Test Current State
```bash
# Commands to verify current state
```

## Implementation Tasks

### Task 1: [Task Name]
**Objective:** [What this task achieves]

**Files to Create:**
- `path/to/file1.ext`
- `path/to/file2.ext`

**Implementation:**
```language
// Code example or detailed steps
```

**Verification:**
- [Verification step 1]
- [Verification step 2]

### Task 2: [Task Name]
**Objective:** [What this task achieves]

**Files to Modify:**
- `path/to/existing_file.ext`

**Changes:**
```language
// Code changes
```

**Verification:**
- [Verification step]

[Continue for all tasks...]

## Files to Create (Summary)

```
project/
├── folder1/
│   ├── file1.ext
│   └── file2.ext
└── folder2/
    └── file3.ext
```

## Files to Modify

- `path/to/file1.ext` - [Description of changes]
- `path/to/file2.ext` - [Description of changes]

## Verification Criteria

### Must Pass
- [ ] [Critical verification 1]
- [ ] [Critical verification 2]
- [ ] [Critical verification 3]

### Should Pass
- [ ] [Important verification 1]
- [ ] [Important verification 2]

### Nice to Have
- [ ] [Optional verification 1]

## Testing Commands

```bash
# Commands to test the implementation
test_command_1
test_command_2
```

## Common Issues and Solutions

### Issue 1: [Issue Name]
**Symptom:** [What you observe]
**Solution:** [How to fix it]

### Issue 2: [Issue Name]
**Symptom:** [What you observe]
**Solution:** [How to fix it]

## Rollback Procedure

If Stage X causes issues:
1. [Rollback step 1]
2. [Rollback step 2]
3. [Document what went wrong]

## Success Criteria

Stage X is complete when:
1. [Criterion 1]
2. [Criterion 2]
3. [Criterion 3]
4. All verification criteria pass

## Next Stage

Once Stage X is verified complete, proceed to:
**Stage Y: [Stage Name]**

---

**Stage Status:** Not Started
**Last Updated:** YYYY-MM-DD
```

---

### 5. SUMMARY.md (Quick Reference)

```markdown
# Implementation Plan Summary

## Overview
Brief description of the plan.

## Plan Structure

```
[Directory tree]
```

## Stage Summary

| Stage | Name | Description | Key Deliverables |
|-------|------|-------------|------------------|
| 1 | [Name] | [Brief description] | [Key files/components] |
| 2 | [Name] | [Brief description] | [Key files/components] |

## Files to Create

### Category 1 (X files)
```
path/to/
├── file1.ext
└── file2.ext
```

### Category 2 (Y files)
```
path/to/
├── file3.ext
└── file4.ext
```

## Dependencies to Add

```bash
# Package manager commands
npm install package1 package2
```

## Implementation Order

```
Stage 1 ──> Stage 2 ──> Stage 3
                          ↓
            Stage 4 <─── Stage 5
```

## Key Integration Points

| Feature | Component | Event/API |
|---------|-----------|-----------|
| [Feature] | [Component] | [Event/Endpoint] |

## Getting Started

1. **Step 1:** Command/action
2. **Step 2:** Command/action
3. **Step 3:** Command/action

## Quick Commands

```bash
# Common commands
command1
command2
```

---

**Created:** YYYY-MM-DD
**Total Stages:** X
**Status:** Ready for Implementation
```

---

### 6. references/[reference_name].md

```markdown
# [Reference Topic] Reference

Description of what this reference covers.

## Section 1

### Item 1
```json
{
  "example": "data"
}
```

### Item 2
Description and examples.

## Section 2

| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data | Data | Data |

---

**Last Updated:** YYYY-MM-DD
```

---

### 7. tests/test_scenarios.md

```markdown
# Test Scenarios

## Stage 1: [Stage Name]

### Unit Tests
- [ ] [Test 1]
- [ ] [Test 2]

### Integration Tests
- [ ] [Test 1]
- [ ] [Test 2]

### Manual Tests
1. [Manual test step 1]
2. [Manual test step 2]

[Continue for all stages...]

## End-to-End Tests

### Full Flow Test
1. [Step 1]
2. [Step 2]

## Compatibility Testing

Test in:
- [ ] Environment 1
- [ ] Environment 2

---

**Last Updated:** YYYY-MM-DD
```

---

## Best Practices

### 1. Stage Design
- Each stage should be completable in 1-4 hours
- Stages should have clear boundaries
- Dependencies should be explicit
- Include rollback procedures

### 2. Documentation
- Use consistent formatting
- Include code examples
- Document verification criteria
- Keep references updated

### 3. Progress Tracking
- Update PROGRESS.md immediately after completing work
- Document issues and blockers
- Record decisions made

### 4. Task Breakdown
- Tasks should be specific and actionable
- Include file paths
- Provide code templates
- List verification steps

### 5. Testing
- Define test scenarios upfront
- Include both automated and manual tests
- Document expected outcomes

---

## Template Usage Prompt

Use this prompt to implement any stage:

```
Implement STAGE_XX from [path]/IMPLEMENTATION_PLAN/stages/STAGE_XX.md.

Context:
- Project location: [path]
- Follow implementation tasks in order
- Create all files listed
- Use code provided as starting point
- Update PROGRESS.md when done

Requirements:
1. Read stage document thoroughly
2. Create all types/interfaces needed
3. Create all components specified
4. Update existing files as noted
5. Ensure code compiles without errors
6. Run verification tests

Stage to implement: STAGE_XX
```

---

**Template Version:** 1.0
**Created:** 2026-01-16
