"""Robin: AI-Powered Dark Web OSINT Tool - Main CLI entry point."""
import asyncio
import click
from datetime import datetime

from config import DEFAULT_MODEL


@click.group()
@click.version_option()
def robin():
    """Robin: AI-Powered Dark Web OSINT Tool using Claude Agent SDK."""
    pass


@robin.command()
@click.option(
    "--query", "-q",
    required=True,
    type=str,
    help="Dark web investigation query",
)
@click.option(
    "--output", "-o",
    type=str,
    help="Filename to save the report. If not provided, auto-generated.",
)
@click.option(
    "--interactive", "-i",
    is_flag=True,
    default=False,
    help="Enable interactive mode for follow-up queries",
)
@click.option(
    "--model", "-m",
    default=DEFAULT_MODEL,
    show_default=True,
    type=str,
    help="Claude model to use",
)
def cli(query: str, output: str, interactive: bool, model: str):
    """Run Robin in CLI mode.

    Examples:
    \b
      robin cli -q "ransomware payments"
      robin cli -q "threat actor APT28" -o report
      robin cli -q "credential leaks" --interactive
    """
    asyncio.run(_run_cli(query, output, interactive, model))


async def _run_cli(query: str, output: str, interactive: bool, model: str):
    """Async CLI implementation."""
    from agent import RobinAgent, InvestigationResult

    # Track tool usage for display
    tool_calls = []

    def on_tool_use(name: str, input_data: dict):
        tool_calls.append(name)
        click.echo(f"\n  [Tool] {name}", nl=False)

    def on_text(text: str):
        # Stream text to terminal
        click.echo(text, nl=False)

    def on_complete(result: InvestigationResult):
        click.echo(f"\n\n[Completed] {result.num_turns or 'N/A'} turns, "
                   f"{len(result.tools_used)} tools used")

    agent = RobinAgent(
        on_text=on_text,
        on_tool_use=on_tool_use,
        on_complete=on_complete,
        model=model,
    )

    click.echo(f"\n{'='*60}")
    click.echo("Robin - Dark Web OSINT Agent")
    click.echo(f"{'='*60}")
    click.echo(f"\nQuery: {query}\n")

    # Run initial investigation
    full_response = ""
    async for chunk in agent.investigate(query):
        full_response += chunk

    # Save report if output specified or auto-generate
    if output or not interactive:
        if not output:
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output = f"robin_report_{now}"

        filename = output if output.endswith(".md") else f"{output}.md"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(full_response)

        click.echo(f"\n[Saved] Report saved to {filename}")

    # Interactive mode for follow-ups
    if interactive:
        click.echo("\n" + "="*60)
        click.echo("Interactive Mode - Enter follow-up queries (Ctrl+C to exit)")
        click.echo("="*60)

        while True:
            try:
                follow_up = click.prompt("\nFollow-up", type=str)
                if follow_up.lower() in ("exit", "quit", "q"):
                    break

                click.echo()
                async for chunk in agent.follow_up(follow_up):
                    pass  # on_text callback handles output

            except (KeyboardInterrupt, EOFError):
                click.echo("\n\nExiting interactive mode.")
                break


if __name__ == "__main__":
    robin()
