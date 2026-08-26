"""Tests for Open Interest Derivatives Context Feature Engine."""

import polars as pl
from quant_platform.features.microstructure.open_interest_features import OpenInterestFeatureEngine


def test_open_interest_alignment_and_regime_classification():
    """Verify joining Open Interest series and classifying 4-State Joint Price/OI regimes."""
    df_klines = pl.DataFrame({
        "open_time": [1000, 2000, 3000, 4000],
        "close_time": [1999, 2999, 3999, 4999],
        "open": [2000.0, 2010.0, 2020.0, 2010.0],
        "high": [2015.0, 2025.0, 2025.0, 2015.0],
        "low": [1995.0, 2005.0, 2005.0, 1990.0],
        "close": [2010.0, 2020.0, 2010.0, 1995.0], # Up, Up, Down, Down
        "volume": [100.0, 100.0, 100.0, 100.0],
    })

    df_oi = pl.DataFrame({
        "event_time_ms": [1900, 2900, 3900, 4900],
        "open_interest": [500000.0, 510000.0, 520000.0, 505000.0], # Up, Up, Up, Down
    })

    df_res = OpenInterestFeatureEngine.align_and_compute_oi_features(df_klines, df_oi)
    assert "joint_price_oi_regime" in df_res.columns
    regimes = df_res["joint_price_oi_regime"].to_list()
    # Bar 2: Price Up + OI Up -> LONG_BUILDUP
    assert regimes[1] == "LONG_BUILDUP"
    # Bar 3: Price Down + OI Up -> SHORT_BUILDUP
    assert regimes[2] == "SHORT_BUILDUP"
    # Bar 4: Price Down + OI Down -> LONG_LIQUIDATION
    assert regimes[3] == "LONG_LIQUIDATION"
