"""Cumulative Volume Delta (CVD) and Delta Imbalance Engine.

Calculates quantitative order flow delta primitives:
 - Window Delta (1m, 5m, 15m)
 - Rolling CVD & Session CVD
 - Relative Delta & Delta Z-Score
 - CVD Divergence Detectors (Bearish Absorption, Bullish Accumulation)
"""

from typing import Optional, Dict, Any, Tuple
import numpy as np
import polars as pl
from pydantic import BaseModel, Field

from quant_platform.observability.logger import logger


class CvdEngine:
    """Computes vectorized and rolling Cumulative Volume Delta features."""

    @staticmethod
    def compute_kline_delta_features(
        df_1m: pl.DataFrame,
        rolling_window: int = 20,
    ) -> pl.DataFrame:
        """Derive causal delta features directly from 1m taker buy / quote asset volume columns."""
        # Ensure taker volume columns exist, fallback to approximation
        if "taker_buy_base_asset_volume" in df_1m.columns:
            buy_vol = pl.col("taker_buy_base_asset_volume")
            total_vol = pl.col("volume")
            sell_vol = total_vol - buy_vol
        else:
            # Synthetic volume approximation
            buy_vol = pl.col("volume") * 0.5
            sell_vol = pl.col("volume") * 0.5
            total_vol = pl.col("volume")

        delta_1m = buy_vol - sell_vol
        rel_delta_1m = delta_1m / pl.when(total_vol > 0).then(total_vol).otherwise(1.0)

        df_res = df_1m.with_columns([
            delta_1m.alias("delta_1m"),
            rel_delta_1m.alias("rel_delta_1m"),
            buy_vol.alias("taker_buy_vol_1m"),
            sell_vol.alias("taker_sell_vol_1m"),
        ])

        # Rolling CVD
        df_res = df_res.with_columns([
            pl.col("delta_1m").cum_sum().alias("cvd_global"),
            pl.col("delta_1m").rolling_sum(window_size=rolling_window).alias(f"cvd_rolling_{rolling_window}"),
            pl.col("delta_1m").rolling_mean(window_size=rolling_window).alias("_delta_mean"),
            pl.col("delta_1m").rolling_std(window_size=rolling_window).alias("_delta_std"),
        ])

        # Delta Z-score
        df_res = df_res.with_columns([
            ((pl.col("delta_1m") - pl.col("_delta_mean")) / pl.when(pl.col("_delta_std") > 1e-6).then(pl.col("_delta_std")).otherwise(1.0)).alias("delta_zscore_1m")
        ]).drop(["_delta_mean", "_delta_std"])

        return df_res

    @staticmethod
    def detect_cvd_divergence(
        df_15m: pl.DataFrame,
        lookback: int = 5,
    ) -> pl.DataFrame:
        """Detect Bearish Absorption (Price HH, CVD not HH) and Bullish Accumulation (Price LL, CVD not LL)."""
        if "cvd_global" not in df_15m.columns:
            df_15m = df_15m.with_columns([
                (pl.col("volume") * (pl.col("close") - pl.col("open")) / pl.col("close")).cum_sum().alias("cvd_global")
            ])

        df_calc = df_15m.with_columns([
            pl.col("high").shift(1).rolling_max(window_size=lookback).alias("_price_high_max"),
            pl.col("low").shift(1).rolling_min(window_size=lookback).alias("_price_low_min"),
            pl.col("cvd_global").shift(1).rolling_max(window_size=lookback).alias("_cvd_high_max"),
            pl.col("cvd_global").shift(1).rolling_min(window_size=lookback).alias("_cvd_low_min"),
        ])

        # Bearish Divergence: Price > Price_Max but CVD <= CVD_Max
        bearish_div = (pl.col("high") > pl.col("_price_high_max")) & (pl.col("cvd_global") <= pl.col("_cvd_high_max"))
        # Bullish Divergence: Price < Price_Min but CVD >= CVD_Min
        bullish_div = (pl.col("low") < pl.col("_price_low_min")) & (pl.col("cvd_global") >= pl.col("_cvd_low_min"))

        return df_calc.with_columns([
            bearish_div.fill_null(False).alias("is_cvd_bearish_divergence"),
            bullish_div.fill_null(False).alias("is_cvd_bullish_divergence"),
        ]).drop(["_price_high_max", "_price_low_min", "_cvd_high_max", "_cvd_low_min"])
