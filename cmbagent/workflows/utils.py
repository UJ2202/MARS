"""
Utility functions for workflow management.

This module provides:
- Work directory cleanup
- Context loading/saving
- Plan loading
"""

import os
import json
import pickle
import shutil
from typing import Dict, Any


def clean_work_dir(work_dir: str) -> None:
    """
    Clear everything inside work_dir if it exists.

    Args:
        work_dir: Path to the working directory to clean
    """
    if os.path.exists(work_dir):
        for item in os.listdir(work_dir):
            item_path = os.path.join(work_dir, item)
            if os.path.isfile(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)


def load_context(context_path: str) -> Dict[str, Any]:
    """
    Load pickled context from file.

    Args:
        context_path: Path to the pickled context file

    Returns:
        Dictionary containing the loaded context
    """
    with open(context_path, 'rb') as f:
        context = pickle.load(f)
    return context


def load_plan(plan_path: str) -> Dict[str, Any]:
    """
    Load a plan from a JSON file into a dictionary.

    Args:
        plan_path: Path to the plan JSON file

    Returns:
        Dictionary containing the plan data
    """
    plan_path = os.path.expanduser(plan_path)
    with open(plan_path, 'r') as f:
        plan_dict = json.load(f)
    return plan_dict
