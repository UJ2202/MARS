"""Functions package for cmbagent - Modular function organization."""

# Re-export all functions for backwards compatibility
from .registration import register_functions_to_agents
from .utils import (
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
