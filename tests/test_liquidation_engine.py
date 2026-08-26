"""Tests for Liquidation Feature Engine."""

import polars as pl
from quant_platform.features.microstructure.liquidation_features import LiquidationFeatureEngine


def test_liquidation_engine_features():
    """Verify aggregating long/short liquidations and burst detection."""
    df_klines = pl.DataFrame({
        "open_time": [1000, 2000, 3000],
        "close_time": [1999, 2999, 3999],
        "open": [2000.0, 2000.0, 2000.0],
        "high": [2010.0, 2010.0, 2010.0],
        "low": [1990.0, 1990.0, 1990.0],
        "close": [2005.0, 2005.0, 2005.0],
        "volume": [100.0, 100.0, 100.0],
    })

    df_liqs = pl.DataFrame({
        "order_id": ["L1", "L2"],
        "side": ["SELL", "SELL"],
        "price": [1985.0, 1980.0],
        "quantity": [30.0, 40.0], # Total 70 > 50 burst
        "event_time_ms": [1500, 1800],
        "received_at_ms": [1510, 1810],
    })

    df_feat = LiquidationFeatureEngine.align_and_compute_liquidation_features(df_klines, df_liqs)
    assert "long_liq_vol_15m" in df_feat.columns
    assert "is_liquidation_burst" in df_feat.columns
    assert df_feat["is_liquidation_burst"].to_list()[0] is True
