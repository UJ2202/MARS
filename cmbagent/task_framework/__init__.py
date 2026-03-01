"""
Denario task integration framework.

Provides utilities and phase classes for the multi-stage
research paper workflow (idea -> method -> experiment -> paper).
"""

from cmbagent.task_framework.utils import (
    get_task_result,
    format_prompt,
    format_prompt_safe,
    extract_markdown_content,
    create_work_dir,
    extract_clean_markdown,
    input_check,
    extract_file_paths,
    check_file_paths,
)

__all__ = [
    "get_task_result",
    "format_prompt",
    "format_prompt_safe",
    "extract_markdown_content",
    "create_work_dir",
    "extract_clean_markdown",
    "input_check",
    "extract_file_paths",
    "check_file_paths",
]
