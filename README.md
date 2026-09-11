<div align="center">
   <img src=".github/assets/logo.png" alt="Logo" width="300">
   <br><a href="https://github.com/apurvsinghgautam/robin/actions/workflows/release.yml"><img alt="Release" src="https://github.com/apurvsinghgautam/robin/actions/workflows/release.yml/badge.svg"></a> <a href="https://github.com/apurvsinghgautam/robin/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/apurvsinghgautam/robin"></a> <a href="https://hub.docker.com/r/apurvsg/robin"><img alt="Docker Pulls" src="https://img.shields.io/docker/pulls/apurvsg/robin"></a>
   <p align="center">
 <a href="https://www.star-history.com/apurvsinghgautam/robin"><img src="https://api.star-history.com/badge?repo=apurvsinghgautam/robin&type=trending" alt="GitHub Trending Repository of the Day" /></a>
</p>
   <h1>Robin: AI-Powered Dark Web OSINT Tool</h1>

   <p>Robin is an AI-powered tool for conducting dark web OSINT investigations. It leverages LLMs to refine queries, filter search results from dark web search engines, and provide an investigation summary.</p>
   <a href="#installation">Installation</a> &bull; <a href="#troubleshooting">Troubleshooting</a> &bull; <a href="#contributing">Contributing</a> &bull; <a href="#acknowledgements">Acknowledgements</a><br><br>
</div>

![Demo](.github/assets/screen-ui.png)


## Architecture
![Workflow](.github/assets/robin-workflow.png)

---

## Features

- ⚙️ **Modular Architecture** – Clean separation between search, scrape, and LLM workflows.
- 🤖 **Multi-Model Support** – Easily switch between OpenAI, Claude, Gemini, Ollama, or any OpenAI-compatible API (LM Studio, llama.cpp, Groq, etc.).
- 🌐 **Web UI** – Streamlit-based interface for interactive investigations.
- 💬 **Conversational Follow-ups** – Ask grounded follow-up questions about an investigation without re-running the search — answered from that investigation's own data.
- 🔀 **One-Click Pivots** – Suggested follow-up queries surfaced from the findings; click one to launch a fresh investigation.
- 🐳 **Docker-Ready** – Recommended Docker deployment for clean, isolated usage.
- 📝 **Custom Reporting** – Save investigation output to file for reporting or further analysis.
- 🧩 **Extensible** – Easy to plug in new search engines, models, or output formats.

---

## ⚠️ Disclaimer
> This tool is intended for educational and lawful investigative purposes only. Accessing or interacting with certain dark web content may be illegal depending on your jurisdiction. The author is not responsible for any misuse of this tool or the data gathered using it.
>
> Use responsibly and at your own risk. Ensure you comply with all relevant laws and institutional policies before conducting OSINT investigations.
>
> Additionally, Robin leverages third-party APIs (including LLMs). Be cautious when sending potentially sensitive queries, and review the terms of service for any API or model provider you use.

## Installation
> [!NOTE]
> The tool needs Tor to do the searches. You can install Tor using `apt install tor` on Linux/Windows(WSL) or `brew install tor` on Mac. Once installed, confirm if Tor is running in the background.

> [!TIP]
> You can provide your LLM of choice API key by either creating .env file (refer to sample env file in the repo) or by setting env variables in PATH.
>
> For Ollama, nothing goes in your `.env`. Robin defaults to `http://host.docker.internal:11434`, which is what the recommended Docker install needs. Two things are still on you:
>
> 1. Run the container with `--add-host=host.docker.internal:host-gateway` (the README command already does).
> 2. Make Ollama listen on all interfaces, since it binds to `127.0.0.1` by default and a container cannot reach that. If you start it yourself, `OLLAMA_HOST=0.0.0.0 ollama serve &`. If it runs under systemd, `sudo systemctl edit ollama.service`, add `[Service]` and `Environment="OLLAMA_HOST=0.0.0.0"`, then `sudo systemctl daemon-reload && sudo systemctl restart ollama`.
>
> Running Robin directly with Python instead of Docker? Add `OLLAMA_BASE_URL=http://127.0.0.1:11434` to override the default. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if it still doesn't appear.
>
> For any other OpenAI-compatible provider (LM Studio, llama.cpp, Groq, etc.), use the **🔌 Custom API Provider** expander in the sidebar — no `.env` changes required. Enter the base URL, an optional API key, and optionally a model name if the provider doesn't expose `/v1/models` for auto-discovery.

### Docker [Recommended]

- Pull the latest Robin docker image
```bash
docker pull apurvsg/robin:latest
```

- Run the docker image as:
```bash
docker run --rm \
   -v "$(pwd)/.env:/app/.env" \
   --add-host=host.docker.internal:host-gateway \
   -p 8501:8501 \
   apurvsg/robin:latest
```

> [!TIP]
> To persist saved investigations across Docker restarts, mount a local directory:
> ```bash
> docker run --rm \
>    -v "$(pwd)/.env:/app/.env" \
>    -v "$(pwd)/investigations:/app/investigations" \
>    --add-host=host.docker.internal:host-gateway \
>    -p 8501:8501 \
>    apurvsg/robin:latest
> ```
> Investigations are saved to the `investigations/` folder in your working directory and can be loaded from the **Past Investigations** panel in the sidebar.

- Open your browser and navigate to `http://localhost:8501`

### Using Python (Development Version)

- With `Python 3.10+` and Tor installed, run the following:

```bash
pip install -r requirements.txt
streamlit run ui.py
```

- Open your browser and navigate to `http://localhost:8501`

---

## Troubleshooting

Empty model dropdown, Ollama not showing up, Tor `resolve failed` errors, 401s,
or "no results found"? See **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** before
opening an issue.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request if you have major feature updates.

- Fork the repository
- Create your feature branch (git checkout -b feature/amazing-feature)
- Commit your changes (git commit -m 'Add some amazing feature')
- Push to the branch (git push origin feature/amazing-feature)
- Open a Pull Request

Pull requests run automated checks before they can be merged: every module is
compiled and imported, `pyflakes` must be clean, the bundled model seed is
validated, and the search parser and no-API-key paths are smoke-tested. Run them
locally first with `python -m compileall -q . && python -m pyflakes *.py`.

Open an Issue for any of these situations:
- If you spot a bug or bad code
- If you have a feature request idea
- If you have questions or doubts about usage
- If you have minor code changes

---

## Acknowledgements

- Idea inspiration from [Thomas Roccia](https://x.com/fr0gger_) and his demo of [Perplexity of the Dark Web](https://x.com/fr0gger_/status/1908051083068645558).
- Tools inspiration from my [OSINT Tools for the Dark Web](https://github.com/apurvsinghgautam/dark-web-osint-tools) repository.
- LLM Prompt inspiration from [OSINT-Assistant](https://github.com/AXRoux/OSINT-Assistant) repository.
- Logo Design by my friend [Tanishq Rupaal](https://github.com/Tanq16/)





