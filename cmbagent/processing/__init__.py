"""
Document processing module for CMBAgent.

This module provides document processing functionality:
- Content parsing from formatted markdown
- Document summarization (single and batch)
- Task preprocessing with arXiv paper extraction
"""

from cmbagent.processing.content_parser import (
    parse_formatted_content,
    collect_markdown_files,
    process_single_markdown_with_error_handling,
)
from cmbagent.processing.document_summarizer import (
    summarize_document,
    summarize_documents,
)
from cmbagent.processing.task_preprocessor import preprocess_task

__all__ = [
    "parse_formatted_content",
    "collect_markdown_files",
    "process_single_markdown_with_error_handling",
    "summarize_document",
    "summarize_documents",
    "preprocess_task",
]
