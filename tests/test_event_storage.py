"""Tests for Tiered Canonical Event Storage Engine."""

import tempfile
from pathlib import Path
import polars as pl
from quant_platform.data.storage.event_storage import CanonicalEventStorage


def test_event_storage_partitioning_and_deduplication():
    """Verify writing partitioned Parquet events and reading back with deduplication."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CanonicalEventStorage(root_dir=Path(tmpdir))

        df_events = pl.DataFrame({
            "trade_id": [1, 2, 3, 2], # Duplicate trade_id 2
            "price": [2000.0, 2001.0, 2002.0, 2001.0],
            "quantity": [1.5, 2.0, 0.5, 2.0],
            "is_buyer_maker": [True, False, True, False],
            "event_time_ms": [1704067200000, 1704067201000, 1704067202000, 1704067201000],
            "received_at_ms": [1704067200010, 1704067201010, 1704067202010, 1704067201010],
        })

        written = storage.write_events(dataset_name="agg_trades", symbol="ETHUSDT", df=df_events)
        assert len(written) > 0

        # Read back
        df_read = storage.read_events(dataset_name="agg_trades", symbol="ETHUSDT")
        assert len(df_read) == 3 # Deduplicated
        assert df_read["trade_id"].to_list() == [1, 2, 3]
