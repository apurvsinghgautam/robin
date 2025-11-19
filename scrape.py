import random
import requests
import threading
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

import warnings
warnings.filterwarnings("ignore")

# Define a list of rotating user agents.
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

import time

# Rate limiting: delay between requests (in seconds)
REQUEST_DELAY = 0.5  # 500ms delay between requests for polite scraping

def scrape_single(url_data, delay=REQUEST_DELAY):
    """
    Scrapes a single URL using direct HTTP/HTTPS requests.
    Returns a tuple (url, scraped_text).
    
    Parameters:
      - url_data: dict with 'link' and 'title' keys
      - delay: delay in seconds before making the request (for rate limiting)
    """
    url = url_data['link']
    
    # Rate limiting: wait before making request
    if delay > 0:
        time.sleep(delay)
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            scraped_text = url_data['title'] + " " + soup.get_text().replace('\n', ' ').replace('\r', '').strip()
        else:
            scraped_text = url_data['title']
    except requests.exceptions.RequestException as e:
        # Better error handling for different types of request errors
        scraped_text = url_data['title'] + f" [Error: {type(e).__name__}]"
    except Exception as e:
        scraped_text = url_data['title'] + f" [Error: {str(e)}]"
    
    return url, scraped_text

def scrape_multiple(urls_data, max_workers=5, delay=REQUEST_DELAY):
    """
    Scrapes multiple URLs concurrently using a thread pool with rate limiting.
    
    Parameters:
      - urls_data: list of URLs to scrape (each dict with 'link' and 'title' keys).
      - max_workers: number of concurrent threads for scraping (default: 5).
      - delay: delay in seconds between requests for rate limiting (default: 0.5).
    
    Returns:
      A dictionary mapping each URL to its scraped content.
    """
    results = {}
    max_chars = 1200  # Taking first n chars from the scraped data
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scrape_single, url_data, delay): url_data
            for url_data in urls_data
        }
        for future in as_completed(future_to_url):
            try:
                url, content = future.result()
                if len(content) > max_chars:
                    content = content[:max_chars]
                results[url] = content
            except Exception as e:
                # Handle any exceptions from individual scraping tasks
                url_data = future_to_url[future]
                results[url_data['link']] = url_data['title'] + f" [Scraping Error: {str(e)}]"
    
    return results