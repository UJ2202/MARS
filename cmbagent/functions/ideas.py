"""Idea recording functionality."""

import datetime
import json
import os
from autogen import register_function


def record_ideas(ideas: list, cmbagent_instance):
    """Record ideas. You must record the entire list of ideas and their descriptions. You must not alter the list."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(cmbagent_instance.work_dir, f'ideas_{timestamp}.json')
    with open(filepath, 'w') as f:
        json.dump(ideas, f)
    return f"\nIdeas saved in {filepath}\n"


def setup_idea_functions(cmbagent_instance):
    """Register idea-related functions with the appropriate agents."""
    idea_saver = cmbagent_instance.get_agent_from_name('idea_saver')
    
    # Create closure to bind cmbagent_instance
    def record_ideas_closure(ideas: list):
        return record_ideas(ideas, cmbagent_instance)
    
    register_function(
        record_ideas_closure,
        caller=idea_saver,
        executor=idea_saver,
        description=r"""
        Records the ideas. You must record the entire list of ideas and their descriptions. You must not alter the list.
        """,
    )
