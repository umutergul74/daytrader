"""Tests for Causal Market Regime Classification."""

import polars as pl
import pytest
from quant_platform.regimes.engine import MarketRegimeEngine


def test_market_regime_classification(synthetic_1m_data: pl.DataFrame):
    """Verify that regime classification produces valid non-null outputs."""
    df_reg = MarketRegimeEngine.classify_regimes(synthetic_1m_data, adx_period=14, vol_lookback=50)

    assert "regime_direction" in df_reg.columns
    assert "regime_state" in df_reg.columns
    assert "regime_volatility" in df_reg.columns
    assert "regime_tag" in df_reg.columns

    # Verify enum values
    valid_dirs = {"BULLISH", "BEARISH", "NEUTRAL"}
    valid_states = {"TRENDING", "RANGING", "COMPRESSION", "EXPANSION", "BREAKOUT"}
    valid_vols = {"VERY_LOW", "LOW", "NORMAL", "HIGH", "EXTREME"}

    for row in df_reg.iter_rows(named=True):
        assert row["regime_direction"] in valid_dirs
        assert row["regime_state"] in valid_states
        assert row["regime_volatility"] in valid_vols
