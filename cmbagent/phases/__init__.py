"""
CMBAgent Phases Module.

This module provides the phase-based workflow system:
- Phase: Abstract base class for all phases
- PhaseContext: Context that flows between phases
- PhaseResult: Result of phase execution
- PhaseConfig: Base configuration for phases
- PhaseStatus: Enum for phase execution states
- PhaseRegistry: Registry for phase types

Available Phases:
- PlanningPhase: Generate structured plans
- ControlPhase: Execute plan steps with context carryover
- OneShotPhase: Single-shot task execution
- HITLCheckpointPhase: Human-in-the-loop approval gates
- IdeaGenerationPhase: Generate and review ideas
- HITLPlanningPhase: Interactive planning with human feedback
- HITLControlPhase: Step-by-step execution with human approval
- CopilotPhase: Flexible assistant that adapts to task complexity

Workflow Context:
- WorkflowContext: Master context for entire workflow
"""

# Base classes
from cmbagent.phases.base import (
    Phase,
    PhaseConfig,
    PhaseContext,
    PhaseResult,
    PhaseStatus,
)

# Context management
from cmbagent.phases.context import WorkflowContext

# Registry
from cmbagent.phases.registry import PhaseRegistry

# Execution manager (generalized phase execution infrastructure)
from cmbagent.phases.execution_manager import (
    PhaseExecutionManager,
    PhaseExecutionConfig,
    PhaseEventType,
    WorkflowCancelledException,
    managed_phase_execution,
)

# Phase implementations
from cmbagent.phases.planning import PlanningPhase, PlanningPhaseConfig
from cmbagent.phases.control import ControlPhase, ControlPhaseConfig
from cmbagent.phases.one_shot import OneShotPhase, OneShotPhaseConfig
from cmbagent.phases.hitl_checkpoint import HITLCheckpointPhase, HITLCheckpointConfig, CheckpointType
from cmbagent.phases.idea_generation import IdeaGenerationPhase, IdeaGenerationPhaseConfig
from cmbagent.phases.hitl_planning import HITLPlanningPhase, HITLPlanningPhaseConfig
from cmbagent.phases.hitl_control import HITLControlPhase, HITLControlPhaseConfig
from cmbagent.phases.copilot_phase import CopilotPhase, CopilotPhaseConfig
from cmbagent.phases.literature_review import LiteratureReviewPhase, LiteratureReviewConfig
from cmbagent.phases.synthesis import SynthesisPhase, SynthesisConfig


# Register all phases with the registry
PhaseRegistry.register_class("planning", PlanningPhase)
PhaseRegistry.register_class("control", ControlPhase)
PhaseRegistry.register_class("one_shot", OneShotPhase)
PhaseRegistry.register_class("hitl_checkpoint", HITLCheckpointPhase)
PhaseRegistry.register_class("idea_generation", IdeaGenerationPhase)
PhaseRegistry.register_class("hitl_planning", HITLPlanningPhase)
PhaseRegistry.register_class("hitl_control", HITLControlPhase)
PhaseRegistry.register_class("copilot", CopilotPhase)
PhaseRegistry.register_class("literature_review", LiteratureReviewPhase)
PhaseRegistry.register_class("synthesis", SynthesisPhase)


__all__ = [
    # Base classes
    'Phase',
    'PhaseConfig',
    'PhaseContext',
    'PhaseResult',
    'PhaseStatus',

    # Context
    'WorkflowContext',

    # Registry
    'PhaseRegistry',

    # Planning
    'PlanningPhase',
    'PlanningPhaseConfig',

    # Control
    'ControlPhase',
    'ControlPhaseConfig',

    # One-shot
    'OneShotPhase',
    'OneShotPhaseConfig',

    # HITL
    'HITLCheckpointPhase',
    'HITLCheckpointConfig',
    'CheckpointType',

    # Idea generation
    'IdeaGenerationPhase',
    'IdeaGenerationPhaseConfig',

    # HITL Planning
    'HITLPlanningPhase',
    'HITLPlanningPhaseConfig',

    # HITL Control
    'HITLControlPhase',
    'HITLControlPhaseConfig',

    # Copilot
    'CopilotPhase',
    'CopilotPhaseConfig',

    # Literature Review (sample extensibility phase)
    'LiteratureReviewPhase',
    'LiteratureReviewConfig',

    # Synthesis (sample extensibility phase)
    'SynthesisPhase',
    'SynthesisConfig',

    # Execution manager
    'PhaseExecutionManager',
    'PhaseExecutionConfig',
    'PhaseEventType',
    'WorkflowCancelledException',
    'managed_phase_execution',
]
