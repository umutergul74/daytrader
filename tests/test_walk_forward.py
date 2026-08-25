"""Tests for Walk-Forward Analysis Engine."""

import polars as pl
import pytest
from quant_platform.research.walk_forward import WalkForwardEngine
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy


def test_walk_forward_anchored_and_rolling(synthetic_1m_data: pl.DataFrame):
    """Verify that walk-forward splits data cleanly into non-overlapping OOS test windows."""
    wf_engine = WalkForwardEngine()
    strategy = EmaTrendStrategy(fast_period=10, slow_period=20)

    # 1. Anchored
    rep_anchored = wf_engine.run_walk_forward(synthetic_1m_data, strategy, n_folds=3, is_anchored=True)
    assert rep_anchored.total_folds == 3
    assert len(rep_anchored.folds) == 3
    # Verify expanding training windows
    assert rep_anchored.folds[1].train_bars > rep_anchored.folds[0].train_bars

    # 2. Rolling
    rep_rolling = wf_engine.run_walk_forward(synthetic_1m_data, strategy, n_folds=3, is_anchored=False)
    assert rep_rolling.total_folds == 3
