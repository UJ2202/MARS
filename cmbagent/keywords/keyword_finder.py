"""
Keyword extraction functions for CMBAgent.

This module provides functions to extract keywords from text using various taxonomies:
- UNESCO taxonomy (hierarchical, 3 levels)
- AAAI keywords
- AAS (American Astronomical Society) keywords
"""

import logging
import os
import json
import time
import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

from cmbagent.utils import (
    work_dir_default,
    get_api_keys_from_env,
    AAS_keywords_string,
    unesco_taxonomy_path,
    aaai_keywords_path,
)
from cmbagent.keywords_utils import UnescoKeywords, AaaiKeywords


def get_keywords(
    input_text: str,
    n_keywords: int = 5,
    work_dir: str = work_dir_default,
    api_keys: Optional[Dict[str, str]] = None,
    kw_type: str = 'unesco'
) -> List[str]:
    """
    Get keywords from input text using specified taxonomy.

    Args:
        input_text: Text to extract keywords from
        n_keywords: Number of keywords to extract. Defaults to 5.
        work_dir: Working directory for outputs
        api_keys: API keys dictionary. If None, reads from environment.
        kw_type: Keyword taxonomy type ('unesco', 'aas', or 'aaai')

    Returns:
        List of extracted keywords
    """
    if api_keys is None:
        api_keys = get_api_keys_from_env()

    if kw_type == 'aas':
        return get_aas_keywords(input_text, n_keywords, work_dir, api_keys)
    elif kw_type == 'unesco':
        aggregated_keywords = []

        ukw = UnescoKeywords(unesco_taxonomy_path)
        keywords_string = ', '.join(ukw.get_unesco_level1_names())
        n_keywords_level1 = ukw.n_keywords_level1
        domains = get_keywords_from_string(input_text, keywords_string, n_keywords_level1, work_dir, api_keys)

        logger.debug("domains: %s", domains)
        domains.append('MATHEMATICS') if 'MATHEMATICS' not in domains else None
        aggregated_keywords.extend(domains)

        for domain in domains:
            logger.debug("inside domain: %s", domain)
            if '&' in domain:
                domain = domain.replace('&', '\\&')
            keywords_string = ', '.join(ukw.get_unesco_level2_names(domain))
            n_keywords_level2 = ukw.n_keywords_level2
            sub_fields = get_keywords_from_string(input_text, keywords_string, n_keywords_level2, work_dir, api_keys)

            logger.debug("sub_fields: %s", sub_fields)
            aggregated_keywords.extend(sub_fields)

            for sub_field in sub_fields:
                logger.debug("inside sub_field: %s", sub_field)
                keywords_string = ', '.join(ukw.get_unesco_level3_names(sub_field))
                n_keywords_level3 = ukw.n_keywords_level3
                specific_areas = get_keywords_from_string(input_text, keywords_string, n_keywords_level3, work_dir, api_keys)
                logger.debug("specific_areas: %s", specific_areas)
                aggregated_keywords.extend(specific_areas)

        aggregated_keywords = list(set(aggregated_keywords))
        keywords_string = ', '.join(aggregated_keywords)
        keywords = get_keywords_from_string(input_text, keywords_string, n_keywords, work_dir, api_keys)

        logger.debug("keywords in unesco: %s", keywords)
        return keywords
    elif kw_type == 'aaai':
        return get_keywords_from_aaai(input_text, n_keywords, work_dir, api_keys)
    else:
        raise ValueError(f"Unknown keyword type: {kw_type}. Must be 'unesco', 'aas', or 'aaai'.")


def get_keywords_from_aaai(
    input_text: str,
    n_keywords: int = 6,
    work_dir: str = work_dir_default,
    api_keys: Optional[Dict[str, str]] = None
) -> List[str]:
    """
    Extract keywords using AAAI taxonomy.

    Args:
        input_text: Text to extract keywords from
        n_keywords: Number of keywords to extract
        work_dir: Working directory for outputs
        api_keys: API keys dictionary. If None, reads from environment.

    Returns:
        List of AAAI keywords
    """
    # Late import to avoid circular dependency
    from cmbagent.cmbagent import CMBAgent

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    start_time = time.time()
    cmbagent = CMBAgent(cache_seed=42, work_dir=work_dir, api_keys=api_keys)
    end_time = time.time()
    initialization_time = end_time - start_time

    PROMPT = f"""
    {input_text}
    """
    start_time = time.time()

    aaai_keywords = AaaiKeywords(aaai_keywords_path)
    keywords_string = aaai_keywords.aaai_keywords_string

    cmbagent.solve(
        task="Find the relevant keywords in the provided list",
        max_rounds=2,
        initial_agent='aaai_keywords_finder',
        mode="one_shot",
        shared_context={
            'text_input_for_AAS_keyword_finder': PROMPT,
            'AAS_keywords_string': keywords_string,
            'N_AAS_keywords': n_keywords,
        }
    )
    end_time = time.time()
    execution_time = end_time - start_time

    if not hasattr(cmbagent, 'groupchat'):
        Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
        cmbagent.groupchat = Dummy()

    cmbagent.display_cost()

    # Save timing report as JSON
    timing_report = {
        'initialization_time': initialization_time,
        'execution_time': execution_time,
        'total_time': initialization_time + execution_time
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timing_path = os.path.join(work_dir, f"timing_report_{timestamp}.json")
    with open(timing_path, 'w') as f:
        json.dump(timing_report, f, indent=2)

    # Grab last user message with role "user"
    user_msg = next(
        (msg["content"] for msg in cmbagent.chat_result.chat_history if msg.get("role") == "user"),
        ""
    )

    # Extract lines starting with a dash
    keywords = [line.lstrip("-").strip() for line in user_msg.splitlines() if line.startswith("-")]
    return keywords


def get_keywords_from_string(
    input_text: str,
    keywords_string: str,
    n_keywords: int,
    work_dir: str,
    api_keys: Optional[Dict[str, str]] = None
) -> List[str]:
    """
    Extract keywords from a predefined string of keywords.

    Args:
        input_text: Text to extract keywords from
        keywords_string: Comma-separated string of candidate keywords
        n_keywords: Number of keywords to extract
        work_dir: Working directory for outputs
        api_keys: API keys dictionary. If None, reads from environment.

    Returns:
        List of extracted keywords
    """
    # Late import to avoid circular dependency
    from cmbagent.cmbagent import CMBAgent

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    start_time = time.time()
    cmbagent = CMBAgent(cache_seed=42, work_dir=work_dir, api_keys=api_keys)
    end_time = time.time()
    initialization_time = end_time - start_time

    PROMPT = f"""
    {input_text}
    """
    start_time = time.time()

    cmbagent.solve(
        task="Find the relevant keywords in the provided list",
        max_rounds=2,
        initial_agent='list_keywords_finder',
        mode="one_shot",
        shared_context={
            'text_input_for_AAS_keyword_finder': PROMPT,
            'AAS_keywords_string': keywords_string,
            'N_AAS_keywords': n_keywords,
        }
    )
    end_time = time.time()
    execution_time = end_time - start_time

    if not hasattr(cmbagent, 'groupchat'):
        Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
        cmbagent.groupchat = Dummy()

    cmbagent.display_cost()

    # Save timing report as JSON
    timing_report = {
        'initialization_time': initialization_time,
        'execution_time': execution_time,
        'total_time': initialization_time + execution_time
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timing_path = os.path.join(work_dir, f"timing_report_{timestamp}.json")
    with open(timing_path, 'w') as f:
        json.dump(timing_report, f, indent=2)

    # Grab last user message with role "user"
    user_msg = next(
        (msg["content"] for msg in cmbagent.chat_result.chat_history if msg.get("role") == "user"),
        ""
    )

    # Extract lines starting with a dash
    keywords = [line.lstrip("-").strip() for line in user_msg.splitlines() if line.startswith("-")]
    return keywords


def get_aas_keywords(
    input_text: str,
    n_keywords: int = 5,
    work_dir: str = work_dir_default,
    api_keys: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Get AAS (American Astronomical Society) keywords from input text.

    Args:
        input_text: Text to extract keywords from
        n_keywords: Number of keywords to extract. Defaults to 5.
        work_dir: Working directory for outputs
        api_keys: API keys dictionary. If None, reads from environment.

    Returns:
        Dictionary of AAS keywords with URLs
    """
    # Late import to avoid circular dependency
    from cmbagent.cmbagent import CMBAgent

    if api_keys is None:
        api_keys = get_api_keys_from_env()

    start_time = time.time()
    cmbagent = CMBAgent(cache_seed=42, work_dir=work_dir, api_keys=api_keys)
    end_time = time.time()
    initialization_time = end_time - start_time

    PROMPT = f"""
    {input_text}
    """
    start_time = time.time()
    cmbagent.solve(
        task="Find the relevant AAS keywords",
        max_rounds=50,
        initial_agent='aas_keyword_finder',
        mode="one_shot",
        shared_context={
            'text_input_for_AAS_keyword_finder': PROMPT,
            'AAS_keywords_string': AAS_keywords_string,
            'N_AAS_keywords': n_keywords,
        }
    )
    end_time = time.time()
    execution_time = end_time - start_time
    aas_keywords = cmbagent.final_context['aas_keywords']

    if not hasattr(cmbagent, 'groupchat'):
        Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
        cmbagent.groupchat = Dummy()

    cmbagent.display_cost()

    # Save timing report as JSON
    timing_report = {
        'initialization_time': initialization_time,
        'execution_time': execution_time,
        'total_time': initialization_time + execution_time
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timing_path = os.path.join(work_dir, f"timing_report_{timestamp}.json")
    with open(timing_path, 'w') as f:
        json.dump(timing_report, f, indent=2)

    logger.debug("aas_keywords: %s", aas_keywords)

    return aas_keywords
