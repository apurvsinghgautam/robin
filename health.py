import os
import time
import socket
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from config import redact_secrets, RobinConfig
from search import SEARCH_ENGINES, get_tor_session, tor_bootstrapped, USER_AGENTS
from scrape import get_over_tor
from llm import get_llm
from llm_utils import resolve_model_config


def check_tor_proxy():
    """Test that Tor is accepting connections and can carry traffic.

    The SOCKS port opens about twenty seconds before Tor can build a circuit,
    so an open port on its own is reported as starting, not up."""
    try:
        start = time.time()
        sock = socket.create_connection(("127.0.0.1", 9050), timeout=5)
        sock.close()
        latency_ms = round((time.time() - start) * 1000)
    except Exception as e:
        return {"status": "down", "latency_ms": None, "error": str(e)}
    if not tor_bootstrapped(os.environ.get("ROBIN_TOR_LOG")):
        return {"status": "starting", "latency_ms": latency_ms,
                "error": "the SOCKS port is open but Tor has not bootstrapped yet"}
    return {"status": "up", "latency_ms": latency_ms, "error": None}


def check_llm_health(model_choice, cfg: Optional[RobinConfig] = None):
    """Test connectivity to the selected LLM by sending a minimal prompt.

    Returns {status, latency_ms, error, provider}. Without `cfg`, the
    configuration comes from the environment.
    """
    cfg = cfg if cfg is not None else RobinConfig.from_env()
    model_cfg = resolve_model_config(model_choice, cfg)
    if model_cfg is None:
        return {
            "status": "error",
            "latency_ms": None,
            "error": f"Unknown model: {model_choice}",
            "provider": "unknown",
        }

    # The provider name is for display only.
    class_name = getattr(model_cfg["class"], "__name__", str(model_cfg["class"]))
    ctor = model_cfg.get("constructor_params", {}) or {}
    if "ChatAnthropic" in class_name:
        provider = "Anthropic"
    elif "ChatGoogleGenerativeAI" in class_name:
        provider = "Google Gemini"
    elif "ChatOllama" in class_name:
        provider = "Ollama (local)"
    elif "ChatOpenAI" in class_name:
        base_url = (ctor.get("base_url") or "").lower()
        if "openrouter" in base_url:
            provider = "OpenRouter"
        elif "llama" in base_url or "localhost" in base_url or "127.0.0.1" in base_url:
            provider = "llama.cpp (local)"
        else:
            provider = "OpenAI"
    else:
        provider = class_name

    try:
        start = time.time()
        llm = get_llm(model_choice, cfg)
        response = llm.invoke("Say OK")
        latency_ms = round((time.time() - start) * 1000)
        text = getattr(response, "content", str(response))
        if text and len(text.strip()) > 0:
            return {
                "status": "up",
                "latency_ms": latency_ms,
                "error": None,
                "provider": provider,
            }
        else:
            return {
                "status": "down",
                "latency_ms": latency_ms,
                "error": "Empty response from API",
                "provider": provider,
            }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000)
        return {
            "status": "down",
            "latency_ms": latency_ms,
            "error": redact_secrets(e, cfg),
            "provider": provider,
        }


def _ping_single_engine(engine):
    """Ping a single search engine via Tor and return its status."""
    name = engine["name"]
    url_template = engine["url"]
    url = url_template.format(query="test")

    try:
        session = get_tor_session()
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        start = time.time()
        # Same policy as the search itself: an engine that redirects off the
        # onion space is reported down, not followed.
        resp, _ = get_over_tor(session, url, allow_clearweb=False,
                               headers=headers, timeout=20)
        # The status line is the ping. The body is never read: an engine that
        # answers with an endless page costs nothing here.
        resp.close()
        latency_ms = round((time.time() - start) * 1000)
        return {
            "name": name,
            "status": "up" if resp.status_code == 200 else "down",
            "latency_ms": latency_ms,
            "error": None if resp.status_code == 200 else f"HTTP {resp.status_code}",
        }
    except Exception as e:
        return {
            "name": name,
            "status": "down",
            "latency_ms": None,
            "error": str(e)[:80],
        }


def check_search_engines(max_workers=8):
    """Ping every search engine via Tor, concurrently.

    Returns a list of per-engine status dicts in SEARCH_ENGINES order.
    """
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_engine = {
            executor.submit(_ping_single_engine, eng): eng
            for eng in SEARCH_ENGINES
        }
        for future in as_completed(future_to_engine):
            results.append(future.result())

    name_order = {e["name"]: i for i, e in enumerate(SEARCH_ENGINES)}
    results.sort(key=lambda r: name_order.get(r["name"], 999))
    return results
