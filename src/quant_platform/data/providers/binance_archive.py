"""Binance Public Archive Data Provider.

Downloads official historical archives from data.binance.vision with SHA-256
checksum verification, atomic writes, and extraction into canonical DataFrames.
"""

import hashlib
import io
import zipfile
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Tuple
import httpx
import polars as pl

from quant_platform.config.constants import BINANCE_PUBLIC_DATA_BASE_URL
from quant_platform.config.settings import settings
from quant_platform.domain.market import MarketIdentity
from quant_platform.domain.kline import CANONICAL_KLINE_SCHEMA
from quant_platform.data.providers.base import BaseDataProvider
from quant_platform.observability.logger import logger


class BinancePublicArchiveProvider(BaseDataProvider):
    """Downloads authoritative bulk history from data.binance.vision."""

    def __init__(self, raw_cache_dir: Optional[Path] = None):
        self.raw_cache_dir = raw_cache_dir or (settings.raw_data_dir / "binance_archive")
        self.raw_cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)

    def _get_monthly_url(self, symbol: str, timeframe: str, year: int, month: int) -> str:
        month_str = f"{month:02d}"
        filename = f"{symbol}-{timeframe}-{year}-{month_str}.zip"
        return f"{BINANCE_PUBLIC_DATA_BASE_URL}/monthly/klines/{symbol}/{timeframe}/{filename}"

    def _get_daily_url(self, symbol: str, timeframe: str, dt: date) -> str:
        filename = f"{symbol}-{timeframe}-{dt.strftime('%Y-%m-%d')}.zip"
        return f"{BINANCE_PUBLIC_DATA_BASE_URL}/daily/klines/{symbol}/{timeframe}/{filename}"

    def _download_with_checksum(self, url: str, target_zip: Path) -> bool:
        """Download zip archive and verify against official .CHECKSUM file if available."""
        if target_zip.exists():
            return True

        checksum_url = f"{url}.CHECKSUM"
        expected_checksum: Optional[str] = None

        # Try fetching checksum
        try:
            r_chk = self.client.get(checksum_url)
            if r_chk.status_code == 200:
                expected_checksum = r_chk.text.strip().split()[0]
        except Exception as e:
            logger.debug(f"Could not fetch checksum from {checksum_url}: {e}")

        # Download ZIP
        part_file = target_zip.with_suffix(".zip.part")
        try:
            logger.info(f"Downloading archive: {url}")
            r = self.client.get(url)
            if r.status_code != 200:
                logger.warning(f"Archive not found or HTTP {r.status_code} for {url}")
                return False

            part_file.write_bytes(r.content)

            # Verify checksum
            if expected_checksum:
                actual_sha256 = hashlib.sha256(r.content).hexdigest()
                if actual_sha256.lower() != expected_checksum.lower():
                    logger.error(f"Checksum mismatch for {url}: expected {expected_checksum}, got {actual_sha256}")
                    part_file.unlink(missing_ok=True)
                    return False

            # Atomic rename
            part_file.rename(target_zip)
            return True
        except Exception as e:
            logger.error(f"Failed downloading {url}: {e}")
            part_file.unlink(missing_ok=True)
            return False

    def parse_archive_zip(self, zip_path: Path) -> pl.DataFrame:
        """Parse raw CSV from inside Binance ZIP into typed Polars DataFrame."""
        with zipfile.ZipFile(zip_path, 'r') as z:
            csv_filenames = [f for f in z.namelist() if f.endswith('.csv')]
            if not csv_filenames:
                raise ValueError(f"No CSV found inside {zip_path}")
            csv_bytes = z.read(csv_filenames[0])

        # Read CSV with Polars
        # Binance format: open_time, open, high, low, close, volume, close_time,
        # quote_volume, count, taker_buy_volume, taker_buy_quote_volume, ignore
        raw_df = pl.read_csv(
            io.BytesIO(csv_bytes),
            has_header=False,
            infer_schema_length=1000,
        )

        # If the first row contains string headers (e.g. "open_time"), strip it
        first_val = str(raw_df[0, 0])
        if "open_time" in first_val.lower() or not first_val.replace(".", "").isdigit():
            raw_df = raw_df.slice(1)

        # Standardize columns
        cols = [
            "open_time", "open", "high", "low", "close", "volume", "close_time",
            "quote_asset_volume", "number_of_trades", "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume"
        ]

        # Select first 11 columns
        selected = raw_df.select([raw_df.columns[i] for i in range(11)])
        selected.columns = cols

        # Cast to canonical types
        df = selected.with_columns([
            pl.col("open_time").cast(pl.Int64),
            pl.col("open").cast(pl.Float64),
            pl.col("high").cast(pl.Float64),
            pl.col("low").cast(pl.Float64),
            pl.col("close").cast(pl.Float64),
            pl.col("volume").cast(pl.Float64),
            pl.col("close_time").cast(pl.Int64),
            pl.col("quote_asset_volume").cast(pl.Float64),
            pl.col("number_of_trades").cast(pl.Int64),
            pl.col("taker_buy_base_asset_volume").cast(pl.Float64),
            pl.col("taker_buy_quote_asset_volume").cast(pl.Float64),
        ]).sort("open_time")

        return df

    def fetch_month(self, symbol: str, timeframe: str, year: int, month: int) -> Optional[pl.DataFrame]:
        """Fetch and parse single monthly archive."""
        url = self._get_monthly_url(symbol, timeframe, year, month)
        dest = self.raw_cache_dir / f"{symbol}-{timeframe}-{year}-{month:02d}.zip"
        success = self._download_with_checksum(url, dest)
        if not success or not dest.exists():
            return None
        return self.parse_archive_zip(dest)

    def fetch_klines(
        self,
        market: MarketIdentity,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> pl.DataFrame:
        """Fetch monthly archives covering the range."""
        frames: List[pl.DataFrame] = []
        current = datetime(start_time.year, start_time.month, 1)
        end_month = datetime(end_time.year, end_time.month, 1)

        while current <= end_month:
            df = self.fetch_month(market.symbol, timeframe, current.year, current.month)
            if df is not None and not df.is_empty():
                frames.append(df)

            # Advance 1 month
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)

        if not frames:
            return pl.DataFrame(schema=CANONICAL_KLINE_SCHEMA)

        combined = pl.concat(frames).unique(subset=["open_time"]).sort("open_time")

        # Filter to requested range
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        return combined.filter(
            (pl.col("open_time") >= start_ms) & (pl.col("open_time") <= end_ms)
        )
