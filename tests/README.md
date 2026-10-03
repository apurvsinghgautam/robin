# Model compatibility checks

Run the offline suite after installing `requirements.txt`:

```bash
python -m unittest discover -s tests -t .
```

The compatibility tests inspect HTTP bodies serialized by the real provider
clients using mock transports and synthetic keys. They check sampling defaults,
typed reasoning blocks, token-split local thinking prefixes, health responses,
and all five LLM stages. The synthetic investigation fixture also detects extra
identifiers and padded relevance selections. No tests in discovery call hosted
models.

Live checks are opt-in and incur normal provider charges. Set the relevant API
keys as usual and use names available in Robin's model picker:

```bash
python -m tests.model_smoke --models gpt-5-mini gemini-3.8-flash \
  --runs 2 --output /tmp/robin-model-checks.json
```

The runner uses synthetic advisory pages and injected search/scrape functions;
it sends no real investigation data and makes no Tor requests. It checks exact
CVE/hash/email preservation, relevant and empty selections, report sections,
source links, extra artifacts, and a follow-up about a missing wallet address.
It records generated text, each check, elapsed time, errors, and dependency
versions. A failed run exits nonzero. Review the saved text for unsupported
claims: these checks cover selected behaviors rather than general report quality.
