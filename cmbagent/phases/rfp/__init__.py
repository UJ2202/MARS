"""
RFP Proposal Generator Phases.

Seven phase classes that wrap each RFP stage inside the Phase-Based workflow
system.  Each phase uses CMBAgent with a dedicated "planner" + "plan_reviewer"
pair (or a single "engineer" for lighter stages) to produce higher-quality
output through multi-turn agent conversation.
"""

from cmbagent.phases.rfp.requirements_phase import RfpRequirementsPhase, RfpRequirementsConfig
from cmbagent.phases.rfp.tools_phase import RfpToolsPhase, RfpToolsConfig
from cmbagent.phases.rfp.cloud_phase import RfpCloudPhase, RfpCloudConfig
from cmbagent.phases.rfp.implementation_phase import RfpImplementationPhase, RfpImplementationConfig
from cmbagent.phases.rfp.architecture_phase import RfpArchitecturePhase, RfpArchitectureConfig
from cmbagent.phases.rfp.execution_phase import RfpExecutionPhase, RfpExecutionConfig
from cmbagent.phases.rfp.proposal_phase import RfpProposalPhase, RfpProposalConfig

__all__ = [
    "RfpRequirementsPhase", "RfpRequirementsConfig",
    "RfpToolsPhase", "RfpToolsConfig",
    "RfpCloudPhase", "RfpCloudConfig",
    "RfpImplementationPhase", "RfpImplementationConfig",
    "RfpArchitecturePhase", "RfpArchitectureConfig",
    "RfpExecutionPhase", "RfpExecutionConfig",
    "RfpProposalPhase", "RfpProposalConfig",
]
