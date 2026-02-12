"""
HITL (Human-in-the-Loop) handoff configurations.

Provides both mandatory checkpoints and smart approval.
Includes WebSocket integration for UI-based approval.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from autogen.agentchat.group import AgentTarget, OnCondition, StringLLMCondition
from .debug import debug_print
from .agent_retrieval import get_all_agents

logger = logging.getLogger(__name__)


# ============================================================================
# WEBSOCKET INTEGRATION FOR ADMIN AGENT
# ============================================================================

def configure_admin_for_websocket(admin_agent, approval_manager, run_id: str):
    """
    Configure admin agent to use WebSocket for human input instead of console.

    This allows AG2 handoffs to route approval requests through the UI
    instead of blocking on console input().

    Args:
        admin_agent: The admin agent instance (UserProxyAgent or ConversableAgent)
        approval_manager: WebSocketApprovalManager instance
        run_id: Current workflow run ID

    Example:
        from cmbagent.database.websocket_approval_manager import WebSocketApprovalManager

        approval_manager = WebSocketApprovalManager(ws_send_event, task_id)
        configure_admin_for_websocket(admin_agent, approval_manager, task_id)
    """
    debug_print(f'→ Configuring admin agent for WebSocket (run_id: {run_id})')

    # Store original get_human_input if it exists
    original_input = getattr(admin_agent.agent, 'get_human_input', None)

    def websocket_human_input_sync(prompt: str) -> str:
        """
        Synchronous wrapper for async WebSocket approval.

        This is needed because AG2's get_human_input is synchronous,
        but our WebSocket approval is async.
        """
        logger.info("human_input_requested", source="ag2_admin", transport="websocket")
        logger.debug("human_input_prompt", prompt_preview=prompt[:200])

        try:
            # Parse the prompt to extract agent name and context
            agent_name = "unknown"
            if "From:" in prompt:
                agent_name = prompt.split("From:")[1].split("\n")[0].strip()

            # Create approval request
            approval_request = approval_manager.create_approval_request(
                run_id=run_id,
                step_id=f"ag2_handoff_{agent_name}",
                checkpoint_type="ag2_dynamic",
                context_snapshot={
                    "agent_name": agent_name,
                    "full_prompt": prompt,
                    "source": "ag2_handoff"
                },
                message=f"**Agent Handoff: {agent_name}**\n\n{prompt}",
                options=["continue", "provide_instructions", "abort"],
            )

            logger.info("approval_request_created", approval_id=str(approval_request.id), source="ag2_admin")
            logger.debug("waiting_for_websocket_approval", approval_id=str(approval_request.id))

            # Create event loop if needed and wait for approval
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Wait for approval (blocking until user responds in UI)
            resolved = loop.run_until_complete(
                approval_manager.wait_for_approval_async(
                    str(approval_request.id),
                    timeout_seconds=1800,  # 30 minutes
                )
            )

            logger.info("approval_resolved", resolution=resolved.resolution, source="ag2_admin")

            # Process the resolution
            if resolved.resolution in ["continue", "approved", "approve"]:
                # User approved - continue with empty response
                return ""
            elif resolved.resolution in ["provide_instructions", "modify", "modified"]:
                # User provided specific instructions
                feedback = resolved.user_feedback or ""
                logger.info("user_provided_instructions", feedback_preview=feedback[:100], source="ag2_admin")
                return feedback
            else:  # abort, reject, rejected
                # User wants to stop
                logger.info("user_aborted", resolution=resolved.resolution, source="ag2_admin")
                return "TERMINATE"

        except TimeoutError:
            logger.warning("websocket_approval_timeout", source="ag2_admin", action="auto_abort")
            return "TERMINATE"
        except Exception as e:
            logger.error("websocket_approval_error", error=str(e), source="ag2_admin", exc_info=True)

            # Fall back to original input if available
            if original_input:
                logger.info("falling_back_to_original_input", source="ag2_admin")
                return original_input(prompt)
            else:
                logger.warning("no_fallback_available", source="ag2_admin", action="abort")
                return "TERMINATE"

    # Override the agent's get_human_input method
    admin_agent.agent.get_human_input = websocket_human_input_sync

    debug_print('Admin agent configured for WebSocket input', indent=2)
    logger.info("websocket_input_handler_installed", source="ag2_admin")


def enable_websocket_for_hitl(
    cmbagent_instance,
    approval_manager,
    run_id: str
):
    """
    Enable WebSocket-based approval for all AG2 HITL handoffs.

    Call this after registering HITL handoffs to route admin agent
    interactions through the UI.

    Args:
        cmbagent_instance: CMBAgent instance
        approval_manager: WebSocketApprovalManager instance
        run_id: Current workflow run ID

    Example:
        # Register handoffs
        register_all_hand_offs(cmbagent, hitl_config={
            'mandatory_checkpoints': ['after_planning'],
            'smart_approval': True,
        })

        # Enable WebSocket
        enable_websocket_for_hitl(cmbagent, approval_manager, task_id)
    """
    debug_print('→ Enabling WebSocket for HITL handoffs...')

    agents = get_all_agents(cmbagent_instance)

    if 'admin' not in agents:
        debug_print('WARNING: Admin agent not found - cannot enable WebSocket', indent=2)
        return

    admin_agent = agents['admin']
    configure_admin_for_websocket(admin_agent, approval_manager, run_id)

    debug_print('WebSocket enabled for HITL\n', indent=2)


# ============================================================================
# HITL HANDOFF REGISTRATION
# ============================================================================

def register_hitl_handoffs(agents: Dict, hitl_config: Dict):
    """
    Register HITL (Human-in-the-Loop) handoffs for human oversight.

    Supports both mandatory checkpoints (always go to human) and smart
    approval (LLM decides when to escalate to human).

    Args:
        agents: Dictionary of agent instances
        hitl_config: Configuration dict with:
            - mandatory_checkpoints: List of checkpoint names
            - smart_approval: Enable dynamic escalation
            - smart_criteria: Criteria for escalation

    Example config:
        {
            'mandatory_checkpoints': ['after_planning', 'before_file_edit'],
            'smart_approval': True,
            'smart_criteria': {
                'escalate_keywords': ['delete', 'production', 'deploy'],
                'risk_threshold': 0.7,
            }
        }
    """
    debug_print('Registering HITL handoffs...')
    debug_print(f'Config: {hitl_config}', indent=2)

    mandatory_checkpoints = hitl_config.get('mandatory_checkpoints', [])
    smart_approval = hitl_config.get('smart_approval', False)
    smart_criteria = hitl_config.get('smart_criteria', {})

    # Mandatory checkpoints
    if mandatory_checkpoints:
        _register_mandatory_hitl_checkpoints(agents, mandatory_checkpoints)

    # Smart approval (dynamic escalation)
    if smart_approval:
        _register_smart_hitl_approval(agents, smart_criteria)

    debug_print('HITL handoffs configured\n', indent=2)


# ============================================================================
# MANDATORY CHECKPOINTS
# ============================================================================

def _register_mandatory_hitl_checkpoints(agents: Dict, checkpoints: List[str]):
    """
    Register mandatory human checkpoints.

    These checkpoints ALWAYS require human approval before proceeding.

    Args:
        agents: Dictionary of agent instances
        checkpoints: List of checkpoint names
    """
    debug_print(f'→ Mandatory checkpoints: {checkpoints}', indent=2)

    admin = agents['admin']

    # Checkpoint: After planning phase
    if 'after_planning' in checkpoints:
        debug_print('after_planning: plan_reviewer → admin → control', indent=3)

        # Override plan_reviewer handoff to go through admin
        agents['plan_reviewer'].agent.handoffs.set_after_work(
            AgentTarget(admin.agent)
        )

        # Note: Admin's handoff will be configured by mode-specific handlers
        # or can be set explicitly here if needed

    # Checkpoint: Before file editing
    if 'before_file_edit' in checkpoints:
        debug_print('before_file_edit: engineer must escalate to admin', indent=3)

        # Add high-priority condition to engineer (checked first)
        agents['engineer'].agent.handoffs.add_llm_conditions([
            OnCondition(
                target=AgentTarget(admin.agent),
                condition=StringLLMCondition(
                    prompt="About to edit, create, delete, or modify any files. "
                           "MUST get admin approval first."
                )
            )
        ])

    # Checkpoint: Before code execution
    if 'before_execution' in checkpoints:
        debug_print('before_execution: engineer must get approval before running code', indent=3)

        # Add condition to engineer for code execution
        agents['engineer'].agent.handoffs.add_llm_conditions([
            OnCondition(
                target=AgentTarget(admin.agent),
                condition=StringLLMCondition(
                    prompt="About to execute code or run commands. "
                           "Must get admin approval for safety."
                )
            )
        ])

    # Checkpoint: Before deployment
    if 'before_deploy' in checkpoints:
        debug_print('before_deploy: any deployment operation needs approval', indent=3)

        # Add condition to control agent
        agents['control'].agent.handoffs.add_llm_conditions([
            OnCondition(
                target=AgentTarget(admin.agent),
                condition=StringLLMCondition(
                    prompt="About to deploy, publish, or make changes to production environment. "
                           "Requires admin approval."
                )
            )
        ])


# ============================================================================
# SMART APPROVAL
# ============================================================================

def _register_smart_hitl_approval(agents: Dict, criteria: Dict):
    """
    Register smart HITL approval (dynamic escalation).

    The LLM decides when to escalate to human based on context,
    risk level, and configured criteria.

    Args:
        agents: Dictionary of agent instances
        criteria: Criteria for escalation
    """
    debug_print(f'→ Smart approval enabled with criteria: {criteria}', indent=2)

    admin = agents['admin']
    control = agents['control']
    engineer = agents['engineer']

    # Extract criteria
    escalate_keywords = criteria.get('escalate_keywords', [
        'delete', 'production', 'deploy', 'critical', 'irreversible'
    ])
    risk_threshold = criteria.get('risk_threshold', 0.7)

    # Build escalation prompt
    escalation_prompt = f"""
Escalate to admin (human) if ANY of these conditions are met:

1. HIGH RISK OPERATIONS detected:
   - Keywords: {', '.join(escalate_keywords)}
   - Production environment changes
   - Data deletion or irreversible operations
   - Security-sensitive operations

2. UNCERTAINTY about correct approach:
   - Ambiguous requirements
   - Multiple valid solutions with trade-offs
   - Potential for significant negative impact

3. COMPLEX DECISIONS requiring judgment:
   - Architectural choices
   - Cost vs. benefit trade-offs
   - Ethical or policy considerations

4. ERROR RECOVERY:
   - Repeated failures (3+ attempts)
   - Unclear how to proceed
   - Need alternative strategy

IMPORTANT: When in doubt, escalate to admin. Better safe than sorry.
"""

    # Add smart conditions to control agent
    # These are checked AFTER mandatory conditions but BEFORE normal agent routing
    control.agent.handoffs.add_llm_conditions([
        OnCondition(
            target=AgentTarget(admin.agent),
            condition=StringLLMCondition(prompt=escalation_prompt)
        )
    ])

    # Also add to engineer for operation-level decisions
    engineer.agent.handoffs.add_llm_conditions([
        OnCondition(
            target=AgentTarget(admin.agent),
            condition=StringLLMCondition(prompt=escalation_prompt)
        )
    ])

    debug_print('Smart approval conditions added to control and engineer agents', indent=3)


# ============================================================================
# PUBLIC API
# ============================================================================

def configure_hitl_checkpoints(
    cmbagent_instance,
    mandatory_checkpoints: Optional[List[str]] = None,
    smart_approval: bool = False,
    smart_criteria: Optional[Dict] = None,
):
    """
    Configure HITL checkpoints after initial handoff registration.

    This allows dynamic configuration of HITL behavior without
    re-registering all handoffs.

    Args:
        cmbagent_instance: CMBAgent instance
        mandatory_checkpoints: List of mandatory checkpoint names
        smart_approval: Enable smart approval
        smart_criteria: Criteria for smart approval

    Example:
        configure_hitl_checkpoints(
            cmbagent,
            mandatory_checkpoints=['after_planning', 'before_file_edit'],
            smart_approval=True,
            smart_criteria={'escalate_keywords': ['delete', 'production']},
        )
    """
    agents = get_all_agents(cmbagent_instance)

    hitl_config = {
        'mandatory_checkpoints': mandatory_checkpoints or [],
        'smart_approval': smart_approval,
        'smart_criteria': smart_criteria or {},
    }

    register_hitl_handoffs(agents, hitl_config)


def disable_hitl_checkpoints(cmbagent_instance):
    """
    Disable all HITL checkpoints and restore standard handoffs.

    Args:
        cmbagent_instance: CMBAgent instance
    """
    debug_print('→ Disabling HITL checkpoints...')

    # Re-register standard handoffs (overrides HITL)
    from . import register_all_hand_offs
    register_all_hand_offs(cmbagent_instance, hitl_config=None)

    debug_print('HITL checkpoints disabled\n', indent=2)


# ============================================================================
# COPILOT TOOL APPROVAL (with auto-allow session support)
# ============================================================================

def configure_admin_for_copilot_tool_approval(
    admin_agent,
    approval_manager,
    run_id: str,
    permission_manager,
):
    """
    Configure admin agent for copilot tool approval with auto-allow support.

    Overrides admin's get_human_input to:
    1. Classify the tool operation category (bash, code_exec, install, etc.)
    2. Check if auto-allowed for this session (via ToolPermissionManager)
    3. If not, send WebSocket approval with [Allow] [Allow for Session] [Deny] [Edit]
    4. On "Allow for Session", auto-allow that category for the rest of the session

    Args:
        admin_agent: The admin agent instance
        approval_manager: WebSocketApprovalManager for UI communication
        run_id: Current workflow run ID
        permission_manager: ToolPermissionManager tracking session permissions
    """
    debug_print(f'→ Configuring admin for copilot tool approval (run_id: {run_id})')

    def copilot_tool_approval_sync(prompt: str) -> str:
        """
        Synchronous tool approval handler for AG2's get_human_input.

        Checks session permissions first, then sends WebSocket approval if needed.
        """
        # 1. Classify the operation
        category = permission_manager.classify_from_prompt(prompt)

        # Also try agent-based classification from the prompt
        agent_name = "unknown"
        if "From:" in prompt:
            try:
                agent_name = prompt.split("From:")[1].split("\n")[0].strip()
                agent_category = permission_manager.classify_from_agent(agent_name)
                # Prefer more specific agent-based classification
                if agent_category != "code_exec" or category == "code_exec":
                    category = agent_category
            except (IndexError, AttributeError):
                pass

        logger.info("copilot_tool_approval_check", category=category, agent=agent_name)

        # 2. Check auto-allow
        if permission_manager.is_allowed(category):
            logger.debug("copilot_tool_auto_allowed", category=category)
            permission_manager.allow_once(category)
            return ""  # Continue without asking

        # 3. Send WebSocket approval request
        try:
            # Build a user-friendly message
            prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
            message = (
                f"**{category.upper().replace('_', ' ')} Approval**\n\n"
                f"Agent `{agent_name}` wants to perform a **{category}** operation:\n\n"
                f"```\n{prompt_preview}\n```"
            )

            approval_request = approval_manager.create_approval_request(
                run_id=run_id,
                step_id=f"tool_{category}_{agent_name}",
                checkpoint_type="tool_approval",
                context_snapshot={
                    "tool_category": category,
                    "agent_name": agent_name,
                    "prompt": prompt_preview,
                    "can_auto_allow": True,
                    "session_permissions": permission_manager.get_session_permissions(),
                },
                message=message,
                options=["allow", "allow_session", "deny", "edit"],
            )

            logger.debug("copilot_tool_waiting_for_response", approval_id=str(approval_request.id))

            # Wait for approval (blocking)
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            resolved = loop.run_until_complete(
                approval_manager.wait_for_approval_async(
                    str(approval_request.id),
                    timeout_seconds=1800,
                )
            )

            resolution = resolved.resolution
            user_feedback = getattr(resolved, 'user_feedback', '') or ''

            logger.info("copilot_tool_approval_resolved", resolution=resolution)

            if resolution == "allow_session":
                permission_manager.allow_for_session(category)
                return user_feedback or ""
            elif resolution in ("allow", "approve", "approved", "continue"):
                permission_manager.allow_once(category)
                return user_feedback or ""
            elif resolution in ("edit", "modify", "modified"):
                permission_manager.allow_once(category)
                return user_feedback or ""
            elif resolution in ("deny", "reject", "rejected", "abort"):
                logger.info("copilot_tool_operation_denied", category=category)
                return "TERMINATE"
            else:
                # Unknown resolution — treat as allow
                return user_feedback or ""

        except TimeoutError:
            logger.warning("copilot_tool_approval_timeout", action="auto_deny")
            return "TERMINATE"
        except Exception as e:
            logger.error("copilot_tool_approval_error", error=str(e), exc_info=True)
            # On error, allow to prevent hanging
            return ""

    # Override admin's human input handler
    admin_agent.agent.get_human_input = copilot_tool_approval_sync

    debug_print('Admin configured for copilot tool approval with auto-allow', indent=2)
    logger.info("copilot_tool_approval_handler_installed")
