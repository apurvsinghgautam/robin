"""Live model registry."""

import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

from config import redact_secrets, RobinConfig

logger = logging.getLogger(__name__)


def _report(line: str) -> None:
    """Write one progress line to stderr, never stdout.

    `entrypoint.sh` warms the registry before the server starts, and in MCP
    mode stdout is the JSON-RPC transport. stderr still reaches `docker logs`.
    """
    sys.stderr.write(line + "\n")
    sys.stderr.flush()

SEED_PATH = Path(__file__).with_name("models.json")
CACHE_FILENAME = "models_cache.json"
# The default location, for a config that names no cache_dir. A config that
# does name one gets its own file there (see _cache_path).
CACHE_DIR = Path(os.getenv("ROBIN_CACHE_DIR") or (Path.home() / ".robin"))
CACHE_PATH = CACHE_DIR / CACHE_FILENAME

# Where each first-party catalogue lives. Also part of a cache scope, so a
# change of endpoint is a change of cache.
OPENAI_API = "https://api.openai.com/v1"
ANTHROPIC_API = "https://api.anthropic.com/v1"
GOOGLE_API = "https://generativelanguage.googleapis.com/v1beta"
MISTRAL_API = "https://api.mistral.ai/v1"

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

# Tokens that mark a model as something other than text chat, applied only where
# the provider gives no capability field of its own. A denylist on purpose:
# anything unrecognized is kept, so a newly released chat model still shows up.
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

    Sorts on the id's numeric version tokens, descending, so `gpt-5.5` precedes
    `gpt-4`. Ids carrying no version (`chat-latest`) sort last.
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
# Each returns a list of provider-side model ids, already filtered to chat.


def _fetch_openai(cfg: RobinConfig) -> List[str]:
    """OpenAI exposes no capability field, so filter by token."""
    data = _get_json(
        OPENAI_API + "/models",
        {"Authorization": "Bearer {}".format(cfg.openai_api_key)},
    )
    return sorted(
        (m["id"] for m in data.get("data", [])
         if m.get("id") and not _looks_non_chat(m["id"], "openai")),
        key=_version_sort_key,
    )


def _fetch_anthropic(cfg: RobinConfig) -> List[str]:
    """Anthropic lists chat models only; nothing to filter."""
    data = _get_json(
        ANTHROPIC_API + "/models?limit=100",
        {"x-api-key": cfg.anthropic_api_key, "anthropic-version": "2023-06-01"},
    )
    return [m["id"] for m in data.get("data", []) if m.get("id")]


def _fetch_google(cfg: RobinConfig) -> List[str]:
    """Google needs both signals: generateContent support AND a token check,
    because its image and text-to-speech models also advertise generateContent."""
    # Google pages its catalogue, so follow nextPageToken (at most 10 pages);
    # the first page alone would truncate the picker.
    entries, token, pages = [], None, 0
    while True:
        # The key travels as a header: in the query string it lands in every
        # exception message and every log line that carries the URL.
        url = GOOGLE_API + "/models?pageSize=1000"
        if token:
            url += "&pageToken=" + token
        data = _get_json(url, {"x-goog-api-key": cfg.google_api_key})
        entries.extend(data.get("models", []))
        token = data.get("nextPageToken")
        pages += 1
        if not token or pages >= 10:
            break

    out = []
    for m in entries:
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        model_id = m.get("name", "").split("/")[-1]
        if model_id and not _looks_non_chat(model_id):
            out.append(model_id)
    return sorted(out, key=_version_sort_key)


def _fetch_mistral(cfg: RobinConfig) -> List[str]:
    """Mistral carries an explicit completion_chat capability flag."""
    data = _get_json(
        MISTRAL_API + "/models",
        {"Authorization": "Bearer {}".format(cfg.mistral_api_key)},
    )
    out = []
    for m in data.get("data", []):
        caps = m.get("capabilities") or {}
        if caps and not caps.get("completion_chat", False):
            continue
        if m.get("id") and not _looks_non_chat(m["id"]):
            out.append(m["id"])
    return sorted(out)


def _openrouter_base(cfg: RobinConfig) -> str:
    """The configured OpenRouter base URL, or the public one if it is not a URL."""
    configured = (cfg.openrouter_base_url or "").strip().rstrip("/")
    if configured.startswith("http"):
        return configured
    return "https://openrouter.ai/api/v1"


def _fetch_openrouter(cfg: RobinConfig) -> List[str]:
    """OpenRouter's catalogue is public, so it lists even without a key.

    ``:batch`` variants are dropped as unusable from a streaming chat call;
    ``:free`` variants are kept, since most users want those.
    """
    base = _openrouter_base(cfg)
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
    "openai": {"fetch": _fetch_openai, "key": lambda cfg: cfg.openai_api_key},
    "anthropic": {"fetch": _fetch_anthropic, "key": lambda cfg: cfg.anthropic_api_key},
    "google": {"fetch": _fetch_google, "key": lambda cfg: cfg.google_api_key},
    "mistral": {"fetch": _fetch_mistral, "key": lambda cfg: cfg.mistral_api_key},
    "openrouter": {"fetch": _fetch_openrouter, "key": lambda cfg: cfg.openrouter_api_key},
}


# Provider -> the catalogue endpoint a config points it at.
ENDPOINTS = {
    "openai": lambda cfg: OPENAI_API,
    "anthropic": lambda cfg: ANTHROPIC_API,
    "google": lambda cfg: GOOGLE_API,
    "mistral": lambda cfg: MISTRAL_API,
    "openrouter": _openrouter_base,
}


def _scope(name: str, cfg: RobinConfig) -> str:
    """Whose catalogue a cached list is: provider, endpoint, and credential.

    A list fetched with one key from one gateway belongs to that account alone.
    The credential enters only as a SHA-256 digest, never as plaintext on disk.
    """
    endpoint = ENDPOINTS.get(name, lambda c: name)(cfg)
    spec = PROVIDERS.get(name)
    key = (spec["key"](cfg) if spec else None) or ""
    material = "\n".join((name, str(endpoint).rstrip("/"), key)).encode("utf-8")
    return "sha256:" + hashlib.sha256(material).hexdigest()[:32]


def configured_providers(cfg: Optional[RobinConfig] = None) -> List[str]:
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    return [name for name, spec in PROVIDERS.items() if _is_set(spec["key"](cfg))]


# --- The three layers ------------------------------------------------------


def _load_json_file(path: Path) -> Optional[dict]:
    """Load a JSON object, or None for anything unusable."""
    try:
        with path.open() as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_seed() -> Dict[str, List[str]]:
    payload = _load_json_file(SEED_PATH) or {}
    return payload.get("providers", {})


NEVER_FETCHED = 0.0


def _cache_path(cfg: Optional[RobinConfig] = None) -> Path:
    """The cache file for `cfg`: its own cache_dir when it names one."""
    if cfg is not None and cfg.cache_dir:
        return Path(cfg.cache_dir) / CACHE_FILENAME
    return CACHE_PATH


def _stamp_of(payload: Optional[dict]) -> Optional[float]:
    if not payload:
        return None
    stamp = payload.get("fetched_at")
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
        return None
    return float(stamp)


def _cache_fetched_at(cfg: Optional[RobinConfig] = None) -> Optional[float]:
    """When the cache was last written from a real fetch, or None."""
    return _stamp_of(_load_json_file(_cache_path(cfg)))


def _cache_stamps(cfg: Optional[RobinConfig] = None) -> Dict[str, float]:
    """When each provider last fetched successfully, for THIS configuration.

    A stamp another config's fetch earned says nothing about ours, the same
    rule the lists themselves follow."""
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    payload = _load_json_file(_cache_path(cfg)) or {}
    stamps = payload.get("stamps")
    scopes = payload.get("scopes")
    if not isinstance(stamps, dict) or not isinstance(scopes, dict):
        return {}
    return {name: float(ts) for name, ts in stamps.items()
            if isinstance(ts, (int, float)) and not isinstance(ts, bool)
            and scopes.get(name) == _scope(name, cfg)}


def _load_cache(ignore_ttl: bool = False,
                cfg: Optional[RobinConfig] = None) -> Optional[Dict[str, List[str]]]:
    """The last fetched lists that belong to `cfg`. `ignore_ttl` returns them
    however old they are."""
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    payload = _load_json_file(_cache_path(cfg))
    if not payload:
        return None
    if not ignore_ttl:
        stamp = _stamp_of(payload)
        if stamp is None or time.time() - stamp > CACHE_TTL_SECONDS:
            return None
    providers = payload.get("providers")
    scopes = payload.get("scopes")
    if not isinstance(providers, dict) or not isinstance(scopes, dict):
        return {}
    # Each provider carries its own stamp, so one that failed while another
    # succeeded is retried instead of riding the other's freshness for the TTL.
    per_provider = isinstance(payload.get("stamps"), dict)
    stamps = payload.get("stamps") if per_provider else {}
    fallback = _stamp_of(payload)
    now = time.time()

    def fresh(name):
        # A cache file with no `stamps` falls back to its one `fetched_at`; a
        # provider absent from `stamps` never fetched.
        own = stamps.get(name) if per_provider else fallback
        return isinstance(own, (int, float)) and not isinstance(own, bool) \
            and now - own <= CACHE_TTL_SECONDS

    return {
        name: models for name, models in providers.items()
        if isinstance(scopes.get(name), str) and scopes[name] == _scope(name, cfg)
        and (ignore_ttl or fresh(name))
    }


def _write_cache(providers: Dict[str, List[str]], fetched_at: float,
                 cfg: Optional[RobinConfig] = None,
                 stamps: Optional[Dict[str, float]] = None) -> None:
    """Write the lists, scoped to `cfg`, with an explicit stamp."""
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    path = _cache_path(cfg)
    payload = {
        "fetched_at": fetched_at,
        "providers": providers,
        "scopes": {name: _scope(name, cfg) for name in providers},
        "stamps": {name: float(ts) for name, ts in (stamps or {}).items()},
    }
    tmp_name = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp",
                                         delete=False) as handle:
            tmp_name = handle.name
            json.dump(payload, handle, indent=2)
        os.replace(tmp_name, path)
        tmp_name = None
    except OSError as exc:
        # A read-only filesystem is fine; the registry just refetches next start.
        logger.debug("Could not write model cache: %s", exc)
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def refresh(cfg: Optional[RobinConfig] = None,
            verbose: bool = False) -> Dict[str, List[str]]:
    """Fetch every configured provider and update the cache.

    Providers that fail keep whatever the previous layer knew about them, so one
    dead key or one unreachable API never empties the picker.
    """
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    # Seed first, then whatever we last fetched on top of it, expired or not.
    # A provider that failed to refresh keeps its last known list.
    merged = dict(_load_seed())
    own_lists = _load_cache(ignore_ttl=True, cfg=cfg) or {}
    merged.update(own_lists)
    # The previous stamp is ours to keep only if the file held our lists: a
    # stamp another config's fetch earned must not make our fallback fresh.
    previous_fetch = _cache_fetched_at(cfg) if own_lists else None
    fetched_ok = set()
    for name in configured_providers(cfg):
        try:
            models = PROVIDERS[name]["fetch"](cfg)
            if models:
                merged[name] = models
                fetched_ok.add(name)
                if verbose:
                    _report("  {:<12} {} models".format(name, len(models)))
            else:
                logger.warning("Provider %s returned an empty model list.", name)
        except Exception as exc:  # noqa: BLE001 - any failure falls back a layer
            # Redacted before it is cut: a truncated key is still a leaked one.
            safe = redact_secrets(exc, cfg)
            logger.warning("Could not refresh %s models (%s). Using last known list.",
                           name, safe[:120])
            if verbose:
                _report("  {:<12} FAILED ({}) - using previous list".format(
                    name, safe[:60]))
    # `fetched_at` records a successful fetch, not an attempt: after a total
    # failure the previous stamp stands, so an outage never looks fresh.
    if fetched_ok:
        stamp = time.time()
    elif previous_fetch is not None:
        stamp = previous_fetch
    else:
        stamp = NEVER_FETCHED
    stamps = dict(_cache_stamps(cfg) if own_lists else {})
    stamps.update({name: time.time() for name in fetched_ok})
    _write_cache(merged, stamp, cfg, stamps=stamps)
    return merged


def get_registry(cfg: Optional[RobinConfig] = None,
                 force_refresh: bool = False) -> Dict[str, List[str]]:
    """Return provider -> chat model ids, cheapest layer first."""
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    if force_refresh:
        return refresh(cfg)
    cached = _load_cache(cfg=cfg)
    if cached:
        # A cache written before a provider was configured has no entry for it,
        # or only the bundled seed's. Refresh then, so a newly added API key
        # takes effect at once rather than when the TTL expires.
        missing = [p for p in configured_providers(cfg) if p not in cached]
        if not missing:
            return cached
        logger.info("Refreshing: %s configured since the cache was written.",
                    ", ".join(missing))
    return refresh(cfg)


def get_entries(cfg: Optional[RobinConfig] = None,
                force_refresh: bool = False) -> List[dict]:
    """Flatten the registry into picker entries, applying the sourcing rule.

    Returns dicts of ``{"key", "provider", "model_name"}``. ``key`` is what the
    UI shows and what ``resolve_model_config`` is given back.
    """
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    registry = get_registry(cfg, force_refresh=force_refresh)
    available = set(configured_providers(cfg))
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
    _cli_cfg = RobinConfig.from_env()
    _report("Configured providers: "
            + (", ".join(configured_providers(_cli_cfg)) or "(none)"))
    refresh(_cli_cfg, verbose=True)
    entries = get_entries(_cli_cfg)
    _report("\n{} models available in the picker.".format(len(entries)))
