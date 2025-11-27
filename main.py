"""
Robin: AI-Powered Dark Web OSINT Tool - Main Entry Point
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import click
from yaspin import yaspin

from constants import MAX_QUERY_LENGTH, MIN_QUERY_LENGTH, DEFAULT_MAX_WORKERS
from scrape import scrape_multiple
from search import get_search_results
from llm import get_llm, refine_query, filter_results, generate_summary
from llm_utils import get_model_choices

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MODEL_CHOICES = get_model_choices()


def validate_query(ctx, param, value: str) -> str:
    """Validate the search query parameter."""
    if not value or not value.strip():
        raise click.BadParameter("Query cannot be empty")

    value = value.strip()

    if len(value) < MIN_QUERY_LENGTH:
        raise click.BadParameter(f"Query must be at least {MIN_QUERY_LENGTH} character(s)")

    if len(value) > MAX_QUERY_LENGTH:
        raise click.BadParameter(f"Query must be at most {MAX_QUERY_LENGTH} characters")

    return value


def validate_output_path(ctx, param, value: str) -> str:
    """Validate the output file path to prevent path traversal."""
    if value is None:
        return value

    value = value.strip()

    # Check for path traversal attempts
    if '..' in value or value.startswith('/') or value.startswith('\\'):
        raise click.BadParameter("Invalid output path: path traversal not allowed")

    # Check for absolute paths on Windows
    if len(value) >= 2 and value[1] == ':':
        raise click.BadParameter("Invalid output path: absolute paths not allowed")

    return value


def validate_threads(ctx, param, value: int) -> int:
    """Validate the thread count parameter."""
    if value < 1:
        raise click.BadParameter("Thread count must be at least 1")
    if value > 50:
        raise click.BadParameter("Thread count must be at most 50")
    return value


@click.group()
@click.version_option()
def robin():
    """Robin: AI-Powered Dark Web OSINT Tool."""
    pass


@robin.command()
@click.option(
    "--model",
    "-m",
    default="gpt-5-mini",
    show_default=True,
    type=click.Choice(MODEL_CHOICES),
    help="Select LLM model to use (e.g., gpt4o, claude sonnet 3.5, ollama models)",
)
@click.option(
    "--query",
    "-q",
    required=True,
    type=str,
    callback=validate_query,
    help="Dark web search query"
)
@click.option(
    "--threads",
    "-t",
    default=DEFAULT_MAX_WORKERS,
    show_default=True,
    type=int,
    callback=validate_threads,
    help="Number of threads to use for scraping",
)
@click.option(
    "--output",
    "-o",
    type=str,
    callback=validate_output_path,
    help="Filename to save the final intelligence summary. If not provided, a filename based on the current date and time is used.",
)
def cli(model: str, query: str, threads: int, output: str):
    """Run Robin in CLI mode.

    Example commands:

    - robin cli -m gpt-5-mini -q "ransomware payments" -t 12

    - robin cli --model claude-sonnet-4-0 --query "sensitive credentials exposure" --threads 8 --output filename

    - robin cli -m llama3.1 -q "zero days"
    """
    logger.info(f"Starting Robin with model={model}, threads={threads}")

    try:
        llm = get_llm(model)
    except ValueError as e:
        click.echo(f"[ERROR] {e}", err=True)
        sys.exit(1)

    # Show spinner while processing the query
    with yaspin(text="Processing...", color="cyan") as sp:
        refined_query = refine_query(llm, query)
        logger.info(f"Refined query: {refined_query}")

        search_results = get_search_results(
            refined_query.replace(" ", "+"), max_workers=threads
        )

        if not search_results:
            sp.fail("No results found")
            click.echo("[INFO] No search results found for the query.", err=True)
            return

        search_filtered = filter_results(llm, refined_query, search_results)

        if not search_filtered:
            sp.fail("No relevant results")
            click.echo("[INFO] No relevant results found after filtering.", err=True)
            return

        scraped_results = scrape_multiple(search_filtered, max_workers=threads)
        sp.ok("Done")

    # Generate the intelligence summary
    summary = generate_summary(llm, query, scraped_results)

    # Determine output filename
    if not output:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"summary_{now}.md"
    else:
        filename = f"{output}.md"

    # Write the summary to file
    try:
        output_path = Path(filename)
        output_path.write_text(summary, encoding="utf-8")
        click.echo(f"\n\n[OUTPUT] Final intelligence summary saved to {filename}")
        logger.info(f"Summary saved to {filename}")
    except IOError as e:
        click.echo(f"[ERROR] Failed to write output file: {e}", err=True)
        sys.exit(1)


@robin.command()
@click.option(
    "--ui-port",
    default=8501,
    show_default=True,
    type=int,
    help="Port for the Streamlit UI",
)
@click.option(
    "--ui-host",
    default="localhost",
    show_default=True,
    type=str,
    help="Host for the Streamlit UI",
)
def ui(ui_port: int, ui_host: str):
    """Run Robin in Web UI mode."""
    from streamlit.web import cli as stcli

    # When PyInstaller one-file, data files live in _MEIPASS
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(__file__)

    ui_script = os.path.join(base, "ui.py")

    # Build sys.argv for streamlit
    sys.argv = [
        "streamlit",
        "run",
        ui_script,
        f"--server.port={ui_port}",
        f"--server.address={ui_host}",
        "--global.developmentMode=false",
    ]

    logger.info(f"Starting Streamlit UI on {ui_host}:{ui_port}")
    sys.exit(stcli.main())


if __name__ == "__main__":
    robin()
