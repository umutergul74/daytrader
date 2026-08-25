"""Tests for Liquidity Levels, Sweeps, and Session Level Causality."""

import polars as pl
import pytest
from quant_platform.features.smc.liquidity import LiquidityEngine


def test_equal_highs_and_lows_detection():
    """Verify EQH detection when two confirmed swing highs are within tolerance."""
    # Synthetic series where bar 3 and bar 11 form equal peaks at price ~110.0
    n = 25
    timestamps = [1000 + i * 60000 for i in range(n)]
    close_times = [ts + 59999 for ts in timestamps]
    highs = [100.0] * n
    highs[3] = 110.0
    highs[11] = 110.1 # Within small ATR tolerance

    lows = [90.0] * n
    opens = [95.0] * n
    closes = [96.0] * n
    volumes = [100.0] * n

    df = pl.DataFrame({
        "open_time": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "close_time": close_times,
    })

    df_res = LiquidityEngine.detect_equal_highs_lows(df, left_bars=2, right_bars=2, tolerance_atr=0.5)
    assert "is_eqh" in df_res.columns
    # EQH should be flagged at the confirmation bar of the second swing (bar 11 + 2 = 13)
    assert df_res["is_eqh"].sum() >= 1


def test_previous_day_levels_causality():
    """Verify PDH/PDL are strictly from the previous day with zero intraday leakage."""
    # Two full days of data (day 0 and day 1)
    day_ms = 86400000
    times = []
    highs = []
    lows = []
    opens = []
    closes = []
    volumes = []

    # Day 0: Max High = 150.0, Min Low = 90.0
    for i in range(24):
        times.append(i * 3600000)
        highs.append(150.0 if i == 12 else 100.0)
        lows.append(90.0 if i == 6 else 95.0)
        opens.append(98.0)
        closes.append(98.0)
        volumes.append(100.0)

    # Day 1: Max High = 200.0, Min Low = 110.0
    for i in range(24):
        times.append(day_ms + i * 3600000)
        highs.append(200.0 if i == 12 else 120.0)
        lows.append(110.0 if i == 6 else 115.0)
        opens.append(118.0)
        closes.append(118.0)
        volumes.append(100.0)

    df = pl.DataFrame({
        "open_time": times,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "close_time": [t + 3599999 for t in times],
    })

    df_res = LiquidityEngine.compute_previous_day_week_levels(df)

    # In Day 1 (indices 24..47), PDH must be exactly 150.0 (Day 0 high) and PDL must be 90.0
    day1_pdh = df_res["pdh"][25]
    day1_pdl = df_res["pdl"][25]
    assert day1_pdh == 150.0
    assert day1_pdl == 90.0
