# Troubleshooting

Most Robin problems fall into one of four buckets: Tor isn't ready, the LLM
provider isn't configured the way Robin expects, the model list is stale, or the
dark web genuinely had nothing to say about your query. Work through the section
that matches what you're seeing.

If none of this helps, open an issue and include the Robin version, whether you
use the web UI or the MCP server, the provider you selected, and the console
output.

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

1. In `.env`, set `OLLAMA_BASE_URL=http://host.docker.internal:11434`.
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

Providers retire models, so Robin keeps no hardcoded model list: it asks each
provider what it currently serves and caches the answer.

- Restart Robin to force a refresh. The container refreshes on start.
- Delete the cache to force a rebuild: remove `~/.robin/models_cache.json`, or
  whatever `ROBIN_CACHE_DIR` points at. A damaged cache repairs itself on the
  next launch, so this is rarely necessary.
- Set `MODEL_REGISTRY_TTL_HOURS` to control how long a fetched list is reused.
  The default is 24.
- If a provider is unreachable, Robin keeps the last list it had rather than
  emptying the picker, so a stale entry can survive an outage. A restart with
  the network back will clear it.
- The bundled offline list covers OpenAI, Anthropic, Google and OpenRouter.
  Mistral has no bundled entry yet, so a Mistral-only setup needs one
  successful online run before its models appear. Robin will name the provider
  it could not reach rather than claiming nothing is configured.

## Local model answers ignore the end of the investigation

Ollama applies its own context window rather than the model's full capability,
so a 128k-capable model can still be truncated to a few thousand tokens. Robin
sets it explicitly, defaulting to 32768.

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

## Saved investigations fail with permission denied on Linux

The container runs as UID 1000, not root. A bind mount keeps the ownership it
has on your host, so if the directory you mounted at `/app/investigations`
belongs to a different user, Robin cannot write into it. You will see one line
like this at startup:

```
WARNING: /app/investigations is not writable by UID 1000, so saved investigations will fail.
```

The investigation itself still runs and the report still renders in the
browser. Only the save to disk fails.

This is a Linux-only problem. Docker Desktop on macOS and Windows maps the
mount to whoever is running the container, so there is nothing to fix there.

Two fixes work. Pick one:

- **Use a named volume instead of a folder.** Docker creates it owned by the
  container's user, so there is nothing to get wrong, on any OS. It is also
  the volume the agent commands in the README mount, so the UI and your agent
  see the same reports:
  ```bash
  docker run --rm \
     -v "$(pwd)/.env:/app/.env" \
     -v robin-investigations:/app/investigations \
     --add-host=host.docker.internal:host-gateway \
     -p 8501:8501 \
     apurvsg/robin:latest
  ```
- **Keep the folder, and give it to UID 1000.** This is the fix when you want
  the JSON files on your own disk. It usually means Docker created the folder
  as root, because the path you passed to `-v` did not exist yet:
  ```bash
  sudo chown -R 1000:1000 investigations
  ```
  Your own account can still read the files. To write into the folder from
  the host as well, add yourself to a group that owns it, or copy the files
  out.

Do not run the container as a different user with `--user`. Tor keeps its
state in `/home/robin/.tor`, which is private to UID 1000, so under any other
UID Tor cannot start and Robin never gets past "Waiting for Tor".

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

It shouldn't. Robin drops any result pointing at one of the 16 search engines it
queries, ignores an engine's own navigation links, and unwraps engine redirect
links to the real target underneath. If you still see one, please open an issue
with the query and the engine.

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

**Tor never finishes bootstrapping.** Tor writes its progress to a log file
inside the container rather than to `docker logs`. Check it with
`docker exec <container> grep Bootstrapped /home/robin/tor-notices.log` and wait
for `Bootstrapped 100% (done)`. On a slow connection this takes a minute or two.

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

Robin stops and says so when there is nothing to report from, rather than
summarizing whatever links it happened to hold. There are four stops, and the
MCP server returns the same four as a `status`:

- **"No search engine answered, so nothing was searched."**
  (`engines_unreachable`) This is an outage, not an empty dark web. Run
  **Check Search Engines**, confirm Tor has bootstrapped, and run the query
  again; an outage is never served from the cache.
- **"No dark web results came back for this query."** (`no_results`) The
  engines answered with nothing. Very specific identifiers often have no dark
  web presence at all, and that is a real answer. Try broader terms.
- **"Found N raw links, but none of them matched this query."**
  (`nothing_relevant`) The model judged every result off topic. Try a
  different phrasing, or raise **Max Results to Filter** to give it more
  candidates.
- **"Found N relevant results, but none of the pages could be read over Tor
  right now."** (`nothing_readable`) Every kept page timed out or refused the
  connection. Onion services go up and down; retry in a few minutes, or raise
  **Max Pages to Scrape** so more candidates get a chance. Through the MCP
  server the reply carries the kept links, so your agent can retry them with
  `robin_scrape`.

Non-English titles (Cyrillic, CJK, Arabic) are kept, so a query in another
language is fine.

## The agent says the MCP server produced invalid output

In stdio mode the container's stdout *is* the wire: it carries nothing but
JSON-RPC. Anything else printed there — a stray `print()`, a library banner, a
warning that went to stdout instead of stderr — lands in the middle of a message
and the host rejects the whole exchange.

Robin's own modules write nothing to stdout. Every log line, every warning, and
the entrypoint's startup messages go to stderr instead, so:

- Look at stderr, not at the chat transcript. `docker logs <container>` while the
  container is alive, or start the same command in a terminal by hand and watch
  the second stream. Most hosts also keep a per-server MCP log.
- If you are running a fork or a local build, grep your changes for `print(`.
  Use `logging` instead; it goes to stderr.
- Confirm you passed `-i`. Without it the container has no stdin, the server has
  nothing to read, and the host reports a broken server rather than a missing
  flag.

## Robin says it has no model of its own

Three replies say this, and none of them is an error. Robin runs a model only
when your client offers MCP sampling or you configured one; most hosts do
neither, and the tools-and-prompts workflow is designed for exactly that.

- **`status: refine_it_yourself`** from `robin_refine`. Robin hands back the
  refiner's own rules and you write the query. Your host is a model, so this
  costs nothing.
- **`status: unfiltered`** from `robin_filter`. Robin judged nothing, so it
  dropped nothing: every result comes back and every one is scrapeable. The
  reply carries the filter's own rules and tells the host to run that pass
  before scraping, so the step still happens, on the host's model instead of
  Robin's.
- **`status: needs_domain`** from `robin_search`. Not about models at all: the
  research domain is the user's to choose, so nothing is searched until they
  have. Ask them, then pass `preset` with `user_chose=true`.

To have Robin judge relevance itself, give the container a provider key in its
environment (and `ROBIN_MODEL` to pick the model), or use a client that
supports sampling. With one, `robin_filter` returns only the results it
judges on topic, most relevant first.

## ChatGPT cannot connect, or the tools never appear in a chat

ChatGPT has two MCP surfaces and they are not interchangeable.

**Settings → MCP servers** (desktop app) configures the Codex host, shared with
the Codex CLI and the IDE extension. Robin starts fine there — you will see its
Tor lines — but its tools appear in Codex sessions, not in an ordinary chat.
Raise `tool_timeout_sec` in `~/.codex/config.toml`: a Tor search outlasts the
default.

**Connectors** (*Settings → Apps & Connectors*) are what an ordinary chat uses.
They run in OpenAI's infrastructure and cannot start or reach a server on your
machine, so Robin cannot be one. Use the Codex surface above instead.

If tools are listed but a call never runs, check the client's approval policy.
A policy set never to ask also never approves, so the call is declined before
it reaches Robin.

## Tools report tor_bootstrapping

Tor starts with the container and needs time to build its first circuits. The MCP
server answers `initialize` straight away so your host does not time out waiting
for it, which means a tool can be called before Tor is ready. Until Tor reports
`Bootstrapped 100%`, every Tor-dependent tool reports `tor_bootstrapping` and
asks you to retry, rather than return an empty result that reads like "nothing
found". Nothing is searched or fetched while it says so.

Wait a few seconds and call again; `robin_health` shows `tor: up` once it is
ready. On a slow connection that takes a minute or two. If it never clears, the
problem is Tor rather than Robin — see **Tor problems** above.

## Claude Code truncates the tool output

Claude Code caps MCP tool results at 25,000 tokens by default and warns at
10,000. A generous scrape is the usual cause: ten pages at 8,000 characters is
roughly 20,000 tokens before anything else is added.

- Raise the cap with `MAX_MCP_OUTPUT_TOKENS` in the environment Claude Code runs
  in.
- Or ask for less per call. Lower **Content per Page** (`content_chars`), or pass
  fewer page ids to each `robin_scrape` call. For Claude Code, Robin bounds one
  call's output at 60,000 characters anyway and tells you which pages fit, so
  splitting a scrape across two calls costs nothing but the second call. If you
  raised `MAX_MCP_OUTPUT_TOKENS`, have your agent pass a larger `max_chars` so
  Robin's bound moves with it; `max_chars=0` removes it.

## Reporting a bug

Include:

- Robin version, and whether you use the web UI or the MCP server (and which host)
- The provider and model you selected
- Whether Tor reached `Bootstrapped 100%` (see **Tor problems** for how to check)
- The output of **Check Search Engines**
- The full error text, not a screenshot crop
- The **Content per Page** and **Max Pages to Scrape** values you were using

Redact your API keys and any sensitive query terms before posting.
