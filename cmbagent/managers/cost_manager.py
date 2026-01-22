"""
Cost tracking and reporting for CMBAgent.

This module provides cost collection, aggregation, and reporting functionality.
"""

import os
import json
import datetime
import pandas as pd
from collections import defaultdict
from typing import List, Dict, Any, Optional


class CostManager:
    """
    Manages cost tracking, reporting, and persistence.

    This class handles:
    - Collecting cost data from all agents
    - Aggregating costs per agent and model
    - Calculating token usage
    - Generating formatted reports
    - Saving cost data as JSON
    """

    # Model pricing per million tokens (as of early 2025)
    PRICING = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    }

    def __init__(self, work_dir: str):
        """
        Initialize the CostManager.

        Args:
            work_dir: Working directory for saving cost reports
        """
        self.work_dir = work_dir

    def collect_costs(
        self,
        agents: List[Any],
        groupchat: Optional[Any] = None
    ) -> Dict[str, List[Any]]:
        """
        Collect cost data from all agents.

        Args:
            agents: List of agent instances
            groupchat: Optional groupchat with additional conversable agents

        Returns:
            Dictionary with cost data by column
        """
        cost_dict = defaultdict(list)

        # Collect all agents
        all_agents = [a.agent for a in agents]
        if groupchat is not None and hasattr(groupchat, "new_conversable_agents"):
            all_agents += groupchat.new_conversable_agents

        for agent in all_agents:
            self._collect_agent_cost(agent, cost_dict)

        return cost_dict

    def _collect_agent_cost(self, agent: Any, cost_dict: Dict[str, List[Any]]) -> None:
        """
        Collect cost from a single agent.

        Args:
            agent: Agent instance
            cost_dict: Dictionary to append costs to
        """
        # First try the custom cost_dict (used by vlm_utils)
        if hasattr(agent, "cost_dict") and agent.cost_dict.get("Agent"):
            name = (
                agent.cost_dict["Agent"][0]
                .replace("admin (", "")
                .replace(")", "")
                .replace("_", " ")
            )
            summed_cost = round(sum(agent.cost_dict["Cost"]), 8)
            summed_prompt = int(sum(agent.cost_dict["Prompt Tokens"]))
            summed_comp = int(sum(agent.cost_dict["Completion Tokens"]))
            summed_total = int(sum(agent.cost_dict["Total Tokens"]))
            model_name = agent.cost_dict["Model"][0]

            if name in cost_dict["Agent"]:
                i = cost_dict["Agent"].index(name)
                cost_dict["Cost ($)"][i] += summed_cost
                cost_dict["Prompt Tokens"][i] += summed_prompt
                cost_dict["Completion Tokens"][i] += summed_comp
                cost_dict["Total Tokens"][i] += summed_total
                cost_dict["Model"][i] += model_name
            else:
                cost_dict["Agent"].append(name)
                cost_dict["Cost ($)"].append(summed_cost)
                cost_dict["Prompt Tokens"].append(summed_prompt)
                cost_dict["Completion Tokens"].append(summed_comp)
                cost_dict["Total Tokens"].append(summed_total)
                cost_dict["Model"].append(model_name)

        # Also try AG2's native usage tracking via client
        elif hasattr(agent, "client") and agent.client is not None:
            try:
                usage_summary = getattr(agent.client, "total_usage_summary", None)
                if usage_summary:
                    agent_name = getattr(agent, "name", "unknown")
                    for model_name, model_usage in usage_summary.items():
                        if isinstance(model_usage, dict):
                            prompt_tokens = model_usage.get("prompt_tokens", 0)
                            completion_tokens = model_usage.get("completion_tokens", 0)
                            total_tokens = prompt_tokens + completion_tokens
                            cost = self._calculate_cost(model_name, prompt_tokens, completion_tokens)

                            if agent_name in cost_dict["Agent"]:
                                i = cost_dict["Agent"].index(agent_name)
                                cost_dict["Cost ($)"][i] += cost
                                cost_dict["Prompt Tokens"][i] += prompt_tokens
                                cost_dict["Completion Tokens"][i] += completion_tokens
                                cost_dict["Total Tokens"][i] += total_tokens
                            else:
                                cost_dict["Agent"].append(agent_name)
                                cost_dict["Cost ($)"].append(cost)
                                cost_dict["Prompt Tokens"].append(prompt_tokens)
                                cost_dict["Completion Tokens"].append(completion_tokens)
                                cost_dict["Total Tokens"].append(total_tokens)
                                cost_dict["Model"].append(model_name)
            except Exception as e:
                print(f"Warning: Could not extract AG2 usage for agent {getattr(agent, 'name', 'unknown')}: {e}")

    def _calculate_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost based on model and token counts.

        Args:
            model_name: Name of the model
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Estimated cost in dollars
        """
        model_key = next((k for k in self.PRICING if k in model_name.lower()), None)
        if model_key:
            input_cost = (prompt_tokens / 1_000_000) * self.PRICING[model_key]["input"]
            output_cost = (completion_tokens / 1_000_000) * self.PRICING[model_key]["output"]
            return input_cost + output_cost
        else:
            # Default $5/M tokens
            return ((prompt_tokens + completion_tokens) / 1_000_000) * 5.0

    def display_cost(
        self,
        agents: List[Any],
        final_context: Dict[str, Any],
        groupchat: Optional[Any] = None,
        name_append: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Display a full cost report as a right-aligned Markdown table.

        Also saves the cost data as JSON in the workdir.

        Args:
            agents: List of agent instances
            final_context: Context dictionary to store cost dataframe
            groupchat: Optional groupchat with additional agents
            name_append: Optional string to append to report filename

        Returns:
            DataFrame with cost data
        """
        cost_dict = self.collect_costs(agents, groupchat)

        # Build DataFrame & totals
        df = pd.DataFrame(cost_dict)

        # Only add totals if DataFrame has data
        if not df.empty:
            numeric_cols = df.select_dtypes(include="number").columns
            totals = df[numeric_cols].sum()
            df.loc["Total"] = pd.concat([pd.Series({"Agent": "Total"}), totals])

        # String formatting for display
        if df.empty:
            print("\nDisplaying cost...\n")
            print("No cost data available (no API calls were made)")
        else:
            self._print_cost_table(df)

        final_context['cost_dataframe'] = df

        # Save cost data as JSON
        json_path = self.save_cost_report(df, name_append)
        final_context['cost_report_path'] = json_path

        return df

    def _print_cost_table(self, df: pd.DataFrame) -> None:
        """
        Print cost DataFrame as formatted Markdown table.

        Args:
            df: DataFrame with cost data
        """
        df_str = df.copy()
        df_str["Cost ($)"] = df_str["Cost ($)"].map(lambda x: f"${x:.8f}")
        for col in ["Prompt Tokens", "Completion Tokens", "Total Tokens"]:
            df_str[col] = df_str[col].astype(int).astype(str)

        columns = df_str.columns.tolist()
        rows = df_str.fillna("").values.tolist()

        # Column widths
        widths = [
            max(len(col), max(len(str(row[i])) for row in rows))
            for i, col in enumerate(columns)
        ]

        # Header with alignment markers
        header = "|" + "|".join(f" {columns[i].ljust(widths[i])} " for i in range(len(columns))) + "|"

        # Markdown alignment row: left for text, right for numbers
        align_row = []
        for i, col in enumerate(columns):
            if col == "Agent":
                align_row.append(":" + "-" * (widths[i] + 1))  # :---- for left
            else:
                align_row.append("-" * (widths[i] + 1) + ":")  # ----: for right
        separator = "|" + "|".join(align_row) + "|"

        # Build data lines
        lines = [header, separator]
        for idx, row in enumerate(rows):
            # Insert rule before the Total row
            if row[0] == "Total":
                lines.append("|" + "|".join("-" * (widths[i] + 2) for i in range(len(columns))) + "|")

            cell = []
            for i, col in enumerate(columns):
                s = str(row[i])
                if col == "Agent":
                    cell.append(f" {s.ljust(widths[i])} ")
                else:
                    cell.append(f" {s.rjust(widths[i])} ")
            lines.append("|" + "|".join(cell) + "|")

        print("\nDisplaying cost...\n")
        print("\n".join(lines))

    def save_cost_report(
        self,
        df: pd.DataFrame,
        name_append: Optional[str] = None
    ) -> str:
        """
        Save cost report to JSON file.

        Args:
            df: DataFrame with cost data
            name_append: Optional string to append to filename

        Returns:
            Path to saved JSON file
        """
        # Convert DataFrame to dict for JSON serialization
        cost_data = df.to_dict(orient='records')

        # Add timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save to JSON file in workdir
        cost_dir = os.path.join(self.work_dir, "cost")
        os.makedirs(cost_dir, exist_ok=True)

        if name_append is not None:
            json_path = os.path.join(cost_dir, f"cost_report_{name_append}_{timestamp}.json")
        else:
            json_path = os.path.join(cost_dir, f"cost_report_{timestamp}.json")

        with open(json_path, 'w') as f:
            json.dump(cost_data, f, indent=2)

        print(f"\nCost report data saved to: {json_path}\n")

        return json_path
