"""Evidence in one MCP session cannot be forged, reused after search, or borrowed by another."""
import json
import re
import tempfile
import unittest

import store
from tests.mcp_harness import StubDeps, build, connect, run, text_of
from tests.model_smoke import PAGES, QUERY, SOURCE, HASH


class HostEvidence(unittest.TestCase):
    def server(self, folder):
        deps = StubDeps(records={url: {"status": "ok", "text": text}
                                 for url, text in PAGES.items()})
        return build(deps=deps, investigations_dir=folder)[0]

    async def read(self, session):
        result = await session.call_tool("robin_scrape", {"urls": list(PAGES)})
        body = text_of(result)
        self.assertIn("evidence_id:", body)
        return list(dict.fromkeys(re.findall(r"evidence_id: (E[0-9a-f]+-\d+)", body)))

    async def save(self, session, keys, artifact_ids=None, **extra):
        summary = json.dumps({"sections": {"Key Insights": keys}, "next_steps": [],
            "artifacts": [{"type": "SHA-256", "value": HASH,
                           "evidence_ids": keys[:1] if artifact_ids is None else artifact_ids}]})
        return text_of(await session.call_tool("robin_save_investigation", {
            "query": QUERY, "preset": "threat_intel", "summary": summary,
            "sources": [{"link": url} for url in PAGES], **extra}))

    def test_a_host_save_uses_the_actual_session_passages_and_source_map(self):
        with tempfile.TemporaryDirectory() as folder:
            server = self.server(folder)

            async def body():
                async with connect(server) as session:
                    keys = await self.read(session)
                    reply = await self.save(session, keys + ["invented-reference"])
                    self.assertIn("status: ok", reply)
                    self.assertNotIn("invented-reference", reply)
            run(body)
            saved = store.load_investigations(folder)[0]
            check = saved["evidence_check"]
            self.assertEqual(check["status"], "source_matched")
            hashes = [item for item in check["artifact_sources"] if item["value"] == HASH]
            self.assertEqual(hashes[0]["sources"], [SOURCE])
            self.assertEqual(check["rejected"], {"unknown_evidence": 1})
            self.assertNotIn("evidence_id:", saved["summary"])

    def test_a_host_saves_concise_findings_with_checked_quotes_and_numbered_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            server = self.server(folder)

            async def body():
                async with connect(server) as session:
                    keys = await self.read(session)
                    quote = "This is an unverified forum claim; no victims, ransomware group, cryptocurrency address, or exploitation date are given."
                    finding = {"text": "The advisory is an unverified forum claim and gives no victim or ransomware-group attribution.",
                               "evidence": [{"evidence_id": keys[0], "quote": quote}]}
                    reply = await self.save(session, [finding], artifact_ids=keys[:1])
                    self.assertIn("status: ok", reply)
            run(body)
            saved = store.load_investigations(folder)[0]
            self.assertIn("no victim or ransomware-group attribution. [1]", saved["summary"])
            self.assertNotIn("Supporting source passages", saved["summary"])
            self.assertNotIn("Context [", saved["summary"])
            self.assertIn("- **SHA-256:** " + HASH + " [1]", saved["summary"])
            self.assertEqual(saved["evidence_check"]["accepted_findings"], 1)
            self.assertEqual(saved["evidence_check"]["findings"][0]["evidence"][0]["source_url"], SOURCE)

    def test_after_scraping_unchecked_prose_or_unread_sources_cannot_be_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            server = self.server(folder)

            async def body():
                async with connect(server) as session:
                    keys = await self.read(session)
                    reply = await self.save(session, keys, summary="The hash exploits the CVE.")
                    self.assertIn("nothing was saved", reply)
                    self.assertIn("evidence-selection JSON", reply)
                    reply = await self.save(session, keys, sources=[{"link": "https://unread.example"}])
                    self.assertIn("no supplied page evidence", reply)
            run(body)
            self.assertEqual(store.load_investigations(folder), [])

    def test_new_search_and_other_sessions_cannot_reuse_page_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            server = self.server(folder)

            async def body():
                async with connect(server) as first:
                    keys = await self.read(first)
                    async with connect(server) as second:
                        reply = await self.save(second, keys)
                        self.assertIn("no supplied page evidence", reply)
                    await first.call_tool("robin_search", {"query": QUERY})
                    reply = await self.save(first, keys)
                    self.assertIn("no supplied page evidence", reply)
            run(body)
            self.assertEqual(store.load_investigations(folder), [])

    def test_imported_markdown_is_explicitly_unchecked(self):
        with tempfile.TemporaryDirectory() as folder:
            server = self.server(folder)

            async def body():
                async with connect(server) as session:
                    reply = await self.save(session, [], summary="## Notes\nExternal report")
                    self.assertIn("source evidence was not checked by Robin", reply)
            run(body)
            saved = store.load_investigations(folder)[0]
            self.assertEqual(saved["evidence_check"], {"status": "not_checked"})


if __name__ == "__main__":
    unittest.main()
