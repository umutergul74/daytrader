"""Counterfactual Shadow Filter Evaluation Engine.

Analyzes offline what trade performance would have been if specific Phase 4 microstructure
confirmations (CVD, OI, Liquidations) had been strictly required on Champion trades.
"""

from typing import Dict, List, Optional, Any, Callable
from pydantic import BaseModel, Field

from quant_platform.domain.trade import TradeRecord


class CounterfactualFilterResult(BaseModel):
    """Performance evaluation of a single counterfactual filter."""
    filter_name: str
    description: str
    original_trade_count: int
    filtered_trade_count: int
    trade_reduction_pct: float
    original_win_rate: float
    filtered_win_rate: float
    original_profit_factor: float
    filtered_profit_factor: float
    original_expectancy_r: float
    filtered_expectancy_r: float
    expectancy_delta_r: float
    marginal_edge_status: str # ACCEPT, REJECT, INCONCLUSIVE


class CounterfactualStudyReport(BaseModel):
    """Consolidated counterfactual study report across multiple filters."""
    strategy_id: str
    total_trades_analyzed: int
    baseline_win_rate: float
    baseline_profit_factor: float
    baseline_expectancy_r: float
    filter_evaluations: List[CounterfactualFilterResult] = Field(default_factory=list)


class CounterfactualAnalyzer:
    """Evaluates hypothetical microstructure filtering on actual executed trades."""

    @staticmethod
    def evaluate_filter(
        trades_with_features: List[Dict[str, Any]],
        filter_fn: Callable[[Dict[str, Any]], bool],
        filter_name: str,
        description: str,
    ) -> CounterfactualFilterResult:
        """Run counterfactual simulation for a single boolean filter condition."""
        total_n = len(trades_with_features)
        if total_n == 0:
            return CounterfactualFilterResult(
                filter_name=filter_name,
                description=description,
                original_trade_count=0,
                filtered_trade_count=0,
                trade_reduction_pct=0.0,
                original_win_rate=0.0,
                filtered_win_rate=0.0,
                original_profit_factor=0.0,
                filtered_profit_factor=0.0,
                original_expectancy_r=0.0,
                filtered_expectancy_r=0.0,
                expectancy_delta_r=0.0,
                marginal_edge_status="INCONCLUSIVE",
            )

        # Baseline metrics
        orig_wins = sum(1 for t in trades_with_features if t["net_pnl"] > 0)
        orig_wr = (orig_wins / total_n) * 100.0
        orig_win_pnl = sum(t["net_pnl"] for t in trades_with_features if t["net_pnl"] > 0)
        orig_loss_pnl = abs(sum(t["net_pnl"] for t in trades_with_features if t["net_pnl"] < 0))
        orig_pf = (orig_win_pnl / max(0.01, orig_loss_pnl)) if orig_loss_pnl > 0 else (orig_win_pnl if orig_win_pnl > 0 else 0.0)
        orig_exp = sum(t.get("r_multiple", 0.0) for t in trades_with_features) / total_n

        # Filtered trades
        passed_trades = [t for t in trades_with_features if filter_fn(t)]
        filtered_n = len(passed_trades)
        reduction_pct = ((total_n - filtered_n) / total_n) * 100.0

        if filtered_n == 0:
            return CounterfactualFilterResult(
                filter_name=filter_name,
                description=description,
                original_trade_count=total_n,
                filtered_trade_count=0,
                trade_reduction_pct=100.0,
                original_win_rate=orig_wr,
                filtered_win_rate=0.0,
                original_profit_factor=0.0,
                filtered_profit_factor=0.0,
                original_expectancy_r=orig_exp,
                filtered_expectancy_r=0.0,
                expectancy_delta_r=-orig_exp,
                marginal_edge_status="REJECT",
            )

        filt_wins = sum(1 for t in passed_trades if t["net_pnl"] > 0)
        filt_wr = (filt_wins / filtered_n) * 100.0
        filt_win_pnl = sum(t["net_pnl"] for t in passed_trades if t["net_pnl"] > 0)
        filt_loss_pnl = abs(sum(t["net_pnl"] for t in passed_trades if t["net_pnl"] < 0))
        filt_pf = (filt_win_pnl / max(0.01, filt_loss_pnl)) if filt_loss_pnl > 0 else (filt_win_pnl if filt_win_pnl > 0 else 0.0)
        filt_exp = sum(t.get("r_multiple", 0.0) for t in passed_trades) / filtered_n
        exp_delta = filt_exp - orig_exp

        status = "ACCEPT" if (exp_delta >= 0.08 and filt_pf >= orig_pf and filtered_n >= 10) else ("CONDITIONAL" if exp_delta > 0 else "REJECT")

        return CounterfactualFilterResult(
            filter_name=filter_name,
            description=description,
            original_trade_count=total_n,
            filtered_trade_count=filtered_n,
            trade_reduction_pct=reduction_pct,
            original_win_rate=orig_wr,
            filtered_win_rate=filt_wr,
            original_profit_factor=orig_pf,
            filtered_profit_factor=filt_pf,
            original_expectancy_r=orig_exp,
            filtered_expectancy_r=filt_exp,
            expectancy_delta_r=exp_delta,
            marginal_edge_status=status,
        )

    @classmethod
    def run_standard_counterfactual_suite(
        cls,
        strategy_id: str,
        trades_with_features: List[Dict[str, Any]],
    ) -> CounterfactualStudyReport:
        """Runs the standard suite of Phase 4 microstructure counterfactual filters."""
        evals = [
            cls.evaluate_filter(
                trades_with_features,
                lambda t: (t.get("direction") == "LONG" and t.get("cvd_bullish_divergence", False)) or (t.get("direction") == "SHORT" and t.get("cvd_bearish_divergence", False)),
                "CVD_DIVERGENCE_REQUIRED",
                "Require Bullish/Bearish CVD Divergence at entry candle",
            ),
            cls.evaluate_filter(
                trades_with_features,
                lambda t: (t.get("direction") == "LONG" and t.get("joint_price_oi_regime") == "LONG_BUILDUP") or (t.get("direction") == "SHORT" and t.get("joint_price_oi_regime") == "SHORT_BUILDUP"),
                "OI_BUILDUP_REQUIRED",
                "Require directional Open Interest buildup regime at entry",
            ),
            cls.evaluate_filter(
                trades_with_features,
                lambda t: bool(t.get("is_liquidation_burst", False)),
                "LIQUIDATION_BURST_REQUIRED",
                "Require high-volume liquidation burst within entry window",
            ),
            cls.evaluate_filter(
                trades_with_features,
                lambda t: ((t.get("direction") == "LONG" and t.get("trade_imbalance_1m", 0.0) > 0.05) or (t.get("direction") == "SHORT" and t.get("trade_imbalance_1m", 0.0) < -0.05)),
                "TRADE_IMBALANCE_DIRECTION_CONFIRMED",
                "Require 1m trade imbalance confirming trade direction",
            ),
        ]

        total_n = len(trades_with_features)
        orig_wins = sum(1 for t in trades_with_features if t["net_pnl"] > 0)
        orig_wr = (orig_wins / max(1, total_n)) * 100.0
        orig_win_pnl = sum(t["net_pnl"] for t in trades_with_features if t["net_pnl"] > 0)
        orig_loss_pnl = abs(sum(t["net_pnl"] for t in trades_with_features if t["net_pnl"] < 0))
        orig_pf = (orig_win_pnl / max(0.01, orig_loss_pnl)) if orig_loss_pnl > 0 else (orig_win_pnl if orig_win_pnl > 0 else 0.0)
        orig_exp = sum(t.get("r_multiple", 0.0) for t in trades_with_features) / max(1, total_n)

        return CounterfactualStudyReport(
            strategy_id=strategy_id,
            total_trades_analyzed=total_n,
            baseline_win_rate=orig_wr,
            baseline_profit_factor=orig_pf,
            baseline_expectancy_r=orig_exp,
            filter_evaluations=evals,
        )
