"""
OpenAI Assistant management for CMBAgent.

This module provides functionality for creating and managing OpenAI Assistants
for RAG agents.
"""

from typing import List, Dict, Any, Optional
from openai import OpenAI

from cmbagent.utils import path_to_assistants, update_yaml_preserving_format
from cmbagent.cmbagent_utils import cmbagent_debug


class AssistantManager:
    """
    Manages OpenAI Assistants for RAG agents.

    This class handles:
    - Creating assistants via OpenAI API
    - Checking assistant existence
    - Updating assistant configurations
    - Managing vector store associations
    - Model synchronization
    """

    def __init__(self, openai_api_key: str, llm_config: Dict[str, Any]):
        """
        Initialize the AssistantManager.

        Args:
            openai_api_key: OpenAI API key
            llm_config: LLM configuration dictionary
        """
        self.openai_api_key = openai_api_key
        self.llm_config = llm_config
        self.client = OpenAI(api_key=openai_api_key)

    def create_assistant(self, agent: Any) -> Any:
        """
        Create an OpenAI assistant for an agent.

        Args:
            agent: Agent instance to create assistant for

        Returns:
            New assistant object from OpenAI
        """
        if cmbagent_debug:
            print(f"-->Creating assistant {agent.name}")
            print(f"--> llm_config: {self.llm_config}")
            print(f"--> agent.llm_config: {agent.llm_config}")

        new_assistant = self.client.beta.assistants.create(
            name=agent.name,
            instructions=agent.info['instructions'],
            tools=[{"type": "file_search"}],
            tool_resources={"file_search": {"vector_store_ids": []}},
            model=agent.llm_config['config_list'][0]['model'],
        )

        if cmbagent_debug:
            print("New assistant created.")
            print(f"--> New assistant id: {new_assistant.id}")
            print(f"--> New assistant model: {new_assistant.model}")
            print("\n")

        return new_assistant

    def check_assistants(
        self,
        agents: List[Any],
        non_rag_agent_names: List[str],
        reset_assistant: Optional[List[str]] = None
    ) -> None:
        """
        Check and create/update assistants for agents.

        Args:
            agents: List of agent instances
            non_rag_agent_names: List of non-RAG agent names (to skip)
            reset_assistant: Optional list of agent names to reset
        """
        if reset_assistant is None:
            reset_assistant = []

        available_assistants = self.client.beta.assistants.list(
            order="desc",
            limit="100",
        )

        # Create lists for easy comparison
        assistant_names = [d.name for d in available_assistants.data]
        assistant_ids = [d.id for d in available_assistants.data]
        assistant_models = [d.model for d in available_assistants.data]

        for agent in agents:
            if cmbagent_debug:
                print('check_assistants: agent: ', agent.name)
                print('non_rag_agent_names: ', non_rag_agent_names)

            # Skip non-RAG agents
            if agent.name in non_rag_agent_names:
                continue

            if cmbagent_debug:
                print(f"Checking agent: {agent.name}")

            # Check if agent name exists in available assistants
            if agent.name in assistant_names:
                idx = assistant_names.index(agent.name)

                if cmbagent_debug:
                    print(f"Agent {agent.name} exists with id: {assistant_ids[idx]}")
                    print(f"assistant model from openai: {assistant_models[idx]}")
                    print(f"assistant model from llm_config: {agent.llm_config['config_list'][0]['model']}")

                # Update model if different
                if assistant_models[idx] != agent.llm_config['config_list'][0]['model']:
                    if cmbagent_debug:
                        print("Assistant model mismatch. Updating.")
                    self.client.beta.assistants.update(
                        assistant_id=assistant_ids[idx],
                        model=agent.llm_config['config_list'][0]['model']
                    )

                # Handle reset
                if reset_assistant and agent.name.replace('_agent', '') in reset_assistant:
                    print("Resetting assistant...")
                    print("Deleting the assistant...")
                    self.client.beta.assistants.delete(assistant_ids[idx])
                    print("Assistant deleted. Creating a new one...")
                    new_assistant = self.create_assistant(agent)
                    agent.info['assistant_config']['assistant_id'] = new_assistant.id
                else:
                    # Sync assistant ID
                    assistant_id = agent.info['assistant_config']['assistant_id']
                    if assistant_id != assistant_ids[idx]:
                        if cmbagent_debug:
                            print("--> Assistant ID mismatch between yaml and openai.")
                            print(f"--> yaml: {assistant_id}")
                            print(f"--> openai: {assistant_ids[idx]}")
                            print("--> Using openai ID")

                        agent.info['assistant_config']['assistant_id'] = assistant_ids[idx]
                        if cmbagent_debug:
                            print(f"--> Updating yaml file with new assistant id")
                        update_yaml_preserving_format(
                            f"{path_to_assistants}/{agent.name.replace('_agent', '')}.yaml",
                            agent.name,
                            assistant_ids[idx],
                            field='assistant_id'
                        )
            else:
                # Create new assistant
                new_assistant = self.create_assistant(agent)
                agent.info['assistant_config']['assistant_id'] = new_assistant.id

    def delete_assistant(self, assistant_id: str) -> None:
        """
        Delete an assistant.

        Args:
            assistant_id: ID of the assistant to delete
        """
        self.client.beta.assistants.delete(assistant_id)

    def update_assistant_model(self, assistant_id: str, model: str) -> None:
        """
        Update an assistant's model.

        Args:
            assistant_id: ID of the assistant to update
            model: New model name
        """
        self.client.beta.assistants.update(
            assistant_id=assistant_id,
            model=model
        )
