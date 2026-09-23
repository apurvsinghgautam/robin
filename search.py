import requests
import random, re
from urllib.parse import urlparse, parse_qs, parse_qsl, urlencode, unquote, quote_plus
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Shared with the scraper, so the Tor proxy and body handling are defined once.
from scrape import (TOR_PROXIES, decode_capped, get_over_tor, no_redirect_target,
                    read_capped, scrub_untrusted_text)

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

DEFAULT_SEARCH_ENGINES = [e["url"] for e in SEARCH_ENGINES]

# Connect and read timeouts. A slow engine can need most of 30 seconds to
# connect, and one that has not answered by then will not answer a retry.
ENGINE_TIMEOUT = (30, 40)


def get_tor_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=0,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.proxies = dict(TOR_PROXIES)
    # Environment proxy variables would otherwise win over session.proxies and
    # route the engines (and health.py's pings, which borrow this) around Tor.
    session.trust_env = False
    # Never resolve redirects inside requests: it reads a 3xx body in full to
    # do so. get_over_tor follows them itself, unread (see scrape.py).
    session.get_redirect_target = no_redirect_target
    return session

ONION_URL_RE = re.compile(r'https?://[a-z0-9.-]+\.onion[^\s"\'<>]*', re.IGNORECASE)

# Hosts of the engines Robin queries: a result on one is another engine's page,
# not a target. Matched on host, not path, since /index.php and /search.php are
# also the landing paths of most PHP onion forums and markets.
_ENGINE_HOSTS = {
    (urlparse(e["url"]).hostname or "").lower() for e in SEARCH_ENGINES
}


def _is_onion_host(url):
    """True when the host a request would reach ends in .onion."""
    return (urlparse(url).hostname or "").lower().endswith(".onion")


def _extract_target_onion(href, engine_host):
    """Return the external .onion URL an anchor points at, or None."""
    if not href:
        return None

    parsed = urlparse(href)
    # A redirect wrapper is on the engine's host (or relative to it) and carries
    # the target in a query parameter. parse_qs splits on & and percent-decodes,
    # so the engine's own parameters do not end up glued onto the target.
    if not (parsed.hostname or "") or (parsed.hostname or "").lower() == engine_host:
        for values in parse_qs(parsed.query).values():
            for value in values:
                for nested in ONION_URL_RE.findall(value):
                    host = (urlparse(nested).hostname or "").lower()
                    if _is_onion_host(nested) and host != engine_host:
                        return nested

    candidates = [u for u in (ONION_URL_RE.findall(href)
                              or ONION_URL_RE.findall(unquote(href)))
                  if _is_onion_host(u)]
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
                host = (urlparse(nested).hostname or "").lower()
                if _is_onion_host(nested) and host != engine_host:
                    return nested
    return None


MAX_TITLE_CHARS = 200


def _is_useful_title(title):
    """A title is usable if it has some length and any alphanumeric character."""
    return bool(title) and len(title) >= 4 and any(ch.isalnum() for ch in title)


def _trim_title(title):
    return title if len(title) <= MAX_TITLE_CHARS else title[:MAX_TITLE_CHARS].rstrip() + "..."


# The most of one engine result page Robin will read.
SEARCH_PAGE_MAX_BYTES = 2 * 1024 * 1024


# What one engine did with a query. "empty" is an engine that answered and
# parsed to nothing, which is a real answer and not the same as one that never
# answered at all.
ENGINE_OK = "ok"
ENGINE_EMPTY = "empty"
ENGINE_FAILED = "failed"

_ENGINE_NAMES = {engine["url"]: engine["name"] for engine in SEARCH_ENGINES}


def _engine_name(endpoint):
    return _ENGINE_NAMES.get(endpoint) or (urlparse(endpoint).hostname or str(endpoint))


def _engine_record(endpoint, status, links=None, http_status=None, error=""):
    links = list(links or [])
    return {"engine": _engine_name(endpoint), "status": status, "results": len(links),
            "http_status": http_status, "error": error, "links": links}


def fetch_search_results_detailed(endpoint, query):
    """Query one engine and return a record of what came back.

    Keys: ``engine``, ``status`` (an ENGINE_* constant), ``results`` (a count),
    ``http_status``, ``error`` and ``links``.
    """
    url = endpoint.format(query=query)
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    session = get_tor_session()

    try:
        # Engines are onion services and nothing opts them into clearweb, so a
        # redirect off the onion space is refused (RedirectRefused lands in
        # the except below). An engine that moved to another onion is followed.
        response, _ = get_over_tor(session, url, allow_clearweb=False,
                                   headers=headers, timeout=ENGINE_TIMEOUT)
        try:
            if response.status_code != 200:
                return _engine_record(endpoint, ENGINE_FAILED,
                                      http_status=response.status_code,
                                      error="http {}".format(response.status_code))
            # Capped like every body on a Tor path: an engine is a remote
            # server, and a hostile or compromised one can answer with an
            # endless page. Result pages are tens of kilobytes.
            html = decode_capped(response, read_capped(response, SEARCH_PAGE_MAX_BYTES))
        finally:
            response.close()

        soup = BeautifulSoup(html, "html.parser")
        engine_host = (urlparse(url).hostname or "").lower()
        links = []

        for a in soup.find_all("a"):
            try:
                target = _extract_target_onion(a.get("href"), engine_host)
                if not target:
                    continue
                if (urlparse(target).hostname or "").lower() in _ENGINE_HOSTS:
                    continue
                # Anchor text is the engine's, so it is scrubbed on the way in.
                title = scrub_untrusted_text(a.get_text(strip=True)).strip()
                if not _is_useful_title(title):
                    continue
                links.append({"title": title, "link": target})
            except Exception:
                continue
        status = ENGINE_OK if links else ENGINE_EMPTY
        return _engine_record(endpoint, status, links, http_status=200)
    except Exception as exc:
        return _engine_record(endpoint, ENGINE_FAILED, error=str(exc)[:200])


# Parameters that identify a referrer or campaign rather than the content.
_TRACKING_PARAMS = {
    "utm", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "referrer", "fbclid", "gclid", "yclid", "msclkid", "src",
}


def _dedup_key(link):
    """Identity of a page, keeping the query string minus tracking parameters."""
    parsed = urlparse(link or "")
    kept = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(sorted(kept), doseq=True)
    return "{}://{}{}{}".format(
        parsed.scheme,
        unquote(parsed.hostname or "").lower(),
        unquote(parsed.path).rstrip("/"),
        "?" + query if query else "",
    )


# How many results one onion host may contribute.
MAX_RESULTS_PER_HOST = 3


def _result_host(link):
    try:
        return unquote(urlparse(link or "").hostname or "").lower()
    except Exception:
        return ""


# Child sexual abuse material: never listed, filtered or scraped. Only
# unambiguous patterns, so an adult or leak title is not dropped with them.
_ABUSE_MATERIAL = re.compile(
    r"child\W{0,3}(?:porn|sex|rape|nud)"
    r"|(?:rape|porn|sex)\W{0,3}child"
    r"|\bpedo(?:phil\w*|s)?\b"
    r"|\bpthc\b|\bjailbait\b|\bpreteens?\b|\blolitas?\b|\bhurtcore\b"
    r"|\bkidflix|\bonly\W{0,3}kids"
    r"|\bkid(?:s|dy|die)?\W{0,3}(?:porn|sex|nud)"
    r"|\bunderage\W{0,3}(?:porn|sex|nud|girls?|boys?)"
    r"|\bcp\W{0,3}(?:porn|videos?|links?|archive|collection)\b"
    r"|\bcsam\b",
    re.IGNORECASE)


def is_abuse_material(result) -> bool:
    """True when a result's title or link names child sexual abuse material."""
    link = result.get("link") or ""
    text = "{} {} {}".format(result.get("title") or "", link, unquote(link))
    return bool(_ABUSE_MATERIAL.search(text))


TOR_BOOTSTRAP_MARK = "Bootstrapped 100%"


def tor_bootstrapped(log_path) -> bool:
    """True when Tor's log says it can build circuits, or there is no log to read.

    The SOCKS port opens about twenty seconds earlier, and a search started in
    that window loses engines.
    """
    if not log_path:
        return True
    try:
        with open(log_path, "r", errors="replace") as handle:
            return TOR_BOOTSTRAP_MARK in handle.read()
    except OSError:
        return True


def engines_unreachable(stats) -> bool:
    """True when no engine replied at all and at least one failed: a search
    that did not run, not an empty dark web."""
    return (stats.get("engines_answered", 0) + stats.get("engines_empty", 0) == 0
            and stats.get("engines_failed", 0) > 0)


def _deduplicate(results):
    """Collapse tracker-tagged and percent-encoded variants of one page."""
    seen_links = set()
    unique_results = []
    for res in results:
        link = res.get("link") or ""
        try:
            clean_link = _dedup_key(link)
        except Exception:
            clean_link = link.rstrip("/")
        if clean_link not in seen_links:
            seen_links.add(clean_link)
            unique_results.append(res)
    return unique_results


def _cap_per_host(results, per_host_limit):
    """Keep at most `per_host_limit` results per host, in the order given.

    Order is what makes this safe to apply after dedup: each host keeps the
    first hits an engine returned for it, which are the ones it ranked highest.
    """
    if not per_host_limit or per_host_limit <= 0:
        return list(results)
    kept = []
    counts = {}
    for res in results:
        host = _result_host(res.get("link"))
        if counts.get(host, 0) >= per_host_limit:
            continue
        counts[host] = counts.get(host, 0) + 1
        kept.append(res)
    return kept


def encode_query(refined_query):
    """Make a refined query safe to drop into an engine's URL template.

    Every engine takes its terms as a `+`-separated query parameter.
    """
    # quote_plus escapes a literal + (which would decode to a space) and an &
    # (which would split the engine's URL), so identifiers arrive verbatim.
    return quote_plus(refined_query or "")


def get_search_results_detailed(refined_query, max_workers=5, per_host_limit=None):
    """The results, plus what the engines did to produce them.

    Returns ``{"results": [...], "stats": {...}}``. The stats separate a thin
    search from a broken one and count what each filter removed.
    """
    limit = MAX_RESULTS_PER_HOST if per_host_limit is None else per_host_limit
    query = encode_query(refined_query)
    order = {endpoint: index for index, endpoint in enumerate(DEFAULT_SEARCH_ENGINES)}
    records = []
    raw = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_search_results_detailed, endpoint, query): endpoint
                   for endpoint in DEFAULT_SEARCH_ENGINES}
        for future in as_completed(futures):
            endpoint = futures[future]
            try:
                record = future.result()
            except Exception as exc:  # A worker that died is a failed engine.
                record = _engine_record(endpoint, ENGINE_FAILED, error=str(exc)[:200])
            records.append((order.get(endpoint, len(order)), record))
            raw.extend(record["links"])

    clean = [dict(result, title=_trim_title(result["title"]))
             for result in raw if not is_abuse_material(result)]
    deduped = _deduplicate(clean)
    kept = _cap_per_host(deduped, limit)
    engines = [record for _, record in sorted(records, key=lambda pair: pair[0])]

    def count(status):
        return sum(1 for record in engines if record["status"] == status)

    return {
        "results": kept,
        "stats": {
            "engines_queried": len(DEFAULT_SEARCH_ENGINES),
            "engines_answered": count(ENGINE_OK),
            "engines_empty": count(ENGINE_EMPTY),
            "engines_failed": count(ENGINE_FAILED),
            "results_raw": len(raw),
            "results_dropped_abuse": len(raw) - len(clean),
            "results_after_dedup": len(deduped),
            "results_kept": len(kept),
            "distinct_hosts": len({_result_host(r.get("link")) for r in kept}),
            "per_host_limit": limit,
            # Per engine, in the order SEARCH_ENGINES lists them. The links
            # themselves are in "results", not repeated here.
            "engines": [{k: v for k, v in record.items() if k != "links"}
                        for record in engines],
        },
    }
