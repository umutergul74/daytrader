"""Tests for Ablation Engine."""

import polars as pl
import pytest
from quant_platform.research.ablation import AblationEngine
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy
from quant_platform.strategies.baselines.rsi_reversion import RsiMeanReversionStrategy


def test_ablation_engine_marginal_contribution(synthetic_1m_data: pl.DataFrame):
    """Verify that ablation engine runs full vs variant and computes marginal impact."""
    engine = AblationEngine()
    base = EmaTrendStrategy(fast_period=20, slow_period=50)
    variants = {
        "variant_rsi": RsiMeanReversionStrategy(),
    }

    result = engine.run_ablation_study(
        df=synthetic_1m_data,
        base_strategy=base,
        ablation_variants=variants,
    )

    assert result.study_id.startswith("ABL-")
    assert "variant_rsi" in result.marginal_contributions
    assert isinstance(result.marginal_contributions["variant_rsi"], float)
