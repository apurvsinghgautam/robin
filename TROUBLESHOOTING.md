# Troubleshooting

Most Robin problems fall into one of four buckets: Tor isn't ready, the LLM
provider isn't configured the way Robin expects, the model list is stale, or the
dark web genuinely had nothing to say about your query. Work through the section
that matches what you're seeing.

If none of this helps, open an issue and include the Robin version, how you're
running it (Docker or local), the provider you selected, and the console output.

---

## The model dropdown is empty, or only shows one provider

Robin only lists models for providers whose API key it can actually see. An
empty dropdown means it found no keys at all.

- Confirm your `.env` sits next to where you launched Robin, and that Docker is
  mounting it: `-v "$(pwd)/.env:/app/.env"`.
- You only need the key for the provider you intend to use. A `.env` containing
  nothing but `ANTHROPIC_API_KEY` is fine, and Robin will show Claude models
  only. There is no requirement to set `OPENAI_API_KEY` if you aren't using it.
- Supported keys are `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`,
  `MISTRAL_API_KEY` and `OPENROUTER_API_KEY`. Local servers (Ollama, llama.cpp,
  any OpenAI-compatible endpoint) need no key at all.
- Only API keys belong in `.env`. Everything else, Ollama's URL included, has a
  working default in `config.py`; add a line only to override one.
- Leftover `your_...` placeholders from an older sample file are harmless. Robin
  treats them as unset and falls back to the default.
- Keys are read at startup. Restart Robin after editing `.env`.

## Ollama models don't appear

This is almost always the container being unable to reach Ollama on the host.

1. In `.env`, set `OLLAMA_BASE_URL=http://host.docker.internal:11434` when
   running under Docker. Use `http://127.0.0.1:11434` only when running Robin
   directly on the host.
2. Run the container with `--add-host=host.docker.internal:host-gateway`.
3. Serve Ollama on all interfaces, not just loopback. Ollama binds to
   `127.0.0.1` by default, which a container cannot reach no matter what
   `OLLAMA_BASE_URL` says.

   If you started Ollama yourself:
   ```bash
   OLLAMA_HOST=0.0.0.0 ollama serve &
   ```

   If Ollama runs as a systemd service, which is the default on most Linux
   installs, the command above will not help because systemd is already running
   its own copy. Edit the service instead:
   ```bash
   sudo systemctl edit ollama.service
   # add these two lines:
   #   [Service]
   #   Environment="OLLAMA_HOST=0.0.0.0"
   sudo systemctl daemon-reload && sudo systemctl restart ollama
   ```

   On macOS, quit the Ollama app first, then run the `ollama serve` command
   above in a terminal.

   Confirm it worked: `curl http://localhost:11434/api/tags` should answer, and
   `ss -lntp | grep 11434` should show `0.0.0.0:11434` rather than
   `127.0.0.1:11434`.
4. Confirm you have actually pulled a model: `ollama list`. Robin lists what
   Ollama reports, so an empty Ollama means an empty section in the picker.

## "Model not found", "this model is out of date", or a failing connection check

Providers retire models. From v2.9 Robin no longer ships a hardcoded model list;
it asks each provider what it currently serves and caches the answer.

- Restart Robin to force a refresh. The container refreshes on start.
- Delete the cache to force a rebuild: remove `~/.robin/models_cache.json`, or
  whatever `ROBIN_CACHE_DIR` points at. A damaged cache repairs itself on the
  next launch, so this is rarely necessary.
- Set `MODEL_REGISTRY_TTL_HOURS` to control how long a fetched list is reused.
  The default is 24.
- If a provider is unreachable, Robin keeps the last list it had rather than
  emptying the picker, so a stale entry can survive an outage. A restart with
  the network back will clear it.

## Local model answers ignore the end of the investigation

Ollama applies its own context window rather than the model's full capability,
so a 128k-capable model can still be truncated to a few thousand tokens. Robin
now sets it explicitly, defaulting to 32768.

- Lower it if your machine is short on RAM: `OLLAMA_NUM_CTX=8192` in `.env`.
- Keep it above the budget you asked for. The sidebar caption under **Content
  per Page** shows the estimated tokens per investigation; the window needs to
  hold that plus the prompt and the answer.
- Reducing **Content per Page** or **Max Pages to Scrape** is the other lever.

## Docker container won't start, or the port is taken

- **"port is already allocated"** or **"name already in use"**: an earlier Robin
  container is still around. Remove it with `docker rm -f robin`, or list what
  is running with `docker ps -a`. The commands in the README use `--rm` so the
  container cleans itself up on exit; if you added `--name robin` yourself,
  you need to remove it between runs.
- **Port 8501 in use by something else**: map a different one, for example
  `-p 8600:8501`, then open `http://localhost:8600`.
- **`.env` not picked up**: the mount is literal. Run the command from the
  directory that holds your `.env`, or give the full path in place of
  `$(pwd)/.env`.
- **`host.docker.internal` not resolving on Linux**: the
  `--add-host=host.docker.internal:host-gateway` flag is what creates it. It is
  in the README command; if you wrote your own, add it.

## Reports feel thin, or an investigation costs more than expected

Two sidebar sliders decide how much the model actually reads, and the caption
under them shows the estimated tokens per investigation before you run it.

- **Content per Page** is how much of each scraped page reaches the model.
  Default 8,000 characters. Raise it when reports miss detail that you can see
  on the page yourself; lower it to cut cost. Raising it never slows the Tor
  scrape, because the trim happens after the page is already downloaded.
- **Max Pages to Scrape** is how many results get scraped and summarized.
- **Max Results to Filter** is how many raw results the model chooses from. It
  affects selection quality, not how much text is read.

If reports are thin but the sources look right, raise Content per Page first.
If the investigation is expensive, lower Max Pages to Scrape first, since it
multiplies the per-page budget.

## Why does an engine appear in my results?

It shouldn't, and from v2.9 it doesn't. Robin drops any result pointing at one
of the 16 search engines it queries, and unwraps engine redirect links to the
real target underneath. Earlier versions collected every `.onion` link on the
page, including the engine's own navigation, categories, adverts and footer, so
reports could be written from a search engine's menu. If you still see one,
please open an issue with the query and the engine.

## 401 / "User not found" / authentication errors

- Regenerate the key. This is by far the most common cause, especially on
  OpenRouter, where the message reads `401 - User not found`.
- Don't wrap values in quotes in `.env`. Write `OPENAI_API_KEY=sk-...`, not
  `OPENAI_API_KEY="sk-..."`. Robin strips matched quotes defensively, but
  unmatched ones will break.
- Watch for trailing spaces and line breaks introduced by copy-paste from a
  provider dashboard.
- Confirm the key's account actually has access to the model you selected.

## Tor problems

Robin routes `.onion` traffic through `socks5h://127.0.0.1:9050` and lets Tor do
the hostname resolution. It cannot work without a running Tor.

**Tor never finishes bootstrapping.** Wait for `Bootstrapped 100% (done)` in the
logs before running a search. On a slow connection this takes a minute or two.

**`Closed N streams for service [scrubbed].onion for reason resolve failed.
Fetch status: No more HSDir available to query.`** This is Tor saying the hidden
service could not be found on the network right now. It is not a Robin error.
Usually it means the onion service is down, or your circuit is unlucky. Run
**Check Search Engines** in the sidebar to see which engines are actually
responding, and retry.

**Running from a censored network.** Robin does not manage bridges. Configure
`obfs4` or `webtunnel` bridges in your own `torrc` and confirm Tor bootstraps to
100% before starting Robin. Bridge questions are better raised with the Tor
project than here; recycled bridge addresses from public channels are frequently
blocked or rate-limited.

## Search engine links look dead

Onion services have irregular uptime. That is normal, and it's exactly why Robin
queries many engines rather than one: it's unlikely they all go down together.
Use **Check Search Engines** in the sidebar to see live status. An engine that
was down yesterday is often back today, so please check before reporting a link
as permanently dead.

## "No results found" instead of a report

From v2.9 Robin stops and tells you when a search returns nothing relevant,
rather than summarizing whatever links it happened to hold. Earlier versions
would fall back to the top raw links, which produced confident reports written
from search engine navigation pages.

If you're seeing this more than you expect:

- Broaden the query. Very specific identifiers often have no dark web presence
  at all, and that is a real answer.
- Non-English results are supported. Earlier versions discarded Cyrillic, CJK
  and Arabic titles at the search layer; from v2.9 they are kept.
- Check how many engines responded. If only one or two did, coverage is thin.
- Raise **Max Results to Filter** in the sidebar to give the filtering model
  more candidates to work with.

## Reporting a bug

Include:

- Robin version, and whether you're on Docker or a local install
- The provider and model you selected
- Whether Tor reached `Bootstrapped 100%`
- The output of **Check Search Engines**
- The full error text, not a screenshot crop
- The **Content per Page** and **Max Pages to Scrape** values you were using

Redact your API keys and any sensitive query terms before posting.
