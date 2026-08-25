"""Strategies and Strategy Catalog CLI Commands."""

import json
import typer
from rich.console import Console
from rich.table import Table

from quant_platform.strategies.catalog import StrategyCatalog

strategies_app = typer.Typer(help="Inspect strategy catalog, hypotheses, and required features.")
console = Console()


@strategies_app.command("list")
def list_strategies():
    """List all registered benchmark and advanced strategies."""
    strategies = StrategyCatalog.list_all()

    table = Table(title="Strategy Catalog", show_header=True, header_style="bold cyan")
    table.add_column("Strategy ID", style="bold")
    table.add_column("Family", style="yellow")
    table.add_column("Version")
    table.add_column("Hypothesis")

    for s in strategies:
        table.add_row(
            s.strategy_id,
            s.family,
            s.version,
            s.hypothesis[:60] + "...",
        )

    console.print(table)


@strategies_app.command("show")
def show_strategy(strategy_id: str = typer.Argument(..., help="Strategy ID (e.g. smc:liquidity_sweep_fvg)")):
    """Show detailed strategy metadata, hypothesis, and parameters."""
    strat = StrategyCatalog.get(strategy_id)
    if not strat:
        console.print(f"[bold red]Strategy '{strategy_id}' not found in catalog.[/bold red]")
        raise typer.Exit(1)

    table = Table(title=f"Strategy Specification: {strat.strategy_id}:{strat.version}", show_header=True)
    table.add_column("Attribute", style="bold cyan")
    table.add_column("Value")

    table.add_row("Family", strat.family)
    table.add_row("Hypothesis", strat.hypothesis)
    table.add_row("Required Features", ", ".join(strat.required_features))
    table.add_row("Parameters", json.dumps(strat.parameters, indent=2))

    console.print(table)
