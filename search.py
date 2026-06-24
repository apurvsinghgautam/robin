import requests
import random, re
from urllib.parse import urlunparse, unquote
import json
import os
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

def fetch_search_results(endpoint, query):
    url = endpoint.format(query=query)
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    session = get_tor_session()
    
    try:
        response = session.get(url, headers=headers, timeout=40)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = []
            # Generic parsing for standard search engine layouts
            from urllib.parse import urlparse, parse_qs
            endpoint_parsed = urlparse(url)
            endpoint_host = (endpoint_parsed.hostname or "").lower()

            for a in soup.find_all('a'):
                try:
                    href = a['href']
                    title = a.get_text(strip=True)
                    # Extract onion links
                    link = re.findall(r'https?:\/\/[a-z0-9\.-]+\.onion[^\s"\'<>]*', href)
                    if len(link) != 0:
                        matched_url = link[0]
                        matched_parsed = urlparse(matched_url)
                        matched_host = (matched_parsed.hostname or "").lower()

                        # If the link is a redirect link pointing to the search engine itself,
                        # attempt to extract the target onion link from the query parameters.
                        if matched_host == endpoint_host:
                            qs = parse_qs(matched_parsed.query)
                            found_nested = False
                            for vals in qs.values():
                                for val in vals:
                                    if ".onion" in val:
                                        nested_links = re.findall(r'https?:\/\/[a-z0-9\.-]+\.onion[^\s"\'<>]*', val)
                                        if nested_links:
                                            matched_url = nested_links[0]
                                            matched_parsed = urlparse(matched_url)
                                            matched_host = (matched_parsed.hostname or "").lower()
                                            found_nested = True
                                            break
                                if found_nested:
                                    break

                        matched_path = matched_parsed.path.rstrip('/')
                        is_self_ref = matched_host == endpoint_host
                        is_utility = matched_path in (
                            "/about", "/contact", "/directory", "/last-added", 
                            "/advertising", "/advertise", "/webmaster", "/search",
                            ""
                        )

                        # Filter out self-referential utility pages
                        if is_self_ref and is_utility:
                            continue

                        # Only drop URLs whose path is exactly /search or /search/
                        # (not URLs that merely contain the word "search" anywhere)
                        is_search_page = matched_parsed.path.rstrip('/') == '/search'

                        # Title quality check: must be 4+ chars and contain at least one alphanumeric,
                        # and must not be excessively long (scraped paragraph noise)
                        has_alphanum = bool(re.search(r'[a-zA-Z0-9]', title))
                        title_ok = len(title) >= 4 and has_alphanum and len(title) <= 200

                        if not is_search_page and title_ok:
                            links.append({"title": title, "link": matched_url})
                except:
                    continue
            return links
        else:
            return []
    except:
        return []

def get_search_results(refined_query, max_workers=5):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_search_results, endpoint, refined_query)
                   for endpoint in DEFAULT_SEARCH_ENGINES]
        for future in as_completed(futures):
            result_urls = future.result()
            results.extend(result_urls)

    # Deduplicate results — normalize to scheme+host+path only (strip query params,
    # fragments, and URL-encoding) so that tracker-tagged variants of the same page
    # are treated as one result.
    from urllib.parse import urlparse as _urlparse
    seen_links = set()
    unique_results = []
    for res in results:
        link = res.get("link") or ""
        try:
            _p = _urlparse(link)
            # Decode percent-encoding and lowercase the host for consistent comparison
            norm_host = unquote(_p.hostname or "").lower()
            norm_path = unquote(_p.path.rstrip('/'))
            clean_link = f"{_p.scheme}://{norm_host}{norm_path}"
        except Exception:
            clean_link = link.rstrip('/')
        if clean_link not in seen_links:
            seen_links.add(clean_link)
            unique_results.append(res)
            
    return unique_results
