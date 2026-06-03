

def search_by_engine(query, engine_name, timeout=None):
    """Search using a single specific engine."""
    engine = get_engine_by_name(engine_name)
    if not engine:
        return []
    return fetch_search_results(engine["url"], query, timeout)


def sort_results(results, sort_by="relevance"):
    """Sort search results by various criteria."""
    if sort_by == "title_length":
        return sorted(results, key=lambda x: len(x.get("title", "")), reverse=True)
    elif sort_by == "link_length":
        return sorted(results, key=lambda x: len(x.get("link", "")))
    elif sort_by == "source":
        return sorted(results, key=lambda x: x.get("source", ""))
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


def export_results_json(results):
    """Export results as JSON."""
    return json.dumps(results, indent=2)


def export_results_csv(results):
    """Export results as CSV."""
    if not results:
        return "title,link,source\n"
    header = "title,link,source\n"
    rows = []
    for r in results:
        title = r.get("title", "").replace('"', '""')
        link = r.get("link", "").replace('"', '""')
        source = r.get("source", "").replace('"', '""')
        rows.append(f'"{title}","{link}","{source}"\n')
    return header + "".join(rows)


def print_engines_list():
    """Print formatted list of all available search engines."""
    print("\n" + "="*70)
    print("AVAILABLE ONION SEARCH ENGINES (A-Z) - ACTIVE & VERIFIED")
    print("="*70)
    
    for i, engine in enumerate(sorted(SEARCH_ENGINES, key=lambda x: x["name"]), 1):
        status = "✓ ACTIVE" if engine.get("active", True) else "✗ INACTIVE"
        name = engine["name"]
        print(f"{i:2d}. [{status}] {name}")
    
    print("="*70)
    active_count = sum(1 for e in SEARCH_ENGINES if e.get("active", True))
    print(f"Total Engines: {len(SEARCH_ENGINES)} | Active: {active_count} | Inactive: {len(SEARCH_ENGINES) - active_count}")
    print("="*70 + "\n")
