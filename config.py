import os
from dotenv import load_dotenv

load_dotenv()

# Configuration variables loaded from the .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLAMA_CPP_BASE_URL= os.getenv("LLAMA_CPP_BASE_URL")

# HTTP backend configuration
# Set to "pycurl" to use libcurl (recommended for .onion sites)
# Set to "requests" to use Python requests library
USE_PYCURL = os.getenv("USE_PYCURL", "true").lower() in ("true", "1", "yes")