"""Trend and Moving Average Indicators in Polars."""

from typing import Optional, Tuple
import numpy as np
import polars as pl
from quant_platform.features.indicators.volatility import compute_atr


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


def compute_vwma(df: pl.DataFrame, period: int = 20, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute Volume-Weighted Moving Average (VWMA)."""
    out = output_col or f"vwma_{period}"
    df_temp = df.with_columns(
        (pl.col("close") * pl.col("volume")).alias("_pv")
    )
    df_res = df_temp.with_columns(
        (pl.col("_pv").rolling_mean(window_size=period) / (pl.col("volume").rolling_mean(window_size=period) + 1e-12)).alias(out)
    ).drop(["_pv"])
    return df_res


def compute_ema_slope(df: pl.DataFrame, period: int = 20, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute normalized slope of EMA in percentage change."""
    ema_col = f"_ema_{period}"
    out = output_col or f"ema_slope_{period}"
    df_temp = compute_ema(df, period=period, output_col=ema_col)
    df_res = df_temp.with_columns(
        ((pl.col(ema_col) - pl.col(ema_col).shift(1)) / (pl.col(ema_col).shift(1) + 1e-12) * 100.0).alias(out)
    ).drop([ema_col])
    return df_res


def compute_ma_distance(df: pl.DataFrame, period: int = 20, output_col: Optional[str] = None) -> pl.DataFrame:
    """Compute percentage distance between close and EMA."""
    ema_col = f"_ema_{period}"
    out = output_col or f"ma_dist_{period}"
    df_temp = compute_ema(df, period=period, output_col=ema_col)
    df_res = df_temp.with_columns(
        ((pl.col("close") - pl.col(ema_col)) / (pl.col(ema_col) + 1e-12) * 100.0).alias(out)
    ).drop([ema_col])
    return df_res


def compute_adx(df: pl.DataFrame, period: int = 14) -> pl.DataFrame:
    """Compute Average Directional Index (ADX), +DI, -DI using Wilder's smoothing."""
    # TR, +DM, -DM
    up_move = pl.col("high") - pl.col("high").shift(1)
    down_move = pl.col("low").shift(1) - pl.col("low")

    plus_dm = pl.when((up_move > down_move) & (up_move > 0)).then(up_move).otherwise(0.0)
    minus_dm = pl.when((down_move > up_move) & (down_move > 0)).then(down_move).otherwise(0.0)

    # TR
    prev_close = pl.col("close").shift(1)
    tr = pl.max_horizontal([
        pl.col("high") - pl.col("low"),
        (pl.col("high") - prev_close).abs(),
        (pl.col("low") - prev_close).abs(),
    ])

    df_temp = df.with_columns([
        plus_dm.alias("_p_dm"),
        minus_dm.alias("_m_dm"),
        tr.alias("_tr"),
    ])

    # Smoothed TR, +DM, -DM (alpha = 1 / period)
    df_temp = df_temp.with_columns([
        pl.col("_tr").ewm_mean(alpha=1.0 / period, adjust=False).alias("_str"),
        pl.col("_p_dm").ewm_mean(alpha=1.0 / period, adjust=False).alias("_sp_dm"),
        pl.col("_m_dm").ewm_mean(alpha=1.0 / period, adjust=False).alias("_sm_dm"),
    ])

    df_temp = df_temp.with_columns([
        (100.0 * pl.col("_sp_dm") / (pl.col("_str") + 1e-12)).alias(f"plus_di_{period}"),
        (100.0 * pl.col("_sm_dm") / (pl.col("_str") + 1e-12)).alias(f"minus_di_{period}"),
    ])

    # DX = 100 * |+DI - -DI| / (|+DI + -DI|)
    plus_di = pl.col(f"plus_di_{period}")
    minus_di = pl.col(f"minus_di_{period}")
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-12)

    df_temp = df_temp.with_columns(dx.alias("_dx"))
    df_res = df_temp.with_columns(
        pl.col("_dx").ewm_mean(alpha=1.0 / period, adjust=False).alias(f"adx_{period}")
    ).drop(["_p_dm", "_m_dm", "_tr", "_str", "_sp_dm", "_sm_dm", "_dx"])

    return df_res


def compute_aroon(df: pl.DataFrame, period: int = 14) -> pl.DataFrame:
    """Compute Aroon Up, Aroon Down, and Aroon Oscillator."""
    # Rolling index of max high and min low
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    n = len(df)

    aroon_up = np.full(n, np.nan, dtype=np.float64)
    aroon_down = np.full(n, np.nan, dtype=np.float64)

    for i in range(period, n):
        window_highs = highs[i - period : i + 1]
        window_lows = lows[i - period : i + 1]
        # index from start of window
        max_idx = np.argmax(window_highs)
        min_idx = np.argmin(window_lows)

        # periods since highest/lowest
        since_high = period - max_idx
        since_low = period - min_idx

        aroon_up[i] = ((period - since_high) / period) * 100.0
        aroon_down[i] = ((period - since_low) / period) * 100.0

    aroon_osc = aroon_up - aroon_down

    return df.with_columns([
        pl.Series(name=f"aroon_up_{period}", values=aroon_up),
        pl.Series(name=f"aroon_down_{period}", values=aroon_down),
        pl.Series(name=f"aroon_osc_{period}", values=aroon_osc),
    ])


def compute_supertrend(df: pl.DataFrame, atr_period: int = 10, factor: float = 3.0) -> pl.DataFrame:
    """Compute Supertrend indicator (line and trend direction: 1=bullish, -1=bearish)."""
    atr_col = f"_st_atr_{atr_period}"
    df_calc = compute_atr(df, period=atr_period, output_col=atr_col)

    highs = df_calc["high"].to_numpy()
    lows = df_calc["low"].to_numpy()
    closes = df_calc["close"].to_numpy()
    atrs = df_calc[atr_col].to_numpy()
    n = len(df)

    st_line = np.full(n, np.nan, dtype=np.float64)
    st_dir = np.zeros(n, dtype=np.int32)

    upper_band = np.zeros(n, dtype=np.float64)
    lower_band = np.zeros(n, dtype=np.float64)

    trend = 1
    for i in range(n):
        if np.isnan(atrs[i]):
            continue

        hl2 = (highs[i] + lows[i]) / 2.0
        basic_upper = hl2 + (factor * atrs[i])
        basic_lower = hl2 - (factor * atrs[i])

        if i == 0 or np.isnan(upper_band[i - 1]):
            upper_band[i] = basic_upper
            lower_band[i] = basic_lower
        else:
            upper_band[i] = basic_upper if (basic_upper < upper_band[i - 1] or closes[i - 1] > upper_band[i - 1]) else upper_band[i - 1]
            lower_band[i] = basic_lower if (basic_lower > lower_band[i - 1] or closes[i - 1] < lower_band[i - 1]) else lower_band[i - 1]

        # Determine trend direction
        if trend == 1:
            if closes[i] < lower_band[i]:
                trend = -1
                st_line[i] = upper_band[i]
            else:
                st_line[i] = lower_band[i]
        else:
            if closes[i] > upper_band[i]:
                trend = 1
                st_line[i] = lower_band[i]
            else:
                st_line[i] = upper_band[i]

        st_dir[i] = trend

    return df_calc.with_columns([
        pl.Series(name=f"supertrend_line_{atr_period}_{factor}", values=st_line),
        pl.Series(name=f"supertrend_dir_{atr_period}_{factor}", values=st_dir),
    ]).drop([atr_col])
