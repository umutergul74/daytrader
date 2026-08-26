"""Open Interest Derivatives Context Feature Engine.

Computes causal Open Interest dynamics and classifies the 4-State Joint Price/OI Matrix:
 - LONG_BUILDUP (Price Up, OI Up)
 - SHORT_COVERING (Price Up, OI Down)
 - SHORT_BUILDUP (Price Down, OI Up)
 - LONG_LIQUIDATION (Price Down, OI Down)
"""

from typing import Optional
import polars as pl
from pydantic import BaseModel


class OpenInterestFeatureEngine:
    """Computes Open Interest shifts, z-scores, and joint price/OI regimes."""

    @staticmethod
    def align_and_compute_oi_features(
        df_klines: pl.DataFrame,
        df_oi: pl.DataFrame,
        oi_lookback: int = 12,
    ) -> pl.DataFrame:
        """Causally joins OI data to klines and computes derivatives features."""
        if df_oi.is_empty() or "open_interest" not in df_oi.columns:
            # Add neutral defaults if OI is absent
            return df_klines.with_columns([
                pl.lit(0.0).alias("open_interest"),
                pl.lit(0.0).alias("oi_change_pct_15m"),
                pl.lit(0.0).alias("oi_zscore_15m"),
                pl.lit("NEUTRAL").alias("joint_price_oi_regime"),
            ])

        # As-of backward join on timestamp
        df_oi_sorted = df_oi.sort("event_time_ms")
        df_joined = df_klines.sort("close_time").join_asof(
            df_oi_sorted.select(["event_time_ms", "open_interest"]),
            left_on="close_time",
            right_on="event_time_ms",
            strategy="backward",
        ).drop("event_time_ms")

        # Fill missing values
        df_joined = df_joined.with_columns([
            pl.col("open_interest").forward_fill().backward_fill().alias("open_interest")
        ])

        # Compute shifts and deltas
        df_feat = df_joined.with_columns([
            (pl.col("open_interest") - pl.col("open_interest").shift(1)).alias("oi_change_abs_15m"),
            ((pl.col("open_interest") - pl.col("open_interest").shift(1)) / pl.when(pl.col("open_interest").shift(1) > 0).then(pl.col("open_interest").shift(1)).otherwise(1.0) * 100.0).alias("oi_change_pct_15m"),
            pl.col("open_interest").rolling_mean(window_size=oi_lookback).alias("_oi_mean"),
            pl.col("open_interest").rolling_std(window_size=oi_lookback).alias("_oi_std"),
        ])

        # Compute OI Z-Score
        df_feat = df_feat.with_columns([
            ((pl.col("open_interest") - pl.col("_oi_mean")) / pl.when(pl.col("_oi_std") > 1e-6).then(pl.col("_oi_std")).otherwise(1.0)).alias("oi_zscore_15m")
        ]).drop(["_oi_mean", "_oi_std"])

        # 4-State Joint Price / OI Regime Classification
        price_up = pl.col("close") > pl.col("open")
        oi_up = pl.col("oi_change_abs_15m") > 0

        df_feat = df_feat.with_columns([
            pl.when(price_up & oi_up)
            .then(pl.lit("LONG_BUILDUP"))
            .when(price_up & (~oi_up))
            .then(pl.lit("SHORT_COVERING"))
            .when((~price_up) & oi_up)
            .then(pl.lit("SHORT_BUILDUP"))
            .otherwise(pl.lit("LONG_LIQUIDATION"))
            .alias("joint_price_oi_regime")
        ])

        return df_feat
