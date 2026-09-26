"""run_investigation, driven with the LLM and the network stubbed out."""
import contextlib
import json
import os
import unittest
from tempfile import TemporaryDirectory
from unittest import mock

import httpx
import openai

import llm
import pipeline
import search
import store
from prompts import PRESETS
from tests.stubs import quiet_logger, search_outcome


RESULTS = [
    {"title": "Leak listing %d" % i, "link": "http://abcdefghij23456%d.onion/t" % i}
    for i in range(1, 9)
]

SCRAPED = {"http://abcdefghij234561.onion/t": "page one body",
           "http://abcdefghij234562.onion/t": "page two body"}

STAGES = ["load_llm", "refine", "search", "filter", "scrape", "summarize", "pivots", "save"]


class StubLLM:
    """A chat client that only has to hold callbacks, like the real one."""

    def __init__(self, name="stub-model"):
        self.name = name
        self.callbacks = []


def streaming_summary(text="## Findings\n- a finding", chunks=("## Findings\n", "- a finding")):
    """A `generate_summary` that streams `chunks` through the attached handler and returns `text`."""

    def _generate(llm, query, content, preset="threat_intel", custom_instructions=""):
        for handler in getattr(llm, "callbacks", []):
            for chunk in chunks:
                handler.on_llm_new_token(chunk)
            handler.on_llm_end(None)
        return text

    return _generate


def silent_summary(text):
    """A `generate_summary` that streams nothing and returns `text`, like a reasoning model."""
    return lambda *args, **kwargs: text


def _boom(*args, **kwargs):
    raise RuntimeError("provider said no")


class PipelineTestCase(unittest.TestCase):
    """Every LLM call stubbed; search and scrape injected; saves go to a temp dir."""

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name + "/investigations"
        self.stages = []
        self.tokens = []
        self.search_calls = []
        self.scrape_calls = []
        self.filter_calls = []
        self.results = list(RESULTS)
        self.stats = {}
        self.filtered = RESULTS[:2]
        self.scraped = dict(SCRAPED)
        self.generate = streaming_summary()

        for name, stub in (
                ("get_llm", lambda model, cfg=None: StubLLM(model)),
                ("refine_query", lambda llm, query: query + " dump"),
                ("filter_results", self._filter),
                ("generate_summary", lambda *a, **k: self.generate(*a, **k)),
                ("suggest_pivots", lambda *a, **k: ["acme vendor leak"])):
            patcher = mock.patch.object(pipeline, name, side_effect=stub)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _filter(self, llm, query, results, limit=20):
        self.filter_calls.append({"results": list(results), "limit": limit})
        return list(self.filtered)

    def _search(self, refined_query, threads):
        self.search_calls.append((refined_query, threads))
        return search_outcome(self.results, **self.stats)

    def _scrape(self, filtered, threads, content_chars):
        self.scrape_calls.append((list(filtered), threads, content_chars))
        return dict(self.scraped)

    def run_it(self, **overrides):
        kwargs = dict(
            cfg=None, query="acme breach", model="stub-model",
            preset="threat_intel", custom_instructions="",
            max_results=50, max_scrape=10, content_chars=8000, threads=4,
            on_stage=lambda name, inv: self.stages.append(name),
            on_token=self.tokens.append,
            search_fn=self._search, scrape_fn=self._scrape,
            investigations_dir=self.dir,
        )
        kwargs.update(overrides)
        return pipeline.run_investigation(**kwargs)


class ACompletedRun(PipelineTestCase):
    """A run that finds, reads and summarizes pages."""

    def test_it_carries_its_work_and_the_settings_it_ran_with(self):
        inv = self.run_it(on_stage=None, on_token=None,
                          max_results=30, max_scrape=5, content_chars=12000, threads=8)
        self.assertEqual(inv.status, pipeline.STATUS_OK)
        self.assertEqual(
            (inv.query, inv.refined, inv.results, inv.filtered, inv.scraped,
             inv.summary, inv.pivots, inv.model, inv.preset),
            ("acme breach", "acme breach dump", RESULTS, RESULTS[:2], SCRAPED,
             "## Findings\n- a finding", ["acme vendor leak"], "stub-model", "threat_intel"))
        self.assertEqual((inv.max_results, inv.max_scrape, inv.content_chars, inv.threads),
                         (30, 5, 12000, 8))
        self.assertTrue(inv.started_at)
        self.assertLessEqual(inv.started_at, inv.finished_at)
        self.assertEqual(self.search_calls, [("acme breach dump", 8)])

    def test_each_stage_is_announced_in_order_with_the_work_done_before_it(self):
        seen = []
        self.run_it(on_stage=lambda name, inv: seen.append(
            (name, inv.refined, len(inv.results), len(inv.filtered))))
        self.assertEqual([entry[0] for entry in seen], STAGES)
        self.assertEqual(seen[:5], [("load_llm", "", 0, 0),
                                    ("refine", "", 0, 0),
                                    ("search", "acme breach dump", 0, 0),
                                    ("filter", "acme breach dump", 8, 0),
                                    ("scrape", "acme breach dump", 8, 2)])

    def test_the_depth_settings_cap_and_reach_every_stage(self):
        self.results = RESULTS * 20
        self.filtered = list(RESULTS)
        inv = self.run_it(max_results=12, max_scrape=3, content_chars=15000, threads=7)
        self.assertEqual(len(self.filter_calls[0]["results"]), 12)
        self.assertEqual(len(inv.results), 12)
        self.assertEqual(self.filter_calls[0]["limit"], 3)
        self.assertEqual(len(self.scrape_calls[0][0]), 3)
        self.assertEqual(len(inv.filtered), 3)
        self.assertEqual(self.scrape_calls[0][1:], (7, 15000))
        self.assertEqual(self.search_calls[0][1], 7)

    def test_without_injected_callables_it_uses_the_core_search_and_scrape(self):
        with mock.patch.object(pipeline, "get_search_results_detailed",
                               return_value=search_outcome(RESULTS)) as searched, \
                mock.patch.object(pipeline, "scrape_multiple", return_value={}) as scraped:
            self.run_it(search_fn=None, scrape_fn=None, threads=3, content_chars=9000)
        searched.assert_called_once_with("acme breach dump", max_workers=3)
        scraped.assert_called_once_with(RESULTS[:2], max_workers=3, max_return_chars=9000)

    def test_the_summary_is_the_stream_or_else_the_return_value(self):
        cases = [  # (case, generate_summary, summary, what the token callback saw)
            ("streamed", streaming_summary(), "## Findings\n- a finding",
             "## Findings\n- a finding"),
            ("nothing streamed", silent_summary("returned"), "returned", ""),
            ("both", streaming_summary("returned", ("streamed ", "text")),
             "streamed text", "streamed text"),
            ("whitespace streamed", streaming_summary("returned", ("  \n",)), "returned", "  \n"),
        ]
        for name, generate, summary, streamed in cases:
            with self.subTest(name):
                self.generate = generate
                self.tokens = []
                self.assertEqual(self.run_it(save=False).summary, summary)
                self.assertEqual("".join(self.tokens), streamed)

    def test_an_injected_factory_builds_both_clients_instead_of_get_llm(self):
        built = []

        def host_model():
            built.append(StubLLM("host"))
            return built[-1]

        self.assertEqual(self.run_it(llm_factory=host_model).status, pipeline.STATUS_OK)
        self.assertEqual(len(built), 2, "one client for the summary, a fresh one for pivots")
        pipeline.get_llm.assert_not_called()


class ARunThatStopsEarly(PipelineTestCase):
    """Each empty stage ends the run with its own status, no summary and no save."""

    def assertStopsAt(self, status, last_stage):
        inv = self.run_it()
        self.assertEqual(inv.status, status)
        self.assertEqual(self.stages, STAGES[:STAGES.index(last_stage) + 1])
        self.assertEqual(inv.summary, "")
        self.assertTrue(inv.finished_at)
        self.assertIsNone(inv.saved_as)
        self.assertFalse(os.path.exists(self.dir), "an empty run was saved")
        return inv

    def test_no_results(self):
        self.results = []
        self.assertEqual(self.assertStopsAt("no_results", "search").refined, "acme breach dump")

    def test_engines_unreachable(self):
        self.results, self.stats = [], {"engines_empty": 0, "engines_failed": 16}
        self.assertStopsAt("engines_unreachable", "search")

    def test_nothing_relevant_keeps_the_raw_results(self):
        self.filtered = []
        self.assertEqual(self.assertStopsAt("nothing_relevant", "filter").results, RESULTS)

    def test_nothing_readable_keeps_what_the_filter_chose(self):
        self.scraped = {}
        inv = self.assertStopsAt("nothing_readable", "scrape")
        self.assertEqual((inv.filtered, inv.scraped), (RESULTS[:2], {}))


class ARunThatFails(PipelineTestCase):
    """A failed stage raises PipelineError naming the stage and carrying the error."""

    def test_every_stage_names_itself(self):
        cases = [
            ("load_llm", "load the selected LLM", "get_llm"),
            ("refine", "refine the query", "refine_query"),
            ("search", "search the dark web", "search_fn"),
            ("filter", "filter the search results", "filter_results"),
            ("scrape", "scrape the selected pages", "scrape_fn"),
            ("summarize", "generate the investigation summary", "generate_summary"),
        ]
        for stage, action, target in cases:
            with self.subTest(stage):
                if target.endswith("_fn"):
                    patch, kwargs = contextlib.nullcontext(), {target: _boom}
                else:
                    patch, kwargs = mock.patch.object(pipeline, target, side_effect=_boom), {}
                with patch, self.assertRaises(pipeline.PipelineError) as caught:
                    self.run_it(**kwargs)
                error = caught.exception
                self.assertEqual((error.stage, error.action), (stage, action))
                self.assertIsInstance(error.original, RuntimeError)
                self.assertIn("provider said no", str(error))

    def test_an_empty_report_fails_the_summarize_stage(self):
        self.generate = silent_summary("")
        with self.assertRaises(pipeline.PipelineError) as caught:
            self.run_it()
        self.assertEqual(caught.exception.stage, "summarize")

    def test_a_rate_limited_filter_fails_its_stage_instead_of_finding_nothing(self):
        def always_rate_limited(_messages):
            raise openai.RateLimitError(
                "rate limited", body=None,
                response=httpx.Response(429, request=httpx.Request("POST", "http://x")))

        quiet_logger(self, "root")
        with mock.patch.object(pipeline, "get_llm", return_value=always_rate_limited), \
                mock.patch.object(pipeline, "filter_results", llm.filter_results), \
                self.assertRaises(pipeline.PipelineError) as caught:
            self.run_it()
        self.assertEqual(caught.exception.stage, "filter")
        self.assertIsInstance(caught.exception.original, openai.RateLimitError)

    def test_failed_pivots_leave_a_finished_investigation(self):
        quiet_logger(self, "pipeline")
        with mock.patch.object(pipeline, "suggest_pivots", side_effect=_boom):
            inv = self.run_it()
        self.assertEqual((inv.status, inv.pivots), (pipeline.STATUS_OK, []))


class Saving(PipelineTestCase):
    """A finished run is saved through the store unless the caller saves it."""

    def test_a_finished_run_saves_its_record_where_it_was_asked_to(self):
        inv = self.run_it(preset_label="Custom label")
        self.assertEqual(os.listdir(self.dir), [inv.saved_as])
        saved = store.load_investigations(investigations_dir=self.dir)[0]
        self.assertEqual(saved.pop("_filename"), inv.saved_as)
        self.assertEqual(saved, inv.to_record())
        self.assertEqual(saved["preset"], "Custom label")

    def test_save_false_leaves_saving_to_the_caller(self):
        inv = self.run_it(save=False)
        self.assertEqual(inv.status, pipeline.STATUS_OK)
        self.assertIsNone(inv.saved_as)
        self.assertFalse(os.path.exists(self.dir))
        self.assertEqual(self.stages, STAGES[:-1])

    def test_a_failed_save_does_not_fail_the_investigation(self):
        quiet_logger(self, "store")
        with mock.patch.object(store.Path, "open",
                               side_effect=PermissionError(13, "Permission denied")):
            inv = self.run_it()
        self.assertEqual(inv.status, pipeline.STATUS_OK)
        self.assertIsNone(inv.saved_as)

    def test_to_record_keeps_the_original_keys_and_leaves_out_page_text(self):
        inv = self.run_it(preset="ransomware_malware", save=False)
        record = inv.to_record()
        self.assertEqual(list(record)[:7], ["timestamp", "query", "refined_query", "model",
                                            "preset", "sources", "summary"])
        self.assertEqual((record["timestamp"], record["finished_at"]),
                         (inv.started_at, inv.finished_at))
        self.assertEqual(record["preset"], PRESETS["ransomware_malware"][0])
        self.assertEqual(record["preset_key"], "ransomware_malware")
        self.assertEqual(record["sources"], RESULTS[:2])
        self.assertEqual((record["results_count"], record["scraped_count"]), (8, 2))
        self.assertNotIn("page one body", json.dumps(record))


class TheSearchLayerEncodesTheQuery(unittest.TestCase):
    """The pipeline hands the refined query over verbatim; the search layer encodes it."""

    def test_spaces_become_plus_and_reserved_characters_are_escaped(self):
        asked = []

        def fetch(endpoint, query):
            asked.append(query)
            return search._engine_record(endpoint, search.ENGINE_EMPTY, http_status=200)

        cases = {"acme breach dump": "acme+breach+dump",
                 "acme+breach": "acme%2Bbreach",
                 "acme & co": "acme+%26+co"}
        with mock.patch.object(search, "fetch_search_results_detailed", side_effect=fetch):
            for query, encoded in cases.items():
                with self.subTest(query):
                    asked.clear()
                    search.get_search_results_detailed(query, max_workers=2)
                    self.assertEqual(set(asked), {encoded})


if __name__ == "__main__":
    unittest.main()
