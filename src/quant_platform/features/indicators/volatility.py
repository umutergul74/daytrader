"""Volatility Indicators in Polars."""

from typing import Optional, Tuple
import numpy as np
import polars as pl


def compute_atr(df: pl.DataFrame, period: int = 14, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Average True Range (Wilder's ATR) and True Range."""
    out = output_col or f"atr_{period}"

    prev_close = pl.col("close").shift(1)
    tr1 = pl.col("high") - pl.col("low")
    tr2 = (pl.col("high") - prev_close).abs()
    tr3 = (pl.col("low") - prev_close).abs()

    df_temp = df.with_columns([
        pl.max_horizontal([tr1, tr2, tr3]).alias("true_range")
    ])

    df_res = df_temp.with_columns(
        pl.col("true_range").ewm_mean(alpha=1.0 / period, adjust=False).alias(out)
    )

    df_res = df_res.with_columns(
        (pl.col(out) / (pl.col("close") + 1e-12) * 100.0).alias(f"natr_{period}")
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
        ((pl.col(upper_col) - pl.col(lower_col)) / (pl.col(mid_col) + 1e-12)).alias(width_col),
        ((pl.col(column) - pl.col(lower_col)) / (pl.col(upper_col) - pl.col(lower_col) + 1e-12)).alias(pct_b_col),
    ]).drop(["_bb_std"])

    return df_res


def compute_keltner_channels(
    df: pl.DataFrame,
    ema_period: int = 20,
    atr_period: int = 10,
    multiplier: float = 2.0,
) -> pl.DataFrame:
    """Compute Keltner Channels (EMA middle, ATR upper and lower)."""
    mid_col = f"kc_mid_{ema_period}"
    upper_col = f"kc_upper_{ema_period}_{atr_period}"
    lower_col = f"kc_lower_{ema_period}_{atr_period}"
    atr_col = f"_kc_atr_{atr_period}"

    df_calc = compute_atr(df, period=atr_period, output_col=atr_col)
    df_calc = df_calc.with_columns(
        pl.col("close").ewm_mean(span=ema_period, adjust=False).alias(mid_col)
    )

    df_res = df_calc.with_columns([
        (pl.col(mid_col) + (multiplier * pl.col(atr_col))).alias(upper_col),
        (pl.col(mid_col) - (multiplier * pl.col(atr_col))).alias(lower_col),
    ]).drop([atr_col])

    return df_res


def compute_donchian_channels(df: pl.DataFrame, period: int = 20) -> pl.DataFrame:
    """Compute Donchian Channels (highest high, lowest low, mid, and width)."""
    high_col = f"donchian_high_{period}"
    low_col = f"donchian_low_{period}"
    mid_col = f"donchian_mid_{period}"
    width_col = f"donchian_width_{period}"

    df_temp = df.with_columns([
        pl.col("high").rolling_max(window_size=period).alias(high_col),
        pl.col("low").rolling_min(window_size=period).alias(low_col),
    ])

    df_res = df_temp.with_columns([
        ((pl.col(high_col) + pl.col(low_col)) / 2.0).alias(mid_col),
        ((pl.col(high_col) - pl.col(low_col)) / ((pl.col(high_col) + pl.col(low_col)) / 2.0 + 1e-12)).alias(width_col),
    ])

    return df_res


def compute_realized_volatility(df: pl.DataFrame, window: int = 30, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute rolling annualized realized volatility from log returns."""
    out = output_col or f"realized_vol_{window}"
    
    df_temp = df.with_columns(
        (pl.col("close") / (pl.col("close").shift(1) + 1e-12)).log().alias("_log_ret")
    )
    
    ANNUAL_FACTOR = np.sqrt(525600.0)
    df_res = df_temp.with_columns(
        (pl.col("_log_ret").rolling_std(window_size=window) * ANNUAL_FACTOR).alias(out)
    ).drop(["_log_ret"])

    return df_res


def compute_volatility_percentiles(df: pl.DataFrame, lookback: int = 100) -> pl.DataFrame:
    """Compute rolling percentile ranking (0 to 100) for ATR and Realized Volatility."""
    df_calc = compute_atr(df, period=14, output_col="_atr_p")
    df_calc = compute_realized_volatility(df_calc, window=30, output_col="_rvol_p")

    # Rolling percent rank via numpy
    atr_vals = df_calc["_atr_p"].to_numpy()
    rvol_vals = df_calc["_rvol_p"].to_numpy()
    n = len(df)

    atr_pctile = np.full(n, 50.0, dtype=np.float64)
    rvol_pctile = np.full(n, 50.0, dtype=np.float64)

    for i in range(lookback, n):
        w_atr = atr_vals[i - lookback : i + 1]
        w_rvol = rvol_vals[i - lookback : i + 1]
        valid_atr = w_atr[~np.isnan(w_atr)]
        valid_rvol = w_rvol[~np.isnan(w_rvol)]

        if len(valid_atr) > 1:
            atr_pctile[i] = (np.sum(valid_atr < atr_vals[i]) / len(valid_atr)) * 100.0
        if len(valid_rvol) > 1:
            rvol_pctile[i] = (np.sum(valid_rvol < rvol_vals[i]) / len(valid_rvol)) * 100.0

    return df_calc.with_columns([
        pl.Series(name=f"atr_percentile_{lookback}", values=atr_pctile),
        pl.Series(name=f"realized_vol_percentile_{lookback}", values=rvol_pctile),
    ]).drop(["_atr_p", "_rvol_p"])


def compute_candle_metrics(df: pl.DataFrame) -> pl.DataFrame:
    """Compute candle anatomy: body-to-range, upper wick ratio, lower wick ratio."""
    candle_range = pl.col("high") - pl.col("low")
    body = (pl.col("close") - pl.col("open")).abs()
    upper_wick = pl.col("high") - pl.max_horizontal([pl.col("open"), pl.col("close")])
    lower_wick = pl.min_horizontal([pl.col("open"), pl.col("close")]) - pl.col("low")

    return df.with_columns([
        (body / (candle_range + 1e-12)).alias("body_to_range_ratio"),
        (upper_wick / (candle_range + 1e-12)).alias("upper_wick_ratio"),
        (lower_wick / (candle_range + 1e-12)).alias("lower_wick_ratio"),
        (pl.col("close") >= pl.col("open")).alias("is_bullish_candle"),
    ])
