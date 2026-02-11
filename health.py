import time
import socket
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from search import SEARCH_ENGINES, get_tor_session, USER_AGENTS
from llm import get_llm
from llm_utils import resolve_model_config


def check_tor_proxy():
    """Test that the Tor SOCKS5 proxy on 127.0.0.1:9050 is accepting connections."""
    try:
        start = time.time()
        sock = socket.create_connection(("127.0.0.1", 9050), timeout=5)
        sock.close()
        latency_ms = round((time.time() - start) * 1000)
        return {"status": "up", "latency_ms": latency_ms, "error": None}
    except Exception as e:
        return {"status": "down", "latency_ms": None, "error": str(e)}


def check_llm_health(model_choice):
    """
    Test actual connectivity to the selected LLM by sending a minimal prompt.
    Returns {status, latency_ms, error, provider}.
    """
    config = resolve_model_config(model_choice)
    if config is None:
        return {
            "status": "error",
            "latency_ms": None,
            "error": f"Unknown model: {model_choice}",
            "provider": "unknown",
        }

    # Determine provider name for display
    class_name = getattr(config["class"], "__name__", str(config["class"]))
    ctor = config.get("constructor_params", {}) or {}
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
        llm = get_llm(model_choice)
        # Send a tiny prompt — cheapest possible API call
        response = llm.invoke("Say OK")
        latency_ms = round((time.time() - start) * 1000)
        # Extract text from response
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
            "error": str(e),
            "provider": provider,
        }


def _ping_single_engine(engine):
    """Ping a single search engine via Tor and return its status."""
    name = engine["name"]
    # Extract base URL (host only) from the template URL
    url_template = engine["url"]
    # Use a dummy query to form a valid URL for the ping
    url = url_template.format(query="test")

    try:
        session = get_tor_session()
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        start = time.time()
        resp = session.get(url, headers=headers, timeout=20)
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
    """
    Concurrently ping all search engines via Tor.
    Returns a list of per-engine status dicts.
    """
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_engine = {
            executor.submit(_ping_single_engine, eng): eng
            for eng in SEARCH_ENGINES
        }
        for future in as_completed(future_to_engine):
            results.append(future.result())

    # Sort by original engine order
    name_order = {e["name"]: i for i, e in enumerate(SEARCH_ENGINES)}
    results.sort(key=lambda r: name_order.get(r["name"], 999))
    return results
