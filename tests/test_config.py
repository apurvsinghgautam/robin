"""RobinConfig: what it reads from the environment and where its keys may go."""
import ast
import os
import unittest
from unittest import mock

import requests

import config
import health
import llm
import llm_utils
import model_registry
from config import DEPTH_LIMITS, RobinConfig, redact_secrets


def from_env(**values):
    return RobinConfig.from_env(env={k: str(v) for k, v in values.items()})


def registry(*entries):
    """Serve these picker entries in place of the live registry."""
    return mock.patch.object(model_registry, "get_entries", return_value=list(entries))


class CleanEnv(unittest.TestCase):
    """One raw setting is stripped, unquoted, and ignored when it is a placeholder."""

    def test_whitespace_and_one_matched_pair_of_quotes_come_off(self):
        """A missing name or a lone quote reads as unset."""
        for env, expected in (({}, "fallback"), ({"NAME": "real"}, "real"),
                              ({"NAME": "  real  "}, "real"), ({"NAME": '"real"'}, "real"),
                              ({"NAME": "'real'"}, "real"), ({"NAME": '"  real  "'}, "real"),
                              ({"NAME": '"real'}, '"real'), ({"NAME": '"'}, "fallback")):
            with self.subTest(env=env):
                self.assertEqual(config._clean_env("NAME", "fallback", env=env), expected)
        self.assertIsNone(config._clean_env("NAME", env={}))

    def test_an_unedited_placeholder_falls_back_to_the_default(self):
        """A real value that merely starts with "your" is kept."""
        for raw in ("your_ollama_url", "YOUR_API_KEY", '"your_key"', "", "   ",
                    "changeme", "none"):
            with self.subTest(raw=raw):
                self.assertEqual(config._clean_env("NAME", "fallback", env={"NAME": raw}),
                                 "fallback")
        self.assertEqual(config._clean_env("NAME", "fallback", env={"NAME": "yourkey123"}),
                         "yourkey123")


class FromEnv(unittest.TestCase):
    """Every field of a config built from an explicit environment mapping."""

    def test_an_empty_environment_gives_the_built_in_defaults(self):
        """No key, the Docker host for Ollama, and the sidebar's depth settings."""
        defaults = {
            "openai_api_key": None, "google_api_key": None, "anthropic_api_key": None,
            "openrouter_api_key": None, "mistral_api_key": None, "custom_api_key": None,
            "ollama_base_url": "http://host.docker.internal:11434",
            "openrouter_base_url": "https://openrouter.ai/api/v1", "ollama_num_ctx": 32768,
            "llama_cpp_base_url": None, "custom_api_base_url": None, "custom_api_model": None,
            "default_threads": 4, "default_max_results": 50, "default_max_scrape": 10,
            "default_content_chars": 8000, "default_preset": "threat_intel",
            "default_preset_set": False, "robin_model": None, "cache_dir": None,
        }
        cfg = RobinConfig.from_env(env={})
        self.assertEqual({name: getattr(cfg, name) for name in defaults}, defaults)

    def test_every_field_reads_its_own_variable(self):
        """Each variable sets exactly the field named beside it."""
        settings = {
            "OPENAI_API_KEY": ("openai_api_key", "sk-openai"),
            "GOOGLE_API_KEY": ("google_api_key", "goog"),
            "ANTHROPIC_API_KEY": ("anthropic_api_key", "ant"),
            "OLLAMA_BASE_URL": ("ollama_base_url", "http://127.0.0.1:11434"),
            "OPENROUTER_BASE_URL": ("openrouter_base_url", "https://gateway.example/api/v1"),
            "OPENROUTER_API_KEY": ("openrouter_api_key", "or-key"),
            "MISTRAL_API_KEY": ("mistral_api_key", "mistral"),
            "OLLAMA_NUM_CTX": ("ollama_num_ctx", 16384),
            "LLAMA_CPP_BASE_URL": ("llama_cpp_base_url", "http://127.0.0.1:8080"),
            "CUSTOM_API_BASE_URL": ("custom_api_base_url", "https://api.groq.com/openai/v1"),
            "CUSTOM_API_KEY": ("custom_api_key", "gsk-abc"),
            "CUSTOM_API_MODEL": ("custom_api_model", "llama-3.3-70b-versatile"),
            "ROBIN_INVESTIGATIONS_DIR": ("investigations_dir", "/tmp/robin-reports"),
            "ROBIN_DEFAULT_THREADS": ("default_threads", 16),
            "ROBIN_DEFAULT_MAX_RESULTS": ("default_max_results", 100),
            "ROBIN_DEFAULT_MAX_SCRAPE": ("default_max_scrape", 20),
            "ROBIN_DEFAULT_CONTENT_CHARS": ("default_content_chars", 20000),
            "ROBIN_DEFAULT_PRESET": ("default_preset", "ransomware_malware"),
            "ROBIN_MODEL": ("robin_model", "gpt-4o"),
            "ROBIN_CACHE_DIR": ("cache_dir", "/tmp/robin-cache"),
            "ROBIN_TOR_LOG": ("tor_log", "/var/log/tor/notices.log"),
        }
        cfg = from_env(**{name: value for name, (_, value) in settings.items()})
        self.assertEqual({field: getattr(cfg, field) for field, _ in settings.values()},
                         dict(settings.values()))

    def test_quotes_and_placeholders_are_cleaned_on_the_way_in(self):
        """The same rules as `_clean_env`, applied to every field."""
        cfg = RobinConfig.from_env(env={
            "OPENAI_API_KEY": '  "sk-quoted"  ', "OLLAMA_BASE_URL": "your_ollama_url",
            "ROBIN_DEFAULT_MAX_SCRAPE": '"20"', "ROBIN_DEFAULT_PRESET": "'corporate_espionage'",
        })
        self.assertEqual(
            (cfg.openai_api_key, cfg.ollama_base_url, cfg.default_max_scrape, cfg.default_preset),
            ("sk-quoted", "http://host.docker.internal:11434", 20, "corporate_espionage"))

    def test_a_non_integer_falls_back_to_the_default(self):
        """A float string is refused rather than truncated."""
        for name, field, raw, default in (
                ("OLLAMA_NUM_CTX", "ollama_num_ctx", "plenty", 32768),
                ("OLLAMA_NUM_CTX", "ollama_num_ctx", "", 32768),
                ("OLLAMA_NUM_CTX", "ollama_num_ctx", "8192.5", 32768),
                ("ROBIN_DEFAULT_THREADS", "default_threads", "lots", 4)):
            with self.subTest(name=name, raw=raw):
                self.assertEqual(getattr(from_env(**{name: raw}), field), default)

    def test_a_depth_default_is_clamped_into_its_sidebar_range(self):
        """An out-of-range value is pulled into range and logged; an in-range one is kept."""
        self.assertEqual(DEPTH_LIMITS, {"threads": (1, 16), "max_results": (10, 100),
                                        "max_scrape": (3, 20), "content_chars": (1000, 20000)})
        for depth, (low, high) in DEPTH_LIMITS.items():
            name = "ROBIN_DEFAULT_" + depth.upper()
            for raw, expected in ((low - 1, low), (high * 10, high), (low + 1, low + 1)):
                with self.subTest(name=name, raw=raw):
                    watch = (self.assertLogs if raw != expected else self.assertNoLogs)
                    with watch("config", level="WARNING") as logs:
                        cfg = from_env(**{name: raw})
                    self.assertEqual(getattr(cfg, "default_" + depth), expected)
                    if logs:
                        self.assertIn(name, logs.output[0])

    def test_default_preset_set_records_whether_the_user_chose_a_domain(self):
        """Setting the built-in preset is a choice; unset, empty or a placeholder is not."""
        for raw, chosen, preset in ((None, False, "threat_intel"),
                                    ("threat_intel", True, "threat_intel"),
                                    ('"threat_intel"', True, "threat_intel"),
                                    ("personal_identity", True, "personal_identity"),
                                    ("your_preset", False, "threat_intel"),
                                    ("", False, "threat_intel")):
            with self.subTest(raw=raw):
                cfg = from_env(**({} if raw is None else {"ROBIN_DEFAULT_PRESET": raw}))
                self.assertEqual((cfg.default_preset_set, cfg.default_preset), (chosen, preset))


def _widgets(source, kind):
    """{label: source text} for every `st.<...>.<kind>("label", ...)` call in a page."""
    return {node.args[0].value: ast.get_source_segment(source, node)
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == kind and node.args and isinstance(node.args[0], ast.Constant)}


class TheSidebarStartsFromTheConfiguredDefaults(unittest.TestCase):
    """ui.py runs Streamlit on import, so its controls are read from source."""

    def test_each_sidebar_control_starts_from_its_configured_default(self):
        """Every depth slider takes its range from DEPTH_LIMITS and its value from config."""
        with open("ui.py", encoding="utf-8") as handle:
            source = handle.read()
        expected = {"Scraping Threads": "default_threads",
                    "Max Results to Filter": "default_max_results",
                    "Max Pages to Scrape": "default_max_scrape",
                    "Content per Page (characters)": "default_content_chars"}
        sliders = _widgets(source, "slider")
        self.assertEqual(set(sliders), set(expected))
        for label, field in expected.items():
            with self.subTest(slider=label):
                self.assertIn("DEPTH_LIMITS", sliders[label])
                self.assertIn(field, sliders[label])
        self.assertIn("default_preset", _widgets(source, "selectbox")["Research Domain"])


PROVIDER_MODELS = {  # provider: (a model id, the client field that holds the key)
    "openai": ("gpt-4o-mini", "openai_api_key"),
    "anthropic": ("claude-3-5-haiku-latest", "anthropic_api_key"),
    "google": ("gemini-2.0-flash", "google_api_key"),
    "mistral": ("mistral-small-latest", "mistral_api_key"),
    "openrouter": ("openai/gpt-4o-mini", "openai_api_key"),
}


def keyed_config(owner):
    """A config holding "<owner>-<provider>-key" for every hosted provider."""
    return RobinConfig(**{p + "_api_key": "%s-%s-key" % (owner, p) for p in PROVIDER_MODELS})


class TheConfiguredKeyReachesTheClient(unittest.TestCase):
    """A client carries its own config's key, never the process environment's."""

    def client_key(self, provider, cfg):
        model, field = PROVIDER_MODELS[provider]
        spec = llm_utils._provider_constructor(provider, model, cfg)
        if spec is None:
            self.skipTest("%s client is not installed" % provider)
        # Through get_llm, so the credential check runs as it does for a user.
        with mock.patch.object(llm, "resolve_model_config", return_value=spec):
            value = getattr(llm.get_llm(model, cfg), field)
        return value.get_secret_value() if hasattr(value, "get_secret_value") else value

    def test_every_provider_client_carries_its_own_configs_key(self):
        """Two configs in one process, with the environment holding other keys or none."""
        for env_owner in ("env", ""):
            env = {p.upper() + "_API_KEY": env_owner and "env-%s-key" % p
                   for p in PROVIDER_MODELS}
            with mock.patch.dict(os.environ, env):
                for owner in ("cfg", "other"):
                    for provider in PROVIDER_MODELS:
                        with self.subTest(env=env_owner, cfg=owner, provider=provider):
                            self.assertEqual(self.client_key(provider, keyed_config(owner)),
                                             "%s-%s-key" % (owner, provider))

    def test_a_local_endpoint_never_receives_the_openai_key(self):
        """llama.cpp's base URL is whatever the user configured, OpenAI's is not."""
        cfg = from_env(OPENAI_API_KEY="fake-openai-key-here",
                       LLAMA_CPP_BASE_URL="http://192.168.1.50:8080")
        with registry(), mock.patch.object(llm_utils, "fetch_llama_cpp_models",
                                           lambda c: ["qwen3-8b"]):
            params = llm_utils.resolve_model_config("qwen3-8b", cfg)["constructor_params"]
        self.assertEqual((params["base_url"], params["api_key"]),
                         ("http://192.168.1.50:8080/v1", "sk-local"))


class SecretsStayOutOfErrors(unittest.TestCase):
    """A configured key never reaches a URL, a log line or a reply."""

    SECRETS = {
        "OPENAI_API_KEY": "fake-openai-aaaaaaaaaa",
        "ANTHROPIC_API_KEY": "fake-anthropic-bbbbbb",
        "GOOGLE_API_KEY": "fake-google-" + "NOTREAL" * 5,
        "MISTRAL_API_KEY": "mistral-dddddddddddd",
        "OPENROUTER_API_KEY": "fake-openrouter-eeeeee",
        "CUSTOM_API_KEY": "custom-ffffffffffff",
    }

    def test_the_google_key_travels_as_a_header_not_in_the_url(self):
        """In the query string it would land in every error that quotes the URL."""
        key, seen = self.SECRETS["GOOGLE_API_KEY"], {}

        def fake_get(url, headers=None, timeout=None):
            seen["url"], seen["headers"] = url, dict(headers or {})
            raise RuntimeError("stop here")

        with mock.patch.object(model_registry.requests, "get", fake_get):
            with self.assertRaises(RuntimeError):
                model_registry._fetch_google(from_env(GOOGLE_API_KEY=key))
        self.assertNotIn(key, seen["url"])
        self.assertEqual(seen["headers"].get("x-goog-api-key"), key)

    def test_every_configured_secret_is_redacted_whole(self):
        """Redacted before any cut: a truncated key is still a leaked one."""
        quoted = "401 for url: https://x/y?key=" + " ".join(self.SECRETS.values())
        safe = redact_secrets(quoted, RobinConfig.from_env(env=self.SECRETS))
        for secret in self.SECRETS.values():
            self.assertNotIn(secret[:12], safe)
        self.assertIn("***", safe)

    def test_the_health_probe_does_not_hand_a_key_to_the_caller(self):
        """`robin_health` returns this error text to the host verbatim."""
        key = "fake-openai-live-aaaaaa"

        def exploding(model, cfg=None):
            raise RuntimeError("401 Incorrect API key provided: " + key)

        entry = {"key": "gpt-4o", "provider": "openai", "model_name": "gpt-4o"}
        with registry(entry), mock.patch.object(health, "get_llm", side_effect=exploding):
            probe = health.check_llm_health("gpt-4o", from_env(OPENAI_API_KEY=key))
        self.assertNotIn(key, str(probe))
        self.assertIn("***", probe["error"])

    def test_every_sink_downstream_of_an_authenticated_call_redacts(self):
        """Each module that reports a provider error passes it through redact_secrets."""
        for module, marker in (("health.py", "redact_secrets(e, cfg)"),
                               ("llm_utils.py", "redact_secrets(exc, cfg)"),
                               ("pipeline.py", "redact_secrets(exc, cfg)"),
                               ("mcp_server.py", "redact_secrets(exc, cfg)"),
                               ("model_registry.py", "redact_secrets(exc, cfg)")):
            with open(module, encoding="utf-8") as handle:
                self.assertIn(marker, handle.read(), module)


ALPHA = "https://alpha.example/v1"
BETA = "https://beta.example/v1"


def endpoint_config(base_url, api_key):
    """A config whose only reachable provider is one custom endpoint."""
    return RobinConfig(ollama_base_url=None, custom_api_base_url=base_url,
                       custom_api_key=api_key)


class TwoConfigsStaySeparate(unittest.TestCase):
    """Two configs in one process never see each other's endpoint, key or answer."""

    def setUp(self):
        llm_utils._probe_cache.clear()
        self.addCleanup(llm_utils._probe_cache.clear)
        self.probes = []
        for patcher in (registry(),
                        mock.patch.object(llm_utils.requests, "get", side_effect=self.fake_get)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_get(self, url, **kwargs):
        """Answer only the two custom endpoints, each naming its own model."""
        self.probes.append(url)
        for name in ("alpha", "beta"):
            if url.startswith("https://%s.example" % name):
                return mock.Mock(**{"json.return_value": {"data": [{"id": name + "-model"}]}})
        raise requests.RequestException("no route to %s in this test" % url)

    def test_the_probe_memo_is_keyed_on_endpoint_and_key(self):
        """A second config is probed afresh; an equal one shares the memo."""
        for first, second, answer, probes in (
                ((ALPHA, "key-a"), (BETA, "key-b"), ["beta-model"], 2),
                ((ALPHA, "key-one"), (ALPHA, "key-two"), ["alpha-model"], 2),
                ((ALPHA, "key-a"), (ALPHA, "key-a"), ["alpha-model"], 1)):
            with self.subTest(first=first, second=second):
                llm_utils._probe_cache.clear()
                self.probes.clear()
                llm_utils.fetch_custom_api_models(endpoint_config(*first))
                self.assertEqual(llm_utils.fetch_custom_api_models(endpoint_config(*second)),
                                 answer)
                self.assertEqual(len(self.probes), probes)

    def test_each_config_resolves_to_its_own_endpoint_and_key(self):
        """Interleaved, in the order a shared process sees them."""
        alpha, beta = endpoint_config(ALPHA, "key-alpha"), endpoint_config(BETA, "key-beta")
        for model, cfg, base, key in (("alpha-model", alpha, ALPHA, "key-alpha"),
                                      ("beta-model", beta, BETA, "key-beta"),
                                      ("alpha-model", alpha, ALPHA, "key-alpha")):
            params = llm_utils.resolve_model_config(model, cfg)["constructor_params"]
            self.assertEqual((params["base_url"], params["api_key"]), (base, key))

    def test_get_llm_builds_an_independent_client_per_config(self):
        client_alpha = llm.get_llm("alpha-model", endpoint_config(ALPHA, "key-alpha"))
        client_beta = llm.get_llm("beta-model", endpoint_config(BETA, "key-beta"))
        self.assertIn("alpha.example", str(client_alpha.openai_api_base))
        self.assertIn("beta.example", str(client_beta.openai_api_base))

    def test_the_picker_and_its_labels_follow_the_given_config(self):
        """beta's endpoint does not serve alpha-model, so it cannot claim it."""
        alpha, beta = endpoint_config(ALPHA, "key-alpha"), endpoint_config(BETA, "key-beta")
        self.assertEqual(llm_utils.get_model_choices(alpha), ["alpha-model"])
        self.assertEqual(llm_utils.get_model_choices(beta), ["beta-model"])
        self.assertEqual(llm_utils.get_model_display_names(["alpha-model"], alpha),
                         {"alpha-model": "[custom] alpha-model"})
        self.assertEqual(llm_utils.get_model_display_names(["alpha-model"], beta),
                         {"alpha-model": "[local] alpha-model"})


if __name__ == "__main__":
    unittest.main()
