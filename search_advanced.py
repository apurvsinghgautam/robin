"""Advanced search features and utilities for onion search engines."""

import json
from datetime import datetime
from search import (
    get_search_results, 
    SEARCH_ENGINES, 
    get_active_engines,
    get_engine_by_name,
    list_all_engines
)


def search_by_specific_engines(query, engine_names, timeout=None, stats=False):
    """Search using only specific engines."""
    results = []
    stats_data = {
        "query": query,
        "requested_engines": engine_names,
        "found_engines": 0,
        "total_results": 0,
        "timestamp": datetime.now().isoformat(),
    }
    
    for name in engine_names:
        engine = get_engine_by_name(name)
        if engine:
            from search import fetch_search_results
            results.extend(fetch_search_results(engine["url"], query, timeout))
            stats_data["found_engines"] += 1
    
    stats_data["total_results"] = len(results)
    
    if stats:
        return results, stats_data
    return results


def sort_results(results, sort_by="relevance"):
    """Sort search results by various criteria."""
    if sort_by == "title_length":
        return sorted(results, key=lambda x: len(x.get("title", "")), reverse=True)
    elif sort_by == "link_length":
        return sorted(results, key=lambda x: len(x.get("link", "")))
    elif sort_by == "source":
        return sorted(results, key=lambda x: x.get("source", ""))
    elif sort_by == "relevance":  # Default: keep original order
        return results
    else:
        return results


def filter_results(results, keyword=None, exclude_keyword=None, domain_filter=None):
    """Advanced filtering of search results."""
    filtered = results
    
    if keyword:
        filtered = [r for r in filtered if keyword.lower() in r.get("title", "").lower()]
    
    if exclude_keyword:
        filtered = [r for r in filtered if exclude_keyword.lower() not in r.get("title", "").lower()]
    
    if domain_filter:
        filtered = [r for r in filtered if domain_filter in r.get("link", "")]
    
    return filtered


def export_results(results, format="json"):
    """Export results in various formats."""
    if format == "json":
        return json.dumps(results, indent=2)
    elif format == "csv":
        if not results:
            return "title,link,source\n"
        header = "title,link,source\n"
        rows = [f'"{r.get("title", "")}","{r.get("link", "")}","{r.get("source", "")}"\n' for r in results]
        return header + "".join(rows)
    elif format == "markdown":
        lines = ["# Search Results\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r.get('title', 'N/A')}**\n")
            lines.append(f"   - Link: {r.get('link', 'N/A')}\n")
            lines.append(f"   - Source: {r.get('source', 'N/A')}\n\n")
        return "".join(lines)
    elif format == "html":
        html = "<html><head><title>Search Results</title></head><body>\n<table border='1'>\n"
        html += "<tr><th>Title</th><th>Link</th><th>Source</th></tr>\n"
        for r in results:
            html += f"<tr><td>{r.get('title', '')}</td><td><a href='{r.get('link', '')}'>{r.get('link', '')}</a></td><td>{r.get('source', '')}</td></tr>\n"
        html += "</table>\n</body></html>"
        return html
    else:
        return str(results)


def advanced_search(query, engines=None, timeout=None, sort_by="relevance", 
                   keyword_filter=None, exclude_keyword=None, domain_filter=None, 
                   format="json", stats=False):
    """Perform an advanced search with multiple filters and options."""
    
    # Get results from specific engines or all active ones
    if engines:
        results, search_stats = search_by_specific_engines(query, engines, timeout, stats=True)
    else:
        results, search_stats = get_search_results(query, timeout=timeout, stats=True)
    
    # Apply filtering
    results = filter_results(results, keyword_filter, exclude_keyword, domain_filter)
    
    # Sort results
    results = sort_results(results, sort_by)
    
    # Prepare output
    output = {
        "query": query,
        "total_results": len(results),
        "stats": search_stats if stats else None,
        "results": results,
    }
    
    if format == "json":
        return json.dumps(output, indent=2)
    else:
        # For other formats, just export the results
        exported = export_results(results, format)
        return exported


def print_engines_list():
    """Print formatted list of all available search engines."""
    print("\n" + "="*60)
    print("AVAILABLE ONION SEARCH ENGINES (A-Z)")
    print("="*60)
    
    engines = list_all_engines()
    for i, engine in enumerate(engines, 1):
        status_symbol = "✓" if "Active" in engine["status"] else "✗"
        print(f"{i:2d}. [{status_symbol}] {engine['name']:20s} - {engine['status']}")
    
    print("="*60)
    print(f"Total: {len(engines)} engines | Active: {sum(1 for e in engines if 'Active' in e['status'])}")
    print("="*60 + "\n")


def search_stats_summary(results, search_stats):
    """Generate a summary of search statistics."""
    summary = f"""
╔════════════════════════════════════════╗
║      SEARCH STATISTICS SUMMARY         ║
╠════════════════════════════════════════╣
║ Total Engines:        {search_stats.get('total_engines', 0):>20} ║
║ Successful:           {search_stats.get('successful_engines', 0):>20} ║
║ Failed:               {search_stats.get('failed_engines', 0):>20} ║
║ Total Results Found:  {search_stats.get('total_results', 0):>20} ║
║ Duplicates Removed:   {search_stats.get('duplicate_count', 0):>20} ║
║ Final Results:        {search_stats.get('final_results', 0):>20} ║
╚════════════════════════════════════════╝
"""
    return summary


if __name__ == "__main__":
    # Example usage
    print_engines_list()
    
    # Example: Search and get statistics
    query = "privacy tools"
    results, stats = advanced_search(query, sort_by="title_length", stats=True)
    
    output = json.loads(results)
    print(search_stats_summary(output["results"], output["stats"]))
