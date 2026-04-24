import click
import logging
import requests
from llm import get_llm, refine_query, filter_results, generate_summary
from search import get_search_results
from scrape import scrape_multiple
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def check_tor():
    """Phase 6: Tor Health Check"""
    try:
        r = requests.get("https://check.torproject.org/api/ip",
                         proxies={"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"},
                         timeout=10)
        if not r.json().get("IsTor"):
            raise RuntimeError("Tor not active")
    except Exception as e:
        click.echo(f"[ERROR] Tor check failed: {e}")
        raise SystemExit(1)

@click.group()
def main():
    pass

@main.command(name='cli')
@click.option('--model', '-m', default='gpt4o', help='LLM model to use')
@click.option('--query', '-q', required=True, help='Search query')
@click.option('--log-level', default='INFO', help='Logging level')
def cli_cmd(model, query, log_level):
    logging.getLogger().setLevel(log_level.upper())
    
    # Phase 6: Tor check before any search
    check_tor()
    
    click.echo(f"[*] Starting Robin CLI for query: {query}")
    
    try:
        llm = get_llm(model)
    except Exception as e:
        click.echo(f"[ERROR] Failed to load LLM: {e}")
        return

    # Refine query
    click.echo("[*] Refining query...")
    refined_query = refine_query(llm, query)
    click.echo(f"[*] Refined query: {refined_query}")

    # Search
    click.echo("[*] Searching dark web...")
    results = get_search_results(refined_query)
    click.echo(f"[*] Found {len(results)} raw results.")

    # Filter
    click.echo("[*] Filtering results...")
    filtered = filter_results(llm, refined_query, results)
    
    # Phase 5: Relevance Gate
    MIN_RESULTS = 3 # abort if signal too weak
    if len(filtered) < MIN_RESULTS:
        click.echo(f"[WARN] Only {len(filtered)} relevant results. "
                   "Query may be too broad or Tor returned noise. Exiting.")
        return

    click.echo(f"[*] Proceeding with {len(filtered)} relevant results.")

    # Scrape
    click.echo("[*] Scraping content...")
    scraped_content = scrape_multiple(filtered)

    # Summarize
    click.echo("[*] Generating summary...")
    summary = generate_summary(llm, query, scraped_content)
    
    click.echo("\n" + "="*50)
    click.echo("INVESTIGATION SUMMARY")
    click.echo("="*50)
    click.echo(summary)

if __name__ == '__main__':
    main()
