#!/usr/bin/env python3
import asyncio
from mcp.server import Server
from mcp.types import Tool, TextContent
from search import get_search_results
from llm import refine_query, get_llm
import json

app = Server("robin-darkweb-search")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_darkweb",
            description="Search dark web using multiple onion search engines. Returns links and titles from dark web sites.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find dark web content"
                    },
                    "max_workers": {
                        "type": "integer",
                        "description": "Number of parallel workers (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="refine_query",
            description="Refine a search query using AI to optimize it for dark web search engines. Returns improved query limited to 5 words.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Original search query to refine"
                    }
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "search_darkweb":
        query = arguments["query"]
        max_workers = arguments.get("max_workers", 5)

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, get_search_results, query, max_workers)

        return [TextContent(
            type="text",
            text=json.dumps(results, indent=2, ensure_ascii=False)
        )]

    elif name == "refine_query":
        query = arguments["query"]

        loop = asyncio.get_event_loop()
        llm = await loop.run_in_executor(None, get_llm, "gpt-4o-mini")
        refined = await loop.run_in_executor(None, refine_query, llm, query)

        return [TextContent(
            type="text",
            text=refined
        )]

    raise ValueError(f"Unknown tool: {name}")

async def main():
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
