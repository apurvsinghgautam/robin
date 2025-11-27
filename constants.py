"""
Centralized constants and configuration for Robin.
This module eliminates code duplication and provides a single source of truth.
"""

import os
from typing import Dict, List

# =============================================================================
# TOR CONFIGURATION
# =============================================================================
TOR_PROXY_HOST = os.getenv("TOR_PROXY_HOST", "127.0.0.1")
TOR_PROXY_PORT = int(os.getenv("TOR_PROXY_PORT", "9050"))
TOR_CONTROL_PORT = int(os.getenv("TOR_CONTROL_PORT", "9051"))

def get_tor_proxies() -> Dict[str, str]:
    """Returns the Tor SOCKS5 proxy configuration."""
    proxy_url = f"socks5h://{TOR_PROXY_HOST}:{TOR_PROXY_PORT}"
    return {
        "http": proxy_url,
        "https": proxy_url
    }

# =============================================================================
# HTTP CONFIGURATION
# =============================================================================
SEARCH_TIMEOUT = int(os.getenv("ROBIN_SEARCH_TIMEOUT", "30"))
SCRAPE_TIMEOUT = int(os.getenv("ROBIN_SCRAPE_TIMEOUT", "45"))
CLEARWEB_TIMEOUT = int(os.getenv("ROBIN_CLEARWEB_TIMEOUT", "30"))

# Maximum characters to keep from scraped content
MAX_SCRAPE_CHARS = int(os.getenv("ROBIN_MAX_SCRAPE_CHARS", "2000"))

# Default number of concurrent workers
DEFAULT_MAX_WORKERS = int(os.getenv("ROBIN_MAX_WORKERS", "5"))

# Maximum search results to keep after LLM filtering
MAX_FILTERED_RESULTS = 20

# =============================================================================
# USER AGENTS
# =============================================================================
USER_AGENTS: List[str] = [
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

# =============================================================================
# DARK WEB SEARCH ENGINE ENDPOINTS
# =============================================================================
SEARCH_ENGINE_ENDPOINTS: List[str] = [
    "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}",  # Ahmia
    "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}",  # OnionLand
    "http://darkhuntyla64h75a3re5e2l3367lqn7ltmdzpgmr6b4nbz3q2iaxrid.onion/search?q={query}",  # DarkRunt
    "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}",  # Torgle
    "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}",  # Amnesia
    "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}",  # Kaizer
    "http://anima4ffe27xmakwnseih3ic2y7y3l6e7fucwk4oerdn4odf7k74tbid.onion/search?q={query}",  # Anima
    "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}",  # Tornado
    "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q={query}",  # TorNet
    "http://torlbmqwtudkorme6prgfpmsnile7ug2zm4u3ejpcncxuhpu4k2j4kyd.onion/index.php?a=search&q={query}",  # Torland
    "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}",  # Find Tor
    "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}",  # Excavator
    "http://oniwayzz74cv2puhsgx4dpjwieww4wdphsydqvf5q7eyz4myjvyw26ad.onion/search.php?s={query}",  # Onionway
    "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}",  # Tor66
    "http://3fzh7yuupdfyjhwt3ugzqqof6ulbcl27ecev33knxe3u7goi3vfn2qqd.onion/oss/index.php?search={query}",  # OSS
]

# =============================================================================
# RETRY CONFIGURATION
# =============================================================================
RETRY_TOTAL = 3
RETRY_READ = 3
RETRY_CONNECT = 3
RETRY_BACKOFF_FACTOR = 0.3
RETRY_STATUS_FORCELIST = [500, 502, 503, 504]

# =============================================================================
# INPUT VALIDATION
# =============================================================================
MAX_QUERY_LENGTH = 5000
MIN_QUERY_LENGTH = 1
