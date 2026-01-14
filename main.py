import click
import subprocess
from yaspin import yaspin
from datetime import datetime
from scrape import scrape_multiple
from search import get_search_results
from llm import get_llm, refine_query, filter_results, generate_summary
from llm_utils import get_model_choices

MODEL_CHOICES = get_model_choices()


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
    llm = get_llm(model)

    # Show spinner while processing the query
    with yaspin(text="Processing...", color="cyan") as sp:
        refined_query = refine_query(llm, query)

        search_results = get_search_results(
            refined_query.replace(" ", "+"), max_workers=threads
        )

        search_filtered = filter_results(llm, refined_query, search_results)

        scraped_results = scrape_multiple(search_filtered, max_workers=threads)
        sp.ok("✔")

    # Generate the intelligence summary.
    summary = generate_summary(llm, query, scraped_results)

    # Save or print the summary
    if not output:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"summary_{now}.md"
    else:
        filename = output + ".md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(summary)
        click.echo(f"\n\n[OUTPUT] Final intelligence summary saved to {filename}")


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
def ui(ui_port, ui_host):
    """Run Robin in Web UI mode."""
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


@robin.command()
def login():
    """Authenticate with Google for Pro subscription access.
    
    Opens a browser window for Google OAuth authentication.
    Tokens are cached locally for future CLI and UI usage.
    
    Example:
        robin login
    """
    try:
        from antigravity import authenticate_cli, is_authenticated, get_user_info, load_cached_credentials
        
        if is_authenticated():
            creds = load_cached_credentials()
            user_info = get_user_info(creds.token)
            email = user_info.get('email', 'Unknown') if user_info else 'Unknown'
            click.echo(f"✅ Already authenticated as: {email}")
            click.echo("Use 'robin logout' to sign out.")
            return
        
        click.echo("🔐 Starting Google OAuth authentication...")
        creds = authenticate_cli()
        
        if creds:
            click.echo("\n✅ Authentication successful!")
            click.echo("You can now use models ending in '-pro' (e.g., gemini-3-flash-pro)")
            click.echo("\nExample:")
            click.echo('  robin cli -m gemini-3-flash-pro -q "your query"')
        else:
            click.echo("❌ Authentication failed.")
            
    except ImportError as e:
        click.echo(f"❌ OAuth dependencies not installed: {e}")
        click.echo("Install with: pip install google-auth-oauthlib")
    except Exception as e:
        click.echo(f"❌ Authentication error: {e}")


@robin.command()
def logout():
    """Clear cached Google authentication.
    
    Removes locally cached OAuth tokens.
    
    Example:
        robin logout
    """
    try:
        from antigravity import clear_credentials, is_authenticated
        
        if not is_authenticated():
            click.echo("ℹ️  Not currently authenticated.")
            return
        
        if clear_credentials():
            click.echo("✅ Successfully logged out.")
            click.echo("Use 'robin login' to authenticate again.")
        else:
            click.echo("ℹ️  No cached credentials found.")
            
    except ImportError as e:
        click.echo(f"❌ OAuth module not available: {e}")
    except Exception as e:
        click.echo(f"❌ Logout error: {e}")


@robin.command()
def status():
    """Check Google Pro authentication status.
    
    Shows current authentication state and user info.
    
    Example:
        robin status
    """
    try:
        from antigravity import is_authenticated, load_cached_credentials, get_user_info, TOKEN_CACHE_FILE
        
        if is_authenticated():
            creds = load_cached_credentials()
            user_info = get_user_info(creds.token)
            
            click.echo("🔐 Authentication Status: ✅ Authenticated")
            if user_info:
                click.echo(f"   Email: {user_info.get('email', 'Unknown')}")
                click.echo(f"   Name: {user_info.get('name', 'Unknown')}")
            click.echo(f"   Token cache: {TOKEN_CACHE_FILE}")
            click.echo("\nAvailable OAuth models:")
            for model in get_model_choices():
                if model.endswith('-pro'):
                    click.echo(f"   • {model}")
        else:
            click.echo("🔐 Authentication Status: ❌ Not authenticated")
            click.echo("\nUse 'robin login' to authenticate with Google Pro subscription.")
            
    except ImportError as e:
        click.echo(f"❌ OAuth module not available: {e}")
    except Exception as e:
        click.echo(f"❌ Status check error: {e}")


if __name__ == "__main__":
    robin()
