"""Microstructure Event Domain Models.

Formal domain representations for event-time market data:
 - Aggregate Trades (aggTrades)
 - Open Interest (OI)
 - Liquidation Events (forceOrder)
 - Derivatives Context (Mark, Index, Funding)
"""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import polars as pl


class MicrostructureEventType(str, Enum):
    AGG_TRADE = "AGG_TRADE"
    OPEN_INTEREST = "OPEN_INTEREST"
    LIQUIDATION = "LIQUIDATION"
    DERIVATIVES_CONTEXT = "DERIVATIVES_CONTEXT"
    KLINE = "KLINE"


class AggTradeEvent(BaseModel):
    """Binance USD(S)-M Futures Aggregate Trade event."""
    symbol: str = "ETHUSDT"
    trade_id: int = Field(description="First aggregate trade ID in batch")
    price: float
    quantity: float
    is_buyer_maker: bool = Field(description="True if maker was buyer, i.e., aggressor was seller")
    event_time_ms: int = Field(description="Exchange timestamp in ms UTC")
    received_at_ms: int = Field(description="Local engine receive timestamp in ms UTC")

    @property
    def is_aggressor_buy(self) -> bool:
        """True if the aggressor executed a market buy order."""
        return not self.is_buyer_maker

    @property
    def signed_volume(self) -> float:
        """Signed volume (+ for buyer aggressor, - for seller aggressor)."""
        return self.quantity if self.is_aggressor_buy else -self.quantity


class OpenInterestEvent(BaseModel):
    """Binance USD(S)-M Futures Open Interest event."""
    symbol: str = "ETHUSDT"
    open_interest: float = Field(description="Total open contracts in base asset")
    open_interest_usdt: float = Field(default=0.0, description="Total notional open interest in USDT")
    event_time_ms: int
    received_at_ms: int


class LiquidationEvent(BaseModel):
    """Binance USD(S)-M Futures Forced Order / Liquidation event."""
    symbol: str = "ETHUSDT"
    order_id: str
    side: str # BUY (Short liquidated), SELL (Long liquidated)
    price: float
    quantity: float
    event_time_ms: int
    received_at_ms: int

    @property
    def is_long_liquidation(self) -> bool:
        """True if a long position was liquidated (forced sell)."""
        return self.side.upper() == "SELL"

    @property
    def is_short_liquidation(self) -> bool:
        """True if a short position was liquidated (forced buy)."""
        return self.side.upper() == "BUY"


class DerivativesContextEvent(BaseModel):
    """Binance USD(S)-M Mark Price, Index Price, and Funding Rate event."""
    symbol: str = "ETHUSDT"
    mark_price: float
    index_price: float
    funding_rate: float
    next_funding_time_ms: int
    event_time_ms: int
    received_at_ms: int


AGG_TRADE_SCHEMA = {
    "trade_id": pl.Int64,
    "price": pl.Float64,
    "quantity": pl.Float64,
    "is_buyer_maker": pl.Boolean,
    "event_time_ms": pl.Int64,
    "received_at_ms": pl.Int64,
}

OPEN_INTEREST_SCHEMA = {
    "open_interest": pl.Float64,
    "open_interest_usdt": pl.Float64,
    "event_time_ms": pl.Int64,
    "received_at_ms": pl.Int64,
}

LIQUIDATION_SCHEMA = {
    "order_id": pl.Utf8,
    "side": pl.Utf8,
    "price": pl.Float64,
    "quantity": pl.Float64,
    "event_time_ms": pl.Int64,
    "received_at_ms": pl.Int64,
}
