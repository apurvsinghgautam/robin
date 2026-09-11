Contributions are welcome! To keep the development process organized, please follow the guidelines below based on the type of contribution you'd like to make.

Please submit a Pull Request exclusively for major feature updates.
- Fork the repository
- Create your feature branch (git checkout -b feature/amazing-feature)
- Commit your changes (git commit -m 'Add some amazing feature')
- Push to the branch (git push origin feature/amazing-feature)
- Open a Pull Request

For all other contributions, please open an Issue. Following counts as an Issue:
- If you spot a bug or bad code
- If you have a feature request idea
- If you have questions or doubts about usage
- If you have minor code changes

## Automated checks

Every branch push and pull request runs `.github/workflows/pr-checks.yml`:

- every module compiles and imports cleanly
- `pyflakes` reports nothing
- the bundled `models.json` seed is well-formed
- the search parser rejects engine-internal links, unwraps redirects, keeps
  non-Latin titles, and does not collapse distinct query strings
- Robin still starts with no API keys configured, showing an empty picker rather
  than crashing

Run the quick ones locally before pushing:

```bash
python -m compileall -q .
python -m pyflakes *.py
```

Before opening a bug report, check [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
Most reports turn out to be Tor not finished bootstrapping, Ollama unreachable
from inside the container, or an expired API key.

## What fits Robin

Robin is a local researcher's tool, not a multi-tenant web service. That shapes
what gets merged:

- `.onion` traffic goes through `socks5h://127.0.0.1:9050` so Tor resolves
  hostnames. Anything that resolves them locally is a privacy bug.
- Clear-web scraping is secondary and opt-in.
- Security additions should come with a threat model that fits a tool running on
  one analyst's machine.
- Model IDs are never hardcoded. `model_registry.py` discovers what each
  provider currently serves, so adding a model should require no code change.
- Never build a LangChain prompt by concatenating scraped or user text into the
  template string. Pass it as an invoke value. Dark web content is full of
  braces and will break the template.

Keep one pull request to one concern. A change that also reformats the UI, bumps
a limit, and adds a provider is three pull requests, and the useful parts end up
blocked behind the debatable ones.
