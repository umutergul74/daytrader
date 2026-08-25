"""Features subsystem package."""

from quant_platform.features.base import BaseFeature, FeatureMetadata
from quant_platform.features.catalog import FeatureCatalog
from quant_platform.features.indicators import (
    compute_sma,
    compute_ema,
    compute_wma,
    compute_hma,
    compute_rsi,
    compute_macd,
    compute_stochastic,
    compute_atr,
    compute_bollinger_bands,
    compute_realized_volatility,
    compute_volume_zscore,
    compute_relative_volume,
    compute_obv,
)
from quant_platform.features.structure.swings import CausalSwingEngine, SwingPoint

__all__ = [
    "BaseFeature",
    "FeatureMetadata",
    "FeatureCatalog",
    "compute_sma",
    "compute_ema",
    "compute_wma",
    "compute_hma",
    "compute_rsi",
    "compute_macd",
    "compute_stochastic",
    "compute_atr",
    "compute_bollinger_bands",
    "compute_realized_volatility",
    "compute_volume_zscore",
    "compute_relative_volume",
    "compute_obv",
    "CausalSwingEngine",
    "SwingPoint",
]
