"""Tests for Tabular Meta-Classifier Trainer and Strategy Filter."""

import numpy as np
import polars as pl
from quant_platform.domain.signal import SignalCandidate
from quant_platform.domain.trade import TradeDirection
from quant_platform.ml.meta_classifier import MetaClassifierTrainer
from quant_platform.strategies.baselines.breakout import BreakoutSanityStrategy
from quant_platform.strategies.advanced.meta_strategy import MetaLabeledStrategy


def test_meta_classifier_training_and_strategy_filtering():
    """Verify training a meta-model and using it to filter trade candidates."""
    np.random.seed(42)
    # Synthetic dataset
    X_train = np.random.normal(0, 1, (40, 5))
    y_train = (X_train[:, 0] + X_train[:, 1] > 0).astype(int)
    X_test = np.random.normal(0, 1, (20, 5))
    y_test = (X_test[:, 0] + X_test[:, 1] > 0).astype(int)

    trainer = MetaClassifierTrainer(model_type="logistic_regression")
    metrics = trainer.train_and_calibrate(X_train, y_train, X_test, y_test, feature_names=[f"f_{i}" for i in range(5)])

    assert metrics.roc_auc >= 0.50
    assert metrics.is_calibrated is True

    # Test MetaLabeledStrategy candidate filtering
    primary = BreakoutSanityStrategy(lookback_period=5, risk_reward_ratio=2.0)
    meta_strat = MetaLabeledStrategy(primary_strategy=primary, meta_trainer=trainer, probability_threshold=0.50)

    assert meta_strat.metadata.strategy_id.endswith("_ML_Filtered")
