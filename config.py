"""Configuration for Robin - Claude Agent SDK version."""
import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic API key (or rely on Claude Code Max subscription)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Tor proxy settings
TOR_SOCKS_PROXY = os.getenv("TOR_SOCKS_PROXY", "socks5h://127.0.0.1:9050")

# Agent settings
DEFAULT_MODEL = os.getenv("ROBIN_MODEL", "claude-sonnet-4-20250514")
MAX_SEARCH_WORKERS = int(os.getenv("MAX_SEARCH_WORKERS", "5"))
MAX_SCRAPE_WORKERS = int(os.getenv("MAX_SCRAPE_WORKERS", "5"))
MAX_AGENT_TURNS = int(os.getenv("MAX_AGENT_TURNS", "20"))
