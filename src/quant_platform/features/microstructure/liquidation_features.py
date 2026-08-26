"""Forced Liquidation Metrics and Confluence Engine.

Computes rolling liquidation volumes, imbalance ratios, burst flags, and confluence
with SMC Liquidity Sweeps.
"""

from typing import Optional
import numpy as np
import polars as pl
from pydantic import BaseModel


class LiquidationFeatureEngine:
    """Computes liquidation intensity, imbalance, and sweep confluence."""

    @staticmethod
    def align_and_compute_liquidation_features(
        df_klines: pl.DataFrame,
        df_liquidations: pl.DataFrame,
        burst_threshold_qty: float = 50.0,
    ) -> pl.DataFrame:
        """Aggregates liquidation events into kline intervals and computes burst features."""
        if df_liquidations.is_empty() or "quantity" not in df_liquidations.columns:
            return df_klines.with_columns([
                pl.lit(0.0).alias("long_liq_vol_15m"),
                pl.lit(0.0).alias("short_liq_vol_15m"),
                pl.lit(0.0).alias("liq_imbalance_15m"),
                pl.lit(False).alias("is_liquidation_burst"),
            ])

        open_times = df_klines["open_time"].to_numpy()
        close_times = df_klines["close_time"].to_numpy()
        n_bars = len(df_klines)

        long_vols = np.zeros(n_bars, dtype=np.float64)
        short_vols = np.zeros(n_bars, dtype=np.float64)

        # Iterate over liquidations
        for liq in df_liquidations.iter_rows(named=True):
            t_ms = liq["event_time_ms"]
            qty = float(liq["quantity"])
            side = str(liq["side"]).upper()

            # Find matching bar index
            idx = np.searchsorted(close_times, t_ms)
            if idx < n_bars and open_times[idx] <= t_ms <= close_times[idx]:
                if side == "SELL": # Long position liquidated
                    long_vols[idx] += qty
                else:             # Short position liquidated
                    short_vols[idx] += qty

        total_vols = long_vols + short_vols
        imbalance = np.zeros(n_bars, dtype=np.float64)
        nz = total_vols > 0
        imbalance[nz] = (long_vols[nz] - short_vols[nz]) / total_vols[nz]
        is_burst = total_vols >= burst_threshold_qty

        df_feat = df_klines.with_columns([
            pl.Series("long_liq_vol_15m", long_vols),
            pl.Series("short_liq_vol_15m", short_vols),
            pl.Series("liq_imbalance_15m", imbalance),
            pl.Series("is_liquidation_burst", is_burst),
        ])

        return df_feat
