"""The public fixture exercises the pipeline without external calls."""
import unittest
import json

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from config import RobinConfig
from evidence import build_evidence
from tests import model_smoke as smoke


class InvestigationQuality(unittest.TestCase):
    def replay(self, extra_artifact="", irrelevant=""):
        keys = list(build_evidence(smoke.PAGES.items())["passages"])
        report = json.dumps({"sections": {"Key Insights": keys + ([extra_artifact] if extra_artifact else [])},
                             "next_steps": []})
        answers = [smoke.QUERY, "2, 4", report, '["CVE-2026-12345 advisory"]',
                   irrelevant, "No Bitcoin address is provided in the source."]
        client = FakeMessagesListChatModel(responses=[AIMessage(content=[
            {"type": "thinking", "thinking": "Consider result 1 and wallet 123"},
            {"type": "text", "text": answer}]) for answer in answers])
        return smoke.evaluate("synthetic", RobinConfig(), llm_factory=lambda: client)

    def test_real_stages_pass_the_grounded_fixture(self):
        record = self.replay()
        self.assertTrue(record["passed"], record)
        self.assertTrue(all(record["checks"].values()))
        self.assertIn(smoke.EMAIL, record["outputs"]["report"])

    def test_invented_evidence_is_omitted_and_padded_selections_fail_the_fixture(self):
        record = self.replay(extra_artifact="\nfabricated@example.net", irrelevant="1")
        self.assertFalse(record["passed"])
        self.assertTrue(record["checks"]["no_extra_artifacts"])
        self.assertNotIn("fabricated@example.net", record["outputs"]["report"])
        self.assertIn("omitted", record["outputs"]["report"])
        self.assertFalse(record["checks"]["empty_selection"])

    def test_repeating_identifiers_in_the_query_is_not_artifact_extraction(self):
        report = self.replay()["outputs"]["report"]
        start = report.index("## Investigation Artifacts")
        end = report.index("## Key Insights", start)
        report = report[:start] + "## Investigation Artifacts\nNo artifacts listed.\n\n" + report[end:]
        self.assertIn(smoke.QUERY, report)
        self.assertFalse(smoke.report_checks(report)["report_identifiers"])
