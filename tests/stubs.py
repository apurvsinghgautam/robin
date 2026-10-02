"""Shared stubs for the scrape, search, Tor and fencing tests.

Nothing here talks to the network beyond 127.0.0.1. `RecordingSession` stands
in for `requests.Session` so a test can assert what a module built and what it
would have sent, which is the only honest way to test an invariant about proxies.
"""
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, List, Optional
from unittest import mock

import httpx
import openai
import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

import scrape
import search


def quiet_logger(testcase, name):
    """Mute a logger for one test; `assertLogs` still sees what it asks for."""
    logger = logging.getLogger(name)
    previous = logger.level
    logger.setLevel(logging.CRITICAL)
    testcase.addCleanup(logger.setLevel, previous)


class FakeResponse:
    """The narrow slice of `requests.Response` that scrape.py actually uses."""

    def __init__(self, status_code=200, body="", content_type="text/html; charset=utf-8",
                 encoding="utf-8", headers=None):
        self.status_code = status_code
        self.headers = {"Content-Type": content_type} if content_type else {}
        self.headers.update(headers or {})
        self.encoding = encoding
        self._body = body.encode(encoding or "utf-8") if isinstance(body, str) else body
        self.text = body if isinstance(body, str) else body.decode("utf-8", "replace")
        self.closed = False

    @property
    def content(self):
        return self._body

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        self.closed = True


class RecordingSession(requests.Session):
    """A real Session that records itself and never reaches the network.

    Subclassing keeps `mount`, adapters and `proxies` behaving exactly as the
    production code expects, so the proxy assertions are about the real object.
    """

    created = []
    calls = []
    routes = {}
    default_response = None

    def __init__(self):
        super().__init__()
        RecordingSession.created.append(self)

    @classmethod
    def reset(cls, routes=None, default_response=None):
        cls.created = []
        cls.calls = []
        cls.routes = dict(routes or {})
        cls.default_response = default_response

    def get(self, url, **kwargs):
        RecordingSession.calls.append({
            "url": url,
            "proxies": dict(self.proxies),
            "kwargs": kwargs,
        })
        response = RecordingSession.routes.get(url, RecordingSession.default_response)
        if response is None:
            raise requests.exceptions.ConnectionError("no route stubbed for %s" % url)
        if isinstance(response, Exception):
            # A route can be a transport failure rather than a reply.
            raise response
        return response

    def request(self, method, url, **kwargs):  # pragma: no cover - guard
        raise AssertionError("a test let a real request escape: %s %s" % (method, url))


def record_sessions(testcase, routes=None, default_response=None):
    """Build every `requests.Session` as a RecordingSession for one test.

    Also drops scrape's per-thread session cache, so no session built before
    the patch is reused, and mutes the scrape logger.
    """
    scrape._thread_local = threading.local()
    testcase.addCleanup(setattr, scrape, "_thread_local", threading.local())
    quiet_logger(testcase, "scrape")
    RecordingSession.reset(routes=routes, default_response=default_response)
    patcher = mock.patch("requests.Session", RecordingSession)
    patcher.start()
    testcase.addCleanup(patcher.stop)


def search_outcome(results, **stats):
    """What `search.get_search_results_detailed` returns, for a stubbed search."""
    engines = {"engines_queried": 16, "engines_answered": 16 if results else 0,
               "engines_empty": 0 if results else 16, "engines_failed": 0}
    engines.update(stats)
    return {"results": list(results), "stats": engines}


class LocalServer:
    """A real HTTP server on 127.0.0.1, for tests that count bytes on the wire.

    `routes` maps a path prefix to ``(status, headers, chunks)``, where `chunks`
    returns the body as an iterable of bytes. `written(path)` waits for that
    response to end and returns how many body bytes the server got out.
    """

    def __init__(self, routes):
        self.sent = {}
        self.ended = threading.Condition()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                status, headers, chunks = next(
                    route for prefix, route in routes.items() if self.path.startswith(prefix))
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                count = 0
                try:
                    for chunk in chunks():
                        self.wfile.write(chunk)
                        count += len(chunk)
                except OSError:
                    pass
                finally:
                    with server.ended:
                        server.sent[self.path] = count
                        server.ended.notify_all()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def written(self, path, timeout=10):
        with self.ended:
            self.ended.wait_for(lambda: path in self.sent, timeout)
        return self.sent[path]

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


BIG_BODY_BYTES = 64 * 1024 * 1024


def big_route(status=200, head=b"", **headers):
    """A LocalServer route whose body is BIG_BODY_BYTES long and starts with `head`."""
    filler = b"<p>" + b"filler " * 9000 + b"</p>"

    def chunks():
        yield head
        left = BIG_BODY_BYTES - len(head)
        while left > 0:
            piece = filler[:left]
            yield piece
            left -= len(piece)

    headers = dict({"Content-Type": "text/html; charset=utf-8",
                    "Content-Length": str(BIG_BODY_BYTES)}, **headers)
    return status, headers, chunks


def unproxied(session, seen):
    """A real Tor session with its proxy removed, so it reaches 127.0.0.1.

    Every response it receives is appended to `seen`.
    """
    session.proxies = {}
    real_send = session.send

    def send(request, **kwargs):
        response = real_send(request, **kwargs)
        seen.append(response)
        return response

    session.send = send
    return session


# Every message CapturingChatModel is sent, one list of contents per call.
RECEIVED: List[List[str]] = []
# Put one item in to make the next filter call raise RateLimitError once.
RATE_LIMIT_FILTER_ONCE: List[bool] = []


class CapturingChatModel(BaseChatModel):
    """Answers each Robin prompt plausibly and keeps every message it got."""

    @property
    def _llm_type(self) -> str:
        return "capturing-fake"

    def _generate(self, messages, stop: Optional[List[str]] = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        contents = [str(m.content) for m in messages]
        RECEIVED.append(contents)
        system = contents[0] if contents else ""
        if "Search Query Expert" in system:
            reply = "acme leak"
        elif "Search Result Analyst" in system:
            if RATE_LIMIT_FILTER_ONCE:
                RATE_LIMIT_FILTER_ONCE.pop()
                raise openai.RateLimitError(
                    "slow down", body=None,
                    response=httpx.Response(429, request=httpx.Request("POST", "http://x")))
            reply = "1, 2"
        elif "SEARCH QUERIES" in system:
            reply = '["acme pivot"]'
        else:
            reply = "## Findings\n- a finding"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=reply))])


def engine_records(links_per_engine):
    """A fetch_search_results_detailed stub: engine i returns links_per_engine[i]."""
    endpoints = list(search.DEFAULT_SEARCH_ENGINES)

    def fetch(endpoint, query):
        index = endpoints.index(endpoint)
        links = links_per_engine[index] if index < len(links_per_engine) else []
        return search._engine_record(
            endpoint, search.ENGINE_OK if links else search.ENGINE_EMPTY, links=links)
    return fetch
