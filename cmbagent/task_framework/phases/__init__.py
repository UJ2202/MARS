"""Denario task phases -- auto-registered with PhaseRegistry on import."""

from cmbagent.task_framework.phases.idea import DenarioIdeaPhase
from cmbagent.task_framework.phases.method import DenarioMethodPhase
from cmbagent.task_framework.phases.experiment import DenarioExperimentPhase
from cmbagent.task_framework.phases.paper import DenarioPaperPhase

__all__ = [
    "DenarioIdeaPhase",
    "DenarioMethodPhase",
    "DenarioExperimentPhase",
    "DenarioPaperPhase",
]
