# Skill System Implementation Roadmap

**Extension to Stages 1-15**
**New Stages: 16-19**
**Estimated Time:** 4-6 weeks
**Dependencies:** Stages 1-9 complete (current state)

---

## Overview

This roadmap extends the existing 15-stage implementation plan to add a comprehensive **Skill Learning System**. The skill system enables CMBAgent to:

1. **Capture detailed agent execution** - Every agent interaction, reasoning, code generation, and tool usage
2. **Extract reusable skills** - Convert successful workflow runs into templates
3. **Match tasks to skills** - Automatically identify relevant skills for new tasks
4. **Execute with skills** - Run skill templates with adaptation
5. **Learn and improve** - Track skill performance and optimize over time

---

## Relationship to Existing Stages

### Builds Upon

- **Stage 2 (Database)** - Extends models with skill tables
- **Stage 4 (DAG System)** - Uses DAG templates for skill patterns
- **Stage 5 (WebSocket)** - Adds skill-related events
- **Stage 8 (Parallel Execution)** - Skills can include parallel patterns
- **Stage 9 (Branching)** - Skills created from successful branches

### Complements

- **Stage 6 (HITL)** - Skills can include approval points
- **Stage 7 (Retry)** - Skills track which retry patterns worked
- **Stage 13 (Cost Tracking)** - Skills track cost efficiency
- **Stage 14 (Observability)** - Skills add execution insights

---

## New Stages

### Stage 16: Agent Execution Logging & Instrumentation

**Phase:** 4 - Intelligence Layer
**Time Estimate:** 7-10 days
**Risk Level:** Medium

#### Objectives

1. Capture detailed agent-level execution within workflow steps
2. Log reasoning, tool usage, and code generation for each agent
3. Track agent transitions and decision points
4. Store intermediate artifacts and code versions
5. Enable fine-grained replay and debugging

#### Database Changes

**Extend `messages` table:**
```sql
ALTER TABLE messages ADD COLUMN agent_role VARCHAR(50);
ALTER TABLE messages ADD COLUMN reasoning TEXT;
ALTER TABLE messages ADD COLUMN tool_calls JSONB;
ALTER TABLE messages ADD COLUMN code_generated TEXT;
ALTER TABLE messages ADD COLUMN execution_result JSONB;
ALTER TABLE messages ADD COLUMN duration_seconds NUMERIC;
```

**Extend `workflow_steps` table:**
```sql
ALTER TABLE workflow_steps ADD COLUMN agent_transitions JSONB;
-- Stores: [{"from": "planner", "to": "engineer", "reason": "...", "timestamp": "..."}]

ALTER TABLE workflow_steps ADD COLUMN intermediate_artifacts JSONB;
-- Stores: [{"file": "plot_v1.py", "timestamp": "...", "superseded_by": "plot_v2.py"}]

ALTER TABLE workflow_steps ADD COLUMN context_snapshots JSONB;
-- Periodic snapshots of ContextVariables during step execution
```

**Extend `files` table:**
```sql
ALTER TABLE files ADD COLUMN created_by_agent VARCHAR(100);
ALTER TABLE files ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE files ADD COLUMN parent_file_id VARCHAR(36) REFERENCES files(id);
-- Tracks file evolution (plot_v1.py -> plot_v2.py -> plot_v3.py)
```

#### Components to Implement

##### 1. AgentExecutionLogger (`cmbagent/execution/agent_logger.py`)

```python
class AgentExecutionLogger:
    """Detailed logging of agent interactions within a step"""
    
    def __init__(self, db_session, run_id: str, step_id: str)
    def log_agent_start(self, agent_name: str, context: ContextVariables)
    def log_agent_reply(self, agent_name: str, reply: Dict, reasoning: str, tools: List)
    def log_code_execution(self, code: str, result: Dict)
    def log_tool_usage(self, tool_name: str, args: Dict, result: Any)
    def log_agent_transition(self, from_agent: str, to_agent: str, reason: str)
    def finalize_step_logging(self) -> StepExecutionSummary
```

##### 2. InstrumentedGroupChat (`cmbagent/execution/instrumented_groupchat.py`)

```python
class InstrumentedGroupChat(GroupChat):
    """GroupChat wrapper that logs all interactions"""
    
    def __init__(self, agents: List, logger: AgentExecutionLogger, **kwargs)
    def select_speaker(self, last_speaker, selector) -> ConversableAgent
    def append(self, message, speaker) -> None
    def _extract_reasoning(self, message: Dict) -> str
    def _extract_tool_calls(self, message: Dict) -> List[Dict]
```

##### 3. InstrumentedConversableAgent (`cmbagent/execution/instrumented_agent.py`)

```python
class InstrumentedConversableAgent(ConversableAgent):
    """ConversableAgent with logging hooks"""
    
    def __init__(self, logger: AgentExecutionLogger, **kwargs)
    def generate_reply(self, messages, sender, **kwargs) -> Dict
    def _log_before_reply(self, messages, sender)
    def _log_after_reply(self, reply, messages, sender)
```

##### 4. ArtifactTracker (`cmbagent/execution/artifact_tracker.py`)

```python
class ArtifactTracker:
    """Track file creation and evolution during workflow"""
    
    def __init__(self, work_dir: str, db_session, run_id: str, step_id: str)
    def track_file_creation(self, file_path: str, creator_agent: str)
    def track_file_modification(self, file_path: str, modifier_agent: str)
    def track_code_evolution(self, code_versions: List[str])
    def get_artifact_history(self, file_path: str) -> List[FileVersion]
```

#### Integration Points

**Modify `cmbagent/cmbagent.py`:**
```python
def _execute_step_with_logging(self, step_id: str, agents: List, context: ContextVariables):
    # Create logger
    agent_logger = AgentExecutionLogger(self.db_session, self.current_run_id, step_id)
    artifact_tracker = ArtifactTracker(self.work_dir, self.db_session, self.current_run_id, step_id)
    
    # Create instrumented GroupChat
    instrumented_agents = [
        InstrumentedConversableAgent(agent, logger=agent_logger)
        for agent in agents
    ]
    
    groupchat = InstrumentedGroupChat(
        agents=instrumented_agents,
        logger=agent_logger,
        messages=[],
        max_round=10
    )
    
    # Execute with logging
    manager = GroupChatManager(groupchat=groupchat, llm_config=self.llm_config)
    result = manager.run(context=context)
    
    # Finalize logging
    summary = agent_logger.finalize_step_logging()
    artifact_tracker.finalize()
    
    return result, summary
```

#### WebSocket Events

Add new event types:
```python
{
    "event": "AGENT_START",
    "data": {
        "agent": "engineer",
        "step_id": "step_5",
        "timestamp": "2026-01-19T10:30:00Z"
    }
}

{
    "event": "AGENT_REASONING",
    "data": {
        "agent": "engineer",
        "reasoning": "I'll create a plotting script using matplotlib...",
        "step_id": "step_5"
    }
}

{
    "event": "CODE_GENERATED",
    "data": {
        "agent": "engineer",
        "code": "import matplotlib.pyplot as plt\n...",
        "language": "python",
        "step_id": "step_5"
    }
}

{
    "event": "TOOL_USAGE",
    "data": {
        "agent": "researcher",
        "tool": "arxiv_search",
        "args": {"query": "dark energy"},
        "step_id": "step_5"
    }
}
```

#### Verification

1. ✅ All agent interactions logged to messages table
2. ✅ Reasoning and tool calls captured
3. ✅ Code generation tracked with versions
4. ✅ Agent transitions recorded
5. ✅ File artifacts linked to creators
6. ✅ WebSocket events emitted for agent actions
7. ✅ Context snapshots saved periodically
8. ✅ Performance overhead < 10%

#### API Endpoints

```python
# GET /api/runs/{run_id}/steps/{step_id}/interactions
# Returns: Detailed agent interaction log

# GET /api/runs/{run_id}/steps/{step_id}/artifacts
# Returns: All files created in step with evolution history

# GET /api/runs/{run_id}/agent-timeline
# Returns: Timeline of all agent activities
```

---

### Stage 17: Skill Extraction & Storage

**Phase:** 4 - Intelligence Layer
**Time Estimate:** 5-7 days
**Risk Level:** Low
**Dependencies:** Stage 16 complete

#### Objectives

1. Extract reusable skill templates from successful workflow runs
2. Store skills in database with searchable metadata
3. Capture DAG patterns, agent sequences, and code templates
4. Build skill artifact library
5. Enable manual skill creation via CLI and API

#### Database Schema

**New table: `skills`**
```sql
CREATE TABLE skills (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    tags JSONB,  -- ["physics", "plotting", "data_analysis"]
    
    -- Pattern matching
    task_pattern VARCHAR(500),
    input_schema JSONB,
    output_schema JSONB,
    
    -- Source
    source_run_id VARCHAR(36) REFERENCES workflow_runs(id),
    source_step_range VARCHAR(50),  -- "all" or "3-7"
    
    -- Execution template
    dag_template JSONB,
    agent_sequence JSONB,  -- ["planner", "engineer", "researcher"]
    context_requirements JSONB,
    
    -- Embeddings for similarity search
    task_embedding BLOB,  -- Vector embedding of task description
    embedding_model VARCHAR(100),  -- "all-MiniLM-L6-v2"
    
    -- Performance metrics
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    avg_execution_time_seconds NUMERIC,
    avg_cost_usd NUMERIC,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    created_by_user VARCHAR(36),
    
    -- Versioning
    version INTEGER DEFAULT 1,
    parent_skill_id VARCHAR(36) REFERENCES skills(id),
    
    -- Visibility
    is_public BOOLEAN DEFAULT FALSE,
    
    UNIQUE(name, version)
);

CREATE INDEX idx_skills_tags ON skills USING GIN(tags);
CREATE INDEX idx_skills_source_run ON skills(source_run_id);
CREATE INDEX idx_skills_success_rate ON skills(success_count, failure_count);
```

**New table: `skill_executions`**
```sql
CREATE TABLE skill_executions (
    id VARCHAR(36) PRIMARY KEY,
    skill_id VARCHAR(36) REFERENCES skills(id) ON DELETE CASCADE,
    run_id VARCHAR(36) REFERENCES workflow_runs(id) ON DELETE CASCADE,
    
    -- Execution details
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds NUMERIC,
    cost_usd NUMERIC,
    
    -- Adaptation tracking
    adapted BOOLEAN DEFAULT FALSE,
    adaptations JSONB,  -- What changed from template
    adaptation_reason TEXT,
    
    -- Outcome
    success BOOLEAN,
    error_message TEXT,
    
    -- Context
    task_description TEXT,
    context_diff JSONB,  -- How input context differed from template
    
    UNIQUE(skill_id, run_id)
);

CREATE INDEX idx_skill_executions_skill ON skill_executions(skill_id);
CREATE INDEX idx_skill_executions_success ON skill_executions(success);
```

**New table: `skill_artifacts`**
```sql
CREATE TABLE skill_artifacts (
    id VARCHAR(36) PRIMARY KEY,
    skill_id VARCHAR(36) REFERENCES skills(id) ON DELETE CASCADE,
    
    -- Artifact details
    artifact_type VARCHAR(50),  -- "code", "plot_template", "config", "data_schema"
    name VARCHAR(255),
    file_path VARCHAR(500),
    content TEXT,  -- Store small files directly
    description TEXT,
    language VARCHAR(50),  -- "python", "yaml", "json"
    
    -- Templates use {variable} syntax
    is_template BOOLEAN DEFAULT FALSE,
    template_variables JSONB,  -- ["data_file", "output_path"]
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    size_bytes INTEGER,
    checksum VARCHAR(64)
);

CREATE INDEX idx_skill_artifacts_skill ON skill_artifacts(skill_id);
CREATE INDEX idx_skill_artifacts_type ON skill_artifacts(artifact_type);
```

#### Components to Implement

##### 1. SkillExtractor (`cmbagent/skills/skill_extractor.py`)

```python
class SkillExtractor:
    """Extract reusable skills from workflow runs"""
    
    def extract_skill_from_run(
        self,
        run_id: str,
        step_range: str = "all",  # or "3-7"
        skill_name: str = None,
        tags: List[str] = None,
        description: str = None,
        make_public: bool = False
    ) -> Skill
    
    def _extract_dag_template(self, steps: List[WorkflowStep]) -> Dict
    def _extract_agent_sequence(self, steps: List[WorkflowStep]) -> List[str]
    def _extract_code_templates(self, files: List[File]) -> List[SkillArtifact]
    def _infer_input_schema(self, first_step: WorkflowStep) -> Dict
    def _infer_output_schema(self, last_step: WorkflowStep) -> Dict
    def _generalize_dag_pattern(self, dag: Dict) -> Dict
    def _create_task_pattern(self, task_description: str) -> str
    def _generate_embedding(self, text: str) -> np.ndarray
    def _auto_tag(self, run: WorkflowRun) -> List[str]
```

##### 2. SkillTemplateBuilder (`cmbagent/skills/template_builder.py`)

```python
class SkillTemplateBuilder:
    """Build executable templates from skill patterns"""
    
    def build_dag_template(self, skill: Skill) -> Dict
    def build_agent_instructions(self, skill: Skill, context: Dict) -> Dict
    def build_code_templates(self, skill: Skill, variables: Dict) -> List[str]
    def instantiate_template(self, template: str, variables: Dict) -> str
```

##### 3. SkillRepository (`cmbagent/database/skill_repository.py`)

```python
class SkillRepository(BaseRepository):
    """Data access for skills"""
    
    def create_skill(self, skill: Skill) -> str
    def get_skill_by_id(self, skill_id: str) -> Skill
    def get_skill_by_name(self, name: str, version: int = None) -> Skill
    def search_skills(self, query: str, tags: List[str] = None) -> List[Skill]
    def get_all_skills(self) -> List[Skill]
    def update_skill_metrics(self, skill_id: str, success: bool, duration: float, cost: float)
    def create_skill_execution(self, execution: SkillExecution) -> str
    def get_skill_executions(self, skill_id: str) -> List[SkillExecution]
    def get_skill_artifacts(self, skill_id: str) -> List[SkillArtifact]
```

#### CLI Commands

```bash
# Extract skill from completed workflow
cmbagent extract-skill <run_id> \
  --name "plot_power_spectrum" \
  --steps "4-7" \
  --tags "plotting,physics,power_spectrum" \
  --description "Generate power spectrum plots from CAMB output" \
  --public

# List all skills
cmbagent list-skills [--tags physics,plotting] [--sort success_rate]

# Show skill details
cmbagent show-skill <skill_name_or_id> [--version 2]

# Delete skill
cmbagent delete-skill <skill_id>

# Export skill to JSON
cmbagent export-skill <skill_id> --output skill.json

# Import skill from JSON
cmbagent import-skill --input skill.json
```

#### API Endpoints

```python
# POST /api/skills/extract
# Body: {run_id, step_range, name, tags, description}
# Returns: {skill_id}

# GET /api/skills
# Query: ?tags=physics,plotting&search=power_spectrum
# Returns: List[Skill]

# GET /api/skills/{skill_id}
# Returns: Skill with full details

# DELETE /api/skills/{skill_id}
# Returns: {success: true}

# GET /api/skills/{skill_id}/executions
# Returns: List[SkillExecution]

# GET /api/skills/{skill_id}/artifacts
# Returns: List[SkillArtifact]
```

#### Verification

1. ✅ Extract skill from successful workflow
2. ✅ DAG template captures execution pattern
3. ✅ Code templates generalized with variables
4. ✅ Artifacts stored and linked
5. ✅ Embeddings generated for similarity search
6. ✅ CLI commands work
7. ✅ API endpoints functional
8. ✅ Skills searchable by tags and text

---

### Stage 18: Skill Matching & Execution

**Phase:** 4 - Intelligence Layer
**Time Estimate:** 7-10 days
**Risk Level:** Medium
**Dependencies:** Stage 17 complete

#### Objectives

1. Match new tasks to existing skills using semantic similarity
2. Execute skill templates with context adaptation
3. Track skill performance and adaptations
4. Enable skill-guided agent execution
5. Provide confidence scores for skill matches

#### Components to Implement

##### 1. SkillMatcher (`cmbagent/skills/skill_matcher.py`)

```python
class SkillMatcher:
    """Match tasks to existing skills"""
    
    def __init__(
        self, 
        db_session,
        embedding_model: str = "all-MiniLM-L6-v2",
        cache_embeddings: bool = True
    )
    
    def find_matching_skills(
        self,
        task_description: str,
        top_k: int = 5,
        min_similarity: float = 0.7,
        required_tags: List[str] = None,
        exclude_failed: bool = True
    ) -> List[Tuple[Skill, float, Dict]]
    
    def explain_match(
        self,
        task_description: str,
        skill: Skill
    ) -> Dict[str, Any]
    
    def _compute_semantic_similarity(self, task_emb: np.ndarray, skill_emb: np.ndarray) -> float
    def _compute_tag_similarity(self, task: str, skill_tags: List[str]) -> float
    def _compute_structural_similarity(self, task: str, skill: Skill) -> float
    def _combine_similarity_scores(self, semantic: float, tag: float, structural: float) -> float
```

##### 2. SkillExecutor (`cmbagent/skills/skill_executor.py`)

```python
class SkillExecutor:
    """Execute skill templates"""
    
    def __init__(self, db_session, session_id: str, cmbagent_instance):
        self.db_session = db_session
        self.session_id = session_id
        self.cmbagent = cmbagent_instance
    
    def execute_skill(
        self,
        skill: Skill,
        task_context: Dict,
        allow_adaptation: bool = True,
        strict_mode: bool = False,  # Fail if template can't be followed
        callbacks: WorkflowCallbacks = None
    ) -> Dict[str, Any]
    
    def _instantiate_dag(self, skill: Skill, context: Dict) -> DAG
    def _create_skill_aware_prompts(self, skill: Skill, context: Dict) -> Dict
    def _inject_skill_knowledge(self, agents: List, skill: Skill)
    def _track_adaptations(self, skill: Skill, execution: Dict) -> List[Dict]
    def _evaluate_execution(self, skill: Skill, result: Dict) -> SkillExecution
```

##### 3. SkillAdaptationTracker (`cmbagent/skills/adaptation_tracker.py`)

```python
class SkillAdaptationTracker:
    """Track how skills are adapted during execution"""
    
    def track_dag_modification(self, original: Dict, modified: Dict) -> Dict
    def track_agent_deviation(self, expected: str, actual: str, reason: str) -> Dict
    def track_code_modification(self, template: str, actual: str) -> Dict
    def track_parameter_changes(self, template_params: Dict, actual_params: Dict) -> Dict
    def summarize_adaptations(self, adaptations: List[Dict]) -> Dict
    def should_update_skill(self, adaptations: List[Dict]) -> bool
```

##### 4. SkillPerformanceTracker (`cmbagent/skills/performance_tracker.py`)

```python
class SkillPerformanceTracker:
    """Track and analyze skill performance over time"""
    
    def record_execution(self, skill_execution: SkillExecution)
    def get_skill_metrics(self, skill_id: str) -> Dict
    def get_success_rate(self, skill_id: str, window_days: int = 30) -> float
    def get_avg_execution_time(self, skill_id: str) -> float
    def get_avg_cost(self, skill_id: str) -> float
    def get_adaptation_frequency(self, skill_id: str) -> float
    def recommend_skill_update(self, skill_id: str) -> Dict
```

#### Integration with CMBAgent

**Modify `cmbagent/cmbagent.py`:**

```python
class CMBAgent:
    
    def __init__(self, ..., enable_skills: bool = True, skill_mode: str = "auto"):
        # ... existing init ...
        
        self.enable_skills = enable_skills
        self.skill_mode = skill_mode  # "auto", "manual", "off"
        
        if self.enable_skills and self.use_database:
            from cmbagent.skills.skill_matcher import SkillMatcher
            from cmbagent.skills.skill_executor import SkillExecutor
            from cmbagent.skills.performance_tracker import SkillPerformanceTracker
            
            self.skill_matcher = SkillMatcher(self.db_session)
            self.skill_executor = SkillExecutor(self.db_session, self.session_id, self)
            self.skill_performance = SkillPerformanceTracker(self.db_session)
    
    def one_shot(
        self,
        task: str,
        use_skill: str = None,  # Specific skill to use
        auto_match_skill: bool = True,  # Auto-find matching skill
        create_skill: bool = False,  # Create skill after success
        skill_name: str = None,
        **kwargs
    ):
        """Enhanced with skill support"""
        
        # 1. Try to use skill if requested or auto-match enabled
        if self.enable_skills:
            skill_to_use = None
            
            # Explicit skill specified
            if use_skill:
                skill_to_use = self.db_session.query(Skill).filter_by(name=use_skill).first()
                if not skill_to_use:
                    print(f"Warning: Skill '{use_skill}' not found. Continuing without skill.")
            
            # Auto-match
            elif auto_match_skill and self.skill_mode == "auto":
                matches = self.skill_matcher.find_matching_skills(task, top_k=1, min_similarity=0.75)
                if matches:
                    skill_to_use, score, explanation = matches[0]
                    print(f"🎯 Matched skill: {skill_to_use.name} (confidence: {score:.2f})")
                    print(f"   Reason: {explanation['reason']}")
                    
                    # Ask user to confirm (if in interactive mode)
                    if self.approval_config.mode != ApprovalMode.NONE:
                        confirm = input("Use this skill? (y/n): ")
                        if confirm.lower() != 'y':
                            skill_to_use = None
            
            # Execute with skill
            if skill_to_use:
                result = self.skill_executor.execute_skill(
                    skill_to_use,
                    task_context={'task': task, **kwargs},
                    allow_adaptation=True,
                    callbacks=kwargs.get('callbacks')
                )
                return {
                    'run_id': result['run_id'],
                    'skill_used': skill_to_use.name,
                    'adapted': result.get('adapted', False),
                    'adaptations': result.get('adaptations'),
                    **result
                }
        
        # 2. Normal execution (no skill)
        run_id = super().one_shot(task, **kwargs)
        
        # 3. Create skill if requested and successful
        if create_skill and self.enable_skills:
            run = self.db_session.query(WorkflowRun).filter_by(id=run_id).first()
            if run.status == "completed":
                skill = self.skill_extractor.extract_skill_from_run(
                    run_id,
                    skill_name=skill_name or f"skill_from_{task[:30]}",
                    tags=self._auto_tag_task(task)
                )
                print(f"✨ Created skill: {skill.name}")
                return {'run_id': run_id, 'skill_created': skill.name}
        
        return {'run_id': run_id}
```

#### WebSocket Events

```python
{
    "event": "SKILL_MATCHED",
    "data": {
        "skill_name": "plot_power_spectrum",
        "confidence": 0.87,
        "explanation": "Task involves plotting power spectra from CAMB data"
    }
}

{
    "event": "SKILL_EXECUTION_START",
    "data": {
        "skill_id": "skill-123",
        "skill_name": "plot_power_spectrum",
        "run_id": "run-456"
    }
}

{
    "event": "SKILL_ADAPTED",
    "data": {
        "skill_name": "plot_power_spectrum",
        "adaptations": [
            {"type": "parameter_change", "parameter": "output_format", "from": "png", "to": "pdf"},
            {"type": "agent_added", "agent": "data_validator"}
        ],
        "reason": "User requested PDF output instead of PNG"
    }
}

{
    "event": "SKILL_EXECUTION_COMPLETE",
    "data": {
        "skill_id": "skill-123",
        "success": true,
        "duration_seconds": 45.2,
        "cost_usd": 0.12,
        "adapted": true
    }
}
```

#### CLI Enhancements

```bash
# Run with specific skill
cmbagent one-shot "Plot power spectrum" --use-skill plot_power_spectrum

# Run with auto-matching (default)
cmbagent one-shot "Create power spectrum visualization"

# Run and create skill from result
cmbagent one-shot "Plot PS data" --create-skill --skill-name my_ps_plotter

# Show skill performance
cmbagent skill-stats plot_power_spectrum

# Compare skill executions
cmbagent compare-skill-runs skill-123 run-1 run-2 run-3
```

#### API Endpoints

```python
# POST /api/skills/match
# Body: {task_description, top_k, min_similarity, required_tags}
# Returns: List[{skill, confidence, explanation}]

# POST /api/skills/{skill_id}/execute
# Body: {task_context, allow_adaptation, strict_mode}
# Returns: {run_id, adapted, adaptations, result}

# GET /api/skills/{skill_id}/performance
# Returns: {success_rate, avg_time, avg_cost, adaptation_rate}

# GET /api/skills/{skill_id}/executions/{execution_id}
# Returns: SkillExecution with full details
```

#### Verification

1. ✅ Semantic similarity matching works (>0.7 for similar tasks)
2. ✅ Skills execute with correct DAG template
3. ✅ Agent prompts include skill context
4. ✅ Adaptations tracked and stored
5. ✅ Performance metrics updated after each execution
6. ✅ Failed skills don't prevent fallback to normal execution
7. ✅ WebSocket events emitted
8. ✅ CLI commands functional

---

### Stage 19: Skill Optimization & Intelligence

**Phase:** 4 - Intelligence Layer
**Time Estimate:** 5-7 days
**Risk Level:** Low
**Dependencies:** Stage 18 complete

#### Objectives

1. Automatically improve skills based on execution history
2. Create new skills by composing existing ones
3. Recommend skills for optimization
4. Build skill analytics dashboard
5. Enable skill versioning and rollback

#### Components to Implement

##### 1. SkillOptimizer (`cmbagent/skills/skill_optimizer.py`)

```python
class SkillOptimizer:
    """Automatically improve skills"""
    
    def analyze_skill_executions(
        self,
        skill_id: str,
        min_executions: int = 10
    ) -> Dict[str, Any]
    
    def recommend_optimizations(
        self,
        skill_id: str
    ) -> List[Dict[str, str]]
    
    def create_optimized_version(
        self,
        skill_id: str,
        optimizations: List[Dict]
    ) -> Skill
    
    def _find_common_adaptations(self, executions: List[SkillExecution]) -> List[Dict]
    def _identify_failure_patterns(self, executions: List[SkillExecution]) -> List[Dict]
    def _suggest_dag_improvements(self, skill: Skill, executions: List) -> List[Dict]
    def _suggest_prompt_improvements(self, skill: Skill, executions: List) -> List[Dict]
```

##### 2. SkillComposer (`cmbagent/skills/skill_composer.py`)

```python
class SkillComposer:
    """Compose new skills from existing ones"""
    
    def compose_skills(
        self,
        skill_ids: List[str],
        composition_pattern: str = "sequential",  # or "parallel", "conditional"
        name: str = None
    ) -> Skill
    
    def find_composable_skills(
        self,
        task: str
    ) -> List[List[Skill]]
    
    def _merge_dag_templates(self, skills: List[Skill], pattern: str) -> Dict
    def _merge_agent_sequences(self, skills: List[Skill]) -> List[str]
    def _merge_context_requirements(self, skills: List[Skill]) -> Dict
```

##### 3. SkillVersionManager (`cmbagent/skills/version_manager.py`)

```python
class SkillVersionManager:
    """Manage skill versions"""
    
    def create_new_version(
        self,
        skill_id: str,
        changes: Dict,
        reason: str
    ) -> Skill
    
    def get_skill_versions(self, skill_name: str) -> List[Skill]
    
    def rollback_to_version(self, skill_name: str, version: int) -> Skill
    
    def compare_versions(
        self,
        skill_name: str,
        version1: int,
        version2: int
    ) -> Dict
```

##### 4. SkillAnalytics (`cmbagent/skills/analytics.py`)

```python
class SkillAnalytics:
    """Analytics and insights for skills"""
    
    def get_skill_dashboard_data(self, skill_id: str) -> Dict
    def get_top_performing_skills(self, limit: int = 10) -> List[Tuple[Skill, Dict]]
    def get_skill_usage_trends(self, skill_id: str, days: int = 30) -> Dict
    def get_skill_cost_analysis(self, skill_id: str) -> Dict
    def get_adaptation_heatmap(self, skill_id: str) -> Dict
    def recommend_skill_consolidation(self) -> List[Tuple[Skill, Skill, float]]
```

#### CLI Commands

```bash
# Analyze skill and recommend optimizations
cmbagent optimize-skill plot_power_spectrum

# Create optimized version
cmbagent optimize-skill plot_power_spectrum --apply --reason "Reduce execution time"

# Compose skills
cmbagent compose-skills \
  --skills data_loader,data_processor,plotter \
  --pattern sequential \
  --name complete_data_pipeline

# Show skill versions
cmbagent skill-versions plot_power_spectrum

# Rollback to previous version
cmbagent rollback-skill plot_power_spectrum --version 2

# Analytics
cmbagent skill-analytics --top 10
cmbagent skill-usage plot_power_spectrum --days 30
```

#### API Endpoints

```python
# POST /api/skills/{skill_id}/analyze
# Returns: {current_performance, recommendations, optimization_potential}

# POST /api/skills/{skill_id}/optimize
# Body: {apply_optimizations: bool, reason: str}
# Returns: {new_version, changes}

# POST /api/skills/compose
# Body: {skill_ids, pattern, name}
# Returns: {skill_id}

# GET /api/skills/{skill_name}/versions
# Returns: List[Skill]

# POST /api/skills/{skill_name}/rollback
# Body: {version}
# Returns: {success, skill_id}

# GET /api/analytics/skills/top
# Query: ?metric=success_rate&limit=10
# Returns: List[{skill, metrics}]

# GET /api/analytics/skills/{skill_id}/dashboard
# Returns: Complete analytics for skill
```

#### Verification

1. ✅ Common adaptations identified correctly
2. ✅ Optimized versions created successfully
3. ✅ Skills composed correctly
4. ✅ Version rollback works
5. ✅ Analytics dashboard shows accurate data
6. ✅ Recommendations are actionable
7. ✅ Performance improves with optimizations

---

## Summary Comparison

### Original Stages (1-15)

| Stage | Component | Status |
|-------|-----------|--------|
| 1 | AG2 Upgrade | ✅ Complete |
| 2 | Database Schema | ✅ Complete |
| 3 | State Machine | ✅ Complete |
| 4 | DAG System | ✅ Complete |
| 5 | WebSocket Events | ✅ Complete |
| 6 | HITL Approval | ✅ Complete |
| 7 | Context-Aware Retry | ✅ Complete |
| 8 | Parallel Execution | ✅ Complete |
| 9 | Branching | ✅ Complete |
| 10 | MCP Server | 🔄 Planned |
| 11 | MCP Client | 🔄 Planned |
| 12 | Agent Registry | 🔄 Planned |
| 13 | Cost Tracking | 🔄 Planned |
| 14 | Observability | 🔄 Planned |
| 15 | Policy Engine | 🔄 Planned |

### New Skill System Stages (16-19)

| Stage | Component | Dependencies | Time |
|-------|-----------|--------------|------|
| 16 | Agent Execution Logging | 2, 5 | 7-10 days |
| 17 | Skill Extraction | 16 | 5-7 days |
| 18 | Skill Matching & Execution | 17 | 7-10 days |
| 19 | Skill Optimization | 18 | 5-7 days |

**Total Time:** 24-34 days (4-6 weeks)

---

## Long-Task Considerations

### Scalability Enhancements for Multi-Day Workflows

#### 1. Message Pagination & Streaming

```python
class MessageRepository:
    def get_messages_streaming(
        self,
        run_id: str,
        chunk_size: int = 100
    ) -> Iterator[List[Message]]:
        """Stream messages in chunks to avoid memory issues"""
        offset = 0
        while True:
            chunk = self.db_session.query(Message)\
                .filter_by(run_id=run_id)\
                .order_by(Message.timestamp)\
                .offset(offset)\
                .limit(chunk_size)\
                .all()
            
            if not chunk:
                break
            
            yield chunk
            offset += chunk_size
```

#### 2. Context Summarization

```python
class ContextSummarizer:
    """Summarize long contexts for token efficiency"""
    
    def summarize_old_messages(
        self,
        messages: List[Message],
        keep_recent: int = 20,
        max_summary_tokens: int = 2000
    ) -> str:
        """
        Keep recent messages verbatim, summarize older ones.
        Critical for multi-day workflows with 10,000+ messages.
        """
        
        recent = messages[-keep_recent:]
        old = messages[:-keep_recent]
        
        # Summarize in batches
        summaries = []
        for batch in self._batch_messages(old, batch_size=50):
            summary = self._llm_summarize(batch, max_tokens=max_summary_tokens // len(batches))
            summaries.append(summary)
        
        full_summary = "\n\n".join(summaries)
        return full_summary
```

#### 3. Incremental Skill Extraction

```python
class IncrementalSkillExtractor:
    """Extract skills from in-progress workflows"""
    
    def extract_partial_skill(
        self,
        run_id: str,
        completed_steps: List[int],
        skill_name: str = None
    ) -> Skill:
        """
        Create skill from subset of completed steps.
        Useful for very long workflows where early patterns emerge.
        """
        # Extract DAG pattern from completed steps only
        # This allows learning before full workflow completes
```

#### 4. Checkpoint-Based Recovery

Your existing checkpoint system (Stage 2) already supports this, but enhance for skills:

```python
class SkillCheckpointManager:
    """Manage checkpoints during skill execution"""
    
    def create_skill_checkpoint(
        self,
        skill_execution_id: str,
        step_number: int,
        context: ContextVariables
    ):
        """Save checkpoint during skill execution"""
        
    def resume_skill_from_checkpoint(
        self,
        skill_execution_id: str,
        checkpoint_id: str
    ) -> ContextVariables:
        """Resume skill execution from saved checkpoint"""
```

### Database Sizing for Long Tasks

| Duration | Messages | DB Size | Optimizations |
|----------|----------|---------|---------------|
| 1 hour | ~500 | 5 MB | None needed |
| 8 hours | ~4,000 | 40 MB | None needed |
| 1 day | ~12,000 | 120 MB | Message pagination |
| 3 days | ~36,000 | 360 MB | Context summarization |
| 1 week | ~84,000 | 840 MB | PostgreSQL + summarization |
| 1 month | ~336,000 | 3.4 GB | PostgreSQL + partitioning |

**Recommendations:**
- **SQLite:** Good for < 1 week workflows
- **PostgreSQL:** Required for 1+ week workflows
- **Message Partitioning:** Archive old messages after 7 days
- **Context Summarization:** Enable for workflows > 24 hours

---

## Integration Examples

### Example 1: One-Shot with Auto-Skill

```python
from cmbagent import CMBAgent

agent = CMBAgent(
    enable_skills=True,
    skill_mode="auto",  # Auto-match skills
    model="gpt-4"
)

# Task similar to previous skill
result = agent.one_shot(
    task="Plot power spectrum from CAMB data in data.txt",
    auto_match_skill=True
)

print(f"Used skill: {result.get('skill_used', 'None')}")
print(f"Adapted: {result.get('adapted', False)}")
```

### Example 2: Create Skill from Workflow

```python
# Run workflow
result = agent.one_shot(
    task="Process survey data and create visualizations",
    create_skill=True,
    skill_name="survey_data_pipeline"
)

# Skill automatically created if successful
if 'skill_created' in result:
    print(f"New skill created: {result['skill_created']}")
```

### Example 3: Explicit Skill Usage

```python
# Use specific skill
result = agent.one_shot(
    task="Process new survey batch",
    use_skill="survey_data_pipeline"
)
```

### Example 4: Skill Optimization

```python
from cmbagent.skills.skill_optimizer import SkillOptimizer

optimizer = SkillOptimizer(agent.db_session)

# Analyze skill after 20 executions
analysis = optimizer.analyze_skill_executions("survey_data_pipeline", min_executions=20)

print(f"Success rate: {analysis['success_rate']}")
print(f"Common adaptations: {analysis['common_adaptations']}")

# Apply optimizations
if analysis['recommendations']:
    optimized = optimizer.create_optimized_version(
        "survey_data_pipeline",
        optimizations=analysis['recommendations']
    )
    print(f"Created optimized version: v{optimized.version}")
```

---

## Migration Path

### From Current State (Stages 1-9) to Skills

#### Phase 1: Enable Execution Logging (Week 1-2)
1. Deploy Stage 16 (Agent Execution Logging)
2. Run existing workflows with logging enabled
3. Verify all interactions captured
4. No impact on existing functionality

#### Phase 2: Manual Skill Creation (Week 3)
1. Deploy Stage 17 (Skill Extraction)
2. Extract 3-5 skills from successful workflows manually
3. Test skill storage and retrieval
4. Build initial skill library

#### Phase 3: Auto-Matching (Week 4-5)
1. Deploy Stage 18 (Skill Matching & Execution)
2. Enable auto-matching in test mode (suggestions only)
3. Collect user feedback on matches
4. Tune similarity thresholds

#### Phase 4: Optimization (Week 6)
1. Deploy Stage 19 (Skill Optimization)
2. Analyze first wave of skill executions
3. Create optimized versions
4. Enable full skill system

---

## Success Metrics

### Stage 16 Metrics
- ✅ 100% of agent interactions logged
- ✅ Reasoning captured for >80% of agent responses
- ✅ Code versions tracked for all generated code
- ✅ <10% performance overhead

### Stage 17 Metrics
- ✅ Successfully extract skill from 90%+ of successful workflows
- ✅ DAG templates instantiate correctly
- ✅ Code templates generalize (variables extracted)
- ✅ Artifacts linked correctly

### Stage 18 Metrics
- ✅ >70% match accuracy for similar tasks (precision)
- ✅ >90% of matched skills execute successfully
- ✅ Adaptations tracked in >95% of cases
- ✅ <15% overhead for skill matching

### Stage 19 Metrics
- ✅ Optimized skills show >20% improvement (time or cost)
- ✅ Composed skills work correctly
- ✅ Rollback succeeds 100% of time
- ✅ Analytics accurate within 5%

---

## Conclusion

The skill system is a **natural evolution** of your existing architecture. It leverages:
- Stage 2's database for skill storage
- Stage 4's DAG system for execution templates
- Stage 5's events for real-time feedback
- Stage 8's parallel execution for skill patterns
- Stage 9's branching for skill variations

**Key Benefits:**
1. **10x faster** execution for known tasks (skip planning, use template)
2. **Lower costs** (reuse proven approaches, avoid trial-and-error)
3. **Knowledge accumulation** (build skill library over time)
4. **Team collaboration** (share skills across users)
5. **Continuous improvement** (skills optimize automatically)

**For very long tasks** (days/weeks), the combination of:
- Checkpoints
- Message pagination
- Context summarization
- PostgreSQL migration

...ensures the system remains responsive and reliable.

**Next Steps:**
1. Complete Stages 10-15 (MCP, Cost Tracking, Observability, Policy)
2. Implement Stage 16 (Agent Logging) - **foundation for everything else**
3. Build out Stages 17-19 incrementally
4. Collect feedback and iterate

The skill system will transform CMBAgent from a workflow executor into a **learning system** that gets smarter with each task.
