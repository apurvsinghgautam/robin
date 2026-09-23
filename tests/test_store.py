"""Saved investigations on disk: exclusive-create names, newest first, never a traceback."""
import contextlib
import json
import os
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import store
from config import RobinConfig
from tests.mcp_harness import args, build, call, text_of


# The seven keys every Robin version writes. A file holding only these must load.
OLD_RECORD = {
    "timestamp": "2026-05-01T10:00:00",
    "query": "acme breach",
    "refined_query": "acme breach dump",
    "model": "gpt-4o-mini",
    "preset": "🔍 Dark Web Threat Intel",
    "sources": [{"title": "Listing", "link": "http://abcdefghij234567.onion/t"}],
    "summary": "## Findings\n- something",
}


class StubInvestigation:
    """Stands in for `pipeline.Investigation`: a record and a `saved_as` slot."""

    def __init__(self, **overrides):
        self.record = dict(OLD_RECORD, status="ok", pivots=["acme vendor leak"], **overrides)
        self.saved_as = None

    def to_record(self):
        return dict(self.record)


class StoreTestCase(unittest.TestCase):
    """A fresh, not yet created investigations directory per test."""

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.dir = self.root / "investigations"

    def freeze_clock(self, *moment):
        """Pin `datetime.now` so every save competes for the same base name."""
        frozen = mock.Mock(wraps=store.datetime)
        frozen.now.return_value = store.datetime(*moment)
        patcher = mock.patch.object(store, "datetime", frozen)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, name, body):
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / name).write_text(body if isinstance(body, str) else json.dumps(body))

    def filenames(self):
        return [item["_filename"] for item in store.load_investigations(investigations_dir=self.dir)]


class SaveAndLoad(StoreTestCase):
    """A save creates the directory and the record loads back unchanged."""

    def test_a_save_round_trips(self):
        inv = StubInvestigation()
        self.assertIs(store.save_investigation(inv, investigations_dir=self.dir), inv)
        self.assertRegex(inv.saved_as, r"^investigation_\d{8}_\d{6}\.json$")
        loaded = store.load_investigations(investigations_dir=self.dir)
        self.assertEqual(loaded, [dict(inv.record, _filename=inv.saved_as)])

    def test_an_older_record_still_loads(self):
        self.write("investigation_20260501_100000.json", OLD_RECORD)
        self.assertEqual(store.load_investigations(investigations_dir=self.dir),
                         [dict(OLD_RECORD, _filename="investigation_20260501_100000.json")])

    def test_unreadable_files_are_skipped_and_a_missing_directory_is_empty(self):
        self.assertEqual(store.load_investigations(investigations_dir=self.dir), [])
        self.write("investigation_20260501_100000.json", OLD_RECORD)
        self.write("investigation_20260502_100000.json", "{not json")
        self.write("investigation_20260503_100000.json", "[1, 2]")
        self.assertEqual(self.filenames(), ["investigation_20260501_100000.json"])

    def test_the_directory_comes_from_the_argument_then_the_config_then_the_default(self):
        moved = RobinConfig.from_env(env={"ROBIN_INVESTIGATIONS_DIR": "/data/robin"})
        cases = [
            ("default", None, RobinConfig.from_env(env={}), "investigations"),
            ("config", None, moved, "/data/robin"),
            ("argument", "/tmp/elsewhere", moved, "/tmp/elsewhere"),
            ("blank variable", None,
             RobinConfig.from_env(env={"ROBIN_INVESTIGATIONS_DIR": "  "}), "investigations"),
        ]
        for name, argument, cfg, expected in cases:
            with self.subTest(name):
                self.assertEqual(store.resolve_dir(argument, cfg=cfg), Path(expected))
        with self.subTest("process environment"), \
                mock.patch.dict(os.environ, {"ROBIN_INVESTIGATIONS_DIR": "/data/env"}):
            self.assertEqual(store.resolve_dir(), Path("/data/env"))


class FileNaming(StoreTestCase):
    """Each save claims its own file with an exclusive create."""

    THREADS = 8

    def test_concurrent_saves_in_one_second_each_get_their_own_file(self):
        self.freeze_clock(2026, 9, 18, 12, 0, 0)
        for attempt in range(3):
            with self.subTest(attempt=attempt):
                for path in self.dir.glob("*.json"):
                    path.unlink()
                barrier = threading.Barrier(self.THREADS)
                saved = [StubInvestigation(query="query-%d" % i) for i in range(self.THREADS)]
                errors = []

                def worker(inv):
                    try:
                        barrier.wait()
                        store.save_investigation(inv, investigations_dir=self.dir)
                    except Exception as exc:  # surfaced below, never swallowed
                        errors.append(exc)

                threads = [threading.Thread(target=worker, args=(inv,)) for inv in saved]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                self.assertEqual(errors, [])
                names = [inv.saved_as for inv in saved]
                self.assertEqual(sorted(path.name for path in self.dir.glob("*.json")),
                                 sorted(set(names)))
                self.assertEqual(len(set(names)), self.THREADS)
                for inv in saved:
                    written = json.loads((self.dir / inv.saved_as).read_text())
                    self.assertEqual(written["query"], inv.record["query"])

    def test_an_existing_file_is_never_overwritten(self):
        self.freeze_clock(2026, 9, 18, 12, 0, 0)
        self.write("investigation_20260918_120000.json", {"query": "already here"})
        inv = store.save_investigation(StubInvestigation(), investigations_dir=self.dir)
        self.assertEqual(inv.saved_as, "investigation_20260918_120000_1.json")
        self.assertEqual(json.loads((self.dir / "investigation_20260918_120000.json")
                                    .read_text())["query"], "already here")


class Ordering(StoreTestCase):
    """Newest first: by second, then by collision suffix as a number."""

    def test_twelve_saves_in_one_second_list_newest_first(self):
        self.freeze_clock(2026, 9, 19, 12, 0, 0)
        saved = [store.save_investigation(StubInvestigation(query="save-%02d" % i),
                                          investigations_dir=self.dir).saved_as
                 for i in range(12)]
        self.assertEqual(self.filenames(), list(reversed(saved)))

    def test_a_later_second_beats_every_suffix_of_an_earlier_one(self):
        names = ["investigation_20260919_115959.json",
                 "investigation_20260919_115959_9.json",
                 "investigation_20260919_120000.json",
                 "investigation_20260919_115959_11.json",
                 "investigation_manual-copy.json"]
        for name in names:
            self.write(name, OLD_RECORD)
        loaded = self.filenames()
        self.assertIn("investigation_manual-copy.json", loaded)
        self.assertEqual([name for name in loaded if "manual" not in name],
                         ["investigation_20260919_120000.json",
                          "investigation_20260919_115959_11.json",
                          "investigation_20260919_115959_9.json",
                          "investigation_20260919_115959.json"])


class AnUnwritableDirectory(StoreTestCase):
    """A failed save logs one warning naming the TROUBLESHOOTING section and returns."""

    def test_it_warns_and_returns_the_investigation_unsaved(self):
        blocker = self.root / "blocker"
        blocker.write_text("a file where a directory should be")
        cases = [
            ("open refused", self.dir,
             mock.patch.object(store.Path, "open",
                               side_effect=PermissionError(13, "Permission denied"))),
            ("mkdir refused", blocker / "sub", contextlib.nullcontext()),
        ]
        for name, directory, patch in cases:
            with self.subTest(name):
                inv = StubInvestigation()
                with patch, self.assertLogs("store", level="WARNING") as logged:
                    returned = store.save_investigation(inv, investigations_dir=directory)
                self.assertIs(returned, inv)
                self.assertIsNone(inv.saved_as)
                self.assertEqual(len(logged.output), 1)
                self.assertIn(store.TROUBLESHOOTING_SECTION, logged.output[0])
        troubleshooting = (Path(__file__).resolve().parent.parent / "TROUBLESHOOTING.md").read_text()
        self.assertIn("## " + store.TROUBLESHOOTING_SECTION, troubleshooting)


class TheMcpSaveTool(StoreTestCase):
    """robin_save_investigation writes through the store to the shared directory."""

    def test_its_save_loads_back_and_the_reply_says_the_volume_holds_it(self):
        server, _ = build(investigations_dir=str(self.dir))
        reply = text_of(call(server, "robin_save_investigation", args()))
        loaded = store.load_investigations(investigations_dir=self.dir)
        self.assertEqual([item["query"] for item in loaded], ["acme breach"])
        self.assertTrue(reply.startswith("status: ok"), reply)
        self.assertIn(loaded[0]["_filename"], reply)
        self.assertIn("investigations volume", reply)


if __name__ == "__main__":
    unittest.main()
