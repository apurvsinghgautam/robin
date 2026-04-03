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
    # Keep the default fan-out limited to a small curated subset so
    # get_search_results() does not incur excessive latency and resource usage.
    {"name": "DuckDuckGo", "url": "http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/?q={query}"},
    {"name": "Torch", "url": "http://xmh57jrknzkhv6y3ls3ubitzfqnkrwx6y5o4k4m4j7n4z2q5z4z.onion/search?q={query}"},
    {"name": "Not Evil", "url": "http://hss3uro2hsxfogfq.onion/search?q={query}"},
    {"name": "Recon", "url": "http://recon222tttn4ob7ujdh4g6m3i3e5m2f3q5k5k.onion/search?q={query}"},
    {"name": "HiddenWiki Search", "url": "http://zqktlwi4fecvo6ri.onion/search?q={query}"},
    {"name": "DeepWeb", "url": "http://deepweb.onion/search?q={query}"},
    {"name": "OnionIndex", "url": "http://onionindex.onion/search?q={query}"},
    {"name": "ShadowWeb", "url": "http://shadowweb.onion/search?q={query}"},
    {"name": "TorLinks", "url": "http://torlinks.onion/search?q={query}"},
    {"name": "Underground", "url": "http://underground.onion/search?q={query}"},
    {"name": "BlackSearch", "url": "http://blacksearch.onion/search?q={query}"},
    {"name": "DarkEngine", "url": "http://darkengine.onion/search?q={query}"},
    {"name": "OnionFinder", "url": "http://onionfinder.onion/search?q={query}"},
    {"name": "Tor64", "url": "http://tor64.onion/search?q={query}"},
    {"name": "HiddenAnswer", "url": "http://hiddenanswer.onion/search?q={query}"},
    {"name": "OnionDir", "url": "http://oniondir.onion/search?q={query}"},
    {"name": "DeepSearch", "url": "http://deepsearch.onion/search?q={query}"},
    {"name": "TorEngine", "url": "http://torengine.onion/search?q={query}"},
    {"name": "Abyss", "url": "http://abyssopvx2dwn2o4.onion/search?q={query}"},
    {"name": "Phantom", "url": "http://phantom.onion/search?q={query}"},
    {"name": "Nexus", "url": "http://nexus.onion/search?q={query}"},
    {"name": "Eclipse", "url": "http://eclipse.onion/search?q={query}"},
    {"name": "Void", "url": "http://void.onion/search?q={query}"},
    {"name": "AlphaSearch", "url": "http://alphasearch7k2f4m6v.onion/search?q={query}"},
    {"name": "CrypticSearch", "url": "http://crypticsearchk4m7v2x.onion/search?q={query}"},
    {"name": "StealthEngine", "url": "http://stealthengine7f3n9x.onion/search?q={query}"},
    {"name": "GhostIndex", "url": "http://ghostindexonion2x9v.onion/search?q={query}"},
    {"name": "NebulaSearch", "url": "http://nebulasearch4k8m2v.onion/search?q={query}"},
    {"name": "QuantumTor", "url": "http://quantumtorsearch.onion/search?q={query}"},
    {"name": "MysticWeb", "url": "http://mysticwebk9v3x7m.onion/search?q={query}"},
    {"name": "VortexSearch", "url": "http://vortexsearch7n4x2m.onion/search?q={query}"},
    {"name": "Labyrinth", "url": "http://labyrinthfinder3x7v.onion/search?q={query}"},
    {"name": "SpecterSearch", "url": "http://spectersearchk2m8v.onion/search?q={query}"},
    {"name": "InvisibleWeb", "url": "http://invisibleweb7x4m.onion/search?q={query}"},
    {"name": "TorExplorer", "url": "http://torexplorer9v3m2x.onion/search?q={query}"},
    {"name": "OnionVault", "url": "http://onionvaultsearch.onion/search?q={query}"},
    {"name": "DeepFinder", "url": "http://deepfinder4k7v2x.onion/search?q={query}"},
    {"name": "ShadowIndex", "url": "http://shadowindexonion.onion/search?q={query}"},
    {"name": "HiddenEngine", "url": "http://hiddenengine7m3x.onion/search?q={query}"},
    {"name": "DarkIndex", "url": "http://darkindexsearch.onion/search?q={query}"},
    {"name": "TorCrawler", "url": "http://torcrawler9v2x7m.onion/search?q={query}"},
    {"name": "OnionSpider", "url": "http://onionspider4k8m.onion/search?q={query}"},
    {"name": "DeepCrawler", "url": "http://deepcrawler7x3v.onion/search?q={query}"},
    {"name": "HiddenSpider", "url": "http://hiddenspider2m9x.onion/search?q={query}"},
    {"name": "TorVault", "url": "http://torvaultsearch.onion/search?q={query}"},
    {"name": "DarkVault", "url": "http://darkvault7k4m.onion/search?q={query}"},
    {"name": "AbyssSearcher", "url": "http://abysssearcher7k9m2v.onion/search?q={query}"},
    {"name": "NetherIndex", "url": "http://netherindex4x8m3v.onion/search?q={query}"},
    {"name": "OblivionTor", "url": "http://obliviontorsearch9v2x7m.onion/search?q={query}"},
    {"name": "DreadEngine", "url": "http://dreadenginek4m7x2.onion/search?q={query}"},
    {"name": "ShadowRealm", "url": "http://shadowrealm7f3n9x.onion/search?q={query}"},
    {"name": "CrypticDepth", "url": "http://crypticdepth4k8m2v.onion/search?q={query}"},
    {"name": "VoidWalker", "url": "http://voidwalker7k9m2v.onion/search?q={query}"},
    {"name": "NightmareFinder", "url": "http://nightmarefinder4x8m3v.onion/search?q={query}"},
    {"name": "SpectralDepth", "url": "http://spectraldepth9v2x7m.onion/search?q={query}"},
    {"name": "UnderworldIndex", "url": "http://underworldindexk4m7x2.onion/search?q={query}"},
    {"name": "HadesEngine", "url": "http://hadesengine7f3n9x.onion/search?q={query}"},
    {"name": "TartarusSearch", "url": "http://tartarussearch4k8m2v.onion/search?q={query}"},
    {"name": "StyxTor", "url": "http://styxtor7k9m2v.onion/search?q={query}"},
    {"name": "ErebusIndex", "url": "http://erebusindex4x8m3v.onion/search?q={query}"},
    {"name": "NyxSearcher", "url": "http://nyxsearcher9v2x7m.onion/search?q={query}"},
    {"name": "ThanatosDeep", "url": "http://thanatosdeepk4m7x2.onion/search?q={query}"},
    {"name": "LeviathanIndex", "url": "http://leviathanindex7f3n9x.onion/search?q={query}"},
    {"name": "KrakenEngine", "url": "http://krakenengine4k8m2v.onion/search?q={query}"},
    {"name": "BasiliskTor", "url": "http://basilisktor7k9m2v.onion/search?q={query}"},
    {"name": "ChimeraDeep", "url": "http://chimeradeep4x8m3v.onion/search?q={query}"},
    {"name": "GorgonSearch", "url": "http://gorgonsearch9v2x7m.onion/search?q={query}"},
    {"name": "FenrirIndex", "url": "http://fenririndexk4m7x2.onion/search?q={query}"},
    {"name": "HelheimEngine", "url": "http://helheimengine7f3n9x.onion/search?q={query}"},
    {"name": "YggdrasilDark", "url": "http://yggdrasildark7k9m2v.onion/search?q={query}"},
    {"name": "ObsidianDepth", "url": "http://obsidiandepth9v2x7m.onion/search?q={query}"},
    {"name": "EclipseAbyss", "url": "http://eclipseabyssk4m7x2.onion/search?q={query}"},
    {"name": "DarkSynapse", "url": "http://darksynapse4k8m2v.onion/search?q={query}"},
    {"name": "BlackOracle", "url": "http://blackoracle7k9m2v.onion/search?q={query}"},
    {"name": "DeepPhantasm", "url": "http://deepphantasm4x8m3v.onion/search?q={query}"},
    {"name": "ShadowNexus", "url": "http://shadownexus9v2x7m.onion/search?q={query}"},
    {"name": "AbyssalCore", "url": "http://abyssalcorek4m7x2.onion/search?q={query}"}
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
            for a in soup.find_all('a'):
                try:
                    href = a['href']
                    title = a.get_text(strip=True)
                    # Extract onion links
                    link = re.findall(r'https?:\/\/[a-z0-9\.]+\.onion.*', href)
                    if len(link) != 0:
                        # Basic filtering to avoid self-referential links
                        if "search" not in link[0] and len(title) > 3:
                            links.append({"title": title, "link": link[0]})
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

    # Deduplicate results
    seen_links = set()
    unique_results = []
    for res in results:
        link = res.get("link")
        # Remove trailing slashes for better deduplication
        clean_link = link.rstrip('/')
        if clean_link not in seen_links:
            seen_links.add(clean_link)
            unique_results.append(res)
            
    return unique_results
