"""Causal Swing High / Swing Low Detection Engine.

Detects fractal pivot highs and lows with strict information-availability delay.
A pivot at bar i with confirmation lookahead R is only recorded as available at bar i + R.
"""

from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field
import numpy as np
import polars as pl


class SwingPoint(BaseModel):
    bar_index: int
    open_time: int
    price: float
    is_high: bool
    confirmation_bar_index: int
    confirmation_time: int


class CausalSwingEngine:
    """Detects swing highs and lows causally with confirmation delay."""

    @staticmethod
    def detect_swings(
        df: pl.DataFrame,
        left_bars: int = 5,
        right_bars: int = 5,
    ) -> pl.DataFrame:
        """Add strictly causal swing columns to DataFrame.

        Columns added:
        - is_swing_high_confirmed: bool (True at bar i + right_bars if bar i was a swing high)
        - is_swing_low_confirmed: bool (True at bar i + right_bars if bar i was a swing low)
        - confirmed_swing_high_price: float (Price of the pivot high confirmed at this bar)
        - confirmed_swing_low_price: float (Price of the pivot low confirmed at this bar)
        - last_swing_high_price: float (Forward-filled most recent confirmed swing high)
        - last_swing_low_price: float (Forward-filled most recent confirmed swing low)
        """
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        open_times = df["open_time"].to_numpy()
        n = len(df)

        is_sh_confirmed = np.zeros(n, dtype=bool)
        is_sl_confirmed = np.zeros(n, dtype=bool)
        sh_price = np.full(n, np.nan, dtype=np.float64)
        sl_price = np.full(n, np.nan, dtype=np.float64)
        last_sh = np.full(n, np.nan, dtype=np.float64)
        last_sl = np.full(n, np.nan, dtype=np.float64)

        current_sh = np.nan
        current_sl = np.nan

        # We can test pivots from left_bars to n - right_bars - 1
        for i in range(left_bars, n - right_bars):
            # Check swing high at index i
            pivot_h = highs[i]
            is_highest = True
            for k in range(1, left_bars + 1):
                if highs[i - k] >= pivot_h:
                    is_highest = False
                    break
            if is_highest:
                for k in range(1, right_bars + 1):
                    if highs[i + k] >= pivot_h:
                        is_highest = False
                        break

            # Check swing low at index i
            pivot_l = lows[i]
            is_lowest = True
            for k in range(1, left_bars + 1):
                if lows[i - k] <= pivot_l:
                    is_lowest = False
                    break
            if is_lowest:
                for k in range(1, right_bars + 1):
                    if lows[i + k] <= pivot_l:
                        is_lowest = False
                        break

            # The swing at bar i is confirmed at bar i + right_bars
            conf_idx = i + right_bars
            if is_highest:
                is_sh_confirmed[conf_idx] = True
                sh_price[conf_idx] = pivot_h
                current_sh = pivot_h

            if is_lowest:
                is_sl_confirmed[conf_idx] = True
                sl_price[conf_idx] = pivot_l
                current_sl = pivot_l

        # Forward fill the last confirmed values
        cur_h = np.nan
        cur_l = np.nan
        for t in range(n):
            if is_sh_confirmed[t]:
                cur_h = sh_price[t]
            if is_sl_confirmed[t]:
                cur_l = sl_price[t]
            last_sh[t] = cur_h
            last_sl[t] = cur_l

        return df.with_columns([
            pl.Series(name=f"is_swing_high_confirmed_L{left_bars}_R{right_bars}", values=is_sh_confirmed),
            pl.Series(name=f"is_swing_low_confirmed_L{left_bars}_R{right_bars}", values=is_sl_confirmed),
            pl.Series(name=f"confirmed_swing_high_price_L{left_bars}_R{right_bars}", values=sh_price),
            pl.Series(name=f"confirmed_swing_low_price_L{left_bars}_R{right_bars}", values=sl_price),
            pl.Series(name=f"last_swing_high_L{left_bars}_R{right_bars}", values=last_sh),
            pl.Series(name=f"last_swing_low_L{left_bars}_R{right_bars}", values=last_sl),
        ])
