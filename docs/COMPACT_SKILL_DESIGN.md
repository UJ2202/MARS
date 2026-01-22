# Compact, Reference-Based Skill Design

**Date:** January 21, 2026  
**Purpose:** Lightweight skill structure with artifact references for cross-platform execution

---

## Design Philosophy

### Core Principles

1. **Compact Manifest** (~5-20KB JSON) - Fits in LLM context window
2. **Artifact References** - URIs to code/docs, not embedded content
3. **Prompt-Ready** - Can be directly fed to any LLM orchestrator
4. **Platform-Agnostic** - Works with LangGraph, Google ADK, AG2, etc.
5. **Modifiable** - Agents can fetch and adapt artifacts as needed

### The Separation

```
┌─────────────────────────────────────────────────────┐
│  SKILL MANIFEST (Compact, Prompt-Ready)             │
│  • What to do (workflow pattern)                    │
│  • References to artifacts                          │
│  • When it applies                                  │
│  • Success criteria                                 │
│  Size: 5-20KB                                       │
└─────────────────────────────────────────────────────┘
                      ↓ references
┌─────────────────────────────────────────────────────┐
│  ARTIFACT STORE (Fetchable On-Demand)               │
│  • Code files (validation.py, analysis.py)          │
│  • Config templates (mcmc_config.yaml)              │
│  • Documentation (methodology.md)                   │
│  • Example data (sample_input.fits)                 │
│  Size: Can be large, fetched only when needed       │
└─────────────────────────────────────────────────────┘
```

---

## Part 1: Skill Manifest Structure

### 1.1 Complete Manifest Schema

```json
{
  "skill_manifest_version": "1.0",
  "manifest": {
    "identity": {
      "skill_id": "sk_a3f7b2c1_4e8d_4a9b",
      "name": "cmb_power_spectrum_analysis",
      "version": "2.1.0",
      "description": "Analyzes CMB power spectrum using Bayesian MCMC methods",
      "category": "data_analysis",
      "tags": ["cmb", "bayesian", "mcmc", "astronomy"],
      "created_at": "2026-01-15T10:30:00Z",
      "language": "en"
    },
    
    "provenance": {
      "source_system": "cmbagent",
      "source_run_id": "80746129-1c39-4d3a-b0a6-6a327113438e",
      "extraction_method": "llm_analysis",
      "extracted_at": "2026-01-15T10:35:00Z",
      "confidence_score": 0.95,
      "human_reviewed": true
    },
    
    "applicability": {
      "task_pattern": {
        "task_types": ["data_analysis", "statistical_analysis"],
        "keywords": ["power spectrum", "cmb", "analyze", "bayesian"],
        "domain": ["cosmology", "astronomy"]
      },
      "input_requirements": {
        "file_types": [".fits", ".dat", ".csv"],
        "data_structure": "tabular_numerical",
        "size_range_mb": {"min": 0.1, "max": 500},
        "required_columns": ["ell", "cl_tt"]
      },
      "preconditions": [
        {
          "check": "input_file_exists",
          "critical": true,
          "description": "Input data file must be accessible"
        },
        {
          "check": "has_numerical_data",
          "critical": true,
          "description": "File must contain numerical tabular data"
        },
        {
          "check": "sufficient_data_points",
          "threshold": 100,
          "critical": false,
          "description": "At least 100 data points recommended"
        }
      ],
      "capabilities_required": [
        "code_generation",
        "code_execution",
        "file_io",
        "data_visualization"
      ]
    },
    
    "workflow": {
      "execution_model": "dag",
      "estimated_duration_seconds": 285,
      "estimated_cost_usd": 0.18,
      
      "steps": [
        {
          "step_id": "research_context",
          "name": "Literature Research",
          "type": "knowledge_retrieval",
          "description": "Query domain knowledge about power spectrum analysis methods",
          "role": "researcher",
          "dependencies": [],
          "parallel_group": null,
          "estimated_duration_seconds": 45,
          
          "instructions": {
            "goal": "Understand CMB power spectrum analysis and identify best practices",
            "approach": "Query knowledge bases for relevant methodology",
            "deliverable": "Summary of methods and recommendations"
          },
          
          "tools": [
            {
              "tool_name": "rag_query",
              "tool_type": "knowledge_retrieval",
              "required": true,
              "parameters": {
                "indices": ["planck_papers", "bayesian_methods"],
                "max_results": 5,
                "focus_areas": ["mcmc", "convergence", "error_analysis"]
              }
            }
          ],
          
          "artifacts": {
            "reference_docs": [
              {
                "artifact_id": "art_methodology_overview",
                "uri": "skill://sk_a3f7b2c1/artifacts/methodology_overview.md",
                "type": "documentation",
                "purpose": "Reference methodology from previous successful run",
                "size_kb": 12,
                "usage": "optional_context"
              }
            ]
          },
          
          "outputs": {
            "context_summary": {
              "type": "text",
              "description": "Summary of relevant methods"
            },
            "recommended_approach": {
              "type": "structured",
              "description": "Specific analysis approach to use"
            }
          }
        },
        
        {
          "step_id": "validate_data",
          "name": "Data Validation",
          "type": "code_execution",
          "description": "Validate input data format, structure, and quality",
          "role": "engineer",
          "dependencies": ["research_context"],
          "parallel_group": null,
          "estimated_duration_seconds": 30,
          
          "instructions": {
            "goal": "Ensure data is valid and suitable for analysis",
            "approach": "Load data, check schema, validate quality metrics",
            "key_checks": [
              "File loads successfully",
              "Required columns present",
              "No NaN/Inf values",
              "Data ranges are reasonable"
            ],
            "deliverable": "Validation report with pass/fail status"
          },
          
          "code_artifacts": [
            {
              "artifact_id": "art_validation_code",
              "uri": "skill://sk_a3f7b2c1/artifacts/validate_power_spectrum.py",
              "type": "python_code",
              "purpose": "Reference implementation of validation logic",
              "size_kb": 3.2,
              "language": "python",
              "framework": ["numpy", "pandas", "astropy"],
              "usage": "template",
              "modification_guidance": {
                "what_to_adapt": [
                  "Update column names if different",
                  "Adjust validation thresholds for your data",
                  "Add domain-specific checks"
                ],
                "what_to_keep": [
                  "Overall validation structure",
                  "Error handling pattern",
                  "Logging approach"
                ],
                "example_modifications": [
                  "Change 'ell' to 'multipole' if needed",
                  "Adjust min_points threshold (currently 100)"
                ]
              }
            }
          ],
          
          "execution_context": {
            "environment": "python3.9+",
            "required_packages": ["numpy", "pandas", "astropy"],
            "timeout_seconds": 60,
            "memory_limit_mb": 256
          },
          
          "outputs": {
            "validation_status": {
              "type": "boolean",
              "description": "True if data passes all checks"
            },
            "data_schema": {
              "type": "object",
              "description": "Detected columns and data types"
            },
            "quality_metrics": {
              "type": "object",
              "description": "Data quality statistics"
            }
          },
          
          "error_handling": {
            "on_failure": "stop_workflow",
            "retry_allowed": false,
            "error_context": "Validation failure means data is unsuitable"
          }
        },
        
        {
          "step_id": "preprocess_data",
          "name": "Data Preprocessing",
          "type": "code_execution",
          "description": "Bin, normalize, and calculate errors",
          "role": "engineer",
          "dependencies": ["validate_data"],
          "parallel_group": null,
          "estimated_duration_seconds": 60,
          
          "instructions": {
            "goal": "Transform data into format suitable for Bayesian analysis",
            "approach": "Apply binning, calculate statistical errors, normalize",
            "deliverable": "Preprocessed data file ready for MCMC"
          },
          
          "code_artifacts": [
            {
              "artifact_id": "art_preprocess_code",
              "uri": "skill://sk_a3f7b2c1/artifacts/preprocess_power_spectrum.py",
              "type": "python_code",
              "purpose": "Reference preprocessing implementation",
              "size_kb": 5.8,
              "language": "python",
              "framework": ["numpy", "scipy"],
              "usage": "template",
              "key_functions": [
                "bin_power_spectrum(data, bin_width)",
                "calculate_errors(binned_data, method='cosmic_variance')",
                "normalize_spectrum(data, normalization='peak')"
              ],
              "modification_guidance": {
                "parameters_to_adjust": {
                  "bin_width": "Default 10, adjust based on data density",
                  "error_method": "Options: 'cosmic_variance', 'bootstrap', 'jackknife'",
                  "normalization": "Options: 'peak', 'integral', 'none'"
                }
              }
            },
            {
              "artifact_id": "art_preprocess_config",
              "uri": "skill://sk_a3f7b2c1/artifacts/preprocess_config.yaml",
              "type": "configuration",
              "purpose": "Default preprocessing parameters",
              "size_kb": 0.5,
              "usage": "reference"
            }
          ],
          
          "outputs": {
            "preprocessed_data_path": {
              "type": "file_path",
              "format": "csv",
              "description": "Path to preprocessed data"
            },
            "preprocessing_log": {
              "type": "object",
              "description": "Parameters used and transformations applied"
            }
          }
        },
        
        {
          "step_id": "run_bayesian_analysis",
          "name": "MCMC Parameter Estimation",
          "type": "code_execution",
          "description": "Run Bayesian MCMC to estimate parameters",
          "role": "executor",
          "dependencies": ["preprocess_data"],
          "parallel_group": "analysis_visualization",
          "estimated_duration_seconds": 180,
          
          "instructions": {
            "goal": "Estimate cosmological parameters with uncertainties",
            "approach": "MCMC sampling using emcee with convergence checking",
            "critical_outputs": [
              "Parameter estimates with uncertainties",
              "Posterior samples for plotting",
              "Convergence diagnostics (Gelman-Rubin)"
            ],
            "deliverable": "Statistical results with convergence proof"
          },
          
          "code_artifacts": [
            {
              "artifact_id": "art_mcmc_code",
              "uri": "skill://sk_a3f7b2c1/artifacts/run_mcmc_analysis.py",
              "type": "python_code",
              "purpose": "MCMC implementation with proven convergence strategy",
              "size_kb": 12.4,
              "language": "python",
              "framework": ["emcee", "scipy", "numpy"],
              "usage": "template",
              "key_components": {
                "likelihood_function": "Chi-squared likelihood for power spectrum",
                "prior_definitions": "Flat priors on physical ranges",
                "sampler_config": "32 walkers, 5000 steps, burn-in 1000",
                "convergence_check": "Gelman-Rubin < 1.1"
              },
              "modification_guidance": {
                "model_customization": "Update likelihood function for your model",
                "prior_adjustment": "Set physically meaningful prior ranges",
                "convergence_tuning": "If not converging, try: increase steps (×2), increase walkers (+10), check initial positions"
              }
            }
          ],
          
          "compute_requirements": {
            "cpu_cores": 2,
            "memory_mb": 512,
            "gpu": false,
            "timeout_seconds": 300
          },
          
          "outputs": {
            "parameter_estimates": {
              "type": "object",
              "schema": {
                "parameters": "dict[str, float]",
                "uncertainties": "dict[str, tuple[float, float]]",
                "confidence_level": "float"
              }
            },
            "posterior_samples": {
              "type": "array",
              "format": "npy",
              "description": "MCMC chain samples"
            },
            "convergence_metrics": {
              "type": "object",
              "required_fields": ["gelman_rubin", "acceptance_rate", "autocorr_time"]
            }
          },
          
          "success_criteria": [
            {
              "check": "convergence_metrics.gelman_rubin < 1.1",
              "critical": true,
              "on_failure": {
                "action": "retry_with_modifications",
                "modifications": {
                  "n_steps": "multiply_by_2",
                  "n_walkers": "add_10"
                },
                "max_retries": 2
              }
            },
            {
              "check": "convergence_metrics.acceptance_rate > 0.2 AND < 0.5",
              "critical": false,
              "on_failure": {
                "action": "log_warning",
                "message": "Acceptance rate outside optimal range"
              }
            }
          ]
        },
        
        {
          "step_id": "generate_visualizations",
          "name": "Create Plots",
          "type": "code_execution",
          "description": "Generate plots of data and analysis results",
          "role": "engineer",
          "dependencies": ["preprocess_data"],
          "parallel_group": "analysis_visualization",
          "estimated_duration_seconds": 45,
          
          "instructions": {
            "goal": "Create publication-quality visualizations",
            "plots_to_generate": [
              "Power spectrum with best-fit model",
              "Residuals plot",
              "Corner plot of parameter posteriors"
            ],
            "deliverable": "PNG and PDF files with captions"
          },
          
          "code_artifacts": [
            {
              "artifact_id": "art_plotting_code",
              "uri": "skill://sk_a3f7b2c1/artifacts/generate_plots.py",
              "type": "python_code",
              "purpose": "Plotting functions with proven aesthetics",
              "size_kb": 8.6,
              "language": "python",
              "framework": ["matplotlib", "seaborn", "corner"],
              "usage": "template",
              "modification_guidance": {
                "styling": "Adjust colors, fonts, DPI in plot_config.yaml",
                "layout": "Modify subplot arrangements as needed",
                "export": "Add formats: 'svg', 'eps' for publications"
              }
            },
            {
              "artifact_id": "art_plot_config",
              "uri": "skill://sk_a3f7b2c1/artifacts/plot_config.yaml",
              "type": "configuration",
              "purpose": "Plot styling configuration",
              "size_kb": 1.2
            }
          ],
          
          "outputs": {
            "plot_files": {
              "type": "array",
              "item_type": "file_path",
              "expected_count": 3,
              "formats": ["png", "pdf"]
            },
            "plot_metadata": {
              "type": "object",
              "description": "Captions and descriptions for each plot"
            }
          }
        },
        
        {
          "step_id": "generate_report",
          "name": "Compile Results Report",
          "type": "synthesis",
          "description": "Create structured report with all findings",
          "role": "synthesizer",
          "dependencies": ["run_bayesian_analysis", "generate_visualizations"],
          "parallel_group": null,
          "estimated_duration_seconds": 30,
          
          "instructions": {
            "goal": "Synthesize all results into coherent report",
            "sections_to_include": [
              "Executive summary",
              "Data description",
              "Methodology",
              "Results with uncertainties",
              "Visualizations",
              "Quality assessment",
              "Recommendations"
            ],
            "format": "markdown",
            "deliverable": "Complete analysis report"
          },
          
          "artifacts": {
            "report_template": [
              {
                "artifact_id": "art_report_template",
                "uri": "skill://sk_a3f7b2c1/artifacts/report_template.md",
                "type": "documentation",
                "purpose": "Markdown template with structure",
                "size_kb": 2.1,
                "usage": "template"
              }
            ]
          },
          
          "outputs": {
            "final_report": {
              "type": "markdown",
              "min_length": 500,
              "description": "Complete analysis report"
            },
            "results_json": {
              "type": "json",
              "description": "Structured results for programmatic access"
            }
          }
        }
      ],
      
      "parallel_execution": {
        "analysis_visualization": {
          "steps": ["run_bayesian_analysis", "generate_visualizations"],
          "execution_mode": "parallel",
          "wait_for_all": true,
          "note": "These can run simultaneously using preprocessed data"
        }
      },
      
      "data_flow": {
        "inputs": {
          "input_file_path": {
            "type": "string",
            "required": true,
            "description": "Path to input data file"
          },
          "analysis_config": {
            "type": "object",
            "required": false,
            "default": {},
            "description": "Override default parameters"
          }
        },
        "outputs": {
          "parameter_estimates": "from:run_bayesian_analysis",
          "plots": "from:generate_visualizations",
          "report": "from:generate_report"
        }
      }
    },
    
    "quality_assurance": {
      "performance_history": {
        "success_rate": 0.947,
        "usage_count": 127,
        "avg_duration_seconds": 285,
        "avg_cost_usd": 0.18,
        "last_run": "2026-01-20T18:45:00Z"
      },
      
      "postconditions": [
        {
          "check": "outputs.parameter_estimates is not null",
          "critical": true
        },
        {
          "check": "outputs.plots.length >= 2",
          "critical": false
        },
        {
          "check": "outputs.report.length > 500",
          "critical": true
        }
      ],
      
      "known_limitations": [
        "Works best with > 100 data points",
        "May need parameter tuning for highly non-Gaussian data",
        "Convergence can be slow for high-dimensional parameter spaces"
      ],
      
      "failure_modes": [
        {
          "symptom": "Convergence failure (Gelman-Rubin > 1.1)",
          "frequency": "5%",
          "mitigation": "Automatically retries with more MCMC steps"
        },
        {
          "symptom": "Invalid input data",
          "frequency": "3%",
          "mitigation": "Caught early in validation step"
        }
      ]
    },
    
    "usage_guide": {
      "quick_start": "Pass skill_id and input_file_path to orchestrator",
      "typical_use_cases": [
        "Analyzing CMB power spectra from Planck mission",
        "Processing CLASS/CAMB simulation outputs",
        "Parameter estimation from custom simulations"
      ],
      "adaptation_notes": [
        "Modify likelihood function for different models",
        "Adjust MCMC parameters for convergence",
        "Update validation rules for different data formats"
      ]
    },
    
    "artifact_manifest": {
      "total_artifacts": 8,
      "total_size_kb": 45.8,
      "artifact_registry": [
        {
          "artifact_id": "art_methodology_overview",
          "uri": "skill://sk_a3f7b2c1/artifacts/methodology_overview.md",
          "type": "documentation",
          "size_kb": 12.0,
          "checksum": "sha256:abc123..."
        },
        {
          "artifact_id": "art_validation_code",
          "uri": "skill://sk_a3f7b2c1/artifacts/validate_power_spectrum.py",
          "type": "python_code",
          "size_kb": 3.2,
          "checksum": "sha256:def456..."
        },
        {
          "artifact_id": "art_preprocess_code",
          "uri": "skill://sk_a3f7b2c1/artifacts/preprocess_power_spectrum.py",
          "type": "python_code",
          "size_kb": 5.8,
          "checksum": "sha256:ghi789..."
        },
        {
          "artifact_id": "art_preprocess_config",
          "uri": "skill://sk_a3f7b2c1/artifacts/preprocess_config.yaml",
          "type": "configuration",
          "size_kb": 0.5,
          "checksum": "sha256:jkl012..."
        },
        {
          "artifact_id": "art_mcmc_code",
          "uri": "skill://sk_a3f7b2c1/artifacts/run_mcmc_analysis.py",
          "type": "python_code",
          "size_kb": 12.4,
          "checksum": "sha256:mno345..."
        },
        {
          "artifact_id": "art_plotting_code",
          "uri": "skill://sk_a3f7b2c1/artifacts/generate_plots.py",
          "type": "python_code",
          "size_kb": 8.6,
          "checksum": "sha256:pqr678..."
        },
        {
          "artifact_id": "art_plot_config",
          "uri": "skill://sk_a3f7b2c1/artifacts/plot_config.yaml",
          "type": "configuration",
          "size_kb": 1.2,
          "checksum": "sha256:stu901..."
        },
        {
          "artifact_id": "art_report_template",
          "uri": "skill://sk_a3f7b2c1/artifacts/report_template.md",
          "type": "documentation",
          "size_kb": 2.1,
          "checksum": "sha256:vwx234..."
        }
      ]
    }
  }
}
```

**Manifest Size:** ~15KB (compact, prompt-ready)

---

## Part 2: Artifact Storage & Access

### 2.1 Artifact URI Scheme

```
skill://[skill_id]/artifacts/[artifact_path]

Examples:
skill://sk_a3f7b2c1/artifacts/validate_power_spectrum.py
skill://sk_a3f7b2c1/artifacts/preprocess_config.yaml
skill://sk_a3f7b2c1/artifacts/docs/methodology_overview.md
```

### 2.2 Artifact Store Architecture

```
┌─────────────────────────────────────────────────────┐
│            ARTIFACT API                              │
├─────────────────────────────────────────────────────┤
│  GET /artifacts/{skill_id}/{artifact_path}          │
│  → Returns artifact content                          │
│                                                      │
│  GET /artifacts/{skill_id}/manifest                 │
│  → Returns list of all artifacts                     │
│                                                      │
│  POST /artifacts/{skill_id}                         │
│  → Upload new artifact (versioned)                   │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│         STORAGE (S3/MinIO/Filesystem)                │
├─────────────────────────────────────────────────────┤
│  skills/                                             │
│    sk_a3f7b2c1_4e8d_4a9b/                           │
│      v2.1.0/                                         │
│        artifacts/                                    │
│          validate_power_spectrum.py                  │
│          preprocess_power_spectrum.py                │
│          run_mcmc_analysis.py                        │
│          generate_plots.py                           │
│          preprocess_config.yaml                      │
│          plot_config.yaml                            │
│          report_template.md                          │
│          methodology_overview.md                     │
│        manifest.json                                 │
│      v2.0.0/                                         │
│        ...                                           │
└─────────────────────────────────────────────────────┘
```

### 2.3 Artifact Fetching (Client-Side)

```python
class SkillArtifactFetcher:
    """Fetch artifacts on-demand from skill URIs"""
    
    def __init__(self, artifact_api_url: str):
        self.api_url = artifact_api_url
        self.cache = {}  # Local cache
    
    def fetch_artifact(self, uri: str) -> str:
        """
        Fetch artifact content from URI
        
        Args:
            uri: skill://sk_a3f7b2c1/artifacts/validate.py
        
        Returns:
            Artifact content as string
        """
        # Check cache
        if uri in self.cache:
            return self.cache[uri]
        
        # Parse URI
        parts = uri.replace("skill://", "").split("/")
        skill_id = parts[0]
        artifact_path = "/".join(parts[2:])  # Skip "artifacts"
        
        # Fetch from API
        response = requests.get(
            f"{self.api_url}/artifacts/{skill_id}/{artifact_path}"
        )
        
        content = response.text
        self.cache[uri] = content
        
        return content
    
    def fetch_all_artifacts(self, skill_id: str) -> dict:
        """Fetch all artifacts for a skill"""
        response = requests.get(
            f"{self.api_url}/artifacts/{skill_id}/all"
        )
        return response.json()
```

---

## Part 3: Using the Skill (Any Orchestrator)

### 3.1 Prompt Template for LLM Orchestrators

```markdown
# Skill Execution Request

You are an AI orchestrator executing a proven skill pattern.

## Skill Information
Name: {skill.name}
Description: {skill.description}
Success Rate: {skill.performance.success_rate}

## Task
{user_task_description}

## Workflow Pattern (Proven Approach)

{for step in skill.workflow.steps}
### Step {step.step_id}: {step.name}
**Goal:** {step.instructions.goal}
**Approach:** {step.instructions.approach}
**Deliverable:** {step.instructions.deliverable}

{if step.code_artifacts}
**Reference Code Available:**
- Artifact: {step.code_artifacts[0].artifact_id}
- Purpose: {step.code_artifacts[0].purpose}
- To fetch: GET {step.code_artifacts[0].uri}

**Modification Guidance:**
{step.code_artifacts[0].modification_guidance}

You should:
1. Fetch the reference code
2. Adapt it for the current task
3. Execute and verify results
{endif}

**Expected Outputs:** {step.outputs}
{endfor}

## Your Task
Execute this workflow pattern for the user's specific task. Fetch artifact code when needed and adapt it appropriately. Follow the proven structure but customize for the input data.

User Input: {user_input_file_path}
```

### 3.2 Example: LangGraph Execution

```python
from langgraph.graph import StateGraph
import requests

# 1. Load skill manifest
skill = load_skill_manifest("sk_a3f7b2c1")

# 2. Create artifact fetcher
fetcher = SkillArtifactFetcher("https://api.cmbagent.com")

# 3. Build LangGraph nodes from skill
def create_node_from_skill_step(step):
    """Convert skill step to LangGraph node"""
    
    def node_function(state):
        # If step has code artifacts, fetch and use them
        if step.code_artifacts:
            code = fetcher.fetch_artifact(step.code_artifacts[0].uri)
            
            # Pass to LLM for adaptation
            adapted_code = llm.invoke(f"""
                Here's reference code from a proven workflow:
                
                {code}
                
                Adapt this code for the current task:
                {state['task_description']}
                
                Input file: {state['input_file']}
                
                Modification guidance:
                {step.code_artifacts[0].modification_guidance}
                
                Generate the adapted code:
            """)
            
            # Execute adapted code
            result = execute_code(adapted_code)
        else:
            # Execute other step types (RAG query, synthesis, etc.)
            result = execute_step(step, state)
        
        return {**state, f"{step.step_id}_result": result}
    
    return node_function

# 4. Build graph
graph = StateGraph()

for step in skill['manifest']['workflow']['steps']:
    node_func = create_node_from_skill_step(step)
    graph.add_node(step['step_id'], node_func)

# Add edges based on dependencies
for step in skill['manifest']['workflow']['steps']:
    for dep in step['dependencies']:
        graph.add_edge(dep, step['step_id'])

# 5. Execute
result = graph.compile().invoke({
    "task_description": "Analyze my CMB data",
    "input_file": "my_data.fits"
})
```

### 3.3 Example: Google ADK Execution

```python
# Google AI Development Kit (ADK) example
from google.adk import Agent, Workflow

skill = load_skill_manifest("sk_a3f7b2c1")

# Create workflow from skill
workflow = Workflow.from_skill(skill)

# Agents fetch and adapt artifacts automatically
for step in skill['manifest']['workflow']['steps']:
    agent = Agent(role=step['role'])
    
    # Agent gets step context including artifact references
    agent.add_context({
        "step_description": step['description'],
        "instructions": step['instructions'],
        "artifacts": step.get('code_artifacts', []),
        "modification_guidance": step.get('code_artifacts', [{}])[0].get('modification_guidance')
    })
    
    workflow.add_agent(agent, step['step_id'])

# Execute with user input
result = workflow.run({
    "input_file_path": "my_data.fits",
    "analysis_config": {}
})
```

---

## Part 4: Benefits & Tradeoffs

### 4.1 Benefits

| Benefit | Description |
|---------|-------------|
| **Compact** | ~15KB manifest fits easily in LLM context |
| **Fast Loading** | Only fetch artifacts when needed |
| **Cost Efficient** | Don't pay for tokens to embed full code |
| **Modifiable** | Agents can adapt artifacts to specific tasks |
| **Portable** | Works with any orchestrator that can make HTTP calls |
| **Versioned** | Artifacts are immutable, versioned |
| **Cacheable** | Frequently used artifacts cached locally |
| **Reusable** | Same artifacts across multiple skills |

### 4.2 Tradeoffs

| Tradeoff | Impact | Mitigation |
|----------|--------|-----------|
| **Network dependency** | Requires artifact API access | Cache artifacts locally, bundle for offline |
| **Additional latency** | Artifact fetches add time | Parallel fetching, aggressive caching |
| **Complexity** | More moving parts | Good tooling, clear documentation |
| **Storage needed** | Artifacts stored separately | S3 is cheap, deduplication helps |

---

## Part 5: Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Design artifact URI scheme
- [ ] Implement artifact storage (S3/MinIO)
- [ ] Build artifact API (FastAPI)
  - [ ] GET /artifacts/{skill_id}/{path}
  - [ ] GET /artifacts/{skill_id}/manifest
  - [ ] POST /artifacts/{skill_id}
- [ ] Create artifact fetcher client library

### Phase 2: Skill Extraction
- [ ] Extract artifacts from successful runs
- [ ] Generate compact manifest with artifact references
- [ ] Version artifacts appropriately
- [ ] Validate manifest schema

### Phase 3: Skill Execution
- [ ] Build prompt template generator
- [ ] Implement skill → LangGraph adapter
- [ ] Implement skill → AG2 adapter
- [ ] Test with real workflows

### Phase 4: Optimization
- [ ] Add artifact caching
- [ ] Implement artifact deduplication
- [ ] Build artifact bundling for offline use
- [ ] Add artifact update/migration tools

---

## Summary

**The Compact Skill Design achieves:**

✅ **Small manifest** (~15KB) that's prompt-ready  
✅ **Artifact references** instead of embedded content  
✅ **On-demand fetching** for efficiency  
✅ **Agent-modifiable** artifacts for task adaptation  
✅ **Platform-agnostic** execution model  
✅ **Proven patterns** from successful runs  

**This makes skills portable, efficient, and practical for real-world cross-platform execution.**
