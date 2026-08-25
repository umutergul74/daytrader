"""Causal Multi-Timeframe Feature Alignment and Leakage Guard."""

from typing import List, Optional, Dict
import numpy as np
import polars as pl

from quant_platform.observability.logger import logger


class MultiTimeframeAligner:
    """Causally merges Higher Timeframe (HTF) features into Lower Timeframe (LTF) bars."""

    @staticmethod
    def align_htf_features(
        ltf_df: pl.DataFrame,
        htf_df: pl.DataFrame,
        htf_timeframe: str,
        feature_cols: Optional[List[str]] = None,
    ) -> pl.DataFrame:
        """Causally joins HTF features into LTF bars using strictly available_at_ms <= ltf.open_time."""
        if "available_at_ms" not in htf_df.columns:
            # Add availability timestamp as close_time + 1
            htf_df = htf_df.with_columns(
                (pl.col("close_time") + 1).alias("available_at_ms")
            )

        # Select columns to merge
        if feature_cols is None:
            # Exclude standard raw kline columns except available_at_ms
            exclude_raw = ["open", "high", "low", "close", "volume", "close_time", "quote_asset_volume", "number_of_trades"]
            feature_cols = [c for c in htf_df.columns if c not in exclude_raw and c != "open_time" and c != "available_at_ms"]

        htf_avail_col = f"htf_{htf_timeframe}_available_at_ms"
        select_cols = [pl.col("available_at_ms").alias(htf_avail_col)] + [
            pl.col(c).alias(f"htf_{htf_timeframe}_{c}") for c in feature_cols
        ]
        htf_sub = htf_df.select(select_cols).sort(htf_avail_col)

        # As-of join (causal backward matching):
        # LTF open_time matches the most recent HTF available_at_ms <= ltf.open_time
        merged = ltf_df.sort("open_time").join_asof(
            htf_sub,
            left_on="open_time",
            right_on=htf_avail_col,
            strategy="backward",
        )

        return merged

    @staticmethod
    def verify_no_lookahead(
        ltf_with_htf: pl.DataFrame,
        htf_timeframe: str,
    ) -> bool:
        """Verify that no LTF row has received data from an unclosed/future HTF bar."""
        avail_col = f"htf_{htf_timeframe}_available_at_ms"
        if avail_col not in ltf_with_htf.columns:
            return True

        # Check: ltf.open_time must always be >= htf.available_at_ms
        violations = ltf_with_htf.filter(
            pl.col(avail_col).is_not_null() & (pl.col("open_time") < pl.col(avail_col))
        )
        if len(violations) > 0:
            raise ValueError(f"LOOKAHEAD LEAKAGE DETECTED! {len(violations)} rows had open_time < htf.available_at_ms")

        return True
