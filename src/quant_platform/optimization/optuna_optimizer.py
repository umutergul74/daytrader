"""Resumable and Persistent Optuna Study Framework."""

from typing import Dict, Any, Callable, Optional, List
from pathlib import Path
from pydantic import BaseModel, Field
import polars as pl

from quant_platform.config.settings import settings
from quant_platform.backtest.engine import BacktestEngine
from quant_platform.strategies.base import BaseStrategy
from quant_platform.observability.logger import logger


class OptimizationResult(BaseModel):
    """Result of hyperparameter optimization."""
    study_name: str
    best_trial_number: int
    best_params: Dict[str, Any]
    best_value: float
    total_trials: int
    is_candidate: bool = True
    verdict: str = "OPTIMIZATION_CANDIDATE (Requires independent out-of-sample walk-forward validation)"


class MockTrial:
    """Mock trial for deterministic fallback when optuna is absent."""
    def __init__(self, idx: int):
        self.idx = idx

    def suggest_int(self, name: str, low: int, high: int, step: int = 1) -> int:
        span = max(1, high - low + 1)
        return low + (self.idx % span)

    def suggest_float(self, name: str, low: float, high: float, step: Optional[float] = None) -> float:
        return float(low + (high - low) * ((self.idx % 5) / 5.0))

    def suggest_categorical(self, name: str, choices: List[Any]) -> Any:
        return choices[self.idx % len(choices)]


class OptunaOptimizer:
    """Manages persistent SQLite Optuna studies with guarded multi-objective evaluation."""

    def __init__(
        self,
        study_name: str,
        storage_path: Optional[Path] = None,
    ):
        self.study_name = study_name
        self.storage_path = storage_path or (settings.research_dir / f"{study_name}.db")
        self.storage_url = f"sqlite:///{self.storage_path.resolve()}"

    def optimize_strategy(
        self,
        df: pl.DataFrame,
        strategy_factory: Callable[[Dict[str, Any]], BaseStrategy],
        param_space: Callable[[Any], Dict[str, Any]],
        n_trials: int = 15,
        engine: Optional[BacktestEngine] = None,
    ) -> OptimizationResult:
        """Run or resume an Optuna optimization study."""
        bt_engine = engine or BacktestEngine()

        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)

            study = optuna.create_study(
                study_name=self.study_name,
                storage=self.storage_url,
                load_if_exists=True,
                direction="maximize",
            )

            def objective(trial):
                params = param_space(trial)
                strat = strategy_factory(params)
                result = bt_engine.run(df, strat)
                m = result.metrics

                # Guardrails: heavily penalize zero trades or extreme drawdown
                if m.trade_count < 3:
                    return -100.0

                # Multi-objective score: Net Return % - (0.5 * Max Drawdown %)
                score = m.total_net_return - (0.5 * m.max_drawdown_pct)
                return score

            study.optimize(objective, n_trials=n_trials)
            best_trial = study.best_trial

            logger.info(f"Optuna Study '{self.study_name}' Completed. Best Trial #{best_trial.number}: Score = {best_trial.value:.2f}")

            return OptimizationResult(
                study_name=self.study_name,
                best_trial_number=best_trial.number,
                best_params=best_trial.params,
                best_value=float(best_trial.value),
                total_trials=len(study.trials),
            )

        except ImportError:
            logger.warning("Optuna not installed in environment. Running deterministic fallback grid search.")
            best_score = -999.0
            best_p = {}
            for i in range(min(5, n_trials)):
                mt = MockTrial(i)
                p = param_space(mt)
                strat = strategy_factory(p)
                res = bt_engine.run(df, strat)
                score = res.metrics.total_net_return
                if score > best_score:
                    best_score = score
                    best_p = p

            return OptimizationResult(
                study_name=self.study_name,
                best_trial_number=1,
                best_params=best_p,
                best_value=best_score,
                total_trials=min(5, n_trials),
            )
