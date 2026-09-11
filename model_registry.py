"""Live model registry.

Robin used to carry a hardcoded map of model IDs in ``llm_utils.py``. Providers
retire models faster than releases go out, so the map went stale and users saw
"this model is out of date" failures from perfectly valid API keys (issue #140).
Every new model also meant a code change and a pull request, which is a race
nobody wins.

The registry asks each provider what it currently serves, in three layers:

1. **Bundled seed** (``models.json``) - shipped in the image, so a first run
   with no network, or a Tor-only host, still gets a working picker.
2. **Disk cache** - the last successful fetch, reused until it ages past a TTL.
3. **Live fetch** - one call per provider whose key is configured.

Only chat-capable models are kept, filtered by each provider's own capability
signal where one exists and by a token denylist where none does. There is no
recency filter: as long as a provider still serves a model it stays in the
picker, and the day they retire it, it leaves on its own.

Sourcing rule (Apurv, 2026-09-10): first-party wins. A model reachable through
its own vendor's API is listed from that API. The OpenRouter copy appears only
when the first-party key is absent, so an OpenRouter-only user keeps access to
GPT, Claude, Gemini and Mistral without seeing every model twice.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

import config

logger = logging.getLogger(__name__)

SEED_PATH = Path(__file__).with_name("models.json")
CACHE_DIR = Path(os.getenv("ROBIN_CACHE_DIR") or (Path.home() / ".robin"))
CACHE_PATH = CACHE_DIR / "models_cache.json"

try:
    CACHE_TTL_SECONDS = int(float(os.getenv("MODEL_REGISTRY_TTL_HOURS", "24")) * 3600)
except ValueError:
    CACHE_TTL_SECONDS = 24 * 3600

FETCH_TIMEOUT = 8

# Vendor prefixes on OpenRouter that Robin can also reach first-party. When the
# first-party key is set, the OpenRouter duplicates are suppressed.
OPENROUTER_FIRST_PARTY = {
    "openai/": "openai",
    "anthropic/": "anthropic",
    "google/": "google",
    "mistralai/": "mistral",
}

# Tokens that mark a model as something other than text chat. Applied only where
# the provider gives us no capability field of its own. Deliberately a denylist:
# anything unrecognized is kept, so a model released after this code was written
# still shows up.
NON_CHAT_TOKENS = (
    "embedding", "embed", "moderation", "whisper", "tts", "transcribe",
    "audio", "speech", "dall-e", "image", "vision-only", "sora", "video",
    "veo", "imagen", "lyria", "nano-banana", "robotics", "computer-use",
    "deep-research", "rerank", "guard", "ocr",
)

# Extra tokens that only make sense for one provider. OpenAI's list mixes the
# legacy completion models and the realtime/search endpoints in with chat, and
# none of those work through a LangChain chat client.
PROVIDER_NON_CHAT_TOKENS = {
    "openai": (
        "babbage", "davinci", "curie", "-instruct", "realtime",
        "gpt-live", "search-api", "search-preview",
    ),
}


def _version_sort_key(model_id: str):
    """Order a provider's models newest-first without hardcoding any names.

    Sorts on the numeric version tokens in the id, descending, so `gpt-6-astra`
    precedes `gpt-5.5` precedes `gpt-4`, and `gemini-3.8-flash` precedes
    `gemini-2.5-pro`. Ids carrying no version (`chat-latest`) sort last, which
    keeps an oddity from becoming the picker's default selection.
    """
    lowered = model_id.lower()
    # Preview/experimental/alias builds sort after stable ones so they never
    # become the picker's default selection.
    unstable = any(t in lowered for t in ("preview", "-exp", "experimental",
                                          "latest", "customtools"))
    # Ignore date stamps and other 4-digit runs; they are not versions.
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", model_id)
               if float(n) < 1000]
    if not numbers:
        return (int(unstable), 1, [], model_id)
    return (int(unstable), 0, [-n for n in numbers], model_id)


def _looks_non_chat(model_id: str, provider: str = "") -> bool:
    lowered = model_id.lower()
    tokens = NON_CHAT_TOKENS + PROVIDER_NON_CHAT_TOKENS.get(provider, ())
    return any(token in lowered for token in tokens)


def _is_set(value: Optional[str]) -> bool:
    return bool(value and str(value).strip() and "your_" not in str(value))


def _get_json(url: str, headers: Optional[Dict[str, str]] = None):
    response = requests.get(url, headers=headers or {}, timeout=FETCH_TIMEOUT)
    response.raise_for_status()
    return response.json()


# --- Per-provider fetchers -------------------------------------------------
#
# Each returns a list of provider-side model ids, already filtered to chat.
# Each raises on transport failure; the caller decides what a failure means.


def _fetch_openai() -> List[str]:
    """OpenAI exposes no capability field, so filter by token."""
    data = _get_json(
        "https://api.openai.com/v1/models",
        {"Authorization": "Bearer {}".format(config.OPENAI_API_KEY)},
    )
    return sorted(
        (m["id"] for m in data.get("data", [])
         if m.get("id") and not _looks_non_chat(m["id"], "openai")),
        key=_version_sort_key,
    )


def _fetch_anthropic() -> List[str]:
    """Anthropic lists chat models only; nothing to filter."""
    data = _get_json(
        "https://api.anthropic.com/v1/models?limit=100",
        {"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
    )
    return [m["id"] for m in data.get("data", []) if m.get("id")]


def _fetch_google() -> List[str]:
    """Google needs both signals: generateContent support AND a token check,
    because its image and text-to-speech models also advertise generateContent."""
    data = _get_json(
        "https://generativelanguage.googleapis.com/v1beta/models?key={}".format(
            config.GOOGLE_API_KEY
        )
    )
    out = []
    for m in data.get("models", []):
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        model_id = m.get("name", "").split("/")[-1]
        if model_id and not _looks_non_chat(model_id):
            out.append(model_id)
    return sorted(out, key=_version_sort_key)


def _fetch_mistral() -> List[str]:
    """Mistral carries an explicit completion_chat capability flag."""
    data = _get_json(
        "https://api.mistral.ai/v1/models",
        {"Authorization": "Bearer {}".format(config.MISTRAL_API_KEY)},
    )
    out = []
    for m in data.get("data", []):
        caps = m.get("capabilities") or {}
        if caps and not caps.get("completion_chat", False):
            continue
        if m.get("id") and not _looks_non_chat(m["id"]):
            out.append(m["id"])
    return sorted(out)


def _openrouter_base() -> str:
    """Fall back to the public base URL when the configured one is unusable.

    Sample .env files ship a ``your_...`` placeholder for this value, and an
    explicit placeholder overrides the default in ``config.py``, so a user who
    never edited that line would otherwise get an unusable URL.
    """
    configured = (config.OPENROUTER_BASE_URL or "").strip().rstrip("/")
    if configured.startswith("http"):
        return configured
    return "https://openrouter.ai/api/v1"


def _fetch_openrouter() -> List[str]:
    """OpenRouter's catalogue is public, so it lists even without a key.

    ``:batch`` variants are dropped because they are not usable from a
    streaming chat call; ``:free`` variants are kept, since those are the
    entries most users actually want from OpenRouter.
    """
    base = _openrouter_base()
    data = _get_json("{}/models".format(base))
    out = []
    for m in data.get("data", []):
        model_id = m.get("id")
        if not model_id or model_id.endswith(":batch") or model_id.startswith("~"):
            continue
        modalities = (m.get("architecture") or {}).get("output_modalities") or ["text"]
        if "text" not in modalities:
            continue
        if _looks_non_chat(model_id):
            continue
        out.append(model_id)
    return sorted(out, key=_version_sort_key)


PROVIDERS = {
    "openai": {"fetch": _fetch_openai, "key": lambda: config.OPENAI_API_KEY},
    "anthropic": {"fetch": _fetch_anthropic, "key": lambda: config.ANTHROPIC_API_KEY},
    "google": {"fetch": _fetch_google, "key": lambda: config.GOOGLE_API_KEY},
    "mistral": {"fetch": _fetch_mistral, "key": lambda: config.MISTRAL_API_KEY},
    "openrouter": {"fetch": _fetch_openrouter, "key": lambda: config.OPENROUTER_API_KEY},
}


def configured_providers() -> List[str]:
    return [name for name, spec in PROVIDERS.items() if _is_set(spec["key"]())]


# --- The three layers ------------------------------------------------------


def _load_json_file(path: Path) -> Optional[dict]:
    """Load a JSON object, or None for anything unusable.

    The isinstance check is load-bearing. A file containing valid JSON that is
    not an object (a torn write leaving "[1,2,3]", say) used to parse fine and
    then raise AttributeError on .get, which llm_utils swallowed as "registry
    unavailable". refresh() was never reached, so the bad file was never
    rewritten and every cloud model stayed missing from the picker on every
    launch until the user deleted it by hand.
    """
    try:
        with path.open() as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_seed() -> Dict[str, List[str]]:
    payload = _load_json_file(SEED_PATH) or {}
    return payload.get("providers", {})


def _load_cache(ignore_ttl: bool = False) -> Optional[Dict[str, List[str]]]:
    """The last fetched lists. `ignore_ttl` returns them however old they are.

    An expired cache is stale, not worthless: it is still a better record of
    what a provider serves than the seed baked into the image months ago.
    """
    payload = _load_json_file(CACHE_PATH)
    if not payload:
        return None
    if not ignore_ttl and time.time() - payload.get("fetched_at", 0) > CACHE_TTL_SECONDS:
        return None
    providers = payload.get("providers")
    return providers if isinstance(providers, dict) else None


def _write_cache(providers: Dict[str, List[str]]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # Write to a sibling and rename, so a crash or a full disk mid-write
        # cannot leave a half-written cache behind.
        tmp = CACHE_PATH.with_suffix(".tmp")
        with tmp.open("w") as handle:
            json.dump({"fetched_at": time.time(), "providers": providers}, handle, indent=2)
        os.replace(tmp, CACHE_PATH)
    except OSError as exc:
        # A read-only filesystem is fine; the registry just refetches next start.
        logger.debug("Could not write model cache: %s", exc)


def refresh(verbose: bool = False) -> Dict[str, List[str]]:
    """Fetch every configured provider and update the cache.

    Providers that fail keep whatever the previous layer knew about them, so one
    dead key or one unreachable API never empties the picker.
    """
    # Seed first, then whatever we last fetched on top of it, expired or not.
    # `_load_cache() or _load_seed()` threw the last-known lists away the moment
    # they aged past the TTL, so a provider that failed to refresh regressed to
    # the shipped seed and that regression was written back with a fresh
    # timestamp, contradicting this function's own fallback promise.
    merged = dict(_load_seed())
    merged.update(_load_cache(ignore_ttl=True) or {})
    for name in configured_providers():
        try:
            models = PROVIDERS[name]["fetch"]()
            if models:
                merged[name] = models
                if verbose:
                    print("  {:<12} {} models".format(name, len(models)))
            else:
                logger.warning("Provider %s returned an empty model list.", name)
        except Exception as exc:  # noqa: BLE001 - any failure falls back a layer
            logger.warning("Could not refresh %s models (%s). Using last known list.",
                           name, str(exc)[:120])
            if verbose:
                print("  {:<12} FAILED ({}) - using previous list".format(
                    name, str(exc)[:60]))
    _write_cache(merged)
    return merged


def get_registry(force_refresh: bool = False) -> Dict[str, List[str]]:
    """Return provider -> chat model ids, cheapest layer first."""
    if force_refresh:
        return refresh()
    cached = _load_cache()
    if cached:
        return cached
    return refresh()


def get_entries(force_refresh: bool = False) -> List[dict]:
    """Flatten the registry into picker entries, applying the sourcing rule.

    Returns dicts of ``{"key", "provider", "model_name"}``. ``key`` is what the
    UI shows and what ``resolve_model_config`` is given back.
    """
    registry = get_registry(force_refresh=force_refresh)
    available = set(configured_providers())
    entries = []

    for provider in ("openai", "anthropic", "google", "mistral"):
        if provider not in available:
            continue
        for model_name in registry.get(provider, []):
            entries.append({"key": model_name, "provider": provider,
                            "model_name": model_name})

    if "openrouter" in available:
        for model_name in registry.get("openrouter", []):
            # First-party wins when its key is set; otherwise OpenRouter is the
            # only door to this vendor and the duplicate is exactly what we want.
            vendor = next((p for prefix, p in OPENROUTER_FIRST_PARTY.items()
                           if model_name.startswith(prefix)), None)
            if vendor and vendor in available:
                continue
            entries.append({
                "key": "{}-openrouter".format(model_name.split("/", 1)[-1]),
                "provider": "openrouter",
                "model_name": model_name,
            })

    return entries


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    print("Configured providers:", ", ".join(configured_providers()) or "(none)")
    refresh(verbose=True)
    entries = get_entries()
    print("\n{} models available in the picker.".format(len(entries)))
