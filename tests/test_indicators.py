"""Tests for technical indicators."""

import polars as pl
import numpy as np
from quant_platform.features import (
    compute_sma,
    compute_ema,
    compute_rsi,
    compute_macd,
    compute_atr,
    compute_bollinger_bands,
)


def test_moving_averages_and_indicators(synthetic_1m_data: pl.DataFrame):
    """Verify indicators compute valid numerical series without NaNs in steady state."""
    df = compute_sma(synthetic_1m_data, period=20, output_col="sma_20")
    df = compute_ema(df, period=20, output_col="ema_20")
    df = compute_rsi(df, period=14, output_col="rsi_14")
    df = compute_macd(df, fast_period=12, slow_period=26, signal_period=9)
    df = compute_atr(df, period=14, output_col="atr_14")
    df = compute_bollinger_bands(df, period=20)

    # Check that after warm-up period (e.g. 50 bars), no NaNs exist
    steady_state = df.slice(50)

    assert "sma_20" in df.columns
    assert "ema_20" in df.columns
    assert "rsi_14" in df.columns
    assert "macd_12_26" in df.columns
    assert "atr_14" in df.columns
    assert "bb_upper_20" in df.columns

    # RSI bounded in [0, 100]
    rsi_vals = steady_state["rsi_14"].to_numpy()
    assert np.all((rsi_vals >= 0.0) & (rsi_vals <= 100.0))

    # ATR strictly positive
    atr_vals = steady_state["atr_14"].to_numpy()
    assert np.all(atr_vals > 0.0)

    # Bollinger Bands upper >= mid >= lower
    bb_u = steady_state["bb_upper_20"].to_numpy()
    bb_m = steady_state["bb_mid_20"].to_numpy()
    bb_l = steady_state["bb_lower_20"].to_numpy()
    assert np.all(bb_u >= bb_m)
    assert np.all(bb_m >= bb_l)
