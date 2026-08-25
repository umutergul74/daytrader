"""Tests for Optuna Optimizer."""

from pathlib import Path
import polars as pl
import pytest
from quant_platform.optimization.optuna_optimizer import OptunaOptimizer
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy


def test_optuna_optimizer_run(synthetic_1m_data: pl.DataFrame, tmp_path: Path):
    """Verify optimizer execution and candidate reporting."""
    db_file = tmp_path / "test_study.db"
    optimizer = OptunaOptimizer(study_name="test_ema_study", storage_path=db_file)

    def factory(params):
        fast = params.get("fast_period", 10)
        slow = params.get("slow_period", 20)
        return EmaTrendStrategy(fast_period=fast, slow_period=slow)

    def search_space(trial):
        return {
            "fast_period": trial.suggest_int("fast_period", 5, 15),
            "slow_period": trial.suggest_int("slow_period", 20, 40),
        }

    res = optimizer.optimize_strategy(
        df=synthetic_1m_data,
        strategy_factory=factory,
        param_space=search_space,
        n_trials=3,
    )

    assert res.study_name == "test_ema_study"
    assert res.total_trials >= 1
    assert "OPTIMIZATION_CANDIDATE" in res.verdict
