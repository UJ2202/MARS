# Task-Specific Forms Integration with CMBAgent File Management System

## Document Version: 1.0
## Date: 2026-01-21
## Status: Integration Design for Product Discovery Application (PDA)

---

## Executive Summary

This document outlines how to integrate the Product Discovery Application (PDA) React frontend with CMBAgent's file management system, transforming direct LLM API calls into structured CMBAgent workflows that properly track, capture, and return all generated artifacts.

**Current State:** React app calls OpenAI API directly for each step
**Target State:** React app orchestrates CMBAgent workflows with full file tracking and multi-format output

---

## Part 1: Current PDA Architecture Analysis

### 1.1 Current Flow (Direct LLM Calls)

```
┌────────────────────────────────────────────────────────────────┐
│                      PDA REACT APP                              │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: IntakeForm                                             │
│     ↓ (user fills form)                                         │
│  Step 2: Research Summary                                       │
│     ↓ callLLM(prompt) → OpenAI API → JSON response             │
│  Step 3: Problem Definition                                     │
│     ↓ callLLM(prompt) → OpenAI API → JSON response             │
│  Step 4: Opportunity Areas                                      │
│     ↓ callLLM(prompt) → OpenAI API → JSON response             │
│  Step 5: Solution Archetypes                                    │
│     ↓ callLLM(prompt) → OpenAI API → JSON response             │
│  Step 6: Feature Set Builder                                    │
│     ↓ callLLM(prompt) → JSON response                           │
│  Step 7: Prompt Generator                                       │
│     ↓ callLLM(prompt) → text prompts                            │
│  Step 8: Slide Generator                                        │
│     ↓ callLLM(prompt) → markdown slides                         │
│  Step 9: Summary                                                │
│     ↓ display all collected data                                │
│                                                                 │
│  Problem: No file tracking, no artifacts saved!                 │
└────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Issues with Current Approach

| Issue | Impact | CMBAgent Solution |
|-------|--------|-------------------|
| **No persistence** | Lose everything on page refresh (localStorage only) | Database + work_dir persistence |
| **No artifacts** | Can't generate reports, slides, or export data | File tracking system captures all outputs |
| **No code execution** | Can't run analysis, create plots, or process data | AG2 code execution with tracking |
| **No provenance** | Can't trace how conclusions were reached | Event tracking + file lineage |
| **No collaboration** | Can't share results or work together | Backend API + WebSocket updates |
| **Manual editing only** | No AI-powered iteration or refinement | Agent-driven refinement workflows |

---

## Part 2: Integrated Architecture with CMBAgent

### 2.1 New Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PDA REACT APP (Enhanced)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Step 1: IntakeForm                                                      │
│     ↓ (user fills form)                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              CMBAgent Backend Integration Layer                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│     ↓                                                                    │
│  POST /api/discovery/start                                               │
│     → Creates discovery_run (database)                                   │
│     → Initializes FileRegistry                                           │
│     → Returns run_id + WebSocket connection                              │
│                                                                          │
│  Step 2-8: Phased Execution                                              │
│     ↓ (for each phase)                                                   │
│  POST /api/discovery/{run_id}/execute-phase                              │
│     → CMBAgent executes structured workflow                              │
│     → FileRegistry tracks all outputs                                    │
│     → WebSocket sends real-time updates                                  │
│     → Returns: phase_results + generated_files[]                         │
│                                                                          │
│  Real-time Updates:                                                      │
│  WebSocket Events:                                                       │
│     • PHASE_STARTED                                                      │
│     • AGENT_MESSAGE                                                      │
│     • FILE_CREATED (with preview if applicable)                          │
│     • PHASE_COMPLETED                                                    │
│                                                                          │
│  Step 9: Final Summary                                                   │
│     ↓                                                                    │
│  GET /api/discovery/{run_id}/outputs                                     │
│     → Returns WorkflowOutputs with all files                             │
│     → Organized by category and phase                                    │
│     → Includes download URLs and embedded previews                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
         ↓                                ↓                      ↓
    Database           FileRegistry          AG2 Agents
    (PostgreSQL)       (File Tracking)       (Execution)
```

### 2.2 Phase-to-Agent Mapping

Each PDA step maps to a CMBAgent workflow phase:

| PDA Step | CMBAgent Phase | Agent | Output Files | Priority |
|----------|----------------|-------|--------------|----------|
| **1. Intake** | `intake` | Structured data capture | `intake_data.json` | PRIMARY |
| **2. Research** | `research` | Researcher + Web Search | `research_summary.json`, `references.md` | PRIMARY |
| **3. Problem** | `problem_definition` | Analyst | `problem_definition.json`, `problem_analysis.md` | PRIMARY |
| **4. Opportunity** | `opportunity_identification` | Strategist | `opportunities.json`, `opportunity_analysis.md` | PRIMARY |
| **5. Solution** | `solution_archetypes` | Solution Architect | `archetypes.json`, `solution_comparison.md` | PRIMARY |
| **6. Features** | `feature_generation` | Product Manager | `features.json`, `user_stories.md`, `requirements.md` | PRIMARY |
| **7. Prompts** | `prompt_generation` | Prompt Engineer | `prompts.json`, `lovable_prompt.md`, `googleai_prompt.md` | PRIMARY |
| **8. Slides** | `presentation_generation` | Presentation Generator | `slides.md`, `slides.pptx`, `presentation.pdf` | PRIMARY |
| **9. Summary** | `finalization` | Aggregator | `executive_summary.md`, `full_report.pdf`, `data_export.zip` | PRIMARY |

---

## Part 3: Backend API Design

### 3.1 New Endpoint: Discovery Workflow

```python
# backend/services/discovery_service.py

from typing import Dict, Any, List
from cmbagent import CMBAgent
from cmbagent.execution.file_registry import FileRegistry, FileCategory, OutputPriority
from cmbagent.execution.output_serializer import OutputSerializer
import uuid
import json
import os

class DiscoveryPhase:
    """Defines a phase in the product discovery workflow."""
    def __init__(
        self,
        name: str,
        agent_type: str,
        prompt_template: str,
        expected_outputs: List[Dict[str, str]]
    ):
        self.name = name
        self.agent_type = agent_type
        self.prompt_template = prompt_template
        self.expected_outputs = expected_outputs

class DiscoveryWorkflowService:
    """
    Orchestrates product discovery workflows with full file tracking.
    
    Key features:
    - Phase-based execution (matches PDA steps)
    - Automatic file tracking for all outputs
    - Real-time WebSocket updates
    - Multi-format output serialization
    """
    
    PHASES = {
        'research': DiscoveryPhase(
            name='research',
            agent_type='researcher',
            prompt_template='''You are a senior Product Discovery strategist.

Using the intake data below, generate a comprehensive research summary:

{intake_json}

**YOUR TASK:**
1. Research market trends relevant to the problem keywords
2. Identify competitor moves in this space
3. Document industry pain points
4. Suggest workshop angles for discovery

**OUTPUT FORMAT:**
Create the following files in the work directory:

1. `research_summary.json` - Structured data with:
   - marketTrends: list of strings
   - competitorMoves: list of strings
   - industryPainPoints: list of strings
   - workshopAngles: list of strings
   - references: list of URLs/sources

2. `research_details.md` - Detailed markdown report with:
   - Executive summary
   - Detailed findings for each area
   - References and sources
   - Recommended focus areas

**CODE EXECUTION:**
Use Python to:
- Search for relevant information
- Structure the JSON output
- Generate the markdown report
- Save both files to the work directory

Mark the JSON file as the primary deliverable.''',
            expected_outputs=[
                {'filename': 'research_summary.json', 'type': 'data', 'is_deliverable': True},
                {'filename': 'research_details.md', 'type': 'report', 'is_deliverable': False}
            ]
        ),
        
        'problem_definition': DiscoveryPhase(
            name='problem_definition',
            agent_type='analyst',
            prompt_template='''You are a problem analysis expert.

Using the research summary and intake data:

**INTAKE:**
{intake_json}

**RESEARCH:**
{research_json}

**YOUR TASK:**
Define the core problem with:
1. Clear problem statement
2. Supporting evidence from research
3. Personas affected
4. KPIs impacted
5. Root cause analysis
6. Problem reframing examples

**OUTPUT FILES:**
1. `problem_definition.json` - Structured problem definition
2. `problem_analysis.md` - Detailed analysis with visualizations
3. `problem_statement.txt` - One-liner for quick reference

Create a Python script to:
- Process the research data
- Generate insights
- Create a visualization of affected personas vs KPIs
- Save all files with proper formatting

Mark the JSON as primary deliverable.''',
            expected_outputs=[
                {'filename': 'problem_definition.json', 'type': 'data', 'is_deliverable': True},
                {'filename': 'problem_analysis.md', 'type': 'report', 'is_deliverable': False},
                {'filename': 'problem_statement.txt', 'type': 'data', 'is_deliverable': False}
            ]
        ),
        
        'opportunity_identification': DiscoveryPhase(
            name='opportunity_identification',
            agent_type='strategist',
            prompt_template='''You are a strategic opportunity identification expert.

**CONTEXT:**
Intake: {intake_json}
Research: {research_json}
Problem: {problem_json}

**YOUR TASK:**
Identify 4-6 high-value opportunity areas:

For each opportunity:
- Title (clear, actionable)
- Explanation (why this is valuable)
- Value category (Revenue/Efficiency/Experience/Risk)
- KPIs that would improve
- "Why now?" (urgency/timing factors)
- Supporting references from research

**OUTPUT FILES:**
1. `opportunities.json` - Array of opportunity objects
2. `opportunity_matrix.png` - 2x2 matrix plotting value vs effort
3. `opportunity_analysis.md` - Detailed breakdown

Use Python to:
- Analyze the problem and research data
- Score opportunities on value/effort
- Create visualization
- Generate all output files

Mark JSON and PNG as primary deliverables.''',
            expected_outputs=[
                {'filename': 'opportunities.json', 'type': 'data', 'is_deliverable': True},
                {'filename': 'opportunity_matrix.png', 'type': 'plot', 'is_deliverable': True},
                {'filename': 'opportunity_analysis.md', 'type': 'report', 'is_deliverable': False}
            ]
        ),
        
        'solution_archetypes': DiscoveryPhase(
            name='solution_archetypes',
            agent_type='solution_architect',
            prompt_template='''You are a solution architecture expert.

**CONTEXT:**
Selected Opportunity: {selected_opportunity_json}
Full Context: {full_context_json}

**YOUR TASK:**
Design 3-4 solution archetypes addressing this opportunity:

For each archetype:
- Title (clear solution approach)
- Summary (2-3 sentences)
- Target personas
- Key benefits
- High-level technical approach
- References/precedents

**OUTPUT FILES:**
1. `solution_archetypes.json` - Array of solution objects
2. `solution_comparison.md` - Comparison table
3. `architecture_sketches.png` - High-level diagrams

Use Python with matplotlib/graphviz to:
- Structure solution data
- Create comparison visualizations
- Generate architecture diagrams
- Save all files

Mark JSON and PNG as primary deliverables.''',
            expected_outputs=[
                {'filename': 'solution_archetypes.json', 'type': 'data', 'is_deliverable': True},
                {'filename': 'architecture_sketches.png', 'type': 'plot', 'is_deliverable': True},
                {'filename': 'solution_comparison.md', 'type': 'report', 'is_deliverable': False}
            ]
        ),
        
        'feature_generation': DiscoveryPhase(
            name='feature_generation',
            agent_type='product_manager',
            prompt_template='''You are a senior product manager specializing in feature definition.

**CONTEXT:**
Selected Solution: {selected_solution_json}
Full Context: {full_context_json}

**YOUR TASK:**
Generate a comprehensive feature set (15-25 features):

For each feature:
- Name (clear, user-centric)
- Description (what it does)
- Strategic goal (ties to opportunity)
- User stories (3-5 stories)
- Success metrics (measurable KPIs)
- Bucket (Foundation/Core/Advanced/Nice-to-Have)
- Priority (Must/Should/Could)

**OUTPUT FILES:**
1. `features.json` - Complete feature set
2. `user_stories.md` - Formatted user stories
3. `feature_roadmap.png` - Timeline visualization
4. `requirements.md` - Detailed requirements doc

Use Python to:
- Generate features based on solution
- Create roadmap visualization
- Format documentation
- Save all files

Mark JSON and roadmap PNG as primary deliverables.''',
            expected_outputs=[
                {'filename': 'features.json', 'type': 'data', 'is_deliverable': True},
                {'filename': 'feature_roadmap.png', 'type': 'plot', 'is_deliverable': True},
                {'filename': 'user_stories.md', 'type': 'report', 'is_deliverable': False},
                {'filename': 'requirements.md', 'type': 'report', 'is_deliverable': False}
            ]
        ),
        
        'prompt_generation': DiscoveryPhase(
            name='prompt_generation',
            agent_type='prompt_engineer',
            prompt_template='''You are an expert prompt engineer.

**CONTEXT:**
Features: {features_json}
Full Discovery Context: {full_context_json}

**YOUR TASK:**
Generate optimized prompts for different AI development platforms:

1. Lovable.dev prompt (React/TypeScript focus)
2. Google AI Studio prompt (Gemini-optimized)
3. General Claude/GPT prompt

Each prompt should:
- Include complete context from discovery
- Specify technical requirements
- Include example feature implementations
- Reference design patterns
- Be copy-paste ready

**OUTPUT FILES:**
1. `prompts.json` - Structured prompts object
2. `lovable_prompt.md` - Lovable.dev specific
3. `googleai_prompt.md` - Google AI Studio specific
4. `general_prompt.md` - Universal prompt
5. `prompt_guide.md` - How to use these prompts

Save all files to work directory.
Mark the JSON as primary deliverable.''',
            expected_outputs=[
                {'filename': 'prompts.json', 'type': 'data', 'is_deliverable': True},
                {'filename': 'lovable_prompt.md', 'type': 'report', 'is_deliverable': False},
                {'filename': 'googleai_prompt.md', 'type': 'report', 'is_deliverable': False}
            ]
        ),
        
        'presentation_generation': DiscoveryPhase(
            name='presentation_generation',
            agent_type='presentation_generator',
            prompt_template='''You are a presentation designer specializing in discovery workshops.

**CONTEXT:**
Full Discovery Data: {full_context_json}

**YOUR TASK:**
Create a comprehensive presentation deck:

**SLIDE STRUCTURE:**
1. Title & Overview
2. Client Context
3. Research Insights (market, competitors, pain points)
4. Problem Definition
5. Opportunity Landscape
6. Selected Opportunity Deep-Dive
7. Solution Archetypes
8. Recommended Solution
9. Feature Breakdown (by bucket)
10. Roadmap & Priorities
11. Success Metrics
12. Next Steps

**OUTPUT FILES:**
1. `slides.md` - Markdown format (Marp/reveal.js compatible)
2. `slides.html` - Self-contained HTML presentation
3. `slides_content.json` - Structured slide data
4. `presentation_guide.md` - Speaker notes

Use Python to:
- Structure slide content
- Generate markdown with proper formatting
- Convert to HTML with styling
- Save all files

Mark MD and HTML as primary deliverables.''',
            expected_outputs=[
                {'filename': 'slides.md', 'type': 'report', 'is_deliverable': True},
                {'filename': 'slides.html', 'type': 'report', 'is_deliverable': True},
                {'filename': 'slides_content.json', 'type': 'data', 'is_deliverable': False}
            ]
        ),
        
        'finalization': DiscoveryPhase(
            name='finalization',
            agent_type='aggregator',
            prompt_template='''You are a discovery workflow aggregator.

**YOUR TASK:**
Create final summary artifacts from all phases:

**AVAILABLE DATA:**
{all_phases_json}

**OUTPUT FILES:**
1. `executive_summary.md` - 2-page executive summary
2. `discovery_report.md` - Complete discovery documentation
3. `data_export.json` - All structured data in one file
4. `file_manifest.json` - Index of all generated files
5. `metrics_dashboard.html` - Interactive metrics view

Use Python to:
- Aggregate all phase data
- Generate summary documents
- Create interactive dashboard
- Package everything
- Generate manifest

Mark executive summary and data export as primary deliverables.''',
            expected_outputs=[
                {'filename': 'executive_summary.md', 'type': 'report', 'is_deliverable': True},
                {'filename': 'data_export.json', 'type': 'data', 'is_deliverable': True},
                {'filename': 'discovery_report.md', 'type': 'report', 'is_deliverable': False},
                {'filename': 'metrics_dashboard.html', 'type': 'report', 'is_deliverable': False}
            ]
        )
    }
    
    def __init__(self, db_session, websocket_manager):
        self.db = db_session
        self.ws_manager = websocket_manager
    
    async def start_discovery(
        self,
        intake_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Initialize a new discovery workflow.
        
        Returns:
            {
                'run_id': str,
                'work_dir': str,
                'websocket_url': str,
                'status': 'initialized'
            }
        """
        run_id = str(uuid.uuid4())
        work_dir = f"/tmp/discovery_runs/{run_id}"
        os.makedirs(work_dir, exist_ok=True)
        
        # Save intake data
        intake_path = os.path.join(work_dir, 'intake_data.json')
        with open(intake_path, 'w') as f:
            json.dump(intake_data, f, indent=2)
        
        # Create database record
        discovery_run = DiscoveryRun(
            run_id=run_id,
            user_id=user_id,
            status='initialized',
            work_dir=work_dir,
            intake_data=intake_data,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(discovery_run)
        self.db.commit()
        
        return {
            'run_id': run_id,
            'work_dir': work_dir,
            'websocket_url': f'/ws/discovery/{run_id}',
            'status': 'initialized'
        }
    
    async def execute_phase(
        self,
        run_id: str,
        phase_name: str,
        phase_inputs: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a single discovery phase with CMBAgent.
        
        Args:
            run_id: Discovery run ID
            phase_name: Name of phase to execute
            phase_inputs: Additional inputs for this phase (e.g., selected opportunity)
        
        Returns:
            {
                'phase': str,
                'status': 'completed' | 'failed',
                'phase_data': dict,  # Parsed from primary output file
                'generated_files': [
                    {
                        'id': str,
                        'filename': str,
                        'category': str,
                        'path': str,
                        'url': str,
                        'preview': str | None  # For small files/images
                    }
                ],
                'execution_time': float,
                'error': str | None
            }
        """
        # Get discovery run
        discovery_run = self.db.query(DiscoveryRun).filter_by(run_id=run_id).first()
        if not discovery_run:
            raise ValueError(f"Discovery run {run_id} not found")
        
        # Get phase definition
        phase = self.PHASES.get(phase_name)
        if not phase:
            raise ValueError(f"Unknown phase: {phase_name}")
        
        # Build context for this phase
        context = self._build_phase_context(discovery_run, phase_inputs)
        
        # Format prompt with context
        prompt = phase.prompt_template.format(**context)
        
        # Initialize CMBAgent with file tracking
        cmbagent = CMBAgent(
            work_dir=discovery_run.work_dir,
            db_session=self.db,
            websocket=self.ws_manager
        )
        
        # Initialize file tracking
        cmbagent._init_file_tracking(run_id)
        cmbagent.file_registry.set_context(
            phase=phase_name,
            agent=phase.agent_type
        )
        
        # Emit phase start event
        await self.ws_manager.emit(run_id, {
            'event_type': 'PHASE_STARTED',
            'data': {
                'phase': phase_name,
                'phase_label': phase_name.replace('_', ' ').title()
            }
        })
        
        # Execute with one_shot mode
        start_time = time.time()
        try:
            result = cmbagent.one_shot(
                task=prompt,
                agent=phase.agent_type,
                model='gpt-4o',
                work_dir=discovery_run.work_dir
            )
            
            execution_time = time.time() - start_time
            
            # Finalize file tracking
            workflow_outputs = cmbagent._finalize_file_tracking()
            
            # Mark expected outputs as deliverables
            for expected in phase.expected_outputs:
                file_path = os.path.join(discovery_run.work_dir, expected['filename'])
                if os.path.exists(file_path):
                    cmbagent.file_registry.mark_as_deliverable(
                        file_path,
                        description=f"{phase_name} output: {expected['filename']}",
                        order=phase.expected_outputs.index(expected)
                    )
            
            # Re-collect outputs with marked deliverables
            output_collector = cmbagent.output_collector
            workflow_outputs = output_collector.collect()
            
            # Serialize outputs for API
            serializer = OutputSerializer(workflow_outputs, discovery_run.work_dir)
            api_outputs = serializer.for_api_response(base_url='http://localhost:8000')
            
            # Load primary phase data
            phase_data = self._extract_phase_data(discovery_run.work_dir, phase)
            
            # Update discovery run
            phase_results = discovery_run.phase_results or {}
            phase_results[phase_name] = {
                'data': phase_data,
                'execution_time': execution_time,
                'completed_at': datetime.now(timezone.utc).isoformat()
            }
            discovery_run.phase_results = phase_results
            discovery_run.current_phase = phase_name
            self.db.commit()
            
            # Emit completion event
            await self.ws_manager.emit(run_id, {
                'event_type': 'PHASE_COMPLETED',
                'data': {
                    'phase': phase_name,
                    'execution_time': execution_time,
                    'files_generated': len(api_outputs['primary_outputs'])
                }
            })
            
            return {
                'phase': phase_name,
                'status': 'completed',
                'phase_data': phase_data,
                'generated_files': api_outputs['primary_outputs'],
                'execution_time': execution_time,
                'error': None
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            await self.ws_manager.emit(run_id, {
                'event_type': 'PHASE_FAILED',
                'data': {
                    'phase': phase_name,
                    'error': str(e)
                }
            })
            
            return {
                'phase': phase_name,
                'status': 'failed',
                'phase_data': None,
                'generated_files': [],
                'execution_time': execution_time,
                'error': str(e)
            }
    
    def _build_phase_context(
        self,
        discovery_run: 'DiscoveryRun',
        phase_inputs: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Build context dictionary for phase prompt."""
        context = {}
        
        # Always include intake data
        context['intake_json'] = json.dumps(discovery_run.intake_data, indent=2)
        
        # Add previous phase results
        phase_results = discovery_run.phase_results or {}
        
        if 'research' in phase_results:
            context['research_json'] = json.dumps(phase_results['research']['data'], indent=2)
        
        if 'problem_definition' in phase_results:
            context['problem_json'] = json.dumps(phase_results['problem_definition']['data'], indent=2)
        
        # Add phase-specific inputs
        if phase_inputs:
            for key, value in phase_inputs.items():
                context[f'{key}_json'] = json.dumps(value, indent=2)
        
        # Add full context for later phases
        if len(phase_results) > 2:
            context['full_context_json'] = json.dumps({
                'intake': discovery_run.intake_data,
                'phases': phase_results
            }, indent=2)
        
        return context
    
    def _extract_phase_data(
        self,
        work_dir: str,
        phase: DiscoveryPhase
    ) -> Dict[str, Any]:
        """Extract primary data from phase output files."""
        # Find primary deliverable (usually .json file)
        for expected in phase.expected_outputs:
            if expected.get('is_deliverable') and expected['filename'].endswith('.json'):
                file_path = os.path.join(work_dir, expected['filename'])
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        return json.load(f)
        
        return {}
    
    async def get_discovery_outputs(
        self,
        run_id: str,
        format: str = 'api'  # 'api', 'mcp', 'tool', 'download'
    ) -> Dict[str, Any]:
        """
        Get all outputs from a discovery run.
        
        Args:
            run_id: Discovery run ID
            format: Output format ('api', 'mcp', 'tool', 'download')
        
        Returns formatted outputs based on format parameter
        """
        discovery_run = self.db.query(DiscoveryRun).filter_by(run_id=run_id).first()
        if not discovery_run:
            raise ValueError(f"Discovery run {run_id} not found")
        
        # Recreate FileRegistry from work_dir
        file_registry = FileRegistry(
            work_dir=discovery_run.work_dir,
            run_id=run_id,
            db_session=self.db
        )
        
        # Scan for all files
        file_registry.scan_work_directory()
        
        # Collect outputs
        from cmbagent.execution.output_collector import OutputCollector
        output_collector = OutputCollector(file_registry, discovery_run.work_dir)
        workflow_outputs = output_collector.collect()
        
        # Serialize based on format
        serializer = OutputSerializer(workflow_outputs, discovery_run.work_dir)
        
        if format == 'api':
            return serializer.for_api_response(base_url='http://localhost:8000')
        elif format == 'mcp':
            return serializer.for_mcp_server()
        elif format == 'tool':
            return serializer.for_tool_execution()
        elif format == 'download':
            # Create ZIP file
            zip_path = os.path.join(discovery_run.work_dir, f'discovery_{run_id}.zip')
            self._create_zip_archive(discovery_run.work_dir, zip_path)
            return {
                'download_url': f'/api/discovery/{run_id}/download',
                'file_size': os.path.getsize(zip_path)
            }
        
        return serializer.for_api_response(base_url='http://localhost:8000')
```

### 3.2 FastAPI Endpoints

```python
# backend/main.py (additions)

from backend.services.discovery_service import DiscoveryWorkflowService

# Initialize service
discovery_service = DiscoveryWorkflowService(db_session, websocket_manager)

@app.post("/api/discovery/start")
async def start_discovery(
    request: DiscoveryStartRequest,
    user: User = Depends(get_current_user)
):
    """Start a new product discovery workflow."""
    result = await discovery_service.start_discovery(
        intake_data=request.intake_data,
        user_id=user.id
    )
    return result

@app.post("/api/discovery/{run_id}/execute-phase")
async def execute_discovery_phase(
    run_id: str,
    request: ExecutePhaseRequest,
    user: User = Depends(get_current_user)
):
    """Execute a specific phase of the discovery workflow."""
    result = await discovery_service.execute_phase(
        run_id=run_id,
        phase_name=request.phase_name,
        phase_inputs=request.phase_inputs
    )
    return result

@app.get("/api/discovery/{run_id}/outputs")
async def get_discovery_outputs(
    run_id: str,
    format: str = Query('api', enum=['api', 'mcp', 'tool', 'download']),
    user: User = Depends(get_current_user)
):
    """Get all outputs from a discovery run."""
    result = await discovery_service.get_discovery_outputs(
        run_id=run_id,
        format=format
    )
    return result

@app.get("/api/discovery/{run_id}/download")
async def download_discovery_outputs(
    run_id: str,
    user: User = Depends(get_current_user)
):
    """Download all discovery outputs as ZIP."""
    discovery_run = db.query(DiscoveryRun).filter_by(run_id=run_id).first()
    zip_path = os.path.join(discovery_run.work_dir, f'discovery_{run_id}.zip')
    
    return FileResponse(
        zip_path,
        media_type='application/zip',
        filename=f'discovery_{run_id}.zip'
    )

@app.websocket("/ws/discovery/{run_id}")
async def websocket_discovery_endpoint(
    websocket: WebSocket,
    run_id: str
):
    """WebSocket endpoint for real-time discovery updates."""
    await websocket_manager.connect(run_id, websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(run_id, websocket)
```

---

## Part 4: React Frontend Integration

### 4.1 New Service Layer

```typescript
// src/lib/cmbagent-service.ts

interface DiscoveryStartResponse {
  run_id: string;
  work_dir: string;
  websocket_url: string;
  status: 'initialized';
}

interface PhaseExecutionResponse {
  phase: string;
  status: 'completed' | 'failed';
  phase_data: any;
  generated_files: GeneratedFile[];
  execution_time: number;
  error?: string;
}

interface GeneratedFile {
  id: string;
  filename: string;
  category: string;
  path: string;
  url: string;
  preview?: string;  // base64 for images, text for small files
}

class CMBAgentDiscoveryService {
  private baseUrl: string;
  private ws: WebSocket | null = null;
  private eventHandlers: Map<string, Function[]> = new Map();
  
  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }
  
  /**
   * Start a new discovery workflow
   */
  async startDiscovery(intakeData: IntakeFormData): Promise<DiscoveryStartResponse> {
    const response = await fetch(`${this.baseUrl}/api/discovery/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intake_data: intakeData })
    });
    
    if (!response.ok) {
      throw new Error(`Failed to start discovery: ${response.statusText}`);
    }
    
    const data = await response.json();
    
    // Connect to WebSocket for real-time updates
    this.connectWebSocket(data.run_id);
    
    return data;
  }
  
  /**
   * Execute a specific phase
   */
  async executePhase(
    runId: string,
    phaseName: string,
    phaseInputs?: Record<string, any>
  ): Promise<PhaseExecutionResponse> {
    const response = await fetch(
      `${this.baseUrl}/api/discovery/${runId}/execute-phase`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phase_name: phaseName,
          phase_inputs: phaseInputs
        })
      }
    );
    
    if (!response.ok) {
      throw new Error(`Failed to execute phase: ${response.statusText}`);
    }
    
    return await response.json();
  }
  
  /**
   * Get all outputs from discovery
   */
  async getOutputs(
    runId: string,
    format: 'api' | 'mcp' | 'tool' | 'download' = 'api'
  ): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}/api/discovery/${runId}/outputs?format=${format}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to get outputs: ${response.statusText}`);
    }
    
    return await response.json();
  }
  
  /**
   * Connect to WebSocket for real-time updates
   */
  private connectWebSocket(runId: string) {
    const wsUrl = `ws://localhost:8000/ws/discovery/${runId}`;
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleWebSocketEvent(message);
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket connection closed');
    };
  }
  
  /**
   * Subscribe to WebSocket events
   */
  on(eventType: string, handler: Function) {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, []);
    }
    this.eventHandlers.get(eventType)!.push(handler);
  }
  
  /**
   * Handle incoming WebSocket events
   */
  private handleWebSocketEvent(message: any) {
    const { event_type, data } = message;
    
    const handlers = this.eventHandlers.get(event_type) || [];
    handlers.forEach(handler => handler(data));
    
    // Also trigger 'all' handlers
    const allHandlers = this.eventHandlers.get('all') || [];
    allHandlers.forEach(handler => handler(message));
  }
  
  /**
   * Disconnect WebSocket
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const cmbAgentService = new CMBAgentDiscoveryService();
```

### 4.2 Enhanced React Components

```typescript
// src/components/steps/ResearchSummary.tsx (Enhanced Version)

import { useEffect, useState } from 'react';
import { cmbAgentService } from '@/lib/cmbagent-service';
import { FilePreview } from '@/components/FilePreview';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';

export function ResearchSummary({ intakeData, runId, initialData, onComplete }) {
  const [isLoading, setIsLoading] = useState(!initialData);
  const [data, setData] = useState(initialData || null);
  const [generatedFiles, setGeneratedFiles] = useState([]);
  const [phaseStatus, setPhaseStatus] = useState('');
  const [agentMessages, setAgentMessages] = useState([]);
  
  useEffect(() => {
    if (!initialData && runId) {
      executePhase();
    }
    
    // Subscribe to WebSocket events
    cmbAgentService.on('PHASE_STARTED', (data) => {
      if (data.phase === 'research') {
        setPhaseStatus('Phase started: Research');
      }
    });
    
    cmbAgentService.on('AGENT_MESSAGE', (data) => {
      setAgentMessages(prev => [...prev, data.content]);
    });
    
    cmbAgentService.on('FILE_CREATED', (data) => {
      setGeneratedFiles(prev => [...prev, data]);
      toast.success(`Generated: ${data.filename}`);
    });
    
    cmbAgentService.on('PHASE_COMPLETED', (data) => {
      if (data.phase === 'research') {
        setPhaseStatus('Research completed');
        toast.success('Research phase completed!');
      }
    });
    
    return () => {
      // Cleanup subscriptions if needed
    };
  }, []);
  
  const executePhase = async () => {
    setIsLoading(true);
    try {
      const result = await cmbAgentService.executePhase(runId, 'research');
      
      if (result.status === 'completed') {
        setData(result.phase_data);
        setGeneratedFiles(result.generated_files);
        onComplete(result.phase_data);
      } else {
        toast.error(`Phase failed: ${result.error}`);
      }
    } catch (error) {
      toast.error('Failed to execute research phase');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };
  
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Spinner className="w-12 h-12 text-primary mb-4" />
        <h3 className="text-xl font-semibold mb-2">Generating Research Summary</h3>
        <p className="text-muted-foreground">{phaseStatus}</p>
        
        {/* Real-time agent messages */}
        <div className="mt-8 w-full max-w-2xl">
          <h4 className="text-sm font-medium mb-2">Agent Activity:</h4>
          <div className="bg-muted/50 rounded-lg p-4 max-h-60 overflow-y-auto">
            {agentMessages.map((msg, idx) => (
              <div key={idx} className="text-sm mb-2 font-mono">
                {msg}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
  
  if (!data) {
    return null;
  }
  
  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      {/* Existing content display */}
      <div>
        <h2 className="text-3xl font-bold">Research Summary</h2>
        {/* ... existing UI ... */}
      </div>
      
      {/* NEW: Generated Files Section */}
      {generatedFiles.length > 0 && (
        <div className="border-t pt-6">
          <h3 className="text-xl font-semibold mb-4">Generated Files</h3>
          <div className="grid gap-4">
            {generatedFiles.map((file) => (
              <FilePreview
                key={file.id}
                file={file}
                onDownload={() => window.open(file.url, '_blank')}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

### 4.3 File Preview Component

```typescript
// src/components/FilePreview.tsx

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Download, FileText, Image, Code, FileJson } from 'lucide-react';

interface FilePreviewProps {
  file: GeneratedFile;
  onDownload: () => void;
}

export function FilePreview({ file, onDownload }: FilePreviewProps) {
  const getIcon = () => {
    switch (file.category) {
      case 'plot': return <Image className="w-5 h-5" />;
      case 'code': return <Code className="w-5 h-5" />;
      case 'data': return <FileJson className="w-5 h-5" />;
      default: return <FileText className="w-5 h-5" />;
    }
  };
  
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 flex-1">
          <div className="text-primary">{getIcon()}</div>
          <div className="flex-1">
            <h4 className="font-medium">{file.filename}</h4>
            <p className="text-sm text-muted-foreground">
              {file.category} • {(file.size_bytes / 1024).toFixed(2)} KB
            </p>
            
            {/* Preview if available */}
            {file.preview && file.category === 'plot' && (
              <div className="mt-3">
                <img 
                  src={`data:image/png;base64,${file.preview}`}
                  alt={file.filename}
                  className="max-w-full rounded border"
                />
              </div>
            )}
            
            {file.preview && file.category === 'data' && (
              <div className="mt-3">
                <pre className="bg-muted p-3 rounded text-xs overflow-x-auto">
                  {file.preview}
                </pre>
              </div>
            )}
          </div>
        </div>
        
        <Button variant="outline" size="sm" onClick={onDownload}>
          <Download className="w-4 h-4 mr-2" />
          Download
        </Button>
      </div>
    </Card>
  );
}
```

---

## Part 5: Complete Integration Flow Example

### Example: User Completes Full Discovery

```typescript
// High-level flow in Index.tsx

const [runId, setRunId] = useState<string | null>(null);
const [generatedFiles, setGeneratedFiles] = useState<Map<string, GeneratedFile[]>>(new Map());

// Step 1: User fills intake form
const handleIntakeSubmit = async (intakeData: IntakeFormData) => {
  const result = await cmbAgentService.startDiscovery(intakeData);
  setRunId(result.run_id);
  setState({ ...state, intakeData, currentStep: 1 });
};

// Step 2: Execute research phase
const handleResearchPhase = async () => {
  const result = await cmbAgentService.executePhase(runId!, 'research');
  setState({ ...state, researchSummary: result.phase_data, currentStep: 2 });
  setGeneratedFiles(prev => new Map(prev).set('research', result.generated_files));
};

// ... similar for other phases ...

// Step 9: Get all outputs
const handleGetFinalOutputs = async () => {
  const outputs = await cmbAgentService.getOutputs(runId!, 'api');
  
  // Display organized outputs
  setFinalOutputs({
    primary: outputs.primary_outputs,
    byPhase: outputs.outputs_by_step,
    downloadUrl: `/api/discovery/${runId}/download`
  });
};
```

---

## Part 6: MCP Server Integration

For exposing CMBAgent as an MCP server to other AI tools:

```python
# cmbagent/mcp/discovery_server.py

from mcp.server import Server
from mcp.types import Resource, Tool, TextContent, ImageContent

class DiscoveryMCPServer:
    """MCP server exposing product discovery workflows."""
    
    def __init__(self):
        self.server = Server("cmbagent-discovery")
        self._register_tools()
        self._register_resources()
    
    def _register_tools(self):
        @self.server.call_tool()
        async def run_product_discovery(arguments: dict) -> list:
            """
            Run a complete product discovery workflow.
            
            Returns structured outputs with embedded files.
            """
            # Start discovery
            service = DiscoveryWorkflowService(db, ws_manager)
            result = await service.start_discovery(
                intake_data=arguments['intake_data'],
                user_id='mcp_user'
            )
            run_id = result['run_id']
            
            # Execute all phases
            phases = ['research', 'problem_definition', 'opportunity_identification']
            for phase in phases:
                await service.execute_phase(run_id, phase)
            
            # Get outputs in MCP format
            outputs = await service.get_discovery_outputs(run_id, format='mcp')
            
            return outputs['content']  # List of TextContent/ImageContent
        
        @self.server.call_tool()
        async def execute_discovery_phase(arguments: dict) -> list:
            """Execute a single discovery phase."""
            service = DiscoveryWorkflowService(db, ws_manager)
            result = await service.execute_phase(
                run_id=arguments['run_id'],
                phase_name=arguments['phase_name'],
                phase_inputs=arguments.get('phase_inputs')
            )
            
            # Convert to MCP content format
            serializer = OutputSerializer(result, work_dir)
            return serializer.for_mcp_server()['content']
```

---

## Part 7: Benefits Summary

| Aspect | Before (Direct LLM) | After (CMBAgent Integration) |
|--------|---------------------|------------------------------|
| **Persistence** | localStorage only | Database + file system |
| **Artifacts** | None | All files tracked and organized |
| **Real-time Updates** | None | WebSocket events |
| **Code Execution** | Not possible | Full Python execution with tracking |
| **Provenance** | No tracking | Complete event and file lineage |
| **Collaboration** | Single user only | Multi-user with shared runs |
| **Output Formats** | JSON only | Multiple formats (API/MCP/download/ZIP) |
| **File Management** | Manual | Automatic categorization and tracking |
| **Error Recovery** | Start over | Resume from any phase |
| **Integration** | Standalone | MCP server + API + WebSocket |

---

## Part 8: Implementation Checklist

- [ ] **Phase 1: Backend Foundation**
  - [ ] Create DiscoveryPhase definitions
  - [ ] Implement DiscoveryWorkflowService
  - [ ] Add FastAPI endpoints
  - [ ] Add DiscoveryRun database model
  - [ ] Test single phase execution

- [ ] **Phase 2: File Management Integration**
  - [ ] Integrate FileRegistry with discovery service
  - [ ] Implement OutputSerializer
  - [ ] Add file preview generation
  - [ ] Test file tracking across phases

- [ ] **Phase 3: Frontend Integration**
  - [ ] Create CMBAgentDiscoveryService
  - [ ] Update React components with WebSocket support
  - [ ] Add FilePreview component
  - [ ] Add real-time progress indicators
  - [ ] Test end-to-end flow

- [ ] **Phase 4: MCP Integration**
  - [ ] Create DiscoveryMCPServer
  - [ ] Implement resource endpoints
  - [ ] Test with Claude Desktop / other MCP clients
  - [ ] Document MCP integration

---

## Conclusion

This integration transforms your PDA from a stateless UI calling LLM APIs into a **production-grade discovery platform** with:

1. ✅ **Complete file tracking** - Every artifact is captured and organized
2. ✅ **Real-time updates** - Users see progress as it happens
3. ✅ **Multi-format outputs** - API, MCP, downloads - all from one source
4. ✅ **Proper persistence** - Database + file system
5. ✅ **Code execution** - Can generate plots, analyze data, create documents
6. ✅ **Collaboration ready** - Multi-user, shareable runs
7. ✅ **Integration friendly** - MCP server for AI tool chains

The file management system ensures **nothing gets lost**, and outputs can be returned in whatever format the consumer needs.
