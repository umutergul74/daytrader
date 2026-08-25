"""Market regime domain models and enums."""

from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class MarketDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class MarketState(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    COMPRESSION = "COMPRESSION"
    EXPANSION = "EXPANSION"
    BREAKOUT = "BREAKOUT"


class VolatilityRegime(str, Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class RegimeSnapshot(BaseModel):
    """Causal point-in-time classification of market state."""
    timestamp: int = Field(description="Availability timestamp in ms UTC")
    direction: MarketDirection = MarketDirection.NEUTRAL
    state: MarketState = MarketState.RANGING
    volatility: VolatilityRegime = VolatilityRegime.NORMAL
    trend_strength: float = Field(default=0.0, description="ADX or normalized slope value")
    atr_percentile: float = Field(default=50.0, description="Rolling ATR percentile (0-100)")
    realized_vol_percentile: float = Field(default=50.0, description="Rolling realized vol percentile (0-100)")
    raw_indicators: Dict[str, Any] = Field(default_factory=dict)
