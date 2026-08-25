"""Causal Market Regime Classifier Engine."""

from typing import Optional, Dict, Any
import numpy as np
import polars as pl

from quant_platform.domain.regime import (
    MarketDirection,
    MarketState,
    VolatilityRegime,
    RegimeSnapshot,
)
from quant_platform.features.indicators.trend import compute_adx, compute_ema_slope
from quant_platform.features.indicators.volatility import (
    compute_atr,
    compute_bollinger_bands,
    compute_donchian_channels,
    compute_volatility_percentiles,
)
from quant_platform.features.structure.market_structure import MarketStructureEngine


class MarketRegimeEngine:
    """Causally classifies market direction, market state, and volatility regime."""

    @classmethod
    def classify_regimes(
        cls,
        df: pl.DataFrame,
        adx_period: int = 14,
        adx_trend_threshold: float = 22.0,
        vol_lookback: int = 100,
    ) -> pl.DataFrame:
        """Enrich dataset with point-in-time causal market regime classifications."""
        # 1. Compute required underlying indicators
        df_calc = compute_adx(df, period=adx_period)
        df_calc = compute_ema_slope(df_calc, period=20, output_col="_ema_slope")
        df_calc = compute_bollinger_bands(df_calc, period=20)
        df_calc = compute_donchian_channels(df_calc, period=20)
        df_calc = compute_volatility_percentiles(df_calc, lookback=vol_lookback)
        df_calc = MarketStructureEngine.compute_market_structure(df_calc)

        # 2. Extract series for vector/numpy classification
        adx_vals = df_calc[f"adx_{adx_period}"].to_numpy()
        plus_di = df_calc[f"plus_di_{adx_period}"].to_numpy()
        minus_di = df_calc[f"minus_di_{adx_period}"].to_numpy()
        ema_slopes = df_calc["_ema_slope"].to_numpy()
        struct_trends = df_calc["structural_trend"].to_numpy()
        bb_widths = df_calc["bb_width_20"].to_numpy()
        donchian_widths = df_calc["donchian_width_20"].to_numpy()
        atr_pctiles = df_calc[f"atr_percentile_{vol_lookback}"].to_numpy()
        n = len(df)

        directions = []
        states = []
        volatilities = []
        regime_tags = []

        for i in range(n):
            # A. Direction Classification
            st_trend = struct_trends[i]
            e_slope = ema_slopes[i] if not np.isnan(ema_slopes[i]) else 0.0
            p_di = plus_di[i] if not np.isnan(plus_di[i]) else 0.0
            m_di = minus_di[i] if not np.isnan(minus_di[i]) else 0.0

            if st_trend == 1 or (e_slope > 0.05 and p_di > m_di):
                direction = MarketDirection.BULLISH
            elif st_trend == -1 or (e_slope < -0.05 and m_di > p_di):
                direction = MarketDirection.BEARISH
            else:
                direction = MarketDirection.NEUTRAL

            # B. State Classification
            adx_v = adx_vals[i] if not np.isnan(adx_vals[i]) else 0.0
            bb_w = bb_widths[i] if not np.isnan(bb_widths[i]) else 0.0
            atr_pct = atr_pctiles[i] if not np.isnan(atr_pctiles[i]) else 50.0

            if adx_v >= adx_trend_threshold:
                state = MarketState.TRENDING
            elif atr_pct <= 20.0 or bb_w < 0.02:
                state = MarketState.COMPRESSION
            elif atr_pct >= 80.0:
                state = MarketState.EXPANSION
            else:
                state = MarketState.RANGING

            # C. Volatility Classification
            if atr_pct < 15.0:
                vol = VolatilityRegime.VERY_LOW
            elif atr_pct < 35.0:
                vol = VolatilityRegime.LOW
            elif atr_pct < 70.0:
                vol = VolatilityRegime.NORMAL
            elif atr_pct < 90.0:
                vol = VolatilityRegime.HIGH
            else:
                vol = VolatilityRegime.EXTREME

            directions.append(direction.value)
            states.append(state.value)
            volatilities.append(vol.value)
            regime_tags.append(f"{direction.value}_{state.value}_{vol.value}")

        df_res = df_calc.with_columns([
            pl.Series(name="regime_direction", values=directions),
            pl.Series(name="regime_state", values=states),
            pl.Series(name="regime_volatility", values=volatilities),
            pl.Series(name="regime_tag", values=regime_tags),
        ]).drop(["_ema_slope"])

        return df_res
