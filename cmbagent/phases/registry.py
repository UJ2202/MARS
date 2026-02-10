"""
Phase registry module for CMBAgent.

This module provides the PhaseRegistry class that manages
registration and lookup of available phase types.
"""

from typing import Dict, Type, List, Any
from cmbagent.phases.base import Phase, PhaseConfig


class PhaseRegistry:
    """
    Registry of available phases.

    Provides class methods for registering phase types and
    creating phase instances by type name.
    """

    _phases: Dict[str, Type[Phase]] = {}

    @classmethod
    def register(cls, phase_type: str):
        """
        Decorator to register a phase class.

        Usage:
            @PhaseRegistry.register("my_phase")
            class MyPhase(Phase):
                ...

        Args:
            phase_type: Unique identifier for the phase type

        Returns:
            Decorator function
        """
        def decorator(phase_class: Type[Phase]):
            cls._phases[phase_type] = phase_class
            return phase_class
        return decorator

    @classmethod
    def register_class(cls, phase_type: str, phase_class: Type[Phase]) -> None:
        """
        Register a phase class directly (non-decorator form).

        Args:
            phase_type: Unique identifier for the phase type
            phase_class: The phase class to register
        """
        cls._phases[phase_type] = phase_class

    @classmethod
    def get(cls, phase_type: str) -> Type[Phase]:
        """
        Get phase class by type.

        Args:
            phase_type: The phase type identifier

        Returns:
            The Phase subclass

        Raises:
            ValueError: If phase type is not registered
        """
        if phase_type not in cls._phases:
            raise ValueError(f"Unknown phase type: {phase_type}. Available: {list(cls._phases.keys())}")
        return cls._phases[phase_type]

    @classmethod
    def create(cls, phase_type: str, config: PhaseConfig = None, **kwargs) -> Phase:
        """
        Create phase instance by type.

        Args:
            phase_type: The phase type identifier
            config: Optional PhaseConfig (or phase-specific config)
            **kwargs: Additional arguments passed to phase constructor

        Returns:
            Phase instance
        """
        phase_class = cls.get(phase_type)
        if config is not None:
            return phase_class(config=config, **kwargs)
        return phase_class(**kwargs)

    @classmethod
    def create_from_dict(cls, phase_def: Dict[str, Any]) -> Phase:
        """
        Create phase from dictionary definition.

        Expected format:
            {
                "type": "planning",
                "config": {"max_plan_steps": 3, ...}
            }

        Args:
            phase_def: Dictionary with 'type' and optional 'config'

        Returns:
            Phase instance
        """
        phase_type = phase_def.get('type')
        if not phase_type:
            raise ValueError("Phase definition must include 'type' key")

        phase_class = cls.get(phase_type)
        config_dict = phase_def.get('config', {})

        # Try to find the specific config class for this phase
        # by looking for a config class with matching phase_type
        config_class = getattr(phase_class, 'config_class', None)
        if config_class is not None:
            config = config_class(**config_dict)
        else:
            # Fall back to base PhaseConfig
            config = PhaseConfig(phase_type=phase_type, **config_dict)

        return phase_class(config=config)

    @classmethod
    def list_all(cls) -> List[str]:
        """
        List all registered phase types.

        Returns:
            List of phase type identifiers
        """
        return list(cls._phases.keys())

    @classmethod
    def get_info(cls, phase_type: str) -> Dict[str, Any]:
        """
        Get phase metadata.

        Args:
            phase_type: The phase type identifier

        Returns:
            Dictionary with phase information
        """
        phase_class = cls.get(phase_type)
        # Create a temporary instance to get display info
        instance = phase_class()
        return {
            'type': phase_type,
            'display_name': instance.display_name,
            'required_agents': instance.get_required_agents(),
        }

    @classmethod
    def list_all_info(cls) -> List[Dict[str, Any]]:
        """
        Get metadata for all registered phases.

        Returns:
            List of phase info dictionaries
        """
        return [cls.get_info(phase_type) for phase_type in cls._phases.keys()]

    @classmethod
    def is_registered(cls, phase_type: str) -> bool:
        """
        Check if a phase type is registered.

        Args:
            phase_type: The phase type identifier

        Returns:
            True if registered, False otherwise
        """
        return phase_type in cls._phases

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered phases (primarily for testing).
        """
        cls._phases.clear()
