<div align="center">
  <img src="logo.png" alt="Logo" width="300">
  <h1>Robin: AI-Powered Dark Web OSINT Tool</h1>

   <p>**Robin** is an AI-powered CLI-based tool for conducting dark web OSINT investigations. It leverages LLMs to refine queries and filter search results from dark web search engines and provide investigation summary.</p><br>

   <a href="#installation">Installation</a> &bull; <a href="#usage">Usage</a> &bull; <a href="#contributing">Contributing</a> &bull; <a href="#acknowledgements">Acknowledgements</a><br>
</div>

---

## Features

- Modular architecture with clearly separated components for search, scrape, and LLM processing.
- Supports multiple LLM providers (OpenAI, Claude, Ollama) via pluggable model interface.
- CLI-first experience for automation and power users.
- Optional Docker deployment for clean, isolated usage.
- Save output summaries to file or use in pipeline workflows.
- Designed for extensibility and integration with other OSINT tools.

---

## Installation

### From Source

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/apurvsinghgautam/robin.git
   cd robin
   ```

2. **Set Up a Virtual Environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```

3. **Install Dependencies:**

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Environment Variables:**

   ```dotenv
   OPENAI_API_KEY=your_secret_openai_key
   ```

5. **Run the tool:**
   
   ```bash
   python main.py -m gpt4o -q "ransomware payments" -t 12
   ```

### Building a Binary with PyInstaller

1. **Install PyInstaller:**

   ```bash
   pip install pyinstaller
   ```

2. **Build the Binary:**

   ```bash
   pyinstaller --onefile --strip --noupx --name robin main.py
   ```

3. **Run the tool:**

   ```bash
   robin -m gpt4o -q "ransomware payments"
   ```

### Docker Image

1. **Build the Docker Image:**

   ```bash
   docker build -t robin .
   ```

2. **Run the Container:**

   ```bash
   mkdir -p output
   docker run --rm \
     -v "$(pwd)/.env:/app/.env" \
     -v "$(pwd)/output:/app/output" \
     -e OPENAI_API_KEY="your_secret_key" \
     robin --model gpt4o --query "dark web financial fraud" --output results
   ```

---

## Usage

```bash
usage: robin [-h] [--model {gpt4o,claude-3-5-sonnet-latest,llama3.1}] --query QUERY [--threads THREADS]
               [--output OUTPUT]

Robin: AI-Powered Dark Web OSINT Tool

options:
  -h, --help            show this help message and exit
  --model {gpt4o,claude-3-5-sonnet-latest,llama3.1}, -m {gpt4o,claude-3-5-sonnet-latest,llama3.1}
                        Select LLM model (e.g., gpt4o, claude sonnet 3.5, ollama models)
  --query QUERY, -q QUERY
                        Dark web search query
  --threads THREADS, -t THREADS
                        Number of threads to use for scraping (Default: 5)
  --output OUTPUT, -o OUTPUT
                        Filename to save the final intelligence summary. If not provided, a filename based on the
                        current date and time is used.

Example commands:
 - robin -m gpt4o -q "ransomware payments" -t 12
 - robin --model claude-3-5-sonnet-latest --query "sensitive credentials exposure" --threads 8 --output filename
 - robin -m llama3.1 -q "zero days"
```

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

* Fork the repository
* Create your feature branch (git checkout -b feature/amazing-feature)
* Commit your changes (git commit -m 'Add some amazing feature')
* Push to the branch (git push origin feature/amazing-feature)
* Open a Pull Request

Open an Issue for any of these situations:
* If you spot a bug or bad code
* If you have questions or about doubts about usage

---

## Acknowledgements

- Idea inspiration from [Thomas Roccia](https://x.com/fr0gger_) and his demo of [Perplexity of the Dark Web](https://x.com/fr0gger_/status/1908051083068645558).
- Tools inspiration from my [OSINT Tools for the Dark Web](https://github.com/apurvsinghgautam/dark-web-osint-tools) repository.
- LLM Prompt inspiration from [OSINT-Assistant](https://github.com/AXRoux/OSINT-Assistant) repository.
