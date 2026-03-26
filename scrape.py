import random
import requests
import ipaddress
import socket
import logging
from urllib.parse import urlparse, urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import ALLOW_CLEARWEB_FALLBACK

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

_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
}

logger = logging.getLogger(__name__)


def _is_private_or_local_ip(value):
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return None

    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _is_safe_url(url, allow_clearweb=False, resolve_hostname=True):
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    if parsed.scheme not in {"http", "https"}:
        return False
    if not hostname:
        return False

    if hostname.endswith(".onion"):
        return True

    if not allow_clearweb:
        return False

    if hostname in _BLOCKED_HOSTNAMES:
        return False

    ip_check = _is_private_or_local_ip(hostname)
    if ip_check is True:
        return False
    if ip_check is False:
        return True

    if not resolve_hostname:
        # Avoid local DNS lookups when traffic is already routed through Tor.
        # In this mode, treat non-onion hostnames as unsafe.
        return False

    try:
        resolved = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except Exception:
        return False

    for item in resolved:
        resolved_ip = item[4][0]
        if _is_private_or_local_ip(resolved_ip):
            return False

    return True


def _safe_fetch_with_redirect_policy(
    session,
    url,
    headers,
    timeout,
    allow_clearweb=False,
    max_redirects=3,
    resolve_hostname=True,
):
    if not _is_safe_url(url, allow_clearweb=allow_clearweb, resolve_hostname=resolve_hostname):
        raise ValueError(f"Blocked URL by security policy: {url}")

    current = url
    for _ in range(max_redirects + 1):
        response = session.get(current, headers=headers, timeout=timeout, allow_redirects=False)
        if response.status_code in {301, 302, 303, 307, 308} and response.headers.get("Location"):
            next_url = urljoin(current, response.headers["Location"])
            if not _is_safe_url(next_url, allow_clearweb=allow_clearweb, resolve_hostname=resolve_hostname):
                response.close()
                raise ValueError(f"Blocked redirect by security policy: {next_url}")
            response.close()
            current = next_url
            continue
        return response

    raise ValueError("Blocked URL due to excessive redirects")


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


def get_clearweb_session():
    """
    Creates a requests Session with retries and no proxy for explicit clearweb fallback.
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
    return session


def scrape_single(url_data, rotate=False, rotate_interval=5, control_port=9051, control_password=None):
    """
    Scrapes a single URL using a robust Tor session.
    Returns a tuple (url, scraped_text).
    """
    url = url_data['link']
    hostname = (urlparse(url).hostname or "").lower()
    use_tor = hostname.endswith(".onion")
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS)
    }
    
    response = None
    try:
        if use_tor:
            session = get_tor_session()
            timeout = 45
            resolve_hostname = False
        else:
            session = get_clearweb_session()
            timeout = 30
            resolve_hostname = True

        response = _safe_fetch_with_redirect_policy(
            session,
            url,
            headers=headers,
            timeout=timeout,
            allow_clearweb=ALLOW_CLEARWEB_FALLBACK,
            max_redirects=3,
            resolve_hostname=resolve_hostname,
        )

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
    except ValueError as e:
        logger.warning("Blocked URL by policy during scrape '%s': %s", url, e)
        scraped_text = url_data['title']
    except Exception as e:
        # Return title only on failure, so we don't lose the reference
        logger.debug("Failed scraping URL '%s': %s", url, e)
        scraped_text = url_data['title']
    finally:
        if response is not None:
            response.close()
    
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
