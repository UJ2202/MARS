"""
CMBAgent Utilities Module

This module provides utility functions and constants that were previously part of the
custom AG2/AutoGen fork. Now maintained as part of the CMBAgent codebase.
"""

import os

# Debug mode flag
cmbagent_debug = False

# see https://github.com/openai/openai-python/blob/da48e4cac78d1d4ac749e2aa5cfd619fde1e6c68/src/openai/types/beta/file_search_tool.py#L20
# default_file_search_max_num_results = 20
# The default is 20 for `gpt-4*` models and 5 for `gpt-3.5-turbo`. This number
# should be between 1 and 50 inclusive.
file_search_max_num_results = 10

# Define the color mapping
cmbagent_color_dict = {
    "admin": "green",
    "control": "red"
}
cmbagent_default_color = "yellow"

# Define the logo as a module-level constant.
LOGO = r"""
    _____   __  __  ____                           _
   / ____| |  \/  ||  _ \                         | |
  | |      | \  / || |_) |  __ _   __ _   ___  _ __| |_
  | |      | |\/| ||  _ <  / _` | / _` | / _ \| '_ \  __|
  | |____  | |  | || |_) || (_| || (_| ||  __/| | | | |_
   \_____| |_|  |_||____/  \__,_| \__, | \___||_| |_|\__|
                                   __/ |
                                  |___/
    multi-agent systems for autonomous discovery
"""

# Version information (from LOGO)
# Version: Beta2
# Last updated: 11/03/5202
# Contributors: B. Bolliet, M. Cranmer, S. Krippendorf,
# A. Laverick, J. Lesgourgues, A. Lewis, B. D. Sherwin,
# K. M. Surrao, F. Villaescusa-Navarro, L. Xu, I. Zubeldia

# Calculate the image width as a module-level variable.
_lines = LOGO.splitlines()
_ascii_width = max(len(line) for line in _lines)
_scaling_factor = 8  # For example, 8 pixels per character.
IMG_WIDTH = _ascii_width * _scaling_factor

# Global flag to control display output (useful for headless environments)
cmbagent_disable_display = os.environ.get('CMBAGENT_DISABLE_DISPLAY', 'false').lower() == 'true'
