"""The onion-only policy on every hop, capped and unread bodies, and what a page yields."""
import re
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import requests
from requests.utils import get_encoding_from_headers

import health
import pipeline
import scrape
import search
from tests.stubs import (CapturingChatModel, FakeResponse, LocalServer, RecordingSession,
                         big_route, quiet_logger, record_sessions, search_outcome, unproxied)

OK, REFUSED = scrape.STATUS_OK, scrape.STATUS_REFUSED_NOT_ONION
BLOCKED, ERROR = scrape.STATUS_BLOCKED, scrape.STATUS_ERROR
TOR = "socks5h://127.0.0.1:9050"
ONION = "http://targetabcdefghij234567.onion/thread"
ONION_A = "http://aaaaaaaaaaaaaaaa.onion/start"
ONION_B = "http://bbbbbbbbbbbbbbbb.onion/landing"
CLEARWEB = "http://example.com/article"
CLEAR = "http://clear.example/page"
PAGE = "<div>" + "Real article body. " * 40 + "</div>"

# URLs whose host depends on which parser reads them: urlparse takes the host
# after the `@`, while requests and urllib3 end the authority at the backslash.
AMBIGUOUS_AUTHORITIES = (
    "http://evil.example\\@abcdefghijklmnop.onion/",
    "http://evil.example\\abcdefghijklmnop.onion/",
    "http://user@abcdefghijklmnop.onion/",
    "http://user:pass@abcdefghijklmnop.onion/thread",
    "http://evil.example%5C@abcdefghijklmnop.onion/",
    "http://abcdefghijklmnop.onion@evil.example/",
    "http://abcdefghijklmnop.onion\t.evil.example/",
)
CLOUDFLARE = ("<html><head><title>Just a moment...</title></head>"
              "<body><div id='cf-browser-verification'>Checking your browser before accessing"
              " example.com. Ray ID: 8a1b2c3d</div></body></html>")
CAPTCHA = ("<html><body><h1>Verify you are human</h1>"
           "<div class='g-recaptcha' data-sitekey='x'></div></body></html>")


def redirect(code, location):
    return FakeResponse(status_code=code, body="", headers={"Location": location})


class ScrapeTestCase(unittest.TestCase):
    """Every session is a RecordingSession; an unrouted URL answers PAGE."""

    def setUp(self):
        record_sessions(self, default_response=FakeResponse(body=PAGE))

    def route(self, url, response):
        RecordingSession.routes[url] = response

    def requested(self):
        return [call["url"] for call in RecordingSession.calls]

    def scrape(self, url, title="t", **kwargs):
        return scrape.scrape_single_detailed({"link": url, "title": title}, **kwargs)[1]

    def assert_every_hop_was_manual_and_over_tor(self):
        self.assertTrue(RecordingSession.calls)
        for call in RecordingSession.calls:
            self.assertIs(call["kwargs"].get("allow_redirects"), False, call["url"])
            self.assertTrue(call["kwargs"].get("stream"), call["url"])
            self.assertEqual(call["proxies"]["http"], TOR)


class OnlyOnionHostsAreFetchedByDefault(ScrapeTestCase):
    def test_is_onion_decides_on_the_host_actually_contacted(self):
        for url in (ONION, "https://ABCDEFGHIJKLMNOP.ONION:8080/x?y=1"):
            with self.subTest(url=url):
                self.assertTrue(scrape.is_onion(url))
        for url in ("http://onion.example.com/x", "http://notanonion/x", "http://x.onion.io/y",
                    CLEARWEB, "", None, "not a url") + AMBIGUOUS_AUTHORITIES:
            with self.subTest(url=url):
                self.assertFalse(scrape.is_onion(url))

    def test_each_url_is_fetched_refused_or_rejected_by_policy(self):
        cases = [(ONION, False, OK), (CLEARWEB, True, OK), (CLEARWEB, False, REFUSED),
                 ("http://onion.example.com/x", False, REFUSED), ("http://notanonion/x", False, REFUSED),
                 ("http://x.onion.io/y", False, REFUSED), ("ftp://x.onion/f", False, ERROR)]
        # Clearweb is an opt-in about hosts, not about URLs whose host is ambiguous.
        cases += [(url, allow, ERROR) for url in AMBIGUOUS_AUTHORITIES for allow in (False, True)]
        for url, allow, status in cases:
            with self.subTest(url=url, allow_clearweb=allow):
                RecordingSession.calls = []
                link, record = scrape.scrape_single_detailed(
                    {"link": url, "title": "Example Title"}, allow_clearweb=allow)
                self.assertEqual((link, record["status"], record["title"]),
                                 (url, status, "Example Title"))
                self.assertEqual(bool(RecordingSession.calls), status == OK)
                if status == OK:
                    self.assertIn("Real article body.", record["text"])
                else:
                    self.assertEqual((record["text"], record["links"]), ("", []))
                if url in AMBIGUOUS_AUTHORITIES:
                    self.assertIn("rejected", record["detail"])

    def test_scrape_multiple_reports_every_url_and_maps_only_read_pages(self):
        urls = [{"link": ONION, "title": "Leaks"}, {"link": CLEARWEB, "title": "Example"}]
        with self.assertLogs("scrape", level="WARNING") as logs:
            detailed = scrape.scrape_multiple_detailed(urls, max_workers=2)
        self.assertEqual({url: r["status"] for url, r in detailed.items()},
                         {ONION: OK, CLEARWEB: REFUSED})
        self.assertTrue(any(CLEARWEB in line for line in logs.output))
        plain = scrape.scrape_multiple(urls, max_workers=2)
        self.assertEqual(list(plain), [ONION])
        self.assertIn("Real article body.", plain[ONION])

    def test_max_return_chars_is_respected(self):
        self.route(ONION, FakeResponse(body="<div>" + "x" * 5000 + "</div>"))
        results = scrape.scrape_multiple([{"link": ONION, "title": "Big"}], max_return_chars=500)
        self.assertLessEqual(len(results[ONION]), 500)

    def test_each_response_maps_to_one_status(self):
        vendor = "<div>Vendor sells a captcha solving service. " + "Listing detail. " * 40 + "</div>"
        cases = [(CLEARWEB, FakeResponse(status_code=code, body="denied"), BLOCKED, code,
                  "http %d" % code) for code in (403, 429, 503)]
        cases += [
            (CLEARWEB, FakeResponse(body=CLOUDFLARE), BLOCKED, 200, "challenge"),
            (CLEARWEB, FakeResponse(body=CAPTCHA), BLOCKED, 200, "challenge"),
            # Onion markets serve real pages that mention or carry a captcha.
            (ONION, FakeResponse(body=vendor), OK, 200, ""),
            (ONION, FakeResponse(status_code=404, body="nope"), ERROR, 404, "http 404"),
            (ONION, requests.exceptions.ConnectionError("tor down"), ERROR, None, "tor down"),
        ]
        for url, response, status, http_status, detail in cases:
            with self.subTest(status=status, detail=detail):
                self.route(url, response)
                record = self.scrape(url, allow_clearweb=True)
                self.assertEqual((record["status"], record["http_status"]), (status, http_status))
                self.assertIn(detail, record["detail"])
                self.assertEqual(record["text"] != "", status == OK)
                mapped = scrape.scrape_multiple([{"link": url, "title": "t"}], allow_clearweb=True)
                self.assertEqual(bool(mapped), status == OK)

    def test_a_page_gets_one_thirty_second_connect_attempt(self):
        retry = scrape._build_session().get_adapter("http://x.onion").max_retries
        self.assertEqual((retry.connect, retry.read, scrape.TOR_TIMEOUT[0]), (0, 3, 30))


LANDING_PAGE = PAGE + '<a href="/next">next</a>'


class RedirectsAreCheckedOnEveryHop(ScrapeTestCase):
    def test_redirects_within_the_onion_space_are_followed(self):
        a_landing = "http://aaaaaaaaaaaaaaaa.onion/landing"
        hops = ["http://aaaaaaaaaaaaaaaa.onion/%d" % i for i in range(scrape.MAX_REDIRECTS + 1)]
        chains = [(str(code), [ONION_A, ONION_B], {ONION_A: redirect(code, ONION_B)})
                  for code in sorted(scrape.REDIRECT_CODES)]
        chains += [("relative location", [ONION_A, a_landing], {ONION_A: redirect(302, "/landing")}),
                   ("longest allowed chain", hops,
                    {here: redirect(302, there) for here, there in zip(hops, hops[1:])})]
        for name, path, routes in chains:
            with self.subTest(chain=name):
                routes[path[-1]] = FakeResponse(body=LANDING_PAGE)
                RecordingSession.reset(routes=routes)
                record = self.scrape(path[0])
                self.assertEqual(record["status"], OK)
                self.assertIn("Real article body.", record["text"])
                self.assertEqual(self.requested(), path)
                self.assert_every_hop_was_manual_and_over_tor()
                self.assertTrue(all(response.closed for response in routes.values()))
                # Links resolve against the page as served, not the first URL.
                final_host = path[-1].split("/")[2]
                self.assertEqual(record["links"], ["http://%s/next" % final_host])

    def test_a_hop_out_of_the_onion_space_is_refused_unfetched(self):
        chains = [(str(code), [ONION_A], {ONION_A: redirect(code, CLEAR)}) for code in (301, 302, 307)]
        chains += [("scheme-relative", [ONION_A], {ONION_A: redirect(302, "//clear.example/page")}),
                   ("late hop", [ONION_A, ONION_B],
                    {ONION_A: redirect(302, ONION_B), ONION_B: redirect(302, CLEAR)})]
        for name, path, routes in chains:
            with self.subTest(chain=name):
                RecordingSession.reset(routes=dict(routes, **{CLEAR: FakeResponse(body=PAGE)}))
                record = self.scrape(ONION_A)
                self.assertEqual((record["status"], record["text"]), (REFUSED, ""))
                self.assertIn("redirect", record["detail"])
                self.assertIn(CLEAR, record["detail"])
                self.assertEqual(self.requested(), path)
        detailed = scrape.scrape_multiple_detailed([{"link": ONION_A, "title": "t"}])
        self.assertEqual(detailed[ONION_A]["status"], REFUSED)
        self.assertEqual(scrape.scrape_multiple([{"link": ONION_A, "title": "t"}]), {})

    def test_a_clearweb_hop_needs_the_opt_in(self):
        self.route(ONION_A, redirect(302, CLEAR))
        self.assertEqual(self.scrape(ONION_A, allow_clearweb=True)["status"], OK)
        self.assert_every_hop_was_manual_and_over_tor()
        RecordingSession.reset(routes={CLEAR: redirect(301, "https://clear.example/moved"),
                                       "https://clear.example/moved": FakeResponse(body=PAGE)})
        self.assertEqual(self.scrape(CLEAR)["status"], REFUSED)
        self.assertEqual(RecordingSession.calls, [])
        self.assertEqual(self.scrape(CLEAR, allow_clearweb=True)["status"], OK)

    def test_a_loop_is_cut_at_the_hop_limit(self):
        self.route(ONION_A, redirect(302, ONION_B))
        self.route(ONION_B, redirect(302, ONION_A))
        record = self.scrape(ONION_A)
        self.assertEqual(record["status"], ERROR)
        self.assertIn("too many redirects", record["detail"])
        self.assertEqual(len(RecordingSession.calls), scrape.MAX_REDIRECTS + 1)

    def test_an_unsafe_location_is_rejected_unfetched_even_with_the_opt_in(self):
        for location in ("http://evil.example\\@aaaaaaaaaaaaaaaa.onion/", "file:///etc/passwd",
                         "ftp://aaaaaaaaaaaaaaaa.onion/x", "gopher://x.onion/"):
            with self.subTest(location=location):
                RecordingSession.reset(routes={ONION_A: redirect(302, location)})
                record = self.scrape(ONION_A, allow_clearweb=True)
                self.assertEqual(record["status"], ERROR)
                self.assertIn("redirect", record["detail"])
                self.assertEqual(self.requested(), [ONION_A])

    def test_a_redirect_without_a_location_is_an_error(self):
        self.route(ONION_A, FakeResponse(status_code=302, body=""))
        record = self.scrape(ONION_A)
        self.assertEqual((record["status"], record["http_status"]), (ERROR, 302))

    def test_the_size_cap_still_applies_after_a_redirect(self):
        self.route(ONION_A, redirect(302, ONION_B))
        self.route(ONION_B, FakeResponse(body="<div>" + "y" * (2 * scrape.MAX_DOWNLOAD_BYTES) + "</div>"))
        record = self.scrape(ONION_A)
        self.assertEqual(record["status"], OK)
        self.assertLessEqual(len(record["text"]), scrape.MAX_EXTRACTED_TEXT_CHARS + len("t - "))
        self.assert_every_hop_was_manual_and_over_tor()


ENGINE = search.DEFAULT_SEARCH_ENGINES[0]
RESULTS_PAGE = '<html><a href="http://targetabcdefghij234567.onion/t">ACME database dump listing</a></html>'


class EveryFetchPathChecksTheFirstUrlAndEveryHop(ScrapeTestCase):
    def test_get_over_tor_checks_the_url_it_is_given(self):
        for url, allow, status in ((CLEAR, False, REFUSED),
                                   ("http://evil.example\\@aaaaaaaaaaaaaaaa.onion/", True, ERROR)):
            with self.subTest(url=url):
                with self.assertRaises(scrape.UrlRefused) as refused:
                    scrape.get_over_tor(scrape._build_session(), url, allow_clearweb=allow, timeout=5)
                self.assertEqual(refused.exception.status, status)
        self.assertEqual(RecordingSession.calls, [])
        response, final = scrape.get_over_tor(scrape._build_session(), ONION_A, timeout=5)
        self.assertEqual((response.status_code, final), (200, ONION_A))

    def test_search_follows_an_engine_only_within_the_onion_space(self):
        moved = "http://cccccccccccccccc.onion/search?q=acme"
        for location, links in ((CLEAR, []), (moved, ["http://targetabcdefghij234567.onion/t"])):
            with self.subTest(location=location):
                RecordingSession.reset(routes={ENGINE.format(query="acme"): redirect(302, location),
                                               CLEAR: FakeResponse(body=RESULTS_PAGE),
                                               moved: FakeResponse(body=RESULTS_PAGE)})
                found = search.fetch_search_results_detailed(ENGINE, "acme")["links"]
                self.assertEqual([r["link"] for r in found], links)
                self.assertNotIn(CLEAR, self.requested())
                self.assert_every_hop_was_manual_and_over_tor()

    def test_a_clearweb_engine_or_engine_redirect_is_never_requested(self):
        clear_engine = {"name": "Clear", "url": "http://clear.example/search?q={query}"}
        self.route(search.SEARCH_ENGINES[0]["url"].format(query="test"), redirect(302, CLEAR))
        self.route("http://clear.example/search?q=acme", FakeResponse(body=RESULTS_PAGE))
        self.assertEqual(search.fetch_search_results_detailed(clear_engine["url"], "acme")["links"], [])
        for engine, error in ((search.SEARCH_ENGINES[0], "redirect"), (clear_engine, "not an onion host")):
            with self.subTest(engine=engine["name"]):
                status = health._ping_single_engine(engine)
                self.assertEqual(status["status"], "down")
                self.assertIn(error, status["error"])
        self.assertFalse([url for url in self.requested() if "clear.example" in url])


UNREAD_BOUND = 16 * 1024 * 1024  # what loopback socket buffers can hold; a read body is 64 MB
WIRE_SLACK = 256 * 1024
LANDING = b"<html><body><div>" + b"Landing page text. " * 40 + b"</div></body></html>"


class BodiesAreCappedOrLeftUnread(unittest.TestCase):
    """Real sockets on 127.0.0.1, reached by real Tor sessions minus their proxy."""

    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer({
            "/big": big_route(),
            "/start": big_route(302, Location="/landing"),
            "/landing": (200, {"Content-Type": "text/html; charset=utf-8",
                               "Content-Length": str(len(LANDING))}, lambda: [LANDING]),
        })
        cls.addClassCleanup(cls.server.close)

    def setUp(self):
        quiet_logger(self, "scrape")
        scrape._thread_local = threading.local()
        self.addCleanup(setattr, scrape, "_thread_local", threading.local())
        self.seen = []

    def wire_bytes(self):
        return sum(response.raw.tell() for response in self.seen)

    def test_no_caller_reads_a_redirect_body(self):
        def streaming(url):
            session = unproxied(scrape._build_session(), self.seen)
            response, final = scrape.get_over_tor(session, url, allow_clearweb=True,
                                                  timeout=(5, 20), stream=True)
            response.close()
            self.assertEqual((response.status_code, final), (200, self.server.base + "/landing"))

        def not_streaming(url):  # how search and the health pings call it
            session = unproxied(search.get_tor_session(), self.seen)
            response, _ = scrape.get_over_tor(session, url, allow_clearweb=True, timeout=(5, 20))
            self.assertIn("Landing page text.", response.text)

        def scraper(url):
            scrape._thread_local.tor_session = unproxied(scrape._build_session(), self.seen)
            record = scrape.scrape_single_detailed({"link": url, "title": "Local"}, allow_clearweb=True)[1]
            self.assertEqual(record["status"], scrape.STATUS_OK)
            self.assertIn("Landing page text.", record["text"])

        for path, caller in (("/start?a", streaming), ("/start?b", not_streaming), ("/start?c", scraper)):
            with self.subTest(caller=caller.__name__):
                self.seen.clear()
                caller(self.server.base + path)
                (hop,) = [r for r in self.seen if r.status_code == 302]
                self.assertIs(hop._content, False, "requests read the redirect body")
                self.assertLess(self.server.written(path), UNREAD_BOUND,
                                "the redirect body was streamed to the client")

    def test_get_over_tor_leaves_the_body_unread_and_read_capped_stops_at_the_cap(self):
        session = unproxied(search.get_tor_session(), self.seen)
        response, _ = scrape.get_over_tor(session, self.server.base + "/big?x",
                                          allow_clearweb=True, timeout=(5, 20))
        try:
            self.assertEqual(response.status_code, 200)
            self.assertLessEqual(self.wire_bytes(), WIRE_SLACK)
            self.assertEqual(len(scrape.read_capped(response, 100_000)), 100_000)
            self.assertLessEqual(self.wire_bytes(), 100_000 + WIRE_SLACK)
        finally:
            response.close()

    def test_a_health_ping_reads_nothing_past_the_headers(self):
        real = search.get_tor_session
        for patch in (mock.patch.object(health, "get_tor_session", lambda: unproxied(real(), self.seen)),
                      mock.patch.object(scrape, "is_onion", lambda url: True)):
            patch.start()
            self.addCleanup(patch.stop)
        status = health._ping_single_engine({"name": "Big", "url": self.server.base + "/big?q={query}"})
        self.assertEqual(status["status"], "up")
        self.assertLessEqual(self.wire_bytes(), WIRE_SLACK)
        self.assertTrue(self.seen)
        self.assertTrue(all(response._content is False for response in self.seen))

    def test_no_tor_module_reads_a_body_without_the_cap(self):
        direct_read = re.compile(r"\b(response|resp|r)\.(content|text|json\(\))")
        for name in ("scrape.py", "search.py", "health.py"):
            source = (Path(__file__).resolve().parent.parent / name).read_text()
            code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
            with self.subTest(module=name):
                self.assertIsNone(direct_read.search(re.sub(r'"""[\s\S]*?"""', "", code)))


PHPBB = ('<div id="page-header"><h1>Leaks Board</h1></div>'
         '<form id="topiclist"><ul class="topiclist topics">'
         '<li><a class="topictitle">ACME Corp 400GB database dump</a> by seller99</li>'
         '<li><a class="topictitle">Bank of X cardholder records 2.1M</a> by vendor7</li>'
         '</ul></form>')
RUSSIAN = "Утечка базы данных банка"


def as_requests_would(body, content_type):
    """A response carrying the encoding requests itself assigns from the headers."""
    return FakeResponse(body=body, content_type=content_type,
                        encoding=get_encoding_from_headers({"content-type": content_type}))


class PageTextIsExtractedAndDecoded(ScrapeTestCase):
    def test_furniture_is_stripped_but_content_is_not(self):
        article = "Real article body. " * 40
        cases = (
            # phpBB and SMF wrap their whole topic listing in a <form>.
            (PHPBB, ["ACME Corp 400GB database dump", "Bank of X cardholder records 2.1M"], []),
            ('<form name="messageindex"><td>Ransomware crew recruiting</td></form>',
             ["Ransomware crew recruiting"], []),
            # A strip that would eat the page is undone.
            ("<nav>Home Forums</nav><header><h1>" + "Topic title here. " * 20 + "</h1></header>",
             ["Topic title here."], []),
            ("<nav>Home Forums Login</nav><div>%s</div><footer>Powered by X</footer>" % article,
             ["Real article body."], ["Powered by X", "Home Forums Login"]),
        )
        for html, kept, dropped in cases:
            with self.subTest(html=html[:40]):
                text = scrape.extract_page_text(html)
                for phrase in kept:
                    self.assertIn(phrase, text)
                for phrase in dropped:
                    self.assertNotIn(phrase, text)

    def test_a_page_decodes_in_its_own_charset(self):
        # requests would assume ISO-8859-1 for a text/* page without a charset.
        cases = (
            ("header wins", '<meta charset="utf-8"><p>' + RUSSIAN, "cp1251", "text/html; charset=windows-1251"),
            ("undeclared utf-8", "<p>" + RUSSIAN, "utf-8", "text/html"),
            ("meta charset", '<meta charset="windows-1251"><p>' + RUSSIAN, "cp1251", "text/html"),
            ("meta http-equiv", '<meta http-equiv="Content-Type" content="text/html; '
             'charset=windows-1251"><p>' + RUSSIAN, "cp1251", "text/html"),
            ("byte order mark", "<p>" + RUSSIAN, "utf-8-sig", "text/html"),
            ("unknown charset name", "<p>" + RUSSIAN, "utf-8", "text/html; charset=x-no-such-charset"),
            ("plain ascii", "<p>ACME dump</p>", "ascii", "text/html"),
        )
        for name, text, codec, content_type in cases:
            with self.subTest(name):
                body = text.encode(codec)
                self.assertEqual(scrape.decode_capped(as_requests_would(body, content_type), body), text)
        # A character cut in half by the byte cap is dropped, not the page.
        cut = ("<p>" + RUSSIAN).encode("utf-8")[:-1]
        self.assertEqual(scrape.decode_capped(as_requests_would(cut, "text/html"), cut),
                         "<p>" + RUSSIAN[:-1])
        self.route(ONION, as_requests_would(("<p>" + RUSSIAN + "</p>").encode("utf-8"), "text/html"))
        self.assertIn(RUSSIAN, self.scrape(ONION)["text"])


ZWSP = chr(0x200B)
ONION_ONE = "http://aaaaaaaaaaaaaaaa.onion/empty"
ONION_TWO = "http://bbbbbbbbbbbbbbbb.onion/blank"
INVISIBLE_PAGES = {
    ONION_ONE: "<html><body><div>" + ZWSP + " " + ZWSP + "</div></body></html>",
    ONION_TWO: "<html><body><p>" + (ZWSP + chr(0x2060) + " \t ") * 50 + "</p></body></html>",
}


class InvisiblePagesAreEmpty(ScrapeTestCase):
    """A zero-width space is not whitespace to str.split, so text is collapsed after scrubbing."""

    def setUp(self):
        super().setUp()
        for url, body in INVISIBLE_PAGES.items():
            self.route(url, FakeResponse(body=body))

    def test_a_page_of_invisible_characters_is_an_empty_page(self):
        for url in INVISIBLE_PAGES:
            with self.subTest(url=url):
                record = self.scrape(url, title="Relevant source")
                self.assertEqual((record["status"], record["detail"], record["text"]),
                                 (ERROR, "empty page", ""))
        self.assertEqual(scrape.scrape_multiple(
            [{"link": url, "title": "Relevant source"} for url in INVISIBLE_PAGES]), {})
        self.route(ONION_ONE, FakeResponse(body="<div>Leak" + ZWSP + "ed " + ZWSP + " records</div>"))
        record = self.scrape(ONION_ONE, title="Board")
        self.assertEqual((record["status"], record["text"]), (OK, "Board - Leaked records"))

    def test_the_pipeline_stops_as_nothing_readable(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        stages = []
        inv = pipeline.run_investigation(
            None, "acme breach", "capturing-fake",
            search_fn=lambda refined, threads: search_outcome([
                {"title": "Relevant source", "link": ONION_ONE},
                {"title": "Another source", "link": ONION_TWO}]),
            investigations_dir=tmp.name,
            on_stage=lambda name, inv: stages.append(name),
            llm_factory=CapturingChatModel,
        )
        self.assertEqual(inv.status, pipeline.STATUS_NOTHING_READABLE)
        self.assertEqual(inv.scraped, {})
        self.assertNotIn("summarize", stages)
        self.assertIsNone(inv.saved_as)


ONION56 = "http://abcdefghij234567890abcdefghij234567890abcdefghij2345.onion"
OTHER56 = "http://zyxwvutsrq234567890abcdefghij234567890abcdefghij2345.onion"
TORNODE = "http://tornode3tnrtzgqwd3vmxdumucddqfd6zk7icu4wzdwxo5c3zn2xqfqd.onion"
HIDDEN_WIKI = "http://zqktlwkvmv5ipqnik77wyxtb74bg6gtlwifjntdbanvprue7qqzaqlid.onion"


class PageLinksAreKept(unittest.TestCase):
    def test_onion_links_come_back_off_host_first_and_deduplicated(self):
        directory = ('<h1>Leak sites</h1><ul><li><a href="{0}/lockbit">LockBit</a></li>'
                     '<li><a href="/leak/acme">ACME dump</a></li><li><a href="#top">Back to top</a></li>'
                     '<li><a href="https://ransomware.live/groups">Tracker</a></li>'
                     '<li><a href="mailto:seller@example.com">Contact</a></li></ul>').format(OTHER56)
        duplicates = ('<a href="{0}/a">one</a><a href="{0}/a">again</a>'
                      '<a href="{0}/a#part2">and the same page</a>').format(ONION56)
        cases = (
            # Clearweb, fragment and mailto links are not leads to scrape.
            (directory, ONION56 + "/dir", [OTHER56 + "/lockbit", ONION56 + "/leak/acme"]),
            (duplicates, ONION56, [ONION56 + "/a"]),
            ("<p>Just prose.</p>", ONION56, []),
            ("<a href=", ONION56, []),
            ('<a href="/go">%s/dir</a>' % TORNODE[len("http://"):], ONION56, [TORNODE + "/dir", ONION56 + "/go"]),
            ('<a href="/go">Read about the onion routing project</a>', ONION56, [ONION56 + "/go"]),
        )
        for html, base, expected in cases:
            with self.subTest(html=html[:40]):
                self.assertEqual(scrape.extract_onion_links(html, base), expected)

    def test_a_directory_that_hides_its_links_in_anchor_text(self):
        page = ('<a href="/t?ad=banner&k=1">Advertise</a>'
                '<a href="?cat=1">Marketplaces</a><a href="?cat=2">Directories</a>'
                '<a href="?cat=3">Hacking</a><a href="?cat=4">Forums</a>'
                '<div class="entry"><a href="/out/1">TorNode</a><a href="/out/1">%s</a></div>'
                '<div class="entry"><a href="/out/2">The Hidden Wiki</a><a href="/out/2">%s</a></div>'
                % (TORNODE, HIDDEN_WIKI))
        found = scrape.extract_onion_links(page, ONION56 + "/?cat=2")
        self.assertEqual(found[:2], [TORNODE, HIDDEN_WIKI])
        self.assertIn(ONION56 + "/out/1", found)

    def test_links_are_bounded_in_number_and_length(self):
        farm = "".join('<a href="%s/%d">x</a>' % (ONION56, i) for i in range(200))
        self.assertEqual(len(scrape.extract_onion_links(farm, ONION56)), scrape.MAX_PAGE_LINKS)
        long = scrape.extract_onion_links('<a href="%s/%s">x</a>' % (ONION56, "a" * 500), ONION56)
        self.assertTrue(long)
        self.assertTrue(all(len(link) <= scrape.MAX_LINK_CHARS for link in long))


if __name__ == "__main__":
    unittest.main()
