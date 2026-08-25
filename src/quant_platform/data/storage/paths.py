"""Storage path helpers for canonical and raw data."""

from pathlib import Path
from quant_platform.config.settings import settings


def get_canonical_dataset_dir(
    market: str = "binance_usdm",
    symbol: str = "ETHUSDT",
    dataset: str = "contract_klines",
    timeframe: str = "1m",
    base_dir: Path = None,
) -> Path:
    """Resolve canonical dataset partition root directory."""
    root = base_dir or settings.canonical_data_dir
    return root / f"market={market}" / f"symbol={symbol}" / f"dataset={dataset}" / f"timeframe={timeframe}"


def get_canonical_month_partition_dir(
    year: int,
    month: int,
    market: str = "binance_usdm",
    symbol: str = "ETHUSDT",
    dataset: str = "contract_klines",
    timeframe: str = "1m",
    base_dir: Path = None,
) -> Path:
    """Resolve month partition directory."""
    dataset_dir = get_canonical_dataset_dir(market, symbol, dataset, timeframe, base_dir)
    return dataset_dir / f"year={year}" / f"month={month:02d}"
