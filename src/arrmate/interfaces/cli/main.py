"""CLI interface for Arrmate."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ...clients.discovery import discover_services
from ...config.settings import settings
from ...core.command_parser import CommandParser
from ...core.executor import Executor
from ...core.intent_engine import IntentEngine

app = typer.Typer(
    name="arrmate",
    help="Natural language interface for media management (Sonarr, Radarr, Lidarr)",
)
console = Console()


@app.command()
def execute(
    command: str = typer.Argument(..., help="Natural language command to execute"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show parsed intent without executing"),
) -> None:
    """Execute a natural language media management command.

    Examples:
        arrmate execute "remove episode 1 and 2 of Angel season 1"
        arrmate execute "add Breaking Bad to my library"
        arrmate execute "search for 4K version of Blade Runner"
    """
    asyncio.run(_execute_command(command, dry_run))


async def _execute_command(command: str, dry_run: bool) -> None:
    """Execute a command (async implementation)."""
    console.print(f"\n[bold]Command:[/bold] {command}\n")

    # Initialize components
    parser = CommandParser()
    engine = IntentEngine()
    executor = Executor()

    try:
        # Parse command
        with console.status("[bold yellow]Parsing command..."):
            intent = await parser.parse(command)

        console.print(f"[bold green]✓[/bold green] Parsed intent:")
        console.print(f"  Action: [cyan]{intent.action}[/cyan]")
        console.print(f"  Media Type: [cyan]{intent.media_type}[/cyan]")
        if intent.title:
            console.print(f"  Title: [cyan]{intent.title}[/cyan]")
        if intent.season is not None:
            console.print(f"  Season: [cyan]{intent.season}[/cyan]")
        if intent.episodes:
            console.print(f"  Episodes: [cyan]{intent.episodes}[/cyan]")
        if intent.criteria:
            console.print(f"  Criteria: [cyan]{intent.criteria}[/cyan]")
        console.print()

        if dry_run:
            console.print("[yellow]Dry run mode - not executing[/yellow]")
            return

        # Enrich intent
        with console.status("[bold yellow]Enriching intent..."):
            enriched_intent = await engine.enrich(intent)

        # Validate
        errors = engine.validate(enriched_intent)
        if errors:
            console.print("[bold red]Validation errors:[/bold red]")
            for error in errors:
                console.print(f"  • {error}")
            return

        # Execute
        with console.status("[bold yellow]Executing..."):
            result = await executor.execute(enriched_intent)

        # Display result
        if result.success:
            console.print(f"\n[bold green]✓ Success![/bold green]")
            console.print(f"{result.message}\n")
            if result.data:
                console.print("[dim]Additional details:[/dim]")
                console.print(result.data)
        else:
            console.print(f"\n[bold red]✗ Failed[/bold red]")
            console.print(f"{result.message}\n")
            if result.errors:
                console.print("[bold red]Errors:[/bold red]")
                for error in result.errors:
                    console.print(f"  • {error}")

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
    finally:
        await parser.close()


@app.command()
def interactive() -> None:
    """Start interactive mode for executing commands."""
    console.print("\n[bold]Arrmate Interactive Mode[/bold]")
    console.print("Enter natural language commands (type 'exit' or 'quit' to stop)\n")

    while True:
        try:
            command = console.input("[bold cyan]>[/bold cyan] ")

            if command.lower() in ["exit", "quit", "q"]:
                console.print("\nGoodbye!")
                break

            if not command.strip():
                continue

            asyncio.run(_execute_command(command, dry_run=False))
            console.print()

        except KeyboardInterrupt:
            console.print("\n\nGoodbye!")
            break
        except EOFError:
            console.print("\n\nGoodbye!")
            break


@app.command()
def services() -> None:
    """List discovered media services and their status."""
    console.print("\n[bold]Discovering services...[/bold]\n")

    services = asyncio.run(discover_services())

    if not services:
        console.print("[yellow]No services configured[/yellow]")
        console.print(
            "\nSet environment variables (SONARR_URL, RADARR_URL, etc.) to configure services."
        )
        return

    # Create table
    table = Table(title="Media Services")
    table.add_column("Service", style="cyan")
    table.add_column("URL", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Version", style="magenta")

    for service_name, service_info in services.items():
        status = "✓ Available" if service_info.available else "✗ Unavailable"
        status_style = "green" if service_info.available else "red"

        table.add_row(
            service_name.upper(),
            service_info.url,
            f"[{status_style}]{status}[/{status_style}]",
            service_info.version or "N/A",
        )

    console.print(table)
    console.print()


@app.command()
def config() -> None:
    """Display current configuration."""
    console.print("\n[bold]Current Configuration[/bold]\n")

    table = Table()
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")

    table.add_row("LLM Provider", settings.llm_provider)
    table.add_row("Log Level", settings.log_level)
    table.add_row("API Port", str(settings.api_port))

    if settings.llm_provider == "ollama":
        table.add_row("Ollama URL", settings.ollama_base_url)
        table.add_row("Ollama Model", settings.ollama_model)
    elif settings.llm_provider == "openai":
        table.add_row("OpenAI Model", settings.openai_model)
        table.add_row("OpenAI API Key", "***" + (settings.openai_api_key[-4:] if settings.openai_api_key else ""))
    elif settings.llm_provider == "anthropic":
        table.add_row("Anthropic Model", settings.anthropic_model)
        table.add_row("Anthropic API Key", "***" + (settings.anthropic_api_key[-4:] if settings.anthropic_api_key else ""))

    console.print(table)
    console.print()


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
