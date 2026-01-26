"""
Web fetching utilities for IT Tools.

Provides functions for:
- ArXiv search and retrieval
- GitHub releases via API
- Tech blog content fetching
- RSS feed parsing
- HTML content extraction
"""

import os
import re
import json
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import quote


def search_arxiv(
    query: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 50,
    categories: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Search ArXiv for papers using the ArXiv API.
    
    Args:
        query: Search query (e.g., "large language models")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        max_results: Maximum number of results to return
        categories: List of ArXiv categories (e.g., ['cs.AI', 'cs.CL'])
    
    Returns:
        List of paper dictionaries with title, authors, abstract, date, url
    """
    base_url = "http://export.arxiv.org/api/query?"
    
    # Build search query
    search_query = query
    if categories:
        cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
        search_query = f"({query}) AND ({cat_query})"
    
    # Add date range if specified
    if start_date and end_date:
        date_query = f"submittedDate:[{start_date.replace('-', '')}* TO {end_date.replace('-', '')}*]"
        search_query = f"{search_query} AND {date_query}"
    
    params = {
        'search_query': search_query,
        'start': 0,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }
    
    url = base_url + "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Parse Atom XML response
        papers = parse_arxiv_response(response.text)
        return papers
        
    except Exception as e:
        print(f"Error searching ArXiv: {str(e)}")
        return []


def parse_arxiv_response(xml_text: str) -> List[Dict[str, Any]]:
    """Parse ArXiv API XML response."""
    import xml.etree.ElementTree as ET
    
    papers = []
    root = ET.fromstring(xml_text)
    
    # Namespace
    ns = {'atom': 'http://www.w3.org/2005/Atom',
          'arxiv': 'http://arxiv.org/schemas/atom'}
    
    for entry in root.findall('atom:entry', ns):
        try:
            # Extract paper info
            title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
            summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
            published = entry.find('atom:published', ns).text[:10]  # YYYY-MM-DD
            
            # Authors
            authors = [author.find('atom:name', ns).text 
                      for author in entry.findall('atom:author', ns)]
            
            # ArXiv ID and URL
            arxiv_id = entry.find('atom:id', ns).text.split('/abs/')[-1]
            url = f"https://arxiv.org/abs/{arxiv_id}"
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            
            # Categories
            categories = [cat.get('term') 
                         for cat in entry.findall('atom:category', ns)]
            
            papers.append({
                'title': title,
                'authors': authors,
                'abstract': summary,
                'date': published,
                'arxiv_id': arxiv_id,
                'url': url,
                'pdf_url': pdf_url,
                'categories': categories
            })
            
        except Exception as e:
            print(f"Error parsing entry: {str(e)}")
            continue
    
    return papers


def search_github_releases(
    topics: List[str] = None,
    start_date: Optional[str] = None,
    language: str = "python",
    min_stars: int = 1000
) -> List[Dict[str, Any]]:
    """
    Search GitHub for recent releases in AI/ML repositories.
    
    Args:
        topics: List of topics to filter by (e.g., ['machine-learning', 'deep-learning'])
        start_date: Only releases after this date (YYYY-MM-DD)
        language: Programming language filter
        min_stars: Minimum stars for repository
    
    Returns:
        List of release dictionaries
    """
    # Popular AI/ML repositories to check
    popular_repos = [
        'pytorch/pytorch',
        'tensorflow/tensorflow',
        'huggingface/transformers',
        'openai/gpt-4',
        'facebookresearch/llama',
        'microsoft/DeepSpeed',
        'google-research/bert',
        'Significant-Gravitas/AutoGPT',
        'langchain-ai/langchain',
        'anthropics/anthropic-sdk-python'
    ]
    
    releases = []
    
    for repo in popular_repos:
        try:
            url = f"https://api.github.com/repos/{repo}/releases"
            headers = {}
            
            # Add GitHub token if available
            github_token = os.getenv('GITHUB_TOKEN')
            if github_token:
                headers['Authorization'] = f'token {github_token}'
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                repo_releases = response.json()
                
                for release in repo_releases[:5]:  # Get latest 5 releases
                    published_at = release.get('published_at', '')[:10]
                    
                    # Filter by date if specified
                    if start_date and published_at < start_date:
                        continue
                    
                    releases.append({
                        'repository': repo,
                        'title': release.get('name') or release.get('tag_name'),
                        'tag': release.get('tag_name'),
                        'date': published_at,
                        'url': release.get('html_url'),
                        'body': release.get('body', '')[:500],  # First 500 chars
                        'author': release.get('author', {}).get('login', 'Unknown')
                    })
            
        except Exception as e:
            print(f"Error fetching releases for {repo}: {str(e)}")
            continue
    
    # Sort by date
    releases.sort(key=lambda x: x['date'], reverse=True)
    
    return releases


def fetch_tech_blog_content(
    blog_sources: List[str] = None,
    start_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch recent content from AI tech blogs.
    
    Note: This is a simplified version. For production, you'd want to:
    - Use RSS feeds
    - Implement proper scraping with BeautifulSoup
    - Add caching
    - Handle rate limiting
    
    Args:
        blog_sources: List of blog sources to fetch from
        start_date: Only content after this date
    
    Returns:
        List of blog post dictionaries
    """
    # RSS feed URLs for major AI blogs
    rss_feeds = {
        'OpenAI': 'https://openai.com/blog/rss/',
        'Anthropic': 'https://www.anthropic.com/news/rss',
        'Google AI': 'https://blog.google/technology/ai/rss/',
        'Meta AI': 'https://ai.meta.com/blog/rss/',
        'HuggingFace': 'https://huggingface.co/blog/feed.xml',
        'DeepMind': 'https://deepmind.google/blog/rss.xml'
    }
    
    if blog_sources:
        rss_feeds = {k: v for k, v in rss_feeds.items() if k in blog_sources}
    
    posts = []
    
    for source, feed_url in rss_feeds.items():
        try:
            response = requests.get(feed_url, timeout=15)
            if response.status_code == 200:
                # Parse RSS feed
                feed_posts = parse_rss_feed(response.text, source)
                
                # Filter by date if specified
                if start_date:
                    feed_posts = [p for p in feed_posts 
                                 if p.get('date', '') >= start_date]
                
                posts.extend(feed_posts)
                
        except Exception as e:
            print(f"Error fetching {source}: {str(e)}")
            continue
    
    # Sort by date
    posts.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    return posts


def parse_rss_feed(xml_text: str, source: str) -> List[Dict[str, Any]]:
    """Parse RSS/Atom feed XML."""
    import xml.etree.ElementTree as ET
    
    posts = []
    
    try:
        root = ET.fromstring(xml_text)
        
        # Try Atom format first
        ns_atom = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('.//atom:entry', ns_atom)
        
        if entries:
            # Atom format
            for entry in entries:
                try:
                    title = entry.find('atom:title', ns_atom).text
                    link_elem = entry.find('atom:link', ns_atom)
                    link = link_elem.get('href') if link_elem is not None else ''
                    
                    summary_elem = entry.find('atom:summary', ns_atom)
                    summary = summary_elem.text if summary_elem is not None else ''
                    
                    published_elem = entry.find('atom:published', ns_atom)
                    if published_elem is None:
                        published_elem = entry.find('atom:updated', ns_atom)
                    published = published_elem.text[:10] if published_elem is not None else ''
                    
                    posts.append({
                        'source': source,
                        'title': title,
                        'url': link,
                        'summary': summary[:300],
                        'date': published
                    })
                except Exception:
                    continue
        else:
            # Try RSS 2.0 format
            items = root.findall('.//item')
            
            for item in items:
                try:
                    title = item.find('title').text
                    link = item.find('link').text
                    description_elem = item.find('description')
                    description = description_elem.text if description_elem is not None else ''
                    
                    pubdate_elem = item.find('pubDate')
                    pubdate = parse_rss_date(pubdate_elem.text) if pubdate_elem is not None else ''
                    
                    posts.append({
                        'source': source,
                        'title': title,
                        'url': link,
                        'summary': description[:300],
                        'date': pubdate
                    })
                except Exception:
                    continue
                    
    except Exception as e:
        print(f"Error parsing RSS feed: {str(e)}")
    
    return posts


def parse_rss_date(date_str: str) -> str:
    """Convert RSS date to YYYY-MM-DD format."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return ''


def fetch_ai_news(
    date_from: str,
    date_to: str,
    topics: List[str] = None,
    sources: List[str] = None
) -> Dict[str, Any]:
    """
    Comprehensive AI news fetching combining multiple sources.
    
    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        topics: Topics to filter (llm, cv, rl, etc.)
        sources: Sources to use (arxiv, github, blogs)
    
    Returns:
        Dictionary containing papers, releases, and blog posts
    """
    results = {
        'date_range': f"{date_from} to {date_to}",
        'papers': [],
        'releases': [],
        'blog_posts': []
    }
    
    # Map topics to ArXiv categories
    topic_categories = {
        'llm': ['cs.CL', 'cs.AI', 'cs.LG'],
        'cv': ['cs.CV'],
        'rl': ['cs.LG', 'cs.AI'],
        'robotics': ['cs.RO'],
        'multimodal': ['cs.CV', 'cs.CL', 'cs.AI'],
        'infra': ['cs.DC', 'cs.PF'],
        'safety': ['cs.AI', 'cs.CY']
    }
    
    if not sources:
        sources = ['arxiv', 'github', 'blogs']
    
    # Fetch ArXiv papers
    if 'arxiv' in sources and topics:
        print("Fetching ArXiv papers...")
        categories = []
        for topic in topics:
            categories.extend(topic_categories.get(topic, ['cs.AI']))
        categories = list(set(categories))  # Remove duplicates
        
        # Search for each topic
        for topic in topics:
            query = get_topic_search_query(topic)
            papers = search_arxiv(
                query=query,
                start_date=date_from,
                end_date=date_to,
                max_results=20,
                categories=categories
            )
            results['papers'].extend(papers)
    
    # Fetch GitHub releases
    if 'github' in sources:
        print("Fetching GitHub releases...")
        releases = search_github_releases(
            topics=topics,
            start_date=date_from
        )
        results['releases'].extend(releases)
    
    # Fetch tech blogs
    if 'blogs' in sources:
        print("Fetching tech blog content...")
        posts = fetch_tech_blog_content(
            start_date=date_from
        )
        results['blog_posts'].extend(posts)
    
    return results


def get_topic_search_query(topic: str) -> str:
    """Get appropriate search query for topic."""
    queries = {
        'llm': 'large language model OR LLM OR GPT OR transformer',
        'cv': 'computer vision OR image recognition OR object detection',
        'rl': 'reinforcement learning OR RL OR deep RL',
        'robotics': 'robotics OR autonomous OR robot learning',
        'multimodal': 'multimodal OR vision language OR VLM',
        'infra': 'machine learning infrastructure OR MLOps OR training',
        'safety': 'AI safety OR alignment OR interpretability'
    }
    return queries.get(topic, topic)


# Example usage
if __name__ == '__main__':
    # Test ArXiv search
    print("Testing ArXiv search...")
    papers = search_arxiv(
        query="large language model",
        start_date="2026-01-19",
        end_date="2026-01-26",
        max_results=5
    )
    print(f"Found {len(papers)} papers")
    if papers:
        print(f"First paper: {papers[0]['title']}")
    
    # Test GitHub releases
    print("\nTesting GitHub releases...")
    releases = search_github_releases(start_date="2026-01-01")
    print(f"Found {len(releases)} releases")
    if releases:
        print(f"Latest: {releases[0]['repository']} - {releases[0]['title']}")
    
    # Test comprehensive fetch
    print("\nTesting comprehensive fetch...")
    results = fetch_ai_news(
        date_from="2026-01-19",
        date_to="2026-01-26",
        topics=['llm', 'cv'],
        sources=['arxiv', 'github']
    )
    print(f"Papers: {len(results['papers'])}")
    print(f"Releases: {len(results['releases'])}")
    print(f"Blog posts: {len(results['blog_posts'])}")
