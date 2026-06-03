import requests
import random, re
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
    # A
    {"name": "Ahmia", "url": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}", "active": True},
    {"name": "Amnesia", "url": "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}", "active": True},
    {"name": "Anima", "url": "http://anima4ffe27xmakwnseih3ic2y7y3l6e7fucwk4oerdn4odf7k74tbid.onion/search?q={query}", "active": True},
    # C
    {"name": "Candle", "url": "http://candle7qhz7l7lz4pbvbxn6zq7k3dh22m4nbf4dh24ibcqjcreuivfmyd.onion/search?q={query}", "active": True},
    # D
    {"name": "Darknet", "url": "http://darknetsearchvs3p4g7t5g4c7p5e6n5o4f6q7r7s3t7d.onion/index.php?q={query}", "active": True},
    {"name": "The Deep Searches", "url": "http://searchgf7gdtauh7bhnbyed4ivxqmuoat3nm6zfrg3ymkq6mtnpye3ad.onion/search?q={query}", "active": True},
    # E
    {"name": "Excavator", "url": "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}", "active": True},
    # F
    {"name": "Find Tor", "url": "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}", "active": True},
    # G
    {"name": "Grams", "url": "http://gramsx6dckypuod7g5od6e7w2b5v3nzpqn2t6vemx5k4w5n6gzy52fqd.onion/?q={query}", "active": True},
    # H
    {"name": "Haystack", "url": "http://haystackb7cvk7nxjxn53646r5qw4ilxc53yqicvr7pxuetbnw47j5frad.onion/?q={query}", "active": True},
    # K
    {"name": "Kaizer", "url": "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}", "active": True},
    # N
    {"name": "Not Evil", "url": "http://notevildqn7jmpu4lsk52uqjoacu3c3aqe2csjl76a3xcc7mst7yd7yd.onion/?q={query}", "active": True},
    # O
    {"name": "OnionLand", "url": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}", "active": True},
    {"name": "Onionway", "url": "http://oniwayzz74cv2puhsgx4dpjwieww4wdphsydqvf5q7eyz4myjvyw26ad.onion/search.php?s={query}", "active": True},
    {"name": "OSS", "url": "http://3fzh7yuupdfyjhwt3ugzqqof6ulbcl27ecev33knxe3u7goi3vfn2qqd.onion/oss/index.php?search={query}", "active": True},
    # S
    {"name": "Searx Onion", "url": "http://searxspider2wvg6ssnds33pa2dn57z5r4e4jvxu3f7rrjahqxryxyd.onion/search?q={query}", "active": True},
    # T
    {"name": "The Tor Project", "url": "http://torprojectxn2w4hjvp7ad6p4gre7g6pvteojvmxc43erbsona72ijpc7od.onion/?q={query}", "active": True},
    {"name": "Torch", "url": "http://torchrt4u7d4hgmqj7ywxzapxnpjhq7x5jjlbz4zpqzgm7qh5y2yj7yd.onion/search?query={query}", "active": True},
    {"name": "Tor66", "url": "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}", "active": True},
    {"name": "Torgle", "url": "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}", "active": True},
    {"name": "Torgol", "url": "http://torgolnpeouim56dykfob6jh5r2ps2j73enc42s2um4ufob3ny4fcdyd.onion/?q={query}", "active": True},
    {"name": "Torland", "url": "http://torlbmqwtudkorme6prgfpmsnile7ug2zm4u3ejpcncxuhpu4k2j4kyd.onion/index.php?a=search&q={query}", "active": True},
    {"name": "TorNet", "url": "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q={query}", "active": True},
    {"name": "Tornado", "url": "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}", "active": True},
    # V
    {"name": "Vindex", "url": "http://vindexjpg7agosl4.onion/search?q={query}", "active": True},
    # Z
    {"name": "ZerSearch", "url": "http://zersearch2sjxtcms5g4ijhkpyonfx7o6xbupxvgxbjjx7z7xvscvw4yd.onion/?q={query}", "active": True},
]

# Backward-compatible flat list used by existing search logic
DEFAULT_SEARCH_ENGINES = [e["url"] for e in SEARCH_ENGINES if e.get("active", True)]

# Advanced search configuration
SEARCH_CONFIG = {
    "timeout": 40,
    "max_workers": 5,
    "retry_attempts": 3,
    "filter_duplicates": True,
    "min_title_length": 3,
}

def get_active_engines():
    """Get only active search engines."""
    return [e for e in SEARCH_ENGINES if e.get("active", True)]

def get_engine_by_name(name):
    """Get search engine by name."""
    for engine in SEARCH_ENGINES:
        if engine["name"].lower() == name.lower():
            return engine
    return None

def list_all_engines():
    """List all available search engines with their status."""
    result = []
    for engine in sorted(SEARCH_ENGINES, key=lambda x: x["name"]):
        status = "✓ Active" if engine.get("active", True) else "✗ Inactive"
        result.append({"name": engine["name"], "status": status})
    return result

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

def fetch_search_results(endpoint, query, timeout=None):
    """Fetch results from a single search engine with advanced error handling."""
    if timeout is None:
        timeout = SEARCH_CONFIG["timeout"]
    
    url = endpoint.format(query=query)
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    session = get_tor_session()
    
    try:
        response = session.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = []
            # Generic parsing for standard search engine layouts
            for a in soup.find_all('a'):
                try:
                    href = a.get('href', '')
                    title = a.get_text(strip=True)
                    
                    if not href or not title:
                        continue
                    
                    # Extract onion links
                    link_match = re.findall(r'https?:\/\/[a-z0-9\.]+\.onion[^\s"]*', href)
                    if link_match:
                        link = link_match[0]
                        # Advanced filtering
                        title_len = len(title)
                        if (title_len > SEARCH_CONFIG["min_title_length"] and 
                            "search" not in link.lower() and
                            link not in [l["link"] for l in links]):  # Local dedup
                            links.append({
                                "title": title, 
                                "link": link,
                                "source": endpoint
                            })
                except Exception as e:
                    continue
            return links
        else:
            return []
    except requests.Timeout:
        print(f"Timeout from {endpoint}")
        return []
    except Exception as e:
        print(f"Error fetching from {endpoint}: {str(e)}")
        return []

def get_search_results(refined_query, max_workers=None, filter_duplicates=True, timeout=None, stats=False):
    """Advanced search results retrieval with statistics and filtering."""
    if max_workers is None:
        max_workers = SEARCH_CONFIG["max_workers"]
    if timeout is None:
        timeout = SEARCH_CONFIG["timeout"]
    
    results = []
    stats_data = {
        "total_engines": len(DEFAULT_SEARCH_ENGINES),
        "successful_engines": 0,
        "failed_engines": 0,
        "total_results": 0,
        "duplicate_count": 0,
        "final_results": 0,
    }
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_search_results, endpoint, refined_query, timeout): endpoint 
                   for endpoint in DEFAULT_SEARCH_ENGINES}
        
        for future in as_completed(futures):
            try:
                result_urls = future.result()
                if result_urls:
                    stats_data["successful_engines"] += 1
                    results.extend(result_urls)
                    stats_data["total_results"] += len(result_urls)
                else:
                    stats_data["failed_engines"] += 1
            except Exception as e:
                stats_data["failed_engines"] += 1

    # Advanced deduplication
    if filter_duplicates:
        seen_links = set()
        unique_results = []
        
        for res in results:
            link = res.get("link", "")
            # Remove trailing slashes and normalize for better deduplication
            clean_link = link.rstrip('/').lower()
            
            if clean_link not in seen_links:
                seen_links.add(clean_link)
                unique_results.append(res)
            else:
                stats_data["duplicate_count"] += 1
        
        stats_data["final_results"] = len(unique_results)
        
        if stats:
            return unique_results, stats_data
        return unique_results
    else:
        stats_data["final_results"] = len(results)
        if stats:
            return results, stats_data
        return results
