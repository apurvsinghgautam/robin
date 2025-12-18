import random
import requests
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import ipaddress

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

def is_valid_url(url):
    """
    Validates a URL to prevent SSRF attacks.
    Rejects URLs pointing to:
    - Private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    - Localhost/loopback addresses (127.0.0.0/8, ::1)
    - Link-local addresses (169.254.0.0/16)
    - Multicast addresses (224.0.0.0/4)
    - Reserved/special addresses
    - URLs without proper schemes
    
    Returns True if URL is safe, False otherwise.
    """
    try:
        # Ensure URL has proper scheme
        if not url or (not url.startswith('http://') and not url.startswith('https://')):
            return False
        
        parsed = urlparse(url)
        
        # Check if URL has a scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return False
        
        # Only allow http and https
        if parsed.scheme not in ('http', 'https'):
            return False
        
        # Extract hostname
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Try to parse as IP address
        try:
            ip = ipaddress.ip_address(hostname)
            # Reject private, loopback, link-local, multicast, and reserved IPs
            if (ip.is_private or ip.is_loopback or ip.is_link_local or 
                ip.is_multicast or ip.is_reserved):
                return False
        except ValueError:
            # Not an IP address, check for localhost
            if hostname.lower() in ('localhost', 'localhost.localdomain'):
                return False
        
        return True
    except Exception:
        return False

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
        "http": "socks5h://127.0.0.1:9050",
        "https": "socks5h://127.0.0.1:9050"
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
        # Validate URL to prevent SSRF attacks (skip for .onion addresses)
        if not use_tor and not is_valid_url(url):
            return url, url_data['title']
        
        if use_tor:
            session = get_tor_session()
            # Increased timeout for Tor latency
            # Use stream=True to prevent loading entire response into memory
            response = session.get(url, headers=headers, timeout=45, stream=True)
        else:
            # Fallback for clearweb if needed, though tool focuses on dark web
            # Use stream=True to prevent loading entire response into memory
            response = requests.get(url, headers=headers, timeout=30, stream=True)

        if response.status_code == 200:
            # Limit response body to 10MB to prevent memory exhaustion
            max_content = 10 * 1024 * 1024
            content_length = response.headers.get('content-length')
            
            if content_length and int(content_length) > max_content:
                return url, url_data['title']
            
            # Read content with size limit
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > max_content:
                    return url, url_data['title']
            
            soup = BeautifulSoup(content, "html.parser")
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
