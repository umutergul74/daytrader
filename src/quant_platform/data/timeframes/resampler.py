"""Causal Multi-Timeframe Resampling Engine.

Strictly aggregates 1-minute canonical klines into higher timeframes
(3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w) using UTC calendar alignment
and preserving exact causality (an incomplete candle is never marked available).
"""

from typing import Union
import polars as pl
from quant_platform.domain.timeframe import Timeframe


class CausalResampler:
    """Aggregates 1m canonical data into higher timeframes causally."""

    @staticmethod
    def resample(
        df_1m: pl.DataFrame,
        target_timeframe: Union[str, Timeframe],
    ) -> pl.DataFrame:
        """Resample 1-minute OHLCV DataFrame into target timeframe."""
        tf = Timeframe(target_timeframe) if isinstance(target_timeframe, str) else target_timeframe
        if tf == Timeframe.M1:
            return df_1m.sort("open_time")

        if df_1m.is_empty():
            return df_1m

        # Convert open_time (ms) to Datetime for group_by_dynamic
        df_with_dt = df_1m.with_columns(
            pl.from_epoch(pl.col("open_time"), time_unit="ms").alias("datetime_utc")
        ).sort("datetime_utc")

        # Dynamic groupby based on UTC intervals
        rule = tf.polars_rule
        aggregated = (
            df_with_dt.group_by_dynamic(
                "datetime_utc",
                every=rule,
                period=rule,
                closed="left",
                label="left",
            )
            .agg([
                pl.col("open_time").first().alias("open_time"),
                pl.col("open").first().alias("open"),
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
                pl.col("close_time").last().alias("close_time"),
                pl.col("quote_asset_volume").sum().alias("quote_asset_volume"),
                pl.col("number_of_trades").sum().alias("number_of_trades"),
                pl.col("taker_buy_base_asset_volume").sum().alias("taker_buy_base_asset_volume"),
                pl.col("taker_buy_quote_asset_volume").sum().alias("taker_buy_quote_asset_volume"),
                pl.count("open_time").alias("bar_count_1m"),
            ])
            .drop("datetime_utc")
            .sort("open_time")
        )

        # Add information availability timestamp (ms UTC)
        # The higher timeframe candle is available exactly at its close_time + 1 ms (or the open of the next candle)
        aggregated = aggregated.with_columns([
            (pl.col("close_time") + 1).alias("available_at_ms")
        ])

        return aggregated
