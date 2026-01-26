# CMBAgent Workflow Visual Diagram

Complete visual representation of the Planning and Control workflow with agent handoffs.

---

## 🎯 **HIGH-LEVEL OVERVIEW**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PLANNING & CONTROL WORKFLOW                           │
└─────────────────────────────────────────────────────────────────────────┘

User Task: "Analyze CMB power spectrum with CLASS"
    │
    ├─────────────────────────────────────────────────────────────────────┐
    │                                                                       │
    ▼                                                                       │
┌────────────────────┐                                                     │
│  1. INITIALIZE     │                                                     │
│  - Setup dirs      │                                                     │
│  - Load API keys   │                                                     │
│  - Init callbacks  │                                                     │
└────────┬───────────┘                                                     │
         │                                                                  │
         ▼                                                                  │
┌────────────────────┐                                                     │
│  2. PLANNING       │  ◄─── Agent Swarm (5-10 agents)                   │
│  - Create plan     │       Iterative refinement                         │
│  - Review plan     │       LLM-driven collaboration                     │
│  - Refine plan     │                                                    │
└────────┬───────────┘                                                     │
         │                                                                  │
         ▼                                                                  │
┌────────────────────┐                                                     │
│  3. APPROVAL       │  ◄─── HITL Checkpoint (optional)                   │
│  (if enabled)      │       User: Approve/Reject/Modify                  │
└────────┬───────────┘                                                     │
         │                                                                  │
         ▼                                                                  │
┌────────────────────┐                                                     │
│  4. CONTROL        │  ◄─── Agent Swarm (10-20 agents)                   │
│  Step 1: Research  │       Execute plan step-by-step                    │
│  Step 2: Code      │       Context carryover between steps              │
│  Step 3: Execute   │                                                    │
│  Step N: Report    │                                                    │
└────────┬───────────┘                                                     │
         │                                                                  │
         ▼                                                                  │
┌────────────────────┐                                                     │
│  5. FINALIZE       │                                                     │
│  - Save results    │                                                     │
│  - Collect files   │                                                     │
│  - Display costs   │                                                     │
└────────┬───────────┘                                                     │
         │                                                                  │
         ▼                                                                  │
    Results returned to user                                               │
         │                                                                  │
         └───────────────────────────────────────────────────────────────┘
                    (Context carries through entire workflow)
```

---

## 🔄 **PLANNING PHASE - DETAILED AGENT FLOW**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          PLANNING PHASE                                   │
│  Goal: Create a multi-step execution plan through agent collaboration   │
└──────────────────────────────────────────────────────────────────────────┘

USER TASK
    │
    ▼
┌───────────────────┐
│   plan_setter     │  Role: Initialize planning session
│   (ConvAgent)     │  Action: "Let's create a plan for this task"
└─────────┬─────────┘  Context: {task, max_steps, constraints}
          │
          │ handoff: set_after_work(planner)
          ▼
┌───────────────────┐
│     planner       │  Role: Design multi-step plan
│   (ConvAgent)     │  Action: "Step 1: Load data, Step 2: Analyze..."
└─────────┬─────────┘  LLM: gpt-4o (default)
          │            Temperature: 0.0 (deterministic)
          │
          │ handoff: set_after_work(planner_response_formatter)
          ▼
┌───────────────────┐
│ planner_response  │  Role: Format plan into structured JSON
│    _formatter     │  Action: Extract steps, agents, dependencies
└─────────┬─────────┘  LLM: gpt-4o-mini (faster formatter)
          │
          │ handoff: set_after_work(plan_recorder)
          ▼
┌───────────────────┐
│  plan_recorder    │  Role: Save plan to database/file
│   (ConvAgent)     │  Action: Write to final_plan.json
└─────────┬─────────┘  Side Effect: Persist plan for control phase
          │
          │ handoff: set_after_work(plan_reviewer)
          ▼
┌───────────────────┐
│  plan_reviewer    │  Role: Critique and improve plan
│   (ConvAgent)     │  Action: "Good plan, but add error handling to Step 2"
└─────────┬─────────┘  LLM: gpt-4o (critical thinking)
          │            Context: {plan, max_steps, hardware_constraints}
          │
          │ handoff: set_after_work(reviewer_response_formatter)
          ▼
┌───────────────────┐
│ reviewer_response │  Role: Format review feedback
│    _formatter     │  Action: Structure critique into actionable items
└─────────┬─────────┘  LLM: gpt-4o-mini
          │
          │ handoff: set_after_work(review_recorder)
          ▼
┌───────────────────┐
│ review_recorder   │  Role: Save review feedback
│   (ConvAgent)     │  Action: Append feedback to context
└─────────┬─────────┘  Context Update: feedback_left -= 1
          │
          │ Decision Point: feedback_left > 0?
          │
          ├─── YES ──────────────────────┐
          │                               │
          │ handoff: back to planner      │
          │                               │
          ▼                               │
┌───────────────────┐                    │
│     planner       │  Role: Refine plan based on feedback
│  (iteration 2+)   │  Action: "Updated Step 2 with error handling"
└─────────┬─────────┘                    │
          │                               │
          └───── (loop continues) ────────┘
          │
          │
          ├─── NO ──────────────────────┐
          │                              │
          ▼                              │
┌───────────────────┐                   │
│   terminator      │  Role: End planning phase
│   (ConvAgent)     │  Action: "TERMINATE" (stops AG2 loop)
└─────────┬─────────┘                   │
          │                              │
          ▼                              │
    PLANNING COMPLETE                    │
    Output: final_plan.json              │
    {                                    │
      "sub_tasks": [                     │
        {                                │
          "sub_task": "Load CMB data",   │
          "sub_task_agent": "engineer",  │
          "bullet_points": [...]         │
        },                               │
        ...                              │
      ]                                  │
    }                                    │
                                         │
          │                              │
          └──────────────────────────────┘
          │
          ▼
    Proceed to APPROVAL or CONTROL
```

### **Planning Phase - Iteration Example**

```
Iteration 1:
planner → "Step 1: Load data, Step 2: Run analysis"
reviewer → "Add error handling and validation"

Iteration 2:
planner → "Step 1: Load + validate data, Step 2: Run with error handling"
reviewer → "Looks good, proceed"

Result: Final plan approved
```

---

## ⚙️ **CONTROL PHASE - DETAILED AGENT FLOW**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           CONTROL PHASE                                   │
│  Goal: Execute each step of the plan with context carryover             │
└──────────────────────────────────────────────────────────────────────────┘

Load final_plan.json → Extract sub_tasks array → Execute sequentially

════════════════════════════════════════════════════════════════════════════
STEP 1: Load CMB Data
════════════════════════════════════════════════════════════════════════════

Context IN: {
  final_plan: [...],
  current_sub_task: "Load CMB data",
  agent_for_sub_task: "engineer",
  current_plan_step_number: 1,
  ...
}

    │
    ▼
┌───────────────────┐
│     control       │  Role: Route to appropriate specialist
│   (ConvAgent)     │  Action: Analyze step → decide agent
└─────────┬─────────┘  Decision Logic: "Need to write code → call engineer"
          │
          │ handoff: AgentTarget(engineer)
          ▼
┌───────────────────┐
│     engineer      │  Role: Write Python code
│   (ConvAgent)     │  Action: Generate script to load CMB data
└─────────┬─────────┘  LLM: gpt-4-turbo (coding optimized)
          │            Output: ```python\n# Load data\nimport numpy as np\n...```
          │
          │ handoff: set_after_work(engineer_response_formatter)
          ▼
┌───────────────────┐
│   engineer_resp   │  Role: Extract code blocks
│    _formatter     │  Action: Parse ```python blocks → save to file
└─────────┬─────────┘  Side Effect: self.python_code = extracted_code
          │
          │ handoff: set_after_work(executor) [nested chat]
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        NESTED CHAT: EXECUTOR                             │
│  (GroupChat with round_robin speaker selection)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───────────────────┐                                                  │
│  │    executor       │  Role: Execute Python code                       │
│  │  (UserProxyAgent) │  Action: Run code in LocalCommandLineCodeExecutor│
│  └─────────┬─────────┘  Code Execution: subprocess in work_dir          │
│            │                                                             │
│            ▼                                                             │
│  ┌───────────────────┐                                                  │
│  │ executor_response │  Role: Format execution results                  │
│  │    _formatter     │  Action: Capture stdout, files, errors           │
│  └─────────┬─────────┘  MessageHistoryLimiter: Keep only last message  │
│            │                                                             │
│            ▼                                                             │
│  Execution Result: {                                                    │
│    stdout: "Loaded 1000 data points...",                                │
│    files_created: ["data.npy"],                                         │
│    exit_code: 0                                                          │
│  }                                                                       │
└──────────────────────────────────────────────────────────────────────────┘
          │
          │ handoff: back to control
          ▼
┌───────────────────┐
│     control       │  Role: Verify step completion
│   (iteration 2)   │  Action: "Step 1 complete, proceeding to Step 2"
└─────────┬─────────┘
          │
          ▼
Context OUT: {
  ...Context IN,
  step_1_result: {files: ["data.npy"], status: "success"},
  completed_steps: [1],
  ...
}

════════════════════════════════════════════════════════════════════════════
STEP 2: Analyze CMB Power Spectrum
════════════════════════════════════════════════════════════════════════════

Context IN: {
  ...Context OUT from Step 1 (carries over!),
  current_sub_task: "Analyze power spectrum",
  agent_for_sub_task: "researcher",
  current_plan_step_number: 2,
  ...
}

    │
    ▼
┌───────────────────┐
│     control       │  Role: Route to researcher
│   (ConvAgent)     │  Decision: "Need literature → call researcher"
└─────────┬─────────┘
          │
          │ handoff: AgentTarget(researcher)
          ▼
┌───────────────────┐
│   researcher      │  Role: Retrieve literature/documentation
│  (RAG Agent)      │  Action: Query vector store for CMB analysis methods
└─────────┬─────────┘  Tool: file_search (RAG retrieval)
          │            LLM: gpt-4o + OpenAI Assistant API
          │
          │ handoff: set_after_work(researcher_response_formatter)
          ▼
┌───────────────────┐
│ researcher_resp   │  Role: Format research findings
│    _formatter     │  Action: Compile literature into actionable summary
└─────────┬─────────┘
          │
          │ handoff: set_after_work(researcher_executor)
          ▼
┌───────────────────┐
│ researcher_exec   │  Role: Save research to file
│   (UserProxy)     │  Action: Write summary.md
└─────────┬─────────┘
          │
          │ handoff: back to control
          ▼
┌───────────────────┐
│     control       │  Role: Proceed to next step or finish
│   (iteration 3)   │  Action: "Step 2 complete, moving to Step 3"
└─────────┬─────────┘
          │
          ▼
Context OUT: {
  ...Context IN,
  step_2_result: {files: ["summary.md"], literature: [...]},
  completed_steps: [1, 2],
  ...
}

════════════════════════════════════════════════════════════════════════════
STEP N: Final Report
════════════════════════════════════════════════════════════════════════════

(Similar flow, but with summarizer agent)

Context IN: All previous step contexts accumulated!

    │
    ▼
┌───────────────────┐
│   summarizer      │  Role: Generate final report
│   (ConvAgent)     │  Action: Compile all results into report
└─────────┬─────────┘  Context: Has access to ALL previous steps
          │
          ▼
┌───────────────────┐
│   terminator      │  Role: End control phase
│   (ConvAgent)     │  Action: "TERMINATE"
└─────────┬─────────┘
          │
          ▼
    CONTROL COMPLETE
```

---

## 🔀 **DECISION POINTS & ROUTING**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                  CONTROL AGENT ROUTING LOGIC                              │
│  (How control agent decides which specialist to call)                    │
└──────────────────────────────────────────────────────────────────────────┘

                          ┌───────────────┐
                          │   control     │
                          │   (brain)     │
                          └───────┬───────┘
                                  │
                  ┌───────────────┴───────────────┐
                  │ Analyze current_sub_task      │
                  │ Check agent_for_sub_task      │
                  │ Examine context               │
                  └───────────────┬───────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐        ┌───────────────┐        ┌───────────────┐
│ Need code?    │        │ Need research?│        │ Need external │
│ → engineer    │        │ → researcher  │        │ API?          │
└───────────────┘        └───────────────┘        │ → perplexity  │
        │                         │                └───────────────┘
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐        ┌───────────────┐        ┌───────────────┐
│ Need CAMB     │        │ Need Cobaya   │        │ Need brainstorm│
│ docs?         │        │ docs?         │        │ ideas?        │
│ → camb_context│        │ → cobaya      │        │ → idea_maker  │
└───────────────┘        └───────────────┘        └───────────────┘

Each specialist has its own handoff chain!
```

---

## 🔁 **CONTEXT CARRYOVER MECHANISM**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     CONTEXT CARRYOVER ACROSS STEPS                        │
│  (How information flows between steps)                                   │
└──────────────────────────────────────────────────────────────────────────┘

Step 0 (Planning):
┌────────────────────────────────────────────────┐
│ Context_0 = {                                  │
│   final_plan: [...],                           │
│   number_of_steps_in_plan: 3,                  │
│   work_dir: "/path/to/work",                   │
│   database_path: "data",                       │
│   codebase_path: "codebase"                    │
│ }                                               │
└────────────────────────────────────────────────┘
           │
           │ Save: context_step_0.pkl
           ▼
Step 1:
┌────────────────────────────────────────────────┐
│ Context_1 = {                                  │
│   ...Context_0,  ◄── ALL previous context     │
│   current_plan_step_number: 1,                 │
│   current_sub_task: "Load data",               │
│   agent_for_sub_task: "engineer",              │
│   step_1_result: {                             │
│     files: ["data.npy"],                       │
│     status: "success"                          │
│   }                                             │
│ }                                               │
└────────────────────────────────────────────────┘
           │
           │ Save: context_step_1.pkl
           ▼
Step 2:
┌────────────────────────────────────────────────┐
│ Context_2 = {                                  │
│   ...Context_0,  ◄── Still has original plan  │
│   ...Context_1,  ◄── Plus Step 1 results      │
│   current_plan_step_number: 2,                 │
│   current_sub_task: "Analyze",                 │
│   agent_for_sub_task: "researcher",            │
│   step_2_result: {                             │
│     files: ["analysis.md"],                    │
│     literature: [...]                          │
│   }                                             │
│ }                                               │
└────────────────────────────────────────────────┘
           │
           │ Save: context_step_2.pkl
           ▼
Step 3:
┌────────────────────────────────────────────────┐
│ Context_3 = {                                  │
│   ...Context_0,  ◄── Original                 │
│   ...Context_1,  ◄── Step 1                   │
│   ...Context_2,  ◄── Step 2                   │
│   current_plan_step_number: 3,                 │
│   current_sub_task: "Report",                  │
│   FULL HISTORY OF ALL STEPS!                   │
│ }                                               │
└────────────────────────────────────────────────┘

This allows later steps to reference earlier work!
```

---

## 🎭 **NESTED CHAT GROUPS**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    NESTED CHAT: EXECUTOR GROUP                            │
│  (Mini team for code execution)                                          │
└──────────────────────────────────────────────────────────────────────────┘

Main Chat (AutoPattern)
    │
    ├─── engineer generates code
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  NESTED: Executor GroupChat (RoundRobin)                                │
│                                                                          │
│  Participants:                                                           │
│  - engineer_response_formatter                                           │
│  - executor (UserProxyAgent with code execution)                         │
│                                                                          │
│  Flow:                                                                   │
│  1. formatter extracts code from engineer's message                      │
│  2. executor runs code in isolated environment                           │
│  3. formatter processes results                                          │
│  4. Loop until code executes successfully OR max_attempts reached        │
│                                                                          │
│  Max Rounds: 3                                                           │
│  Speaker Selection: round_robin (alternating)                            │
│                                                                          │
│  Message History: Limited to last 1 message (MessageHistoryLimiter)     │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Result passed back to main chat

┌──────────────────────────────────────────────────────────────────────────┐
│                    NESTED CHAT: IDEA MAKER GROUP                          │
│  (Mini team for brainstorming)                                           │
└──────────────────────────────────────────────────────────────────────────┘

Main Chat (AutoPattern)
    │
    ├─── control requests brainstorming
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  NESTED: Idea Maker GroupChat (RoundRobin)                              │
│                                                                          │
│  Participants:                                                           │
│  - idea_maker (generates ideas)                                          │
│  - idea_hater (critiques ideas)                                          │
│  - idea_saver (records best ideas)                                       │
│                                                                          │
│  Flow:                                                                   │
│  1. idea_maker proposes approach                                         │
│  2. idea_hater critiques                                                 │
│  3. idea_maker refines                                                   │
│  4. idea_saver records final idea                                        │
│                                                                          │
│  Max Rounds: 6 (2 full cycles)                                           │
│  Speaker Selection: round_robin                                          │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Best idea passed back to main chat
```

---

## 📊 **DATA FLOW DIAGRAM**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW THROUGH WORKFLOW                         │
└──────────────────────────────────────────────────────────────────────────┘

USER TASK (string)
    │
    ├──────────────────────────────────────────────────────────┐
    │                                                            │
    ▼                                                            │
[Planning Phase]                                                 │
    │                                                            │
    ├─→ Agents collaborate via messages                         │
    ├─→ Context shared via ContextVariables                     │
    ├─→ Plan saved to final_plan.json                           │
    │                                                            │
    ▼                                                            │
PLAN OBJECT                                                      │
{                                                                │
  "sub_tasks": [                                                 │
    {"sub_task": "...", "sub_task_agent": "..."},               │
    ...                                                          │
  ],                                                             │
  "number_of_steps_in_plan": N                                  │
}                                                                │
    │                                                            │
    ├─→ Saved to context_step_0.pkl                             │
    │                                                            │
    ▼                                                            │
[Approval Gate]                                                  │
    │                                                            │
    ├─→ Shown to user via WebSocket                             │
    ├─→ User provides approval/rejection/feedback               │
    │                                                            │
    ▼                                                            │
APPROVED PLAN (possibly modified)                                │
    │                                                            │
    ▼                                                            │
[Control Phase - Loop through steps]                             │
    │                                                            │
    ├─ FOR step 1 TO N:                                         │
    │   │                                                        │
    │   ├─→ Load context from previous step                     │
    │   ├─→ Add current step info to context                    │
    │   ├─→ Agents execute step                                 │
    │   ├─→ Files created/modified                              │
    │   ├─→ Results added to context                            │
    │   ├─→ Save context_step_N.pkl                             │
    │   │                                                        │
    │   ▼                                                        │
    │ STEP RESULT                                                │
    │ {                                                          │
    │   files: [...],                                            │
    │   outputs: {...},                                          │
    │   timing: {...},                                           │
    │   errors: [...]                                            │
    │ }                                                          │
    │   │                                                        │
    │   └─→ Carried to next step                                │
    │                                                            │
    ▼                                                            │
AGGREGATED RESULTS                                               │
{                                                                │
  chat_history: [...],                                           │
  final_context: {all steps combined},                           │
  initialization_time_planning: X,                               │
  execution_time_planning: Y,                                    │
  initialization_time_control: Z,                                │
  execution_time_control: W,                                     │
  outputs: {                                                     │
    files: [...],                                                │
    manifest: {...}                                              │
  },                                                             │
  run_id: "uuid"                                                 │
}                                                                │
    │                                                            │
    └────────────────────────────────────────────────────────────┘
    │
    ▼
RETURNED TO USER

SIDE EFFECTS (on disk):
- work_dir/planning/final_plan.json
- work_dir/control/data/*.npy
- work_dir/control/codebase/*.py
- work_dir/context/context_step_*.pkl
- work_dir/time/timing_report_*.json
- work_dir/cost/cost_report.json
```

---

## 🔄 **RETRY & ERROR HANDLING FLOW**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      ERROR HANDLING & RETRY LOGIC                         │
└──────────────────────────────────────────────────────────────────────────┘

Step Execution
    │
    ├─→ Try to execute
    │
    ▼
┌───────────────┐
│ Success?      │
└───┬───────┬───┘
    │       │
   YES      NO
    │       │
    │       ▼
    │   ┌─────────────────────────┐
    │   │ n_attempts < max_attempts?│
    │   └────┬────────────────┬────┘
    │       YES               NO
    │        │                 │
    │        ▼                 ▼
    │   ┌─────────┐      ┌─────────┐
    │   │ Retry   │      │ Fail    │
    │   │ n++     │      │ Step    │
    │   └────┬────┘      └─────────┘
    │        │                 │
    │        └─→ (loop back)   │
    │                          │
    ▼                          ▼
Proceed to next step    Workflow stops
                        (or skip if configured)

Context tracks n_attempts per step!
```

---

## 🎨 **AGENT TYPES & CAPABILITIES**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           AGENT TAXONOMY                                  │
└──────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ ConversableAgent (Standard LLM agents)                          │
├─────────────────────────────────────────────────────────────────┤
│ - planner, plan_reviewer, engineer, researcher                  │
│ - idea_maker, idea_hater, control, summarizer                   │
│ - Capabilities: Generate text, reason, decide handoffs          │
│ - No code execution                                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ UserProxyAgent (Code executors)                                 │
├─────────────────────────────────────────────────────────────────┤
│ - executor, researcher_executor, executor_bash                  │
│ - Capabilities: Run Python/bash code in LocalCommandLineCodeExec│
│ - No LLM calls (just execute)                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ GPTAssistantAgent (RAG agents with vector stores)               │
├─────────────────────────────────────────────────────────────────┤
│ - camb_agent, cobaya_agent, classy_sz_agent, planck_agent       │
│ - Capabilities: file_search tool (retrieval from docs)          │
│ - Uses OpenAI Assistant API + vector stores                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Formatter Agents (Response processors)                          │
├─────────────────────────────────────────────────────────────────┤
│ - *_response_formatter agents                                   │
│ - Capabilities: Extract code, format output, clean responses    │
│ - Use faster models (gpt-4o-mini)                               │
│ - MessageHistoryLimiter (only see last message)                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Recorder Agents (State persistence)                             │
├─────────────────────────────────────────────────────────────────┤
│ - plan_recorder, review_recorder, task_recorder                 │
│ - Capabilities: Save to files, update context                   │
│ - Side effects: Write JSON, update ContextVariables             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Special Agents                                                  │
├─────────────────────────────────────────────────────────────────┤
│ - terminator: Ends conversation (returns "TERMINATE")           │
│ - admin: Human proxy (can interrupt workflow)                   │
│ - control: Master router (decides which specialist to call)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧩 **MODULAR REFACTORING PROPOSAL**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    FROM MONOLITH TO MODULAR                               │
└──────────────────────────────────────────────────────────────────────────┘

CURRENT (900 lines):
┌──────────────────────────────────────────────────────────────┐
│ planning_control.py                                          │
│                                                              │
│ def planning_and_control_context_carryover():               │
│     # Everything in one function:                           │
│     - Setup directories                                     │
│     - Load API keys                                         │
│     - Initialize callbacks                                  │
│     - Create planning agents                                │
│     - Run planning                                          │
│     - Handle approval                                       │
│     - Loop through control steps                            │
│     - Create execution agents per step                      │
│     - Execute step                                          │
│     - Save context                                          │
│     - Aggregate results                                     │
│     - Cleanup                                               │
│     - Return                                                │
└──────────────────────────────────────────────────────────────┘

PROPOSED (modular):
┌──────────────────────────────────────────────────────────────┐
│ workflows/planning_control/                                  │
│                                                              │
│ ├─ __init__.py (exports main function)                      │
│ │                                                            │
│ ├─ orchestrator.py (50 lines)                               │
│ │   └─ planning_and_control_context_carryover()            │
│ │       → Calls sub-functions                               │
│ │                                                            │
│ ├─ setup.py (100 lines)                                     │
│ │   ├─ initialize_workflow()                                │
│ │   ├─ setup_directories()                                  │
│ │   ├─ load_api_keys()                                      │
│ │   └─ initialize_callbacks()                               │
│ │                                                            │
│ ├─ planning.py (200 lines)                                  │
│ │   ├─ execute_planning_phase()                             │
│ │   ├─ create_planning_agent()                              │
│ │   ├─ extract_plan()                                       │
│ │   └─ save_plan()                                          │
│ │                                                            │
│ ├─ approval.py (100 lines)                                  │
│ │   ├─ handle_planning_approval()                           │
│ │   ├─ wait_for_approval()                                  │
│ │   └─ incorporate_feedback()                               │
│ │                                                            │
│ ├─ control.py (300 lines)                                   │
│ │   ├─ execute_control_phase()                              │
│ │   ├─ execute_single_step()                                │
│ │   ├─ create_execution_agent()                             │
│ │   └─ prepare_step_context()                               │
│ │                                                            │
│ └─ finalization.py (100 lines)                              │
│     ├─ finalize_workflow()                                  │
│     ├─ save_results()                                       │
│     └─ cleanup_directories()                                │
└──────────────────────────────────────────────────────────────┘

Benefits:
✅ Each module is testable independently
✅ Easy to understand (50-300 lines per file)
✅ Reusable components
✅ Clear separation of concerns
✅ Easier to maintain and extend
```

---

## 📝 **SUMMARY: KEY CONCEPTS**

| Concept | Explanation |
|---------|-------------|
| **Workflow** | Planning Phase + Control Phase |
| **Planning Phase** | Agents collaborate to create multi-step plan |
| **Control Phase** | Agents execute plan step-by-step |
| **Handoff** | One agent finishes → automatically triggers next agent |
| **Handoff Chain** | Series of handoffs forming a workflow path |
| **Context Carryover** | Previous step results available to next step |
| **Nested Chat** | Sub-group of agents with its own orchestration |
| **AutoPattern** | AG2's automatic agent coordination pattern |
| **ContextVariables** | Shared state dictionary accessible by all agents |
| **Approval Gate** | Human-in-the-loop checkpoint for plan review |

---

## 🎓 **LEARNING PATH**

```
For someone with zero knowledge, learn in this order:

1. ✅ Understand what a single agent does
   → Read: cmbagent/agents/*/agent.yaml

2. ✅ Understand agent handoffs
   → Read: cmbagent/hand_offs.py
   → Concept: agent.handoffs.set_after_work(next_agent)

3. ✅ Understand AutoPattern
   → Concept: Agents decide flow dynamically
   → Read: cmbagent/cmbagent.py (solve method)

4. ✅ Understand Planning Phase flow
   → This diagram: PLANNING PHASE section
   → Run: tests/test_planning.py (if exists)

5. ✅ Understand Control Phase flow
   → This diagram: CONTROL PHASE section
   → Run: tests/test_control.py (if exists)

6. ✅ Understand Context Carryover
   → This diagram: CONTEXT CARRYOVER section
   → Key: Each step builds on previous steps

7. ✅ Understand full workflow
   → This diagram: HIGH-LEVEL OVERVIEW
   → Run: python -m cmbagent.cli (try it yourself!)

8. ✅ Ready to refactor!
   → Understand modular architecture
   → Start implementing small methods
```

---

**Next Steps:**
- Study specific agent handoff chains you're interested in
- Try running the workflow with debug mode to see agent flow
- Ask about specific sections you want clarified
- Ready to implement the modular refactoring!
