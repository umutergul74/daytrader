"""CLI command group: `quant research`."""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from quant_platform.research.ledger import ResearchLedger

app = typer.Typer(help="Inspect, query, and compare permanent research experiments.")
console = Console()


@app.command("list")
def list_experiments(
    limit: int = typer.Option(20, help="Number of experiments to show"),
    status: Optional[str] = typer.Option(None, help="Filter by status (completed, rejected, candidate, etc.)"),
):
    """List historical experiments from the Research Ledger."""
    ledger = ResearchLedger()
    experiments = ledger.list_experiments()

    if status:
        experiments = [e for e in experiments if e.get("status") == status.lower()]

    if not experiments:
        console.print("[yellow]No experiments found in Research Ledger.[/yellow]")
        return

    table = Table(title="Permanent Research Ledger Index", header_style="bold cyan")
    table.add_column("Experiment ID", style="bold white", width=26)
    table.add_column("Strategy", style="cyan")
    table.add_column("Status", width=12)
    table.add_column("Net Ret %", justify="right")
    table.add_column("Win Rate", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("Trades", justify="right")

    for e in experiments[:limit]:
        status_str = e.get("status", "unknown")
        status_color = "green" if status_str in ["completed", "validated", "candidate"] else "red"
        net_ret = e.get("net_return", 0.0)

        table.add_row(
            e["experiment_id"],
            e.get("strategy_id", "unknown"),
            f"[{status_color}]{status_str}[/{status_color}]",
            f"{net_ret:+.2f}%",
            f"{e.get('win_rate', 0.0):.1f}%",
            f"{e.get('sharpe', 0.0):.2f}",
            str(e.get("trade_count", 0)),
        )

    console.print(table)
    console.print(f"\nShowing [bold]{min(len(experiments), limit)}[/bold] of [bold]{len(experiments)}[/bold] total experiments.\n")


@app.command("show")
def show_experiment(experiment_id: str):
    """Display comprehensive details of a single experiment."""
    ledger = ResearchLedger()
    exp = ledger.get_experiment(experiment_id)

    if not exp:
        console.print(f"[red]Experiment '{experiment_id}' not found in ledger.[/red]")
        raise typer.Exit(code=1)

    console.print(f"\n[bold cyan]Experiment Audit Record: {exp.experiment_id}[/bold cyan]")
    console.print(f"Strategy: [bold]{exp.strategy_id}[/bold] (v{exp.strategy_version})")
    console.print(f"Hypothesis: [italic]\"{exp.hypothesis}\"[/italic]")
    console.print(f"Status: [bold]{exp.status.value}[/bold] | Date Range: {exp.date_range_start} -> {exp.date_range_end}")
    console.print(f"Git SHA: {exp.git_sha} (Dirty: {exp.git_dirty})")
    console.print(f"Dataset Fingerprint: {exp.dataset_fingerprint}")

    if exp.metrics:
        m = exp.metrics
        console.print(f"\n[bold green]Metrics Summary:[/bold green]")
        console.print(f" - Net Return: {m.total_net_return:+.2f}%")
        console.print(f" - Win Rate: {m.win_rate:.1f}% ({m.trade_count} trades)")
        console.print(f" - Profit Factor: {m.profit_factor:.2f}")
        console.print(f" - Sharpe: {m.sharpe_ratio:.2f} | Sortino: {m.sortino_ratio:.2f}")
        console.print(f" - Max Drawdown: {m.max_drawdown_pct:.2f}%")
        console.print(f" - Expectancy: ${m.expectancy:.2f} | Avg R: {m.average_r:.2f}R")

    if exp.conclusion:
        console.print(f"\n[bold]Conclusion:[/bold] {exp.conclusion}\n")
