"""CLI command group: `quant backtest`."""

from datetime import datetime
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from quant_platform.strategies.catalog import StrategyCatalog
from quant_platform.data.storage.canonical import CanonicalStorage
from quant_platform.data.timeframes.resampler import CausalResampler
from quant_platform.backtest.engine import BacktestEngine
from quant_platform.backtest.costs import CostModel
from quant_platform.research.ledger import ResearchLedger
from quant_platform.research.mlflow_adapter import MLflowAdapter
from quant_platform.research.reporting import ReportGenerator
from quant_platform.domain.experiment import ExperimentRecord, ExperimentStatus
from quant_platform.colab.git_sync import SafeGitSync

app = typer.Typer(help="Run reproducible backtests and generate publication reports.")
console = Console()


@app.command("run")
def run_backtest(
    strategy_name: str = typer.Option("ema_trend", help="Strategy from StrategyCatalog"),
    symbol: str = typer.Option("ETHUSDT", help="Contract symbol"),
    timeframe: str = typer.Option("15m", help="Trading timeframe"),
    start_date: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD)"),
    capital: float = typer.Option(10000.0, help="Initial account capital in USDT"),
    register: bool = typer.Option(True, help="Register in Research Ledger"),
):
    """Execute event-aware causal backtest for a strategy."""
    strat_cls = StrategyCatalog.get_strategy_class(strategy_name)
    if not strat_cls:
        console.print(f"[red]Unknown strategy '{strategy_name}'. Available: {StrategyCatalog.list_strategies()}[/red]")
        raise typer.Exit(code=1)

    strategy = strat_cls()
    console.print(f"[cyan]Initializing backtest for [bold]{strategy.metadata.strategy_id}[/bold] ({timeframe})...[/cyan]")

    # 1. Load canonical 1m data
    storage = CanonicalStorage()
    dt_start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    dt_end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    df_1m = storage.read_range(start_time=dt_start, end_time=dt_end, symbol=symbol)
    if df_1m.is_empty():
        console.print(f"[red]No canonical data available for {symbol}. Run `quant data fetch` or check range.[/red]")
        raise typer.Exit(code=1)

    # 2. Resample to target timeframe causally if != 1m
    df_tf = CausalResampler.resample(df_1m, target_timeframe=timeframe) if timeframe != "1m" else df_1m
    console.print(f"Loaded [bold]{len(df_tf)}[/bold] bars ({df_tf['open_time'].min()} -> {df_tf['open_time'].max()})")

    # 3. Run backtest
    engine = BacktestEngine(initial_capital=capital)
    result = engine.run(df_tf, strategy)
    m = result.metrics

    # 4. Display Summary Table
    table = Table(title=f"Backtest Results: {strategy.metadata.strategy_id}", header_style="bold green")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Total Net Return", f"[bold {'green' if m.total_net_return >= 0 else 'red'}]{m.total_net_return:+.2f}%[/bold {'green' if m.total_net_return >= 0 else 'red'}]")
    table.add_row("Win Rate", f"{m.win_rate:.1f}%")
    table.add_row("Profit Factor", f"{m.profit_factor:.2f}")
    table.add_row("Sharpe Ratio", f"{m.sharpe_ratio:.2f}")
    table.add_row("Sortino Ratio", f"{m.sortino_ratio:.2f}")
    table.add_row("Max Drawdown", f"[red]{m.max_drawdown_pct:.2f}%[/red]")
    table.add_row("Trade Count", str(m.trade_count))
    table.add_row("Average R", f"{m.average_r:.2f}R")
    table.add_row("Total Fees Paid", f"${m.total_fees:.2f}")
    table.add_row("Intrabar Ambiguities", str(m.intrabar_ambiguity_count))

    console.print(table)

    # 5. Register in Research Ledger & MLflow & HTML Report
    if register:
        ledger = ResearchLedger()
        exp_id = ledger.generate_experiment_id()
        git_info = SafeGitSync().get_git_info()

        first_ts = int(df_tf["open_time"].min())
        last_ts = int(df_tf["open_time"].max())
        d_start_str = datetime.fromtimestamp(first_ts/1000.0).strftime("%Y-%m-%d")
        d_end_str = datetime.fromtimestamp(last_ts/1000.0).strftime("%Y-%m-%d")

        record = ExperimentRecord(
            experiment_id=exp_id,
            hypothesis=strategy.metadata.hypothesis,
            strategy_id=strategy.metadata.strategy_id,
            strategy_version=strategy.metadata.version,
            feature_set_version="v1",
            parameters=strategy.metadata.parameters,
            parameter_hash=ledger._compute_parameter_hash(strategy.metadata.parameters),
            dataset_fingerprint="synthetic_or_canonical",
            symbol=symbol,
            timeframe=timeframe,
            date_range_start=d_start_str,
            date_range_end=d_end_str,
            git_sha=git_info["git_sha"],
            git_dirty=git_info["is_dirty"],
            cost_model=engine.cost_model.model_dump(),
            execution_model="EVENT_AWARE_TAKER_ENTRY_LIMIT_TP_MARKET_SL",
            risk_model="STRUCTURAL_ATR_FIXED_RISK_1PCT",
            metrics=m,
            trade_count=m.trade_count,
            status=ExperimentStatus.COMPLETED if m.total_net_return > 0 else ExperimentStatus.REJECTED,
            conclusion="Automated backtest completed successfully.",
        )

        ledger.register_experiment(record)

        # Generate Reports
        reporter = ReportGenerator()
        html_path = reporter.generate_html_report(record, result.ledger)
        json_path = reporter.generate_json_export(record)

        # MLflow logging
        mlflow_adapter = MLflowAdapter()
        mlflow_adapter.log_experiment(record, artifact_paths={"report_html": html_path, "export_json": json_path})

        console.print(f"[bold green]Registered in Research Ledger:[/bold green] {exp_id}")
        console.print(f"HTML Report generated at: [cyan]{html_path}[/cyan]\n")
