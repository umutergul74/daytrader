"""Machine-readable Feature Catalog."""

from typing import Dict, List, Optional
from quant_platform.features.base import FeatureMetadata


class FeatureCatalog:
    """Catalog of registered, versioned, and audited quantitative features."""

    _registry: Dict[str, FeatureMetadata] = {}

    @classmethod
    def register(cls, metadata: FeatureMetadata) -> None:
        cls._registry[metadata.feature_id] = metadata

    @classmethod
    def get(cls, feature_id: str) -> Optional[FeatureMetadata]:
        return cls._registry.get(feature_id)

    @classmethod
    def list_features(cls) -> List[FeatureMetadata]:
        return list(cls._registry.values())


# Register core features
FeatureCatalog.register(FeatureMetadata(
    feature_id="technical:ema:v1",
    version="v1",
    category="trend",
    name="Exponential Moving Average",
    description="Vectorized exponential moving average with span parameter",
    parameters={"period": 20},
    lookback_bars=20,
    causality_status="strictly_causal",
))

FeatureCatalog.register(FeatureMetadata(
    feature_id="technical:rsi:v1",
    version="v1",
    category="momentum",
    name="Relative Strength Index",
    description="Wilder's smoothed 14-period RSI",
    parameters={"period": 14},
    lookback_bars=14,
    causality_status="strictly_causal",
))

FeatureCatalog.register(FeatureMetadata(
    feature_id="technical:atr:v1",
    version="v1",
    category="volatility",
    name="Average True Range",
    description="Wilder's smoothed 14-period True Range and NATR",
    parameters={"period": 14},
    lookback_bars=14,
    causality_status="strictly_causal",
))

FeatureCatalog.register(FeatureMetadata(
    feature_id="technical:bollinger:v1",
    version="v1",
    category="volatility",
    name="Bollinger Bands",
    description="20-period moving average with 2.0 std deviation bands and bandwidth",
    parameters={"period": 20, "num_std": 2.0},
    lookback_bars=20,
    causality_status="strictly_causal",
))

FeatureCatalog.register(FeatureMetadata(
    feature_id="structure:causal_swing:v1",
    version="v1",
    category="structure",
    name="Causal Swing High / Swing Low",
    description="Fractal pivots with Left=5, Right=5 confirmation delay",
    parameters={"left_bars": 5, "right_bars": 5},
    lookback_bars=11,
    causality_status="confirmed_delay",
))
