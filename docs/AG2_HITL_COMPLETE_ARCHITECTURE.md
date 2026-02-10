# AG2 HITL System - Complete Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CMBAgent Workflow                             │
│                                                                       │
│  ┌─────────────────┐         ┌──────────────────┐                   │
│  │ HITLPlanning    │────────>│ HITLControl      │────────> Results  │
│  │ Phase           │         │ Phase            │                   │
│  └─────────────────┘         └──────────────────┘                   │
│         │                              │                             │
│         │                              │                             │
│         ▼                              ▼                             │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              AG2 Handoffs System (NEW!)                     │    │
│  │                                                               │    │
│  │  ┌──────────────┐    ┌──────────────┐   ┌──────────────┐  │    │
│  │  │  Mandatory   │    │    Smart     │   │   Dynamic    │  │    │
│  │  │ Checkpoints  │    │   Approval   │   │     Config   │  │    │
│  │  └──────────────┘    └──────────────┘   └──────────────┘  │    │
│  │         │                     │                  │          │    │
│  │         └─────────────────────┴──────────────────┘          │    │
│  │                              │                               │    │
│  │                              ▼                               │    │
│  │                    ┌──────────────────┐                     │    │
│  │                    │   Admin Agent    │                     │    │
│  │                    │    (Human UI)    │                     │    │
│  │                    └──────────────────┘                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Two-Layer Approval Architecture

### Layer 1: Phase-Level Approval (WebSocket)
```
┌──────────────────────────────────────────────────┐
│        WebSocket Approval Manager               │
│                                                  │
│  ┌────────────┐   ┌────────────┐   ┌─────────┐ │
│  │  Before    │   │   After    │   │   On    │ │
│  │   Step     │   │   Step     │   │  Error  │ │
│  └────────────┘   └────────────┘   └─────────┘ │
│         │               │                │       │            │
│         └───────────────┴────────────────┘       │
│                        │                         │
│                        ▼                         │
│              ┌───────────────────┐               │
│              │   WebSocket UI    │               │
│              └───────────────────┘               │
└──────────────────────────────────────────────────┘
```

**Characteristics:**
- Structured checkpoints at phase boundaries
- Before/after step execution
- UI-based approval via WebSocket events
- **Existing system - unchanged!**

---

### Layer 2: Agent-Level Approval (AG2 Handoffs)
```
┌──────────────────────────────────────────────────────────┐
│              AG2 Handoffs (Inside Conversation)          │
│                                                          │
│  ┌──────────────────────┐     ┌────────────────────┐   │
│  │ Mandatory Checkpoints│     │  Smart Approval    │   │
│  │   (Always human)     │     │  (LLM decides)     │   │
│  └──────────────────────┘     └────────────────────┘   │
│           │                             │               │
│           │   after_planning            │   High risk  │
│           │   before_file_edit          │   detected   │
│           │   before_execution          │   Uncertainty│
│           │   before_deploy             │   Complex    │
│           │                             │   decision   │
│           └─────────────┬───────────────┘               │
│                         │                               │
│                         ▼                               │
│              ┌─────────────────────┐                    │
│              │    Admin Agent      │                    │
│   agent.handoffs.set_after_work()  │                    │
│   agent.handoffs.add_llm_conditions()                   │
│              └─────────────────────┘                    │
│                         │                               │
│                         ▼                               │
│              ┌─────────────────────┐                    │
│              │   Human Interface   │                    │
│              │  (Console or UI)    │                    │
│              └─────────────────────┘                    │
└──────────────────────────────────────────────────────────┘
```

**Characteristics:**
- Dynamic agent-level decisions
- Inside conversation flow
- Admin agent participates naturally
- **NEW system - AG2-native!**

---

## Complete Workflow Flow

### Planning Phase with HITL

```
User Task
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ HITLPlanningPhase                                          │
│                                                            │
│  Task Improver                                            │
│       │                                                   │
│       ▼                                                   │
│  Planner Agent ──> generates plan                        │
│       │                                                   │
│       ▼                                                   │
│  Plan Reviewer ──> reviews plan                          │
│       │                                                   │
│       │  [AG2 HITL: use_ag2_handoffs=True]              │
│       │  [Checkpoint: 'after_planning']                 │
│       │                                                   │
│       ▼                                                   │
│  ┌──────────────────────────────────────────┐            │
│  │ Admin Agent (Human)                      │            │
│  │                                          │            │
│  │ "Review this plan:                      │            │
│  │  Step 1: Analyze data                   │            │
│  │  Step 2: Build model                    │            │
│  │  Step 3: Generate report                │            │
│  │                                          │            │
│  │ Options: Approve / Reject / Revise"     │            │
│  └──────────────────────────────────────────┘            │
│       │                                                   │
│       ▼                                                   │
│  [Human approves] ──> Control Phase continues            │
│  [Human rejects]  ──> Workflow fails                     │
│  [Human revises]  ──> Planner regenerates with feedback  │
│                                                            │
└─────────────────────────────────────────────────────────────┘
```

---

### Control Phase with HITL

```
┌─────────────────────────────────────────────────────────────┐
│ HITLControlPhase                                           │
│                                                             │
│  For each step in plan:                                    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Layer 1: WebSocket Approval (existing)              │  │
│  │                                                      │  │
│  │  "About to execute Step 1?"                         │  │
│  │  → User approves via UI                             │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Step Execution                                       │  │
│  │                                                      │  │
│  │  Control Agent ──> decides which agent to call      │  │
│  │       │                                              │  │
│  │       ▼                                              │  │
│  │  Engineer Agent ──> working on subtask...           │  │
│  │       │                                              │  │
│  │       │ Engineer says: "I need to edit config.yaml" │  │
│  │       │                                              │  │
│  │       │  [AG2 HITL: Checkpoint 'before_file_edit']  │  │
│  │       │                                              │  │
│  │       ▼                                              │  │
│  │  ┌──────────────────────────────────────────┐       │  │
│  │  │ Admin Agent (Human)                      │       │  │
│  │  │                                          │       │  │
│  │  │ "About to edit config.yaml:             │       │  │
│  │  │  - Add new API endpoint                 │       │  │
│  │  │  - Update timeout to 30s                │       │  │
│  │  │                                          │       │  │
│  │  │ Approve this file edit?"                │       │  │
│  │  └──────────────────────────────────────────┘       │  │
│  │       │                                              │  │
│  │       ▼                                              │  │
│  │  [Human approves] ──> Engineer continues            │  │
│  │                                                      │  │
│  │       │  Engineer: "delete old_data/"               │  │
│  │       │                                              │  │
│  │       │  [AG2 Smart Approval: keyword 'delete']     │  │
│  │       │                                              │  │
│  │       ▼                                              │  │
│  │  ┌──────────────────────────────────────────┐       │  │
│  │  │ Admin Agent (Human)                      │       │  │
│  │  │                                          │       │  │
│  │  │ "⚠️ High-risk operation detected:        │       │  │
│  │  │  About to delete old_data/              │       │  │
│  │  │                                          │       │  │
│  │  │ This contains 500 files.                │       │  │
│  │  │ Approve deletion?"                       │       │  │
│  │  └──────────────────────────────────────────┘       │  │
│  │       │                                              │  │
│  │       ▼                                              │  │
│  │  [Human approves] ──> Engineer executes deletion    │  │
│  │                                                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Layer 1: WebSocket Approval (existing)              │  │
│  │                                                      │  │
│  │  "Step 1 complete. Review results?"                 │  │
│  │  → User reviews via UI                              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  Repeat for Step 2, Step 3, ...                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Decision Flow

### When Mandatory Checkpoint Triggers

```
Agent completes work
       │
       │  Is there a mandatory checkpoint?
       ▼
  ┌─────────┐
  │   YES   │──────> ALWAYS hand off to admin
  └─────────┘              │
       │                   ▼
       │            ┌──────────────┐
       NO           │ Admin Agent  │
       │            │   (Human)    │
       │            └──────────────┘
       │                   │
       │              ┌────┴─────┐
       │              │          │
       │         Approved    Rejected
       │              │          │
       │              ▼          ▼
       │         Continue     Abort
       │
       ▼
  Normal handoff (LLM condition or explicit)
```

---

### When Smart Approval Evaluates

```
Agent is about to hand off
       │
       │  Check smart approval conditions
       ▼
  ┌──────────────────────────────────────┐
  │ LLM evaluates conversation context:  │
  │                                      │
  │ - High-risk keywords detected?       │
  │ - Production environment?            │
  │ - Uncertainty in message?            │
  │ - Complex decision needed?           │
  │ - Repeated failures?                 │
  └──────────────────────────────────────┘
       │
       ├────> If ANY condition met:
       │          │
       │          ▼
       │      ┌──────────────┐
       │      │ Admin Agent  │
       │      │   (Human)    │
       │      └──────────────┘
       │          │
       │     ┌────┴─────┐
       │     │          │
       │ Approved   Rejected
       │     │          │
       │     ▼          ▼
       │ Continue    Abort
       │
       └────> If NO condition met:
                  │
                  ▼
              Normal handoff
```

---

## Configuration Matrix

### HITLPlanningPhase

| Config | Effect |
|--------|--------|
| `use_ag2_handoffs=False` | Standard planning (no AG2 HITL) |
| `use_ag2_handoffs=True`<br>`ag2_mandatory_checkpoints=['after_planning']` | Human MUST review plan |
| `use_ag2_handoffs=True`<br>`ag2_smart_approval=True` | LLM decides when to escalate during planning |

### HITLControlPhase

| Config | Effect |
|--------|--------|
| `approval_mode='before_step'`<br>`use_ag2_handoffs=False` | WebSocket approval only (existing) |
| `approval_mode='before_step'`<br>`use_ag2_handoffs=True`<br>`ag2_mandatory_checkpoints=['before_file_edit']` | WebSocket + mandatory AG2 checkpoint for file edits |
| `approval_mode='before_step'`<br>`use_ag2_handoffs=True`<br>`ag2_smart_approval=True` | WebSocket + dynamic AG2 escalation |
| `approval_mode='never'`<br>`use_ag2_handoffs=True`<br>`ag2_smart_approval=True` | Only AG2 approvals (no WebSocket) |

---

## Agent Handoff Chains

### Without HITL
```
control ──> [engineer │ researcher │ terminator]
             (LLM decides based on task)
```

### With Mandatory Checkpoint
```
plan_reviewer ──> admin ──> control
                  (MUST)    (if approved)
```

### With Smart Approval
```
engineer ──> {risky?} ──yes──> admin ──> engineer
             (LLM)             (human)   (continues)
              │
              └─no──> continues normally
```

### Full HITL
```
Planning:
  planner ──> reviewer ──> admin ──> control
                          (MUST)    (if approved)

Control:
  control ──> engineer ──> {file edit?} ──yes──> admin ──> engineer
                           (MUST check)          (human)   (continues)
                                │
                                ├──> {risky?} ──yes──> admin ──> engineer
                                │    (smart)          (human)   (continues)
                                │
                                └──no──> continues normally
```

---

## File Organization

```
cmbagent/
├── handoffs/               # Modular handoff system
│   ├── hitl.py            # Mandatory + smart approval
│   ├── [10 other modules] # Planning, execution, etc.
│   └── README.md          # Module documentation
│
├── phases/
│   ├── hitl_planning.py   # Planning with AG2 handoffs
│   └── hitl_control.py    # Control with AG2 handoffs
│
└── docs/
    ├── AG2_HITL_PHASE_INTEGRATION.md    # Integration guide
    ├── HITL_HANDOFFS_QUICKREF.md        # Quick reference
    ├── HANDOFFS_REFACTOR_GUIDE.md       # Complete guide
    └── INTEGRATION_COMPLETE_SUMMARY.md   # Summary
```

---

## Summary

**Two approval systems working together:**

1. **WebSocket (Phase-level)**
   - Structured checkpoints
   - Before/after steps
   - UI-based
   - **Existing system**

2. **AG2 Handoffs (Agent-level)**
   - Dynamic agent decisions
   - Inside conversation
   - Mandatory + smart
   - **New AG2-native system**

**Result:** Comprehensive human oversight at both phase and agent levels!
