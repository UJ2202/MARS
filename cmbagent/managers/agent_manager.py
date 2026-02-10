"""
Agent management for CMBAgent.

This module provides agent initialization, lookup, and management functionality.
"""

import os
import sys
import copy
import importlib
from typing import List, Dict, Any, Optional, Type

from cmbagent.utils import path_to_agents, get_model_config, clean_llm_config
from cmbagent.utils import default_formatter_model as default_formatter_model_default
from cmbagent.rag_utils import import_rag_agents
from cmbagent.cmbagent_utils import cmbagent_debug


def import_non_rag_agents() -> Dict[str, Dict[str, Any]]:
    """
    Dynamically import all non-RAG agent classes from the agents directory.

    Returns:
        Dictionary mapping class names to agent info dictionaries containing
        'agent_class' and 'agent_name' keys.
    """
    imported_non_rag_agents = {}
    for subdir in os.listdir(path_to_agents):
        # Skip rag_agents folder and non-directories
        if subdir == "rag_agents":
            continue
        subdir_path = os.path.join(path_to_agents, subdir)
        if os.path.isdir(subdir_path):
            for filename in os.listdir(subdir_path):
                # Skip __init__.py, hidden files (.), and private files (_)
                if filename.endswith(".py") and filename != "__init__.py" and filename[0] not in (".", "_"):
                    module_name = filename[:-3]  # Remove the .py extension
                    class_name = ''.join([part.capitalize() for part in module_name.split('_')]) + 'Agent'
                    # Assuming the module path is agents.<subdir>.<module_name>
                    module_path = f"cmbagent.agents.{subdir}.{module_name}"
                    module = importlib.import_module(module_path)
                    agent_class = getattr(module, class_name)
                    imported_non_rag_agents[class_name] = {
                        'agent_class': agent_class,
                        'agent_name': module_name,
                    }
    return imported_non_rag_agents


class AgentManager:
    """
    Manages agent initialization, lookup, and configuration.

    This class handles:
    - Loading RAG and non-RAG agents
    - Agent instantiation and configuration
    - Model configuration assignment
    - Agent filtering based on skip flags
    """

    def __init__(
        self,
        llm_config: Dict[str, Any],
        work_dir: str,
        agent_type: str,
        api_keys: Dict[str, str],
        agent_list: Optional[List[str]] = None,
        skip_memory: bool = True,
        skip_executor: bool = True,
        skip_rag_software_formatter: bool = True,
        skip_rag_agents: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize the AgentManager.

        Args:
            llm_config: LLM configuration dictionary
            work_dir: Working directory for agents
            agent_type: Type of agents ('oai' or 'assistants')
            api_keys: API keys dictionary
            agent_list: List of agents to use (None for all)
            skip_memory: Skip memory agent
            skip_executor: Skip executor agent
            skip_rag_software_formatter: Skip RAG software formatter
            skip_rag_agents: Skip all RAG agents
            verbose: Enable verbose output
        """
        self.llm_config = llm_config
        self.work_dir = work_dir
        self.agent_type = agent_type
        self.api_keys = api_keys
        self.agent_list = agent_list
        self.skip_memory = skip_memory
        self.skip_executor = skip_executor
        self.skip_rag_software_formatter = skip_rag_software_formatter
        self.skip_rag_agents = skip_rag_agents
        self.verbose = verbose

        # These will be populated during init_agents
        self.agents: List[Any] = []
        self.agent_classes: Dict[str, Type] = {}
        self.agent_names: List[str] = []
        self.rag_agent_names: List[str] = []
        self.non_rag_agent_names: List[str] = []

    def init_agents(
        self,
        agent_llm_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        default_formatter_model: str = default_formatter_model_default
    ) -> List[Any]:
        """
        Initialize all agents.

        Args:
            agent_llm_configs: Custom LLM configs for specific agents
            default_formatter_model: Default model for formatter agents

        Returns:
            List of initialized agent instances
        """
        if agent_llm_configs is None:
            agent_llm_configs = {}

        # Load all agent classes
        imported_rag_agents = import_rag_agents()
        imported_non_rag_agents = import_non_rag_agents()

        # Store classes for each agent
        self.agent_classes = {}
        self.rag_agent_names = []
        self.non_rag_agent_names = []

        for k in imported_rag_agents.keys():
            self.agent_classes[imported_rag_agents[k]['agent_name']] = imported_rag_agents[k]['agent_class']
            self.rag_agent_names.append(imported_rag_agents[k]['agent_name'])

        for k in imported_non_rag_agents.keys():
            self.agent_classes[imported_non_rag_agents[k]['agent_name']] = imported_non_rag_agents[k]['agent_class']
            self.non_rag_agent_names.append(imported_non_rag_agents[k]['agent_name'])

        if cmbagent_debug:
            print('self.agent_classes: ', self.agent_classes)
            print('self.rag_agent_names: ', self.rag_agent_names)
            print('self.non_rag_agent_names: ', self.non_rag_agent_names)

        # All agents list
        self.agents = []

        if self.agent_list is None:
            self.agent_list = list(self.agent_classes.keys())

        # Filter agent classes based on agent_list
        self.agent_classes = {
            k: v for k, v in self.agent_classes.items()
            if k in self.agent_list or k in self.non_rag_agent_names
        }

        # Remove skipped agents
        if self.skip_memory:
            self.agent_classes.pop('session_summarizer', None)

        if self.skip_executor:
            self.agent_classes.pop('executor', None)

        if self.skip_rag_software_formatter:
            self.agent_classes.pop('rag_software_formatter', None)

        if cmbagent_debug:
            print('self.agent_classes after skipping agents:')
            for agent_class, value in self.agent_classes.items():
                print(f'{agent_class}: {value}')

        # Instantiate agents
        for agent_name in self.agent_classes:
            agent_class = self.agent_classes[agent_name]

            if cmbagent_debug:
                print('instantiating agent: ', agent_name)

            if agent_name in agent_llm_configs:
                llm_config = copy.deepcopy(self.llm_config)
                llm_config['config_list'][0].update(agent_llm_configs[agent_name])
                clean_llm_config(llm_config)

                if cmbagent_debug:
                    print('found agent_llm_configs for: ', agent_name)
                    print('llm_config updated to: ', llm_config)
            else:
                llm_config = copy.deepcopy(self.llm_config)

            agent_instance = agent_class(
                llm_config=llm_config,
                agent_type=self.agent_type,
                work_dir=self.work_dir
            )

            self.agents.append(agent_instance)

        # Remove RAG agents if skip_rag_agents is True
        if self.skip_rag_agents:
            self.agents = [
                agent for agent in self.agents
                if agent.name.replace('_agent', '') not in self.rag_agent_names
            ]

        self.agent_names = [agent.name for agent in self.agents]

        # Update formatter agents with default formatter model
        for agent in self.agents:
            if "formatter" in agent.name:
                agent.llm_config['config_list'][0].update(
                    get_model_config(default_formatter_model, self.api_keys)
                )
            # Clean LLM config
            clean_llm_config(agent.llm_config)

        if self.verbose or cmbagent_debug:
            print("Using following agents: ", self.agent_names)
            print("Using following llm for agents: ")
            for agent in self.agents:
                print(f"{agent.name}: {agent.llm_config['config_list'][0]['model']}")
            print()

        return self.agents

    def get_agent_from_name(self, name: str) -> Any:
        """
        Get an AG2 agent by name.

        Args:
            name: Name of the agent

        Returns:
            The AG2 agent object
        """
        for agent in self.agents:
            if agent.info['name'] == name:
                return agent.agent
        print(f"get_agent_from_name: agent {name} not found")
        sys.exit()

    def get_agent_object_from_name(self, name: str) -> Any:
        """
        Get the CMBAgent wrapper object by name.

        Args:
            name: Name of the agent

        Returns:
            The agent wrapper object
        """
        for agent in self.agents:
            if agent.info['name'] == name:
                return agent
        print(f"get_agent_object_from_name: agent {name} not found")
        sys.exit()

    def filter_and_combine_agent_names(self, input_list: List[str]) -> str:
        """
        Filter input list to include only entries in agent_names and combine to string.

        Args:
            input_list: List of agent names to filter

        Returns:
            Comma-separated string of filtered agent names
        """
        filtered_list = [item for item in input_list if item in self.agent_names]
        return ', '.join(filtered_list)
