<div align="center">
   <img src=".github/assets/logo.png" alt="Logo" width="300">
   <br><a href="https://github.com/apurvsinghgautam/robin/actions/workflows/binary.yml"><img alt="Build" src="https://github.com/apurvsinghgautam/robin/actions/workflows/binary.yml/badge.svg"></a> <a href="https://github.com/apurvsinghgautam/robin/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/apurvsinghgautam/robin"></a> <a href="https://hub.docker.com/r/apurvsg/robin"><img alt="Docker Pulls" src="https://img.shields.io/docker/pulls/apurvsg/robin"></a>
   <h1>Robin: AI-Powered Dark Web OSINT Tool</h1>

   <p>Robin is an AI-powered tool for conducting dark web OSINT investigations. It leverages LLMs to refine queries, filter search results from dark web search engines, and provide an investigation summary.</p>
   <a href="#installation">Installation</a> &bull; <a href="#usage">Usage</a> &bull; <a href="#contributing">Contributing</a> &bull; <a href="#acknowledgements">Acknowledgements</a><br><br>
</div>

![Demo](.github/assets/screen.png)
![Demo](.github/assets/screen-ui.png)


---

## Features

- ⚙️ **Modular Architecture** – Clean separation between search, scrape, and LLM workflows.
- 🤖 **Multi-Model Support** – Easily switch between OpenAI, Claude, Gemini or local models like Ollama.
- 💻 **CLI-First Design** – Built for terminal warriors and automation ninjas.
- 🐳 **Docker-Ready** – Optional Docker deployment for clean, isolated usage.
- 📝 **Custom Reporting** – Save investigation output to file for reporting or further analysis.
- 🧩 **Extensible** – Easy to plug in new search engines, models, or output formats.
- 🔄 **Modern Python Packaging** – Uses src layout and pyproject.toml for better maintainability
- ⚡ **uv Support** – Fast Python package management and execution support

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
> You can provide OpenAI or Anthropic or Google API key by either creating .env file (refer to sample env file in the repo) or by setting env variables in PATH.
>
> For Ollama, provide `http://host.docker.internal:11434` as Ollama URL if running using docker image method or `http://127.0.0.1:11434` for other methods.

### Docker (Web UI Mode) [Recommended]

```bash
docker run --rm \
   -v "$(pwd)/.env:/app/.env" \
   --add-host=host.docker.internal:host-gateway \
   -p 8501:8501 \
   apurvsg/robin:latest web --ui-port 8501 --ui-host 0.0.0.0
```

### Using uv (Modern Python Package Manager) [Recommended for Development]

```bash
# Install uv if not already installed
pip install uv

# Install and run the project
uv sync
uv run robin --help
```

### Release Binary (CLI Mode)

- Download the appropriate binary for your system from the [latest release](https://github.com/apurvsinghgautam/robin/releases/latest)
- Unzip the file, make it executable 
```bash
chmod +x robin
```

- Run the binary as:
```bash
robin cli --model gpt-4.1 --query "ransomware payments"
```
---

## Usage

```bash
Robin: AI-Powered Dark Web OSINT Tool

options:
  -h, --help            show this help message and exit
  --version             show the version and exit
  --model {gpt4o,gpt-4.1,claude-3-5-sonnet-latest,llama3.1,gemini-2.5-flash}, -m {gpt4o,gpt-4.1,claude-3-5-sonnet-latest,llama3.1,gemini-2.5-flash}
                        Select LLM model (e.g., gpt4o, claude sonnet 3.5, ollama models, gemini 2.5 flash)
  --query QUERY, -q QUERY
                        Dark web search query
  --threads THREADS, -t THREADS
                        Number of threads to use for scraping (Default: 5)
  --output OUTPUT, -o OUTPUT
                        Filename to save the final intelligence summary. If not provided, a filename based on the
                        current date and time is used.

Commands:
  cli  Run Robin in CLI mode.
  web  Run Robin in Web UI mode.

Example commands (using uv):
 - uv run robin cli -m gpt4o -q "ransomware payments" -t 12
 - uv run robin cli --model claude-3-5-sonnet-latest --query "sensitive credentials exposure" --threads 8 --output filename
 - uv run robin cli -m llama3.1 -q "zero days"
 - uv run robin cli -m gemini-2.5-flash -q "zero days"
 - uv run robin web --ui-port 8501 --ui-host localhost
```

## Project Structure Changes

This fork introduces modern Python packaging practices while preserving all original functionality:

- **src layout**: All Python code is now in `src/robin/` directory for better project organization
- **pyproject.toml**: Uses hatchling build backend with comprehensive dependency management
- **uv support**: Optimized for fast package management and execution using uv
- **Docker improvements**: Updated to work with new project structure and use uv for dependency installation
- **Import compatibility**: Updated import statements to work in both module and direct script contexts

### Using uv for Fast Development

The project now fully supports `uv` for fast dependency management and execution:
```bash
# Install dependencies quickly
uv sync

# Run to get help
uv run robin --help
# Run CLI ui directly with uv
uv run robin cli [options]

# Run the Web UI directly with uv
uv run robin web
```

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

- Fork the repository
- Create your feature branch (git checkout -b feature/amazing-feature)
- Commit your changes (git commit -m 'Add some amazing feature')
- Push to the branch (git push origin feature/amazing-feature)
- Open a Pull Request

Open an Issue for any of these situations:
- If you spot a bug or bad code
- If you have a feature request idea
- If you have questions or doubts about usage

---

## Acknowledgements

**Original Author**: [Apurv Singh Gautam](https://github.com/apurvsinghgautam/) - Original creator and maintainer of Robin

- Idea inspiration from [Thomas Roccia](https://x.com/fr0gger_) and his demo of [Perplexity of the Dark Web](https://x.com/fr0gger_/status/1908051083068645558).
- Tools inspiration from the original [OSINT Tools for the Dark Web](https://github.com/apurvsinghgautam/dark-web-osint-tools) repository.
- LLM Prompt inspiration from [OSINT-Assistant](https://github.com/AXRoux/OSINT-Assistant) repository.
- Logo Design by [Tanishq Rupaal](https://github.com/Tanq16/)

**Fork Changes**: This fork introduces modern Python packaging (src layout, pyproject.toml), uv support, and improved Docker configuration while maintaining all original functionality and credits to the original author.
