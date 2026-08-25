"""Displacement Calculation Engine in Polars."""

from typing import Optional
import numpy as np
import polars as pl

from quant_platform.features.indicators.volatility import compute_atr, compute_candle_metrics
from quant_platform.features.indicators.volume import compute_relative_volume


class DisplacementEngine:
    """Computes quantitative displacement metrics."""

    @staticmethod
    def compute_displacement(
        df: pl.DataFrame,
        atr_period: int = 14,
        min_body_ratio: float = 0.6,
        min_range_atr: float = 1.3,
        min_rvol: float = 1.2,
    ) -> pl.DataFrame:
        """Compute displacement flags and composite score."""
        atr_col = f"_disp_atr_{atr_period}"
        rvol_col = f"_disp_rvol_{atr_period}"

        df_calc = compute_atr(df, period=atr_period, output_col=atr_col)
        df_calc = compute_candle_metrics(df_calc)
        df_calc = compute_relative_volume(df_calc, period=atr_period, output_col=rvol_col)

        candle_range = pl.col("high") - pl.col("low")
        range_atr = candle_range / (pl.col(atr_col) + 1e-12)

        bullish_disp = (
            pl.col("is_bullish_candle")
            & (pl.col("body_to_range_ratio") >= min_body_ratio)
            & (range_atr >= min_range_atr)
            & (pl.col(rvol_col) >= min_rvol)
        )

        bearish_disp = (
            (~pl.col("is_bullish_candle"))
            & (pl.col("body_to_range_ratio") >= min_body_ratio)
            & (range_atr >= min_range_atr)
            & (pl.col(rvol_col) >= min_rvol)
        )

        # Composite score
        disp_score = (
            pl.col("body_to_range_ratio") * 0.4
            + (range_atr / 2.0).clip(0.0, 1.5) * 0.3
            + (pl.col(rvol_col) / 2.0).clip(0.0, 1.5) * 0.3
        )

        df_res = df_calc.with_columns([
            range_atr.alias("range_atr_ratio"),
            bullish_disp.alias("is_bullish_displacement"),
            bearish_disp.alias("is_bearish_displacement"),
            disp_score.alias("displacement_score"),
        ]).drop([atr_col, rvol_col])

        return df_res
