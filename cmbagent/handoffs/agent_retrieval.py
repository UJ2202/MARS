"""
Agent retrieval utilities.

Provides functions to retrieve agent instances from CMBAgent.
"""

from typing import Dict
from .debug import debug_print


def get_all_agents(cmbagent_instance) -> Dict:
    """
    Retrieve all agent instances and return as a dictionary.

    Args:
        cmbagent_instance: CMBAgent instance

    Returns:
        Dictionary mapping agent names to agent objects
    """
    debug_print('Retrieving agent instances...')

    agent_names = [
        # Planning agents
        'task_improver', 'task_recorder', 'planner', 'planner_response_formatter',
        'plan_recorder', 'plan_reviewer', 'reviewer_response_formatter',
        'review_recorder', 'plan_setter',

        # Execution agents
        'engineer', 'engineer_response_formatter', 'engineer_nest',
        'researcher', 'researcher_response_formatter', 'researcher_executor',
        'executor', 'executor_bash', 'executor_response_formatter',

        # Control agents
        'control', 'admin', 'terminator',

        # Idea agents
        'idea_maker', 'idea_maker_response_formatter', 'idea_maker_nest',
        'idea_hater', 'idea_hater_response_formatter', 'idea_saver',

        # Utility agents
        'summarizer', 'summarizer_response_formatter',
        'installer', 'aas_keyword_finder', 'plot_judge', 'plot_debugger',
        'perplexity',

        # Context agents
        'camb_context', 'camb_response_formatter',
        'classy_context', 'classy_response_formatter',
    ]

    agents = {}
    for name in agent_names:
        try:
            agents[name] = cmbagent_instance.get_agent_object_from_name(name)
        except Exception as e:
            debug_print(f'Warning: Could not retrieve agent "{name}": {e}', indent=2)

    # RAG agents (conditional)
    if not cmbagent_instance.skip_rag_agents:
        rag_names = [
            'camb_agent', 'classy_sz_agent', 'classy_sz_response_formatter',
            'planck_agent', 'cobaya_agent', 'cobaya_response_formatter',
        ]
        for name in rag_names:
            try:
                agents[name] = cmbagent_instance.get_agent_object_from_name(name)
            except Exception as e:
                debug_print(f'Warning: Could not retrieve RAG agent "{name}": {e}', indent=2)

    debug_print(f'Retrieved {len(agents)} agents\n', indent=2)

    return agents
