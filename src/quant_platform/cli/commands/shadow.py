"""CLI Commands for Shadow Baseline Management and Telemetry Monitoring."""

import typer
from rich.console import Console
from rich.table import Table

from quant_platform.live.shadow_release import ShadowReleaseManager
from quant_platform.live.reliability import OperationalReliabilityTracker
from quant_platform.live.expectation_monitor import ExpectationMonitor
from quant_platform.live.paper_broker import PaperPortfolio
from quant_platform.research.counterfactual_analyzer import CounterfactualAnalyzer

app = typer.Typer(help="Operational Shadow baseline freeze, reliability telemetry, and expectation monitoring.")
console = Console()


@app.command(name="freeze")
def freeze_shadow_baseline():
    """Create and freeze the canonical shadow-baseline-v1 operational release."""
    manifest = ShadowReleaseManager.create_shadow_baseline_v1()
    console.print(f"[bold green][OK] Shadow Baseline Frozen Successfully![/bold green]")
    console.print(f"[cyan]Release ID:[/cyan] {manifest.release_id}")
    console.print(f"[cyan]Git SHA:[/cyan] {manifest.git_sha}")
    console.print(f"[cyan]Champion:[/cyan] {manifest.champion_strategy.component_name}:{manifest.champion_strategy.version}")
    console.print(f"[cyan]Policy:[/cyan] {manifest.operational_policy}")


@app.command(name="status")
def show_shadow_status(symbol: str = "ETHUSDT"):
    """Display live operational reliability metrics, drift state, and expectations."""
    tracker = OperationalReliabilityTracker(symbol=symbol)
    record = tracker.checkpoint_daily_telemetry()

    table = Table(title=f"Shadow Platform Reliability Telemetry ({symbol})")
    table.add_column("Subsystem", style="cyan", justify="left")
    table.add_column("Metric", style="white", justify="left")
    table.add_column("Value", style="green", justify="right")

    table.add_row("Market Data", "WebSocket Connected", str(record.market_data.websocket_connected))
    table.add_row("Market Data", "Messages Received", f"{record.market_data.total_messages_received:,}")
    table.add_row("Market Data", "Reconnects", str(record.market_data.reconnect_count))
    table.add_row("Signal Engine", "Total Bar Evaluations", f"{record.signal_engine.total_bar_evaluations:,}")
    table.add_row("Signal Engine", "NO_TRADE Decisions", f"{record.signal_engine.no_trade_decisions:,}")
    table.add_row("Paper Broker", "Simulated Entries", str(record.paper_broker.simulated_entries_count))
    table.add_row("Notifications", "Telegram Dispatches", str(record.notifications.telegram_dispatches_success))

    console.print(table)


@app.command(name="counterfactual")
def run_counterfactual_audit(strategy_id: str = "smc:liquidity_sweep_fvg:v2"):
    """Evaluate offline counterfactual microstructure filters on trades."""
    # Synthetic trade evaluations
    mock_trades = [
        {"net_pnl": 50.0, "r_multiple": 2.0, "direction": "LONG", "cvd_bullish_divergence": True, "joint_price_oi_regime": "LONG_BUILDUP", "trade_imbalance_1m": 0.10, "is_liquidation_burst": True},
        {"net_pnl": -25.0, "r_multiple": -1.0, "direction": "LONG", "cvd_bullish_divergence": False, "joint_price_oi_regime": "LONG_LIQUIDATION", "trade_imbalance_1m": -0.08, "is_liquidation_burst": False},
        {"net_pnl": 40.0, "r_multiple": 1.6, "direction": "SHORT", "cvd_bearish_divergence": True, "joint_price_oi_regime": "SHORT_BUILDUP", "trade_imbalance_1m": -0.15, "is_liquidation_burst": True},
        {"net_pnl": -25.0, "r_multiple": -1.0, "direction": "SHORT", "cvd_bearish_divergence": False, "joint_price_oi_regime": "SHORT_COVERING", "trade_imbalance_1m": 0.05, "is_liquidation_burst": False},
    ] * 5

    study = CounterfactualAnalyzer.run_standard_counterfactual_suite(strategy_id=strategy_id, trades_with_features=mock_trades)

    table = Table(title=f"Counterfactual Microstructure Filter Study ({strategy_id})")
    table.add_column("Filter", style="cyan")
    table.add_column("Trades", justify="right")
    table.add_column("Win Rate", justify="right")
    table.add_column("Profit Factor", justify="right")
    table.add_column("Expectancy Delta", justify="right")
    table.add_column("Status", justify="center")

    table.add_row("BASELINE", str(study.total_trades_analyzed), f"{study.baseline_win_rate:.1f}%", f"{study.baseline_profit_factor:.2f}", "0.00R", "BENCHMARK")

    for f_res in study.filter_evaluations:
        status_style = "[bold green]ACCEPT[/bold green]" if f_res.marginal_edge_status == "ACCEPT" else ("[yellow]CONDITIONAL[/yellow]" if f_res.marginal_edge_status == "CONDITIONAL" else "[red]REJECT[/red]")
        table.add_row(
            f_res.filter_name,
            f"{f_res.filtered_trade_count} (-{f_res.trade_reduction_pct:.0f}%)",
            f"{f_res.filtered_win_rate:.1f}%",
            f"{f_res.filtered_profit_factor:.2f}",
            f"{f_res.expectancy_delta_r:+.2f}R",
            status_style,
        )

    console.print(table)
