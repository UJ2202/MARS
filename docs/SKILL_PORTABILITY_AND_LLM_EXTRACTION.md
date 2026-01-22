# Skill Portability & LLM-Based Extraction

**Date:** January 21, 2026  
**Purpose:** Design framework-agnostic skill structure and LLM-based skill extraction

---

## Executive Summary

This document addresses two critical design considerations:

1. **Skill Portability:** Skills should be consumable by any orchestration engine (AG2, LangGraph, Temporal, Airflow, etc.)
2. **LLM-Based Extraction:** Use LLMs to automatically extract skills from complete execution context

---

## Part 1: Framework-Agnostic Skill Structure

### 1.1 Core Principle: Separation of Concerns

```
┌─────────────────────────────────────────────────────────────┐
│              SKILL DEFINITION (Portable)                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Declarative Workflow Description                     │  │
│  │  - What needs to be done (tasks, sequence, logic)    │  │
│  │  - Required inputs/outputs                            │  │
│  │  - Success criteria                                   │  │
│  │  - Tool/function specifications (OpenAPI format)      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Consumed by
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           FRAMEWORK ADAPTERS (Implementation)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ AG2 Adapter  │  │LangGraph     │  │  Temporal    │      │
│  │              │  │Adapter       │  │  Adapter     │      │
│  │ - Create     │  │              │  │              │      │
│  │   agents     │  │ - Build      │  │ - Define     │      │
│  │ - Setup      │  │   graph      │  │   workflows  │      │
│  │   GroupChat  │  │ - Map nodes  │  │ - Activities │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Universal Skill Schema (Version 1.0)

```json
{
  "skill_schema_version": "1.0",
  "skill": {
    "metadata": {
      "id": "uuid",
      "name": "skill_name",
      "version": "1.0.0",
      "description": "What this skill does",
      "category": "data_analysis",
      "tags": ["cmb", "analysis"],
      "author": "system",
      "created_at": "2026-01-21T00:00:00Z",
      "framework_agnostic": true
    },
    
    "provenance": {
      "source_system": "cmbagent",
      "extracted_from_run_id": "uuid",
      "extraction_method": "llm_analysis",
      "source_framework": "ag2",
      "extraction_confidence": 0.95
    },
    
    "interface": {
      "inputs": [
        {
          "name": "input_file_path",
          "type": "string",
          "description": "Path to input data file",
          "required": true,
          "validation": {
            "format": "file_path",
            "exists": true,
            "extensions": [".fits", ".dat", ".csv"]
          }
        },
        {
          "name": "analysis_parameters",
          "type": "object",
          "description": "Analysis configuration",
          "required": false,
          "default": {},
          "schema": {
            "bin_width": {"type": "integer", "default": 10},
            "confidence_level": {"type": "float", "default": 0.95}
          }
        }
      ],
      "outputs": [
        {
          "name": "analysis_results",
          "type": "object",
          "description": "Statistical analysis results",
          "schema": {
            "parameters": "object",
            "uncertainties": "object",
            "convergence_metrics": "object"
          }
        },
        {
          "name": "visualization_files",
          "type": "array",
          "description": "Generated plot files",
          "item_type": "file_path"
        },
        {
          "name": "report",
          "type": "string",
          "description": "Markdown report",
          "format": "markdown"
        }
      ],
      "side_effects": {
        "files_created": ["*.png", "*.pdf", "results.json"],
        "directories_created": ["output/"],
        "external_apis_called": [],
        "stateful": false
      }
    },
    
    "workflow": {
      "type": "dag",
      "execution_model": "parallel_where_possible",
      "tasks": [
        {
          "task_id": "understand_context",
          "name": "Literature & Context",
          "type": "agent_task",
          "description": "Query domain knowledge and understand the problem",
          "role": "researcher",
          "capabilities_required": ["knowledge_retrieval", "synthesis"],
          "dependencies": [],
          "parallel_group": null,
          "estimated_duration_seconds": 45,
          "tools": [
            {
              "name": "rag_query",
              "type": "function",
              "required": true,
              "openapi_spec": {
                "function": "query_knowledge_base",
                "parameters": {
                  "query": {"type": "string"},
                  "indices": {"type": "array", "items": {"type": "string"}},
                  "max_results": {"type": "integer", "default": 5}
                },
                "returns": {
                  "type": "array",
                  "items": {
                    "title": "string",
                    "content": "string",
                    "relevance": "float"
                  }
                }
              }
            }
          ],
          "inputs": {
            "from_skill_inputs": ["input_file_path"],
            "from_previous_tasks": []
          },
          "outputs": {
            "context_summary": "string",
            "relevant_papers": "array",
            "methodology_notes": "string"
          },
          "success_criteria": [
            {
              "check": "outputs.relevant_papers.length >= 3",
              "critical": true
            }
          ]
        },
        {
          "task_id": "validate_data",
          "name": "Data Validation",
          "type": "code_execution_task",
          "description": "Validate input data format and quality",
          "role": "engineer",
          "capabilities_required": ["code_generation", "code_execution"],
          "dependencies": ["understand_context"],
          "parallel_group": null,
          "estimated_duration_seconds": 30,
          "code_template": {
            "language": "python",
            "template_type": "validation",
            "imports": ["numpy", "pandas", "astropy.io.fits"],
            "logic_description": "Load data file, check format, validate columns, assess quality",
            "expected_operations": [
              "file_read",
              "schema_check",
              "null_check",
              "range_validation"
            ]
          },
          "inputs": {
            "from_skill_inputs": ["input_file_path"],
            "from_previous_tasks": ["understand_context.context_summary"]
          },
          "outputs": {
            "validation_status": "boolean",
            "data_schema": "object",
            "quality_report": "object"
          },
          "error_handling": {
            "on_validation_failure": "raise_error",
            "retry_allowed": false
          }
        },
        {
          "task_id": "preprocess_data",
          "name": "Data Preprocessing",
          "type": "code_execution_task",
          "description": "Bin, normalize, and prepare data for analysis",
          "role": "engineer",
          "capabilities_required": ["code_generation", "code_execution"],
          "dependencies": ["validate_data"],
          "parallel_group": null,
          "estimated_duration_seconds": 60,
          "code_template": {
            "language": "python",
            "template_type": "transformation",
            "logic_description": "Apply binning, calculate errors, normalize",
            "parameterized": true,
            "parameters_from_inputs": ["analysis_parameters.bin_width"]
          },
          "inputs": {
            "from_skill_inputs": ["input_file_path", "analysis_parameters"],
            "from_previous_tasks": ["validate_data.data_schema"]
          },
          "outputs": {
            "preprocessed_data_path": "string",
            "preprocessing_log": "object"
          }
        },
        {
          "task_id": "run_analysis",
          "name": "Bayesian Analysis",
          "type": "code_execution_task",
          "description": "Run statistical analysis on preprocessed data",
          "role": "executor",
          "capabilities_required": ["code_execution", "computation"],
          "dependencies": ["preprocess_data"],
          "parallel_group": "analysis_and_viz",
          "estimated_duration_seconds": 180,
          "compute_requirements": {
            "memory_mb": 512,
            "cpu_cores": 2,
            "gpu": false
          },
          "code_template": {
            "language": "python",
            "template_type": "analysis",
            "frameworks": ["scipy", "emcee"],
            "logic_description": "Run MCMC sampling for parameter estimation"
          },
          "inputs": {
            "from_previous_tasks": ["preprocess_data.preprocessed_data_path"],
            "from_skill_inputs": ["analysis_parameters"]
          },
          "outputs": {
            "parameter_estimates": "object",
            "posterior_samples": "array",
            "convergence_metrics": "object"
          },
          "success_criteria": [
            {
              "check": "outputs.convergence_metrics.gelman_rubin < 1.1",
              "critical": true,
              "on_failure": "retry_with_more_steps"
            }
          ]
        },
        {
          "task_id": "generate_plots",
          "name": "Visualization",
          "type": "code_execution_task",
          "description": "Create plots of data and results",
          "role": "engineer",
          "capabilities_required": ["code_generation", "visualization"],
          "dependencies": ["preprocess_data"],
          "parallel_group": "analysis_and_viz",
          "estimated_duration_seconds": 45,
          "code_template": {
            "language": "python",
            "template_type": "visualization",
            "frameworks": ["matplotlib", "seaborn"],
            "plot_types": ["line_plot", "scatter_plot", "corner_plot"]
          },
          "inputs": {
            "from_previous_tasks": ["preprocess_data.preprocessed_data_path"]
          },
          "outputs": {
            "plot_files": "array"
          }
        },
        {
          "task_id": "generate_report",
          "name": "Report Generation",
          "type": "agent_task",
          "description": "Compile results into structured report",
          "role": "formatter",
          "capabilities_required": ["synthesis", "formatting"],
          "dependencies": ["run_analysis", "generate_plots"],
          "parallel_group": null,
          "estimated_duration_seconds": 30,
          "inputs": {
            "from_previous_tasks": [
              "run_analysis.parameter_estimates",
              "run_analysis.convergence_metrics",
              "generate_plots.plot_files"
            ]
          },
          "outputs": {
            "report": "string"
          }
        }
      ],
      "parallel_groups": {
        "analysis_and_viz": {
          "tasks": ["run_analysis", "generate_plots"],
          "execution": "parallel",
          "wait_for_all": true
        }
      }
    },
    
    "matching": {
      "pattern_signature": {
        "task_types": ["data_analysis", "statistical_analysis"],
        "domain": ["cosmology", "astronomy", "physics"],
        "keywords": ["power spectrum", "cmb", "bayesian", "mcmc"],
        "input_characteristics": {
          "file_formats": [".fits", ".dat", ".csv"],
          "data_structure": "tabular",
          "size_range_mb": [0.1, 500]
        },
        "complexity": "medium",
        "computational_intensity": "high"
      },
      "preconditions": [
        {
          "type": "llm_intent_match",
          "description": "Task involves analyzing power spectrum data",
          "confidence_threshold": 0.75
        },
        {
          "type": "input_validation",
          "description": "Input file exists and is readable",
          "critical": true
        },
        {
          "type": "capability_check",
          "required_capabilities": ["code_execution", "knowledge_retrieval"],
          "critical": true
        }
      ],
      "embedding_vector": "<1536-dimensional vector for similarity search>"
    },
    
    "quality": {
      "performance_metrics": {
        "success_rate": 0.947,
        "usage_count": 127,
        "avg_execution_time_seconds": 285,
        "avg_cost_usd": 0.18,
        "last_used": "2026-01-20T18:45:00Z"
      },
      "postconditions": [
        {
          "check": "outputs.analysis_results != null",
          "critical": true
        },
        {
          "check": "outputs.visualization_files.length >= 2",
          "critical": false
        },
        {
          "check": "outputs.report.length > 100",
          "critical": true
        }
      ]
    },
    
    "framework_adapters": {
      "ag2": {
        "agent_mapping": {
          "researcher": "ResearcherAgent",
          "engineer": "EngineerAgent",
          "executor": "ExecutorAgent",
          "formatter": "FormatterAgent"
        },
        "execution_pattern": "groupchat",
        "context_carryover": true,
        "implementation_notes": "Use GroupChat with auto speaker selection"
      },
      "langgraph": {
        "node_mapping": {
          "understand_context": "researcher_node",
          "validate_data": "validator_node",
          "preprocess_data": "preprocessor_node",
          "run_analysis": "analyzer_node",
          "generate_plots": "visualizer_node",
          "generate_report": "reporter_node"
        },
        "edges": [
          ["understand_context", "validate_data"],
          ["validate_data", "preprocess_data"],
          ["preprocess_data", "run_analysis"],
          ["preprocess_data", "generate_plots"],
          ["run_analysis", "generate_report"],
          ["generate_plots", "generate_report"]
        ],
        "state_schema": "defined_in_adapter",
        "implementation_notes": "Use conditional edges for parallel group"
      },
      "temporal": {
        "workflow_name": "CMBPowerSpectrumAnalysisWorkflow",
        "activity_mapping": {
          "understand_context": "QueryKnowledgeBaseActivity",
          "validate_data": "ValidateDataActivity",
          "preprocess_data": "PreprocessDataActivity",
          "run_analysis": "RunBayesianAnalysisActivity",
          "generate_plots": "GeneratePlotsActivity",
          "generate_report": "GenerateReportActivity"
        },
        "implementation_notes": "Use async activities for parallel execution"
      },
      "airflow": {
        "dag_id": "cmb_power_spectrum_analysis",
        "operator_mapping": {
          "understand_context": "PythonOperator",
          "validate_data": "PythonOperator",
          "preprocess_data": "PythonOperator",
          "run_analysis": "PythonOperator",
          "generate_plots": "PythonOperator",
          "generate_report": "PythonOperator"
        },
        "implementation_notes": "Use TaskGroups for parallel execution"
      }
    }
  }
}
```

### 1.3 Key Portability Features

#### A. Framework-Agnostic Task Specification
```json
{
  "task": {
    "task_id": "analyze_data",
    "type": "code_execution_task",  // Generic type
    "role": "engineer",              // Role, not specific agent class
    "capabilities_required": [       // What's needed, not how
      "code_generation",
      "code_execution"
    ],
    "tools": [                       // OpenAPI specs, not framework-specific
      {
        "name": "execute_code",
        "openapi_spec": { /* ... */ }
      }
    ]
  }
}
```

#### B. Declarative Workflow (DAG)
```json
{
  "workflow": {
    "type": "dag",
    "tasks": [ /* ... */ ],
    "dependencies": "defined_per_task",
    "parallel_groups": { /* ... */ }
  }
}
```

Any orchestration engine can interpret this!

#### C. Standard Tool Specifications (OpenAPI)
```json
{
  "tool": {
    "name": "query_rag",
    "openapi_spec": {
      "function": "query_knowledge_base",
      "parameters": {
        "query": {"type": "string"},
        "indices": {"type": "array"}
      },
      "returns": {"type": "array"}
    }
  }
}
```

---

## Part 2: LLM-Based Skill Extraction

### 2.1 Can We Feed Complete Context to LLM? **YES!**

**The Key Insight:** Your `execution_events` table already captures EVERYTHING needed for skill extraction!

```
COMPLETE EXECUTION CONTEXT
──────────────────────────────────────────────────────
1. Task Description (from workflow_run)
2. All Agent Messages (from messages table)
3. All Execution Events (from execution_events)
   ├─ Agent calls
   ├─ Tool calls
   ├─ Code executions
   ├─ File generations
   ├─ Hand-offs
   └─ Errors & retries
4. Generated Files (from files table)
5. Cost & Duration (from cost_records)
6. Final Outputs (from workflow_run.result)
```

### 2.2 LLM Skill Extraction Pipeline

```python
from cmbagent.skills import LLMSkillExtractor

class LLMSkillExtractor:
    """Extract skills using LLM analysis of complete execution context"""
    
    def extract_skill(self, run_id: str, branch_id: str = None) -> dict:
        """
        Extract skill by feeding complete execution context to LLM
        
        Args:
            run_id: Workflow run to extract from
            branch_id: Specific branch (if comparing branches)
        
        Returns:
            Complete skill definition (framework-agnostic)
        """
        # 1. Gather complete context
        context = self._gather_execution_context(run_id, branch_id)
        
        # 2. Build LLM prompt
        prompt = self._build_extraction_prompt(context)
        
        # 3. Call LLM with structured output
        skill_json = self._call_llm_with_schema(prompt)
        
        # 4. Validate and enrich
        skill = self._validate_and_enrich(skill_json, context)
        
        return skill
    
    def _gather_execution_context(self, run_id: str, branch_id: str) -> dict:
        """Gather ALL context from database"""
        
        # Get workflow run
        run = db.query(WorkflowRun).filter_by(id=run_id).first()
        
        # Get all execution events (this is the goldmine!)
        events = db.query(ExecutionEvent).filter_by(
            run_id=run_id
        ).order_by(ExecutionEvent.timestamp).all()
        
        # Get all messages
        messages = db.query(Message).filter_by(
            run_id=run_id
        ).order_by(Message.created_at).all()
        
        # Get generated files
        files = db.query(File).filter_by(run_id=run_id).all()
        
        # Get DAG structure
        nodes = db.query(DAGNode).filter_by(run_id=run_id).all()
        edges = self._get_dag_edges(nodes)
        
        # Get cost records
        costs = db.query(CostRecord).filter_by(run_id=run_id).all()
        
        # Build comprehensive context
        context = {
            "task": {
                "description": run.goal,
                "type": run.strategy,
                "duration_seconds": (run.end_time - run.start_time).total_seconds(),
                "status": run.status
            },
            "execution_flow": self._reconstruct_execution_flow(events, nodes),
            "agent_interactions": self._extract_agent_interactions(messages, events),
            "code_executions": self._extract_code_executions(events),
            "tool_usage": self._extract_tool_usage(events),
            "data_flow": self._trace_data_flow(events),
            "decisions_made": self._extract_decisions(messages, events),
            "errors_and_retries": self._extract_error_patterns(events),
            "generated_artifacts": self._summarize_files(files),
            "performance": {
                "total_duration_seconds": (run.end_time - run.start_time).total_seconds(),
                "total_cost_usd": sum(c.total_cost for c in costs),
                "total_tokens": sum(c.total_tokens for c in costs)
            },
            "dag_structure": {
                "nodes": [{"id": n.node_id, "name": n.name, "status": n.status} for n in nodes],
                "edges": edges,
                "parallel_groups": self._identify_parallel_groups(nodes, edges)
            }
        }
        
        return context
    
    def _build_extraction_prompt(self, context: dict) -> str:
        """Build comprehensive prompt for LLM skill extraction"""
        
        prompt = f"""
# Task: Extract Reusable Skill from Successful Workflow Execution

You are analyzing a successful workflow execution to extract a reusable skill that can be applied to similar tasks in the future.

## Original Task
{context['task']['description']}

## Execution Summary
- Strategy: {context['task']['type']}
- Duration: {context['task']['duration_seconds']} seconds
- Status: {context['task']['status']}

## Execution Flow
{self._format_execution_flow(context['execution_flow'])}

## Agent Interactions
{self._format_agent_interactions(context['agent_interactions'])}

## Code Executions
{self._format_code_executions(context['code_executions'])}

## Tool Usage
{self._format_tool_usage(context['tool_usage'])}

## Data Flow
{self._format_data_flow(context['data_flow'])}

## Decisions Made
{self._format_decisions(context['decisions_made'])}

## Errors & Recovery
{self._format_errors(context['errors_and_retries'])}

## Generated Artifacts
{self._format_artifacts(context['generated_artifacts'])}

## DAG Structure
Nodes: {json.dumps(context['dag_structure']['nodes'], indent=2)}
Edges: {json.dumps(context['dag_structure']['edges'], indent=2)}
Parallel Groups: {json.dumps(context['dag_structure']['parallel_groups'], indent=2)}

## Performance Metrics
- Total Duration: {context['performance']['total_duration_seconds']}s
- Total Cost: ${context['performance']['total_cost_usd']}
- Total Tokens: {context['performance']['total_tokens']}

---

# Your Task

Extract a **framework-agnostic, reusable skill** from this execution. The skill should:

1. **Generalize** the approach (not specific to this exact input)
2. **Capture the pattern** (what made this execution successful)
3. **Be portable** (work with any orchestration framework)
4. **Include all necessary details** for replication

Generate a JSON object following this schema:

{{
  "skill_schema_version": "1.0",
  "skill": {{
    "metadata": {{
      "name": "descriptive_skill_name",
      "description": "What this skill does",
      "category": "category",
      "tags": ["tag1", "tag2"]
    }},
    "interface": {{
      "inputs": [
        {{
          "name": "input_name",
          "type": "type",
          "description": "description",
          "required": true/false
        }}
      ],
      "outputs": [/* similar structure */]
    }},
    "workflow": {{
      "type": "dag",
      "tasks": [
        {{
          "task_id": "unique_id",
          "name": "Task Name",
          "type": "agent_task|code_execution_task|tool_call_task",
          "description": "What this task does",
          "role": "researcher|engineer|executor|formatter",
          "capabilities_required": ["capability1", "capability2"],
          "dependencies": ["task_id1", "task_id2"],
          "parallel_group": null or "group_name",
          "estimated_duration_seconds": X,
          "tools": [/* tool specs */],
          "code_template": {{
            "language": "python",
            "logic_description": "What the code should do",
            "frameworks": ["numpy", "scipy"]
          }},
          "inputs": {{
            "from_skill_inputs": ["input_name"],
            "from_previous_tasks": ["task.output"]
          }},
          "outputs": {{
            "output_name": "type"
          }}
        }}
      ]
    }},
    "matching": {{
      "pattern_signature": {{
        "task_types": ["type1", "type2"],
        "keywords": ["keyword1", "keyword2"],
        "input_characteristics": {{ /* ... */ }}
      }},
      "preconditions": [/* when to apply this skill */]
    }},
    "quality": {{
      "performance_metrics": {{
        "estimated_execution_time_seconds": X,
        "estimated_cost_usd": Y
      }},
      "postconditions": [/* expected outcomes */]
    }}
  }}
}}

**Important Guidelines:**

1. **Abstract away specifics**: Replace file paths with parameters, specific values with variables
2. **Identify the core pattern**: What is the essential sequence that leads to success?
3. **Capture decision logic**: What made agents choose specific approaches?
4. **Generalize tool usage**: How were tools used effectively?
5. **Note error recovery**: What retry strategies worked?
6. **Define success criteria**: What indicates this skill completed successfully?

Generate the complete skill JSON now:
"""
        
        return prompt
    
    def _call_llm_with_schema(self, prompt: str) -> dict:
        """Call LLM with structured output schema"""
        
        from openai import OpenAI
        
        client = OpenAI()
        
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing workflow executions and extracting reusable patterns. You generate precise, framework-agnostic skill definitions."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3,  # Lower temperature for consistency
            max_tokens=4000
        )
        
        skill_json = json.loads(response.choices[0].message.content)
        
        return skill_json
    
    def _validate_and_enrich(self, skill_json: dict, context: dict) -> dict:
        """Validate LLM output and enrich with metadata"""
        
        # Add provenance
        skill_json["skill"]["provenance"] = {
            "source_system": "cmbagent",
            "extracted_from_run_id": context["task"]["id"],
            "extraction_method": "llm_analysis",
            "extraction_date": datetime.utcnow().isoformat(),
            "extraction_confidence": self._calculate_confidence(skill_json, context)
        }
        
        # Generate embedding for similarity search
        embedding = self._generate_embedding(skill_json)
        skill_json["skill"]["matching"]["embedding_vector"] = embedding.tolist()
        
        # Add actual performance metrics from execution
        skill_json["skill"]["quality"]["performance_metrics"]["actual"] = context["performance"]
        
        # Validate schema
        self._validate_schema(skill_json)
        
        return skill_json
    
    def _generate_embedding(self, skill_json: dict) -> np.ndarray:
        """Generate embedding vector for skill matching"""
        
        # Combine key text fields
        text_parts = [
            skill_json["skill"]["metadata"]["name"],
            skill_json["skill"]["metadata"]["description"],
            " ".join(skill_json["skill"]["metadata"]["tags"]),
            " ".join(skill_json["skill"]["matching"]["pattern_signature"]["keywords"])
        ]
        
        text = " ".join(text_parts)
        
        # Generate embedding using OpenAI
        from openai import OpenAI
        client = OpenAI()
        
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        
        return np.array(response.data[0].embedding)
```

### 2.3 Example: Full Context → LLM → Skill

**Input Context (Simplified):**
```
Task: "Analyze CMB power spectrum from Planck data"

Execution Flow:
  1. researcher_agent: Queried RAG for "CMB power spectrum" → 5 papers found
  2. engineer_agent: Wrote validation code → executed successfully
  3. engineer_agent: Wrote preprocessing code → executed successfully  
  4. executor_agent: Ran MCMC analysis → initially failed (convergence)
  5. executor_agent: Retried with more steps → succeeded
  6. engineer_agent: Generated 3 plots → successful
  7. formatter_agent: Created markdown report → complete

Code Executions:
  - validation.py: Loaded FITS, checked columns, validated data (30s)
  - preprocess.py: Binned data, calculated errors (60s)
  - analyze.py: MCMC with 5000 steps → failed
  - analyze.py: MCMC with 10000 steps → succeeded (180s)
  - plot.py: Created power_spectrum.png, residuals.png, corner.png (45s)

Tools Used:
  - RAG query (3 times): planck_papers index
  - Code executor (5 times): Python code execution

Data Flow:
  planck_data.fits → validate → preprocessed.csv → analyze → results.json
                                                  → plot → *.png files
                                                  
Decisions:
  - Chose MCMC over grid search (based on RAG findings)
  - Used emcee sampler (mentioned in literature)
  - Retry with 2x steps on convergence failure
```

**LLM Output (Skill):**
```json
{
  "skill": {
    "metadata": {
      "name": "cmb_power_spectrum_bayesian_analysis",
      "description": "Validates, preprocesses, and performs Bayesian analysis on CMB power spectrum data using MCMC methods"
    },
    "workflow": {
      "tasks": [
        {
          "task_id": "research_methods",
          "role": "researcher",
          "description": "Query literature for optimal analysis methods",
          "tools": [{"name": "rag_query", "indices": ["planck_papers", "bayesian_methods"]}]
        },
        {
          "task_id": "validate",
          "role": "engineer",
          "code_template": {
            "logic_description": "Load FITS file, validate columns [ell, tt, ee], check for NaNs"
          }
        },
        {
          "task_id": "analyze",
          "role": "executor",
          "code_template": {
            "frameworks": ["emcee"],
            "parameters": {"n_steps": 5000, "n_walkers": 32}
          },
          "error_handling": {
            "on_convergence_failure": {
              "strategy": "increase_mcmc_steps",
              "multiplier": 2,
              "max_retries": 2
            }
          }
        }
        // ... rest of workflow
      ]
    }
  }
}
```

**The LLM successfully extracted:**
- ✅ The core workflow pattern
- ✅ Tool usage strategy (RAG for methods, code executor)
- ✅ Error recovery pattern (2x MCMC steps on failure)
- ✅ Data flow and dependencies
- ✅ Generalized parameters

---

## Part 3: Implementation Architecture

### 3.1 Skill Extraction Service

```python
class SkillExtractionService:
    """Service for extracting and managing skills"""
    
    def __init__(self, db_session, llm_client):
        self.db = db_session
        self.llm = llm_client
        self.extractor = LLMSkillExtractor(db_session, llm_client)
        self.validator = SkillValidator()
        self.registry = SkillRegistry(db_session)
    
    async def extract_skill_from_run(
        self,
        run_id: str,
        user_feedback: dict = None,
        auto_approve: bool = False
    ) -> Skill:
        """
        Extract skill from successful run
        
        Args:
            run_id: Workflow run ID
            user_feedback: Optional user annotations
            auto_approve: Skip human review
        
        Returns:
            Extracted skill object
        """
        # 1. Verify run was successful
        run = self.db.query(WorkflowRun).filter_by(id=run_id).first()
        if run.status != "completed":
            raise ValueError("Can only extract skills from completed runs")
        
        # 2. Extract using LLM
        skill_json = await self.extractor.extract_skill(run_id)
        
        # 3. Incorporate user feedback if provided
        if user_feedback:
            skill_json = self._incorporate_feedback(skill_json, user_feedback)
        
        # 4. Validate schema
        self.validator.validate(skill_json)
        
        # 5. Human review (unless auto-approved)
        if not auto_approve:
            skill_json = await self._request_human_review(skill_json)
        
        # 6. Save to database
        skill = Skill(**skill_json["skill"])
        self.db.add(skill)
        self.db.commit()
        
        # 7. Register in skill library
        self.registry.register(skill)
        
        return skill
    
    async def extract_skill_from_branches(
        self,
        branch_ids: List[str],
        comparison_criteria: dict
    ) -> Skill:
        """
        Extract skill by comparing multiple branches
        
        Chooses best approach based on criteria
        """
        # Compare branches
        comparator = BranchComparator(self.db)
        best_branch = comparator.select_best(branch_ids, comparison_criteria)
        
        # Extract from best branch
        skill = await self.extract_skill_from_run(best_branch.run_id)
        
        # Add comparison metadata
        skill.provenance["branches_compared"] = len(branch_ids)
        skill.provenance["selection_criteria"] = comparison_criteria
        
        return skill
```

### 3.2 Framework Adapter Pattern

```python
class SkillAdapter(ABC):
    """Base class for framework-specific adapters"""
    
    @abstractmethod
    def load_skill(self, skill_json: dict):
        """Load skill into framework-specific format"""
        pass
    
    @abstractmethod
    def execute_skill(self, inputs: dict) -> dict:
        """Execute skill using this framework"""
        pass

class AG2SkillAdapter(SkillAdapter):
    """Adapter for AG2 (AutoGen) framework"""
    
    def load_skill(self, skill_json: dict):
        """Convert skill to AG2 agents and GroupChat"""
        
        # Create agents based on roles
        agents = {}
        for task in skill_json["skill"]["workflow"]["tasks"]:
            role = task["role"]
            if role not in agents:
                agents[role] = self._create_agent(role, skill_json)
        
        # Setup GroupChat
        group_chat = GroupChat(
            agents=list(agents.values()),
            messages=[],
            max_round=50
        )
        
        return {
            "agents": agents,
            "group_chat": group_chat,
            "skill_def": skill_json
        }
    
    def execute_skill(self, skill_loaded, inputs: dict) -> dict:
        """Execute skill using AG2"""
        
        # Build initial prompt from inputs
        prompt = self._build_prompt_from_inputs(
            skill_loaded["skill_def"],
            inputs
        )
        
        # Execute GroupChat
        manager = GroupChatManager(
            groupchat=skill_loaded["group_chat"]
        )
        
        result = skill_loaded["agents"]["planner"].initiate_chat(
            manager,
            message=prompt
        )
        
        return self._extract_outputs(result, skill_loaded["skill_def"])

class LangGraphSkillAdapter(SkillAdapter):
    """Adapter for LangGraph framework"""
    
    def load_skill(self, skill_json: dict):
        """Convert skill to LangGraph graph"""
        from langgraph.graph import StateGraph
        
        # Build graph structure
        graph = StateGraph(state_schema=self._build_state_schema(skill_json))
        
        # Add nodes for each task
        for task in skill_json["skill"]["workflow"]["tasks"]:
            node_func = self._create_node_function(task)
            graph.add_node(task["task_id"], node_func)
        
        # Add edges based on dependencies
        for task in skill_json["skill"]["workflow"]["tasks"]:
            for dep in task["dependencies"]:
                graph.add_edge(dep, task["task_id"])
        
        return graph.compile()
    
    def execute_skill(self, compiled_graph, inputs: dict) -> dict:
        """Execute skill using LangGraph"""
        result = compiled_graph.invoke(inputs)
        return result

# Usage
adapter = AG2SkillAdapter()
skill_loaded = adapter.load_skill(skill_json)
result = adapter.execute_skill(skill_loaded, {
    "input_file_path": "data.fits"
})
```

---

## Part 4: Benefits & Future

### 4.1 Benefits of This Approach

1. **Framework Independence:** Skills work with any orchestration engine
2. **LLM-Powered Extraction:** Automatic pattern recognition
3. **Human Oversight:** Review and refine before deployment
4. **Version Control:** Track skill evolution over time
5. **Composability:** Skills can reference other skills
6. **Transparency:** Full provenance from extraction to usage

### 4.2 Future Enhancements

1. **Cross-Framework Testing:** Test same skill on AG2, LangGraph, Temporal
2. **Skill Composition:** Combine multiple skills into workflows
3. **Active Learning:** Skills improve from usage feedback
4. **Skill Marketplace:** Share skills across organizations
5. **Automated Adaptation:** LLM adapts skills to new contexts

---

## Conclusion

**Yes, we can give complete execution context to LLM for skill creation!**

Your execution_events table is the perfect foundation - it captures everything needed. The LLM analyzes this rich context and extracts a **portable, framework-agnostic skill** that can be used by any orchestration engine through adapters.

**This is the ultimate goal:** Learn from experience → Extract patterns → Reuse efficiently
