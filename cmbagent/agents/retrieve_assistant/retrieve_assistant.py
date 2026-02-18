import os
import logging
import structlog
from cmbagent.base_agent import BaseAgent
from autogen.agentchat.contrib.retrieve_assistant_agent import RetrieveAssistantAgent as AG2RetrieveAssistant

logger = structlog.get_logger(__name__)

class RetrieveAssistantAgent(BaseAgent):
    """
    Retrieve Assistant agent with RAG (Retrieval-Augmented Generation) capabilities.
    Uses AG2's built-in RetrieveAssistantAgent.
    """

    def __init__(self, llm_config=None, **kwargs):
        agent_id = os.path.splitext(os.path.abspath(__file__))[0]
        super().__init__(llm_config=llm_config, agent_id=agent_id, **kwargs)

    def set_agent(self, **kwargs):
        """
        Sets up RetrieveAssistantAgent with RAG capabilities.
        """
        # Use AG2's RetrieveAssistantAgent which has built-in RAG
        try:
            self.agent = AG2RetrieveAssistant(
                name=self.name,
                llm_config=self.llm_config,
                **kwargs
            )
            logger.info("retrieve_assistant_agent_created: %s", self.name)
        except Exception as e:
            logger.warning("retrieve_assistant_agent_fallback: %s error=%s", self.name, e)
            # Make sure we have instructions in self.info for fallback
            if 'instructions' not in self.info:
                self.info['instructions'] = self.system_message
            # Fallback to regular assistant if RetrieveAssistant fails
            super().set_assistant_agent(**kwargs)
