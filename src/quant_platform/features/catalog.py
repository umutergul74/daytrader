"""Evidence-Aware Feature Catalog and Lifecycle Registry."""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class FeatureLifecycle(str, Enum):
    DISCOVERED = "DISCOVERED"
    SPECIFIED = "SPECIFIED"
    IMPLEMENTED = "IMPLEMENTED"
    UNIT_TESTED = "UNIT_TESTED"
    CAUSALITY_TESTED = "CAUSALITY_TESTED"
    BACKTESTED = "BACKTESTED"
    ROBUSTNESS_TESTED = "ROBUSTNESS_TESTED"
    ACCEPTED = "ACCEPTED"
    CONDITIONAL = "CONDITIONAL"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class FeatureMetadata(BaseModel):
    """Machine-readable metadata and evidence tracking for a quantitative feature."""
    feature_id: str
    version: str = "v1"
    category: str # "trend", "momentum", "volatility", "volume", "structure", "smc", "regime", "time_session", "derivatives"
    mathematical_definition: str
    source_implementation: str
    required_timeframe: str = "15m"
    parameter_schema: Dict[str, Any] = Field(default_factory=dict)
    availability_semantics: str = "close_time + 1"
    causality_status: str = "STRICTLY_CAUSAL"
    lifecycle_status: FeatureLifecycle = FeatureLifecycle.IMPLEMENTED
    experiment_count: int = 0
    evidence_summary: str = "Pending empirical testing in Milestone 2."
    failure_modes: List[str] = Field(default_factory=list)


class FeatureCatalog:
    """Central registry of quantitative feature definitions and accumulated evidence."""

    _features: Dict[str, FeatureMetadata] = {}

    @classmethod
    def register(cls, metadata: FeatureMetadata) -> None:
        key = f"{metadata.feature_id}:{metadata.version}"
        cls._features[key] = metadata

    @classmethod
    def get(cls, feature_id: str, version: str = "v1") -> Optional[FeatureMetadata]:
        return cls._features.get(f"{feature_id}:{version}")

    @classmethod
    def list_all(cls) -> List[FeatureMetadata]:
        return list(cls._features.values())

    @classmethod
    def list_by_status(cls, status: FeatureLifecycle) -> List[FeatureMetadata]:
        return [f for f in cls._features.values() if f.lifecycle_status == status]

    @classmethod
    def update_evidence(cls, feature_id: str, version: str, status: FeatureLifecycle, summary: str) -> None:
        key = f"{feature_id}:{version}"
        if key in cls._features:
            feat = cls._features[key]
            feat.lifecycle_status = status
            feat.evidence_summary = summary
            feat.experiment_count += 1


# --- Default Registry Population ---

# SMC Primitives
FeatureCatalog.register(FeatureMetadata(
    feature_id="smc:fvg_three_candle",
    version="v1",
    category="smc",
    mathematical_definition="Bullish: Low[i] > High[i-2], Bearish: High[i] < Low[i-2]",
    source_implementation="quant_platform.features.smc.fvg.FvgEngine",
    parameter_schema={"atr_period": 14, "min_gap_atr_ratio": 0.2},
    lifecycle_status=FeatureLifecycle.CAUSALITY_TESTED,
    evidence_summary="Lifecycle-aware 3-candle FVG engine with 50% CE mitigation tracking.",
))

FeatureCatalog.register(FeatureMetadata(
    feature_id="smc:displacement",
    version="v1",
    category="smc",
    mathematical_definition="Body/Range >= 0.6 and Range/ATR >= 1.3 and RVOL >= 1.2",
    source_implementation="quant_platform.features.smc.displacement.DisplacementEngine",
    parameter_schema={"min_body_ratio": 0.6, "min_range_atr": 1.3, "min_rvol": 1.2},
    lifecycle_status=FeatureLifecycle.CAUSALITY_TESTED,
))

FeatureCatalog.register(FeatureMetadata(
    feature_id="smc:liquidity_sweep",
    version="v1",
    category="smc",
    mathematical_definition="Price trades beyond confirmed swing level then reclaims inside",
    source_implementation="quant_platform.features.smc.liquidity.LiquidityEngine",
    parameter_schema={"left_bars": 5, "right_bars": 5, "atr_period": 14},
    lifecycle_status=FeatureLifecycle.CAUSALITY_TESTED,
))

FeatureCatalog.register(FeatureMetadata(
    feature_id="structure:bos_choch",
    version="v1",
    category="structure",
    mathematical_definition="Break of structural swing highs/lows by wick or close",
    source_implementation="quant_platform.features.structure.market_structure.MarketStructureEngine",
    parameter_schema={"left_bars": 5, "right_bars": 5},
    lifecycle_status=FeatureLifecycle.CAUSALITY_TESTED,
))

FeatureCatalog.register(FeatureMetadata(
    feature_id="regime:rules",
    version="v1",
    category="regime",
    mathematical_definition="Multi-dimensional classification into Bullish/Bearish/Neutral, Trending/Ranging, and Volatility buckets",
    source_implementation="quant_platform.regimes.engine.MarketRegimeEngine",
    parameter_schema={"adx_period": 14, "vol_lookback": 100},
    lifecycle_status=FeatureLifecycle.CAUSALITY_TESTED,
))

FeatureCatalog.register(FeatureMetadata(
    feature_id="time_session:utc",
    version="v1",
    category="time_session",
    mathematical_definition="Asia (00-08 UTC), London (07-15 UTC), NY (13-21 UTC), Overlap (13-15 UTC)",
    source_implementation="quant_platform.features.time_session.engine.TimeSessionEngine",
    lifecycle_status=FeatureLifecycle.CAUSALITY_TESTED,
))
