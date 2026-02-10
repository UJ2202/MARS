# cmbagent/utils.py
import os
import autogen
import pickle
import logging
from ruamel.yaml import YAML
from .cmbagent_utils import cmbagent_debug
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')



# Get the path of the current file
path_to_basedir = os.path.dirname(os.path.abspath(__file__))
if cmbagent_debug:
    print('path_to_basedir: ', path_to_basedir)

# Construct the path to the APIs directory
path_to_apis = os.path.join(path_to_basedir, "apis")
if cmbagent_debug:
    print('path_to_apis: ', path_to_apis)

# Construct the path to the assistants directory
path_to_assistants = os.path.join(path_to_basedir, "agents/rag_agents/")
if cmbagent_debug:
    print('path_to_assistants: ', path_to_assistants)
path_to_agents = os.path.join(path_to_basedir, "agents/")

# Always use current working directory
work_dir_default = os.path.join(os.getcwd(), "cmbagent_workdir")

# Keep as string, don't convert to Path to avoid symlink resolution and / operator issues
work_dir_default = os.path.abspath(os.path.expanduser(work_dir_default))

if cmbagent_debug:
    print('\n\n\n\n\nwork_dir_default: ', work_dir_default)


default_chunking_strategy = {
    "type": "static",
    "static": {
        "max_chunk_size_tokens": 200, # reduce size to ensure better context integrity
        "chunk_overlap_tokens": 100 # increase overlap to maintain context across chunks
    }
}

# notes from https://platform.openai.com/docs/assistants/tools/file-search:

# max_chunk_size_tokens must be between 100 and 4096 inclusive.
# chunk_overlap_tokens must be non-negative and should not exceed max_chunk_size_tokens / 2.

# By default, the file_search tool outputs up to 20 chunks for gpt-4* models and up to 5 chunks for gpt-3.5-turbo. 
# You can adjust this by setting file_search.max_num_results in the tool when creating the assistant or the run.

default_top_p = 0.05
default_temperature = 0.00001


default_select_speaker_prompt_template = """
Read the above conversation. Then select the next role from {agentlist} to play. Only return the role.
Note that only planner can modify or update the PLAN. planner should not be selected after the PLAN has been approved.
executor should not be selected unless admin says "execute".
engineer should be selected to check for conflicts. 
engineer should be selected to check code. 
engineer should be selected to provide code to save summary of session. 
executor should be selected to execute. 
planner should be the first agent to speak. 
"""
### note that we hardcoded the requirement that planner speaks first. 


default_select_speaker_message_template = """
You are in a role play game about cosmological data analysis. The following roles are available:
                {roles}.
                Read the following conversation.
                Then select the next role from {agentlist} to play. Only return the role.
Note that only planner can modify or update the PLAN.
planner should not be selected after the PLAN has been approved.
executor should not be selected unless admin says "execute".
engineer should be selected to check for conflicts. 
engineer should be selected to check code. 
executor should be selected to execute. 
planner should be the first agent to speak.
"""


default_groupchat_intro_message = """
We have assembled a team of LLM agents and a human admin to solve Cosmological data analysis tasks. 

In attendance are:
"""

# TODO
# see https://github.com/openai/openai-python/blob/da48e4cac78d1d4ac749e2aa5cfd619fde1e6c68/src/openai/types/beta/file_search_tool.py#L20
# default_file_search_max_num_results = 20
# The default is 20 for `gpt-4*` models and 5 for `gpt-3.5-turbo`. This number
# should be between 1 and 50 inclusive.
from .cmbagent_utils import file_search_max_num_results

default_max_round = 50

default_llm_model = 'gpt-4.1-2025-04-14'
default_formatter_model = 'o3-mini-2025-01-31'


# Core agents - general purpose, always available
CORE_AGENTS = {
    "engineer": "gpt-4.1-2025-04-14",
    "researcher": "gpt-4.1-2025-04-14",
    "planner": "gpt-4.1-2025-04-14",
    "plan_reviewer": "o3-mini-2025-01-31",
    "web_surfer": "gpt-4.1-2025-04-14",
    "retrieve_assistant": "gpt-4.1-2025-04-14",
}

# Domain-specific agents - cosmology/science focused
DOMAIN_AGENTS = {
    "idea_hater": "o3-mini-2025-01-31",
    "idea_maker": "gpt-4.1-2025-04-14",
    "plot_judge": "o3-mini-2025-01-31",
    "plot_debugger": "gpt-4o-2024-11-20",
    "aas_keyword_finder": "o3-mini-2025-01-31",
    "task_improver": "o3-mini-2025-01-31",
    "task_recorder": "gpt-4o-2024-11-20",
    "perplexity": "o3-mini-2025-01-31",
    # RAG agents
    "classy_sz": "gpt-4o-2024-11-20",
    "camb": "gpt-4o-2024-11-20",
    "classy": "gpt-4o-2024-11-20",
    "cobaya": "gpt-4o-2024-11-20",
    "planck": "gpt-4o-2024-11-20",
    "camb_context": "gpt-4.1-2025-04-14",
}


def get_agents_by_type(include_domain: bool = True) -> dict:
    """Get agent model configs by type.

    Args:
        include_domain: If True, include domain-specific agents.
                       If False, return only core agents.

    Returns:
        Dictionary of agent name -> model name
    """
    if include_domain:
        return {**CORE_AGENTS, **DOMAIN_AGENTS}
    return CORE_AGENTS.copy()


# Full agent list (backward compatible)

default_agents_llm_model ={
    "engineer": "gpt-4.1-2025-04-14",
    "aas_keyword_finder": "o3-mini-2025-01-31",
    "task_improver": "o3-mini-2025-01-31",
    "task_recorder": "gpt-4o-2024-11-20",
    "researcher": "gpt-4.1-2025-04-14",
    "web_surfer": "gpt-4.1-2025-04-14",
    "retrieve_assistant": "gpt-4.1-2025-04-14",
    "perplexity": "o3-mini-2025-01-31",
    "planner": "gpt-4.1-2025-04-14",
    "plan_reviewer": "o3-mini-2025-01-31",
    "idea_hater":  "o3-mini-2025-01-31",
    "idea_maker": "gpt-4.1-2025-04-14",
    "plot_judge": "o3-mini-2025-01-31",

    # rag agents
    "classy_sz": "gpt-4o-2024-11-20",
    "camb": "gpt-4o-2024-11-20",
    "classy": "gpt-4o-2024-11-20",
    "cobaya": "gpt-4o-2024-11-20",
    "planck": "gpt-4o-2024-11-20",

    "camb_context": "gpt-4.1-2025-04-14",

    'plot_debugger': 'gpt-4o-2024-11-20',

    # Summarizer agents
    'summarizer': default_llm_model,
    'summarizer_response_formatter': default_formatter_model,
}

default_agent_llm_configs = {}

def get_api_keys_from_env():
    api_keys = {
        "OPENAI" : os.getenv("OPENAI_API_KEY"),
        "GEMINI" : os.getenv("GEMINI_API_KEY"),
        "ANTHROPIC" : os.getenv("ANTHROPIC_API_KEY"),
        "MISTRAL" : os.getenv("MISTRAL_API_KEY"),
    }
    return api_keys

def get_model_config(model, api_keys):
    config = {
        "model": model,
        "api_key": None,
        "api_type": None
    }
    
    if 'o3' in model:
        config.update({
            "reasoning_effort": "medium",
            "api_key": api_keys["OPENAI"],
            "api_type": "openai"
        })
    elif "gemini" in model:
        config.update({
            "api_key": api_keys["GEMINI"],
            "api_type": "google"
        })
    elif "claude" in model:
        config.update({
            "api_key": api_keys["ANTHROPIC"],
            "api_type": "anthropic"
        })
    else:
        config.update({
            "api_key": api_keys["OPENAI"],
            "api_type": "openai"
        })
    return config

api_keys_env = get_api_keys_from_env()

for agent in default_agents_llm_model:
    default_agent_llm_configs[agent] =  get_model_config(default_agents_llm_model[agent], api_keys_env)


default_llm_config_list = [get_model_config(default_llm_model, api_keys_env)]


def update_yaml_preserving_format(yaml_file, agent_name, new_id, field = 'vector_store_ids'):
    yaml = YAML()
    yaml.preserve_quotes = True  # This preserves quotes in the YAML file if they are present

    # Load the YAML file while preserving formatting
    with open(yaml_file, 'r') as file:
        yaml_content = yaml.load(file)
    
    # Update the vector_store_id for the specific agent
    if yaml_content['name'] == agent_name:
        if field == 'vector_store_ids':
            yaml_content['assistant_config']['tool_resources']['file_search']['vector_store_ids'][0] = new_id
        elif field == 'assistant_id':
            yaml_content['assistant_config']['assistant_id'] = new_id
    else:
        print(f"Agent {agent_name} not found.")
    
    # Write the changes back to the YAML file while preserving formatting
    with open(yaml_file, 'w') as file:
        yaml.dump(yaml_content, file)

with open(path_to_basedir + '/keywords/aas_kwd_to_url.pkl', 'rb') as file:
    AAS_keywords_dict = pickle.load(file)

AAS_keywords_string = ', '.join(AAS_keywords_dict.keys())

unesco_taxonomy_path = path_to_basedir + '/keywords/unesco_hierarchical.json'
aaai_keywords_path = path_to_basedir + '/keywords/aaai.md'

camb_context_url = "https://camb.readthedocs.io/en/latest/_static/camb_docs_combined.md"
classy_context_url = "https://github.com/santiagocasas/clapp/tree/main/classy_docs.md"



def clean_llm_config(llm_config):
    if "reasoning_effort" in llm_config['config_list'][0]:
        if 'temperature' in llm_config:
            llm_config.pop('temperature')
        if 'top_p' in llm_config:
            llm_config.pop('top_p')


    # Pop temperature if using GPT-5 model
    if 'gpt-5' in llm_config['config_list'][0]['model']:
        if 'temperature' in llm_config:
            llm_config.pop('temperature', None)
        if 'top_p' in llm_config:
            llm_config.pop('top_p', None)

    if llm_config['config_list'][0]['api_type'] == 'google':
        if 'top_p' in llm_config:
            llm_config.pop('top_p') 