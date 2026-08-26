"""Dataset Manifest & Fingerprinting Manager."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import polars as pl

from quant_platform.config.settings import settings
from quant_platform.data.validation.integrity import DataIntegrityReport, DataIntegrityValidator
from quant_platform.data.storage.canonical import CanonicalStorage
from quant_platform.observability.logger import logger


class DatasetManifest(BaseModel):
    """Immutable manifest representing the exact state and fingerprint of a dataset."""
    dataset_id: str
    schema_version: str = "v1"
    provider: str = "binance_archive+rest"
    market: str = "binance_usdm"
    symbol: str = "ETHUSDT"
    contract_type: str = "perpetual"
    dataset_type: str = "contract_klines"
    timeframe: str = "1m"
    first_timestamp: int
    last_timestamp: int
    first_datetime_utc: str
    last_datetime_utc: str
    row_count: int
    partition_count: int
    source_files: List[str]
    canonical_fingerprint: str = Field(description="SHA-256 fingerprint of the canonical dataset")
    duplicate_count: int = 0
    gap_count: int = 0
    unresolved_gaps_count: int = 0
    validation_warnings: List[str] = Field(default_factory=list)
    build_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class DatasetManifestManager:
    """Computes SHA-256 fingerprint, audits partitions, and manages manifest JSON files."""

    def __init__(self, manifest_dir: Optional[Path] = None, storage: Optional[CanonicalStorage] = None):
        self.manifest_dir = manifest_dir or settings.manifest_data_dir
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        self.storage = storage or CanonicalStorage()

    def compute_df_fingerprint(self, df: pl.DataFrame) -> str:
        """Compute SHA-256 hash of open_time, open, high, low, close, volume."""
        import io
        hasher = hashlib.sha256()
        key_cols = ["open_time", "open", "high", "low", "close", "volume"]
        sub_df = df.select(key_cols).sort("open_time")
        buf = io.BytesIO()
        sub_df.write_ipc(buf)
        hasher.update(buf.getvalue())
        return hasher.hexdigest()

    def generate_manifest(
        self,
        market: str = "binance_usdm",
        symbol: str = "ETHUSDT",
        dataset: str = "contract_klines",
        timeframe: str = "1m",
    ) -> DatasetManifest:
        """Build and persist dataset manifest for the canonical partition tree."""
        files = self.storage.list_partition_files(market, symbol, dataset, timeframe)
        if not files:
            raise FileNotFoundError(f"No canonical partition files found for {market}/{symbol}/{dataset}/{timeframe}")

        df = self.storage.read_range(market=market, symbol=symbol, dataset=dataset, timeframe=timeframe)
        if df.is_empty():
            raise ValueError("Dataset is empty.")

        # Run integrity audit
        report = DataIntegrityValidator.validate_1m_series(df)

        # Compute deterministic fingerprint
        fingerprint = self.compute_df_fingerprint(df)
        dataset_id = f"DS-{symbol}-{timeframe}-{fingerprint[:12]}"

        first_ts = int(df["open_time"].min())
        last_ts = int(df["open_time"].max())
        first_dt = datetime.fromtimestamp(first_ts / 1000.0, tz=timezone.utc).isoformat()
        last_dt = datetime.fromtimestamp(last_ts / 1000.0, tz=timezone.utc).isoformat()

        manifest = DatasetManifest(
            dataset_id=dataset_id,
            schema_version="v1",
            provider="binance_archive+rest",
            market=market,
            symbol=symbol,
            contract_type="perpetual",
            dataset_type=dataset,
            timeframe=timeframe,
            first_timestamp=first_ts,
            last_timestamp=last_ts,
            first_datetime_utc=first_dt,
            last_datetime_utc=last_dt,
            row_count=len(df),
            partition_count=len(files),
            source_files=[f.name for f in files],
            canonical_fingerprint=fingerprint,
            duplicate_count=report.duplicate_count,
            gap_count=report.gap_count,
            unresolved_gaps_count=len(report.unresolved_gaps),
            validation_warnings=report.warnings,
        )

        manifest_path = self.manifest_dir / f"manifest_{symbol}_{timeframe}.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"Manifest saved to {manifest_path} (Fingerprint: {fingerprint})")
        return manifest

    def load_manifest(self, symbol: str = "ETHUSDT", timeframe: str = "1m") -> Optional[DatasetManifest]:
        """Load manifest if present."""
        path = self.manifest_dir / f"manifest_{symbol}_{timeframe}.json"
        if not path.exists():
            return None
        return DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))
