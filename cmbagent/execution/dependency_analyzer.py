"""
Dependency Analyzer - LLM-based task dependency analysis

This module uses LLM to analyze workflow tasks and identify dependencies
between them for parallel execution optimization.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from cmbagent.execution.dependency_graph import DependencyGraph

logger = logging.getLogger(__name__)


DEPENDENCY_ANALYSIS_PROMPT = """You are analyzing a scientific workflow to identify task dependencies.

Given these tasks:
{task_list}

For each pair of tasks, determine:
1. DEPENDENT: Task B must wait for Task A to complete
2. INDEPENDENT: Tasks can execute in parallel
3. CONDITIONAL: Dependency exists only under certain conditions

Consider:
- Data flow (outputs → inputs)
- File system conflicts (same file writes)
- API rate limits (same external service)
- Scientific logic (conceptual dependencies)
- Order dependencies (task order matters)

Return JSON with this exact structure:
{{
  "dependencies": [
    {{"from": "task_id_1", "to": "task_id_2", "type": "data", "reason": "task_2 needs output from task_1"}},
    {{"from": "task_id_1", "to": "task_id_3", "type": "none", "reason": "tasks are independent"}}
  ],
  "parallel_groups": [
    ["task_id_2", "task_id_3"],
    ["task_id_4"]
  ]
}}

Important rules:
- Every task pair must have an entry in dependencies
- Type can be: "data", "file", "api", "logic", "order", "none"
- parallel_groups should list tasks that can run simultaneously
- Be conservative: if unsure, mark as dependent
"""


class DependencyAnalyzer:
    """Analyzes task dependencies using LLM"""

    def __init__(self, llm_client: Optional[Any] = None):
        """
        Initialize dependency analyzer

        Args:
            llm_client: Optional LLM client (uses OpenAI by default)
        """
        self.llm_client = llm_client
        self._cache = {}  # Cache analysis results

    def analyze(
        self,
        tasks: List[Dict[str, Any]],
        use_cache: bool = True
    ) -> DependencyGraph:
        """
        Analyze task dependencies and create dependency graph

        Args:
            tasks: List of task dictionaries with id, description, agent, etc.
            use_cache: Whether to use cached results

        Returns:
            DependencyGraph with nodes and edges
        """
        # Create cache key
        cache_key = self._create_cache_key(tasks)

        if use_cache and cache_key in self._cache:
            logger.info("Using cached dependency analysis")
            return self._cache[cache_key]

        logger.info(f"Analyzing dependencies for {len(tasks)} tasks")

        # Build dependency graph
        graph = DependencyGraph()

        # Add all nodes
        for task in tasks:
            graph.add_node(
                node_id=task["id"],
                metadata={
                    "description": task.get("description", ""),
                    "agent": task.get("agent", ""),
                    "type": task.get("type", "agent")
                }
            )

        # If only one task, no dependencies to analyze
        if len(tasks) <= 1:
            self._cache[cache_key] = graph
            return graph

        # Use LLM to analyze dependencies
        try:
            dependency_data = self._llm_analyze_dependencies(tasks)

            # Add edges based on analysis
            for dep in dependency_data.get("dependencies", []):
                if dep["type"] != "none":
                    graph.add_edge(
                        from_id=dep["from"],
                        to_id=dep["to"],
                        dependency_type=dep["type"],
                        reason=dep.get("reason", "")
                    )

            logger.info(
                f"Dependency analysis complete: {len(graph.edges)} dependencies found"
            )

        except Exception as e:
            logger.warning(f"LLM dependency analysis failed: {e}")
            logger.info("Falling back to sequential dependencies")
            # Fallback: create sequential dependencies
            self._create_sequential_dependencies(graph, tasks)

        # Cache result
        self._cache[cache_key] = graph

        return graph

    def _llm_analyze_dependencies(
        self,
        tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use LLM to analyze task dependencies

        Args:
            tasks: List of task dictionaries

        Returns:
            Dictionary with dependencies and parallel_groups
        """
        # Format task list for prompt
        task_descriptions = []
        for task in tasks:
            task_desc = (
                f"- ID: {task['id']}\n"
                f"  Agent: {task.get('agent', 'unknown')}\n"
                f"  Description: {task.get('description', 'No description')}"
            )
            task_descriptions.append(task_desc)

        task_list_str = "\n".join(task_descriptions)

        prompt = DEPENDENCY_ANALYSIS_PROMPT.format(task_list=task_list_str)

        # Get LLM client
        if self.llm_client is None:
            self.llm_client = self._get_default_llm_client()

        # Call LLM
        response = self.llm_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a workflow dependency analyzer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        # Parse response
        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        return result

    def _get_default_llm_client(self) -> Any:
        """Get default OpenAI client (auto-detects Azure)"""
        try:
            import os
            from cmbagent.llm_provider import create_openai_client

            return create_openai_client()
        except ImportError:
            raise ImportError(
                "OpenAI client not available. Install with: pip install openai"
            )

    def _create_sequential_dependencies(
        self,
        graph: DependencyGraph,
        tasks: List[Dict[str, Any]]
    ) -> None:
        """
        Create sequential dependencies (fallback)

        Args:
            graph: Dependency graph to populate
            tasks: List of tasks
        """
        for i in range(len(tasks) - 1):
            graph.add_edge(
                from_id=tasks[i]["id"],
                to_id=tasks[i + 1]["id"],
                dependency_type="order",
                reason="Sequential execution (fallback)"
            )

    def _create_cache_key(self, tasks: List[Dict[str, Any]]) -> str:
        """
        Create cache key from tasks

        Args:
            tasks: List of task dictionaries

        Returns:
            Cache key string
        """
        # Create hash from task IDs and descriptions
        task_str = "|".join([
            f"{t['id']}:{t.get('description', '')[:50]}"
            for t in tasks
        ])
        return str(hash(task_str))

    def clear_cache(self) -> None:
        """Clear analysis cache"""
        self._cache.clear()
        logger.info("Dependency analysis cache cleared")
