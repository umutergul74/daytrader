"""Tests for causal timeframe resampling and zero lookahead leakage."""

import polars as pl
from quant_platform.data.timeframes.resampler import CausalResampler


def test_timeframe_resampling_aggregation(synthetic_1m_data: pl.DataFrame):
    """Verify 1m to 5m and 15m resampling obeys open, high, low, close, volume aggregation rules."""
    df_5m = CausalResampler.resample(synthetic_1m_data, target_timeframe="5m")

    # 1000 1m bars resampled to 5m = 200 bars
    assert len(df_5m) == 200

    # Verify first 5m bar against the first 5 1m bars
    first_5_1m = synthetic_1m_data.slice(0, 5)
    first_5m = df_5m.row(0, named=True)

    assert first_5m["open"] == first_5_1m["open"][0]
    assert first_5m["high"] == first_5_1m["high"].max()
    assert first_5m["low"] == first_5_1m["low"].min()
    assert first_5m["close"] == first_5_1m["close"][-1]
    assert round(first_5m["volume"], 4) == round(first_5_1m["volume"].sum(), 4)
    assert first_5m["bar_count_1m"] == 5


def test_timeframe_availability_timestamp(synthetic_1m_data: pl.DataFrame):
    """Verify available_at_ms timestamp guarantees causal barrier."""
    df_15m = CausalResampler.resample(synthetic_1m_data, target_timeframe="15m")

    for row in df_15m.iter_rows(named=True):
        open_time = row["open_time"]
        close_time = row["close_time"]
        available_at = row["available_at_ms"]
        bar_count = row["bar_count_1m"]

        # Availability must be strictly after the candle close
        assert available_at > close_time
        if bar_count == 15:
            assert available_at >= open_time + (15 * 60 * 1000)
