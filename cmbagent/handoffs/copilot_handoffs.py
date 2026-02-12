"""
Copilot-mode handoff configurations.

Adds human-in-the-loop checkpoints before dangerous tool executions
(bash, code execution, file changes, package installation) without
disturbing the existing standard/HITL handoffs.

These handoffs are registered ONLY when copilot_config is passed
to register_all_hand_offs(), keeping them separate from hitl_config.
"""

from typing import Dict
from autogen.agentchat.group import AgentTarget, OnCondition, StringLLMCondition
from .debug import debug_print


def register_copilot_mode_handoffs(agents: Dict, copilot_config: Dict):
    """
    Register copilot-specific handoffs with human-in-loop for tool execution.

    Adds OnCondition handoffs that route to admin (human) before dangerous
    operations. Combined with ToolPermissionManager, this allows:
    - First-time: user sees approval dialog
    - "Allow for Session": subsequent operations auto-approved
    - "Deny": operation blocked

    Args:
        agents: Dictionary of agent instances
        copilot_config: Copilot configuration with keys:
            - tool_approval: str - "prompt" | "auto_allow_all" | "none"

    Example:
        register_copilot_mode_handoffs(agents, {
            'tool_approval': 'prompt',
        })
    """
    tool_approval = copilot_config.get('tool_approval', 'prompt')

    if tool_approval == 'none':
        debug_print('Copilot tool approval: disabled (none)')
        return

    if tool_approval == 'auto_allow_all':
        debug_print('Copilot tool approval: auto-allow all')
        return  # ToolPermissionManager handles this at runtime

    debug_print('Registering copilot tool approval handoffs...')

    if 'admin' not in agents:
        debug_print('WARNING: admin agent not found — cannot register copilot tool handoffs')
        return

    admin = agents['admin']

    # Before bash/shell execution
    if 'executor_bash' in agents:
        agents['executor_bash'].agent.handoffs.add_llm_conditions([
            OnCondition(
                target=AgentTarget(admin.agent),
                condition=StringLLMCondition(
                    prompt=(
                        "About to execute a bash or shell command. "
                        "This includes any terminal commands, scripts, or system operations. "
                        "Must get human approval before executing."
                    )
                )
            )
        ])
        debug_print('executor_bash → admin (before bash execution)', indent=2)

    # Before code execution via engineer
    if 'engineer' in agents:
        agents['engineer'].agent.handoffs.add_llm_conditions([
            OnCondition(
                target=AgentTarget(admin.agent),
                condition=StringLLMCondition(
                    prompt=(
                        "About to execute code, write to files, or run programs. "
                        "This includes Python scripts, file creation/modification, "
                        "and any operation that changes the filesystem. "
                        "Must get human approval before proceeding."
                    )
                )
            )
        ])
        debug_print('engineer → admin (before code/file operations)', indent=2)

    # Before package installation
    if 'installer' in agents:
        agents['installer'].agent.handoffs.add_llm_conditions([
            OnCondition(
                target=AgentTarget(admin.agent),
                condition=StringLLMCondition(
                    prompt=(
                        "About to install packages, dependencies, or modify the system environment. "
                        "This includes pip install, npm install, apt-get, and similar operations. "
                        "Must get human approval before installing."
                    )
                )
            )
        ])
        debug_print('installer → admin (before package installation)', indent=2)

    # Before executor runs code
    if 'executor' in agents:
        agents['executor'].agent.handoffs.add_llm_conditions([
            OnCondition(
                target=AgentTarget(admin.agent),
                condition=StringLLMCondition(
                    prompt=(
                        "About to execute code or run a program. "
                        "Must get human approval before executing."
                    )
                )
            )
        ])
        debug_print('executor → admin (before code execution)', indent=2)

    debug_print('Copilot tool approval handoffs configured\n', indent=2)
