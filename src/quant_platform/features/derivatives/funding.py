"""Derivatives and Funding Rate Feature Engineering in Polars."""

from typing import Optional
import polars as pl


def compute_funding_features(
    df: pl.DataFrame,
    funding_col: str = "funding_rate",
    period: int = 24, # 24 periods = 8 days if 8h funding
) -> pl.DataFrame:
    """Compute rolling funding mean, z-score, momentum, and extreme funding flags."""
    if funding_col not in df.columns:
        # Graceful zero-fill if funding data not in klines
        return df.with_columns([
            pl.lit(0.0).alias("funding_zscore"),
            pl.lit(False).alias("is_extreme_positive_funding"),
            pl.lit(False).alias("is_extreme_negative_funding"),
        ])

    mean_col = f"_fnd_mean_{period}"
    std_col = f"_fnd_std_{period}"

    df_temp = df.with_columns([
        pl.col(funding_col).rolling_mean(window_size=period).alias(mean_col),
        pl.col(funding_col).rolling_std(window_size=period).alias(std_col),
    ])

    df_res = df_temp.with_columns([
        ((pl.col(funding_col) - pl.col(mean_col)) / (pl.col(std_col) + 1e-12)).alias("funding_zscore"),
        (pl.col(funding_col) - pl.col(funding_col).shift(1)).alias("funding_momentum"),
        (pl.col(funding_col) >= 0.0003).alias("is_extreme_positive_funding"), # > +0.03% / 8h
        (pl.col(funding_col) <= -0.0003).alias("is_extreme_negative_funding"), # < -0.03% / 8h
    ]).drop([mean_col, std_col])

    return df_res
