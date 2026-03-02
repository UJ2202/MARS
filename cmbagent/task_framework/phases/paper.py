"""Denario Paper Generation Phase.

Source: Denario/denario/denario.py:get_paper()
Key details:
  - Uses LangGraph build_graph() from paper_agents/agents_graph.py
  - MUST use await graph.ainvoke() (citations_node is async)
  - GraphState expects: files.Folder, llm.{model,temperature,max_output_tokens},
    paper.{journal,add_citations,cmbagent_keywords}, keys, writer
  - preprocess_node reads from project_dir/input_files/{idea,methods,results}.md and plots/
  - Creates paper/ dir with 4 versions: v1_preliminary, v2_no_citations, v3_citations, v4_final
  - config MUST include configurable.thread_id for LangGraph checkpointer
  - Default: llm=gemini-2.5-flash, writer='scientist', journal=Journal.NONE, add_citations=True
"""

import os
import traceback
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.registry import PhaseRegistry
from cmbagent.phases.execution_manager import PhaseExecutionManager
from cmbagent.task_framework.config import PAPER_FOLDER

logger = logging.getLogger(__name__)


@dataclass
class DenarioPaperPhaseConfig(PhaseConfig):
    """Configuration for Denario paper generation phase."""
    phase_type: str = "denario_paper"

    # Paper config (from denario.py:793-797)
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.7
    llm_max_output_tokens: int = 65536
    writer: str = "scientist"
    journal: Optional[str] = None      # Journal.NONE
    add_citations: bool = True
    cmbagent_keywords: bool = False

    # Parent tracking
    parent_run_id: str = ""
    stage_name: str = "paper_generation"

    # API keys (KeyManager or dict)
    api_keys: Any = None


@PhaseRegistry.register("denario_paper")
class DenarioPaperPhase(Phase):
    """Generate research paper using LangGraph pipeline.

    Mirrors Denario/denario/denario.py:get_paper() exactly.
    """

    config_class = DenarioPaperPhaseConfig

    def __init__(self, config: DenarioPaperPhaseConfig = None):
        if config is None:
            config = DenarioPaperPhaseConfig()
        super().__init__(config)
        self.config: DenarioPaperPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "denario_paper"

    @property
    def display_name(self) -> str:
        return "Denario Paper Generation"

    def get_required_agents(self) -> List[str]:
        return []  # LangGraph manages its own nodes

    async def execute(self, context: PhaseContext) -> PhaseResult:
        from cmbagent.task_framework.paper_agents.agents_graph import build_graph
        from cmbagent.task_framework.paper_agents.journal import Journal
        from cmbagent.task_framework.key_manager import KeyManager

        manager = PhaseExecutionManager(context, self)
        manager.start()

        try:
            # project_dir is context.work_dir (contains input_files/ from earlier stages)
            project_dir = str(context.work_dir)

            # Resolve journal enum
            journal = self.config.journal
            if journal is None:
                journal = Journal.NONE
            elif isinstance(journal, str):
                journal = Journal(journal)

            # Resolve keys -- prefer config api_keys, fall back to context
            keys = self.config.api_keys
            if keys is None:
                # Try to construct KeyManager from context api_keys dict
                keys = KeyManager()
                keys.get_keys_from_env()
            elif isinstance(keys, dict):
                keys = KeyManager(**keys)

            # LangGraph config (denario.py:827)
            # MUST include thread_id for checkpointer
            config = {
                "configurable": {"thread_id": "1"},
                "recursion_limit": 100,
            }

            # Build graph (denario.py:833)
            graph = build_graph(mermaid_diagram=False)

            # Build GraphState -- MUST match paper_agents/parameters.py GraphState exactly
            # Source: denario.py:836-845
            input_state = {
                "files": {"Folder": project_dir},
                "llm": {
                    "model": self.config.llm_model,
                    "temperature": self.config.llm_temperature,
                    "max_output_tokens": self.config.llm_max_output_tokens,
                },
                "paper": {
                    "journal": journal,
                    "add_citations": self.config.add_citations,
                    "cmbagent_keywords": self.config.cmbagent_keywords,
                },
                "keys": keys,
                "writer": self.config.writer,
            }

            manager.start_step(1, "Generating research paper")

            # CRITICAL: Must use await ainvoke (citations_node is async).
            # Since execute() is already async, we await directly instead of
            # asyncio.run() which would fail in a running event loop.
            await graph.ainvoke(input_state, config)

            # Paper outputs are written to project_dir/paper/ by the graph nodes
            # 4 versions: v1_preliminary, v2_no_citations, v3_citations, v4_final
            paper_dir = os.path.join(project_dir, PAPER_FOLDER)
            paper_pdf = None
            paper_tex = None

            # Find the final paper (v4 > v3 > v2 > v1)
            if os.path.exists(paper_dir):
                for version in [
                    "paper_v4_final",
                    "paper_v3_citations",
                    "paper_v2_no_citations",
                    "paper_v1_preliminary",
                ]:
                    pdf_path = os.path.join(paper_dir, f"{version}.pdf")
                    tex_path = os.path.join(paper_dir, f"{version}.tex")
                    if os.path.exists(pdf_path):
                        paper_pdf = pdf_path
                        break
                    if os.path.exists(tex_path):
                        paper_tex = tex_path

            manager.complete_step(1, "Research paper generated")

            return manager.complete(output_data={
                'shared': {
                    'paper_dir': paper_dir,
                    'paper_pdf': paper_pdf,
                    'paper_tex': paper_tex,
                },
                'artifacts': {
                    'paper/': paper_dir,
                    'paper_pdf': paper_pdf,
                },
            })

        except Exception as e:
            logger.error("Paper generation failed: %s", e, exc_info=True)
            return manager.fail(str(e), traceback.format_exc())

    def validate_input(self, context: PhaseContext) -> List[str]:
        errors = []
        # Paper phase reads from input_files/ directory, not shared_state
        input_files_dir = os.path.join(str(context.work_dir), "input_files")
        if not os.path.exists(input_files_dir):
            errors.append(
                "input_files/ directory is required (run idea, method, experiment phases first)"
            )
        return errors
