# Robin MCP Server

MCP (Model Context Protocol) server for Robin dark web search engine.

## Features

- **search_darkweb**: Search across 16 dark web search engines
- **refine_query**: AI-powered query optimization for dark web searches

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

1. Ensure Tor is running on `127.0.0.1:9050`
2. Configure `.env` with your LLM API keys (see main README)

## Usage with Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "robin": {
      "command": "python",
      "args": ["/Users/bluedog/develop/anwang/robin/mcp_server.py"]
    }
  }
}
```

## Usage with Kiro CLI

Add to `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "robin": {
      "command": "python",
      "args": ["/Users/bluedog/develop/anwang/robin/mcp_server.py"],
      "disabled": false
    }
  }
}
```

## Tools

### search_darkweb

Search dark web content across multiple onion search engines.

**Parameters:**
- `query` (required): Search query string
- `max_workers` (optional): Parallel workers, default 5

**Returns:** JSON array of results with `title` and `link` fields

### refine_query

Optimize search query using AI for better dark web search results.

**Parameters:**
- `query` (required): Original search query

**Returns:** Refined query (max 5 words)

## Example

```python
# Via MCP client
await client.call_tool("refine_query", {"query": "stolen credit cards"})
# Returns: "credit card dumps"

await client.call_tool("search_darkweb", {"query": "credit card dumps"})
# Returns: [{"title": "...", "link": "http://...onion/..."}, ...]
```

## Requirements

- Python 3.8+
- Tor proxy running
- LLM API key configured
