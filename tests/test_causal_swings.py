"""Tests for Causal Swing Engine and confirmation delay."""

import numpy as np
import polars as pl
from quant_platform.features.structure.swings import CausalSwingEngine


def test_causal_swing_high_confirmation_delay():
    """Verify that a swing high at bar i is confirmed strictly at bar i + R."""
    n = 20
    # Construct prices: rising from 0 to 10, peak at 10 (price=2500), then falling from 10 to 15
    highs = np.zeros(n, dtype=np.float64)
    lows = np.zeros(n, dtype=np.float64)

    for i in range(n):
        if i < 10:
            highs[i] = 2000.0 + (i * 10)
        elif i == 10:
            highs[i] = 2500.0  # Sharp distinct peak at index 10
        else:
            highs[i] = 2500.0 - ((i - 10) * 10)
        lows[i] = highs[i] - 5.0

    df = pl.DataFrame({
        "open_time": [1000 * i for i in range(n)],
        "open": highs - 2.0,
        "high": highs,
        "low": lows,
        "close": highs - 1.0,
        "volume": [100.0] * n,
    })

    # Detect swings with Left=3, Right=3
    L, R = 3, 3
    df_swings = CausalSwingEngine.detect_swings(df, left_bars=L, right_bars=R)

    is_sh_confirmed = df_swings[f"is_swing_high_confirmed_L{L}_R{R}"].to_list()
    conf_price = df_swings[f"confirmed_swing_high_price_L{L}_R{R}"].to_list()
    last_sh = df_swings[f"last_swing_high_L{L}_R{R}"].to_list()

    # At bar index 10, 11, 12, the swing high is NOT yet confirmed (future bars required)
    assert is_sh_confirmed[10] is False
    assert is_sh_confirmed[11] is False
    assert is_sh_confirmed[12] is False

    # At bar index 13 (10 + R = 13), confirmation occurs!
    assert is_sh_confirmed[13] is True
    assert conf_price[13] == 2500.0

    # From bar 13 onwards, last_swing_high is forward filled with 2500.0
    for idx in range(13, n):
        assert last_sh[idx] == 2500.0
