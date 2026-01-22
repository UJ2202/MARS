# Skill Structure Specification

## Overview
This document defines the complete structure for storing and applying reusable execution patterns (Skills) in the CMBAgent system.

---

## 1. Core Skill Components

### 1.1 Skill Identity & Metadata
```json
{
  "id": "uuid-v4",
  "name": "cmb_power_spectrum_analysis",
  "display_name": "CMB Power Spectrum Analysis",
  "version": "2.1.0",
  "description": "Analyzes CMB power spectrum from Planck/CLASS output files using optimized Bayesian methods",
  "category": "data_analysis",
  "tags": ["cmb", "power_spectrum", "bayesian", "planck", "class"],
  "created_at": "2026-01-15T10:30:00Z",
  "updated_at": "2026-01-20T14:22:00Z",
  "author": "system",
  "status": "production"
}
```

### 1.2 Provenance & Extraction Info
```json
{
  "provenance": {
    "extracted_from_run_id": "550e8400-e29b-41d4-a716-446655440000",
    "extraction_date": "2026-01-15T10:30:00Z",
    "extraction_method": "automated_pattern_analysis",
    "branch_comparison": {
      "branches_analyzed": 3,
      "best_branch_id": "550e8400-e29b-41d4-a716-446655440001",
      "success_criteria": "execution_time < 300s AND accuracy > 0.95"
    },
    "source_events_count": 247,
    "refinement_iterations": 5
  }
}
```

### 1.3 Pattern Signature (Task Matching)
```json
{
  "pattern_signature": {
    "task_type": "data_analysis",
    "task_keywords": [
      "power spectrum",
      "cmb",
      "analyze",
      "planck",
      "class output",
      "cosmological parameters"
    ],
    "input_characteristics": {
      "file_types": ["fits", "dat", "txt", "csv"],
      "file_size_range": {
        "min_mb": 0.1,
        "max_mb": 500
      },
      "required_columns": ["ell", "tt", "ee", "te"],
      "data_structure": "tabular_2d"
    },
    "output_requirements": {
      "types": ["plot", "statistical_summary", "json_results"],
      "visualization": true,
      "statistical_analysis": true
    },
    "complexity_indicators": {
      "estimated_steps": "5-8",
      "computation_intensive": true,
      "requires_domain_knowledge": true
    },
    "embedding_vector": [0.234, -0.456, 0.789, "... 1536 dims"]
  }
}
```

### 1.4 Preconditions (When to Apply)
```json
{
  "preconditions": {
    "required": [
      {
        "type": "file_exists",
        "description": "Input data file must exist",
        "validation": "check_file_path"
      },
      {
        "type": "file_format",
        "description": "Must be FITS, DAT, or CSV with numeric columns",
        "validation": "validate_data_format"
      },
      {
        "type": "task_intent",
        "description": "Task must involve spectrum analysis",
        "validation": "llm_intent_classification",
        "confidence_threshold": 0.75
      }
    ],
    "optional": [
      {
        "type": "python_packages",
        "description": "Preferred packages for optimal performance",
        "packages": ["numpy", "scipy", "matplotlib", "astropy"],
        "fallback": "use_alternative_methods"
      }
    ],
    "constraints": {
      "max_file_size_mb": 500,
      "min_data_points": 100,
      "python_version": ">=3.8"
    }
  }
}
```

### 1.5 Execution Template (The Core Pattern)
```json
{
  "execution_template": {
    "dag_structure": {
      "nodes": [
        {
          "node_id": "step_1_understand",
          "name": "Literature & Context Understanding",
          "agent": "researcher_agent",
          "dependencies": [],
          "parallel_group": null
        },
        {
          "node_id": "step_2_validate",
          "name": "Data Validation",
          "agent": "engineer_agent",
          "dependencies": ["step_1_understand"],
          "parallel_group": null
        },
        {
          "node_id": "step_3_prepare",
          "name": "Data Preprocessing",
          "agent": "engineer_agent",
          "dependencies": ["step_2_validate"],
          "parallel_group": null
        },
        {
          "node_id": "step_4_analyze",
          "name": "Bayesian Analysis",
          "agent": "executor_agent",
          "dependencies": ["step_3_prepare"],
          "parallel_group": 1
        },
        {
          "node_id": "step_4_visualize",
          "name": "Generate Plots",
          "agent": "engineer_agent",
          "dependencies": ["step_3_prepare"],
          "parallel_group": 1
        },
        {
          "node_id": "step_5_summarize",
          "name": "Generate Report",
          "agent": "formatter_agent",
          "dependencies": ["step_4_analyze", "step_4_visualize"],
          "parallel_group": null
        }
      ]
    },
    "agent_sequence": [
      {
        "step_id": "step_1_understand",
        "agent_name": "researcher_agent",
        "agent_type": "RAGAgent",
        "goal": "Understand the physics of CMB power spectrum and relevant analysis methods",
        "system_prompt_template": "You are analyzing CMB power spectrum data. Query literature for: {{task_context}}",
        "tools_allowed": ["rag_query", "web_search", "paper_retrieval"],
        "max_iterations": 3,
        "expected_outputs": ["context_summary", "methodology_notes"],
        "estimated_duration_seconds": 45,
        "event_patterns": {
          "expected_event_types": ["agent_call", "tool_call:rag_query"],
          "typical_event_count": 12
        },
        "parameters": {
          "rag_indices": ["planck_papers", "class_docs", "bayesian_methods"],
          "max_papers": 5,
          "focus_areas": ["power spectrum estimation", "error analysis"]
        }
      },
      {
        "step_id": "step_2_validate",
        "agent_name": "engineer_agent",
        "agent_type": "CodeAgent",
        "goal": "Validate input data structure and quality",
        "system_prompt_template": "Write Python code to validate the data file at {{input_file_path}}. Check for: proper format, required columns, data quality.",
        "tools_allowed": ["code_executor", "file_reader"],
        "max_iterations": 2,
        "expected_outputs": ["validation_report", "data_schema"],
        "estimated_duration_seconds": 30,
        "code_template": {
          "language": "python",
          "framework": "numpy/pandas",
          "snippet": "import numpy as np\nimport pandas as pd\nfrom astropy.io import fits\n\ndef validate_power_spectrum_data(filepath):\n    # Load data\n    if filepath.endswith('.fits'):\n        data = fits.open(filepath)[1].data\n    else:\n        data = pd.read_csv(filepath)\n    \n    # Validate columns\n    required_cols = ['ell', 'tt']\n    assert all(col in data.columns for col in required_cols)\n    \n    # Check data quality\n    assert len(data) > 100\n    assert not data.isnull().any().any()\n    \n    return {'status': 'valid', 'rows': len(data), 'columns': list(data.columns)}"
        },
        "parameters": {
          "validation_rules": ["check_nans", "check_negative_ell", "check_monotonic"],
          "quality_thresholds": {
            "min_points": 100,
            "max_missing_fraction": 0.05
          }
        }
      },
      {
        "step_id": "step_3_prepare",
        "agent_name": "engineer_agent",
        "agent_type": "CodeAgent",
        "goal": "Preprocess data for analysis (binning, error propagation, normalization)",
        "system_prompt_template": "Based on validation results {{validation_report}}, write code to preprocess the data.",
        "context_dependencies": ["step_2_validate.outputs.validation_report"],
        "tools_allowed": ["code_executor"],
        "max_iterations": 3,
        "expected_outputs": ["preprocessed_data_path", "preprocessing_log"],
        "estimated_duration_seconds": 60,
        "code_template": {
          "language": "python",
          "operations": ["binning", "error_calculation", "normalization"],
          "snippet": "def preprocess_power_spectrum(data, bin_width=10):\n    # Bin data\n    bins = np.arange(data['ell'].min(), data['ell'].max(), bin_width)\n    binned_data = data.groupby(pd.cut(data['ell'], bins)).mean()\n    \n    # Calculate errors\n    binned_data['error'] = data.groupby(pd.cut(data['ell'], bins)).std() / np.sqrt(data.groupby(pd.cut(data['ell'], bins)).size())\n    \n    return binned_data"
        },
        "parameters": {
          "bin_width": 10,
          "normalization_method": "cosmic_variance",
          "error_propagation": "quadrature"
        }
      },
      {
        "step_id": "step_4_analyze",
        "agent_name": "executor_agent",
        "agent_type": "ExecutionAgent",
        "goal": "Run Bayesian analysis on preprocessed data",
        "system_prompt_template": "Execute Bayesian parameter estimation on {{preprocessed_data_path}}",
        "context_dependencies": ["step_3_prepare.outputs.preprocessed_data_path"],
        "tools_allowed": ["code_executor", "resource_monitor"],
        "max_iterations": 1,
        "expected_outputs": ["parameter_estimates", "posterior_samples", "convergence_metrics"],
        "estimated_duration_seconds": 180,
        "code_template": {
          "language": "python",
          "framework": "scipy/emcee",
          "snippet": "import emcee\nfrom scipy.optimize import minimize\n\ndef run_bayesian_analysis(data):\n    # Define likelihood\n    def log_likelihood(params, data):\n        model = power_spectrum_model(params, data['ell'])\n        return -0.5 * np.sum(((data['tt'] - model) / data['error'])**2)\n    \n    # Run MCMC\n    sampler = emcee.EnsembleSampler(nwalkers=32, ndim=6, log_prob_fn=log_likelihood)\n    sampler.run_mcmc(initial_pos, nsteps=5000)\n    \n    return sampler.get_chain(flat=True)"
        },
        "parameters": {
          "method": "mcmc",
          "sampler": "emcee",
          "n_walkers": 32,
          "n_steps": 5000,
          "burn_in": 1000,
          "convergence_check": true
        }
      },
      {
        "step_id": "step_4_visualize",
        "agent_name": "engineer_agent",
        "agent_type": "CodeAgent",
        "goal": "Create publication-quality plots",
        "system_prompt_template": "Generate plots showing power spectrum, residuals, and parameter constraints",
        "context_dependencies": ["step_3_prepare.outputs.preprocessed_data_path"],
        "tools_allowed": ["code_executor", "file_writer"],
        "max_iterations": 2,
        "expected_outputs": ["plot_files", "figure_captions"],
        "estimated_duration_seconds": 45,
        "code_template": {
          "language": "python",
          "framework": "matplotlib",
          "plot_types": ["power_spectrum_plot", "residual_plot", "corner_plot"]
        },
        "parameters": {
          "style": "publication",
          "dpi": 300,
          "formats": ["png", "pdf"],
          "color_scheme": "viridis"
        }
      },
      {
        "step_id": "step_5_summarize",
        "agent_name": "formatter_agent",
        "agent_type": "FormatterAgent",
        "goal": "Compile results into structured report",
        "system_prompt_template": "Generate summary report with analysis results {{parameter_estimates}} and plots {{plot_files}}",
        "context_dependencies": [
          "step_4_analyze.outputs.parameter_estimates",
          "step_4_visualize.outputs.plot_files"
        ],
        "tools_allowed": ["markdown_formatter", "json_writer"],
        "max_iterations": 1,
        "expected_outputs": ["final_report", "results_json"],
        "estimated_duration_seconds": 30,
        "parameters": {
          "report_format": "markdown",
          "include_plots": true,
          "include_raw_data": false
        }
      }
    ],
    "handoff_protocol": {
      "type": "sequential_with_parallel",
      "context_carryover": [
        "input_file_path",
        "task_description",
        "intermediate_outputs"
      ],
      "error_handling": "retry_with_context"
    }
  }
}
```

### 1.6 Parameters & Configuration
```json
{
  "parameters": {
    "required": [
      {
        "name": "input_file_path",
        "type": "string",
        "description": "Path to input power spectrum data file",
        "validation": "file_exists"
      },
      {
        "name": "output_directory",
        "type": "string",
        "description": "Directory for output files",
        "default": "./output",
        "validation": "writable_directory"
      }
    ],
    "optional": [
      {
        "name": "bin_width",
        "type": "integer",
        "description": "Bin width for data preprocessing",
        "default": 10,
        "range": [5, 50]
      },
      {
        "name": "n_mcmc_steps",
        "type": "integer",
        "description": "Number of MCMC steps",
        "default": 5000,
        "range": [1000, 50000]
      },
      {
        "name": "confidence_level",
        "type": "float",
        "description": "Confidence level for parameter estimates",
        "default": 0.95,
        "range": [0.8, 0.99]
      },
      {
        "name": "plot_style",
        "type": "string",
        "description": "Matplotlib style for plots",
        "default": "publication",
        "options": ["publication", "presentation", "notebook"]
      }
    ],
    "advanced": [
      {
        "name": "custom_priors",
        "type": "object",
        "description": "Custom prior distributions for Bayesian analysis",
        "default": null
      }
    ]
  }
}
```

### 1.7 Success Metrics & Performance
```json
{
  "performance_metrics": {
    "success_rate": 0.947,
    "usage_count": 127,
    "avg_execution_time_seconds": 285,
    "std_execution_time_seconds": 42,
    "avg_cost_usd": 0.18,
    "median_tokens_used": 45000,
    "resource_requirements": {
      "avg_memory_mb": 512,
      "avg_cpu_cores": 2,
      "disk_space_mb": 100
    },
    "last_successful_run": "2026-01-20T18:45:00Z",
    "last_failed_run": "2026-01-18T09:22:00Z",
    "success_by_context": {
      "planck_fits_files": 0.98,
      "class_output_files": 0.95,
      "custom_simulations": 0.87
    }
  },
  "quality_metrics": {
    "output_completeness": 0.96,
    "user_satisfaction_score": 4.7,
    "manual_intervention_rate": 0.08,
    "false_positive_rate": 0.05
  }
}
```

### 1.8 Postconditions (Expected Outcomes)
```json
{
  "postconditions": {
    "required_outputs": [
      {
        "name": "parameter_estimates",
        "type": "json",
        "description": "Estimated cosmological parameters with uncertainties",
        "validation": "has_required_fields"
      },
      {
        "name": "power_spectrum_plot",
        "type": "file",
        "format": "png",
        "description": "Plot of data and best-fit model",
        "validation": "file_exists_and_valid"
      },
      {
        "name": "final_report",
        "type": "markdown",
        "description": "Comprehensive analysis report",
        "validation": "markdown_valid"
      }
    ],
    "quality_checks": [
      {
        "check": "convergence_achieved",
        "description": "MCMC chains converged (Gelman-Rubin < 1.1)",
        "critical": true
      },
      {
        "check": "positive_error_bars",
        "description": "All error estimates are positive",
        "critical": true
      },
      {
        "check": "plot_files_generated",
        "description": "At least 2 plot files created",
        "critical": false
      }
    ],
    "side_effects": {
      "files_created": ["data_preprocessed.csv", "results.json", "*.png", "report.md"],
      "directories_created": ["output/plots", "output/data"],
      "cleanup_required": false
    }
  }
}
```

### 1.9 Error Handling & Fallbacks
```json
{
  "error_handling": {
    "common_errors": [
      {
        "error_type": "file_not_found",
        "category": "input_validation",
        "recovery_strategy": "prompt_user_for_correct_path",
        "retry_allowed": false
      },
      {
        "error_type": "convergence_failure",
        "category": "execution",
        "recovery_strategy": "increase_mcmc_steps",
        "retry_allowed": true,
        "max_retries": 2,
        "retry_modifications": {
          "n_mcmc_steps": "multiply_by_2",
          "n_walkers": "increase_by_10"
        }
      },
      {
        "error_type": "insufficient_memory",
        "category": "resource",
        "recovery_strategy": "reduce_batch_size",
        "retry_allowed": true,
        "max_retries": 1
      }
    ],
    "fallback_skill": "simple_power_spectrum_plot",
    "escalation_policy": {
      "after_retries_exhausted": "notify_user_and_switch_to_planning",
      "critical_errors": "immediate_user_notification"
    }
  }
}
```

### 1.10 Versioning & Evolution
```json
{
  "versioning": {
    "version": "2.1.0",
    "changelog": [
      {
        "version": "2.1.0",
        "date": "2026-01-20",
        "changes": [
          "Improved convergence checking",
          "Added parallel plotting step",
          "Optimized memory usage"
        ],
        "breaking_changes": false
      },
      {
        "version": "2.0.0",
        "date": "2026-01-10",
        "changes": [
          "Switched to emcee sampler",
          "Complete rewrite of preprocessing",
          "New parameter schema"
        ],
        "breaking_changes": true
      },
      {
        "version": "1.0.0",
        "date": "2025-12-15",
        "changes": ["Initial skill extraction"],
        "breaking_changes": false
      }
    ],
    "deprecation_notice": null,
    "migration_guide": null
  },
  "evolution_tracking": {
    "a_b_tests": [
      {
        "test_id": "test_001",
        "versions_compared": ["2.0.0", "2.1.0"],
        "metric": "success_rate",
        "result": "v2.1.0 winner (95% vs 92%)",
        "date": "2026-01-18"
      }
    ],
    "improvement_suggestions": [
      {
        "suggestion": "Add support for polarization spectra",
        "priority": "medium",
        "votes": 8
      }
    ]
  }
}
```

---

## 2. Database Mapping

### 2.1 Skill Table Schema
```sql
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    version VARCHAR(50) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    tags TEXT[],
    
    -- Provenance
    extracted_from_run_id UUID REFERENCES workflow_runs(id),
    extraction_date TIMESTAMP,
    source_branch_id UUID,
    
    -- Pattern & Matching
    pattern_signature JSONB NOT NULL,
    embedding_vector vector(1536),  -- pgvector extension
    
    -- Execution
    preconditions JSONB NOT NULL,
    execution_template JSONB NOT NULL,
    parameters JSONB NOT NULL,
    postconditions JSONB NOT NULL,
    error_handling JSONB,
    
    -- Metrics
    success_rate FLOAT DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0,
    avg_execution_time_seconds FLOAT,
    avg_cost_usd FLOAT,
    performance_metrics JSONB,
    quality_metrics JSONB,
    
    -- Versioning
    version_info JSONB,
    status VARCHAR(50) DEFAULT 'draft',  -- draft, testing, production, deprecated
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255),
    
    -- Indices
    CONSTRAINT unique_skill_version UNIQUE(name, version)
);

CREATE INDEX idx_skills_embedding ON skills USING ivfflat (embedding_vector vector_cosine_ops);
CREATE INDEX idx_skills_category ON skills(category);
CREATE INDEX idx_skills_tags ON skills USING gin(tags);
CREATE INDEX idx_skills_success_rate ON skills(success_rate DESC);
CREATE INDEX idx_skills_pattern ON skills USING gin(pattern_signature);
```

### 2.2 Skill Usage Tracking
```sql
CREATE TABLE skill_usages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES skills(id),
    skill_version VARCHAR(50),
    run_id UUID REFERENCES workflow_runs(id),
    
    -- Matching info
    match_confidence FLOAT,
    preconditions_met JSONB,
    parameters_used JSONB,
    
    -- Execution results
    status VARCHAR(50),  -- success, failed, partial
    execution_time_seconds FLOAT,
    cost_usd FLOAT,
    resource_usage JSONB,
    
    -- Quality
    postconditions_met JSONB,
    quality_score FLOAT,
    user_feedback_score INTEGER,
    
    -- Deviations
    deviations_detected JSONB,
    fallback_used BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_skill_usages_skill ON skill_usages(skill_id);
CREATE INDEX idx_skill_usages_run ON skill_usages(run_id);
CREATE INDEX idx_skill_usages_status ON skill_usages(status);
```

### 2.3 Linking to Existing Tables
```sql
-- Add skill_id to workflow_runs
ALTER TABLE workflow_runs ADD COLUMN skill_id UUID REFERENCES skills(id);
ALTER TABLE workflow_runs ADD COLUMN skill_version VARCHAR(50);
ALTER TABLE workflow_runs ADD COLUMN skill_match_confidence FLOAT;
ALTER TABLE workflow_runs ADD COLUMN used_planning BOOLEAN DEFAULT TRUE;

CREATE INDEX idx_workflow_runs_skill ON workflow_runs(skill_id);
```

---

## 3. Complete Example: Sample Skill JSON

```json
{
  "skill": {
    "id": "a3f7b2c1-4e8d-4a9b-b1c2-d3e4f5a6b7c8",
    "name": "cmb_power_spectrum_analysis",
    "display_name": "CMB Power Spectrum Analysis",
    "version": "2.1.0",
    "description": "Analyzes CMB power spectrum from Planck/CLASS output files using optimized Bayesian methods. Handles data validation, preprocessing, MCMC parameter estimation, and generates publication-quality plots.",
    "category": "data_analysis",
    "tags": ["cmb", "power_spectrum", "bayesian", "planck", "class", "mcmc", "cosmology"],
    "status": "production",
    
    "provenance": {
      "extracted_from_run_id": "550e8400-e29b-41d4-a716-446655440000",
      "extraction_date": "2026-01-15T10:30:00Z",
      "extraction_method": "automated_pattern_analysis",
      "source_branch_id": "550e8400-e29b-41d4-a716-446655440001",
      "branches_analyzed": 3,
      "source_events_count": 247
    },
    
    "pattern_signature": {
      "task_type": "data_analysis",
      "task_keywords": ["power spectrum", "cmb", "analyze", "planck", "class", "cosmological parameters"],
      "input_characteristics": {
        "file_types": ["fits", "dat", "txt", "csv"],
        "file_size_range": {"min_mb": 0.1, "max_mb": 500},
        "required_columns": ["ell", "tt"],
        "data_structure": "tabular_2d"
      },
      "output_requirements": {
        "types": ["plot", "statistical_summary", "json_results"],
        "visualization": true,
        "statistical_analysis": true
      },
      "embedding_vector": "<1536-dimensional vector>"
    },
    
    "preconditions": {
      "required": [
        {
          "type": "file_exists",
          "description": "Input data file must exist",
          "validation": "check_file_path"
        },
        {
          "type": "file_format",
          "description": "Must be FITS, DAT, or CSV with numeric columns",
          "validation": "validate_data_format"
        },
        {
          "type": "task_intent",
          "description": "Task must involve spectrum analysis",
          "validation": "llm_intent_classification",
          "confidence_threshold": 0.75
        }
      ],
      "constraints": {
        "max_file_size_mb": 500,
        "min_data_points": 100
      }
    },
    
    "execution_template": {
      "dag_structure": {
        "nodes": [
          {"node_id": "step_1", "name": "Literature Review", "agent": "researcher_agent", "dependencies": []},
          {"node_id": "step_2", "name": "Data Validation", "agent": "engineer_agent", "dependencies": ["step_1"]},
          {"node_id": "step_3", "name": "Preprocessing", "agent": "engineer_agent", "dependencies": ["step_2"]},
          {"node_id": "step_4a", "name": "Bayesian Analysis", "agent": "executor_agent", "dependencies": ["step_3"], "parallel_group": 1},
          {"node_id": "step_4b", "name": "Generate Plots", "agent": "engineer_agent", "dependencies": ["step_3"], "parallel_group": 1},
          {"node_id": "step_5", "name": "Generate Report", "agent": "formatter_agent", "dependencies": ["step_4a", "step_4b"]}
        ]
      },
      "agent_sequence": [
        {
          "step_id": "step_1",
          "agent_name": "researcher_agent",
          "goal": "Understand CMB power spectrum physics and analysis methods",
          "tools_allowed": ["rag_query", "web_search"],
          "parameters": {"rag_indices": ["planck_papers", "class_docs"], "max_papers": 5},
          "estimated_duration_seconds": 45
        },
        {
          "step_id": "step_2",
          "agent_name": "engineer_agent",
          "goal": "Validate input data structure and quality",
          "tools_allowed": ["code_executor", "file_reader"],
          "code_template": "validate_power_spectrum_data_v2",
          "parameters": {"validation_rules": ["check_nans", "check_negative_ell"]},
          "estimated_duration_seconds": 30
        },
        {
          "step_id": "step_3",
          "agent_name": "engineer_agent",
          "goal": "Preprocess data (binning, error propagation)",
          "context_dependencies": ["step_2.outputs.validation_report"],
          "parameters": {"bin_width": 10, "normalization_method": "cosmic_variance"},
          "estimated_duration_seconds": 60
        },
        {
          "step_id": "step_4a",
          "agent_name": "executor_agent",
          "goal": "Run Bayesian parameter estimation",
          "context_dependencies": ["step_3.outputs.preprocessed_data_path"],
          "parameters": {"method": "mcmc", "n_walkers": 32, "n_steps": 5000},
          "estimated_duration_seconds": 180
        },
        {
          "step_id": "step_4b",
          "agent_name": "engineer_agent",
          "goal": "Create publication-quality plots",
          "context_dependencies": ["step_3.outputs.preprocessed_data_path"],
          "parameters": {"style": "publication", "dpi": 300},
          "estimated_duration_seconds": 45
        },
        {
          "step_id": "step_5",
          "agent_name": "formatter_agent",
          "goal": "Compile results into structured report",
          "context_dependencies": ["step_4a.outputs", "step_4b.outputs"],
          "estimated_duration_seconds": 30
        }
      ]
    },
    
    "parameters": {
      "required": [
        {"name": "input_file_path", "type": "string", "description": "Path to input data file"}
      ],
      "optional": [
        {"name": "bin_width", "type": "integer", "default": 10, "range": [5, 50]},
        {"name": "n_mcmc_steps", "type": "integer", "default": 5000, "range": [1000, 50000]},
        {"name": "confidence_level", "type": "float", "default": 0.95, "range": [0.8, 0.99]}
      ]
    },
    
    "postconditions": {
      "required_outputs": [
        {"name": "parameter_estimates", "type": "json", "validation": "has_required_fields"},
        {"name": "power_spectrum_plot", "type": "file", "format": "png"},
        {"name": "final_report", "type": "markdown"}
      ],
      "quality_checks": [
        {"check": "convergence_achieved", "critical": true},
        {"check": "positive_error_bars", "critical": true}
      ]
    },
    
    "performance_metrics": {
      "success_rate": 0.947,
      "usage_count": 127,
      "avg_execution_time_seconds": 285,
      "avg_cost_usd": 0.18,
      "last_successful_run": "2026-01-20T18:45:00Z"
    },
    
    "error_handling": {
      "common_errors": [
        {
          "error_type": "convergence_failure",
          "recovery_strategy": "increase_mcmc_steps",
          "retry_allowed": true,
          "max_retries": 2
        }
      ],
      "fallback_skill": "simple_power_spectrum_plot"
    },
    
    "versioning": {
      "version": "2.1.0",
      "changelog": [
        {
          "version": "2.1.0",
          "date": "2026-01-20",
          "changes": ["Improved convergence checking", "Added parallel plotting"],
          "breaking_changes": false
        }
      ]
    },
    
    "created_at": "2026-01-15T10:30:00Z",
    "updated_at": "2026-01-20T14:22:00Z",
    "created_by": "system"
  }
}
```

---

## 4. Usage Flow

### 4.1 Skill Extraction Process
```python
# After successful workflow with branches
from cmbagent.skills import SkillExtractor

extractor = SkillExtractor()
skill = extractor.extract_from_run(
    run_id="550e8400-e29b-41d4-a716-446655440000",
    branch_comparison={
        "branches": ["branch_a", "branch_b", "branch_c"],
        "best_branch": "branch_a",
        "success_criteria": "execution_time < 300s AND accuracy > 0.95"
    }
)

# Analyze execution events
events = db.query(ExecutionEvent).filter_by(run_id=run_id).all()
agent_sequence = extractor.extract_agent_sequence(events)
parameters = extractor.extract_parameters(events)
preconditions = extractor.infer_preconditions(events, task_description)

# Create skill
skill_json = extractor.create_skill_template(
    name="cmb_power_spectrum_analysis",
    agent_sequence=agent_sequence,
    parameters=parameters,
    preconditions=preconditions
)

# Generate embedding
embedding = embed_skill(skill_json)
skill_json["pattern_signature"]["embedding_vector"] = embedding

# Save to database
db.add(Skill(**skill_json))
db.commit()
```

### 4.2 Skill Matching Process
```python
# New task arrives
from cmbagent.skills import SkillMatcher

matcher = SkillMatcher()
task = "Analyze the CMB power spectrum from this Planck FITS file"

# Find matching skills
candidates = matcher.find_matching_skills(
    task_description=task,
    file_info={"path": "planck_spectrum.fits", "size_mb": 45},
    top_k=5
)

# Validate preconditions
for candidate in candidates:
    if matcher.validate_preconditions(candidate, task_context):
        print(f"Match found: {candidate.name} (confidence: {candidate.match_score})")
        break
```

### 4.3 Skill Execution Process
```python
# Apply skill to task
from cmbagent.skills import SkillExecutor

executor = SkillExecutor()
result = executor.execute_skill(
    skill_id="a3f7b2c1-4e8d-4a9b-b1c2-d3e4f5a6b7c8",
    parameters={
        "input_file_path": "planck_spectrum.fits",
        "bin_width": 15,  # Override default
        "output_directory": "./my_analysis"
    },
    monitor_deviations=True
)

# Track usage
db.add(SkillUsage(
    skill_id=skill.id,
    run_id=result.run_id,
    status="success",
    execution_time_seconds=result.duration,
    match_confidence=0.89
))

# Update skill metrics
skill.usage_count += 1
skill.success_rate = calculate_success_rate(skill.id)
db.commit()
```

---

## 5. Key Benefits

1. **Speed**: Skip planning phase (80% faster)
2. **Cost**: Fewer LLM calls (60% cheaper)
3. **Reliability**: Proven patterns (higher success rate)
4. **Reusability**: One skill serves many similar tasks
5. **Evolution**: Skills improve over time with usage data
6. **Transparency**: Full provenance and versioning
7. **Fallback**: Graceful degradation to planning if skill fails

---

## 6. Implementation Priority

### Phase 1: Foundation (Weeks 1-2)
- [ ] Add `Skill` and `SkillUsage` tables to database
- [ ] Implement basic Skill model in Python
- [ ] Create embedding generation pipeline

### Phase 2: Extraction (Weeks 3-5)
- [ ] Build `SkillExtractor` class
- [ ] Implement pattern analysis from execution events
- [ ] Create skill template generation logic

### Phase 3: Matching (Weeks 6-7)
- [ ] Build `SkillMatcher` class
- [ ] Implement similarity search with embeddings
- [ ] Create precondition validation logic

### Phase 4: Execution (Weeks 8-9)
- [ ] Build `SkillExecutor` class
- [ ] Implement template instantiation
- [ ] Add deviation monitoring

### Phase 5: UI & Analytics (Weeks 10-12)
- [ ] Skill library browser in UI
- [ ] Usage analytics dashboard
- [ ] A/B testing framework
