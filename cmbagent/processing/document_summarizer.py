"""
Document summarization functionality for CMBAgent.

This module provides functions to summarize single documents and batches of documents.
"""

import logging
import structlog
import os
import json
import time
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional

from cmbagent.utils import work_dir_default, get_api_keys_from_env, get_model_config, default_agents_llm_model
from cmbagent.workflows.utils import clean_work_dir
from cmbagent.processing.content_parser import (
    parse_formatted_content,
    collect_markdown_files,
    process_single_markdown_with_error_handling,
)

logger = structlog.get_logger(__name__)


def summarize_document(
    markdown_document_path: str,
    work_dir: str = work_dir_default,
    clear_work_dir: bool = True,
    summarizer_model: str = default_agents_llm_model['summarizer'],
    summarizer_response_formatter_model: str = default_agents_llm_model['summarizer_response_formatter']
) -> Optional[Dict[str, Any]]:
    """
    Summarize a single markdown document.

    Args:
        markdown_document_path: Path to the markdown document
        work_dir: Working directory for outputs
        clear_work_dir: Whether to clear the work directory before processing
        summarizer_model: Model for summarizer agent
        summarizer_response_formatter_model: Model for formatter agent

    Returns:
        Dictionary containing the document summary, or None if summarization fails
    """
    # Late import to avoid circular dependency
    from cmbagent.cmbagent import CMBAgent

    api_keys = get_api_keys_from_env()

    # Load the document from the document_path to markdown file
    with open(markdown_document_path, 'r') as f:
        markdown_document = f.read()

    # Create work directory if it doesn't exist
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if clear_work_dir:
        clean_work_dir(work_dir)

    summarizer_config = get_model_config(summarizer_model, api_keys)
    summarizer_response_formatter_config = get_model_config(summarizer_response_formatter_model, api_keys)

    cmbagent = CMBAgent(
        cache_seed=42,
        work_dir=work_dir,
        agent_llm_configs={
            'summarizer': summarizer_config,
            'summarizer_response_formatter': summarizer_response_formatter_config,
        },
        api_keys=api_keys,
    )

    start_time = time.time()
    cmbagent.solve(
        markdown_document,
        max_rounds=10,
        initial_agent="summarizer",
        shared_context={'current_plan_step_number': 'document_summarizer'}
    )
    end_time = time.time()
    execution_time_summarization = end_time - start_time

    # Extract the final result from the CMBAgent
    final_context = cmbagent.final_context.data if hasattr(cmbagent.final_context, 'data') else cmbagent.final_context
    chat_result = cmbagent.chat_result

    # Extract structured JSON from the chat result
    document_summary = None
    if hasattr(chat_result, 'chat_history'):
        # Look for the summarizer_response_formatter response in the chat history
        for message in chat_result.chat_history:
            if isinstance(message, dict) and message.get('name') == 'summarizer_response_formatter':
                # Try to extract from tool_calls or parse the formatted content
                if 'tool_calls' in message:
                    for tool_call in message.get('tool_calls', []):
                        if hasattr(tool_call, 'function') and hasattr(tool_call.function, 'arguments'):
                            try:
                                document_summary = json.loads(tool_call.function.arguments)
                                break
                            except:
                                continue

                if not document_summary:
                    # Fallback: parse the formatted content back to structured data
                    formatter_content = message.get('content', '')
                    document_summary = parse_formatted_content(formatter_content)
                break

    # Save structured summary to JSON if we have it
    if document_summary and work_dir:
        try:
            summary_file = os.path.join(work_dir, 'document_summary.json')
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(document_summary, f, indent=2, ensure_ascii=False)
            logger.info("document_summary_saved", path=summary_file)
        except Exception as e:
            logger.warning("document_summary_save_failed", error=str(e))

    # Log the document_summary
    logger.debug("document_summary_result", summary=json.dumps(document_summary, indent=4))

    # Delete codebase and database folders as they are not needed
    shutil.rmtree(os.path.join(work_dir, final_context['codebase_path']), ignore_errors=True)
    shutil.rmtree(os.path.join(work_dir, final_context['database_path']), ignore_errors=True)

    cmbagent.display_cost()

    return document_summary


def summarize_documents(
    folder_path: str,
    work_dir_base: str = work_dir_default,
    clear_work_dir: bool = True,
    summarizer_model: str = default_agents_llm_model['summarizer'],
    summarizer_response_formatter_model: str = default_agents_llm_model['summarizer_response_formatter'],
    max_workers: int = 4,
    max_depth: int = 10
) -> Dict[str, Any]:
    """
    Process multiple markdown documents in parallel, summarizing each one.

    Args:
        folder_path: Path to folder containing markdown files
        work_dir_base: Base working directory for output
        clear_work_dir: Whether to clear the working directory
        summarizer_model: Model to use for summarizer agent
        summarizer_response_formatter_model: Model to use for formatter agent
        max_workers: Maximum number of parallel workers
        max_depth: Maximum depth for recursive file search

    Returns:
        Dictionary with summary of processing results including individual document summaries
    """
    api_keys = get_api_keys_from_env()
    folder_path = os.path.abspath(os.path.expanduser(str(folder_path)))

    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    if not os.path.isdir(folder_path):
        raise ValueError(f"Path is not a directory: {folder_path}")

    logger.info("scanning_folder", folder=folder_path, max_depth=max_depth, max_workers=max_workers)

    # Collect all markdown files
    markdown_files = collect_markdown_files(folder_path, max_depth)

    if not markdown_files:
        logger.warning("no_markdown_files_found", folder=folder_path)
        return {
            "processed_files": 0,
            "failed_files": 0,
            "total_files": 0,
            "results": [],
            "folder_path": str(folder_path),
            "work_dir_base": str(work_dir_base)
        }

    logger.info("markdown_files_found", count=len(markdown_files))

    # Create base work directory
    work_dir_base = os.path.abspath(os.path.expanduser(str(work_dir_base)))
    os.makedirs(work_dir_base, exist_ok=True)

    # Initialize results
    results = {
        "processed_files": 0,
        "failed_files": 0,
        "total_files": len(markdown_files),
        "results": [],
        "folder_path": str(folder_path),
        "work_dir_base": str(work_dir_base)
    }

    start_time = time.time()

    if clear_work_dir:
        clean_work_dir(work_dir_base)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_markdown = {
            executor.submit(
                process_single_markdown_with_error_handling,
                markdown_path,
                i + 1,  # 1-indexed
                work_dir_base,
                clear_work_dir,
                summarizer_model,
                summarizer_response_formatter_model
            ): (markdown_path, i + 1) for i, markdown_path in enumerate(markdown_files)
        }

        # Process completed tasks
        for future in as_completed(future_to_markdown):
            markdown_path, index = future_to_markdown[future]

            try:
                result = future.result()
                if result.get("success", False):
                    results["processed_files"] += 1
                    logger.info("document_processed", index=index, filename=Path(markdown_path).name)
                else:
                    results["failed_files"] += 1
                    logger.warning("document_processing_failed", index=index, filename=Path(markdown_path).name, error=result.get('error', 'Unknown error'))

                results["results"].append(result)
            except Exception as e:
                results["failed_files"] += 1
                logger.warning("document_processing_failed", index=index, filename=Path(markdown_path).name, error=str(e))
                results["results"].append({
                    "markdown_path": str(markdown_path),
                    "index": index,
                    "success": False,
                    "error": str(e)
                })

    end_time = time.time()
    total_time = end_time - start_time

    logger.info("processing_complete", processed=results['processed_files'], failed=results['failed_files'], total_time_seconds=round(total_time, 2), output_dir=results['work_dir_base'])

    # Save overall summary
    summary_file = os.path.join(work_dir_base, "processing_summary.json")
    try:
        results["processing_time"] = total_time
        results["timestamp"] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info("processing_summary_saved", path=summary_file)
    except Exception as e:
        logger.warning("processing_summary_save_failed", error=str(e))

    return results
