import os
from dotenv import find_dotenv, load_dotenv

# Locate and load the nearest .env file from the current working directory or parent directories.
# This makes loading environment variables more reliable when the app is started from a subdirectory.
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)
else:
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
CUSTOM_API_BASE_URL = _clean_env("CUSTOM_API_BASE_URL")
CUSTOM_API_KEY = _clean_env("CUSTOM_API_KEY")
CUSTOM_API_MODEL = _clean_env("CUSTOM_API_MODEL")
