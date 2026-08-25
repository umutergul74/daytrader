"""Order, position, and trade execution domain models."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class ExitReason(str, Enum):
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    SIGNAL_REVERSAL = "SIGNAL_REVERSAL"
    EXPIRY = "EXPIRY"
    MAX_HOLDING_TIME = "MAX_HOLDING_TIME"
    EMERGENCY_EXIT = "EMERGENCY_EXIT"


class TradeRecord(BaseModel):
    """Detailed lifecycle record of an executed trade."""
    trade_id: str
    signal_id: str
    strategy_id: str
    symbol: str
    side: PositionSide
    entry_time: int = Field(description="Entry timestamp in ms UTC")
    exit_time: int = Field(description="Exit timestamp in ms UTC")
    entry_price: float
    exit_price: float
    quantity: float
    notional_entry: float
    notional_exit: float
    fee_paid: float
    slippage_paid: float
    funding_paid: float = 0.0
    gross_pnl: float
    net_pnl: float
    pnl_percent: float
    r_multiple: float
    mfe: float = Field(default=0.0, description="Maximum Favorable Excursion")
    mae: float = Field(default=0.0, description="Maximum Adverse Excursion")
    exit_reason: ExitReason
    holding_period_minutes: float
    regime_at_entry: Dict[str, Any] = Field(default_factory=dict)
