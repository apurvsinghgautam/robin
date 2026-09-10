import os
from dotenv import load_dotenv

load_dotenv()


# Defaults live here, not in .env. A user only needs to add a line to .env when
# they want to override one of these, so the sample file can stay short enough
# to read: API keys, and nothing else.
#
# Precedence: .env / environment  >  the default below.
# An unedited placeholder (`your_ollama_url`) counts as "not set", so someone
# who copies an older sample file still lands on the working default.


def _is_placeholder(value):
	lowered = value.strip().strip("\"'").lower()
	return lowered.startswith("your_") or lowered in ("", "changeme", "none")


def _clean_env(name, default=None):
	value = os.getenv(name)
	if value is not None:
		value = str(value).strip()
		# Support accidentally quoted values copied into .env
		if len(value) >= 2 and (
			(value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
		):
			value = value[1:-1].strip()
		if not _is_placeholder(value):
			return value
	return default

# Configuration variables loaded from the .env file
OPENAI_API_KEY = _clean_env("OPENAI_API_KEY")
GOOGLE_API_KEY = _clean_env("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = _clean_env("ANTHROPIC_API_KEY")
# Docker is the recommended install, so the container-to-host URL is the default.
# Running Robin directly with Python? Set OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_BASE_URL = _clean_env("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OPENROUTER_BASE_URL = _clean_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = _clean_env("OPENROUTER_API_KEY")
MISTRAL_API_KEY = _clean_env("MISTRAL_API_KEY")
LLAMA_CPP_BASE_URL = _clean_env("LLAMA_CPP_BASE_URL")
CUSTOM_API_BASE_URL = _clean_env("CUSTOM_API_BASE_URL")
CUSTOM_API_KEY = _clean_env("CUSTOM_API_KEY")
CUSTOM_API_MODEL = _clean_env("CUSTOM_API_MODEL")
