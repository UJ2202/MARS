"""Copilot routing functionality - intelligent task analysis and agent selection."""

import logging
from typing import List, Optional
from autogen import register_function
from autogen.agentchat.group import ContextVariables, AgentTarget, ReplyResult, TerminateTarget
from IPython.display import Markdown, display

from cmbagent.structured_output import CopilotRoutingDecision
from cmbagent.functions.copilot_tools import COPILOT_TOOLS, get_copilot_tools_description

logger = logging.getLogger(__name__)


def analyze_task_for_routing(
    route_type: str,
    complexity_score: int,
    complexity_reasoning: str,
    primary_agent: str,
    supporting_agents: List[str],
    agent_reasoning: str,
    estimated_steps: int,
    clarifying_questions: List[str],
    refined_task: str,
    confidence: float,
    context_variables: ContextVariables,
    cmbagent_instance,
) -> ReplyResult:
    """
    Records the copilot control agent's routing decision.

    This function captures the intelligent analysis of a task and stores
    the routing decision for the copilot phase to act upon.

    Args:
        route_type: How to handle task - 'one_shot', 'planned', or 'clarify'
        complexity_score: Task complexity 0-100
        complexity_reasoning: Why this complexity score
        primary_agent: Best agent for the task
        supporting_agents: Additional agents that might be needed
        agent_reasoning: Why these agents were selected
        estimated_steps: Estimated steps if planning is needed
        clarifying_questions: Questions if route_type is 'clarify'
        refined_task: Refined/clarified version of the task
        confidence: Confidence in this decision (0-1)
        context_variables: Shared context
        cmbagent_instance: Reference to CMBAgent
    """
    # Build structured decision
    decision = CopilotRoutingDecision(
        route_type=route_type,
        complexity_score=complexity_score,
        complexity_reasoning=complexity_reasoning,
        primary_agent=primary_agent,
        supporting_agents=supporting_agents or [],
        agent_reasoning=agent_reasoning,
        estimated_steps=estimated_steps,
        clarifying_questions=clarifying_questions or [],
        refined_task=refined_task,
        confidence=confidence,
    )

    # Store in context
    context_variables["copilot_routing_decision"] = decision.model_dump()
    context_variables["copilot_route_type"] = route_type
    context_variables["copilot_primary_agent"] = primary_agent
    context_variables["copilot_supporting_agents"] = supporting_agents or []
    context_variables["copilot_complexity"] = complexity_score
    context_variables["copilot_refined_task"] = refined_task
    context_variables["copilot_estimated_steps"] = estimated_steps

    # Log the decision
    logger.info("copilot_routing_decision",
                route_type=route_type,
                primary_agent=primary_agent,
                complexity_score=complexity_score,
                confidence=confidence,
                estimated_steps=estimated_steps)
    logger.debug("copilot_routing_detail", decision=decision.format())

    # Terminate - the copilot phase will read the decision from context
    # and take appropriate action
    terminator = cmbagent_instance.get_agent_from_name('terminator')

    return ReplyResult(
        target=AgentTarget(terminator),
        message="Routing decision recorded. Ready for execution.",
        context_variables=context_variables
    )


def record_copilot_handoff(
    should_handoff: bool,
    target_agent: str,
    handoff_reason: str,
    context_to_pass: List[str],
    context_variables: ContextVariables,
    cmbagent_instance,
) -> ReplyResult:
    """
    Records a mid-execution handoff decision from copilot control.

    Used when the copilot control determines a different agent should
    take over during execution.

    Args:
        should_handoff: Whether to handoff to another agent
        target_agent: Agent to handoff to
        handoff_reason: Why this handoff is needed
        context_to_pass: Key context items to pass
        context_variables: Shared context
        cmbagent_instance: Reference to CMBAgent
    """
    context_variables["copilot_handoff_decision"] = {
        "should_handoff": should_handoff,
        "target_agent": target_agent,
        "handoff_reason": handoff_reason,
        "context_to_pass": context_to_pass or [],
    }

    if should_handoff and target_agent:
        logger.info("copilot_handoff", target_agent=target_agent, reason=handoff_reason)

        try:
            next_agent = cmbagent_instance.get_agent_from_name(target_agent)
            return ReplyResult(
                target=AgentTarget(next_agent),
                message=f"Handing off to {target_agent}: {handoff_reason}",
                context_variables=context_variables
            )
        except Exception as e:
            logger.warning("copilot_handoff_agent_not_found", target_agent=target_agent, error=str(e))

    # No handoff or agent not found - terminate
    terminator = cmbagent_instance.get_agent_from_name('terminator')
    return ReplyResult(
        target=AgentTarget(terminator),
        message="No handoff needed or target not found.",
        context_variables=context_variables
    )


def setup_copilot_functions(cmbagent_instance, available_agents: List[str] = None):
    """Register copilot-related functions with the copilot_control agent."""
    try:
        copilot_control = cmbagent_instance.get_agent_from_name('copilot_control')
    except Exception:
        logger.debug("copilot_control_agent_not_found", action="skipping_function_registration")
        return

    # Create closures to bind cmbagent_instance
    def analyze_task_closure(
        route_type: str,
        complexity_score: int,
        complexity_reasoning: str,
        primary_agent: str,
        supporting_agents: List[str],
        agent_reasoning: str,
        estimated_steps: int,
        clarifying_questions: List[str],
        refined_task: str,
        confidence: float,
        context_variables: ContextVariables,
    ) -> ReplyResult:
        return analyze_task_for_routing(
            route_type=route_type,
            complexity_score=complexity_score,
            complexity_reasoning=complexity_reasoning,
            primary_agent=primary_agent,
            supporting_agents=supporting_agents,
            agent_reasoning=agent_reasoning,
            estimated_steps=estimated_steps,
            clarifying_questions=clarifying_questions,
            refined_task=refined_task,
            confidence=confidence,
            context_variables=context_variables,
            cmbagent_instance=cmbagent_instance,
        )

    def handoff_closure(
        should_handoff: bool,
        target_agent: str,
        handoff_reason: str,
        context_to_pass: List[str],
        context_variables: ContextVariables,
    ) -> ReplyResult:
        return record_copilot_handoff(
            should_handoff=should_handoff,
            target_agent=target_agent,
            handoff_reason=handoff_reason,
            context_to_pass=context_to_pass,
            context_variables=context_variables,
            cmbagent_instance=cmbagent_instance,
        )

    # Build agent info string for the prompt
    agent_info = []
    default_agents = available_agents or ["engineer", "researcher"]
    for agent_name in default_agents:
        try:
            agent = cmbagent_instance.get_agent_from_name(agent_name)
            desc = getattr(agent, 'description', f'{agent_name} agent')
            agent_info.append(f"- **{agent_name}**: {desc}")
        except Exception:
            agent_info.append(f"- **{agent_name}**: Available agent")

    # Store available agents info in context for the prompt
    # This will be injected into the copilot_control instructions

    # Register the routing analysis function
    register_function(
        analyze_task_closure,
        caller=copilot_control,
        executor=copilot_control,
        description=r"""
Analyze the task and record a routing decision.

Call this function with your analysis to determine how the task should be handled.

Args:
    route_type: How to handle - 'one_shot' (simple, direct execution),
                'planned' (needs multi-step plan), or 'clarify' (need more info)
    complexity_score: Task complexity 0-100 (0-30=simple, 30-60=moderate, 60+=complex)
    complexity_reasoning: Brief explanation of the complexity score
    primary_agent: Best agent for this task (e.g., 'engineer', 'researcher')
    supporting_agents: List of other agents that might be needed
    agent_reasoning: Why these agents were selected
    estimated_steps: Estimated number of steps if route_type is 'planned'
    clarifying_questions: List of questions if route_type is 'clarify'
    refined_task: Clarified/refined version of the original task
    confidence: Your confidence in this decision (0.0 to 1.0)
        """,
    )

    # Register the handoff function
    register_function(
        handoff_closure,
        caller=copilot_control,
        executor=copilot_control,
        description=r"""
Record a handoff decision to transfer control to another agent.

Use this when you determine a different agent should take over mid-execution.

Args:
    should_handoff: True if handoff is needed, False otherwise
    target_agent: Name of agent to handoff to
    handoff_reason: Why this handoff is needed
    context_to_pass: List of key context items to pass to next agent
        """,
    )

    return copilot_control


def setup_copilot_tools_mode(cmbagent_instance, available_agents: List[str] = None):
    """
    Register copilot tools for autonomous mode.

    In this mode, the copilot agent has tools to invoke different modes
    (planning, execution, research) dynamically rather than rigid routing.

    The agent can chain operations and make decisions autonomously.
    """
    try:
        # Try to get copilot_control agent first
        try:
            main_agent = cmbagent_instance.get_agent_from_name('copilot_control')
            agent_name = 'copilot_control'
        except:
            # Fallback to engineer if copilot_control doesn't exist
            main_agent = cmbagent_instance.get_agent_from_name('engineer')
            agent_name = 'engineer'

        logger.info("copilot_tools_registering", agent=agent_name)

    except Exception as e:
        logger.warning("copilot_tools_no_suitable_agent", error=str(e))
        return

    # Register all copilot tools
    for tool_func in COPILOT_TOOLS:
        register_function(
            tool_func,
            caller=main_agent,
            executor=main_agent,
            description=tool_func.__doc__ or f"Tool: {tool_func.__name__}",
        )

    logger.info("copilot_tools_registered", tool_count=len(COPILOT_TOOLS))

    # Update agent instructions to include tool usage guidelines
    if hasattr(main_agent, 'system_message'):
        tools_guide = get_copilot_tools_description()

        current_instructions = main_agent.system_message or ""
        if "You have access to the following tools" not in current_instructions:
            main_agent.system_message = f"{current_instructions}\n\n{tools_guide}"
            logger.debug("copilot_tools_instructions_updated", agent=agent_name)

    return main_agent
