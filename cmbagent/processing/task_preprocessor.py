"""
Task preprocessing functionality for CMBAgent.

This module provides the preprocess_task function that:
1. Extracts arXiv URLs and downloads PDFs
2. OCRs PDFs to markdown
3. Summarizes the papers
4. Appends contextual information to the original text
"""

import logging
import os
from typing import Optional

from cmbagent.utils import work_dir_default, default_agents_llm_model
from cmbagent.workflows.utils import clean_work_dir

logger = logging.getLogger(__name__)


def preprocess_task(
    text: str,
    work_dir: str = work_dir_default,
    clear_work_dir_flag: bool = True,
    max_workers: int = 4,
    max_depth: int = 10,
    summarizer_model: str = default_agents_llm_model['summarizer'],
    summarizer_response_formatter_model: str = default_agents_llm_model['summarizer_response_formatter'],
    skip_arxiv_download: bool = False,
    skip_ocr: bool = False,
    skip_summarization: bool = False,
    callbacks=None,
) -> str:
    """
    Preprocess a task description by:
    1. Extracting arXiv URLs and downloading PDFs
    2. OCRing PDFs to markdown
    3. Summarizing the papers
    4. Appending contextual information to the original text

    Args:
        text: The input task description text containing arXiv URLs
        work_dir: Working directory for processing files
        clear_work_dir_flag: Whether to clear the work directory before starting
        max_workers: Number of parallel workers for processing
        max_depth: Maximum directory depth for file searching
        summarizer_model: Model for summarizer agent
        summarizer_response_formatter_model: Model for formatter agent
        skip_arxiv_download: Skip the arXiv download step
        skip_ocr: Skip the OCR step
        skip_summarization: Skip the summarization step
        callbacks: Optional WorkflowCallbacks for tracking

    Returns:
        The original text with appended "Contextual Information and References" section
    """
    # Late imports to avoid circular dependencies
    from cmbagent.arxiv_downloader import arxiv_filter
    from cmbagent.ocr import process_folder
    from cmbagent.processing.document_summarizer import summarize_documents

    if callbacks:
        callbacks.invoke_phase_change("execution", 1)

    logger.info("task_preprocessing_started", work_dir=work_dir)

    if clear_work_dir_flag:
        clean_work_dir(work_dir)

    # Step 1: Extract arXiv URLs and download PDFs
    arxiv_results = None
    if not skip_arxiv_download:
        logger.info("step_1_downloading_arxiv_papers")
        try:
            arxiv_results = arxiv_filter(text, work_dir=work_dir)
            logger.info("arxiv_download_complete", downloads_successful=arxiv_results['downloads_successful'], total_available=arxiv_results['downloads_successful'] + arxiv_results['downloads_skipped'])

            if arxiv_results['downloads_successful'] + arxiv_results['downloads_skipped'] == 0:
                logger.info("no_arxiv_papers_found", action="skipping processing steps")
                return text
        except Exception as e:
            logger.error("arxiv_download_failed", error=str(e))
            return text

    # Get the docs folder path where PDFs were downloaded
    docs_folder = os.path.join(work_dir, "docs")
    if not os.path.exists(docs_folder):
        logger.info("no_docs_folder_found", action="returning original text")
        return text

    # Step 2: OCR PDFs to markdown
    ocr_results = None
    if not skip_ocr:
        logger.info("step_2_converting_pdfs_to_markdown")
        try:
            ocr_results = process_folder(
                folder_path=docs_folder,
                save_markdown=True,
                save_json=False,  # We don't need JSON for summarization
                save_text=False,
                max_depth=max_depth,
                max_workers=max_workers,
                work_dir=work_dir
            )
            logger.info("ocr_complete", processed_files=ocr_results.get('processed_files', 0))
            if ocr_results.get('processed_files', 0) == 0:
                logger.info("no_pdf_files_for_ocr", action="returning original text")
                return text
        except Exception as e:
            logger.error("ocr_processing_failed", error=str(e))
            return text

    # Find the markdown output directory from OCR
    docs_processed_folder = docs_folder + "_processed"
    if not os.path.exists(docs_processed_folder):
        logger.info("no_processed_markdown_folder", path=docs_processed_folder, action="returning original text")
        return text

    # Step 3: Summarize the markdown documents
    summary_results = None
    if not skip_summarization:
        logger.info("step_3_summarizing_papers")
        try:
            # Create summaries directory in the main work directory
            summaries_dir = os.path.join(work_dir, "summaries")
            summary_results = summarize_documents(
                folder_path=docs_processed_folder,
                work_dir_base=summaries_dir,
                clear_work_dir=clear_work_dir_flag,
                max_workers=max_workers,
                max_depth=max_depth,
                summarizer_model=summarizer_model,
                summarizer_response_formatter_model=summarizer_response_formatter_model
            )
            logger.info("summarization_complete", processed_files=summary_results.get('processed_files', 0))

            if summary_results.get('processed_files', 0) == 0:
                logger.info("no_documents_summarized", action="returning original text")
                return text

            # Step 4: Collect all summaries and format the contextual information
            logger.info("step_4_formatting_contextual_information")
            contextual_info = []

            for result in summary_results.get('results', []):
                if result.get('success', False) and 'document_summary' in result:
                    summary = result['document_summary']
                    arxiv_id = result.get('arxiv_id')

                    # Format each summary
                    title = summary.get('title', 'Unknown Title')
                    authors = summary.get('authors', [])
                    authors_str = ', '.join(authors) if authors else 'Unknown Authors'
                    date = summary.get('date', 'Unknown Date')
                    abstract = summary.get('abstract', 'No abstract available')
                    keywords = summary.get('keywords', [])
                    keywords_str = ', '.join(keywords) if keywords else 'No keywords'
                    key_findings = summary.get('key_findings', [])

                    # Add arXiv ID if available
                    arxiv_info = f" (arXiv:{arxiv_id})" if arxiv_id else ""

                    paper_info = f"""
**{title}{arxiv_info}**
- Authors: {authors_str}
- Date: {date}
- Keywords: {keywords_str}
- Abstract: {abstract}"""

                    if key_findings:
                        paper_info += "\n- Key Findings:"
                        for finding in key_findings:
                            paper_info += f"\n  - {finding}"

                    contextual_info.append(paper_info)

            # Step 5: Append the contextual information to the original text
            if contextual_info:
                footer = "\n\n## Contextual Information and References\n"
                footer += "\n".join(contextual_info)

                enhanced_text = text + footer

                # Save enhanced text to enhanced_input.md
                enhanced_input_path = os.path.join(work_dir, "enhanced_input.md")
                try:
                    with open(enhanced_input_path, 'w', encoding='utf-8') as f:
                        f.write(enhanced_text)
                    logger.info("enhanced_input_saved", path=enhanced_input_path)
                except Exception as e:
                    logger.warning("enhanced_input_save_failed", error=str(e))

                logger.info("task_preprocessing_completed", papers_count=len(contextual_info))
                return enhanced_text
            else:
                logger.info("no_valid_summaries_found", action="returning original text")
                return text
        except Exception as e:
            logger.error("summarization_failed", error=str(e))
            return text

    return text
