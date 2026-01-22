"""
Keywords extraction module for CMBAgent.

This module provides keyword extraction functions using various taxonomies:
- UNESCO taxonomy
- AAAI keywords
- AAS (American Astronomical Society) keywords
"""

from cmbagent.keywords.keyword_finder import (
    get_keywords,
    get_keywords_from_string,
    get_keywords_from_aaai,
    get_aas_keywords,
)

__all__ = [
    "get_keywords",
    "get_keywords_from_string",
    "get_keywords_from_aaai",
    "get_aas_keywords",
]
