"""CLI Commands for Phase 5 Machine Learning Meta-Labeling."""

import typer
from rich.console import Console
from rich.table import Table
import numpy as np
import polars as pl

from quant_platform.data.storage.canonical import CanonicalStorage
from quant_platform.data.timeframes.resampler import CausalResampler
from quant_platform.features.indicators.momentum import compute_rsi
from quant_platform.features.indicators.volatility import compute_atr
from quant_platform.features.microstructure.cvd import CvdEngine
from quant_platform.strategies.baselines.breakout import BreakoutSanityStrategy
from quant_platform.ml.meta_labeling import MetaLabelingEngine
from quant_platform.ml.meta_classifier import MetaClassifierTrainer

app = typer.Typer(help="Machine Learning Meta-Labeling training and calibration.")
console = Console()


@app.command(name="train")
def train_meta_model(symbol: str = "ETHUSDT", model_type: str = "gradient_boosting"):
    """Train and calibrate a secondary tabular ML Meta-Labeling classifier."""
    storage = CanonicalStorage()
    df_1m = storage.read_symbol(symbol=symbol, start_year=2024, start_month=1)
    if df_1m.is_empty():
        console.print(f"[bold red]No canonical data found for {symbol}.[/bold red]")
        raise typer.Exit(1)

    # 1. Resample to 15m and generate indicators
    df_15m = CausalResampler.resample(df_1m.head(5000), target_timeframe="15m")
    df_15m = compute_atr(df_15m, period=14)
    df_15m = compute_rsi(df_15m, period=14)
    df_15m = CvdEngine.compute_kline_delta_features(df_15m)

    # 2. Generate Primary Strategy Candidates
    strat = BreakoutSanityStrategy(lookback_period=5, risk_reward_ratio=2.0)
    candidates = strat.generate_signals(df_15m)

    if len(candidates) < 4:
        console.print(f"[yellow]Insufficient primary candidates ({len(candidates)}) generated for ML training.[/yellow]")
        raise typer.Exit(0)

    # 3. Triple-Barrier Labeling
    dataset = MetaLabelingEngine.compute_triple_barrier_labels(df_15m, candidates, max_holding_bars=20)
    if len(dataset.y) < 4:
        console.print(f"[yellow]Insufficient labeled samples ({len(dataset.y)}) generated.[/yellow]")
        raise typer.Exit(0)

    X_train, y_train, X_test, y_test = MetaLabelingEngine.purged_walk_forward_split(dataset, train_ratio=0.70)

    # 4. Train and Calibrate Model
    trainer = MetaClassifierTrainer(model_type=model_type)
    metrics = trainer.train_and_calibrate(X_train, y_train, X_test, y_test, feature_names=dataset.feature_names)

    # 5. Display Results
    table = Table(title=f"Meta-Model Performance Metrics ({model_type})")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    table.add_row("Train Samples", str(metrics.train_samples))
    table.add_row("Test Samples (OOS)", str(metrics.test_samples))
    table.add_row("ROC-AUC", f"{metrics.roc_auc:.3f}")
    table.add_row("Brier Score", f"{metrics.brier_score:.4f}")
    table.add_row("Precision", f"{metrics.precision:.2%}")
    table.add_row("Recall", f"{metrics.recall:.2%}")
    table.add_row("Calibrated", str(metrics.is_calibrated))

    console.print(table)

    if metrics.feature_importances:
        feat_table = Table(title="Meta-Model Feature Importances")
        feat_table.add_column("Feature", style="cyan")
        feat_table.add_column("Importance", justify="right", style="green")
        for fname, imp in sorted(metrics.feature_importances.items(), key=lambda x: x[1], reverse=True):
            feat_table.add_row(fname, f"{imp:.4f}")
        console.print(feat_table)
