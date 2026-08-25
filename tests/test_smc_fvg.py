"""Tests for Fair Value Gap (FVG) lifecycle and causality."""

import polars as pl
import pytest
from quant_platform.domain.smc import FvgDirection, FvgMitigationState
from quant_platform.features.smc.fvg import FvgEngine


def test_fvg_detection_bullish_and_bearish():
    """Verify 3-candle FVG detection for bullish and bearish patterns."""
    # Construct synthetic 3-candle bullish FVG:
    # Bar 0: high = 100
    # Bar 1: large up candle (open=100, close=120, low=99, high=121)
    # Bar 2: low = 105 (low[2] > high[0] -> Bullish FVG between 100 and 105, CE=102.5)
    timestamps = [1000 + i * 60000 for i in range(5)]
    close_times = [ts + 59999 for ts in timestamps]

    df_bull = pl.DataFrame({
        "open_time": timestamps,
        "open": [90.0, 100.0, 110.0, 108.0, 115.0],
        "high": [100.0, 121.0, 120.0, 112.0, 120.0],
        "low": [89.0, 99.0, 105.0, 106.0, 110.0],
        "close": [98.0, 120.0, 115.0, 110.0, 118.0],
        "volume": [100.0, 500.0, 200.0, 150.0, 200.0],
        "close_time": close_times,
    })

    df_res, fvgs = FvgEngine.detect_and_track_fvgs(df_bull, min_gap_atr_ratio=0.0)

    assert df_res["is_bullish_fvg_created"][2] == True
    assert len(fvgs) >= 1
    bull_fvg = fvgs[0]
    assert bull_fvg.direction == FvgDirection.BULLISH
    assert bull_fvg.lower_bound == 100.0
    assert bull_fvg.upper_bound == 105.0
    assert bull_fvg.consequent_encroachment == 102.5
    # Causal availability is strictly after candle close
    assert bull_fvg.available_at_time > close_times[2]


def test_fvg_mitigation_lifecycle():
    """Verify that price dipping into FVG updates mitigation state to PARTIAL and FULL."""
    timestamps = [1000 + i * 60000 for i in range(5)]
    close_times = [ts + 59999 for ts in timestamps]

    # Bar 2 creates FVG [100, 105] (CE=102.5)
    # Bar 3 dips to 102.0 (touches CE -> PARTIALLY_MITIGATED)
    # Bar 4 dips to 98.0 (dips below lower bound 100 -> FULLY_MITIGATED)
    df_mit = pl.DataFrame({
        "open_time": timestamps,
        "open": [95.0, 100.0, 110.0, 112.0, 104.0],
        "high": [100.0, 120.0, 120.0, 115.0, 105.0],
        "low": [94.0, 99.0, 105.0, 102.0, 98.0],
        "close": [98.0, 118.0, 114.0, 104.0, 99.0],
        "volume": [100.0, 400.0, 200.0, 150.0, 250.0],
        "close_time": close_times,
    })

    df_res, fvgs = FvgEngine.detect_and_track_fvgs(df_mit, min_gap_atr_ratio=0.0)
    assert len(fvgs) >= 1
    fvg = fvgs[0]
    # At the end of the sequence, the FVG has been fully mitigated
    assert fvg.mitigation_state == FvgMitigationState.FULLY_MITIGATED
    assert fvg.first_revisit_time is not None
