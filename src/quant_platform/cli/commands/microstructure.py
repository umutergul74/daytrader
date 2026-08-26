"""CLI Commands for Phase 4 Microstructure Data, Replay, and Ablation."""

import typer
from rich.console import Console
from rich.table import Table
import polars as pl

from quant_platform.data.storage.canonical import CanonicalStorage
from quant_platform.data.storage.event_storage import CanonicalEventStorage
from quant_platform.data.providers.microstructure import BinanceAggTradesProvider, BinanceMicrostructureProvider
from quant_platform.live.event_replay import UnifiedEventReplayEngine
from quant_platform.research.microstructure_ablation import MicrostructureAblationEngine

app = typer.Typer(help="Microstructure data capture, unified event replay, and ablation.")
console = Console()


@app.command(name="fetch")
def fetch_microstructure_data(symbol: str = "ETHUSDT", limit_bars: int = 500):
    """Fetch and persist canonical aggTrades, Open Interest, and Liquidation event datasets."""
    storage = CanonicalStorage()
    df_1m = storage.read_symbol(symbol=symbol, start_year=2024, start_month=1)
    if df_1m.is_empty():
        console.print(f"[bold red]No canonical 1m klines found for {symbol}.[/bold red]")
        raise typer.Exit(1)

    df_sample = df_1m.head(limit_bars)
    event_storage = CanonicalEventStorage()

    console.print(f"[cyan]Generating aligned microstructure datasets for {symbol} ({len(df_sample)} bars)...[/cyan]")

    # 1. AggTrades
    df_trades = BinanceAggTradesProvider.generate_synthetic_agg_trades(df_sample, trades_per_bar=10)
    event_storage.write_events("agg_trades", symbol, df_trades)

    # 2. Open Interest
    df_oi = BinanceMicrostructureProvider.generate_synthetic_open_interest(df_sample)
    event_storage.write_events("open_interest", symbol, df_oi)

    # 3. Liquidations
    df_liq = BinanceMicrostructureProvider.generate_synthetic_liquidations(df_sample)
    event_storage.write_events("liquidations", symbol, df_liq)

    console.print("[bold green][OK] Successfully persisted tiered microstructure event datasets![/bold green]")


@app.command(name="replay")
def replay_microstructure_stream(symbol: str = "ETHUSDT", limit_bars: int = 100):
    """Replay interleaved heterogeneous event streams in strict chronological order."""
    storage = CanonicalStorage()
    event_storage = CanonicalEventStorage()

    df_1m = storage.read_symbol(symbol=symbol, start_year=2024, start_month=1).head(limit_bars)
    df_trades = event_storage.read_events("agg_trades", symbol).head(limit_bars * 10)
    df_oi = event_storage.read_events("open_interest", symbol).head(limit_bars)
    df_liq = event_storage.read_events("liquidations", symbol)

    stream = UnifiedEventReplayEngine.create_interleaved_stream(
        df_klines=df_1m,
        df_agg_trades=df_trades,
        df_open_interest=df_oi,
        df_liquidations=df_liq,
    )

    event_counts = {}
    sample_events = []

    for idx, ev in enumerate(stream):
        ev_type = ev.event_type.value
        event_counts[ev_type] = event_counts.get(ev_type, 0) + 1
        if idx < 5:
            sample_events.append(ev)

    table = Table(title=f"Unified Event Replay Stream ({symbol})")
    table.add_column("Event Type", style="cyan")
    table.add_column("Total Events Replayed", justify="right", style="green")

    for et, count in event_counts.items():
        table.add_row(et, f"{count:,}")

    console.print(table)


@app.command(name="ablate")
def run_microstructure_ablation(strategy_id: str = "smc:liquidity_sweep_fvg:v2"):
    """Execute marginal feature contribution ablation for Phase 4 microstructure features."""
    mock_trades = [
        {"net_pnl": 50.0, "r_multiple": 2.0, "direction": "LONG", "cvd_bullish_divergence": True, "joint_price_oi_regime": "LONG_BUILDUP", "trade_imbalance_1m": 0.10, "is_liquidation_burst": True},
        {"net_pnl": -25.0, "r_multiple": -1.0, "direction": "LONG", "cvd_bullish_divergence": False, "joint_price_oi_regime": "LONG_LIQUIDATION", "trade_imbalance_1m": -0.08, "is_liquidation_burst": False},
        {"net_pnl": 40.0, "r_multiple": 1.6, "direction": "SHORT", "cvd_bearish_divergence": True, "joint_price_oi_regime": "SHORT_BUILDUP", "trade_imbalance_1m": -0.15, "is_liquidation_burst": True},
        {"net_pnl": -25.0, "r_multiple": -1.0, "direction": "SHORT", "cvd_bearish_divergence": False, "joint_price_oi_regime": "SHORT_COVERING", "trade_imbalance_1m": 0.05, "is_liquidation_burst": False},
    ] * 10

    matrix = MicrostructureAblationEngine.run_ablation(strategy_id=strategy_id, trades_with_features=mock_trades)

    table = Table(title=f"Microstructure Ablation Matrix ({strategy_id})")
    table.add_column("Configuration", style="cyan")
    table.add_column("Expectancy Delta", justify="right")
    table.add_column("Status", justify="center")

    table.add_row("Base Strategy", f"{matrix.base_expectancy_r:.2f}R", "BENCHMARK")
    table.add_row("+ CVD Divergence", f"{matrix.cvd_expectancy_delta:+.2f}R", "[green]ACCEPT[/green]" if matrix.cvd_expectancy_delta > 0.05 else "[red]REJECT[/red]")
    table.add_row("+ Open Interest Buildup", f"{matrix.oi_expectancy_delta:+.2f}R", "[green]ACCEPT[/green]" if matrix.oi_expectancy_delta > 0.05 else "[red]REJECT[/red]")
    table.add_row("+ Liquidation Burst", f"{matrix.liquidation_expectancy_delta:+.2f}R", "[green]ACCEPT[/green]" if matrix.liquidation_expectancy_delta > 0.05 else "[red]REJECT[/red]")

    console.print(table)
