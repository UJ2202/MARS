"""
Branching module for workflow exploration and hypothesis testing.
"""

from cmbagent.branching.branch_manager import BranchManager
from cmbagent.branching.branch_executor import BranchExecutor
from cmbagent.branching.play_from_node import PlayFromNodeExecutor
from cmbagent.branching.comparator import BranchComparator

__all__ = [
    "BranchManager",
    "BranchExecutor",
    "PlayFromNodeExecutor",
    "BranchComparator",
]
