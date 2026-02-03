"""Custom tools for the Robin OSINT agent."""
import asyncio
from datetime import datetime
from typing import Any, Callable, Optional
from contextvars import ContextVar

# Import core functionality
from core.search import get_search_results, SearchProgress
from core.scrape import scrape_multiple

# Import sub-agent orchestration
from .subagents import run_subagents_parallel, get_available_subagents

# Context variable for progress callback (set by AgentService)
_progress_callback: ContextVar[Optional[Callable[[SearchProgress], None]]] = ContextVar(
    '_progress_callback', default=None
)


def set_search_progress_callback(callback: Optional[Callable[[SearchProgress], None]]) -> None:
    """Set the callback for search progress updates."""
    _progress_callback.set(callback)


def get_search_progress_callback() -> Optional[Callable[[SearchProgress], None]]:
    """Get the current search progress callback."""
    return _progress_callback.get()


# Tool definitions for Anthropic API
TOOL_DEFINITIONS = [
    {
        "name": "darkweb_search",
        "description": "Search multiple dark web search engines simultaneously via Tor. Returns deduplicated results with titles and .onion links. Use this to gather initial intelligence on a topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to run across dark web search engines"
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Number of concurrent search workers (default 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "darkweb_scrape",
        "description": "Scrape and extract text content from .onion URLs via Tor. Pass a list of target objects, each with 'title' and 'link' keys. Returns cleaned text content from each page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "targets": {
                    "type": "array",
                    "description": "List of targets to scrape, each with 'title' and 'link' keys",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "link": {"type": "string"}
                        },
                        "required": ["link"]
                    }
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Number of concurrent scraping workers (default 5)",
                    "default": 5
                }
            },
            "required": ["targets"]
        }
    },
    {
        "name": "save_report",
        "description": "Save the investigation report to a markdown file. Use this when the user asks to save or export the findings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The report content to save"
                },
                "filename": {
                    "type": "string",
                    "description": "Optional filename (defaults to robin_report_<timestamp>.md)"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "delegate_analysis",
        "description": """Delegate specialized analysis to expert sub-agents. Available agents:
- ThreatActorProfiler: Profiles threat actors, APT groups, cybercriminals
- IOCExtractor: Extracts IPs, domains, hashes, emails, crypto addresses
- MalwareAnalyst: Analyzes malware, ransomware, exploits
- MarketplaceInvestigator: Investigates dark web markets and vendors

You can delegate to multiple agents simultaneously for comprehensive analysis.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_types": {
                    "type": "array",
                    "description": "List of agent types to run",
                    "items": {"type": "string"}
                },
                "content": {
                    "type": "string",
                    "description": "The scraped content to analyze"
                },
                "context": {
                    "type": "string",
                    "description": "Additional context (original query, investigation goals)"
                }
            },
            "required": ["agent_types", "content"]
        }
    }
]


async def execute_tool(tool_name: str, args: dict[str, Any]) -> str:
    """Execute a tool by name and return the result as a string."""
    if tool_name == "darkweb_search":
        result = await darkweb_search(args)
    elif tool_name == "darkweb_scrape":
        result = await darkweb_scrape(args)
    elif tool_name == "save_report":
        result = await save_report(args)
    elif tool_name == "delegate_analysis":
        result = await delegate_analysis(args)
    else:
        return f"Unknown tool: {tool_name}"

    # Extract text from result
    if isinstance(result, dict) and "content" in result:
        content = result["content"]
        if isinstance(content, list) and len(content) > 0:
            return content[0].get("text", str(content))
    return str(result)


async def darkweb_search(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search 17 dark web search engines concurrently via Tor.
    Returns unique results with title and link.
    """
    query = args["query"]
    max_workers = args.get("max_workers", 5)

    # Get progress callback if available
    progress_callback = get_search_progress_callback()
    print(f"[DEBUG] darkweb_search: progress_callback is {'SET' if progress_callback else 'NONE'}")

    # Run synchronous search in executor
    loop = asyncio.get_running_loop()
    try:
        results = await loop.run_in_executor(
            None,
            lambda: get_search_results(
                query,
                max_workers=max_workers,
                on_progress=progress_callback
            )
        )
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Search failed: {str(e)}. Make sure Tor is running on port 9050."
            }]
        }

    if not results:
        return {
            "content": [{
                "type": "text",
                "text": "No results found. Try refining your search query or check Tor connectivity."
            }]
        }

    # Format results for agent consumption - include full URLs so agent can pass to scrape
    formatted = []
    for i, res in enumerate(results, 1):
        title = res["title"][:80] + "..." if len(res["title"]) > 80 else res["title"]
        link = res["link"]
        formatted.append(f"{i}. **{title}**\n   URL: {link}")

    # Limit display to first 50 results to avoid context overflow
    display_results = formatted[:50]
    total_count = len(results)

    result_text = f"Found **{total_count}** unique results from dark web search engines.\n\n"
    result_text += "\n\n".join(display_results)

    if total_count > 50:
        result_text += f"\n\n... and {total_count - 50} more results."

    result_text += "\n\n**Next step**: Select the most relevant results and use `darkweb_scrape` with a list of targets containing title and link for each."

    return {
        "content": [{
            "type": "text",
            "text": result_text
        }]
    }


async def darkweb_scrape(args: dict[str, Any]) -> dict[str, Any]:
    """
    Scrape multiple .onion URLs concurrently via Tor.
    Returns cleaned text content for each URL.
    """
    targets = args["targets"]
    max_workers = args.get("max_workers", 5)

    if not targets:
        return {
            "content": [{
                "type": "text",
                "text": "No targets provided. Please specify URLs to scrape as a list of objects with 'title' and 'link' keys."
            }]
        }

    # Validate target format
    urls_data = []
    for target in targets:
        if isinstance(target, dict) and "link" in target:
            urls_data.append({
                "title": target.get("title", "Unknown"),
                "link": target["link"]
            })
        elif isinstance(target, str):
            # If just a URL string was passed
            urls_data.append({
                "title": "Unknown",
                "link": target
            })

    if not urls_data:
        return {
            "content": [{
                "type": "text",
                "text": "Invalid target format. Provide a list of objects with 'title' and 'link' keys, or a list of URL strings."
            }]
        }

    # Run synchronous scraping in executor
    loop = asyncio.get_running_loop()
    try:
        results = await loop.run_in_executor(
            None,
            lambda: scrape_multiple(urls_data, max_workers=max_workers)
        )
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Scraping failed: {str(e)}. Some .onion sites may be offline."
            }]
        }

    if not results:
        return {
            "content": [{
                "type": "text",
                "text": "Failed to scrape any content. The .onion sites may be offline or blocking requests."
            }]
        }

    # Format scraped content
    content_parts = []
    success_count = 0
    for url, content in results.items():
        if content and len(content) > 50:  # Meaningful content
            success_count += 1
            # Truncate very long content
            display_content = content[:2000] + "..." if len(content) > 2000 else content
            content_parts.append(f"## Source: {url}\n\n{display_content}\n\n---")
        else:
            content_parts.append(f"## Source: {url}\n\n*[Minimal or no content extracted]*\n\n---")

    result_text = f"Successfully scraped **{success_count}/{len(urls_data)}** pages.\n\n"
    result_text += "\n".join(content_parts)
    result_text += "\n\n**Next step**: Analyze this content for intelligence artifacts and generate your findings report."

    return {
        "content": [{
            "type": "text",
            "text": result_text
        }]
    }


async def save_report(args: dict[str, Any]) -> dict[str, Any]:
    """
    Save the final report to a markdown file.
    """
    content = args["content"]
    filename = args.get("filename", "")

    if not filename:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"robin_report_{now}.md"

    if not filename.endswith(".md"):
        filename += ".md"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "content": [{
                "type": "text",
                "text": f"Report saved successfully to **{filename}**"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Failed to save report: {str(e)}"
            }]
        }


async def delegate_analysis(args: dict[str, Any]) -> dict[str, Any]:
    """
    Delegate analysis to specialized sub-agents.
    """
    agent_types = args["agent_types"]
    content = args["content"]
    context = args.get("context", "")

    if not agent_types:
        available = get_available_subagents()
        agent_list = "\n".join([f"- **{k}**: {v}" for k, v in available.items()])
        return {
            "content": [{
                "type": "text",
                "text": f"No agents specified. Available sub-agents:\n\n{agent_list}"
            }]
        }

    # Validate agent types
    available = get_available_subagents()
    invalid = [a for a in agent_types if a not in available]
    if invalid:
        return {
            "content": [{
                "type": "text",
                "text": f"Invalid agent types: {invalid}. Valid types: {list(available.keys())}"
            }]
        }

    if not content:
        return {
            "content": [{
                "type": "text",
                "text": "No content provided for analysis. Please include the scraped content to analyze."
            }]
        }

    # Run sub-agents in parallel
    try:
        results = await run_subagents_parallel(agent_types, content, context)
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Sub-agent execution failed: {str(e)}"
            }]
        }

    # Format results
    output_parts = [f"## Sub-Agent Analysis Results\n\nDelegated to: {', '.join(agent_types)}\n"]

    for result in results:
        if result.success:
            output_parts.append(f"### {result.agent_type}\n\n{result.analysis}\n")
        else:
            output_parts.append(f"### {result.agent_type}\n\n*Analysis failed: {result.error}*\n")

    output_parts.append("---\n\n**Next step**: Synthesize these findings into your final report.")

    return {
        "content": [{
            "type": "text",
            "text": "\n".join(output_parts)
        }]
    }
