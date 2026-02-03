import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import TOR_SOCKS_PROXY

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

def get_tor_session():
    """
    Creates a requests Session with Tor SOCKS proxy and automatic retries.
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    session.proxies = {
        "http": TOR_SOCKS_PROXY,
        "https": TOR_SOCKS_PROXY
    }
    return session

def scrape_single(url_data, rotate=False, rotate_interval=5, control_port=9051, control_password=None):
    """
    Scrapes a single URL using a robust Tor session.
    Returns a tuple (url, scraped_text).
    """
    url = url_data['link']
    use_tor = ".onion" in url
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS)
    }
    
    try:
        if use_tor:
            session = get_tor_session()
            # Increased timeout for Tor latency
            response = session.get(url, headers=headers, timeout=45)
        else:
            # Fallback for clearweb if needed, though tool focuses on dark web
            response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Clean up text: remove scripts/styles
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=' ')
            # Normalize whitespace
            text = ' '.join(text.split())
            scraped_text = f"{url_data['title']} - {text}"
        else:
            scraped_text = url_data['title']
    except Exception as e:
        # Return title only on failure, so we don't lose the reference
        scraped_text = url_data['title']
    
    return url, scraped_text

def scrape_multiple(urls_data, max_workers=5):
    """
    Scrapes multiple URLs concurrently using a thread pool.
    """
    results = {}
    max_chars = 2000  # Increased limit slightly for better context
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scrape_single, url_data): url_data
            for url_data in urls_data
        }
        for future in as_completed(future_to_url):
            try:
                url, content = future.result()
                if len(content) > max_chars:
                    content = content[:max_chars] + "...(truncated)"
                results[url] = content
            except Exception:
                continue
                
    return results
