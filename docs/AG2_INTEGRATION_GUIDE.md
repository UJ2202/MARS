# AG2 (AutoGen) Integration Guide

> **Comprehensive documentation on how CMBAgent uses AG2 (AutoGen) framework**

---

## Table of Contents

1. [AG2 Overview](#ag2-overview)
2. [AG2 Components Used by CMBAgent](#ag2-components-used-by-cmbagent)
3. [Agent Types and Base Classes](#agent-types-and-base-classes)
4. [Group Chat and Orchestration](#group-chat-and-orchestration)
5. [Hand-offs and Agent Transitions](#hand-offs-and-agent-transitions)
6. [Context Variables and State Management](#context-variables-and-state-management)
7. [Function Registration](#function-registration)
8. [Code Execution](#code-execution)
9. [Nested Chats](#nested-chats)
10. [Message Transforms](#message-transforms)
11. [Interoperability with External Tools](#interoperability-with-external-tools)
12. [IOStream for Event Capture](#iostream-for-event-capture)
13. [Cost Tracking](#cost-tracking)
14. [Complete AG2 Import Map](#complete-ag2-import-map)

---

## AG2 Overview

### What is AG2?

AG2 (formerly AutoGen) is an open-source framework for building multi-agent AI systems. Version 0.10.3+ introduced the "Swarm" pattern which CMBAgent heavily leverages.

**Key Concepts:**
- **Agents**: Autonomous entities that can converse, execute code, and use tools
- **Group Chat**: Multi-agent conversation orchestration
- **Hand-offs**: Explicit agent-to-agent transitions
- **Context Variables**: Shared state across all agents
- **Functions**: Tools that agents can invoke

### Why CMBAgent Uses AG2

CMBAgent uses AG2 because it provides:
- Robust multi-agent orchestration
- Built-in code execution capabilities
- OpenAI Assistants API integration (for RAG)
- Function calling/tool use infrastructure
- Flexible conversation patterns (swarm, group chat, nested)
- Interoperability with LangChain and CrewAI tools

---

## AG2 Components Used by CMBAgent

### Core Imports

```python
# File: cmbagent/cmbagent.py

import autogen
from autogen.agentchat import initiate_group_chat
from autogen.agentchat.group import ContextVariables
from autogen.agentchat.group.patterns import AutoPattern
```

```python
# File: cmbagent/base_agent.py

from autogen.coding import LocalCommandLineCodeExecutor
from autogen.agentchat.contrib.gpt_assistant_agent import GPTAssistantAgent
from autogen.agentchat import UserProxyAgent
from autogen.agentchat import ConversableAgent, UpdateSystemMessage
```

```python
# File: cmbagent/hand_offs.py

from autogen.agentchat.group import AgentTarget, TerminateTarget, OnCondition, StringLLMCondition
from autogen import GroupChatManager, GroupChat
from autogen.agentchat.contrib.capabilities.transform_messages import TransformMessages
from autogen.agentchat.contrib.capabilities.transforms import MessageHistoryLimiter
```

```python
# File: cmbagent/functions/*.py

from autogen import register_function
from autogen.agentchat.group import ContextVariables, AgentTarget, ReplyResult, TerminateTarget
```

```python
# File: cmbagent/external_tools/ag2_free_tools.py

from autogen.interop import Interoperability
```

---

## Agent Types and Base Classes

### AG2 Agent Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AG2 AGENT CLASS HIERARCHY                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ConversableAgent (AG2 Base)                                                │
│  ├── UserProxyAgent                                                         │
│  │   └── CmbAgentUserProxyAgent (custom)     ← Admin, Executor             │
│  │                                                                          │
│  ├── AssistantAgent                                                         │
│  │   └── GPTAssistantAgent                   ← RAG agents (camb, classy)   │
│  │                                                                          │
│  └── CmbAgentSwarmAgent (custom)             ← All other agents            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### CmbAgentSwarmAgent

CMBAgent extends `ConversableAgent` to create a swarm-compatible agent:

```python
# File: cmbagent/base_agent.py

class CmbAgentSwarmAgent(ConversableAgent):
    """CMB Swarm agent for participating in a swarm.

    CmbAgentSwarmAgent is a subclass of SwarmAgent, which is a subclass of ConversableAgent.

    Additional args:
        functions (List[Callable]): A list of functions to register with the agent.
    """
    pass
```

**Purpose:** All non-RAG, non-executor agents use this class. It inherits all AG2 capabilities while being compatible with the swarm/group chat pattern.

### CmbAgentUserProxyAgent

Customizes the default descriptions for user proxy agents:

```python
# File: cmbagent/base_agent.py

class CmbAgentUserProxyAgent(UserProxyAgent):
    """A custom proxy agent for the user with redefined default descriptions."""

    DEFAULT_USER_PROXY_AGENT_DESCRIPTIONS = {
        "ALWAYS": "An attentive HUMAN user who can answer questions about the task and provide feedback.",
        "TERMINATE": "A user that can run Python code and report back the execution results.",
        "NEVER": "A computer terminal that performs no other action than running Python scripts.",
    }
```

**Used by:** `admin` agent (ALWAYS mode), `executor` agent (NEVER mode)

### BaseAgent.set_agent Methods

The `BaseAgent` class provides four methods to set up different agent types:

```python
# File: cmbagent/base_agent.py

class BaseAgent:
    
    def set_gpt_assistant_agent(self, ...):
        """For RAG agents using OpenAI Assistants API"""
        self.agent = GPTAssistantAgent(
            name=self.name,
            instructions=self.info["instructions"],
            description=self.info["description"],
            assistant_config=self.info["assistant_config"],
            llm_config=self.llm_config,
            overwrite_tools=True,
            overwrite_instructions=True,
        )
    
    def set_assistant_agent(self, ...):
        """For standard swarm agents (planner, engineer, etc.)"""
        self.agent = CmbAgentSwarmAgent(
            name=self.name,
            update_agent_state_before_reply=[UpdateSystemMessage(self.info["instructions"])],
            description=self.info["description"],
            llm_config=self.llm_config,
            functions=functions,
        )
    
    def set_code_agent(self, ...):
        """For code execution agents (executor, executor_bash)"""
        self.agent = CmbAgentSwarmAgent(
            name=self.name,
            system_message=self.info["instructions"],
            description=self.info["description"],
            llm_config=self.llm_config,
            human_input_mode=self.info["human_input_mode"],
            max_consecutive_auto_reply=self.info["max_consecutive_auto_reply"],
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
            code_execution_config={
                "executor": LocalCommandLineCodeExecutor(
                    work_dir=self.work_dir,
                    timeout=self.info["timeout"],
                    execution_policies=execution_policies
                ),
                "last_n_messages": 2,
            },
        )
    
    def set_admin_agent(self, ...):
        """For human-in-the-loop admin agent"""
        self.agent = CmbAgentUserProxyAgent(
            name=self.name,
            update_agent_state_before_reply=[UpdateSystemMessage(self.info["instructions"])],
            code_execution_config=self.info["code_execution_config"],
        )
```

### Agent Type Distribution

| Agent Category | AG2 Class | CMBAgent Method | Example Agents |
|----------------|-----------|-----------------|----------------|
| RAG Agents | `GPTAssistantAgent` | `set_gpt_assistant_agent()` | camb_agent, classy_sz_agent, cobaya_agent |
| Standard Agents | `CmbAgentSwarmAgent` | `set_assistant_agent()` | planner, engineer, researcher, control |
| Code Executors | `CmbAgentSwarmAgent` | `set_code_agent()` | executor, executor_bash, researcher_executor |
| User Proxy | `CmbAgentUserProxyAgent` | `set_admin_agent()` | admin |

---

## Group Chat and Orchestration

### AutoPattern

CMBAgent uses AG2's `AutoPattern` for swarm-style orchestration:

```python
# File: cmbagent/cmbagent.py

from autogen.agentchat.group.patterns import AutoPattern
from autogen.agentchat import initiate_group_chat

def solve(self, task, initial_agent='task_improver', ...):
    
    # Create context variables (shared state)
    context_variables = ContextVariables(data=this_shared_context)
    
    # Create the swarm pattern
    agent_pattern = AutoPattern(
        agents=[agent.agent for agent in self.agents],
        initial_agent=self.get_agent_from_name(initial_agent),
        context_variables=context_variables,
        group_manager_args={
            "llm_config": self.llm_config,
            "name": "main_cmbagent_chat"
        },
    )
    
    # Start the group chat
    chat_result, context_variables, last_agent = initiate_group_chat(
        pattern=agent_pattern,
        messages=this_shared_context['main_task'],
        max_rounds=max_rounds,
    )
```

### How AutoPattern Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AUTOPATTERN EXECUTION FLOW                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Pattern receives initial message                                         │
│     └── Sent to initial_agent (e.g., task_improver)                         │
│                                                                              │
│  2. Agent processes message                                                  │
│     └── LLM generates response                                              │
│     └── May call registered functions                                        │
│                                                                              │
│  3. Function returns ReplyResult                                            │
│     └── Contains target agent for next turn                                 │
│     └── Contains updated context_variables                                  │
│     └── Contains message for next agent                                     │
│                                                                              │
│  4. Hand-off to next agent                                                  │
│     └── Via AgentTarget in ReplyResult                                      │
│     └── Or via agent.handoffs.set_after_work(AgentTarget(...))             │
│                                                                              │
│  5. Repeat until:                                                           │
│     └── TerminateTarget() is returned                                       │
│     └── max_rounds is reached                                               │
│     └── Termination message detected                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### GroupChat for Nested Execution

CMBAgent also uses standard `GroupChat` for isolated sub-workflows:

```python
# File: cmbagent/hand_offs.py

from autogen import GroupChatManager, GroupChat

# Code execution nested chat
executor_chat = GroupChat(
    agents=[
        engineer_response_formatter.agent,
        executor.agent,
    ],
    messages=[],
    max_round=3,
    speaker_selection_method='round_robin',
)

executor_manager = GroupChatManager(
    groupchat=executor_chat,
    llm_config=cmbagent_instance.llm_config,
    name="engineer_nested_chat",
)
```

---

## Hand-offs and Agent Transitions

### Hand-off Mechanism

AG2 provides explicit agent-to-agent transitions via the `handoffs` API:

```python
# File: cmbagent/hand_offs.py

from autogen.agentchat.group import AgentTarget, TerminateTarget, OnCondition, StringLLMCondition

def register_all_hand_offs(cmbagent_instance):
    
    # Get agent references
    task_improver = cmbagent_instance.get_agent_object_from_name('task_improver')
    task_recorder = cmbagent_instance.get_agent_object_from_name('task_recorder')
    planner = cmbagent_instance.get_agent_object_from_name('planner')
    # ... more agents
    
    # Static hand-offs (always go to next agent)
    task_improver.agent.handoffs.set_after_work(AgentTarget(task_recorder.agent))
    task_recorder.agent.handoffs.set_after_work(AgentTarget(planner.agent))
    planner.agent.handoffs.set_after_work(AgentTarget(planner_response_formatter.agent))
    # ... more static hand-offs
```

### Hand-off Types

#### 1. Static Hand-offs

Always transition to the same agent:

```python
# After planner finishes, always go to planner_response_formatter
planner.agent.handoffs.set_after_work(AgentTarget(planner_response_formatter.agent))
```

#### 2. Terminate Hand-offs

End the conversation:

```python
# Terminator ends the workflow
terminator.agent.handoffs.set_after_work(TerminateTarget())
```

#### 3. LLM-Conditional Hand-offs

Let the LLM decide which agent to hand off to:

```python
# Control agent can route to different agents based on context
control.agent.handoffs.add_llm_conditions([
    OnCondition(
        target=AgentTarget(engineer.agent),
        condition=StringLLMCondition(prompt="Code execution failed."),
    ),
    OnCondition(
        target=AgentTarget(researcher.agent),
        condition=StringLLMCondition(prompt="Researcher needed to generate reasoning, write report, or interpret results"),
    ),
    OnCondition(
        target=AgentTarget(engineer.agent),
        condition=StringLLMCondition(prompt="Engineer needed to write code, make plots, do calculations."),
    ),
    OnCondition(
        target=AgentTarget(idea_maker.agent),
        condition=StringLLMCondition(prompt="idea_maker needed to make new ideas"),
    ),
    OnCondition(
        target=AgentTarget(terminator.agent),
        condition=StringLLMCondition(prompt="The task is completed."),
    ),
])
```

### Complete Hand-off Chain (Planning)

```
task_improver
     │ set_after_work(AgentTarget(task_recorder))
     ▼
task_recorder
     │ set_after_work(AgentTarget(planner)) ← Function returns ReplyResult
     ▼
planner
     │ set_after_work(AgentTarget(planner_response_formatter))
     ▼
planner_response_formatter
     │ set_after_work(AgentTarget(plan_recorder))
     ▼
plan_recorder
     │ set_after_work(AgentTarget(plan_reviewer))
     ▼
plan_reviewer
     │ set_after_work(AgentTarget(reviewer_response_formatter))
     ▼
reviewer_response_formatter
     │ set_after_work(AgentTarget(review_recorder))
     ▼
review_recorder
     │ set_after_work(AgentTarget(planner)) ← Loops back for revision
     │                    OR
     │ Function returns AgentTarget(terminator) ← When feedback_left == 0
     ▼
terminator
     │ set_after_work(TerminateTarget())
     ▼
END
```

---

## Context Variables and State Management

### ContextVariables Class

AG2's `ContextVariables` provides shared state across all agents:

```python
# File: cmbagent/cmbagent.py

from autogen.agentchat.group import ContextVariables

# Initialize context
context_variables = ContextVariables(data=this_shared_context)

# Pass to pattern
agent_pattern = AutoPattern(
    agents=[...],
    initial_agent=...,
    context_variables=context_variables,  # Shared state
    ...
)
```

### Context Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CONTEXT VARIABLES FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Initial Context (solve())                                                  │
│  ├── main_task: "User's task description"                                   │
│  ├── improved_main_task: ""                                                 │
│  ├── work_dir: "/path/to/workdir"                                           │
│  ├── plans: []                                                              │
│  ├── reviews: []                                                            │
│  ├── feedback_left: 2                                                       │
│  └── ... many more fields                                                   │
│                                                                              │
│                           ↓                                                  │
│                                                                              │
│  Function Updates Context                                                    │
│  (e.g., record_improved_task)                                               │
│                                                                              │
│  def record_improved_task(improved_main_task: str,                          │
│                           context_variables: ContextVariables) -> ReplyResult│
│      context_variables["improved_main_task"] = improved_main_task           │
│      return ReplyResult(                                                    │
│          target=AgentTarget(planner),                                       │
│          message="...",                                                     │
│          context_variables=context_variables  # Return updated context      │
│      )                                                                      │
│                                                                              │
│                           ↓                                                  │
│                                                                              │
│  Updated Context Passed to Next Agent                                       │
│  ├── main_task: "User's task description"                                   │
│  ├── improved_main_task: "Enhanced version..."  ← UPDATED                  │
│  └── ... rest unchanged                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### UpdateSystemMessage

AG2's `UpdateSystemMessage` dynamically updates agent instructions:

```python
# File: cmbagent/base_agent.py

from autogen.agentchat import UpdateSystemMessage

self.agent = CmbAgentSwarmAgent(
    name=self.name,
    # Instead of static system_message, use dynamic update
    update_agent_state_before_reply=[UpdateSystemMessage(self.info["instructions"])],
    description=self.info["description"],
    llm_config=self.llm_config,
)
```

**How it works:** Before each reply, the agent's system message is updated. This allows instructions to contain template variables that get filled from context.

---

## Function Registration

### AG2 Function Registration

AG2 provides `register_function` decorator and agent methods:

```python
from autogen import register_function

# Method 1: Using agent.register_for_llm()
agent.register_for_llm()(my_function)

# Method 2: Using agent.register_for_execution()
executor.register_for_execution()(my_function)
```

### ReplyResult for Hand-offs

Functions return `ReplyResult` to control conversation flow:

```python
# File: cmbagent/functions/planning.py

from autogen.agentchat.group import ContextVariables, AgentTarget, ReplyResult, TerminateTarget

def record_plan(plan_suggestion: str, 
                number_of_steps_in_plan: int, 
                context_variables: ContextVariables, 
                cmbagent_instance) -> ReplyResult:
    """Records a suggested plan and updates context."""
    
    plan_reviewer = cmbagent_instance.get_agent_from_name('plan_reviewer')
    terminator = cmbagent_instance.get_agent_from_name('terminator')
    
    # Update context
    context_variables["plans"].append(plan_suggestion)
    context_variables["proposed_plan"] = plan_suggestion
    context_variables["number_of_steps_in_plan"] = number_of_steps_in_plan
    
    # Decide next agent
    if context_variables["feedback_left"] <= 0:
        context_variables["final_plan"] = context_variables["plans"][-1]
        return ReplyResult(
            target=AgentTarget(terminator),  # End planning
            message="Planning stage complete. Exiting.",
            context_variables=context_variables
        )
    else:
        return ReplyResult(
            target=AgentTarget(plan_reviewer),  # Continue to review
            message="Plan has been logged.",
            context_variables=context_variables
        )
```

### Function Registration in CMBAgent

```python
# File: cmbagent/functions/registration.py

def register_functions_to_agents(cmbagent_instance):
    """Register all functions with appropriate agents."""
    
    # Get agent references
    task_recorder = cmbagent_instance.get_agent_from_name('task_recorder')
    plan_recorder = cmbagent_instance.get_agent_from_name('plan_recorder')
    # ...
    
    # Setup planning functions (creates closures)
    setup_planning_functions(cmbagent_instance, cmbagent_disable_display)
    
    # Setup execution control functions
    setup_execution_control_functions(cmbagent_instance)
    
    # Setup status functions
    setup_status_functions(cmbagent_instance)
```

### Function Categories

| Category | Functions | Registered To |
|----------|-----------|---------------|
| Planning | `record_improved_task`, `record_plan`, `record_review`, `save_final_plan` | task_recorder, plan_recorder, review_recorder |
| Execution Control | `transfer_to_agent`, `post_execution_transfer`, `terminate_session` | control, executor_response_formatter |
| Status | `update_step_status`, `get_current_step`, `mark_step_complete` | control, engineer, researcher |
| Ideas | `record_idea`, `record_critique`, `save_idea` | idea_maker, idea_hater, idea_saver |
| Keywords | `find_aas_keywords`, `extract_keywords` | aas_keyword_finder |

---

## Code Execution

### LocalCommandLineCodeExecutor

AG2 provides a secure code executor:

```python
# File: cmbagent/base_agent.py

from autogen.coding import LocalCommandLineCodeExecutor

def set_code_agent(self, ...):
    
    execution_policies = {
        "python": True,
        "bash": False,
        "shell": False,
        "sh": False,
        "pwsh": False,
        "powershell": False,
        "ps1": False,
        "javascript": False,
        "html": False,
        "css": False,
    }
    
    # Bash executor has different policies
    if 'bash' in self.name:
        execution_policies = {
            "python": False,
            "bash": True,
            # ... others False
        }
    
    self.agent = CmbAgentSwarmAgent(
        name=self.name,
        system_message=self.info["instructions"],
        description=self.info["description"],
        llm_config=self.llm_config,
        human_input_mode=self.info["human_input_mode"],
        max_consecutive_auto_reply=self.info["max_consecutive_auto_reply"],
        is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
        code_execution_config={
            "executor": LocalCommandLineCodeExecutor(
                work_dir=self.work_dir,
                timeout=self.info["timeout"],
                execution_policies=execution_policies
            ),
            "last_n_messages": 2,  # Look at last 2 messages for code
        },
    )
```

### Execution Flow

```
Engineer generates code
        │
        ▼
engineer_response_formatter
        │ Formats code block
        ▼
engineer_nest (nested chat trigger)
        │
        ▼
┌───────────────────────────────┐
│    executor_manager           │
│    (GroupChatManager)         │
│    ┌─────────────────────┐    │
│    │ executor_chat       │    │
│    │ (GroupChat)         │    │
│    │   ┌─────────────┐   │    │
│    │   │ eng_fmt     │───┼────┼──→ Formats code
│    │   │             │   │    │
│    │   │ executor    │───┼────┼──→ Runs code via LocalCommandLineCodeExecutor
│    │   │             │   │    │
│    │   └─────────────┘   │    │
│    │   (round_robin)     │    │
│    └─────────────────────┘    │
└───────────────────────────────┘
        │
        ▼
executor_response_formatter
        │ Captures output
        ▼
control (decides next step)
```

### TrackedCodeExecutor

CMBAgent wraps the AG2 executor for additional tracking:

```python
# File: cmbagent/execution/tracked_code_executor.py

from autogen.coding import LocalCommandLineCodeExecutor

class TrackedCodeExecutor:
    """
    Wraps AG2's LocalCommandLineCodeExecutor to:
    1. Track executed code
    2. Capture execution events
    3. Store execution history
    """
    
    def __init__(self, work_dir, timeout, execution_policies, **kwargs):
        self._executor = LocalCommandLineCodeExecutor(
            work_dir=work_dir,
            timeout=timeout,
            execution_policies=execution_policies,
            **kwargs
        )
        self._execution_history = []
    
    def execute_code_blocks(self, code_blocks):
        """Execute code and track execution."""
        # Store code for tracking
        self._execution_history.append({
            'code': code_blocks,
            'timestamp': datetime.now()
        })
        
        # Delegate to AG2 executor
        return self._executor.execute_code_blocks(code_blocks)
```

---

## Nested Chats

### What are Nested Chats?

Nested chats allow an agent to spawn a separate conversation before continuing. CMBAgent uses this for code execution and idea generation.

### Code Execution Nested Chat

```python
# File: cmbagent/hand_offs.py

# Create a GroupChat for code execution
executor_chat = GroupChat(
    agents=[
        engineer_response_formatter.agent,
        executor.agent,
    ],
    messages=[],
    max_round=3,
    speaker_selection_method='round_robin',
)

# Wrap in a manager
executor_manager = GroupChatManager(
    groupchat=executor_chat,
    llm_config=cmbagent_instance.llm_config,
    name="engineer_nested_chat",
)

# Define nested chat configuration
nested_chats = [
    {
        "recipient": executor_manager,
        "message": lambda recipient, messages, sender, config: f"{messages[-1]['content']}" if messages else "",
        "max_turns": 1,
        "summary_method": "last_msg",
    }
]

# Get all other agents (for trigger)
other_agents = [agent for agent in cmbagent_instance.agents if agent != engineer.agent]

# Register nested chat with engineer_nest
engineer_nest.agent.register_nested_chats(
    trigger=lambda sender: sender not in other_agents,
    chat_queue=nested_chats
)

# Wire up hand-offs
engineer_nest.agent.handoffs.set_after_work(AgentTarget(executor_response_formatter.agent))
engineer.agent.handoffs.set_after_work(AgentTarget(engineer_nest.agent))
```

### Idea Generation Nested Chat

```python
# Similar pattern for idea generation
idea_maker_chat = GroupChat(
    agents=[
        idea_maker_response_formatter.agent,
        idea_saver.agent
    ],
    messages=[],
    max_round=4,
    speaker_selection_method='round_robin',
)

idea_maker_manager = GroupChatManager(
    groupchat=idea_maker_chat,
    llm_config=cmbagent_instance.llm_config,
    name="idea_maker_manager",
)

nested_chats = [
    {
        "recipient": idea_maker_manager,
        "message": lambda recipient, messages, sender, config: f"{messages[-1]['content']}",
        "max_turns": 1,
        "summary_method": "last_msg",
    }
]

idea_maker_nest.agent.register_nested_chats(
    trigger=lambda sender: sender not in other_agents,
    chat_queue=nested_chats
)
```

---

## Message Transforms

### TransformMessages and MessageHistoryLimiter

AG2 provides message transformation capabilities. CMBAgent uses this to limit context for certain agents:

```python
# File: cmbagent/hand_offs.py

from autogen.agentchat.contrib.capabilities.transform_messages import TransformMessages
from autogen.agentchat.contrib.capabilities.transforms import MessageHistoryLimiter

# Create transform that keeps only the last message
context_handling = TransformMessages(
    transforms=[
        MessageHistoryLimiter(max_messages=1),
    ]
)

# Apply to "one-shot" agents that don't need full history
context_handling.add_to_agent(executor_response_formatter.agent)
context_handling.add_to_agent(planner_response_formatter.agent)
context_handling.add_to_agent(plan_recorder.agent)
context_handling.add_to_agent(reviewer_response_formatter.agent)
context_handling.add_to_agent(review_recorder.agent)
context_handling.add_to_agent(researcher_response_formatter.agent)
context_handling.add_to_agent(researcher_executor.agent)
context_handling.add_to_agent(idea_maker_response_formatter.agent)
context_handling.add_to_agent(idea_hater_response_formatter.agent)
context_handling.add_to_agent(summarizer_response_formatter.agent)
```

**Why?** Response formatter agents only need to see the last message (the response to format). Including full history would waste tokens and potentially confuse the agent.

---

## Interoperability with External Tools

### AG2 Interoperability Module

AG2 provides native integration with LangChain and CrewAI tools:

```python
# File: cmbagent/external_tools/ag2_free_tools.py

from autogen.interop import Interoperability

class AG2FreeToolsLoader:
    """Loader for all free tools from LangChain and CrewAI."""
    
    def __init__(self):
        self.interop = Interoperability()
        self.loaded_tools = {'langchain': [], 'crewai': []}
    
    def load_langchain_tools(self, tool_names=None):
        """Load LangChain tools using AG2 Interoperability."""
        tools = []
        
        # DuckDuckGo Search (FREE)
        if tool_names is None or 'duckduckgo' in tool_names:
            from langchain_community.tools import DuckDuckGoSearchRun
            from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
            
            api_wrapper = DuckDuckGoSearchAPIWrapper()
            langchain_tool = DuckDuckGoSearchRun(api_wrapper=api_wrapper)
            
            # Convert to AG2 format using Interoperability
            ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
            tools.append(ag2_tool)
        
        # Wikipedia (FREE)
        if tool_names is None or 'wikipedia' in tool_names:
            from langchain_community.tools import WikipediaQueryRun
            from langchain_community.utilities import WikipediaAPIWrapper
            
            langchain_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
            ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
            tools.append(ag2_tool)
        
        # ArXiv (FREE)
        if tool_names is None or 'arxiv' in tool_names:
            from langchain_community.tools import ArxivQueryRun
            from langchain_community.utilities import ArxivAPIWrapper
            
            langchain_tool = ArxivQueryRun(api_wrapper=ArxivAPIWrapper())
            ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
            tools.append(ag2_tool)
        
        return tools
```

### Tool Registration

```python
# File: cmbagent/functions/registration.py

if getattr(cmbagent_instance, 'enable_ag2_free_tools', True):
    from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader
    
    loader = AG2FreeToolsLoader()
    combined_tools = loader.get_combined_tool_list()
    
    # Register with agents for LLM (function calling)
    for agent in agents_for_tools:
        for tool in combined_tools:
            agent.register_for_llm()(tool)
    
    # Register with executor for actual execution
    for tool in combined_tools:
        executor.register_for_execution()(tool)
```

---

## IOStream for Event Capture

### AG2 IOStream

AG2 uses IOStream for I/O operations. CMBAgent captures this for WebSocket streaming:

```python
# File: backend/main_legacy.py

from autogen.io.base import IOStream

class AG2IOStreamCapture(IOStream):
    """
    Custom AG2 IOStream that intercepts all AG2 events 
    and forwards them to WebSocket.
    """
    
    def __init__(self, websocket, task_id, loop):
        self.websocket = websocket
        self.task_id = task_id
        self.loop = loop
        self._original_print = print
    
    def print(self, *args, **kwargs):
        """Capture print statements from AG2."""
        try:
            message = " ".join(str(arg) for arg in args)
            
            # Send to WebSocket
            asyncio.run_coroutine_threadsafe(
                self.websocket.send_json({
                    "type": "output",
                    "data": message,
                    "task_id": self.task_id
                }),
                self.loop
            )
            
            # Also call original print
            self._original_print(*args, **kwargs)
            
        except Exception as e:
            self._original_print(f"Error in AG2IOStreamCapture.print: {e}")
    
    def send(self, data, **kwargs):
        """Capture send events from AG2."""
        try:
            asyncio.run_coroutine_threadsafe(
                self.websocket.send_json({
                    "type": "ag2_event",
                    "data": data,
                    "task_id": self.task_id
                }),
                self.loop
            )
        except Exception as e:
            self._original_print(f"Error in AG2IOStreamCapture.send: {e}")

# Usage during task execution:
ag2_iostream = AG2IOStreamCapture(websocket, task_id, loop)
IOStream.set_global_default(ag2_iostream)
```

---

## Cost Tracking

### AG2 Usage Tracking

AG2 agents track token usage via their client:

```python
# File: cmbagent/managers/cost_manager.py

class CostManager:
    
    def _collect_agent_cost(self, agent, cost_dict):
        """Collect cost from a single agent."""
        
        # Try AG2's native usage tracking via client
        if hasattr(agent, "client") and agent.client is not None:
            try:
                usage_summary = getattr(agent.client, "total_usage_summary", None)
                if usage_summary:
                    agent_name = getattr(agent, "name", "unknown")
                    for model_name, model_usage in usage_summary.items():
                        if isinstance(model_usage, dict):
                            prompt_tokens = model_usage.get("prompt_tokens", 0)
                            completion_tokens = model_usage.get("completion_tokens", 0)
                            total_tokens = prompt_tokens + completion_tokens
                            cost = self._calculate_cost(model_name, prompt_tokens, completion_tokens)
                            
                            # Add to cost_dict
                            cost_dict["Agent"].append(agent_name)
                            cost_dict["Cost ($)"].append(cost)
                            cost_dict["Prompt Tokens"].append(prompt_tokens)
                            cost_dict["Completion Tokens"].append(completion_tokens)
                            cost_dict["Total Tokens"].append(total_tokens)
                            cost_dict["Model"].append(model_name)
            except Exception as e:
                print(f"Warning: Could not extract AG2 usage for agent {agent.name}: {e}")
```

---

## Complete AG2 Import Map

### All AG2 Imports Used by CMBAgent

```python
# Core orchestration
from autogen.agentchat import initiate_group_chat
from autogen.agentchat.group.patterns import AutoPattern
from autogen.agentchat.group import ContextVariables

# Agent classes
from autogen.agentchat import ConversableAgent
from autogen.agentchat import UserProxyAgent
from autogen.agentchat import UpdateSystemMessage
from autogen.agentchat.contrib.gpt_assistant_agent import GPTAssistantAgent
from autogen.agentchat.contrib.retrieve_assistant_agent import RetrieveAssistantAgent

# Hand-offs and targets
from autogen.agentchat.group import AgentTarget
from autogen.agentchat.group import TerminateTarget
from autogen.agentchat.group import OnCondition
from autogen.agentchat.group import StringLLMCondition
from autogen.agentchat.group import ReplyResult

# Group chat
from autogen import GroupChat
from autogen import GroupChatManager

# Function registration
from autogen import register_function

# Code execution
from autogen.coding import LocalCommandLineCodeExecutor

# Message transforms
from autogen.agentchat.contrib.capabilities.transform_messages import TransformMessages
from autogen.agentchat.contrib.capabilities.transforms import MessageHistoryLimiter

# Interoperability
from autogen.interop import Interoperability

# I/O streaming
from autogen.io.base import IOStream
```

### Feature Matrix

| AG2 Feature | CMBAgent Usage | File(s) |
|-------------|----------------|---------|
| `AutoPattern` | Main swarm orchestration | `cmbagent.py` |
| `initiate_group_chat` | Start conversation | `cmbagent.py` |
| `ContextVariables` | Shared state | `cmbagent.py`, `functions/*.py` |
| `ConversableAgent` | Base for swarm agents | `base_agent.py` |
| `UserProxyAgent` | Admin/executor agents | `base_agent.py` |
| `GPTAssistantAgent` | RAG agents | `base_agent.py` |
| `UpdateSystemMessage` | Dynamic instructions | `base_agent.py` |
| `AgentTarget` | Hand-off destinations | `hand_offs.py`, `functions/*.py` |
| `TerminateTarget` | End conversation | `hand_offs.py`, `functions/*.py` |
| `OnCondition` | LLM-based routing | `hand_offs.py` |
| `StringLLMCondition` | Routing conditions | `hand_offs.py` |
| `ReplyResult` | Function return type | `functions/*.py` |
| `GroupChat` | Nested execution | `hand_offs.py` |
| `GroupChatManager` | Manage nested chat | `hand_offs.py` |
| `register_nested_chats` | Attach nested chats | `hand_offs.py` |
| `LocalCommandLineCodeExecutor` | Run Python/Bash | `base_agent.py` |
| `TransformMessages` | Message processing | `hand_offs.py` |
| `MessageHistoryLimiter` | Context windowing | `hand_offs.py` |
| `Interoperability` | LangChain/CrewAI tools | `external_tools/*.py` |
| `IOStream` | Event capture | `backend/main_legacy.py` |
| `register_function` | Tool registration | `functions/*.py` |

---

## Summary

CMBAgent extensively leverages AG2's multi-agent capabilities:

1. **Agent Types**: Uses `ConversableAgent`, `UserProxyAgent`, and `GPTAssistantAgent` with custom subclasses
2. **Orchestration**: Uses `AutoPattern` + `initiate_group_chat` for swarm-style execution
3. **Hand-offs**: Explicit transitions via `AgentTarget`, `TerminateTarget`, and LLM conditions
4. **State**: Shared context via `ContextVariables`, updated through `ReplyResult`
5. **Functions**: Tool registration via `register_for_llm()` and `register_for_execution()`
6. **Code Execution**: Secure execution via `LocalCommandLineCodeExecutor`
7. **Nested Chats**: Isolated sub-workflows for code execution and idea generation
8. **Message Transforms**: Context windowing for formatter agents
9. **Interoperability**: Native integration with LangChain and CrewAI tools
10. **Event Capture**: Custom `IOStream` for WebSocket streaming

This architecture allows CMBAgent to orchestrate 45+ specialized agents for complex multi-step autonomous research tasks.

---

*AG2 Integration Guide for CMBAgent*  
*Last updated: January 2026*
