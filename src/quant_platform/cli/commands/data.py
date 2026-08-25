"""CLI command group: `quant data`."""

from datetime import datetime
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from quant_platform.data.providers.binance_archive import BinancePublicArchiveProvider
from quant_platform.data.storage.canonical import CanonicalStorage
from quant_platform.data.validation.integrity import DataIntegrityValidator
from quant_platform.data.manifest.manifest_manager import DatasetManifestManager
from quant_platform.observability.logger import logger

app = typer.Typer(help="Historical market data acquisition, validation, and manifest management.")
console = Console()


@app.command("fetch")
def fetch_data(
    symbol: str = typer.Option("ETHUSDT", help="Contract symbol"),
    timeframe: str = typer.Option("1m", help="Kline timeframe"),
    year: int = typer.Option(2024, help="Year to fetch"),
    month: int = typer.Option(1, help="Month to fetch (1-12)"),
):
    """Fetch monthly historical archive from Binance and save to canonical Parquet."""
    console.print(f"[cyan]Fetching {symbol} {timeframe} for {year}-{month:02d} from Binance public archive...[/cyan]")
    provider = BinancePublicArchiveProvider()
    storage = CanonicalStorage()

    df = provider.fetch_month(symbol, timeframe, year, month)
    if df is None or df.is_empty():
        console.print(f"[red]Failed to fetch or empty data for {year}-{month:02d}[/red]")
        raise typer.Exit(code=1)

    path = storage.write_month_partition(df, year=year, month=month, symbol=symbol, timeframe=timeframe)
    console.print(f"[green]Successfully saved canonical partition:[/green] {path} ({len(df)} bars)")


@app.command("status")
def data_status(
    symbol: str = typer.Option("ETHUSDT", help="Contract symbol"),
    timeframe: str = typer.Option("1m", help="Kline timeframe"),
):
    """Inspect current canonical partitions and coverage."""
    storage = CanonicalStorage()
    files = storage.list_partition_files(symbol=symbol, timeframe=timeframe)

    if not files:
        console.print(f"[yellow]No canonical data partitions found for {symbol} ({timeframe}).[/yellow]")
        return

    table = Table(title=f"Canonical Datasets: {symbol} ({timeframe})", header_style="bold cyan")
    table.add_column("Partition File", style="white")
    table.add_column("Size (KB)", justify="right")

    total_size = 0
    for f in files:
        sz_kb = f.stat().st_size / 1024.0
        total_size += sz_kb
        table.add_row(f.name, f"{sz_kb:.1f} KB")

    console.print(table)
    console.print(f"\nTotal Partitions: [bold]{len(files)}[/bold] | Total Size: [bold]{total_size/1024.0:.2f} MB[/bold]\n")


@app.command("verify")
def verify_data(
    symbol: str = typer.Option("ETHUSDT", help="Contract symbol"),
    timeframe: str = typer.Option("1m", help="Kline timeframe"),
):
    """Run full data integrity and gap detection audit."""
    storage = CanonicalStorage()
    df = storage.read_range(symbol=symbol, timeframe=timeframe)

    if df.is_empty():
        console.print(f"[yellow]No canonical data to verify for {symbol}.[/yellow]")
        return

    console.print(f"[cyan]Auditing {len(df)} bars for {symbol} ({timeframe})...[/cyan]")
    report = DataIntegrityValidator.validate_1m_series(df)

    table = Table(title="Data Integrity & Continuity Audit", header_style="bold green")
    table.add_column("Check", style="cyan")
    table.add_column("Result", style="white")

    table.add_row("Total 1-Minute Rows", str(report.total_rows))
    table.add_row("Duplicate Timestamps", f"[green]0[/green]" if report.duplicate_count == 0 else f"[red]{report.duplicate_count}[/red]")
    table.add_row("Invalid OHLC Records", f"[green]0[/green]" if report.invalid_ohlc_count == 0 else f"[red]{report.invalid_ohlc_count}[/red]")
    table.add_row("Negative Volume Records", f"[green]0[/green]" if report.negative_volume_count == 0 else f"[red]{report.negative_volume_count}[/red]")
    table.add_row("Detected Missing Gaps", f"[green]0[/green]" if report.gap_count == 0 else f"[yellow]{report.gap_count}[/yellow]")

    console.print(table)
    if report.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for w in report.warnings:
            console.print(f" - {w}")


@app.command("manifest")
def generate_manifest(
    symbol: str = typer.Option("ETHUSDT", help="Contract symbol"),
    timeframe: str = typer.Option("1m", help="Kline timeframe"),
):
    """Generate and persist immutable dataset manifest with SHA-256 fingerprint."""
    manager = DatasetManifestManager()
    manifest = manager.generate_manifest(symbol=symbol, timeframe=timeframe)
    console.print(f"[bold green]Dataset Manifest Generated:[/bold green]")
    console.print(f"Dataset ID: [bold]{manifest.dataset_id}[/bold]")
    console.print(f"SHA-256 Fingerprint: [cyan]{manifest.canonical_fingerprint}[/cyan]")
    console.print(f"Total Rows: {manifest.row_count} across {manifest.partition_count} partitions")
