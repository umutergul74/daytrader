"""Time and Session Feature Generator in Polars (Strictly UTC)."""

from typing import Optional
from datetime import datetime, timezone
import polars as pl


class TimeSessionEngine:
    """Computes UTC session and temporal features."""

    @staticmethod
    def compute_session_features(df: pl.DataFrame) -> pl.DataFrame:
        """Add UTC hour, weekday, weekend flag, and trading session classifications."""
        # Convert open_time (ms) to Datetime in UTC
        df_temp = df.with_columns(
            pl.from_epoch(pl.col("open_time"), time_unit="ms").alias("_dt_utc")
        )

        df_temp = df_temp.with_columns([
            pl.col("_dt_utc").dt.hour().alias("utc_hour"),
            pl.col("_dt_utc").dt.weekday().alias("utc_day_of_week"), # 1=Mon, 7=Sun in Polars
        ])

        # Session boolean flags
        # Asia: 00:00 - 08:00 UTC (hours 0..7)
        # London: 07:00 - 15:00 UTC (hours 7..14)
        # New York: 13:00 - 21:00 UTC (hours 13..20)
        # London / NY Overlap: 13:00 - 15:00 UTC (hours 13..14)
        is_asia = (pl.col("utc_hour") >= 0) & (pl.col("utc_hour") < 8)
        is_london = (pl.col("utc_hour") >= 7) & (pl.col("utc_hour") < 15)
        is_ny = (pl.col("utc_hour") >= 13) & (pl.col("utc_hour") < 21)
        is_overlap = (pl.col("utc_hour") >= 13) & (pl.col("utc_hour") < 15)
        is_weekend = pl.col("utc_day_of_week") >= 6

        session_name = (
            pl.when(is_overlap)
            .then(pl.lit("LONDON_NY_OVERLAP"))
            .when(is_london)
            .then(pl.lit("LONDON"))
            .when(is_ny)
            .then(pl.lit("NEW_YORK"))
            .when(is_asia)
            .then(pl.lit("ASIA"))
            .otherwise(pl.lit("OFF_HOURS"))
        )

        df_res = df_temp.with_columns([
            is_weekend.alias("is_weekend"),
            is_asia.alias("is_asia_session"),
            is_london.alias("is_london_session"),
            is_ny.alias("is_ny_session"),
            is_overlap.alias("is_london_ny_overlap"),
            session_name.alias("trading_session"),
        ]).drop(["_dt_utc"])

        return df_res
