"""Trade Flow and Aggressive Order Flow Metrics Engine.

Computes trade imbalance ratios, aggressive buyer/seller volume proportions,
and signed-volume momentum features from tick/kline taker metrics.
"""

from typing import Optional
import polars as pl
from pydantic import BaseModel


class TradeFlowEngine:
    """Computes order flow trade intensity, aggression, and imbalance features."""

    @staticmethod
    def compute_trade_flow_features(
        df: pl.DataFrame,
        imbalance_window: int = 14,
    ) -> pl.DataFrame:
        """Derive trade imbalance ratio, buyer ratio, and signed volume momentum."""
        if "taker_buy_base_asset_volume" in df.columns:
            buy_vol = pl.col("taker_buy_base_asset_volume")
            total_vol = pl.col("volume")
            sell_vol = total_vol - buy_vol
        else:
            total_vol = pl.col("volume")
            buy_vol = total_vol * 0.5
            sell_vol = total_vol * 0.5

        imbalance = (buy_vol - sell_vol) / pl.when(total_vol > 0).then(total_vol).otherwise(1.0)
        buy_ratio = buy_vol / pl.when(total_vol > 0).then(total_vol).otherwise(1.0)

        df_flow = df.with_columns([
            imbalance.alias("trade_imbalance_1m"),
            buy_ratio.alias("buy_volume_ratio_1m"),
        ])

        # Rolling smooth imbalance and signed volume momentum
        df_flow = df_flow.with_columns([
            pl.col("trade_imbalance_1m").rolling_mean(window_size=imbalance_window).alias(f"trade_imbalance_rolling_{imbalance_window}"),
            (pl.col("trade_imbalance_1m") - pl.col("trade_imbalance_1m").shift(3)).alias("signed_volume_momentum_3m"),
        ])

        return df_flow
