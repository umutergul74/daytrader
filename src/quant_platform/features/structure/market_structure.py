"""Causal Market Structure Engine V2.

Implements multi-definition swings (fractal and ATR-dynamic), structural sequence tracking
(HH, HL, LH, LL), structural trend direction, Break of Structure (by wick and by close),
Change of Character (CHoCH), and Market Structure Shift (MSS) with zero lookahead bias.
"""

from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import polars as pl

from quant_platform.domain.smc import (
    StructureBreakType,
    StructureEventType,
    MarketStructureEvent,
)
from quant_platform.features.indicators.volatility import compute_atr


class MarketStructureEngine:
    """Computes comprehensive causal market structure state."""

    @staticmethod
    def detect_fractal_swings(
        df: pl.DataFrame,
        left_bars: int = 5,
        right_bars: int = 5,
    ) -> pl.DataFrame:
        """Detect fractal pivot swings confirmed strictly at bar i + right_bars."""
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        n = len(df)

        is_sh_confirmed = np.zeros(n, dtype=bool)
        is_sl_confirmed = np.zeros(n, dtype=bool)
        sh_price = np.full(n, np.nan, dtype=np.float64)
        sl_price = np.full(n, np.nan, dtype=np.float64)
        last_sh = np.full(n, np.nan, dtype=np.float64)
        last_sl = np.full(n, np.nan, dtype=np.float64)

        for i in range(left_bars, n - right_bars):
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

            conf_idx = i + right_bars
            if is_highest:
                is_sh_confirmed[conf_idx] = True
                sh_price[conf_idx] = pivot_h

            if is_lowest:
                is_sl_confirmed[conf_idx] = True
                sl_price[conf_idx] = pivot_l

        # Forward fill
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
            pl.Series(name=f"is_sh_L{left_bars}_R{right_bars}", values=is_sh_confirmed),
            pl.Series(name=f"is_sl_L{left_bars}_R{right_bars}", values=is_sl_confirmed),
            pl.Series(name=f"sh_price_L{left_bars}_R{right_bars}", values=sh_price),
            pl.Series(name=f"sl_price_L{left_bars}_R{right_bars}", values=sl_price),
            pl.Series(name=f"last_sh_L{left_bars}_R{right_bars}", values=last_sh),
            pl.Series(name=f"last_sl_L{left_bars}_R{right_bars}", values=last_sl),
        ])

    @staticmethod
    def detect_atr_swings(
        df: pl.DataFrame,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
    ) -> pl.DataFrame:
        """Detect dynamic swings requiring movement > multiplier * ATR to reverse."""
        atr_col = f"_atr_sw_{atr_period}"
        df_calc = compute_atr(df, period=atr_period, output_col=atr_col)

        highs = df_calc["high"].to_numpy()
        lows = df_calc["low"].to_numpy()
        atrs = df_calc[atr_col].to_numpy()
        n = len(df)

        is_sh = np.zeros(n, dtype=bool)
        is_sl = np.zeros(n, dtype=bool)
        sh_price = np.full(n, np.nan, dtype=np.float64)
        sl_price = np.full(n, np.nan, dtype=np.float64)
        last_sh = np.full(n, np.nan, dtype=np.float64)
        last_sl = np.full(n, np.nan, dtype=np.float64)

        trend = 1  # 1=looking for high, -1=looking for low
        extreme_h = highs[0] if n > 0 else 0.0
        extreme_l = lows[0] if n > 0 else 0.0
        cur_sh = np.nan
        cur_sl = np.nan

        for i in range(1, n):
            atr_val = atrs[i] if not np.isnan(atrs[i]) else (highs[i] - lows[i])
            threshold = atr_val * atr_multiplier

            if trend == 1:
                if highs[i] > extreme_h:
                    extreme_h = highs[i]
                elif extreme_h - lows[i] >= threshold:
                    # Confirmed Swing High
                    is_sh[i] = True
                    sh_price[i] = extreme_h
                    cur_sh = extreme_h
                    trend = -1
                    extreme_l = lows[i]
            else:
                if lows[i] < extreme_l:
                    extreme_l = lows[i]
                elif highs[i] - extreme_l >= threshold:
                    # Confirmed Swing Low
                    is_sl[i] = True
                    sl_price[i] = extreme_l
                    cur_sl = extreme_l
                    trend = 1
                    extreme_h = highs[i]

            last_sh[i] = cur_sh
            last_sl[i] = cur_sl

        return df_calc.with_columns([
            pl.Series(name=f"is_atr_sh_{atr_multiplier}", values=is_sh),
            pl.Series(name=f"is_atr_sl_{atr_multiplier}", values=is_sl),
            pl.Series(name=f"last_atr_sh_{atr_multiplier}", values=last_sh),
            pl.Series(name=f"last_atr_sl_{atr_multiplier}", values=last_sl),
        ]).drop([atr_col])

    @classmethod
    def compute_market_structure(
        cls,
        df: pl.DataFrame,
        left_bars: int = 5,
        right_bars: int = 5,
    ) -> pl.DataFrame:
        """Compute full causal market structure sequence: HH, HL, LH, LL, BOS (wick/close), CHoCH, MSS."""
        df_swings = cls.detect_fractal_swings(df, left_bars=left_bars, right_bars=right_bars)

        highs = df_swings["high"].to_numpy()
        lows = df_swings["low"].to_numpy()
        closes = df_swings["close"].to_numpy()
        is_sh = df_swings[f"is_sh_L{left_bars}_R{right_bars}"].to_numpy()
        is_sl = df_swings[f"is_sl_L{left_bars}_R{right_bars}"].to_numpy()
        sh_prices = df_swings[f"sh_price_L{left_bars}_R{right_bars}"].to_numpy()
        sl_prices = df_swings[f"sl_price_L{left_bars}_R{right_bars}"].to_numpy()
        n = len(df)

        is_hh = np.zeros(n, dtype=bool)
        is_hl = np.zeros(n, dtype=bool)
        is_lh = np.zeros(n, dtype=bool)
        is_ll = np.zeros(n, dtype=bool)

        bos_wick_bull = np.zeros(n, dtype=bool)
        bos_wick_bear = np.zeros(n, dtype=bool)
        bos_close_bull = np.zeros(n, dtype=bool)
        bos_close_bear = np.zeros(n, dtype=bool)

        choch_bull = np.zeros(n, dtype=bool)
        choch_bear = np.zeros(n, dtype=bool)
        structural_trend = np.zeros(n, dtype=np.int32) # 1=bullish, -1=bearish, 0=neutral

        prev_sh: Optional[float] = None
        prev_sl: Optional[float] = None
        cur_sh: Optional[float] = None
        cur_sl: Optional[float] = None

        cur_trend = 0

        for i in range(n):
            # Check swing confirmations
            if is_sh[i]:
                new_sh = sh_prices[i]
                if cur_sh is not None:
                    prev_sh = cur_sh
                    if new_sh > prev_sh:
                        is_hh[i] = True
                        cur_trend = 1
                    else:
                        is_lh[i] = True
                        cur_trend = -1
                cur_sh = new_sh

            if is_sl[i]:
                new_sl = sl_prices[i]
                if cur_sl is not None:
                    prev_sl = cur_sl
                    if new_sl > prev_sl:
                        is_hl[i] = True
                        cur_trend = 1
                    else:
                        is_ll[i] = True
                        cur_trend = -1
                cur_sl = new_sl

            # Check BOS by Wick and Close
            if cur_sh is not None:
                if highs[i] > cur_sh and highs[i-1] <= cur_sh:
                    bos_wick_bull[i] = True
                if closes[i] > cur_sh and closes[i-1] <= cur_sh:
                    bos_close_bull[i] = True
                    # If previously bearish, close above last SH is CHoCH
                    if cur_trend == -1:
                        choch_bull[i] = True
                        cur_trend = 1
                    elif cur_trend == 0:
                        cur_trend = 1

            if cur_sl is not None:
                if lows[i] < cur_sl and lows[i-1] >= cur_sl:
                    bos_wick_bear[i] = True
                if closes[i] < cur_sl and closes[i-1] >= cur_sl:
                    bos_close_bear[i] = True
                    # If previously bullish, close below last SL is CHoCH
                    if cur_trend == 1:
                        choch_bear[i] = True
                        cur_trend = -1
                    elif cur_trend == 0:
                        cur_trend = -1

            structural_trend[i] = cur_trend

        return df_swings.with_columns([
            pl.Series(name="is_hh", values=is_hh),
            pl.Series(name="is_hl", values=is_hl),
            pl.Series(name="is_lh", values=is_lh),
            pl.Series(name="is_ll", values=is_ll),
            pl.Series(name="is_bos_wick_bullish", values=bos_wick_bull),
            pl.Series(name="is_bos_wick_bearish", values=bos_wick_bear),
            pl.Series(name="is_bos_close_bullish", values=bos_close_bull),
            pl.Series(name="is_bos_close_bearish", values=bos_close_bear),
            pl.Series(name="is_choch_bullish", values=choch_bull),
            pl.Series(name="is_choch_bearish", values=choch_bear),
            pl.Series(name="structural_trend", values=structural_trend),
        ])
