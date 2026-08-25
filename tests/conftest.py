"""Test fixtures and synthetic market data generator."""

import sys
from pathlib import Path
from datetime import datetime, timezone
import pytest
import numpy as np
import polars as pl

# Ensure src is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quant_platform.domain.kline import CANONICAL_KLINE_SCHEMA


@pytest.fixture
def synthetic_1m_data() -> pl.DataFrame:
    """Generate 1000 bars of deterministic synthetic 1-minute ETHUSDT data."""
    np.random.seed(42)
    n = 1000
    start_ts = 1704067200000  # 2024-01-01 00:00:00 UTC
    step_ms = 60000

    timestamps = [start_ts + (i * step_ms) for i in range(n)]
    close_times = [ts + 59999 for ts in timestamps]

    # Geometric random walk with slight upward drift
    base_price = 2200.0
    returns = np.random.normal(0.0001, 0.002, n)
    price_path = base_price * np.cumprod(1.0 + returns)

    opens = np.roll(price_path, 1)
    opens[0] = base_price
    closes = price_path

    highs = np.maximum(opens, closes) + np.random.uniform(0.5, 3.0, n)
    lows = np.minimum(opens, closes) - np.random.uniform(0.5, 3.0, n)
    volumes = np.random.uniform(10.0, 150.0, n)
    quote_vols = volumes * closes
    trades_count = np.random.randint(50, 400, n)
    taker_buy_base = volumes * np.random.uniform(0.4, 0.6, n)
    taker_buy_quote = taker_buy_base * closes

    df = pl.DataFrame({
        "open_time": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "close_time": close_times,
        "quote_asset_volume": quote_vols,
        "number_of_trades": trades_count,
        "taker_buy_base_asset_volume": taker_buy_base,
        "taker_buy_quote_asset_volume": taker_buy_quote,
    }, schema=CANONICAL_KLINE_SCHEMA)

    return df
