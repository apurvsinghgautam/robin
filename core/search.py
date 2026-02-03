"""Dark web search engine module with progress reporting."""
import requests
import random
import re
from dataclasses import dataclass, asdict
from typing import Callable, Optional, List, Dict, Any
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import threading

from config import TOR_SOCKS_PROXY

import warnings
warnings.filterwarnings("ignore")

# Search configuration
SEARCH_TIMEOUT = 15  # seconds per request (reduced from 30)
MIN_RESULTS_EARLY_EXIT = 20  # exit early if we have this many results
MAX_FAILURES_PERCENT = 80  # exit if this % of engines fail


@dataclass
class SearchProgress:
    """Progress update from search operation."""
    engine_name: str
    status: str  # 'searching', 'success', 'failed', 'timeout'
    results_count: int
    total_engines: int
    completed_engines: int
    total_results: int
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Callback type for progress updates
ProgressCallback = Optional[Callable[[SearchProgress], None]]


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
]

# Search engines with names for progress reporting
SEARCH_ENGINES: Dict[str, str] = {
    "Ahmia": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}",
    "OnionLand": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}",
    "DarkHunt": "http://darkhuntyla64h75a3re5e2l3367lqn7ltmdzpgmr6b4nbz3q2iaxrid.onion/search?q={query}",
    "Torgle": "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}",
    "Amnesia": "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}",
    "Kaizer": "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}",
    "Anima": "http://anima4ffe27xmakwnseih3ic2y7y3l6e7fucwk4oerdn4odf7k74tbid.onion/search?q={query}",
    "Tornado": "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}",
    "TorNet": "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q={query}",
    "Torland": "http://torlbmqwtudkorme6prgfpmsnile7ug2zm4u3ejpcncxuhpu4k2j4kyd.onion/index.php?a=search&q={query}",
    "FindTor": "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}",
    "Excavator": "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}",
    "Onionway": "http://oniwayzz74cv2puhsgx4dpjwieww4wdphsydqvf5q7eyz4myjvyw26ad.onion/search.php?s={query}",
    "Tor66": "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}",
    "OSS": "http://3fzh7yuupdfyjhwt3ugzqqof6ulbcl27ecev33knxe3u7goi3vfn2qqd.onion/oss/index.php?search={query}",
    "Torgol": "http://torgolnpeouim56dykfob6jh5r2ps2j73enc42s2um4ufob3ny4fcdyd.onion/?q={query}",
    "DeepSearches": "http://searchgf7gdtauh7bhnbyed4ivxqmuoat3nm6zfrg3ymkq6mtnpye3ad.onion/search?q={query}",
}


def get_tor_proxies() -> Dict[str, str]:
    """Get Tor SOCKS proxy configuration."""
    return {
        "http": TOR_SOCKS_PROXY,
        "https": TOR_SOCKS_PROXY
    }


def fetch_search_results(engine_name: str, endpoint: str, query: str) -> tuple[str, str, List[Dict]]:
    """
    Fetch results from a single search engine.

    Returns:
        Tuple of (engine_name, status, results_list)
    """
    url = endpoint.format(query=query)
    headers = {
        "User-Agent": random.choice(USER_AGENTS)
    }
    proxies = get_tor_proxies()

    try:
        response = requests.get(url, headers=headers, proxies=proxies, timeout=SEARCH_TIMEOUT)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = []
            for a in soup.find_all('a'):
                try:
                    href = a.get('href', '')
                    title = a.get_text(strip=True)
                    # Extract .onion URLs
                    onion_links = re.findall(r'https?:\/\/[^\/]*\.onion[^\s"\'<>]*', href)
                    if onion_links:
                        links.append({"title": title, "link": onion_links[0]})
                except Exception:
                    continue
            return (engine_name, "success", links)
        else:
            return (engine_name, "failed", [])
    except requests.exceptions.Timeout:
        return (engine_name, "timeout", [])
    except Exception:
        return (engine_name, "failed", [])


def get_search_results(
    query: str,
    max_workers: int = 5,
    on_progress: ProgressCallback = None,
) -> List[Dict]:
    """
    Search multiple dark web search engines concurrently.

    Args:
        query: Search query (spaces should be preserved, will be URL encoded)
        max_workers: Number of concurrent search workers
        on_progress: Optional callback for progress updates

    Returns:
        List of unique search results with 'title' and 'link' keys
    """
    # URL encode the query
    encoded_query = query.replace(" ", "+")

    total_engines = len(SEARCH_ENGINES)
    results: List[Dict] = []
    seen_links: set = set()
    completed = 0
    failed = 0
    lock = threading.Lock()
    should_stop = threading.Event()

    def report_progress(engine: str, status: str, engine_results: int):
        """Report progress via callback."""
        nonlocal completed, failed

        with lock:
            if status in ("success", "failed", "timeout"):
                completed += 1
            if status in ("failed", "timeout"):
                failed += 1

            total_results = len(results)

            if status == "success":
                message = f"Found {engine_results} results"
            elif status == "timeout":
                message = f"Timed out after {SEARCH_TIMEOUT}s"
            elif status == "failed":
                message = "Connection failed"
            else:
                message = "Searching..."

            if on_progress:
                progress = SearchProgress(
                    engine_name=engine,
                    status=status,
                    results_count=engine_results,
                    total_engines=total_engines,
                    completed_engines=completed,
                    total_results=total_results,
                    message=message,
                )
                on_progress(progress)

    # Report initial state
    if on_progress:
        on_progress(SearchProgress(
            engine_name="",
            status="starting",
            results_count=0,
            total_engines=total_engines,
            completed_engines=0,
            total_results=0,
            message=f"Starting search across {total_engines} dark web engines...",
        ))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all search tasks
        future_to_engine: Dict[Future, str] = {}
        for name, endpoint in SEARCH_ENGINES.items():
            if should_stop.is_set():
                break
            future = executor.submit(fetch_search_results, name, endpoint, encoded_query)
            future_to_engine[future] = name

        # Process results as they complete
        for future in as_completed(future_to_engine):
            if should_stop.is_set():
                break

            engine_name = future_to_engine[future]
            try:
                name, status, engine_results = future.result()

                # Add unique results
                with lock:
                    for res in engine_results:
                        link = res.get("link")
                        if link and link not in seen_links:
                            seen_links.add(link)
                            results.append(res)

                report_progress(name, status, len(engine_results))

                # Check early exit conditions
                with lock:
                    # Exit if we have enough results
                    if len(results) >= MIN_RESULTS_EARLY_EXIT:
                        should_stop.set()
                        if on_progress:
                            on_progress(SearchProgress(
                                engine_name="",
                                status="early_exit",
                                results_count=0,
                                total_engines=total_engines,
                                completed_engines=completed,
                                total_results=len(results),
                                message=f"Found {len(results)} results, stopping early",
                            ))
                        break

                    # Exit if too many failures
                    if completed > 0:
                        failure_rate = (failed / completed) * 100
                        if completed >= 5 and failure_rate >= MAX_FAILURES_PERCENT:
                            should_stop.set()
                            if on_progress:
                                on_progress(SearchProgress(
                                    engine_name="",
                                    status="high_failure_rate",
                                    results_count=0,
                                    total_engines=total_engines,
                                    completed_engines=completed,
                                    total_results=len(results),
                                    message=f"{int(failure_rate)}% of engines failed, stopping",
                                ))
                            break

            except Exception as e:
                report_progress(engine_name, "failed", 0)

    # Final progress report
    if on_progress:
        on_progress(SearchProgress(
            engine_name="",
            status="complete",
            results_count=0,
            total_engines=total_engines,
            completed_engines=completed,
            total_results=len(results),
            message=f"Search complete: {len(results)} unique results from {completed} engines",
        ))

    return results


def get_available_engines() -> List[str]:
    """Return list of available search engine names."""
    return list(SEARCH_ENGINES.keys())
