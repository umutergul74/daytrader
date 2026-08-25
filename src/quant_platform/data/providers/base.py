"""Abstract BaseDataProvider."""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
import polars as pl
from quant_platform.domain.market import MarketIdentity


class BaseDataProvider(ABC):
    """Abstract data provider for historical and live market data."""

    @abstractmethod
    def fetch_klines(
        self,
        market: MarketIdentity,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> pl.DataFrame:
        """Fetch raw kline data within time range."""
        pass
