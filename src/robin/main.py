import click
import subprocess
import logging
from yaspin import yaspin
from datetime import datetime

# Handle both direct execution and module import scenarios
try:
    from .scrape import scrape_multiple
    from .search import get_search_results
    from .llm import get_llm, refine_query, filter_results, generate_summary
    from .config import logger, OUTPUTS_DIR
except ImportError:
    from scrape import scrape_multiple
    from search import get_search_results
    from llm import get_llm, refine_query, filter_results, generate_summary
    from .config import OUTPUTS_DIR
    # Initialize a logger if running directly
    import logging
    logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def robin():
    """Robin: AI-Powered Dark Web OSINT Tool."""
    pass


@robin.command()
@click.option(
    "--model",
    "-m",
    default="gpt4o",
    show_default=True,
    type=click.Choice(
        ["gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"]
    ),
    help="Select LLM model to use (e.g., gpt4o, claude sonnet 3.5, ollama models)",
)
@click.option("--query", "-q", required=True, type=str, help="Dark web search query")
@click.option(
    "--threads",
    "-t",
    default=5,
    show_default=True,
    type=int,
    help="Number of threads to use for scraping (Default: 5)",
)
@click.option(
    "--output",
    "-o",
    type=str,
    help="Filename to save the final intelligence summary. If not provided, a filename based on the current date and time is used.",
)
def cli(model, query, threads, output):
    """Run Robin in CLI mode.\n
    Example commands:\n
    - robin -m gpt4o -q "ransomware payments" -t 12\n
    - robin --model claude-3-5-sonnet-latest --query "sensitive credentials exposure" --threads 8 --output filename\n
    - robin -m llama3.1 -q "zero days"\n
    """
    # In CLI mode, set console logging to INFO level to show more details
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(logging.INFO)

    logger.info(f"Starting CLI mode with query: {query}")
    llm = get_llm(model)

    # Show spinner while processing the query
    with yaspin(text="Processing...", color="cyan") as sp:
        refined_query = refine_query(llm, query)
        logger.info(f"Refined query: {refined_query}")

        search_results = get_search_results(
            refined_query.replace(" ", "+"), max_workers=threads
        )
        logger.info(f"Found {len(search_results)} search results")

        search_filtered = filter_results(llm, refined_query, search_results)
        logger.info(f"Filtered to {len(search_filtered)} results")

        scraped_results = scrape_multiple(search_filtered, max_workers=threads)
        logger.info(f"Scraped {len(scraped_results)} results")
        sp.ok("✔")

    # Generate the intelligence summary.
    logger.info("Generating intelligence summary...")
    summary = generate_summary(llm, query, scraped_results)

    # Save or print the summary
    if not output:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = OUTPUTS_DIR / f"summary_{now}.md"
    else:
        filename = OUTPUTS_DIR / output + ".md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(summary)
        logger.info(f"Final intelligence summary saved to {filename}")
        click.echo(f"\n\n[OUTPUT] Final intelligence summary saved to {filename}")


@robin.command()
@click.option(
    "--ui-port",
    default=8501,
    show_default=True,
    type=int,
    help="Port for the Streamlit Web UI",
)
@click.option(
    "--ui-host",
    default="localhost",
    show_default=True,
    type=str,
    help="Host for the Streamlit Web UI",
)
def web(ui_port, ui_host):
    """Run Robin in Web UI mode."""
    # In Web UI mode, keep console logging at WARNING level to avoid cluttering the terminal
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(logging.WARNING)

    logger.info(f"Starting Web UI mode on {ui_host}:{ui_port}")
    import sys, os

    # Use streamlit's internet CLI entrypoint
    from streamlit.web import cli as stcli

    # When PyInstaller one-file, data files livei n _MEIPASS
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(__file__)

    ui_script = os.path.join(base, "ui.py")
    # Build sys.argv
    sys.argv = [
        "streamlit",
        "run",
        ui_script,
        f"--server.port={ui_port}",
        f"--server.address={ui_host}",
        "--global.developmentMode=false",
    ]
    # This will never return until streamlit exits
    sys.exit(stcli.main())


if __name__ == "__main__":
    robin()
