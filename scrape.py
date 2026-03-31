import random
import requests
import threading
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

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

MAX_DOWNLOAD_BYTES = 1_000_000
MAX_EXTRACTED_TEXT_CHARS = 50_000
MAX_RETURN_CHARS = 2_000
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
_thread_local = threading.local()
_logger = logging.getLogger(__name__)


def _normalize_url_data(url_data):
    if not isinstance(url_data, dict):
        return "", "Untitled"
    url = str(url_data.get("link") or "").strip()
    title = str(url_data.get("title") or "Untitled").strip() or "Untitled"
    return url, title


def _build_session(use_tor=False):
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    if use_tor:
        session.proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050"
        }

    return session


def _get_session(use_tor=False):
    key = "tor_session" if use_tor else "direct_session"
    if not hasattr(_thread_local, key):
        setattr(_thread_local, key, _build_session(use_tor=use_tor))
    return getattr(_thread_local, key)

def get_tor_session():
    """
    Creates a requests Session with Tor SOCKS proxy and automatic retries.
    """
    return _build_session(use_tor=True)

def scrape_single(url_data, rotate=False, rotate_interval=5, control_port=9051, control_password=None):
    """
    Scrapes a single URL using a robust Tor session.
    Returns a tuple (url, scraped_text).
    """
    url, title = _normalize_url_data(url_data)
    if not url:
        return "", title

    parsed_url = urlparse(url)
    if parsed_url.scheme not in ("http", "https"):
        return url, title

    use_tor = (urlparse(url).hostname or "").lower().endswith(".onion")
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    }
    
    response = None
    try:
        session = _get_session(use_tor=use_tor)
        if use_tor:
            # Increased timeout for Tor latency
            response = session.get(url, headers=headers, timeout=(10, 45), stream=True)
        else:
            # Fallback for clearweb if needed, though tool focuses on dark web
            response = session.get(url, headers=headers, timeout=(5, 25), stream=True)

        if response.status_code == 200:
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and not any(t in content_type for t in ALLOWED_CONTENT_TYPES):
                return url, title

            chunks = []
            bytes_read = 0
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                bytes_read += len(chunk)
                if bytes_read > MAX_DOWNLOAD_BYTES:
                    break
                chunks.append(chunk)

            html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")

            soup = BeautifulSoup(html, "html.parser")
            # Clean up text: remove scripts/styles
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=' ')
            # Normalize whitespace
            text = ' '.join(text.split())
            text = text[:MAX_EXTRACTED_TEXT_CHARS]
            scraped_text = f"{title} - {text}" if text else title
        else:
            scraped_text = title
    except (requests.RequestException, ValueError) as exc:
        # Return title only on failure, so we don't lose the reference
        _logger.debug("Failed to scrape url=%s: %s", url, exc)
        scraped_text = title
    finally:
        if response is not None:
            response.close()
    
    return url, scraped_text

def scrape_multiple(urls_data, max_workers=5):
    """
    Scrapes multiple URLs concurrently using a thread pool.
    """
    results = {}
    max_workers = max(1, min(int(max_workers), 16))
    if not isinstance(urls_data, (list, tuple)):
        return results

    # Deduplicate links to reduce unnecessary requests under real workloads.
    unique_urls_data = []
    seen_links = set()
    for item in urls_data:
        url, title = _normalize_url_data(item)
        if not url or url in seen_links:
            continue
        seen_links.add(url)
        unique_urls_data.append({"link": url, "title": title})
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scrape_single, url_data): url_data
            for url_data in unique_urls_data
        }
        for future in as_completed(future_to_url):
            try:
                url, content = future.result()
                if not url:
                    continue
                if len(content) > MAX_RETURN_CHARS:
                    suffix = "...(truncated)"
                    if len(suffix) >= MAX_RETURN_CHARS:
                        # Fallback: ensure we never exceed MAX_RETURN_CHARS even if suffix is long
                        content = suffix[:MAX_RETURN_CHARS]
                    else:
                        available = MAX_RETURN_CHARS - len(suffix)
                        content = content[:available] + suffix
                results[url] = content
            except Exception as exc:
                _logger.debug("Worker failed to scrape a URL: %s", exc)
                continue
                
    return results
