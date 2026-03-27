"""Phase 7 — Proposal Compilation."""

import os
from dataclasses import dataclass
from cmbagent.phases.rfp.base import RfpPhaseBase, RfpPhaseConfig, PhaseContext


@dataclass
class RfpProposalConfig(RfpPhaseConfig):
    phase_type: str = "rfp_proposal"


class RfpProposalPhase(RfpPhaseBase):
    config_class = RfpProposalConfig

    def __init__(self, config=None):
        super().__init__(config or RfpProposalConfig())

    @property
    def phase_type(self) -> str:
        return "rfp_proposal"

    @property
    def display_name(self) -> str:
        return "Proposal Compilation"

    @property
    def shared_output_key(self) -> str:
        return "proposal_compilation"

    @property
    def output_filename(self) -> str:
        return "proposal.md"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a world-class proposal writer who has authored winning proposals for "
            "Fortune 500 RFP responses worth $10M-$500M.  You produce polished, executive-ready "
            "documents that rival top-tier consulting firms (McKinsey, Deloitte, Accenture).  "
            "The final document must be comprehensive, professionally structured with clear "
            "section numbering, suitable for board-level presentation, and demonstrate deep "
            "technical competence while remaining accessible to non-technical stakeholders.  "
            "Use professional formatting: numbered sections and subsections (1.1, 1.2, etc.), "
            "tables for comparisons and costs, bullet points for clarity, and bold key terms."
        )

    def build_user_prompt(self, context: PhaseContext) -> str:
        ss = context.shared_state
        requirements = ss.get("requirements_analysis", "(Not yet generated)")
        tools = ss.get("tools_technology", "(Not yet generated)")
        cloud = ss.get("cloud_infrastructure", "(Not yet generated)")
        implementation = ss.get("implementation_plan", "(Not yet generated)")
        architecture = ss.get("architecture_design", "(Not yet generated)")
        execution = ss.get("execution_strategy", "(Not yet generated)")

        return f"""You are compiling a **comprehensive, professional technical proposal** in response to a detailed RFP.  This is NOT a summary — it is the FULL proposal document that will be submitted to the client.  It must be thorough, well-documented, and demonstrate mastery of every aspect.

Below are the detailed analyses from each prior stage.  You must synthesize ALL of this content — do not omit details, cost figures, timelines, or technical specifications.  Expand and enhance where needed.

---

### SOURCE: Requirements Analysis
{requirements}

---

### SOURCE: Tools & Technology Selection
{tools}

---

### SOURCE: Cloud & Infrastructure Planning
{cloud}

---

### SOURCE: Implementation Plan
{implementation}

---

### SOURCE: Architecture Design
{architecture}

---

### SOURCE: Execution Strategy
{execution}

---

Produce the COMPLETE proposal document with ALL of the following sections.  Each section must be substantive (not a brief paragraph — provide real depth and detail).

## Document Structure Required:

### 1. Cover Page
- Proposal title, date, version, "Prepared for [Client]" / "Prepared by [Organization]"
- Confidentiality notice

### 2. Executive Summary (1-2 pages)
- Business context and opportunity
- Solution overview in non-technical language
- Key differentiators of the proposed approach
- High-level cost summary and ROI projection
- Recommended timeline overview

### 3. Purpose & Introduction
- Clearly state the purpose of this proposal — how it addresses the project objectives and meets the RFP requirements
- Introduction to the proposing organisation and its mission
- Problem Statement — the client challenge this proposal solves
- Solution Overview — a concise narrative tying every section together
- Key Benefits to the client (cost savings, efficiency, risk reduction, etc.)
- Tips and recommendations for the client to maximise value from the proposed solution

### 4. Methodology
- Describe the methods, frameworks, and processes that will be used to complete the project
- Development methodology (Agile / SAFe / Waterfall / Hybrid) with justification
- Quality assurance approach and testing strategy
- Continuous integration / continuous delivery (CI/CD) practices
- Communication cadence and collaboration tools

### 5. Understanding of Requirements
- Demonstrate thorough understanding of the client's needs
- Map each major requirement to the proposed solution component
- Identify implicit requirements and how they are addressed
- Functional requirements summary table
- Non-functional requirements (performance, security, scalability, accessibility)
- Requirements traceability matrix (table format)

### 6. Proposed Solution Overview
- End-to-end solution narrative
- How all components work together
- Key architectural decisions and rationale
- Solution differentiators vs. alternative approaches

### 7. Technology Stack & Tooling
- Complete technology inventory table (tool, purpose, license type, annual cost)
- Selection criteria and evaluation process
- Justification for each major tool choice
- Integration architecture between tools

### 8. Cloud Infrastructure & Provider Selection
- **Cloud Provider Comparison** — Reproduce the comparison matrix from Stage 3
- **Selected Provider & Justification** — Why this provider was chosen (data-backed)
- **Why Other Providers Were Not Selected** — Specific reasons for each rejected provider
- Complete infrastructure blueprint with service-by-service mapping
- Detailed monthly and annual cost breakdown tables
- Cost optimization strategy and projected savings

### 9. System Architecture
- High-level architecture description (reference diagrams from Stage 5)
- Component-level design with responsibilities
- Data flow and integration patterns
- Security architecture and compliance controls
- Scalability and performance design
- Architecture Decision Records (ADRs) for key decisions

### 10. Timeline & Milestones
- Detailed project schedule with phases, milestones, and deliverables
- Sprint/iteration breakdown per phase
- Dependencies and critical path
- Gantt-style timeline table
- Key decision gates and client approval points

### 11. Resources
- Proposed team structure diagram
- Key personnel profiles (role, expertise, relevant experience)
- Headcount per phase
- Equipment, software, and material requirements
- Third-party vendors or subcontractors (if any)

### 12. Implementation Approach
- Phased delivery roadmap with milestones
- Go-live strategy and hypercare
- Knowledge transfer plan
- Change management process

### 13. Execution Plan
- Project governance structure
- Communication plan and cadence
- Escalation matrix
- Post-launch support and maintenance plan

### 14. Risk Management
- Risk register table (risk, probability, impact, mitigation, owner)
- Technical risks and mitigation
- Operational risks and mitigation
- Commercial risks and mitigation
- Contingency plans for top-5 risks

### 15. Qualifications & Experience
- Organisation credentials, certifications, and awards
- Relevant case studies / past projects of similar scope
- Client references (placeholder format)
- Key team member qualifications and certifications

### 16. Compliance
- How the proposal meets every requirement specified in the RFP
- Regulatory and industry compliance (ISO 27001, SOC 2, GDPR, HIPAA, etc.)
- Data residency and sovereignty considerations
- Accessibility standards (WCAG 2.1, Section 508)
- Compliance matrix mapping each RFP requirement to the proposal section that addresses it

### 17. Pricing Summary & Total Cost of Ownership
- Summary pricing table by category
- Detailed cost breakdown: infrastructure, licensing, personnel, support
- Year 1 / Year 2 / Year 3 TCO projection
- Payment schedule and milestones
- Value justification and ROI analysis

### 18. Terms, Assumptions & Constraints
- Key assumptions underlying the proposal
- Scope boundaries and exclusions
- Client responsibilities and dependencies

### 19. Supporting Information & Appendices
You MUST generate FULL, REAL content for each appendix — not summaries, not descriptions, not one-liners.

**Appendix A: Detailed Cost Breakdowns**
- Reproduce EVERY cost table from Sections 7, 8, and 17 into this appendix
- Create a consolidated master cost table with columns: Category | Service/Tool | Monthly Cost (USD) | Annual Cost (USD)
- Include ALL line items: every cloud service, every tool license, every personnel cost
- Show subtotals per category and a grand total row

**Appendix B: Technology Evaluation Matrices**
- Create a full evaluation matrix table for EACH technology category (Frontend, Backend, Database, DevOps, Monitoring, Security, etc.)
- Columns: Tool Name | Cost | Security Rating | License | Community/Support | Performance | Verdict (Selected/Rejected)
- Include every tool that was evaluated (both selected and rejected alternatives)
- Minimum 5-8 rows per matrix

**Appendix C: Supporting Charts & Data**
- Architecture diagrams described in text form
- Performance benchmarks and capacity planning data
- SLA targets table (availability, response time, RPO, RTO)
- Infrastructure sizing table (instance types, storage, bandwidth)

**Appendix D: Glossary of Terms and Acronyms**
- List EVERY technical term and acronym used in this proposal
- Format as a table: Term/Acronym | Full Form | Definition
- Include at minimum 20-30 entries

**Appendix E: References and Citations**
- List the actual standards, frameworks, and official documentation referenced: ISO 27001, SOC 2, GDPR, HIPAA, OWASP, NIST, AWS Well-Architected Framework, etc.
- Include links or citation format for each tool's official documentation
- Minimum 10-15 references

CRITICAL INSTRUCTIONS:
- This must read as a REAL, PROFESSIONAL proposal — not an AI-generated summary
- Use proper section numbering (1, 1.1, 1.2, 2, 2.1, etc.)
- Include ALL cost figures, timelines, and technical details from the source sections
- Use professional tables for all comparisons, costs, and matrices
- The cloud section MUST clearly differentiate the chosen provider and explain why others were rejected
- The technology section MUST include comparison tables showing each tool vs. alternatives and why it was chosen
- Include security comparison for every major tool and cloud service
- If the RFP specifies a budget, clearly show how ALL costs fit within that budget
- Minimum expected length: 3000+ words — be comprehensive, not brief
- Every section should have substantive content, not just placeholder text

CURRENCY RULE — MANDATORY:
- ALL monetary values in the ENTIRE document MUST be in USD ($) only
- NEVER use INR, EUR, GBP, or any other currency
- Every cost table must use $ symbol with USD amounts

COST TABLE FORMAT — MANDATORY:
- Every cost table MUST have both Monthly Cost and Annual Cost columns with actual dollar figures
- Annual Cost = Monthly Cost x 12 (verify the math is correct)
- NEVER leave cost cells empty — every row must have a dollar amount
- Format: $X,XXX (with comma separators for thousands)
- NEVER put pipe characters inside a table cell
- Every cost table MUST end with a **Total** row summing all line items

ABSOLUTELY FORBIDDEN — NEVER DO THIS:
- NEVER use placeholder text like "[Insert ...]", "[To be added]", "[Insert detailed cost tables]", "[Insert glossary]", "[Insert references]", or any bracket-enclosed placeholder
- If you do not have specific data for a section, create it from the information available in the source sections above
- The Appendices section MUST contain REAL, COMPLETE content
- Every single section must have actual substantive content — zero placeholders allowed"""
