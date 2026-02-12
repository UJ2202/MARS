"""
CrewAI free tools integration for CMBAgent.

This module provides access to CrewAI's free tools that don't require API keys.
"""

import logging
from typing import List
from .tool_adapter import AG2ToolAdapter, convert_crewai_tool_to_ag2

logger = logging.getLogger(__name__)


def get_crewai_free_tools() -> List[AG2ToolAdapter]:
    """
    Get all available free CrewAI tools.

    Returns:
        List of AG2ToolAdapter instances for free CrewAI tools

    Example:
        >>> from cmbagent.external_tools import get_crewai_free_tools
        >>> tools = get_crewai_free_tools()
    """
    tools = []

    try:
        # File operations tools (free)
        from crewai_tools import (
            FileReadTool,
            DirectoryReadTool,
            FileWriteTool,
        )

        tools.extend([
            convert_crewai_tool_to_ag2(FileReadTool()),
            convert_crewai_tool_to_ag2(DirectoryReadTool()),
            convert_crewai_tool_to_ag2(FileWriteTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="CrewAI file tools", error=str(e))

    try:
        # Code analysis tools (free)
        from crewai_tools import (
            CodeDocsSearchTool,
            CodeInterpreterTool,
        )

        tools.extend([
            convert_crewai_tool_to_ag2(CodeDocsSearchTool()),
            convert_crewai_tool_to_ag2(CodeInterpreterTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="CrewAI code tools", error=str(e))

    try:
        # Web scraping tools (free)
        from crewai_tools import (
            ScrapeWebsiteTool,
            WebsiteSearchTool,
        )

        tools.extend([
            convert_crewai_tool_to_ag2(ScrapeWebsiteTool()),
            convert_crewai_tool_to_ag2(WebsiteSearchTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="CrewAI web tools", error=str(e))

    try:
        # Directory and file search tools (free)
        from crewai_tools import (
            DirectorySearchTool,
            TXTSearchTool,
            JSONSearchTool,
            XMLSearchTool,
            CSVSearchTool,
            MDXSearchTool,
        )

        tools.extend([
            convert_crewai_tool_to_ag2(DirectorySearchTool()),
            convert_crewai_tool_to_ag2(TXTSearchTool()),
            convert_crewai_tool_to_ag2(JSONSearchTool()),
            convert_crewai_tool_to_ag2(XMLSearchTool()),
            convert_crewai_tool_to_ag2(CSVSearchTool()),
            convert_crewai_tool_to_ag2(MDXSearchTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="CrewAI search tools", error=str(e))

    try:
        # PDF tools (free)
        from crewai_tools import PDFSearchTool

        tools.append(convert_crewai_tool_to_ag2(PDFSearchTool()))
    except ImportError as e:
        logger.warning("tool_import_failed", tool="CrewAI PDF tools", error=str(e))

    try:
        # GitHub tools (free with GitHub API)
        from crewai_tools import GithubSearchTool

        tools.append(convert_crewai_tool_to_ag2(GithubSearchTool()))
    except ImportError as e:
        logger.warning("tool_import_failed", tool="CrewAI GitHub tools", error=str(e))

    return tools


def get_crewai_file_tools() -> List[AG2ToolAdapter]:
    """
    Get CrewAI file operation tools.

    Returns:
        List of file-related tools
    """
    tools = []

    try:
        from crewai_tools import (
            FileReadTool,
            DirectoryReadTool,
            FileWriteTool,
            DirectorySearchTool,
        )

        tools.extend([
            convert_crewai_tool_to_ag2(FileReadTool()),
            convert_crewai_tool_to_ag2(DirectoryReadTool()),
            convert_crewai_tool_to_ag2(FileWriteTool()),
            convert_crewai_tool_to_ag2(DirectorySearchTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="CrewAI file tools", error=str(e))

    return tools


def get_crewai_web_tools() -> List[AG2ToolAdapter]:
    """
    Get CrewAI web scraping and search tools.

    Returns:
        List of web-related tools
    """
    tools = []

    try:
        from crewai_tools import (
            ScrapeWebsiteTool,
            WebsiteSearchTool,
        )

        tools.extend([
            convert_crewai_tool_to_ag2(ScrapeWebsiteTool()),
            convert_crewai_tool_to_ag2(WebsiteSearchTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="CrewAI web tools", error=str(e))

    return tools


def get_crewai_code_tools() -> List[AG2ToolAdapter]:
    """
    Get CrewAI code analysis tools.

    Returns:
        List of code-related tools
    """
    tools = []

    try:
        from crewai_tools import (
            CodeDocsSearchTool,
            CodeInterpreterTool,
        )

        tools.extend([
            convert_crewai_tool_to_ag2(CodeDocsSearchTool()),
            convert_crewai_tool_to_ag2(CodeInterpreterTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="CrewAI code tools", error=str(e))

    return tools


def get_crewai_search_tools() -> List[AG2ToolAdapter]:
    """
    Get CrewAI document search tools.

    Returns:
        List of search-related tools
    """
    tools = []

    try:
        from crewai_tools import (
            TXTSearchTool,
            JSONSearchTool,
            XMLSearchTool,
            CSVSearchTool,
            MDXSearchTool,
            PDFSearchTool,
        )

        tools.extend([
            convert_crewai_tool_to_ag2(TXTSearchTool()),
            convert_crewai_tool_to_ag2(JSONSearchTool()),
            convert_crewai_tool_to_ag2(XMLSearchTool()),
            convert_crewai_tool_to_ag2(CSVSearchTool()),
            convert_crewai_tool_to_ag2(MDXSearchTool()),
            convert_crewai_tool_to_ag2(PDFSearchTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="CrewAI search tools", error=str(e))

    return tools
