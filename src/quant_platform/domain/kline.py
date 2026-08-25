"""Kline and OHLCV domain schema."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
import polars as pl


class KlineBar(BaseModel):
    """Immutable representation of a single OHLCV bar."""
    open_time: int = Field(description="Open timestamp in milliseconds UTC")
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int = Field(description="Close timestamp in milliseconds UTC")
    quote_asset_volume: float
    number_of_trades: int
    taker_buy_base_asset_volume: float
    taker_buy_quote_asset_volume: float

    @property
    def open_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.open_time / 1000.0, tz=timezone.utc)

    @property
    def close_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.close_time / 1000.0, tz=timezone.utc)


# Canonical Polars Schema for 1-minute and aggregated klines
CANONICAL_KLINE_SCHEMA = {
    "open_time": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
    "close_time": pl.Int64,
    "quote_asset_volume": pl.Float64,
    "number_of_trades": pl.Int64,
    "taker_buy_base_asset_volume": pl.Float64,
    "taker_buy_quote_asset_volume": pl.Float64,
}
