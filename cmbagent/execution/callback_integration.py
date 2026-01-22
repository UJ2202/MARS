"""
Integration between event capture and callback system.

NOTE: This integration is currently DISABLED to avoid duplicate events.
Event capture is handled automatically by AG2 hooks (ag2_hooks.py) which
capture events at a lower level. This module is kept for reference and
potential future use in scenarios where AG2 hooks are not sufficient.
"""

from typing import Optional, TYPE_CHECKING
from cmbagent.callbacks import WorkflowCallbacks, StepInfo, PlanInfo

if TYPE_CHECKING:
    from cmbagent.execution.event_capture import EventCaptureManager


def create_callbacks_with_event_capture(
    event_captor: 'EventCaptureManager',
    **callback_kwargs
) -> WorkflowCallbacks:
    """
    Create WorkflowCallbacks WITHOUT automatic event capture.
    
    Event capture is handled by AG2 hooks instead to avoid duplicates.
    This function now just passes through callbacks without event capture.
    
    Args:
        event_captor: EventCaptureManager instance (unused)
        **callback_kwargs: Callback functions to use
        
    Returns:
        WorkflowCallbacks with original callbacks only
    """
    
    # Simply return callbacks without event capture wrappers
    # AG2 hooks handle event capture automatically
    callbacks = WorkflowCallbacks(**callback_kwargs)
    
    return callbacks
