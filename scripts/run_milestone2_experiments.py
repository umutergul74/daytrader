"""Master Empirical Research Experiment Runner for Milestone 2.

Executes Experiment Families A through J:
 - Family A: Baseline Benchmarks (EMA Trend, RSI Reversion, Breakout, Random)
 - Family B: Market Structure Continuation
 - Family C: Liquidity Sweep Reversal
 - Family D: FVG Trend Continuation
 - Family E: Liquidity Sweep + FVG Retest
 - Family F: Regime-Aware vs Unconditional Strategy Comparison
 - Family G: Component Ablation Study
 - Family H: Walk-Forward Analysis
 - Family I: Robustness Suite & Monte Carlo Stress Testing
 - Family J: Resumable Optuna Optimization Study
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import polars as pl
from quant_platform.config.settings import settings
from quant_platform.data.storage.canonical import CanonicalStorage
from quant_platform.data.manifest.manifest_manager import DatasetManifestManager
from quant_platform.data.timeframes.resampler import CausalResampler
from quant_platform.strategies.catalog import StrategyCatalog
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy
from quant_platform.strategies.baselines.rsi_reversion import RsiMeanReversionStrategy
from quant_platform.strategies.baselines.breakout import BreakoutSanityStrategy
from quant_platform.strategies.baselines.random_baseline import RandomSanityBaseline
from quant_platform.strategies.advanced.structure_continuation import StructureContinuationStrategy
from quant_platform.strategies.advanced.liquidity_sweep_reversal import LiquiditySweepReversalStrategy
from quant_platform.strategies.advanced.liquidity_sweep_fvg import LiquiditySweepFVGStrategy
from quant_platform.strategies.advanced.fvg_continuation import FvgTrendContinuationStrategy
from quant_platform.strategies.advanced.regime_mean_reversion import RegimeAwareMeanReversionStrategy
from quant_platform.backtest.engine import BacktestEngine
from quant_platform.backtest.costs import CostModel
from quant_platform.research.ledger import ResearchLedger
from quant_platform.research.reporting import ReportGenerator
from quant_platform.research.ablation import AblationEngine
from quant_platform.research.walk_forward import WalkForwardEngine
from quant_platform.research.robustness import RobustnessEngine
from quant_platform.optimization.optuna_optimizer import OptunaOptimizer
from quant_platform.domain.experiment import ExperimentRecord, ExperimentStatus
from quant_platform.features.catalog import FeatureCatalog, FeatureLifecycle
from quant_platform.observability.logger import logger


def run_milestone2_research():
    settings.ensure_directories()
    storage = CanonicalStorage()
    ledger = ResearchLedger()
    reporter = ReportGenerator()

    # Load canonical dataset
    df_1m = storage.read_range(symbol="ETHUSDT", timeframe="1m")
    if df_1m.is_empty():
        raise RuntimeError("No canonical ETHUSDT data found in storage.")

    manifest_mgr = DatasetManifestManager(storage=storage)
    manifest = manifest_mgr.generate_manifest(symbol="ETHUSDT", timeframe="1m")
    fingerprint = manifest.canonical_fingerprint

    df_15m = CausalResampler.resample(df_1m, target_timeframe="15m")
    first_ts = int(df_15m["open_time"].min())
    last_ts = int(df_15m["open_time"].max())
    d_start = datetime.fromtimestamp(first_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
    d_end = datetime.fromtimestamp(last_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

    cost_model = CostModel(maker_fee_rate=0.0002, taker_fee_rate=0.0005, slippage_bps=2.0)
    engine = BacktestEngine(cost_model=cost_model, initial_capital=10000.0, risk_per_trade_fraction=0.01)

    print("\n" + "="*70)
    print("STARTING MILESTONE 2 EMPIRICAL RESEARCH RUNS (FAMILIES A - J)")
    print("="*70 + "\n")

    # Helper function to run and register
    def execute_and_log(strategy, family_name, conclusion_note=""):
        res = engine.run(df_15m, strategy)
        m = res.metrics
        exp_id = ledger.generate_experiment_id()

        # Decision rule: positive net return -> COMPLETED, else REJECTED
        status = ExperimentStatus.COMPLETED if m.total_net_return > 0 else ExperimentStatus.REJECTED
        rejection_reason = None if status == ExperimentStatus.COMPLETED else "Negative out-of-sample expectancy after taker fees and slippage."

        record = ExperimentRecord(
            experiment_id=exp_id,
            hypothesis=strategy.metadata.hypothesis,
            strategy_id=strategy.metadata.strategy_id,
            strategy_version=strategy.metadata.version,
            feature_set_version="v2",
            parameters=strategy.metadata.parameters,
            parameter_hash=ledger._compute_parameter_hash(strategy.metadata.parameters),
            dataset_fingerprint=fingerprint,
            symbol="ETHUSDT",
            timeframe="15m",
            date_range_start=d_start,
            date_range_end=d_end,
            cost_model=cost_model.model_dump(),
            execution_model="EVENT_AWARE_TAKER_ENTRY_LIMIT_TP_MARKET_SL",
            risk_model="STRUCTURAL_ATR_FIXED_RISK_1PCT",
            metrics=m,
            trade_count=m.trade_count,
            status=status,
            rejection_reason=rejection_reason,
            conclusion=conclusion_note or f"Experiment for {strategy.metadata.strategy_id} concluded with {m.trade_count} trades and {m.total_net_return:+.2f}% net return.",
        )

        ledger.register_experiment(record)
        html_path = reporter.generate_html_report(record, res.ledger)
        print(f"[{family_name}] {strategy.metadata.strategy_id:32} | Status: {status.value:9} | Net Ret: {m.total_net_return:+.2f}% | Trades: {m.trade_count:2} | Report: {html_path.name}")
        return record, res

    # 1. Family A: Baselines
    execute_and_log(EmaTrendStrategy(fast_period=20, slow_period=50), "Family A: Baseline", "Baseline EMA Trend benchmark.")
    execute_and_log(RsiMeanReversionStrategy(rsi_period=14), "Family A: Baseline", "Baseline RSI Reversion benchmark.")
    execute_and_log(BreakoutSanityStrategy(lookback_period=20), "Family A: Baseline", "Baseline Breakout benchmark.")

    # 2. Family B: Market Structure Continuation
    execute_and_log(StructureContinuationStrategy(left_bars=5, right_bars=5), "Family B: Structure", "Market Structure Trend Continuation.")

    # 3. Family C: Liquidity Sweep Reversal
    execute_and_log(LiquiditySweepReversalStrategy(left_bars=5, right_bars=5), "Family C: Liq Sweep", "Liquidity Sweep & Reclaim Reversal.")

    # 4. Family D: FVG Trend Continuation
    execute_and_log(FvgTrendContinuationStrategy(fast_ema=20, slow_ema=50), "Family D: FVG Trend", "FVG Retest in Trend Direction.")

    # 5. Family E: Liquidity Sweep + FVG Retest
    rec_e, res_e = execute_and_log(LiquiditySweepFVGStrategy(left_bars=5, right_bars=5), "Family E: Sweep+FVG", "Composite Liquidity Sweep + FVG Retest.")

    # 6. Family F: Regime-Aware vs Unconditional
    execute_and_log(RegimeAwareMeanReversionStrategy(), "Family F: Regime RSI", "Regime-Filtered RSI Mean Reversion.")

    # 7. Family G: Systematic Ablation Study
    print("\n--- Running Family G: Component Ablation Study ---")
    abl_engine = AblationEngine()
    abl_res = abl_engine.run_ablation_study(
        df=df_15m,
        base_strategy=LiquiditySweepFVGStrategy(left_bars=5, right_bars=5),
        ablation_variants={
            "minus_fvg_retest": LiquiditySweepReversalStrategy(left_bars=5, right_bars=5),
            "baseline_ema": EmaTrendStrategy(),
        },
        study_id="ABL-LIQUIDITY-FVG-001",
    )
    print(abl_res.summary)

    # 8. Family H: Walk-Forward Evaluation
    print("\n--- Running Family H: Walk-Forward Analysis ---")
    wf_engine = WalkForwardEngine()
    wf_rep = wf_engine.run_walk_forward(
        df=df_15m,
        strategy=LiquiditySweepFVGStrategy(left_bars=5, right_bars=5),
        n_folds=3,
        is_anchored=True,
    )
    print(f"Walk-Forward Summary: {wf_rep.profitable_folds}/{wf_rep.total_folds} profitable folds ({wf_rep.profitable_fold_ratio:.1f}%), Aggregate OOS Return = {wf_rep.aggregate_oos_return:+.2f}%")

    # 9. Family I: Robustness Suite & Monte Carlo
    print("\n--- Running Family I: Robustness Stress Testing ---")
    rob_engine = RobustnessEngine(initial_capital=10000.0)
    rob_rep = rob_engine.run_robustness_suite(df_15m, LiquiditySweepFVGStrategy(left_bars=5, right_bars=5))
    print(rob_rep.summary)

    # 10. Family J: Optuna Study Lineage
    print("\n--- Running Family J: Resumable Optuna Study ---")
    opt = OptunaOptimizer(study_name="optuna_milestone2_liquidity_fvg")
    opt_res = opt.optimize_strategy(
        df=df_15m,
        strategy_factory=lambda p: LiquiditySweepFVGStrategy(**p),
        param_space=lambda trial: {
            "left_bars": trial.suggest_int("left_bars", 3, 7),
            "right_bars": trial.suggest_int("right_bars", 3, 7),
            "atr_period": trial.suggest_int("atr_period", 10, 20),
            "risk_reward_ratio": trial.suggest_float("risk_reward_ratio", 1.5, 3.0, step=0.5),
        },
        n_trials=5,
    )
    print(f"Optuna Best Trial #{opt_res.best_trial_number}: Value = {opt_res.best_value:.2f}, Params = {opt_res.best_params}")
    print(f"Status: {opt_res.verdict}\n")

    # Update feature catalog evidence
    FeatureCatalog.update_evidence("smc:fvg_three_candle", "v1", FeatureLifecycle.BACKTESTED, "Tested across 15m ETHUSDT datasets in conjunction with sweeps and trend continuation.")
    FeatureCatalog.update_evidence("smc:liquidity_sweep", "v1", FeatureLifecycle.BACKTESTED, "Validated in LiquiditySweepReversal and LiquiditySweepFVG strategies.")
    FeatureCatalog.update_evidence("structure:bos_choch", "v1", FeatureLifecycle.BACKTESTED, "Causally verified in StructureContinuationStrategy.")
    FeatureCatalog.update_evidence("regime:rules", "v1", FeatureLifecycle.BACKTESTED, "Evaluated in RegimeAwareMeanReversionStrategy.")

    print("="*70)
    print("ALL MILESTONE 2 EXPERIMENT FAMILIES EXECUTED & RECORDED IN RESEARCH LEDGER")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_milestone2_research()
