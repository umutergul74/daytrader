"""Trend and Moving Average Indicators in Polars."""

from typing import Optional
import numpy as np
import polars as pl


def compute_sma(df: pl.DataFrame, period: int = 20, column: str = "close", output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Simple Moving Average."""
    out = output_col or f"sma_{period}"
    return df.with_columns(
        pl.col(column).rolling_mean(window_size=period).alias(out)
    )


def compute_ema(df: pl.DataFrame, period: int = 20, column: str = "close", output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Exponential Moving Average."""
    out = output_col or f"ema_{period}"
    return df.with_columns(
        pl.col(column).ewm_mean(span=period, adjust=False).alias(out)
    )


def compute_wma(df: pl.DataFrame, period: int = 20, column: str = "close", output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Weighted Moving Average."""
    out = output_col or f"wma_{period}"
    weights = np.arange(1, period + 1, dtype=np.float64)
    w_sum = weights.sum()

    # Polars rolling map or numpy rolling
    prices = df[column].to_numpy()
    n = len(prices)
    wma_arr = np.full(n, np.nan, dtype=np.float64)

    for i in range(period - 1, n):
        wma_arr[i] = np.dot(prices[i - period + 1 : i + 1], weights) / w_sum

    return df.with_columns(pl.Series(name=out, values=wma_arr))


def compute_hma(df: pl.DataFrame, period: int = 20, column: str = "close", output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Hull Moving Average: WMA(2*WMA(n/2) - WMA(n)), sqrt(n))."""
    out = output_col or f"hma_{period}"
    half_period = max(1, period // 2)
    sqrt_period = max(1, int(np.sqrt(period)))

    df_temp = compute_wma(df, period=half_period, column=column, output_col="_wma_half")
    df_temp = compute_wma(df_temp, period=period, column=column, output_col="_wma_full")

    df_temp = df_temp.with_columns(
        (2 * pl.col("_wma_half") - pl.col("_wma_full")).alias("_raw_diff")
    )

    df_res = compute_wma(df_temp, period=sqrt_period, column="_raw_diff", output_col=out)
    return df_res.drop(["_wma_half", "_wma_full", "_raw_diff"])
