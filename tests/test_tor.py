"""The Tor invariant: nothing Robin builds or sends escapes the SOCKS proxy."""
import ast
import inspect
import os
import re
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import requests

import health
import mcp_server
import scrape
import search
from tests.stubs import FakeResponse, RecordingSession, record_sessions

TOR = "socks5h://127.0.0.1:9050"
EXPECTED_PROXIES = {"http": TOR, "https": TOR}
ONION = "http://targetabcdefghij234567.onion/thread?id=1"
REPO = Path(__file__).resolve().parent.parent

# Every session builder, by the name it has in its module.
SESSION_BUILDERS = {
    "scrape._build_session": scrape._build_session,
    "scrape._get_session": scrape._get_session,
    "search.get_tor_session": search.get_tor_session,
}

# How many times each module may call `requests.Session(`. A new call site is a
# new session path, and SESSION_BUILDERS must cover it. The zeros are modules
# that must borrow a builder rather than make one.
SESSION_CONSTRUCTION_SITES = {
    "scrape.py": 1,
    "search.py": 1,
    "health.py": 0,
    "pipeline.py": 0,
    "mcp_server.py": 0,
}

# What a corporate network or Docker's client proxy config injects into every
# container. A request resolved to this proxy has left by the user's own route.
HOSTILE_PROXY_ENV = {name: "http://corp-proxy.example:3128"
                     for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                                  "http_proxy", "https_proxy", "all_proxy")}


def resolved_proxy(session, url):
    """The proxy `requests` would actually use for `url` on this session.

    Session.request merges environment proxies in as request-level settings,
    which beat `session.proxies`, so asserting on `session.proxies` alone misses it.
    """
    prepared = session.prepare_request(requests.Request("GET", url))
    settings = session.merge_environment_settings(prepared.url, {}, None, None, None)
    return requests.utils.select_proxy(prepared.url, settings["proxies"])


def assert_hardened(testcase, session, name):
    """Tor proxy, environment ignored even with proxy variables set, no redirect resolution."""
    testcase.assertEqual(dict(session.proxies), EXPECTED_PROXIES, name)
    testcase.assertFalse(session.trust_env, "%s trusts the environment" % name)
    # requests reads a redirect's whole body to prepare Response.next unless
    # get_redirect_target says there is none.
    hop = FakeResponse(status_code=302, headers={"Location": "http://clear.example/"})
    testcase.assertIsNone(session.get_redirect_target(hop), name)
    with mock.patch.dict(os.environ, HOSTILE_PROXY_ENV):
        for url in (ONION, "https://example.com/article", "http://example.com/"):
            testcase.assertEqual(resolved_proxy(session, url), TOR,
                                 "%s sent %s through the environment's proxy" % (name, url))


def functions_constructing_sessions(tree):
    """Every function in `tree` that calls `requests.Session(...)`."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute)
                and inner.func.attr == "Session" and isinstance(inner.func.value, ast.Name)
                and inner.func.value.id == "requests" for inner in ast.walk(node)):
            yield node


def assigned(function, attribute):
    """The constant values `function` assigns to `<something>.<attribute>`."""
    return [inner.value.value if isinstance(inner.value, ast.Constant) else inner.value
            for inner in ast.walk(function) if isinstance(inner, ast.Assign)
            for target in inner.targets
            if isinstance(target, ast.Attribute) and target.attr == attribute]


class EverySessionIsATorSession(unittest.TestCase):
    def test_every_builder_returns_a_hardened_tor_session(self):
        scrape._thread_local = threading.local()
        self.addCleanup(setattr, scrape, "_thread_local", threading.local())
        for name, build in SESSION_BUILDERS.items():
            with self.subTest(builder=name):
                assert_hardened(self, build(), name)
                self.assertNotIn("use_tor", inspect.signature(build).parameters)

    def test_the_sources_build_sessions_only_in_hardened_builders(self):
        # requests.get() and friends build a fresh, unproxied, env-trusting session.
        bare = re.compile(r"\brequests\.(get|post|put|patch|delete|head|options|request)\(")
        for filename, expected in SESSION_CONSTRUCTION_SITES.items():
            source = (REPO / filename).read_text(encoding="utf-8")
            with self.subTest(module=filename):
                self.assertEqual(len(re.findall(r"requests\.Session\(", source)), expected,
                                 "a new session path must be added to SESSION_BUILDERS")
                self.assertIsNone(bare.search(source), "%s calls requests directly" % filename)
                if filename in ("scrape.py", "search.py"):
                    self.assertNotIn("use_tor", source)
                    self.assertNotIn("direct_session", source)
                functions = list(functions_constructing_sessions(ast.parse(source)))
                self.assertEqual(len(functions), expected)
                for function in functions:
                    self.assertTrue(any(value is False for value in assigned(function, "trust_env")),
                                    "%s.%s does not set trust_env = False" % (filename, function.name))
                    self.assertTrue(assigned(function, "get_redirect_target"),
                                    "%s.%s lets requests resolve redirects" % (filename, function.name))

    def test_every_fetch_path_sends_through_tor(self):
        paths = {
            "scrape an onion page": lambda: scrape.scrape_single_detailed(
                {"link": ONION, "title": "Leaks Board"}),
            "scrape a clearweb page": lambda: scrape.scrape_single_detailed(
                {"link": "http://example.com/page", "title": "Example"}, allow_clearweb=True),
            "scrape on two workers": lambda: scrape.scrape_multiple(
                [{"link": ONION, "title": "One"}, {"link": ONION + "&p=2", "title": "Two"}],
                max_workers=2),
            "query an engine": lambda: search.fetch_search_results_detailed(
                search.DEFAULT_SEARCH_ENGINES[0], "ransomware"),
            "ping an engine": lambda: health._ping_single_engine(search.SEARCH_ENGINES[0]),
        }
        record_sessions(self)
        for name, fetch in paths.items():
            with self.subTest(path=name):
                scrape._thread_local = threading.local()
                RecordingSession.reset(default_response=FakeResponse(body="<div>body text here</div>"))
                fetch()
                self.assertTrue(RecordingSession.calls, "no request was recorded")
                for call in RecordingSession.calls:
                    self.assertEqual(call["proxies"], EXPECTED_PROXIES,
                                     "request to %s left without the Tor proxy" % call["url"])
                for session in RecordingSession.created:
                    assert_hardened(self, session, name)


class TorReadiness(unittest.TestCase):
    """Tor is ready when its log says it bootstrapped, not when the port opens."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.logs = Path(tmp.name)

    def log(self, text):
        path = self.logs / ("tor-%d.log" % len(list(self.logs.iterdir())))
        path.write_text(text)
        return str(path)

    def test_the_bootstrap_log_decides(self):
        """A log without the 100% mark is not ready; no log or an unreadable one is."""
        for log, ready in ((None, True), ("", True), ("/nonexistent/tor-notices.log", True),
                           (self.log("[notice] Bootstrapped 75% (enough_dirinfo)\n"), False),
                           (self.log("[notice] Bootstrapped 100% (done): Done\n"), True)):
            with self.subTest(log):
                self.assertEqual(search.tor_bootstrapped(log), ready)

    def test_the_probe_needs_an_open_port_and_a_bootstrapped_log(self):
        """probe_tor and the health check both want the port and the log."""
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        self.addCleanup(sock.close)
        half = self.log("[notice] Bootstrapped 50% (loading_descriptors)\n")
        done = self.log("[notice] Bootstrapped 100% (done): Done\n")
        port = sock.getsockname()[1]
        self.assertFalse(mcp_server.probe_tor(port=port, bootstrap_log=half))
        self.assertTrue(mcp_server.probe_tor(port=port, bootstrap_log=done))
        self.assertFalse(mcp_server.probe_tor(port=1, bootstrap_log=done))
        for log, status in ((half, "starting"), (done, "up")):
            with mock.patch.object(health.socket, "create_connection",
                                   lambda *a, **k: mock.MagicMock()), \
                    mock.patch.dict(os.environ, {"ROBIN_TOR_LOG": log}):
                self.assertEqual(health.check_tor_proxy()["status"], status)


if __name__ == "__main__":
    unittest.main()
