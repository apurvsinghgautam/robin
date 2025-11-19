import requests
import random
import re
import time
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

import warnings
warnings.filterwarnings("ignore")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54"
]

# Common web search engine endpoints
# Note: These are example endpoints. Some may require API keys or have rate limits.
# For production use, consider using official search APIs (Google Custom Search, Bing Search API, etc.)
SEARCH_ENGINE_ENDPOINTS = [
    "https://www.google.com/search?q={query}",
    "https://www.bing.com/search?q={query}",
    "https://duckduckgo.com/html/?q={query}",
    "https://www.startpage.com/sp/search?query={query}",
    "https://search.yahoo.com/search?p={query}",
]

# Rate limiting for search requests
SEARCH_REQUEST_DELAY = 1.0  # 1 second delay between search requests

def fetch_search_results(endpoint, query, delay=SEARCH_REQUEST_DELAY):
    """
    Fetches search results from a search engine endpoint.
    
    Parameters:
      - endpoint: URL template for the search engine
      - query: search query string
      - delay: delay in seconds before making the request (for rate limiting)
    
    Returns:
      List of dictionaries with 'title' and 'link' keys
    """
    url = endpoint.format(query=query)
    
    # Rate limiting
    if delay > 0:
        time.sleep(delay)
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.google.com/"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = []
            
            # Extract links from search results
            # Different search engines have different HTML structures
            # This is a generic approach that looks for common patterns
            for a in soup.find_all('a', href=True):
                try:
                    href = a['href']
                    title = a.get_text(strip=True)
                    
                    # Filter for valid HTTP/HTTPS URLs (excluding .onion, javascript:, mailto:, etc.)
                    # Match standard web URLs
                    link_match = re.findall(r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*)?(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?', href)
                    
                    if link_match:
                        link_url = link_match[0]
                        # Skip common non-content URLs
                        if not any(skip in link_url.lower() for skip in ['javascript:', 'mailto:', '#', '.onion']):
                            # Clean up Google redirect URLs
                            if 'google.com/url?q=' in link_url:
                                from urllib.parse import urlparse, parse_qs
                                parsed = urlparse(link_url)
                                params = parse_qs(parsed.query)
                                if 'q' in params:
                                    link_url = params['q'][0]
                            
                            if title and len(title) > 3:  # Filter out very short titles
                                links.append({"title": title, "link": link_url})
                except (KeyError, AttributeError, IndexError):
                    continue
            
            return links
        else:
            return []
    except requests.exceptions.RequestException as e:
        # Log error but don't crash - return empty list
        return []
    except Exception as e:
        return []

def get_search_results(refined_query, max_workers=5, delay=SEARCH_REQUEST_DELAY):
    """
    Gets search results from multiple search engines concurrently.
    
    Parameters:
      - refined_query: search query string
      - max_workers: number of concurrent threads (default: 5)
      - delay: delay in seconds between requests (default: 1.0)
    
    Returns:
      List of unique search results (dicts with 'title' and 'link' keys)
    """
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_search_results, endpoint, refined_query, delay)
                   for endpoint in SEARCH_ENGINE_ENDPOINTS]
        for future in as_completed(futures):
            try:
                result_urls = future.result()
                results.extend(result_urls)
            except Exception as e:
                # Continue even if one search engine fails
                continue

    # Deduplicate results based on the link
    seen_links = set()
    unique_results = []
    for res in results:
        link = res.get("link")
        if link and link not in seen_links:
            seen_links.add(link)
            unique_results.append(res)
    
    return unique_results