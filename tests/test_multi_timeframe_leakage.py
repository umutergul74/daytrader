"""Tests for Multi-Timeframe Causal Alignment and Forward Leakage Guard."""

import polars as pl
import pytest
from quant_platform.data.timeframes.resampler import CausalResampler
from quant_platform.data.timeframes.multi_timeframe import MultiTimeframeAligner
from quant_platform.features.indicators.trend import compute_ema


def test_multi_timeframe_alignment_no_lookahead(synthetic_1m_data: pl.DataFrame):
    """Verify that HTF features joined to LTF bars never leak future/unclosed HTF data."""
    # 1. Resample to 15m (LTF) and 1h (HTF)
    df_15m = CausalResampler.resample(synthetic_1m_data, target_timeframe="15m")
    df_1h = CausalResampler.resample(synthetic_1m_data, target_timeframe="1h")

    # 2. Add an indicator to 1H data
    df_1h_feat = compute_ema(df_1h, period=10, output_col="ema_10")

    # 3. Causal join into 15m
    merged = MultiTimeframeAligner.align_htf_features(
        ltf_df=df_15m,
        htf_df=df_1h_feat,
        htf_timeframe="1h",
    )

    # 4. Verify zero lookahead leakage
    assert MultiTimeframeAligner.verify_no_lookahead(merged, htf_timeframe="1h") is True

    # 5. Check explicitly that HTF values only update after 1h candle closes
    # For any 15m bar at open_time T, the merged htf available_at_ms must be <= T
    for row in merged.filter(pl.col("htf_1h_available_at_ms").is_not_null()).iter_rows(named=True):
        assert row["open_time"] >= row["htf_1h_available_at_ms"]
