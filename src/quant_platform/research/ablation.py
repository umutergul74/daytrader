"""Ablation Engine for Incremental Feature & Component Attribution."""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import polars as pl

from quant_platform.strategies.base import BaseStrategy
from quant_platform.backtest.engine import BacktestEngine, BacktestResult
from quant_platform.research.ledger import ResearchLedger
from quant_platform.domain.experiment import ExperimentRecord, ExperimentStatus
from quant_platform.observability.logger import logger


class AblationResult(BaseModel):
    """Result of an ablation study comparing full and reduced strategy configurations."""
    study_id: str
    base_strategy_id: str
    full_metrics: Dict[str, Any]
    ablated_variations: Dict[str, Dict[str, Any]]
    marginal_contributions: Dict[str, float]
    summary: str


class AblationEngine:
    """Systematically runs ablation tests to measure true marginal value of strategy components."""

    def __init__(self, backtest_engine: Optional[BacktestEngine] = None, ledger: Optional[ResearchLedger] = None):
        self.engine = backtest_engine or BacktestEngine()
        self.ledger = ledger or ResearchLedger()

    def run_ablation_study(
        self,
        df: pl.DataFrame,
        base_strategy: BaseStrategy,
        ablation_variants: Dict[str, BaseStrategy],
        study_id: Optional[str] = None,
    ) -> AblationResult:
        """Run base strategy and all ablated variations, recording results and marginal delta."""
        sid = study_id or f"ABL-{base_strategy.metadata.strategy_id}"
        logger.info(f"Running Ablation Study: {sid}")

        # 1. Full Base Strategy
        full_res = self.engine.run(df, base_strategy)
        full_m = full_res.metrics.model_dump()
        full_net = full_res.metrics.total_net_return

        variations_m: Dict[str, Dict[str, Any]] = {}
        marginal_delta: Dict[str, float] = {}

        # 2. Run each variant
        for name, variant_strat in ablation_variants.items():
            var_res = self.engine.run(df, variant_strat)
            var_m = var_res.metrics.model_dump()
            variations_m[name] = var_m
            # Marginal value: (Full Net Return) - (Variant without component)
            delta = full_net - var_res.metrics.total_net_return
            marginal_delta[name] = delta
            logger.info(f"Ablation Variant '{name}': Net Return = {var_res.metrics.total_net_return:+.2f}% (Marginal Impact: {delta:+.2f}%)")

        summary_lines = [f"Ablation Study: {sid}"]
        for name, delta in marginal_delta.items():
            verdict = "ESSENTIAL" if delta > 1.0 else ("MARGINAL" if delta > 0 else "DETRIMENTAL")
            summary_lines.append(f" - Removing '{name}': Net Delta = {delta:+.2f}% ({verdict})")

        return AblationResult(
            study_id=sid,
            base_strategy_id=base_strategy.metadata.strategy_id,
            full_metrics=full_m,
            ablated_variations=variations_m,
            marginal_contributions=marginal_delta,
            summary="\n".join(summary_lines),
        )
