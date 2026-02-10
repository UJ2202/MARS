"""
Context Pipeline - Pass data between phases.

This module handles context transformation and data passing between phases.
"""

from typing import Dict, Any, Optional


class ContextPipeline:
    """
    Pipeline for passing context between phases.

    Handles:
    - Context transformation
    - Data filtering
    - Output → Input mapping
    """

    def __init__(self):
        self._transformations = []

    def add_transformation(self, func):
        """Add a transformation function to the pipeline."""
        self._transformations.append(func)

    def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all transformations to the data."""
        result = data.copy()
        for transform_func in self._transformations:
            result = transform_func(result)
        return result

    def extract_output(self, phase_result: Any) -> Dict[str, Any]:
        """Extract output data from a phase result."""
        if hasattr(phase_result, 'context'):
            if hasattr(phase_result.context, 'output_data'):
                return phase_result.context.output_data or {}
        return {}

    def prepare_input(self, previous_output: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare input for next phase from previous output."""
        result = {}

        # Add previous output if available
        if previous_output:
            result['previous_output'] = previous_output

        # Merge with config
        result.update(config)

        return result
