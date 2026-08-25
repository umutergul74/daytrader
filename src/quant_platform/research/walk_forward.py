"""Anchored and Rolling Walk-Forward Analysis Engine."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import polars as pl

from quant_platform.strategies.base import BaseStrategy
from quant_platform.backtest.engine import BacktestEngine, BacktestResult
from quant_platform.domain.experiment import QuantMetrics
from quant_platform.observability.logger import logger


class WalkForwardFold(BaseModel):
    """Result of a single walk-forward fold."""
    fold_index: int
    train_bars: int
    test_bars: int
    train_start_ts: int
    train_end_ts: int
    test_start_ts: int
    test_end_ts: int
    test_metrics: QuantMetrics


class WalkForwardReport(BaseModel):
    """Comprehensive multi-fold walk-forward analysis report."""
    strategy_id: str
    mode: str # "ANCHORED" or "ROLLING"
    total_folds: int
    profitable_folds: int
    profitable_fold_ratio: float
    aggregate_oos_return: float
    worst_fold_drawdown: float
    folds: List[WalkForwardFold]


class WalkForwardEngine:
    """Evaluates strategy performance across expanding or rolling chronological out-of-sample folds."""

    def __init__(self, backtest_engine: Optional[BacktestEngine] = None):
        self.engine = backtest_engine or BacktestEngine()

    def run_walk_forward(
        self,
        df: pl.DataFrame,
        strategy: BaseStrategy,
        n_folds: int = 5,
        train_fraction: float = 0.6,
        is_anchored: bool = True,
    ) -> WalkForwardReport:
        """Run anchored or rolling walk-forward test."""
        total_bars = len(df)
        if total_bars < 100:
            raise ValueError(f"Insufficient bars for walk-forward: {total_bars}")

        fold_size = int(total_bars / n_folds)
        train_window_bars = int(fold_size * train_fraction)
        test_window_bars = fold_size - train_window_bars

        folds: List[WalkForwardFold] = []
        profitable_count = 0
        total_oos_return = 0.0
        worst_dd = 0.0

        for fold_idx in range(n_folds):
            if is_anchored:
                # Anchored: Train starts at bar 0 and expands
                train_start = 0
                train_end = (fold_idx + 1) * fold_size - test_window_bars
            else:
                # Rolling: Fixed window train
                train_start = fold_idx * fold_size
                train_end = train_start + train_window_bars

            test_start = train_end
            test_end = min(total_bars, (fold_idx + 1) * fold_size)

            if test_end <= test_start or test_start >= total_bars:
                break

            df_test = df.slice(test_start, test_end - test_start)
            test_res = self.engine.run(df_test, strategy)
            m = test_res.metrics

            if m.total_net_return > 0:
                profitable_count += 1
            total_oos_return += m.total_net_return
            if m.max_drawdown_pct > worst_dd:
                worst_dd = m.max_drawdown_pct

            fold = WalkForwardFold(
                fold_index=fold_idx + 1,
                train_bars=train_end - train_start,
                test_bars=test_end - test_start,
                train_start_ts=int(df["open_time"][train_start]),
                train_end_ts=int(df["open_time"][train_end - 1]),
                test_start_ts=int(df["open_time"][test_start]),
                test_end_ts=int(df["open_time"][test_end - 1]),
                test_metrics=m,
            )
            folds.append(fold)
            logger.info(f"Fold {fold_idx + 1}/{n_folds}: OOS Trades = {m.trade_count}, Net Return = {m.total_net_return:+.2f}%, MaxDD = {m.max_drawdown_pct:.2f}%")

        valid_folds = len(folds)
        prof_ratio = (profitable_count / valid_folds) * 100.0 if valid_folds > 0 else 0.0

        return WalkForwardReport(
            strategy_id=strategy.metadata.strategy_id,
            mode="ANCHORED" if is_anchored else "ROLLING",
            total_folds=valid_folds,
            profitable_folds=profitable_count,
            profitable_fold_ratio=prof_ratio,
            aggregate_oos_return=total_oos_return,
            worst_fold_drawdown=worst_dd,
            folds=folds,
        )
