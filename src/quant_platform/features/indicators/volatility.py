"""Volatility Indicators in Polars."""

from typing import Optional, Tuple
import numpy as np
import polars as pl


def compute_atr(df: pl.DataFrame, period: int = 14, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Average True Range (Wilder's ATR) and True Range."""
    out = output_col or f"atr_{period}"

    # TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
    prev_close = pl.col("close").shift(1)
    tr1 = pl.col("high") - pl.col("low")
    tr2 = (pl.col("high") - prev_close).abs()
    tr3 = (pl.col("low") - prev_close).abs()

    df_temp = df.with_columns([
        pl.max_horizontal([tr1, tr2, tr3]).alias("true_range")
    ])

    # Wilder's smoothing (alpha = 1 / period)
    df_res = df_temp.with_columns(
        pl.col("true_range").ewm_mean(alpha=1.0 / period, adjust=False).alias(out)
    )

    # Normalized ATR (NATR = ATR / Close * 100)
    df_res = df_res.with_columns(
        (pl.col(out) / pl.col("close") * 100.0).alias(f"natr_{period}")
    )

    return df_res


def compute_bollinger_bands(
    df: pl.DataFrame,
    period: int = 20,
    num_std: float = 2.0,
    column: str = "close",
) -> pl.DataFrame:
    """Compute Bollinger Bands (middle, upper, lower, bandwidth, %B)."""
    mid_col = f"bb_mid_{period}"
    upper_col = f"bb_upper_{period}"
    lower_col = f"bb_lower_{period}"
    width_col = f"bb_width_{period}"
    pct_b_col = f"bb_pct_b_{period}"

    df_temp = df.with_columns([
        pl.col(column).rolling_mean(window_size=period).alias(mid_col),
        pl.col(column).rolling_std(window_size=period).alias("_bb_std"),
    ])

    df_res = df_temp.with_columns([
        (pl.col(mid_col) + num_std * pl.col("_bb_std")).alias(upper_col),
        (pl.col(mid_col) - num_std * pl.col("_bb_std")).alias(lower_col),
    ])

    df_res = df_res.with_columns([
        ((pl.col(upper_col) - pl.col(lower_col)) / pl.col(mid_col)).alias(width_col),
        ((pl.col(column) - pl.col(lower_col)) / (pl.col(upper_col) - pl.col(lower_col) + 1e-12)).alias(pct_b_col),
    ]).drop(["_bb_std"])

    return df_res


def compute_realized_volatility(df: pl.DataFrame, window: int = 30, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute rolling annualized realized volatility from log returns."""
    out = output_col or f"realized_vol_{window}"
    
    # log returns
    df_temp = df.with_columns(
        (pl.col("close") / pl.col("close").shift(1)).log().alias("_log_ret")
    )
    
    # standard deviation of log returns * sqrt(annualization factor for minutes = 365*24*60 = 525600)
    ANNUAL_FACTOR = np.sqrt(525600.0)
    df_res = df_temp.with_columns(
        (pl.col("_log_ret").rolling_std(window_size=window) * ANNUAL_FACTOR).alias(out)
    ).drop(["_log_ret"])

    return df_res
