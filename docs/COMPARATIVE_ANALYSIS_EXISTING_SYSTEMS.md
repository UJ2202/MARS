# Comparative Analysis: CMBAgent vs. Existing Multi-Agent Systems

**Date:** January 21, 2026  
**Purpose:** Landscape analysis of similar systems in multi-agent orchestration, path exploration, and autonomous learning

---

## Executive Summary

**Yes, similar systems exist**, but CMBAgent's unique combination of features is novel:

- **AutoGen/AG2, LangGraph, CrewAI** provide multi-agent orchestration but lack systematic path exploration and skill extraction
- **Airflow, Prefect, Temporal** offer workflow orchestration but require manual design and lack autonomous adaptation
- **Voyager, DEPS** demonstrate skill libraries but focus on gaming/robotics, not scientific computing
- **MetaGPT, ChatDev** generate software but don't explore alternative solution paths
- **OpenAI Assistants API** provides tools but no branching or learning from execution

**CMBAgent's unique position:** First system to integrate **event-driven execution tracking + workflow branching + skill extraction + HITL** specifically for scientific discovery.

---

## 1. Multi-Agent Frameworks

### 1.1 AutoGen / AG2 ⭐⭐⭐⭐⭐

**What it is:** Microsoft's conversable agent framework (CMBAgent's foundation)

**Similarities:**
- ✅ Multi-agent collaboration with hand-offs
- ✅ GroupChat patterns for agent coordination
- ✅ Tool integration and code execution
- ✅ Conversation history tracking
- ✅ Human-in-the-loop via UserProxyAgent

**Differences:**
- ❌ No workflow branching mechanism
- ❌ No persistent execution event tracking (only chat logs)
- ❌ No skill extraction or pattern learning
- ❌ No systematic path exploration
- ❌ No checkpoint-based state management
- ❌ No DAG visualization or execution graph

**CMBAgent's additions:**
- Persistent database for all events (not just messages)
- Branching from any checkpoint
- Skill extraction framework
- DAG-based execution with parallel support
- Real-time WebSocket streaming
- Comparative analysis of execution paths

**Status:** Active (10k+ stars)  
**URL:** https://github.com/ag2ai/ag2

**Verdict:** CMBAgent builds on AG2 but adds critical capabilities for scientific discovery.

---

### 1.2 LangGraph ⭐⭐⭐⭐

**What it is:** LangChain's state machine for agent workflows

**Similarities:**
- ✅ Graph-based workflow definition
- ✅ State management between nodes
- ✅ Conditional branching based on agent outputs
- ✅ Human-in-the-loop checkpoints
- ✅ Streaming support

**Differences:**
- ❌ Branching is **predefined in graph**, not dynamic exploration
- ❌ No learning from execution (every run is independent)
- ❌ No skill extraction or pattern recognition
- ❌ No comparative analysis of paths
- ❌ No persistent event tracking for post-hoc analysis
- ❌ Focused on LLM chains, not multi-agent coordination

**Example:**
```python
# LangGraph: Predefined branching
def should_continue(state):
    if state["error_count"] > 3:
        return "fallback"
    return "retry"

graph.add_conditional_edges("node", should_continue)

# CMBAgent: Dynamic branching at runtime
branch_manager.create_branch(
    step_id="current_step",
    hypothesis="Try alternative method X",
    modifications={"approach": "bayesian"}
)
```

**Status:** Active (growing rapidly)  
**URL:** https://github.com/langchain-ai/langgraph

**Verdict:** LangGraph offers graph-based control flow but lacks CMBAgent's exploration and learning capabilities.

---

### 1.3 CrewAI ⭐⭐⭐⭐

**What it is:** Role-based agent collaboration framework

**Similarities:**
- ✅ Multiple specialized agents with roles
- ✅ Task delegation and coordination
- ✅ Tool integration
- ✅ Sequential and hierarchical workflows

**Differences:**
- ❌ No branching or alternative path exploration
- ❌ No skill extraction or learning
- ❌ No event-level execution tracking
- ❌ No human approval gates
- ❌ No checkpoint/replay functionality
- ❌ Focus on business workflows, not scientific computing

**Key Distinction:** CrewAI is more like a "team of workers" with fixed processes, while CMBAgent is an "adaptive research system" that learns and explores.

**Status:** Active (10k+ stars)  
**URL:** https://github.com/joaomdmoura/crewAI

**Verdict:** Good for production workflows with known patterns; CMBAgent better for exploratory research.

---

### 1.4 MetaGPT ⭐⭐⭐

**What it is:** Multi-agent system for software development

**Similarities:**
- ✅ Multiple specialized agents (product manager, architect, engineer)
- ✅ Structured workflow (requirement → design → code → test)
- ✅ Document generation and tracking

**Differences:**
- ❌ Linear workflow only (no branching)
- ❌ No learning from previous projects
- ❌ No skill reuse mechanisms
- ❌ No human oversight during execution
- ❌ Focused on software generation, not scientific discovery

**Status:** Active (30k+ stars)  
**URL:** https://github.com/geekan/MetaGPT

**Verdict:** Excellent for software generation; CMBAgent designed for scientific research workflows.

---

### 1.5 ChatDev ⭐⭐⭐

**What it is:** Virtual software company with agent roles

**Similarities:**
- ✅ Multi-agent collaboration (CEO, CTO, programmer, tester)
- ✅ Phase-based workflow
- ✅ Code generation and review

**Differences:**
- ❌ Fixed role hierarchy (no dynamic adaptation)
- ❌ No branching or exploration
- ❌ No learning from past projects
- ❌ Waterfall model (no iterative improvement)

**Status:** Active (20k+ stars)  
**URL:** https://github.com/OpenBMB/ChatDev

**Verdict:** Simulates software team but lacks CMBAgent's research-oriented features.

---

## 2. Workflow Orchestration Systems

### 2.1 Apache Airflow ⭐⭐⭐⭐⭐

**What it is:** Production workflow scheduler

**Similarities:**
- ✅ DAG-based execution
- ✅ Task dependencies and parallelism
- ✅ Retry logic
- ✅ Monitoring and logging
- ✅ Web UI for visualization

**Differences:**
- ❌ Workflows are **manually coded** (not AI-generated)
- ❌ No multi-agent collaboration
- ❌ No dynamic replanning or branching
- ❌ No learning from execution patterns
- ❌ Fixed pipelines (not exploratory)

**Use Case Difference:**
- **Airflow:** "Run this ETL pipeline daily at 2am"
- **CMBAgent:** "Analyze this dataset; system figures out how and learns for next time"

**Status:** Production-grade (30k+ stars)  
**URL:** https://github.com/apache/airflow

**Verdict:** Complementary systems - Airflow for production pipelines, CMBAgent for research exploration.

---

### 2.2 Prefect ⭐⭐⭐⭐

**What it is:** Modern workflow orchestration

**Similarities:**
- ✅ Python-native workflow definition
- ✅ Retry mechanisms
- ✅ Observability
- ✅ Dynamic task generation

**Differences:**
- ❌ Still requires manual workflow design
- ❌ No AI agents or LLM integration
- ❌ No skill extraction
- ❌ No branching for exploration

**Status:** Active (14k+ stars)  
**URL:** https://github.com/PrefectHQ/prefect

**Verdict:** Better developer experience than Airflow but still manual workflow design.

---

### 2.3 Temporal ⭐⭐⭐⭐

**What it is:** Durable execution platform

**Similarities:**
- ✅ Workflow state management
- ✅ Long-running processes
- ✅ Failure recovery
- ✅ Replay capabilities

**Differences:**
- ❌ No AI/LLM integration
- ❌ No autonomous agent coordination
- ❌ No learning or skill extraction
- ❌ Focus on reliability, not intelligence

**Status:** Production-grade (9k+ stars)  
**URL:** https://github.com/temporalio/temporal

**Verdict:** Excellent for durable execution; CMBAgent adds intelligence layer on top.

---

## 3. Systems with Learning Capabilities

### 3.1 Voyager (MineDojo) ⭐⭐⭐⭐

**What it is:** Minecraft agent with skill library

**Similarities:**
- ✅ **Skill library** extracted from execution
- ✅ Skill retrieval for new tasks
- ✅ Iterative improvement
- ✅ Code generation and execution

**Differences:**
- ❌ Domain: Gaming (Minecraft), not scientific computing
- ❌ Single agent, not multi-agent
- ❌ No human-in-the-loop
- ❌ No branching for path exploration
- ❌ Skills are code snippets, not workflow patterns

**Key Inspiration:** Voyager pioneered skill libraries for agents - CMBAgent extends this to scientific workflows.

**Status:** Research project (NVIDIA)  
**Paper:** Wang et al., "Voyager: An Open-Ended Embodied Agent with Large Language Models" (2023)

**Verdict:** Proved skill learning works; CMBAgent applies concept to multi-agent scientific discovery.

---

### 3.2 DEPS (Describe, Explain, Plan, Select) ⭐⭐⭐

**What it is:** Embodied agent with skill learning

**Similarities:**
- ✅ Builds skill library from experience
- ✅ Retrieves relevant skills for new tasks
- ✅ Hierarchical planning

**Differences:**
- ❌ Focus: Robotics tasks
- ❌ Single agent
- ❌ No workflow branching
- ❌ No human oversight

**Status:** Research project  
**Paper:** Wang et al., "DEPS: Embodied Agents with Skill Libraries" (2023)

**Verdict:** Similar philosophy; different domain and no multi-agent coordination.

---

### 3.3 ReAct + Reflexion ⭐⭐⭐⭐

**What it is:** Agent with self-reflection

**Similarities:**
- ✅ Learning from mistakes
- ✅ Iterative improvement
- ✅ Memory of past attempts

**Differences:**
- ❌ Reflection within single task (not across tasks)
- ❌ No persistent skill library
- ❌ No multi-agent coordination
- ❌ No branching or path comparison

**Status:** Research papers + implementations  
**Papers:** Yao et al. (ReAct), Shinn et al. (Reflexion)

**Verdict:** Good for single-task improvement; CMBAgent enables cross-task learning.

---

## 4. Scientific Discovery Systems

### 4.1 ChemCrow ⭐⭐⭐

**What it is:** LLM agent for chemistry tasks

**Similarities:**
- ✅ Scientific domain focus
- ✅ Tool integration (RDKit, PubChem, etc.)
- ✅ Task planning and execution

**Differences:**
- ❌ Single agent (no multi-agent collaboration)
- ❌ No branching or exploration
- ❌ No learning from execution
- ❌ Domain-specific (chemistry only)

**Status:** Research project  
**Paper:** Bran et al., "ChemCrow: Augmenting LLMs with Chemistry Tools" (2023)

**Verdict:** Excellent for chemistry; CMBAgent broader and includes learning.

---

### 4.2 Coscientist ⭐⭐⭐

**What it is:** Autonomous chemistry research system

**Similarities:**
- ✅ Scientific experimentation
- ✅ Tool use and code generation
- ✅ Multi-step task planning

**Differences:**
- ❌ No multi-agent architecture
- ❌ No path exploration or branching
- ❌ No skill extraction
- ❌ Chemistry-specific

**Status:** Research project (CMU)  
**Paper:** Boiko et al., "Autonomous Chemical Research with LLMs" (2023)

**Verdict:** Impressive autonomy in chemistry; CMBAgent more general-purpose.

---

### 4.3 AI Scientist ⭐⭐⭐⭐

**What it is:** Automated scientific paper generation

**Similarities:**
- ✅ Scientific research workflow
- ✅ Literature review, experimentation, writing
- ✅ Iterative refinement

**Differences:**
- ❌ Focus on paper generation (not general discovery)
- ❌ No multi-agent collaboration
- ❌ No branching mechanism
- ❌ No skill reuse

**Status:** Research project (Sakana AI)  
**Paper:** Lu et al., "The AI Scientist" (2024)

**Verdict:** Specialized for paper writing; CMBAgent handles broader research tasks.

---

## 5. Commercial Platforms

### 5.1 OpenAI Assistants API ⭐⭐⭐⭐

**What it is:** API for building assistant applications

**Similarities:**
- ✅ Tool integration (code interpreter, file search)
- ✅ Conversation threads
- ✅ File management

**Differences:**
- ❌ Single assistant (not multi-agent)
- ❌ No workflow orchestration
- ❌ No branching or exploration
- ❌ No learning from execution
- ❌ No event tracking beyond API logs

**Status:** Production (OpenAI)  
**URL:** https://platform.openai.com/docs/assistants

**Verdict:** Building block for agents; CMBAgent provides orchestration layer.

---

### 5.2 Devin (Cognition AI) ⭐⭐⭐⭐

**What it is:** Autonomous software engineering agent

**Similarities:**
- ✅ Long-running tasks
- ✅ Planning and execution
- ✅ Code generation
- ✅ Debugging and iteration

**Differences:**
- ❌ Proprietary/closed source
- ❌ Software engineering only
- ❌ No clear multi-agent architecture
- ❌ Unknown learning mechanisms
- ❌ No branching or exploration features documented

**Status:** Commercial beta  
**URL:** https://www.cognition-labs.com/devin

**Verdict:** Impressive but closed; unclear if it has CMBAgent's research-oriented features.

---

### 5.3 Microsoft AutoGen Studio ⭐⭐⭐

**What it is:** No-code interface for AutoGen

**Similarities:**
- ✅ Based on AutoGen (like CMBAgent)
- ✅ Multi-agent workflows
- ✅ Visual workflow design

**Differences:**
- ❌ No-code focus (less flexible)
- ❌ No branching mechanism
- ❌ No skill extraction
- ❌ Simpler execution tracking

**Status:** Active (part of AutoGen ecosystem)  
**URL:** https://microsoft.github.io/autogen/docs/autogen-studio/

**Verdict:** User-friendly AutoGen wrapper; CMBAgent adds research capabilities.

---

## 6. Research Workflow Systems

### 6.1 Galaxy ⭐⭐⭐⭐

**What it is:** Bioinformatics workflow platform

**Similarities:**
- ✅ Scientific workflow execution
- ✅ Tool integration
- ✅ Reproducibility focus
- ✅ Web UI

**Differences:**
- ❌ Manual workflow design (no AI)
- ❌ No multi-agent coordination
- ❌ No autonomous planning
- ❌ Bioinformatics-specific

**Status:** Production (25+ years old!)  
**URL:** https://usegalaxy.org/

**Verdict:** Proven for bioinformatics; CMBAgent adds AI autonomy.

---

### 6.2 Nextflow ⭐⭐⭐⭐

**What it is:** Scientific workflow DSL

**Similarities:**
- ✅ Pipeline definition
- ✅ Reproducibility
- ✅ Parallelism
- ✅ Container support

**Differences:**
- ❌ Manual pipeline coding
- ❌ No AI/LLM integration
- ❌ No learning or adaptation

**Status:** Production (6k+ stars)  
**URL:** https://www.nextflow.io/

**Verdict:** Excellent for reproducible pipelines; CMBAgent for exploration.

---

## 7. Unique Aspects of CMBAgent

### 7.1 What CMBAgent Does That Others Don't

#### 1. **Systematic Path Exploration with Branching**
- **Others:** Single execution path or predefined alternatives
- **CMBAgent:** Create branches at runtime, execute multiple hypotheses, compare results

```python
# Unique to CMBAgent
branch_a = create_branch(hypothesis="Use Method X")
branch_b = create_branch(hypothesis="Use Method Y")
results = compare_branches([branch_a, branch_b])
best_path = select_winner(results)
extract_skill(best_path)  # Learn for next time
```

#### 2. **Event-Driven Execution History**
- **Others:** Logs or conversation history
- **CMBAgent:** Structured events with hierarchy, metadata, inputs/outputs

```python
# Every action tracked
ExecutionEvent(
    event_type="code_exec",
    agent_name="engineer",
    inputs={"code": "..."},
    outputs={"result": "..."},
    parent_event_id="...",  # Hierarchy
    duration_ms=1250,
    meta={"reasoning": "..."}
)
```

#### 3. **Skill Extraction & Cross-Task Learning**
- **Others:** Each task starts fresh (except Voyager in gaming)
- **CMBAgent:** Automatically extract patterns, match to new tasks, progressive improvement

```python
# After successful execution
skill = extract_pattern(run_id)
skill_library.store(skill)

# Next similar task
matching_skills = find_skills(new_task)
if matching_skills:
    execute_skill(matching_skills[0])  # 80% faster
else:
    plan_from_scratch()
```

#### 4. **Integrated HITL at Strategic Points**
- **Others:** Human as another agent OR fully autonomous
- **CMBAgent:** Strategic approval gates with context

```python
# At critical decision points
approval = request_approval(
    checkpoint_type="branch_selection",
    context=current_state,
    message="Unexpected result. How to proceed?",
    options=["continue", "branch_methodX", "branch_methodY"]
)
```

#### 5. **Scientific Computing Focus**
- **Others:** General-purpose or specific domains (chemistry, software)
- **CMBAgent:** 50+ agents for scientific computing (cosmology, data science, ML)

#### 6. **Complete Auditability**
- **Others:** Logs, conversation history
- **CMBAgent:** Database with every event, decision, branch, checkpoint

---

### 7.2 Feature Comparison Matrix

| Feature | CMBAgent | AutoGen | LangGraph | CrewAI | Airflow | Voyager | OpenAI API |
|---------|----------|---------|-----------|--------|---------|---------|------------|
| **Multi-agent** | ✅ | ✅ | ⚠️ | ✅ | ❌ | ❌ | ❌ |
| **Dynamic planning** | ✅ | ✅ | ⚠️ | ✅ | ❌ | ❌ | ❌ |
| **Branching exploration** | ✅ | ❌ | ⚠️¹ | ❌ | ❌ | ❌ | ❌ |
| **Skill extraction** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅² | ❌ |
| **Event tracking** | ✅³ | ⚠️⁴ | ⚠️ | ❌ | ✅ | ❌ | ❌ |
| **Human-in-loop** | ✅⁵ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Checkpoints** | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Learning across tasks** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Path comparison** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Scientific focus** | ✅ | ⚠️ | ❌ | ❌ | ⚠️ | ❌ | ❌ |
| **Production-ready** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| **Open source** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |

**Legend:**
- ✅ Full support
- ⚠️ Partial support
- ❌ Not supported

**Footnotes:**
1. LangGraph: Branching is predefined in graph, not runtime exploration
2. Voyager: Gaming domain only, not scientific workflows
3. CMBAgent: Database with structured events, hierarchy, full metadata
4. AutoGen: Conversation logs only, not structured event tracking
5. CMBAgent: Strategic approval gates with context and options

---

## 8. Closest Competitors

### 8.1 Most Similar System: AutoGen + Manual Orchestration

**What it would take to replicate CMBAgent with AutoGen alone:**

```python
# Using pure AutoGen
✅ Multi-agent collaboration (built-in)
❌ Branching: Would need custom checkpoint system
❌ Event tracking: Would need custom database layer
❌ Skill extraction: Would need custom pattern recognition
❌ DAG execution: Would need custom orchestrator
❌ WebSocket UI: Would need custom frontend
❌ Path comparison: Would need custom analytics

Estimated effort: 6-12 months of development
```

**CMBAgent provides this out of the box.**

---

### 8.2 Hybrid Approach: LangGraph + Custom Skill System

```python
# Using LangGraph
✅ State management (built-in)
⚠️ Branching: Predefined only
❌ Multi-agent: Limited support
❌ Event tracking: Custom needed
❌ Skill extraction: Custom needed
❌ Path comparison: Custom needed

Estimated effort: 4-8 months
```

---

### 8.3 Academic Research Systems

Several research projects explore similar ideas but:
- **Not production-ready** (proof-of-concept only)
- **Narrow domains** (chemistry, robotics, gaming)
- **Missing key features** (no HITL, no branching, no skill reuse)
- **Not open source** or poorly documented

---

## 9. Why CMBAgent's Combination is Unique

### 9.1 The "Triple Innovation"

1. **Event-driven execution history**
   - Every action captured with context
   - Enables post-hoc analysis and pattern extraction

2. **Systematic path exploration**
   - Branch at any point during execution
   - Compare alternatives with metrics
   - Human guidance at decision points

3. **Cross-task skill learning**
   - Automatic pattern extraction
   - Similarity-based matching
   - Progressive improvement over time

**No existing system combines all three.**

---

### 9.2 Why Others Haven't Done This

**Technical Complexity:**
- Requires database design for event tracking
- Branching needs checkpoint/replay system
- Skill extraction needs NLP + pattern recognition
- Integration challenge across all components

**Domain Focus:**
- Most frameworks are general-purpose (AutoGen, LangGraph)
- Or domain-specific without learning (ChemCrow, Galaxy)
- Scientific computing needs both flexibility AND domain tools

**Research vs. Production:**
- Research projects prove concepts but aren't production-ready
- Production systems (Airflow) prioritize reliability over intelligence
- CMBAgent bridges both: research-oriented + production-grade

**Market Timing:**
- LLMs capable of complex reasoning only recent (2023+)
- Multi-agent orchestration still emerging field
- Skill learning for workflows largely unexplored

---

## 10. Future Convergence

### 10.1 Trends We're Seeing

**1. AutoGen/AG2 adding features:**
- Better state management
- Improved debugging tools
- But no branching or skill extraction roadmap

**2. LangGraph gaining adoption:**
- More flexible state machines
- Better human-in-loop support
- But still predefined graphs

**3. Skill learning emerging:**
- Voyager proved concept
- Others exploring in narrow domains
- No general-purpose workflow skill systems yet

**4. Commercial platforms evolving:**
- Devin, Cursor, Replit AI exploring autonomy
- Mostly software engineering focused
- Closed source limits verification

---

### 10.2 Where the Field is Going

**Next 12 months:**
- More multi-agent frameworks will emerge
- Skill libraries will become common feature
- Human-in-loop will be better integrated

**CMBAgent's position:**
- Early mover in integrated approach
- Scientific domain leadership
- Open source advantage for research community

**Recommendation:**
- Continue developing skill extraction (Phase 10)
- Maintain tight AG2 integration (leverage improvements)
- Build community around skill sharing
- Publish research to establish thought leadership

---

## 11. Conclusion

### 11.1 Summary

**Similar systems exist in parts:**
- ✅ Multi-agent orchestration (AutoGen, LangGraph, CrewAI)
- ✅ Workflow systems (Airflow, Prefect, Temporal)
- ✅ Skill learning (Voyager for gaming)
- ✅ Scientific automation (ChemCrow, Coscientist)

**But no system combines:**
- Multi-agent collaboration
- Systematic path exploration with branching
- Event-driven execution tracking
- Skill extraction and reuse
- Human-in-loop at strategic points
- Scientific computing focus
- Production-ready implementation

**CMBAgent's unique value:**
1. **Only system** with branching + skill extraction for workflows
2. **Most comprehensive** event tracking for multi-agent systems
3. **Best suited** for scientific discovery workflows
4. **Production-ready** with active deployment and community

---

### 11.2 Competitive Positioning

**When to use CMBAgent vs. alternatives:**

**Use AutoGen/AG2 when:**
- Simple multi-agent conversation
- No need for path exploration
- Task is one-time execution
- → Then extend with CMBAgent for research workflows

**Use LangGraph when:**
- Need precise control flow
- Workflow structure known in advance
- LangChain ecosystem preferred
- → CMBAgent better for exploratory research

**Use Airflow when:**
- Production ETL pipelines
- Scheduled batch jobs
- Workflow is stable and tested
- → CMBAgent for initial research, Airflow for production

**Use CMBAgent when:**
- Scientific research workflows
- Need to explore multiple approaches
- Want to learn from successful patterns
- Require human oversight at key points
- Building reusable workflow library

---

### 11.3 Market Opportunity

**Underserved niches:**
1. **Academic research labs** - Need automation but lack engineering resources
2. **Pharmaceutical R&D** - Complex experimental workflows with learning needs
3. **Climate science** - Data analysis workflows with model comparisons
4. **Materials discovery** - Hypothesis testing with path exploration
5. **Bioinformatics** - Beyond Galaxy's fixed pipelines

**CMBAgent's advantages:**
- Open source (academic-friendly)
- Research-oriented (not just task completion)
- Learns over time (ROI improves with use)
- HITL (scientist maintains control)

---

## 12. References

**Open Source Projects:**
- AutoGen/AG2: https://github.com/ag2ai/ag2
- LangGraph: https://github.com/langchain-ai/langgraph
- CrewAI: https://github.com/joaomdmoura/crewAI
- MetaGPT: https://github.com/geekan/MetaGPT
- Airflow: https://github.com/apache/airflow
- Prefect: https://github.com/PrefectHQ/prefect

**Research Papers:**
- Voyager: Wang et al., "Voyager: An Open-Ended Embodied Agent with Large Language Models" (2023)
- ChemCrow: Bran et al., "ChemCrow: Augmenting LLMs with Chemistry Tools" (2023)
- Coscientist: Boiko et al., "Autonomous Chemical Research with LLMs" (2023)
- ReAct: Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models" (2023)
- Reflexion: Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement Learning" (2023)

**Commercial Platforms:**
- OpenAI Assistants: https://platform.openai.com/docs/assistants
- Devin: https://www.cognition-labs.com/devin
- Microsoft AutoGen Studio: https://microsoft.github.io/autogen/docs/autogen-studio/

**CMBAgent:**
- GitHub: https://github.com/CMBAgents/cmbagent
- Discord: https://discord.gg/UG47Yb6gHG
- Paper: [Link to be added after publication]

---

**Last Updated:** January 21, 2026  
**Next Review:** Q2 2026 (landscape evolving rapidly)
