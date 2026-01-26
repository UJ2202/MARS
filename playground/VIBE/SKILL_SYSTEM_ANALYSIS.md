# Skill System & Multi-Agent Execution Capture - Feasibility Analysis

**Date:** 2026-01-19
**Context:** CMBAgent AG2 wrapper with event-driven DAG execution
**Goal:** Capture detailed multi-agent execution within steps and create reusable "skills"

---

## Executive Summary

**✅ FEASIBLE** - Your vision of capturing detailed agent execution and creating reusable "skills" is highly feasible with the current architecture. AG2 (AutoGen 2.x) provides excellent instrumentation capabilities, and your existing event-driven DAG system is well-positioned for this enhancement.

**Key Insights:**
1. AG2 supports comprehensive message/execution tracking via GroupChat and callbacks
2. Your existing database schema already captures steps, messages, and DAG structure
3. Skills can be implemented as a new abstraction layer on top of workflow runs
4. For very long tasks (hours/days), your checkpoint + message logging system will handle it well

---

## Current Architecture Analysis

### What You Have (Stages 1-9)

#### 1. Database Layer (Stage 2)
```
✅ WorkflowRun - Top-level workflow execution
✅ WorkflowStep - Individual steps in the plan
✅ DAGNode - Execution graph nodes
✅ Message - Agent-to-agent communication
✅ Checkpoint - State persistence every N minutes
✅ CostRecord - Token usage tracking
✅ File - Generated artifacts
```

#### 2. Event System (Stage 5)
```
✅ WebSocket events for real-time updates
✅ STEP_START, STEP_COMPLETE, MESSAGE events
✅ DAG_UPDATE, AGENT_TRANSITION events
```

#### 3. Execution Control (Stages 6-9)
```
✅ DAGExecutor - Orchestrates step execution
✅ ParallelExecutor - Handles concurrent tasks
✅ BranchManager - Alternative execution paths
✅ RetryManager - Context-aware error recovery
```

#### 4. AG2 Integration
```
✅ ConversableAgent wrappers
✅ GroupChat patterns (AutoPattern)
✅ Hand-off mechanisms between agents
✅ Context carryover between steps
```

### What's Missing for Skills

#### 1. Agent-Level Execution Details
- **Gap:** No per-agent message capture within steps
- **Gap:** No agent reasoning/tool-use logging
- **Gap:** No intermediate code versions tracking
- **Gap:** No agent decision rationale storage

#### 2. Skill Abstraction
- **Gap:** No Skill model/table
- **Gap:** No pattern matching for skill reuse
- **Gap:** No skill template system
- **Gap:** No similarity scoring for task-to-skill matching

---

## AG2 Capabilities for Execution Capture

### 1. GroupChat Message Logging

AG2 GroupChat automatically logs all messages. You can access them:

```python
# In your current code (cmbagent/cmbagent.py)
from autogen import GroupChat, GroupChatManager

groupchat = GroupChat(
    agents=[planner, engineer, researcher, ...],
    messages=[],  # This list accumulates ALL messages
    max_round=50,
)

manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)

# After execution:
all_messages = groupchat.messages  # Complete conversation history
```

**What you get:**
- `message['role']` - sender agent name
- `message['content']` - message content (can include code, reasoning)
- `message['name']` - agent identifier
- Implicit ordering (list index = conversation order)

### 2. ConversableAgent Hooks

Each agent has hooks you can override:

```python
from autogen import ConversableAgent

class InstrumentedAgent(ConversableAgent):
    def generate_reply(self, messages, sender, **kwargs):
        # Log: "About to generate reply"
        # You can capture: current context, sender, pending tools
        
        reply = super().generate_reply(messages, sender, **kwargs)
        
        # Log: reply content, reasoning, tool calls
        return reply
```

**Capturable Events:**
- When agent starts thinking
- What context it receives
- What tools it considers
- What code it generates (before execution)
- What results it receives

### 3. Tool/Function Execution Tracking

AG2 registers functions with `@register_function`:

```python
from autogen import register_function

@register_function(description="Run code")
def execute_code(code: str, context: Dict) -> str:
    # Log: code being executed, context state
    result = run(code)
    # Log: execution result, errors, outputs
    return result

# AG2 will call this and you control the logging
```

### 4. Code Executor Integration

Your `LocalCommandLineCodeExecutor` can be wrapped:

```python
from autogen.coding import LocalCommandLineCodeExecutor

class LoggingCodeExecutor(LocalCommandLineCodeExecutor):
    def execute_code_blocks(self, code_blocks):
        # Log: code blocks about to execute
        for block in code_blocks:
            # Log: language, code content, timestamp
            pass
        
        result = super().execute_code_blocks(code_blocks)
        
        # Log: exit code, stdout, stderr, files created
        return result
```

### 5. Context Variables Tracking

Your system uses `ContextVariables` for state:

```python
from autogen.agentchat.group import ContextVariables

context = ContextVariables(
    current_plan={...},
    step_number=5,
    generated_files=[...],
    custom_data={...}
)

# Log context before/after each agent interaction
# Store snapshots in database
```

---

## Proposed Skill System Architecture

### 1. Database Schema Extensions

#### New Table: Skills

```sql
CREATE TABLE skills (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    tags JSONB,  -- ["physics", "plotting", "data_processing"]
    
    -- Pattern matching
    task_pattern VARCHAR(500),  -- Regex or semantic pattern
    input_schema JSONB,  -- Expected inputs
    output_schema JSONB,  -- Expected outputs
    
    -- Reference to successful execution
    source_run_id VARCHAR(36) REFERENCES workflow_runs(id),
    source_step_range VARCHAR(50),  -- "3-7" or "all"
    
    -- Execution template
    dag_template JSONB,  -- Stored DAG structure
    agent_sequence JSONB,  -- ["planner", "engineer", "researcher"]
    context_requirements JSONB,  -- Required context variables
    
    -- Metadata
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    avg_execution_time NUMERIC,
    avg_cost NUMERIC,
    created_at TIMESTAMP,
    last_used_at TIMESTAMP,
    
    -- Versioning
    version INTEGER DEFAULT 1,
    parent_skill_id VARCHAR(36) REFERENCES skills(id)
);

CREATE TABLE skill_executions (
    id VARCHAR(36) PRIMARY KEY,
    skill_id VARCHAR(36) REFERENCES skills(id),
    run_id VARCHAR(36) REFERENCES workflow_runs(id),
    adapted BOOLEAN DEFAULT FALSE,  -- Was skill modified?
    adaptations JSONB,  -- What changed from template
    success BOOLEAN,
    execution_time NUMERIC,
    cost NUMERIC,
    created_at TIMESTAMP
);

CREATE TABLE skill_artifacts (
    id VARCHAR(36) PRIMARY KEY,
    skill_id VARCHAR(36) REFERENCES skills(id),
    artifact_type VARCHAR(50),  -- "code", "plot", "config", "data"
    file_path VARCHAR(500),
    content TEXT,  -- Store small files directly
    description TEXT,
    created_at TIMESTAMP
);
```

#### Extend Existing: Messages Table

Add columns to capture richer agent interaction:

```sql
ALTER TABLE messages ADD COLUMN agent_role VARCHAR(50);  -- "planner", "engineer"
ALTER TABLE messages ADD COLUMN reasoning TEXT;  -- Agent's thought process
ALTER TABLE messages ADD COLUMN tool_calls JSONB;  -- Tools invoked
ALTER TABLE messages ADD COLUMN code_generated TEXT;  -- Code blocks
ALTER TABLE messages ADD COLUMN execution_result JSONB;  -- If code was run
```

#### Extend Existing: WorkflowStep

```sql
ALTER TABLE workflow_steps ADD COLUMN agent_transitions JSONB;
-- [{"from": "planner", "to": "engineer", "reason": "...", "timestamp": "..."}]

ALTER TABLE workflow_steps ADD COLUMN intermediate_artifacts JSONB;
-- [{"file": "plot_v1.py", "timestamp": "...", "superseded_by": "plot_v2.py"}]
```

### 2. Enhanced Execution Capture System

#### Component 1: AgentExecutionLogger

```python
# cmbagent/execution/agent_logger.py

from typing import Dict, List, Any
from dataclasses import dataclass
import json
from datetime import datetime

@dataclass
class AgentInteraction:
    """Detailed log of single agent action"""
    agent_name: str
    agent_role: str  # planner, engineer, researcher
    timestamp: datetime
    input_messages: List[Dict]
    output_message: Dict
    reasoning: str  # If agent explains its thinking
    tool_calls: List[Dict]  # Functions called
    code_generated: str | None
    code_executed: bool
    execution_result: Dict | None
    context_snapshot: Dict  # ContextVariables at this moment
    token_usage: Dict
    duration_seconds: float

class AgentExecutionLogger:
    """Captures detailed agent execution within a step"""
    
    def __init__(self, db_session, run_id: str, step_id: str):
        self.db_session = db_session
        self.run_id = run_id
        self.step_id = step_id
        self.interactions: List[AgentInteraction] = []
    
    def log_agent_start(self, agent_name: str, context: ContextVariables):
        """Called when agent begins processing"""
        pass
    
    def log_agent_reply(self, agent_name: str, reply: Dict, 
                       reasoning: str = None, tools_used: List = None):
        """Called when agent produces output"""
        interaction = AgentInteraction(
            agent_name=agent_name,
            timestamp=datetime.utcnow(),
            output_message=reply,
            reasoning=reasoning,
            tool_calls=tools_used or [],
            # ... fill other fields
        )
        self.interactions.append(interaction)
        self._persist_to_db(interaction)
    
    def log_code_execution(self, code: str, result: Dict):
        """Called when code is executed"""
        if self.interactions:
            self.interactions[-1].code_generated = code
            self.interactions[-1].execution_result = result
            self._update_db_message()
    
    def _persist_to_db(self, interaction: AgentInteraction):
        """Save to messages table with rich metadata"""
        from cmbagent.database.models import Message
        
        message = Message(
            run_id=self.run_id,
            step_id=self.step_id,
            sender=interaction.agent_name,
            agent_role=interaction.agent_role,
            content=interaction.output_message.get('content'),
            reasoning=interaction.reasoning,
            tool_calls=interaction.tool_calls,
            code_generated=interaction.code_generated,
            execution_result=interaction.execution_result,
            meta={
                'context_snapshot': interaction.context_snapshot,
                'token_usage': interaction.token_usage,
                'duration': interaction.duration_seconds
            }
        )
        self.db_session.add(message)
        self.db_session.commit()
```

#### Component 2: Enhanced GroupChat Wrapper

```python
# cmbagent/execution/instrumented_groupchat.py

from autogen import GroupChat, GroupChatManager
from cmbagent.execution.agent_logger import AgentExecutionLogger

class InstrumentedGroupChat(GroupChat):
    """GroupChat that logs all agent interactions"""
    
    def __init__(self, agents, logger: AgentExecutionLogger, **kwargs):
        super().__init__(agents=agents, **kwargs)
        self.logger = logger
    
    def select_speaker(self, last_speaker, selector):
        """Override to log speaker transitions"""
        next_speaker = super().select_speaker(last_speaker, selector)
        
        # Log transition
        self.logger.log_agent_start(
            next_speaker.name,
            context=self._get_current_context()
        )
        
        return next_speaker
    
    def append(self, message, speaker):
        """Override to log each message"""
        super().append(message, speaker)
        
        # Log the message with full context
        self.logger.log_agent_reply(
            agent_name=speaker.name,
            reply=message,
            reasoning=self._extract_reasoning(message),
            tools_used=self._extract_tool_calls(message)
        )
```

#### Component 3: Code Artifact Tracker

```python
# cmbagent/execution/artifact_tracker.py

class ArtifactTracker:
    """Tracks generated files, code versions, plots"""
    
    def __init__(self, work_dir: str, db_session, run_id: str, step_id: str):
        self.work_dir = work_dir
        self.db_session = db_session
        self.run_id = run_id
        self.step_id = step_id
        self.artifacts = []
    
    def track_file_creation(self, file_path: str, creator_agent: str):
        """Called when agent creates a file"""
        from cmbagent.database.models import File
        
        file_record = File(
            run_id=self.run_id,
            step_id=self.step_id,
            file_path=file_path,
            file_type=self._infer_type(file_path),
            created_by_agent=creator_agent,
            content=self._read_if_small(file_path),
            meta={'version': self._get_version_number(file_path)}
        )
        self.db_session.add(file_record)
        self.artifacts.append(file_record)
    
    def track_code_evolution(self, code_versions: List[str], step: int):
        """Track how code evolved during step"""
        # Store each version as an artifact
        for i, code in enumerate(code_versions):
            self.track_file_creation(
                f"code_step{step}_v{i}.py",
                creator_agent="engineer"  # infer from context
            )
```

### 3. Skill Creation & Matching System

#### Component 1: SkillExtractor

```python
# cmbagent/skills/skill_extractor.py

from typing import List, Dict
from cmbagent.database.models import WorkflowRun, Skill

class SkillExtractor:
    """Extracts reusable skills from successful workflow runs"""
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    def extract_skill_from_run(
        self, 
        run_id: str, 
        step_range: str = "all",
        skill_name: str = None,
        tags: List[str] = None
    ) -> Skill:
        """
        Extract a skill from a successful workflow run.
        
        Args:
            run_id: Source workflow run
            step_range: "all" or "3-7" for specific steps
            skill_name: Human-readable name
            tags: Categorization tags
            
        Returns:
            Skill object ready for reuse
        """
        
        # 1. Load the workflow run
        run = self.db_session.query(WorkflowRun).filter_by(id=run_id).first()
        
        # 2. Extract the execution pattern
        steps = self._get_steps_in_range(run_id, step_range)
        dag_template = self._extract_dag_template(steps)
        agent_sequence = self._extract_agent_sequence(steps)
        
        # 3. Extract all agent interactions
        messages = self._get_all_messages(steps)
        agent_interactions = self._structure_interactions(messages)
        
        # 4. Extract artifacts
        files = self._get_all_files(steps)
        code_templates = self._extract_code_templates(files)
        
        # 5. Infer input/output schema
        input_schema = self._infer_inputs(steps[0])
        output_schema = self._infer_outputs(steps[-1])
        
        # 6. Create skill
        skill = Skill(
            name=skill_name or self._generate_skill_name(run),
            description=run.task_description,
            tags=tags or self._auto_tag(run),
            task_pattern=self._create_pattern(run.task_description),
            input_schema=input_schema,
            output_schema=output_schema,
            source_run_id=run_id,
            source_step_range=step_range,
            dag_template=dag_template,
            agent_sequence=agent_sequence,
            context_requirements=self._extract_context_needs(steps),
        )
        
        # 7. Store artifacts
        for file in files:
            artifact = SkillArtifact(
                skill_id=skill.id,
                artifact_type=file.file_type,
                file_path=file.file_path,
                content=file.content,
                description=f"Generated by {file.created_by_agent}"
            )
            self.db_session.add(artifact)
        
        self.db_session.add(skill)
        self.db_session.commit()
        
        return skill
    
    def _extract_dag_template(self, steps) -> Dict:
        """Convert executed steps into reusable DAG template"""
        nodes = []
        edges = []
        
        for step in steps:
            nodes.append({
                'agent': step.agent,
                'description_template': step.meta.get('description_template'),
                'context_inputs': step.inputs,
                'expected_outputs': step.outputs,
                'timeout': step.meta.get('timeout')
            })
        
        # Extract dependencies
        for step in steps:
            for dep in step.meta.get('dependencies', []):
                edges.append({'from': dep, 'to': step.step_number})
        
        return {'nodes': nodes, 'edges': edges}
    
    def _structure_interactions(self, messages) -> List[Dict]:
        """Structure agent interactions for skill template"""
        interactions = []
        
        for msg in messages:
            interactions.append({
                'agent': msg.sender,
                'role': msg.agent_role,
                'reasoning_pattern': self._generalize(msg.reasoning),
                'tool_usage': msg.tool_calls,
                'code_pattern': self._generalize_code(msg.code_generated)
            })
        
        return interactions
```

#### Component 2: SkillMatcher

```python
# cmbagent/skills/skill_matcher.py

from typing import List, Tuple
from sentence_transformers import SentenceTransformer
import numpy as np

class SkillMatcher:
    """Matches new tasks to existing skills"""
    
    def __init__(self, db_session, embedding_model="all-MiniLM-L6-v2"):
        self.db_session = db_session
        self.model = SentenceTransformer(embedding_model)
        self._load_skill_embeddings()
    
    def find_matching_skills(
        self, 
        task_description: str, 
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> List[Tuple[Skill, float]]:
        """
        Find skills similar to the given task.
        
        Returns:
            List of (Skill, similarity_score) tuples
        """
        
        # 1. Embed the new task
        task_embedding = self.model.encode(task_description)
        
        # 2. Compute similarities
        skills = self.db_session.query(Skill).all()
        matches = []
        
        for skill in skills:
            # Semantic similarity
            semantic_sim = self._cosine_similarity(
                task_embedding, 
                skill.embedding
            )
            
            # Tag overlap similarity
            tag_sim = self._tag_similarity(task_description, skill.tags)
            
            # Combined score
            score = 0.7 * semantic_sim + 0.3 * tag_sim
            
            if score >= min_similarity:
                matches.append((skill, score))
        
        # 3. Sort by score
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return matches[:top_k]
    
    def _cosine_similarity(self, vec1, vec2):
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
```

#### Component 3: SkillExecutor

```python
# cmbagent/skills/skill_executor.py

class SkillExecutor:
    """Executes a skill template, adapting to new context"""
    
    def __init__(self, db_session, session_id: str):
        self.db_session = db_session
        self.session_id = session_id
    
    def execute_skill(
        self, 
        skill: Skill, 
        task_context: Dict,
        allow_adaptation: bool = True
    ) -> str:
        """
        Execute a skill template.
        
        Args:
            skill: Skill to execute
            task_context: Current task context (may differ from template)
            allow_adaptation: Allow agents to adapt the skill
            
        Returns:
            run_id of the execution
        """
        
        # 1. Create new workflow run
        from cmbagent.database.models import WorkflowRun
        
        run = WorkflowRun(
            session_id=self.session_id,
            mode="skill_execution",
            agent="skill_based",
            model=task_context.get('model', 'gpt-4'),
            status="executing",
            task_description=f"[SKILL: {skill.name}] {task_context.get('task')}",
            meta={'skill_id': skill.id, 'skill_version': skill.version}
        )
        self.db_session.add(run)
        self.db_session.commit()
        
        # 2. Instantiate DAG from template
        dag_builder = DAGBuilder(self.db_session, self.session_id)
        dag = dag_builder.instantiate_from_template(
            skill.dag_template,
            context=task_context
        )
        
        # 3. Set up execution with skill guidance
        dag_executor = DAGExecutor(self.db_session, self.session_id)
        
        # Inject skill knowledge into agents
        agent_prompts = self._create_skill_aware_prompts(skill, task_context)
        
        # 4. Execute
        result = dag_executor.execute(
            run_id=run.id,
            dag=dag,
            agent_instructions=agent_prompts,
            allow_adaptation=allow_adaptation
        )
        
        # 5. Record execution
        skill_exec = SkillExecution(
            skill_id=skill.id,
            run_id=run.id,
            adapted=result.get('adapted', False),
            adaptations=result.get('adaptations'),
            success=result['status'] == 'completed',
            execution_time=result.get('duration'),
            cost=result.get('total_cost')
        )
        self.db_session.add(skill_exec)
        
        # 6. Update skill metrics
        skill.success_count += 1 if skill_exec.success else 0
        skill.failure_count += 0 if skill_exec.success else 1
        skill.last_used_at = datetime.utcnow()
        
        self.db_session.commit()
        
        return run.id
    
    def _create_skill_aware_prompts(self, skill: Skill, context: Dict) -> Dict:
        """Inject skill knowledge into agent prompts"""
        
        prompts = {}
        
        # For planner
        prompts['planner'] = f"""
        You are executing a known skill: {skill.name}
        
        Previous successful execution pattern:
        {json.dumps(skill.dag_template, indent=2)}
        
        Agent sequence that worked: {skill.agent_sequence}
        
        You can follow this pattern, but adapt if the current task differs.
        Current task: {context.get('task')}
        """
        
        # For engineer
        if skill.artifacts:
            code_examples = [a.content for a in skill.artifacts 
                           if a.artifact_type == 'code']
            prompts['engineer'] = f"""
            Previous successful code from similar task:
            
            {code_examples[0] if code_examples else ''}
            
            You can use this as a starting point, but adapt for current needs.
            """
        
        return prompts
```

### 4. Integration into CMBAgent

#### Modified: cmbagent/cmbagent.py

```python
class CMBAgent:
    
    def __init__(self, ..., enable_skill_learning=True, **kwargs):
        # ... existing init ...
        
        self.enable_skill_learning = enable_skill_learning
        
        if self.enable_skill_learning and self.use_database:
            from cmbagent.skills.skill_extractor import SkillExtractor
            from cmbagent.skills.skill_matcher import SkillMatcher
            from cmbagent.skills.skill_executor import SkillExecutor
            
            self.skill_extractor = SkillExtractor(self.db_session)
            self.skill_matcher = SkillMatcher(self.db_session)
            self.skill_executor = SkillExecutor(self.db_session, self.session_id)
    
    def planning_and_control_context_carryover(
        self, 
        task: str,
        use_skills: bool = True,
        create_skill: bool = False,
        skill_name: str = None,
        **kwargs
    ):
        """Enhanced with skill support"""
        
        # 1. Check for matching skills
        if use_skills:
            matches = self.skill_matcher.find_matching_skills(task, top_k=3)
            
            if matches:
                best_skill, score = matches[0]
                print(f"Found matching skill: {best_skill.name} (score: {score:.2f})")
                
                # Execute with skill template
                run_id = self.skill_executor.execute_skill(
                    best_skill, 
                    {'task': task, 'model': self.default_llm_model}
                )
                
                return {'run_id': run_id, 'used_skill': best_skill.name}
        
        # 2. Normal execution (no skill match)
        # Create agent logger for this run
        run_id = self._create_workflow_run(task)
        
        for step_num in range(1, num_steps + 1):
            step_id = self._create_step(run_id, step_num)
            
            # Create logger for this step
            from cmbagent.execution.agent_logger import AgentExecutionLogger
            agent_logger = AgentExecutionLogger(self.db_session, run_id, step_id)
            
            # Execute step with logging
            result = self._execute_step_with_logging(
                step_id, 
                agent_logger,
                context
            )
        
        # 3. After successful completion, optionally create skill
        if create_skill and self._workflow_successful(run_id):
            skill = self.skill_extractor.extract_skill_from_run(
                run_id,
                skill_name=skill_name,
                tags=self._auto_tag_task(task)
            )
            print(f"Created skill: {skill.name}")
        
        return {'run_id': run_id}
    
    def _execute_step_with_logging(
        self, 
        step_id: str, 
        agent_logger: AgentExecutionLogger,
        context: ContextVariables
    ):
        """Execute step with detailed agent logging"""
        
        # Create instrumented GroupChat
        from cmbagent.execution.instrumented_groupchat import InstrumentedGroupChat
        
        groupchat = InstrumentedGroupChat(
            agents=[self.planner, self.engineer, self.researcher],
            logger=agent_logger,
            messages=[],
            max_round=10
        )
        
        manager = GroupChatManager(groupchat=groupchat, llm_config=self.llm_config)
        
        # Execute
        result = manager.run(context=context)
        
        # Log all interactions
        agent_logger.finalize()  # Saves all buffered logs
        
        return result
```

---

## Feasibility for Very Long Tasks (Hours/Days)

### Current System Strengths

✅ **Checkpoint System (Stage 2)**
- Already saves state every N minutes
- Database + pickle dual persistence
- Can resume from any checkpoint

✅ **Message Logging**
- All agent messages stored in `messages` table
- No in-memory limits - persisted to disk
- Can reconstruct full conversation history

✅ **Work Directory Isolation**
- Each session has isolated directory
- All files preserved
- No cleanup during execution

✅ **Heartbeat Tracking**
- `last_heartbeat_at` column tracks liveness
- Can detect stalled workflows
- Resume/recovery mechanisms

### Enhancements Needed for Long Tasks

#### 1. Message Pagination

For workflows with 10,000+ messages:

```python
# cmbagent/database/repository.py

class MessageRepository:
    def get_messages_paginated(
        self, 
        run_id: str, 
        page: int = 1, 
        page_size: int = 100
    ):
        """Get messages in chunks to avoid memory issues"""
        offset = (page - 1) * page_size
        return self.db_session.query(Message)\
            .filter_by(run_id=run_id)\
            .order_by(Message.timestamp)\
            .offset(offset)\
            .limit(page_size)\
            .all()
```

#### 2. Incremental Skill Building

For long workflows, extract skills incrementally:

```python
class IncrementalSkillExtractor:
    """Extract skills from ongoing workflows"""
    
    def extract_partial_skill(
        self, 
        run_id: str, 
        completed_steps: List[int]
    ):
        """Extract skill from steps completed so far"""
        # This allows learning from partial execution
        # Before the full workflow finishes
```

#### 3. Context Summarization

For very long contexts, periodically summarize:

```python
class ContextSummarizer:
    """Summarize long contexts to prevent token limit issues"""
    
    def summarize_context(
        self, 
        messages: List[Message], 
        max_tokens: int = 4000
    ) -> str:
        """
        Summarize old messages while keeping recent ones.
        Use LLM to create summary of earlier conversation.
        """
        
        # Keep last N messages verbatim
        recent = messages[-20:]
        
        # Summarize older messages
        old = messages[:-20]
        summary = self._llm_summarize(old)
        
        return summary + recent
```

#### 4. Streaming Results

For real-time feedback:

```python
# Already have WebSocket events, enhance with:
{
    "event": "AGENT_REASONING",
    "data": {
        "agent": "engineer",
        "thought": "I'm now analyzing the data...",
        "progress": 45
    }
}
```

### Scalability Analysis

| Workflow Duration | Message Count | DB Size | Memory | Feasible? |
|------------------|---------------|---------|--------|-----------|
| 1 hour | ~500 | 5 MB | 100 MB | ✅ Yes |
| 8 hours | ~4,000 | 40 MB | 200 MB | ✅ Yes |
| 24 hours | ~12,000 | 120 MB | 300 MB | ✅ Yes (with pagination) |
| 3 days | ~36,000 | 360 MB | 500 MB | ✅ Yes (with summarization) |
| 1 week | ~84,000 | 840 MB | 1 GB | ⚠️  Possible (needs optimization) |

**Bottlenecks:**
- SQLite handles 100s of MB easily, GB+ needs PostgreSQL
- Message pagination prevents memory issues
- Context summarization prevents token limit issues
- Checkpoint system enables resume after crashes

---

## Implementation Roadmap

### Phase 1: Enhanced Execution Capture (1-2 weeks)

**Stage 10: Agent-Level Execution Logging**
1. Extend Message model with reasoning, tool_calls, code fields
2. Implement AgentExecutionLogger
3. Wrap GroupChat with instrumentation
4. Add code artifact tracking
5. Extend WorkflowStep with agent_transitions

**Deliverables:**
- Every agent interaction logged
- Code evolution tracked
- Tool usage captured
- Database captures full execution graph

### Phase 2: Skill Extraction (1 week)

**Stage 11: Skill System Core**
1. Create skills, skill_executions, skill_artifacts tables
2. Implement SkillExtractor
3. Add CLI command: `cmbagent extract-skill <run_id>`
4. Build DAG template extraction
5. Create artifact collection

**Deliverables:**
- Extract skills from successful runs
- Store reusable templates
- Capture code/plot artifacts

### Phase 3: Skill Matching & Execution (1-2 weeks)

**Stage 12: Skill Intelligence**
1. Implement SkillMatcher with embeddings
2. Create SkillExecutor
3. Add skill-aware agent prompts
4. Build skill similarity ranking
5. Implement skill adaptation tracking

**Deliverables:**
- Automatic skill matching for new tasks
- Execute with skill templates
- Track adaptations
- Learn from successes/failures

### Phase 4: Long-Task Optimizations (1 week)

**Stage 13: Scalability Enhancements**
1. Add message pagination
2. Implement context summarization
3. Build incremental skill extraction
4. Add checkpoint optimization
5. PostgreSQL migration guide

**Deliverables:**
- Handle 24+ hour workflows
- Memory-efficient message handling
- Real-time skill learning

---

## API Examples

### Creating a Skill

```bash
# After successful run
cmbagent extract-skill abc123 \
  --name "plot_power_spectrum" \
  --steps "4-7" \
  --tags "plotting,physics,power_spectrum"
```

```python
# Programmatic
cmbagent = CMBAgent(enable_skill_learning=True)
result = cmbagent.one_shot(task="Plot power spectrum")

if result['success']:
    skill = cmbagent.skill_extractor.extract_skill_from_run(
        run_id=result['run_id'],
        skill_name="plot_power_spectrum",
        tags=["plotting", "physics"]
    )
```

### Using a Skill

```python
# Automatic matching
cmbagent = CMBAgent(enable_skill_learning=True)
result = cmbagent.one_shot(
    task="Create a power spectrum plot",
    use_skills=True  # Will auto-match to "plot_power_spectrum" skill
)

# Explicit skill usage
skill = cmbagent.db_session.query(Skill).filter_by(name="plot_power_spectrum").first()
result = cmbagent.skill_executor.execute_skill(
    skill,
    context={'task': 'Plot PS with new data', 'data_file': 'data.txt'}
)
```

### Browsing Skills

```bash
# List all skills
cmbagent list-skills

# Search for skills
cmbagent search-skills "plotting physics"

# Show skill details
cmbagent show-skill plot_power_spectrum
```

---

## Recommendations

### Must-Have

1. **Implement AgentExecutionLogger first** - Foundation for everything
2. **Extend Message model** - Capture reasoning, code, tools
3. **Basic skill extraction** - Manual creation via CLI
4. **Skill templates in database** - Reusable patterns

### Nice-to-Have

1. **Automatic skill matching** - Semantic similarity search
2. **Skill adaptation tracking** - Learn what changes work
3. **Skill versioning** - Track evolution of skills
4. **Skill marketplace** - Share skills between users

### Future Enhancements

1. **Skill composition** - Combine multiple skills
2. **Skill optimization** - Auto-improve skills over time
3. **Meta-learning** - Learn which skills to apply when
4. **Skill transfer** - Export/import skills between systems

---

## Conclusion

**Your vision is highly feasible** with the current architecture. The combination of:
- AG2's built-in message logging
- Your event-driven DAG system
- Database-backed persistence
- Checkpoint mechanisms

...provides a solid foundation for detailed execution capture and skill learning.

The skill system would be a **powerful addition** for:
- Accelerating similar tasks (10x faster with skill templates)
- Knowledge accumulation over time
- Reducing costs (reuse proven approaches)
- Team collaboration (share skills)

For **very long tasks** (days/weeks), you'll need:
- Message pagination ✅ Easy to add
- Context summarization ✅ Proven techniques
- PostgreSQL migration ✅ Already designed for it
- Incremental checkpointing ✅ Already have it

**Start with Phase 1** (Agent Execution Logging) - it's the foundation and immediately valuable for debugging/observability. Then build up to full skill system in Phases 2-3.
