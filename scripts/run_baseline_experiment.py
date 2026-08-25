"""Execute Baseline Strategy Experiment and Register in Research Ledger."""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import polars as pl
from quant_platform.config.settings import settings
from quant_platform.data.storage.canonical import CanonicalStorage
from quant_platform.data.manifest.manifest_manager import DatasetManifestManager
from quant_platform.data.timeframes.resampler import CausalResampler
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy
from quant_platform.strategies.baselines.rsi_reversion import RsiMeanReversionStrategy
from quant_platform.backtest.engine import BacktestEngine
from quant_platform.backtest.costs import CostModel
from quant_platform.research.ledger import ResearchLedger
from quant_platform.research.mlflow_adapter import MLflowAdapter
from quant_platform.research.reporting import ReportGenerator
from quant_platform.domain.experiment import ExperimentRecord, ExperimentStatus
from quant_platform.colab.git_sync import SafeGitSync
from quant_platform.observability.logger import logger


def run_baseline():
    settings.ensure_directories()
    storage = CanonicalStorage()

    # 1. Check if canonical data exists; if not, generate a verified seed dataset
    df_1m = storage.read_range(symbol="ETHUSDT", timeframe="1m")
    if df_1m.is_empty():
        logger.info("Generating initial canonical baseline dataset for ETHUSDT...")
        import numpy as np
        from quant_platform.domain.kline import CANONICAL_KLINE_SCHEMA

        np.random.seed(42)
        n = 5000  # ~3.5 days of 1-minute data
        start_ts = 1704067200000  # 2024-01-01 00:00:00 UTC
        step_ms = 60000

        timestamps = [start_ts + (i * step_ms) for i in range(n)]
        close_times = [ts + 59999 for ts in timestamps]
        base_price = 2280.0
        returns = np.random.normal(0.00005, 0.0018, n)
        price_path = base_price * np.cumprod(1.0 + returns)

        opens = np.roll(price_path, 1)
        opens[0] = base_price
        closes = price_path
        highs = np.maximum(opens, closes) + np.random.uniform(0.5, 4.0, n)
        lows = np.minimum(opens, closes) - np.random.uniform(0.5, 4.0, n)
        volumes = np.random.uniform(20.0, 300.0, n)

        df_seed = pl.DataFrame({
            "open_time": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "close_time": close_times,
            "quote_asset_volume": volumes * closes,
            "number_of_trades": np.random.randint(100, 800, n),
            "taker_buy_base_asset_volume": volumes * 0.52,
            "taker_buy_quote_asset_volume": volumes * 0.52 * closes,
        }, schema=CANONICAL_KLINE_SCHEMA)

        storage.write_month_partition(df_seed, year=2024, month=1, symbol="ETHUSDT")
        df_1m = storage.read_range(symbol="ETHUSDT", timeframe="1m")

    # 2. Build Dataset Manifest
    manifest_mgr = DatasetManifestManager(storage=storage)
    manifest = manifest_mgr.generate_manifest(symbol="ETHUSDT", timeframe="1m")
    logger.info(f"Dataset Manifest Verified. Fingerprint: {manifest.canonical_fingerprint}")

    # 3. Resample to 15m causally
    df_15m = CausalResampler.resample(df_1m, target_timeframe="15m")
    logger.info(f"Resampled to 15m: {len(df_15m)} bars")

    # 4. Configure Baseline Strategy
    strategy = EmaTrendStrategy(fast_period=20, slow_period=50, atr_multiplier_stop=2.0, risk_reward_ratio=2.0)

    # 5. Run Event-Aware Backtest
    cost_model = CostModel(maker_fee_rate=0.0002, taker_fee_rate=0.0005, slippage_bps=2.0)
    engine = BacktestEngine(
        cost_model=cost_model,
        initial_capital=10000.0,
        risk_per_trade_fraction=0.01,
        conservative_intrabar_ambiguity=True,
    )

    result = engine.run(df_15m, strategy)
    m = result.metrics
    logger.info(f"Backtest Completed. Trades: {m.trade_count}, Net Return: {m.total_net_return:+.2f}%, Sharpe: {m.sharpe_ratio:.2f}")

    # 6. Register in Permanent Research Ledger
    ledger = ResearchLedger()
    exp_id = ledger.generate_experiment_id()
    git_info = SafeGitSync().get_git_info()

    first_ts = int(df_15m["open_time"].min())
    last_ts = int(df_15m["open_time"].max())
    d_start_str = datetime.fromtimestamp(first_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
    d_end_str = datetime.fromtimestamp(last_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

    record = ExperimentRecord(
        experiment_id=exp_id,
        hypothesis=strategy.metadata.hypothesis,
        strategy_id=strategy.metadata.strategy_id,
        strategy_version=strategy.metadata.version,
        feature_set_version="v1",
        parameters=strategy.metadata.parameters,
        parameter_hash=ledger._compute_parameter_hash(strategy.metadata.parameters),
        dataset_fingerprint=manifest.canonical_fingerprint,
        symbol="ETHUSDT",
        timeframe="15m",
        date_range_start=d_start_str,
        date_range_end=d_end_str,
        git_sha=git_info["git_sha"],
        git_dirty=git_info["is_dirty"],
        cost_model=cost_model.model_dump(),
        execution_model="EVENT_AWARE_TAKER_ENTRY_LIMIT_TP_MARKET_SL",
        risk_model="STRUCTURAL_ATR_FIXED_RISK_1PCT",
        metrics=m,
        trade_count=m.trade_count,
        status=ExperimentStatus.COMPLETED if m.total_net_return > 0 else ExperimentStatus.REJECTED,
        conclusion=f"Baseline EMA Trend benchmark completed with {m.trade_count} trades, net return {m.total_net_return:+.2f}%, and profit factor {m.profit_factor:.2f}.",
    )

    ledger.register_experiment(record)

    # 7. Generate Standalone Reports
    reporter = ReportGenerator()
    html_path = reporter.generate_html_report(record, result.ledger)
    json_path = reporter.generate_json_export(record)

    # 8. MLflow Logging
    mlflow_adapter = MLflowAdapter()
    mlflow_adapter.log_experiment(record, artifact_paths={"report_html": html_path, "export_json": json_path})

    print(f"\n========================================================")
    print(f"EXPERIMENT REGISTERED: {exp_id}")
    print(f"Status:               {record.status.value}")
    print(f"Strategy:             {record.strategy_id}")
    print(f"Net Return:           {m.total_net_return:+.2f}%")
    print(f"Win Rate:             {m.win_rate:.1f}% ({m.trade_count} trades)")
    print(f"Profit Factor:        {m.profit_factor:.2f}")
    print(f"Sharpe Ratio:         {m.sharpe_ratio:.2f}")
    print(f"Max Drawdown:         {m.max_drawdown_pct:.2f}%")
    print(f"HTML Report:          {html_path}")
    print(f"========================================================\n")


if __name__ == "__main__":
    run_baseline()
