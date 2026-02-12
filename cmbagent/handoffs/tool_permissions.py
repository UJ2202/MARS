"""
Tool Permission Manager — session-level auto-allow for tool execution.

Like Claude Code's permission system: users can approve tool categories
once and have them auto-allowed for the rest of the session.

Tool Categories:
    - bash: Shell/bash command execution
    - code_exec: Python/code execution
    - file_write: Creating or modifying files
    - install: Package installation (pip, npm, etc.)
    - web: Web requests, API calls
    - read_only: Safe read operations (auto-allowed by default)
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Set, Dict, List, Optional

logger = logging.getLogger(__name__)

# Tool categories ordered by risk level
TOOL_CATEGORIES = {
    "bash": "Shell/bash command execution",
    "code_exec": "Python or other code execution",
    "file_write": "Creating or modifying files",
    "install": "Package installation",
    "web": "Web requests and API calls",
    "read_only": "Safe read-only operations",
}

# Categories that are safe by default (never need approval)
SAFE_CATEGORIES = {"read_only"}

# Keywords for classifying operations from prompt context
CATEGORY_KEYWORDS = {
    "bash": [
        "bash", "shell", "terminal", "command line", "subprocess",
        "os.system", "chmod", "rm ", "mkdir", "mv ", "cp ",
        "sudo", "apt", "brew", "curl", "wget",
    ],
    "install": [
        "pip install", "npm install", "yarn add", "conda install",
        "apt-get", "brew install", "pip3 install", "requirements.txt",
        "package", "dependency", "install",
    ],
    "file_write": [
        "write file", "create file", "save file", "edit file",
        "modify file", "delete file", "overwrite", "open.*'w'",
        "with open", "f.write", "pathlib.*write",
    ],
    "code_exec": [
        "execute", "run code", "python", "script",
        "exec(", "eval(", "compile(",
    ],
    "web": [
        "requests.get", "requests.post", "urllib", "httpx",
        "fetch", "api call", "http://", "https://",
    ],
}


@dataclass
class ToolPermissionManager:
    """
    Tracks session-level tool permissions.

    Like Claude Code's 'Allow for Session' — once a user approves a tool
    category, all subsequent operations of that type are auto-allowed.

    Usage:
        manager = ToolPermissionManager(mode="prompt")

        # Check before executing
        if manager.is_allowed("bash"):
            execute()  # Auto-allowed
        else:
            ask_user()  # Need approval

        # User clicks "Allow for Session"
        manager.allow_for_session("bash")

        # Now all bash commands are auto-allowed
        assert manager.is_allowed("bash") == True
    """

    mode: str = "prompt"  # "prompt" | "auto_allow_all" | "none"
    _session_allowed: Set[str] = field(default_factory=lambda: set(SAFE_CATEGORIES))
    _denied: Set[str] = field(default_factory=set)
    _history: List[Dict] = field(default_factory=list)

    def is_allowed(self, category: str) -> bool:
        """Check if a tool category is auto-allowed for this session."""
        if self.mode == "auto_allow_all":
            return True
        if self.mode == "none":
            return True  # No approval needed = everything allowed
        if category in self._denied:
            return False
        return category in self._session_allowed

    def allow_for_session(self, category: str) -> None:
        """Mark a tool category as auto-allowed for the rest of this session."""
        self._session_allowed.add(category)
        self._denied.discard(category)
        self._history.append({
            "action": "allow_session",
            "category": category,
        })
        logger.info("tool_category_auto_allowed", category=category)

    def deny_for_session(self, category: str) -> None:
        """Mark a tool category as denied for the rest of this session."""
        self._denied.add(category)
        self._session_allowed.discard(category)
        self._history.append({
            "action": "deny_session",
            "category": category,
        })
        logger.info("tool_category_denied", category=category)

    def allow_once(self, category: str) -> None:
        """Record a one-time allow (doesn't persist for session)."""
        self._history.append({
            "action": "allow_once",
            "category": category,
        })

    def classify_from_prompt(self, prompt: str) -> str:
        """
        Classify what tool category an operation belongs to based on the prompt.

        Args:
            prompt: The human input prompt from AG2 (contains agent context)

        Returns:
            Tool category string (bash, code_exec, file_write, install, etc.)
        """
        prompt_lower = prompt.lower()

        # Check each category's keywords (most specific first)
        for category in ["install", "bash", "file_write", "web", "code_exec"]:
            keywords = CATEGORY_KEYWORDS.get(category, [])
            for keyword in keywords:
                if keyword in prompt_lower:
                    return category

        return "code_exec"  # Default for unknown operations

    def classify_from_agent(self, agent_name: str) -> str:
        """
        Classify tool category based on the agent name.

        Args:
            agent_name: Name of the agent requesting approval

        Returns:
            Tool category string
        """
        agent_lower = agent_name.lower()

        if "bash" in agent_lower or "executor_bash" in agent_lower:
            return "bash"
        elif "installer" in agent_lower:
            return "install"
        elif "executor" in agent_lower or "engineer" in agent_lower:
            return "code_exec"
        elif "researcher" in agent_lower or "web_surfer" in agent_lower:
            return "web"
        elif "formatter" in agent_lower or "summarizer" in agent_lower:
            return "read_only"
        else:
            return "code_exec"

    def get_session_permissions(self) -> Dict[str, bool]:
        """Get current session permission state for all categories."""
        return {
            cat: self.is_allowed(cat)
            for cat in TOOL_CATEGORIES
        }

    def get_history(self) -> List[Dict]:
        """Get the approval history for this session."""
        return self._history.copy()
