"""State machine for managing workflow and step state transitions."""
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session

from cmbagent.database.states import WorkflowState, StepState
from cmbagent.database.transitions import WORKFLOW_TRANSITIONS, STEP_TRANSITIONS
from cmbagent.database.models import WorkflowRun, WorkflowStep, StateHistory


class StateMachineError(Exception):
    """Raised when invalid state transition attempted."""
    pass


class EventEmitter:
    """Simple event emitter for state changes."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def on(self, event_name: str, callback: Callable):
        """
        Register event listener.

        Args:
            event_name: Name of event to listen for
            callback: Function to call when event is emitted
        """
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def emit(self, event_name: str, **kwargs):
        """
        Emit event to all listeners.

        Args:
            event_name: Name of event to emit
            **kwargs: Event data to pass to listeners
        """
        listeners = self._listeners.get(event_name, [])
        for listener in listeners:
            try:
                listener(**kwargs)
            except Exception as e:
                # Log error but don't fail state transition
                import logging
                logging.getLogger(__name__).warning("Event listener error for '%s': %s", event_name, e)

    def remove_listener(self, event_name: str, callback: Callable):
        """Remove a specific listener for an event."""
        if event_name in self._listeners:
            try:
                self._listeners[event_name].remove(callback)
            except ValueError:
                pass


class StateMachine:
    """Manages state transitions for workflows and steps."""

    def __init__(
        self,
        db_session: Session,
        entity_type: str,
        event_emitter: Optional[EventEmitter] = None,
        emit_ws_callback: Optional[Callable] = None
    ):
        """
        Initialize state machine.

        Args:
            db_session: SQLAlchemy session
            entity_type: "workflow_run" or "workflow_step"
            event_emitter: Optional event emitter for broadcasting state changes
            emit_ws_callback: Optional callback for emitting WebSocket events.
                Signature: (entity_type: str, entity_id: str, from_state: str, to_state: str, reason: str, entity: Any) -> None
        """
        self.db = db_session
        self.entity_type = entity_type
        self.event_emitter = event_emitter or EventEmitter()
        self._emit_ws_callback = emit_ws_callback

        if entity_type == "workflow_run":
            self.model_class = WorkflowRun
            self.state_class = WorkflowState
            self.transitions = WORKFLOW_TRANSITIONS
        elif entity_type == "workflow_step":
            self.model_class = WorkflowStep
            self.state_class = StepState
            self.transitions = STEP_TRANSITIONS
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

    def transition_to(
        self,
        entity_id: str,
        new_state: str,
        reason: Optional[str] = None,
        transitioned_by: str = "system",
        meta: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Transition entity to new state with validation.

        Args:
            entity_id: UUID of workflow_run or workflow_step
            new_state: Target state
            reason: Optional reason for transition
            transitioned_by: Who/what triggered transition (default: "system")
            meta: Optional metadata for the transition

        Raises:
            StateMachineError: If transition invalid
        """
        # Load entity
        entity = self.db.query(self.model_class).filter(
            self.model_class.id == entity_id
        ).first()

        if not entity:
            raise StateMachineError(f"{self.entity_type} {entity_id} not found")

        current_state = entity.status

        # Convert new_state to enum to validate
        try:
            new_state_enum = self.state_class(new_state)
        except ValueError:
            raise StateMachineError(
                f"Invalid state '{new_state}' for {self.entity_type}"
            )

        # Skip transition if already in target state
        if current_state == new_state:
            return

        # Validate transition
        self._validate_transition(entity, current_state, new_state_enum)

        # Emit event BEFORE transition
        self.event_emitter.emit(
            "state_changing",
            entity_type=self.entity_type,
            entity_id=entity_id,
            from_state=current_state,
            to_state=new_state,
            reason=reason,
            transitioned_by=transitioned_by
        )

        # Update entity state
        entity.status = new_state

        # Record in state history
        state_history = StateHistory(
            entity_type=self.entity_type,
            entity_id=entity_id,
            session_id=entity.session_id,
            from_state=current_state,
            to_state=new_state,
            transition_reason=reason,
            transitioned_by=transitioned_by,
            meta=meta or {}
        )
        self.db.add(state_history)

        # Commit transaction
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise StateMachineError(f"Failed to commit state transition: {e}")

        # Emit event AFTER successful transition
        self.event_emitter.emit(
            "state_changed",
            entity_type=self.entity_type,
            entity_id=entity_id,
            from_state=current_state,
            to_state=new_state,
            reason=reason,
            transitioned_by=transitioned_by
        )

        # Emit WebSocket event for real-time updates
        self._emit_websocket_event(
            entity=entity,
            entity_id=entity_id,
            from_state=current_state,
            to_state=new_state,
            reason=reason
        )

    def _validate_transition(
        self,
        entity: Any,
        current_state: str,
        new_state: str
    ) -> None:
        """
        Validate state transition is allowed.

        Args:
            entity: The workflow_run or workflow_step entity
            current_state: Current state of entity
            new_state: Target state

        Raises:
            StateMachineError: If transition not allowed
        """
        try:
            current_state_enum = self.state_class(current_state)
        except ValueError:
            raise StateMachineError(
                f"Invalid current state '{current_state}' for {self.entity_type}"
            )

        transition_rules = self.transitions.get(current_state_enum)

        if not transition_rules:
            raise StateMachineError(
                f"No transition rules for state: {current_state}"
            )

        allowed_next = transition_rules["allowed_next"]
        new_state_enum = self.state_class(new_state)

        if new_state_enum not in allowed_next:
            raise StateMachineError(
                f"Invalid transition: {current_state} -> {new_state}. "
                f"Allowed: {[s.value for s in allowed_next]}"
            )

        # Check guards
        guards = transition_rules.get("guards", {})
        guard_func = guards.get(new_state_enum)
        if guard_func and not guard_func(entity):
            raise StateMachineError(
                f"Guard failed for transition: {current_state} -> {new_state}"
            )

    def get_allowed_transitions(self, entity_id: str) -> List[str]:
        """
        Get list of valid next states for entity.

        Args:
            entity_id: UUID of entity

        Returns:
            List of allowed state values
        """
        entity = self.db.query(self.model_class).filter(
            self.model_class.id == entity_id
        ).first()

        if not entity:
            return []

        try:
            current_state_enum = self.state_class(entity.status)
        except ValueError:
            return []

        transition_rules = self.transitions.get(current_state_enum, {})
        return [s.value for s in transition_rules.get("allowed_next", [])]

    def can_transition_to(self, entity_id: str, new_state: str) -> bool:
        """
        Check if transition to new_state is valid.

        Args:
            entity_id: UUID of entity
            new_state: Target state to check

        Returns:
            True if transition is valid, False otherwise
        """
        try:
            entity = self.db.query(self.model_class).filter(
                self.model_class.id == entity_id
            ).first()

            if not entity:
                return False

            current_state = entity.status
            new_state_enum = self.state_class(new_state)

            self._validate_transition(entity, current_state, new_state_enum)
            return True
        except (StateMachineError, ValueError):
            return False

    def get_state_history(self, entity_id: str) -> List[StateHistory]:
        """
        Get full state transition history for entity.

        Args:
            entity_id: UUID of entity

        Returns:
            List of StateHistory records ordered by created_at
        """
        return self.db.query(StateHistory).filter(
            StateHistory.entity_type == self.entity_type,
            StateHistory.entity_id == entity_id
        ).order_by(StateHistory.created_at).all()

    def get_current_state(self, entity_id: str) -> Optional[str]:
        """
        Get current state of entity.

        Args:
            entity_id: UUID of entity

        Returns:
            Current state value or None if entity not found
        """
        entity = self.db.query(self.model_class).filter(
            self.model_class.id == entity_id
        ).first()

        return entity.status if entity else None

    def _emit_websocket_event(
        self,
        entity: Any,
        entity_id: str,
        from_state: str,
        to_state: str,
        reason: Optional[str]
    ) -> None:
        """
        Emit WebSocket event for state transition via callback.

        Args:
            entity: The workflow_run or workflow_step entity
            entity_id: UUID of entity
            from_state: Previous state
            to_state: New state
            reason: Transition reason
        """
        if not self._emit_ws_callback:
            return
        try:
            self._emit_ws_callback(
                self.entity_type,
                str(entity_id),
                from_state,
                to_state,
                reason,
                entity
            )
        except Exception as e:
            # Don't fail the state transition if WebSocket emission fails
            import logging
            logging.getLogger(__name__).warning(
                "Failed to emit WebSocket event for %s %s: %s",
                self.entity_type, entity_id, e
            )
