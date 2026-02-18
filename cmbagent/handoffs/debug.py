"""
Debug utilities for handoff registration.

Provides debug printing and logging functionality.
"""

import logging
import structlog
from ..cmbagent_utils import cmbagent_debug

logger = structlog.get_logger(__name__)


def is_debug_enabled() -> bool:
    """Check if debug mode is enabled."""
    return cmbagent_debug


def debug_print(message: str, indent: int = 1):
    """
    Print debug message if debug mode is enabled.

    Args:
        message: Message to print
        indent: Indentation level (0=none, 1=arrow, 2=checkmark)
    """
    if not cmbagent_debug:
        return

    if indent == 0:
        logger.debug("handoff_debug", message=message)
    elif indent == 1:
        logger.debug("handoff_debug", message=message, indent="arrow")
    elif indent == 2:
        logger.debug("handoff_debug", message=message, indent="check")
    else:
        logger.debug("handoff_debug", message=message, indent_level=indent)


def debug_section(title: str):
    """
    Print a section header if debug mode is enabled.

    Args:
        title: Section title
    """
    if not cmbagent_debug:
        return

    logger.debug("handoff_debug_section", title=title)
