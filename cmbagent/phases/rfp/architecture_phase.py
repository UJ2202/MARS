"""Phase 5 — Architecture Design."""

from dataclasses import dataclass
from cmbagent.phases.rfp.base import RfpPhaseBase, RfpPhaseConfig, PhaseContext


@dataclass
class RfpArchitectureConfig(RfpPhaseConfig):
    phase_type: str = "rfp_architecture"


class RfpArchitecturePhase(RfpPhaseBase):
    config_class = RfpArchitectureConfig

    def __init__(self, config=None):
        super().__init__(config or RfpArchitectureConfig())

    @property
    def phase_type(self) -> str:
        return "rfp_architecture"

    @property
    def display_name(self) -> str:
        return "Architecture Design"

    @property
    def shared_output_key(self) -> str:
        return "architecture_design"

    @property
    def output_filename(self) -> str:
        return "architecture.md"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a principal system architect.  Design robust, scalable "
            "architectures with clear component boundaries, data flows, and "
            "Architecture Decision Records."
        )

    def build_user_prompt(self, context: PhaseContext) -> str:
        ss = context.shared_state
        return f"""Based on all previous analysis and planning, design the complete system architecture.

Requirements Analysis:
{ss.get("requirements_analysis", "(Not yet generated)")}

Tools & Technology:
{ss.get("tools_technology", "(Not yet generated)")}

Cloud & Infrastructure:
{ss.get("cloud_infrastructure", "(Not yet generated)")}

Implementation Plan:
{ss.get("implementation_plan", "(Not yet generated)")}

Produce:
1. **High-Level Architecture** — System context diagram (describe in text/ASCII)
2. **Component Architecture** — Major components and their responsibilities
3. **Data Architecture** — Data models, data flow, storage strategy
4. **Integration Architecture** — APIs, message queues, event-driven patterns
5. **Security Architecture** — Authentication, authorization, encryption, audit
6. **Deployment Architecture** — Container strategy, orchestration, environments
7. **Scalability Design** — Horizontal/vertical scaling, caching strategy
8. **Monitoring & Observability** — Logging, metrics, tracing, alerting
9. **Technology Stack Summary** — Layer-by-layer technology choices
10. **Architecture Decision Records (ADRs)** — Key decisions with rationale

Produce a detailed markdown document with ASCII diagrams where helpful."""
