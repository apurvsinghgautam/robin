import config
import requests
from urllib.parse import urljoin
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing import Callable, Optional, List
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
try:  # optional: only needed when a Mistral key is configured
    from langchain_mistralai import ChatMistralAI
except ImportError:  # pragma: no cover
    ChatMistralAI = None
import model_registry
from langchain_core.callbacks.base import BaseCallbackHandler
import os
import time
from config import (
    OLLAMA_BASE_URL,
    OPENROUTER_BASE_URL,
    OPENROUTER_API_KEY,
    GOOGLE_API_KEY,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    LLAMA_CPP_BASE_URL,
)


class BufferedStreamingHandler(BaseCallbackHandler):
    def __init__(self, buffer_limit: int = 60, ui_callback: Optional[Callable[[str], None]] = None):
        self.buffer = ""
        self.buffer_limit = buffer_limit
        self.ui_callback = ui_callback

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.buffer += token
        if "\n" in token or len(self.buffer) >= self.buffer_limit:
            print(self.buffer, end="", flush=True)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""

    def on_llm_end(self, response, **kwargs) -> None:
        if self.buffer:
            print(self.buffer, end="", flush=True)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""


# --- Configuration Data ---
# Instantiate common dependencies once
_common_callbacks = [BufferedStreamingHandler(buffer_limit=60)]

# Define common parameters for most LLMs
_common_llm_params = {
    "temperature": 0,
    "streaming": True,
    "callbacks": _common_callbacks,
}

# Model IDs are no longer hardcoded here. `model_registry` asks each provider
# what it currently serves (see that module's docstring and issue #140); this
# table only says how to *construct* a client once a model has been chosen.
#
# Anything Robin can reach through a first-party API is constructed against that
# API. The OpenRouter branch is used only for models with no first-party path,
# or when the first-party key is missing — the registry decides which.


def _openrouter_base() -> str:
    return model_registry._openrouter_base()


def _provider_constructor(provider: str, model_name: str) -> Optional[dict]:
    """Return {"class", "constructor_params"} for a registry entry."""
    if provider == "openai":
        return {"class": ChatOpenAI,
                "constructor_params": {"model_name": model_name}}
    if provider == "anthropic":
        return {"class": ChatAnthropic,
                "constructor_params": {"model": model_name}}
    if provider == "google":
        return {"class": ChatGoogleGenerativeAI,
                "constructor_params": {"model": model_name,
                                       "google_api_key": GOOGLE_API_KEY}}
    if provider == "mistral":
        if ChatMistralAI is None:
            return None
        return {"class": ChatMistralAI,
                "constructor_params": {"model": model_name,
                                       "api_key": config.MISTRAL_API_KEY}}
    if provider == "openrouter":
        return {"class": ChatOpenAI,
                "constructor_params": {"model_name": model_name,
                                       "base_url": _openrouter_base(),
                                       "api_key": OPENROUTER_API_KEY}}
    return None


def _registry_entries(force_refresh: bool = False) -> List[dict]:
    """Registry entries, or an empty list if the registry is unusable."""
    try:
        return model_registry.get_entries(force_refresh=force_refresh)
    except Exception as exc:  # noqa: BLE001 - never let the picker hard-fail
        import logging
        logging.warning("Model registry unavailable (%s).", str(exc)[:120])
        return []


def _normalize_model_name(name: str) -> str:
    return name.strip().lower()


# Streamlit re-runs the whole script on every widget interaction, and the three
# local-provider probes below are each called more than once per run. With a
# provider configured but not actually running, every probe pays the full
# connect timeout: measured at ~10s of added latency per rerun. A short memo
# collapses that to one probe, while staying short enough that starting Ollama
# shows up in the picker within half a minute.
_PROBE_TTL_SECONDS = 30
_PROBE_TIMEOUT = 2
_probe_cache = {}


def _ttl_cached(identity):
    """Memoize a zero-argument probe for _PROBE_TTL_SECONDS.

    `identity` returns whatever the probe's result depends on, and is part of
    the cache key. That matters for the custom provider, whose URL and key are
    typed into the sidebar and changed mid-session: keying on the function name
    alone would keep serving the old endpoint's answer for the whole TTL, so a
    user would enter a Base URL and watch nothing happen.
    """
    def decorator(fn):
        def wrapper():
            key = (fn.__name__, identity())
            now = time.monotonic()
            cached = _probe_cache.get(key)
            if cached and now - cached[0] < _PROBE_TTL_SECONDS:
                return cached[1]
            value = fn()
            _probe_cache[key] = (now, value)
            return value
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        wrapper.cache_clear = _probe_cache.clear
        return wrapper
    return decorator


def _get_ollama_base_url() -> Optional[str]:
    if not OLLAMA_BASE_URL:
        return None
    return OLLAMA_BASE_URL.rstrip("/") + "/"


@_ttl_cached(lambda: OLLAMA_BASE_URL)
def fetch_ollama_models() -> List[str]:
    """
    Retrieve the list of locally available Ollama models by querying the Ollama HTTP API.
    Returns an empty list if the API isn't reachable or the base URL is not defined.
    """
    base_url = _get_ollama_base_url()
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
        import logging
        if OLLAMA_BASE_URL and ("localhost" in OLLAMA_BASE_URL.lower() or "127.0.0.1" in OLLAMA_BASE_URL.lower()):
            logging.warning(
                "Ollama unreachable at %s. If running Robin in Docker, use "
                "http://host.docker.internal:<port> instead of localhost.", OLLAMA_BASE_URL
            )
        return []


# Added Support for llama.cpp models since they use OpenAI-compatible API
@_ttl_cached(lambda: LLAMA_CPP_BASE_URL)
def fetch_llama_cpp_models() -> List[str]:
    """
    Retrieve available models from an OpenAI-compatible llama.cpp server.
    Uses /v1/models.
    """
    if not LLAMA_CPP_BASE_URL:
        return []

    base = LLAMA_CPP_BASE_URL.rstrip("/")
    try:
        resp = requests.get(f"{base}/v1/models", timeout=_PROBE_TIMEOUT)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [m["id"] for m in data if "id" in m]
    except (requests.RequestException, ValueError, KeyError):
        return []


@_ttl_cached(lambda: (config.CUSTOM_API_BASE_URL, config.CUSTOM_API_KEY))
def fetch_custom_api_models() -> List[str]:
    """Retrieve models from any OpenAI-compatible API endpoint."""
    if not config.CUSTOM_API_BASE_URL:
        return []
    base = config.CUSTOM_API_BASE_URL.rstrip("/")
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


def get_model_choices() -> List[str]:
    """Every chat model the user can actually reach right now.

    Cloud models come from the live registry, gated on the provider's key being
    present. Local models are discovered the way they always have been.
    """
    gated_base_models = [entry["key"] for entry in _registry_entries()]

    # Local Models
    dynamic_models = []

    # Dynamic local models via Ollama-style API (/api/tags)
    dynamic_models += fetch_ollama_models()

    # Dynamic local models via llama.cpp which uses OpenAI style API
    dynamic_models += fetch_llama_cpp_models()

    dynamic_models += fetch_custom_api_models()

    # Manual model from sidebar — add it if not already discovered
    if config.CUSTOM_API_MODEL and config.CUSTOM_API_MODEL.strip():
        manual = config.CUSTOM_API_MODEL.strip()
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


def resolve_model_config(model_choice: str):
    """
    Resolve a model choice (case-insensitive) to the corresponding configuration.
    Supports both the predefined remote models and any locally installed Ollama models.
    """
    model_choice_lower = _normalize_model_name(model_choice)

    for entry in _registry_entries():
        if _normalize_model_name(entry["key"]) == model_choice_lower:
            cfg = _provider_constructor(entry["provider"], entry["model_name"])
            if cfg:
                return cfg

    # llama.cpp (OpenAI-compatible)
    for llama_model in fetch_llama_cpp_models():
        if _normalize_model_name(llama_model) == model_choice_lower:
            base = (LLAMA_CPP_BASE_URL or "").rstrip("/")
            if not base.endswith("/v1"):
                base += "/v1"
            return {
                "class": ChatOpenAI,
                "constructor_params": {
                    "model_name": llama_model,
                    "base_url": base,
                    "api_key": OPENAI_API_KEY or "sk-local",
                    "streaming": False,
                },
            }

    # Custom OpenAI-compatible API — manual model name or auto-discovered
    custom_candidates = list(fetch_custom_api_models())
    if config.CUSTOM_API_MODEL and config.CUSTOM_API_MODEL.strip():
        manual = config.CUSTOM_API_MODEL.strip()
        if _normalize_model_name(manual) not in {_normalize_model_name(m) for m in custom_candidates}:
            custom_candidates.append(manual)
    for custom_model in custom_candidates:
        if _normalize_model_name(custom_model) == model_choice_lower:
            base = (config.CUSTOM_API_BASE_URL or "").rstrip("/")
            if not base.endswith("/v1"):
                base += "/v1"
            return {
                "class": ChatOpenAI,
                "constructor_params": {
                    "model_name": custom_model,
                    "base_url": base,
                    "api_key": config.CUSTOM_API_KEY or "sk-custom",
                    "streaming": False,
                },
            }

    for ollama_model in fetch_ollama_models():
        if _normalize_model_name(ollama_model) == model_choice_lower:
            return {
                "class": ChatOllama,
                "constructor_params": {
                    "model": ollama_model,
                    "base_url": OLLAMA_BASE_URL,
                    # Without this, Ollama's own default window applies and the
                    # tail of every investigation is dropped before the model
                    # ever sees it, however large the model's real context is.
                    "num_ctx": config.OLLAMA_NUM_CTX,
                },
            }

    return None


def get_model_display_names(model_keys: List[str]) -> dict:
    """Return a display label dict mapping model key -> '[provider] model_key'."""
    ollama_set = set(fetch_ollama_models())
    llama_cpp_set = set(fetch_llama_cpp_models())
    custom_set = set(fetch_custom_api_models())

    registry_providers = {
        _normalize_model_name(e["key"]): e["provider"] for e in _registry_entries()
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