Title: Improve robustness, docs, and Tor awareness; fix CLI docs; add retries; safer LLM filtering

Summary
This PR hardens the app for real-world use, improves documentation, and addresses a few correctness bugs. It introduces:
- Fixed README development command (click subcommand) and added detailed environment variable docs.
- Added missing dependency (click) to requirements.
- Safer LLM output parsing for result indices with fallback behaviors.
- Retry with backoff for network requests; onion URL normalization.
- Tor SOCKS detection and user-facing warnings in CLI and UI.
- Configurability for Tor host/port and maximum scrape size via env vars.

Motivation
Dark web endpoints are flaky and slow. Small improvements to networking, parsing, and UX significantly increase success rates and reduce confusion (e.g., when Tor is not running). The README previously suggested a command that would fail without the click subcommand.

Changes
- requirements.txt
  - Added click dependency.
- README.md
  - Corrected development command to `python main.py cli ...`.
  - Added Environment variables section (OPENAI/ANTHROPIC/GOOGLE API keys, OLLAMA_BASE_URL, TOR_SOCKS_HOST/PORT, MAX_SCRAPE_CHARS) and Tor note.
- .env.example
  - Now includes TOR_SOCKS_HOST, TOR_SOCKS_PORT, and MAX_SCRAPE_CHARS; set OLLAMA_BASE_URL to a sensible localhost default.
- config.py
  - New config vars: TOR_SOCKS_HOST, TOR_SOCKS_PORT, MAX_SCRAPE_CHARS.
- llm.py
  - Removed direct dependency on `openai.RateLimitError`; now catches general exceptions.
  - Added robust parsing of model indices using regex with bounds checks, dedupe, and fallback to first N if model output is malformed.
- search.py
  - Added Tor availability check function `is_tor_running`.
  - Introduced `_request_with_retries` helper with exponential backoff and jitter.
  - Normalized onion links and added debug logging for parse/request failures.
- scrape.py
  - Added simple retry/backoff for scraping and debug logging.
  - Scrape size limit now configurable via `MAX_SCRAPE_CHARS`.
- main.py and ui.py
  - Display a warning if Tor SOCKS proxy is not detected.

Notes / Trade-offs
- Logging is basic (standard logging + debug lines); a future PR can introduce configurable log levels and structured logs.
- Retries are naive; next steps could migrate to httpx + asyncio and a global rate limiter.

Testing
- Manual
  - Verified README dev command works with click subcommand.
  - Simulated missing Tor to see warnings in CLI/UI.
  - Confirmed that malformed LLM output (e.g., "1, 2, x") no longer crashes filter_results.
- Suggested future automated tests (next PR):
  - Unit tests for LLM index parsing and dedup/dedup bounds.
  - Parser tests for link extraction.
  - CLI smoke tests using click.testing.

Backward compatibility
- No breaking API changes; defaults preserve previous behavior. New warnings are informational.

Roadmap follow-ups (proposed next PRs)
1) API key + model validation UX (fail-fast in CLI; badge in UI).
2) UI: list filtered results with include/exclude toggles and progress bars; export CSV/JSON of sources.
3) Docker hardening: Tor readiness wait, non-root user, optional HEALTHCHECK.
4) Logging improvements: global logger with log level env, run ID, structured logs.
5) Async httpx migration with semaphore limit for Tor friendliness.
6) Tests + CI with mocked network calls.

Checklist
- [x] Docs updated
- [x] Lint pass locally (N/A, basic changes)
- [x] Manual verification steps noted above

Screenshots
- N/A (UI change is a warning message; behavior verified locally)
