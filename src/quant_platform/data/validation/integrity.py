"""Data integrity and gap detection engine."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
import polars as pl

from quant_platform.observability.logger import logger


class DataGap(BaseModel):
    start_time: int = Field(description="Missing gap start timestamp ms UTC")
    end_time: int = Field(description="Missing gap end timestamp ms UTC")
    missing_minutes: int
    start_datetime_str: str
    end_datetime_str: str


class DataIntegrityReport(BaseModel):
    is_valid: bool
    total_rows: int
    first_timestamp: Optional[int] = None
    last_timestamp: Optional[int] = None
    duplicate_count: int = 0
    gap_count: int = 0
    unresolved_gaps: List[DataGap] = Field(default_factory=list)
    invalid_ohlc_count: int = 0
    negative_volume_count: int = 0
    out_of_order_count: int = 0
    warnings: List[str] = Field(default_factory=list)


class DataIntegrityValidator:
    """Validates temporal monotonicity, OHLC relationships, and gap detection."""

    @staticmethod
    def validate_1m_series(df: pl.DataFrame) -> DataIntegrityReport:
        """Thoroughly audit a 1-minute canonical dataset."""
        if df.is_empty():
            return DataIntegrityReport(
                is_valid=False,
                total_rows=0,
                warnings=["Dataset is empty"],
            )

        total_rows = len(df)
        first_ts = int(df["open_time"].min())
        last_ts = int(df["open_time"].max())

        # 1. Duplicates
        duplicates = df.filter(pl.col("open_time").is_duplicated())
        dup_count = len(duplicates)

        # 2. Invalid OHLC checks
        # high >= max(open, close) and low <= min(open, close) and low <= high
        invalid_ohlc = df.filter(
            (pl.col("high") < pl.col("low")) |
            (pl.col("high") < pl.col("open")) |
            (pl.col("high") < pl.col("close")) |
            (pl.col("low") > pl.col("open")) |
            (pl.col("low") > pl.col("close")) |
            (pl.col("open") <= 0) |
            (pl.col("close") <= 0)
        )
        invalid_ohlc_count = len(invalid_ohlc)

        # 3. Negative volume
        neg_vol = df.filter(pl.col("volume") < 0)
        neg_vol_count = len(neg_vol)

        # 4. Out-of-order timestamps
        # Sort check
        diffs = df.select(
            (pl.col("open_time") - pl.col("open_time").shift(1)).alias("time_diff")
        ).drop_nulls()

        out_of_order = diffs.filter(pl.col("time_diff") <= 0)
        out_of_order_count = len(out_of_order)

        # 5. Gap detection (expected 60,000 ms step between 1m candles)
        gaps: List[DataGap] = []
        ONE_MINUTE_MS = 60_000

        # Find rows where time_diff > 60_000
        time_diff_df = df.with_columns(
            pl.col("open_time").shift(1).alias("prev_open_time")
        ).filter(
            (pl.col("open_time") - pl.col("prev_open_time")) > ONE_MINUTE_MS
        )

        for row in time_diff_df.iter_rows(named=True):
            prev_ts = int(row["prev_open_time"])
            curr_ts = int(row["open_time"])
            missing_ms = curr_ts - prev_ts - ONE_MINUTE_MS
            missing_mins = missing_ms // ONE_MINUTE_MS
            gap_start = prev_ts + ONE_MINUTE_MS
            gap_end = curr_ts - ONE_MINUTE_MS

            start_dt = datetime.fromtimestamp(gap_start / 1000.0, tz=timezone.utc).isoformat()
            end_dt = datetime.fromtimestamp(gap_end / 1000.0, tz=timezone.utc).isoformat()

            gaps.append(DataGap(
                start_time=gap_start,
                end_time=gap_end,
                missing_minutes=missing_mins,
                start_datetime_str=start_dt,
                end_datetime_str=end_dt,
            ))

        warnings: List[str] = []
        if dup_count > 0:
            warnings.append(f"Found {dup_count} duplicate timestamps")
        if invalid_ohlc_count > 0:
            warnings.append(f"Found {invalid_ohlc_count} invalid OHLC records")
        if neg_vol_count > 0:
            warnings.append(f"Found {neg_vol_count} negative volume records")
        if out_of_order_count > 0:
            warnings.append(f"Found {out_of_order_count} out-of-order timestamps")
        if len(gaps) > 0:
            warnings.append(f"Found {len(gaps)} missing time gaps (total {sum(g.missing_minutes for g in gaps)} minutes)")

        is_valid = (invalid_ohlc_count == 0) and (neg_vol_count == 0) and (out_of_order_count == 0)

        return DataIntegrityReport(
            is_valid=is_valid,
            total_rows=total_rows,
            first_timestamp=first_ts,
            last_timestamp=last_ts,
            duplicate_count=dup_count,
            gap_count=len(gaps),
            unresolved_gaps=gaps,
            invalid_ohlc_count=invalid_ohlc_count,
            negative_volume_count=neg_vol_count,
            out_of_order_count=out_of_order_count,
            warnings=warnings,
        )
