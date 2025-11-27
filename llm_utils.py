"""
LLM utilities for model configuration and management.
"""

import logging
import time
from typing import Callable, Optional, List, Dict, Any
from urllib.parse import urljoin

import requests
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.callbacks.base import BaseCallbackHandler

from config import OLLAMA_BASE_URL, OPENROUTER_BASE_URL, OPENROUTER_API_KEY, GOOGLE_API_KEY

logger = logging.getLogger(__name__)

# Cache for Ollama models with TTL
_ollama_models_cache: List[str] = []
_ollama_cache_timestamp: float = 0
_OLLAMA_CACHE_TTL_SECONDS = 300  # 5 minutes


class BufferedStreamingHandler(BaseCallbackHandler):
    """Handler for buffered streaming output from LLMs."""

    def __init__(
        self,
        buffer_limit: int = 60,
        ui_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        self.buffer = ""
        self.buffer_limit = buffer_limit
        self.ui_callback = ui_callback

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Handle new token from LLM."""
        self.buffer += token
        if "\n" in token or len(self.buffer) >= self.buffer_limit:
            print(self.buffer, end="", flush=True)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""

    def on_llm_end(self, response, **kwargs) -> None:
        """Handle end of LLM response."""
        if self.buffer:
            print(self.buffer, end="", flush=True)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""


# Common LLM parameters
_common_callbacks = [BufferedStreamingHandler(buffer_limit=60)]

_common_llm_params: Dict[str, Any] = {
    "temperature": 0,
    "streaming": True,
    "callbacks": _common_callbacks,
}

# Model configuration map
_llm_config_map: Dict[str, Dict[str, Any]] = {
    'gpt-4.1': {
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-4.1'}
    },
    'gpt-5.1': {
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-5.1'}
    },
    'gpt-5-mini': {
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-5-mini'}
    },
    'gpt-5-nano': {
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-5-nano'}
    },
    'claude-sonnet-4-5': {
        'class': ChatAnthropic,
        'constructor_params': {'model': 'claude-sonnet-4-5'}
    },
    'claude-sonnet-4-0': {
        'class': ChatAnthropic,
        'constructor_params': {'model': 'claude-sonnet-4-0'}
    },
    'gemini-2.5-flash': {
        'class': ChatGoogleGenerativeAI,
        'constructor_params': {'model': 'gemini-2.5-flash', 'google_api_key': GOOGLE_API_KEY}
    },
    'gemini-2.5-flash-lite': {
        'class': ChatGoogleGenerativeAI,
        'constructor_params': {'model': 'gemini-2.5-flash-lite', 'google_api_key': GOOGLE_API_KEY}
    },
    'gemini-2.5-pro': {
        'class': ChatGoogleGenerativeAI,
        'constructor_params': {'model': 'gemini-2.5-pro', 'google_api_key': GOOGLE_API_KEY}
    },
    'gpt-5.1-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'openai/gpt-5.1',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    'gpt-5-mini-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'openai/gpt-5-mini',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    'claude-sonnet-4.5-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'anthropic/claude-sonnet-4.5',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    'grok-4.1-fast-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'x-ai/grok-4.1-fast',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
}


def _normalize_model_name(name: str) -> str:
    """Normalize model name for case-insensitive comparison."""
    return name.strip().lower()


def _get_ollama_base_url() -> Optional[str]:
    """Get the Ollama base URL with trailing slash."""
    if not OLLAMA_BASE_URL:
        return None
    return OLLAMA_BASE_URL.rstrip("/") + "/"


def fetch_ollama_models(use_cache: bool = True) -> List[str]:
    """
    Retrieve the list of locally available Ollama models.

    Args:
        use_cache: Whether to use cached results (default: True)

    Returns:
        List of available Ollama model names
    """
    global _ollama_models_cache, _ollama_cache_timestamp

    # Check cache
    if use_cache and _ollama_models_cache:
        cache_age = time.time() - _ollama_cache_timestamp
        if cache_age < _OLLAMA_CACHE_TTL_SECONDS:
            logger.debug(f"Using cached Ollama models (age: {cache_age:.1f}s)")
            return _ollama_models_cache

    base_url = _get_ollama_base_url()
    if not base_url:
        return []

    try:
        resp = requests.get(urljoin(base_url, "api/tags"), timeout=3)
        resp.raise_for_status()
        models = resp.json().get("models", [])

        available = []
        for m in models:
            name = m.get("name") or m.get("model")
            if name:
                available.append(name)

        # Update cache
        _ollama_models_cache = available
        _ollama_cache_timestamp = time.time()
        logger.debug(f"Fetched {len(available)} Ollama models")

        return available

    except requests.RequestException as e:
        logger.debug(f"Failed to fetch Ollama models: {e}")
        return _ollama_models_cache if _ollama_models_cache else []
    except (ValueError, KeyError) as e:
        logger.debug(f"Failed to parse Ollama response: {e}")
        return _ollama_models_cache if _ollama_models_cache else []


def get_model_choices() -> List[str]:
    """
    Get all available model choices.

    Returns:
        List of model names (cloud models + Ollama models)
    """
    base_models = list(_llm_config_map.keys())
    dynamic_models = fetch_ollama_models()

    normalized = {_normalize_model_name(m): m for m in base_models}
    for dm in dynamic_models:
        key = _normalize_model_name(dm)
        if key not in normalized:
            normalized[key] = dm

    # Preserve order: base models first, then dynamic ones alphabetically
    ordered_dynamic = sorted(
        [name for key, name in normalized.items() if name not in base_models],
        key=_normalize_model_name,
    )

    return base_models + ordered_dynamic


def resolve_model_config(model_choice: str) -> Optional[Dict[str, Any]]:
    """
    Resolve a model choice to its configuration.

    Args:
        model_choice: The model name (case-insensitive)

    Returns:
        Configuration dictionary or None if not found
    """
    model_choice_lower = _normalize_model_name(model_choice)

    # Check predefined models first
    config = _llm_config_map.get(model_choice_lower)
    if config:
        return config

    # Check Ollama models
    for ollama_model in fetch_ollama_models():
        if _normalize_model_name(ollama_model) == model_choice_lower:
            return {
                "class": ChatOllama,
                "constructor_params": {
                    "model": ollama_model,
                    "base_url": OLLAMA_BASE_URL
                },
            }

    return None


def clear_ollama_cache() -> None:
    """Clear the Ollama models cache."""
    global _ollama_models_cache, _ollama_cache_timestamp
    _ollama_models_cache = []
    _ollama_cache_timestamp = 0
    logger.debug("Ollama cache cleared")
