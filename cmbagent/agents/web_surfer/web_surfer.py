import os
import logging
import structlog
from cmbagent.base_agent import BaseAgent
from autogen.agentchat.contrib.web_surfer import WebSurferAgent as AG2WebSurfer

logger = structlog.get_logger(__name__)

class WebSurferAgent(BaseAgent):
    """
    WebSurfer agent that can browse web pages and extract information.
    Uses AG2's built-in WebSurferAgent capabilities.
    """

    def __init__(self, llm_config=None, **kwargs):
        agent_id = os.path.splitext(os.path.abspath(__file__))[0]
        super().__init__(llm_config=llm_config, agent_id=agent_id, **kwargs)

    def set_agent(self, **kwargs):
        """
        Sets up WebSurferAgent with browsing capabilities.
        """
        # Use AG2's WebSurferAgent which has built-in web browsing
        try:
            self.agent = AG2WebSurfer(
                name=self.name,
                llm_config=self.llm_config,
                **kwargs
            )
            logger.info("web_surfer_agent_created: %s", self.name)
        except Exception as e:
            logger.warning("web_surfer_agent_fallback: %s error=%s", self.name, e)
            # Make sure we have instructions in self.info for fallback
            if 'instructions' not in self.info:
                self.info['instructions'] = self.system_message
            # Fallback to regular assistant if WebSurfer fails
            super().set_assistant_agent(**kwargs)
