import os
from dotenv import load_dotenv

load_dotenv()


def _clean_env(name, default=None):
    value = os.getenv(name, default)
    if value is None:
        return None
    value = str(value).strip()
    # Support accidentally quoted values copied into .env
    if len(value) >= 2 and (
        (value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
    ):
        value = value[1:-1].strip()
    return value

# Configuration variables loaded from the .env file
OPENAI_API_KEY = _clean_env("OPENAI_API_KEY")
GOOGLE_API_KEY = _clean_env("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = _clean_env("ANTHROPIC_API_KEY")
OLLAMA_BASE_URL = _clean_env("OLLAMA_BASE_URL")
OPENROUTER_BASE_URL = _clean_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = _clean_env("OPENROUTER_API_KEY")
LLAMA_CPP_BASE_URL = _clean_env("LLAMA_CPP_BASE_URL")
ALLOW_CLEARWEB_FALLBACK = str(_clean_env("ALLOW_CLEARWEB_FALLBACK", "false")).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
