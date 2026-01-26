import os
import logging
import importlib
import requests
import autogen
import json
import sys
import pandas as pd
import copy
import datetime
from pathlib import Path
import time
import pickle
from collections import defaultdict
from openai import OpenAI
from typing import List, Dict, Any, Optional
import glob
from IPython.display import Image
from autogen.agentchat.group import ContextVariables
from autogen.agentchat.group.patterns import AutoPattern

from .callbacks import WorkflowCallbacks, StepInfo, PlanInfo, StepStatus, create_null_callbacks
from .agents.planner_response_formatter.planner_response_formatter import save_final_plan
from .utils import work_dir_default
from .utils import default_llm_model as default_llm_model_default
from .utils import default_formatter_model as default_formatter_model_default
from .utils import clean_llm_config

from .utils import (path_to_assistants, path_to_apis,path_to_agents, update_yaml_preserving_format, get_model_config,
                    default_top_p, default_temperature, default_max_round,default_llm_config_list, default_agent_llm_configs,
                    default_agents_llm_model, camb_context_url,classy_context_url, AAS_keywords_string, get_api_keys_from_env)

from .rag_utils import import_rag_agents, push_vector_stores
from .hand_offs import register_all_hand_offs
from .functions import register_functions_to_agents
from .data_retriever import setup_cmbagent_data

from .keywords_utils import UnescoKeywords
from .keywords_utils import AaaiKeywords
from .utils import unesco_taxonomy_path, aaai_keywords_path

# Import from managers module for backward compatibility
from cmbagent.managers.agent_manager import import_non_rag_agents

from .cmbagent_utils import cmbagent_debug
from autogen.agentchat import initiate_group_chat
from cmbagent.context import shared_context as shared_context_default
import shutil

class CMBAgent:

    logging.disable(logging.CRITICAL)

    def __init__(self,
                 cache_seed=None,
                 temperature=default_temperature,
                 top_p=default_top_p,
                 timeout=1200,
                 max_round=default_max_round,
                 platform='oai',
                 model='gpt4o',
                 llm_api_key=None,
                 llm_api_type=None,
                 make_vector_stores=False, #set to True to update all vector_stores, or a list of agents to update only those vector_stores e.g., make_vector_stores= ['cobaya', 'camb'].
                 agent_list = ['camb','classy_sz','cobaya','planck'],
                 verbose = False,
                 reset_assistant = False,
                 agent_instructions = {
                        "executor":
                        """
                        You execute python code provided to you by the engineer or save content provided by the researcher.
                        """,      
                    },
                 agent_descriptions = None,
                 agent_temperature = None,
                 agent_top_p = None,
                #  vector_store_ids = None,
                 chunking_strategy = {
                    'camb_agent': 
                    {
                    "type": "static",
                    "static": {
                      "max_chunk_size_tokens": 800, # reduce size to ensure better context integrity
                      "chunk_overlap_tokens": 200 # increase overlap to maintain context across chunks
                    }
                }
                },
                 select_speaker_prompt = None,
                 select_speaker_message = None,
                 intro_message = None,
                 set_allowed_transitions = None,
                 skip_executor = False,
                 skip_memory = True,
                 skip_rag_software_formatter = True,
                 skip_rag_agents = True,
                 default_llm_model = default_llm_model_default,
                 default_formatter_model = default_formatter_model_default,
                 default_llm_config_list = default_llm_config_list,
                 agent_llm_configs = default_agent_llm_configs,
                 agent_type = 'swarm',# None,# 'swarm',
                 shared_context = shared_context_default,
                 work_dir = work_dir_default,
                 clear_work_dir = True,
                 mode = "planning_and_control", # can be "one_shot" , "chat" or "planning_and_control" (default is planning and control), or "planning_and_control_context_carryover"
                 chat_agent = None,
                 api_keys = None,
                 approval_config = None,  # Optional ApprovalConfig for HITL control
                 enable_ag2_free_tools = True,  # Enable AG2 free tools by default (LangChain + CrewAI)
                 enable_mcp_client = False,  # Enable MCP client for external MCP servers (GitHub, filesystem, etc.)
                #  make_new_rag_agents = False, ## can be a list of names for new rag agents to be created
                 **kwargs):
        """
        Initialize the CMBAgent.

        Args:
            cache_seed (int, optional): Seed for caching. Defaults to 42.
            temperature (float, optional): Temperature for LLM sampling. Defaults to 0.
            timeout (int, optional): Timeout for LLM requests in seconds. Defaults to 1200.
            max_round (int, optional): Maximum number of conversation rounds. Defaults to 50. If too small, the conversation stops.
            llm_api_key (str, optional): API key for LLM. If None, uses the key from the config file.
            make_vector_stores (bool or list of strings, optional): Whether to create vector stores. Defaults to False. For only subset, use, e.g., make_vector_stores= ['cobaya', 'camb'].
            agent_list (list of strings, optional): List of agents to include in the conversation. Defaults to all agents.
            chunking_strategy (dict, optional): Chunking strategy for vector stores. Defaults to None.
            make_new_rag_agents (list of strings, optional): List of names for new rag agents to be created. Defaults to False.
            enable_ag2_free_tools (bool, optional): Enable AG2 free tools from LangChain and CrewAI. Defaults to True.
            
            **kwargs: Additional keyword arguments.

        Attributes:
            kwargs (dict): Additional keyword arguments.
            work_dir (str): Working directory for output.
            path_to_assistants (str): Path to the assistants directory.
            llm_api_key (str): OpenAI API key.
            engineer (engineer_agent): Agent for engineering tasks.
            planner (planner_agent): Agent for planning tasks.
            executor (executor_agent): Agent for executing tasks.

        Note:
            This class initializes various agents and configurations for cosmological data analysis.
        """
        if default_llm_model != default_llm_model_default:

            default_llm_config_list = [get_model_config(default_llm_model, api_keys)]

        self.kwargs = kwargs
        
        self.enable_ag2_free_tools = enable_ag2_free_tools
        self.enable_mcp_client = enable_mcp_client

        self.skip_executor = skip_executor

        self.skip_rag_agents = skip_rag_agents

        if make_vector_stores is not False:
            self.skip_rag_agents = False

        self.skip_rag_software_formatter = skip_rag_software_formatter

        # self.make_new_rag_agents = make_new_rag_agents
        self.set_allowed_transitions = set_allowed_transitions

        self.vector_store_ids = None

        self.logger = logging.getLogger(__name__)

        # self.non_rag_agents = ['engineer', 'planner', 'executor', 'admin', 'summarizer', 'rag_software_formatter']

        self.agent_list = agent_list

        self.skip_memory = skip_memory

        self.results = {}

        self.mode = mode
        self.chat_agent = chat_agent

        # HITL approval configuration
        self.approval_config = approval_config
        if self.approval_config is None:
            from cmbagent.database.approval_types import ApprovalConfig, ApprovalMode
            self.approval_config = ApprovalConfig(mode=ApprovalMode.NONE)

        if not self.skip_memory and 'memory' not in agent_list:
            self.agent_list.append('memory')

        self.verbose = verbose



        if work_dir != work_dir_default:
            # delete work_dir_default as it wont be used
            # exception if we are working within work_dir_default, i.e., work_dir is a subdirectory of work_dir_default
            # Convert to Path objects for comparison if they are strings
            work_dir_default_path = Path(work_dir_default) if isinstance(work_dir_default, str) else work_dir_default
            work_dir_path = Path(work_dir) if isinstance(work_dir, str) else work_dir
            if not work_dir_default_path.resolve() in work_dir_path.resolve().parents:
                shutil.rmtree(work_dir_default, ignore_errors=True)
            # shutil.rmtree(work_dir_default, ignore_errors=True)

        # Always store work_dir as absolute string path (without resolving symlinks)
        if isinstance(work_dir, str):
            self.work_dir = os.path.abspath(os.path.expanduser(work_dir))
        else:
            # Convert Path to string using abspath to avoid resolving symlinks
            self.work_dir = os.path.abspath(os.path.expanduser(str(work_dir)))
        self.clear_work_dir_bool = clear_work_dir
        if clear_work_dir:
            self.clear_work_dir()

        # add the work_dir to the python path so we can import modules from it
        sys.path.append(self.work_dir)

        # Database initialization (optional, controlled by environment variable)
        self.use_database = os.getenv("CMBAGENT_USE_DATABASE", "true").lower() == "true"
        self.db_session: Optional[Any] = None
        self.session_id: Optional[str] = None
        self.workflow_repo: Optional[Any] = None
        self.persistence: Optional[Any] = None
        self.dag_builder: Optional[Any] = None
        self.dag_executor: Optional[Any] = None
        self.dag_visualizer: Optional[Any] = None
        self.workflow_sm: Optional[Any] = None
        self.approval_manager: Optional[Any] = None
        self.retry_manager: Optional[Any] = None
        self.retry_metrics: Optional[Any] = None

        if self.use_database:
            try:
                from cmbagent.database import get_db_session, init_database
                from cmbagent.database.repository import WorkflowRepository
                from cmbagent.database.persistence import DualPersistenceManager
                from cmbagent.database.session_manager import SessionManager
                from cmbagent.database.dag_builder import DAGBuilder
                from cmbagent.database.dag_executor import DAGExecutor
                from cmbagent.database.dag_visualizer import DAGVisualizer
                from cmbagent.database.state_machine import StateMachine
                from cmbagent.database.approval_manager import ApprovalManager

                # Initialize database
                init_database()

                # Create database session
                self.db_session = get_db_session()

                # Get or create session
                session_manager = SessionManager(self.db_session)
                self.session_id = session_manager.get_or_create_default_session()

                # Create repositories
                self.workflow_repo = WorkflowRepository(self.db_session, self.session_id)

                # Create persistence manager
                self.persistence = DualPersistenceManager(
                    self.db_session,
                    self.session_id,
                    self.work_dir
                )

                # Create DAG components
                self.dag_builder = DAGBuilder(self.db_session, self.session_id)
                self.dag_executor = DAGExecutor(self.db_session, self.session_id)
                self.dag_visualizer = DAGVisualizer(self.db_session)
                self.workflow_sm = StateMachine(self.db_session, "workflow_run")

                # Create approval manager
                self.approval_manager = ApprovalManager(self.db_session, self.session_id)

                # Create retry context manager and metrics
                from cmbagent.retry.retry_context_manager import RetryContextManager
                from cmbagent.retry.retry_metrics import RetryMetrics
                self.retry_manager = RetryContextManager(self.db_session, self.session_id)
                self.retry_metrics = RetryMetrics(self.db_session)

                if cmbagent_debug:
                    print(f"Database initialized with session_id: {self.session_id}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize database: {e}. Continuing without database.")
                self.use_database = False
                self.db_session = None
                self.session_id = None
                self.workflow_repo = None
                self.persistence = None
                self.dag_builder = None
                self.dag_executor = None
                self.dag_visualizer = None
                self.workflow_sm = None
                self.approval_manager = None
                self.retry_manager = None
                self.retry_metrics = None

        # MCP Client initialization (optional, controlled by parameter)
        self.mcp_client_manager = None
        self.mcp_tool_integration = None
        if self.enable_mcp_client:
            try:
                from cmbagent.mcp import MCPClientManager, MCPToolIntegration
                import asyncio
                
                self.mcp_client_manager = MCPClientManager()
                # Connect to all enabled MCP servers asynchronously
                asyncio.run(self.mcp_client_manager.connect_all())
                
                # Create tool integration helper
                self.mcp_tool_integration = MCPToolIntegration(self.mcp_client_manager)
                
                connected_servers = len(self.mcp_client_manager.sessions)
                if cmbagent_debug or self.verbose:
                    print(f"MCP client initialized. Connected to {connected_servers} servers.")
                    
            except Exception as e:
                self.logger.warning(f"Failed to initialize MCP client: {e}. Continuing without MCP.")
                self.enable_mcp_client = False
                self.mcp_client_manager = None
                self.mcp_tool_integration = None

        self.path_to_assistants = path_to_assistants

        self.logger.info(f"Autogen version: {autogen.__version__}")

        llm_config_list = default_llm_config_list.copy()

        if llm_api_key is not None:
            llm_config_list[0]['api_key'] = llm_api_key

        if llm_api_type is not None:
            llm_config_list[0]['api_type'] = llm_api_type

        self.llm_api_key = llm_config_list[0]['api_key']
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        self.logger.info(f"Path to APIs: {path_to_apis}")

        self.cache_seed = cache_seed

        self.llm_config = {
                        "cache_seed": self.cache_seed,  # change the cache_seed for different trials
                        "temperature": temperature,
                        "top_p": top_p,
                        "config_list": llm_config_list,
                        "timeout": timeout,
                        "check_every_ms": None,
                    }
        
        if cmbagent_debug:
            print('\n\n\n\nin cmbagent.py self.llm_config: ',self.llm_config)

        # self.llm_config =  {"model": "gpt-4o-mini", "cache_seed": None}

        self.logger.info("LLM Configuration:")

        for key, value in self.llm_config.items():

            self.logger.info(f"{key}: {value}")

        self.agent_type = agent_type

        self.agent_llm_configs = default_agent_llm_configs.copy()
        self.agent_llm_configs.update(agent_llm_configs)

        if api_keys is not None:

            self.llm_config["config_list"][0] = get_model_config(self.llm_config["config_list"][0]["model"], api_keys)
            
            for agent in self.agent_llm_configs.keys():                
                self.agent_llm_configs[agent] = get_model_config(self.agent_llm_configs[agent]["model"], api_keys)


        self.api_keys = api_keys

        self.init_agents(agent_llm_configs=self.agent_llm_configs, default_formatter_model=default_formatter_model) # initialize agents

        if cmbagent_debug:
            print("\n\n All agents instantiated!!!\n\n")

        if cmbagent_debug:  
            print("\n\n Checking assistants...\n\n")

        if not self.skip_rag_agents:
            setup_cmbagent_data()

            self.check_assistants(reset_assistant=reset_assistant) # check if assistants exist

            if cmbagent_debug:
                print("\n\n Assistants checked!!!\n\n")

            if cmbagent_debug:
                print('\npushing vector stores...')
            push_vector_stores(self, make_vector_stores, chunking_strategy, verbose = verbose) # push vector stores

        if cmbagent_debug:
            print('\nsetting planner instructions currently not doing anything...')
            print('\nmodify if you want to tune the instruction prompt...')
        self.set_planner_instructions() # set planner instructions

        if self.verbose or cmbagent_debug:
            print("\nSetting up agents:----------------------------------")

        # then we set the agents, note that self.agents is set in init_agents
        for agent in self.agents:

            agent.agent_type = self.agent_type
            if cmbagent_debug:
                print(f"\t- {agent.name}")

            instructions = agent_instructions[agent.name] if agent_instructions and agent.name in agent_instructions else None
            description = agent_descriptions[agent.name] if agent_descriptions and agent.name in agent_descriptions else None
            agent_kwargs = {}

            if instructions is not None:
                agent_kwargs['instructions'] = instructions

            if description is not None:
                agent_kwargs['description'] = description
           

            if agent.name not in self.non_rag_agent_names: ## loop over all rag agents 
                if self.skip_rag_agents:
                    continue
                vector_ids = self.vector_store_ids[agent.name] if self.vector_store_ids and agent.name in self.vector_store_ids else None
                temperature = agent_temperature[agent.name] if agent_temperature and agent.name in agent_temperature else None
                top_p = agent_top_p[agent.name] if agent_top_p and agent.name in agent_top_p else None

                if vector_ids is not None:
                    agent_kwargs['vector_store_ids'] = vector_ids

                if temperature is not None:
                    agent_kwargs['agent_temperature'] = temperature
                else:
                    agent_kwargs['agent_temperature'] = default_temperature

                if top_p is not None:
                    agent_kwargs['agent_top_p'] = top_p
                else:
                    agent_kwargs['agent_top_p'] = default_top_p

                # cmbagent debug --> removed this option, pass in make_vector_stores=True in kwargs
                # #### the files list is appended twice to the instructions.... TBD!!!
                setagent = agent.set_agent(**agent_kwargs)

                if setagent == 1:

                    if cmbagent_debug:
                        print(f"setting make_vector_stores=['{agent.name.removesuffix('_agent')}'],")
                    
                    push_vector_stores(self, [agent.name.removesuffix('_agent')], chunking_strategy, verbose = verbose)

                    agent_kwargs['vector_store_ids'] = self.vector_store_ids[agent.name] 

                    
                    agent.set_agent(**agent_kwargs) 

                # else:
                # see above for trick on how to make vector store if it is not found. 
                # agent.set_agent(**agent_kwargs)

            else: ## set all non-rag agents
                
                agent.set_agent(**agent_kwargs)

            ## debug print to help debug
            #print('in cmbagent.py self.agents instructions: ',instructions)
            #print('in cmbagent.py self.agents description: ',description)

        if self.verbose or cmbagent_debug:
            print("Planner instructions:")
            print("\nAll agents:")
            for agent in self.agents:
                print("\n\n----------------------------------")
                print(f"- {agent.name}")
                print(dir(agent))
                print("\n\n----------------------------------")
            print()
            planner = self.get_agent_object_from_name('planner')
            print(planner.info['instructions'])

        if cmbagent_debug:
            print('\nregistering all hand_offs...')

        register_all_hand_offs(self)

        if cmbagent_debug:
            print('\nall hand_offs registered...')


        if cmbagent_debug:
            print('\nadding functions to agents...')

        register_functions_to_agents(self)

        if cmbagent_debug:
            print('\nfunctions added to agents...')

        self.shared_context = shared_context_default
        if shared_context is not None:
            self.shared_context.update(shared_context)

        if cmbagent_debug:
            print('\nshared_context: ', self.shared_context)

    def display_cost(self, name_append = None):
        """Display a full cost report as a right‑aligned Markdown table with $ and a
        rule above the total row. Also saves the cost data as JSON in the workdir."""
        import json

        cost_dict = defaultdict(list)

        # --- collect per‑agent costs ------------------------------------------------
        all_agents = [a.agent for a in self.agents]
        if hasattr(self, "groupchat"):
            all_agents += self.groupchat.new_conversable_agents

        for agent in all_agents:
            # First try the custom cost_dict (used by vlm_utils)
            if hasattr(agent, "cost_dict") and agent.cost_dict.get("Agent"):
                name = (
                    agent.cost_dict["Agent"][0]
                    .replace("admin (", "")
                    .replace(")", "")
                    .replace("_", " ")
                )
                summed_cost   = round(sum(agent.cost_dict["Cost"]), 8)
                summed_prompt = int(sum(agent.cost_dict["Prompt Tokens"]))
                summed_comp   = int(sum(agent.cost_dict["Completion Tokens"]))
                summed_total  = int(sum(agent.cost_dict["Total Tokens"]))

                model_name = agent.cost_dict["Model"][0]
                

                if name in cost_dict["Agent"]:
                    i = cost_dict["Agent"].index(name)
                    cost_dict["Cost ($)"][i]          += summed_cost
                    cost_dict["Prompt Tokens"][i]     += summed_prompt
                    cost_dict["Completion Tokens"][i] += summed_comp
                    cost_dict["Total Tokens"][i]      += summed_total
                    cost_dict["Model"][i]             += model_name
                else:
                    cost_dict["Agent"].append(name)
                    cost_dict["Cost ($)"].append(summed_cost)
                    cost_dict["Prompt Tokens"].append(summed_prompt)
                    cost_dict["Completion Tokens"].append(summed_comp)
                    cost_dict["Total Tokens"].append(summed_total)
                    cost_dict["Model"].append(model_name)
            # Also try AG2's native usage tracking via client
            elif hasattr(agent, "client") and agent.client is not None:
                try:
                    usage_summary = getattr(agent.client, "total_usage_summary", None)
                    if usage_summary:
                        agent_name = getattr(agent, "name", "unknown")
                        for model_name, model_usage in usage_summary.items():
                            if isinstance(model_usage, dict):
                                prompt_tokens = model_usage.get("prompt_tokens", 0)
                                completion_tokens = model_usage.get("completion_tokens", 0)
                                total_tokens = prompt_tokens + completion_tokens
                                # Estimate cost based on model (rough pricing)
                                pricing = {
                                    "gpt-4o": {"input": 2.50, "output": 10.00},
                                    "gpt-4": {"input": 30.00, "output": 60.00},
                                    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
                                    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
                                    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
                                }
                                # Default pricing if model not found
                                model_key = next((k for k in pricing if k in model_name.lower()), None)
                                if model_key:
                                    input_cost = (prompt_tokens / 1_000_000) * pricing[model_key]["input"]
                                    output_cost = (completion_tokens / 1_000_000) * pricing[model_key]["output"]
                                    cost = input_cost + output_cost
                                else:
                                    cost = (total_tokens / 1_000_000) * 5.0  # Default $5/M tokens

                                if agent_name in cost_dict["Agent"]:
                                    i = cost_dict["Agent"].index(agent_name)
                                    cost_dict["Cost ($)"][i] += cost
                                    cost_dict["Prompt Tokens"][i] += prompt_tokens
                                    cost_dict["Completion Tokens"][i] += completion_tokens
                                    cost_dict["Total Tokens"][i] += total_tokens
                                else:
                                    cost_dict["Agent"].append(agent_name)
                                    cost_dict["Cost ($)"].append(cost)
                                    cost_dict["Prompt Tokens"].append(prompt_tokens)
                                    cost_dict["Completion Tokens"].append(completion_tokens)
                                    cost_dict["Total Tokens"].append(total_tokens)
                                    cost_dict["Model"].append(model_name)
                except Exception as e:
                    print(f"Warning: Could not extract AG2 usage for agent {getattr(agent, 'name', 'unknown')}: {e}")

        # --- build DataFrame & totals ----------------------------------------------
        df = pd.DataFrame(cost_dict)

        # Only add totals if DataFrame has data
        if not df.empty:
            numeric_cols = df.select_dtypes(include="number").columns
            totals = df[numeric_cols].sum()
            df.loc["Total"] = pd.concat([pd.Series({"Agent": "Total"}), totals])

        # --- string formatting for display ------------------------------------------------------
        if df.empty:
            print("\nDisplaying cost…\n")
            print("No cost data available (no API calls were made)")
        else:
            df_str = df.copy()
            df_str["Cost ($)"] = df_str["Cost ($)"].map(lambda x: f"${x:.8f}")
            for col in ["Prompt Tokens", "Completion Tokens", "Total Tokens"]:
                df_str[col] = df_str[col].astype(int).astype(str)

            columns = df_str.columns.tolist()
            rows = df_str.fillna("").values.tolist()

            # --- column widths ----------------------------------------------------------
            widths = [
                max(len(col), max(len(str(row[i])) for row in rows))
                for i, col in enumerate(columns)
            ]

            # --- header with alignment markers -----------------------------------------
            header   = "|" + "|".join(f" {columns[i].ljust(widths[i])} " for i in range(len(columns))) + "|"

            # Markdown alignment row: left for text, right for numbers
            align_row = []
            for i, col in enumerate(columns):
                if col == "Agent":
                    align_row.append(":" + "-"*(widths[i]+1))      # :---- for left
                else:
                    align_row.append("-"*(widths[i]+1) + ":")      # ----: for right
            separator = "|" + "|".join(align_row) + "|"

            # --- build data lines -------------------------------------------------------
            lines = [header, separator]
            for idx, row in enumerate(rows):
                # insert rule before the Total row
                if row[0] == "Total":
                    lines.append("|" + "|".join("-"*(widths[i]+2) for i in range(len(columns))) + "|")

                cell = []
                for i, col in enumerate(columns):
                    s = str(row[i])
                    if col == "Agent":
                        cell.append(f" {s.ljust(widths[i])} ")
                    else:
                        cell.append(f" {s.rjust(widths[i])} ")
                lines.append("|" + "|".join(cell) + "|")

            print("\nDisplaying cost…\n")
            print("\n".join(lines))

        self.final_context['cost_dataframe'] = df

        # --- Save cost data as JSON ------------------------------------------------
        # Convert DataFrame to dict for JSON serialization
        cost_data = df.to_dict(orient='records')
        
        # Add timestamp
        # Use module-level datetime import (already imported at top)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save to JSON file in workdir
        if name_append is not None:
            json_path = os.path.join(self.work_dir, f"cost/cost_report_{name_append}_{timestamp}.json")
        else:
            json_path = os.path.join(self.work_dir, f"cost/cost_report_{timestamp}.json")
        with open(json_path, 'w') as f:
            json.dump(cost_data, f, indent=2)
            
        print(f"\nCost report data saved to: {json_path}\n")

        self.final_context['cost_report_path'] = json_path
        
        return df

        

    def clear_work_dir(self):
        # Clear everything inside work_dir if it exists
        if os.path.exists(self.work_dir):
            for item in os.listdir(self.work_dir):
                item_path = os.path.join(self.work_dir, item)
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

    def create_retry_context_for_step(self, step, attempt_number, max_attempts, user_feedback=None):
        """
        Create retry context for a step.

        Args:
            step: WorkflowStep object
            attempt_number: Current attempt number
            max_attempts: Maximum retry attempts
            user_feedback: Optional user feedback/guidance

        Returns:
            RetryContext object or None if retry manager not available
        """
        if self.retry_manager:
            return self.retry_manager.create_retry_context(
                step=step,
                attempt_number=attempt_number,
                max_attempts=max_attempts,
                user_feedback=user_feedback
            )
        return None

    def format_retry_prompt_for_context(self, retry_context):
        """
        Format retry context into a prompt string.

        Args:
            retry_context: RetryContext object

        Returns:
            Formatted prompt string or empty string if retry manager not available
        """
        if self.retry_manager and retry_context:
            return self.retry_manager.format_retry_prompt(retry_context)
        return ""

    def record_retry_attempt(self, step, attempt_number, error_type, error_message, traceback, agent_output):
        """
        Record a retry attempt for a step.

        Args:
            step: WorkflowStep object
            attempt_number: Attempt number
            error_type: Type of error (if failed)
            error_message: Error message (if failed)
            traceback: Full traceback (if failed)
            agent_output: Agent output
        """
        if self.retry_manager:
            self.retry_manager.record_attempt(
                step=step,
                attempt_number=attempt_number,
                error_type=error_type,
                error_message=error_message,
                traceback=traceback,
                agent_output=agent_output
            )

    def get_retry_stats(self, run_id):
        """
        Get retry statistics for a workflow run.

        Args:
            run_id: Workflow run ID

        Returns:
            Dictionary with retry statistics or None if metrics not available
        """
        if self.retry_metrics:
            return self.retry_metrics.get_retry_stats(run_id)
        return None

    def generate_retry_report(self, run_id):
        """
        Generate a retry report for a workflow run.

        Args:
            run_id: Workflow run ID

        Returns:
            Formatted report string or None if metrics not available
        """
        if self.retry_metrics:
            return self.retry_metrics.generate_retry_report(run_id)
        return None

    def solve(self, task, 
              initial_agent='task_improver', 
              shared_context=None,
              mode = "default", # can be "one_shot" or "default" (default is planning and control)
              step = None,
              max_rounds=10):
        self.step = step ## record the step for the context carryover workflow 
        this_shared_context = copy.deepcopy(self.shared_context)
        
        if mode == "one_shot" or mode == "chat":
            one_shot_shared_context = {'final_plan': "Step 1: solve the main task.",
                                        'current_status': "In progress",
                                        'current_plan_step_number': 1,
                                        'current_sub_task' : "solve the main task.",
                                        'current_instructions': "solve the main task.",
                                        'agent_for_sub_task': initial_agent,
                                        'feedback_left': 0,
                                        "number_of_steps_in_plan": 1,
                                        'maximum_number_of_steps_in_plan': 1,
                                        'researcher_append_instructions': '',
                                        'engineer_append_instructions': '',
                                        'perplexity_append_instructions': '',
                                        'idea_maker_append_instructions': '',
                                        'idea_hater_append_instructions': '',
                                        }
            
            if initial_agent == 'perplexity':
                one_shot_shared_context['perplexity_query'] = self.get_agent_object_from_name('perplexity').info['instructions'].format(main_task=task)
                # print('one_shot_shared_context: ', one_shot_shared_context)

            this_shared_context.update(one_shot_shared_context)
            this_shared_context.update(shared_context or {})

            # print('one_shot_shared_context: ', one_shot_shared_context)
            # print('shared_context: ', this_shared_context)
            # sys.exit()
            
        else:
            if shared_context is not None:
                this_shared_context.update(shared_context)
        
        try:
            self.clear_cache() ## obsolete
            # import pdb; pdb.set_trace()
        except:
            pass
        if self.clear_work_dir_bool:
            self.clear_work_dir()

        # Define full paths
        database_full_path = os.path.join(self.work_dir, this_shared_context.get("database_path", "data"))
        codebase_full_path = os.path.join(self.work_dir, this_shared_context.get("codebase_path", "codebase"))

        # add the codebase to the python path so we can import modules from it
        sys.path.append(codebase_full_path)

        chat_full_path = os.path.join(self.work_dir, "chats")
        time_full_path = os.path.join(self.work_dir, "time")
        cost_full_path = os.path.join(self.work_dir, "cost")
        
        # Create directories if they don't exist
        os.makedirs(database_full_path, exist_ok=True)
        os.makedirs(codebase_full_path, exist_ok=True)

        os.makedirs(chat_full_path, exist_ok=True)
        os.makedirs(time_full_path, exist_ok=True)
        os.makedirs(cost_full_path, exist_ok=True)

        for agent in self.agents:
            try:
                agent.agent.reset()
            except:
                pass

        this_shared_context['main_task'] = task
        this_shared_context['improved_main_task'] = task # initialize improved main task

        this_shared_context['work_dir'] = self.work_dir
        # print('this_shared_context: ', this_shared_context)
        # sys.exit()

        context_variables = ContextVariables(data=this_shared_context)

        # Create the pattern
        agent_pattern = AutoPattern(
                agents=[agent.agent for agent in self.agents],
                initial_agent=self.get_agent_from_name(initial_agent),
                context_variables=context_variables,
                group_manager_args = {"llm_config": self.llm_config, 
                                      "name": "main_cmbagent_chat"},
            )

        chat_result, context_variables, last_agent = initiate_group_chat(
            pattern=agent_pattern,
            messages=this_shared_context['main_task'],
            # user_agent=self.get_agent_from_name("admin"),
            max_rounds = max_rounds,
        )

        self.final_context = copy.deepcopy(context_variables)

        self.last_agent = last_agent
        self.chat_result = chat_result


    def get_agent_object_from_name(self,name):
        for agent in self.agents:
            if agent.info['name'] == name:
                return agent
        print(f"get_agent_object_from_name: agent {name} not found")
        sys.exit()

    def get_agent_from_name(self,name):
        for agent in self.agents:
            if agent.info['name'] == name:
                return agent.agent
        print(f"get_agent_from_name: agent {name} not found")
        sys.exit()

    def init_agents(self,agent_llm_configs=None, default_formatter_model=default_formatter_model_default):

        # this automatically loads all the agents from the assistants folder
        imported_rag_agents = import_rag_agents()
        imported_non_rag_agents = import_non_rag_agents()
        # print('imported_rag_agents: ', imported_rag_agents)
        # print("making new rag agents: ", self.make_new_rag_agents)
        # make_rag_agents(self.make_new_rag_agents)
        # imported_rag_agents = import_rag_agents()
        # print('imported_rag_agents: ', imported_rag_agents)

        ## this will store classes for each agents
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

        if cmbagent_debug:
            print('self.agent_classes after update: ')
            print()
            for agent_class, value in self.agent_classes.items():
                print(f'{agent_class}: {value}')
                print()

        # all agents
        self.agents = []

        if self.agent_list is None:
            self.agent_list = list(self.agent_classes.keys())

        # Drop entries from self.agent_classes that are not in self.agent_list
        self.agent_classes = {k: v for k, v in self.agent_classes.items() if k in self.agent_list or k in self.non_rag_agent_names}

        if cmbagent_debug:
            print('self.agent_classes after list update: ')
            print()
            for agent_class, value in self.agent_classes.items():
                print(f'{agent_class}: {value}')
                print()

        # remove agents that are not set to be skipped
        if self.skip_memory:
            # self.agent_classes.pop('memory')
            self.agent_classes.pop('session_summarizer')
        
        if self.skip_executor:
            self.agent_classes.pop('executor')

        if self.skip_rag_software_formatter:
            self.agent_classes.pop('rag_software_formatter')

        if cmbagent_debug:
            print('self.agent_classes after skipping agents: ')
            print()
            for agent_class, value in self.agent_classes.items():
                print(f'{agent_class}: {value}')
                print()

        # instantiate the agents and llm_configs
        if cmbagent_debug:
            print('self.llm_config: ', self.llm_config)


        for agent_name  in self.agent_classes:
            agent_class = self.agent_classes[agent_name]

            if cmbagent_debug:
                print('instantiating agent: ', agent_name)

            if agent_name in agent_llm_configs:
                llm_config = copy.deepcopy(self.llm_config)
                llm_config['config_list'][0].update(agent_llm_configs[agent_name])
                clean_llm_config(llm_config)
                
                if cmbagent_debug:
                    print('in cmbagent.py: found agent_llm_configs for: ', agent_name)
                    print('in cmbagent.py: llm_config updated to: ', llm_config)
            else:
                llm_config = copy.deepcopy(self.llm_config)

            if cmbagent_debug:
                print('in cmbagent.py BEFORE agent_instance: llm_config: ', llm_config)

            agent_instance = agent_class(llm_config=llm_config,agent_type=self.agent_type, work_dir=self.work_dir)

            if cmbagent_debug:
                print('agent_type: ', agent_instance.agent_type)

            # setattr(self, agent_name, agent_instance)

            self.agents.append(agent_instance)

        if self.skip_rag_agents:
            self.agents = [agent for agent in self.agents if agent.name.replace('_agent', '') not in self.rag_agent_names]

        # print('rag_agent_names: ', self.rag_agent_names)
        self.agent_names =  [agent.name for agent in self.agents]
        # print('skip_rag_agents: ', self.skip_rag_agents)
        # print('self.agents: ', self.agent_names)
        # import sys 
        # sys.exit()

        if cmbagent_debug:
            for agent in self.agents:
                print('\n\nagent.name: ', agent.name)
                print('agent.llm_config: ', agent.llm_config)
                print('\n\n')

        for agent in self.agents:

            if "formatter" in agent.name:

                # print("="*10)
                # print('\n\nagent.name BEFORE: ', agent.name)
                # print('agent.llm_config: ', agent.llm_config)
                # print('\n\n')

                agent.llm_config['config_list'][0].update(get_model_config(default_formatter_model, self.api_keys))
                
                # print('\n\nagent.name AFTER: ', agent.name)
                # print('agent.llm_config: ', agent.llm_config)
                # print('\n\n')
            # make sure the llm config doesnt have inconsistent parameters
            clean_llm_config(agent.llm_config)


        if self.verbose or cmbagent_debug:

            print("Using following agents: ", self.agent_names)
            print("Using following llm for agents: ")
            for agent in self.agents:
                print(f"{agent.name}: {agent.llm_config['config_list'][0]['model']}")
            print()

    def create_assistant(self, client, agent):

        if cmbagent_debug:
            print(f"-->Creating assistant {agent.name}")
            print(f"--> llm_config: {self.llm_config}")
            print(f"--> agent.llm_config: {agent.llm_config}")

        new_assistant = client.beta.assistants.create(
            name=agent.name,
            instructions=agent.info['instructions'],
            tools=[{"type": "file_search"}],
            tool_resources={"file_search": {"vector_store_ids":[]}},
            model=agent.llm_config['config_list'][0]['model'],
            # tool_choice={"type": "function", "function": {"name": "file_search"}}, ## not possible to set tool_choice as argument as of 8/03/2025
            # response_format=agent.llm_config['config_list'][0]['response_format']
        )

        if cmbagent_debug:
            print("New assistant created.")
            print(f"--> New assistant id: {new_assistant.id}")
            print(f"--> New assistant model: {new_assistant.model}")
            # print(f"--> New assistant response format: {new_assistant.response_format}")
            # print(f"--> New assistant tool choice: {new_assistant.tool_choice}")
            print("\n")

        return new_assistant


    def check_assistants(self, reset_assistant=[]):

        client = OpenAI(api_key = self.openai_api_key)
        available_assistants = client.beta.assistants.list(
            order="desc",
            limit="100",
        )


        # Create a list of assistant names for easy comparison
        assistant_names = [d.name for d in available_assistants.data]
        assistant_ids = [d.id for d in available_assistants.data]
        assistant_models = [d.model for d in available_assistants.data]

        for agent in self.agents:

            if cmbagent_debug:
                print('in cmbagent.py check_assistants: agent: ', agent.name)
                print('non_rag_agent_names: ', self.non_rag_agent_names)

            if agent.name not in self.non_rag_agent_names:
                if cmbagent_debug:
                    print(f"Checking agent: {agent.name}")

                # Check if agent name exists in the available assistants
                if agent.name in assistant_names:
                    if cmbagent_debug:
                        print(f"in cmbagent.py check_assistants: Agent {agent.name} exists in available assistants with id: {assistant_ids[assistant_names.index(agent.name)]}")

                    if cmbagent_debug:
                        print('in cmbagent.py check_assistants: this assistant model from openai: ',assistant_models[assistant_names.index(agent.name)])
                        print('in cmbagent.py check_assistants: this assistant model from llm_config: ', agent.llm_config['config_list'][0]['model'])
                    if assistant_models[assistant_names.index(agent.name)] != agent.llm_config['config_list'][0]['model']:
                        if cmbagent_debug:
                            print("in cmbagent.py check_assistants: Assistant model from openai does not match the requested model. Updating the assistant model.")
                        client.beta.assistants.update(
                            assistant_id=assistant_ids[assistant_names.index(agent.name)],
                            model=agent.llm_config['config_list'][0]['model']
                        )

                    if reset_assistant and agent.name.replace('_agent', '') in reset_assistant:
                        
                        print("This agent is in the reset_assistant list. Resetting the assistant.")
                        print("Deleting the assistant...")
                        client.beta.assistants.delete(assistant_ids[assistant_names.index(agent.name)])
                        print("Assistant deleted. Creating a new one...")
                        new_assistant = self.create_assistant(client, agent)
                        agent.info['assistant_config']['assistant_id'] = new_assistant.id
                        

                    else:

                        assistant_id = agent.info['assistant_config']['assistant_id']

                        if assistant_id != assistant_ids[assistant_names.index(agent.name)]:
                            if cmbagent_debug:
                                print("--> Assistant ID between yaml and openai do not match.")
                                print(f"--> Assistant ID from your yaml: {assistant_id}")
                                print(f"--> Assistant ID in openai: {assistant_ids[assistant_names.index(agent.name)]}")
                                print("--> We will use the assistant id from openai")
                            

                            agent.info['assistant_config']['assistant_id'] = assistant_ids[assistant_names.index(agent.name)]
                            if cmbagent_debug:
                                print(f"--> Updating yaml file with new assistant id: {assistant_ids[assistant_names.index(agent.name)]}")
                            update_yaml_preserving_format(f"{path_to_assistants}/{agent.name.replace('_agent', '') }.yaml", agent.name, assistant_ids[assistant_names.index(agent.name)], field = 'assistant_id')
                    
                else:

                    new_assistant = self.create_assistant(client, agent)
                    agent.info['assistant_config']['assistant_id'] = new_assistant.id



    def show_plot(self,plot_name):

        return Image(filename=self.work_dir + '/' + plot_name)


    def clear_cache(self):
        # print('clearing cache...')
        cache_dir = autogen.oai.client.LEGACY_CACHE_DIR ## "./cache" 
        # print("cache_dir: ", cache_dir)
        # if os.path.exists(cache_dir):
        #     # print("found cache_dir: ", cache_dir)
        #     shutil.rmtree(cache_dir)
            # print("cache_dir removed")
        # else:
            # print("no cache_dir found...")
        return None
        #  autogen.Completion.clear_cache(self.cache_seed) ## obsolete AttributeError: module 'autogen' has no attribute 'Completion'



    def filter_and_combine_agent_names(self, input_list):
        # Filter the input list to include only entries in self.agent_names
        filtered_list = [item for item in input_list if item in self.agent_names]

        # Convert the filtered list of strings into one string
        combined_string = ', '.join(filtered_list)

        return combined_string


    def set_planner_instructions(self):
        ### this is a template. Currently not used.

        # available agents and their roles:
        # available_agents = "\n\n#### Available agents and their roles\n\n"
        
        # for agent in self.agents:

        #     if agent.name in ['planner', 'engineer', 'executor', 'admin']:
        #         continue


        #     if 'description' in agent.info:

        #         role = agent.info['description']

        #     else:

        #         role = agent.info['instructions']

        #     available_agents += f"- *{agent.name}* : {role}\n"


        # # collect allowed transitions
        # all_allowed_transitions = "\n\n#### Allowed transitions\n\n"

        # for agent in self.agents:

        #     all_allowed_transitions += f"\t- {agent.name} -> {self.filter_and_combine_agent_names(agent.info['allowed_transitions'])}\n"



        # commenting for now
        # self.planner.info['instructions'] += available_agents + '\n\n' #+ all_allowed_transitions

        return


# Backward compatibility - import workflow utilities
from cmbagent.workflows.utils import clean_work_dir, load_context, load_plan

# Backward compatibility - import workflow functions
from cmbagent.workflows import (
    planning_and_control_context_carryover,
    planning_and_control,
    one_shot,
    human_in_the_loop,
    control,
)

# Alias for deep_research
deep_research = planning_and_control_context_carryover

# Import from keywords module for backward compatibility
from cmbagent.keywords import (
    get_keywords,
    get_keywords_from_string,
    get_keywords_from_aaai,
    get_aas_keywords,
)

# Import from processing module for backward compatibility
from cmbagent.processing.content_parser import (
    parse_formatted_content as _parse_formatted_content,
    collect_markdown_files as _collect_markdown_files,
    process_single_markdown_with_error_handling as _process_single_markdown_with_error_handling,
)
from cmbagent.processing.document_summarizer import summarize_document, summarize_documents
from cmbagent.processing.task_preprocessor import preprocess_task


# Note: Workflow functions (planning_and_control_context_carryover, planning_and_control,
# one_shot, human_in_the_loop, control) have been moved to cmbagent.workflows module.
# They are imported above for backward compatibility.

# END OF FILE
