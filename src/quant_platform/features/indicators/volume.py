"""Volume Indicators in Polars."""

from typing import Optional
import numpy as np
import polars as pl


def compute_volume_zscore(df: pl.DataFrame, period: int = 20, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute rolling Z-score of volume."""
    out = output_col or f"vol_zscore_{period}"
    mean_col = f"_vol_mean_{period}"
    std_col = f"_vol_std_{period}"

    df_temp = df.with_columns([
        pl.col("volume").rolling_mean(window_size=period).alias(mean_col),
        pl.col("volume").rolling_std(window_size=period).alias(std_col),
    ])

    df_res = df_temp.with_columns(
        ((pl.col("volume") - pl.col(mean_col)) / (pl.col(std_col) + 1e-12)).alias(out)
    ).drop([mean_col, std_col])

    return df_res


def compute_relative_volume(df: pl.DataFrame, period: int = 20, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Relative Volume (RVOL = volume / SMA(volume, period))."""
    out = output_col or f"rvol_{period}"
    return df.with_columns(
        (pl.col("volume") / (pl.col("volume").rolling_mean(window_size=period) + 1e-12)).alias(out)
    )


def compute_obv(df: pl.DataFrame, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute On-Balance Volume (OBV)."""
    out = output_col or "obv"

    # OBV delta: +volume if close > prev_close, -volume if close < prev_close, 0 if equal
    prev_close = pl.col("close").shift(1)
    obv_delta = (
        pl.when(pl.col("close") > prev_close)
        .then(pl.col("volume"))
        .when(pl.col("close") < prev_close)
        .then(-pl.col("volume"))
        .otherwise(0.0)
    )

    df_temp = df.with_columns(obv_delta.fill_null(0.0).alias("_obv_delta"))
    return df_temp.with_columns(
        pl.col("_obv_delta").cum_sum().alias(out)
    ).drop(["_obv_delta"])
