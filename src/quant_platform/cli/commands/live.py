"""Live Shadow Platform CLI Commands (`quant live`)."""

import asyncio
from datetime import datetime, timezone
import typer
from rich.console import Console
from rich.table import Table

from quant_platform.data.storage.canonical import CanonicalStorage
from quant_platform.live.parity import ParityEngine
from quant_platform.live.replay import MarketReplayEngine
from quant_platform.live.state_engine import LiveStateEngine
from quant_platform.live.paper_broker import PaperBroker
from quant_platform.live.champion_challenger import ChampionChallengerCoordinator
from quant_platform.live.websocket_client import BinanceFuturesWebSocketClient
from quant_platform.strategies.advanced.liquidity_sweep_fvg import LiquiditySweepFVGStrategy
from quant_platform.strategies.baselines.breakout import BreakoutSanityStrategy
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy
from quant_platform.strategies.advanced.regime_mean_reversion import RegimeAwareMeanReversionStrategy

live_app = typer.Typer(help="Live shadow platform, parity verification, market replay, and paper trading.")
console = Console()


@live_app.command("parity")
def verify_parity_cmd(
    symbol: str = typer.Option("ETHUSDT", help="Market symbol"),
    limit_bars: int = typer.Option(500, help="Number of 1m bars to audit for parity"),
):
    """Verify 100% Backtest / Live Parity between batch and streaming computations."""
    storage = CanonicalStorage()
    df_1m = storage.read_range(symbol=symbol)

    if df_1m.is_empty():
        console.print("[red]No canonical dataset found. Run `quant data fetch` or synthesis first.[/red]")
        raise typer.Exit(1)

    df_subset = df_1m.tail(limit_bars)
    console.print(f"[cyan]Auditing Backtest/Live Parity across {len(df_subset)} bars...[/cyan]")

    rep = ParityEngine.verify_parity(df_subset, symbol=symbol)

    table = Table(title=f"Backtest / Live Parity Audit: {symbol}", header_style="bold cyan")
    table.add_column("Feature / Indicator", style="bold")
    table.add_column("Timeframe")
    table.add_column("Max Abs Delta", justify="right")
    table.add_column("Parity %", justify="right")
    table.add_column("Status", justify="center")

    for c in rep.checks:
        parity_ratio = (c.matches / max(1, c.total_bars_checked)) * 100.0
        status_style = "[bold green]MATCH[/bold green]" if c.is_parity_clean else "[bold red]MISMATCH[/bold red]"
        table.add_row(
            c.feature_name,
            c.timeframe,
            f"{c.max_absolute_delta:.6f}",
            f"{parity_ratio:.1f}%",
            status_style,
        )

    console.print(table)
    if rep.is_full_parity_achieved:
        console.print(f"\n[bold green]PASSED: 100% Mathematical & Event Parity Achieved ({rep.overall_parity_pct:.1f}%).[/bold green]\n")
    else:
        console.print(f"\n[bold red]FAILED: Parity discrepancies detected ({rep.overall_parity_pct:.1f}%).[/bold red]\n")


@live_app.command("replay")
def run_market_replay_cmd(
    symbol: str = typer.Option("ETHUSDT", help="Market symbol"),
    bars: int = typer.Option(500, help="Number of 1m bars to replay"),
    speed: float = typer.Option(0.0, help="Speed multiplier (0.0 for instant, 50.0 for 50x live speed)"),
):
    """Run accelerated historical market replay through the live shadow state engine."""
    storage = CanonicalStorage()
    df_1m = storage.read_range(symbol=symbol)

    if df_1m.is_empty():
        console.print("[red]No canonical dataset found.[/red]")
        raise typer.Exit(1)

    df_subset = df_1m.tail(bars)

    champion = LiquiditySweepFVGStrategy(left_bars=3, right_bars=3)
    challengers = {
        "Breakout": BreakoutSanityStrategy(lookback_period=20),
        "EmaTrend": EmaTrendStrategy(fast_period=10, slow_period=30),
    }

    state_engine = LiveStateEngine(symbol=symbol)
    coordinator = ChampionChallengerCoordinator(champion_strategy=champion, challengers=challengers)

    replay_engine = MarketReplayEngine(state_engine=state_engine, speed_multiplier=speed)

    console.print(f"[cyan]Initiating Market Replay of {len(df_subset)} bars...[/cyan]")
    res = replay_engine.replay(df_subset, on_bar_callback=lambda snap: coordinator.evaluate_live_bar(state_engine))

    table = Table(title=f"Market Replay Summary: {symbol}", header_style="bold cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Total 1m Bars Replayed", str(res.total_bars_replayed))
    table.add_row("Simulated Time", f"{res.simulated_days:.2f} days")
    table.add_row("Execution Duration", f"{res.duration_seconds:.2f}s")
    table.add_row("Effective Speed", f"{res.effective_speed_multiplier:.0f}x live")
    table.add_row("Final Evaluated Price", f"${res.final_price:,.2f}")
    table.add_row("Signals Generated", str(coordinator.signals_generated_count))

    console.print(table)

    # Print comparative portfolio table
    comp_rows = coordinator.get_comparative_table()
    comp_table = Table(title="Champion vs Challengers Replay Performance", header_style="bold green")
    comp_table.add_column("Role", style="yellow")
    comp_table.add_column("Strategy")
    comp_table.add_column("Trades", justify="right")
    comp_table.add_column("Net PnL", justify="right")
    comp_table.add_column("Return %", justify="right")
    comp_table.add_column("Win Rate", justify="right")
    comp_table.add_column("Max DD %", justify="right")

    for row in comp_rows:
        comp_table.add_row(
            row.role,
            row.strategy_name,
            str(row.total_trades),
            f"${row.net_pnl_usdt:+,.2f}",
            f"{row.net_return_pct:+.2f}%",
            f"{row.win_rate_pct:.1f}%",
            f"{row.max_drawdown_pct:.2f}%",
        )

    console.print(comp_table)


@live_app.command("start")
def start_live_shadow_cmd(
    symbol: str = typer.Option("ETHUSDT", help="Contract symbol"),
    duration_minutes: int = typer.Option(60, help="Live session duration in minutes"),
):
    """Launch live shadow mode connecting to Binance Futures WebSocket."""
    champion = LiquiditySweepFVGStrategy(left_bars=3, right_bars=3)
    challengers = {
        "Breakout": BreakoutSanityStrategy(lookback_period=20),
        "EmaTrend": EmaTrendStrategy(fast_period=10, slow_period=30),
    }

    state_engine = LiveStateEngine(symbol=symbol)
    coordinator = ChampionChallengerCoordinator(champion_strategy=champion, challengers=challengers)
    ws_client = BinanceFuturesWebSocketClient(symbol=symbol, state_engine=state_engine, coordinator=coordinator)

    console.print(f"[bold green]Starting Live Shadow Session for {symbol} ({duration_minutes} min)...[/bold green]")
    console.print("[yellow]Execution Policy: NO_REAL_MONEY (Paper trading simulation)[/yellow]")

    try:
        asyncio.run(ws_client.connect_and_listen(max_duration_seconds=duration_minutes * 60))
    except KeyboardInterrupt:
        console.print("\n[cyan]Live Shadow session interrupted by user.[/cyan]")
