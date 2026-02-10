"""
Phase Orchestrator System

A composable system for orchestrating workflow phases dynamically.

Features:
- Execute phases from agent tool calls
- DAG (Directed Acyclic Graph) tracking for phase dependencies
- Comprehensive logging and monitoring
- Context passing between phases
- Error recovery and retry logic
- Performance metrics and tracking
- Unified swarm orchestration with all agents

Usage:
    # Single phase execution
    from cmbagent.orchestrator import PhaseOrchestrator, OrchestratorConfig

    config = OrchestratorConfig(
        enable_dag_tracking=True,
        enable_logging=True,
        log_dir="/path/to/logs"
    )

    orchestrator = PhaseOrchestrator(config)

    result = await orchestrator.execute_phase("research", {
        "query": "topic",
        "depth": "deep"
    })

    # Unified swarm orchestration
    from cmbagent.orchestrator import SwarmOrchestrator, SwarmConfig

    swarm_config = SwarmConfig(
        max_rounds=100,
        enable_phase_tools=True,
        load_all_agents=True,
    )

    swarm = SwarmOrchestrator(swarm_config)
    await swarm.initialize(api_keys, work_dir)

    result = await swarm.run("Build a REST API with authentication")

    # Continue if paused at max rounds
    if result['status'] == 'paused':
        result = await swarm.continue_execution()
"""

from cmbagent.orchestrator.config import (
    OrchestratorConfig,
    DEFAULT_CONFIG,
    DEVELOPMENT_CONFIG,
    PRODUCTION_CONFIG,
    FAST_CONFIG,
    PARALLEL_CONFIG,
)
from cmbagent.orchestrator.phase_orchestrator import (
    PhaseOrchestrator,
    PhaseExecutionRequest,
    PhaseExecutionResult,
    set_global_orchestrator,
    get_global_orchestrator,
    EXECUTABLE_PHASE_TOOLS,
    # Executable phase functions
    execute_planning_phase,
    execute_control_phase,
    execute_one_shot_phase,
    execute_hitl_planning_phase,
    execute_hitl_control_phase,
    execute_idea_generation_phase,
    chain_phases_executable,
    # Sync wrappers
    execute_planning_phase_sync,
    execute_control_phase_sync,
    execute_one_shot_phase_sync,
    execute_hitl_planning_phase_sync,
    execute_hitl_control_phase_sync,
    execute_idea_generation_phase_sync,
    chain_phases_sync,
)
from cmbagent.orchestrator.swarm_orchestrator import (
    SwarmOrchestrator,
    SwarmConfig,
    SwarmState,
    SwarmStatus,
    run_swarm,
    run_swarm_sync,
)
from cmbagent.orchestrator.dag_tracker import DAGTracker, PhaseNode
from cmbagent.orchestrator.context_pipeline import ContextPipeline
from cmbagent.orchestrator.logger import OrchestratorLogger
from cmbagent.orchestrator.metrics import MetricsCollector

__all__ = [
    # Config
    'OrchestratorConfig',
    'DEFAULT_CONFIG',
    'DEVELOPMENT_CONFIG',
    'PRODUCTION_CONFIG',
    'FAST_CONFIG',
    'PARALLEL_CONFIG',

    # Phase Orchestrator
    'PhaseOrchestrator',
    'PhaseExecutionRequest',
    'PhaseExecutionResult',
    'set_global_orchestrator',
    'get_global_orchestrator',
    'EXECUTABLE_PHASE_TOOLS',

    # Executable phase functions
    'execute_planning_phase',
    'execute_control_phase',
    'execute_one_shot_phase',
    'execute_hitl_planning_phase',
    'execute_hitl_control_phase',
    'execute_idea_generation_phase',
    'chain_phases_executable',

    # Sync wrappers
    'execute_planning_phase_sync',
    'execute_control_phase_sync',
    'execute_one_shot_phase_sync',
    'execute_hitl_planning_phase_sync',
    'execute_hitl_control_phase_sync',
    'execute_idea_generation_phase_sync',
    'chain_phases_sync',

    # Swarm Orchestrator
    'SwarmOrchestrator',
    'SwarmConfig',
    'SwarmState',
    'SwarmStatus',
    'run_swarm',
    'run_swarm_sync',

    # Supporting components
    'DAGTracker',
    'PhaseNode',
    'ContextPipeline',
    'OrchestratorLogger',
    'MetricsCollector',
]

__version__ = '0.2.0'
