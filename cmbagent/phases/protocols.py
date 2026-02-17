"""
Typed protocols for the library/app boundary.

These protocols define the contracts that the app layer must satisfy
when providing execution context to the library. They replace
stringly-typed shared_state dicts with type-safe interfaces.
"""

from typing import Protocol, Optional, runtime_checkable

from cmbagent.callbacks import WorkflowCallbacks


@runtime_checkable
class ExecutionContext(Protocol):
    """Type-safe execution context provided by the app layer.

    The app (backend) creates concrete instances of this protocol
    and passes them into library code. The library never imports
    from the app — it only depends on this protocol.
    """
    run_id: str
    session_id: str
    work_dir: str
    callbacks: WorkflowCallbacks
