"""llm.py's selection parsing and prompts, and a core that never writes to stdout."""
import contextlib
import io
import tempfile
import unittest
from unittest import mock

import httpx
import openai

import llm
import model_registry
import prompts
from config import RobinConfig
from llm_utils import BufferedStreamingHandler
from tests.mcp_harness import results
from tests.stubs import quiet_logger

PRESET_KEYS = ("threat_intel", "ransomware_malware", "personal_identity", "corporate_espionage")


def selected(reply):
    """The indices the filter reads out of a model's reply."""
    return list(llm._iter_selected_indices(llm._strip_leading_label(reply)))


class TheSelectionIsParsed(unittest.TestCase):
    """A reply's labels, list markers and trailing prose never become selections."""

    def test_a_label_is_dropped_before_the_indices_are_read(self):
        """Only a leading label goes: a later labelled line or a trailing colon stays out."""
        for reply, expected in (
                ("Indices: 3, 9, 12\nReasoning: these match the 2024 breach", [3, 9, 12]),
                ("Selected: 3, 9\nNote: see http://abc.onion/page1", [3, 9]),
                ("Top 5 results, ranked by relevance: 3, 9, 12", [3, 9, 12]),
                ("Selected indices:\n1, 4, 9", [1, 4, 9]),
                ('{"indices": [2, 5, 9]}', [2, 5, 9]),
                ("1, 2, 3: my picks", [1, 2, 3])):
            with self.subTest(reply=reply):
                self.assertEqual(selected(reply), expected)

    def test_list_markers_are_not_indices_and_real_ranges_expand(self):
        """A bullet hyphen is not a range dash; a numbered list's ordinals are not picks."""
        for reply, expected in (
                ("- 3\n- 9\n- 12", [3, 9, 12]),
                ("1. 3\n2. 9\n3. 12", [3, 9, 12]),
                ("1. Index 3 - Forum thread\n2. Index 9 - Leak listing", [3, 9]),
                ("1-5", [1, 2, 3, 4, 5]),
                ("10 - 12", [10, 11, 12]),
                ("3, 9, 12", [3, 9, 12])):
            with self.subTest(reply=reply):
                self.assertEqual(list(llm._iter_selected_indices(reply)), expected)


class PromptsLiveInOneModule(unittest.TestCase):
    """llm.py sends the words prompts.py holds, so the MCP server serves the same ones."""

    def test_llm_uses_the_prompt_modules_own_objects(self):
        """Plain strings: the module imports no client library."""
        self.assertIs(llm.PRESET_PROMPTS, prompts.PRESET_PROMPTS)
        self.assertIs(llm.FOLLOWUP_SYSTEM, prompts.FOLLOWUP_SYSTEM)
        self.assertIs(llm.FOLLOWUP_PERSONAS, prompts.FOLLOWUP_PERSONAS)
        with open("prompts.py", encoding="utf-8") as handle:
            self.assertNotIn("langchain", handle.read())

    def test_every_preset_has_a_prompt_a_persona_and_a_sidebar_label(self):
        """The catalog is a one-line label and description per preset, in sidebar wording."""
        for table in (prompts.PRESET_PROMPTS, prompts.PRESETS, prompts.FOLLOWUP_PERSONAS):
            self.assertEqual(tuple(table), PRESET_KEYS)
        self.assertEqual([label for label, _ in prompts.PRESETS.values()],
                         ["🔍 Dark Web Threat Intel", "🦠 Ransomware / Malware Focus",
                          "👤 Personal / Identity Investigation",
                          "🏢 Corporate Espionage / Data Leaks"])
        for key, (label, description) in prompts.PRESETS.items():
            self.assertTrue(description.strip(), key)
            self.assertNotIn("\n", label + description, key)

    def test_each_prompt_keeps_its_substitution_points_and_grounding_rule(self):
        """The code fills these placeholders; without them a value silently goes missing."""
        for text, markers in (
                (prompts.FILTER_SYSTEM_PROMPT, ("{limit}", "Search Query: {query}")),
                (prompts.PIVOTS_SYSTEM_PROMPT, ("{max_pivots}", "INVESTIGATION QUERY: {query}")),
                (prompts.FOLLOWUP_SYSTEM, ("{persona}", "INVESTIGATION CONTEXT:")),
                *((text, ("0. STRICT GROUNDING:", "## Input Query\n    {query}"))
                  for text in prompts.PRESET_PROMPTS.values())):
            for marker in markers:
                self.assertIn(marker, text)


@contextlib.contextmanager
def captured():
    """Run a block with stdout and stderr captured separately."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def rate_limit_error():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai.RateLimitError("rate limited", response=httpx.Response(429, request=request),
                                 body=None)


class NothingReachesStdout(unittest.TestCase):
    """In MCP stdio mode stdout is the JSON-RPC wire, so the core never writes to it."""

    def test_the_streaming_handler_hands_every_chunk_to_the_ui_and_none_to_stdout(self):
        """Flushed on a newline, on the buffer limit and at the end; with or without a callback."""
        for seen, tokens in (([], ("line one\n", "some tokens here", "tail")),
                             (None, ("some tokens here",))):
            with self.subTest(callback=seen is not None):
                handler = BufferedStreamingHandler(
                    buffer_limit=8, ui_callback=None if seen is None else seen.append)
                with captured() as (out, err):
                    for token in tokens:
                        handler.on_llm_new_token(token)
                    handler.on_llm_end(None)
                self.assertEqual((out.getvalue(), err.getvalue()), ("", ""))
                if seen is not None:
                    self.assertEqual(seen, list(tokens))

    def test_the_filters_rate_limit_retry_logs_rather_than_prints(self):
        """One retry on truncated titles; a second 429 propagates rather than selecting nothing."""
        results = [{"link": "http://abcdefghij234567.onion/a", "title": "A leak listing"}]
        for failures in (1, 2):
            with self.subTest(failures=failures):
                calls = []

                def model(_messages):
                    calls.append(1)
                    if len(calls) <= failures:
                        raise rate_limit_error()
                    return "1"

                with captured() as (out, _), \
                        self.assertLogs("root", level="WARNING") as logged:
                    if failures == 2:
                        with self.assertRaises(openai.RateLimitError):
                            llm.filter_results(model, "query", results)
                    else:
                        self.assertEqual(llm.filter_results(model, "query", results), results)
                self.assertEqual(len(calls), 2)
                self.assertEqual(out.getvalue(), "")
                self.assertTrue(any("runcat" in line for line in logged.output))

    def test_a_verbose_registry_refresh_reports_on_stderr_only(self):
        """Quiet on both streams unless asked; progress and failures go to stderr."""
        def boom(cfg):
            raise RuntimeError("provider unreachable")

        quiet_logger(self, "model_registry")
        with tempfile.TemporaryDirectory() as cache_dir:
            cfg = RobinConfig(openai_api_key="sk-test", ollama_base_url=None, cache_dir=cache_dir)
            for fetch, verbose, reported in ((lambda c: ["model-a", "model-b"], True, "2 models"),
                                             (boom, True, "FAILED"),
                                             (lambda c: ["model-a"], False, None)):
                with self.subTest(reported=reported):
                    table = {"openai": {"fetch": fetch, "key": lambda c: c.openai_api_key}}
                    with mock.patch.object(model_registry, "PROVIDERS", table), \
                            captured() as (out, err):
                        model_registry.refresh(cfg, verbose=verbose)
                    self.assertEqual(out.getvalue(), "")
                    if reported:
                        self.assertIn("openai", err.getvalue())
                        self.assertIn(reported, err.getvalue())
                    else:
                        self.assertEqual(err.getvalue(), "")


class LlmFilterSelection(unittest.TestCase):
    """llm.filter_results, as the UI calls it, selects by the model's indices."""

    def fake_model(self, reply):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        return FakeListChatModel(responses=[reply])

    def test_the_ui_filter_is_the_detailed_selection(self):
        """filter_results returns what filter_results_detailed selects, in order and to the limit."""
        found = results(5)
        for reply in ("2, 4", "", "Top 2: 5, 1", "I cannot help with that."):
            self.assertEqual(
                llm.filter_results(self.fake_model(reply), "acme", found, limit=20),
                llm.filter_results_detailed(self.fake_model(reply), "acme", found, limit=20)[0])
        for reply, limit, expected in (("2, 4", 20, [found[1], found[3]]), ("", 20, []),
                                       ("5, 1, 3", 2, [found[4], found[0]])):
            self.assertEqual(llm.filter_results(self.fake_model(reply), "acme", found,
                                                limit=limit), expected)
        self.assertEqual(llm.filter_results(self.fake_model("1"), "acme", []), [])

    def test_the_detailed_variant_reports_the_reply_and_reads_long_ranges(self):
        """The raw reply comes back, and a range of 101 selects all 101."""
        found = results(3)
        self.assertEqual(llm.filter_results_detailed(self.fake_model("sorry, no"), "acme",
                                                     found), ([], "sorry, no"))
        self.assertEqual(llm.filter_results_detailed(self.fake_model("x"), "acme", []),
                         ([], None))
        many = results(101)
        selected, _ = llm.filter_results_detailed(self.fake_model("1-101"), "acme", many,
                                                  limit=101)
        self.assertEqual(len(selected), 101)


if __name__ == "__main__":
    unittest.main()
