"""Momentum Indicators in Polars."""

from typing import Optional, Tuple
import numpy as np
import polars as pl


def compute_rsi(df: pl.DataFrame, period: int = 14, column: str = "close", output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Relative Strength Index (Wilder's RSI)."""
    out = output_col or f"rsi_{period}"
    
    diff = pl.col(column).diff()
    gain = pl.when(diff > 0).then(diff).otherwise(0.0)
    loss = pl.when(diff < 0).then(-diff).otherwise(0.0)

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
    
    df_temp = df_temp.with_columns(
        pl.col("_raw_k").rolling_mean(window_size=s_period).alias("stoch_k")
    )
    
    df_res = df_temp.with_columns(
        pl.col("stoch_k").rolling_mean(window_size=d_period).alias("stoch_d")
    ).drop(["_raw_k"])

    return df_res


def compute_stoch_rsi(
    df: pl.DataFrame,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_period: int = 3,
    d_period: int = 3,
) -> pl.DataFrame:
    """Compute Stochastic RSI (%K and %D)."""
    rsi_col = f"_rsi_{rsi_period}"
    df_calc = compute_rsi(df, period=rsi_period, output_col=rsi_col)

    rsi_min = pl.col(rsi_col).rolling_min(window_size=stoch_period)
    rsi_max = pl.col(rsi_col).rolling_max(window_size=stoch_period)

    raw_stoch_rsi = (pl.col(rsi_col) - rsi_min) / (rsi_max - rsi_min + 1e-12)

    df_temp = df_calc.with_columns(raw_stoch_rsi.alias("_raw_stoch_rsi"))
    df_temp = df_temp.with_columns(
        (pl.col("_raw_stoch_rsi").rolling_mean(window_size=k_period) * 100.0).alias(f"stoch_rsi_k_{rsi_period}")
    )
    df_res = df_temp.with_columns(
        pl.col(f"stoch_rsi_k_{rsi_period}").rolling_mean(window_size=d_period).alias(f"stoch_rsi_d_{rsi_period}")
    ).drop([rsi_col, "_raw_stoch_rsi"])

    return df_res


def compute_roc(df: pl.DataFrame, period: int = 12, column: str = "close", output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Rate of Change (ROC)."""
    out = output_col or f"roc_{period}"
    return df.with_columns(
        ((pl.col(column) - pl.col(column).shift(period)) / (pl.col(column).shift(period) + 1e-12) * 100.0).alias(out)
    )


def compute_momentum(df: pl.DataFrame, period: int = 10, column: str = "close", output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute raw price momentum."""
    out = output_col or f"momentum_{period}"
    return df.with_columns(
        (pl.col(column) - pl.col(column).shift(period)).alias(out)
    )


def compute_cci(df: pl.DataFrame, period: int = 20, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Commodity Channel Index (CCI)."""
    out = output_col or f"cci_{period}"
    tp = (pl.col("high") + pl.col("low") + pl.col("close")) / 3.0

    df_temp = df.with_columns(tp.alias("_tp"))
    tp_sma = pl.col("_tp").rolling_mean(window_size=period)

    # Mean absolute deviation: Polars rolling mean of |tp - tp_sma|
    df_temp = df_temp.with_columns(tp_sma.alias("_tp_sma"))
    df_temp = df_temp.with_columns(
        (pl.col("_tp") - pl.col("_tp_sma")).abs().rolling_mean(window_size=period).alias("_tp_mad")
    )

    df_res = df_temp.with_columns(
        ((pl.col("_tp") - pl.col("_tp_sma")) / (0.015 * pl.col("_tp_mad") + 1e-12)).alias(out)
    ).drop(["_tp", "_tp_sma", "_tp_mad"])

    return df_res


def compute_williams_r(df: pl.DataFrame, period: int = 14, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Williams %R (-100 to 0)."""
    out = output_col or f"williams_r_{period}"
    high_max = pl.col("high").rolling_max(window_size=period)
    low_min = pl.col("low").rolling_min(window_size=period)

    return df.with_columns(
        (-100.0 * (high_max - pl.col("close")) / (high_max - low_min + 1e-12)).alias(out)
    )


def compute_mfi(df: pl.DataFrame, period: int = 14, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Money Flow Index (MFI)."""
    out = output_col or f"mfi_{period}"
    tp = (pl.col("high") + pl.col("low") + pl.col("close")) / 3.0
    raw_money_flow = tp * pl.col("volume")

    df_temp = df.with_columns([
        tp.alias("_tp"),
        raw_money_flow.alias("_rmf"),
    ])

    prev_tp = pl.col("_tp").shift(1)
    pos_flow = pl.when(pl.col("_tp") > prev_tp).then(pl.col("_rmf")).otherwise(0.0)
    neg_flow = pl.when(pl.col("_tp") < prev_tp).then(pl.col("_rmf")).otherwise(0.0)

    df_temp = df_temp.with_columns([
        pos_flow.alias("_pos_flow"),
        neg_flow.alias("_neg_flow"),
    ])

    df_temp = df_temp.with_columns([
        pl.col("_pos_flow").rolling_sum(window_size=period).alias("_pos_mf"),
        pl.col("_neg_flow").rolling_sum(window_size=period).alias("_neg_mf"),
    ])

    df_res = df_temp.with_columns(
        (100.0 - (100.0 / (1.0 + (pl.col("_pos_mf") / (pl.col("_neg_mf") + 1e-12))))).alias(out)
    ).drop(["_tp", "_rmf", "_pos_flow", "_neg_flow", "_pos_mf", "_neg_mf"])

    return df_res
