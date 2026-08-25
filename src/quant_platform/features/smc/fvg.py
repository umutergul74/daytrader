"""Lifecycle-aware Fair Value Gap (FVG) Engine in Polars."""

from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import polars as pl

from quant_platform.domain.smc import (
    FvgDirection,
    FvgMitigationState,
    FairValueGap,
)
from quant_platform.features.indicators.volatility import compute_atr


class FvgEngine:
    """Detects and tracks lifecycle of 3-candle Fair Value Gaps."""

    @classmethod
    def detect_and_track_fvgs(
        cls,
        df: pl.DataFrame,
        atr_period: int = 14,
        min_gap_atr_ratio: float = 0.2,
        timeframe: str = "15m",
    ) -> Tuple[pl.DataFrame, List[FairValueGap]]:
        """Compute causal FVG features and track lifecycle."""
        atr_col = f"_fvg_atr_{atr_period}"
        df_calc = compute_atr(df, period=atr_period, output_col=atr_col)

        highs = df_calc["high"].to_numpy()
        lows = df_calc["low"].to_numpy()
        closes = df_calc["close"].to_numpy()
        open_times = df_calc["open_time"].to_numpy()
        close_times = df_calc["close_time"].to_numpy()
        atrs = df_calc[atr_col].to_numpy()
        n = len(df)

        is_bull_fvg = np.zeros(n, dtype=bool)
        is_bear_fvg = np.zeros(n, dtype=bool)
        fvg_size_atr = np.zeros(n, dtype=np.float64)
        active_bull_count = np.zeros(n, dtype=np.int32)
        active_bear_count = np.zeros(n, dtype=np.int32)
        inside_bull_fvg = np.zeros(n, dtype=bool)
        inside_bear_fvg = np.zeros(n, dtype=bool)

        all_fvgs: List[FairValueGap] = []
        active_bull_fvgs: List[FairValueGap] = []
        active_bear_fvgs: List[FairValueGap] = []

        for i in range(2, n):
            c_high = highs[i]
            c_low = lows[i]
            c_close = closes[i]
            atr_val = atrs[i] if not np.isnan(atrs[i]) else 1.0

            # 1. Check for Bullish FVG creation at candle i (candles: i-2, i-1, i)
            # Bullish: low[i] > high[i-2]
            if c_low > highs[i - 2]:
                gap_size = c_low - highs[i - 2]
                gap_ratio = gap_size / (atr_val + 1e-12)
                if gap_ratio >= min_gap_atr_ratio:
                    fvg = FairValueGap(
                        fvg_id=f"FVG-BULL-{open_times[i]}",
                        direction=FvgDirection.BULLISH,
                        upper_bound=float(c_low),
                        lower_bound=float(highs[i - 2]),
                        consequent_encroachment=float((c_low + highs[i - 2]) / 2.0),
                        gap_size=float(gap_size),
                        gap_size_atr=float(gap_ratio),
                        created_at_time=int(close_times[i]),
                        available_at_time=int(close_times[i] + 1),
                        creation_bar_index=i,
                        timeframe=timeframe,
                    )
                    is_bull_fvg[i] = True
                    fvg_size_atr[i] = gap_ratio
                    all_fvgs.append(fvg)
                    active_bull_fvgs.append(fvg)

            # 2. Check for Bearish FVG creation at candle i
            # Bearish: high[i] < low[i-2]
            if c_high < lows[i - 2]:
                gap_size = lows[i - 2] - c_high
                gap_ratio = gap_size / (atr_val + 1e-12)
                if gap_ratio >= min_gap_atr_ratio:
                    fvg = FairValueGap(
                        fvg_id=f"FVG-BEAR-{open_times[i]}",
                        direction=FvgDirection.BEARISH,
                        upper_bound=float(lows[i - 2]),
                        lower_bound=float(c_high),
                        consequent_encroachment=float((lows[i - 2] + c_high) / 2.0),
                        gap_size=float(gap_size),
                        gap_size_atr=float(gap_ratio),
                        created_at_time=int(close_times[i]),
                        available_at_time=int(close_times[i] + 1),
                        creation_bar_index=i,
                        timeframe=timeframe,
                    )
                    is_bear_fvg[i] = True
                    fvg_size_atr[i] = gap_ratio
                    all_fvgs.append(fvg)
                    active_bear_fvgs.append(fvg)

            # 3. Update Active Bullish FVGs lifecycle
            remaining_bull = []
            for f in active_bull_fvgs:
                if f.creation_bar_index == i:
                    remaining_bull.append(f)
                    continue

                f.age_bars += 1
                # Test interaction with current candle i
                if c_low <= f.upper_bound:
                    if f.first_revisit_time is None:
                        f.first_revisit_time = int(open_times[i])

                    # Check if inside FVG
                    if c_low >= f.lower_bound or c_high <= f.upper_bound:
                        inside_bull_fvg[i] = True

                    # Partial mitigation (CE 50%)
                    if c_low <= f.consequent_encroachment:
                        f.mitigation_state = FvgMitigationState.PARTIALLY_MITIGATED

                    # Full mitigation / invalidation (price closed or dipped below lower bound)
                    if c_low <= f.lower_bound or c_close < f.lower_bound:
                        f.mitigation_state = FvgMitigationState.FULLY_MITIGATED
                        f.fully_mitigated_time = int(close_times[i])
                        continue # removed from active

                remaining_bull.append(f)
            active_bull_fvgs = remaining_bull

            # 4. Update Active Bearish FVGs lifecycle
            remaining_bear = []
            for f in active_bear_fvgs:
                if f.creation_bar_index == i:
                    remaining_bear.append(f)
                    continue

                f.age_bars += 1
                if c_high >= f.lower_bound:
                    if f.first_revisit_time is None:
                        f.first_revisit_time = int(open_times[i])

                    if c_high <= f.upper_bound or c_low >= f.lower_bound:
                        inside_bear_fvg[i] = True

                    if c_high >= f.consequent_encroachment:
                        f.mitigation_state = FvgMitigationState.PARTIALLY_MITIGATED

                    if c_high >= f.upper_bound or c_close > f.upper_bound:
                        f.mitigation_state = FvgMitigationState.FULLY_MITIGATED
                        f.fully_mitigated_time = int(close_times[i])
                        continue

                remaining_bear.append(f)
            active_bear_fvgs = remaining_bear

            active_bull_count[i] = len(active_bull_fvgs)
            active_bear_count[i] = len(active_bear_fvgs)

        df_res = df_calc.with_columns([
            pl.Series(name="is_bullish_fvg_created", values=is_bull_fvg),
            pl.Series(name="is_bearish_fvg_created", values=is_bear_fvg),
            pl.Series(name="fvg_size_atr", values=fvg_size_atr),
            pl.Series(name="active_bullish_fvg_count", values=active_bull_count),
            pl.Series(name="active_bearish_fvg_count", values=active_bear_count),
            pl.Series(name="is_inside_bullish_fvg", values=inside_bull_fvg),
            pl.Series(name="is_inside_bearish_fvg", values=inside_bear_fvg),
        ]).drop([atr_col])

        return df_res, all_fvgs
