"""
Debug utilities for handoff registration.

Provides debug printing and logging functionality.
"""

from ..cmbagent_utils import cmbagent_debug


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
        print(message)
    elif indent == 1:
        print(f'→ {message}')
    elif indent == 2:
        print(f'  ✓ {message}')
    else:
        print(f'{"  " * indent}{message}')


def debug_section(title: str):
    """
    Print a section header if debug mode is enabled.

    Args:
        title: Section title
    """
    if not cmbagent_debug:
        return

    print('\n' + '=' * 60)
    print(title)
    print('=' * 60)
    if not title.startswith('ALL'):
        print()
