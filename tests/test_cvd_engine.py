"""Tests for Cumulative Volume Delta (CVD) and Divergence Engine."""

import polars as pl
from quant_platform.features.microstructure.cvd import CvdEngine


def test_cvd_engine_delta_and_divergence():
    """Verify calculating window delta, rolling CVD, and divergence signals."""
    df_klines = pl.DataFrame({
        "open_time": [1000, 2000, 3000, 4000, 5000],
        "close_time": [1999, 2999, 3999, 4999, 5999],
        "open": [2000.0, 2010.0, 2020.0, 2030.0, 2040.0],
        "high": [2015.0, 2025.0, 2035.0, 2045.0, 2055.0],
        "low": [1995.0, 2005.0, 2015.0, 2025.0, 2035.0],
        "close": [2010.0, 2020.0, 2030.0, 2040.0, 2050.0],
        "volume": [100.0, 120.0, 150.0, 110.0, 130.0],
        "taker_buy_base_asset_volume": [60.0, 70.0, 40.0, 30.0, 20.0], # Declining aggressive buyers
    })

    df_delta = CvdEngine.compute_kline_delta_features(df_klines, rolling_window=3)
    assert "delta_1m" in df_delta.columns
    assert "cvd_global" in df_delta.columns
    assert df_delta["delta_1m"].to_list() == [20.0, 20.0, -70.0, -50.0, -90.0]

    # Detect Divergence
    df_div = CvdEngine.detect_cvd_divergence(df_delta, lookback=2)
    assert "is_cvd_bearish_divergence" in df_div.columns
    assert "is_cvd_bullish_divergence" in df_div.columns
