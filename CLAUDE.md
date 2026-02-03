# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Robin is an autonomous AI agent for conducting dark web OSINT (Open Source Intelligence) investigations. Built with the Claude Agent SDK, it uses a coordinator-subagent architecture to search, scrape, and analyze dark web content through Tor.

## Common Commands

### Docker Compose (Recommended)

```bash
# Setup authentication
./robin.sh setup-auth

# Start all services
./robin.sh up

# Build and start
./robin.sh build

# View logs
./robin.sh logs

# Check status
./robin.sh status

# Stop services
./robin.sh down
```

Services: PostgreSQL (5432), Tor (9050), FastAPI (8000), Next.js (3000)

Open `http://localhost:3000`

### Local Development (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r backend/requirements.txt
cd frontend && npm install

# Run backend API (FastAPI)
cd backend && uvicorn app.main:app --reload

# Run frontend (Next.js) - in separate terminal
cd frontend && npm run dev

# Type check frontend
cd frontend && npm run type-check

# Lint frontend
cd frontend && npm run lint
```

Requires Tor and PostgreSQL running locally.

### CLI Mode

```bash
# Run a single investigation
python main.py cli -q "ransomware payments 2024"

# Interactive mode with follow-ups
python main.py cli -q "threat actor APT28" --interactive

# Custom output file
python main.py cli -q "credential dumps" -o report.md
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=agent --cov-report=html

# Run specific test file
pytest tests/test_tools.py -v
```

## Architecture

### Coordinator-Subagent Pattern

The main agent (`RobinAgent` in `agent/client.py`) orchestrates investigations using four custom MCP tools:

1. **darkweb_search** - Searches 17 .onion search engines concurrently via Tor
2. **darkweb_scrape** - Extracts content from .onion URLs
3. **save_report** - Exports findings to markdown
4. **delegate_analysis** - Invokes specialized sub-agents

### Sub-Agents (`agent/subagents.py`)

Sub-agents are single-turn, tool-less Claude instances specialized for analysis:

- **ThreatActorProfiler** - Profiles APT groups, threat actors, TTPs
- **IOCExtractor** - Extracts IPs, domains, hashes, emails, crypto addresses
- **MalwareAnalyst** - Analyzes malware families, capabilities, mitigations
- **MarketplaceInvestigator** - Investigates dark web markets, vendors, pricing

Sub-agents are invoked via `run_subagents_parallel()` and receive content + context.

### Tool Registration

Tools are defined using the `@tool` decorator from `claude_code_sdk` and registered via `create_sdk_mcp_server()` in `agent/client.py`. The MCP server exposes tools with the `mcp__robin__` prefix.

### Core Modules

- `core/search.py` - Concurrent searches across 17 dark web search engines using ThreadPoolExecutor
- `core/scrape.py` - Tor-based content extraction with retry logic and session management

### Web Interface (`frontend/` + `backend/`)

Next.js frontend with FastAPI backend providing:
- SSE streaming for real-time agent responses
- PostgreSQL persistence for investigation history
- Graph visualization for threat intelligence relationships
- Report builder with export options

## Configuration

Environment variables (or `.env` file):

**Authentication (choose one):**
- `ANTHROPIC_API_KEY` - API key from console.anthropic.com
- `CLAUDE_CODE_OAUTH_TOKEN` - OAuth token from `claude setup-token` (for Max subscribers)

**Other settings:**
- `TOR_SOCKS_PROXY` - Tor proxy (default: `socks5h://127.0.0.1:9050`)
- `ROBIN_MODEL` - Claude model (default: `claude-sonnet-4-5-20250514`)
- `MAX_AGENT_TURNS` - Max reasoning turns (default: 20)
- `MAX_SEARCH_WORKERS` - Concurrent search threads (default: 5)
- `MAX_SCRAPE_WORKERS` - Concurrent scrape threads (default: 5)

## Key Patterns

- Tools return `{"content": [{"type": "text", "text": "..."}]}` format for MCP compatibility
- Sub-agents use `max_turns=1` and `allowed_tools=[]` since they are analysis-only
- Session continuity is maintained via `session_id` in `ClaudeCodeOptions.resume`
- Scraped content is truncated to 2000 chars per page to manage context
