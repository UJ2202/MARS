"""
Backwards-compatible shim for functions.py

This module maintains backwards compatibility by re-exporting the main
register_functions_to_agents function from the new modular package structure.

All existing imports will continue to work:
    from cmbagent.functions import register_functions_to_agents
"""

# Import the main registration function from the new package
from .functions.registration import register_functions_to_agents

# Re-export utility functions for backwards compatibility
from .functions.utils import (
    extract_file_path_from_source,
    extract_functions_docstrings_from_file,
    load_docstrings,
    load_plots
)

__all__ = [
    'register_functions_to_agents',
    'extract_file_path_from_source',
    'extract_functions_docstrings_from_file',
    'load_docstrings',
    'load_plots'
]
