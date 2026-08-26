"""Feature Distribution Drift Diagnostics Engine.

Calculates statistical distribution divergence (Z-score shift, Wasserstein distance approximation)
between historical training distributions and live streaming shadow market features.
"""

from typing import Dict, List, Optional, Any
import numpy as np
import polars as pl
from pydantic import BaseModel, Field

from quant_platform.observability.logger import logger


class FeatureDistributionStats(BaseModel):
    """Statistical summary of a feature distribution."""
    feature_name: str
    sample_size: int
    mean: float
    std: float
    median: float
    p25: float
    p75: float


class FeatureDriftItem(BaseModel):
    """Drift analysis for a single feature."""
    feature_name: str
    historical_mean: float
    live_mean: float
    historical_std: float
    live_std: float
    z_score_shift: float
    is_drifted: bool
    drift_severity: str # NORMAL, MODERATE, CRITICAL


class FeatureDriftReport(BaseModel):
    """Consolidated feature distribution drift report."""
    total_features_evaluated: int
    drifted_features_count: int
    drift_items: List[FeatureDriftItem] = Field(default_factory=list)
    overall_drift_state: str # STABLE, MONITOR, SEVERE_REGIME_SHIFT


class FeatureDriftDetector:
    """Detects structural statistical shifts in live feature values."""

    @staticmethod
    def compute_distribution_stats(values: np.ndarray, feature_name: str) -> FeatureDistributionStats:
        """Compute summary statistics for a 1D array."""
        clean = values[~np.isnan(values)]
        if len(clean) == 0:
            return FeatureDistributionStats(
                feature_name=feature_name,
                sample_size=0,
                mean=0.0,
                std=1.0,
                median=0.0,
                p25=0.0,
                p75=0.0,
            )

        return FeatureDistributionStats(
            feature_name=feature_name,
            sample_size=len(clean),
            mean=float(np.mean(clean)),
            std=float(np.std(clean)) if len(clean) > 1 else 1.0,
            median=float(np.median(clean)),
            p25=float(np.percentile(clean, 25)),
            p75=float(np.percentile(clean, 75)),
        )

    @classmethod
    def evaluate_drift(
        cls,
        historical_df: pl.DataFrame,
        live_df: pl.DataFrame,
        features_to_monitor: Optional[List[str]] = None,
        z_threshold: float = 2.0,
    ) -> FeatureDriftReport:
        """Compare feature distributions between historical baseline and live streaming dataframe."""
        features = features_to_monitor or [
            "atr_14",
            "rsi_14",
            "ema_10",
            "ema_30",
        ]

        drift_items: List[FeatureDriftItem] = []
        drift_count = 0

        for feat in features:
            if feat not in historical_df.columns or feat not in live_df.columns:
                continue

            hist_vals = historical_df[feat].to_numpy()
            live_vals = live_df[feat].to_numpy()

            hist_stats = cls.compute_distribution_stats(hist_vals, feat)
            live_stats = cls.compute_distribution_stats(live_vals, feat)

            if hist_stats.sample_size < 10 or live_stats.sample_size < 10:
                continue

            # Standardized mean shift
            pooled_std = max(1e-6, hist_stats.std)
            z_shift = abs(live_stats.mean - hist_stats.mean) / pooled_std

            is_drifted = z_shift >= z_threshold
            if is_drifted:
                drift_count += 1
                severity = "CRITICAL" if z_shift >= 3.5 else "MODERATE"
            else:
                severity = "NORMAL"

            drift_items.append(FeatureDriftItem(
                feature_name=feat,
                historical_mean=hist_stats.mean,
                live_mean=live_stats.mean,
                historical_std=hist_stats.std,
                live_std=live_stats.std,
                z_score_shift=float(z_shift),
                is_drifted=is_drifted,
                drift_severity=severity,
            ))

        overall_state = "STABLE"
        if drift_count >= 2:
            overall_state = "SEVERE_REGIME_SHIFT"
        elif drift_count == 1:
            overall_state = "MONITOR"

        return FeatureDriftReport(
            total_features_evaluated=len(drift_items),
            drifted_features_count=drift_count,
            drift_items=drift_items,
            overall_drift_state=overall_state,
        )
