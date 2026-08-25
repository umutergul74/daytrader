"""Liquidity Level, Sweep, and Session Levels Engine in Polars."""

from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
import numpy as np
import polars as pl

from quant_platform.domain.smc import (
    LiquidityLevelType,
    LiquidityLevel,
    SweepEvent,
)
from quant_platform.features.indicators.volatility import compute_atr
from quant_platform.features.structure.market_structure import MarketStructureEngine


class LiquidityEngine:
    """Detects liquidity levels, EQH/EQL clusters, sweeps, reclaims, and dealing ranges."""

    @classmethod
    def detect_equal_highs_lows(
        cls,
        df: pl.DataFrame,
        left_bars: int = 5,
        right_bars: int = 5,
        atr_period: int = 14,
        tolerance_atr: float = 0.15,
        cluster_window: int = 50,
    ) -> pl.DataFrame:
        """Detect Equal Highs (EQH) and Equal Lows (EQL) within ATR-normalized tolerance."""
        df_swings = MarketStructureEngine.detect_fractal_swings(df, left_bars=left_bars, right_bars=right_bars)
        atr_col = f"_eq_atr_{atr_period}"
        df_swings = compute_atr(df_swings, period=atr_period, output_col=atr_col)

        is_sh = df_swings[f"is_sh_L{left_bars}_R{right_bars}"].to_numpy()
        is_sl = df_swings[f"is_sl_L{left_bars}_R{right_bars}"].to_numpy()
        sh_prices = df_swings[f"sh_price_L{left_bars}_R{right_bars}"].to_numpy()
        sl_prices = df_swings[f"sl_price_L{left_bars}_R{right_bars}"].to_numpy()
        atrs = df_swings[atr_col].to_numpy()
        n = len(df)

        is_eqh = np.zeros(n, dtype=bool)
        is_eql = np.zeros(n, dtype=bool)
        eqh_price = np.full(n, np.nan, dtype=np.float64)
        eql_price = np.full(n, np.nan, dtype=np.float64)

        recent_sh_idx: List[int] = []
        recent_sl_idx: List[int] = []

        for i in range(n):
            # Prune old swings outside cluster window
            recent_sh_idx = [idx for idx in recent_sh_idx if i - idx <= cluster_window]
            recent_sl_idx = [idx for idx in recent_sl_idx if i - idx <= cluster_window]

            atr_val = atrs[i] if not np.isnan(atrs[i]) else 1.0
            tol = tolerance_atr * atr_val

            if is_sh[i]:
                new_h = sh_prices[i]
                for prev_idx in recent_sh_idx:
                    prev_h = sh_prices[prev_idx]
                    if abs(new_h - prev_h) <= tol:
                        is_eqh[i] = True
                        eqh_price[i] = (new_h + prev_h) / 2.0
                        break
                recent_sh_idx.append(i)

            if is_sl[i]:
                new_l = sl_prices[i]
                for prev_idx in recent_sl_idx:
                    prev_l = sl_prices[prev_idx]
                    if abs(new_l - prev_l) <= tol:
                        is_eql[i] = True
                        eql_price[i] = (new_l + prev_l) / 2.0
                        break
                recent_sl_idx.append(i)

        return df_swings.with_columns([
            pl.Series(name="is_eqh", values=is_eqh),
            pl.Series(name="is_eql", values=is_eql),
            pl.Series(name="eqh_price", values=eqh_price),
            pl.Series(name="eql_price", values=eql_price),
        ]).drop([atr_col])

    @classmethod
    def detect_liquidity_sweeps(
        cls,
        df: pl.DataFrame,
        left_bars: int = 5,
        right_bars: int = 5,
        atr_period: int = 14,
    ) -> Tuple[pl.DataFrame, List[SweepEvent]]:
        """Detect Buy-side and Sell-side liquidity sweeps and reclaims."""
        df_eq = cls.detect_equal_highs_lows(df, left_bars=left_bars, right_bars=right_bars, atr_period=atr_period)
        atr_col = f"_swp_atr_{atr_period}"
        df_eq = compute_atr(df_eq, period=atr_period, output_col=atr_col)

        highs = df_eq["high"].to_numpy()
        lows = df_eq["low"].to_numpy()
        closes = df_eq["close"].to_numpy()
        open_times = df_eq["open_time"].to_numpy()
        close_times = df_eq["close_time"].to_numpy()
        last_sh = df_eq[f"last_sh_L{left_bars}_R{right_bars}"].to_numpy()
        last_sl = df_eq[f"last_sl_L{left_bars}_R{right_bars}"].to_numpy()
        atrs = df_eq[atr_col].to_numpy()
        n = len(df)

        is_buyside_sweep = np.zeros(n, dtype=bool)
        is_sellside_sweep = np.zeros(n, dtype=bool)
        is_buyside_reclaim = np.zeros(n, dtype=bool)
        is_sellside_reclaim = np.zeros(n, dtype=bool)
        sweep_overshoot_atr = np.zeros(n, dtype=np.float64)

        sweeps: List[SweepEvent] = []

        for i in range(1, n):
            target_sh = last_sh[i - 1]
            target_sl = last_sl[i - 1]
            atr_val = atrs[i] if not np.isnan(atrs[i]) else 1.0

            # Buy-side sweep: High traded above SH
            if not np.isnan(target_sh) and highs[i] > target_sh:
                overshoot = highs[i] - target_sh
                overshoot_ratio = overshoot / (atr_val + 1e-12)
                is_buyside_sweep[i] = True
                sweep_overshoot_atr[i] = overshoot_ratio

                # Reclaim if close is back below SH
                if closes[i] < target_sh:
                    is_buyside_reclaim[i] = True
                    sweeps.append(SweepEvent(
                        sweep_id=f"SWP-BUY-{open_times[i]}",
                        level_id=f"SH-{target_sh}",
                        level_type=LiquidityLevelType.SWING_HIGH,
                        level_price=float(target_sh),
                        sweep_price=float(highs[i]),
                        overshoot_distance=float(overshoot),
                        overshoot_atr=float(overshoot_ratio),
                        is_reclaimed=True,
                        sweep_time=int(open_times[i]),
                        confirmed_time=int(close_times[i]),
                        is_bullish_sweep=False, # Bearish reversal after buy-side sweep
                    ))

            # Sell-side sweep: Low traded below SL
            if not np.isnan(target_sl) and lows[i] < target_sl:
                overshoot = target_sl - lows[i]
                overshoot_ratio = overshoot / (atr_val + 1e-12)
                is_sellside_sweep[i] = True
                sweep_overshoot_atr[i] = overshoot_ratio

                # Reclaim if close is back above SL
                if closes[i] > target_sl:
                    is_sellside_reclaim[i] = True
                    sweeps.append(SweepEvent(
                        sweep_id=f"SWP-SELL-{open_times[i]}",
                        level_id=f"SL-{target_sl}",
                        level_type=LiquidityLevelType.SWING_LOW,
                        level_price=float(target_sl),
                        sweep_price=float(lows[i]),
                        overshoot_distance=float(overshoot),
                        overshoot_atr=float(overshoot_ratio),
                        is_reclaimed=True,
                        sweep_time=int(open_times[i]),
                        confirmed_time=int(close_times[i]),
                        is_bullish_sweep=True, # Bullish bounce after sell-side sweep
                    ))

        df_res = df_eq.with_columns([
            pl.Series(name="is_buyside_sweep", values=is_buyside_sweep),
            pl.Series(name="is_sellside_sweep", values=is_sellside_sweep),
            pl.Series(name="is_buyside_reclaim", values=is_buyside_reclaim),
            pl.Series(name="is_sellside_reclaim", values=is_sellside_reclaim),
            pl.Series(name="sweep_overshoot_atr", values=sweep_overshoot_atr),
        ]).drop([atr_col])

        return df_res, sweeps

    @staticmethod
    def compute_previous_day_week_levels(df: pl.DataFrame) -> pl.DataFrame:
        """Compute causal Previous Day High/Low (PDH/PDL) and Week High/Low (PWH/PWL)."""
        # Group by UTC day (open_time // 86400000)
        df_temp = df.with_columns([
            (pl.col("open_time") // 86400000).alias("_day_id"),
            (pl.col("open_time") // (86400000 * 7)).alias("_week_id"),
        ])

        # Aggregate daily max/min
        daily_stats = df_temp.group_by("_day_id").agg([
            pl.col("high").max().alias("_day_high"),
            pl.col("low").min().alias("_day_low"),
            pl.col("open").first().alias("_day_open"),
        ]).sort("_day_id")

        # Shift by 1 day so yesterday's values are available today
        daily_stats = daily_stats.with_columns([
            pl.col("_day_high").shift(1).alias("pdh"),
            pl.col("_day_low").shift(1).alias("pdl"),
            pl.col("_day_open").alias("daily_open"),
        ])

        # Join back
        df_res = df_temp.join(daily_stats.select(["_day_id", "pdh", "pdl", "daily_open"]), on="_day_id", how="left")

        # Dealing Range & Equilibrium relative to PDH/PDL
        df_res = df_res.with_columns([
            ((pl.col("pdh") + pl.col("pdl")) / 2.0).alias("pd_equilibrium"),
            (pl.col("close") > (pl.col("pdh") + pl.col("pdl")) / 2.0).alias("is_in_premium"),
            (pl.col("close") < (pl.col("pdh") + pl.col("pdl")) / 2.0).alias("is_in_discount"),
        ]).drop(["_day_id", "_week_id"])

        return df_res
