"""
Register web fetching tools for CMBAgent agents.

These functions can be called by researcher agent to fetch real data.
"""

from cmbagent.web_fetcher import (
    search_arxiv,
    search_github_releases,
    fetch_tech_blog_content,
    fetch_ai_news
)
from typing import List, Dict, Any
from autogen import register_function


def register_web_tools(researcher_agent):
    """
    Register web fetching tools with the researcher agent.
    
    Args:
        researcher_agent: The researcher agent to register tools with
    """
    
    # Register ArXiv search
    register_function(
        search_arxiv,
        caller=researcher_agent,
        executor=researcher_agent,
        name="search_arxiv",
        description="""
        Search ArXiv for academic papers using the ArXiv API.
        Use this to find recent papers on AI/ML topics.
        
        Returns list of papers with title, authors, abstract, date, and URLs.
        """
    )
    
    # Register GitHub releases search
    register_function(
        search_github_releases,
        caller=researcher_agent,
        executor=researcher_agent,
        name="search_github_releases",
        description="""
        Search for recent releases in major AI/ML GitHub repositories.
        Use this to find software releases, version updates, and new features.
        
        Returns list of releases with repository, version, date, and changelog.
        """
    )
    
    # Register tech blog fetching
    register_function(
        fetch_tech_blog_content,
        caller=researcher_agent,
        executor=researcher_agent,
        name="fetch_tech_blog_content",
        description="""
        Fetch recent posts from major AI tech blogs (OpenAI, Anthropic, Meta, Google, etc).
        Use this to find announcements, research highlights, and product launches.
        
        Returns list of blog posts with title, summary, date, and URL.
        """
    )
    
    # Register comprehensive AI news fetch
    register_function(
        fetch_ai_news,
        caller=researcher_agent,
        executor=researcher_agent,
        name="fetch_ai_news",
        description="""
        Comprehensive AI news fetching from multiple sources (ArXiv, GitHub, tech blogs).
        Use this for the AI Weekly Report tool to get all news in one call.
        
        Returns dictionary with papers, releases, and blog_posts lists.
        """
    )
    
    print("✅ Web fetching tools registered with researcher agent")


# Convenience function for agent setup
def setup_researcher_with_web_tools(cmbagent_instance):
    """
    Setup researcher agent with web fetching capabilities.
    
    Args:
        cmbagent_instance: CMBAgent instance
    """
    researcher = cmbagent_instance.get_agent_from_name('researcher')
    
    if researcher:
        register_web_tools(researcher)
        return True
    else:
        print("⚠️  Researcher agent not found")
        return False
