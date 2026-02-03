"""Core functionality for dark web operations."""
from .search import get_search_results, fetch_search_results
from .scrape import scrape_multiple, scrape_single

__all__ = [
    "get_search_results",
    "fetch_search_results",
    "scrape_multiple",
    "scrape_single",
]
