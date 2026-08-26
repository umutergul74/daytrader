"""Tests for Feature Distribution Drift Detector."""

import polars as pl
import numpy as np
from quant_platform.live.feature_drift_detector import FeatureDriftDetector


def test_feature_drift_detection():
    """Verify statistical drift detection between historical and shifted live features."""
    np.random.seed(42)
    hist_df = pl.DataFrame({
        "atr_14": np.random.normal(15.0, 2.0, 100),
        "rsi_14": np.random.normal(50.0, 10.0, 100),
    })

    # Shifted live dataframe (high volatility)
    live_df = pl.DataFrame({
        "atr_14": np.random.normal(30.0, 3.0, 100), # Major shift (+7.5 sigma)
        "rsi_14": np.random.normal(51.0, 9.0, 100),  # Stable
    })

    report = FeatureDriftDetector.evaluate_drift(
        historical_df=hist_df,
        live_df=live_df,
        features_to_monitor=["atr_14", "rsi_14"],
        z_threshold=2.0,
    )

    assert report.total_features_evaluated == 2
    assert report.drifted_features_count == 1
    assert report.drift_items[0].feature_name == "atr_14"
    assert report.drift_items[0].is_drifted is True
    assert report.drift_items[0].drift_severity == "CRITICAL"
    assert report.drift_items[1].feature_name == "rsi_14"
    assert report.drift_items[1].is_drifted is False
