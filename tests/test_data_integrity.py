"""Tests for data integrity validation, gap detection, and Parquet storage."""

import polars as pl
from quant_platform.data.validation.integrity import DataIntegrityValidator
from quant_platform.data.storage.canonical import CanonicalStorage
from quant_platform.data.manifest.manifest_manager import DatasetManifestManager


def test_data_integrity_valid_series(synthetic_1m_data: pl.DataFrame):
    """Ensure clean synthetic series passes all validation checks."""
    report = DataIntegrityValidator.validate_1m_series(synthetic_1m_data)
    assert report.is_valid is True
    assert report.duplicate_count == 0
    assert report.invalid_ohlc_count == 0
    assert report.negative_volume_count == 0
    assert report.gap_count == 0
    assert report.total_rows == 1000


def test_data_integrity_detects_gaps_and_invalid_ohlc(synthetic_1m_data: pl.DataFrame):
    """Ensure validator catches missing timestamps and corrupted OHLC relationships."""
    corrupted = synthetic_1m_data.clone()

    # Introduce a 5-minute gap by dropping rows 10 to 15
    corrupted = corrupted.filter(~pl.col("open_time").is_in(corrupted["open_time"][10:15]))

    # Introduce an invalid OHLC (High < Low)
    corrupted = corrupted.with_columns(
        pl.when(pl.col("open_time") == corrupted["open_time"][20])
        .then(100.0)
        .otherwise(pl.col("high"))
        .alias("high")
    )

    report = DataIntegrityValidator.validate_1m_series(corrupted)
    assert report.is_valid is False
    assert report.gap_count == 1
    assert report.invalid_ohlc_count >= 1
    assert report.unresolved_gaps[0].missing_minutes == 5


def test_canonical_storage_and_manifest(tmp_path, synthetic_1m_data: pl.DataFrame):
    """Test saving to partitioned Parquet and generating dataset manifest."""
    storage = CanonicalStorage(base_dir=tmp_path / "canonical")
    manifest_mgr = DatasetManifestManager(manifest_dir=tmp_path / "manifests", storage=storage)

    # Write partition
    saved_file = storage.write_month_partition(
        synthetic_1m_data,
        year=2024,
        month=1,
        symbol="ETHUSDT",
        timeframe="1m",
    )
    assert saved_file.exists()

    # Read range back
    loaded_df = storage.read_range(symbol="ETHUSDT", timeframe="1m")
    assert len(loaded_df) == len(synthetic_1m_data)
    assert loaded_df["open_time"].to_list() == synthetic_1m_data["open_time"].to_list()

    # Generate and verify manifest
    manifest = manifest_mgr.generate_manifest(symbol="ETHUSDT", timeframe="1m")
    assert manifest.row_count == 1000
    assert len(manifest.canonical_fingerprint) == 64
    assert manifest.duplicate_count == 0
