"""
Scraping module for extracting content from dark web pages via Tor.
"""

import logging
import random
from typing import Dict, List, Tuple, Any

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException, Timeout, ConnectionError

from constants import (
    USER_AGENTS,
    SCRAPE_TIMEOUT,
    CLEARWEB_TIMEOUT,
    MAX_SCRAPE_CHARS,
    DEFAULT_MAX_WORKERS,
    RETRY_TOTAL,
    RETRY_READ,
    RETRY_CONNECT,
    RETRY_BACKOFF_FACTOR,
    RETRY_STATUS_FORCELIST,
    get_tor_proxies,
)

logger = logging.getLogger(__name__)


def get_tor_session() -> requests.Session:
    """
    Creates a requests Session with Tor SOCKS proxy and automatic retries.

    Returns:
        Configured requests.Session with Tor proxy and retry logic
    """
    session = requests.Session()
    retry = Retry(
        total=RETRY_TOTAL,
        read=RETRY_READ,
        connect=RETRY_CONNECT,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_FORCELIST
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.proxies = get_tor_proxies()
    return session


def scrape_single(url_data: Dict[str, str]) -> Tuple[str, str]:
    """
    Scrapes a single URL using a robust Tor session.

    Args:
        url_data: Dictionary with 'link' and 'title' keys

    Returns:
        Tuple of (url, scraped_text)
    """
    url = url_data['link']
    title = url_data.get('title', '')
    use_tor = ".onion" in url

    headers = {"User-Agent": random.choice(USER_AGENTS)}

    try:
        if use_tor:
            session = get_tor_session()
            response = session.get(url, headers=headers, timeout=SCRAPE_TIMEOUT)
        else:
            response = requests.get(url, headers=headers, timeout=CLEARWEB_TIMEOUT)

        if response.status_code != 200:
            logger.debug(f"Non-200 status code {response.status_code} from {url}")
            return url, title

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove scripts and styles
        for script in soup(["script", "style"]):
            script.extract()

        text = soup.get_text(separator=' ')
        # Normalize whitespace
        text = ' '.join(text.split())
        scraped_text = f"{title} - {text}"

        return url, scraped_text

    except Timeout:
        logger.debug(f"Timeout scraping {url}")
        return url, title
    except ConnectionError:
        logger.debug(f"Connection error scraping {url}")
        return url, title
    except RequestException as e:
        logger.debug(f"Request error scraping {url}: {e}")
        return url, title
    except Exception as e:
        logger.warning(f"Unexpected error scraping {url}: {e}")
        return url, title


def scrape_multiple(
    urls_data: List[Dict[str, str]],
    max_workers: int = DEFAULT_MAX_WORKERS
) -> Dict[str, str]:
    """
    Scrapes multiple URLs concurrently using a thread pool.

    Args:
        urls_data: List of dictionaries with 'link' and 'title' keys
        max_workers: Maximum number of concurrent threads

    Returns:
        Dictionary mapping URLs to their scraped content
    """
    results: Dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scrape_single, url_data): url_data
            for url_data in urls_data
        }

        for future in as_completed(future_to_url):
            url_data = future_to_url[future]
            try:
                url, content = future.result()

                if len(content) > MAX_SCRAPE_CHARS:
                    content = content[:MAX_SCRAPE_CHARS] + "... (truncated)"

                results[url] = content
            except Exception as e:
                logger.warning(f"Error processing result for {url_data.get('link', 'unknown')}: {e}")
                continue

    logger.info(f"Successfully scraped {len(results)} out of {len(urls_data)} URLs")
    return results
