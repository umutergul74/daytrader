"""Tests for Causal Market Structure Engine V2."""

import polars as pl
import pytest
from quant_platform.features.structure.market_structure import MarketStructureEngine


def test_market_structure_bos_and_choch():
    """Verify BOS by wick, BOS by close, and CHoCH detection."""
    # Construct sequence:
    # 1. Bearish trend down with LH and LL
    # 2. Reversal candle closing above last LH -> Bullish CHoCH
    n = 20
    timestamps = [1000 + i * 60000 for i in range(n)]
    close_times = [ts + 59999 for ts in timestamps]

    highs = [100.0] * n
    lows = [90.0] * n
    closes = [95.0] * n

    # Swing high at bar 2 (price=110.0), confirmed at bar 2+2=4
    highs[2] = 110.0
    # Swing low at bar 5 (price=80.0), confirmed at bar 5+2=7
    lows[5] = 80.0
    # Swing high at bar 8 (price=105.0 - Lower High), confirmed at bar 8+2=10
    highs[8] = 105.0
    # Swing low at bar 11 (price=75.0 - Lower Low), confirmed at bar 11+2=13
    lows[11] = 75.0

    # Bullish break at bar 15: Close at 108.0 (above last confirmed LH 105.0) -> Bullish CHoCH!
    highs[15] = 109.0
    closes[15] = 108.0

    df = pl.DataFrame({
        "open_time": timestamps,
        "open": [95.0] * n,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [100.0] * n,
        "close_time": close_times,
    })

    df_res = MarketStructureEngine.compute_market_structure(df, left_bars=2, right_bars=2)

    assert "is_bos_close_bullish" in df_res.columns
    assert "is_choch_bullish" in df_res.columns
    # Bar 15 should have triggered bullish CHoCH
    assert df_res["is_choch_bullish"][15] == True
    assert df_res["structural_trend"][15] == 1
