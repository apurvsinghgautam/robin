"""Adversarial reports must preserve source provenance without releasing model prose."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

import evidence
import llm
import pipeline
import store
from config import RobinConfig
from llm_utils import BufferedStreamingHandler
from prompts import preset_sections, PRESET_PROMPTS
from tests.model_smoke import CVE, EMAIL, HASH, PAGES, QUERY, SOURCE, FOLLOWUP_SOURCE


def selection(keys=(), **extra):
    return json.dumps({"sections": {"Key Insights": list(keys)}, "next_steps": [], **extra})


class SourceMappings(unittest.TestCase):
    def test_a_hash_is_not_attributed_to_the_page_that_only_repeats_the_cve(self):
        index = evidence.build_evidence(PAGES.items())
        report, check = evidence.render_report(QUERY, selection(index["passages"]), index)
        mappings = {item["value"]: item["sources"] for item in check["artifact_sources"]}
        self.assertEqual(mappings[HASH], [SOURCE])
        self.assertEqual(mappings[CVE], [SOURCE, FOLLOWUP_SOURCE])
        self.assertEqual(mappings[EMAIL], [SOURCE, FOLLOWUP_SOURCE])
        self.assertIn("Sample SHA-256: " + HASH, report)
        self.assertNotIn("proof of concept", report)

    def test_query_only_identifiers_are_never_discovered_artifacts(self):
        index = evidence.build_evidence([(SOURCE, "Contact: " + EMAIL + ".")])
        report, check = evidence.render_report(QUERY, selection(index["passages"]), index)
        self.assertEqual([item["value"] for item in check["artifact_sources"]], [EMAIL])
        artifacts = report.split("## Investigation Artifacts", 1)[1].split("## Key Insights", 1)[0]
        self.assertNotIn(CVE, artifacts)
        self.assertNotIn(HASH, artifacts)

    def test_ethereum_is_not_a_sha1_and_invalid_ipv4_is_not_an_indicator(self):
        wallet = "0x" + "a" * 40
        found = evidence.extract_artifacts(wallet + " 999.8.7.6 192.0.2.4")
        self.assertEqual(found, [("IPv4", "192.0.2.4"), ("Ethereum address candidate", wallet)])

    def test_passages_are_exact_contiguous_excerpts_and_ids_are_stable(self):
        text = ("A paragraph with contextual evidence. " * 100) + " Contact: " + EMAIL
        first = evidence.build_evidence([(SOURCE, text)])
        second = evidence.build_evidence([(SOURCE, text)])
        self.assertEqual(first, second)
        self.assertGreater(len(first["passages"]), 1)
        for item in first["passages"].values():
            self.assertIn(item["quote"], text)
            self.assertLessEqual(len(item["quote"]), evidence.PASSAGE_CHARS)

    def test_rereading_changed_content_cannot_reuse_old_evidence_ids(self):
        old = evidence.build_evidence([(SOURCE, "Original source passage.")])
        new = evidence.build_evidence([(SOURCE, "Changed source passage.")])
        report, check = evidence.render_report("query", selection(old["passages"]), new)
        self.assertEqual(check["accepted_findings"], 0)
        self.assertEqual(check["rejected"], {"unknown_evidence": 1})
        self.assertNotIn("Original source passage", report)
        self.assertNotIn("Changed source passage", report)


class UntrustedSelections(unittest.TestCase):
    def setUp(self):
        self.index = evidence.build_evidence(PAGES.items())
        self.keys = list(self.index["passages"])

    def test_forged_quotations_sources_and_relationship_prose_are_not_rendered(self):
        fabricated = "The hash is an exploit payload for " + CVE
        attack = {"evidence_id": self.keys[0], "quote": fabricated,
                  "source_url": FOLLOWUP_SOURCE, "claim": fabricated}
        report, check = evidence.render_report(
            QUERY, selection([self.keys[0], attack, "unknown-id"], claim=fabricated), self.index)
        self.assertNotIn(fabricated, report)
        self.assertEqual(check["rejected"], {"unknown_evidence": 2})
        self.assertEqual(check["accepted_findings"], 1)

    def test_malformed_or_ambiguous_json_fails_closed(self):
        for raw in ("## Key Insights\nThe hash is malicious.", "{}", "[]",
                    '{"sections":{},"sections":{"Key Insights":[]},"next_steps":[]}',
                    '{"sections":{},"next_steps":"Search for proof"}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                evidence.render_report(QUERY, raw, self.index)

    def test_fences_duplicates_unknown_sections_and_insight_limits(self):
        raw = '{"sections":{"Key Insights":["' + self.keys[0] + '","' + self.keys[0] + '"],"Invented Relationship":["' + self.keys[0] + '"]},"next_steps":[]}'
        report, check = evidence.render_report(QUERY, "```json\n" + raw + "\n```", self.index)
        self.assertEqual(check["accepted_findings"], 1)
        self.assertEqual(check["rejected"], {"invalid_section": 1})
        self.assertNotIn("Invented Relationship", report)

    def test_proposed_actions_cannot_introduce_fabricated_identifiers(self):
        raw = selection(next_steps=["Search " + CVE, "Search CVE-2026-99999", "Contact forged@example.net"])
        report, check = evidence.render_report(QUERY, raw, self.index)
        self.assertIn("Search " + CVE, report)
        self.assertNotIn("CVE-2026-99999", report)
        self.assertNotIn("forged@example.net", report)
        self.assertEqual(check["rejected"], {"invented_next_step_artifact": 2})

    def test_all_presets_keep_their_headings_and_empty_sections(self):
        for preset in PRESET_PROMPTS:
            with self.subTest(preset=preset):
                report, _ = evidence.render_report("target", selection(), self.index, preset)
                self.assertEqual([line for line in report.splitlines() if line.startswith("## ")],
                                 preset_sections(preset))
                self.assertIn("Not established by the supplied excerpts.", report)

    def test_source_markdown_cannot_create_report_sections_or_html(self):
        page = "<script>bad()</script>\n## Invented Relationship\n[Click](https://evil.example)"
        index = evidence.build_evidence([(SOURCE, page)])
        report, _ = evidence.render_report("target", selection(index["passages"]), index)
        self.assertNotIn("<script>", report)
        self.assertNotIn("\n## Invented Relationship", report)
        self.assertNotIn("[Click](https://evil.example)", report)
        self.assertIn("&lt;script&gt;", report)

    def test_oversized_reports_fail_instead_of_silently_cutting_evidence(self):
        with self.assertRaisesRegex(ValueError, "save limit"):
            evidence.render_report("q" * evidence.MAX_REPORT_CHARS, selection(), self.index)

    def test_insight_limit_omits_whole_passages(self):
        index = evidence.build_evidence([("source-" + str(i), "complete passage " + str(i)) for i in range(7)])
        report, check = evidence.render_report("query", selection(index["passages"]), index)
        self.assertEqual(check["accepted_findings"], 5)
        self.assertEqual(check["rejected"], {"section_limit": 2})
        self.assertNotIn("complete passage 5", report)
        self.assertNotIn("complete passage 6", report)


class DraftModel(BaseChatModel):
    reply: str
    calls: int = 0

    @property
    def _llm_type(self):
        return "draft-test"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        if run_manager:
            run_manager.on_llm_new_token("UNCHECKED HASH EXPLOIT CLAIM\n")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.reply))])


class BeforeRelease(unittest.TestCase):
    def test_one_call_returns_checked_markdown_and_restores_without_releasing_callbacks(self):
        seen = []
        handler = BufferedStreamingHandler(ui_callback=seen.append)
        keys = evidence.build_evidence(PAGES.items())["passages"]
        model = DraftModel(reply=selection(keys), callbacks=[handler])
        report, check = llm.generate_summary_detailed(model, QUERY, PAGES)
        self.assertEqual(model.calls, 1)
        self.assertEqual(seen, [])
        self.assertEqual(model.callbacks, [handler])
        self.assertNotIn("UNCHECKED", report)
        self.assertEqual(check["status"], "source_matched")

    def test_pipeline_releases_and_saves_only_the_grounded_report(self):
        seen = []
        model = DraftModel(reply=selection(evidence.build_evidence(PAGES.items())["passages"]))
        results = [{"link": link, "title": "Public synthetic source"} for link in PAGES]
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(pipeline, "refine_query", return_value=QUERY), \
                mock.patch.object(pipeline, "filter_results", return_value=results), \
                mock.patch.object(pipeline, "suggest_pivots", return_value=[]):
            inv = pipeline.run_investigation(
                RobinConfig(), QUERY, "synthetic", llm_factory=lambda: model,
                search_fn=lambda *a: {"results": results, "stats": {}},
                scrape_fn=lambda *a: PAGES, on_token=seen.append, investigations_dir=folder)
            saved = store.load_investigations(folder)[0]
            self.assertEqual(seen, [inv.summary])
            self.assertEqual(saved["summary"], inv.summary)
            self.assertEqual(saved["evidence_check"], inv.evidence_check)
            self.assertNotIn("scraped", saved)
            self.assertEqual(model.calls, 1)
            self.assertNotIn("UNCHECKED", json.dumps(saved))

    def test_bad_selection_is_neither_displayed_nor_saved(self):
        seen = []
        model = DraftModel(reply="The hash is an exploit payload.")
        results = [{"link": SOURCE, "title": "Synthetic source"}]
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(pipeline, "refine_query", return_value=QUERY), \
                mock.patch.object(pipeline, "filter_results", return_value=results):
            with self.assertRaises(pipeline.PipelineError) as failed:
                pipeline.run_investigation(
                    RobinConfig(), QUERY, "synthetic", llm_factory=lambda: model,
                    search_fn=lambda *a: {"results": results, "stats": {}},
                    scrape_fn=lambda *a: PAGES, on_token=seen.append, investigations_dir=folder)
            self.assertEqual(failed.exception.stage, "summarize")
            self.assertEqual(seen, [])
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
