"""
Comprehensive Free Tools Integration for AG2 Agents.

This module integrates all free tools from LangChain and CrewAI frameworks
into AG2 agents using the native Interoperability module as shown in the
AG2 documentation.

Based on: https://docs.ag2.ai/latest/docs/use-cases/notebooks/notebooks/agentchat_captainagent_crosstool/

Free Tools Available:
- LangChain: DuckDuckGo Search, Wikipedia, ArXiv, File operations, etc.
- CrewAI: Web scraping, File operations, Code analysis, etc.
"""

import logging
import structlog
from typing import List, Dict, Any, Optional
import warnings

logger = structlog.get_logger(__name__)

try:
    from autogen.interop import Interoperability
    HAS_INTEROP = True
except ImportError:
    HAS_INTEROP = False
    warnings.warn("autogen.interop not available. Please install: pip install ag2[openai,interop-langchain,interop-crewai]")


class AG2FreeToolsLoader:
    """
    Loader for all free tools from LangChain and CrewAI frameworks.
    Uses AG2's native Interoperability module for robust tool conversion.
    """

    def __init__(self):
        """Initialize the tools loader with Interoperability."""
        self.interop = Interoperability() if HAS_INTEROP else None
        self.loaded_tools = {
            'langchain': [],
            'crewai': [],
        }

    def load_langchain_tools(self, tool_names: Optional[List[str]] = None) -> List[Any]:
        """
        Load free LangChain tools using AG2 Interoperability.

        Args:
            tool_names: Specific tool names to load. If None, loads all free tools.
                       Options: 'duckduckgo', 'wikipedia', 'arxiv', 'python_repl',
                               'file_read', 'file_write', 'list_directory'

        Returns:
            List of AG2-converted tools ready to pass to agents

        Example:
            >>> loader = AG2FreeToolsLoader()
            >>> tools = loader.load_langchain_tools(['duckduckgo', 'wikipedia'])
        """
        if not HAS_INTEROP:
            warnings.warn("Interoperability not available. Cannot load LangChain tools.")
            return []

        tools = []

        # DuckDuckGo Search (FREE - no API key needed)
        if tool_names is None or 'duckduckgo' in tool_names:
            try:
                from langchain_community.tools import DuckDuckGoSearchRun
                from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

                api_wrapper = DuckDuckGoSearchAPIWrapper()
                langchain_tool = DuckDuckGoSearchRun(api_wrapper=api_wrapper)
                ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
                tools.append(ag2_tool)
                logger.info("tool_loaded", tool="DuckDuckGo Search")
            except ImportError as e:
                logger.warning("tool_load_failed", tool="DuckDuckGo", error=str(e), install_hint="pip install duckduckgo-search")

        # Wikipedia (FREE)
        if tool_names is None or 'wikipedia' in tool_names:
            try:
                from langchain_community.tools import WikipediaQueryRun
                from langchain_community.utilities import WikipediaAPIWrapper

                langchain_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
                ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
                tools.append(ag2_tool)
                logger.info("tool_loaded", tool="Wikipedia")
            except ImportError as e:
                logger.warning("tool_load_failed", tool="Wikipedia", error=str(e), install_hint="pip install wikipedia")

        # ArXiv (FREE)
        if tool_names is None or 'arxiv' in tool_names:
            try:
                from langchain_community.tools import ArxivQueryRun
                from langchain_community.utilities import ArxivAPIWrapper

                langchain_tool = ArxivQueryRun(api_wrapper=ArxivAPIWrapper())
                ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
                tools.append(ag2_tool)
                logger.info("tool_loaded", tool="ArXiv")
            except ImportError as e:
                logger.warning("tool_load_failed", tool="ArXiv", error=str(e), install_hint="pip install arxiv")

        # Python REPL requires langchain_experimental (separate package)
        # Skipping for now - users can install langchain_experimental if needed

        # File Management Tools (FREE - built-in)
        if tool_names is None or any(x in tool_names for x in ['file_read', 'file_write', 'list_directory']):
            try:
                from langchain_community.tools import (
                    ReadFileTool,
                    WriteFileTool,
                    ListDirectoryTool,
                )

                if tool_names is None or 'file_read' in tool_names:
                    langchain_tool = ReadFileTool()
                    ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
                    tools.append(ag2_tool)
                    logger.info("tool_loaded", tool="File Read")

                if tool_names is None or 'file_write' in tool_names:
                    langchain_tool = WriteFileTool()
                    ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
                    tools.append(ag2_tool)
                    logger.info("tool_loaded", tool="File Write")

                if tool_names is None or 'list_directory' in tool_names:
                    langchain_tool = ListDirectoryTool()
                    ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
                    tools.append(ag2_tool)
                    logger.info("tool_loaded", tool="List Directory")

            except ImportError as e:
                logger.warning("tool_load_failed", tool="file management", error=str(e))

        # # Human Input Tool (FREE - built-in)
        # if tool_names is None or 'human' in tool_names:
        #     try:
        #         from langchain_community.tools import HumanInputRun

        #         langchain_tool = HumanInputRun()
        #         ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
        #         tools.append(ag2_tool)
        #         print("Loaded Human Input tool")
        #     except ImportError as e:
        #         print(f"Could not load Human Input tool: {e}")

        # Note: Shell, HTTP Requests, JSON tools require additional configuration
        # or are in langchain-experimental. Omitted for simplicity.
        # Advanced file operations (Move/Copy/Delete) also require specific setup.

        self.loaded_tools['langchain'] = tools
        return tools

    def load_crewai_tools(self, tool_names: Optional[List[str]] = None) -> List[Any]:
        """
        Load free CrewAI tools using AG2 Interoperability.

        Args:
            tool_names: Specific tool names to load. If None, loads all free tools.
                       Options: 'scrape_website', 'file_read', 'file_write',
                               'directory_read', 'code_docs', 'code_interpreter'

        Returns:
            List of AG2-converted tools ready to pass to agents

        Example:
            >>> loader = AG2FreeToolsLoader()
            >>> tools = loader.load_crewai_tools(['scrape_website', 'file_read'])
        """
        if not HAS_INTEROP:
            warnings.warn("Interoperability not available. Cannot load CrewAI tools.")
            return []

        # Workaround for AG2 0.10.3 bug: get CrewAI interoperability class directly from registry
        # In AG2 0.10.3, convert_tool(type="crewai") fails even though CrewAI is in the registry
        try:
            if 'crewai' in self.interop.registry._registry:
                # CrewAI is registered - instantiate it directly
                CrewAIClass = self.interop.registry._registry['crewai']
                crewai_interop = CrewAIClass()
            else:
                logger.warning("crewai_interop_unavailable", available=list(self.interop.registry._registry.keys()))
                return []
        except (AttributeError, KeyError) as e:
            logger.warning("crewai_interop_access_failed", error=str(e))
            return []

        tools = []

        # Web Scraping Tool (FREE)
        if tool_names is None or 'scrape_website' in tool_names:
            try:
                from crewai_tools import ScrapeWebsiteTool

                crewai_tool = ScrapeWebsiteTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                logger.info("tool_loaded", tool="ScrapeWebsite")
            except ImportError as e:
                logger.warning("tool_load_failed", tool="ScrapeWebsite", error=str(e), install_hint="pip install 'crewai[tools]'")
            except Exception as e:
                logger.warning("tool_convert_failed", tool="ScrapeWebsite", error=str(e))

        # File Operations (FREE)
        if tool_names is None or any(x in tool_names for x in ['file_read', 'file_write', 'directory_read']):
            try:
                from crewai_tools import FileReadTool, DirectoryReadTool

                if tool_names is None or 'file_read' in tool_names:
                    crewai_tool = FileReadTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    logger.info("tool_loaded", tool="FileRead")

                if tool_names is None or 'directory_read' in tool_names:
                    crewai_tool = DirectoryReadTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    logger.info("tool_loaded", tool="DirectoryRead")

            except ImportError as e:
                logger.warning("tool_load_failed", tool="file operations", error=str(e))
            except Exception as e:
                logger.warning("tool_convert_failed", tool="file operations", error=str(e))

        # Code Analysis Tools (FREE)
        if tool_names is None or any(x in tool_names for x in ['code_docs', 'code_interpreter']):
            try:
                from crewai_tools import CodeDocsSearchTool, CodeInterpreterTool

                if tool_names is None or 'code_docs' in tool_names:
                    crewai_tool = CodeDocsSearchTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    logger.info("tool_loaded", tool="CodeDocsSearch")

                if tool_names is None or 'code_interpreter' in tool_names:
                    crewai_tool = CodeInterpreterTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    logger.info("tool_loaded", tool="CodeInterpreter")

            except ImportError as e:
                logger.warning("tool_load_failed", tool="code analysis", error=str(e))
            except Exception as e:
                logger.warning("tool_convert_failed", tool="code analysis", error=str(e))

        # Search Tools (FREE)
        if tool_names is None or any(x in tool_names for x in ['directory_search', 'txt_search', 'json_search', 'csv_search']):
            try:
                from crewai_tools import DirectorySearchTool, TXTSearchTool, JSONSearchTool, CSVSearchTool

                if tool_names is None or 'directory_search' in tool_names:
                    crewai_tool = DirectorySearchTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    logger.info("tool_loaded", tool="DirectorySearch")

                if tool_names is None or 'txt_search' in tool_names:
                    crewai_tool = TXTSearchTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    logger.info("tool_loaded", tool="TXTSearch")

                if tool_names is None or 'json_search' in tool_names:
                    crewai_tool = JSONSearchTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    logger.info("tool_loaded", tool="JSONSearch")

                if tool_names is None or 'csv_search' in tool_names:
                    crewai_tool = CSVSearchTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    logger.info("tool_loaded", tool="CSVSearch")

            except ImportError as e:
                logger.warning("tool_load_failed", tool="search", error=str(e))
            except Exception as e:
                logger.warning("tool_convert_failed", tool="search", error=str(e))

        # PDF Tools (FREE)
        if tool_names is None or 'pdf_search' in tool_names:
            try:
                from crewai_tools import PDFSearchTool

                crewai_tool = PDFSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                logger.info("tool_loaded", tool="PDFSearch")
            except ImportError as e:
                logger.warning("tool_load_failed", tool="PDF search", error=str(e))
            except Exception as e:
                logger.warning("tool_convert_failed", tool="PDF search", error=str(e))

        # Website Search Tool (FREE)
        if tool_names is None or 'website_search' in tool_names:
            try:
                from crewai_tools import WebsiteSearchTool

                crewai_tool = WebsiteSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                logger.info("tool_loaded", tool="WebsiteSearch")
            except ImportError as e:
                logger.warning("tool_load_failed", tool="website search", error=str(e))
            except Exception as e:
                logger.warning("tool_convert_failed", tool="website search", error=str(e))

        # Additional CrewAI Tools (FREE - no API key needed)
        if tool_names is None or 'docx_search' in tool_names:
            try:
                from crewai_tools import DOCXSearchTool

                crewai_tool = DOCXSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                logger.info("tool_loaded", tool="DOCX Search")
            except ImportError as e:
                logger.warning("tool_load_failed", tool="DOCX search", error=str(e))
            except Exception as e:
                logger.warning("tool_convert_failed", tool="DOCX search", error=str(e))

        if tool_names is None or 'xml_search' in tool_names:
            try:
                from crewai_tools import XMLSearchTool

                crewai_tool = XMLSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                logger.info("tool_loaded", tool="XML Search")
            except ImportError as e:
                logger.warning("tool_load_failed", tool="XML search", error=str(e))
            except Exception as e:
                logger.warning("tool_convert_failed", tool="XML search", error=str(e))

        if tool_names is None or 'mdx_search' in tool_names:
            try:
                from crewai_tools import MDXSearchTool

                crewai_tool = MDXSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                logger.info("tool_loaded", tool="MDX Search")
            except ImportError as e:
                logger.warning("tool_load_failed", tool="MDX search", error=str(e))
            except Exception as e:
                logger.warning("tool_convert_failed", tool="MDX search", error=str(e))

        if tool_names is None or 'youtube_video_search' in tool_names:
            try:
                from crewai_tools import YoutubeVideoSearchTool

                crewai_tool = YoutubeVideoSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                logger.info("tool_loaded", tool="YouTube Video Search")
            except ImportError as e:
                logger.warning("tool_load_failed", tool="YouTube video search", error=str(e))
            except Exception as e:
                logger.warning("tool_convert_failed", tool="YouTube video search", error=str(e))

        if tool_names is None or 'youtube_channel_search' in tool_names:
            try:
                from crewai_tools import YoutubeChannelSearchTool

                crewai_tool = YoutubeChannelSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                logger.info("tool_loaded", tool="YouTube Channel Search")
            except ImportError as e:
                logger.warning("tool_load_failed", tool="YouTube channel search", error=str(e))
            except Exception as e:
                logger.warning("tool_convert_failed", tool="YouTube channel search", error=str(e))

        self.loaded_tools['crewai'] = tools
        return tools

    def load_all_free_tools(self) -> Dict[str, List[Any]]:
        """
        Load all available free tools from both LangChain and CrewAI.

        Returns:
            Dictionary with 'langchain' and 'crewai' keys containing tool lists

        Example:
            >>> loader = AG2FreeToolsLoader()
            >>> all_tools = loader.load_all_free_tools()
        """
        logger.info("loading_tools", framework="LangChain")
        langchain_tools = self.load_langchain_tools()

        logger.info("loading_tools", framework="CrewAI")
        crewai_tools = self.load_crewai_tools()

        logger.info("all_tools_loaded", langchain_count=len(langchain_tools), crewai_count=len(crewai_tools), total=len(langchain_tools) + len(crewai_tools))

        return {
            'langchain': langchain_tools,
            'crewai': crewai_tools,
        }

    def get_combined_tool_list(self) -> List[Any]:
        """
        Get a combined flat list of all loaded tools.

        Returns:
            List of all AG2-converted tools
        """
        return self.loaded_tools['langchain'] + self.loaded_tools['crewai']


# Convenience functions
def load_all_free_tools() -> Dict[str, List[Any]]:
    """
    Convenience function to load all free tools.

    Returns:
        Dictionary with 'langchain' and 'crewai' keys containing tool lists

    Example:
        >>> from cmbagent.external_tools.ag2_free_tools import load_all_free_tools
        >>> tools = load_all_free_tools()
    """
    loader = AG2FreeToolsLoader()
    return loader.load_all_free_tools()


def load_langchain_free_tools(tool_names: Optional[List[str]] = None) -> List[Any]:
    """
    Convenience function to load LangChain free tools.

    Args:
        tool_names: Specific tool names to load (optional)

    Returns:
        List of AG2-converted LangChain tools
    """
    loader = AG2FreeToolsLoader()
    return loader.load_langchain_tools(tool_names)


def load_crewai_free_tools(tool_names: Optional[List[str]] = None) -> List[Any]:
    """
    Convenience function to load CrewAI free tools.

    Args:
        tool_names: Specific tool names to load (optional)

    Returns:
        List of AG2-converted CrewAI tools
    """
    loader = AG2FreeToolsLoader()
    return loader.load_crewai_tools(tool_names)
