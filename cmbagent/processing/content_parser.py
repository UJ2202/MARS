"""
Content parsing utilities for document processing.

This module provides functions to parse formatted content and collect markdown files.
"""

import logging
import os
import re
import glob
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def parse_formatted_content(content: str) -> Optional[Dict[str, Any]]:
    """
    Parse the formatted markdown content from summarizer_response_formatter to extract structured data.
    The content is in markdown format with specific sections.

    Args:
        content: Markdown formatted content string

    Returns:
        Dictionary with parsed fields or None if parsing fails
    """
    summary_data = {}

    try:
        # Extract title (first heading)
        title_match = re.search(r'^# (.+)', content, re.MULTILINE)
        if title_match:
            summary_data['title'] = title_match.group(1).strip()

        # Extract authors
        authors_match = re.search(r'\*\*Authors:\*\*\s*(.+)', content)
        if authors_match:
            authors_text = authors_match.group(1).strip()
            summary_data['authors'] = [author.strip() for author in authors_text.split(',')]

        # Extract date
        date_match = re.search(r'\*\*Date:\*\*\s*(.+)', content)
        if date_match:
            summary_data['date'] = date_match.group(1).strip()

        # Extract journal
        journal_match = re.search(r'\*\*Journal:\*\*\s*(.+)', content)
        if journal_match:
            summary_data['journal'] = journal_match.group(1).strip()

        # Extract abstract
        abstract_match = re.search(r'\*\*Abstract:\*\*\s*(.+?)(?=\n\n\*\*|\n\*\*|\Z)', content, re.DOTALL)
        if abstract_match:
            summary_data['abstract'] = abstract_match.group(1).strip()

        # Extract keywords
        keywords_match = re.search(r'\*\*Keywords:\*\*\s*(.+?)(?=\n\n\*\*|\n\*\*|\Z)', content, re.DOTALL)
        if keywords_match:
            keywords_text = keywords_match.group(1).strip()
            summary_data['keywords'] = [keyword.strip() for keyword in keywords_text.split(',')]

        # Extract key findings
        findings_match = re.search(r'\*\*Key Findings:\*\*\s*\n(.*?)(?=\n\n\*\*|\n\*\*|\Z)', content, re.DOTALL)
        if findings_match:
            findings_text = findings_match.group(1).strip()
            findings_lines = [
                line.strip('- ').strip()
                for line in findings_text.split('\n')
                if line.strip() and line.strip().startswith('-')
            ]
            summary_data['key_findings'] = findings_lines

        # Extract scientific software
        software_match = re.search(r'\*\*Scientific Software:\*\*\s*\n(.*?)(?=\n\n\*\*|\n\*\*|\Z)', content, re.DOTALL)
        if software_match:
            software_text = software_match.group(1).strip()
            if software_text and not software_text.lower().startswith('none'):
                software_lines = [
                    line.strip('- ').strip()
                    for line in software_text.split('\n')
                    if line.strip() and line.strip().startswith('-')
                ]
                summary_data['scientific_software'] = software_lines
            else:
                summary_data['scientific_software'] = []

        # Extract data sources
        sources_match = re.search(r'\*\*Data Sources:\*\*\s*\n(.*?)(?=\n\n\*\*|\n\*\*|\Z)', content, re.DOTALL)
        if sources_match:
            sources_text = sources_match.group(1).strip()
            if sources_text and not sources_text.lower().startswith('none'):
                sources_lines = [
                    line.strip('- ').strip()
                    for line in sources_text.split('\n')
                    if line.strip() and line.strip().startswith('-')
                ]
                summary_data['data_sources'] = sources_lines
            else:
                summary_data['data_sources'] = []

        # Extract data sets
        datasets_match = re.search(r'\*\*Data Sets:\*\*\s*\n(.*?)(?=\n\n\*\*|\n\*\*|\Z)', content, re.DOTALL)
        if datasets_match:
            datasets_text = datasets_match.group(1).strip()
            if datasets_text and not datasets_text.lower().startswith('none'):
                datasets_lines = [
                    line.strip('- ').strip()
                    for line in datasets_text.split('\n')
                    if line.strip() and line.strip().startswith('-')
                ]
                summary_data['data_sets'] = datasets_lines
            else:
                summary_data['data_sets'] = []

        # Extract data analysis methods
        methods_match = re.search(r'\*\*Data Analysis Methods:\*\*\s*\n(.*?)(?=\n\n\*\*|\n\*\*|\Z)', content, re.DOTALL)
        if methods_match:
            methods_text = methods_match.group(1).strip()
            if methods_text:
                methods_lines = [
                    line.strip('- ').strip()
                    for line in methods_text.split('\n')
                    if line.strip() and line.strip().startswith('-')
                ]
                summary_data['data_analysis_methods'] = methods_lines
            else:
                summary_data['data_analysis_methods'] = []

    except Exception as e:
        logger.warning("formatted_content_parse_error", error=str(e))
        return None

    return summary_data if summary_data else None


def collect_markdown_files(folder_path: str, max_depth: int = 10) -> List[str]:
    """
    Collect all markdown files from the folder and subfolders.

    Args:
        folder_path: Path to the folder to search
        max_depth: Maximum directory depth to search

    Returns:
        Sorted list of markdown file paths
    """
    markdown_files = []

    # Use glob to find all markdown files recursively
    for ext in ['*.md', '*.markdown']:
        pattern = os.path.join(folder_path, "**", ext)
        markdown_files.extend(glob.glob(pattern, recursive=True))

    # Filter by depth if needed
    if max_depth < float('inf'):
        filtered_files = []
        for markdown_file in markdown_files:
            relative_path = os.path.relpath(markdown_file, folder_path)
            depth = len(relative_path.split(os.sep)) - 1  # -1 because the file itself is not a directory
            if depth <= max_depth:
                filtered_files.append(markdown_file)
        markdown_files = filtered_files

    return sorted(markdown_files)


def process_single_markdown_with_error_handling(
    markdown_path: str,
    index: int,
    work_dir_base: str,
    clear_work_dir: bool,
    summarizer_model: str,
    summarizer_response_formatter_model: str
) -> Dict[str, Any]:
    """
    Process a single markdown file with error handling.

    Args:
        markdown_path: Path to the markdown file
        index: Index number for this file
        work_dir_base: Base working directory
        clear_work_dir: Whether to clear the work directory
        summarizer_model: Model for summarizer agent
        summarizer_response_formatter_model: Model for formatter agent

    Returns:
        Dictionary with processing results
    """
    # Late import to avoid circular dependency
    from cmbagent.processing.document_summarizer import summarize_document

    try:
        # Create indexed work directory for this document
        work_dir = os.path.join(
            work_dir_base,
            f"doc_{index:03d}_{os.path.splitext(os.path.basename(markdown_path))[0]}"
        )

        # Extract arXiv ID from filename if possible
        filename = os.path.splitext(os.path.basename(markdown_path))[0]
        arxiv_id_pattern = r'([0-9]+\.[0-9]+(?:v[0-9]+)?)'
        arxiv_match = re.search(arxiv_id_pattern, filename)
        arxiv_id = arxiv_match.group(1) if arxiv_match else None

        # Time the summarize_document function
        start_time = time.time()

        # Call the individual summarize_document function
        summary = summarize_document(
            markdown_document_path=markdown_path,
            work_dir=work_dir,
            clear_work_dir=clear_work_dir,
            summarizer_model=summarizer_model,
            summarizer_response_formatter_model=summarizer_response_formatter_model
        )
        end_time = time.time()
        execution_time_summarization = end_time - start_time
        logger.info("summarization_timing", execution_time_seconds=execution_time_summarization)

        # Save the timing report
        timing_report = {
            "execution_time_summarization": execution_time_summarization,
            "arxiv_id": arxiv_id
        }
        timing_path = os.path.join(work_dir, "time/timing_report_summarization.json")
        os.makedirs(os.path.dirname(timing_path), exist_ok=True)
        with open(timing_path, 'w') as f:
            json.dump(timing_report, f, indent=2)
        logger.debug("timing_report_saved", path=timing_path)

        return {
            "markdown_path": str(markdown_path),
            "index": index,
            "work_dir": str(work_dir),
            "success": True,
            "document_summary": summary,
            "filename": Path(markdown_path).name,
            "arxiv_id": arxiv_id
        }

    except Exception as e:
        # Extract arXiv ID even in error case
        filename = Path(markdown_path).stem
        arxiv_id_pattern = r'([0-9]+\.[0-9]+(?:v[0-9]+)?)'
        arxiv_match = re.search(arxiv_id_pattern, filename)
        arxiv_id = arxiv_match.group(1) if arxiv_match else None

        return {
            "markdown_path": str(markdown_path),
            "index": index,
            "success": False,
            "error": str(e),
            "filename": Path(markdown_path).name,
            "arxiv_id": arxiv_id
        }


# Backward compatibility aliases
_parse_formatted_content = parse_formatted_content
_collect_markdown_files = collect_markdown_files
_process_single_markdown_with_error_handling = process_single_markdown_with_error_handling
