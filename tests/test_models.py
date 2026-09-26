"""Which models exist and which one a caller gets: the registry cache and model choice."""
import ast
import json
import os
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import requests

import health
import llm
import llm_utils
import model_registry
import pipeline
from config import RobinConfig
from tests.mcp_harness import StubDeps, an_investigation, build, call
from tests.stubs import quiet_logger

CFG = RobinConfig(openai_api_key="sk-test", google_api_key="g-test", ollama_base_url=None)


def fails(cfg):
    raise RuntimeError("provider unreachable")


def serves(*models):
    return lambda cfg: list(models)


class RegistryTestCase(unittest.TestCase):
    """A model cache in a temporary directory, with no bundled seed."""

    def setUp(self):
        quiet_logger(self, "model_registry")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cache_path = self.root / "default" / "models_cache.json"
        for attr, value in (("CACHE_DIR", self.cache_path.parent),
                            ("CACHE_PATH", self.cache_path),
                            ("_load_seed", lambda: {})):
            patcher = mock.patch.object(model_registry, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def providers(self, **fetchers):
        """Only these providers, each keyed on its own config field, never the network."""
        return mock.patch.object(model_registry, "PROVIDERS", {
            name: {"fetch": fetch, "key": lambda cfg, n=name: getattr(cfg, n + "_api_key")}
            for name, fetch in fetchers.items()})

    def write_cache(self, providers, fetched_at=12345.0):
        """A cache file holding `providers`, scoped to CFG, without per-provider stamps."""
        payload = {"providers": providers,
                   "scopes": {name: model_registry._scope(name, CFG) for name in providers}}
        if fetched_at != "missing":
            payload["fetched_at"] = fetched_at
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(payload))

    def read_cache(self):
        return json.loads(self.cache_path.read_text())


class RefreshStampsOnlyASuccess(RegistryTestCase):
    """`fetched_at` and the per-provider stamps record a fetch that answered."""

    def test_a_refresh_that_learns_nothing_keeps_the_stamp_and_the_last_lists(self):
        """So the next call retries instead of trusting the outage for the whole TTL."""
        for fetch in (fails, serves()):
            with self.subTest(fetch="raises" if fetch is fails else "empty"):
                self.write_cache({"openai": ["old-model"]})
                with self.providers(openai=fetch):
                    merged = model_registry.refresh(CFG)
                payload = self.read_cache()
                self.assertEqual(payload["fetched_at"], 12345.0)
                self.assertEqual(merged["openai"], ["old-model"])
                self.assertEqual(payload["providers"]["openai"], ["old-model"])
                attempts = []
                with self.providers(openai=lambda c: attempts.append(1) or ["fresh-model"]):
                    model_registry.get_registry(CFG)
                self.assertEqual(len(attempts), 1)

    def test_one_success_restamps_the_file_but_only_its_own_provider_is_fresh(self):
        """The provider that failed is not served from the cache and is fetched again."""
        self.write_cache({"openai": ["old-model"], "google": ["old-gem"]})
        before = time.time()
        with self.providers(openai=serves("fresh-model"), google=fails):
            model_registry.refresh(CFG)
        payload = self.read_cache()
        self.assertGreaterEqual(payload["fetched_at"], before)
        self.assertEqual(payload["providers"],
                         {"openai": ["fresh-model"], "google": ["old-gem"]})
        self.assertEqual(sorted(payload["stamps"]), ["openai"])
        self.assertEqual(model_registry._load_cache(cfg=CFG), {"openai": ["fresh-model"]})
        tried = []
        with self.providers(openai=lambda c: tried.append("openai") or ["fresh-model"],
                            google=lambda c: tried.append("google") or ["gem"]):
            entries = model_registry.get_entries(CFG)
        self.assertIn("google", tried)
        self.assertEqual([(e["provider"], e["key"]) for e in entries],
                         [("openai", "fresh-model"), ("google", "gem")])

    def test_a_stamp_another_configuration_earned_is_not_inherited(self):
        """The stamps follow the same scope rule as the lists they date."""
        other = RobinConfig(openai_api_key="sk-other", google_api_key="g-other",
                            ollama_base_url=None)
        with self.providers(openai=serves("fresh-model"), google=fails):
            model_registry.refresh(CFG)
        self.assertEqual(sorted(model_registry._cache_stamps(CFG)), ["openai"])
        self.assertEqual(model_registry._cache_stamps(other), {})

    def test_a_cache_with_one_stamp_for_all_providers_still_loads(self):
        self.write_cache({"openai": ["old-model"], "google": ["old-gem"]},
                         fetched_at=time.time())
        self.assertEqual(sorted(model_registry._load_cache(cfg=CFG)), ["google", "openai"])

    def test_a_provider_error_quoting_the_key_is_logged_redacted(self):
        """The provider quotes the key back; the log line must not."""
        cfg = RobinConfig(openai_api_key="fake-openai-" + "NOTREAL" * 3, ollama_base_url=None)
        refused = mock.Mock(**{"raise_for_status.side_effect": requests.HTTPError(
            "401 Unauthorized: bad key " + cfg.openai_api_key)})
        with mock.patch.object(model_registry.requests, "get", return_value=refused), \
                self.assertLogs("model_registry", level="WARNING") as logs:
            model_registry.refresh(cfg)
        self.assertNotIn(cfg.openai_api_key, "\n".join(logs.output))
        self.assertIn("***", logs.output[0])


class AnUnusableStampIsStale(RegistryTestCase):
    """A bad `fetched_at` makes the cache stale, never raises, and never costs the lists."""

    def test_a_bad_stamp_is_stale_but_keeps_its_lists(self):
        """bool is a subclass of int, so it needs refusing explicitly."""
        for stamp in ("yesterday", None, True, "missing"):
            with self.subTest(stamp=stamp):
                self.write_cache({"openai": ["old-model"]}, fetched_at=stamp)
                self.assertIsNone(model_registry._load_cache(cfg=CFG))
                self.assertEqual(model_registry._load_cache(ignore_ttl=True, cfg=CFG),
                                 {"openai": ["old-model"]})

    def test_the_next_refresh_rewrites_a_bad_stamp_whether_or_not_it_fetches(self):
        for fetch, expected in ((serves("fresh-model"), ["fresh-model"]),
                                (fails, ["old-model"])):
            with self.subTest(expected=expected):
                self.write_cache({"openai": ["old-model"]}, fetched_at="yesterday")
                with self.providers(openai=fetch):
                    registry = model_registry.get_registry(CFG)
                payload = self.read_cache()
                self.assertIsInstance(payload["fetched_at"], float)
                self.assertEqual(registry["openai"], expected)
                self.assertEqual(payload["providers"]["openai"], expected)


KEY_A = "fake-account-a-0123456789"
KEY_B = "fake-account-b-9876543210"
CFG_A = RobinConfig(openrouter_api_key=KEY_A, ollama_base_url=None,
                    openrouter_base_url="https://gateway-a.example/api/v1")
CFG_B = RobinConfig(openrouter_api_key=KEY_B, ollama_base_url=None,
                    openrouter_base_url="https://gateway-b.example/api/v1")


class TheCacheBelongsToOneConfiguration(RegistryTestCase):
    """A cached list is scoped to its cache_dir, endpoint and credential."""

    def setUp(self):
        super().setUp()
        self.fetches = []

        def fetch(cfg):
            self.fetches.append(cfg.openrouter_api_key)
            return ["vendor/account-%s-model" % ("a" if cfg.openrouter_api_key == KEY_A else "b")]

        patcher = self.providers(openrouter=fetch)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_cache_dir_holds_its_own_cache(self):
        one = replace(CFG_A, cache_dir=str(self.root / "one"))
        two = replace(CFG_A, cache_dir=str(self.root / "two"))
        model_registry.refresh(one)
        model_registry.get_registry(two)
        self.assertTrue((self.root / "one" / "models_cache.json").is_file())
        self.assertFalse(self.cache_path.exists())
        self.assertEqual(len(self.fetches), 2, "the second dir reused the first's cache")

    def test_a_cached_list_is_served_only_to_the_account_that_fetched_it(self):
        """Another gateway, or the same gateway with another key, fetches its own."""
        same_gateway = replace(CFG_B, openrouter_base_url=CFG_A.openrouter_base_url)
        for asking, account, fetches in ((CFG_A, "a", [KEY_A]),
                                         (CFG_B, "b", [KEY_A, KEY_B]),
                                         (same_gateway, "b", [KEY_A, KEY_B])):
            with self.subTest(asking=asking.openrouter_base_url, account=account):
                self.fetches.clear()
                model_registry.refresh(CFG_A)
                names = [e["model_name"] for e in model_registry.get_entries(asking)]
                self.assertEqual(names, ["vendor/account-%s-model" % account])
                self.assertEqual(self.fetches, fetches)

    def test_the_plaintext_key_is_never_written(self):
        model_registry.refresh(CFG_A)
        text = self.cache_path.read_text()
        self.assertNotIn(KEY_A, text)
        self.assertIn("scopes", json.loads(text))

    def test_a_cache_with_no_scopes_is_treated_as_absent(self):
        self.cache_path.parent.mkdir(parents=True)
        self.cache_path.write_text(json.dumps({
            "fetched_at": time.time(),
            "providers": {"openrouter": ["vendor/someone-elses-model"]}}))
        self.assertFalse(model_registry._load_cache(cfg=CFG_B))
        self.assertEqual(model_registry.get_registry(CFG_B)["openrouter"],
                         ["vendor/account-b-model"])


class ConcurrentWritersNeverCorruptTheCache(RegistryTestCase):
    """Two writers racing on one cache leave one whole payload and no temporary files."""

    LONG = {"openrouter": ["vendor/model-%03d" % i for i in range(200)]}
    SHORT = {"openrouter": ["vendor/short"]}

    def test_a_slower_writer_cannot_leave_trailing_json(self):
        """Both hold a temporary file open; the long payload is published first."""
        real_dump, real_replace = json.dump, os.replace
        both_open = threading.Barrier(2, timeout=10)
        long_published = threading.Event()
        errors = []

        def dump(obj, handle, **kwargs):
            both_open.wait()
            if obj["providers"] is not self.LONG:
                long_published.wait(5)
            return real_dump(obj, handle, **kwargs)

        def publish(src, dst):
            real_replace(src, dst)
            long_published.set()

        def write(providers):
            try:
                model_registry._write_cache(providers, 1.0, CFG)
            except Exception as exc:  # surfaced below
                errors.append(exc)

        with mock.patch.object(model_registry.json, "dump", dump), \
                mock.patch.object(model_registry.os, "replace", publish):
            threads = [threading.Thread(target=write, args=(p,)) for p in (self.LONG, self.SHORT)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(15)

        self.assertEqual(errors, [])
        published = json.loads(self.cache_path.read_text())
        self.assertIn(published["providers"], (self.LONG, self.SHORT))
        self.assertEqual([p.name for p in self.cache_path.parent.iterdir()],
                         ["models_cache.json"], "temporary files left behind")


class TheDefaultModel(unittest.TestCase):
    """A caller that names no model gets the newest cheap tier, not the flagship."""

    def test_the_first_cheap_tier_wins_matched_as_a_whole_segment(self):
        """"mini" inside "gemini" is not a tier; tokens are tried cheapest first."""
        for choices, expected in (
                (["gemini-2.5-pro", "gpt-4.1-mini"], "gpt-4.1-mini"),
                (["gemini-2.5-pro", "gemini-1.5-pro"], "gemini-2.5-pro"),
                (["gpt-5", "gpt-5-mini"], "gpt-5-mini"),
                (["gpt-4.1-mini", "gpt-4.1-nano"], "gpt-4.1-nano"),
                (["gemini-2.5-flash", "gemini-2.5-flash-lite"], "gemini-2.5-flash-lite"),
                (["gpt-5-mini", "gpt-4.1-mini"], "gpt-5-mini"),
                (["claude-opus-4-1", "claude-haiku-4-5"], "claude-haiku-4-5"),
                (["mistral-large-latest", "mistral-small-latest"], "mistral-small-latest"),
                (["gemini-2.5-pro", "gemini-2.5-flash"], "gemini-2.5-flash"),
                (["openai/gpt-5", "openai/gpt-5-mini"], "openai/gpt-5-mini"),
                (["qwen3:32b", "qwen3:mini"], "qwen3:mini"),
                (["x_big", "x_small"], "x_small"),
                (["GPT-5", "GPT-5-MINI"], "GPT-5-MINI"),
                (["dominion-7b", "terminator"], "dominion-7b"),
                (["gpt-4o", "claude-sonnet-4"], "gpt-4o"),
                ([], "")):
            with self.subTest(choices=choices):
                self.assertEqual(llm_utils.default_model(choices), expected)

    def test_robin_investigate_runs_on_the_default_unless_robin_model_is_set(self):
        quiet_logger(self, "mcp.server.lowlevel.server")
        for env, expected in (({}, "gpt-5-mini"), ({"ROBIN_MODEL": "gpt-5"}, "gpt-5")):
            with self.subTest(env=env):
                deps = StubDeps(models=["gpt-5", "gpt-5-mini", "claude-opus-4-1"],
                                investigation=an_investigation())
                cfg = RobinConfig.from_env(env=dict(env, ROBIN_DEFAULT_PRESET="threat_intel"))
                server, _ = build(deps, cfg=cfg)
                call(server, "robin_investigate",
                     {"query": "acme breach", "preset": "threat_intel"})
                self.assertEqual(deps.run_calls[-1]["model"], expected)


class TheOllamaProbe(unittest.TestCase):
    """Ollama's models come from its /api/tags; an unreachable server lists none."""

    def test_the_probe_reads_tags_and_treats_a_dead_server_as_empty(self):
        self.addCleanup(llm_utils._probe_cache.clear)
        cfg = RobinConfig(ollama_base_url="http://ollama.test:11434")
        tags = mock.Mock(**{"json.return_value": {
            "models": [{"name": "llama3:8b"}, {"model": "qwen3:4b"}, {}]}})
        for reply, expected in ((tags, ["llama3:8b", "qwen3:4b"]),
                                (requests.ConnectionError("refused"), [])):
            with self.subTest(expected=expected):
                llm_utils._probe_cache.clear()
                with mock.patch.object(llm_utils.requests, "get", side_effect=[reply]) as get:
                    self.assertEqual(llm_utils.fetch_ollama_models(cfg), expected)
                self.assertEqual(get.call_args.args, ("http://ollama.test:11434/api/tags",))


class AnUnknownModelIsRefused(unittest.TestCase):
    """A model no provider serves resolves to nothing, and each caller says so."""

    def test_get_llm_raises_and_the_health_probe_reports_it(self):
        cfg = RobinConfig(ollama_base_url=None)
        with mock.patch.object(model_registry, "get_entries", return_value=[]):
            self.assertIsNone(llm_utils.resolve_model_config("no-such-model", cfg))
            with self.assertRaisesRegex(ValueError, "Unsupported LLM model: 'no-such-model'"):
                llm.get_llm("no-such-model", cfg)
            probe = health.check_llm_health("no-such-model", cfg)
        self.assertEqual((probe["status"], probe["provider"]), ("error", "unknown"))


def resolvable(*names):
    known = {n.lower() for n in names}
    return lambda name: name.lower() in known


class TheFollowUpModel(unittest.TestCase):
    """A follow-up runs on the report's model when it can, else on the sidebar's."""

    def test_a_host_marker_or_unresolvable_model_falls_back_to_the_sidebar(self):
        """A report an agent saved stores "host", which is provenance, not a model."""
        def broken(name):
            raise ValueError("registry unavailable")

        for stored, resolver, expected in (
                ("host", resolvable("host", "gpt-5-mini"), "gpt-5-mini"),
                ("host sampling", resolvable("host sampling"), "gpt-5-mini"),
                ("HOST", resolvable("host"), "gpt-5-mini"),
                (" Host Sampling ", resolvable("host sampling"), "gpt-5-mini"),
                ("retired-model-2023", resolvable("gpt-5-mini"), "gpt-5-mini"),
                ("", resolvable("gpt-5-mini"), "gpt-5-mini"),
                (None, resolvable("gpt-5-mini"), "gpt-5-mini"),
                ("gpt-4o", broken, "gpt-5-mini"),
                ("claude-haiku-4-5", resolvable("claude-haiku-4-5"), "claude-haiku-4-5")):
            with self.subTest(stored=stored):
                self.assertEqual(pipeline.followup_model(stored, "gpt-5-mini", resolver),
                                 expected)

    def test_the_markers_the_mcp_server_writes_are_markers(self):
        with open("mcp_server.py", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn('model = "host sampling"', source)
        self.assertIn('model: str = "host"', source)
        self.assertLessEqual({"host", "host sampling"}, pipeline.HOST_MODEL_MARKERS)

    def test_the_ui_follow_up_resolves_its_model_through_followup_model(self):
        """ui.py runs Streamlit on import, so its calls are read from source."""
        with open("ui.py", encoding="utf-8") as handle:
            source = handle.read()
        called = {node.func.id for node in ast.walk(ast.parse(source))
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertIn("followup_model", called)
        self.assertNotIn('get_llm(inv.get("model")', source)


if __name__ == "__main__":
    unittest.main()
