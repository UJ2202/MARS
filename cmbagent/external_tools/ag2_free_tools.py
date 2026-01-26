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

from typing import List, Dict, Any, Optional
import warnings

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
                print("✓ Loaded DuckDuckGo Search tool")
            except ImportError as e:
                print(f"⚠ Could not load DuckDuckGo: {e}")
                print("  Install with: pip install duckduckgo-search")
        
        # Wikipedia (FREE)
        if tool_names is None or 'wikipedia' in tool_names:
            try:
                from langchain_community.tools import WikipediaQueryRun
                from langchain_community.utilities import WikipediaAPIWrapper
                
                langchain_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
                ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
                tools.append(ag2_tool)
                print("✓ Loaded Wikipedia tool")
            except ImportError as e:
                print(f"⚠ Could not load Wikipedia: {e}")
                print("  Install with: pip install wikipedia")
        
        # ArXiv (FREE)
        if tool_names is None or 'arxiv' in tool_names:
            try:
                from langchain_community.tools import ArxivQueryRun
                from langchain_community.utilities import ArxivAPIWrapper
                
                langchain_tool = ArxivQueryRun(api_wrapper=ArxivAPIWrapper())
                ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
                tools.append(ag2_tool)
                print("✓ Loaded ArXiv tool")
            except ImportError as e:
                print(f"⚠ Could not load ArXiv: {e}")
                print("  Install with: pip install arxiv")
        
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
                    print("✓ Loaded File Read tool")
                
                if tool_names is None or 'file_write' in tool_names:
                    langchain_tool = WriteFileTool()
                    ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
                    tools.append(ag2_tool)
                    print("✓ Loaded File Write tool")
                
                if tool_names is None or 'list_directory' in tool_names:
                    langchain_tool = ListDirectoryTool()
                    ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
                    tools.append(ag2_tool)
                    print("✓ Loaded List Directory tool")
                    
            except ImportError as e:
                print(f"⚠ Could not load file management tools: {e}")
        
        # # Human Input Tool (FREE - built-in)
        # if tool_names is None or 'human' in tool_names:
        #     try:
        #         from langchain_community.tools import HumanInputRun
                
        #         langchain_tool = HumanInputRun()
        #         ag2_tool = self.interop.convert_tool(tool=langchain_tool, type="langchain")
        #         tools.append(ag2_tool)
        #         print("✓ Loaded Human Input tool")
        #     except ImportError as e:
        #         print(f"⚠ Could not load Human Input tool: {e}")
        
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
                print(f"⚠ CrewAI interoperability not available in registry")
                print(f"  Available: {list(self.interop.registry._registry.keys())}")
                return []
        except (AttributeError, KeyError) as e:
            print(f"⚠ Could not access CrewAI interoperability: {e}")
            return []
        
        tools = []
        
        # Web Scraping Tool (FREE)
        if tool_names is None or 'scrape_website' in tool_names:
            try:
                from crewai_tools import ScrapeWebsiteTool
                
                crewai_tool = ScrapeWebsiteTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                print("✓ Loaded ScrapeWebsite tool")
            except ImportError as e:
                print(f"⚠ Could not load ScrapeWebsite: {e}")
                print("  Install with: pip install 'crewai[tools]'")
            except Exception as e:
                print(f"⚠ Error converting ScrapeWebsite tool: {e}")
        
        # File Operations (FREE)
        if tool_names is None or any(x in tool_names for x in ['file_read', 'file_write', 'directory_read']):
            try:
                from crewai_tools import FileReadTool, DirectoryReadTool
                
                if tool_names is None or 'file_read' in tool_names:
                    crewai_tool = FileReadTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    print("✓ Loaded FileRead tool")
                
                if tool_names is None or 'directory_read' in tool_names:
                    crewai_tool = DirectoryReadTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    print("✓ Loaded DirectoryRead tool")
                    
            except ImportError as e:
                print(f"⚠ Could not load file operation tools: {e}")
            except Exception as e:
                print(f"⚠ Error converting file operation tools: {e}")
        
        # Code Analysis Tools (FREE)
        if tool_names is None or any(x in tool_names for x in ['code_docs', 'code_interpreter']):
            try:
                from crewai_tools import CodeDocsSearchTool, CodeInterpreterTool
                
                if tool_names is None or 'code_docs' in tool_names:
                    crewai_tool = CodeDocsSearchTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    print("✓ Loaded CodeDocsSearch tool")
                
                if tool_names is None or 'code_interpreter' in tool_names:
                    crewai_tool = CodeInterpreterTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    print("✓ Loaded CodeInterpreter tool")
                    
            except ImportError as e:
                print(f"⚠ Could not load code analysis tools: {e}")
            except Exception as e:
                print(f"⚠ Error converting code analysis tools: {e}")
        
        # Search Tools (FREE)
        if tool_names is None or any(x in tool_names for x in ['directory_search', 'txt_search', 'json_search', 'csv_search']):
            try:
                from crewai_tools import DirectorySearchTool, TXTSearchTool, JSONSearchTool, CSVSearchTool
                
                if tool_names is None or 'directory_search' in tool_names:
                    crewai_tool = DirectorySearchTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    print("✓ Loaded DirectorySearch tool")
                
                if tool_names is None or 'txt_search' in tool_names:
                    crewai_tool = TXTSearchTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    print("✓ Loaded TXTSearch tool")
                
                if tool_names is None or 'json_search' in tool_names:
                    crewai_tool = JSONSearchTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    print("✓ Loaded JSONSearch tool")
                
                if tool_names is None or 'csv_search' in tool_names:
                    crewai_tool = CSVSearchTool()
                    ag2_tool = crewai_interop.convert_tool(crewai_tool)
                    tools.append(ag2_tool)
                    print("✓ Loaded CSVSearch tool")
                    
            except ImportError as e:
                print(f"⚠ Could not load search tools: {e}")
            except Exception as e:
                print(f"⚠ Error converting search tools: {e}")
        
        # PDF Tools (FREE)
        if tool_names is None or 'pdf_search' in tool_names:
            try:
                from crewai_tools import PDFSearchTool
                
                crewai_tool = PDFSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                print("✓ Loaded PDFSearch tool")
            except ImportError as e:
                print(f"⚠ Could not load PDF search tool: {e}")
            except Exception as e:
                print(f"⚠ Error converting PDF search tool: {e}")
        
        # Website Search Tool (FREE)
        if tool_names is None or 'website_search' in tool_names:
            try:
                from crewai_tools import WebsiteSearchTool
                
                crewai_tool = WebsiteSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                print("✓ Loaded WebsiteSearch tool")
            except ImportError as e:
                print(f"⚠ Could not load website search tool: {e}")
            except Exception as e:
                print(f"⚠ Error converting website search tool: {e}")
        
        # Additional CrewAI Tools (FREE - no API key needed)
        if tool_names is None or 'docx_search' in tool_names:
            try:
                from crewai_tools import DOCXSearchTool
                
                crewai_tool = DOCXSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                print("✓ Loaded DOCX Search tool")
            except ImportError as e:
                print(f"⚠ Could not load DOCX search tool: {e}")
            except Exception as e:
                print(f"⚠ Error converting DOCX search tool: {e}")
        
        if tool_names is None or 'xml_search' in tool_names:
            try:
                from crewai_tools import XMLSearchTool
                
                crewai_tool = XMLSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                print("✓ Loaded XML Search tool")
            except ImportError as e:
                print(f"⚠ Could not load XML search tool: {e}")
            except Exception as e:
                print(f"⚠ Error converting XML search tool: {e}")
        
        if tool_names is None or 'mdx_search' in tool_names:
            try:
                from crewai_tools import MDXSearchTool
                
                crewai_tool = MDXSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                print("✓ Loaded MDX Search tool")
            except ImportError as e:
                print(f"⚠ Could not load MDX search tool: {e}")
            except Exception as e:
                print(f"⚠ Error converting MDX search tool: {e}")
        
        if tool_names is None or 'youtube_video_search' in tool_names:
            try:
                from crewai_tools import YoutubeVideoSearchTool
                
                crewai_tool = YoutubeVideoSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                print("✓ Loaded YouTube Video Search tool")
            except ImportError as e:
                print(f"⚠ Could not load YouTube video search tool: {e}")
            except Exception as e:
                print(f"⚠ Error converting YouTube video search tool: {e}")
        
        if tool_names is None or 'youtube_channel_search' in tool_names:
            try:
                from crewai_tools import YoutubeChannelSearchTool
                
                crewai_tool = YoutubeChannelSearchTool()
                ag2_tool = crewai_interop.convert_tool(crewai_tool)
                tools.append(ag2_tool)
                print("✓ Loaded YouTube Channel Search tool")
            except ImportError as e:
                print(f"⚠ Could not load YouTube channel search tool: {e}")
            except Exception as e:
                print(f"⚠ Error converting YouTube channel search tool: {e}")
        
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
            >>> print(f"Loaded {len(all_tools['langchain'])} LangChain tools")
            >>> print(f"Loaded {len(all_tools['crewai'])} CrewAI tools")
        """
        print("\n" + "="*60)
        print("Loading LangChain Free Tools")
        print("="*60)
        langchain_tools = self.load_langchain_tools()
        
        print("\n" + "="*60)
        print("Loading CrewAI Free Tools")
        print("="*60)
        crewai_tools = self.load_crewai_tools()
        
        print("\n" + "="*60)
        print(f"✓ Total: {len(langchain_tools)} LangChain + {len(crewai_tools)} CrewAI = {len(langchain_tools) + len(crewai_tools)} tools")
        print("="*60 + "\n")
        
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
