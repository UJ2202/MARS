import os
from cmbagent.base_agent import BaseAgent


class CopilotControlAgent(BaseAgent):
    """
    Copilot Control Agent - Intelligent task routing and agent selection.

    This agent analyzes incoming tasks and makes dynamic decisions about:
    1. Route type: one_shot (simple), planned (complex), clarify (need more info)
    2. Primary agent selection based on task requirements
    3. Supporting agents for multi-step tasks
    4. Complexity estimation

    Uses structured output (CopilotRoutingDecision) for consistent responses.
    """

    def __init__(self, llm_config=None, **kwargs):
        agent_id = os.path.splitext(os.path.abspath(__file__))[0]
        super().__init__(llm_config=llm_config, agent_id=agent_id, **kwargs)

    def set_agent(self, **kwargs):
        super().set_assistant_agent(**kwargs)
