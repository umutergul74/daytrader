"""Canonical Parquet Storage Engine."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import polars as pl

from quant_platform.domain.kline import CANONICAL_KLINE_SCHEMA
from quant_platform.data.storage.paths import (
    get_canonical_dataset_dir,
    get_canonical_month_partition_dir,
)
from quant_platform.observability.logger import logger


class CanonicalStorage:
    """Read and write partitioned canonical Parquet datasets."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir

    def write_month_partition(
        self,
        df: pl.DataFrame,
        year: int,
        month: int,
        market: str = "binance_usdm",
        symbol: str = "ETHUSDT",
        dataset: str = "contract_klines",
        timeframe: str = "1m",
    ) -> Path:
        """Write DataFrame into canonical monthly partition."""
        if df.is_empty():
            raise ValueError(f"Cannot write empty DataFrame for {year}-{month:02d}")

        partition_dir = get_canonical_month_partition_dir(
            year=year,
            month=month,
            market=market,
            symbol=symbol,
            dataset=dataset,
            timeframe=timeframe,
            base_dir=self.base_dir,
        )
        partition_dir.mkdir(parents=True, exist_ok=True)

        target_file = partition_dir / f"{symbol}-{timeframe}-{year}-{month:02d}.parquet"
        part_file = target_file.with_suffix(".parquet.part")

        # Sort and write to .part first
        sorted_df = df.sort("open_time")
        sorted_df.write_parquet(part_file, compression="zstd")

        # Atomic rename
        part_file.replace(target_file)
        logger.info(f"Canonical partition saved: {target_file} ({len(sorted_df)} rows)")
        return target_file

    def list_partition_files(
        self,
        market: str = "binance_usdm",
        symbol: str = "ETHUSDT",
        dataset: str = "contract_klines",
        timeframe: str = "1m",
    ) -> List[Path]:
        """List all parquet files under the canonical dataset path."""
        dataset_dir = get_canonical_dataset_dir(
            market=market,
            symbol=symbol,
            dataset=dataset,
            timeframe=timeframe,
            base_dir=self.base_dir,
        )
        if not dataset_dir.exists():
            return []
        return sorted(list(dataset_dir.glob("year=*/month=*/*.parquet")))

    def read_range(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        market: str = "binance_usdm",
        symbol: str = "ETHUSDT",
        dataset: str = "contract_klines",
        timeframe: str = "1m",
    ) -> pl.DataFrame:
        """Read canonical data across partitions with date filtering."""
        files = self.list_partition_files(market, symbol, dataset, timeframe)
        if not files:
            return pl.DataFrame(schema=CANONICAL_KLINE_SCHEMA)

        # Lazy scan all files
        lazy_df = pl.scan_parquet([str(f) for f in files])

        if start_time is not None:
            start_ms = int(start_time.timestamp() * 1000)
            lazy_df = lazy_df.filter(pl.col("open_time") >= start_ms)

        df = lazy_df.sort("open_time").collect()
        return df.unique(subset=["open_time"]).sort("open_time")

    def read_symbol(
        self,
        symbol: str = "ETHUSDT",
        start_year: Optional[int] = None,
        start_month: Optional[int] = None,
        market: str = "binance_usdm",
        dataset: str = "contract_klines",
        timeframe: str = "1m",
    ) -> pl.DataFrame:
        """Convenience method to read canonical data for a symbol."""
        start_time = None
        if start_year is not None:
            start_time = datetime(start_year, start_month or 1, 1, tzinfo=timezone.utc)
        return self.read_range(
            start_time=start_time,
            market=market,
            symbol=symbol,
            dataset=dataset,
            timeframe=timeframe,
        )
