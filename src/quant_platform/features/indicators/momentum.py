"""Momentum Indicators in Polars."""

from typing import Optional, Tuple
import polars as pl


def compute_rsi(df: pl.DataFrame, period: int = 14, column: str = "close", output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Relative Strength Index (Wilder's RSI)."""
    out = output_col or f"rsi_{period}"
    
    # Calculate price change
    diff = pl.col(column).diff()
    gain = pl.when(diff > 0).then(diff).otherwise(0.0)
    loss = pl.when(diff < 0).then(-diff).otherwise(0.0)

    # Wilder's smoothing corresponds to ewm with alpha = 1 / period (span = 2*period - 1)
    df_temp = df.with_columns([
        gain.alias("_gain"),
        loss.alias("_loss"),
    ])

    df_temp = df_temp.with_columns([
        pl.col("_gain").ewm_mean(alpha=1.0 / period, adjust=False).alias("_avg_gain"),
        pl.col("_loss").ewm_mean(alpha=1.0 / period, adjust=False).alias("_avg_loss"),
    ])

    df_res = df_temp.with_columns(
        pl.when(pl.col("_avg_loss") == 0)
        .then(100.0)
        .otherwise(
            100.0 - (100.0 / (1.0 + (pl.col("_avg_gain") / pl.col("_avg_loss"))))
        )
        .alias(out)
    ).drop(["_gain", "_loss", "_avg_gain", "_avg_loss"])

    return df_res


def compute_macd(
    df: pl.DataFrame,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    column: str = "close",
) -> pl.DataFrame:
    """Compute Moving Average Convergence Divergence (MACD)."""
    fast_col = f"_ema_{fast_period}"
    slow_col = f"_ema_{slow_period}"
    macd_col = f"macd_{fast_period}_{slow_period}"
    sig_col = f"macd_signal_{signal_period}"
    hist_col = f"macd_hist_{fast_period}_{slow_period}_{signal_period}"

    df_temp = df.with_columns([
        pl.col(column).ewm_mean(span=fast_period, adjust=False).alias(fast_col),
        pl.col(column).ewm_mean(span=slow_period, adjust=False).alias(slow_col),
    ])

    df_temp = df_temp.with_columns(
        (pl.col(fast_col) - pl.col(slow_col)).alias(macd_col)
    )

    df_temp = df_temp.with_columns(
        pl.col(macd_col).ewm_mean(span=signal_period, adjust=False).alias(sig_col)
    )

    df_res = df_temp.with_columns(
        (pl.col(macd_col) - pl.col(sig_col)).alias(hist_col)
    ).drop([fast_col, slow_col])

    return df_res


def compute_stochastic(
    df: pl.DataFrame,
    k_period: int = 14,
    d_period: int = 3,
    s_period: int = 3,
) -> pl.DataFrame:
    """Compute Stochastic Oscillator %K and %D."""
    low_min = pl.col("low").rolling_min(window_size=k_period)
    high_max = pl.col("high").rolling_max(window_size=k_period)

    raw_k = 100.0 * (pl.col("close") - low_min) / (high_max - low_min + 1e-12)

    df_temp = df.with_columns(raw_k.alias("_raw_k"))
    
    # Smooth %K
    df_temp = df_temp.with_columns(
        pl.col("_raw_k").rolling_mean(window_size=s_period).alias("stoch_k")
    )
    
    # %D is SMA of %K
    df_res = df_temp.with_columns(
        pl.col("stoch_k").rolling_mean(window_size=d_period).alias("stoch_d")
    ).drop(["_raw_k"])

    return df_res
