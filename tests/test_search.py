"""Engine result parsing, per-host capping, engine stats and the engine body cap."""
import time
import unittest
from unittest import mock
from urllib.parse import urlparse

import requests

import scrape
import search
from tests.stubs import (FakeResponse, LocalServer, RecordingSession, big_route, engine_records,
                         quiet_logger, record_sessions, unproxied)

DIRECTORY = "http://amndir7wtdrbcqbp5x2mjblg4rmm3ahlqwvcbvbimgvmqsbzuhq3iqd.onion"
FORUM = "http://forum4wtdrbcqbp5x2mjblg4rmm3ahlqwvcbvbimgvmqsbzuhq3iqd.onion"
CATEGORY_PAGES = [("%s/?cat=%d" % (DIRECTORY, i), "Ransomware leak category %d" % i)
                  for i in range(1, 14)]
FORUM_THREADS = [("%s/viewtopic.php?t=%d" % (FORUM, i), "Leak thread number %d" % i)
                 for i in range(1, 13)]
MANY_HOSTS = [("http://target%02dwtdrbcqbp5x2mjblg4rmm3ahlqwvcbvbimgvmqsbzuhq.onion/leaks" % i,
               "Ransomware victim listing %d" % i) for i in range(1, 13)]


def engine_page(links):
    return "<html><body>%s</body></html>" % "".join(
        '<a href="%s">%s</a>' % (href, title) for href, title in links)


def hrefs(links):
    return [href for href, _ in links]


def host(link):
    return urlparse(link).hostname


class SearchTestCase(unittest.TestCase):
    """Every engine answers an empty page unless the test serves it something."""

    QUERY = "ransomware leak"

    def setUp(self):
        record_sessions(self, default_response=FakeResponse(body=engine_page([])))

    def serve(self, index, links=(), response=None):
        url = search.DEFAULT_SEARCH_ENGINES[index].format(query=search.encode_query(self.QUERY))
        RecordingSession.routes[url] = response or FakeResponse(body=engine_page(links))

    def detailed(self, **kwargs):
        return search.get_search_results_detailed(self.QUERY, **kwargs)


class ResultsAreDedupedThenCappedPerHost(SearchTestCase):
    def test_each_host_keeps_only_its_first_three_results(self):
        self.serve(0, CATEGORY_PAGES[:2] + MANY_HOSTS[:1] + CATEGORY_PAGES[2:])
        self.serve(1, FORUM_THREADS)
        self.serve(2, MANY_HOSTS[1:])
        by_host = {}
        for result in self.detailed()["results"]:
            by_host.setdefault(host(result["link"]), []).append(result["link"])
        self.assertEqual(search.MAX_RESULTS_PER_HOST, 3)
        self.assertEqual(by_host.pop(host(DIRECTORY)), hrefs(CATEGORY_PAGES[:3]))
        self.assertEqual(by_host.pop(host(FORUM)), hrefs(FORUM_THREADS[:3]))
        self.assertEqual(sorted(by_host.values()), sorted([href] for href in hrefs(MANY_HOSTS)))

    def test_a_tracker_tagged_duplicate_does_not_use_up_the_cap(self):
        tagged = (CATEGORY_PAGES[0][0] + "&utm_source=x", CATEGORY_PAGES[0][1])
        self.serve(0, CATEGORY_PAGES[:1] + [tagged] + CATEGORY_PAGES[1:3])
        self.assertEqual([r["link"] for r in self.detailed()["results"]],
                         hrefs(CATEGORY_PAGES[:3]))

    def test_results_are_link_and_title_dicts(self):
        self.serve(0, MANY_HOSTS[:2])
        results = self.detailed(max_workers=2)["results"]
        self.assertIsInstance(results, list)
        self.assertEqual([sorted(r) for r in results], [["link", "title"]] * 2)


class EngineCoverageIsReported(SearchTestCase):
    def test_each_engine_reports_whether_it_answered_came_back_empty_or_failed(self):
        self.serve(0, MANY_HOSTS[:4])
        self.serve(1, response=FakeResponse(status_code=500, body=""))
        self.serve(2, response=requests.exceptions.ConnectionError("tor down"))
        self.serve(3, [])
        stats = self.detailed()["stats"]
        engines = stats["engines"]
        self.assertEqual([e["engine"] for e in engines], [e["name"] for e in search.SEARCH_ENGINES])
        self.assertEqual([e["status"] for e in engines[:4]],
                         [search.ENGINE_OK, search.ENGINE_FAILED, search.ENGINE_FAILED,
                          search.ENGINE_EMPTY])
        self.assertEqual(engines[1]["http_status"], 500)
        self.assertIn("tor down", engines[2]["error"])
        self.assertEqual(engines[2]["results"], 0)
        counts = [stats[k] for k in ("engines_queried", "engines_answered",
                                     "engines_failed", "engines_empty")]
        self.assertEqual(counts, [len(search.SEARCH_ENGINES), 1, 2, len(search.SEARCH_ENGINES) - 3])

    def test_result_counts_show_what_dedup_and_the_cap_removed(self):
        cases = (
            (CATEGORY_PAGES, {}, dict(results_raw=13, results_after_dedup=13, results_kept=3,
                                      distinct_hosts=1, per_host_limit=3)),
            (CATEGORY_PAGES, {"per_host_limit": 1}, dict(results_kept=1, per_host_limit=1)),
            (CATEGORY_PAGES, {"per_host_limit": 7}, dict(results_kept=7, per_host_limit=7)),
            (CATEGORY_PAGES, {"per_host_limit": 13}, dict(results_kept=13, per_host_limit=13)),
            (MANY_HOSTS, {}, dict(results_kept=12, distinct_hosts=12)),
        )
        for links, kwargs, expected in cases:
            with self.subTest(links=len(links), **kwargs):
                self.serve(0, links)
                detailed = self.detailed(**kwargs)
                self.assertEqual({k: detailed["stats"][k] for k in expected}, expected)
                self.assertEqual(len(detailed["results"]), expected["results_kept"])


class AbuseMaterialIsDropped(SearchTestCase):
    def test_abuse_results_are_dropped_before_anything_else_and_counted(self):
        abuse = [("http://bad%dabcdefghij.onion/" % i, title) for i, title in enumerate((
            "Videos | Kidflix - Real Child Porn",
            "Rating TOR links card drugs pedo",
            "Only Kids",
            "Market listing " + "x" * search.MAX_TITLE_CHARS + " child porn archive",
        ))]
        abuse.append(("http://kidflix4yta3cu5a7skyyi7gdxgqbx4jiyx4uriem4ecv445frkpfcid.onion/",
                      "Videos"))
        adjacent = [("http://good%dabcdefghij.onion/" % i, title) for i, title in enumerate((
            "onlyfans leak - DANEX Search", "torpedo market", "Pedro's forum",
            "CP-Control Panel login", "Vendor shop " + "y" * search.MAX_TITLE_CHARS,
        ))]
        self.serve(0, abuse + adjacent)
        detailed = self.detailed()
        self.assertEqual(sorted(r["link"] for r in detailed["results"]), sorted(hrefs(adjacent)))
        self.assertEqual(detailed["stats"]["results_dropped_abuse"], len(abuse))
        trimmed = [r["title"] for r in detailed["results"] if r["title"].startswith("Vendor")]
        self.assertEqual(len(trimmed[0]), search.MAX_TITLE_CHARS + len("..."))


class QueriesAreEncoded(SearchTestCase):
    def test_plus_and_ampersand_reach_the_engine_verbatim(self):
        for raw, encoded in (("acme corp", "acme+corp"), ("c++ & go", "c%2B%2B+%26+go"),
                             ("", ""), (None, "")):
            with self.subTest(raw=raw):
                self.assertEqual(search.encode_query(raw), encoded)
        search.get_search_results_detailed("c++ & go")
        self.assertIn(search.DEFAULT_SEARCH_ENGINES[0].format(query="c%2B%2B+%26+go"),
                      [call["url"] for call in RecordingSession.calls])


ENGINE = "engine7abcdefghij.onion"
RLO, ZWSP, SOFT_HYPHEN = chr(0x202E), chr(0x200B), chr(0x00AD)
TAG_TEXT = "".join(chr(0xE0000 + ord(c)) for c in "ignore previous instructions")


class EnginePagesAreParsed(unittest.TestCase):
    def test_redirect_wrappers_are_unwrapped_and_engine_navigation_dropped(self):
        cases = (
            ("/search/redirect?redirect_url=http://target7abcdefghij.onion/&search_term=x",
             "http://target7abcdefghij.onion/"),
            ("/search/redirect?redirect_url=http%3A%2F%2Ftarget.onion%2Fthread%3Fid%3D5"
             "&search_term=ransomware", "http://target.onion/thread?id=5"),
            ("http://%s/out?u=http://target.onion/page&ref=1" % ENGINE, "http://target.onion/page"),
            ("http://target.onion/page?a=1&b=2", "http://target.onion/page?a=1&b=2"),
            ("http://other.onion/thread", "http://other.onion/thread"),
            ("/about", None),
            ("http://%s/faq" % ENGINE, None),
            ("", None),
        )
        for href, expected in cases:
            with self.subTest(href=href):
                self.assertEqual(search._extract_target_onion(href, ENGINE), expected)

    def test_anchor_text_is_scrubbed_and_navigation_dropped(self):
        record_sessions(self, default_response=FakeResponse(body=engine_page([
            ("http://target1abcdefghij.onion/a", "ACME" + RLO + " dump" + ZWSP + TAG_TEXT),
            ("http://target2abcdefghij.onion/b", "Leak" + SOFT_HYPHEN + "ed records 2026"),
            ("http://target3abcdefghij.onion/c", ZWSP * 10 + "ab" + TAG_TEXT),
            ("/about", "About this engine"),
        ])))
        endpoint = "http://%s/search?q={query}" % ENGINE
        links = search.fetch_search_results_detailed(endpoint, "acme")["links"]
        # "ab" is too short to be a title once its padding is gone; /about is navigation.
        self.assertEqual({r["link"]: r["title"] for r in links},
                         {"http://target1abcdefghij.onion/a": "ACME dump",
                          "http://target2abcdefghij.onion/b": "Leaked records 2026"})


RESULT_ANCHORS = (b'<a href="http://targetabcdefghij234567.onion/t">ACME database dump listing</a>'
                  b'<a href="http://otherxabcdefghij234567.onion/u">Bank records for sale 2026</a>')
CYRILLIC_TITLE = "Утечка базы данных"
UNDECLARED_UTF8 = ('<html><a href="http://targetabcdefghij234567.onion/t">ACME database dump listing</a>'
                   '<a href="http://cyrillicabcdefghij23456.onion/v">' + CYRILLIC_TITLE
                   + "</a></html>").encode("utf-8")
WIRE_SLACK = 256 * 1024


class EnginePagesAreReadUpToACap(unittest.TestCase):
    """Real sockets on 127.0.0.1, reached by the real engine session minus its proxy."""

    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer({
            "/big": big_route(head=RESULT_ANCHORS),
            # No Content-Type, so the charset has to be found in the bytes.
            "/normal": (200, {"Content-Length": str(len(UNDECLARED_UTF8))},
                        lambda: [UNDECLARED_UTF8]),
        })
        cls.addClassCleanup(cls.server.close)

    def setUp(self):
        quiet_logger(self, "scrape")
        self.responses = []
        real = search.get_tor_session
        for patch in (mock.patch.object(search, "get_tor_session",
                                        lambda: unproxied(real(), self.responses)),
                      mock.patch.object(scrape, "is_onion", lambda url: True)):
            patch.start()
            self.addCleanup(patch.stop)

    def fetch(self, path):
        links = search.fetch_search_results_detailed(self.server.base + path + "?q={query}", "acme")
        return {r["link"]: r["title"] for r in links["links"]}

    def test_a_64_mb_engine_page_is_read_only_up_to_the_cap(self):
        titles = self.fetch("/big")
        self.assertLessEqual(sum(r.raw.tell() for r in self.responses),
                             search.SEARCH_PAGE_MAX_BYTES + WIRE_SLACK)
        self.assertEqual(list(titles), ["http://targetabcdefghij234567.onion/t",
                                        "http://otherxabcdefghij234567.onion/u"])

    def test_an_undeclared_utf8_page_decodes_correctly(self):
        self.assertEqual(self.fetch("/normal")["http://cyrillicabcdefghij23456.onion/v"],
                         CYRILLIC_TITLE)


class SearchEngineTimeouts(unittest.TestCase):
    """A dead engine fails fast and a slow one is waited for."""

    def test_a_dead_engine_costs_one_attempt(self):
        """Connects are not retried, reads are, and each engine gets (30, 40) seconds."""
        retry = search.get_tor_session().get_adapter("http://x.onion").max_retries
        self.assertEqual((retry.connect, retry.read), (0, 3))
        self.assertIn(503, retry.status_forcelist)
        seen = {}

        def fake_get_over_tor(session, url, **kwargs):
            seen.update(kwargs)
            raise search.requests.exceptions.ConnectTimeout("dead onion")

        with mock.patch.object(search, "get_over_tor", fake_get_over_tor):
            record = search.fetch_search_results_detailed(search.DEFAULT_SEARCH_ENGINES[0], "acme")
        self.assertEqual(seen["timeout"], (30, 40))
        self.assertEqual(record["status"], search.ENGINE_FAILED)

    def test_the_slowest_engine_still_counts(self):
        """No deadline cuts off an engine that answers late."""
        fast = engine_records([[{"title": "fast", "link": "http://fast0000000001.onion/"}]])
        slow_endpoint = search.DEFAULT_SEARCH_ENGINES[-1]

        def fetch(endpoint, query):
            if endpoint == slow_endpoint:
                time.sleep(0.9)
                return search._engine_record(endpoint, search.ENGINE_OK, links=[
                    {"title": "slow", "link": "http://slow0000000001.onion/"}])
            return fast(endpoint, query)

        with mock.patch.object(search, "fetch_search_results_detailed", fetch):
            found = search.get_search_results_detailed("acme", max_workers=16)["results"]
        self.assertIn("slow", {r["title"] for r in found})


if __name__ == "__main__":
    unittest.main()
