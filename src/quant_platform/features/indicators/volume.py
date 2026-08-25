"""Volume and Order-Flow Proxy Indicators in Polars."""

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


def compute_quote_volume_zscore(df: pl.DataFrame, period: int = 20, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute rolling Z-score of quote asset volume."""
    out = output_col or f"quote_vol_zscore_{period}"
    if "quote_asset_volume" not in df.columns:
        return df.with_columns(pl.lit(0.0).alias(out))

    mean_col = f"_qvol_mean_{period}"
    std_col = f"_qvol_std_{period}"

    df_temp = df.with_columns([
        pl.col("quote_asset_volume").rolling_mean(window_size=period).alias(mean_col),
        pl.col("quote_asset_volume").rolling_std(window_size=period).alias(std_col),
    ])

    df_res = df_temp.with_columns(
        ((pl.col("quote_asset_volume") - pl.col(mean_col)) / (pl.col(std_col) + 1e-12)).alias(out)
    ).drop([mean_col, std_col])

    return df_res


def compute_trade_count_zscore(df: pl.DataFrame, period: int = 20, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute rolling Z-score of number of trades."""
    out = output_col or f"trades_zscore_{period}"
    if "number_of_trades" not in df.columns:
        return df.with_columns(pl.lit(0.0).alias(out))

    mean_col = f"_ntrades_mean_{period}"
    std_col = f"_ntrades_std_{period}"

    df_temp = df.with_columns([
        pl.col("number_of_trades").cast(pl.Float64).rolling_mean(window_size=period).alias(mean_col),
        pl.col("number_of_trades").cast(pl.Float64).rolling_std(window_size=period).alias(std_col),
    ])

    df_res = df_temp.with_columns(
        ((pl.col("number_of_trades") - pl.col(mean_col)) / (pl.col(std_col) + 1e-12)).alias(out)
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


def compute_cmf(df: pl.DataFrame, period: int = 20, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Chaikin Money Flow (CMF)."""
    out = output_col or f"cmf_{period}"
    # Multiplier = ((Close - Low) - (High - Close)) / (High - Low)
    clv = ((pl.col("close") - pl.col("low")) - (pl.col("high") - pl.col("close"))) / (pl.col("high") - pl.col("low") + 1e-12)
    mf_vol = clv * pl.col("volume")

    df_temp = df.with_columns([
        mf_vol.alias("_mf_vol")
    ])

    df_res = df_temp.with_columns(
        (pl.col("_mf_vol").rolling_sum(window_size=period) / (pl.col("volume").rolling_sum(window_size=period) + 1e-12)).alias(out)
    ).drop(["_mf_vol"])

    return df_res


def compute_taker_buy_ratios(df: pl.DataFrame) -> pl.DataFrame:
    """Compute taker buy base and quote volume ratios."""
    cols = []
    if "taker_buy_base_asset_volume" in df.columns and "volume" in df.columns:
        cols.append((pl.col("taker_buy_base_asset_volume") / (pl.col("volume") + 1e-12)).alias("taker_buy_base_ratio"))
    if "taker_buy_quote_asset_volume" in df.columns and "quote_asset_volume" in df.columns:
        cols.append((pl.col("taker_buy_quote_asset_volume") / (pl.col("quote_asset_volume") + 1e-12)).alias("taker_buy_quote_ratio"))

    if not cols:
        return df
    return df.with_columns(cols)


def compute_volume_expansion(
    df: pl.DataFrame,
    rvol_period: int = 20,
    rvol_threshold: float = 2.0,
    zscore_threshold: float = 2.0,
) -> pl.DataFrame:
    """Flag volume surge / expansion events."""
    rvol_col = f"_rvol_{rvol_period}"
    zscore_col = f"_zscore_{rvol_period}"

    df_calc = compute_relative_volume(df, period=rvol_period, output_col=rvol_col)
    df_calc = compute_volume_zscore(df_calc, period=rvol_period, output_col=zscore_col)

    df_res = df_calc.with_columns(
        ((pl.col(rvol_col) >= rvol_threshold) | (pl.col(zscore_col) >= zscore_threshold)).alias(f"is_volume_expansion_{rvol_period}")
    ).drop([rvol_col, zscore_col])

    return df_res
