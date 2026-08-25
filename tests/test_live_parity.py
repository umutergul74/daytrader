"""Tests for Backtest / Live Parity Validation Engine."""

import polars as pl
import pytest
from quant_platform.live.parity import ParityEngine


def test_backtest_live_parity_100_percent(synthetic_1m_data: pl.DataFrame):
    """Verify that batch calculation and incremental streaming produce identical features."""
    df_slice = synthetic_1m_data.tail(300)
    report = ParityEngine.verify_parity(df_slice, symbol="ETHUSDT", tolerance=1e-4)

    assert report.total_1m_bars_processed == len(df_slice)
    assert len(report.checks) > 0
    # Every verified feature must have 100% parity
    for c in report.checks:
        assert c.is_parity_clean is True, f"Parity mismatch in {c.feature_name}: {c.mismatches} mismatches (max delta: {c.max_absolute_delta})"

    assert report.is_full_parity_achieved is True
    assert report.overall_parity_pct == 100.0
