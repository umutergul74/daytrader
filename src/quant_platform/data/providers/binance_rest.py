"""Binance Futures REST Data Provider for incremental updates and gap repairs."""

from datetime import datetime
import time
from typing import Optional, List
import httpx
import polars as pl

from quant_platform.config.constants import BINANCE_FUTURES_REST_BASE_URL
from quant_platform.domain.market import MarketIdentity
from quant_platform.domain.kline import CANONICAL_KLINE_SCHEMA
from quant_platform.data.providers.base import BaseDataProvider
from quant_platform.observability.logger import logger


class BinanceFuturesRestProvider(BaseDataProvider):
    """Fetches real-time / recent historical klines from official Binance USD-M REST API."""

    def __init__(self, base_url: str = BINANCE_FUTURES_REST_BASE_URL):
        self.base_url = base_url
        self.client = httpx.Client(base_url=self.base_url, timeout=15.0)

    def fetch_klines_chunk(
        self,
        symbol: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: Optional[int] = None,
        limit: int = 1500,
    ) -> pl.DataFrame:
        """Fetch a single chunk of klines up to limit (1500 max)."""
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "startTime": start_time_ms,
            "limit": min(limit, 1500),
        }
        if end_time_ms:
            params["endTime"] = end_time_ms

        endpoint = "/fapi/v1/klines"
        for attempt in range(3):
            try:
                response = self.client.get(endpoint, params=params)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "5"))
                    logger.warning(f"Rate limited by Binance. Sleeping {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()
                if not data:
                    return pl.DataFrame(schema=CANONICAL_KLINE_SCHEMA)

                # Format of Binance /fapi/v1/klines:
                # [
                #   [0: open_time, 1: open, 2: high, 3: low, 4: close, 5: volume,
                #    6: close_time, 7: quote_volume, 8: count, 9: taker_buy_volume,
                #    10: taker_buy_quote_volume, 11: ignore]
                # ]
                rows = []
                for row in data:
                    rows.append({
                        "open_time": int(row[0]),
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]),
                        "close_time": int(row[6]),
                        "quote_asset_volume": float(row[7]),
                        "number_of_trades": int(row[8]),
                        "taker_buy_base_asset_volume": float(row[9]),
                        "taker_buy_quote_asset_volume": float(row[10]),
                    })

                df = pl.DataFrame(rows, schema=CANONICAL_KLINE_SCHEMA)
                return df.sort("open_time")
            except Exception as e:
                logger.warning(f"Attempt {attempt+1}/3 failed for REST klines: {e}")
                time.sleep(1.0 * (attempt + 1))

        logger.error(f"Failed to fetch klines from REST after 3 attempts.")
        return pl.DataFrame(schema=CANONICAL_KLINE_SCHEMA)

    def fetch_klines(
        self,
        market: MarketIdentity,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> pl.DataFrame:
        """Paginate across the entire requested range."""
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        current_ms = start_ms

        frames: List[pl.DataFrame] = []

        while current_ms < end_ms:
            df = self.fetch_klines_chunk(
                symbol=market.symbol,
                interval=timeframe,
                start_time_ms=current_ms,
                end_time_ms=end_ms,
                limit=1500,
            )
            if df.is_empty():
                break

            frames.append(df)
            last_open = df["open_time"].max()
            if last_open is None or last_open <= current_ms:
                break

            # 1m step advance
            current_ms = int(last_open) + 60000
            time.sleep(0.05)  # slight spacing for rate limits

        if not frames:
            return pl.DataFrame(schema=CANONICAL_KLINE_SCHEMA)

        combined = pl.concat(frames).unique(subset=["open_time"]).sort("open_time")
        return combined.filter(
            (pl.col("open_time") >= start_ms) & (pl.col("open_time") <= end_ms)
        )
