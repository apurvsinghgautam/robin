"""
Search module for querying dark web search engines via Tor.
"""

import logging
import random
import re
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import RequestException, Timeout, ConnectionError

from constants import (
    USER_AGENTS,
    SEARCH_ENGINE_ENDPOINTS,
    SEARCH_TIMEOUT,
    DEFAULT_MAX_WORKERS,
    get_tor_proxies,
)

logger = logging.getLogger(__name__)


def fetch_search_results(endpoint: str, query: str) -> List[Dict[str, str]]:
    """
    Fetch search results from a single dark web search engine endpoint.

    Args:
        endpoint: The search engine URL template with {query} placeholder
        query: The search query to execute

    Returns:
        List of dictionaries containing 'title' and 'link' keys
    """
    url = endpoint.format(query=query)
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    proxies = get_tor_proxies()

    try:
        response = requests.get(
            url,
            headers=headers,
            proxies=proxies,
            timeout=SEARCH_TIMEOUT
        )

        if response.status_code != 200:
            logger.debug(f"Non-200 status code {response.status_code} from {endpoint}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        links = []

        for a in soup.find_all('a'):
            try:
                href = a.get('href', '')
                title = a.get_text(strip=True)
                link_matches = re.findall(r'https?://[^/]*\.onion.*', href)
                if link_matches:
                    links.append({"title": title, "link": link_matches[0]})
            except (AttributeError, TypeError) as e:
                logger.debug(f"Error parsing link element: {e}")
                continue

        return links

    except Timeout:
        logger.debug(f"Timeout fetching results from {endpoint}")
        return []
    except ConnectionError:
        logger.debug(f"Connection error fetching results from {endpoint}")
        return []
    except RequestException as e:
        logger.debug(f"Request error fetching results from {endpoint}: {e}")
        return []


def get_search_results(
    refined_query: str,
    max_workers: int = DEFAULT_MAX_WORKERS
) -> List[Dict[str, str]]:
    """
    Query all configured dark web search engines concurrently.

    Args:
        refined_query: The refined search query
        max_workers: Maximum number of concurrent threads

    Returns:
        Deduplicated list of search results
    """
    results: List[Dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_search_results, endpoint, refined_query)
            for endpoint in SEARCH_ENGINE_ENDPOINTS
        ]

        for future in as_completed(futures):
            try:
                result_urls = future.result()
                results.extend(result_urls)
            except Exception as e:
                logger.warning(f"Unexpected error in search worker: {e}")
                continue

    # Deduplicate results based on the link
    seen_links: set = set()
    unique_results: List[Dict[str, str]] = []

    for res in results:
        link = res.get("link")
        if link and link not in seen_links:
            seen_links.add(link)
            unique_results.append(res)

    logger.info(f"Found {len(unique_results)} unique results from {len(SEARCH_ENGINE_ENDPOINTS)} search engines")
    return unique_results
