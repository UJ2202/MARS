"""
Copilot Tool Functions - Modes as Tools

This module converts copilot "modes" into functions/tools that can be
called by the copilot_control agent. This enables fluent, autonomous
operation where the agent decides what to do rather than rigid routing.

Instead of:
    User → Analyze → Route to ONE mode → Execute → Ask "what next?"

We have:
    User → Agent has tools → Agent chains tools as needed → Done

Tools available:
- create_and_execute_plan(task) - For complex multi-step work
- execute_task_directly(task) - For simple one-shot execution
- research_information(query) - For gathering information
- ask_user_for_clarification(questions) - When something is unclear
- report_completion(summary) - When task is finished
"""

from typing import Annotated, Dict, Any, List, Optional
import json


def create_and_execute_plan(
    task: Annotated[str, "The complex task that needs a step-by-step plan"],
    max_steps: Annotated[int, "Maximum number of steps (default 5)"] = 5
) -> str:
    """
    Create a detailed plan and execute it step by step.

    Use this when:
    - Task has multiple clear steps
    - Task requires sequential operations
    - Task involves different types of work (code + research + testing)

    The plan will be created, shown to user for approval, then executed.

    Returns:
        JSON string with execution results and summary
    """
    # This is called by the agent - we store the request in context
    # The actual execution happens in copilot_phase
    return json.dumps({
        "action": "create_and_execute_plan",
        "task": task,
        "max_steps": max_steps,
        "status": "planning_requested"
    })


def execute_task_directly(
    task: Annotated[str, "The task to execute directly without planning"],
    agent_type: Annotated[str, "Which agent should handle this (engineer/researcher)"] = "engineer"
) -> str:
    """
    Execute a task directly without creating a plan.

    Use this when:
    - Task is straightforward and can be done in one go
    - Writing a simple function or script
    - Quick research or lookup
    - Making a simple code change

    Returns:
        JSON string with execution results
    """
    return json.dumps({
        "action": "execute_directly",
        "task": task,
        "agent_type": agent_type,
        "status": "execution_requested"
    })


def research_information(
    query: Annotated[str, "What to research or look up"],
    depth: Annotated[str, "How thorough: 'quick' or 'deep'"] = "quick"
) -> str:
    """
    Research information, look up documentation, or gather context.

    Use this when:
    - Need to understand something before coding
    - Looking up API documentation
    - Researching best practices or patterns
    - Gathering requirements

    Returns:
        JSON string with research findings
    """
    return json.dumps({
        "action": "research",
        "query": query,
        "depth": depth,
        "status": "research_requested"
    })


def ask_user_for_clarification(
    questions: Annotated[List[str], "List of specific questions to ask the user"]
) -> str:
    """
    Ask the user for clarification when the task is ambiguous or incomplete.

    Use this when:
    - Task is vague or unclear
    - Multiple valid approaches exist and user should decide
    - Missing critical information (API keys, file paths, requirements)
    - Potentially destructive action needs confirmation

    Returns:
        JSON string indicating clarification was requested
    """
    return json.dumps({
        "action": "ask_clarification",
        "questions": questions,
        "status": "awaiting_user_response"
    })


def report_completion(
    summary: Annotated[str, "Summary of what was accomplished"],
    files_modified: Annotated[List[str], "List of files that were changed"] = None,
    next_steps: Annotated[List[str], "Optional suggestions for what to do next"] = None
) -> str:
    """
    Report that the task is complete.

    Use this when:
    - Task is fully completed
    - All requested work is done
    - Ready to return to user

    Returns:
        JSON string with completion summary
    """
    return json.dumps({
        "action": "complete",
        "summary": summary,
        "files_modified": files_modified or [],
        "next_steps": next_steps or [],
        "status": "completed"
    })


def chain_operations(
    operations: Annotated[List[Dict[str, Any]], "Sequence of operations to perform"]
) -> str:
    """
    Execute multiple operations in sequence.

    Use this when:
    - Task naturally breaks into sequential stages
    - Each stage depends on previous stage
    - Want to show progress through complex workflow

    Example:
        [
            {"type": "research", "query": "React hooks best practices"},
            {"type": "execute", "task": "Create useAuth hook"},
            {"type": "execute", "task": "Add tests for hook"}
        ]

    Returns:
        JSON string indicating chained operations started
    """
    return json.dumps({
        "action": "chain_operations",
        "operations": operations,
        "status": "chaining_started"
    })


# Tool metadata for registration
COPILOT_TOOLS = [
    create_and_execute_plan,
    execute_task_directly,
    research_information,
    ask_user_for_clarification,
    report_completion,
    chain_operations,
]


def get_copilot_tools_description() -> str:
    """Get description of available tools for agent prompt."""
    return """
You have access to the following tools to accomplish tasks:

1. **create_and_execute_plan(task, max_steps=5)** - For complex multi-step work
   - Creates a detailed plan
   - Executes each step
   - Good for: implementations, features, refactoring

2. **execute_task_directly(task, agent_type='engineer')** - For simple one-shot work
   - No planning, just do it
   - Good for: small functions, quick fixes, simple scripts

3. **research_information(query, depth='quick')** - For gathering information
   - Look up docs, patterns, context
   - Good for: understanding before coding, API lookup

4. **ask_user_for_clarification(questions)** - When you need input
   - Ask specific questions
   - Good for: vague tasks, missing info, confirmation

5. **report_completion(summary, files_modified, next_steps)** - When done
   - Summarize what was accomplished
   - List what changed
   - Suggest next steps

6. **chain_operations(operations)** - For sequential workflows
   - Execute multiple operations in order
   - Good for: research → code → test flows

**Important Guidelines:**
- Choose tools autonomously based on task complexity
- Chain tools when needed (research then code, plan then execute)
- Only ask_user_for_clarification when genuinely unclear
- Always report_completion when task is done
- Be proactive - don't ask permission for standard operations
"""
