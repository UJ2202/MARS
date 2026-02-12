# Copilot Flow Design

## Overview

Three primary user flows that the copilot system should support:

---

## Flow 1: Complex Task with Clarification & Plan Approval

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLEX TASK FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌─────────────────┐    ┌──────────────────┐               │
│  │  User    │───►│ Task Analysis   │───►│ Needs            │               │
│  │  Input   │    │ (copilot_ctrl)  │    │ Clarification?   │               │
│  └──────────┘    └─────────────────┘    └────────┬─────────┘               │
│                                                   │                         │
│                         ┌─────────────────────────┼─────────────────────┐   │
│                         │ YES                     │ NO                  │   │
│                         ▼                         ▼                     │   │
│               ┌──────────────────┐      ┌──────────────────┐           │   │
│               │ HITL: Ask User   │      │ Create Plan      │           │   │
│               │ for Clarification│      │ (planning phase) │           │   │
│               └────────┬─────────┘      └────────┬─────────┘           │   │
│                        │                         │                      │   │
│                        │ User responds           │                      │   │
│                        ▼                         ▼                      │   │
│               ┌──────────────────┐      ┌──────────────────┐           │   │
│               │ Update Task with │      │ HITL: Present    │           │   │
│               │ Clarification    │─────►│ Plan for         │           │   │
│               └──────────────────┘      │ Approval         │           │   │
│                                         └────────┬─────────┘           │   │
│                                                  │                      │   │
│               ┌──────────────────────────────────┼──────────────────┐   │   │
│               │ APPROVE          │ MODIFY        │ REJECT           │   │   │
│               ▼                  ▼               ▼                  │   │   │
│     ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │   │   │
│     │ Execute Plan │   │ User Edits   │   │ Re-plan or   │         │   │   │
│     │ Step by Step │   │ Plan → Loop  │   │ Ask New Task │         │   │   │
│     └──────┬───────┘   └──────────────┘   └──────────────┘         │   │   │
│            │                                                        │   │   │
│            ▼                                                        │   │   │
│     ┌──────────────┐                                               │   │   │
│     │ HITL: Step   │ (optional, based on approval_mode)            │   │   │
│     │ Checkpoints  │                                               │   │   │
│     └──────┬───────┘                                               │   │   │
│            │                                                        │   │   │
│            ▼                                                        │   │   │
│     ┌──────────────┐                                               │   │   │
│     │ Complete     │                                               │   │   │
│     └──────────────┘                                               │   │   │
│                                                                     │   │   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation Requirements

1. **Clarification BEFORE Planning**
   - Move clarification check to happen first, before any routing
   - Location: `_execute_round()` should call `_check_clarification_needed()` first

2. **Plan Approval Checkpoint**
   - After planning completes, automatically trigger HITL checkpoint
   - Options: [Approve] [Modify] [Re-plan] [Cancel]

3. **Clarification Detection Improvements**
   - Remove word count threshold (currently `<= 5`)
   - Use LLM-based detection for ambiguity
   - Check for missing: purpose, inputs, outputs, constraints

---

## Flow 2: Simple Task Direct Execution

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SIMPLE TASK FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌─────────────────┐    ┌──────────────────┐               │
│  │  User    │───►│ Task Analysis   │───►│ Simple Task?     │               │
│  │  Input   │    │ (complexity<30) │    │ (clear, 1-2 step)│               │
│  └──────────┘    └─────────────────┘    └────────┬─────────┘               │
│                                                   │                         │
│                                        YES        │                         │
│                                                   ▼                         │
│                                         ┌──────────────────┐               │
│                                         │ Direct Agent     │               │
│                                         │ Execution        │               │
│                                         │ (one_shot mode)  │               │
│                                         └────────┬─────────┘               │
│                                                  │                         │
│                                                  ▼                         │
│                                         ┌──────────────────┐               │
│                                         │ HITL: Result     │               │
│                                         │ Satisfaction     │               │
│                                         │ Check            │               │
│                                         └────────┬─────────┘               │
│                                                  │                         │
│               ┌──────────────────────────────────┼──────────────────┐      │
│               │ SATISFIED        │ NEEDS CHANGES │ NEW TASK         │      │
│               ▼                  ▼               ▼                  │      │
│     ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │      │
│     │ Complete     │   │ Iterate with │   │ Start New    │         │      │
│     │              │   │ Feedback     │   │ Flow         │         │      │
│     └──────────────┘   └──────────────┘   └──────────────┘         │      │
│                                                                     │      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation Requirements

1. **Post-Execution Satisfaction Check**
   - After agent completes, automatically ask: "Does this meet your needs?"
   - Options: [Yes, done] [Needs changes] [Start over]

2. **Iteration Support**
   - If user says "needs changes", incorporate feedback and re-execute
   - Keep context from previous attempt

---

## Flow 3: Conversational with Implementation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONVERSATIONAL FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐                                                              │
│  │  User    │ "Help me design a new authentication system"                 │
│  │  Input   │                                                              │
│  └────┬─────┘                                                              │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    CONVERSATION MODE                             │       │
│  │  ┌─────────────────────────────────────────────────────────┐    │       │
│  │  │                                                         │    │       │
│  │  │  Agent: "I can help! What auth method do you prefer?"   │    │       │
│  │  │  ↓                                                      │    │       │
│  │  │  User: "OAuth with Google and GitHub"                   │    │       │
│  │  │  ↓                                                      │    │       │
│  │  │  Agent: "Good choice. Session storage?"                 │    │       │
│  │  │  ↓                                                      │    │       │
│  │  │  User: "JWT tokens"                                     │    │       │
│  │  │  ↓                                                      │    │       │
│  │  │  Agent: "Here's what I understand: [summary]"           │    │       │
│  │  │  ↓                                                      │    │       │
│  │  │  User: "Yes, implement it"  ◄── TRANSITION TRIGGER      │    │       │
│  │  │                                                         │    │       │
│  │  └─────────────────────────────────────────────────────────┘    │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│       │                                                                     │
│       │ Detected: "implement", "build", "create", "do it"                  │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    EXECUTION MODE                                │       │
│  │                                                                  │       │
│  │  ┌──────────────┐                                               │       │
│  │  │ Create Plan  │ (from conversation context)                   │       │
│  │  └──────┬───────┘                                               │       │
│  │         │                                                        │       │
│  │         ▼                                                        │       │
│  │  ┌──────────────┐    ┌──────────────┐                          │       │
│  │  │ Execute      │───►│ User can     │                          │       │
│  │  │ Step 1       │    │ PAUSE here   │                          │       │
│  │  └──────────────┘    └──────┬───────┘                          │       │
│  │                              │                                   │       │
│  │         ┌────────────────────┼────────────────────┐             │       │
│  │         │ PAUSE              │ CONTINUE           │             │       │
│  │         ▼                    ▼                    │             │       │
│  │  ┌──────────────┐    ┌──────────────┐            │             │       │
│  │  │ HITL: Get    │    │ Execute      │            │             │       │
│  │  │ User Input   │    │ Step 2...N   │            │             │       │
│  │  └──────┬───────┘    └──────────────┘            │             │       │
│  │         │                                         │             │       │
│  │         │ User provides input                     │             │       │
│  │         ▼                                         │             │       │
│  │  ┌──────────────┐                                │             │       │
│  │  │ Incorporate  │                                │             │       │
│  │  │ & Continue   │────────────────────────────────┘             │       │
│  │  └──────────────┘                                               │       │
│  │                                                                  │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation Requirements

1. **Conversation to Execution Transition**
   - Detect intent to implement: "implement", "build", "create it", "do it", "go ahead"
   - Compile conversation into structured requirements
   - Transition to planning/execution mode

2. **Mid-Execution Pause**
   - User can click [Pause] at any time
   - System completes current step, then waits
   - User provides input/feedback
   - System incorporates and continues

3. **Context Preservation**
   - All conversation context flows into execution
   - User decisions recorded and available to agents

---

## Configuration Modes

```python
# Flow 1: Complex with approval
copilot(
    task="...",
    intelligent_routing="aggressive",  # Ask questions for ambiguity
    approval_mode="both",              # Before AND after steps
    enable_planning=True,
    plan_approval=True,                # NEW: Require plan approval
)

# Flow 2: Simple direct
copilot(
    task="...",
    intelligent_routing="minimal",     # Prefer action
    approval_mode="after_step",        # Check satisfaction after
    enable_planning=False,             # Skip planning
    auto_approve_simple=True,
)

# Flow 3: Conversational
copilot(
    task="...",
    conversational=True,               # Human in every turn
    allow_execution_transition=True,   # NEW: Allow "implement" trigger
    pause_enabled=True,                # NEW: Allow mid-execution pause
)
```

---

## Key Changes Required

### 1. Clarification First (Before Routing)

```python
# In _execute_round() - add at the beginning
async def _execute_round(self):
    # FIRST: Check if clarification needed
    if self.state.current_round == 0:
        clarification_result = await self._check_clarification_needed()
        if clarification_result.get('needs_clarification'):
            return await self._handle_clarification_request(clarification_result)

    # THEN: Normal routing and execution
    ...
```

### 2. Plan Approval Checkpoint

```python
# In planning phase or after invoke_planning_phase
async def _execute_phase_as_tool(self, phase_type, task, config):
    ...
    result = await phase.execute(phase_context)

    # NEW: If planning phase, trigger approval
    if phase_type == "planning" and self.config.plan_approval:
        approval_result = await self._request_plan_approval(result)
        if approval_result.get('action') == 'reject':
            return self._handle_plan_rejection(approval_result)
        elif approval_result.get('action') == 'modify':
            return self._handle_plan_modification(approval_result)
    ...
```

### 3. Satisfaction Check

```python
# After task completion
async def _post_execution_satisfaction_check(self, result):
    if not self._approval_manager:
        return result

    request = self._approval_manager.create_approval_request(
        checkpoint_type="satisfaction",
        message="Does this result meet your needs?",
        options=["satisfied", "needs_changes", "start_over"],
    )

    resolved = await self._approval_manager.wait_for_approval_async(...)

    if resolved.resolution == "needs_changes":
        # Incorporate feedback and re-execute
        self.state.current_task += f"\n\nUser Feedback: {resolved.user_feedback}"
        return await self._execute_round()
    ...
```

### 4. Conversation-to-Execution Transition

```python
# In conversational loop
async def _process_human_response(self, response):
    # Detect implementation intent
    impl_triggers = ['implement', 'build', 'create it', 'do it', 'go ahead', 'make it']

    if any(trigger in response.lower() for trigger in impl_triggers):
        # Transition to execution mode
        requirements = self._compile_conversation_to_requirements()
        self._is_conversational = False  # Exit conversation mode
        return await self._start_execution_from_conversation(requirements)

    # Continue conversation
    ...
```

### 5. Mid-Execution Pause Support

```python
# Check before each step
async def _execute_step(self, step):
    # Check for user pause request
    if self._check_pause_requested():
        pause_result = await self._handle_pause()
        if pause_result.get('action') == 'stop':
            return {'status': 'stopped_by_user'}
        # Incorporate any user input
        self._incorporate_pause_feedback(pause_result)

    # Execute step
    ...
```

---

## UI Components Needed

### 1. Clarification Dialog
- Shows questions
- Text input for answers
- [Submit] [Skip] buttons

### 2. Plan Approval Dialog
- Shows plan steps
- [Approve] [Modify] [Re-plan] [Cancel] buttons
- Edit capability for modifications

### 3. Satisfaction Dialog
- Shows result summary
- [Satisfied] [Needs Changes] [Start Over] buttons
- Feedback text input

### 4. Execution Control
- [Pause] button visible during execution
- Progress indicator
- Current step display

### 5. Conversation Mode
- Chat interface
- Detected intent indicators
- [Implement Now] quick action button
