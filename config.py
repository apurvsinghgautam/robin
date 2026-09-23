import logging
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


# Defaults live here, not in .env. A user only needs to add a line to .env when
# they want to override one of these, so the sample file can stay short enough
# to read: API keys, and nothing else.

# Docker is the recommended install, so the container-to-host URL is the default.
# Running Robin directly with Python? Set OLLAMA_BASE_URL=http://127.0.0.1:11434
DEFAULT_OLLAMA_BASE_URL = "http://host.docker.internal:11434"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Ollama applies its own context window rather than the model's full capability,
# so Robin sets one: the default content budget plus room for prompt and
# answer. Costs RAM, so lower it on a constrained machine.
DEFAULT_OLLAMA_NUM_CTX = 32768

# The sidebar's depth settings, as the one place their numbers are written.
# `pipeline.py` imports these and the MCP tool schema is built from them, so a
# default moves in one edit rather than three.
DEFAULT_PRESET = "threat_intel"
DEFAULT_MAX_RESULTS = 50
DEFAULT_MAX_SCRAPE = 10
DEFAULT_CONTENT_CHARS = 8000
DEFAULT_THREADS = 4

# The range each depth setting accepts, shared by the web UI's sliders and the
# MCP server's tool parameters. A ROBIN_DEFAULT_* outside its range is clamped
# when it is read.
DEPTH_LIMITS = {
	"threads": (1, 16),
	"max_results": (10, 100),
	"max_scrape": (3, 20),
	"content_chars": (1000, 20000),
}

_logger = logging.getLogger("config")


def _clean_depth(name, default, limits, env=None):
	"""An integer depth setting, clamped into the range its control accepts."""
	value = _clean_int(name, default, env=env)
	low, high = limits
	clamped = min(max(value, low), high)
	if clamped != value:
		_logger.warning("%s=%s is outside %s..%s; using %s.", name, value, low, high, clamped)
	return clamped


def _is_placeholder(value):
	lowered = value.strip().strip("\"'").lower()
	return lowered.startswith("your_") or lowered in ("", "changeme", "none")


def _clean_env(name, default=None, env=None):
	"""Read one setting, honouring quotes and unedited sample placeholders.

	`env` is a mapping to read instead of os.environ, so a config can be built
	from elsewhere and these rules tested without a developer's real .env.
	"""
	value = env.get(name) if env is not None else os.getenv(name)
	if value is not None:
		value = str(value).strip()
		# Unwrap values accidentally quoted in .env.
		if len(value) >= 2 and (
			(value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
		):
			value = value[1:-1].strip()
		if not _is_placeholder(value):
			return value
	return default


def _clean_int(name, default, env=None):
	"""Same rules, then an integer. A value that is not one falls back."""
	try:
		return int(_clean_env(name, str(default), env=env))
	except (TypeError, ValueError):
		return default


@dataclass(frozen=True)
class RobinConfig:
	"""Every setting Robin reads, as one value that can be passed around."""

	openai_api_key: Optional[str] = None
	google_api_key: Optional[str] = None
	anthropic_api_key: Optional[str] = None
	ollama_base_url: Optional[str] = DEFAULT_OLLAMA_BASE_URL
	openrouter_base_url: Optional[str] = DEFAULT_OPENROUTER_BASE_URL
	openrouter_api_key: Optional[str] = None
	mistral_api_key: Optional[str] = None
	ollama_num_ctx: int = DEFAULT_OLLAMA_NUM_CTX
	llama_cpp_base_url: Optional[str] = None
	custom_api_base_url: Optional[str] = None
	custom_api_key: Optional[str] = None
	custom_api_model: Optional[str] = None
	# Where saved investigations live. Read here rather than in store.py so one
	# module owns every environment read and the same quote and placeholder
	# rules apply to this setting as to the keys.
	investigations_dir: Optional[str] = None
	# Persistent depth defaults. These are what a tool call gets when the caller
	# names no depth, on either front door.
	default_threads: int = DEFAULT_THREADS
	default_max_results: int = DEFAULT_MAX_RESULTS
	default_max_scrape: int = DEFAULT_MAX_SCRAPE
	default_content_chars: int = DEFAULT_CONTENT_CHARS
	default_preset: str = DEFAULT_PRESET
	# Whether the user set ROBIN_DEFAULT_PRESET at all. Comparing the value to
	# the built-in default cannot tell "unset" from "set to threat_intel", and
	# only the second is a choice the MCP server may act on without asking.
	default_preset_set: bool = False
	# The same for ROBIN_DEFAULT_MAX_RESULTS: only a value the user set may cap
	# what robin_search returns.
	default_max_results_set: bool = False
	# The model robin_investigate runs on when the host offers no sampling.
	robin_model: Optional[str] = None
	# Where the model cache lives.
	cache_dir: Optional[str] = None
	# Tor's notice log, read to tell bootstrapped from port-open. Unset
	# means nothing to read and the open port stands.
	tor_log: Optional[str] = None

	@classmethod
	def from_env(cls, env=None) -> "RobinConfig":
		"""Build a config from the environment, with .env already loaded above."""
		return cls(
			openai_api_key=_clean_env("OPENAI_API_KEY", env=env),
			google_api_key=_clean_env("GOOGLE_API_KEY", env=env),
			anthropic_api_key=_clean_env("ANTHROPIC_API_KEY", env=env),
			ollama_base_url=_clean_env("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL, env=env),
			openrouter_base_url=_clean_env(
				"OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL, env=env),
			openrouter_api_key=_clean_env("OPENROUTER_API_KEY", env=env),
			mistral_api_key=_clean_env("MISTRAL_API_KEY", env=env),
			ollama_num_ctx=_clean_int("OLLAMA_NUM_CTX", DEFAULT_OLLAMA_NUM_CTX, env=env),
			llama_cpp_base_url=_clean_env("LLAMA_CPP_BASE_URL", env=env),
			custom_api_base_url=_clean_env("CUSTOM_API_BASE_URL", env=env),
			custom_api_key=_clean_env("CUSTOM_API_KEY", env=env),
			custom_api_model=_clean_env("CUSTOM_API_MODEL", env=env),
			investigations_dir=_clean_env("ROBIN_INVESTIGATIONS_DIR", env=env),
			default_threads=_clean_depth(
				"ROBIN_DEFAULT_THREADS", DEFAULT_THREADS, DEPTH_LIMITS["threads"], env=env),
			default_max_results=_clean_depth(
				"ROBIN_DEFAULT_MAX_RESULTS", DEFAULT_MAX_RESULTS, DEPTH_LIMITS["max_results"], env=env),
			default_max_scrape=_clean_depth(
				"ROBIN_DEFAULT_MAX_SCRAPE", DEFAULT_MAX_SCRAPE, DEPTH_LIMITS["max_scrape"], env=env),
			default_content_chars=_clean_depth(
				"ROBIN_DEFAULT_CONTENT_CHARS", DEFAULT_CONTENT_CHARS, DEPTH_LIMITS["content_chars"], env=env),
			default_preset=_clean_env("ROBIN_DEFAULT_PRESET", DEFAULT_PRESET, env=env),
			default_preset_set=_clean_env("ROBIN_DEFAULT_PRESET", env=env) is not None,
			default_max_results_set=_clean_env("ROBIN_DEFAULT_MAX_RESULTS", env=env) is not None,
			robin_model=_clean_env("ROBIN_MODEL", env=env),
			cache_dir=_clean_env("ROBIN_CACHE_DIR", env=env),
			tor_log=_clean_env("ROBIN_TOR_LOG", env=env),
		)


_env_config = RobinConfig.from_env()


def redact_secrets(text, cfg: Optional[RobinConfig] = None) -> str:
	"""Strip configured secrets out of text that came from an authenticated call.

	A provider quotes the request back in its errors, so the text can carry the
	key that was sent. Apply before cutting: a truncated key is still leaked."""
	cfg = cfg if cfg is not None else _env_config
	out = str(text)
	for value in (cfg.openai_api_key, cfg.anthropic_api_key, cfg.google_api_key,
	              cfg.mistral_api_key, cfg.openrouter_api_key, cfg.custom_api_key):
		if value and len(value) >= 8:
			out = out.replace(value, "***")
	return out
