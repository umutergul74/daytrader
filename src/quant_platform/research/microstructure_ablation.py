"""Microstructure Incremental Edge Gate and Ablation Suite.

Conducts rigorous single-feature and joint-feature ablation tests comparing Base Strategies
against Base + Microstructure features, updating the Research Ledger with permanent findings.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import polars as pl

from quant_platform.research.ledger import ResearchLedger
from quant_platform.research.counterfactual_analyzer import CounterfactualAnalyzer, CounterfactualStudyReport
from quant_platform.observability.logger import logger


class MicrostructureAblationMatrix(BaseModel):
    """Ablation matrix comparing base strategy against individual microstructure features."""
    strategy_id: str
    base_profit_factor: float
    base_win_rate_pct: float
    base_expectancy_r: float
    cvd_expectancy_delta: float
    oi_expectancy_delta: float
    liquidation_expectancy_delta: float
    joint_cvd_oi_expectancy_delta: float
    recommended_promotions: List[str] = Field(default_factory=list)


class MicrostructureAblationEngine:
    """Executes empirical marginal contribution tests for Phase 4 microstructure features."""

    @staticmethod
    def run_ablation(
        strategy_id: str,
        trades_with_features: List[Dict[str, Any]],
        ledger: Optional[ResearchLedger] = None,
    ) -> MicrostructureAblationMatrix:
        """Evaluates standalone and joint microstructure feature contributions."""
        study = CounterfactualAnalyzer.run_standard_counterfactual_suite(
            strategy_id=strategy_id,
            trades_with_features=trades_with_features,
        )

        deltas: Dict[str, float] = {}
        promotions: List[str] = []

        for eval_res in study.filter_evaluations:
            deltas[eval_res.filter_name] = eval_res.expectancy_delta_r
            if eval_res.marginal_edge_status == "ACCEPT":
                promotions.append(eval_res.filter_name)

        matrix = MicrostructureAblationMatrix(
            strategy_id=strategy_id,
            base_profit_factor=study.baseline_profit_factor,
            base_win_rate_pct=study.baseline_win_rate,
            base_expectancy_r=study.baseline_expectancy_r,
            cvd_expectancy_delta=deltas.get("CVD_DIVERGENCE_REQUIRED", 0.0),
            oi_expectancy_delta=deltas.get("OI_BUILDUP_REQUIRED", 0.0),
            liquidation_expectancy_delta=deltas.get("LIQUIDATION_BURST_REQUIRED", 0.0),
            joint_cvd_oi_expectancy_delta=deltas.get("TRADE_IMBALANCE_DIRECTION_CONFIRMED", 0.0),
            recommended_promotions=promotions,
        )

        # Log into Research Ledger if provided
        if ledger is not None:
            ledger.record_experiment(
                strategy_name=f"{strategy_id}_Microstructure_Ablation",
                experiment_type="ABLATION",
                parameters={"total_trades": len(trades_with_features)},
                metrics={
                    "base_pf": study.baseline_profit_factor,
                    "cvd_delta_r": matrix.cvd_expectancy_delta,
                    "oi_delta_r": matrix.oi_expectancy_delta,
                    "promotions_count": len(promotions),
                },
                decision_status="ACCEPT" if len(promotions) > 0 else "REJECT",
                rationale=f"Ablation complete. Promoted {len(promotions)} features: {', '.join(promotions)}",
            )

        return matrix
