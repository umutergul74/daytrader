"""Main CLI Application entry point."""

import typer
from rich.console import Console
from quant_platform.cli.commands.doctor import run_doctor
from quant_platform.cli.commands.data import app as data_app
from quant_platform.cli.commands.backtest import app as backtest_app
from quant_platform.cli.commands.research import app as research_app
from quant_platform.cli.commands.features import features_app
from quant_platform.cli.commands.strategies import strategies_app

cli = typer.Typer(
    name="quant",
    help="ETHUSDT Quantitative Research & Signal Platform CLI.",
    add_completion=False,
)

console = Console()

# Register command groups
cli.add_typer(data_app, name="data")
cli.add_typer(backtest_app, name="backtest")
cli.add_typer(research_app, name="research")
cli.add_typer(features_app, name="features")
cli.add_typer(strategies_app, name="strategies")


@cli.command("doctor")
def doctor_cmd():
    """Run comprehensive system health and environment diagnostics."""
    run_doctor()


@cli.command("bootstrap")
def bootstrap_cmd():
    """Ensure all local and drive workspace directories are initialized."""
    from quant_platform.config.settings import settings
    settings.ensure_directories()
    console.print("[green]Quant platform workspace directories initialized successfully.[/green]")


if __name__ == "__main__":
    cli()
