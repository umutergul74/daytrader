"""Smart Money Concepts (SMC) and Market Structure domain models."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class StructureBreakType(str, Enum):
    WICK = "WICK"
    CLOSE = "CLOSE"


class StructureEventType(str, Enum):
    BOS = "BOS"      # Break of Structure
    CHOCH = "CHOCH"  # Change of Character
    MSS = "MSS"      # Market Structure Shift


class FvgDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class FvgMitigationState(str, Enum):
    UNMITIGATED = "UNMITIGATED"
    PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED" # Touched CE (50%)
    FULLY_MITIGATED = "FULLY_MITIGATED"         # Crossed opposite boundary
    INVALIDATED = "INVALIDATED"                 # Broken through completely
    INVERTED = "INVERTED"                       # Acting as support/resistance in reverse


class FairValueGap(BaseModel):
    """Lifecycle-aware Fair Value Gap representation."""
    fvg_id: str
    direction: FvgDirection
    upper_bound: float
    lower_bound: float
    consequent_encroachment: float = Field(description="50% midpoint of the FVG zone")
    gap_size: float
    gap_size_atr: float = 0.0
    created_at_time: int
    available_at_time: int
    creation_bar_index: int
    timeframe: str = "15m"
    mitigation_state: FvgMitigationState = FvgMitigationState.UNMITIGATED
    first_revisit_time: Optional[int] = None
    fully_mitigated_time: Optional[int] = None
    age_bars: int = 0
    is_inverted: bool = False


class LiquidityLevelType(str, Enum):
    SWING_HIGH = "SWING_HIGH"
    SWING_LOW = "SWING_LOW"
    EQUAL_HIGHS = "EQUAL_HIGHS"
    EQUAL_LOWS = "EQUAL_LOWS"
    PREVIOUS_DAY_HIGH = "PDH"
    PREVIOUS_DAY_LOW = "PDL"
    PREVIOUS_WEEK_HIGH = "PWH"
    PREVIOUS_WEEK_LOW = "PWL"
    SESSION_HIGH = "SESSION_HIGH"
    SESSION_LOW = "SESSION_LOW"


class LiquidityLevel(BaseModel):
    """Lifecycle-aware liquidity level."""
    level_id: str
    level_type: LiquidityLevelType
    price: float
    timeframe: str
    tolerance_atr: float = 0.1
    created_at: int
    available_at: int
    touch_count: int = 1
    is_active: bool = True
    swept_at: Optional[int] = None
    reclaimed_at: Optional[int] = None


class SweepEvent(BaseModel):
    """Detected liquidity sweep event."""
    sweep_id: str
    level_id: str
    level_type: LiquidityLevelType
    level_price: float
    sweep_price: float
    overshoot_distance: float
    overshoot_atr: float
    is_reclaimed: bool
    sweep_time: int
    confirmed_time: int
    is_bullish_sweep: bool # True if sell-side swept and price bounced up


class MarketStructureEvent(BaseModel):
    """Causal market structure confirmation event (BOS / CHoCH / MSS)."""
    event_id: str
    event_type: StructureEventType
    break_type: StructureBreakType
    is_bullish: bool
    broken_level_price: float
    break_price: float
    event_time: int
    confirmed_time: int
    timeframe: str
