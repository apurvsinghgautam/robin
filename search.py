import requests
import random, re
import json
import os
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

SEARCH_ENGINES = [
    {"name": "Ahmia", "url": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}"},
    {"name": "OnionLand", "url": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}"},
    {"name": "Torgle", "url": "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}"},
    {"name": "Amnesia", "url": "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}"},
    {"name": "Kaizer", "url": "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}"},
    {"name": "Anima", "url": "http://anima4ffe27xmakwnseih3ic2y7y3l6e7fucwk4oerdn4odf7k74tbid.onion/search?q={query}"},
    {"name": "Tornado", "url": "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}"},
    {"name": "TorNet", "url": "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q={query}"},
    {"name": "Torland", "url": "http://torlbmqwtudkorme6prgfpmsnile7ug2zm4u3ejpcncxuhpu4k2j4kyd.onion/index.php?a=search&q={query}"},
    {"name": "Find Tor", "url": "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}"},
    {"name": "Excavator", "url": "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}"},
    {"name": "Onionway", "url": "http://oniwayzz74cv2puhsgx4dpjwieww4wdphsydqvf5q7eyz4myjvyw26ad.onion/search.php?s={query}"},
    {"name": "Tor66", "url": "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}"},
    {"name": "OSS", "url": "http://3fzh7yuupdfyjhwt3ugzqqof6ulbcl27ecev33knxe3u7goi3vfn2qqd.onion/oss/index.php?search={query}"},
    {"name": "Torgol", "url": "http://torgolnpeouim56dykfob6jh5r2ps2j73enc42s2um4ufob3ny4fcdyd.onion/?q={query}"},
    {"name": "The Deep Searches", "url": "http://searchgf7gdtauh7bhnbyed4ivxqmuoat3nm6zfrg3ymkq6mtnpye3ad.onion/search?q={query}"},
]

# Backward-compatible flat list used by existing search logic
DEFAULT_SEARCH_ENGINES = [e["url"] for e in SEARCH_ENGINES]

def get_tor_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.5,
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

ONION_URL_RE = re.compile(r'https?://[a-z0-9.-]+\.onion[^\s"\'<>]*', re.IGNORECASE)

# Paths that are the engine's own result page rather than a discovered target.
_SEARCH_PATHS = {"/search", "/index.php", "/search.php", "/oss/index.php"}


def _extract_target_onion(href, engine_host):
    """Return the external .onion URL an anchor points at, or None.

    Two things make this less trivial than a regex match:

    * Engines wrap results in their own redirect endpoint
      (``/search/redirect?redirect_url=http://target.onion``), so the raw href
      is on the engine's host even though it leads somewhere else.
    * Engine pages are full of navigation, category, FAQ and footer links on
      the engine's own host. Those are not search results and must not reach
      the scraper — see issue #146, where reports were being written about a
      search engine's own menu.
    """
    if not href:
        return None

    candidates = ONION_URL_RE.findall(href) or ONION_URL_RE.findall(unquote(href))
    if not candidates:
        return None

    for url in candidates:
        if (urlparse(url).hostname or "").lower() != engine_host:
            return url

    # Everything matched points back at the engine: unwrap a redirect target
    # from the query string if there is one, otherwise it is internal navigation.
    for values in parse_qs(urlparse(candidates[0]).query).values():
        for value in values:
            for nested in ONION_URL_RE.findall(unquote(value)):
                if (urlparse(nested).hostname or "").lower() != engine_host:
                    return nested
    return None


def _is_useful_title(title):
    return bool(title) and 4 <= len(title) <= 200 and bool(re.search(r"[a-zA-Z0-9]", title))


def fetch_search_results(endpoint, query):
    url = endpoint.format(query=query)
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    session = get_tor_session()

    try:
        response = session.get(url, headers=headers, timeout=40)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        engine_host = (urlparse(url).hostname or "").lower()
        links = []

        for a in soup.find_all("a"):
            try:
                target = _extract_target_onion(a.get("href"), engine_host)
                if not target:
                    continue
                # Drop links to another engine's result page (path match only, so
                # a target URL that merely contains the word "search" survives).
                if urlparse(target).path.rstrip("/") in _SEARCH_PATHS:
                    continue
                title = a.get_text(strip=True)
                if not _is_useful_title(title):
                    continue
                links.append({"title": title, "link": target})
            except Exception:
                continue
        return links
    except Exception:
        return []


def get_search_results(refined_query, max_workers=5):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_search_results, endpoint, refined_query)
                   for endpoint in DEFAULT_SEARCH_ENGINES]
        for future in as_completed(futures):
            result_urls = future.result()
            results.extend(result_urls)

    # Deduplicate on scheme + host + path so that tracker-tagged and
    # percent-encoded variants of the same page collapse into one result.
    seen_links = set()
    unique_results = []
    for res in results:
        link = res.get("link") or ""
        try:
            parsed = urlparse(link)
            clean_link = "{}://{}{}".format(
                parsed.scheme,
                unquote(parsed.hostname or "").lower(),
                unquote(parsed.path).rstrip("/"),
            )
        except Exception:
            clean_link = link.rstrip("/")
        if clean_link not in seen_links:
            seen_links.add(clean_link)
            unique_results.append(res)

    return unique_results
