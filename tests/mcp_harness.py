"""Shared plumbing for the MCP server tests.

Every test drives the real server through the SDK's in-memory client, so what
is asserted is what a host receives. Nothing talks to Tor, a search engine or
a provider: the server is built with stub callables in place of each.
"""
import functools
import json
import re
import tempfile

import anyio
import mcp.types as mcp_types
from mcp.shared.memory import create_connected_server_and_client_session as connect

import config
import mcp_server
import pipeline
from tests.stubs import search_outcome


def run(async_fn, *args, **kwargs):
    """Run one async test body. `anyio.run` wants a zero-argument callable."""
    return anyio.run(functools.partial(async_fn, *args, **kwargs))


def text_of(result):
    """The text a tool call returned, joined across content blocks."""
    return "\n".join(block.text for block in result.content
                     if getattr(block, "type", "") == "text")


OPEN_FENCE = "<<<ROBIN_UNTRUSTED_CONTENT"
CLOSE_FENCE = "<<<END_ROBIN_UNTRUSTED_CONTENT>>>"


def outside_fences(text):
    """Everything in `text` that is not between untrusted-data delimiters.

    An unclosed fence fails loudly rather than counting its tail as fenced.
    """
    outside = []
    rest = text
    while OPEN_FENCE in rest:
        before, _, after = rest.partition(OPEN_FENCE)
        outside.append(before)
        if CLOSE_FENCE not in after:
            raise AssertionError("an untrusted-data fence is never closed")
        rest = after.partition(CLOSE_FENCE)[2]
    outside.append(rest)
    return "".join(outside)


ONION = "http://abcdefghij23456{}.onion/t"


def results(count=3):
    return [{"title": "Leak listing %d" % i, "link": ONION.format(i)}
            for i in range(1, count + 1)]


def scraped_records(count=3, body="page body", status="ok"):
    return {
        ONION.format(i): {
            "status": status,
            "title": "Leak listing %d" % i,
            "text": body,
            "http_status": 200,
            "detail": "",
        }
        for i in range(1, count + 1)
    }


class StubDeps:
    """Everything the server would otherwise reach the world for."""

    def __init__(self, **overrides):
        self.search_calls = []
        self.scrape_calls = []
        self.run_calls = []
        self.filter_calls = []
        self.refine_calls = []
        self.llm_calls = []
        # What the stub filter keeps: None keeps every result, a list keeps
        # those 1-based positions, in that order. `filter_reply` is the raw
        # reply it reports; None stands for "no model answered".
        self.keep = None
        self.filter_reply = "1"
        self.refined = "acme breach leak"
        self.results = results()
        self.records = scraped_records()
        self.tor_up = True
        self.models = ["gpt-4o", "claude-sonnet-4"]
        self.llm_health = {"status": "up", "latency_ms": 12, "error": None,
                           "provider": "OpenAI"}
        self.investigation = None
        self.__dict__.update(overrides)

    def search_fn(self, query, threads):
        self.search_calls.append((query, threads))
        return search_outcome(self.results)

    def scrape_fn(self, targets, threads, content_chars, allow_clearweb):
        self.scrape_calls.append({
            "targets": list(targets), "threads": threads,
            "content_chars": content_chars, "allow_clearweb": allow_clearweb,
        })
        return dict(self.records)

    def run_fn(self, **kwargs):
        self.run_calls.append(dict(kwargs))
        if self.investigation is None:
            raise AssertionError("test did not provide an investigation")
        return self.investigation

    def filter_fn(self, model, query, results, limit):
        self.filter_calls.append({"model": model, "query": query,
                                  "results": list(results), "limit": limit})
        if self.keep is None:
            kept = list(results)
        else:
            kept = [results[i - 1] for i in self.keep if 1 <= i <= len(results)]
        return kept, self.filter_reply

    def refine_fn(self, model, question):
        self.refine_calls.append({"model": model, "question": question})
        return self.refined

    def get_llm_fn(self, name, cfg):
        self.llm_calls.append(name)
        return ("stub-model", name)

    def tor_probe(self):
        return self.tor_up

    def model_choices_fn(self, cfg):
        return list(self.models)

    def llm_health_fn(self, model, cfg):
        return dict(self.llm_health)


# robin_search runs only on a research domain the user chose. Most tests are
# about something else, so by default the server runs as if the user had set
# ROBIN_DEFAULT_PRESET, which is one of the ways a user chooses.
DEFAULT_TEST_PRESET = "threat_intel"


def test_cfg(domain_chosen=True, **env):
    """A config read from `env` alone, never from the machine running tests."""
    if domain_chosen:
        env.setdefault("ROBIN_DEFAULT_PRESET", DEFAULT_TEST_PRESET)
    return config.RobinConfig.from_env(env={k: str(v) for k, v in env.items()})


# Removed when the test run ends; each server gets its own empty folder in it.
_SCRATCH = tempfile.TemporaryDirectory(prefix="robin-mcp-tests-")


def build(deps=None, cfg=None, domain_chosen=True, **kwargs):
    """A server wired to stubs, saving to a fresh temporary directory."""
    deps = deps if deps is not None else StubDeps()
    if cfg is None:
        cfg = test_cfg(domain_chosen)
    kwargs.setdefault("investigations_dir", tempfile.mkdtemp(dir=_SCRATCH.name))
    kwargs.setdefault("filter_fn", deps.filter_fn)
    kwargs.setdefault("refine_fn", deps.refine_fn)
    kwargs.setdefault("get_llm_fn", deps.get_llm_fn)
    server = mcp_server.build_server(
        cfg,
        search_fn=deps.search_fn,
        scrape_fn=deps.scrape_fn,
        run_fn=deps.run_fn,
        tor_probe=deps.tor_probe,
        model_choices_fn=deps.model_choices_fn,
        llm_health_fn=deps.llm_health_fn,
        **kwargs,
    )
    return server, deps


def served_tools(server):
    """The tools a host lists, by name."""
    async def body():
        async with connect(server) as session:
            return {t.name: t for t in (await session.list_tools()).tools}
    return run(body)


def tool_schema(server, name):
    """The input schema the server serves for one tool, as a dict."""
    return json.loads(json.dumps(served_tools(server)[name].inputSchema))


def call(server, name, arguments=None, **client_kwargs):
    """Call one tool through an in-memory client and return the CallToolResult."""
    async def body():
        async with connect(server, **client_kwargs) as session:
            return await session.call_tool(name, arguments or {})
    return run(body)


# A result id as robin_search prints it, such as `[r1-3fa9c2]`.
RESULT_ID = re.compile(r"\[(r\d+(?:-[0-9a-f]+)?)\]")


def result_ids(text):
    """The result ids in a robin_search reply, in listing order."""
    return RESULT_ID.findall(text)


# How Claude Code names itself at initialize.
CLAUDE_CODE = mcp_types.Implementation(name="claude-code", version="2.1.278")


def sampling_client(*replies, seen=None):
    """Client kwargs for a host that offers sampling and answers with `replies`
    in turn, repeating the last; `seen` collects each request."""
    replies = list(replies or ["a sampled answer"])

    async def sampling_callback(context, params):
        if seen is not None:
            seen.append(params)
        text = replies.pop(0) if len(replies) > 1 else replies[0]
        return mcp_types.CreateMessageResult(
            role="assistant", content=mcp_types.TextContent(type="text", text=text),
            model="host-model")
    return {"sampling_callback": sampling_callback}


def refusing_sampling_client():
    """Client kwargs for a host that offers sampling and then refuses the request."""
    async def sampling_callback(context, params):
        return mcp_types.ErrorData(code=-1, message="User rejected sampling request")
    return {"sampling_callback": sampling_callback}


def elicitation_client(action="accept", content=None, seen=None):
    """Client kwargs for a host that can ask its user, answering with `action`."""
    async def elicitation_callback(context, params):
        if seen is not None:
            seen.append(params)
        return mcp_types.ElicitResult(action=action, content=content)
    return {"elicitation_callback": elicitation_callback}


def search_then_scrape(server, pick, scrape_args=None, query="acme breach",
                       filter_first=True, **client_kwargs):
    """Run robin_search, robin_filter and robin_scrape in one client session."""
    async def body():
        async with connect(server, **client_kwargs) as session:
            found = text_of(await session.call_tool("robin_search", {"query": query}))
            ids = result_ids(found)
            if filter_first:
                await session.call_tool("robin_filter", {"query": query})
            chosen = pick(ids) if callable(pick) else [ids[i - 1] for i in pick]
            arguments = dict(scrape_args or {})
            arguments["ids"] = chosen
            return ids, await session.call_tool("robin_scrape", arguments)
    return run(body)


def session_run(server, steps, **client_kwargs):
    """Run (tool, arguments) steps in one session and return each reply's text.

    An argument given as a callable is called with the latest search's ids.
    """
    async def body():
        texts, ids = [], []
        async with connect(server, **client_kwargs) as session:
            for name, arguments in steps:
                arguments = {k: (v(ids) if callable(v) else v)
                             for k, v in dict(arguments).items()}
                text = text_of(await session.call_tool(name, arguments))
                if name == "robin_search":
                    ids = result_ids(text)
                texts.append(text)
        return texts
    return run(body)


def an_investigation(**overrides):
    inv = pipeline.Investigation(
        query="acme breach",
        status=pipeline.STATUS_OK,
        refined="acme breach dump",
        results=results(5),
        filtered=results(2),
        scraped={"http://abcdefghij234561.onion/t": "page body"},
        summary="## Key Insights\n- acme data is for sale",
        pivots=["acme vendor leak"],
        model="stub-model",
        preset="threat_intel",
        started_at="2026-09-18T12:00:00",
        finished_at="2026-09-18T12:04:00",
    )
    for key, value in overrides.items():
        setattr(inv, key, value)
    return inv


def args(**overrides):
    """robin_save_investigation arguments for a small, valid report."""
    base = {
        "query": "acme breach",
        "preset": "threat_intel",
        "summary": "## Key Insights\n- acme customer data is listed for sale",
        "sources": [{"title": "Acme dump", "link": "http://abcdefghij234561.onion/t"}],
        "refined_query": "acme breach dump",
        "pivots": ["acme vendor leak"],
    }
    base.update(overrides)
    return base


def fenced_record(text):
    """The JSON record inside a resource body's untrusted-data fence."""
    inside = text.split(OPEN_FENCE, 1)[1].split(CLOSE_FENCE, 1)[0]
    return json.loads(inside[inside.index("{"):inside.rindex("}") + 1])
