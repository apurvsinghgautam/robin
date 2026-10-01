"""The public fixture exercises the pipeline without external calls."""
import unittest

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from config import RobinConfig
from prompts import preset_sections
from tests import model_smoke as smoke


class InvestigationQuality(unittest.TestCase):
    def replay(self, extra_artifact="", irrelevant=""):
        sections = preset_sections("threat_intel")
        report = f"{sections[0]}\n{smoke.QUERY}\n{sections[1]}\n"
        report += "\n".join(smoke.PAGES)
        report += f"\n{sections[2]}\n{smoke.CVE} {smoke.HASH} {smoke.EMAIL}{extra_artifact}\n"
        report += "\n".join(sections[3:])
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

    def test_invented_artifacts_and_padded_selections_fail_the_fixture(self):
        record = self.replay(extra_artifact="\nfabricated@example.net", irrelevant="1")
        self.assertFalse(record["passed"])
        self.assertFalse(record["checks"]["no_extra_artifacts"])
        self.assertFalse(record["checks"]["empty_selection"])

    def test_repeating_identifiers_in_the_query_is_not_artifact_extraction(self):
        report = self.replay()["outputs"]["report"]
        report = report.replace(f"{smoke.CVE} {smoke.HASH} {smoke.EMAIL}\n", "No artifacts listed.\n")
        self.assertIn(smoke.QUERY, report)
        self.assertFalse(smoke.report_checks(report)["report_identifiers"])
