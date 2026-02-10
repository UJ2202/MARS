# Building a Copilot-Like Assistant with CMBAgent

> **Analysis & Architecture Document**

---

## Table of Contents

1. [What Makes a Copilot Assistant?](#what-makes-a-copilot-assistant)
2. [Current CMBAgent Capabilities](#current-cmbagent-capabilities)
3. [Gap Analysis](#gap-analysis)
4. [Architecture for Copilot Mode](#architecture-for-copilot-mode)
5. [Implementation Plan](#implementation-plan)
6. [Integration with Phase Architecture](#integration-with-phase-architecture)

---

## What Makes a Copilot Assistant?

### Core Characteristics of AI Assistants (like GitHub Copilot, Claude, ChatGPT)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COPILOT ASSISTANT CHARACTERISTICS                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. CONVERSATIONAL LOOP                                                     │
│     ┌──────────────────────────────────────────────────────────────────┐    │
│     │  User ──message──► Assistant ──response──► User ──message──► ... │    │
│     │        ↑                                            │             │    │
│     │        └────────────── continuous ─────────────────┘             │    │
│     └──────────────────────────────────────────────────────────────────┘    │
│     • Multi-turn conversation (not one-shot task)                           │
│     • Context maintained across turns                                       │
│     • User can ask follow-up questions                                     │
│                                                                              │
│  2. DYNAMIC TOOL USE                                                        │
│     ┌──────────────────────────────────────────────────────────────────┐    │
│     │  User Query → Intent Recognition → Tool Selection → Execution    │    │
│     │                                                                   │    │
│     │  "Read this file" → file_read tool                               │    │
│     │  "Run this code" → terminal tool                                 │    │
│     │  "Search the web" → web_search tool                              │    │
│     │  "Explain this" → (no tool, just reasoning)                      │    │
│     └──────────────────────────────────────────────────────────────────┘    │
│     • LLM decides which tools to use                                       │
│     • Can use multiple tools in sequence                                   │
│     • Self-corrects on tool failures                                       │
│                                                                              │
│  3. STREAMING RESPONSES                                                     │
│     ┌──────────────────────────────────────────────────────────────────┐    │
│     │  Token → Token → Token → Token → ... → Complete                  │    │
│     │  "The"  "code"  "looks"  "correct"                               │    │
│     └──────────────────────────────────────────────────────────────────┘    │
│     • Real-time output (not waiting for complete response)                 │
│     • Shows thinking/tool calls as they happen                             │
│     • Interruptible (user can cancel mid-response)                         │
│                                                                              │
│  4. CONTEXT AWARENESS                                                       │
│     ┌──────────────────────────────────────────────────────────────────┐    │
│     │  • Current file open                                             │    │
│     │  • Workspace structure                                           │    │
│     │  • Recent edits                                                  │    │
│     │  • Terminal output                                               │    │
│     │  • Error messages                                                │    │
│     │  • User preferences                                              │    │
│     └──────────────────────────────────────────────────────────────────┘    │
│     • Injected context before each query                                   │
│     • Adapts to current environment                                        │
│                                                                              │
│  5. MEMORY & CONVERSATION HISTORY                                          │
│     ┌──────────────────────────────────────────────────────────────────┐    │
│     │  Turn 1: User: "Create a function to parse JSON"                 │    │
│     │          Assistant: "def parse_json(...)..."                     │    │
│     │  Turn 2: User: "Add error handling"                              │    │
│     │          Assistant: (knows which function from context)          │    │
│     │  Turn 3: User: "Now use it in main.py"                           │    │
│     │          Assistant: (remembers the function created)             │    │
│     └──────────────────────────────────────────────────────────────────┘    │
│     • Remembers previous turns                                             │
│     • Can reference earlier context                                        │
│     • Manages context window intelligently                                 │
│                                                                              │
│  6. AGENTIC CAPABILITIES                                                    │
│     ┌──────────────────────────────────────────────────────────────────┐    │
│     │  "Build a REST API for user management"                          │    │
│     │                                                                   │    │
│     │  → Break into steps (implicit planning)                          │    │
│     │  → Create models.py                                              │    │
│     │  → Create routes.py                                              │    │
│     │  → Create tests.py                                               │    │
│     │  → Run tests to verify                                           │    │
│     │  → Report results                                                │    │
│     └──────────────────────────────────────────────────────────────────┘    │
│     • Can handle complex multi-step tasks                                  │
│     • Plans implicitly (not always explicit plan generation)               │
│     • Self-corrects on failures                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Current CMBAgent Capabilities

### What CMBAgent Already Has ✅

| Capability | Status | Implementation |
|------------|--------|----------------|
| Multi-agent orchestration | ✅ Ready | AG2 Swarm patterns |
| Tool registration | ✅ Ready | `register_for_llm`, `register_for_execution` |
| MCP integration | ✅ Ready | `MCPClientManager`, `MCPToolIntegration` |
| WebSocket real-time | ✅ Ready | `WebSocketManager`, event streaming |
| Database persistence | ✅ Ready | SQLAlchemy models, `WorkflowRepository` |
| Session management | ✅ Ready | `SessionManager`, session isolation |
| HITL approval | ✅ Ready | `ApprovalManager`, checkpoints |
| Code execution | ✅ Ready | Executor agent, Docker isolation |
| RAG capabilities | ✅ Ready | OpenAI assistants, vector stores |
| Planning | ✅ Ready | Planner agent, plan review |
| File operations | ✅ Ready | Work directory management |
| Web tools | ✅ Ready | Perplexity, Brave search |
| Context carryover | ✅ Ready | `shared_context` between steps |

### What CMBAgent Is Missing ❌

| Capability | Status | Gap Description |
|------------|--------|-----------------|
| Continuous conversation loop | ❌ Missing | Currently task-oriented, not chat-oriented |
| Streaming token output | ❌ Missing | Only streams events, not LLM tokens |
| Dynamic tool routing | ⚠️ Partial | Tools registered, but fixed workflows |
| Intent classification | ❌ Missing | No router to decide simple vs complex tasks |
| Conversation memory | ⚠️ Partial | Has `memory` agent but not optimized for chat |
| Context window management | ❌ Missing | No summarization/truncation strategy |
| Interruptibility | ⚠️ Partial | Has pause/cancel but not mid-response |
| Simple query handling | ❌ Missing | Everything goes through agent swarm |

---

## Gap Analysis

### Gap 1: Conversation Loop vs Task Execution

**Current (Task-Oriented):**
```python
# User sends task → System runs to completion → Returns result
result = cmbagent.solve("Build a REST API")
# User must wait for entire workflow to complete
```

**Needed (Conversation-Oriented):**
```python
# User sends message → System responds → User can follow up
response = assistant.chat("Build a REST API")
# "I'll create a REST API. Let me start with the models..."
response = assistant.chat("Actually, use FastAPI instead of Flask")
# "Got it, switching to FastAPI..."
response = assistant.chat("Show me what you have so far")
# Shows current progress, can modify
```

### Gap 2: Streaming Output

**Current:**
```python
# Events are streamed (agent started, tool called, etc.)
# But actual LLM output comes as complete chunks
WebSocketEvent(type="agent_message", data={"content": "full message here"})
```

**Needed:**
```python
# Token-by-token streaming
WebSocketEvent(type="token", data={"token": "The"})
WebSocketEvent(type="token", data={"token": " code"})
WebSocketEvent(type="token", data={"token": " looks"})
# User sees text appear in real-time
```

### Gap 3: Intent Classification / Routing

**Current:**
```
User Input → Fixed Workflow (planning → control → ...)
```

**Needed:**
```
User Input → Intent Classifier
                ├── Simple Question → Direct LLM Response
                ├── Code Question → Single Agent (engineer)
                ├── Research Task → Multi-step Workflow
                ├── File Operation → Tool Call
                └── Complex Task → Full Planning Workflow
```

### Gap 4: Conversation Memory

**Current:**
- Chat history stored per workflow run
- Context passed between steps in single workflow
- No cross-conversation memory

**Needed:**
- Persistent conversation history
- Context window management (summarization when too long)
- Ability to reference previous conversations
- Smart retrieval of relevant past context

---

## Architecture for Copilot Mode

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COPILOT ASSISTANT ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         FRONTEND (Chat UI)                           │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │    │
│  │  │ Chat Input  │ │ Message     │ │ Streaming   │ │ Context     │    │    │
│  │  │ Component   │ │ Display     │ │ Handler     │ │ Sidebar     │    │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘    │    │
│  └───────────────────────────────────┬─────────────────────────────────┘    │
│                                      │ WebSocket                             │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      CONVERSATION MANAGER                            │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │                    Message Handler                           │    │    │
│  │  │  • Receive user message                                      │    │    │
│  │  │  • Inject context (files, workspace, history)               │    │    │
│  │  │  • Route to appropriate handler                              │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  │                              │                                       │    │
│  │                              ▼                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │                    Intent Router                             │    │    │
│  │  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐    │    │    │
│  │  │  │ Simple Q  │ │ Tool Call │ │ Code Gen  │ │ Workflow  │    │    │    │
│  │  │  │ (direct)  │ │ (1 tool)  │ │ (agent)   │ │ (phases)  │    │    │    │
│  │  │  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘    │    │    │
│  │  └────────┼─────────────┼─────────────┼─────────────┼───────────┘    │    │
│  │           │             │             │             │                │    │
│  └───────────┼─────────────┼─────────────┼─────────────┼────────────────┘    │
│              ▼             ▼             ▼             ▼                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      EXECUTION LAYER                                 │    │
│  │                                                                       │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │    │
│  │  │ Direct LLM  │ │ Tool        │ │ Single      │ │ Phase       │     │    │
│  │  │ Response    │ │ Executor    │ │ Agent       │ │ Workflow    │     │    │
│  │  │ (streaming) │ │             │ │             │ │ Executor    │     │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │    │
│  │                                                                       │    │
│  └───────────────────────────────────┬─────────────────────────────────┘    │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      STREAMING OUTPUT                                │    │
│  │  • Token-by-token for LLM responses                                 │    │
│  │  • Tool call notifications                                          │    │
│  │  • Progress updates for workflows                                   │    │
│  │  • File/code change notifications                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      MEMORY & CONTEXT                                │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │    │
│  │  │ Conversation│ │ Context     │ │ Workspace   │ │ Summarizer  │    │    │
│  │  │ History     │ │ Injector    │ │ Indexer     │ │             │    │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### New Components Needed

#### 1. Conversation Manager

```python
# cmbagent/assistant/conversation.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncIterator
import asyncio
from enum import Enum


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class Message:
    role: MessageRole
    content: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # For tool calls
    tool_calls: List[Dict] = field(default_factory=list)
    tool_call_id: Optional[str] = None


@dataclass
class ConversationContext:
    """Context injected into each turn."""
    
    # Workspace context
    current_file: Optional[str] = None
    current_file_content: Optional[str] = None
    workspace_structure: Optional[str] = None
    
    # Editor context
    selected_text: Optional[str] = None
    cursor_position: Optional[Dict] = None
    visible_range: Optional[Dict] = None
    
    # Terminal context
    recent_terminal_output: Optional[str] = None
    last_command: Optional[str] = None
    
    # Error context
    current_errors: List[Dict] = field(default_factory=list)
    
    # User preferences
    preferred_language: str = "python"
    coding_style: Optional[str] = None


class ConversationManager:
    """
    Manages multi-turn conversations with context.
    """
    
    def __init__(
        self,
        model: str = "gpt-4o",
        max_history_tokens: int = 100000,
        system_prompt: Optional[str] = None,
    ):
        self.model = model
        self.max_history_tokens = max_history_tokens
        self.system_prompt = system_prompt or self._default_system_prompt()
        
        self.messages: List[Message] = []
        self.context: ConversationContext = ConversationContext()
        
        # Tools available
        self.tools: List[Dict] = []
    
    def _default_system_prompt(self) -> str:
        return """You are an expert AI programming assistant. You help users with coding tasks, 
answer questions, and assist with software development.

When you need to perform actions like reading files, searching code, or running commands,
use the available tools. Always explain what you're doing and why.

Be concise but thorough. Show code when helpful. Ask for clarification when needed."""
    
    async def chat(
        self,
        user_message: str,
        context: Optional[ConversationContext] = None,
    ) -> AsyncIterator[str]:
        """
        Process user message and stream response.
        
        Yields tokens as they are generated.
        """
        # Update context if provided
        if context:
            self.context = context
        
        # Add user message to history
        self.messages.append(Message(
            role=MessageRole.USER,
            content=user_message,
            timestamp=time.time(),
        ))
        
        # Build messages for LLM
        llm_messages = self._build_llm_messages()
        
        # Stream response
        assistant_content = ""
        async for token in self._stream_llm_response(llm_messages):
            assistant_content += token
            yield token
        
        # Add assistant message to history
        self.messages.append(Message(
            role=MessageRole.ASSISTANT,
            content=assistant_content,
            timestamp=time.time(),
        ))
        
        # Manage history length
        self._maybe_summarize_history()
    
    def _build_llm_messages(self) -> List[Dict]:
        """Build message list for LLM, including context."""
        messages = []
        
        # System prompt with injected context
        system_content = self.system_prompt
        if self.context.current_file:
            system_content += f"\n\nCurrent file: {self.context.current_file}"
        if self.context.workspace_structure:
            system_content += f"\n\nWorkspace structure:\n{self.context.workspace_structure}"
        
        messages.append({"role": "system", "content": system_content})
        
        # Conversation history
        for msg in self.messages:
            messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })
        
        return messages
    
    async def _stream_llm_response(self, messages: List[Dict]) -> AsyncIterator[str]:
        """Stream response from LLM."""
        # This would use the actual LLM client with streaming
        # Example with OpenAI:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI()
        
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools if self.tools else None,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            
            # Handle tool calls
            if chunk.choices[0].delta.tool_calls:
                for tool_call in chunk.choices[0].delta.tool_calls:
                    yield f"\n[Calling tool: {tool_call.function.name}...]\n"
    
    def _maybe_summarize_history(self):
        """Summarize old messages if history is too long."""
        # Token counting and summarization logic
        pass
    
    def register_tool(self, tool: Dict):
        """Register a tool for the assistant to use."""
        self.tools.append(tool)
    
    def clear_history(self):
        """Clear conversation history."""
        self.messages = []
```

#### 2. Intent Router

```python
# cmbagent/assistant/router.py

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class IntentType(Enum):
    # Simple responses (no tools needed)
    SIMPLE_QUESTION = "simple_question"       # "What is a decorator?"
    EXPLANATION = "explanation"               # "Explain this code"
    GREETING = "greeting"                     # "Hi", "Thanks"
    
    # Single tool actions
    FILE_READ = "file_read"                   # "Show me main.py"
    FILE_EDIT = "file_edit"                   # "Fix the bug on line 42"
    FILE_CREATE = "file_create"               # "Create a new file config.py"
    SEARCH_CODE = "search_code"               # "Find where User is defined"
    RUN_COMMAND = "run_command"               # "Run the tests"
    WEB_SEARCH = "web_search"                 # "Search for FastAPI docs"
    
    # Single agent tasks
    CODE_GENERATION = "code_generation"       # "Write a function to..."
    CODE_REVIEW = "code_review"               # "Review this code"
    DEBUGGING = "debugging"                   # "Help me debug this error"
    
    # Multi-step workflows
    COMPLEX_TASK = "complex_task"             # "Build a REST API"
    RESEARCH = "research"                     # "Research best practices for..."
    REFACTORING = "refactoring"               # "Refactor this module"
    
    # Unknown/fallback
    UNKNOWN = "unknown"


@dataclass
class ClassifiedIntent:
    intent_type: IntentType
    confidence: float
    extracted_entities: Dict[str, Any]
    suggested_handler: str
    reasoning: str


class IntentRouter:
    """
    Classifies user intent and routes to appropriate handler.
    
    Uses a lightweight LLM call to classify intent before
    deciding how to handle the request.
    """
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        
        # Handler mapping
        self.handlers = {
            IntentType.SIMPLE_QUESTION: "direct_response",
            IntentType.EXPLANATION: "direct_response",
            IntentType.GREETING: "direct_response",
            
            IntentType.FILE_READ: "tool_executor",
            IntentType.FILE_EDIT: "tool_executor",
            IntentType.FILE_CREATE: "tool_executor",
            IntentType.SEARCH_CODE: "tool_executor",
            IntentType.RUN_COMMAND: "tool_executor",
            IntentType.WEB_SEARCH: "tool_executor",
            
            IntentType.CODE_GENERATION: "single_agent",
            IntentType.CODE_REVIEW: "single_agent",
            IntentType.DEBUGGING: "single_agent",
            
            IntentType.COMPLEX_TASK: "workflow_executor",
            IntentType.RESEARCH: "workflow_executor",
            IntentType.REFACTORING: "workflow_executor",
            
            IntentType.UNKNOWN: "direct_response",
        }
    
    async def classify(
        self,
        message: str,
        context: Optional[Dict] = None,
    ) -> ClassifiedIntent:
        """
        Classify user intent.
        
        Uses a fast LLM call with structured output.
        """
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI()
        
        # Build classification prompt
        prompt = f"""Classify the user's intent. Return a JSON object with:
- intent_type: One of {[e.value for e in IntentType]}
- confidence: Float 0-1
- entities: Extracted entities (file names, function names, etc.)
- reasoning: Brief explanation

User message: {message}

Context:
- Current file: {context.get('current_file', 'None') if context else 'None'}
- Has selected text: {bool(context.get('selected_text')) if context else False}
"""
        
        response = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        
        result = json.loads(response.choices[0].message.content)
        
        intent_type = IntentType(result.get("intent_type", "unknown"))
        
        return ClassifiedIntent(
            intent_type=intent_type,
            confidence=result.get("confidence", 0.5),
            extracted_entities=result.get("entities", {}),
            suggested_handler=self.handlers[intent_type],
            reasoning=result.get("reasoning", ""),
        )
    
    def get_handler(self, intent: ClassifiedIntent) -> str:
        """Get handler name for intent."""
        return self.handlers.get(intent.intent_type, "direct_response")
```

#### 3. Streaming Response Handler

```python
# cmbagent/assistant/streaming.py

from typing import AsyncIterator, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio
import json


class StreamEventType(Enum):
    # Content tokens
    TOKEN = "token"                    # Single token from LLM
    CONTENT_BLOCK = "content_block"    # Larger content chunk
    
    # Tool events
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_ARGS = "tool_call_args"
    TOOL_CALL_END = "tool_call_end"
    TOOL_RESULT = "tool_result"
    
    # Status events
    THINKING = "thinking"
    SEARCHING = "searching"
    EXECUTING = "executing"
    
    # Completion events
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class StreamEvent:
    event_type: StreamEventType
    data: Dict[str, Any]
    
    def to_json(self) -> str:
        return json.dumps({
            "type": self.event_type.value,
            "data": self.data,
        })


class StreamingResponseHandler:
    """
    Handles streaming output to client.
    
    Converts various sources (LLM, tools, workflows) into
    a unified stream of events.
    """
    
    def __init__(self, websocket):
        self.websocket = websocket
        self._cancelled = False
    
    async def stream_llm_response(
        self,
        response_iterator: AsyncIterator[str],
    ) -> str:
        """Stream LLM response token by token."""
        full_content = ""
        
        async for token in response_iterator:
            if self._cancelled:
                await self._send_event(StreamEvent(
                    event_type=StreamEventType.CANCELLED,
                    data={"partial_content": full_content}
                ))
                break
            
            full_content += token
            await self._send_event(StreamEvent(
                event_type=StreamEventType.TOKEN,
                data={"token": token}
            ))
        
        await self._send_event(StreamEvent(
            event_type=StreamEventType.DONE,
            data={"full_content": full_content}
        ))
        
        return full_content
    
    async def stream_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        executor: Callable,
    ) -> Dict[str, Any]:
        """Stream a tool call with progress."""
        
        # Notify tool call start
        await self._send_event(StreamEvent(
            event_type=StreamEventType.TOOL_CALL_START,
            data={"tool": tool_name}
        ))
        
        # Stream arguments
        await self._send_event(StreamEvent(
            event_type=StreamEventType.TOOL_CALL_ARGS,
            data={"tool": tool_name, "args": tool_args}
        ))
        
        # Execute tool
        try:
            result = await executor(tool_name, tool_args)
            
            await self._send_event(StreamEvent(
                event_type=StreamEventType.TOOL_RESULT,
                data={"tool": tool_name, "result": result, "success": True}
            ))
            
            return result
            
        except Exception as e:
            await self._send_event(StreamEvent(
                event_type=StreamEventType.TOOL_RESULT,
                data={"tool": tool_name, "error": str(e), "success": False}
            ))
            raise
        
        finally:
            await self._send_event(StreamEvent(
                event_type=StreamEventType.TOOL_CALL_END,
                data={"tool": tool_name}
            ))
    
    async def stream_workflow_progress(
        self,
        workflow_executor,
    ):
        """Stream workflow execution progress."""
        # Connect to workflow callbacks
        pass
    
    async def _send_event(self, event: StreamEvent):
        """Send event to WebSocket."""
        try:
            await self.websocket.send_text(event.to_json())
        except Exception as e:
            print(f"Failed to send stream event: {e}")
    
    def cancel(self):
        """Cancel the current stream."""
        self._cancelled = True
```

#### 4. Tool Registry for Assistant

```python
# cmbagent/assistant/tools.py

from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass
import asyncio


@dataclass
class AssistantTool:
    """Tool definition for assistant."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema
    handler: Callable
    category: str = "general"
    requires_confirmation: bool = False


class AssistantToolRegistry:
    """
    Registry of tools available to the assistant.
    
    Provides tools for:
    - File operations (read, write, search)
    - Terminal commands
    - Web search
    - Code analysis
    """
    
    def __init__(self):
        self.tools: Dict[str, AssistantTool] = {}
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """Register built-in tools."""
        
        # File tools
        self.register(AssistantTool(
            name="read_file",
            description="Read contents of a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "start_line": {"type": "integer", "description": "Start line (optional)"},
                    "end_line": {"type": "integer", "description": "End line (optional)"},
                },
                "required": ["path"],
            },
            handler=self._read_file,
            category="file",
        ))
        
        self.register(AssistantTool(
            name="write_file",
            description="Write content to a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            handler=self._write_file,
            category="file",
            requires_confirmation=True,
        ))
        
        self.register(AssistantTool(
            name="edit_file",
            description="Edit a file by replacing text",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
            },
            handler=self._edit_file,
            category="file",
            requires_confirmation=True,
        ))
        
        # Search tools
        self.register(AssistantTool(
            name="search_code",
            description="Search for text in codebase",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "file_pattern": {"type": "string", "description": "Glob pattern (optional)"},
                },
                "required": ["query"],
            },
            handler=self._search_code,
            category="search",
        ))
        
        self.register(AssistantTool(
            name="find_files",
            description="Find files matching pattern",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern"},
                },
                "required": ["pattern"],
            },
            handler=self._find_files,
            category="search",
        ))
        
        # Terminal tools
        self.register(AssistantTool(
            name="run_command",
            description="Run a terminal command",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string", "description": "Working directory (optional)"},
                },
                "required": ["command"],
            },
            handler=self._run_command,
            category="terminal",
            requires_confirmation=True,
        ))
        
        # Web tools
        self.register(AssistantTool(
            name="web_search",
            description="Search the web",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
            handler=self._web_search,
            category="web",
        ))
    
    def register(self, tool: AssistantTool):
        """Register a tool."""
        self.tools[tool.name] = tool
    
    def get_openai_tools(self) -> List[Dict]:
        """Get tools in OpenAI format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in self.tools.values()
        ]
    
    async def execute(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Execute a tool."""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        tool = self.tools[tool_name]
        return await tool.handler(**args)
    
    # Tool implementations
    async def _read_file(self, path: str, start_line: int = None, end_line: int = None) -> str:
        """Read file contents."""
        with open(path, 'r') as f:
            lines = f.readlines()
        
        if start_line and end_line:
            lines = lines[start_line-1:end_line]
        
        return ''.join(lines)
    
    async def _write_file(self, path: str, content: str) -> Dict:
        """Write file."""
        with open(path, 'w') as f:
            f.write(content)
        return {"success": True, "path": path}
    
    async def _edit_file(self, path: str, old_text: str, new_text: str) -> Dict:
        """Edit file by replacement."""
        with open(path, 'r') as f:
            content = f.read()
        
        if old_text not in content:
            return {"success": False, "error": "Text not found"}
        
        new_content = content.replace(old_text, new_text, 1)
        
        with open(path, 'w') as f:
            f.write(new_content)
        
        return {"success": True, "path": path}
    
    async def _search_code(self, query: str, file_pattern: str = None) -> List[Dict]:
        """Search code."""
        import subprocess
        
        cmd = ["grep", "-rn", query, "."]
        if file_pattern:
            cmd.extend(["--include", file_pattern])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        matches = []
        for line in result.stdout.split('\n')[:20]:  # Limit results
            if ':' in line:
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    matches.append({
                        "file": parts[0],
                        "line": int(parts[1]),
                        "content": parts[2].strip(),
                    })
        
        return matches
    
    async def _find_files(self, pattern: str) -> List[str]:
        """Find files."""
        import glob
        return glob.glob(pattern, recursive=True)[:50]
    
    async def _run_command(self, command: str, cwd: str = None) -> Dict:
        """Run terminal command."""
        import subprocess
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=60,
        )
        
        return {
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:1000],
            "exit_code": result.returncode,
        }
    
    async def _web_search(self, query: str) -> List[Dict]:
        """Web search (would use Perplexity/Brave)."""
        # Placeholder - would integrate with actual search
        return [{"title": "Result", "url": "https://...", "snippet": "..."}]
```

---

## Integration with Phase Architecture

### Copilot as a Phase

```python
# cmbagent/phases/copilot.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncIterator
import time

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.assistant.conversation import ConversationManager
from cmbagent.assistant.router import IntentRouter, IntentType
from cmbagent.assistant.tools import AssistantToolRegistry


@dataclass
class CopilotPhaseConfig(PhaseConfig):
    """Configuration for copilot/assistant phase."""
    phase_type: str = "copilot"
    
    # Model settings
    model: str = "gpt-4o"
    
    # Behavior
    streaming: bool = True
    max_turns: int = 100  # Max conversation turns before requiring new phase
    
    # Tool settings
    enable_file_tools: bool = True
    enable_terminal_tools: bool = True
    enable_web_tools: bool = True
    require_confirmation_for_edits: bool = True


class CopilotPhase(Phase):
    """
    Copilot/Assistant phase - conversational AI with tool use.
    
    This phase runs a continuous conversation loop where:
    - User sends messages
    - Assistant responds with streaming output
    - Tools are called as needed
    - Conversation continues until user exits or max turns reached
    
    Can be composed with other phases:
    - After planning, to discuss the plan
    - After execution, to explain results
    - As standalone for general assistance
    """
    
    def __init__(self, config: CopilotPhaseConfig = None):
        if config is None:
            config = CopilotPhaseConfig()
        super().__init__(config)
        self.config: CopilotPhaseConfig = config
        
        # Initialize components
        self.conversation = ConversationManager(model=config.model)
        self.router = IntentRouter()
        self.tools = AssistantToolRegistry()
        
        # Register tools with conversation
        for tool_def in self.tools.get_openai_tools():
            self.conversation.register_tool(tool_def)
    
    @property
    def phase_type(self) -> str:
        return "copilot"
    
    @property
    def display_name(self) -> str:
        return "AI Assistant"
    
    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Run copilot conversation loop.
        
        This is different from other phases - it runs continuously
        until user exits or max turns reached.
        """
        self._status = PhaseStatus.RUNNING
        context.started_at = time.time()
        
        turns = 0
        chat_history = []
        
        # Get message queue from context (injected by workflow executor)
        message_queue = context.shared_state.get('_message_queue')
        response_stream = context.shared_state.get('_response_stream')
        
        if not message_queue or not response_stream:
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error="Copilot phase requires message_queue and response_stream in context",
            )
        
        try:
            while turns < self.config.max_turns:
                # Wait for user message
                user_message = await message_queue.get()
                
                if user_message == "__EXIT__":
                    break
                
                turns += 1
                
                # Classify intent
                intent = await self.router.classify(
                    user_message,
                    context={"current_file": context.shared_state.get('current_file')}
                )
                
                # Handle based on intent
                if intent.suggested_handler == "workflow_executor":
                    # Complex task - might want to switch to planning phase
                    context.output_data['switch_to_workflow'] = True
                    context.output_data['detected_task'] = user_message
                    break
                
                # Stream response
                full_response = ""
                async for token in self.conversation.chat(user_message):
                    full_response += token
                    await response_stream.put({"type": "token", "token": token})
                
                await response_stream.put({"type": "done"})
                
                chat_history.append({
                    "role": "user",
                    "content": user_message,
                })
                chat_history.append({
                    "role": "assistant", 
                    "content": full_response,
                })
            
            context.output_data['chat_history'] = chat_history
            context.output_data['turns'] = turns
            context.completed_at = time.time()
            self._status = PhaseStatus.COMPLETED
            
            return PhaseResult(
                status=PhaseStatus.COMPLETED,
                context=context,
                chat_history=chat_history,
            )
            
        except Exception as e:
            self._status = PhaseStatus.FAILED
            return PhaseResult(
                status=PhaseStatus.FAILED,
                context=context,
                error=str(e),
            )


# Workflow that starts with Copilot and can escalate to full workflow
COPILOT_WITH_ESCALATION_WORKFLOW = WorkflowDefinition(
    id="copilot_with_escalation",
    name="AI Assistant (with escalation)",
    description="Conversational assistant that can escalate to full workflows",
    phases=[
        {"type": "copilot", "config": {"max_turns": 50}},
        # If copilot detects complex task, can transition to:
        {"type": "planning", "config": {"conditional": "switch_to_workflow"}},
        {"type": "hitl_checkpoint", "config": {"conditional": "switch_to_workflow"}},
        {"type": "control", "config": {"conditional": "switch_to_workflow"}},
    ],
    is_system=True,
)
```

---

## Implementation Plan

### Phase 1: Core Conversation Infrastructure (Week 1-2)

- [ ] Create `ConversationManager` with streaming
- [ ] Create `IntentRouter` for classification
- [ ] Create `AssistantToolRegistry` with basic tools
- [ ] Create `StreamingResponseHandler`

### Phase 2: WebSocket Integration (Week 2)

- [ ] Add token-level streaming to WebSocket
- [ ] Create client-side streaming handler
- [ ] Add conversation endpoints to API

### Phase 3: Tool Integration (Week 2-3)

- [ ] Integrate existing MCP tools
- [ ] Integrate AG2 free tools
- [ ] Add file operation tools
- [ ] Add terminal tools

### Phase 4: Memory & Context (Week 3)

- [ ] Implement conversation history persistence
- [ ] Add context window management
- [ ] Implement summarization for long conversations
- [ ] Add workspace indexing

### Phase 5: UI Components (Week 3-4)

- [ ] Create chat input component
- [ ] Create streaming message display
- [ ] Create tool call visualization
- [ ] Create conversation history sidebar

### Phase 6: Integration with Phases (Week 4)

- [ ] Create `CopilotPhase`
- [ ] Implement workflow escalation
- [ ] Test phase composition

---

## Summary

### Can We Build Copilot with Current Architecture?

**Partially Yes, But Need These Additions:**

| Component | Status | Work Needed |
|-----------|--------|-------------|
| Multi-agent orchestration | ✅ Have | - |
| Tool execution | ✅ Have | Wrap in assistant-style API |
| WebSocket | ✅ Have | Add token streaming |
| Database | ✅ Have | Add conversation tables |
| **Conversation loop** | ❌ Need | Build `ConversationManager` |
| **Token streaming** | ❌ Need | Modify LLM calls |
| **Intent routing** | ❌ Need | Build `IntentRouter` |
| **Context injection** | ⚠️ Partial | Build `ConversationContext` |
| **Memory management** | ⚠️ Partial | Build summarization |

### Architecture Fit

The Phase-based architecture we designed **directly supports** adding a Copilot mode:

```python
# Copilot as a Phase that can be composed
INTERACTIVE_WORKFLOW = [
    CopilotPhase(max_turns=50),           # Interactive chat
    # Escalate to workflow if complex task detected
    PlanningPhase(conditional="complex"),  
    ControlPhase(conditional="complex"),
]
```

### Estimated Effort

- **Core Infrastructure**: 2 weeks
- **UI Components**: 1 week  
- **Integration & Testing**: 1 week
- **Total**: ~4 weeks

The existing CMBAgent architecture provides 60-70% of what's needed. The main additions are the conversation loop, streaming, and intent routing.

---

*Copilot Architecture Analysis*  
*Version 1.0*  
*January 2026*
