import logging
import requests
from urllib.parse import urljoin
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing import Callable, Optional, List
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
try:  # Optional: only needed when a Mistral key is configured.
    from langchain_mistralai import ChatMistralAI
except ImportError:  # pragma: no cover
    ChatMistralAI = None
import model_registry
from langchain_core.callbacks.base import BaseCallbackHandler
import hashlib
import re
import time
from config import redact_secrets, RobinConfig


class BufferedStreamingHandler(BaseCallbackHandler):
    """Collect streamed tokens and hand them to `ui_callback` in readable chunks.

    Never to stdout: in MCP stdio mode it is the JSON-RPC wire, and one stray
    token ends the session. A debug log carries the chunks for terminal users.
    """

    def __init__(self, buffer_limit: int = 60, ui_callback: Optional[Callable[[str], None]] = None):
        self.buffer = ""
        self.buffer_limit = buffer_limit
        self.ui_callback = ui_callback

    def _flush(self) -> None:
        if not self.buffer:
            return
        logging.getLogger(__name__).debug("%s", self.buffer)
        if self.ui_callback:
            self.ui_callback(self.buffer)
        self.buffer = ""

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.buffer += token
        if "\n" in token or len(self.buffer) >= self.buffer_limit:
            self._flush()

    def on_llm_end(self, response, **kwargs) -> None:
        self._flush()


# --- Configuration Data ---
_common_callbacks = [BufferedStreamingHandler(buffer_limit=60)]

# Parameters every client gets. temperature is deliberately NOT here: OpenAI's
# reasoning and gpt-5 family reject an explicit temperature outright.
_common_llm_params = {
    "streaming": True,
    "callbacks": _common_callbacks,
}

# OpenAI families that accept an explicit temperature. An allowlist rather
# than a denylist of reasoning models: omitting temperature always works,
# sending it to a model that refuses it does not.
_TEMPERATURE_OK = re.compile(r"^(gpt-3\.5|gpt-4|chatgpt-4)", re.IGNORECASE)


def _openai_temperature(model_name: str) -> dict:
    bare = model_name.split("/", 1)[-1]
    return {"temperature": 0} if _TEMPERATURE_OK.match(bare) else {}

# `model_registry` asks each provider what it currently serves; the functions
# below only say how to construct a client once a model has been chosen.


def _openrouter_base(cfg: RobinConfig) -> str:
    return model_registry._openrouter_base(cfg)


def _api_key(key: Optional[str]) -> dict:
    return {"api_key": key} if key else {}


def _provider_constructor(provider: str, model_name: str,
                          cfg: RobinConfig) -> Optional[dict]:
    """Return {"class", "constructor_params"} for a registry entry."""
    # Every branch passes the config's key explicitly. Left out, the OpenAI and
    # Anthropic clients read the process environment instead.
    if provider == "openai":
        return {"class": ChatOpenAI,
                "constructor_params": dict(model_name=model_name,
                                           **_api_key(cfg.openai_api_key),
                                           **_openai_temperature(model_name))}
    if provider == "anthropic":
        return {"class": ChatAnthropic,
                "constructor_params": {"model": model_name, "temperature": 0,
                                       **_api_key(cfg.anthropic_api_key)}}
    if provider == "google":
        return {"class": ChatGoogleGenerativeAI,
                "constructor_params": {"model": model_name, "temperature": 0,
                                       "google_api_key": cfg.google_api_key}}
    if provider == "mistral":
        if ChatMistralAI is None:
            return None
        return {"class": ChatMistralAI,
                "constructor_params": {"model": model_name, "temperature": 0,
                                       "api_key": cfg.mistral_api_key}}
    if provider == "openrouter":
        # An OpenRouter id carries its vendor as a prefix, so the same rule
        # applies to the OpenAI models served through it.
        return {"class": ChatOpenAI,
                "constructor_params": dict(model_name=model_name,
                                           base_url=_openrouter_base(cfg),
                                           api_key=cfg.openrouter_api_key,
                                           **(_openai_temperature(model_name)
                                              if model_name.startswith("openai/")
                                              else {"temperature": 0}))}
    return None


def _registry_entries(cfg: RobinConfig, force_refresh: bool = False) -> List[dict]:
    """Registry entries, or an empty list if the registry is unusable."""
    try:
        return model_registry.get_entries(cfg, force_refresh=force_refresh)
    except Exception as exc:  # noqa: BLE001 - never let the picker hard-fail
        logging.warning("Model registry unavailable (%s).", redact_secrets(exc, cfg)[:120])
        return []


def _normalize_model_name(name: str) -> str:
    return name.strip().lower()


# Streamlit reruns the whole script on every interaction and calls each local
# probe several times per run. A short memo spares a configured-but-down
# provider's connect timeout, yet a newly started one appears within 30 s.
_PROBE_TTL_SECONDS = 30
_PROBE_TIMEOUT = 2
_probe_cache = {}


def _ttl_cached(identity):
    """Memoize a probe of one config for _PROBE_TTL_SECONDS."""
    def decorator(fn):
        def wrapper(cfg: Optional[RobinConfig] = None):
            cfg = cfg if cfg is not None else RobinConfig.from_env()
            # Hash the identity: the custom provider's identity includes its API
            # key, and a cache key would otherwise hold it in plaintext for the
            # process lifetime.
            key = (fn.__name__,
                   hashlib.sha256(repr(identity(cfg)).encode()).hexdigest())
            now = time.monotonic()
            cached = _probe_cache.get(key)
            if cached and now - cached[0] < _PROBE_TTL_SECONDS:
                return cached[1]
            value = fn(cfg)
            _probe_cache[key] = (now, value)
            return value
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        wrapper.cache_clear = lambda: [
            _probe_cache.pop(k) for k in list(_probe_cache) if k[0] == fn.__name__
        ]
        return wrapper
    return decorator


def _get_ollama_base_url(cfg: RobinConfig) -> Optional[str]:
    if not cfg.ollama_base_url:
        return None
    return cfg.ollama_base_url.rstrip("/") + "/"


@_ttl_cached(lambda cfg: cfg.ollama_base_url)
def fetch_ollama_models(cfg: RobinConfig) -> List[str]:
    """The models Ollama serves, from its /api/tags endpoint.

    Returns an empty list if the API isn't reachable or no base URL is set.
    """
    base_url = _get_ollama_base_url(cfg)
    if not base_url:
        return []

    try:
        resp = requests.get(urljoin(base_url, "api/tags"), timeout=_PROBE_TIMEOUT)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        available = []
        for m in models:
            name = m.get("name") or m.get("model")
            if name:
                available.append(name)
        return available
    except (requests.RequestException, ValueError):
        ollama_base_url = cfg.ollama_base_url
        if ollama_base_url and ("localhost" in ollama_base_url.lower() or "127.0.0.1" in ollama_base_url.lower()):
            logging.warning(
                "Ollama unreachable at %s. If running Robin in Docker, use "
                "http://host.docker.internal:<port> instead of localhost.", ollama_base_url
            )
        return []


@_ttl_cached(lambda cfg: cfg.llama_cpp_base_url)
def fetch_llama_cpp_models(cfg: RobinConfig) -> List[str]:
    """The models an OpenAI-compatible llama.cpp server lists at /v1/models."""
    if not cfg.llama_cpp_base_url:
        return []

    base = cfg.llama_cpp_base_url.rstrip("/")
    try:
        resp = requests.get(f"{base}/v1/models", timeout=_PROBE_TIMEOUT)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [m["id"] for m in data if "id" in m]
    except (requests.RequestException, ValueError, KeyError):
        return []


@_ttl_cached(lambda cfg: (cfg.custom_api_base_url, cfg.custom_api_key))
def fetch_custom_api_models(cfg: RobinConfig) -> List[str]:
    """Retrieve models from any OpenAI-compatible API endpoint."""
    if not cfg.custom_api_base_url:
        return []
    base = cfg.custom_api_base_url.rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    try:
        resp = requests.get(f"{base}/models", timeout=_PROBE_TIMEOUT)
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("data", []) if "id" in m]
    except (requests.RequestException, ValueError, KeyError):
        return []


def _is_set(v: Optional[str]) -> bool:
    return bool(v and str(v).strip() and "your_" not in str(v))


def get_model_choices(cfg: Optional[RobinConfig] = None) -> List[str]:
    """Every chat model `cfg` (default: the environment) can reach right now.

    Cloud models come from the live registry, gated on the provider's key being
    present; local models are probed from their servers.
    """
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    gated_base_models = [entry["key"] for entry in _registry_entries(cfg)]

    dynamic_models = []
    dynamic_models += fetch_ollama_models(cfg)
    dynamic_models += fetch_llama_cpp_models(cfg)
    dynamic_models += fetch_custom_api_models(cfg)

    # The manually entered custom model, unless discovery already found it.
    if cfg.custom_api_model and cfg.custom_api_model.strip():
        manual = cfg.custom_api_model.strip()
        if _normalize_model_name(manual) not in {_normalize_model_name(m) for m in dynamic_models}:
            dynamic_models.append(manual)

    normalized = {_normalize_model_name(m): m for m in gated_base_models}
    for dm in dynamic_models:
        key = _normalize_model_name(dm)
        if key not in normalized:
            normalized[key] = dm

    ordered_dynamic = sorted(
        [name for key, name in normalized.items() if name not in gated_base_models],
        key=_normalize_model_name,
    )
    return gated_base_models + ordered_dynamic


def resolve_model_config(model_choice: str, cfg: Optional[RobinConfig] = None):
    """Resolve a model choice (case-insensitive) to its client config, or None.

    Returns {"class", "constructor_params"}. Every endpoint and credential in it
    comes from `cfg`, so two configs get two independent clients.
    """
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    model_choice_lower = _normalize_model_name(model_choice)

    for entry in _registry_entries(cfg):
        if _normalize_model_name(entry["key"]) == model_choice_lower:
            constructor = _provider_constructor(entry["provider"],
                                                entry["model_name"], cfg)
            if constructor:
                return constructor

    # llama.cpp (OpenAI-compatible)
    for llama_model in fetch_llama_cpp_models(cfg):
        if _normalize_model_name(llama_model) == model_choice_lower:
            base = (cfg.llama_cpp_base_url or "").rstrip("/")
            if not base.endswith("/v1"):
                base += "/v1"
            return {
                "class": ChatOpenAI,
                "constructor_params": {
                    "model_name": llama_model,
                    "temperature": 0,
                    "base_url": base,
                    # A placeholder, never the OpenAI key: llama.cpp ignores it
                    # and the endpoint is not OpenAI's to send a live key to.
                    "api_key": "sk-local",
                    "streaming": False,
                },
            }

    # Custom OpenAI-compatible API: a manual model name or a discovered one.
    custom_candidates = list(fetch_custom_api_models(cfg))
    if cfg.custom_api_model and cfg.custom_api_model.strip():
        manual = cfg.custom_api_model.strip()
        if _normalize_model_name(manual) not in {_normalize_model_name(m) for m in custom_candidates}:
            custom_candidates.append(manual)
    for custom_model in custom_candidates:
        if _normalize_model_name(custom_model) == model_choice_lower:
            base = (cfg.custom_api_base_url or "").rstrip("/")
            if not base.endswith("/v1"):
                base += "/v1"
            return {
                "class": ChatOpenAI,
                "constructor_params": {
                    "model_name": custom_model,
                    "temperature": 0,
                    "base_url": base,
                    "api_key": cfg.custom_api_key or "sk-custom",
                    "streaming": False,
                },
            }

    for ollama_model in fetch_ollama_models(cfg):
        if _normalize_model_name(ollama_model) == model_choice_lower:
            return {
                "class": ChatOllama,
                "constructor_params": {
                    "model": ollama_model,
                    "temperature": 0,
                    "base_url": cfg.ollama_base_url,
                    # Without this, Ollama's own default window applies and the
                    # tail of every investigation is dropped before the model
                    # ever sees it, however large the model's real context is.
                    "num_ctx": cfg.ollama_num_ctx,
                },
            }

    return None


# Tier tokens that mark a provider's inexpensive models, cheapest first. Matched
# on the tier rather than a model name, so the default is always a model the
# provider currently serves.
CHEAP_TIER_TOKENS = ("nano", "mini", "flash-lite", "flash", "lite", "haiku", "small")


def _has_tier_token(name: str, token: str) -> bool:
    """Match a tier token as a whole segment, so "mini" does not match "gemini"."""
    return re.search(r"(?:^|[-_. /:])" + re.escape(token) + r"(?:$|[-_. /:])",
                     name.lower()) is not None


def default_model(choices: List[str]) -> str:
    """The model a caller gets when it names none: the newest cheap one."""
    for token in CHEAP_TIER_TOKENS:
        for name in choices:
            if _has_tier_token(name, token):
                return name
    return choices[0] if choices else ""


def get_model_display_names(model_keys: List[str],
                            cfg: Optional[RobinConfig] = None) -> dict:
    """Return a display label dict mapping model key -> '[provider] model_key'."""
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    ollama_set = set(fetch_ollama_models(cfg))
    llama_cpp_set = set(fetch_llama_cpp_models(cfg))
    custom_set = set(fetch_custom_api_models(cfg))

    registry_providers = {
        _normalize_model_name(e["key"]): e["provider"] for e in _registry_entries(cfg)
    }

    display = {}
    for key in model_keys:
        provider = registry_providers.get(_normalize_model_name(key))
        if provider:
            prefix = provider
        elif key in ollama_set:
            prefix = "ollama"
        elif key in llama_cpp_set:
            prefix = "llama.cpp"
        elif key in custom_set:
            prefix = "custom"
        else:
            prefix = "local"
        display[key] = f"[{prefix}] {key}"
    return display
